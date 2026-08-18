# src/sequence_memory.py

import json
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]

GAME_MEMORY_FILE = (
    ROOT_DIR
    / "memory"
    / "game_memory.json"
)

SEQUENCE_MEMORY_FILE = (
    ROOT_DIR
    / "memory"
    / "sequence_memory.json"
)


def load_json(path: Path, default):
    if not path.exists():
        return default

    try:
        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            return json.load(file)

    except (
        OSError,
        json.JSONDecodeError,
    ):
        return default


def save_json(path: Path, data) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )


def move_signature(move: dict[str, Any],) -> str:
    move_type = (
        move.get("move_type")
        or move.get("type")
        or "unknown"
    )

    card_name = move.get("card_name")

    if move_type == "discard":
        choices = (
            move.get("reward_choices")
            or move.get("choices")
            or []
        )

        choice_text = ",".join(choices)

        return (
            f"discard:{card_name or 'unknown'}:"
            f"{move.get('reward_type') or 'unknown'}:"
            f"{choice_text}"
        )

    if card_name:
        return f"{move_type}:{card_name}"

    return move_type


def build_sequence_memory(
    minimum_length: int = 2,
    maximum_length: int = 3,
) -> list[dict[str, Any]]:
    games = load_json(
        GAME_MEMORY_FILE,
        [],
    )

    aggregated = {}

    for game in games:
        ai_moves = [
            move
            for move in game.get("moves", [])
            if (
                move.get("player")
                == "AI Companion"
                and move.get("move_type")
                != "pass"
            )
        ]

        if len(ai_moves) < minimum_length:
            continue

        ai_won = (
            game.get("winner")
            == "AI Companion"
        )

        for length in range(
            minimum_length,
            maximum_length + 1,
        ):
            if len(ai_moves) < length:
                continue

            for start in range(
                len(ai_moves) - length + 1
            ):
                window = ai_moves[
                    start:start + length
                ]

                signatures = [
                    move_signature(move)
                    for move in window
                ]

                key = tuple(signatures)

                total_reward = sum(
                    float(
                        move.get(
                            "immediate_reward",
                            0,
                        )
                    )
                    for move in window
                    if isinstance(
                        move.get(
                            "immediate_reward",
                            0,
                        ),
                        (int, float),
                    )
                )

                if key not in aggregated:
                    aggregated[key] = {
                        "sequence": signatures,
                        "length": length,
                        "attempts": 0,
                        "wins": 0,
                        "losses": 0,
                        "success_rate": 0.0,
                        "total_reward": 0.0,
                        "average_reward": 0.0,
                    }

                record = aggregated[key]
                record["attempts"] += 1
                record["total_reward"] += (
                    total_reward
                )

                if ai_won:
                    record["wins"] += 1
                else:
                    record["losses"] += 1

    records = []

    for record in aggregated.values():
        attempts = record["attempts"]

        record["success_rate"] = (
            record["wins"] / attempts
            if attempts
            else 0.0
        )

        record["average_reward"] = round(
            record["total_reward"] / attempts,
            2,
        ) if attempts else 0.0

        records.append(record)

    records.sort(
        key=lambda item: (
            item["average_reward"],
            item["success_rate"],
            item["attempts"],
        ),
        reverse=True,
    )

    save_json(
        SEQUENCE_MEMORY_FILE,
        records,
    )

    return records


def get_sequence_bonus(
    recent_moves: list[dict[str, Any]],
    candidate_move: dict[str, Any],
) -> tuple[int, str | None]:
    records = load_json(
        SEQUENCE_MEMORY_FILE,
        [],
    )

    candidate_signature = move_signature(
        candidate_move
    )

    previous_signatures = [
        move_signature(move)
        for move in recent_moves
    ]

    candidate_sequences = []

    if len(previous_signatures) >= 1:
        candidate_sequences.append(
            previous_signatures[-1:]
            + [candidate_signature]
        )

    if len(previous_signatures) >= 2:
        candidate_sequences.append(
            previous_signatures[-2:]
            + [candidate_signature]
        )

    best_bonus = 0
    best_reason = None

    for sequence in candidate_sequences:
        for record in records:
            if record.get("sequence") != sequence:
                continue

            attempts = record.get(
                "attempts",
                0,
            )
            average_reward = record.get(
                "average_reward",
                0.0,
            )
            success_rate = record.get(
                "success_rate",
                0.0,
            )

            if attempts < 3:
                continue

            if (
                average_reward >= 25
                and success_rate >= 0.55
            ):
                bonus = 40
            elif average_reward >= 10:
                bonus = 20
            elif average_reward <= -15:
                bonus = -30
            else:
                bonus = 0

            if abs(bonus) > abs(best_bonus):
                best_bonus = bonus
                best_reason = (
                    "sequence memory evaluated "
                    f"{' -> '.join(sequence)} "
                    f"with average reward "
                    f"{average_reward:+.1f}"
                )

    return best_bonus, best_reason


def print_sequence_report() -> None:
    records = load_json(
        SEQUENCE_MEMORY_FILE,
        [],
    )

    print("=" * 75)
    print("RES ARCANA SEQUENCE MEMORY")
    print("=" * 75)

    if not records:
        print("No sequence records available.")
        return

    for record in records[:25]:
        print()
        print(
            "Sequence:",
            " -> ".join(
                record["sequence"]
            ),
        )
        print(
            "Attempts:",
            record["attempts"],
        )
        print(
            "Success rate:",
            f"{record['success_rate']:.1%}",
        )
        print(
            "Average reward:",
            record["average_reward"],
        )


def main() -> None:
    records = build_sequence_memory()

    print(
        f"Built {len(records)} "
        "sequence records."
    )

    print_sequence_report()


if __name__ == "__main__":
    main()