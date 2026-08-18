# src/victory_reactions.py

from __future__ import annotations

from rules_engine import compute_player_vp


GOLDEN_STATUE_NAME = "Golden Statue"
GOLDEN_STATUE_COST = 3
GOLDEN_STATUE_BONUS = 3


def card_name(card) -> str:
    if card is None:
        return ""

    definition = getattr(
        card,
        "definition",
        None,
    )

    if definition is None:
        return str(card)

    raw = getattr(
        definition,
        "raw_data",
        {},
    )

    return (
        getattr(definition, "name", None)
        or raw.get("name_en")
        or raw.get("name")
        or raw.get("id")
        or ""
    )


def player_has_golden_statue(player) -> bool:
    return any(
        card_name(monument) == GOLDEN_STATUE_NAME
        for monument in getattr(
            player,
            "monuments",
            [],
        )
    )


def can_use_golden_statue(player) -> bool:
    if not player_has_golden_statue(player):
        return False

    if getattr(
        player,
        "golden_statue_used_this_check",
        False,
    ):
        return False

    return (
        player.essence_pool.get("gold", 0)
        >= GOLDEN_STATUE_COST
    )


def use_golden_statue(player) -> bool:
    if not can_use_golden_statue(player):
        return False

    player.essence_pool["gold"] -= (
        GOLDEN_STATUE_COST
    )

    player.victory_check_bonus = (
        int(
            getattr(
                player,
                "victory_check_bonus",
                0,
            )
        )
        + GOLDEN_STATUE_BONUS
    )

    player.golden_statue_used_this_check = True

    return True


def reset_victory_reactions(game) -> None:
    game.victory_reaction_started = False
    game.victory_reaction_finished = False
    game.victory_reaction_queue = []
    game.pending_golden_statue_player = None
    game.show_golden_statue_prompt = False

    for player in game.players:
        player.victory_check_bonus = 0
        player.golden_statue_used_this_check = False


def begin_victory_reactions(game) -> None:
    game.victory_reaction_started = True
    game.victory_reaction_finished = False

    game.pending_golden_statue_player = None
    game.show_golden_statue_prompt = False

    for player in game.players:
        player.victory_check_bonus = 0
        player.golden_statue_used_this_check = False

    ordered_players = []

    start_index = int(
        getattr(
            game,
            "current_player_index",
            0,
        )
    )

    for offset in range(
        len(game.players)
    ):
        index = (
            start_index + offset
        ) % len(game.players)

        ordered_players.append(
            game.players[index]
        )

    game.victory_reaction_queue = [
        player
        for player in ordered_players
        if can_use_golden_statue(player)
    ]


def should_ai_use_golden_statue(
    game,
    ai_player,
) -> bool:
    if not can_use_golden_statue(
        ai_player
    ):
        return False

    # Calculate the real current VP.
    current_vp = compute_player_vp(
        ai_player,
        game,
    )

    # If +3 VP wins immediately, always use it.
    if (
        current_vp
        + GOLDEN_STATUE_BONUS
        >= 10
    ):
        return True

    # Find the opponent first.
    opponent = next(
        (
            player
            for player in game.players
            if player is not ai_player
        ),
        None,
    )

    if opponent is None:
        return False

    # Calculate opponent's real current VP.
    opponent_vp = compute_player_vp(
        opponent,
        game,
    )

    # Use Golden Statue when opponent is
    # close to winning and the bonus gives
    # the AI meaningful scoring pressure.
    return (
        opponent_vp >= 8
        and (
            current_vp
            + GOLDEN_STATUE_BONUS
            >= 8
        )
    )