"""Optional Pygame window for replaying Engine simulation snapshots."""

import math
import os
import sys
from collections import Counter
from typing import Any

from src.domain.models import MapData, Zone, ZoneType
from src.simulation.engine import Engine
from src.simulation.models import DroneSnapshot


WIDTH = 1180
HEIGHT = 760
_BACKGROUND = (7, 12, 22)
_PANEL = (12, 21, 35)
_GRID = (18, 39, 57)
_CYAN = (22, 224, 255)
_MAGENTA = (255, 69, 212)
_AMBER = (255, 194, 71)
_RED = (255, 64, 94)
_WHITE = (226, 240, 255)
_MUTED = (117, 143, 166)
_DRONE_COLORS = (
    _CYAN, _MAGENTA, _AMBER, (125, 255, 154),
    (117, 141, 255), (245, 130, 255), (255, 120, 97),
)
_ZONE_COLORS = {
    ZoneType.NORMAL: _CYAN,
    ZoneType.PRIORITY: _MAGENTA,
    ZoneType.RESTRICTED: _AMBER,
    ZoneType.BLOCKED: _RED,
}
_NAMED_COLORS = {
    "cyan": _CYAN, "magenta": _MAGENTA, "amber": _AMBER,
    "yellow": (255, 228, 94), "red": _RED, "green": (125, 255, 154),
    "blue": (117, 141, 255), "white": _WHITE,
    "orange": (255, 141, 69), "purple": (181, 140, 255),
    "pink": (255, 114, 207), "teal": (76, 235, 208),
    "lime": (197, 255, 85), "violet": (189, 131, 255),
}


def metadata_color(zone: Zone) -> tuple[int, int, int]:
    """Resolve a zone's metadata color or use its type color."""
    if zone.color is not None:
        value = zone.color.lower()
        if value in _NAMED_COLORS:
            return _NAMED_COLORS[value]
        if len(value) == 7 and value.startswith("#"):
            try:
                return tuple(
                    int(value[index:index + 2], 16)
                    for index in (1, 3, 5)
                )  # type: ignore[return-value]
            except ValueError:
                pass
    return _ZONE_COLORS[zone.zone_type]


