import cProfile
import pstats

from src.evaluate_ablation import (
    run_ablation_game,
    ABLATION_CONFIGS,
)


def main():

    print("=" * 70)
    print("PROFILING ONE REWARD-ONLY ABLATION GAME")
    print("=" * 70)

    profiler = cProfile.Profile()

    profiler.enable()

    result = run_ablation_game(
        seed=10000,
        tested_config=ABLATION_CONFIGS[
            "reward_only"
        ],
        swap=False,
    )

    profiler.disable()

    print()
    print("=" * 70)
    print("GAME RESULT")
    print("=" * 70)

    print(result)

    print()
    print("=" * 70)
    print("TOP TIME-CONSUMING FUNCTIONS")
    print("=" * 70)

    stats = pstats.Stats(
        profiler
    )

    stats.sort_stats(
        "cumulative"
    )

    stats.print_stats(
        40
    )

    profiler.dump_stats(
        "ablation_profile.prof"
    )


if __name__ == "__main__":
    main()