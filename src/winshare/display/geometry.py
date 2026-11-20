"""Geometry in physical screen pixels, shared by placement and pointer mapping."""

from dataclasses import dataclass

EDGES = ("Izquierda", "Derecha", "Arriba", "Abajo")


@dataclass(frozen=True)
class Rect:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self):
        return self.right - self.left

    @property
    def height(self):
        return self.bottom - self.top

    def contains(self, x, y):
        return self.left <= x < self.right and self.top <= y < self.bottom

    def point(self, x, y):
        return (self.left + round((self.width - 1) * x / 65535),
                self.top + round((self.height - 1) * y / 65535))


@dataclass(frozen=True)
class Monitor:
    name: str
    bounds: Rect
    work: Rect


def touches(rect, other, edge):
    vertical_overlap = max(rect.top, other.top) < min(rect.bottom, other.bottom)
    horizontal_overlap = max(rect.left, other.left) < min(rect.right, other.right)
    return (
        rect.left == other.right and vertical_overlap,
        rect.right == other.left and vertical_overlap,
        rect.top == other.bottom and horizontal_overlap,
        rect.bottom == other.top and horizontal_overlap,
    )[edge]


def at_edge(rect, edge, x, y, margin=10):
    if not rect.contains(x, y):
        return False
    return (x - rect.left, rect.right - 1 - x, y - rect.top, rect.bottom - 1 - y)[edge] < margin


def fit(width, height, area_width, area_height):
    scale = min(area_width / width, area_height / height)
    w, h = max(1, round(width * scale)), max(1, round(height * scale))
    x, y = (area_width - w) // 2, (area_height - h) // 2
    return Rect(x, y, x + w, y + h)


def moved_without_resizing(start, current):
    return ((start.left, start.top) != (current.left, current.top)
            and (start.width, start.height) == (current.width, current.height))


def qualifies_drag(start, end, mouse_at_start, mouse_at_end, cancelled, moved=False):
    return (mouse_at_start and not mouse_at_end and not cancelled and start != end
            and (moved or moved_without_resizing(start, end)))
