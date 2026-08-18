# src/brain/decision.py

from typing import Any
import random

from ai_brain import (
    apply_human_like_noise,
    apply_memory_reaction,
)
from sequence_memory import get_sequence_bonus
from lookahead import get_lookahead_bonus

# ------------------------------------------------------------------
# Experience brain
# ------------------------------------------------------------------

try:
    from brain.experience_brain import (
        evaluate_candidate_from_experience,
    )
except ImportError:
    try:
        from .experience_brain import (
            evaluate_candidate_from_experience,
        )
    except ImportError:
        evaluate_candidate_from_experience = None


# ------------------------------------------------------------------
# Neural model
# ------------------------------------------------------------------

import sys

IS_WEB = sys.platform == "emscripten"

if not IS_WEB:
    try:
        from ml.neural_counter_model import (
            load_trained_model,
            predict_human_style_score,
        )
    except ImportError:
        load_trained_model = None
        predict_human_style_score = None
else:
    try:
        from ml.web_neural_model import (
            load_trained_model,
            predict_human_style_score,
        )

        print("WEB NEURAL INFERENCE ENABLED")

    except ImportError as error:
        print(
            "WEB NEURAL IMPORT FAILED:",
            error,
        )

        load_trained_model = None
        predict_human_style_score = None


_NEURAL_MODEL_BUNDLE = None
_NEURAL_MODEL_LOAD_ATTEMPTED = False

# Neural learning is still useful, but it remains only one signal.
NEURAL_BONUS_WEIGHT = 20.0

# Human experience learning is also capped.
EXPERIENCE_BONUS_WEIGHT = 1.0

# Controlled exploration:
# usually choose the best move, but occasionally try another strong move.
EXPLORATION_CHANCE = 0.10
EXPLORATION_SCORE_WINDOW = 18.0
EXPLORATION_MAX_ALTERNATIVES = 3


def learning_enabled(player):
    return bool(
        getattr(
            player,
            "learning_enabled",
            True,
        )
    )


def reward_memory_enabled(player):
    return (
        learning_enabled(player)
        and bool(
            getattr(
                player,
                "reward_memory_enabled",
                True,
            )
        )
    )


def context_memory_enabled(player):
    return (
        learning_enabled(player)
        and bool(
            getattr(
                player,
                "context_memory_enabled",
                True,
            )
        )
    )


def sequence_memory_enabled(player):
    return (
        learning_enabled(player)
        and bool(
            getattr(
                player,
                "sequence_memory_enabled",
                True,
            )
        )
    )


def counter_memory_enabled(player):
    return (
        learning_enabled(player)
        and bool(
            getattr(
                player,
                "counter_memory_enabled",
                True,
            )
        )
    )


def neural_learning_enabled(player):
    return (
        learning_enabled(player)
        and bool(
            getattr(
                player,
                "neural_learning_enabled",
                True,
            )
        )
    )


def experience_learning_enabled(player):
    return (
        learning_enabled(player)
        and bool(
            getattr(
                player,
                "experience_learning_enabled",
                True,
            )
        )
    )


def get_neural_model_bundle():
    """
    Load the trained neural model only once per process.
    """
    global _NEURAL_MODEL_BUNDLE
    global _NEURAL_MODEL_LOAD_ATTEMPTED

    if _NEURAL_MODEL_LOAD_ATTEMPTED:
        return _NEURAL_MODEL_BUNDLE

    _NEURAL_MODEL_LOAD_ATTEMPTED = True

    if load_trained_model is None:
        return None

    try:
        _NEURAL_MODEL_BUNDLE = (
            load_trained_model()
        )
    except Exception as error:
        print(
            "Warning: neural model could not be loaded: "
            f"{error}"
        )
        _NEURAL_MODEL_BUNDLE = None

    return _NEURAL_MODEL_BUNDLE


def _history_move_type(move):
    if not isinstance(move, dict):
        return None

    return (
        move.get("move_type")
        or move.get("type")
    )


