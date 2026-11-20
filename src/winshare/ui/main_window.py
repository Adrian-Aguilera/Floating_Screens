"""Role selection, pairing and session controls."""

import queue
import socket
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from ..input.controller import InputController
from ..network.protocol import PORT
from ..network.session import Destination, Origin
from ..pairing.security import new_key, tls_context
from .control_pad import ControlPad


class MainWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.name = socket.gethostname()[:100]
        self.origin: Origin | None = None
        self.destination: Destination | None = None
        self.targets: dict[str, tuple[str, str]] = {}
        self.updates: queue.SimpleQueue[tuple[object, str, str | None]] = queue.SimpleQueue()
        self.session_token = object()
        self.closing = False
        self.role = tk.BooleanVar(value=False)
        self.status = tk.StringVar()
        self.key = tk.StringVar()

        root.title("Floating Screens")
        root.minsize(500, 430)
        root.protocol("WM_DELETE_WINDOW", self._close)
        shell = ttk.Frame(root, padding=20)
        shell.pack(fill="both", expand=True)
        ttk.Label(shell, text=self.name, font=("Segoe UI", 17, "bold")).pack(anchor="w")
        self.switch = ttk.Checkbutton(shell, text="Origen PC", variable=self.role,
                                      command=self._change_role)
        self.switch.pack(anchor="w", pady=(8, 12))
        ttk.Label(shell, textvariable=self.status, wraplength=450).pack(
            side="bottom", anchor="w", pady=(12, 0)
        )

        self.source_panel = ttk.Frame(shell)
        actions = ttk.Frame(self.source_panel)
        actions.pack(fill="x")
        ttk.Label(actions, text="PC de destino").pack(side="left")
        ttk.Button(actions, text="+", width=4, command=self._add_target).pack(side="right")
        self.target_list = tk.Listbox(self.source_panel, height=4, exportselection=False)
        self.target_list.pack(fill="x", pady=(6, 8))
        self.target_list.bind("<<ListboxSelect>>", lambda _event: self._update_buttons())
        self.connect_button = ttk.Button(self.source_panel, text="Conectar",
                                         command=self._toggle_origin)
        self.connect_button.pack(anchor="w", pady=(0, 10))
        self.pad = ControlPad(self.source_panel, self._send)
        self.pad.pack(fill="both", expand=True)

        self.destination_panel = ttk.Frame(shell)
        ttk.Label(self.destination_panel, text=f"PC de destino · TCP {PORT}").pack(anchor="w")
        ttk.Label(self.destination_panel, wraplength=450, text=(
            "Activa la recepción y copia la Security Key en la PC de origen."
        )).pack(anchor="w", pady=(6, 12))
        self.receive_button = ttk.Button(self.destination_panel, text="Activar recepción",
                                         command=self._toggle_destination)
        self.receive_button.pack(anchor="w")
        self.key_entry = ttk.Entry(self.destination_panel, textvariable=self.key, state="readonly")
        self.key_entry.pack(fill="x", pady=(12, 6))
        self.copy_button = ttk.Button(self.destination_panel, text="Copiar Security Key",
                                      command=self._copy_key)
        self.copy_button.pack(anchor="w")

        self._change_role()
        root.after(40, self._poll)

    def _change_role(self):
        self.session_token = object()
        self._stop()
        self.source_panel.pack_forget()
        self.destination_panel.pack_forget()
        panel = self.source_panel if self.role.get() else self.destination_panel
        panel.pack(fill="both", expand=True)
        target = "Agrega una PC con el botón +." if self.role.get() else "Recepción desactivada."
        self.status.set(target)
        self._update_buttons()

    def _add_target(self):
        address = simpledialog.askstring("Agregar destino", "Nombre de red o IPv4 del destino:",
                                         parent=self.root)
        if not address or not address.strip():
            return
        address = address.strip()
        key = simpledialog.askstring("Agregar destino", "Security Key de la PC de destino:",
                                     show="*", parent=self.root)
        if key is None:
            return
        try:
            tls_context(key, server=False)
        except ValueError as error:
            messagebox.showerror("Security Key", str(error), parent=self.root)
            return
        self.targets[address] = (address, key)
        self._refresh_targets(address)
        if self.origin is None and self.destination is None:
            self._toggle_origin()

    def _refresh_targets(self, selected: str):
        self.target_list.delete(0, tk.END)
        for index, (address, (name, _key)) in enumerate(self.targets.items()):
            label = name if address == name else f"{name} ({address})"
            self.target_list.insert(tk.END, label)
            if address == selected:
                self.target_list.selection_set(index)
                self.target_list.see(index)
        self._update_buttons()

    def _toggle_origin(self):
        if self.origin:
            self._stop()
            self.status.set("Desconectando…")
        else:
            selection = self.target_list.curselection()
            if not selection:
                return
            self.active_address = list(self.targets)[selection[0]]
            _, key = self.targets[self.active_address]
            token = self.session_token = object()
            self.status.set(f"Conectando a {self.active_address}…")
            self.origin = Origin(self.active_address, tls_context(key, server=False),
                                 lambda status, name: self.updates.put((token, status, name)))
        self._update_buttons()

    def _toggle_destination(self):
        if self.destination:
            self._stop()
            self.status.set("Desactivando recepción…")
        else:
            token = self.session_token = object()
            key = new_key()
            controller = InputController()
            try:
                self.destination = Destination(
                    self.name, tls_context(key, server=True), controller.handle,
                    controller.release, lambda status: self.updates.put((token, status, None)),
                )
            except (OSError, ValueError) as error:
                messagebox.showerror("Recepción", str(error), parent=self.root)
                return
            self.key.set(key)
            self.status.set("Esperando un origen…")
        self._update_buttons()

    def _send(self, kind: str, **fields: object):
        if self.origin:
            self.origin.send(kind, **fields)

    def _copy_key(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.key.get())

    def _stop(self):
        self.pad.set_enabled(False)
        self.key.set("")
        for session in (self.origin, self.destination):
            if session:
                session.stop()

    def _update_buttons(self):
        origin_stopping = self.origin and self.origin.stopped.is_set()
        destination_stopping = self.destination and self.destination.stopped.is_set()
        self.connect_button.configure(
            text="Desconectar" if self.origin else "Conectar",
            state="normal" if not origin_stopping and not self.destination
            and (self.origin or self.target_list.curselection()) else "disabled",
        )
        self.receive_button.configure(
            text="Desactivar recepción" if self.destination else "Activar recepción",
            state="disabled" if destination_stopping or self.origin else "normal",
        )
        self.copy_button.configure(state="normal" if self.key.get() else "disabled")

    def _poll(self):
        while True:
            try:
                token, status, name = self.updates.get_nowait()
            except queue.Empty:
                break
            if token is not self.session_token or self.closing:
                continue
            self.status.set(status)
            if name and self.origin and not self.origin.stopped.is_set():
                address = self.active_address
                _, key = self.targets[address]
                self.targets[address] = (name, key)
                self._refresh_targets(address)
                self.pad.set_enabled(True)

        if self.origin and not self.origin.thread.is_alive():
            self.origin = None
            self.pad.set_enabled(False)
            self._update_buttons()
        if self.destination and not self.destination.thread.is_alive():
            stopped = self.destination.stopped.is_set()
            self.destination = None
            self.key.set("")
            if stopped and not self.role.get():
                self.status.set("Recepción desactivada.")
            self._update_buttons()
        if self.closing and not (self.origin or self.destination):
            self.root.destroy()
        else:
            self.root.after(40, self._poll)

    def _close(self):
        self.closing = True
        self._stop()
        self.root.withdraw()