def map_positions(
    map_data: MapData, area: tuple[int, int, int, int]
) -> dict[str, tuple[float, float]]:
    """Place zones from map coordinates or a stable grid fallback."""
    left, top, width, height = area
    zones = list(map_data.zones.values())
    raw = {zone.name: (zone.x, zone.y) for zone in zones}
    if len(set(raw.values())) == len(zones):
        xs = [point[0] for point in raw.values()]
        ys = [point[1] for point in raw.values()]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        scale = min(
            (width - 100) / max(max_x - min_x, 1),
            (height - 100) / max(max_y - min_y, 1),
        )
        return {
            name: (
                left + width / 2 + (x - (min_x + max_x) / 2) * scale,
                top + height / 2 - (y - (min_y + max_y) / 2) * scale,
            )
            for name, (x, y) in raw.items()
        }
    columns = min(6, max(1, math.ceil(math.sqrt(len(zones)))))
    rows = math.ceil(len(zones) / columns)
    return {
        zone.name: (
            left + 50
            + (index % columns) * (width - 100) / max(columns - 1, 1),
            top + 50
            + (index // columns) * (height - 100) / max(rows - 1, 1),
        )
        for index, zone in enumerate(zones)
    }


def drone_position(
    state: DroneSnapshot,
    positions: dict[str, tuple[float, float]],
) -> tuple[float, float] | None:
    """Return zone position or midpoint while the Engine says in transit."""
    if state.transit_connection is not None:
        start, end = state.transit_connection
        start_pos, end_pos = positions[start], positions[end]
        return ((start_pos[0] + end_pos[0]) / 2,
                (start_pos[1] + end_pos[1]) / 2)
    if state.current_zone is None:
        return None
    return positions[state.current_zone]


def connection_usage(
    states: tuple[DroneSnapshot, ...],
) -> Counter[tuple[str, str]]:
    """Count Engine-reported drones currently traversing each connection."""
    loads: Counter[tuple[str, str]] = Counter()
    for state in states:
        if state.transit_connection is None:
            continue
        left, right = state.transit_connection
        loads[_connection_key(left, right)] += 1
    return loads


def _connection_key(left: str, right: str) -> tuple[str, str]:
    return (left, right) if left <= right else (right, left)


def has_visible_display(driver: str) -> bool:
    """Return whether SDL selected a driver capable of showing a window."""
    return driver not in {"offscreen", "dummy"}


class PygameVisualizer:
    """Display a controllable animation of recorded Engine state."""

    def __init__(self, map_data: MapData, engine: Engine) -> None:
        self._map_data = map_data
        self._engine = engine

    def run(self) -> bool:
        """Open the Pygame window; return False if Pygame/display is absent."""
        try:
            os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
            import pygame
        except ImportError:
            print(
                "Pygame is not installed. Run `make install` to enable "
                "the visualizer.",
                file=sys.stderr,
            )
            return False
        try:
            return self._play(pygame)
        except pygame.error as error:
            print(f"Pygame visualizer unavailable: {error}",
                  file=sys.stderr)
            return False

    def _play(self, pygame: Any) -> bool:
        pygame.init()
        screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
        if not has_visible_display(pygame.display.get_driver()):
            pygame.quit()
            print(
                "Pygame selected SDL's offscreen display, so no window can "
                "be shown. Run `make run` from a graphical desktop session "
                "with X11 or Wayland available.",
                file=sys.stderr,
            )
            return False
        pygame.display.set_caption("FLY-IN // NEON CONTROL")
        clock = pygame.time.Clock()
        font = pygame.font.Font(None, 22)
        small = pygame.font.Font(None, 16)
        history = self._engine.state_history
        if not history:
            pygame.quit()
            return True
        frame_index = 0
        playing = True
        speed = 1.0
        elapsed = 0.0
        running = True
        while running:
            dt = clock.tick(60) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_q):
                        running = False
                    elif event.key == pygame.K_SPACE:
                        playing = not playing
                    elif event.key == pygame.K_n:
                        playing = False
                        frame_index = min(frame_index + 1, len(history) - 1)
                    elif event.key == pygame.K_r:
                        frame_index, elapsed = 0, 0.0
                    elif event.key in (pygame.K_EQUALS, pygame.K_PLUS):
                        speed = min(speed + 0.5, 4.0)
                    elif event.key == pygame.K_MINUS:
                        speed = max(speed - 0.5, 0.5)
            if playing:
                elapsed += dt * speed
                if elapsed >= 0.65:
                    if frame_index < len(history) - 1:
                        frame_index += 1
                        elapsed = 0.0
                    else:
                        elapsed = 0.65
                        playing = False
            screen.fill(_BACKGROUND)
            self._draw(screen, pygame, font, small, history[frame_index],
                       frame_index, speed, playing,
                       min(elapsed / 0.65, 1.0), history)
            pygame.display.flip()
        pygame.quit()
        return True

    def _draw(
        self,
        screen: Any,
        pygame: Any,
        font: Any,
        small: Any,
        states: tuple[DroneSnapshot, ...],
        frame_index: int,
        speed: float,
        playing: bool,
        progress: float,
        history: tuple[tuple[DroneSnapshot, ...], ...],
    ) -> None:
        width, height = screen.get_size()
        pygame.draw.rect(
            screen, _PANEL, (18, 18, width - 36, 76), border_radius=8
        )
        _text(screen, font, "FLY-IN // NEON CONTROL", (35, 29), _CYAN)
        delivered = sum(state.is_delivered for state in states)
        transit = sum(state.transit_connection is not None for state in states)
        _text(screen, small,
              f"TURN {frame_index:03d}    DELIVERED {delivered}/{len(states)}"
              f"    ACTIVE {len(states) - delivered - transit}"
              f"    IN TRANSIT {transit}", (38, 62), _WHITE)
        map_area = (25, 118, int(width * 0.68), height - 160)
        pygame.draw.rect(screen, _PANEL,
                         (map_area[0], map_area[1], map_area[2], map_area[3]),
                         border_radius=8)
        for x in range(map_area[0], map_area[0] + map_area[2], 28):
            pygame.draw.line(screen, _GRID, (x, map_area[1]),
                             (x, map_area[1] + map_area[3]))
        for y in range(map_area[1], map_area[1] + map_area[3], 28):
            pygame.draw.line(screen, _GRID, (map_area[0], y),
                             (map_area[0] + map_area[2], y))
        positions = map_positions(self._map_data, map_area)
        loads = connection_usage(states)
        for connection in self._map_data.connections:
            start = positions[connection.zone_a]
            end = positions[connection.zone_b]
            pygame.draw.line(
                screen, (41, 73, 91),
                tuple(round(value) for value in start),
                tuple(round(value) for value in end), 3,
            )
            middle = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
            key = _connection_key(connection.zone_a, connection.zone_b)
            used = loads[key]
            load_color = (
                _RED
                if used >= connection.max_link_capacity and used
                else _MUTED
            )
            _text(screen, small,
                  f"{used}/{connection.max_link_capacity}",
                  middle, load_color, center=True)
        usage: Counter[str] = Counter(
            state.current_zone for state in states
            if state.current_zone is not None
        )
        for zone in self._map_data.zones.values():
            zone_position = positions[zone.name]
            point = (round(zone_position[0]), round(zone_position[1]))
            color = metadata_color(zone)
            pygame.draw.circle(screen, color, point, 20, 2)
            pygame.draw.circle(screen, _PANEL, point, 15)
            mark = (
                "S" if zone.is_start else "E" if zone.is_end
                else zone.zone_type.value[0].upper()
            )
            _text(screen, small, mark, point, color, center=True)
            _text(screen, small, zone.name,
                  (point[0], point[1] + 29), _WHITE, center=True)
            cap = "∞" if zone.is_start or zone.is_end else str(zone.max_drones)
            capacity_color = (
                _RED
                if not (zone.is_start or zone.is_end)
                and usage[zone.name] >= zone.max_drones
                else _MUTED
            )
            _text(screen, small, f"{usage[zone.name]}/{cap}",
                  (point[0], point[1] + 43), capacity_color, center=True)
        previous_states = {
            state.drone_id: state
            for state in history[frame_index - 1]
        } if frame_index else {}
        for state in states:
            target = drone_position(state, positions)
            if target is None:
                continue
            prior = previous_states.get(state.drone_id)
            previous = drone_position(prior, positions) if prior else target
            if previous is None:
                previous = target
            drone_center = (
                previous[0] + (target[0] - previous[0]) * progress,
                previous[1] + (target[1] - previous[1]) * progress,
            )
            color = _DRONE_COLORS[(state.drone_id - 1) % len(_DRONE_COLORS)]
            x, y = round(drone_center[0]), round(drone_center[1] - 26)
            pygame.draw.circle(screen, color, (x, y), 9)
            _text(screen, small, f"{state.drone_id}", (x, y), _BACKGROUND,
                  center=True)
            if state.transit_turns_remaining is not None:
                progress = 2 - state.transit_turns_remaining
                _text(screen, small, f"TRANSIT {progress}/2", (x, y - 15),
                      _AMBER, center=True)
        panel_x = map_area[0] + map_area[2] + 18
        pygame.draw.rect(screen, _PANEL,
                         (panel_x, 118, width - panel_x - 25, height - 160),
                         border_radius=8)
        y = 140
        _text(screen, font, "ZONE CAPACITY", (panel_x + 16, y), _MAGENTA)
        y += 29
        for zone in self._map_data.zones.values():
            cap = "∞" if zone.is_start or zone.is_end else str(zone.max_drones)
            _text(screen, small,
                  f"{zone.name}: {usage[zone.name]}/{cap}",
                  (panel_x + 16, y), _WHITE)
            y += 21
        y += 14
        _text(screen, font, "CONNECTION LOAD", (panel_x + 16, y), _AMBER)
        y += 28
        for connection in self._map_data.connections:
            key = _connection_key(connection.zone_a, connection.zone_b)
            used = loads[key]
            _text(
                screen, small,
                f"{connection.zone_a} - {connection.zone_b}: "
                f"{used}/{connection.max_link_capacity}",
                (panel_x + 16, y),
                (_RED if used >= connection.max_link_capacity and used
                 else _WHITE),
            )
            y += 19
        y += 10
        _text(screen, font, "EVENT LOG", (panel_x + 16, y), _CYAN)
        y += 28
        moves = self._engine.history[frame_index - 1] if frame_index else []
        for move in moves[-8:]:
            _text(screen, small,
                  f"D{move.drone_id} -> {move.destination}",
                  (panel_x + 16, y),
                  _AMBER if move.kind.value == "start_transit" else _WHITE)
            y += 20
        status = "PLAYING" if playing else "PAUSED"
        _text(screen, small,
              f"{status}  {speed:g}x   SPACE pause  N step  +/- speed  "
              "R reset  Q quit",
              (30, height - 27), _MUTED)


def _text(
    screen: Any,
    font: Any,
    value: str,
    point: tuple[int, int] | tuple[float, float],
    color: tuple[int, int, int],
    *,
    center: bool = False,
) -> None:
    surface = font.render(value, True, color)
    rect = surface.get_rect()
    if center:
        rect.center = (round(point[0]), round(point[1]))
    else:
        rect.topleft = (round(point[0]), round(point[1]))
    screen.blit(surface, rect)
