from src.self_play import run_single_self_play_game


def main():
    # Try a small set first.
    # We only care about games that hit the safety limit.
    seeds = range(1000, 1050)

    safety_games = 0

    for seed in seeds:
        result = run_single_self_play_game(
            seed=seed,
            verbose=False,
        )

        if result.get(
            "ended_by_safety_limit",
            False,
        ):
            safety_games += 1

            print("\n" + "=" * 70)
            print(f"SAFETY GAME — Seed {seed}")
            print("=" * 70)

            print(
                f"Winner: {result.get('winner')}"
            )
            print(
                f"Rounds: {result.get('rounds')}"
            )
            print(
                f"Actions: {result.get('actions')}"
            )
            print(
                f"Scores: {result.get('scores')}"
            )

            debug = result.get(
                "safety_debug",
                {},
            )

            print(
                f"Reason: {debug.get('reason')}"
            )
            print(
                f"Safety round: {debug.get('round')}"
            )
            print(
                "Actions this round:",
                debug.get(
                    "actions_this_round"
                ),
            )
            print(
                "Total actions:",
                debug.get(
                    "total_actions"
                ),
            )

            print("\nLAST MOVES:")

            for move in debug.get(
                "last_moves",
                [],
            ):
                print(
                    f"Round {move.get('round')} | "
                    f"{move.get('player')} | "
                    f"{move.get('type')} | "
                    f"{move.get('card')} | "
                    f"VP={move.get('vp')} | "
                    f"Passed={move.get('passed')}"
                )

    print("\n" + "=" * 70)
    print("SAFETY DEBUG COMPLETE")
    print("=" * 70)
    print(
        f"Games tested: {len(seeds)}"
    )
    print(
        f"Safety games: {safety_games}"
    )


if __name__ == "__main__":
    main()