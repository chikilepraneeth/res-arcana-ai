import json
from pathlib import Path

from src.ml.state_encoder import (
    encode_state,
    feature_count,
)


ROOT = Path(__file__).resolve().parents[2]

MEMORY_FILE = (
    ROOT
    / "memory"
    / "game_memory.json"
)


def main():

    with open(
        MEMORY_FILE,
        "r",
        encoding="utf-8",
    ) as file:

        games = json.load(file)

    found = False

    for game in games:

        for move in game.get(
            "moves",
            [],
        ):

            state = move.get(
                "state_before_move"
            )

            if not state:
                continue

            player_names = [
                player.get("name")
                for player in state.get(
                    "players",
                    [],
                )
            ]

            if (
                "Chikile"
                in player_names
                and "AI Companion"
                in player_names
            ):

                vector = encode_state(
                    state,
                    ai_name="AI Companion",
                    opponent_name="Chikile",
                )

                print(
                    "Feature count:",
                    len(vector),
                )

                print(
                    "Expected count:",
                    feature_count(),
                )

                print(
                    "Vector:"
                )

                print(vector)

                print(
                    "\nExample move:"
                )

                print(
                    move.get("player"),
                    move.get("move_type"),
                    move.get("card_name"),
                )

                found = True
                break

        if found:
            break

    if not found:
        print(
            "No usable human move "
            "was found."
        )


if __name__ == "__main__":
    main()