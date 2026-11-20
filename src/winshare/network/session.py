"""Authenticated bidirectional control, independent of video bandwidth."""

import queue
import socket
import ssl
import threading
from collections.abc import Callable

from .protocol import PORT, VERSION, encode, receive

PollHandler = Callable[[list[dict]], None]


class Outbox:
    def __init__(self):
        self._messages: queue.Queue[dict] = queue.Queue(maxsize=128)

    def send(self, kind: str, **fields: object):
        try:
            self._messages.put_nowait({"type": kind, **fields})
        except queue.Full:
            if kind != "move":
                raise ConnectionError("Cola de control llena.")

    def batch(self) -> list[dict]:
        messages = []
        for _ in range(24):
            try:
                messages.append(self._messages.get_nowait())
            except queue.Empty:
                break
        return messages


def exchange_messages(record: dict | None) -> list[dict]:
    if record is None or record.get("type") != "exchange":
        raise ValueError("Intercambio de control inválido.")
    messages = record.get("messages")
    if not isinstance(messages, list) or len(messages) > 24:
        raise ValueError("Lote de control inválido.")
    if any(not isinstance(message, dict) for message in messages):
        raise ValueError("Evento inválido.")
    return messages


def configure(socket_: socket.socket):
    socket_.settimeout(2)
    socket_.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)


class Origin:
    def __init__(self, address: str, context: ssl.SSLContext, ready: Callable,
                 handle: PollHandler, closed: Callable):
        self.address = address
        self.context = context
        self.outbox = Outbox()
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self._run, args=(ready, handle, closed), daemon=True)
        self.thread.start()

    def stop(self):
        self.stopped.set()

    def _run(self, ready, handle, closed):
        reason = "Desconectado."
        try:
            with socket.create_connection((self.address, PORT), timeout=2) as raw:
                configure(raw)
                with self.context.wrap_socket(raw, server_hostname=self.address) as peer:
                    with peer.makefile("rb") as stream:
                        hello = receive(stream)
                        if not hello or hello.get("type") != "ready" or hello.get("version") != VERSION:
                            raise ValueError("Actualiza Floating Screens en ambas PCs.")
                        peer.sendall(encode("hello", version=VERSION))
                        ready(hello)
                        while not self.stopped.is_set():
                            peer.sendall(encode("exchange", messages=self.outbox.batch()))
                            handle(exchange_messages(receive(stream)))
                            self.stopped.wait(0.012)
        except (OSError, ValueError) as error:
            if not self.stopped.is_set():
                reason = str(error)
        finally:
            self.stopped.set()
            closed(reason)


class Destination:
    def __init__(self, name: str, monitors: list[dict], context: ssl.SSLContext,
                 connected: Callable, handle: Callable, disconnected: Callable):
        self.stopped = threading.Event()
        self.listener = socket.create_server(("0.0.0.0", PORT), backlog=1)
        self.listener.settimeout(0.2)
        self.thread = threading.Thread(
            target=self._run, args=(name, monitors, context, connected, handle, disconnected),
            daemon=True,
        )
        self.thread.start()

    def stop(self):
        self.stopped.set()

    def _run(self, name, monitors, context, connected, handle, disconnected):
        with self.listener:
            while not self.stopped.is_set():
                try:
                    raw, _ = self.listener.accept()
                except TimeoutError:
                    continue
                link = Outbox()
                active = False
                try:
                    with raw:
                        configure(raw)
                        with context.wrap_socket(raw, server_side=True) as peer:
                            with peer.makefile("rb") as stream:
                                peer.sendall(encode("ready", version=VERSION, name=name, monitors=monitors))
                                if receive(stream) != {"type": "hello", "version": VERSION}:
                                    continue
                                active = True
                                connected(link)
                                while not self.stopped.is_set():
                                    record = receive(stream)
                                    if record is None:
                                        break
                                    handle(link, exchange_messages(record))
                                    peer.sendall(encode("exchange", messages=link.batch()))
                except (OSError, ValueError):
                    pass
                finally:
                    if active:
                        disconnected(link)
