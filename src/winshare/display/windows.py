"""Native monitor, window and cursor queries."""

import ctypes as ct
from ctypes import wintypes as wt

from ..input.win32 import user32
from .geometry import Monitor, Rect

dwmapi = ct.WinDLL("dwmapi")
dwmapi.DwmGetWindowAttribute.argtypes = [wt.HWND, wt.DWORD, wt.LPVOID, wt.DWORD]
HOOK = ct.WINFUNCTYPE(None, wt.HANDLE, wt.DWORD, wt.HWND, wt.LONG,
                      wt.LONG, wt.DWORD, wt.DWORD)
MONITOR_CALLBACK = ct.WINFUNCTYPE(wt.BOOL, wt.HANDLE, wt.HDC, ct.POINTER(wt.RECT), wt.LPARAM)


class MonitorInfo(ct.Structure):
    _fields_ = [("size", wt.DWORD), ("monitor", wt.RECT), ("work", wt.RECT),
                ("flags", wt.DWORD), ("name", wt.WCHAR * 32)]


def bind(name, result, *arguments):
    function = getattr(user32, name)
    function.restype = result
    function.argtypes = list(arguments)
    return function


foreground = bind("GetForegroundWindow", wt.HWND)
visible = bind("IsWindowVisible", wt.BOOL, wt.HWND)
minimized = bind("IsIconic", wt.BOOL, wt.HWND)
maximized = bind("IsZoomed", wt.BOOL, wt.HWND)
exists = bind("IsWindow", wt.BOOL, wt.HWND)
ancestor = bind("GetAncestor", wt.HWND, wt.HWND, wt.UINT)
window_from_point = bind("WindowFromPoint", wt.HWND, wt.POINT)
window_thread = bind("GetWindowThreadProcessId", wt.DWORD, wt.HWND, ct.POINTER(wt.DWORD))
set_foreground = bind("SetForegroundWindow", wt.BOOL, wt.HWND)
get_rect = bind("GetWindowRect", wt.BOOL, wt.HWND, ct.POINTER(wt.RECT))
get_cursor = bind("GetCursorPos", wt.BOOL, ct.POINTER(wt.POINT))
key_state = bind("GetAsyncKeyState", wt.SHORT, ct.c_int)
get_metrics = bind("GetSystemMetrics", ct.c_int, ct.c_int)
get_monitor_info = bind("GetMonitorInfoW", wt.BOOL, wt.HANDLE, ct.POINTER(MonitorInfo))
enum_monitors = bind("EnumDisplayMonitors", wt.BOOL, wt.HDC, ct.POINTER(wt.RECT),
                     MONITOR_CALLBACK, wt.LPARAM)
get_title = bind("GetWindowTextW", ct.c_int, wt.HWND, wt.LPWSTR, ct.c_int)
set_hook = bind("SetWinEventHook", wt.HANDLE, wt.DWORD, wt.DWORD, wt.HMODULE,
                HOOK, wt.DWORD, wt.DWORD, wt.DWORD)
unhook = bind("UnhookWinEvent", wt.BOOL, wt.HANDLE)
set_pos = bind("SetWindowPos", wt.BOOL, wt.HWND, wt.HWND, ct.c_int, ct.c_int,
               ct.c_int, ct.c_int, wt.UINT)


def enable_dpi_awareness():
    bind("SetProcessDpiAwarenessContext", wt.BOOL, wt.HANDLE)(ct.c_void_p(-4))


def rect_of(value):
    return Rect(value.left, value.top, value.right, value.bottom)


def monitors():
    result = []

    @MONITOR_CALLBACK
    def collect(handle, _dc, _rect, _data):
        info = MonitorInfo(size=ct.sizeof(MonitorInfo))
        if get_monitor_info(handle, ct.byref(info)):
            result.append(Monitor(info.name, rect_of(info.monitor), rect_of(info.work)))
        return True

    enum_monitors(None, None, collect, 0)
    return result


def cursor():
    point = wt.POINT()
    return (point.x, point.y) if get_cursor(ct.byref(point)) else None


def down(vk):
    return bool(key_state(vk) & 0x8000)


def bounds(hwnd, *, captured=False):
    rect = wt.RECT()
    if captured and dwmapi.DwmGetWindowAttribute(hwnd, 9, ct.byref(rect), ct.sizeof(rect)) == 0:
        return rect_of(rect)
    if get_rect(hwnd, ct.byref(rect)):
        return rect_of(rect)
    return None


def identity(hwnd):
    process = wt.DWORD()
    thread = window_thread(hwnd, ct.byref(process))
    return (process.value, thread) if thread else None


def title(hwnd):
    buffer = ct.create_unicode_buffer(161)
    get_title(hwnd, buffer, len(buffer))
    return buffer.value


def desktop_bounds():
    left, top, width, height = (get_metrics(i) for i in (76, 77, 78, 79))
    return Rect(left, top, left + width, top + height)


def owns_point(hwnd, x, y):
    hit = window_from_point(wt.POINT(x, y))
    return bool(hit and ancestor(hit, 2) == hwnd)


def place_mirror(window, monitor):
    window.update_idletasks()
    child = window.winfo_id()
    hwnd = ancestor(child, 2) or child
    work = monitor.work
    width, height = min(1000, work.width), min(720, work.height)
    x = work.left + (work.width - width) // 2
    y = work.top + (work.height - height) // 2
    set_pos(hwnd, None, x, y, width, height, 0x0014)
