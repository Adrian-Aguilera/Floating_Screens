import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from winshare.display.geometry import Monitor, Rect
from winshare.input.clipboard import Clipboard, valid_text
from winshare.input.desktop import DesktopDestination, DesktopOrigin
from winshare.input.seam import edge_point, fraction, move, normalized, opposite
from winshare.network.session import Outbox


class SeamTests(unittest.TestCase):
    def test_crossing_right_into_a_screen_with_a_different_origin(self):
        source = Rect(-1600, -900, 0, 0)
        target = Rect(2560, 200, 4480, 1280)
        position = fraction(source, 1, (-1, -450))
        point = edge_point(target, opposite(1), position, inset=1)
        self.assertEqual(point, (2561, 740))
        self.assertEqual(move(target, 0, point, (-4, 0), True), (2560, 740))
        self.assertIsNone(move(target, 0, point, (-4, 0), False))
        self.assertEqual(normalized(target, (2560, 200)), {"x": 0, "y": 0})

    def test_vertical_crossing_preserves_horizontal_position(self):
        source = Rect(0, 100, 1280, 820)
        target = Rect(-1600, -1200, 0, 0)
        position = fraction(source, 2, (639, 100))
        self.assertEqual(edge_point(target, opposite(2), position, inset=1), (-801, -2))


class ClipboardTests(unittest.TestCase):
    @patch("winshare.input.clipboard.sequence")
    def test_remote_clipboard_write_does_not_echo(self, sequence):
        sequence.return_value = 10
        root = Mock()
        clipboard = Clipboard(root)
        root.clipboard_get.return_value = "Copiado en destino"
        clipboard.apply("Copiado en destino")
        root.clipboard_append.assert_called_once_with("Copiado en destino")
        self.assertIsNone(clipboard.changed())
        sequence.return_value = 11
        root.clipboard_get.return_value = "Nuevo texto"
        self.assertEqual(clipboard.changed(), "Nuevo texto")

    def test_wire_size_and_invalid_unicode(self):
        self.assertTrue(valid_text("á 🙂\n"))
        for invalid in (None, "\x00", chr(0xD800), "ñ" * 6000, "\n" * 6000):
            with self.subTest(value=type(invalid)):
                self.assertFalse(valid_text(invalid))


class DesktopTests(unittest.TestCase):
    @patch("winshare.input.desktop.set_cursor", return_value=True)
    @patch("winshare.input.desktop.Clipboard")
    @patch("winshare.input.desktop.windows")
    def test_ack_then_enter_and_release_on_return(self, windows, clipboard, set_cursor):
        bounds = Rect(0, 0, 1600, 900)
        remote = Rect(-1920, 0, 0, 1080)
        link = SimpleNamespace(outbox=Outbox(), stopped=Mock())
        link.stopped.is_set.return_value = False
        windows.down.return_value = False
        windows.cursor.return_value = (1599, 450)
        clipboard.return_value.changed.return_value = "texto"
        assignment = SimpleNamespace(edge=1, remote="remote")
        handoff = DesktopOrigin(Mock(), lambda _point: (
            link, assignment, Monitor("local", bounds, bounds), Monitor("remote", remote, remote)
        ), Mock())

        handoff._begin((1599, 450), (4, 0))
        self.assertFalse(handoff.active)
        enter, = link.outbox.batch()
        self.assertEqual(enter["type"], "desktop_enter")
        handoff.receive(link, {"type": "desktop_ready", "token": "wrong"})
        self.assertFalse(handoff.active)
        handoff.receive(link, {"type": "desktop_ready", "token": enter["token"]})
        self.assertTrue(handoff.active)
        self.assertEqual([packet["type"] for packet in link.outbox.batch()],
                         ["desktop_activate", "desktop_clipboard"])
        x, y = handoff.parked
        event = SimpleNamespace(point=SimpleNamespace(x=x - 4, y=y))
        self.assertTrue(handoff._mouse(0x200, event))
        handoff.poll()
        self.assertFalse(handoff.active)
        leave, = link.outbox.batch()
        self.assertEqual(leave["type"], "desktop_leave")
        self.assertEqual(set_cursor.call_args.args[0], bounds.right - 13)

    @patch("winshare.input.desktop.InputController")
    @patch("winshare.input.desktop.Clipboard")
    @patch("winshare.input.desktop.windows")
    def test_destination_accepts_input_only_after_activation(self, windows, _clipboard, controller):
        bounds = Rect(-1600, 0, 0, 900)
        windows.monitors.return_value = [Monitor("remote", bounds, bounds)]
        windows.desktop_bounds.return_value = Rect(-1600, 0, 1920, 1080)
        link = Outbox()
        message = {"token": "a" * 32, "monitor": "remote", "edge": 1, "position": 32768}
        handoff = DesktopDestination(Mock(), link, message)
        key = {"type": "desktop_key", "vk": 65, "down": True, "extended": False}
        handoff.handle(key)
        controller.return_value.keyboard.handle.assert_not_called()
        self.assertEqual(link.batch()[0]["type"], "desktop_ready")
        handoff.activate()
        controller.return_value.mouse.handle.assert_called_once()
        handoff.handle(key)
        controller.return_value.keyboard.handle.assert_called_once_with(key)
        handoff.close()
        controller.return_value.release.assert_called_once()
