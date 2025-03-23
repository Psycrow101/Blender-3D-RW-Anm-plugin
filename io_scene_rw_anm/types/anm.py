from dataclasses import dataclass
from mathutils import Quaternion, Vector
from os import SEEK_SET, SEEK_CUR, SEEK_END
from typing import List

from . binary_utils import *
from . common import *
from . eighting import *
from . climax import *
from . trashmasters import *

ANM_CHUNK_ID = 0x1b
ANM_ANIMATION_VERSION = 0x100

KEYFRAME_TYPE_UNCOMPRESSED   = 1
KEYFRAME_TYPE_COMPRESSED     = 2
KEYFRAME_TYPE_TM             = 0x64
KEYFRAME_TYPE_COMPRESSED_ROT = 0x100
KEYFRAME_TYPE_8ING           = 0x400
KEYFRAME_TYPE_CLIMAX         = 0x1103


def read_keyframes_uncompressed(fd, keyframes_num) -> List[AnmKeyframe]:
    keyframes: List[AnmKeyframe] = []
    frame_offs = []
    bone_id = -1

    for kf_id in range(keyframes_num):
        frame_offs.append(kf_id * 36)
        time = read_float32(fd)
        rot = read_float32(fd, 4)
        rot = Quaternion((rot[3], rot[0], rot[1], rot[2]))
        pos = Vector(read_float32(fd, 3))
        prev_frame_off = read_uint32(fd)

        if prev_frame_off & 0x3F000000:
            bone_id = bone_id + 1 if time == 0.0 else 0
        else:
            prev_kf_id = frame_offs.index(prev_frame_off)
            bone_id = keyframes[prev_kf_id].bone_id

        keyframes.append(AnmKeyframe(time, bone_id, pos, rot))

    return keyframes


def read_keyframes_compressed(fd, keyframes_num) -> List[AnmKeyframe]:
    keyframes: List[AnmKeyframe] = []
    frame_offs = []
    bone_id = -1

    for kf_id in range(keyframes_num):
        frame_offs.append(kf_id * 24)
        time = read_float32(fd)
        rot = read_float16(fd, 4)
        rot = Quaternion((rot[3], rot[0], rot[1], rot[2]))
        pos = Vector(read_float16(fd, 3))
        prev_frame_off = read_uint32(fd)

        if prev_frame_off & 0x3F000000:
            bone_id = bone_id + 1 if time == 0.0 else 0
        else:
            prev_kf_id = frame_offs.index(prev_frame_off)
            bone_id = keyframes[prev_kf_id].bone_id

        keyframes.append(AnmKeyframe(time, bone_id, pos, rot))

    pos_offset = Vector(read_float32(fd, 3))
    pos_scale = Vector(read_float32(fd, 3))
    for kf in keyframes:
        kf.pos *= pos_scale
        kf.pos += pos_offset

    return keyframes


def write_keyframes_uncompressed(fd, keyframes: List[AnmKeyframe]):
    prev_frame_offs = {}

    for kf_id, kf in enumerate(keyframes):
        write_float32(fd, kf.time)
        write_float32(fd, (kf.rot.x, kf.rot.y, kf.rot.z, kf.rot.w))
        write_float32(fd, kf.pos)

        if kf.bone_id not in prev_frame_offs:
            write_uint32(fd, KEYFRAME_PARENT_NONE_OFFSET)
        else:
            write_uint32(fd, prev_frame_offs[kf.bone_id])
        prev_frame_offs[kf.bone_id] = kf_id * 36


