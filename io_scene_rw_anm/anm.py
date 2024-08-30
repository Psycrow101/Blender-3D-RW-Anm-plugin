import struct
from mathutils import Quaternion, Vector
from os import SEEK_SET, SEEK_CUR, SEEK_END
from dataclasses import dataclass

ANM_CHUNK_ID = 0x1b
ANM_ACTION_VERSION = 0x100
ANM_ACTION_PARENT_NONE_OFFSET = 0xFF30C9D8

KEYFRAME_TYPE_UNCOMPRESSED = 1
KEYFRAME_TYPE_COMPRESSED   = 2
KEYFRAME_TYPE_CLIMAX       = 0x1103


def decode_float16(value):
    sign = -1.0 if (value >> 15) else 1.0
    if (value & 0x7FFF) == 0:
        return sign * 0.0
    exponent = ((value >> 11) & 15) - 15
    mantissa = (value & 0x07FF) / 0x800 + 1.0
    return sign * mantissa * 2**exponent


def encode_float16(value):
    if value < 0:
        sign = 1
        value = -value
    else:
        sign = 0

    if value == 0:
        return sign << 15

    exponent = 0
    while value < 1.0 and exponent > -15:
        value *= 2.0
        exponent -= 1
    exponent += 15
    mantissa = int((value - 1.0) * 0x800) & 0x07FF
    return (sign << 15) | (exponent << 11) | mantissa


def read_float16(fd, num=1, en='<'):
    res = struct.unpack('%s%dH' % (en, num), fd.read(2 * num))
    res = tuple(map(decode_float16, res))
    return res if num > 1 else res[0]


def read_float32(fd, num=1, en='<'):
    res = struct.unpack('%s%df' % (en, num), fd.read(4 * num))
    return res if num > 1 else res[0]


def read_uint16(fd, num=1, en='<'):
    res = struct.unpack('%s%dH' % (en, num), fd.read(2 * num))
    return res if num > 1 else res[0]


def read_uint32(fd, num=1, en='<'):
    res = struct.unpack('%s%dI' % (en, num), fd.read(4 * num))
    return res if num > 1 else res[0]


def write_float16(fd, vals, en='<'):
    data = vals if hasattr(vals, '__len__') else (vals, )
    data = struct.pack('%s%dH' % (en, len(data)), *tuple(map(encode_float16, vals)))
    fd.write(data)


def write_float32(fd, vals, en='<'):
    data = vals if hasattr(vals, '__len__') else (vals, )
    data = struct.pack('%s%df' % (en, len(data)), *data)
    fd.write(data)


def write_uint16(fd, vals, en='<'):
    data = vals if hasattr(vals, '__len__') else (vals, )
    data = struct.pack('%s%dH' % (en, len(data)), *data)
    fd.write(data)


def write_uint32(fd, vals, en='<'):
    data = vals if hasattr(vals, '__len__') else (vals, )
    data = struct.pack('%s%dI' % (en, len(data)), *data)
    fd.write(data)


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


def read_keyframes_uncompressed(fd, keyframes_num):
    keyframes = []
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


def read_keyframes_compressed(fd, keyframes_num):
    keyframes = []
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


def read_keyframes_climax(fd, keyframes_num):
    keyframes = []
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


def write_keyframes_uncompressed(fd, keyframes):
    prev_frame_offs = {}

    for kf_id, kf in enumerate(keyframes):
        write_float32(fd, kf.time)
        write_float32(fd, (kf.rot.x, kf.rot.y, kf.rot.z, kf.rot.w))
        write_float32(fd, kf.pos)

        if kf.bone_id not in prev_frame_offs:
            write_uint32(fd, ANM_ACTION_PARENT_NONE_OFFSET)
        else:
            write_uint32(fd, prev_frame_offs[kf.bone_id])
        prev_frame_offs[kf.bone_id] = kf_id * 36


def write_keyframes_compressed(fd, keyframes):
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
            write_uint32(fd, ANM_ACTION_PARENT_NONE_OFFSET)
        else:
            write_uint32(fd, prev_frame_offs[kf.bone_id])
        prev_frame_offs[kf.bone_id] = kf_id * 24

    write_float32(fd, pos_offset)
    write_float32(fd, pos_scale)


def write_keyframes_climax(fd, keyframes):
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
            write_uint32(fd, ANM_ACTION_PARENT_NONE_OFFSET)
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


@dataclass
class AnmKeyframe:
    time: float
    bone_id: int
    pos: Vector
    rot: Quaternion


@dataclass
class AnmAction:
    version: int
    keyframe_type: int
    flags: int
    duration: float
    keyframes: []

    @classmethod
    def read(cls, fd):
        version, keyframe_type, keyframes_num, flags = read_uint32(fd, 4)
        duration = read_float32(fd)

        keyframes = []
        if keyframe_type == KEYFRAME_TYPE_UNCOMPRESSED:
            keyframes = read_keyframes_uncompressed(fd, keyframes_num)
        elif keyframe_type == KEYFRAME_TYPE_COMPRESSED:
            keyframes = read_keyframes_compressed(fd, keyframes_num)
        elif keyframe_type == KEYFRAME_TYPE_CLIMAX:
            keyframes = read_keyframes_climax(fd, keyframes_num)

        return cls(version, keyframe_type, flags, duration, keyframes)


    def write(self, fd):
        write_uint32(fd, (self.version, self.keyframe_type, len(self.keyframes), self.flags))
        write_float32(fd, self.duration)

        if self.keyframe_type == KEYFRAME_TYPE_UNCOMPRESSED:
            write_keyframes_uncompressed(fd, self.keyframes)
        elif self.keyframe_type == KEYFRAME_TYPE_COMPRESSED:
            write_keyframes_compressed(fd, self.keyframes)
        elif self.keyframe_type == KEYFRAME_TYPE_CLIMAX:
            write_keyframes_climax(fd, self.keyframes)


@dataclass
class AnmChunk:
    chunk_id: int
    version: int
    action: AnmAction


@dataclass
class Anm:
    chunks: []

    @classmethod
    def read(cls, fd):
        fd.seek(0, SEEK_END)
        file_size = fd.tell()
        fd.seek(0, SEEK_SET)

        chunks = []

        while fd.tell() < file_size:
            chunk_id, chunk_size, chunk_version = read_uint32(fd, 3)
            if chunk_id == ANM_CHUNK_ID:
                anm_chunk = AnmChunk(chunk_id, chunk_version, AnmAction.read(fd))
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
            chunk_size = 20 + len(anm_chunk.action.keyframes) * 36
            write_uint32(fd, (anm_chunk.chunk_id, chunk_size, anm_chunk.version))
            anm_chunk.action.write(fd)


    def save(self, filepath):
        with open(filepath, 'wb') as fd:
            return self.write(fd)
