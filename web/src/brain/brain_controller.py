# src/brain/brain_controller.py

from typing import Any

from .perception import perceive_game
from .working_memory import WorkingMemory
from .reasoning import reason_about_game
from .goals import choose_primary_goal
from .planner import create_plans
from .decision import choose_best_plan
from .reflection import ReflectionSystem


class BrainController:
    def __init__(self):
        self.working_memory = (
            WorkingMemory()
        )

        self.reflection = (
            ReflectionSystem()
        )

        self.last_thought_process = {}
        self.last_state_value = None

    def choose_action(
        self,
        game,
        ai_player,
    ) -> tuple[
        dict[str, Any],
        list[dict[str, Any]],
    ]:
        # Local import avoids circular import
        # while ai_advisor imports BrainController.
        from ai_advisor import (
            get_ai_legal_moves,
            execute_move_for_simulation,
        )

        perception = perceive_game(
            game,
            ai_player,
        )

        self.working_memory.reset_turn_reasoning()

        self.working_memory.update_perception(
            perception
        )

        reasoning = reason_about_game(
            perception
        )

        self.working_memory.set_questions(
            reasoning["questions"]
        )

        self.working_memory.set_predictions(
            reasoning["predictions"]
        )

        self.working_memory.set_conclusions(
            reasoning["conclusions"]
        )

        primary_goal, all_goals = (
            choose_primary_goal(
                perception,
                reasoning,
            )
        )

        self.working_memory.set_goal(
            primary_goal
        )

        legal_moves = get_ai_legal_moves(
            game,
            ai_player,
        )

        plans = create_plans(
            legal_moves,
            primary_goal,
            perception,
        )

        best_move, evaluated_moves = (
            choose_best_plan(
                plans,
                game,
                ai_player,
                execute_move_for_simulation,
            )
        )

        selected_plan = next(
            (
                plan
                for plan in plans
                if plan["first_move"].get(
                    "type"
                )
                == best_move.get("type")
                and plan[
                    "first_move"
                ].get("card_name")
                == best_move.get(
                    "card_name"
                )
            ),
            None,
        )

        self.working_memory.set_plan(
            selected_plan
        )

        self.last_state_value = (
            self.reflection.current_state_value(
                game,
                ai_player,
            )
        )

        self.last_thought_process = {
            "perception": perception,
            "questions": reasoning[
                "questions"
            ],
            "predictions": reasoning[
                "predictions"
            ],
            "conclusions": reasoning[
                "conclusions"
            ],
            "primary_goal": primary_goal,
            "all_goals": all_goals,
            "selected_plan": selected_plan,
            "chosen_move": best_move,
            "top_moves": (
                evaluated_moves[:5]
            ),
        }

        best_move["brain_thoughts"] = (
            self.explain_thought_process()
        )

        return best_move, evaluated_moves

    def reflect_after_action(
        self,
        game,
        ai_player,
        executed_move: dict[str, Any],
    ) -> dict[str, Any]:
        after_value = (
            self.reflection.current_state_value(
                game,
                ai_player,
            )
        )

        result = (
            self.reflection.reflect_after_move(
                game=game,
                ai_player=ai_player,
                decision=executed_move,
                state_value_before=(
                    self.last_state_value
                ),
                state_value_after=after_value,
            )
        )

        self.working_memory.remember_event({
            "type": "reflection",
            **result,
        })

        return result

    def explain_thought_process(
        self,
    ) -> list[str]:

        data = self.last_thought_process

        thoughts = []

        # ========================================================
        # GOAL
        # ========================================================

        goal = data.get(
            "primary_goal",
            {},
        )

        if goal:
            reason = goal.get(
                "reason",
                "",
            )

            if reason:
                thoughts.append(
                    f"Goal: {reason}"
                )

        # ========================================================
        # CHOSEN MOVE
        # ========================================================

        chosen_move = data.get(
            "chosen_move",
            {},
        )

        if chosen_move:

            # Use the REAL reasons attached to
            # the selected move.
            move_reasons = chosen_move.get(
                "reasons",
                [],
            )

            # Keep only useful unique reasons.
            seen = set()

            for reason in move_reasons:

                reason = str(reason).strip()

                if not reason:
                    continue

                if reason in seen:
                    continue

                seen.add(reason)

                thoughts.append(reason)

                # Do not flood the GUI.
                if len(thoughts) >= 4:
                    break

        # ========================================================
        # IMPORTANT PREDICTION
        # ========================================================

        predictions = data.get(
            "predictions",
            [],
        )

        if predictions:

            prediction = predictions[0].get(
                "prediction",
                "",
            )

            if (
                prediction
                and prediction not in thoughts
            ):
                thoughts.append(
                    f"Prediction: {prediction}"
                )

        # ========================================================
        # FINAL DECISION
        # ========================================================

        if chosen_move:

            move_type = chosen_move.get(
                "type",
                "unknown",
            )

            card_name = chosen_move.get(
                "card_name",
            )

            score = chosen_move.get(
                "score",
            )

            if card_name:
                decision = (
                    f"Selected {move_type} "
                    f"on {card_name}"
                )
            else:
                decision = (
                    f"Selected {move_type}"
                )

            if score is not None:
                decision += (
                    f" with score {score}"
                )

            thoughts.append(
                decision
            )

        # ========================================================
        # REMOVE DUPLICATES
        # ========================================================

        final_thoughts = []
        seen = set()

        for thought in thoughts:

            key = thought.lower().strip()

            if key in seen:
                continue

            seen.add(key)

            final_thoughts.append(
                thought
            )

        return final_thoughts[:6]

    def get_debug_report(
        self,
    ) -> dict[str, Any]:
        return {
            "thought_process": (
                self.last_thought_process
            ),
            "working_memory": (
                self.working_memory.summary()
            ),
            "recent_reflections": (
                self.reflection
                .recent_reflections()
            ),
        }