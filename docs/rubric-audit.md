# Fly-in rubric readiness audit

This matrix records evidence from the current checkout against the rubric
criteria transcribed in the project review. The original attached rubric was
not present in the repository, so exact wording and omitted criteria still
need confirmation against that source.

| Area | Requirement | Responsible code | Test / evidence | Demonstration command | Status / next action |
| --- | --- | --- | --- | --- | --- |
| Architecture | Object-oriented design with clear layer responsibilities | `src/domain/`, `src/parser/`, `src/algorithms/`, `src/simulation/`; `main.py` assembles components | Integration coverage in `tests/test_simulation_integration.py`; full suite: 185 passed | `.venv/bin/python -m pytest -q` | **Largely covered by inspection and integration.** |
| Types | Coherent annotations; mypy clean | All production modules; `Makefile` target `lint` | mypy clean across 20 source files | `make lint` | **Verified with current lint configuration.** |
| Graph | Own graph; avoid prohibited graph libraries | `src/domain/graph.py` | `tests/test_graph.py`; no prohibited graph imports found in source/tests | `.venv/bin/python -m pytest tests/test_graph.py -q` | **Covered by code/tests.** Confirm prohibited list against original rubric. |
| Parser | Map format, defaults, comments, validation | `src/parser/map_parser.py` | `tests/test_parser.py` covers syntax, defaults, comments, metadata, malformed maps and capacities | `.venv/bin/python -m pytest tests/test_parser.py -q` | **Covered by code/tests; README example added.** |
| Simulation | Zone/link capacities, coordinated moves, restricted transit takes two turns | `src/simulation/scheduler.py`, `src/simulation/engine.py` | `tests/test_scheduler.py`, `tests/test_engine.py`, `tests/test_simulation_integration.py` | `.venv/bin/python -m pytest tests/test_scheduler.py tests/test_engine.py tests/test_simulation_integration.py -q` | **Covered by tests, including capacity contention and restricted transit.** |
| Completion / failure | Deliver all drones or fail cleanly without infinite loop | `src/simulation/engine.py`, `main.py` | Engine/integration tests and `tests/test_cli.py`; full suite passed | `.venv/bin/python -m pytest tests/test_engine.py tests/test_simulation_integration.py tests/test_cli.py -q` | **Verified by current tests.** |
| Pathfinding | Respect blocked/restricted/priority behavior and report no route | `src/algorithms/pathfinding.py`, `main.py::create_engine()` | `tests/test_pathfinding.py`, no-route CLI coverage | `.venv/bin/python -m pytest tests/test_pathfinding.py tests/test_cli.py -q` | **Covered by tests.** |
| Standard CLI | One line per turn; required `D<ID>-<zone/connection>` tokens; omit idle drones; stop at completion | `main.py::_format_turn()` | `tests/test_cli.py`; manual linear map produced four turn lines | `make run MAP=maps/easy/01_linear_path.txt` | **Implemented from the transcribed contract.** Confirm exact connection token grammar against original rubric. |
| Visualizer | Readable topology, positions/moves, metadata colors and useful status | `src/display/visualizer.py` (empty) | No display tests | Not available | **Not implemented.** Build optional presentation over engine/map state. |
| Controls / diagnostics | Start, pause, step, reset, speed and diagnostic output | No implementation; `main.py` only accepts `map_file` | No tests | Not available | **Not implemented; scope depends on selected visualizer.** |
| Live modification exercise | Add `--capacity-info` showing zone/link use each turn | CLI presenter and engine/simulation state seam; option absent | No dedicated tests | No command yet | **Reserved for defense practice.** Confirm whether the evaluator expects it absent beforehand. |
| Performance | Meet per-map targets, especially challenger under 45 turns | `scripts/compare_routing_policies.py`; maps under `maps/` | Previous results are reported, not reverified against the final rubric thresholds | `python -m scripts.compare_routing_policies` | **Not reverified.** Rerun against the exact rubric thresholds after delivery changes. |
| Documentation / execution | Root README, setup/run/test/lint, algorithm and I/O example | `README.md`, `Makefile`, `main.py` | `make run` and `make lint` passed; full suite passed | `make run MAP=maps/easy/01_linear_path.txt` | **README and execution commands verified.** |

## Demonstration commands

From the repository root, after the virtual environment is installed:

```sh
.venv/bin/python -m pytest -v
make lint
make run MAP=maps/easy/01_linear_path.txt
python -m scripts.compare_routing_policies
```

The benchmark command compares experimental assignment policies and should
remain separate from production simulation behavior.

## Audit constraints

- No benchmark, test, or algorithm changes were made as part of this audit.
- The virtual environment is present in this checkout. Historical test and
  lint reports are not treated as current verification until rerun.
- The exact attached rubric file was not found in the workspace; this matrix
  uses only the criteria transcribed in the review request.
