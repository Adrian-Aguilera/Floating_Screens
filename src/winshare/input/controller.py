"""Dispatch remote input and release held keys and buttons on session exit."""

from .keyboard import Keyboard
from .mouse import Mouse


class InputController:
    def __init__(self):
        self.mouse = Mouse()
        self.keyboard = Keyboard()

    def handle(self, message: dict):
        kind = message.get("type")
        if kind == "key":
            self.keyboard.handle(message)
        elif kind in ("move", "button", "wheel"):
            self.mouse.handle(message)
        elif kind == "release":
            self.release()
        else:
            raise ValueError("Evento de entrada desconocido.")

    def release(self):
        self.mouse.release()
        self.keyboard.release()
