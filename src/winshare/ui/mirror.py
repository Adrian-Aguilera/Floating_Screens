"""A native, resizable mirror with focused-only input forwarding."""

import time
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from ..display import windows
from ..display.geometry import fit
from ..input.keyboard import virtual_key


LABELS = {
    "paused": "Control en pausa. Enfoca la ventana original y vuelve al espejo.",
    "active": "Control activo · Esc para soltar",
    "minimized": "La ventana original está minimizada.",
}


class Mirror:
    def __init__(self, root, title, monitor, edge, send, close):
        self.window = tk.Toplevel(root)
        self.window.withdraw()
        self.window.title(title)
        self.window.minsize(260, 160)
        self.window.protocol("WM_DELETE_WINDOW", close)
        self.send = send
        self.focused = False
        self.state = "paused"
        self.frame = None
        self.photo = None
        self.image_bounds = None
        self.last_move = 0
        self.status = ttk.Label(self.window, text="Esperando imagen…", anchor="w")
        self.status.pack(side="bottom", fill="x")
        self.canvas = tk.Canvas(self.window, background="#111827", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.picture = self.canvas.create_image(0, 0, anchor="nw")
        self.canvas.bind("<Configure>", lambda _event: self.draw())
        self.canvas.bind("<FocusIn>", lambda _event: self._focus(True))
        self.canvas.bind("<FocusOut>", lambda _event: self._focus(False))
        self.canvas.bind("<KeyPress>", lambda event: self._key(event, True))
        self.canvas.bind("<KeyRelease>", lambda event: self._key(event, False))
        self.canvas.bind("<Motion>", self._move)
        self.canvas.bind("<ButtonPress>", lambda event: self._button(event, True))
        self.canvas.bind("<ButtonRelease>", lambda event: self._button(event, False))
        self.canvas.bind("<MouseWheel>", self._wheel)
        self.window.bind("<Unmap>", lambda _event: self._focus(False))
        self.window.deiconify()
        windows.place_mirror(self.window, monitor, edge)

    def _focus(self, active):
        if self.focused != active:
            self.focused = active
            self.send("focus", active=active)
            self._caption()

    def _caption(self):
        message = LABELS[self.state]
        if self.state == "active" and not self.focused:
            message = "Haz clic en la imagen para controlar la ventana."
        self.status.configure(text=message)

    def set_state(self, state):
        if state in LABELS:
            self.state = state
            self._caption()
            self.draw()

    def show(self, image):
        self.frame = image
        self.draw()

    def draw(self):
        if not self.frame or self.state == "minimized":
            self.canvas.itemconfigure(self.picture, image="")
            self.image_bounds = None
            return
        canvas = self.canvas
        self.image_bounds = rect = fit(
            self.frame.width, self.frame.height, canvas.winfo_width(), canvas.winfo_height()
        )
        rendered = self.frame.resize((rect.width, rect.height), Image.Resampling.BILINEAR)
        self.photo = ImageTk.PhotoImage(rendered, master=self.window)
        canvas.coords(self.picture, rect.left, rect.top)
        canvas.itemconfigure(self.picture, image=self.photo)

    def _key(self, event, down):
        if event.keysym == "Escape":
            if down:
                self._focus(False)
                self.window.focus_set()
        elif self.focused and self.state == "active" and self.image_bounds:
            vk, extended = virtual_key(event.keycode, event.keysym)
            if 8 <= vk <= 254:
                self.send("key", vk=vk, extended=extended, down=down)
        return "break"

    def _position(self, event):
        rect = self.image_bounds
        if self.focused and self.state == "active" and rect and rect.contains(event.x, event.y):
            return {
                "x": round(65535 * (event.x - rect.left) / max(1, rect.width - 1)),
                "y": round(65535 * (event.y - rect.top) / max(1, rect.height - 1)),
            }
        return None

    def _move(self, event):
        position = self._position(event)
        now = time.monotonic()
        if position and now - self.last_move >= 1 / 60:
            self.send("move", **position)
            self.last_move = now

    def _button(self, event, down):
        if down and not self.focused:
            self.canvas.focus_set()
            return "break"
        position = self._position(event)
        if position and event.num in (1, 2, 3):
            self.send("button", button=event.num, down=down, **position)
        elif not down and self.focused:
            self.send("release")
        return "break"

    def _wheel(self, event):
        position = self._position(event)
        if position:
            self.send("wheel", delta=max(-1200, min(1200, event.delta)), **position)
        return "break"

    def dispose(self):
        self.focused = False
        self.window.destroy()
