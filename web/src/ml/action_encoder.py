from typing import Any


MOVE_TYPES = [
    "play_card",
    "use_power",
    "discard",
    "buy_monument",
    "buy_place_of_power",
    "pass",
]


def encode_move(
    move: dict[str, Any],
) -> list[float]:

    features = []

    move_type = move.get(
        "move_type"
    ) or move.get(
        "type"
    )

    # ========================================================
    # MOVE TYPE ONE-HOT
    # ========================================================

    for candidate in MOVE_TYPES:
        features.append(
            1.0
            if move_type == candidate
            else 0.0
        )

    # ========================================================
    # SIMPLE MOVE PARAMETERS
    # ========================================================

    features.append(
        1.0
        if move.get("card_name")
        else 0.0
    )

    features.append(
        1.0
        if move.get("reward_type") == "gold"
        else 0.0
    )

    features.append(
        1.0
        if move.get("reward_type") == "essence"
        else 0.0
    )

    reward_choices = move.get(
        "reward_choices"
    ) or []

    features.append(
        float(
            len(reward_choices)
        )
    )

    x_value = move.get(
        "x_value"
    )

    try:
        x_value = float(
            x_value or 0
        )
    except (
        TypeError,
        ValueError,
    ):
        x_value = 0.0

    features.append(
        x_value
    )

    features.append(
        1.0
        if move.get("target_card")
        else 0.0
    )

    return features


def action_feature_count():

    dummy = {
        "move_type": "pass"
    }

    return len(
        encode_move(
            dummy
        )
    )