def _normalize_history_move(move):
    if not isinstance(move, dict):
        return None

    normalized = dict(move)

    if (
        "move_type" not in normalized
        and "type" in normalized
    ):
        normalized["move_type"] = (
            normalized["type"]
        )

    if (
        "type" not in normalized
        and "move_type" in normalized
    ):
        normalized["type"] = (
            normalized["move_type"]
        )

    return normalized


def _player_name_from_move(move):
    if not isinstance(move, dict):
        return None

    return (
        move.get("player")
        or move.get("player_name")
    )


def _recent_recorded_moves(game):
    candidates = []

    game_record = getattr(
        game,
        "game_record",
        None,
    )

    if isinstance(game_record, dict):
        candidates = game_record.get(
            "moves",
            [],
        )

    if not candidates:
        game_record = getattr(
            game,
            "current_game_record",
            None,
        )

        if isinstance(game_record, dict):
            candidates = game_record.get(
                "moves",
                [],
            )

    if not candidates:
        candidates = getattr(
            game,
            "move_history",
            [],
        )

    if not candidates:
        candidates = getattr(
            game,
            "ai_move_history",
            [],
        )

    return (
        candidates
        if isinstance(candidates, list)
        else []
    )


def _find_previous_moves(
    game,
    ai_player,
):
    history = _recent_recorded_moves(
        game
    )

    previous_human_move = None
    previous_ai_move = None

    ai_name = getattr(
        ai_player,
        "name",
        None,
    )

    for old_move in reversed(history):
        player_name = (
            _player_name_from_move(
                old_move
            )
        )

        if (
            previous_ai_move is None
            and player_name == ai_name
        ):
            previous_ai_move = (
                _normalize_history_move(
                    old_move
                )
            )

        if (
            previous_human_move is None
            and player_name
            and player_name != ai_name
        ):
            previous_human_move = (
                _normalize_history_move(
                    old_move
                )
            )

        if (
            previous_human_move is not None
            and previous_ai_move is not None
        ):
            break

    return (
        previous_human_move,
        previous_ai_move,
    )


def _snapshot_for_neural_model(game):
    try:
        from game_memory import snapshot_game
        return snapshot_game(game)
    except Exception:
        return None


def get_neural_bonus(
    game,
    ai_player,
    candidate_move,
):
    print(
        "WEB NEURAL DEBUG:",
        "enabled=",
        neural_learning_enabled(ai_player),
        "predictor=",
        predict_human_style_score is not None,
        "loader=",
        load_trained_model is not None,
    )

    if not neural_learning_enabled(
        ai_player
    ):
        return 0.0, None, None

    if predict_human_style_score is None:
        return 0.0, None, None

    bundle = get_neural_model_bundle()

    print(
        "WEB NEURAL BUNDLE:",
        "loaded=",
        bundle is not None,
        "type=",
        type(bundle).__name__ if bundle is not None else None,
    )

    if bundle is None:
        return 0.0, None, None

    state = _snapshot_for_neural_model(
        game
    )

    if state is None:
        return 0.0, None, None

    (
        previous_human_move,
        previous_ai_move,
    ) = _find_previous_moves(
        game,
        ai_player,
    )

    try:
        probability = float(
            predict_human_style_score(
                state=state,
                candidate_move=candidate_move,
                previous_human_move=(
                    previous_human_move
                ),
                previous_ai_move=(
                    previous_ai_move
                ),
                model_bundle=bundle,
            )
        )
    except Exception as error:
        return (
            0.0,
            None,
            "neural score unavailable: "
            f"{error}",
        )

    probability = max(
        0.0,
        min(
            1.0,
            probability,
        ),
    )

    bonus = (
        probability - 0.5
    ) * (
        NEURAL_BONUS_WEIGHT * 2.0
    )

    reason = (
        "neural learned-pattern score "
        f"{probability:.3f} "
        f"({bonus:+.1f})"
    )

    return (
        bonus,
        probability,
        reason,
    )


