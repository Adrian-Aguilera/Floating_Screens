"""Display local monitor geometry and attached remote edges."""

import tkinter as tk
from tkinter import ttk

from ..display.geometry import EDGES
from ..display.layout import Assignment, available


def label(name):
    return name.rsplit("\\", 1)[-1]


class ScreenMap(tk.Canvas):
    def __init__(self, parent, edit):
        super().__init__(parent, background="#eef2f7", highlightthickness=0, height=240)
        self.edit = edit
        self.monitors = []
        self.assignments = []
        self.connected = set()
        self.bind("<Configure>", lambda _event: self.redraw())

    def update_layout(self, monitors, assignments, connected):
        self.monitors = monitors
        self.assignments = list(assignments)
        self.connected = set(connected)
        self.redraw()

    def redraw(self):
        self.delete("all")
        if not self.monitors:
            return
        left = min(m.bounds.left for m in self.monitors)
        top = min(m.bounds.top for m in self.monitors)
        right = max(m.bounds.right for m in self.monitors)
        bottom = max(m.bounds.bottom for m in self.monitors)
        width, height = self.winfo_width(), self.winfo_height()
        zoom = min(max(1, width - 210) / (right - left), max(1, height - 92) / (bottom - top))
        ox = (width - (right - left) * zoom) / 2
        oy = (height - (bottom - top) * zoom) / 2
        positions = {}
        for monitor in self.monitors:
            bounds = monitor.bounds
            x = ox + (bounds.left - left) * zoom
            y = oy + (bounds.top - top) * zoom
            w, h = bounds.width * zoom, bounds.height * zoom
            positions[monitor.name] = x, y, w, h
            self.create_rectangle(x, y, x + w, y + h, fill="#fff", outline="#64748b", width=2)
            self.create_text(x + w / 2, y + h / 2, text=label(monitor.name), width=max(25, w - 5))
        for index, assignment in enumerate(self.assignments):
            if assignment.local not in positions:
                continue
            x, y, w, h = positions[assignment.local]
            edge = assignment.edge
            ax, ay = ((x, y + h / 2), (x + w, y + h / 2), (x + w / 2, y),
                      (x + w / 2, y + h))[edge]
            bx = ax + (-55, 55, 0, 0)[edge]
            by = ay + (0, 0, -24, 24)[edge]
            tag = f"remote-{index}"
            online = assignment.address in self.connected
            accent = "#2563a6" if online else "#64748b"
            self.create_line(ax, ay, bx, by, fill=accent, width=2)
            self.create_rectangle(bx - 49, by - 17, bx + 49, by + 17,
                                  fill="#dcecff" if online else "#e2e8f0", outline=accent, tags=tag)
            self.create_text(bx, by, text=f"{assignment.name[:15]}\n{label(assignment.remote)}",
                             width=92, tags=tag)
            self.tag_bind(tag, "<Button-1>", lambda _e, a=assignment: self.edit(a))
            self.tag_bind(tag, "<Enter>", lambda _event: self.configure(cursor="hand2"))
            self.tag_bind(tag, "<Leave>", lambda _event: self.configure(cursor=""))

    def choose(self, address, name, remote, existing=None):
        dialog = tk.Toplevel(self)
        dialog.title("Asignar pantalla")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        body = ttk.Frame(dialog, padding=16)
        body.pack(fill="both", expand=True)
        selections = []
        for caption, options, selected in (
            ("Monitor local", [label(m.name) for m in self.monitors],
             next((i for i, m in enumerate(self.monitors) if existing and m.name == existing.local), 0)),
            ("Borde", EDGES, existing.edge if existing else 1),
            (f"Monitor de {name}", [label(m.name) for m in remote],
             next((i for i, m in enumerate(remote) if existing and m.name == existing.remote), 0)),
        ):
            ttk.Label(body, text=caption).pack(anchor="w")
            box = ttk.Combobox(body, values=options, state="readonly", width=28)
            box.current(selected)
            box.pack(fill="x", pady=(2, 8))
            selections.append(box)


        result = existing
        warning = ttk.Label(body, wraplength=280)
        warning.pack(anchor="w")

        def save():
            nonlocal result
            local = self.monitors[selections[0].current()].name
            edge = selections[1].current()
            if not available(self.monitors, local, edge):
                warning.configure(text="Ese borde conecta con un monitor físico.")
                return
            if any(a != existing and (a.local, a.edge) == (local, edge) for a in self.assignments):
                warning.configure(text="Ese borde ya tiene un destino.")
                return
            result = Assignment(address, name, remote[selections[2].current()].name, local, edge)
            dialog.destroy()

        def remove():
            nonlocal result
            result = None
            dialog.destroy()

        ttk.Button(body, text="Guardar", command=save).pack(side="left", pady=(10, 0))
        if existing:
            ttk.Button(body, text="Quitar", command=remove).pack(side="left", padx=8, pady=(10, 0))
        dialog.wait_window()
        return result
