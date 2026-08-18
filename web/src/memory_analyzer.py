# src/memory_analyzer.py

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
MEMORY_FILE = ROOT_DIR / "memory" / "game_memory.json"


def load_games() -> list[dict[str, Any]]:
    """Load all completed games from the memory JSON file."""

    if not MEMORY_FILE.exists():
        print(f"Memory file not found: {MEMORY_FILE}")
        return []

    try:
        with MEMORY_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)

    except json.JSONDecodeError as error:
        print(f"Memory JSON is invalid: {error}")
        return []

    except OSError as error:
        print(f"Could not read memory file: {error}")
        return []

    if not isinstance(data, list):
        print("Memory file must contain a list of games.")
        return []

    return data


def extract_name(value: Any) -> str | None:
    """
    Supports both old memory format:

        "mage": "Scholar"

    and new memory format:

        "mage": {
            "card_id": "...",
            "name": "Scholar",
            "tapped": false
        }
    """

    if isinstance(value, str):
        return value

    if isinstance(value, dict):
        return value.get("name")

    return None


def get_final_player(
    game: dict[str, Any],
    player_name: str,
) -> dict[str, Any] | None:
    final_state = game.get("final_state", {})

    for player in final_state.get("players", []):
        if player.get("name") == player_name:
            return player

    return None


def analyze_games(games: list[dict[str, Any]]) -> dict[str, Any]:
    winner_counter = Counter()
    move_counter = Counter()

    human_card_counter = Counter()
    ai_card_counter = Counter()

    human_strategy_counter = Counter()
    ai_strategy_counter = Counter()

    human_mage_counter = Counter()
    ai_mage_counter = Counter()

    human_item_counter = Counter()
    ai_item_counter = Counter()

    human_opening_counter = Counter()
    ai_opening_counter = Counter()

    total_moves = 0
    games_with_moves = 0

    for game in games:
        winner = game.get("winner")

        if winner:
            winner_counter[winner] += 1

        moves = game.get("moves", [])

        if moves:
            games_with_moves += 1

        total_moves += len(moves)

        human_moves = []
        ai_moves = []

        for move in moves:
            move_type = move.get("move_type")
            player = move.get("player")
            card = move.get("card_name")

            if move_type:
                move_counter[move_type] += 1

            if player == "Chikile":
                human_moves.append(move)

                if card:
                    human_card_counter[card] += 1

            elif player == "AI Companion":
                ai_moves.append(move)

                if card:
                    ai_card_counter[card] += 1

        # First meaningful action of each player
        if human_moves:
            first_move = human_moves[0]

            opening_key = (
                first_move.get("move_type"),
                first_move.get("card_name"),
            )

            human_opening_counter[opening_key] += 1

        if ai_moves:
            first_move = ai_moves[0]

            opening_key = (
                first_move.get("move_type"),
                first_move.get("card_name"),
            )

            ai_opening_counter[opening_key] += 1

        # Saved strategy labels
        for strategy_data in game.get("strategies", []):
            player = strategy_data.get("player")
            strategy = strategy_data.get("strategy")

            if not strategy:
                continue

            if player == "Chikile":
                human_strategy_counter[strategy] += 1

            elif player == "AI Companion":
                ai_strategy_counter[strategy] += 1

        # Final mage and item
        human = get_final_player(game, "Chikile")
        ai = get_final_player(game, "AI Companion")

        if human:
            mage = extract_name(human.get("mage"))
            item = extract_name(human.get("item"))

            if mage:
                human_mage_counter[mage] += 1

            if item:
                human_item_counter[item] += 1

        if ai:
            mage = extract_name(ai.get("mage"))
            item = extract_name(ai.get("item"))

            if mage:
                ai_mage_counter[mage] += 1

            if item:
                ai_item_counter[item] += 1

    average_moves = (
        total_moves / games_with_moves
        if games_with_moves
        else 0
    )

    return {
        "games_played": len(games),
        "games_with_moves": games_with_moves,
        "total_moves": total_moves,
        "average_moves": average_moves,
        "winners": winner_counter,
        "move_types": move_counter,
        "human_cards": human_card_counter,
        "ai_cards": ai_card_counter,
        "human_strategies": human_strategy_counter,
        "ai_strategies": ai_strategy_counter,
        "human_mages": human_mage_counter,
        "ai_mages": ai_mage_counter,
        "human_items": human_item_counter,
        "ai_items": ai_item_counter,
        "human_openings": human_opening_counter,
        "ai_openings": ai_opening_counter,
    }


def print_counter(
    title: str,
    counter: Counter,
    limit: int = 10,
) -> None:
    print()
    print(title)
    print("-" * len(title))

    if not counter:
        print("No data available.")
        return

    for value, count in counter.most_common(limit):
        if isinstance(value, tuple):
            move_type, card = value

            card_text = card or "No card"
            print(f"{move_type} | {card_text}: {count}")

        else:
            print(f"{value}: {count}")


def print_report(summary: dict[str, Any]) -> None:
    print("=" * 60)
    print("RES ARCANA MEMORY ANALYSIS")
    print("=" * 60)

    print(f"Games saved:       {summary['games_played']}")
    print(f"Games with moves:  {summary['games_with_moves']}")
    print(f"Total moves:       {summary['total_moves']}")
    print(f"Average moves:     {summary['average_moves']:.2f}")

    print_counter(
        "Winners",
        summary["winners"],
    )

    print_counter(
        "Move Types",
        summary["move_types"],
    )

    print_counter(
        "Human Most Used Cards",
        summary["human_cards"],
    )

    print_counter(
        "AI Most Used Cards",
        summary["ai_cards"],
    )

    print_counter(
        "Human Strategies",
        summary["human_strategies"],
    )

    print_counter(
        "AI Strategies",
        summary["ai_strategies"],
    )

    print_counter(
        "Human Mages",
        summary["human_mages"],
    )

    print_counter(
        "AI Mages",
        summary["ai_mages"],
    )

    print_counter(
        "Human Items",
        summary["human_items"],
    )

    print_counter(
        "AI Items",
        summary["ai_items"],
    )

    print_counter(
        "Human Opening Moves",
        summary["human_openings"],
    )

    print_counter(
        "AI Opening Moves",
        summary["ai_openings"],
    )


def main() -> None:
    games = load_games()

    if not games:
        print("No saved games were found.")
        return

    summary = analyze_games(games)
    print_report(summary)


if __name__ == "__main__":
    main()