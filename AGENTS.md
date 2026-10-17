# Fly-in Agent Instructions

## Project Context

Fly-in is a Python simulation project organized into separate layers:

- `src/domain/`: static domain models and graph representation.
- `src/parser/`: map parsing and validation.
- `src/algorithms/`: pathfinding and other algorithms.
- `src/simulation/`: dynamic simulation state, scheduling and engine.
- `src/display/`: visualization.
- `tests/`: automated tests.

The project is currently being developed incrementally. Some components exist independently but are not yet connected into a complete end-to-end execution flow.

## Architecture Rules

- Preserve the separation between domain, parser, algorithms, simulation and display.
- Keep domain models independent from higher-level orchestration.
- Keep parsing and validation logic inside the parser layer.
- Keep pathfinding algorithms independent from simulation orchestration.
- `Scheduler` is responsible for planning valid moves.
- `Engine` is responsible for orchestrating the simulation and applying approved moves.
- Do not move business logic into `main.py`.
- Do not introduce cross-layer dependencies without a clear architectural reason.

## Development Rules

- Read and understand the existing implementation before making changes.
- Preserve existing behavior unless the task explicitly requires changing it.
- Prefer small, focused changes.
- Do not introduce new dependencies without justification.
- Do not perform unrelated refactors.

## Testing Rules

- Run relevant tests after making changes.
- Do not modify tests merely to make them pass.
- Treat existing tests as part of the project's behavioral contract.
- When changing behavior, explain which tests should change and why.
- Do not remove or weaken test coverage to hide a failure.

## Agent Behavior

- Before implementing a non-trivial change, explain the proposed approach.
- If architectural intent is unclear, inspect the existing code and tests before making assumptions.
- Distinguish between existing behavior and proposed future behavior.
- Do not implement currently missing functionality unless the task explicitly asks for it.
- When a task is ambiguous, identify the ambiguity before modifying code.
- After implementation, report the files changed and tests executed.

