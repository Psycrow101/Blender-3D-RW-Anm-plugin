import struct


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
