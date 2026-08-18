# src/brain/reflection.py

from typing import Any

from state_evaluator import (
    evaluate_game_state,
)


class ReflectionSystem:
    def __init__(self):
        self.reflections = []

    def reflect_after_move(
        self,
        game,
        ai_player,
        decision: dict[str, Any],
        state_value_before: float | None,
        state_value_after: float | None,
    ) -> dict[str, Any]:
        improvement = None

        if (
            state_value_before is not None
            and state_value_after is not None
        ):
            improvement = (
                state_value_after
                - state_value_before
            )

        reflection = {
            "round": getattr(
                game,
                "round_no",
                None,
            ),
            "move_type": decision.get("type"),
            "card_name": decision.get(
                "card_name"
            ),
            "goal": decision.get(
                "brain_goal"
            ),
            "plan": decision.get(
                "brain_plan"
            ),
            "predicted_score": decision.get(
                "score"
            ),
            "state_value_before": (
                state_value_before
            ),
            "state_value_after": (
                state_value_after
            ),
            "actual_improvement": (
                improvement
            ),
            "prediction_correct": (
                improvement is not None
                and improvement > 0
            ),
        }

        if improvement is None:
            reflection["lesson"] = (
                "The result could not be "
                "evaluated immediately."
            )

        elif improvement > 10:
            reflection["lesson"] = (
                "The move strongly improved "
                "the AI position."
            )

        elif improvement > 0:
            reflection["lesson"] = (
                "The move slightly improved "
                "the AI position."
            )

        elif improvement == 0:
            reflection["lesson"] = (
                "The move had no immediate "
                "board-value improvement."
            )

        else:
            reflection["lesson"] = (
                "The move reduced immediate "
                "board value and may only have "
                "delayed strategic value."
            )

        self.reflections.append(
            reflection
        )

        self.reflections = (
            self.reflections[-100:]
        )

        return reflection

    def current_state_value(
        self,
        game,
        ai_player,
    ) -> float:
        return evaluate_game_state(
            game,
            ai_player,
        )

    def recent_reflections(
        self,
        count: int = 10,
    ) -> list[dict[str, Any]]:
        return self.reflections[-count:]