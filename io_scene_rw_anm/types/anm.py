from dataclasses import dataclass
from mathutils import Quaternion, Vector
from os import SEEK_SET, SEEK_CUR, SEEK_END
from typing import List

from . binary_utils import *
from . common import *

from . vendors.aki import *
from . vendors.eighting import *
from . vendors.climax import *
from . vendors.trashmasters import *

ANM_CHUNK_ID = 0x1b
ANM_ANIMATION_VERSION = 0x100


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

    reader_func = {
        # RW common
        KeyframeType.UNCOMPRESSED: read_keyframes_uncompressed,
        KeyframeType.COMPRESSED: read_keyframes_compressed,
        # AKI
        KeyframeType.AKI_COMPRESSED_ROT: read_keyframes_aki_compressed_rot,
        KeyframeType.AKI_COMPRESSED_POS: read_keyframes_aki_compressed_pos,
        # TrashMasters (TM Studios)
        KeyframeType.TM: read_keyframes_tm,
        KeyframeType.TM_COMPRESSED_ROT: read_keyframes_tm_compressed_rot,
        # 8ing
        KeyframeType.EIGHTING: read_keyframes_8ing,
        # Climax Studios
        KeyframeType.CLIMAX: read_keyframes_climax,
    }.get(keyframe_type)

    if reader_func:
        keyframes = reader_func(fd, keyframes_num)

    return AnmAnimation(version, keyframe_type, flags, duration, keyframes)


def write_anm_animation(fd, animation: AnmAnimation):
    write_uint32(fd, (animation.version, animation.keyframe_type, len(animation.keyframes), animation.flags))
    write_float32(fd, animation.duration)

    writer_func = {
        # RW common
        KeyframeType.UNCOMPRESSED: write_keyframes_uncompressed,
        KeyframeType.COMPRESSED: write_keyframes_compressed,
        # TrashMasters (TM Studios)
        KeyframeType.TM_COMPRESSED_ROT: write_keyframes_tm_compressed_rot,
        # Climax Studios
        KeyframeType.CLIMAX: write_keyframes_climax,
    }[animation.keyframe_type]

    writer_func(fd, animation.keyframes)


def read_anm_chunk(fd) -> RWAnmChunk:
    chunk_id, chunk_size, chunk_version = read_uint32(fd, 3)
    if chunk_id == ANM_CHUNK_ID:
        return RWAnmChunk(chunk_id, chunk_version, read_anm_animation(fd))
    else:
        fd.seek(chunk_size, SEEK_CUR)


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
            anm_chunk = read_anm_chunk(fd)
            if anm_chunk:
                chunks.append(anm_chunk)

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
