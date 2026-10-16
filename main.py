"""Command-line entry point for running Fly-in simulations."""

import argparse
import sys
from pathlib import Path

from src.algorithms.pathfinding import find_k_shortest_paths
from src.domain.graph import Graph
from src.domain.models import MapData
from src.display.visualizer import TerminalVisualizer
from src.parser.map_parser import MapParser
from src.parser.exceptions import ParsingError
from src.simulation.engine import Engine
from src.simulation.models import Drone, MoveKind, PlannedMove
from src.simulation.scheduler import Scheduler


def create_engine(map_data: MapData) -> Engine:
    """Build an engine and assign drones across the best available routes.

    Args:
        map_data: Parsed map containing the drone count and route endpoints.

    Returns:
        An initialized simulation engine.

    Raises:
        ValueError: If no route connects the map's start and end hubs.
    """
    graph = Graph(map_data)
    routes = find_k_shortest_paths(
        graph,
        map_data.start_hub.name,
        map_data.end_hub.name,
        k=2,
    )
    if not routes:
        raise ValueError(
            f"No route exists from '{map_data.start_hub.name}' to "
            f"'{map_data.end_hub.name}'."
        )

    drones = [
        Drone(
            drone_id=drone_id,
            path=tuple(routes[(drone_id - 1) % len(routes)]),
        )
        for drone_id in range(1, map_data.nb_drones + 1)
    ]
    return Engine(Scheduler(graph), drones)


def _format_turn(moves: list[PlannedMove]) -> str:
    """Format the moves recorded for one simulation turn.

    Args:
        moves: Planned moves completed during the turn.

    Returns:
        A space-separated summary, or an empty string when there were no
        moves.
    """
    tokens: list[str] = []
    for move in moves:
        if move.kind == MoveKind.START_TRANSIT:
            location = (
                f"{move.connection.zone_a}-{move.connection.zone_b}"
            )
        else:
            location = move.destination
        tokens.append(f"D{move.drone_id}-{location}")
    return " ".join(tokens)


def main() -> int:
    """Parse command-line options and run the requested simulation.

    Returns:
        Zero on success, or one when map loading or simulation fails.

    Raises:
        SystemExit: If argument parsing fails or help is requested.
    """
    parser = argparse.ArgumentParser(
        description="Run a Fly-in map simulation.",
    )
    parser.add_argument(
        "map_file", nargs="?", help="Path to the map file to simulate"
    )
    parser.add_argument(
        "--map", "--maps", dest="map_option",
        help="Path to the map file to simulate",
    )
    parser.add_argument(
        "--visualize",
        action="store_true",
        help="Open the animated Pygame window alongside terminal output",
    )
    parser.add_argument(
        "--terminal-visualize",
        action="store_true",
        help="Show the interactive terminal dashboard",
    )
    args = parser.parse_args()
    if args.map_file and args.map_option:
        parser.error("provide the map path either positionally or with --map")
    map_file = args.map_option or args.map_file
    if map_file is None:
        parser.error("a map path is required; use --map PATH")

    try:
        map_data = MapParser().parse_file(map_file)
        engine = create_engine(map_data)
        if args.terminal_visualize:
            TerminalVisualizer(map_data, engine).run()
            return 0
        history = engine.run()
        for moves in history:
            print(_format_turn(moves), flush=True)
        if args.visualize:
            from src.display.pygame_visualizer import PygameVisualizer

            PygameVisualizer(
                map_data, engine, map_label=Path(map_file).name
            ).run()
    except (ParsingError, OSError, RuntimeError, ValueError) as error:
        message = f"Error: {error}"
        if (args.visualize or args.terminal_visualize) and sys.stderr.isatty():
            message = f"\033[91m{message}\033[0m"
        print(message, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
