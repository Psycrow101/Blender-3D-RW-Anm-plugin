from mathutils import Quaternion, Vector
from typing import List

from . binary_utils import *
from . common import *


class Anm8ingKeyframe(AnmKeyframe):
    def is_indexed_bones(self) -> bool:
        return False

    def is_pose_space(self) -> bool:
        return True


def read_keyframes_8ing(fd, keyframes_num) -> List[Anm8ingKeyframe]:
    keyframes: List[Anm8ingKeyframe] = []

    for _ in range(keyframes_num):
        rot = read_int16(fd, 4)
        rot = Quaternion((rot[3] / 8192, rot[0] / 8192, rot[1] / 8192, rot[2] / 8192))
        pos = Vector(v / 8192 for v in read_int16(fd, 3))
        bone_id = read_uint16(fd)
        time = read_float32(fd)
        prev_frame_off = read_uint32(fd)

        keyframes.append(Anm8ingKeyframe(time, bone_id, pos, rot))

    return keyframes


def write_keyframes_8ing(fd, keyframes: List[AnmKeyframe]):
    prev_frame_offs = {}

    for kf_id, kf in enumerate(keyframes):
        write_int16(fd, (
            int(kf.rot.x * 8192),
            int(kf.rot.y * 8192),
            int(kf.rot.z * 8192),
            int(kf.rot.w * 8192))
        )
        write_int16(fd, (int(v * 8192) for v in kf.pos))
        write_uint16(fd, kf.bone_id)
        write_float32(fd, kf.time)

        if kf.time == 0.0:
            write_uint32(fd, KEYFRAME_PARENT_NONE_OFFSET)
        else:
            write_uint32(fd, prev_frame_offs[kf.bone_id])

        prev_frame_offs[kf.bone_id] = kf_id * 24
