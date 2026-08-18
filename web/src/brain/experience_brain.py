# src/brain/experience_brain.py

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


# How many past examples to use when judging a candidate.
MAX_NEIGHBORS = 12

# Final influence on decision.py.
MAX_EXPERIENCE_BONUS = 28.0

# Similarity below this is ignored.
MIN_SIMILARITY = 0.42


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _memory_path() -> Path:
    return _project_root() / "memory" / "game_memory.json"


def _safe_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _load_games() -> list[dict[str, Any]]:
    path = _memory_path()

    if not path.exists():
        return []

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        if isinstance(data, list):
            return data

    except (OSError, json.JSONDecodeError):
        pass

    return []


def _move_type(move: dict[str, Any]) -> str:
    return str(
        move.get("move_type")
        or move.get("type")
        or ""
    )


def _player_name(move: dict[str, Any]) -> str:
    return str(
        move.get("player")
        or move.get("player_name")
        or ""
    )


def _card_name(move: dict[str, Any]) -> str:
    return str(move.get("card_name") or "")


def _extract_player_state(
    state: dict[str, Any],
    player_name: str,
) -> dict[str, Any]:
    """
    Works with several snapshot layouts so the module survives
    small future changes to game_memory.py.
    """
    if not isinstance(state, dict):
        return {}

    players = state.get("players")

    if isinstance(players, list):
        for player in players:
            if not isinstance(player, dict):
                continue

            name = (
                player.get("name")
                or player.get("player_name")
            )

            if name == player_name:
                return player

    if isinstance(players, dict):
        player = players.get(player_name)

        if isinstance(player, dict):
            return player

    direct = state.get(player_name)

    if isinstance(direct, dict):
        return direct

    return {}


def _pool_vector(player_state: dict[str, Any]) -> list[float]:
    pool = (
        player_state.get("essence_pool")
        or player_state.get("essence")
        or {}
    )

    if not isinstance(pool, dict):
        pool = {}

    return [
        _safe_float(pool.get("elan")),
        _safe_float(pool.get("life")),
        _safe_float(pool.get("calm")),
        _safe_float(pool.get("death")),
        _safe_float(pool.get("gold")),
    ]


def _list_len(player_state: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = player_state.get(key)

        if isinstance(value, list):
            return len(value)

    return 0


def _state_features(
    state: dict[str, Any],
    ai_name: str,
    human_name: str,
) -> list[float]:
    """
    General board features only.
    No hand-written strategy labels such as dragon/death/storage.
    """
    ai_state = _extract_player_state(state, ai_name)
    human_state = _extract_player_state(state, human_name)

    features: list[float] = []

    features.extend(_pool_vector(ai_state))
    features.extend(_pool_vector(human_state))

    features.extend(
        [
            _safe_float(
                ai_state.get("victory_points")
                or ai_state.get("vp")
            ),
            _safe_float(
                human_state.get("victory_points")
                or human_state.get("vp")
            ),
            float(_list_len(ai_state, "hand")),
            float(_list_len(human_state, "hand")),
            float(
                _list_len(
                    ai_state,
                    "played",
                    "artifacts",
                )
            ),
            float(
                _list_len(
                    human_state,
                    "played",
                    "artifacts",
                )
            ),
            float(
                _list_len(
                    ai_state,
                    "monuments",
                )
            ),
            float(
                _list_len(
                    human_state,
                    "monuments",
                )
            ),
            float(
                _list_len(
                    ai_state,
                    "places",
                    "places_of_power",
                )
            ),
            float(
                _list_len(
                    human_state,
                    "places",
                    "places_of_power",
                )
            ),
            _safe_float(state.get("round_no"), 1.0),
        ]
    )

    return features


def _cosine_similarity(
    a: list[float],
    b: list[float],
) -> float:
    if not a or not b:
        return 0.0

    length = min(len(a), len(b))
    a = a[:length]
    b = b[:length]

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))

    if norm_a <= 0 or norm_b <= 0:
        return 0.0

    return max(
        0.0,
        min(1.0, dot / (norm_a * norm_b)),
    )


def _action_similarity(
    candidate: dict[str, Any],
    historical: dict[str, Any],
) -> float:
    """
    The AI should reuse an idea, not require the exact same card.

    Same action type matters most.
    Same exact card adds extra confidence when available.
    """
    candidate_type = _move_type(candidate)
    historical_type = _move_type(historical)

    if not candidate_type or candidate_type != historical_type:
        return 0.0

    score = 0.72

    candidate_card = _card_name(candidate)
    historical_card = _card_name(historical)

    if (
        candidate_card
        and historical_card
        and candidate_card == historical_card
    ):
        score += 0.20

    candidate_reward = candidate.get("reward_type")
    historical_reward = historical.get("reward_type")

    if (
        candidate_reward
        and historical_reward
        and candidate_reward == historical_reward
    ):
        score += 0.08

    return min(1.0, score)


def _move_outcome_value(
    move: dict[str, Any],
    next_move: dict[str, Any] | None,
    game_result: dict[str, Any],
    human_name: str,
) -> float:
    """
    Estimate whether the demonstrated human decision was useful.

    We prefer saved explicit rewards when present.
    Otherwise use:
      - winner of the finished game
      - immediate reward / VP change fields when available
      - whether the action was followed by continued useful play
    """
    explicit_reward = move.get("reward")

    if explicit_reward is not None:
        return max(
            -1.0,
            min(1.0, _safe_float(explicit_reward)),
        )

    value = 0.0

    winner = (
        game_result.get("winner")
        or game_result.get("winning_player")
    )

    if winner:
        if winner == human_name:
            value += 0.55
        else:
            value -= 0.35

    for key in (
        "immediate_reward",
        "reward_value",
        "vp_delta",
    ):
        if key in move:
            raw = _safe_float(move.get(key))
            value += max(-0.35, min(0.35, raw / 5.0))

    # If the human immediately continued with another non-pass move,
    # lightly reward the demonstrated move as part of a sequence.
    if next_move is not None:
        if (
            _player_name(next_move) == human_name
            and _move_type(next_move) != "pass"
        ):
            value += 0.08

    return max(-1.0, min(1.0, value))


