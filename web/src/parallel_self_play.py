# src/parallel_self_play.py

from __future__ import annotations

import os
import time
import traceback

from concurrent.futures import (
    ProcessPoolExecutor,
    as_completed,
)

from src.self_play import (
    run_single_self_play_game,
)

from src.game_memory import (
    load_memory,
    save_memory,
)

from src.counter_memory import (
    build_counter_memory,
)

from src.context_memory import (
    build_context_memory,
)

from src.reward_memory import (
    build_reward_memory,
)

from src.sequence_memory import (
    build_sequence_memory,
)


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_WORKERS = 4

DEFAULT_GAMES_PER_GENERATION = 8

DEFAULT_GENERATIONS = 5

STARTING_SEED = 1000


# ============================================================
# SINGLE WORKER GAME
# ============================================================

def worker_play_game(seed: int):
    """
    Runs ONE complete self-play game.

    IMPORTANT:
    The worker does NOT write to global memory.

    It only returns:
        winner
        rounds
        actions
        scores
        game_record
        runtime
    """

    start_time = time.perf_counter()

    try:
        result = run_single_self_play_game(
            seed=seed,
            verbose=False,
            save_memory=False,
        )

        runtime = (
            time.perf_counter()
            - start_time
        )

        return {
            "success": True,
            "seed": seed,
            "runtime": runtime,
            **result,
        }

    except Exception as error:

        runtime = (
            time.perf_counter()
            - start_time
        )

        return {
            "success": False,
            "seed": seed,
            "runtime": runtime,
            "error": str(error),
            "traceback": traceback.format_exc(),
        }


# ============================================================
# MEMORY MERGE
# ============================================================

def save_generation_records(results):
    """
    Only the MAIN process calls this.

    All completed game records are appended
    to game_memory.json in one operation.
    """

    memory = load_memory()

    added = 0

    for result in results:

        if not result.get(
            "success",
            False,
        ):
            continue

        # Do not use artificial safety-limit
        # games as learning examples.
        if result.get(
            "ended_by_safety_limit",
            False,
        ):
            continue

        game_record = result.get(
            "game_record"
        )

        if not game_record:
            continue

        memory.append(
            game_record
        )

        added += 1

    if added > 0:
        save_memory(
            memory
        )

    return added


# ============================================================
# LEARNING UPDATE
# ============================================================

def rebuild_learning_memories():
    """
    Rebuild learned memories ONCE after
    the whole generation is finished.
    """

    print()
    print(
        "Updating learned memories..."
    )

    start_time = time.perf_counter()

    failures = []

    try:
        build_counter_memory()

    except Exception as error:
        failures.append(
            f"counter memory: {error}"
        )

    try:
        build_context_memory()

    except Exception as error:
        failures.append(
            f"context memory: {error}"
        )

    try:
        build_reward_memory()

    except Exception as error:
        failures.append(
            f"reward memory: {error}"
        )

    try:
        build_sequence_memory()

    except Exception as error:
        failures.append(
            f"sequence memory: {error}"
        )

    runtime = (
        time.perf_counter()
        - start_time
    )

    print(
        f"Learning update completed "
        f"in {runtime:.2f}s"
    )

    if failures:
        print(
            "Learning update warnings:"
        )

        for failure in failures:
            print(
                f"  - {failure}"
            )

    return runtime


# ============================================================
# GENERATION
# ============================================================

