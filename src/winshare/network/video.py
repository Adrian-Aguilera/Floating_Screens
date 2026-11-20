"""A short-lived TLS video stream bound to the authenticated control share."""

import socket
import threading
from secrets import compare_digest

from .protocol import VIDEO_PORT, encode, receive, receive_frame, video_packet
from .session import configure


class Video:
    def __init__(self, run, failed):
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self._guard, args=(run, failed), daemon=True)
        self.thread.start()

    def _guard(self, run, failed):
        try:
            run(self.stopped)
        except (OSError, ValueError) as error:
            if not self.stopped.is_set():
                failed(str(error))
        finally:
            self.stopped.set()

    def stop(self):
        self.stopped.set()


def transmit(address, context, token, frames, failed):
    def run(stopped):
        with socket.create_connection((address, VIDEO_PORT), timeout=2) as raw:
            configure(raw)
            with context.wrap_socket(raw, server_hostname=address) as peer:
                with peer.makefile("rb") as stream:
                    peer.sendall(encode("video", token=token))
                    if receive(stream) != {"type": "accepted"}:
                        raise ValueError("El destino rechazó el canal de video.")
                    while not stopped.is_set():
                        frame = frames.take(0.2)
                        if frame is None:
                            peer.sendall(b"\x00" * 4)
                        else:
                            peer.sendall(video_packet(frame))
    return Video(run, failed)


def receive_video(listener, context, token, frames, failed, decode):
    def run(stopped):
        listener.settimeout(2)
        with listener:
            raw, _ = listener.accept()
            with raw:
                configure(raw)
                with context.wrap_socket(raw, server_side=True) as peer:
                    with peer.makefile("rb") as stream:
                        hello = receive(stream)
                        candidate = hello.get("token") if hello and hello.get("type") == "video" else None
                        if not isinstance(candidate, str) or not candidate.isascii() or not compare_digest(token, candidate):
                            raise ValueError("Token de video inválido.")
                        peer.sendall(encode("accepted"))
                        while not stopped.is_set():
                            frame = receive_frame(stream)
                            if frame is None:
                                raise ConnectionError("Canal de video cerrado.")
                            if frame:
                                frames.put(decode(frame))
    return Video(run, failed)