def get_experience_bonus(
    game,
    ai_player,
    candidate_move,
):
    """
    Ask the new experience brain whether similar human decisions
    from previous real games support this candidate.
    """
    if not experience_learning_enabled(
        ai_player
    ):
        return 0.0, None, None

    if evaluate_candidate_from_experience is None:
        return 0.0, None, None

    try:
        bonus, info = (
            evaluate_candidate_from_experience(
                game,
                ai_player,
                candidate_move,
            )
        )
    except Exception as error:
        return (
            0.0,
            None,
            "experience brain unavailable: "
            f"{error}",
        )

    bonus *= EXPERIENCE_BONUS_WEIGHT

    matches = int(
        info.get(
            "matches",
            0,
        )
    )

    if matches <= 0:
        return (
            0.0,
            info,
            None,
        )

    similarity = info.get(
        "mean_similarity",
        0.0,
    )

    learned_value = info.get(
        "learned_value",
        0.0,
    )

    reason = (
        "human experience "
        f"{matches} similar decision(s), "
        f"similarity={similarity:.3f}, "
        f"learned_value={learned_value:+.3f}, "
        f"bonus={bonus:+.1f}"
    )

    return (
        bonus,
        info,
        reason,
    )


def evaluate_plan(
    plan: dict[str, Any],
    game,
    ai_player,
    execute_move_for_simulation,
) -> dict[str, Any]:
    move = dict(
        plan["first_move"]
    )

    score = float(
        move.get(
            "score",
            0,
        )
    )

    reasons = list(
        move.get(
            "reasons",
            [],
        )
    )

    alignment_score = float(
        plan.get(
            "alignment_score",
            0,
        )
    )

    risk = float(
        plan.get(
            "risk",
            0,
        )
    )

    score += alignment_score
    score -= risk

    reasons.extend(
        plan.get(
            "plan_reasons",
            [],
        )
    )

    if alignment_score:
        reasons.append(
            "brain goal alignment "
            f"{alignment_score:+.1f}"
        )

    if risk:
        reasons.append(
            f"plan risk {-risk:+.1f}"
        )

    recent_moves = getattr(
        game,
        "ai_move_history",
        [],
    )

    # ============================================================
    # STAGNATION / REPETITION
    # ============================================================

    same_move_count = sum(
        1
        for old_move in recent_moves
        if (
            old_move.get("player")
            == ai_player.name
            and _history_move_type(
                old_move
            )
            == move.get("type")
            and old_move.get(
                "card_name"
            )
            == move.get(
                "card_name"
            )
        )
    )

    if same_move_count >= 2:
        repetition_penalty = (
            same_move_count * 30
        )

        score -= repetition_penalty

        reasons.append(
            "repeated action without "
            "new progress "
            f"{-repetition_penalty}"
        )

    if (
        same_move_count >= 2
        and move.get(
            "type"
        ) == "use_power"
        and getattr(
            ai_player,
            "victory_points",
            0,
        ) >= 7
    ):
        score -= 60

        reasons.append(
            "late-game stagnation: "
            "look for direct VP progress"
        )

    # ============================================================
    # SEQUENCE MEMORY
    # ============================================================

    if sequence_memory_enabled(
        ai_player
    ):
        (
            sequence_bonus,
            sequence_reason,
        ) = get_sequence_bonus(
            recent_moves,
            move,
        )

        score += sequence_bonus

        if sequence_reason:
            reasons.append(
                sequence_reason
            )

    # ============================================================
    # EXISTING MEMORY SYSTEMS
    # ============================================================

    score, reasons = (
        apply_memory_reaction(
            move,
            score,
            reasons,
            game=game,
            ai_player=ai_player,
            use_reward=(
                reward_memory_enabled(
                    ai_player
                )
            ),
            use_context=(
                context_memory_enabled(
                    ai_player
                )
            ),
            use_counter=(
                counter_memory_enabled(
                    ai_player
                )
            ),
        )
    )

    # ============================================================
    # EXISTING NEURAL LEARNING
    # ============================================================

    (
        neural_bonus,
        neural_probability,
        neural_reason,
    ) = get_neural_bonus(
        game,
        ai_player,
        move,
    )

    score += neural_bonus

    if neural_reason:
        reasons.append(
            neural_reason
        )

    # ============================================================
    # NEW EXPERIENCE BRAIN
    # ============================================================

    (
        experience_bonus,
        experience_info,
        experience_reason,
    ) = get_experience_bonus(
        game,
        ai_player,
        move,
    )

    score += experience_bonus

    if experience_reason:
        reasons.append(
            experience_reason
        )

    # ============================================================
    # LOOKAHEAD
    # ============================================================

    if move.get(
        "type"
    ) != "use_power":
        (
            lookahead_bonus,
            lookahead_reason,
        ) = get_lookahead_bonus(
            game,
            ai_player,
            move,
            execute_move_for_simulation,
        )

        score += lookahead_bonus

        if lookahead_reason:
            reasons.append(
                lookahead_reason
            )

    # ============================================================
    # HUMAN-LIKE VARIATION
    # ============================================================

    score = apply_human_like_noise(
        score,
        difficulty="normal",
    )

    move["score"] = round(
        score,
        2,
    )

    move["reasons"] = reasons
    move["brain_goal"] = (
        plan.get("goal")
    )
    move["brain_plan"] = (
        plan.get("name")
    )
    move["goal_alignment"] = (
        alignment_score
    )
    move["plan_risk"] = risk

    move["neural_score"] = (
        neural_probability
    )
    move["neural_bonus"] = round(
        neural_bonus,
        2,
    )

    move["experience_bonus"] = round(
        experience_bonus,
        2,
    )

    move["experience_info"] = (
        experience_info
    )

    return move


