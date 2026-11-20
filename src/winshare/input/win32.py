"""Native Windows input primitives."""

import ctypes
from ctypes import wintypes

ULONG_PTR = ctypes.c_size_t
user32 = ctypes.WinDLL("user32", use_last_error=True)


class MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG), ("dy", wintypes.LONG),
        ("data", wintypes.DWORD), ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD), ("extra", ULONG_PTR),
    ]


class KeyboardInput(ctypes.Structure):
    _fields_ = [
        ("vk", wintypes.WORD), ("scan", wintypes.WORD),
        ("flags", wintypes.DWORD), ("time", wintypes.DWORD),
        ("extra", ULONG_PTR),
    ]


class InputValue(ctypes.Union):
    _fields_ = [("mouse", MouseInput), ("keyboard", KeyboardInput)]


class Input(ctypes.Structure):
    _fields_ = [("kind", wintypes.DWORD), ("value", InputValue)]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(Input), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT


def send(event: Input):
    if user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(Input)) != 1:
        raise OSError("Windows rechazó el evento de entrada.")


def mouse(flags: int, x: int = 0, y: int = 0, data: int = 0):
    send(Input(0, InputValue(mouse=MouseInput(x, y, data, flags, 0, 0))))


def keyboard(vk: int, extended: bool, pressed: bool):
    flags = int(extended) | (0 if pressed else 0x0002)
    send(Input(1, InputValue(keyboard=KeyboardInput(vk, 0, flags, 0, 0))))
