from mathutils import Quaternion, Vector
from typing import List

from .. binary_utils import *
from .. common import *


def read_keyframes_climax(fd, keyframes_num) -> List[AnmKeyframe]:
    keyframes: List[AnmKeyframe] = []
    bone_id = -1

    pos_offset = Vector(read_float32(fd, 3))
    pos_scale = Vector(read_float32(fd, 3))

    for kf_id in range(keyframes_num):
        prev_frame = read_uint32(fd)
        time = read_float32(fd)

        if prev_frame & 0x3F000000:
            bone_id = bone_id + 1 if time == 0.0 else 0
        else:
            bone_id = keyframes[kf_id - prev_frame // 20].bone_id

        keyframes.append(AnmKeyframe(time, bone_id, Vector(), Quaternion()))

    for kf_id in range(keyframes_num):
        compressed1 = read_uint32(fd)
        compressed2 = read_uint16(fd)

        qx = ((compressed1 >> 20) - 2048.0) / 2047.0
        qy = (((compressed1 >> 8) & 0xFFF) - 2048.0) / 2047.0
        qz = ((((compressed1 * 16) & 0xFFF) | (compressed2 >> 12)) - 2048.0) / 2047.0
        qw = ((compressed2 & 0xFFF) - 2048.0 ) / 2047.0

        keyframes[kf_id].pos = Vector(read_uint16(fd, 3)) / 65535.0 * pos_scale + pos_offset
        keyframes[kf_id].rot = Quaternion((qw, qx, qy, qz))

    return keyframes


def write_keyframes_climax(fd, keyframes: List[AnmKeyframe]):
    prev_frame_offs = {}

    pos_offset_x, pos_scale_x = calculate_linear_scale(tuple(kf.pos.x for kf in keyframes), True)
    pos_offset_y, pos_scale_y = calculate_linear_scale(tuple(kf.pos.y for kf in keyframes), True)
    pos_offset_z, pos_scale_z = calculate_linear_scale(tuple(kf.pos.z for kf in keyframes), True)

    pos_offset = Vector((pos_offset_x, pos_offset_y, pos_offset_z))
    pos_scale = Vector((pos_scale_x, pos_scale_y, pos_scale_z))

    write_float32(fd, pos_offset)
    write_float32(fd, pos_scale)

    for kf_id, kf in enumerate(keyframes):
        if kf.bone_id not in prev_frame_offs:
            write_uint32(fd, KEYFRAME_PARENT_NONE_OFFSET)
        else:
            write_uint32(fd, (kf_id - prev_frame_offs[kf.bone_id]) * 20)
        prev_frame_offs[kf.bone_id] = kf_id

        write_float32(fd, kf.time)

    for kf in keyframes:
        qx = round((kf.rot.x * 2047.0) + 2048.0)
        qy = round((kf.rot.y * 2047.0) + 2048.0)
        qz = round((kf.rot.z * 2047.0) + 2048.0)
        qw = round((kf.rot.w * 2047.0) + 2048.0)

        compressed1 = (qx << 20) | (qy << 8) | ((qz & 0xFFF0) >> 4)
        compressed2 = ((qz & 0x0F) << 12) | (qw & 0xFFF)

        write_uint32(fd, compressed1)
        write_uint16(fd, compressed2)

        pos = Vector((v1/v2 for v1, v2 in zip(kf.pos - pos_offset, pos_scale)))
        write_uint16(fd, (round(pos.x * 65535), round(pos.y * 65535), round(pos.z * 65535)))
