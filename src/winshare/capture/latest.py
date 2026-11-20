"""A one-element mailbox that drops stale frames under load."""

from threading import Condition


class Latest:
    def __init__(self):
        self._changed = Condition()
        self._value = None

    def put(self, value):
        with self._changed:
            self._value = value
            self._changed.notify()

    def take(self, timeout=0):
        with self._changed:
            if self._value is None and timeout:
                self._changed.wait_for(lambda: self._value is not None, timeout)
            value, self._value = self._value, None
            return value
