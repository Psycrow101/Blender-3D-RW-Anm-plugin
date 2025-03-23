from dataclasses import dataclass
from os import SEEK_SET, SEEK_CUR
from typing import List

from . anm import read_anm_chunk
from . binary_utils import read_uint32
from . common import RWAnmChunk


@dataclass
class Tmo:
    chunks: List[RWAnmChunk]

    @classmethod
    def read(cls, fd):
        chunks: List[RWAnmChunk] = []

        chunks_num = read_uint32(fd)
        fd.seek(12, SEEK_CUR)

        for _ in range(chunks_num):
            chunk_size = read_uint32(fd)
            fd.seek(12, SEEK_CUR)
            next_chunk_pos = fd.tell() + chunk_size

            if chunk_size > 0:
                chunks.append(read_anm_chunk(fd))

            fd.seek(next_chunk_pos, SEEK_SET)

        return cls(chunks)

    @classmethod
    def load(cls, filepath):
        with open(filepath, 'rb') as fd:
            return cls.read(fd)
