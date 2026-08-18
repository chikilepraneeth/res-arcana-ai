import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent

MEMORY_FILE = (
    ROOT
    / "memory"
    / "game_memory.json"
)

OUTPUT_FILE = (
    ROOT
    / "models"
    / "player_profiles.json"
)


def normalize(value):
    if value is None:
        return ""

    return str(value).strip()


def player_key(value):
    return normalize(value).lower()


def get_move_type(move):
    return (
        move.get("move_type")
        or move.get("type")
        or ""
    )


def get_card_name(move):
    return (
        move.get("card_name")
        or move.get("card")
        or ""
    )


def get_item_name(move):
    """
    Try several fields because older game records
    may have stored item choices differently.
    """

    for key in [
        "item_name",
        "selected_item",
        "new_item",
        "card_name",
    ]:
        value = move.get(key)

        if value:
            return normalize(value)

    return ""


def main():
    if not MEMORY_FILE.exists():
        raise FileNotFoundError(
            f"Memory file not found: {MEMORY_FILE}"
        )

    with open(
        MEMORY_FILE,
        "r",
        encoding="utf-8-sig",
    ) as f:
        games = json.load(f)

    profiles = defaultdict(
        lambda: {
            "display_name": "",
            "games": 0,
            "wins": 0,
            "losses": 0,
            "item_choices": Counter(),
            "move_types": Counter(),
            "favorite_cards": Counter(),
        }
    )

    for game in games:

        if not isinstance(game, dict):
            continue

        real_player_name = (
            game.get("player_name")
            or game.get("human_player_name")
        )

        # Historical games do not have a real web-player name.
        # Keep them under the old internal identity.
        if not real_player_name:
            real_player_name = "Chikile"

        key = player_key(
            real_player_name
        )

        if not key:
            continue

        profile = profiles[key]

        profile["display_name"] = (
            real_player_name
        )

        profile["games"] += 1

        winner = normalize(
            game.get("winner")
        )

        # Internally old/new human games may still store
        # the human winner as "Chikile".
        if winner == "Chikile":
            profile["wins"] += 1

        elif winner:
            profile["losses"] += 1

        moves = game.get(
            "moves",
            []
        )

        for move in moves:

            if not isinstance(move, dict):
                continue

            player = normalize(
                move.get("player")
            )

            # Only learn the human player's behavior.
            if player not in [
                "Chikile",
                real_player_name,
            ]:
                continue

            move_type = get_move_type(
                move
            )

            if move_type:
                profile[
                    "move_types"
                ][move_type] += 1

            card_name = get_card_name(
                move
            )

            if card_name:
                profile[
                    "favorite_cards"
                ][card_name] += 1

            # Item selection can be represented in several
            # ways depending on the recorded game version.
            if move_type in [
                "choose_item",
                "select_item",
                "take_item",
                "pass",
            ]:

                item_name = get_item_name(
                    move
                )

                if item_name:
                    profile[
                        "item_choices"
                    ][item_name] += 1

    result = {}

    for key, profile in profiles.items():

        item_total = sum(
            profile[
                "item_choices"
            ].values()
        )

        item_preferences = {}

        for item, count in (
            profile[
                "item_choices"
            ].most_common()
        ):

            probability = (
                count / item_total
                if item_total
                else 0.0
            )

            item_preferences[item] = {
                "count": count,
                "rate": round(
                    probability,
                    4,
                ),
            }

        result[key] = {
            "display_name":
                profile[
                    "display_name"
                ],

            "games":
                profile["games"],

            "wins":
                profile["wins"],

            "losses":
                profile["losses"],

            "item_choices":
                item_preferences,

            "move_types":
                dict(
                    profile[
                        "move_types"
                    ].most_common()
                ),

            "favorite_cards":
                dict(
                    profile[
                        "favorite_cards"
                    ].most_common(20)
                ),
        }

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            result,
            f,
            indent=2,
            ensure_ascii=False,
        )

    print("=" * 70)
    print("PLAYER PROFILES BUILT")
    print("=" * 70)

    print(
        "Games analyzed:",
        len(games),
    )

    print(
        "Players found:",
        len(result),
    )

    for key, profile in result.items():

        print()
        print(
            "PLAYER:",
            profile[
                "display_name"
            ],
        )

        print(
            "Games:",
            profile["games"],
        )

        print(
            "Top item choices:",
            list(
                profile[
                    "item_choices"
                ].items()
            )[:5],
        )

        print(
            "Top cards:",
            list(
                profile[
                    "favorite_cards"
                ].items()
            )[:5],
        )

    print()
    print(
        "Saved:",
        OUTPUT_FILE,
    )

    print("=" * 70)


if __name__ == "__main__":
    main()