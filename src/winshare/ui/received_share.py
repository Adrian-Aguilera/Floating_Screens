"""Destination lifecycle for a paired mirror and its video stream."""

import socket

from ..capture.latest import Latest
from ..capture.window import decode
from ..display import windows
from ..network.protocol import VIDEO_PORT
from ..network.video import receive_video
from .mirror import Mirror


class ReceivedShare:
    def __init__(self, root, link, context, message, close, failed):
        self.link = link
        self.token = message.get("token")
        title = message.get("title")
        edge = message.get("edge")
        monitor = next((m for m in windows.monitors() if m.name == message.get("monitor")), None)
        if (not isinstance(self.token, str) or len(self.token) != 64
                or any(c not in "0123456789abcdef" for c in self.token)
                or not isinstance(title, str) or not 1 <= len(title) <= 160
                or type(edge) is not int or not 0 <= edge <= 3 or monitor is None):
            raise ValueError("La pantalla seleccionada ya no está disponible o la solicitud es inválida.")
        self.frames = Latest()
        listener = socket.create_server(("0.0.0.0", VIDEO_PORT), backlog=1)
        try:
            self.mirror = Mirror(root, title, monitor, edge, self.send, close)
        except Exception:
            listener.close()
            raise
        report_failure = lambda reason: failed(self.token, reason)
        self.listener = listener
        self.video = receive_video(listener, context, self.token, self.frames, report_failure, decode)
        try:
            self.send("accepted")
        except ConnectionError:
            self.close(notify=False)
            raise

    def send(self, kind, **fields):
        self.link.send(kind, token=self.token, **fields)

    def poll(self):
        frame = self.frames.take()
        if frame is not None:
            self.mirror.show(frame)

    def close(self, notify=True):
        self.video.stop()
        self.listener.close()
        self.mirror.dispose()
        if notify:
            self.send("closed")
