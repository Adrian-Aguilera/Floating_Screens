"""Pair machines, configure screen edges, and coordinate sharing on Tk's thread."""

import queue
import socket
import time
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from ..capture.share import SourceShare
from ..display import windows
from ..display.drag import DragMonitor
from ..display.layout import find_assignment, read_monitors, wire_monitors
from ..network.protocol import PORT, VIDEO_PORT
from ..network.session import Destination, Origin
from ..pairing.security import new_key, tls_context
from .received_share import ReceivedShare
from .screen_map import ScreenMap


class MainWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.name = socket.gethostname()[:100]
        self.locals = windows.monitors()
        self.remotes = {}
        self.credentials = {}
        self.origins = {}
        self.connected = set()
        self.assignments = {}
        self.listener = None
        self.receiver_context = None
        self.receiver_link = None
        self.source = None
        self.received = None
        self.events = queue.SimpleQueue()
        self.batches = queue.Queue(maxsize=128)
        self.closing = False
        self.role = tk.BooleanVar(value=False)
        self.status = tk.StringVar()
        self.key = tk.StringVar()
        self.next_monitor_scan = 0

        root.title("Floating Screens")
        root.minsize(600, 400)
        root.protocol("WM_DELETE_WINDOW", self._close)
        shell = ttk.Frame(root, padding=20)
        shell.pack(fill="both", expand=True)
        ttk.Label(shell, text=self.name, font=("Segoe UI", 17, "bold")).pack(anchor="w")
        ttk.Checkbutton(shell, text="Origen PC", variable=self.role,
                        command=self._role_changed).pack(anchor="w", pady=(8, 12))
        ttk.Label(shell, textvariable=self.status, wraplength=550).pack(
            side="bottom", anchor="w", pady=(12, 0)
        )

        self.source_panel = ttk.Frame(shell)
        actions = ttk.Frame(self.source_panel)
        actions.pack(fill="x", pady=(0, 8))
        ttk.Label(actions, text="Pantallas").pack(side="left")
        ttk.Button(actions, text="+ Añadir pantalla", command=self._add).pack(side="right")
        self.stop_share_button = ttk.Button(actions, text="Dejar de compartir",
                                            command=self._stop_source, state="disabled")
        self.stop_share_button.pack(side="right", padx=8)
        self.screen_map = ScreenMap(self.source_panel, self._edit)
        self.screen_map.pack(fill="both", expand=True)

        self.destination_panel = ttk.Frame(shell)
        ttk.Label(self.destination_panel, text=f"PC de destino · TCP {PORT} y {VIDEO_PORT}").pack(anchor="w")
        ttk.Label(self.destination_panel, text="Activa la recepción y copia la Security Key.").pack(
            anchor="w", pady=(6, 12)
        )
        self.receive_button = ttk.Button(self.destination_panel, text="Activar recepción",
                                         command=self._toggle_receive)
        self.receive_button.pack(anchor="w")
        ttk.Entry(self.destination_panel, textvariable=self.key, state="readonly").pack(
            fill="x", pady=(12, 6)
        )
        self.copy_button = ttk.Button(self.destination_panel, text="Copiar Security Key",
                                      command=self._copy_key, state="disabled")
        self.copy_button.pack(anchor="w")

        self.drag = DragMonitor(self._dropped)
        self._role_changed()
        root.after(15, self._poll)

    def _role_changed(self):
        self._stop_sessions()
        self.source_panel.pack_forget()
        self.destination_panel.pack_forget()
        if self.role.get():
            self.source_panel.pack(fill="both", expand=True)
            self.status.set("Añade un destino y asígnalo al borde de una pantalla.")
            for address in self.assignments:
                self._connect(address, self.credentials[address])
        else:
            self.destination_panel.pack(fill="both", expand=True)
            self.status.set("Recepción desactivada.")
        self._redraw()

    def _redraw(self):
        self.screen_map.update_layout(self.locals, self.assignments.values(), self.connected)

    def _add(self):
        address = simpledialog.askstring("Añadir pantalla", "Nombre de red o IPv4 del destino:",
                                         parent=self.root)
        if not address or not address.strip() or not self.role.get():
            return
        address = address.strip()
        if address in self.origins:
            if address in self.remotes:
                self._edit_address(address)
            return
        key = simpledialog.askstring("Añadir pantalla", "Security Key del destino:",
                                     show="*", parent=self.root)
        if key is None:
            return
        try:
            context = tls_context(key, server=False)
        except ValueError as error:
            messagebox.showerror("Security Key", str(error), parent=self.root)
            return
        self.credentials[address] = context
        self._connect(address, context)

    def _connect(self, address, context):
        generation = object()
        self.origins[address] = generation, Origin(
            address, context,
            lambda hello: self.events.put(("ready", address, generation, hello)),
            lambda batch: self._enqueue_batch(("origin", address, generation, batch)) if batch else None,
            lambda reason: self.events.put(("closed", address, generation, reason)),
        )
        self.status.set(f"Conectando a {address}…")

    def _edit(self, assignment):
        address = assignment.address
        if address in self.connected:
            self._edit_address(address)
        elif address not in self.origins:
            self._connect(address, self.credentials[address])

    def _edit_address(self, address):
        name, monitors = self.remotes[address]
        previous = self.assignments.get(address)
        assignment = self.screen_map.choose(address, name, monitors, previous)
        if address not in self.connected or not self.role.get():
            return
        if assignment:
            self.assignments[address] = assignment
            self.status.set("Arrastra la ventana activa y suéltala en el borde asignado.")
        else:
            self.assignments.pop(address, None)
            origin = self.origins.get(address)
            if origin:
                origin[1].stop()
            if self.source and self.source.link.address == address:
                self._stop_source()
        self._redraw()

    def _dropped(self, hwnd, point):
        if not self.role.get() or self.closing or windows.foreground() != hwnd:
            return
        assignment = find_assignment(windows.monitors(), self.assignments.values(), point)
        if assignment is None:
            return
        pair = self.origins.get(assignment.address)
        if pair is None or assignment.address not in self.connected:
            self.status.set("Pulsa la tarjeta del destino para reconectarlo.")
            return
        _, origin = pair
        if origin.stopped.is_set():
            return
        if self.source:
            self.status.set("Cierra el espejo actual antes de compartir otra ventana.")
            return
        callbacks = queue.SimpleQueue()
        try:
            source = SourceShare(origin, assignment, hwnd, callbacks.put)
        except (OSError, ValueError) as error:
            self.status.set(str(error))
            return
        self.source = source
        self.source_failures = callbacks
        self.stop_share_button.configure(state="normal")
        self.status.set(f"Compartiendo con {assignment.name}…")

    def _stop_source(self, notify=True):
        if self.source:
            source, self.source = self.source, None
            source.close(notify)
            self.stop_share_button.configure(state="disabled")
            self.status.set("Ventana compartida cerrada.")

    def _toggle_receive(self):
        if self.listener:
            self.listener.stop()
            self._stop_received(notify=False)
            self.key.set("")
            self.copy_button.configure(state="disabled")
            self.receive_button.configure(state="disabled")
            self.status.set("Desactivando recepción…")
            return
        key = new_key()
        try:
            self.receiver_context = tls_context(key, server=True)
            generation = self.receiver_generation = object()
            self.listener = Destination(
                self.name, wire_monitors(windows.monitors()), self.receiver_context,
                lambda link: self.events.put(("connected", generation, link)),
                lambda link, batch: self._enqueue_batch(("destination", generation, link, batch)) if batch else None,
                lambda link: self.events.put(("disconnected", generation, link)),
            )
        except (OSError, ValueError) as error:
            messagebox.showerror("Recepción", str(error), parent=self.root)
            return
        self.key.set(key)
        self.status.set("Esperando un origen…")
        self.receive_button.configure(text="Desactivar recepción")
        self.copy_button.configure(state="normal")

    def _stop_received(self, notify=True):
        if self.received:
            received, self.received = self.received, None
            try:
                received.close(notify)
            except ConnectionError:
                if self.listener:
                    self.listener.stop()

    def _copy_key(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.key.get())

    def _stop_sessions(self):
        self._stop_source()
        self._stop_received()
        for _generation, origin in self.origins.values():
            origin.stop()
        self.origins.clear()
        self.connected.clear()
        if self.listener:
            self.listener.stop()
            self.receive_button.configure(state="disabled")
        self.receiver_link = None
        self.key.set("")
        self.copy_button.configure(state="disabled")

    def _origin_event(self, kind, address, generation, data):
        pair = self.origins.get(address)
        if not pair or generation is not pair[0]:
            return
        origin = pair[1]
        if kind == "ready":
            name = data.get("name")
            if not isinstance(name, str) or not 1 <= len(name) <= 100:
                raise ValueError("Nombre de destino inválido.")
            self.remotes[address] = name, read_monitors(data.get("monitors"))
            self.connected.add(address)
            self._redraw()
            assigned = self.assignments.get(address)
            if assigned and any(m.name == assigned.remote for m in self.remotes[address][1]):
                self.status.set("Destino conectado. Suelta la ventana en el borde asignado.")
            else:
                self.root.after_idle(lambda: self._edit_address(address) if address in self.connected else None)
        elif kind == "origin" and self.source and self.source.link is origin and not origin.stopped.is_set():
            for message in data:
                if message.get("token") == self.source.token and message.get("type") == "closed":
                    self._stop_source(notify=False)
                    break
                self.source.receive(message)
        elif kind == "closed":
            if self.source and self.source.link is origin:
                self._stop_source(notify=False)
            self.origins.pop(address)
            self.connected.discard(address)
            self._redraw()
            self.status.set(data)

    def _destination_event(self, kind, generation, link, data=()):
        if (not self.listener or self.listener.stopped.is_set()
                or generation is not self.receiver_generation):
            return
        if kind == "connected":
            self.receiver_link = link
            self.status.set("Origen conectado. Esperando una ventana…")
        elif self.receiver_link is link:
            if kind == "disconnected":
                self._stop_received(notify=False)
                self.receiver_link = None
                self.status.set("Esperando un origen…")
            else:
                for message in data:
                    self._destination_message(link, message)

    def _destination_message(self, link, message):
        kind = message.get("type")
        token = message.get("token")
        if kind == "share" and self.received is None:
            try:
                self.received = ReceivedShare(
                    self.root, link, self.receiver_context, message, self._stop_received,
                    lambda video_token, reason: self.events.put(("video_failure", video_token, reason)),
                )
            except (OSError, ValueError, tk.TclError) as error:
                self.status.set(str(error))
                if isinstance(token, str) and len(token) == 64:
                    link.send("closed", token=token)
        elif self.received and token == self.received.token:
            if kind == "state" and isinstance(message.get("state"), str):
                self.received.mirror.set_state(message["state"])
            elif kind == "closed":
                self._stop_received(notify=False)

    def _enqueue_batch(self, event):
        try:
            self.batches.put_nowait(event)
        except queue.Full as error:
            raise ConnectionError("Demasiados eventos pendientes.") from error

    def _poll(self):
        self.drag.poll()
        for _ in range(100):
            try:
                kind, *event = self.events.get_nowait()
            except queue.Empty:
                try:
                    kind, *event = self.batches.get_nowait()
                except queue.Empty:
                    break
            try:
                if kind in ("ready", "origin", "closed"):
                    self._origin_event(kind, *event)
                elif kind == "video_failure":
                    token, reason = event
                    if self.received and self.received.token == token:
                        self._stop_received()
                        self.status.set(reason)
                else:
                    self._destination_event(kind, *event)
            except (OSError, ValueError, RuntimeError) as error:
                if kind in ("ready", "origin"):
                    origin = self.origins.get(event[0])
                    if kind == "ready" and origin:
                        origin[1].stop()
                    self._stop_source()
                else:
                    self._stop_received()
                self.status.set(str(error))

        if self.source:
            try:
                self.source.poll()
                reason = self.source_failures.get_nowait()
            except queue.Empty:
                pass
            except (OSError, ValueError, RuntimeError) as error:
                self._stop_source()
                self.status.set(str(error))
            else:
                self._stop_source()
                self.status.set(reason)
        if self.received:
            self.received.poll()
        if self.listener and not self.listener.thread.is_alive():
            self._stop_received(notify=False)
            self.listener = None
            self.receive_button.configure(text="Activar recepción", state="normal")
            self.key.set("")
            self.copy_button.configure(state="disabled")
            if not self.role.get():
                self.status.set("Recepción desactivada.")
        if time.monotonic() >= self.next_monitor_scan:
            self.next_monitor_scan = time.monotonic() + 1
            displays = windows.monitors()
            if displays != self.locals:
                self.locals = displays
                self._redraw()
        self.root.after(15, self._poll)

    def _close(self):
        self.closing = True
        self.drag.close()
        self._stop_sessions()
        self.root.destroy()
