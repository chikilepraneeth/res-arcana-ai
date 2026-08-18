# src/brain/goals.py

from typing import Any


GOAL_SCORE_VP = "score_vp"
GOAL_FINISH_GAME = "finish_game"
GOAL_BLOCK_OPPONENT = "block_opponent"
GOAL_BUILD_ENGINE = "build_engine"
GOAL_GAIN_RESOURCES = "gain_resources"
GOAL_DRAW_CARDS = "draw_cards"
GOAL_PREPARE_COMBO = "prepare_combo"
GOAL_TAKE_FIRST_PLAYER = "take_first_player"
GOAL_BALANCED = "balanced"


def create_goal(
    name: str,
    priority: int,
    reason: str,
    target: str | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "priority": priority,
        "reason": reason,
        "target": target,
    }


def generate_candidate_goals(
    perception: dict[str, Any],
    reasoning: dict[str, Any],
) -> list[dict[str, Any]]:
    questions = reasoning.get(
        "questions",
        {},
    )

    goals = []

    if questions.get("can_i_win_soon"):
        goals.append(
            create_goal(
                GOAL_FINISH_GAME,
                100,
                (
                    "AI is close to the victory "
                    "threshold."
                ),
            )
        )

    if questions.get(
        "can_opponent_win_soon"
    ):
        goals.append(
            create_goal(
                GOAL_BLOCK_OPPONENT,
                98,
                (
                    "Opponent is close to "
                    "winning."
                ),
            )
        )

    if questions.get("can_i_score_now"):
        goals.append(
            create_goal(
                GOAL_SCORE_VP,
                88,
                (
                    "A scoring card is "
                    "affordable now."
                ),
            )
        )

    threat = questions.get(
        "highest_market_threat"
    )

    if (
        threat
        and threat.get("danger", 0) >= 7
    ):
        goals.append(
            create_goal(
                GOAL_BLOCK_OPPONENT,
                85,
                (
                    f"{threat['name']} is a "
                    "major market threat."
                ),
                target=threat["name"],
            )
        )

    if questions.get("should_build_engine"):
        goals.append(
            create_goal(
                GOAL_BUILD_ENGINE,
                70,
                (
                    "Early-game board "
                    "development is weak."
                ),
            )
        )

    if questions.get("do_i_need_resources"):
        goals.append(
            create_goal(
                GOAL_GAIN_RESOURCES,
                68,
                (
                    "Resources are missing for "
                    "important hand cards."
                ),
            )
        )

    if questions.get("is_my_hand_empty"):
        goals.append(
            create_goal(
                GOAL_DRAW_CARDS,
                65,
                (
                    "The AI needs more cards "
                    "and future options."
                ),
            )
        )

    if questions.get(
        "should_take_first_player"
    ):
        goals.append(
            create_goal(
                GOAL_TAKE_FIRST_PLAYER,
                35,
                (
                    "Taking first player may "
                    "improve next round."
                ),
            )
        )

    goals.append(
        create_goal(
            GOAL_BALANCED,
            20,
            (
                "Maintain a balanced position "
                "when no urgent goal dominates."
            ),
        )
    )

    goals.sort(
        key=lambda goal: goal["priority"],
        reverse=True,
    )

    return goals


def choose_primary_goal(
    perception: dict[str, Any],
    reasoning: dict[str, Any],
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
]:
    goals = generate_candidate_goals(
        perception,
        reasoning,
    )

    return goals[0], goals