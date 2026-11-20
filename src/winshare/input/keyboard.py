"""Translate and track keyboard events for a single control session."""

from .win32 import keyboard

MODIFIERS = {
    "Shift_L": 0xA0, "Shift_R": 0xA1,
    "Control_L": 0xA2, "Control_R": 0xA3,
    "Alt_L": 0xA4, "Alt_R": 0xA5,
}
EXTENDED_KEYS = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28,
                 0x2C, 0x2D, 0x2E, 0x5B, 0x5C, 0x5D, 0x6F, 0x90,
                 0xA3, 0xA5}


def virtual_key(keycode: int, keysym: str) -> tuple[int, bool]:
    vk = MODIFIERS.get(keysym, keycode)
    keypad = keysym.startswith("KP_")
    extended = keysym == "KP_Enter" or vk == 0x6F or (vk in EXTENDED_KEYS and not keypad)
    return vk, extended


class Keyboard:
    def __init__(self):
        self._held: dict[tuple[int, bool], None] = {}

    def handle(self, message: dict):
        vk = message.get("vk")
        pressed = message.get("down")
        extended = message.get("extended")
        if type(vk) is not int or not 8 <= vk <= 254:
            raise ValueError("Tecla inválida.")
        if type(pressed) is not bool or type(extended) is not bool:
            raise ValueError("Estado de tecla inválido.")
        key = (vk, extended)
        if pressed:
            keyboard(vk, extended, True)
            self._held[key] = None
        elif key in self._held:
            keyboard(vk, extended, False)
            self._held.pop(key)

    def release(self):
        for vk, extended in reversed(self._held):
            try:
                keyboard(vk, extended, False)
            except OSError:
                pass
        self._held.clear()
