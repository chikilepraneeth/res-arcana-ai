# src/reward_memory.py

import json
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]

GAME_MEMORY_FILE = (
    ROOT_DIR
    / "memory"
    / "game_memory.json"
)

REWARD_MEMORY_FILE = (
    ROOT_DIR
    / "memory"
    / "reward_memory.json"
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

    except (OSError, json.JSONDecodeError):
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


def build_reward_memory() -> list[dict[str, Any]]:
    games = load_json(
        GAME_MEMORY_FILE,
        [],
    )

    aggregated = {}

    for game in games:
        for move in game.get("moves", []):
            if move.get("player") != "AI Companion":
                continue

            reward = move.get("immediate_reward")

            if not isinstance(reward, (int, float)):
                continue

            key = (
                move.get("move_type"),
                move.get("card_name"),
                move.get("reward_type"),
                tuple(
                    move.get("reward_choices")
                    or []
                ),
            )

            if key not in aggregated:
                aggregated[key] = {
                    "move_type": key[0],
                    "card_name": key[1],
                    "reward_type": key[2],
                    "reward_choices": list(key[3]),
                    "attempts": 0,
                    "total_reward": 0.0,
                    "average_reward": 0.0,
                    "positive_results": 0,
                    "negative_results": 0,
                }

            record = aggregated[key]
            record["attempts"] += 1
            record["total_reward"] += reward

            if reward > 0:
                record["positive_results"] += 1
            elif reward < 0:
                record["negative_results"] += 1

    records = []

    for record in aggregated.values():
        attempts = record["attempts"]

        record["average_reward"] = round(
            record["total_reward"] / attempts,
            2,
        )

        records.append(record)

    records.sort(
        key=lambda item: (
            item["average_reward"],
            item["attempts"],
        ),
        reverse=True,
    )

    save_json(
        REWARD_MEMORY_FILE,
        records,
    )

    return records


def get_reward_memory_bonus(
    move: dict[str, Any],
) -> tuple[int, str | None]:
    records = load_json(
        REWARD_MEMORY_FILE,
        [],
    )

    for record in records:
        if record.get("move_type") != move.get("type"):
            continue

        if record.get("card_name") != move.get("card_name"):
            continue

        if record.get("reward_type") != move.get("reward_type"):
            continue

        saved_choices = (
            record.get("reward_choices")
            or []
        )

        move_choices = (
            move.get("choices")
            or []
        )

        if saved_choices != move_choices:
            continue

        attempts = record.get("attempts", 0)
        average_reward = record.get(
            "average_reward",
            0,
        )

        if attempts < 3:
            return 0, None

        bounded_bonus = max(
            -50,
            min(
                50,
                int(average_reward),
            ),
        )

        if bounded_bonus > 0:
            return (
                bounded_bonus,
                (
                    "reward memory favors this move "
                    f"with average reward "
                    f"{average_reward:+.1f}"
                ),
            )

        if bounded_bonus < 0:
            return (
                bounded_bonus,
                (
                    "reward memory warns against "
                    f"this move with average reward "
                    f"{average_reward:+.1f}"
                ),
            )

        return 0, None

    return 0, None


def main() -> None:
    records = build_reward_memory()

    print(
        f"Built {len(records)} reward records."
    )

    for record in records[:20]:
        print(
            record["move_type"],
            "|",
            record["card_name"],
            "| attempts:",
            record["attempts"],
            "| average reward:",
            record["average_reward"],
        )


if __name__ == "__main__":
    main()