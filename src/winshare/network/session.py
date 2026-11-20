"""Connect an origin to a destination and supervise the input session."""

import queue
import socket
import ssl
import threading
from collections.abc import Callable

from .protocol import PORT, encode, receive


class Destination:
    def __init__(self, name: str, context: ssl.SSLContext, handle: Callable,
                 release: Callable, status: Callable):
        self.stopped = threading.Event()
        self._listener = socket.create_server(("0.0.0.0", PORT), backlog=1)
        self._listener.settimeout(0.25)
        self.thread = threading.Thread(
            target=self._run, args=(name, context, handle, release, status),
            daemon=True,
        )
        self.thread.start()

    def _run(self, name, context, handle, release, status):
        with self._listener:
            while not self.stopped.is_set():
                try:
                    raw, address = self._listener.accept()
                except TimeoutError:
                    continue
                except OSError as error:
                    status(f"Error de red: {error}")
                    return

                connected = False
                try:
                    with raw:
                        raw.settimeout(3)
                        raw.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                        with context.wrap_socket(raw, server_side=True) as peer:
                            if self.stopped.is_set():
                                return
                            peer.sendall(encode("ready", name=name))
                            connected = True
                            status(f"Origen conectado desde {address[0]}")
                            with peer.makefile("rb") as stream:
                                while not self.stopped.is_set():
                                    message = receive(stream)
                                    if message is None or self.stopped.is_set():
                                        break
                                    if message == {"type": "ping"}:
                                        peer.sendall(encode("pong"))
                                    else:
                                        handle(message)
                except (OSError, ValueError) as error:
                    if connected and not self.stopped.is_set():
                        status(f"Sesión terminada: {error}")
                finally:
                    if connected:
                        release()
                if not self.stopped.is_set():
                    status("Esperando un origen…")

    def stop(self):
        self.stopped.set()


class Origin:
    def __init__(self, address: str, context: ssl.SSLContext, status: Callable):
        self.stopped = threading.Event()
        self._messages: queue.Queue[bytes] = queue.Queue(maxsize=128)
        self.thread = threading.Thread(
            target=self._run, args=(address, context, status), daemon=True
        )
        self.thread.start()

    def send(self, kind: str, **fields: object):
        if self.stopped.is_set():
            return
        try:
            self._messages.put_nowait(encode(kind, **fields))
        except queue.Full:
            if kind != "move":
                self.stop()

    def stop(self):
        self.stopped.set()

    def _run(self, address, context, status):
        reason = "Desconectado"
        try:
            with socket.create_connection((address, PORT), timeout=3) as raw:
                raw.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                with context.wrap_socket(raw, server_hostname=address) as peer:
                    with peer.makefile("rb") as stream:
                        ready = receive(stream)
                        if not ready or ready.get("type") != "ready":
                            raise ValueError("El destino no confirmó la sesión.")
                        name = ready.get("name")
                        if not isinstance(name, str) or not 1 <= len(name) <= 100:
                            raise ValueError("Nombre de destino inválido.")
                        if not self.stopped.is_set():
                            status(f"Conectado a {name}", name)
                        while not self.stopped.is_set():
                            try:
                                packet = self._messages.get(timeout=0.5)
                            except queue.Empty:
                                packet = None
                            if self.stopped.is_set():
                                break
                            if packet is None:
                                peer.sendall(encode("ping"))
                                reply = receive(stream)
                                if reply != {"type": "pong"}:
                                    raise ValueError("El destino dejó de responder.")
                            else:
                                peer.sendall(packet)
        except (OSError, ValueError) as error:
            if not self.stopped.is_set():
                reason = f"No se pudo mantener la conexión: {error}"
        finally:
            self.stopped.set()
            status(reason, None)
