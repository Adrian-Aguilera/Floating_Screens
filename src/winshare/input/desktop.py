"""Coordinate the pointer, keyboard and clipboard during a desktop handoff."""

import ctypes as ct
import secrets
import time

from ..display import windows
from .clipboard import Clipboard
from .controller import InputController
from .hooks import DesktopHooks, set_cursor
from .seam import edge_point, fraction, move, normalized, opposite, outward, touches_edge

BUTTONS = {
    0x201: (1, True), 0x202: (1, False),
    0x204: (3, True), 0x205: (3, False),
    0x207: (2, True), 0x208: (2, False),
}
LOCAL_BUTTONS_AND_KEYS = (1, 2, 4, 5, 6, *range(8, 255))


class DesktopOrigin:
    def __init__(self, root, resolve, status):
        self.root = root
        self.resolve = resolve
        self.status = status
        self.hooks = None
        self.link = None
        self.active = False
        self.buttons = set()
        self.keys = set()
        self.retained_keys = set()
        self.retained_buttons = set()
        self.pending_move = None
        self.cooldown = 0
        self.clipboard = None
        self.last_local = None
        self.return_requested = False

    def arm(self, enabled):
        if enabled and self.hooks is None:
            self.hooks = DesktopHooks(self._mouse, self._key)
        elif not enabled:
            self.stop()
            if self.hooks:
                self.hooks.close()
                self.hooks = None
            self.retained_keys.clear()
            self.retained_buttons.clear()

    def _send(self, kind, **message):
        self.link.outbox.send(f"desktop_{kind}", token=self.token, **message)

    def _begin(self, point, delta):
        if time.monotonic() < self.cooldown or self.retained_keys or self.retained_buttons:
            return
        route = self.resolve(point)
        if route is None:
            return
        link, assignment, local, remote = route
        edge = assignment.edge
        if not touches_edge(local.bounds, edge, point) or outward(edge, *delta) <= 0:
            return
        if any(windows.down(vk) for vk in LOCAL_BUTTONS_AND_KEYS):
            return
        self.link = link
        self.token = secrets.token_hex(16)
        self.local = local.bounds
        self.remote = remote.bounds
        self.edge = edge
        self.position = fraction(self.local, edge, point)
        self.remote_point = edge_point(self.remote, opposite(edge), self.position, inset=1)
        self.deadline = time.monotonic() + 1.5
        self._send("enter", monitor=assignment.remote, edge=edge, position=self.position)

    def receive(self, link, message):
        if self.link is not link or message.get("token") != self.token:
            return
        kind = message.get("type")
        if kind == "desktop_ready" and not self.active:
            if any(windows.down(vk) for vk in LOCAL_BUTTONS_AND_KEYS):
                self.stop()
                return
            point = windows.cursor()
            if point is None or not touches_edge(self.local, self.edge, point):
                self.stop()
                return
            self.parked = self.local.point(32768, 32768)
            if not set_cursor(*self.parked):
                self.stop()
                return
            self.active = True
            self._send("activate")
            self.clipboard = Clipboard(self.root)
            text = self.clipboard.changed(initial=True)
            if text is not None:
                self._send("clipboard", text=text)
            self.status("Control en el destino. Vuelve por el borde o pulsa Ctrl+Alt+Esc.")
        elif kind == "desktop_clipboard" and self.active:
            self.clipboard.apply(message.get("text"))
        elif kind == "desktop_stop":
            self.stop(notify=False)

    def _mouse(self, message, event):
        point = (event.point.x, event.point.y)
        try:
            if self.link and self.link.stopped.is_set():
                self.stop(notify=False)
            if not self.active:
                button = BUTTONS.get(message)
                if button and button[0] in self.retained_buttons:
                    if not button[1]:
                        self.retained_buttons.discard(button[0])
                    return True
                if message == 0x200:
                    old = self.last_local or windows.cursor()
                    self.last_local = point
                    if not self.link and old is not None:
                        self._begin(point, (point[0] - old[0], point[1] - old[1]))
                return False
            if self.return_requested:
                return True
            if message == 0x200:
                delta = (point[0] - self.parked[0], point[1] - self.parked[1])
                target = move(self.remote, opposite(self.edge), self.remote_point, delta,
                              self.buttons or self.keys)
                if target is None:
                    self.return_requested = True
                elif target != self.remote_point:
                    self.remote_point = target
                    self.pending_move = target
            elif message in BUTTONS:
                button, pressed = BUTTONS[message]
                if pressed:
                    self.buttons.add(button)
                else:
                    self.buttons.discard(button)
                self._send("button", button=button, down=pressed,
                           **normalized(self.remote, self.remote_point))
            elif message == 0x20A:
                delta = ct.c_short(event.data >> 16).value
                self._send("wheel", delta=max(-1200, min(1200, delta)),
                           **normalized(self.remote, self.remote_point))
            return True
        except (OSError, ValueError):
            self.stop()
            return False

    def _key(self, _message, event):
        vk, pressed = event.vk, not bool(event.flags & 0x80)
        if vk in self.retained_keys:
            if not pressed:
                self.retained_keys.discard(vk)
            return True
        if not self.active:
            return False
        if pressed:
            self.keys.add(vk)
        else:
            self.keys.discard(vk)
        if vk == 0x1B and pressed and self.keys & {0x11, 0xA2, 0xA3} and self.keys & {0x12, 0xA4, 0xA5}:
            self.return_requested = True
            return True
        try:
            if not self.return_requested and 8 <= vk <= 254:
                self._send("key", vk=vk, extended=bool(event.flags & 1), down=pressed)
        except ConnectionError:
            self.stop()
        return True

    def poll(self):
        if not self.link:
            return
        if (self.return_requested or self.link.stopped.is_set()
                or (not self.active and time.monotonic() > self.deadline)):
            self.stop()
        elif self.active:
            if self.pending_move is not None:
                self._send("move", **normalized(self.remote, self.pending_move))
                self.pending_move = None
            text = self.clipboard.changed()
            if text is not None:
                self._send("clipboard", text=text)

    def stop(self, notify=True):
        link, self.link = self.link, None
        if link is None:
            return
        if notify and not link.stopped.is_set():
            try:
                link.outbox.send("desktop_leave", token=self.token)
            except ConnectionError:
                link.stop()
        if self.active:
            position = fraction(self.remote, opposite(self.edge), self.remote_point)
            self.active = False
            self.last_local = edge_point(self.local, self.edge, position, inset=12)
            set_cursor(*self.last_local)
            self.status("Control en la PC de origen.")
        self.retained_keys.update(self.keys)
        self.retained_buttons.update(self.buttons)
        self.keys.clear()
        self.buttons.clear()
        self.pending_move = None
        self.return_requested = False
        self.clipboard = None
        self.cooldown = time.monotonic() + 0.5


