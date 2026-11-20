"""Apply remote input only to the explicitly shared foreground window."""

from ..display import windows
from .controller import InputController


class TargetInput:
    def __init__(self, hwnd):
        self.hwnd = hwnd
        self.identity = windows.identity(hwnd)
        self.controller = InputController()
        self.requested = False

    def alive(self):
        return self.identity is not None and windows.exists(self.hwnd) and (
            windows.identity(self.hwnd) == self.identity
        )

    def state(self):
        if not self.alive():
            return "closed"
        if windows.minimized(self.hwnd) or not windows.visible(self.hwnd):
            return "minimized"
        return "active" if self.requested and windows.foreground() == self.hwnd else "paused"

    def handle(self, message):
        kind = message.get("type")
        if kind == "focus":
            self.requested = message.get("active") is True
            if self.requested and self.alive() and not windows.minimized(self.hwnd):
                windows.set_foreground(self.hwnd)
            else:
                self.release()
            return
        if kind == "release":
            self.release()
            return
        if self.state() != "active":
            self.release()
            return
        if kind in ("move", "button", "wheel"):
            self._pointer(message)
        elif kind == "key" and windows.foreground() == self.hwnd:
            self.controller.keyboard.handle(message)

    def _pointer(self, message):
        x, y = message.get("x"), message.get("y")
        if any(type(value) is not int or not 0 <= value <= 65535 for value in (x, y)):
            raise ValueError("Posición del mouse inválida.")
        rect = windows.bounds(self.hwnd, captured=True)
        if not rect or rect.width <= 0 or rect.height <= 0:
            self.release()
            return
        x, y = rect.point(x, y)
        desktop = windows.desktop_bounds()
        if (not desktop.contains(x, y) or not windows.owns_point(self.hwnd, x, y)
                or windows.foreground() != self.hwnd):
            self.release()
            return
        self.controller.mouse.handle({
            **message,
            "x": round(65535 * (x - desktop.left) / max(1, desktop.width - 1)),
            "y": round(65535 * (y - desktop.top) / max(1, desktop.height - 1)),
        })

    def release(self):
        self.controller.release()
