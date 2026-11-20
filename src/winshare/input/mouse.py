"""Map normalized mouse positions onto the destination's primary display."""

from .win32 import mouse

BUTTONS = {1: (0x0002, 0x0004), 2: (0x0020, 0x0040), 3: (0x0008, 0x0010)}


class Mouse:
    def __init__(self):
        self._held: set[int] = set()

    def handle(self, message: dict):
        for axis in ("x", "y"):
            position = message.get(axis)
            if type(position) is not int or not 0 <= position <= 65535:
                raise ValueError("Posición del mouse inválida.")
        kind = message["type"]
        flags = 0x8001
        data = 0
        if kind == "button":
            button = message.get("button")
            pressed = message.get("down")
            if type(button) is not int or button not in BUTTONS or type(pressed) is not bool:
                raise ValueError("Botón del mouse inválido.")
            if pressed or button in self._held:
                flags |= BUTTONS[button][0 if pressed else 1]
        if kind == "wheel":
            data = message.get("delta")
            if type(data) is not int or not -1200 <= data <= 1200:
                raise ValueError("Desplazamiento del mouse inválido.")
            flags |= 0x0800

        mouse(flags, message["x"], message["y"], data)
        if kind == "button":
            if pressed:
                self._held.add(button)
            else:
                self._held.discard(button)

    def release(self):
        for button in self._held:
            try:
                mouse(BUTTONS[button][1])
            except OSError:
                pass
        self._held.clear()
