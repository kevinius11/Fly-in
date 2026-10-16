"""Optional terminal dashboard for observing a Fly-in simulation."""

import os
import select
import sys
from collections import Counter
from typing import TextIO

from src.domain.models import Connection, MapData, Zone, ZoneType
from src.simulation.engine import Engine
from src.simulation.models import DroneSnapshot, MoveKind, PlannedMove


_RESET = "\033[0m"
_PALETTE = {
    "cyan": "\033[96m",
    "magenta": "\033[95m",
    "amber": "\033[38;5;214m",
    "yellow": "\033[93m",
    "red": "\033[91m",
    "green": "\033[92m",
    "blue": "\033[94m",
    "white": "\033[97m",
    "orange": "\033[38;5;208m",
    "purple": "\033[38;5;141m",
    "pink": "\033[38;5;213m",
    "teal": "\033[38;5;37m",
    "lime": "\033[38;5;118m",
    "violet": "\033[38;5;135m",
    "gray": "\033[38;5;245m",
    "grey": "\033[38;5;245m",
    "brown": "\033[38;5;130m",
}
_DRONE_COLORS = ("cyan", "magenta", "amber", "green", "blue", "purple")
_TYPE_COLORS = {
    ZoneType.NORMAL: "cyan",
    ZoneType.PRIORITY: "magenta",
    ZoneType.RESTRICTED: "amber",
    ZoneType.BLOCKED: "red",
}
_ZONE_MARKERS = {
    ZoneType.NORMAL: "O",
    ZoneType.PRIORITY: "P",
    ZoneType.RESTRICTED: "R",
    ZoneType.BLOCKED: "X",
}


def _paint(value: str, color: str, enabled: bool) -> str:
    """Wrap text in a known ANSI palette color when output is a terminal."""
    if not enabled:
        return value
    code = _PALETTE.get(color.lower())
    if code is None and len(color) == 7 and color.startswith("#"):
        try:
            red, green, blue = (
                int(color[index:index + 2], 16)
                for index in (1, 3, 5)
            )
        except ValueError:
            return value
        code = f"\033[38;2;{red};{green};{blue}m"
    if code is None:
        return value
    return f"{code}{value}{_RESET}"


def _zone_color(zone: Zone) -> str:
    """Prefer an explicit metadata color and fall back to the zone type."""
    if zone.color is not None:
        color = zone.color.lower()
        if color in _PALETTE or (
            len(color) == 7 and color.startswith("#")
        ):
            return color
    return _TYPE_COLORS[zone.zone_type]


def _connection_key(connection: Connection) -> tuple[str, str]:
    return (
        min(connection.zone_a, connection.zone_b),
        max(connection.zone_a, connection.zone_b),
    )


