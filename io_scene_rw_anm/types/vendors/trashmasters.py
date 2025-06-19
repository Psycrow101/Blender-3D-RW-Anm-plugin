from mathutils import Quaternion, Vector
from typing import List

from .. binary_utils import *
from .. common import *


def read_keyframes_tm(fd, keyframes_num) -> List[AnmKeyframe]:
    keyframes: List[AnmKeyframe] = []
    frame_offs = []
    bone_id = -1
    next_frame_off = 0

    keyframes_with_pos_num = read_uint32(fd)
    flag = read_uint8(fd)

    if flag & 1:
        start_bone_id = read_uint32(fd)
        start_bone_name = read_string(fd, 64)
        bone_id += start_bone_id
    else:
        start_bone_id = 0

    pos_scale = Vector(read_float32(fd, 3))
    pos_offset = Vector(read_float32(fd, 3))

    for _ in range(keyframes_num):
        frame_offs.append(next_frame_off)
        kf_type = read_uint8(fd)
        time = read_float32(fd)
        rot = read_float16(fd, 4)
        rot = Quaternion((rot[3], rot[0], rot[1], rot[2]))

        if kf_type == 0:
            pos = None
            next_frame_off += 18

        elif kf_type == 1:
            pos = Vector(read_float16(fd, 3)) * pos_scale + pos_offset
            next_frame_off += 24

        elif kf_type == 2:
            pos = read_float32(fd, 3)
            next_frame_off += 30

        prev_frame_off = read_uint32(fd)

        if prev_frame_off == 0:
            bone_id = bone_id + 1 if time == 0.0 else start_bone_id
        else:
            prev_kf_id = frame_offs.index(prev_frame_off)
            bone_id = keyframes[prev_kf_id].bone_id

        keyframes.append(AnmKeyframe(time, bone_id, pos, rot))

    return keyframes


def read_keyframes_tm_compressed_rot(fd, keyframes_num) -> List[AnmKeyframe]:
    keyframes: List[AnmKeyframe] = []
    frame_offs = []
    bone_id = -1

    for kf_id in range(keyframes_num):
        frame_offs.append(kf_id * 16)
        time = read_float32(fd)
        rot = read_int16(fd, 4)
        rot = Quaternion((rot[3] / 32767, rot[0] / 32767, rot[1] / 32767, rot[2] / 32767))
        prev_frame_off = read_uint32(fd)

        if prev_frame_off & 0x3F000000:
            bone_id = bone_id + 1 if time == 0.0 else 0
        else:
            prev_kf_id = frame_offs.index(prev_frame_off)
            bone_id = keyframes[prev_kf_id].bone_id

        keyframes.append(AnmKeyframe(time, bone_id, None, rot))

    return keyframes


def write_keyframes_tm_compressed_rot(fd, keyframes: List[AnmKeyframe]):
    prev_frame_offs = {}

    for kf_id, kf in enumerate(keyframes):
        write_float32(fd, kf.time)
        write_int16(fd, (
            int(kf.rot.x * 32767),
            int(kf.rot.y * 32767),
            int(kf.rot.z * 32767),
            int(kf.rot.w * 32767))
        )

        if kf.bone_id not in prev_frame_offs:
            write_uint32(fd, KEYFRAME_PARENT_NONE_OFFSET)
        else:
            write_uint32(fd, prev_frame_offs[kf.bone_id])
        prev_frame_offs[kf.bone_id] = kf_id * 16
