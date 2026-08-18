# src/brain/perception.py

from typing import Any


ESSENCE_NAMES = [
    "gold",
    "elan",
    "life",
    "calm",
    "death",
]


def get_card_name(card) -> str:
    if card is None:
        return ""

    definition = getattr(card, "definition", None)

    if definition is None:
        return str(card)

    return (
        getattr(definition, "name", None)
        or getattr(definition, "card_id", None)
        or definition.raw_data.get("name_en")
        or definition.raw_data.get("id")
        or "Unknown card"
    )


def get_card_id(card) -> str | None:
    if card is None:
        return None

    definition = getattr(card, "definition", None)

    if definition is None:
        return None

    return (
        getattr(definition, "card_id", None)
        or definition.raw_data.get("id")
    )


def get_card_tags(card) -> list[str]:
    if card is None:
        return []

    definition = getattr(card, "definition", None)

    if definition is None:
        return []

    return list(
        definition.raw_data.get("tags", [])
    )


def get_card_cost(card) -> dict[str, Any]:
    if card is None:
        return {}

    definition = getattr(card, "definition", None)

    if definition is None:
        return {}

    return (
        definition.raw_data.get(
            "placement_cost",
            {},
        )
        or {}
    )


def serialize_card(card) -> dict[str, Any]:
    if card is None:
        return {}

    definition = getattr(card, "definition", None)
    raw = (
        definition.raw_data
        if definition is not None
        else {}
    )

    return {
        "id": get_card_id(card),
        "name": get_card_name(card),
        "type": (
            getattr(definition, "card_type", None)
            or raw.get("type")
        ),
        "tags": get_card_tags(card),
        "cost": get_card_cost(card),
        "tapped": bool(
            getattr(card, "tapped", False)
        ),
        "stored_essence": dict(
            getattr(
                card,
                "stored_essence",
                {},
            )
            or {}
        ),
        "base_vp": int(
            raw.get("vp", {}).get(
                "base",
                0,
            )
            or 0
        ),
        "has_power": bool(
            raw.get("powers")
        ),
    }


def serialize_cards(cards) -> list[dict[str, Any]]:
    return [
        serialize_card(card)
        for card in list(cards or [])
    ]


def essence_pool(player) -> dict[str, int]:
    pool = getattr(
        player,
        "essence_pool",
        {},
    )

    return {
        essence: int(
            pool.get(essence, 0)
        )
        for essence in ESSENCE_NAMES
    }


def total_essence(player) -> int:
    return sum(
        essence_pool(player).values()
    )


def board_cards(player) -> list:
    return (
        list(getattr(player, "played", []))
        + list(getattr(player, "monuments", []))
        + list(getattr(player, "places", []))
    )


def board_size(player) -> int:
    return len(board_cards(player))


def ready_card_count(player) -> int:
    return sum(
        1
        for card in board_cards(player)
        if not getattr(card, "tapped", False)
    )


def find_opponent(game, player):
    return next(
        (
            candidate
            for candidate in game.players
            if candidate is not player
        ),
        None,
    )


def can_afford_simple(
    player,
    card,
) -> bool:
    cost = get_card_cost(card)

    essence_cost = cost.get(
        "essence",
        {},
    )

    pool = essence_pool(player)

    for essence, amount in essence_cost.items():
        if pool.get(essence, 0) < int(amount):
            return False

    wild = cost.get("wild")

    if isinstance(wild, int):
        remaining = sum(pool.values()) - sum(
            int(value)
            for value in essence_cost.values()
        )

        if remaining < wild:
            return False

    return True


def missing_resources_for_card(
    player,
    card,
) -> list[str]:
    cost = get_card_cost(card)
    essence_cost = cost.get(
        "essence",
        {},
    )

    pool = essence_pool(player)
    missing = []

    for essence, amount in essence_cost.items():
        required = int(amount)
        available = pool.get(essence, 0)

        if required > available:
            missing.extend(
                [essence]
                * (required - available)
            )

    return missing


def identify_visible_threats(
    game,
    opponent,
) -> list[dict[str, Any]]:
    threats = []

    if opponent is None:
        return threats

    opponent_resources = essence_pool(
        opponent
    )

    for place in getattr(
        game,
        "market_places",
        [],
    ):
        card = serialize_card(place)
        name = card["name"]

        danger = 0
        reasons = []

        if name in [
            "Dragon’s Lair",
            "Dragon's Lair",
        ]:
            danger += 5
            reasons.append(
                "important dragon strategy card"
            )

        if name == "Catacombs of the Dead":
            danger += 5
            reasons.append(
                "important death strategy card"
            )

        if name == "Sacred Grove":
            danger += 4
            reasons.append(
                "important life strategy card"
            )

        if card["base_vp"] > 0:
            danger += (
                card["base_vp"] * 2
            )
            reasons.append(
                "provides direct VP"
            )

        missing = missing_resources_for_card(
            opponent,
            place,
        )

        if not missing:
            danger += 5
            reasons.append(
                "opponent can afford it now"
            )
        elif len(missing) <= 2:
            danger += 2
            reasons.append(
                "opponent is close to affording it"
            )

        if danger > 0:
            threats.append({
                "name": name,
                "danger": danger,
                "reasons": reasons,
                "opponent_resources": (
                    opponent_resources
                ),
            })

    threats.sort(
        key=lambda item: item["danger"],
        reverse=True,
    )

    return threats


