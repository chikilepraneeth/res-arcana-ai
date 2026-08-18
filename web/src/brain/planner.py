# src/brain/planner.py

from typing import Any


SCORING_MOVE_TYPES = {
    "buy_monument",
    "buy_place_of_power",
}

ENGINE_MOVE_TYPES = {
    "play_card",
    "use_power",
}

RESOURCE_MOVE_TYPES = {
    "discard",
    "use_power",
}


def move_label(move: dict[str, Any]) -> str:
    move_type = move.get(
        "type",
        "unknown",
    )

    card_name = move.get("card_name")

    if card_name:
        return f"{move_type}: {card_name}"

    return move_type


def goal_alignment_score(
    move: dict[str, Any],
    goal: dict[str, Any],
    perception: dict[str, Any],
) -> tuple[float, list[str]]:
    move_type = move.get("type")
    card_name = move.get(
        "card_name",
        "",
    )

    goal_name = goal.get("name")
    target = goal.get("target")

    score = 0.0
    reasons = []

    if goal_name == "finish_game":
        if move_type in SCORING_MOVE_TYPES:
            score += 90
            reasons.append(
                "directly supports finishing "
                "the game"
            )

        if move_type == "pass":
            score -= 35
            reasons.append(
                "passing may waste a winning "
                "opportunity"
            )

    elif goal_name == "score_vp":
        if move_type == "buy_place_of_power":
            score += 75
            reasons.append(
                "Place of Power supports "
                "the VP goal"
            )

        elif move_type == "buy_monument":
            score += 65
            reasons.append(
                "monument supports the VP goal"
            )

        elif move_type == "play_card":
            score += 15
            reasons.append(
                "board development may create VP"
            )

    elif goal_name == "block_opponent":
        if target and card_name == target:
            score += 120
            reasons.append(
                f"denies the opponent {target}"
            )

        if move_type in SCORING_MOVE_TYPES:
            score += 30
            reasons.append(
                "claims a contested market card"
            )

    elif goal_name == "build_engine":
        if move_type == "play_card":
            score += 70
            reasons.append(
                "playing a card develops "
                "the engine"
            )

        elif move_type == "use_power":
            score += 35
            reasons.append(
                "using a power generates "
                "engine value"
            )

        elif move_type == "discard":
            score -= 15
            reasons.append(
                "discarding reduces future "
                "engine options"
            )

    elif goal_name == "gain_resources":
        if move_type == "discard":
            score += 60
            reasons.append(
                "discarding produces needed "
                "resources"
            )

        elif move_type == "use_power":
            score += 45
            reasons.append(
                "power may improve resources"
            )

        if move.get("reward_type") == "gold":
            score += 15
            reasons.append(
                "gold supports flexible scoring"
            )

    elif goal_name == "draw_cards":
        reasons_text = " ".join(
            move.get("reasons", [])
        ).lower()

        if (
            move_type == "use_power"
            and "draw" in reasons_text
        ):
            score += 90
            reasons.append(
                "power draws cards"
            )

        elif move_type == "pass":
            score += 10
            reasons.append(
                "passing may provide a fresh "
                "item and next-round card"
            )

    elif goal_name == "take_first_player":
        if move_type == "pass":
            score += 70
            reasons.append(
                "passing can claim first player"
            )

    elif goal_name == "balanced":
        if move_type in {
            "play_card",
            "use_power",
            "buy_monument",
            "buy_place_of_power",
        }:
            score += 10
            reasons.append(
                "maintains balanced development"
            )

    if (
        perception.get(
            "opponent_close_to_winning",
            False,
        )
        and move_type == "pass"
    ):
        score -= 50
        reasons.append(
            "passing is risky while the "
            "opponent is close to winning"
        )

    return score, reasons


def create_single_move_plan(
    move: dict[str, Any],
    goal: dict[str, Any],
    perception: dict[str, Any],
) -> dict[str, Any]:
    alignment_score, reasons = (
        goal_alignment_score(
            move,
            goal,
            perception,
        )
    )

    return {
        "name": move_label(move),
        "goal": goal["name"],
        "moves": [move],
        "first_move": move,
        "alignment_score": (
            alignment_score
        ),
        "plan_reasons": reasons,
        "risk": estimate_plan_risk(
            move,
            perception,
        ),
    }


def estimate_plan_risk(
    move: dict[str, Any],
    perception: dict[str, Any],
) -> float:
    move_type = move.get("type")
    risk = 0.0

    if move_type == "discard":
        risk += 15

    if move_type == "pass":
        risk += 10

    if (
        perception.get(
            "opponent_close_to_winning",
            False,
        )
        and move_type not in SCORING_MOVE_TYPES
    ):
        risk += 30

    if move_type == "use_power":
        reasons = " ".join(
            move.get("reasons", [])
        ).lower()

        if "unknown effect" in reasons:
            risk += 20

    return risk


def create_plans(
    legal_moves: list[dict[str, Any]],
    goal: dict[str, Any],
    perception: dict[str, Any],
) -> list[dict[str, Any]]:
    plans = [
        create_single_move_plan(
            move,
            goal,
            perception,
        )
        for move in legal_moves
    ]

    plans.sort(
        key=lambda plan: (
            plan["alignment_score"]
            - plan["risk"]
        ),
        reverse=True,
    )

    return plans