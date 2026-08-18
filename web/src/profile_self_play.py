# src/profile_self_play.py

from __future__ import annotations

import cProfile
import pstats
import io
import os
import sys

CURRENT_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

PROJECT_ROOT = os.path.dirname(
    CURRENT_DIR
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)


from self_play import (
    run_single_self_play_game,
)


def run_profile():
    profiler = cProfile.Profile()

    print("=" * 70)
    print("STARTING SELF-PLAY PROFILE")
    print("=" * 70)

    profiler.enable()

    result = run_single_self_play_game(
        seed=2000,
        verbose=False,
        save_memory=False,
    )

    profiler.disable()

    print()
    print("=" * 70)
    print("GAME RESULT")
    print("=" * 70)

    print(
        f"Winner: {result['winner']}"
    )

    print(
        f"Rounds: {result['rounds']}"
    )

    print(
        f"Actions: {result['actions']}"
    )

    print(
        f"Scores: {result['scores']}"
    )

    print()
    print("=" * 70)
    print("TOP TIME-CONSUMING FUNCTIONS")
    print("=" * 70)

    stream = io.StringIO()

    stats = pstats.Stats(
        profiler,
        stream=stream,
    )

    stats.strip_dirs()
    stats.sort_stats(
        pstats.SortKey.CUMULATIVE
    )

    stats.print_stats(40)

    print(
        stream.getvalue()
    )

    profiler.dump_stats(
        "self_play_profile.prof"
    )

    print()
    print(
        "Full profile saved as:"
    )

    print(
        "self_play_profile.prof"
    )


if __name__ == "__main__":
    run_profile()