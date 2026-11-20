"""Capture one HWND and encode the most recent frame off the capture thread."""

import io
import threading
import time

from PIL import Image
from windows_capture import WindowsCapture

from .latest import Latest


def decode(frame):
    try:
        image = Image.open(io.BytesIO(frame), formats=["JPEG"])
    except Image.DecompressionBombError as error:
        raise ValueError("Dimensiones de video inválidas.") from error
    with image:
        if image.width > 1920 or image.height > 1080:
            raise ValueError("Dimensiones de video inválidas.")
        return image.convert("RGB")


class WindowCapture:
    def __init__(self, hwnd, frames, failed):
        self.stopped = threading.Event()
        self.raw = Latest()
        self.capture = WindowsCapture(window_hwnd=hwnd, cursor_capture=False)
        last = 0.0

        @self.capture.event
        def on_frame_arrived(frame, capture_control):
            nonlocal last
            now = time.monotonic()
            if not self.stopped.is_set() and now - last >= 1 / 30:
                last = now
                self.raw.put(frame.frame_buffer.copy())

        @self.capture.event
        def on_closed():
            if not self.stopped.is_set():
                failed("La ventana compartida se cerró.")

        self.control = self.capture.start_free_threaded()
        threading.Thread(target=self._encode, args=(frames, failed), daemon=True).start()

    def _encode(self, frames, failed):
        try:
            while not self.stopped.is_set():
                pixels = self.raw.take(0.2)
                if pixels is None:
                    continue
                height, width = pixels.shape[:2]
                image = Image.frombytes("RGB", (width, height), pixels.tobytes(), "raw", "BGRX")
                image.thumbnail((1920, 1080), Image.Resampling.BILINEAR)
                output = io.BytesIO()
                image.save(output, format="JPEG", quality=75)
                frames.put(output.getvalue())
        except (OSError, ValueError) as error:
            if not self.stopped.is_set():
                failed(str(error))

    def stop(self):
        self.stopped.set()
        def stop_capture():
            if not self.control.is_finished():
                self.control.stop()

        threading.Thread(target=stop_capture, daemon=True).start()
