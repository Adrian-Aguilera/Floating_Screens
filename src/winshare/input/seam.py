"""Mapping between the two sides of a configured monitor seam."""

from ..display.geometry import at_edge


def opposite(edge):
    return edge ^ 1


def fraction(rect, edge, point):
    x, y = point
    if edge < 2:
        return round(65535 * (y - rect.top) / max(1, rect.height - 1))
    return round(65535 * (x - rect.left) / max(1, rect.width - 1))


def edge_point(rect, edge, position, inset=0):
    x, y = rect.point(position, position)
    return (
        (min(rect.right - 1, rect.left + inset), y),
        (max(rect.left, rect.right - 1 - inset), y),
        (x, min(rect.bottom - 1, rect.top + inset)),
        (x, max(rect.top, rect.bottom - 1 - inset)),
    )[edge]


def outward(edge, dx, dy):
    return (-dx, dx, -dy, dy)[edge]


def move(rect, edge, point, delta, held):
    x, y = point
    dx, dy = delta
    limit = (x - rect.left, rect.right - 1 - x, y - rect.top, rect.bottom - 1 - y)[edge]
    if not held and outward(edge, dx, dy) > limit:
        return None
    return (
        min(rect.right - 1, max(rect.left, x + dx)),
        min(rect.bottom - 1, max(rect.top, y + dy)),
    )


def touches_edge(rect, edge, point):
    return at_edge(rect, edge, *point, margin=1)


def normalized(rect, point):
    x, y = point
    return {
        "x": round(65535 * (x - rect.left) / max(1, rect.width - 1)),
        "y": round(65535 * (y - rect.top) / max(1, rect.height - 1)),
    }
