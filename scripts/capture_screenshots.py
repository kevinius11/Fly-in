"""Render portfolio screenshots from real Fly-in engine snapshots.

Run with ``.venv/bin/python scripts/capture_screenshots.py``.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "maps" / "medium" / "03_priority_puzzle.txt"
OUTPUT = ROOT / "assets" / "screenshots"


def main() -> None:
    """Render three representative frames from the real simulation."""
    sys.path.insert(0, str(ROOT))
    import pygame

    from main import create_engine
    from src.display.pygame_visualizer import HEIGHT, WIDTH, PygameVisualizer
    from src.parser.map_parser import MapParser

    map_data = MapParser().parse_file(str(MAP_PATH))
    engine = create_engine(map_data)
    engine.run()
    history = engine.state_history
    transit_frame = next(
        index for index, states in enumerate(history)
        if any(state.transit_connection is not None for state in states)
    )
    busy_frame = max(
        range(1, len(history) - 1),
        key=lambda index: sum(
            state.current_zone is not None
            and not state.is_delivered
            for state in history[index]
        ),
    )
    frames = [
        ("01-fleet-in-motion.png", busy_frame),
        ("02-restricted-transit.png", transit_frame),
        ("03-arrival.png", len(history) - 1),
    ]

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    backdrop_path = ROOT / "assets" / "arasaka_wallpaper.jpg"
    backdrop = pygame.image.load(str(backdrop_path)).convert()
    backdrop = pygame.transform.smoothscale(backdrop, (WIDTH, HEIGHT))
    backdrop.set_alpha(42)
    visualizer = PygameVisualizer(
        map_data, engine, map_label="PRIORITY PUZZLE"
    )
    font = pygame.font.Font(None, 22)
    small = pygame.font.Font(None, 16)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    for filename, frame_index in frames:
        screen.fill((8, 10, 18))
        screen.blit(backdrop, (0, 0))
        visualizer._draw(
            screen, pygame, font, small, history[frame_index], frame_index,
            1.0, False, 0.0, history,
        )
        pygame.image.save(screen, OUTPUT / filename)
    pygame.quit()


if __name__ == "__main__":
    main()
