"""Read and optionally consume native mouse and keyboard events."""

import ctypes as ct
from ctypes import wintypes as wt

from ..display.windows import bind
from .win32 import ULONG_PTR

RESULT = ct.c_ssize_t
CALLBACK = ct.WINFUNCTYPE(RESULT, ct.c_int, wt.WPARAM, wt.LPARAM)
install = bind("SetWindowsHookExW", wt.HANDLE, ct.c_int, CALLBACK, wt.HMODULE, wt.DWORD)
remove = bind("UnhookWindowsHookEx", wt.BOOL, wt.HANDLE)
next_hook = bind("CallNextHookEx", RESULT, wt.HANDLE, ct.c_int, wt.WPARAM, wt.LPARAM)
set_cursor = bind("SetCursorPos", wt.BOOL, ct.c_int, ct.c_int)
module = ct.WinDLL("kernel32").GetModuleHandleW
module.argtypes = [wt.LPCWSTR]
module.restype = wt.HMODULE


class MouseEvent(ct.Structure):
    _fields_ = [("point", wt.POINT), ("data", wt.DWORD), ("flags", wt.DWORD),
                ("time", wt.DWORD), ("extra", ULONG_PTR)]


class KeyEvent(ct.Structure):
    _fields_ = [("vk", wt.DWORD), ("scan", wt.DWORD), ("flags", wt.DWORD),
                ("time", wt.DWORD), ("extra", ULONG_PTR)]


class DesktopHooks:
    def __init__(self, mouse, keyboard):
        self.handles = []
        self.callbacks = (
            self._wrap(MouseEvent, 1, mouse),
            self._wrap(KeyEvent, 0x10, keyboard),
        )
        for kind, callback in zip((14, 13), self.callbacks):
            handle = install(kind, callback, module(None), 0)
            if not handle:
                self.close()
                raise OSError("No se pudieron activar los controles por borde.")
            self.handles.append(handle)

    @staticmethod
    def _wrap(event_type, injected_flag, handle):
        @CALLBACK
        def callback(code, message, address):
            if code == 0:
                event = ct.cast(address, ct.POINTER(event_type)).contents
                if not event.flags & injected_flag and handle(message, event):
                    return 1
            return next_hook(None, code, message, address)

        return callback

    def close(self):
        for handle in self.handles:
            remove(handle)
        self.handles.clear()
