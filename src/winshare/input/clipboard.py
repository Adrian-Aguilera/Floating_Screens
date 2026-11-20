"""Synchronize Unicode clipboard text while a desktop handoff is active."""

import json
import tkinter as tk

from ctypes import wintypes as wt

from ..display.windows import bind

sequence = bind("GetClipboardSequenceNumber", wt.DWORD)
MAX_TEXT_BYTES = 12_000


def valid_text(value):
    return (isinstance(value, str) and "\x00" not in value
            and len(json.dumps(value, ensure_ascii=False).encode("utf-8", errors="surrogatepass"))
            <= MAX_TEXT_BYTES
            and not any(0xD800 <= ord(character) <= 0xDFFF for character in value))


class Clipboard:
    def __init__(self, root):
        self.root = root
        self.sequence = sequence()
        self.remote_text = None

    def changed(self, initial=False):
        current = sequence()
        if not initial and self.sequence == current:
            return None
        try:
            text = self.root.clipboard_get()
        except tk.TclError:
            return None
        self.sequence = current
        if valid_text(text) and text != self.remote_text:
            self.remote_text = None
            return text
        return None

    def apply(self, text):
        if not valid_text(text):
            raise ValueError("Texto de portapapeles inválido.")
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.sequence = sequence()
        self.remote_text = text