def _historical_examples(
    human_name: str,
) -> list[dict[str, Any]]:
    examples = []

    for game in _load_games():
        moves = game.get("moves", []) or []

        if not isinstance(moves, list):
            continue

        for index, move in enumerate(moves):
            if not isinstance(move, dict):
                continue

            if _player_name(move) != human_name:
                continue

            state_before = (
                move.get("state_before")
                or move.get("before_state")
                or move.get("state")
            )

            if not isinstance(state_before, dict):
                continue

            next_move = None

            if index + 1 < len(moves):
                maybe_next = moves[index + 1]

                if isinstance(maybe_next, dict):
                    next_move = maybe_next

            examples.append(
                {
                    "state_before": state_before,
                    "move": move,
                    "next_move": next_move,
                    "outcome": _move_outcome_value(
                        move,
                        next_move,
                        game,
                        human_name,
                    ),
                }
            )

    return examples


_EXAMPLE_CACHE: dict[str, list[dict[str, Any]]] = {}


def clear_experience_cache():
    """
    Call this after retraining/updating memory if you want the current
    process to immediately reload newly saved human games.
    """
    _EXAMPLE_CACHE.clear()


def _get_examples(
    human_name: str,
) -> list[dict[str, Any]]:
    if human_name not in _EXAMPLE_CACHE:
        _EXAMPLE_CACHE[human_name] = (
            _historical_examples(
                human_name
            )
        )

    return _EXAMPLE_CACHE[human_name]


def evaluate_candidate_from_experience(
    game,
    ai_player,
    candidate_move: dict[str, Any],
) -> tuple[float, dict[str, Any]]:
    """
    Main public function.

    Returns:
        experience_bonus,
        debug_info

    The system does not use fixed strategy names.
    It asks:
      "In similar board states, what did the human do?"
      "Did that kind of move help?"
      "Is my current candidate similar to the demonstrated move?"
    """
    try:
        from game_memory import snapshot_game
        current_state = snapshot_game(game)
    except Exception:
        return 0.0, {
            "reason": "snapshot unavailable",
            "matches": 0,
        }

    if not isinstance(current_state, dict):
        return 0.0, {
            "reason": "invalid snapshot",
            "matches": 0,
        }

    ai_name = getattr(
        ai_player,
        "name",
        "AI Companion",
    )

    human_player = next(
        (
            player
            for player in getattr(game, "players", [])
            if player is not ai_player
        ),
        None,
    )

    if human_player is None:
        return 0.0, {
            "reason": "human player unavailable",
            "matches": 0,
        }

    human_name = getattr(
        human_player,
        "name",
        "Chikile",
    )

    current_features = _state_features(
        current_state,
        ai_name=ai_name,
        human_name=human_name,
    )

    examples = _get_examples(
        human_name
    )

    if not examples:
        return 0.0, {
            "reason": "no human experience yet",
            "matches": 0,
        }

    ranked = []

    for example in examples:
        old_state = example["state_before"]

        old_features = _state_features(
            old_state,
            ai_name=ai_name,
            human_name=human_name,
        )

        state_similarity = _cosine_similarity(
            current_features,
            old_features,
        )

        if state_similarity < MIN_SIMILARITY:
            continue

        action_similarity = _action_similarity(
            candidate_move,
            example["move"],
        )

        if action_similarity <= 0:
            continue

        combined_similarity = (
            state_similarity * 0.72
            + action_similarity * 0.28
        )

        ranked.append(
            (
                combined_similarity,
                state_similarity,
                action_similarity,
                example,
            )
        )

    if not ranked:
        return 0.0, {
            "reason": "no similar human decisions",
            "matches": 0,
        }

    ranked.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    neighbors = ranked[:MAX_NEIGHBORS]

    weighted_value = 0.0
    total_weight = 0.0

    exact_card_matches = 0

    for (
        combined_similarity,
        state_similarity,
        action_similarity,
        example,
    ) in neighbors:
        weight = combined_similarity ** 2

        outcome = float(
            example["outcome"]
        )

        weighted_value += weight * outcome
        total_weight += weight

        if (
            _card_name(candidate_move)
            and _card_name(candidate_move)
            == _card_name(example["move"])
        ):
            exact_card_matches += 1

    if total_weight <= 0:
        return 0.0, {
            "reason": "experience weights were zero",
            "matches": 0,
        }

    learned_value = (
        weighted_value / total_weight
    )

    # Confidence grows with both similarity and number of examples.
    mean_similarity = sum(
        item[0]
        for item in neighbors
    ) / len(neighbors)

    sample_confidence = min(
        1.0,
        len(neighbors) / 6.0,
    )

    confidence = (
        mean_similarity * 0.70
        + sample_confidence * 0.30
    )

    bonus = (
        learned_value
        * confidence
        * MAX_EXPERIENCE_BONUS
    )

    bonus = max(
        -MAX_EXPERIENCE_BONUS,
        min(MAX_EXPERIENCE_BONUS, bonus),
    )

    info = {
        "reason": "similar human decisions found",
        "matches": len(neighbors),
        "mean_similarity": round(
            mean_similarity,
            3,
        ),
        "learned_value": round(
            learned_value,
            3,
        ),
        "confidence": round(
            confidence,
            3,
        ),
        "exact_card_matches": exact_card_matches,
        "bonus": round(bonus, 2),
    }

    return round(bonus, 2), info