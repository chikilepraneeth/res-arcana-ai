# src/context_memory.py

import json
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
GAME_MEMORY_FILE = ROOT_DIR / "memory" / "game_memory.json"
CONTEXT_MEMORY_FILE = ROOT_DIR / "memory" / "context_memory.json"


def load_json(path: Path, default):
    if not path.exists():
        return default

    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    except (OSError, json.JSONDecodeError):
        return default


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )


def load_game_memory() -> list[dict[str, Any]]:
    data = load_json(GAME_MEMORY_FILE, [])
    return data if isinstance(data, list) else []


def load_context_memory() -> list[dict[str, Any]]:
    data = load_json(CONTEXT_MEMORY_FILE, [])
    return data if isinstance(data, list) else []


def get_player_from_state(
    state: dict[str, Any],
    player_name: str,
) -> dict[str, Any] | None:
    for player in state.get("players", []):
        if player.get("name") == player_name:
            return player

    return None


def get_saved_human_strategy(
    game_record: dict[str, Any],
) -> str | None:
    for item in game_record.get("strategies", []):
        if item.get("player") == "Chikile":
            return item.get("strategy")

    return None


def classify_round(round_no: int) -> str:
    if round_no <= 2:
        return "early"

    if round_no <= 4:
        return "middle"

    return "late"


def classify_difference(value: float) -> str:
    if value >= 2:
        return "ahead"

    if value <= -2:
        return "behind"

    return "close"


def total_essence(player_state: dict[str, Any]) -> int:
    essence = player_state.get("essence", {})

    return sum(
        int(value)
        for value in essence.values()
        if isinstance(value, (int, float))
    )


def count_board_cards(
    player_state: dict[str, Any],
) -> int:
    return (
        len(player_state.get("played", []))
        + len(player_state.get("monuments", []))
        + len(player_state.get("places", []))
    )


def build_move_context(
    game_record: dict[str, Any],
    move: dict[str, Any],
) -> dict[str, Any] | None:
    state = move.get("state_before_move", {})

    human = get_player_from_state(state, "Chikile")
    ai = get_player_from_state(state, "AI Companion")

    if not human or not ai:
        return None

    round_no = int(
        move.get(
            "round",
            state.get("round", 1),
        )
    )

    human_vp = int(human.get("vp", 0))
    ai_vp = int(ai.get("vp", 0))

    human_resources = total_essence(human)
    ai_resources = total_essence(ai)

    human_board = count_board_cards(human)
    ai_board = count_board_cards(ai)

    return {
        "human_strategy": get_saved_human_strategy(
            game_record
        ),
        "round_stage": classify_round(round_no),
        "vp_position": classify_difference(
            ai_vp - human_vp
        ),
        "resource_position": classify_difference(
            ai_resources - human_resources
        ),
        "board_position": classify_difference(
            ai_board - human_board
        ),
        "move_type": move.get("move_type"),
        "card_name": move.get("card_name"),
    }


def context_key(
    context: dict[str, Any],
) -> tuple:
    return (
        context.get("human_strategy"),
        context.get("round_stage"),
        context.get("vp_position"),
        context.get("resource_position"),
        context.get("board_position"),
        context.get("move_type"),
        context.get("card_name"),
    )


def build_context_memory() -> list[dict[str, Any]]:
    games = load_game_memory()

    aggregated: dict[
        tuple,
        dict[str, Any],
    ] = {}

    for game in games:
        moves = game.get("moves", [])

        if not moves:
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

            context = build_move_context(
                game,
                move,
            )

            if not context:
                continue

            key = context_key(context)

            if key not in aggregated:
                aggregated[key] = {
                    **context,
                    "attempts": 0,
                    "wins": 0,
                    "losses": 0,
                    "success_rate": 0.0,
                    "total_reward": 0.0,
                    "average_reward": 0.0,
                    "positive_rewards": 0,
                    "negative_rewards": 0,
                }

            record = aggregated[key]
            record["attempts"] += 1

            if ai_won:
                record["wins"] += 1
            else:
                record["losses"] += 1

            immediate_reward = move.get(
                "immediate_reward",
                0,
            )

            if isinstance(
                immediate_reward,
                (int, float),
            ):
                record["total_reward"] += (
                    immediate_reward
                )

                if immediate_reward > 0:
                    record[
                        "positive_rewards"
                    ] += 1

                elif immediate_reward < 0:
                    record[
                        "negative_rewards"
                    ] += 1

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
        CONTEXT_MEMORY_FILE,
        records,
    )

    return records


def get_context_bonus(
    human_strategy: str,
    game,
    ai_player,
    move: dict[str, Any],
) -> tuple[int, str | None]:
    records = load_context_memory()

    human = next(
        (
            player
            for player in game.players
            if player is not ai_player
        ),
        None,
    )

    if human is None:
        return 0, None

    ai_board = (
        len(ai_player.played)
        + len(ai_player.monuments)
        + len(ai_player.places)
    )

    human_board = (
        len(human.played)
        + len(human.monuments)
        + len(human.places)
    )

    current_context = {
        "human_strategy": human_strategy,
        "round_stage": classify_round(
            game.round_no
        ),
        "vp_position": classify_difference(
            ai_player.victory_points
            - human.victory_points
        ),
        "resource_position": classify_difference(
            sum(ai_player.essence_pool.values())
            - sum(human.essence_pool.values())
        ),
        "board_position": classify_difference(
            ai_board - human_board
        ),
        "move_type": move.get("type"),
        "card_name": move.get("card_name"),
    }

    fields = [
        "human_strategy",
        "round_stage",
        "vp_position",
        "resource_position",
        "board_position",
        "move_type",
        "card_name",
    ]

    for record in records:
        same_context = all(
            record.get(field)
            == current_context.get(field)
            for field in fields
        )

        if not same_context:
            continue

        attempts = record.get("attempts", 0)
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
            average_reward >= 20
            and success_rate >= 0.55
        ):
            return (
                50,
                (
                    "context memory strongly "
                    "favors this move; average "
                    f"reward {average_reward:+.1f}, "
                    f"win rate {success_rate:.0%}"
                ),
            )

        if average_reward >= 8:
            return (
                25,
                (
                    "context memory slightly "
                    "favors this move; average "
                    f"reward {average_reward:+.1f}"
                ),
            )

        if average_reward <= -10:
            return (
                -40,
                (
                    "context memory warns against "
                    "this move; average reward "
                    f"{average_reward:+.1f}"
                ),
            )

        if success_rate <= 0.25:
            return (
                -20,
                (
                    "context memory reports a low "
                    f"win rate of {success_rate:.0%}"
                ),
            )

        return 0, None

    return 0, None


def print_context_report() -> None:
    records = load_context_memory()

    print("=" * 75)
    print("RES ARCANA CONTEXT MEMORY")
    print("=" * 75)

    if not records:
        print("No context records available.")
        return

    for record in records[:25]:
        print()
        print(
            "Human strategy:",
            record["human_strategy"],
        )
        print(
            "Round stage:",
            record["round_stage"],
        )
        print(
            "VP position:",
            record["vp_position"],
        )
        print(
            "Resource position:",
            record["resource_position"],
        )
        print(
            "Board position:",
            record["board_position"],
        )
        print(
            "AI move:",
            record["move_type"],
            "|",
            record["card_name"],
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
    records = build_context_memory()

    print(
        f"Built {len(records)} context records."
    )

    print_context_report()


if __name__ == "__main__":
    main()