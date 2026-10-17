"""Render and control an animated view of recorded simulation snapshots."""

import math
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from src.domain.models import MapData, Zone, ZoneType
from src.simulation.engine import Engine
from src.simulation.models import DroneSnapshot


WIDTH = 1440
HEIGHT = 900
_BACKGROUND = (15, 16, 18)
_PANEL = (25, 26, 29)
_GRID = (48, 49, 53)
_CYAN = (160, 164, 170)
_MAGENTA = (192, 190, 190)
_AMBER = (220, 163, 79)
_RED = (211, 35, 49)
_WHITE = (235, 233, 229)
_MUTED = (139, 140, 144)
_DRONE_COLORS = (
    (211, 35, 49), (232, 82, 89), (174, 28, 42),
    (241, 119, 120), (190, 48, 62), (220, 163, 79),
    (210, 210, 207),
)
_ZONE_COLORS = {
    ZoneType.NORMAL: (190, 191, 194),
    ZoneType.PRIORITY: (211, 35, 49),
    ZoneType.RESTRICTED: (220, 163, 79),
    ZoneType.BLOCKED: (115, 48, 54),
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
    """Resolve a zone's metadata color or use its type color.

    Args:
        zone: Zone whose display color should be resolved.

    Returns:
        RGB color tuple.
    """
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


def _display_color(color: tuple[int, int, int]) -> tuple[int, int, int]:
    """Blend a map color into the display's muted graphite palette.

    Args:
        color: Source RGB color.

    Returns:
        Muted RGB color tuple.
    """
    base = (45, 31, 34)
    return (
        round(color[0] * 0.48 + base[0] * 0.52),
        round(color[1] * 0.48 + base[1] * 0.52),
        round(color[2] * 0.48 + base[2] * 0.52),
    )


def map_positions(
    map_data: MapData, area: tuple[int, int, int, int]
) -> dict[str, tuple[float, float]]:
    """Project zones into a display area using map coordinates when possible.

    Args:
        map_data: Map containing the zones to position.
        area: Left, top, width, and height of the available drawing area.

    Returns:
        A mapping from zone name to its pixel coordinates.
    """
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
    """Find a drone's rendered position from its snapshot.

    Args:
        state: Snapshot for the drone to position.
        positions: Pixel positions indexed by zone name.

    Returns:
        Zone position, connection midpoint while in transit, or None if the
        drone has no current location.
    """
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
    """Count drones currently traversing each connection.

    Args:
        states: Drone snapshots for one simulation frame.

    Returns:
        A counter keyed by normalized endpoint pairs.
    """
    loads: Counter[tuple[str, str]] = Counter()
    for state in states:
        if state.transit_connection is None:
            continue
        left, right = state.transit_connection
        loads[_connection_key(left, right)] += 1
    return loads


def _connection_key(left: str, right: str) -> tuple[str, str]:
    """Normalize a connection's endpoints for direction-independent lookup.

    Args:
        left: Name of one endpoint.
        right: Name of the other endpoint.

    Returns:
        The endpoint names in lexicographic order.
    """
    return (left, right) if left <= right else (right, left)


def has_visible_display(driver: str) -> bool:
    """Check whether SDL selected a driver capable of showing a window.

    Args:
        driver: Name reported by SDL for its active display driver.

    Returns:
        True for a visible display driver; otherwise False.
    """
    return driver not in {"offscreen", "dummy"}


class PygameVisualizer:
    """Display a controllable animation of recorded Engine state."""

    def __init__(
        self, map_data: MapData, engine: Engine, *, map_label: str = ""
    ) -> None:
        """Store map and engine data for later rendering.

        Args:
            map_data: Static map whose zones and connections are displayed.
            engine: Engine containing recorded state snapshots.
            map_label: Optional label shown in the window header.
        """
        self._map_data = map_data
        self._engine = engine
        self._map_label = map_label or "Simulation map"

    def run(self) -> bool:
        """Open the Pygame window and run animation playback.

        Returns:
            True if the visualizer exits normally, or False if Pygame/display
            support is unavailable.
        """
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
        """Initialize Pygame and run the snapshot playback loop.

        Args:
            pygame: Imported Pygame module used for display and events.

        Returns:
            True when playback exits normally; False for a headless driver.
        """
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
        pygame.display.set_caption(
            f"ARASAKA CORPORATION — {self._map_label}"
        )
        backdrop_path = (
            Path(__file__).resolve().parents[2]
            / "assets"
            / "arasaka_wallpaper.jpg"
        )
        backdrop_image = (
            pygame.image.load(str(backdrop_path)).convert()
            if backdrop_path.is_file() else None
        )
        backdrop_size: tuple[int, int] | None = None
        backdrop_surface = None
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
                        elapsed = 0.0
                    elif event.key == pygame.K_p:
                        playing = False
                        frame_index = max(frame_index - 1, 0)
                        elapsed = 0.0
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
            if backdrop_image is not None:
                size = screen.get_size()
                if size != backdrop_size:
                    backdrop_surface = pygame.transform.smoothscale(
                        backdrop_image, size
                    )
                    backdrop_surface.set_alpha(132)
                    backdrop_size = size
                screen.blit(backdrop_surface, (0, 0))
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
        """Draw one simulation frame and its playback controls.

        Args:
            screen: Active display surface.
            pygame: Pygame module providing drawing operations.
            font: Main display font.
            small: Compact label font.
            states: Drone snapshots for the current frame.
            frame_index: Index of the current frame in history.
            speed: Playback speed multiplier.
            playing: Whether playback is advancing automatically.
            progress: Interpolation progress between frames in the range 0–1.
            history: Recorded snapshots used to interpolate drone positions.
        """
        width, height = screen.get_size()
        delivered = sum(state.is_delivered for state in states)
        transit = sum(state.transit_connection is not None for state in states)
        underway = len(states) - delivered
        logo = [(31, 25), (42, 25), (52, 48), (45, 48),
                (41, 39), (37, 48), (30, 48), (38, 31)]
        pygame.draw.polygon(screen, _RED, logo, 2)
        _text(screen, font, "ARASAKA", (63, 19), _WHITE)
        _text(screen, small,
              f"CORPORATION  /  MAP: {self._map_label.upper()}",
              (64, 48), _RED)
        _text(screen, small, f"TURN  {frame_index:02d}", (width - 155, 27),
              _WHITE)
        summary = (
            f"{delivered} of {len(states)} drones delivered   ·   "
            f"{underway} still travelling   ·   {transit} on restricted links"
        )
        _text(screen, small, summary, (width - 370, 54), _MUTED)
        pygame.draw.line(screen, _GRID, (30, 82), (width - 30, 82), 1)

        map_left, map_top = 30, 108
        zones = list(self._map_data.zones.values())
        xs = [zone.x for zone in zones]
        coordinate_width = max(xs) - min(xs) if xs else 0
        # Los mapas largos usan el espacio lateral para mostrar toda la red.
        show_sidebar = coordinate_width <= 12
        side_width = (
            min(330, max(270, int(width * 0.29))) if show_sidebar else 0
        )
        gap = 28 if show_sidebar else 0
        map_width = width - map_left - side_width - gap - 30
        map_height = max(250, height - 165)
        map_area = (map_left, map_top, map_width, map_height)
        positions = map_positions(self._map_data, map_area)
        loads = connection_usage(states)
        for connection in self._map_data.connections:
            start = positions[connection.zone_a]
            end = positions[connection.zone_b]
            pygame.draw.line(
                screen, (91, 91, 83),
                tuple(round(value) for value in start),
                tuple(round(value) for value in end), 2,
            )
            middle = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
            key = _connection_key(connection.zone_a, connection.zone_b)
            used = loads[key]
            if used:
                _text(
                    screen, small,
                    f"{used}/{connection.max_link_capacity}",
                    middle, _AMBER, center=True,
                )
        usage: Counter[str] = Counter(
            state.current_zone for state in states
            if state.current_zone is not None
        )
        for zone in self._map_data.zones.values():
            zone_position = positions[zone.name]
            point = (round(zone_position[0]), round(zone_position[1]))
            color = _display_color(metadata_color(zone))
            pygame.draw.circle(screen, color, point, 17, 2)
            pygame.draw.circle(screen, _BACKGROUND, point, 13)
            mark = (
                "S" if zone.is_start else "E" if zone.is_end
                else zone.zone_type.value[0].upper()
            )
            _text(screen, small, mark, point, color, center=True)
            if show_sidebar:
                _text(screen, small, zone.name,
                      (point[0], point[1] + 27), _WHITE, center=True)
            else:
                label = pygame.transform.rotate(
                    small.render(zone.name, True, _WHITE), 90
                )
                label_rect = label.get_rect(
                    center=(point[0] + 24, point[1] + 4)
                )
                screen.blit(label, label_rect)
            place_count = (
                f"{usage[zone.name]} here"
                if zone.is_start or zone.is_end
                else f"{usage[zone.name]}/{zone.max_drones} here"
            )
            _text(screen, small, place_count,
                  (point[0], point[1] + 40), _MUTED, center=True)
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
            x, y = round(drone_center[0]), round(drone_center[1] - 24)
            pygame.draw.circle(screen, _BACKGROUND, (x, y), 11)
            pygame.draw.circle(screen, color, (x, y), 8)
            _text(screen, small, f"{state.drone_id}", (x, y), _PANEL,
                  center=True)
            if state.transit_turns_remaining is not None:
                transit_progress = 2 - state.transit_turns_remaining
                _text(screen, small,
                      f"slow link · {transit_progress}/2", (x, y - 15),
                      _AMBER, center=True)

        panel_x = map_area[0] + map_area[2] + gap
        if show_sidebar:
            pygame.draw.rect(screen, _RED, (panel_x, map_top, 3, 21))
            _text(screen, font, "Flight log", (panel_x + 12, map_top), _WHITE)
            y = map_top + 31
            moves = (
                self._engine.history[frame_index - 1] if frame_index else []
            )
            if not moves:
                _text(screen, small, "No activity recorded", (panel_x + 12, y),
                      _MUTED)
            for move in moves[-5:]:
                _text(screen, small,
                      f"Drone {move.drone_id}  ->  {move.destination}",
                      (panel_x + 12, y),
                      _AMBER if move.kind.value == "start_transit" else _WHITE)
                y += 19
            _text(screen, small, "Place labels show drones / limit.",
                  (panel_x, height - 75), _MUTED)
            _text(screen, small, "Link labels appear while in use.",
                  (panel_x, height - 55), _MUTED)
        status = "PLAYING" if playing else "PAUSED"
        pygame.draw.line(screen, _GRID, (30, height - 39),
                         (width - 30, height - 39), 1)
        _text(screen, small,
              f"{status.lower()} · {speed:g}×     Space pause/resume  ·  "
              "P previous  ·  N next  ·  R restart  ·  Q close",
              (30, height - 28), _MUTED)


def _text(
    screen: Any,
    font: Any,
    value: str,
    point: tuple[int, int] | tuple[float, float],
    color: tuple[int, int, int],
    *,
    center: bool = False,
) -> None:
    """Render text at a top-left point or centered on a point.

    Args:
        screen: Surface to draw the rendered text on.
        font: Font used to render the value.
        value: Text content to display.
        point: Pixel coordinates for placement.
        color: RGB text color.
        center: Whether ``point`` is the text center instead of its top-left.
    """
    surface = font.render(value, True, color)
    rect = surface.get_rect()
    if center:
        rect.center = (round(point[0]), round(point[1]))
    else:
        rect.topleft = (round(point[0]), round(point[1]))
    screen.blit(surface, rect)
