from mathutils import Quaternion, Vector
from os import SEEK_SET, SEEK_CUR, SEEK_END
import struct
from dataclasses import dataclass

ANM_CHUNK_ID = 0x1b
ANM_ACTION_VERSION = 0x100
ANM_ACTION_PARENT_NONE_OFFSET = 0xFF30C9D8


def decode_float16(value):
    sign = -1.0 if (value >> 15) else 1.0
    if (value & 0x7FFF) == 0:
        return sign * 0.0
    exponent = ((value >> 11) & 15) - 15
    mantissa = (value & 0x07FF) / 0x800 + 1.0
    return sign * mantissa * 2**exponent


def read_float16(fd, num=1, en='<'):
    res = struct.unpack('%s%dH' % (en, num), fd.read(2 * num))
    res = tuple(map(decode_float16, res))
    return res if num > 1 else res[0]


def read_float32(fd, num=1, en='<'):
    res = struct.unpack('%s%df' % (en, num), fd.read(4 * num))
    return res if num > 1 else res[0]


def read_uint32(fd, num=1, en='<'):
    res = struct.unpack('%s%dI' % (en, num), fd.read(4 * num))
    return res if num > 1 else res[0]


def write_uint32(fd, vals, en='<'):
    data = vals if hasattr(vals, '__len__') else (vals, )
    data = struct.pack('%s%dI' % (en, len(data)), *data)
    fd.write(data)


def write_float32(fd, vals, en='<'):
    data = vals if hasattr(vals, '__len__') else (vals, )
    data = struct.pack('%s%df' % (en, len(data)), *data)
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


@dataclass
class AnmKeyframe:
    time: float
    bone_id: int
    pos: Vector
    rot: Quaternion


@dataclass
class AnmAction:
    version: int
    flags: int
    duration: float
    keyframes: []

    @classmethod
    def read(cls, fd):
        version, keyframe_type, keyframes_num, flags = read_uint32(fd, 4)
        duration = read_float32(fd)

        keyframes = []
        frame_offs = []
        bone_id = -1

        for kf_id in range(keyframes_num):
            time = read_float32(fd)
            if keyframe_type == 1:
                frame_offs.append(kf_id * 36)
                rot = read_float32(fd, 4)
                pos = Vector(read_float32(fd, 3))
            else:
                frame_offs.append(kf_id * 24)
                rot = read_float16(fd, 4)
                pos = Vector(read_float16(fd, 3))
            rot = Quaternion((rot[3], rot[0], rot[1], rot[2]))
            prev_frame_off = read_uint32(fd)

            if time == 0.0:
                bone_id += 1
            else:
                prev_kf_id = frame_offs.index(prev_frame_off)
                bone_id = keyframes[prev_kf_id].bone_id

            keyframes.append(AnmKeyframe(time, bone_id, pos, rot))

        if keyframe_type == 2:
            offset = Vector(read_float32(fd, 3))
            scalar = Vector(read_float32(fd, 3))
            for kf in keyframes:
                kf.pos *= scalar
                kf.pos += offset

        return cls(version, flags, duration, keyframes)


    def write(self, fd):
        write_uint32(fd, (self.version, 1, len(self.keyframes), self.flags))
        write_float32(fd, self.duration)

        prev_frame_offs = {}

        for kf_id, kf in enumerate(self.keyframes):
            write_float32(fd, kf.time)
            write_float32(fd, (kf.rot[1], kf.rot[2], kf.rot[3], kf.rot[0]))
            write_float32(fd, kf.pos)

            if kf.time == 0.0:
                write_uint32(fd, ANM_ACTION_PARENT_NONE_OFFSET)
            else:
                write_uint32(fd, prev_frame_offs[kf.bone_id])
            prev_frame_offs[kf.bone_id] = kf_id * 36


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
