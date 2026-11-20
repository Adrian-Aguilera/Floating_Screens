"""Bounded control and video records for protocol version 2."""

import json
import struct
from typing import BinaryIO

PORT = 49731
VIDEO_PORT = 49732
VERSION = 2
MAX_MESSAGE = 16 * 1024
MAX_FRAME = 2 * 1024 * 1024


def encode(kind: str, **fields: object) -> bytes:
    record = json.dumps({"type": kind, **fields}, separators=(",", ":")).encode() + b"\n"
    if len(record) > MAX_MESSAGE:
        raise ValueError("Mensaje demasiado largo.")
    return record


def receive(stream: BinaryIO) -> dict | None:
    line = stream.readline(MAX_MESSAGE + 1)
    if not line:
        return None
    if len(line) > MAX_MESSAGE or not line.endswith(b"\n"):
        raise ValueError("Mensaje incompleto o demasiado largo.")
    message = json.loads(line)
    if not isinstance(message, dict):
        raise ValueError("Mensaje inválido.")
    return message


def video_packet(frame: bytes) -> bytes:
    if not 0 < len(frame) <= MAX_FRAME:
        raise ValueError("Tamaño de cuadro inválido.")
    return struct.pack("!I", len(frame)) + frame


def receive_frame(stream: BinaryIO) -> bytes | None:
    header = stream.read(4)
    if not header:
        return None
    if len(header) != 4:
        raise ValueError("Cabecera de video incompleta.")
    size, = struct.unpack("!I", header)
    if size == 0:
        return b""
    if size > MAX_FRAME:
        raise ValueError("Tamaño de cuadro inválido.")
    frame = stream.read(size)
    if len(frame) != size:
        raise ValueError("Cuadro incompleto.")
    return frame