class TerminalVisualizer:
    """Render and optionally control an Engine in a terminal."""

    def __init__(
        self,
        map_data: MapData,
        engine: Engine,
        *,
        input_stream: TextIO | None = None,
        output_stream: TextIO | None = None,
        frame_delay: float = 0.35,
    ) -> None:
        self._map_data = map_data
        self._engine = engine
        self._input = input_stream if input_stream is not None else sys.stdin
        self._output = (
            output_stream if output_stream is not None else sys.stdout
        )
        self._frame_delay = max(0.05, frame_delay)
        self._paused = False

    def render(self, *, color: bool = False) -> str:
        """Return a complete dashboard frame from the current Engine state."""
        states = self._engine.drone_states
        occupancy: Counter[str | None] = Counter(
            state.current_zone
            for state in states
            if state.current_zone is not None
        )
        transit_states = [
            state for state in states if state.transit_connection is not None
        ]
        delivered = sum(state.is_delivered for state in states)
        active = len(states) - delivered - len(transit_states)
        lines = [
            _paint(
                f"╔═ FLY-IN // NEON CONTROL "
                f"{'═' * 33}╗",
                "cyan", color,
            ),
            _paint(
                "║" + " CITY AIRSPACE GRID // SIMULATION LIVE ".center(60)
                + "║",
                "magenta", color,
            ),
            _paint(
                f"╚{'═' * 60}╝",
                "cyan", color,
            ),
            (f" TURN {self._engine.turns_elapsed:03d}   "
             f"DELIVERED {delivered:02d}/{len(states):02d}   "
             f"ACTIVE {active:02d}   IN TRANSIT {len(transit_states):02d}"),
            "",
            " NETWORK TOPOLOGY",
            *self._render_topology(states, occupancy, color),
            "",
            " ZONE CAPACITY",
            *self._render_zone_capacity(occupancy, color),
            "",
            " CONNECTION LOAD  (current turn)",
            *self._render_connection_capacity(
                transit_states, self._engine.last_moves, color
            ),
            "",
            " TURN EVENT LOG",
            *self._render_events(states, color),
            "",
            " LEGEND  S origin  E destination  O normal  P priority  "
            "R restricted  X blocked",
            " CONTROLS  Space pause/resume  N step  +/- speed  Q quit",
        ]
        return "\n".join(lines)

    def _coordinates(self) -> dict[str, tuple[int, int]]:
        """Use map coordinates, or stable grid positions if they are absent."""
        zones = list(self._map_data.zones.values())
        valid = all(
            isinstance(zone.x, int) and isinstance(zone.y, int)
            for zone in zones
        )
        points = {(zone.x, zone.y) for zone in zones if valid}
        if valid and len(points) == len(zones):
            return {zone.name: (zone.x, zone.y) for zone in zones}

        ordered_names = list(self._map_data.zones)
        return {
            name: ((index % 4) * 3, (index // 4) * 3)
            for index, name in enumerate(ordered_names)
        }

    def _render_topology(
        self,
        states: tuple[DroneSnapshot, ...],
        occupancy: Counter[str | None],
        color: bool,
    ) -> list[str]:
        """Draw a compact, coordinate-based ASCII map and its node labels."""
        coordinates = self._coordinates()
        xs = [point[0] for point in coordinates.values()]
        ys = [point[1] for point in coordinates.values()]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        width = 54
        height = max(3, min(13, len(set(ys)) * 2 + 1))

        def project(point: tuple[int, int]) -> tuple[int, int]:
            x, y = point
            px = 2 if max_x == min_x else 2 + round(
                (x - min_x) * (width - 4) / (max_x - min_x)
            )
            py = height // 2 if max_y == min_y else 1 + round(
                (y - min_y) * (height - 2) / (max_y - min_y)
            )
            return px, py

        canvas = [[" " for _ in range(width)] for _ in range(height)]
        cell_colors: dict[tuple[int, int], str] = {}
        positions = {
            name: project(point) for name, point in coordinates.items()
        }
        for connection in self._map_data.connections:
            start = positions[connection.zone_a]
            end = positions[connection.zone_b]
            self._draw_line(canvas, start, end)

        for state in states:
            if state.transit_connection is None:
                continue
            origin, destination = state.transit_connection
            if origin in positions and destination in positions:
                x = round(
                    (positions[origin][0] + positions[destination][0]) / 2
                )
                y = round(
                    (positions[origin][1] + positions[destination][1]) / 2
                )
                canvas[y][x] = str(state.drone_id % 10)
                cell_colors[(x, y)] = _DRONE_COLORS[
                    (state.drone_id - 1) % len(_DRONE_COLORS)
                ]

        zone_at_position = {point: name for name, point in positions.items()}
        for point, name in zone_at_position.items():
            x, y = point
            zone = self._map_data.zones[name]
            drones_here = [
                state for state in states if state.current_zone == name
            ]
            if len(drones_here) == 1:
                marker = str(drones_here[0].drone_id % 10)
            elif len(drones_here) > 1:
                marker = "*"
            elif zone.is_start:
                marker = "S"
            elif zone.is_end:
                marker = "E"
            else:
                marker = _ZONE_MARKERS[zone.zone_type]
            canvas[y][x] = marker
            cell_colors[(x, y)] = (
                _DRONE_COLORS[(drones_here[0].drone_id - 1)
                              % len(_DRONE_COLORS)]
                if drones_here else _zone_color(zone)
            )

        rendered = []
        for y, row in enumerate(canvas):
            rendered_row = "  " + "".join(
                _paint(char, cell_colors[(x, y)], color)
                if (x, y) in cell_colors else _paint(char, "cyan", color)
                if char == "·" else char
                for x, char in enumerate(row)
            )
            rendered.append(rendered_row.rstrip())
        rendered.append("  NODES")
        for zone in self._map_data.zones.values():
            marker = _ZONE_MARKERS[zone.zone_type]
            role = "START" if zone.is_start else "END" if zone.is_end else ""
            line = f"  {marker} {zone.name} [{zone.zone_type.value}] {role}"
            rendered.append(_paint(line.rstrip(), _zone_color(zone), color))
        for state in states:
            if state.transit_connection is not None:
                continue
            location = state.current_zone or "unknown"
            label = "DELIVERED" if state.is_delivered else "AT"
            tint = _DRONE_COLORS[
                (state.drone_id - 1) % len(_DRONE_COLORS)
            ]
            rendered.append(_paint(
                f"  D{state.drone_id:02d} {label} {location}", tint, color
            ))
        transit_lines = [
            (state.drone_id, state.transit_origin,
             state.transit_destination, state.transit_turns_remaining)
            for state in states if state.transit_connection is not None
        ]
        for (drone_id, transit_origin, transit_destination,
             remaining) in transit_lines:
            elapsed = 2 - (remaining or 0)
            rendered.append(_paint(
                f"  D{drone_id:02d} {transit_origin} -> "
                f"{transit_destination} "
                f"TRANSIT {elapsed}/2",
                "amber", color,
            ))
        return rendered

    @staticmethod
    def _draw_line(
        canvas: list[list[str]],
        start: tuple[int, int],
        end: tuple[int, int],
    ) -> None:
        """Draw a dotted connection using the integer Bresenham algorithm."""
        x0, y0 = start
        x1, y1 = end
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        error = dx - dy
        while (x0, y0) != (x1, y1):
            if (x0, y0) != start and canvas[y0][x0] == " ":
                canvas[y0][x0] = "·"
            doubled = 2 * error
            if doubled > -dy:
                error -= dy
                x0 += sx
            if doubled < dx:
                error += dx
                y0 += sy

    def _render_zone_capacity(
        self,
        occupancy: Counter[str | None],
        color: bool,
    ) -> list[str]:
        """Show physical zone occupancy and the configured/effective limit."""
        lines = []
        for zone in self._map_data.zones.values():
            used = occupancy[zone.name]
            capacity = "∞" if zone.is_start or zone.is_end else str(
                zone.max_drones
            )
            ratio = f"{used}/{capacity}"
            saturated = not (zone.is_start or zone.is_end) and (
                used >= zone.max_drones
            )
            tint = "red" if saturated else _zone_color(zone)
            lines.append(_paint(
                f"  {zone.name:<18} {ratio:<8} {zone.zone_type.value}",
                tint, color,
            ))
        return lines

    def _render_connection_capacity(
        self,
        transit_states: list[DroneSnapshot],
        last_moves: tuple[PlannedMove, ...],
        color: bool,
    ) -> list[str]:
        """Show link use from completed moves and ongoing transits."""
        usage: Counter[tuple[str, str]] = Counter()
        started_this_turn: set[int] = set()
        for move in last_moves:
            key = _connection_key(move.connection)
            usage[key] += 1
            if move.kind == MoveKind.START_TRANSIT:
                started_this_turn.add(move.drone_id)
        for state in transit_states:
            if (state.drone_id in started_this_turn
                    or state.transit_connection is None):
                continue
            origin, destination = state.transit_connection
            usage[(min(origin, destination), max(origin, destination))] += 1
        lines = []
        for connection in self._map_data.connections:
            used = usage[_connection_key(connection)]
            saturated = used >= connection.max_link_capacity and used > 0
            tint = "red" if saturated else "cyan"
            lines.append(_paint(
                f"  {connection.zone_a} <-> {connection.zone_b}  "
                f"{used}/{connection.max_link_capacity}",
                tint, color,
            ))
        return lines

    def _render_events(
        self,
        states: tuple[DroneSnapshot, ...],
        color: bool,
    ) -> list[str]:
        """Describe only the moves recorded by the Engine for this turn."""
        moves = self._engine.last_moves
        if not moves:
            return ["  No movement this turn."]
        state_by_id = {state.drone_id: state for state in states}
        lines = []
        for move in moves:
            if move.kind == MoveKind.START_TRANSIT:
                state = state_by_id[move.drone_id]
                remaining = state.transit_turns_remaining or 0
                elapsed = 2 - remaining
                message = (
                    f"  D{move.drone_id:02d} ENTERS "
                    f"{move.origin} -> {move.destination} "
                    f"(restricted transit {elapsed}/2)"
                )
                tint = "amber"
            elif move.kind == MoveKind.COMPLETE_TRANSIT:
                message = (
                    f"  D{move.drone_id:02d} ARRIVES at {move.destination}"
                )
                tint = "green"
            else:
                message = (
                    f"  D{move.drone_id:02d} {move.origin} -> "
                    f"{move.destination}"
                )
                tint = _DRONE_COLORS[(move.drone_id - 1) % len(_DRONE_COLORS)]
            lines.append(_paint(message, tint, color))
        return lines[-8:]

    def run(self) -> None:
        """Run interactively on a TTY or render every turn without input."""
        interactive = (
            self._input.isatty()
            and self._output.isatty()
            and hasattr(self._input, "fileno")
            and os.name == "posix"
        )
        if interactive:
            self._run_interactive()
            return

        self._write_frame(color=False, clear=False)
        while not self._engine.all_drones_delivered():
            self._advance_checked()
            self._write_frame(color=False, clear=False)

    def _advance_checked(self) -> None:
        """Advance once and preserve Engine.run's deadlock protection."""
        before = self._engine.drone_states
        self._engine.advance_turn()
        if (before == self._engine.drone_states
                and not self._engine.all_drones_delivered()):
            raise RuntimeError(
                "Simulation is deadlocked: no drone state changed."
            )

    def _write_frame(self, *, color: bool, clear: bool) -> None:
        if clear:
            self._output.write("\033[?25l\033[2J\033[H")
        self._output.write(self.render(color=color))
        self._output.write("\n\n")
        self._output.flush()

    def _run_interactive(self) -> None:
        """Poll keyboard controls and advance the simulation frame by frame."""
        import termios
        import tty

        descriptor = self._input.fileno()
        previous_settings = termios.tcgetattr(descriptor)
        try:
            tty.setcbreak(descriptor)
            self._write_frame(color=True, clear=True)
            while not self._engine.all_drones_delivered():
                timeout = 0.1 if self._paused else self._frame_delay
                ready, _, _ = select.select([descriptor], [], [], timeout)
                if ready:
                    command = os.read(descriptor, 1).decode(
                        "utf-8", errors="ignore"
                    ).lower()
                    if command == "q":
                        break
                    if command == " ":
                        self._paused = not self._paused
                    elif command == "n" and self._paused:
                        self._advance_checked()
                    elif command in ("+", "="):
                        self._frame_delay = max(0.05, self._frame_delay / 1.5)
                    elif command == "-":
                        self._frame_delay = min(2.0, self._frame_delay * 1.5)
                elif not self._paused:
                    self._advance_checked()
                self._write_frame(color=True, clear=True)
        finally:
            termios.tcsetattr(descriptor, termios.TCSADRAIN, previous_settings)
            self._output.write("\033[0m\033[?25h\n")
            self._output.flush()
