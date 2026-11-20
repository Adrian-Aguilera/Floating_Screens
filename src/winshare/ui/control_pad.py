"""Forward input only while the origin's control area has focus."""

import time
import tkinter as tk
from collections.abc import Callable

from ..input.keyboard import virtual_key


class ControlPad(tk.Canvas):
    def __init__(self, parent, send: Callable):
        super().__init__(parent, height=190, background="#edf3fc", takefocus=False,
                         highlightthickness=2, highlightcolor="#2358a4",
                         highlightbackground="#b5c5df")
        self.send = send
        self.enabled = False
        self._last_move = 0.0
        self._caption = self.create_text(0, 0, justify="center", fill="#203958")
        self.bind("<Configure>", self._arrange)
        self.bind("<FocusIn>", lambda _event: self._update_caption())
        self.bind("<FocusOut>", self._blur)
        self.bind("<KeyPress>", self._key_down)
        self.bind("<KeyRelease>", lambda event: self._key(event, False))
        self.bind("<Motion>", self._motion)
        self.bind("<ButtonPress>", self._press)
        self.bind("<ButtonRelease>", lambda event: self._button(event, False))
        self.bind("<MouseWheel>", self._wheel)
        self._update_caption()

    def set_enabled(self, enabled: bool):
        self.enabled = enabled
        if not enabled and self.focus_get() is self:
            self.winfo_toplevel().focus_set()
        self._update_caption()

    def _arrange(self, event):
        self.coords(self._caption, event.width / 2, event.height / 2)
        self.itemconfigure(self._caption, width=max(50, event.width - 20))

    def _update_caption(self):
        caption = "Conecta un destino para habilitar el panel."
        if self.enabled:
            caption = "Haz clic aquí para controlar el destino."
            if self.focus_get() is self:
                caption = "Control activo · Esc para salir"
        self.itemconfigure(self._caption, text=caption)

    def _blur(self, _event):
        if self.enabled:
            self.send("release")
        self._update_caption()

    def _press(self, event):
        if self.enabled and self.focus_get() is not self:
            if event.num == 1:
                self.focus_set()
                self._update_caption()
            return "break"
        return self._button(event, True)

    def _key_down(self, event):
        if event.keysym == "Escape":
            self.winfo_toplevel().focus_set()
            return "break"
        return self._key(event, True)

    def _key(self, event, down):
        if self.enabled and self.focus_get() is self:
            vk, extended = virtual_key(event.keycode, event.keysym)
            if 8 <= vk <= 254 and event.keysym != "Escape":
                self.send("key", vk=vk, extended=extended, down=down)
        return "break"

    def _position(self, event):
        width = max(1, self.winfo_width() - 1)
        height = max(1, self.winfo_height() - 1)
        return {
            "x": round(65535 * min(max(event.x, 0), width) / width),
            "y": round(65535 * min(max(event.y, 0), height) / height),
        }

    def _motion(self, event):
        now = time.monotonic()
        if self.enabled and self.focus_get() is self and now - self._last_move >= 1 / 60:
            self.send("move", **self._position(event))
            self._last_move = now

    def _button(self, event, down):
        if self.enabled and self.focus_get() is self and event.num in (1, 2, 3):
            self.send("button", button=event.num, down=down, **self._position(event))
        return "break"

    def _wheel(self, event):
        if self.enabled and self.focus_get() is self:
            delta = max(-1200, min(1200, event.delta))
            self.send("wheel", delta=delta, **self._position(event))
        return "break"
