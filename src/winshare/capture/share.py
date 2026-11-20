"""Origin lifecycle for one locally selected window."""

import secrets
import time

from ..display import windows
from ..input.target import TargetInput
from ..network.video import transmit
from .latest import Latest
from .window import WindowCapture


class SourceShare:
    def __init__(self, link, monitor, hwnd, failed):
        self.link = link
        self.target = TargetInput(hwnd)
        self.token = secrets.token_hex(32)
        self.failed = failed
        self.capture = None
        self.video = None
        self.last_state = None
        self.deadline = time.monotonic() + 5
        self.send("share", title=windows.title(hwnd) or "Ventana compartida",
                  monitor=monitor)

    def send(self, kind, **fields):
        self.link.outbox.send(kind, token=self.token, **fields)

    def receive(self, message):
        if message.get("token") != self.token:
            return False
        kind = message.get("type")
        if kind == "accepted" and self.capture is None:
            frames = Latest()
            self.capture = WindowCapture(self.target.hwnd, frames, self.failed)
            self.video = transmit(self.link.address, self.link.context, self.token, frames, self.failed)
        elif self.capture and kind in ("focus", "release", "key", "move", "button", "wheel"):
            self.target.handle(message)
        return True

    def poll(self):
        if self.capture is None and time.monotonic() > self.deadline:
            self.failed("El destino no confirmó el espejo.")
            return
        state = self.target.state()
        if state == "closed":
            self.failed("La ventana compartida se cerró.")
        elif state != self.last_state:
            if state != "active":
                self.target.release()
            self.last_state = state
            self.send("state", state=state)

    def close(self, notify=True):
        self.target.release()
        if self.video:
            self.video.stop()
        if self.capture:
            self.capture.stop()
        if notify and not self.link.stopped.is_set():
            try:
                self.send("closed")
            except ConnectionError:
                self.link.stop()