def write_keyframes_compressed(fd, keyframes: List[AnmKeyframe]):
    prev_frame_offs = {}

    pos_offset_x, pos_scale_x = calculate_linear_scale(tuple(kf.pos.x for kf in keyframes))
    pos_offset_y, pos_scale_y = calculate_linear_scale(tuple(kf.pos.y for kf in keyframes))
    pos_offset_z, pos_scale_z = calculate_linear_scale(tuple(kf.pos.z for kf in keyframes))

    pos_offset = Vector((pos_offset_x, pos_offset_y, pos_offset_z))
    pos_scale = Vector((pos_scale_x, pos_scale_y, pos_scale_z))

    for kf_id, kf in enumerate(keyframes):
        write_float32(fd, kf.time)
        write_float16(fd, (kf.rot.x, kf.rot.y, kf.rot.z, kf.rot.w))
        write_float16(fd, Vector((v1/v2 for v1, v2 in zip(kf.pos - pos_offset, pos_scale))))

        if kf.bone_id not in prev_frame_offs:
            write_uint32(fd, KEYFRAME_PARENT_NONE_OFFSET)
        else:
            write_uint32(fd, prev_frame_offs[kf.bone_id])
        prev_frame_offs[kf.bone_id] = kf_id * 24

    write_float32(fd, pos_offset)
    write_float32(fd, pos_scale)


def read_anm_animation(fd) -> AnmAnimation:
    version, keyframe_type, keyframes_num, flags = read_uint32(fd, 4)
    duration = read_float32(fd)
    keyframes: List[AnmKeyframe] = []

    # RW common
    if keyframe_type == KEYFRAME_TYPE_UNCOMPRESSED:
        keyframes = read_keyframes_uncompressed(fd, keyframes_num)
    elif keyframe_type == KEYFRAME_TYPE_COMPRESSED:
        keyframes = read_keyframes_compressed(fd, keyframes_num)
    # TrashMasters (TM Studios)
    elif keyframe_type == KEYFRAME_TYPE_TM:
        keyframes = read_keyframes_tm(fd, keyframes_num)
    elif keyframe_type == KEYFRAME_TYPE_COMPRESSED_ROT:
        keyframes = read_keyframes_compressed_rot(fd, keyframes_num)
    # 8ing
    elif keyframe_type == KEYFRAME_TYPE_8ING:
        keyframes = read_keyframes_8ing(fd, keyframes_num)
    # Climax Studios
    elif keyframe_type == KEYFRAME_TYPE_CLIMAX:
        keyframes = read_keyframes_climax(fd, keyframes_num)

    return AnmAnimation(version, keyframe_type, flags, duration, keyframes)


def write_anm_animation(fd, animation: AnmAnimation):
    write_uint32(fd, (animation.version, animation.keyframe_type, len(animation.keyframes), animation.flags))
    write_float32(fd, animation.duration)

    if animation.keyframe_type == KEYFRAME_TYPE_UNCOMPRESSED:
        write_keyframes_uncompressed(fd, animation.keyframes)
    elif animation.keyframe_type == KEYFRAME_TYPE_COMPRESSED:
        write_keyframes_compressed(fd, animation.keyframes)
    elif animation.keyframe_type == KEYFRAME_TYPE_COMPRESSED_ROT:
        write_keyframes_compressed_rot(fd, animation.keyframes)
    elif animation.keyframe_type == KEYFRAME_TYPE_CLIMAX:
        write_keyframes_climax(fd, animation.keyframes)


@dataclass
class Anm:
    chunks: List[RWAnmChunk]

    @classmethod
    def read(cls, fd):
        fd.seek(0, SEEK_END)
        file_size = fd.tell()
        fd.seek(0, SEEK_SET)

        chunks: List[RWAnmChunk] = []

        while fd.tell() < file_size:
            chunk_id, chunk_size, chunk_version = read_uint32(fd, 3)
            if chunk_id == ANM_CHUNK_ID:
                anm_chunk = RWAnmChunk(chunk_id, chunk_version, read_anm_animation(fd))
                chunks.append(anm_chunk)
            else:
                fd.seek(chunk_size, SEEK_CUR)

        return cls(chunks)

    @classmethod
    def load(cls, filepath):
        with open(filepath, 'rb') as fd:
            return cls.read(fd)

    def write(self, fd):
        for anm_chunk in self.chunks:
            chunk_size = 20 + len(anm_chunk.animation.keyframes) * 36
            write_uint32(fd, (anm_chunk.chunk_id, chunk_size, anm_chunk.version))
            write_anm_animation(fd, anm_chunk.animation)

    def save(self, filepath):
        with open(filepath, 'wb') as fd:
            return self.write(fd)
