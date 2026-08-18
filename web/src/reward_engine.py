# src/reward_engine.py

from typing import Any


ESSENCE_VALUES = {
    "gold": 3.0,
    "death": 1.2,
    "life": 1.0,
    "calm": 1.0,
    "elan": 1.0,
}


def get_player_state(
    state: dict[str, Any],
    player_name: str,
) -> dict[str, Any] | None:
    for player in state.get("players", []):
        if player.get("name") == player_name:
            return player

    return None


def essence_value(player_state: dict[str, Any]) -> float:
    pool = player_state.get("essence", {})

    return sum(
        float(pool.get(essence, 0)) * value
        for essence, value in ESSENCE_VALUES.items()
    )


def stored_essence_value(player_state: dict[str, Any]) -> float:
    total = 0.0

    zones = [
        "played",
        "monuments",
        "places",
    ]

    for zone in zones:
        for card in player_state.get(zone, []):
            stored = card.get("stored_essence", {})

            total += sum(
                float(stored.get(essence, 0)) * value
                for essence, value in ESSENCE_VALUES.items()
            )

    return total


def board_card_count(player_state: dict[str, Any]) -> int:
    return (
        len(player_state.get("played", []))
        + len(player_state.get("monuments", []))
        + len(player_state.get("places", []))
    )


def calculate_move_reward(
    move_type: str,
    state_before: dict[str, Any],
    state_after: dict[str, Any],
    player_name: str,
    opponent_name: str,
) -> tuple[float, list[str]]:
    before_player = get_player_state(
        state_before,
        player_name,
    )
    after_player = get_player_state(
        state_after,
        player_name,
    )

    before_opponent = get_player_state(
        state_before,
        opponent_name,
    )
    after_opponent = get_player_state(
        state_after,
        opponent_name,
    )

    if not before_player or not after_player:
        return 0.0, ["missing player snapshot"]

    reward = 0.0
    breakdown = []

    vp_change = (
        float(after_player.get("vp", 0))
        - float(before_player.get("vp", 0))
    )

    if vp_change:
        value = vp_change * 25
        reward += value
        breakdown.append(
            f"VP change {vp_change:+g}: {value:+g}"
        )

    resource_change = (
        essence_value(after_player)
        - essence_value(before_player)
    )

    if resource_change:
        value = resource_change * 2
        reward += value
        breakdown.append(
            f"resource value change "
            f"{resource_change:+.1f}: {value:+.1f}"
        )

    stored_change = (
        stored_essence_value(after_player)
        - stored_essence_value(before_player)
    )

    if stored_change:
        value = stored_change * 1.5
        reward += value
        breakdown.append(
            f"stored essence change "
            f"{stored_change:+.1f}: {value:+.1f}"
        )

    board_change = (
        board_card_count(after_player)
        - board_card_count(before_player)
    )

    if board_change:
        value = board_change * 8
        reward += value
        breakdown.append(
            f"board development {board_change:+d}: "
            f"{value:+g}"
        )

    hand_change = (
        int(after_player.get("hand_count", 0))
        - int(before_player.get("hand_count", 0))
    )

    if hand_change > 0:
        value = hand_change * 4
        reward += value
        breakdown.append(
            f"card advantage {hand_change:+d}: {value:+g}"
        )

    if before_opponent and after_opponent:
        opponent_resource_loss = (
            essence_value(before_opponent)
            - essence_value(after_opponent)
        )

        if opponent_resource_loss > 0:
            value = opponent_resource_loss * 1.5
            reward += value
            breakdown.append(
                f"opponent resource loss "
                f"{opponent_resource_loss:.1f}: {value:+.1f}"
            )

    if move_type == "buy_place_of_power":
        reward += 15
        breakdown.append(
            "claimed Place of Power: +15"
        )

    elif move_type == "buy_monument":
        reward += 10
        breakdown.append(
            "claimed monument: +10"
        )

    elif move_type == "play_card":
        reward += 5
        breakdown.append(
            "developed artifact engine: +5"
        )

    elif move_type == "discard":
        reward -= 3
        breakdown.append(
            "discarded a card: -3"
        )

    elif move_type == "pass":
        reward -= 2
        breakdown.append(
            "passed turn: -2"
        )

    if state_after.get("game_over"):
        winner = state_after.get("winner")

        if winner == player_name:
            reward += 100
            breakdown.append(
                "won game: +100"
            )

        elif winner:
            reward -= 100
            breakdown.append(
                "lost game: -100"
            )

    return round(reward, 2), breakdown