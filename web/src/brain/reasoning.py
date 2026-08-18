# src/brain/reasoning.py

from typing import Any


def ask_questions(
    perception: dict[str, Any],
) -> dict[str, Any]:
    visible_threats = perception.get(
        "visible_threats",
        [],
    )

    highest_threat = (
        visible_threats[0]
        if visible_threats
        else None
    )

    missing_resources = (
        perception.get(
            "hand_missing_resources",
            {},
        )
    )

    nearly_affordable_cards = [
        card_name
        for card_name, missing
        in missing_resources.items()
        if 0 < len(missing) <= 2
    ]

    questions = {
        "am_i_ahead": (
            perception.get(
                "vp_difference",
                0,
            ) > 0
        ),
        "am_i_behind": (
            perception.get(
                "vp_difference",
                0,
            ) < 0
        ),
        "am_i_far_behind": (
            perception.get(
                "vp_difference",
                0,
            ) <= -3
        ),
        "can_i_score_now": bool(
            perception.get(
                "affordable_places"
            )
            or perception.get(
                "affordable_monuments"
            )
        ),
        "can_opponent_win_soon": (
            perception.get(
                "opponent_close_to_winning",
                False,
            )
        ),
        "can_i_win_soon": (
            perception.get(
                "ai_close_to_winning",
                False,
            )
        ),
        "is_my_hand_empty": (
            perception.get(
                "ai_hand_size",
                0,
            ) == 0
        ),
        "do_i_need_resources": bool(
            nearly_affordable_cards
        ),
        "which_cards_are_nearly_affordable": (
            nearly_affordable_cards
        ),
        "is_market_threatening": bool(
            highest_threat
            and highest_threat.get(
                "danger",
                0,
            ) >= 7
        ),
        "highest_market_threat": (
            highest_threat
        ),
        "should_build_engine": (
            perception.get(
                "round",
                1,
            ) <= 2
            and perception.get(
                "ai_board_size",
                0,
            ) < 3
        ),
        "should_score_immediately": (
            perception.get(
                "round",
                1,
            ) >= 4
            or perception.get(
                "opponent_close_to_winning",
                False,
            )
        ),
        "should_take_first_player": (
            perception.get(
                "first_player_token_available",
                False,
            )
            and not perception.get(
                "has_first_player_token",
                False,
            )
        ),
    }

    return questions


def infer_opponent_intention(
    perception: dict[str, Any],
) -> list[dict[str, Any]]:
    predictions = []

    focus = perception.get(
        "opponent_resource_focus"
    )

    visible_places = {
        card.get("name")
        for card in perception.get(
            "available_places",
            [],
        )
    }

    if (
        focus == "death"
        and "Catacombs of the Dead"
        in visible_places
    ):
        predictions.append({
            "prediction": (
                "opponent may be preparing "
                "to buy Catacombs of the Dead"
            ),
            "confidence": 0.75,
            "target": (
                "Catacombs of the Dead"
            ),
        })

    if (
        focus in {"death", "life", "calm"}
        and (
            "Dragon’s Lair"
            in visible_places
            or "Dragon's Lair"
            in visible_places
        )
    ):
        predictions.append({
            "prediction": (
                "opponent may be preparing "
                "a Dragon's Lair strategy"
            ),
            "confidence": 0.55,
            "target": "Dragon’s Lair",
        })

    if (
        perception.get(
            "opponent_resources",
            {},
        ).get("gold", 0) >= 4
        and perception.get(
            "available_monuments"
        )
    ):
        predictions.append({
            "prediction": (
                "opponent can buy a monument "
                "on the next action"
            ),
            "confidence": 0.85,
            "target": "monument",
        })

    if perception.get(
        "opponent_close_to_winning",
        False,
    ):
        predictions.append({
            "prediction": (
                "opponent is likely to choose "
                "direct VP over engine growth"
            ),
            "confidence": 0.9,
            "target": "direct_scoring",
        })

    return predictions


def create_conclusions(
    perception: dict[str, Any],
    questions: dict[str, Any],
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    conclusions = []

    if questions["can_opponent_win_soon"]:
        conclusions.append({
            "type": "danger",
            "priority": 100,
            "message": (
                "The opponent is close to "
                "winning. Defensive or direct "
                "scoring actions are urgent."
            ),
        })

    if questions["can_i_win_soon"]:
        conclusions.append({
            "type": "opportunity",
            "priority": 95,
            "message": (
                "The AI is close to winning "
                "and should prioritize direct VP."
            ),
        })

    if questions["am_i_far_behind"]:
        conclusions.append({
            "type": "position",
            "priority": 85,
            "message": (
                "The AI is far behind in VP "
                "and must increase scoring speed."
            ),
        })

    if questions["can_i_score_now"]:
        conclusions.append({
            "type": "opportunity",
            "priority": 80,
            "message": (
                "A scoring card is currently "
                "affordable."
            ),
        })

    if questions["is_market_threatening"]:
        threat = questions[
            "highest_market_threat"
        ]

        conclusions.append({
            "type": "threat",
            "priority": 78,
            "message": (
                f"{threat['name']} is a "
                "dangerous market card."
            ),
            "target": threat["name"],
        })

    if questions["should_build_engine"]:
        conclusions.append({
            "type": "development",
            "priority": 55,
            "message": (
                "The AI has a small board in "
                "the early game and should "
                "develop its engine."
            ),
        })

    if questions["do_i_need_resources"]:
        cards = questions[
            "which_cards_are_nearly_affordable"
        ]

        conclusions.append({
            "type": "resource_need",
            "priority": 60,
            "message": (
                "The AI needs resources for: "
                + ", ".join(cards)
            ),
            "cards": cards,
        })

    if questions["is_my_hand_empty"]:
        conclusions.append({
            "type": "card_shortage",
            "priority": 50,
            "message": (
                "The AI has no cards in hand "
                "and should value draw effects."
            ),
        })

    for prediction in predictions:
        conclusions.append({
            "type": "prediction",
            "priority": int(
                prediction["confidence"]
                * 70
            ),
            "message": prediction[
                "prediction"
            ],
            "target": prediction.get(
                "target"
            ),
        })

    conclusions.sort(
        key=lambda item: item["priority"],
        reverse=True,
    )

    return conclusions


def reason_about_game(
    perception: dict[str, Any],
) -> dict[str, Any]:
    questions = ask_questions(
        perception
    )

    predictions = infer_opponent_intention(
        perception
    )

    conclusions = create_conclusions(
        perception,
        questions,
        predictions,
    )

    return {
        "questions": questions,
        "predictions": predictions,
        "conclusions": conclusions,
    }