"""Bounded, newline-delimited messages carried inside the TLS session."""

import json
from typing import BinaryIO

PORT = 49731
MAX_MESSAGE = 512


def encode(kind: str, **fields: object) -> bytes:
    return json.dumps({"type": kind, **fields}, separators=(",", ":")).encode() + b"\n"


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
