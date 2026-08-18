import json
from pathlib import Path

from src.ml.state_encoder import (
    encode_state,
)


ROOT = Path(__file__).resolve().parents[2]

MEMORY_FILE = (
    ROOT
    / "memory"
    / "game_memory.json"
)

OUTPUT_FILE = (
    ROOT
    / "memory"
    / "ml_training_data.json"
)


HUMAN_NAME = "Chikile"
AI_NAME = "AI Companion"


def build_training_data():

    with open(
        MEMORY_FILE,
        "r",
        encoding="utf-8",
    ) as file:
        games = json.load(file)

    samples = []

    human_games = 0
    human_moves = 0
    response_pairs = 0

    for game_index, game in enumerate(
        games
    ):

        moves = game.get(
            "moves",
            [],
        )

        if not moves:
            continue

        players_seen = {
            move.get("player")
            for move in moves
        }

        # Only use real human-vs-AI games.
        if (
            HUMAN_NAME not in players_seen
            or AI_NAME not in players_seen
        ):
            continue

        human_games += 1

        winner = game.get(
            "winner"
        )

        for index, move in enumerate(
            moves
        ):

            if move.get(
                "player"
            ) != HUMAN_NAME:
                continue

            human_moves += 1

            # We need the state AFTER the human move,
            # because this is the state the AI reacts to.
            state_after_human = move.get(
                "state_after_move"
            )

            if not state_after_human:
                continue

            # Find the next AI move.
            ai_response = None

            for next_index in range(
                index + 1,
                len(moves),
            ):

                candidate = moves[
                    next_index
                ]

                candidate_player = (
                    candidate.get(
                        "player"
                    )
                )

                if (
                    candidate_player
                    == HUMAN_NAME
                ):
                    # Human acted again before AI.
                    # This is not a clean response pair.
                    break

                if (
                    candidate_player
                    == AI_NAME
                ):
                    ai_response = (
                        candidate
                    )
                    break

            if ai_response is None:
                continue

            try:
                state_vector = (
                    encode_state(
                        state_after_human,
                        ai_name=AI_NAME,
                        opponent_name=HUMAN_NAME,
                    )
                )

            except ValueError:
                continue

            ai_won = (
                winner == AI_NAME
            )

            human_won = (
                winner == HUMAN_NAME
            )

            final_reward = 0.0

            if ai_won:
                final_reward = 1.0

            elif human_won:
                final_reward = -1.0

            immediate_reward = float(
                ai_response.get(
                    "immediate_reward",
                    0.0,
                )
                or 0.0
            )

            sample = {
                "game_index": (
                    game_index
                ),

                "round": move.get(
                    "round"
                ),

                "state_vector": (
                    state_vector
                ),

                "human_move": {
                    "move_type": (
                        move.get(
                            "move_type"
                        )
                    ),
                    "card_name": (
                        move.get(
                            "card_name"
                        )
                    ),
                    "reward_type": (
                        move.get(
                            "reward_type"
                        )
                    ),
                    "reward_choices": (
                        move.get(
                            "reward_choices"
                        )
                    ),
                    "x_value": (
                        move.get(
                            "x_value"
                        )
                    ),
                    "target_card": (
                        move.get(
                            "target_card"
                        )
                    ),
                },

                "ai_response": {
                    "move_type": (
                        ai_response.get(
                            "move_type"
                        )
                    ),
                    "card_name": (
                        ai_response.get(
                            "card_name"
                        )
                    ),
                    "reward_type": (
                        ai_response.get(
                            "reward_type"
                        )
                    ),
                    "reward_choices": (
                        ai_response.get(
                            "reward_choices"
                        )
                    ),
                    "x_value": (
                        ai_response.get(
                            "x_value"
                        )
                    ),
                    "target_card": (
                        ai_response.get(
                            "target_card"
                        )
                    ),
                },

                "immediate_reward": (
                    immediate_reward
                ),

                "final_reward": (
                    final_reward
                ),

                "winner": winner,
            }

            samples.append(
                sample
            )

            response_pairs += 1

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            samples,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print("=" * 70)
    print("ML TRAINING DATA BUILDER")
    print("=" * 70)

    print(
        "Human games found:",
        human_games,
    )

    print(
        "Human moves found:",
        human_moves,
    )

    print(
        "Human → AI response pairs:",
        response_pairs,
    )

    print(
        "Training samples saved:",
        len(samples),
    )

    print(
        "Output:",
        OUTPUT_FILE,
    )

    print("=" * 70)


if __name__ == "__main__":
    build_training_data()