def run_generation(
    generation_number: int,
    games: int,
    workers: int,
    starting_seed: int,
):

    print()
    print("=" * 70)

    print(
        f"SELF-PLAY GENERATION "
        f"{generation_number}"
    )

    print("=" * 70)

    print(
        f"Games:   {games}"
    )

    print(
        f"Workers: {workers}"
    )

    print(
        f"Seeds:   "
        f"{starting_seed} - "
        f"{starting_seed + games - 1}"
    )

    generation_start = (
        time.perf_counter()
    )

    results = []

    wins = {
        "AI_A": 0,
        "AI_B": 0,
    }

    failures = 0
    safety_limit_games = 0

    completed = 0

    # --------------------------------------------------------
    # RUN GAMES IN PARALLEL
    # --------------------------------------------------------

    with ProcessPoolExecutor(
        max_workers=workers
    ) as executor:

        futures = {}

        for game_index in range(
            games
        ):

            seed = (
                starting_seed
                + game_index
            )

            future = executor.submit(
                worker_play_game,
                seed,
            )

            futures[
                future
            ] = seed

        for future in as_completed(
            futures
        ):

            result = future.result()

            completed += 1

            results.append(
                result
            )
            if result.get(
                "ended_by_safety_limit",
                False,
            ):
                safety_limit_games += 1

            if result.get(
                "success",
                False,
            ):

                winner = result.get(
                    "winner"
                )

                if not result.get(
                    "ended_by_safety_limit",
                    False,
                ):
                    wins[winner] = (
                        wins.get(
                            winner,
                            0,
                        )
                        + 1
                    )

                print(
                    f"[{completed}/{games}] "
                    f"Seed={result['seed']} | "
                    f"Winner={winner} | "
                    f"Rounds={result['rounds']} | "
                    f"Actions={result['actions']} | "
                    f"Time={result['runtime']:.2f}s"
                )

            else:

                failures += 1

                print(
                    f"[{completed}/{games}] "
                    f"FAILED | "
                    f"Seed={result['seed']} | "
                    f"{result.get('error')}"
                )

    # --------------------------------------------------------
    # SAVE ALL GAME RECORDS ONCE
    # --------------------------------------------------------

    records_saved = (
        save_generation_records(
            results
        )
    )

    # --------------------------------------------------------
    # REBUILD BRAIN MEMORY ONCE
    # --------------------------------------------------------

    learning_time = 0.0

    if records_saved > 0:

        learning_time = (
            rebuild_learning_memories()
        )

    generation_time = (
        time.perf_counter()
        - generation_start
    )

    successful = [
        result
        for result in results
        if result.get(
            "success",
            False,
        )
    ]

    # --------------------------------------------------------
    # STATISTICS
    # --------------------------------------------------------

    if successful:

        average_rounds = (
            sum(
                result["rounds"]
                for result
                in successful
            )
            / len(successful)
        )

        average_actions = (
            sum(
                result["actions"]
                for result
                in successful
            )
            / len(successful)
        )

        average_game_runtime = (
            sum(
                result["runtime"]
                for result
                in successful
            )
            / len(successful)
        )

        fastest_game = min(
            result["runtime"]
            for result
            in successful
        )

        slowest_game = max(
            result["runtime"]
            for result
            in successful
        )

    else:

        average_rounds = 0
        average_actions = 0
        average_game_runtime = 0
        fastest_game = 0
        slowest_game = 0

    print()
    print("-" * 70)

    print(
        f"GENERATION "
        f"{generation_number} SUMMARY"
    )

    print("-" * 70)

    print(
        f"Games completed: "
        f"{len(successful)}/{games}"
    )

    print(
        f"Failures: "
        f"{failures}"
    )
    print(
        f"Safety-limit games: "
        f"{safety_limit_games}"
    )
        
    print(
        f"AI_A wins: "
        f"{wins.get('AI_A', 0)}"
    )

    print(
        f"AI_B wins: "
        f"{wins.get('AI_B', 0)}"
    )

    print(
        f"Average rounds: "
        f"{average_rounds:.2f}"
    )

    print(
        f"Average actions: "
        f"{average_actions:.2f}"
    )

    print(
        f"Average individual game time: "
        f"{average_game_runtime:.2f}s"
    )

    print(
        f"Fastest game: "
        f"{fastest_game:.2f}s"
    )

    print(
        f"Slowest game: "
        f"{slowest_game:.2f}s"
    )

    print(
        f"Learning update time: "
        f"{learning_time:.2f}s"
    )

    print(
        f"Wall-clock generation time: "
        f"{generation_time:.2f}s"
    )

    print(
        f"Records saved: "
        f"{records_saved}"
    )

    print("-" * 70)

    return {
        "generation": generation_number,
        "games_requested": games,
        "games_completed": len(
            successful
        ),
        "failures": failures,
        "wins": wins,
        "safety_limit_games": safety_limit_games,
        "average_rounds": average_rounds,
        "average_actions": average_actions,
        "average_game_runtime": (
            average_game_runtime
        ),
        "wall_clock_time": (
            generation_time
        ),
        "learning_time": (
            learning_time
        ),
        "records_saved": (
            records_saved
        ),
    }


