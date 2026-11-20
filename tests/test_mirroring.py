import io
import queue
import socket
import struct
import unittest
from unittest.mock import patch

from winshare.capture.latest import Latest
from winshare.display.geometry import Monitor, Rect, fit, qualifies_drag
from winshare.display.layout import Assignment, available, find_assignment
from winshare.input.target import TargetInput
from winshare.network.protocol import MAX_FRAME, VIDEO_PORT, receive_frame, video_packet
from winshare.network.session import Destination, Origin
from winshare.network.video import receive_video, transmit
from winshare.pairing.security import new_key, tls_context


class GeometryTests(unittest.TestCase):
    def test_unoccupied_edge_and_negative_coordinates(self):
        left = Monitor("left", Rect(-1600, -900, 0, 0), Rect(-1600, -900, 0, 0))
        main = Monitor("main", Rect(0, -600, 2400, 900), Rect(0, -600, 2400, 900))
        assignment = Assignment("host", "Host", "remote", "left", 0)
        self.assertFalse(available([left, main], "left", 1))
        self.assertTrue(available([left, main], "left", 0))
        self.assertEqual(assignment, find_assignment([left, main], [assignment], (-1600, -320)))
        self.assertIsNone(find_assignment([left, main], [assignment], (-1400, -320)))

    def test_letterbox_and_window_mapping(self):
        image = fit(1920, 1080, 800, 800)
        self.assertEqual(image, Rect(0, 175, 800, 625))
        self.assertFalse(image.contains(100, 80))
        self.assertEqual(Rect(-800, 200, 0, 650).point(65535, 65535), (-1, 649))

    def test_ignore_resize_keyboard_move_and_cancel(self):
        a = Rect(0, 0, 10, 10)
        b = Rect(2, 2, 12, 12)
        self.assertTrue(qualifies_drag(a, b, True, False, False))
        self.assertFalse(qualifies_drag(a, b, False, False, False))
        self.assertFalse(qualifies_drag(a, b, True, False, True))
        self.assertFalse(qualifies_drag(a, Rect(0, 0, 11, 11), True, False, False))
        snapped = Rect(0, 0, 1920, 1080)
        self.assertTrue(qualifies_drag(a, snapped, True, False, False, moved=True))
        self.assertFalse(qualifies_drag(a, a, True, False, False, moved=True))


class InputTests(unittest.TestCase):
    @patch("winshare.input.target.windows")
    @patch("winshare.input.target.InputController")
    def test_never_inject_when_foreground_does_not_match(self, controller, windows):
        windows.foreground.return_value = 7
        target = TargetInput(3)
        target.handle({"type": "focus", "active": True})
        target.handle({"type": "key", "vk": 65, "down": True, "extended": False})
        controller.return_value.keyboard.handle.assert_not_called()
        controller.return_value.release.assert_called()
        windows.foreground.return_value = 3
        windows.minimized.return_value = False
        target.handle({"type": "key", "vk": 65, "down": True, "extended": False})
        controller.return_value.keyboard.handle.assert_called_once()
        target.handle({"type": "focus", "active": False})
        self.assertEqual(target.state(), "paused")

    @patch("winshare.input.target.windows")
    @patch("winshare.input.target.InputController")
    def test_pointer_cannot_hit_overlapping_window(self, controller, windows):
        target = TargetInput(3)
        target.requested = True
        windows.minimized.return_value = False
        windows.foreground.return_value = 3
        windows.bounds.return_value = Rect(-900, 0, -200, 600)
        windows.desktop_bounds.return_value = Rect(-1920, 0, 1920, 1080)
        windows.owns_point.return_value = False
        target.handle({"type": "button", "x": 100, "y": 300, "button": 1, "down": True})
        controller.return_value.mouse.handle.assert_not_called()


class NetworkTests(unittest.TestCase):
    def test_frame_limits(self):
        self.assertEqual(receive_frame(io.BytesIO(video_packet(b"frame"))), b"frame")
        self.assertEqual(receive_frame(io.BytesIO(bytes(4))), b"")
        with self.assertRaises(ValueError):
            receive_frame(io.BytesIO(struct.pack("!I", MAX_FRAME + 1)))
        with self.assertRaises(ValueError):
            receive_frame(io.BytesIO(video_packet(b"frame")[:-1]))

    def test_tls_control_bidirectional_and_bad_key(self):
        key = new_key()
        server_events, client_events, endings = queue.Queue(), queue.Queue(), queue.Queue()
        create_server = socket.create_server
        with patch("winshare.network.session.socket.create_server",
                   side_effect=lambda _address, **kwargs: create_server(("127.0.0.1", 0), **kwargs)):
            server = Destination(
                "Destino", [], tls_context(key, server=True), lambda _link: None,
                lambda link, batch: self._reply(link, batch, server_events),
                lambda _link: server_events.put("disconnect"),
            )
        port = patch("winshare.network.session.PORT", server.listener.getsockname()[1])
        port.start()
        self.addCleanup(port.stop)
        self.addCleanup(server.thread.join, 4)
        self.addCleanup(server.stop)
        wrong = Origin("127.0.0.1", tls_context(new_key(), server=False),
                       client_events.put, lambda _batch: None, endings.put)
        self.addCleanup(wrong.thread.join, 4)
        endings.get(timeout=4)
        self.assertTrue(client_events.empty())
        origin = Origin("127.0.0.1", tls_context(key, server=False), client_events.put,
                        lambda batch: client_events.put(batch) if batch else None, endings.put)
        self.addCleanup(origin.thread.join, 4)
        self.addCleanup(origin.stop)
        self.assertEqual("Destino", client_events.get(timeout=4)["name"])
        origin.outbox.send("share", token="sample")
        self.assertEqual("sample", server_events.get(timeout=4)["token"])
        self.assertEqual([{"type": "focus", "active": True}], client_events.get(timeout=4))
        origin.stop()
        self.assertEqual("disconnect", server_events.get(timeout=4))

    @staticmethod
    def _reply(link, batch, events):
        if batch:
            events.put(batch[0])
            link.send("focus", active=True)

    def test_video_heartbeat_frame_and_single_use_token(self):
        key = new_key()
        for sent in ("wrong", "expected"):
            with self.subTest(token=sent):
                failures, source, destination = queue.Queue(), Latest(), Latest()
                listener = socket.create_server(("127.0.0.1", VIDEO_PORT))
                receiver = receive_video(listener, tls_context(key, server=True),
                                         "expected", destination, failures.put, bytes)
                sender = transmit("127.0.0.1", tls_context(key, server=False), sent,
                                  source, failures.put)
                try:
                    if sent == "wrong":
                        self.assertIsNotNone(failures.get(timeout=4))
                        self.assertIsNone(destination.take())
                    else:
                        source.put(b"frame")
                        self.assertEqual(destination.take(4), b"frame")
                        receiver.stop()
                        receiver.thread.join(4)
                        self.assertIsNotNone(failures.get(timeout=4))
                finally:
                    sender.stop()
                    receiver.stop()
                    sender.thread.join(4)
                    receiver.thread.join(4)
