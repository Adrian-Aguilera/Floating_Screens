"""Detect a mouse-driven native move and report its release point."""

import os

from . import windows
from .geometry import moved_without_resizing, qualifies_drag


class DragMonitor:
    def __init__(self, released):
        self.released = released
        self.pending_drop = None
        self.drag = None
        self.cancelled = False
        self.moved = False
        self.callback = windows.HOOK(self._event)
        # OUTOFCONTEXT | SKIPOWNPROCESS. Tk pumps the registering thread's messages.
        self.hook = windows.set_hook(0x000A, 0x000B, None, self.callback, 0, 0, 0x0002)
        if not self.hook:
            raise OSError("No se pudo observar el movimiento de ventanas.")

    def poll(self):
        # WinEvent can interrupt Tcl. Dispatch application code from the Tk timer.
        pending, self.pending_drop = self.pending_drop, None
        if pending is not None:
            self.released(*pending)
        if self.drag is None:
            return
        if windows.down(0x1B):
            self.cancelled = True
        hwnd, start, mouse, was_maximized = self.drag
        if mouse and not self.moved and windows.down(0x01):
            current = windows.bounds(hwnd)
            self.moved = bool(current and (
                moved_without_resizing(start, current) or (was_maximized and not windows.maximized(hwnd))
            ))

    def pointer(self):
        if self.drag and self.drag[2] and not self.cancelled and windows.down(0x01):
            return windows.cursor()
        return None

    def close(self):
        windows.unhook(self.hook)
        self.pending_drop = None

    def _event(self, _hook, event, hwnd, _object, _child, _thread, _time):
        if not hwnd:
            return
        hwnd = windows.ancestor(hwnd, 2) or hwnd
        if event == 0x000A:
            self.drag = None
            self.cancelled = False
            self.moved = False
            owner = windows.identity(hwnd)
            start = windows.bounds(hwnd)
            if start and owner and owner[0] != os.getpid() and windows.foreground() == hwnd:
                self.drag = (hwnd, start, windows.down(0x01), windows.maximized(hwnd))
        elif self.drag and self.drag[0] == hwnd:
            _, start, mouse, was_maximized = self.drag
            self.drag = None
            end = windows.bounds(hwnd)
            point = windows.cursor()
            moved = self.moved or (was_maximized and not windows.maximized(hwnd))
            if end and point and qualifies_drag(start, end, mouse, windows.down(0x01),
                                                self.cancelled or windows.down(0x1B), moved):
                self.pending_drop = (hwnd, point)