# ============================================================
# MULTI-GENERATION SELF PLAY
# ============================================================

def run_parallel_self_play(
    generations=DEFAULT_GENERATIONS,
    games_per_generation=(
        DEFAULT_GAMES_PER_GENERATION
    ),
    workers=DEFAULT_WORKERS,
    starting_seed=STARTING_SEED,
):

    total_start = (
        time.perf_counter()
    )

    cpu_count = (
        os.cpu_count()
        or 1
    )

    workers = max(
        1,
        min(
            workers,
            cpu_count,
        ),
    )

    print()
    print("=" * 70)

    print(
        "PARALLEL RES ARCANA SELF-PLAY"
    )

    print("=" * 70)

    print(
        f"CPU logical cores: "
        f"{cpu_count}"
    )

    print(
        f"Workers used: "
        f"{workers}"
    )

    print(
        f"Generations: "
        f"{generations}"
    )

    print(
        f"Games per generation: "
        f"{games_per_generation}"
    )

    print(
        f"Total planned games: "
        f"{generations * games_per_generation}"
    )

    print("=" * 70)

    generation_results = []

    next_seed = starting_seed

    # --------------------------------------------------------
    # GENERATION LOOP
    # --------------------------------------------------------

    for generation in range(
        1,
        generations + 1,
    ):

        result = run_generation(
            generation_number=(
                generation
            ),
            games=games_per_generation,
            workers=workers,
            starting_seed=next_seed,
        )

        generation_results.append(
            result
        )

        next_seed += (
            games_per_generation
        )

        print()
        print(
            "Generation complete."
        )

        print(
            "The next generation will "
            "use the newly rebuilt memory."
        )

    # --------------------------------------------------------
    # FINAL STATISTICS
    # --------------------------------------------------------

    total_time = (
        time.perf_counter()
        - total_start
    )

    total_completed = sum(
        result[
            "games_completed"
        ]
        for result
        in generation_results
    )

    total_failures = sum(
        result[
            "failures"
        ]
        for result
        in generation_results
    )
    total_safety_limit_games = sum(
        result.get(
            "safety_limit_games",
            0,
        )
        for result
        in generation_results
    )

    total_ai_a_wins = sum(
        result[
            "wins"
        ].get(
            "AI_A",
            0,
        )
        for result
        in generation_results
    )

    total_ai_b_wins = sum(
        result[
            "wins"
        ].get(
            "AI_B",
            0,
        )
        for result
        in generation_results
    )

    print()
    print("=" * 70)

    print(
        "PARALLEL SELF-PLAY COMPLETE"
    )

    print("=" * 70)

    print(
        f"Games completed: "
        f"{total_completed}"
    )

    print(
        f"Failures: "
        f"{total_failures}"
    )

    print(
        f"AI_A wins: "
        f"{total_ai_a_wins}"
    )
    print(
        f"Safety-limit games: "
        f"{total_safety_limit_games}"
    )

    print(
        f"AI_B wins: "
        f"{total_ai_b_wins}"
    )

    print(
        f"Total wall-clock time: "
        f"{total_time:.2f}s"
    )

    if total_completed > 0:

        print(
            f"Wall-clock seconds/game: "
            f"{total_time / total_completed:.2f}"
        )

    print("=" * 70)

    return generation_results


# ============================================================
# WINDOWS ENTRY POINT
# ============================================================

if __name__ == "__main__":

    # Start small.
    #
    # 3 generations × 4 games
    # = 12 total games.
    #
    # After this works cleanly,
    # increase these values.

    run_parallel_self_play(
        generations=5,
        games_per_generation=100,
        workers=4,
        starting_seed=20000,
    )