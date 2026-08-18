# src/brain/working_memory.py

from collections import deque
from typing import Any


class WorkingMemory:
    def __init__(
        self,
        maximum_events: int = 20,
    ):
        self.maximum_events = (
            maximum_events
        )

        self.current_perception = {}
        self.previous_perception = {}
        self.current_goal = None
        self.current_plan = None

        self.predictions = []
        self.conclusions = []
        self.questions = {}
        self.recent_events = deque(
            maxlen=maximum_events
        )

    def update_perception(
        self,
        perception: dict[str, Any],
    ) -> None:
        self.previous_perception = (
            self.current_perception
        )

        self.current_perception = (
            perception
        )

        self._detect_changes()

    def _detect_changes(self) -> None:
        previous = self.previous_perception
        current = self.current_perception

        if not previous:
            return

        fields = [
            "ai_vp",
            "opponent_vp",
            "ai_hand_size",
            "ai_board_size",
            "opponent_board_size",
            "resource_difference",
        ]

        for field in fields:
            old_value = previous.get(field)
            new_value = current.get(field)

            if old_value == new_value:
                continue

            self.remember_event({
                "type": "state_change",
                "field": field,
                "before": old_value,
                "after": new_value,
            })

        previous_places = {
            card.get("name")
            for card in previous.get(
                "available_places",
                [],
            )
        }

        current_places = {
            card.get("name")
            for card in current.get(
                "available_places",
                [],
            )
        }

        removed_places = (
            previous_places - current_places
        )

        for place_name in removed_places:
            self.remember_event({
                "type": "market_change",
                "message": (
                    f"{place_name} left the "
                    "Place of Power market"
                ),
            })

    def remember_event(
        self,
        event: dict[str, Any],
    ) -> None:
        self.recent_events.append(event)

    def set_questions(
        self,
        questions: dict[str, Any],
    ) -> None:
        self.questions = questions

    def set_conclusions(
        self,
        conclusions: list[dict[str, Any]],
    ) -> None:
        self.conclusions = conclusions

    def set_predictions(
        self,
        predictions: list[dict[str, Any]],
    ) -> None:
        self.predictions = predictions

    def set_goal(
        self,
        goal: dict[str, Any],
    ) -> None:
        self.current_goal = goal

    def set_plan(
        self,
        plan: dict[str, Any] | None,
    ) -> None:
        self.current_plan = plan

    def summary(self) -> dict[str, Any]:
        return {
            "current_goal": self.current_goal,
            "current_plan": self.current_plan,
            "questions": self.questions,
            "conclusions": self.conclusions,
            "predictions": self.predictions,
            "recent_events": list(
                self.recent_events
            ),
        }

    def reset_turn_reasoning(self) -> None:
        self.questions = {}
        self.conclusions = []
        self.predictions = []
        self.current_plan = None