def detect_resource_focus(player) -> str | None:
    pool = essence_pool(player)

    if not pool:
        return None

    essence, amount = max(
        pool.items(),
        key=lambda item: item[1],
    )

    if amount < 3:
        return None

    return essence


def perceive_game(
    game,
    ai_player,
) -> dict[str, Any]:
    opponent = find_opponent(
        game,
        ai_player,
    )

    ai_vp = int(
        getattr(
            ai_player,
            "victory_points",
            0,
        )
    )

    opponent_vp = int(
        getattr(
            opponent,
            "victory_points",
            0,
        )
    ) if opponent else 0

    ai_resources = essence_pool(
        ai_player
    )

    opponent_resources = (
        essence_pool(opponent)
        if opponent
        else {}
    )

    available_places = serialize_cards(
        getattr(
            game,
            "market_places",
            [],
        )
    )

    available_monuments = serialize_cards(
        getattr(
            game,
            "market_monuments",
            [],
        )
    )

    affordable_places = [
        get_card_name(card)
        for card in getattr(
            game,
            "market_places",
            [],
        )
        if can_afford_simple(
            ai_player,
            card,
        )
    ]

    affordable_monuments = []

    if ai_resources.get("gold", 0) >= 4:
        affordable_monuments = [
            get_card_name(card)
            for card in getattr(
                game,
                "market_monuments",
                [],
            )
        ]

    hand = serialize_cards(
        getattr(ai_player, "hand", [])
    )

    hand_missing_resources = {
        card["name"]: missing_resources_for_card(
            ai_player,
            original_card,
        )
        for card, original_card in zip(
            hand,
            list(
                getattr(
                    ai_player,
                    "hand",
                    [],
                )
            ),
        )
    }

    opponent_close_to_winning = (
        opponent_vp >= 8
    )

    ai_close_to_winning = ai_vp >= 8

    if opponent_vp - ai_vp >= 3:
        danger_level = "high"
    elif opponent_vp > ai_vp:
        danger_level = "medium"
    else:
        danger_level = "low"

    return {
        "round": int(
            getattr(game, "round_no", 1)
        ),
        "phase": getattr(
            game,
            "phase",
            None,
        ),
        "ai_name": getattr(
            ai_player,
            "name",
            "AI",
        ),
        "opponent_name": (
            getattr(opponent, "name", None)
            if opponent
            else None
        ),
        "ai_vp": ai_vp,
        "opponent_vp": opponent_vp,
        "vp_difference": (
            ai_vp - opponent_vp
        ),
        "ai_resources": ai_resources,
        "opponent_resources": (
            opponent_resources
        ),
        "resource_difference": (
            total_essence(ai_player)
            - (
                total_essence(opponent)
                if opponent
                else 0
            )
        ),
        "ai_resource_focus": (
            detect_resource_focus(
                ai_player
            )
        ),
        "opponent_resource_focus": (
            detect_resource_focus(
                opponent
            )
            if opponent
            else None
        ),
        "ai_hand": hand,
        "ai_hand_size": len(hand),
        "ai_played": serialize_cards(
            getattr(
                ai_player,
                "played",
                [],
            )
        ),
        "ai_monuments": serialize_cards(
            getattr(
                ai_player,
                "monuments",
                [],
            )
        ),
        "ai_places": serialize_cards(
            getattr(
                ai_player,
                "places",
                [],
            )
        ),
        "opponent_played": (
            serialize_cards(
                getattr(
                    opponent,
                    "played",
                    [],
                )
            )
            if opponent
            else []
        ),
        "opponent_monuments": (
            serialize_cards(
                getattr(
                    opponent,
                    "monuments",
                    [],
                )
            )
            if opponent
            else []
        ),
        "opponent_places": (
            serialize_cards(
                getattr(
                    opponent,
                    "places",
                    [],
                )
            )
            if opponent
            else []
        ),
        "ai_board_size": board_size(
            ai_player
        ),
        "opponent_board_size": (
            board_size(opponent)
            if opponent
            else 0
        ),
        "ai_ready_cards": ready_card_count(
            ai_player
        ),
        "opponent_ready_cards": (
            ready_card_count(opponent)
            if opponent
            else 0
        ),
        "available_places": (
            available_places
        ),
        "available_monuments": (
            available_monuments
        ),
        "affordable_places": (
            affordable_places
        ),
        "affordable_monuments": (
            affordable_monuments
        ),
        "hand_missing_resources": (
            hand_missing_resources
        ),
        "visible_threats": (
            identify_visible_threats(
                game,
                opponent,
            )
        ),
        "danger_level": danger_level,
        "opponent_close_to_winning": (
            opponent_close_to_winning
        ),
        "ai_close_to_winning": (
            ai_close_to_winning
        ),
        "has_first_player_token": bool(
            getattr(
                ai_player,
                "has_first_player_token",
                False,
            )
        ),
        "first_player_token_available": bool(
            getattr(
                game,
                "first_player_token_available",
                False,
            )
        ),
        "ai_passed": bool(
            getattr(
                ai_player,
                "passed",
                False,
            )
        ),
    }