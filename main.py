import argparse

from src.algorithms.pathfinding import find_k_shortest_paths
from src.domain.graph import Graph
from src.domain.models import MapData
from src.parser.map_parser import MapParser
from src.simulation.engine import Engine
from src.simulation.models import Drone
from src.simulation.scheduler import Scheduler


def create_engine(map_data: MapData) -> Engine:
    """Build a simulation with drones alternating across up to two routes."""
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


def main() -> None:
    """Entry point for the Fly-in drone simulation."""
    parser = argparse.ArgumentParser(
        description="Run a Fly-in map simulation.",
    )
    parser.add_argument("map_file", help="Path to the map file to simulate")
    args = parser.parse_args()

    map_data = MapParser().parse_file(args.map_file)
    engine = create_engine(map_data)
    history = engine.run()

    for turn_number, moves in enumerate(history, start=1):
        descriptions = ", ".join(
            f"D{move.drone_id}: {move.origin or 'transit'} -> "
            f"{move.destination} ({move.kind.value})"
            for move in moves
        )
        print(f"Turn {turn_number}: {descriptions or 'no moves'}")
    print(
        f"Delivered {map_data.nb_drones} drones in "
        f"{engine.turns_elapsed} turns."
    )


if __name__ == "__main__":
    main()