def _exploration_enabled(
    game,
    ai_player,
):
    explicit = getattr(
        game,
        "brain_exploration_enabled",
        None,
    )

    if explicit is not None:
        return bool(explicit)

    if getattr(
        game,
        "self_play",
        False,
    ):
        return False

    return bool(
        getattr(
            ai_player,
            "brain_exploration_enabled",
            True,
        )
    )


def _choose_with_exploration(
    evaluated_moves,
    game,
    ai_player,
):
    best = evaluated_moves[0]

    if not _exploration_enabled(
        game,
        ai_player,
    ):
        return best

    chance = float(
        getattr(
            ai_player,
            "brain_exploration_chance",
            EXPLORATION_CHANCE,
        )
    )

    chance = max(
        0.0,
        min(0.30, chance),
    )

    if random.random() >= chance:
        return best

    best_score = float(
        best.get(
            "score",
            0.0,
        )
    )

    window = float(
        getattr(
            ai_player,
            "brain_exploration_score_window",
            EXPLORATION_SCORE_WINDOW,
        )
    )

    alternatives = [
        move
        for move in evaluated_moves[
            1:
            1 + EXPLORATION_MAX_ALTERNATIVES
        ]
        if (
            move.get("type") != "pass"
            and float(
                move.get(
                    "score",
                    -9999,
                )
            )
            >= best_score - window
        )
    ]

    if not alternatives:
        return best

    chosen = random.choice(
        alternatives
    )

    chosen = dict(chosen)

    reasons = list(
        chosen.get(
            "reasons",
            [],
        )
    )

    reasons.append(
        "controlled exploration: "
        "trying another strong move "
        "instead of always repeating "
        "the highest-scored choice"
    )

    chosen["reasons"] = reasons
    chosen["brain_exploration"] = True

    return chosen


def choose_best_plan(
    plans: list[dict[str, Any]],
    game,
    ai_player,
    execute_move_for_simulation,
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
]:
    if not plans:
        fallback = {
            "type": "pass",
            "score": 0,
            "reasons": [
                "brain found no available plan"
            ],
            "brain_goal": "balanced",
            "brain_plan": "pass",
            "neural_score": None,
            "neural_bonus": 0.0,
            "experience_bonus": 0.0,
            "experience_info": None,
        }

        return (
            fallback,
            [fallback],
        )

    evaluated_moves = [
        evaluate_plan(
            plan,
            game,
            ai_player,
            execute_move_for_simulation,
        )
        for plan in plans
    ]

    evaluated_moves.sort(
        key=lambda move: move[
            "score"
        ],
        reverse=True,
    )

    chosen = _choose_with_exploration(
        evaluated_moves,
        game,
        ai_player,
    )

    return (
        chosen,
        evaluated_moves,
    )