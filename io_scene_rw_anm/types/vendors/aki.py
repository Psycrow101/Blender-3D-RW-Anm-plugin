from mathutils import Quaternion, Vector
from typing import List

from .. binary_utils import *
from .. common import *


def read_keyframes_aki_compressed_rot(fd, keyframes_num) -> List[AnmKeyframe]:
    keyframes: List[AnmKeyframe] = []
    frame_offs = []
    bone_id = -1

    for kf_id in range(keyframes_num):
        frame_offs.append(kf_id * 16)
        time = read_float32(fd)
        prev_frame_off = read_uint32(fd)
        rot = read_float16(fd, 4)
        rot = Quaternion((rot[3], rot[0], rot[1], rot[2]))

        if time == 0.0:
            bone_id = bone_id + 1
        else:
            prev_kf_id = frame_offs.index(prev_frame_off)
            bone_id = keyframes[prev_kf_id].bone_id

        keyframes.append(AnmKeyframe(time, bone_id, None, rot))

    return keyframes


def read_keyframes_aki_compressed_pos(fd, keyframes_num) -> List[AnmKeyframe]:
    keyframes: List[AnmKeyframe] = []
    frame_offs = []
    bone_id = -1

    for kf_id in range(keyframes_num):
        frame_offs.append(kf_id * 16)
        time = read_float32(fd)
        prev_frame_off = read_uint32(fd)
        pos = Vector(read_float16(fd, 3))

        if time == 0.0:
            bone_id = bone_id + 1
        else:
            prev_kf_id = frame_offs.index(prev_frame_off)
            bone_id = keyframes[prev_kf_id].bone_id

        keyframes.append(AnmKeyframe(time, bone_id, pos, None))

    pos_offset = Vector(read_float32(fd, 3))
    pos_scale = Vector(read_float32(fd, 3))
    for kf in keyframes:
        kf.pos *= pos_scale
        kf.pos += pos_offset

    return keyframes


def write_keyframes_aki_compressed_rot(fd, keyframes: List[AnmKeyframe]):
    prev_frame_offs = {}

    for kf_id, kf in enumerate(keyframes):
        prev_frame_offs[kf.bone_id] = kf_id * 16

    for kf_id, kf in enumerate(keyframes):
        write_float32(fd, kf.time)
        write_uint32(fd, prev_frame_offs[kf.bone_id])
        write_float16(fd, (kf.rot.x, kf.rot.y, kf.rot.z, kf.rot.w))

        prev_frame_offs[kf.bone_id] = kf_id * 16


def write_keyframes_aki_compressed_pos(fd, keyframes: List[AnmKeyframe]):
    prev_frame_offs = {}

    for kf_id, kf in enumerate(keyframes):
        prev_frame_offs[kf.bone_id] = kf_id * 16

    pos_offset_x, pos_scale_x = calculate_linear_scale(tuple(kf.pos.x for kf in keyframes))
    pos_offset_y, pos_scale_y = calculate_linear_scale(tuple(kf.pos.y for kf in keyframes))
    pos_offset_z, pos_scale_z = calculate_linear_scale(tuple(kf.pos.z for kf in keyframes))

    pos_offset = Vector((pos_offset_x, pos_offset_y, pos_offset_z))
    pos_scale = Vector((pos_scale_x, pos_scale_y, pos_scale_z))

    for kf_id, kf in enumerate(keyframes):
        write_float32(fd, kf.time)
        write_uint32(fd, prev_frame_offs[kf.bone_id])
        write_float16(fd, Vector((v1/v2 for v1, v2 in zip(kf.pos - pos_offset, pos_scale))))

        prev_frame_offs[kf.bone_id] = kf_id * 16

    write_float32(fd, pos_offset)
    write_float32(fd, pos_scale)
