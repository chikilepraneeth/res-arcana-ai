# src/evaluate_ablation.py

from __future__ import annotations

import os
import sys
import time
import statistics
import io
import traceback

from contextlib import (
    redirect_stdout,
    redirect_stderr,
)

from concurrent.futures import (
    ProcessPoolExecutor,
    as_completed,
)


CURRENT_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

PROJECT_ROOT = os.path.dirname(
    CURRENT_DIR
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(
        0,
        PROJECT_ROOT,
    )

if CURRENT_DIR not in sys.path:
    sys.path.insert(
        0,
        CURRENT_DIR,
    )


# ============================================================
# SETTINGS
# ============================================================

DEFAULT_WORKERS = 4

GAMES_PER_TEST = 50

STARTING_SEED = 10000


# ============================================================
# MEMORY CONFIGURATIONS
# ============================================================

ABLATION_CONFIGS = {

    "baseline": {
        "learning_enabled": False,
        "reward": False,
        "strategy": False,
        "context": False,
        "sequence": False,
        "counter": False,
    },

    "reward_only": {
        "learning_enabled": True,
        "reward": True,
        "strategy": False,
        "context": False,
        "sequence": False,
        "counter": False,
    },

    "strategy_only": {
        "learning_enabled": True,
        "reward": False,
        "strategy": True,
        "context": False,
        "sequence": False,
        "counter": False,
    },

    "context_only": {
        "learning_enabled": True,
        "reward": False,
        "strategy": False,
        "context": True,
        "sequence": False,
        "counter": False,
    },

    "sequence_only": {
        "learning_enabled": True,
        "reward": False,
        "strategy": False,
        "context": False,
        "sequence": True,
        "counter": False,
    },

    "counter_only": {
        "learning_enabled": True,
        "reward": False,
        "strategy": False,
        "context": False,
        "sequence": False,
        "counter": True,
    },

    "full_memory": {
        "learning_enabled": True,
        "reward": True,
        "strategy": True,
        "context": True,
        "sequence": True,
        "counter": True,
    },
}


# ============================================================
# APPLY MEMORY CONFIGURATION
# ============================================================

def apply_memory_config(
    player,
    config,
):

    player.learning_enabled = (
        config["learning_enabled"]
    )

    player.reward_memory_enabled = (
        config["reward"]
    )

    player.strategy_memory_enabled = (
        config["strategy"]
    )

    player.context_memory_enabled = (
        config["context"]
    )

    player.sequence_memory_enabled = (
        config["sequence"]
    )

    player.counter_memory_enabled = (
        config["counter"]
    )


# ============================================================
# CONFIGURE PLAYERS
# ============================================================

def configure_ablation_players(
    game,
    tested_config,
    swap=False,
):

    if not swap:

        tested = game.players[0]
        baseline = game.players[1]

    else:

        tested = game.players[1]
        baseline = game.players[0]

    tested.name = "Test_AI"

    apply_memory_config(
        tested,
        tested_config,
    )

    baseline.name = "Baseline_AI"

    apply_memory_config(
        baseline,
        ABLATION_CONFIGS[
            "baseline"
        ],
    )

    return tested, baseline


# ============================================================
# ONE GAME
# ============================================================

def run_ablation_game(
    seed,
    tested_config,
    swap=False,
):

    from self_play import (
        prepare_self_play_game,
        run_self_play_collection,
        execute_self_play_turn,
        get_next_active_player_index,
        start_next_self_play_round,
        MAX_ROUNDS,
        MAX_ACTIONS_PER_ROUND,
    )

    from rules_engine import (
        check_victory,
    )

    game = prepare_self_play_game(
        seed=seed
    )

    tested, baseline = (
        configure_ablation_players(
            game,
            tested_config,
            swap=swap,
        )
    )

    # Important:
    # memories may be READ,
    # but evaluation must not train.
    game.evaluation_mode = True

    run_self_play_collection(
        game
    )

    action_count = 0
    safety_limit = False

    while (
        not game.game_over
        and game.round_no <= MAX_ROUNDS
    ):

        actions_this_round = 0

        while (
            not game.game_over
            and not all(
                player.passed
                for player in game.players
            )
        ):

            actions_this_round += 1
            action_count += 1

            if (
                actions_this_round
                > MAX_ACTIONS_PER_ROUND
            ):

                safety_limit = True
                break

            current_player = (
                game.players[
                    game.current_player_index
                ]
            )

            if current_player.passed:

                game.current_player_index = (
                    get_next_active_player_index(
                        game,
                        game.current_player_index,
                    )
                )

                continue

            execute_self_play_turn(
                game,
                current_player,
            )

            if getattr(
                game,
                "force_victory_check",
                False,
            ):
                break

            game.current_player_index = (
                get_next_active_player_index(
                    game,
                    game.current_player_index,
                )
            )

        if safety_limit:
            break

        check_victory(
            game
        )

        if game.game_over:
            break

        start_next_self_play_round(
            game
        )

    # ========================================================
    # SAFETY FALLBACK
    # ========================================================

    if not game.game_over:

        safety_limit = True

        leader = max(
            game.players,
            key=lambda player:
                player.victory_points,
        )

        game.game_over = True
        game.winner = leader.name

    return {
        "success": True,
        "seed": seed,
        "winner": game.winner,
        "tested_vp": tested.victory_points,
        "baseline_vp": baseline.victory_points,
        "rounds": game.round_no,
        "actions": action_count,
        "safety_limit": safety_limit,
        "swap": swap,
    }


# ============================================================
# MULTIPROCESSING WORKER
# ============================================================

def worker_ablation_game(
    seed,
    config_name,
    swap,
):
    """
    Runs inside a separate Python process.

    Console output from the game itself is hidden
    so the terminal stays clean.
    """

    start = time.perf_counter()

    try:

        config = ABLATION_CONFIGS[
            config_name
        ]

        # Hide:
        # pygame startup text
        # Loading cards...
        # AI debug messages
        output_buffer = io.StringIO()

        with (
            redirect_stdout(output_buffer),
            redirect_stderr(output_buffer),
        ):

            result = run_ablation_game(
                seed=seed,
                tested_config=config,
                swap=swap,
            )

        result["runtime"] = (
            time.perf_counter()
            - start
        )

        return result

    except Exception as error:

        return {
            "success": False,
            "seed": seed,
            "swap": swap,
            "runtime": (
                time.perf_counter()
                - start
            ),
            "error": str(error),
            "traceback": (
                traceback.format_exc()
            ),
        }


# ============================================================
# TEST ONE CONFIGURATION
# ============================================================

def evaluate_configuration(
    config_name,
    games=50,
    workers=4,
    starting_seed=10000,
):

    print()
    print("=" * 70)

    print(
        f"ABLATION TEST: "
        f"{config_name}"
    )

    print("=" * 70)

    print(
        f"Games:   {games}"
    )

    print(
        f"Workers: {workers}"
    )

    start = time.perf_counter()

    results = []

    completed = 0
    failures = 0

    # ========================================================
    # PARALLEL EXECUTION
    # ========================================================

    with ProcessPoolExecutor(
        max_workers=workers
    ) as executor:

        futures = {}

        for index in range(
            games
        ):

            seed = (
                starting_seed
                + index
            )

            swap = (
                index % 2 == 1
            )

            future = executor.submit(
                worker_ablation_game,
                seed,
                config_name,
                swap,
            )

            futures[future] = seed

        for future in as_completed(
            futures
        ):

            result = future.result()

            completed += 1

            if result.get(
                "success",
                False,
            ):

                results.append(
                    result
                )

            else:

                failures += 1

                print(
                    f"FAILED seed "
                    f"{result['seed']}: "
                    f"{result.get('error')}"
                )

            # Print progress every 10 games
            # and on the last game.
            if (
                completed % 10 == 0
                or completed == games
            ):

                print(
                    f"[{completed}/{games}] "
                    f"completed"
                )

    elapsed = (
        time.perf_counter()
        - start
    )

    # ========================================================
    # ANALYSIS
    # ========================================================

    safety_games = sum(
        1
        for result in results
        if result["safety_limit"]
    )

    normal_results = [
        result
        for result in results
        if not result[
            "safety_limit"
        ]
    ]

    normal_games = len(
        normal_results
    )

    tested_wins = sum(
        1
        for result in normal_results
        if result["winner"]
        == "Test_AI"
    )

    baseline_wins = sum(
        1
        for result in normal_results
        if result["winner"]
        == "Baseline_AI"
    )

    # ========================================================
    # POSITION ANALYSIS
    # ========================================================

    first_results = [
        result
        for result in normal_results
        if not result["swap"]
    ]

    second_results = [
        result
        for result in normal_results
        if result["swap"]
    ]

    first_wins = sum(
        1
        for result in first_results
        if result["winner"]
        == "Test_AI"
    )

    second_wins = sum(
        1
        for result in second_results
        if result["winner"]
        == "Test_AI"
    )

    # ========================================================
    # VP ANALYSIS
    # ========================================================

    tested_vps = [
        result["tested_vp"]
        for result in normal_results
    ]

    baseline_vps = [
        result["baseline_vp"]
        for result in normal_results
    ]

    win_rate = (
        tested_wins
        / normal_games
        * 100
        if normal_games
        else 0.0
    )

    first_rate = (
        first_wins
        / len(first_results)
        * 100
        if first_results
        else 0.0
    )

    second_rate = (
        second_wins
        / len(second_results)
        * 100
        if second_results
        else 0.0
    )

    avg_tested_vp = (
        statistics.mean(
            tested_vps
        )
        if tested_vps
        else 0.0
    )

    avg_baseline_vp = (
        statistics.mean(
            baseline_vps
        )
        if baseline_vps
        else 0.0
    )

    vp_difference = (
        avg_tested_vp
        - avg_baseline_vp
    )

    average_game_time = (
        statistics.mean(
            result["runtime"]
            for result in results
        )
        if results
        else 0.0
    )

    # ========================================================
    # CONFIGURATION SUMMARY
    # ========================================================

    print()
    print("-" * 70)

    print(
        f"{config_name} SUMMARY"
    )

    print("-" * 70)

    print(
        f"Normal games: "
        f"{normal_games}"
    )

    print(
        f"Safety games: "
        f"{safety_games}"
    )

    print(
        f"Failures: "
        f"{failures}"
    )

    print(
        f"Test AI wins: "
        f"{tested_wins}"
    )

    print(
        f"Baseline wins: "
        f"{baseline_wins}"
    )

    print(
        f"Win rate: "
        f"{win_rate:.2f}%"
    )

    print(
        f"VP difference: "
        f"{vp_difference:+.2f}"
    )

    print(
        f"Average individual game: "
        f"{average_game_time:.2f}s"
    )

    print(
        f"Wall-clock time: "
        f"{elapsed:.2f}s"
    )

    print("-" * 70)

    return {
        "name": config_name,
        "games": games,
        "normal_games": normal_games,
        "safety_games": safety_games,
        "failures": failures,
        "tested_wins": tested_wins,
        "baseline_wins": baseline_wins,
        "win_rate": win_rate,
        "first_rate": first_rate,
        "second_rate": second_rate,
        "avg_tested_vp": (
            avg_tested_vp
        ),
        "avg_baseline_vp": (
            avg_baseline_vp
        ),
        "vp_difference": (
            vp_difference
        ),
        "average_game_time": (
            average_game_time
        ),
        "time": elapsed,
    }


# ============================================================
# FULL ABLATION STUDY
# ============================================================

def run_ablation(
    games_per_test=50,
    workers=4,
):

    tests = [
        "reward_only",
        "strategy_only",
        "context_only",
        "sequence_only",
        "counter_only",
        "full_memory",
    ]

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

    total_games = (
        len(tests)
        * games_per_test
    )

    print()
    print("=" * 80)

    print(
        "RES ARCANA AI "
        "PARALLEL ABLATION STUDY"
    )

    print("=" * 80)

    print(
        f"CPU logical cores: "
        f"{cpu_count}"
    )

    print(
        f"Workers: "
        f"{workers}"
    )

    print(
        f"Tests: "
        f"{len(tests)}"
    )

    print(
        f"Games/test: "
        f"{games_per_test}"
    )

    print(
        f"Total games: "
        f"{total_games}"
    )

    print("=" * 80)

    total_start = (
        time.perf_counter()
    )

    results = []

    for index, name in enumerate(
        tests
    ):

        print()
        print(
            f"[{index + 1}/"
            f"{len(tests)}]"
        )

        result = (
            evaluate_configuration(
                config_name=name,
                games=games_per_test,
                workers=workers,

                # Same seeds for every
                # configuration.
                starting_seed=STARTING_SEED,
            )
        )

        results.append(
            result
        )

    total_elapsed = (
        time.perf_counter()
        - total_start
    )

    # ========================================================
    # FINAL TABLE
    # ========================================================

    print()
    print("=" * 86)
    print("ABLATION RESULTS")
    print("=" * 86)

    print(
        f"{'Configuration':<20}"
        f"{'Win %':>10}"
        f"{'VP Diff':>10}"
        f"{'P1 %':>10}"
        f"{'P2 %':>10}"
        f"{'Safety':>10}"
        f"{'Time':>12}"
    )

    print("-" * 86)

    for result in results:

        print(
            f"{result['name']:<20}"
            f"{result['win_rate']:>10.2f}"
            f"{result['vp_difference']:>10.2f}"
            f"{result['first_rate']:>10.2f}"
            f"{result['second_rate']:>10.2f}"
            f"{result['safety_games']:>10}"
            f"{result['time']:>11.1f}s"
        )

    print("=" * 86)

    print(
        f"Total wall-clock time: "
        f"{total_elapsed:.2f}s"
    )

    print("=" * 86)

    return results


# ============================================================
# WINDOWS ENTRY POINT
# ============================================================

if __name__ == "__main__":

    run_ablation(
        games_per_test=50,
        workers=4,
    )