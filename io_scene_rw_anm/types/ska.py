from dataclasses import dataclass
from mathutils import Quaternion, Vector

from . binary_utils import *
from . common import AnmAnimation, AnmKeyframe, KEYFRAME_PARENT_NONE_OFFSET


def read_keyframes_ska(fd, keyframes_num):
    keyframes = []
    frame_offs = []
    bone_id = -1

    for kf_id in range(keyframes_num):
        frame_offs.append(kf_id * 36)
        rot = read_float32(fd, 4)
        rot = Quaternion((-rot[3], rot[0], rot[1], rot[2]))
        pos = Vector(read_float32(fd, 3))
        time = read_float32(fd)
        prev_frame_off = read_uint32(fd)

        if prev_frame_off & 0x3F000000:
            bone_id = bone_id + 1 if time == 0.0 else 0
        else:
            prev_kf_id = frame_offs.index(prev_frame_off)
            bone_id = keyframes[prev_kf_id].bone_id

        keyframes.append(AnmKeyframe(time, bone_id, pos, rot))

    return keyframes


def write_keyframes_ska(fd, keyframes):
    prev_frame_offs = {}

    for kf_id, kf in enumerate(keyframes):
        write_float32(fd, (kf.rot.x, kf.rot.y, kf.rot.z, -kf.rot.w))
        write_float32(fd, kf.pos)
        write_float32(fd, kf.time)

        if kf.bone_id not in prev_frame_offs:
            write_uint32(fd, KEYFRAME_PARENT_NONE_OFFSET)
        else:
            write_uint32(fd, prev_frame_offs[kf.bone_id])
        prev_frame_offs[kf.bone_id] = kf_id * 36


def read_ska_animation(fd):
    keyframes_num, flags = read_uint32(fd, 2)
    duration = read_float32(fd)
    keyframes = read_keyframes_ska(fd, keyframes_num)

    return AnmAnimation(0, 0, flags, duration, keyframes)


def write_ska_animation(fd, animation: AnmAnimation):
    write_uint32(fd, (len(animation.keyframes), animation.flags))
    write_float32(fd, animation.duration)
    write_keyframes_ska(fd, animation.keyframes)


@dataclass
class Ska:
    animation: AnmAnimation

    @classmethod
    def read(cls, fd):
        animation = read_ska_animation(fd)
        return cls(animation)

    @classmethod
    def load(cls, filepath):
        with open(filepath, 'rb') as fd:
            return cls.read(fd)

    def write(self, fd):
        write_ska_animation(fd, self.animation)

    def save(self, filepath):
        with open(filepath, 'wb') as fd:
            return self.write(fd)
