# src/evaluate_learning.py

from __future__ import annotations

import os
import sys
import time
import statistics

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


from self_play import (
    run_single_self_play_game,
)


# ============================================================
# CONFIG
# ============================================================

EVALUATION_GAMES = 50
STARTING_SEED = 5000


# ============================================================
# PLAYER CONFIGURATION
# ============================================================

def configure_players(
    game,
    swap=False,
):
    """
    Learned AI uses learned memories.
    Baseline AI uses the same brain,
    but memory bonuses are disabled.
    """

    if not swap:
        learned = game.players[0]
        baseline = game.players[1]

    else:
        learned = game.players[1]
        baseline = game.players[0]

    learned.name = "Learned_AI"
    learned.learning_enabled = True

    baseline.name = "Baseline_AI"
    baseline.learning_enabled = False

    return learned, baseline


# ============================================================
# SINGLE EVALUATION GAME
# ============================================================

def run_evaluation_game(
    seed,
    swap=False,
):
    """
    Run one self-play game without saving
    new learning memory.
    """

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

    learned, baseline = (
        configure_players(
            game,
            swap=swap,
        )
    )

    # Evaluation must not update
    # long-term learning memory.
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

                print(
                    f"WARNING: Seed {seed} exceeded "
                    f"MAX_ACTIONS_PER_ROUND."
                )

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

    # ----------------------------------------
    # SAFETY LIMIT
    # ----------------------------------------

    

    if not game.game_over:

        safety_limit = True

        leader = max(
            game.players,
            key=lambda p:
                p.victory_points,
        )

        game.game_over = True
        game.winner = leader.name

    learned_vp = (
        learned.victory_points
    )

    baseline_vp = (
        baseline.victory_points
    )

    return {
        "seed": seed,
        "winner": game.winner,
        "learned_vp": learned_vp,
        "baseline_vp": baseline_vp,
        "rounds": game.round_no,
        "actions": action_count,
        "safety_limit": safety_limit,
        "swap": swap,
    }


# ============================================================
# TOURNAMENT
# ============================================================

def run_evaluation(
    games=EVALUATION_GAMES,
    starting_seed=STARTING_SEED,
):

    print()
    print("=" * 70)
    print("LEARNED AI VS BASELINE AI")
    print("=" * 70)

    print(
        f"Games: {games}"
    )

    print(
        "Learned AI:"
        " memory enabled"
    )

    print(
        "Baseline AI:"
        " memory disabled"
    )

    print(
        "Memory updates:"
        " disabled during evaluation"
    )

    print("=" * 70)

    started = time.perf_counter()

    results = []

    learned_wins = 0
    baseline_wins = 0
    safety_games = 0

    learned_first_wins = 0
    learned_second_wins = 0

    learned_first_games = 0
    learned_second_games = 0

    for index in range(games):

        seed = (
            starting_seed
            + index
        )

        swap = (
            index % 2 == 1
        )

        result = run_evaluation_game(
            seed=seed,
            swap=swap,
        )

        results.append(
            result
        )

        if result["safety_limit"]:

            safety_games += 1

        else:

            if (
                result["winner"]
                == "Learned_AI"
            ):
                learned_wins += 1

            elif (
                result["winner"]
                == "Baseline_AI"
            ):
                baseline_wins += 1
        if not result["safety_limit"]:

            if not swap:

                learned_first_games += 1

                if (
                    result["winner"]
                    == "Learned_AI"
                ):
                    learned_first_wins += 1

            else:

                learned_second_games += 1

                if (
                    result["winner"]
                    == "Learned_AI"
                ):
                    learned_second_wins += 1
        print(
            f"[{index + 1}/{games}] "
            f"Winner={result['winner']} | "
            f"Learned VP={result['learned_vp']} | "
            f"Baseline VP={result['baseline_vp']} | "
            f"Rounds={result['rounds']} | "
            f"Safety={result['safety_limit']}"
        )

    elapsed = (
        time.perf_counter()
        - started
    )

    # ========================================================
    # RESULTS
    # ========================================================

    normal_games = (
        games
        - safety_games
    )

    learned_vps = [
        result["learned_vp"]
        for result in results
    ]

    baseline_vps = [
        result["baseline_vp"]
        for result in results
    ]

    round_counts = [
        result["rounds"]
        for result in results
    ]

    vp_differences = [
        (
            result["learned_vp"]
            - result["baseline_vp"]
        )
        for result in results
    ]

    print()
    print("=" * 70)
    print("EVALUATION SUMMARY")
    print("=" * 70)

    print(
        f"Games played: "
        f"{games}"
    )

    print(
        f"Normal games: "
        f"{normal_games}"
    )

    print(
        f"Safety-limit games: "
        f"{safety_games}"
    )

    print()

    print(
        f"Learned AI wins: "
        f"{learned_wins}"
    )

    print(
        f"Baseline AI wins: "
        f"{baseline_wins}"
    )

    if normal_games > 0:

        print(
            f"Learned win rate: "
            f"{(
                learned_wins
                / normal_games
            ) * 100:.2f}%"
        )

        print(
            f"Baseline win rate: "
            f"{(
                baseline_wins
                / normal_games
            ) * 100:.2f}%"
        )

    print()

    print(
        f"Average Learned VP: "
        f"{statistics.mean(learned_vps):.2f}"
    )

    print(
        f"Average Baseline VP: "
        f"{statistics.mean(baseline_vps):.2f}"
    )

    print(
        f"Average VP difference: "
        f"{statistics.mean(vp_differences):+.2f}"
    )

    print(
        f"Average rounds: "
        f"{statistics.mean(round_counts):.2f}"
    )

    print()

    if learned_first_games > 0:

        print(
            "Learned AI win rate "
            "when Player 1: "
            f"{(
                learned_first_wins
                / learned_first_games
            ) * 100:.2f}%"
        )

    if learned_second_games > 0:

        print(
            "Learned AI win rate "
            "when Player 2: "
            f"{(
                learned_second_wins
                / learned_second_games
            ) * 100:.2f}%"
        )

    print()

    print(
        f"Evaluation time: "
        f"{elapsed:.2f}s"
    )

    print("=" * 70)

    return results


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    run_evaluation(
        games=500,
        starting_seed=30000,
    )