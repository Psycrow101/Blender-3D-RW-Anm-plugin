from enum import IntEnum
from dataclasses import dataclass
from mathutils import Quaternion, Vector
from typing import List

KEYFRAME_PARENT_NONE_OFFSET = 0xFF30C9D8


class KeyframeType(IntEnum):
    UNCOMPRESSED       = 0x1
    COMPRESSED         = 0x2
    AKI_COMPRESSED_ROT = 0x8
    AKI_COMPRESSED_POS = 0x9
    TM                 = 0x64
    TM_COMPRESSED_ROT  = 0x100
    EIGHTING           = 0x400
    CLIMAX             = 0x1103


@dataclass
class AnmKeyframe:
    time: float
    bone_id: int
    pos: Vector
    rot: Quaternion

    def is_indexed_bones(self) -> bool:
        return True

    def is_pose_space(self) -> bool:
        return False


@dataclass
class AnmAnimation:
    version: int
    keyframe_type: int
    flags: int
    duration: float
    keyframes: List[AnmKeyframe]

    def is_mergable_with(self, other) -> bool:
        return sorted((self.keyframe_type, other.keyframe_type)) == [KeyframeType.AKI_COMPRESSED_ROT, KeyframeType.AKI_COMPRESSED_POS] \
            and self.duration == other.duration

    def merge_with(self, other):
        for other_kf in other.keyframes:
            merged_kf = next((kf for kf in self.keyframes if kf.time == other_kf.time and kf.bone_id == other_kf.bone_id), None)
            if merged_kf:
                if merged_kf.pos is None:
                    merged_kf.pos = other_kf.pos
                else:
                    merged_kf.rot = other_kf.rot
            else:
                self.keyframes.append(other_kf)


@dataclass
class RWAnmChunk:
    chunk_id: int
    version: int
    animation: AnmAnimation


def unpack_rw_lib_id(version):
    v = (version >> 14 & 0x3ff00) + 0x30000 | (version >> 16 & 0x3f)
    bin_ver = v & 0x3f
    min_rev = (v >> 8) & 0xf
    maj_rev = (v >> 12) & 0xf
    rw_ver = (v >> 16) & 0x7
    return rw_ver, maj_rev, min_rev, bin_ver


def pack_rw_lib_id(rw_ver, maj_rev, min_rev, bin_ver):
    ver = ((rw_ver & 0x7) << 16) | ((maj_rev & 0xf) << 12) | ((min_rev & 0xf) << 8) | (bin_ver & 0x3f)
    ver -= 0x30000
    b = ver & 0xff
    n = (ver >> 8) & 0xf
    j = (ver >> 12) & 0xf
    v = (ver >> 16) & 0xf
    return 0xffff | (b << 16) | (n << 22) | (j << 26) | (v << 30)


def calculate_linear_scale(data, unsigned=False):
    if not data:
        return 0, 1.0

    min_val, max_val = min(data), max(data)
    if max_val == min_val:
        return 0, max_val

    if unsigned:
        offset = min_val
        scale = max_val - offset
    else:
        offset = (min_val + max_val) / 2
        scale = max((abs(min_val), abs(max_val))) - abs(offset)
    return offset, scale
