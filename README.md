# Fly-in

Fly-in simulates a fleet of drones moving through a capacity-limited map. The
project is organized into domain, parser, pathfinding, simulation, and display
layers. The standard command line runs the simulation and prints one line per
turn, with tokens only for drones that moved.

## Requirements

- Python 3.10 or newer
- `make` for the convenience commands below

The visualizer uses Pygame. The development checks use `pytest`, `flake8`, and
`mypy`.

## Setup and run

```sh
make
make run
```

Running `make` creates `.venv` if needed and installs the project and its
development tools. `make install` does the same explicitly.

Run these commands from the project directory. When `MAP` is omitted,
`make run` uses `maps/hard/01_maze_nightmare.txt` by default. Choose another
map with `make run MAP=maps/medium/02_circular_loop.txt` (or `MAPS=...`).
The direct CLI also accepts `--map` or `--maps`, for example:

```sh
.venv/bin/python main.py --map maps/easy/02_simple_fork.txt --visualize
```

Or run it directly:

```sh
.venv/bin/python main.py maps/easy/01_linear_path.txt
```

`make run` prints the normal turn output in the terminal and opens the animated
Pygame visualizer in a separate window. The equivalent direct command is:

```sh
.venv/bin/python main.py --visualize maps/easy/01_linear_path.txt
```

The window replays the Engine's recorded drone positions over the map. It uses
a dark neon palette and metadata colors, and shows zone types, restricted
transit progress, zone occupancy, connection capacity, turn counters, and
recent events. Map coordinates determine node placement; if coordinates
overlap, a stable grid layout is used. Start and end zones show unlimited
effective capacity because the scheduler does not constrain hub occupancy.

Use Space to pause or resume, N to step a turn, +/- to change speed, R to
restart, and Q or Escape to close. To use the terminal-only dashboard instead,
run:

```sh
.venv/bin/python main.py --terminal-visualize maps/easy/01_linear_path.txt
```

The terminal dashboard advances automatically when stdin or stdout is not an
interactive terminal, so it can also be captured by scripts. In an interactive
terminal, Space pauses or resumes, N advances one turn while paused, `+`/`-`
changes playback speed, and Q exits. The dashboard shows the network, zone
types and metadata colors, drones in zones or restricted transit, zone and
link capacity, delivery counts, and events from the current turn.

If Pygame cannot open a graphical display, it reports the problem and leaves
the standard terminal output available.

Each output line is a simulation turn. A normal move or arrival is printed as
`D<ID>-<zone>`; entering a restricted zone starts a two-turn transit and is
printed as `D<ID>-<zone_a>-<zone_b>`. Drones that wait are omitted. Map and
simulation failures are reported to standard error and return a nonzero status.

### Optional live-coding exercise

The live review may ask you to add a `--capacity-info` option that prints zone
and connection usage for each turn. This option is intentionally not
implemented in the project; use these steps as a short practice guide during
the review.

1. In `main.py`, add `parser.add_argument("--capacity-info", action="store_true", ...)`.
2. Find where `engine.run()` returns the turn history. Keep that call so the
   engine's deadlock check still runs. Pair its turns with
   `engine.state_history[1:]`; each entry is the snapshot after that turn.
3. For each turn, count snapshots whose `current_zone` is each zone. For link
   use, count snapshots with a matching `transit_connection`, and include moves
   from that turn if you want to count ordinary moves too. The parsed map has
   each zone's `max_drones` and each connection's `max_link_capacity`.
4. When `--capacity-info` is set, print lines such as `Zone A: 1/2 drones`
   and `Connection A-B: 1/1` alongside the existing turn line. Leave output
   unchanged when the option is absent.

You can demonstrate it with
`.venv/bin/python main.py --capacity-info maps/easy/01_linear_path.txt`.
Explain that the Engine snapshots and parsed map supply the display data; the
scheduler and pathfinding code do not need to change.

## Map format

Maps are UTF-8 text files. Blank lines and text after `#` are ignored. Declare
the drone count first, then the start, end, and other zones, followed by their
connections. Zone metadata is optional: zones default to `normal`, capacity
defaults to one drone, and color is unset. Connection capacity also defaults
to one.

```text
nb_drones: 2
start_hub: start 0 0 [color=green]
hub: junction 1 0 [zone=priority max_drones=2 color=cyan]
hub: slow 2 0 [zone=restricted]
end_hub: goal 3 0 [color=red]
connection: start-junction [max_link_capacity=2]
connection: junction-slow
connection: slow-goal
```

Supported zone metadata keys are `zone` (`normal`, `priority`, `restricted`,
or `blocked`), `max_drones` (positive integer), and `color`. Connections use
`max_link_capacity` (positive integer). Zone names cannot contain hyphens,
because a connection is written as `zone_a-zone_b`. Zone declarations must
precede connection declarations.

## Design

- `src/domain/` contains map models and the project's adjacency-list graph.
- `src/parser/` parses map text and validates declarations and references.
- `src/algorithms/` finds shortest routes with Dijkstra and alternate routes
  with Yen's algorithm.
- `src/simulation/` assigns routes, schedules capacity-compatible moves, and
  advances drone/transit state. Restricted destinations take two turns.
- `src/display/visualizer.py` presents snapshots from the `Engine`; it does
  not plan or apply moves itself.
- `main.py` wires these components together and formats standard CLI output.

The benchmark policy comparison in `scripts/compare_routing_policies.py` is
an experiment and is kept separate from the production simulation path.

## Checks

```sh
.venv/bin/python -m pytest -q
make lint
```

Run an individual map with the same command used above. The benchmark maps and
their challenge descriptions are listed in [`maps/README.md`](maps/README.md).
