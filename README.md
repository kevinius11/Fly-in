*This project has been created as part of the 42 curriculum by kcastro-.*

# Fly-in

## Description

Fly-in simulates a fleet of drones moving through a capacity-limited map. The
project is organized into domain, parser, pathfinding, simulation, and display
layers. The standard command line runs the simulation and prints one line per
turn, with tokens only for drones that moved.

## Requirements

- Python 3.10 or newer
- `make` for the convenience commands below

The visualizer uses Pygame. The development checks use `pytest`, `flake8`, and
`mypy`.

## Instructions

```sh
make
make run
```

Running `make` creates `.venv` if needed and installs the project and its
development tools. `make install` does the same explicitly.

Run these commands from the project directory. When `MAP` is omitted,
`make run` uses `maps/04_edge_case_gauntlet.txt` by default. Choose another
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

Use Space to pause or resume, N to move to the next turn, P to move to the
previous turn, +/- to change speed, R to restart, and Q or Escape to close.
To use the terminal-only dashboard instead, run:

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

### Capacity information

The capacity reporting logic is prepared for the live-coding review. To turn
it on, add this single line among the other argument declarations in
`main.py`, before `args = parser.parse_args()`:

```python
parser.add_argument("--capacity-info", action="store_true")
```

Then run `.venv/bin/python main.py --capacity-info MAP`. The existing code
prints zone occupancy and connection use after every turn alongside the
usual movement output; without the option, the normal CLI output is unchanged.

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

## Algorithm explanation

The graph stores the map as an adjacency list. Dijkstra's algorithm finds a
minimum-turn route, assigning restricted-zone entry a cost of two turns.
Yen's algorithm finds a second simple route so the simulation can distribute
drones across alternatives. Equal-cost paths prefer routes containing more
priority zones. The scheduler then plans each turn against connection
capacity, zone occupancy, and reserved arrivals; the engine applies those
moves and records snapshots for the visualizers.

## Visual representation

The project provides two ways to follow a simulation:

- The Pygame visualizer places zones using their map coordinates (and uses a
  fallback grid if coordinates overlap), draws connections, and animates drone
  positions from snapshots recorded by the engine. Zone type and optional
  metadata colors make priority, restricted, and blocked areas easier to
  distinguish. Its side panel shows zone occupancy, connection use, turn
  progress, and recent events. Space pauses or resumes playback, N/P step
  between turns, +/- changes speed, and R restarts the replay.
- The terminal dashboard shows the same map and live simulation details in
  text form. It supports pause, single-turn stepping, speed changes, and
  quitting from an interactive terminal.

These views make route choices, congestion, capacity constraints, and the
two-turn transit through restricted zones visible as the simulation runs.

## Example input and output

Example input (`example.map`):

```text
nb_drones: 1
start_hub: start 0 0
hub: middle 1 0
end_hub: goal 2 0
connection: start-middle
connection: middle-goal
```

Running `.venv/bin/python main.py example.map` prints:

```text
D1-middle
D1-goal
```

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

## Resources

- E. W. Dijkstra, [“A note on two problems in connexion with graphs”](https://doi.org/10.1007/BF01386390), *Numerische Mathematik*, 1959.
- J. Y. Yen, [“Finding the K Shortest Loopless Paths in a Network”](https://doi.org/10.1287/mnsc.17.11.712), *Management Science*, 1971.
- [Python documentation](https://docs.python.org/3/), including the standard library used by the command-line interface.
- [pygame-ce documentation](https://pyga.me/docs/), for the graphical simulation view.
- The repository's [`maps/README.md`](maps/README.md) explains the supplied challenge maps.

### AI assistance

AI assistance was used to review and revise this README: organize the project
overview, explain the existing algorithms and visualizer behavior, and check
that the example matches the command-line output. The implementation details
described here come from the project source. No application code or simulation
algorithms were generated by AI for this documentation update.

## Checks

```sh
.venv/bin/python -m pytest -q
make lint
```

Run an individual map with the same command used above. The benchmark maps and
their challenge descriptions are listed in [`maps/README.md`](maps/README.md).
