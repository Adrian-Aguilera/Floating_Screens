"""Choose the mirror destination and detect a native window dropped on the box."""

import tkinter as tk
from tkinter import ttk

from ..display import windows
from .screen_map import label


class DropBox(ttk.LabelFrame):
    def __init__(self, parent, pick):
        super().__init__(parent, text="Compartir ventana", padding=8)
        self.targets = []
        self.addresses = []
        self.remote_monitors = {}
        fields = ttk.Frame(self)
        fields.pack(fill="x", pady=(0, 6))
        self.destination = ttk.Combobox(fields, state="readonly", width=28)
        self.destination.pack(side="left", padx=(0, 6))
        self.destination.bind("<<ComboboxSelected>>", lambda _event: self._update_monitors())
        self.monitor = ttk.Combobox(fields, state="readonly", width=14)
        self.monitor.pack(side="left")
        self.area = tk.Label(self, height=3, borderwidth=2, relief="groove",
                             font=("Segoe UI", 10, "bold"), wraplength=530)
        self.area.pack(fill="x")
        self.hover = False
        self.drag_over = False
        self.area.bind("<Enter>", lambda _event: self._set_hover(True))
        self.area.bind("<Leave>", lambda _event: self._set_hover(False))
        self.pick = ttk.Button(self, text="Elegir ventana abierta…", command=pick)
        self.pick.pack(anchor="w", pady=(6, 0))
        self._paint()

    def _set_hover(self, hover):
        self.hover = hover
        self._paint()

    def indicate_drag(self, point):
        over = point is not None and self.contains(point)
        if over != self.drag_over:
            self.drag_over = over
            self._paint()

    def _paint(self):
        enabled = self.monitor_name is not None
        if not enabled:
            text, fill, ink = "Conecta una PC para compartir una ventana", "#eef2f7", "#475569"
        elif self.drag_over:
            text, fill, ink = "Suelta para compartir la ventana", "#205ca2", "#ffffff"
        elif self.hover:
            text, fill, ink = "Suelta aquí la ventana arrastrada desde su barra de título", "#bfdbfe", "#17345a"
        else:
            text, fill, ink = "Arrastra una ventana aquí por su barra de título", "#e4efff", "#17345a"
        self.area.configure(text=text, background=fill, foreground=ink)
        self.pick.configure(state="normal" if enabled else "disabled")

    @property
    def address(self):
        index = self.destination.current()
        return self.addresses[index] if 0 <= index < len(self.addresses) else None

    @property
    def monitor_name(self):
        index = self.monitor.current()
        return self.targets[index].name if 0 <= index < len(self.targets) else None

    def update_targets(self, remotes, connected):
        address, monitor = self.address, self.monitor_name
        self.addresses = [key for key in remotes if key in connected]
        self.remote_monitors = remotes
        self.destination.configure(values=[f"{remotes[key][0]} ({key})" for key in self.addresses])
        if self.addresses:
            self.destination.current(self.addresses.index(address) if address in self.addresses else 0)
        else:
            self.destination.set("")
        self._update_monitors(monitor if self.address == address else None)

    def _update_monitors(self, chosen=None):
        self.targets = self.remote_monitors.get(self.address, ("", []))[1]
        self.monitor.configure(values=[label(m.name) for m in self.targets])
        if self.targets:
            self.monitor.current(next((i for i, m in enumerate(self.targets) if m.name == chosen), 0))
        else:
            self.monitor.set("")
        self._paint()

    def contains(self, point):
        if not self.area.winfo_viewable():
            return False
        bounds = windows.bounds(self.area.winfo_id())
        return bool(bounds and bounds.contains(*point))
