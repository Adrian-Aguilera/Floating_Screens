import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from winshare.display.drag import DragMonitor
from winshare.display.geometry import Rect
from winshare.input.desktop import DesktopOrigin


class NativeCallbackTests(unittest.TestCase):
    @patch("winshare.display.drag.windows")
    def test_drop_dispatch_waits_for_the_tk_poll(self, windows):
        windows.identity.return_value = (0, 1)
        windows.foreground.return_value = 42
        windows.bounds.side_effect = [Rect(0, 0, 100, 100), Rect(20, 30, 120, 130)]
        windows.down.side_effect = [True, False, False]
        windows.maximized.return_value = False
        windows.cursor.return_value = (80, 80)
        released = Mock()
        drag = DragMonitor(released)

        drag._event(None, 0x000A, 42, 0, 0, 0, 0)
        drag._event(None, 0x000B, 42, 0, 0, 0, 0)
        released.assert_not_called()
        drag.poll()
        released.assert_called_once_with(42, (80, 80))
        drag.poll()
        self.assertEqual(released.call_count, 1)
        drag.close()

    def test_mouse_hook_defers_route_lookup(self):
        resolve = Mock(return_value=None)
        desktop = DesktopOrigin(Mock(), resolve, Mock())
        desktop.last_local = (94, 20)
        event = SimpleNamespace(point=SimpleNamespace(x=99, y=20))

        self.assertFalse(desktop._mouse(0x200, event))
        resolve.assert_not_called()
        desktop.poll()
        resolve.assert_called_once_with((99, 20))
