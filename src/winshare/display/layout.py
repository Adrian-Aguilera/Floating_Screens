"""Monitor assignments and edge selection."""

from dataclasses import asdict, dataclass

from .geometry import Monitor, Rect, at_edge, touches


@dataclass(frozen=True)
class Assignment:
    address: str
    name: str
    remote: str
    local: str
    edge: int


def wire_monitors(monitors):
    return [asdict(monitor) for monitor in monitors[:32]]


def available(monitors, name, edge):
    local = next((monitor for monitor in monitors if monitor.name == name), None)
    return local is not None and not any(
        touches(local.bounds, other.bounds, edge)
        for other in monitors if other != local
    )


def find_assignment(monitors, assignments, point):
    for monitor in monitors:
        if monitor.bounds.contains(*point):
            candidates = (
                assignment for assignment in assignments
                if assignment.local == monitor.name
                and available(monitors, monitor.name, assignment.edge)
                and at_edge(monitor.bounds, assignment.edge, *point)
            )
            return min(candidates, key=lambda assignment: assignment.edge, default=None)
    return None


def read_monitors(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 32:
        raise ValueError("El destino no anunció pantallas válidas.")
    result = []
    names = set()
    for item in value:
        name = item.get("name") if isinstance(item, dict) else None
        if not isinstance(name, str) or not 1 <= len(name) <= 32 or name in names:
            raise ValueError("Identificador de pantalla inválido.")
        geometry = []
        for key in ("bounds", "work"):
            data = item.get(key)
            if not isinstance(data, dict) or set(data) != {"left", "top", "right", "bottom"}:
                raise ValueError("Geometría de pantalla inválida.")
            if any(type(v) is not int or abs(v) > 65536 for v in data.values()):
                raise ValueError("Coordenadas de pantalla inválidas.")
            rect = Rect(**data)
            if rect.width <= 0 or rect.height <= 0:
                raise ValueError("Dimensiones de pantalla inválidas.")
            geometry.append(rect)
        names.add(name)
        result.append(Monitor(name, *geometry))
    return result
