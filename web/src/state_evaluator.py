# src/state_evaluator.py

from typing import Any


ESSENCE_VALUES = {
    "gold": 3.0,
    "death": 1.2,
    "life": 1.0,
    "calm": 1.0,
    "elan": 1.0,
}


def essence_pool_value(player) -> float:
    return sum(
        float(
            player.essence_pool.get(
                essence,
                0,
            )
        ) * value
        for essence, value
        in ESSENCE_VALUES.items()
    )


def stored_essence_value(player) -> float:
    total = 0.0

    cards = (
        list(player.played)
        + list(player.monuments)
        + list(player.places)
    )

    for card in cards:
        stored = getattr(
            card,
            "stored_essence",
            {},
        ) or {}

        total += sum(
            float(
                stored.get(essence, 0)
            ) * value
            for essence, value
            in ESSENCE_VALUES.items()
        )

    return total


def board_development_value(player) -> float:
    value = 0.0

    value += len(player.played) * 6
    value += len(player.monuments) * 14
    value += len(player.places) * 18

    ready_cards = sum(
        1
        for card in (
            list(player.played)
            + list(player.monuments)
            + list(player.places)
        )
        if not getattr(card, "tapped", False)
    )

    value += ready_cards * 1.5

    return value


def player_position_value(
    player,
    game,
) -> float:
    value = 0.0

    value += (
        float(player.victory_points)
        * 35
    )

    value += essence_pool_value(
        player
    ) * 2

    value += stored_essence_value(
        player
    ) * 1.5

    value += board_development_value(
        player
    )

    value += len(player.hand) * 3

    if player.has_first_player_token:
        value += 8

    if player.passed:
        value -= 4

    return value


def evaluate_game_state(
    game,
    ai_player,
) -> float:
    opponent = next(
        (
            player
            for player in game.players
            if player is not ai_player
        ),
        None,
    )

    ai_value = player_position_value(
        ai_player,
        game,
    )

    if opponent is None:
        return ai_value

    opponent_value = player_position_value(
        opponent,
        game,
    )

    state_value = (
        ai_value - opponent_value
    )

    if getattr(game, "game_over", False):
        if game.winner == ai_player.name:
            state_value += 1000
        elif game.winner:
            state_value -= 1000

    return round(state_value, 2)


def explain_state(
    game,
    ai_player,
) -> dict[str, Any]:
    opponent = next(
        (
            player
            for player in game.players
            if player is not ai_player
        ),
        None,
    )

    report = {
        "ai_value": player_position_value(
            ai_player,
            game,
        ),
        "ai_vp": ai_player.victory_points,
        "ai_resources": essence_pool_value(
            ai_player
        ),
        "ai_board": board_development_value(
            ai_player
        ),
        "state_value": evaluate_game_state(
            game,
            ai_player,
        ),
    }

    if opponent:
        report.update({
            "opponent_value": (
                player_position_value(
                    opponent,
                    game,
                )
            ),
            "opponent_vp": (
                opponent.victory_points
            ),
            "opponent_resources": (
                essence_pool_value(
                    opponent
                )
            ),
            "opponent_board": (
                board_development_value(
                    opponent
                )
            ),
        })

    return report