# src/lookahead.py

import copy
import types
from typing import Callable, Any

from state_evaluator import (
    evaluate_game_state,
)


MoveExecutor = Callable[
    [Any, Any, dict],
    bool,
]


_ATOMIC_TYPES = (
    str,
    bytes,
    int,
    float,
    bool,
    complex,
    type(None),
)


def _build_shared_runtime_memo(
    obj,
    memo: dict[int, Any],
    visited: set[int],
):
    """
    Build a deepcopy memo for runtime objects that should be shared
    instead of copied.

    The GUI game can contain pygame Surface/Font/runtime objects.
    pygame Surface cannot be pickled/deep-copied normally.

    Simulation never mutates rendering objects, so sharing them is
    safe while the real game-state objects remain isolated.
    """
    object_id = id(obj)

    if object_id in visited:
        return

    visited.add(object_id)

    if isinstance(obj, _ATOMIC_TYPES):
        return

    if isinstance(
        obj,
        (
            types.ModuleType,
            types.FunctionType,
            types.BuiltinFunctionType,
            type,
        ),
    ):
        memo[object_id] = obj
        return

    module_name = getattr(
        type(obj),
        "__module__",
        "",
    )

    if (
        module_name == "pygame"
        or module_name.startswith("pygame.")
    ):
        memo[object_id] = obj
        return

    if isinstance(obj, dict):
        for key, value in obj.items():
            _build_shared_runtime_memo(
                key,
                memo,
                visited,
            )
            _build_shared_runtime_memo(
                value,
                memo,
                visited,
            )
        return

    if isinstance(
        obj,
        (
            list,
            tuple,
            set,
            frozenset,
        ),
    ):
        for value in obj:
            _build_shared_runtime_memo(
                value,
                memo,
                visited,
            )
        return

    attributes = getattr(
        obj,
        "__dict__",
        None,
    )

    if isinstance(attributes, dict):
        for value in attributes.values():
            _build_shared_runtime_memo(
                value,
                memo,
                visited,
            )


def clone_game_for_simulation(
    game,
):
    """
    Safely clone a complete GameState for simulation.

    Returns:
        (copied_game, error_message)
    """
    memo: dict[int, Any] = {}

    try:
        _build_shared_runtime_memo(
            game,
            memo,
            set(),
        )

        copied_game = copy.deepcopy(
            game,
            memo,
        )

        return copied_game, None

    except Exception as error:
        return (
            None,
            (
                "game state could not be copied: "
                f"{error}"
            ),
        )


def find_copied_player(
    copied_game,
    original_player,
):
    original_name = getattr(
        original_player,
        "name",
        None,
    )

    for player in copied_game.players:
        if player.name == original_name:
            return player

    return None


def find_player_by_name(
    game,
    player_name,
):
    for player in game.players:
        if player.name == player_name:
            return player

    return None


def simulate_candidate_move(
    game,
    ai_player,
    move: dict,
    move_executor: MoveExecutor,
) -> tuple[float | None, str | None]:
    copied_game, copy_error = (
        clone_game_for_simulation(
            game
        )
    )

    if copied_game is None:
        return (
            None,
            copy_error,
        )

    copied_player = find_copied_player(
        copied_game,
        ai_player,
    )

    if copied_player is None:
        return (
            None,
            "copied AI player was not found",
        )

    before_value = evaluate_game_state(
        copied_game,
        copied_player,
    )

    try:
        success = move_executor(
            copied_game,
            copied_player,
            move,
        )

    except Exception as error:
        return (
            None,
            (
                "simulated move failed: "
                f"{error}"
            ),
        )

    if not success:
        return (
            None,
            "simulated move was unsuccessful",
        )

    after_value = evaluate_game_state(
        copied_game,
        copied_player,
    )

    improvement = (
        after_value - before_value
    )

    return round(
        improvement,
        2,
    ), None


def simulate_move_sequence(
    game,
    ai_player,
    moves: list[dict],
    move_executor: MoveExecutor,
) -> tuple[float | None, str | None]:
    """
    Simulate several forced moves on one isolated game clone.
    """
    copied_game, copy_error = (
        clone_game_for_simulation(
            game
        )
    )

    if copied_game is None:
        return (
            None,
            copy_error,
        )

    copied_player = find_copied_player(
        copied_game,
        ai_player,
    )

    if copied_player is None:
        return (
            None,
            "copied AI player was not found",
        )

    before_value = evaluate_game_state(
        copied_game,
        copied_player,
    )

    for move_index, move in enumerate(
        moves,
        start=1,
    ):
        try:
            success = move_executor(
                copied_game,
                copied_player,
                move,
            )

        except Exception as error:
            return (
                None,
                (
                    "simulated sequence move "
                    f"{move_index} failed: {error}"
                ),
            )

        if not success:
            return (
                None,
                (
                    "simulated sequence move "
                    f"{move_index} was unsuccessful"
                ),
            )

    after_value = evaluate_game_state(
        copied_game,
        copied_player,
    )

    improvement = (
        after_value - before_value
    )

    return round(
        improvement,
        2,
    ), None


def get_lookahead_bonus(
    game,
    ai_player,
    move: dict,
    move_executor: MoveExecutor,
) -> tuple[int, str | None]:
    improvement, error = (
        simulate_candidate_move(
            game,
            ai_player,
            move,
            move_executor,
        )
    )

    if improvement is None:
        return 0, error

    bounded_bonus = max(
        -80,
        min(
            100,
            int(improvement),
        ),
    )

    return (
        bounded_bonus,
        (
            "one-step lookahead predicts "
            f"board improvement "
            f"{improvement:+.1f}"
        ),
    )