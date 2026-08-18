# src/counter_memory.py

import json
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
MEMORY_FILE = (
    ROOT_DIR
    / "memory"
    / "game_memory.json"
)
COUNTER_FILE = (
    ROOT_DIR
    / "memory"
    / "counter_memory.json"
)


def load_json_file(path: Path, default):
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


def save_json_file(
    path: Path,
    data,
) -> None:
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


def load_game_memory() -> list[dict[str, Any]]:
    data = load_json_file(
        MEMORY_FILE,
        [],
    )

    return data if isinstance(data, list) else []


def load_counter_memory() -> list[dict[str, Any]]:
    data = load_json_file(
        COUNTER_FILE,
        [],
    )

    return data if isinstance(data, list) else []


def save_counter_memory(
    records: list[dict[str, Any]],
) -> None:
    save_json_file(
        COUNTER_FILE,
        records,
    )


def get_human_strategy(
    game_record: dict[str, Any],
) -> str | None:
    for strategy_data in game_record.get(
        "strategies",
        [],
    ):
        if (
            strategy_data.get("player")
            == "Chikile"
        ):
            return strategy_data.get(
                "strategy"
            )

    return None


def normalize_response(
    move: dict[str, Any],
) -> dict[str, Any]:
    return {
        "move_type": move.get("move_type"),
        "card_name": move.get("card_name"),
        "reward_type": move.get(
            "reward_type"
        ),
        "reward_choices": move.get(
            "reward_choices"
        ),
    }


def response_key(
    human_strategy: str,
    response: dict[str, Any],
) -> tuple:
    reward_choices = (
        response.get("reward_choices")
        or []
    )

    return (
        human_strategy,
        response.get("move_type"),
        response.get("card_name"),
        response.get("reward_type"),
        tuple(reward_choices),
    )


def build_counter_memory() -> list[
    dict[str, Any]
]:
    games = load_game_memory()

    aggregated: dict[
        tuple,
        dict[str, Any],
    ] = {}

    for game in games:
        moves = game.get("moves", [])

        if not moves:
            continue

        human_strategy = (
            get_human_strategy(game)
        )

        if not human_strategy:
            continue

        ai_won = (
            game.get("winner")
            == "AI Companion"
        )

        for move in moves:
            if (
                move.get("player")
                != "AI Companion"
            ):
                continue

            if move.get("move_type") == "pass":
                continue

            response = normalize_response(move)

            key = response_key(
                human_strategy,
                response,
            )

            if key not in aggregated:
                aggregated[key] = {
                    "human_strategy": (
                        human_strategy
                    ),
                    "ai_response": response,
                    "attempts": 0,
                    "wins": 0,
                    "losses": 0,
                    "success_rate": 0.0,
                    "average_score": 0.0,
                    "average_reward": 0.0,
                    "scores": [],
                    "rewards": [],
                }

            record = aggregated[key]
            record["attempts"] += 1

            if ai_won:
                record["wins"] += 1
            else:
                record["losses"] += 1

            move_score = move.get(
                "move_score"
            )

            if isinstance(
                move_score,
                (int, float),
            ):
                record["scores"].append(
                    move_score
                )

            immediate_reward = move.get(
                "immediate_reward"
            )

            if isinstance(
                immediate_reward,
                (int, float),
            ):
                record["rewards"].append(
                    immediate_reward
                )

    records = []

    for record in aggregated.values():
        attempts = record["attempts"]

        scores = record.pop(
            "scores",
            [],
        )
        rewards = record.pop(
            "rewards",
            [],
        )

        record["success_rate"] = (
            record["wins"] / attempts
            if attempts
            else 0.0
        )

        record["average_score"] = round(
            sum(scores) / len(scores),
            2,
        ) if scores else 0.0

        record["average_reward"] = round(
            sum(rewards) / len(rewards),
            2,
        ) if rewards else 0.0

        records.append(record)

    records.sort(
        key=lambda item: (
            item["average_reward"],
            item["success_rate"],
            item["attempts"],
        ),
        reverse=True,
    )

    save_counter_memory(records)

    return records


def get_counter_bonus(
    human_strategy: str,
    move: dict[str, Any],
) -> tuple[int, str | None]:
    records = load_counter_memory()

    move_type = move.get("type")
    card_name = move.get("card_name")
    reward_type = move.get(
        "reward_type"
    )
    choices = move.get("choices") or []

    for record in records:
        if (
            record.get("human_strategy")
            != human_strategy
        ):
            continue

        response = record.get(
            "ai_response",
            {},
        )

        if (
            response.get("move_type")
            != move_type
        ):
            continue

        if (
            response.get("card_name")
            != card_name
        ):
            continue

        if (
            response.get("reward_type")
            != reward_type
        ):
            continue

        saved_choices = (
            response.get("reward_choices")
            or []
        )

        if saved_choices != choices:
            continue

        attempts = record.get(
            "attempts",
            0,
        )
        success_rate = record.get(
            "success_rate",
            0.0,
        )
        average_reward = record.get(
            "average_reward",
            0.0,
        )

        if attempts < 3:
            return 0, None

        if (
            success_rate >= 0.60
            and average_reward >= 12
        ):
            return (
                45,
                (
                    "counter memory strongly "
                    "favors this response; "
                    f"reward {average_reward:+.1f}, "
                    f"win rate {success_rate:.0%}"
                ),
            )

        if average_reward >= 6:
            return (
                20,
                (
                    "counter memory slightly "
                    "favors this response; "
                    f"reward {average_reward:+.1f}"
                ),
            )

        if average_reward <= -10:
            return (
                -35,
                (
                    "counter memory warns against "
                    "this response; average reward "
                    f"{average_reward:+.1f}"
                ),
            )

        if success_rate <= 0.25:
            return (
                -20,
                (
                    "counter memory reports only "
                    f"{success_rate:.0%} success"
                ),
            )

        return 0, None

    return 0, None


def print_counter_report() -> None:
    records = load_counter_memory()

    print("=" * 70)
    print("RES ARCANA COUNTER MEMORY")
    print("=" * 70)

    if not records:
        print("No counter records available.")
        return

    for record in records[:20]:
        response = record["ai_response"]

        print()
        print(
            "Human strategy:",
            record["human_strategy"],
        )
        print(
            "AI response:",
            response.get("move_type"),
            "|",
            response.get("card_name"),
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
    records = build_counter_memory()

    print(
        f"Built {len(records)} "
        "counter-memory records."
    )

    print_counter_report()


if __name__ == "__main__":
    main()