class DesktopDestination:
    def __init__(self, root, link, message):
        self.link = link
        self.token = message.get("token")
        edge, position = message.get("edge"), message.get("position")
        monitor = next((m for m in windows.monitors() if m.name == message.get("monitor")), None)
        if (not isinstance(self.token, str) or len(self.token) != 32
                or any(char not in "0123456789abcdef" for char in self.token)
                or type(edge) is not int or not 0 <= edge < 4
                or type(position) is not int or not 0 <= position <= 65535 or monitor is None):
            raise ValueError("Solicitud de control de escritorio inválida.")
        self.clipboard = Clipboard(root)
        self.controller = InputController()
        self.bounds = monitor.bounds
        self.start_point = edge_point(self.bounds, opposite(edge), position, inset=1)
        self.active = False
        self.deadline = time.monotonic() + 2
        self.send("ready")

    def activate(self):
        self.active = True
        self.handle({"type": "desktop_move", **normalized(self.bounds, self.start_point)})

    def send(self, kind, **message):
        self.link.send(f"desktop_{kind}", token=self.token, **message)

    def handle(self, message):
        if not self.active:
            return
        kind = message["type"].removeprefix("desktop_")
        if kind == "clipboard":
            self.clipboard.apply(message.get("text"))
        elif kind == "key":
            self.controller.keyboard.handle(message)
        elif kind in ("move", "button", "wheel"):
            x, y = message.get("x"), message.get("y")
            if any(type(v) is not int or not 0 <= v <= 65535 for v in (x, y)):
                raise ValueError("Posición de escritorio inválida.")
            point = self.bounds.point(x, y)
            desktop = windows.desktop_bounds()
            if not desktop.contains(*point):
                raise ValueError("La pantalla de destino ya no está disponible.")
            self.controller.mouse.handle({
                **message, "type": kind, **normalized(desktop, point),
            })

    def poll(self):
        if not self.active:
            if time.monotonic() > self.deadline:
                raise TimeoutError("El origen no completó el cambio de PC.")
            return
        text = self.clipboard.changed()
        if text is not None:
            self.send("clipboard", text=text)

    def close(self):
        self.controller.release()
