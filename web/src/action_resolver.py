# src/action_resolver.py

from rules_engine import (
    play_card_from_hand,
    use_power,
    get_effective_placement_cost,
)
from game_memory import record_move, snapshot_game

ESSENCE_ORDER = ["elan", "life", "calm", "death", "gold"]


class ActionResolver:
    """
    One reusable GUI resolver for:
    - playing cards
    - using powers
    - discount choices
    - wild payment choices
    - X value
    - straighten target
    - additional tap target

    It does not draw anything.
    It only opens ActionPanel choices through GameScreen.
    """

    def __init__(self, screen_controller):
        self.screen = screen_controller
        self.game = screen_controller.game_state

        self.reset()

    def reset(self):
        self.mode = None

        self.player = None
        self.card = None
        self.power = None

        self.cost = {}
        self.discount_choices = []
        self.wild_choices = []

        self.x_value = None
        self.target_choices = {}
        self.additional_tap_target_id = None
        self.target_candidates = []
        self.gain_wild_choices = []
        self.store_wild_choices = []

    # -------------------------------------------------
    # START ACTIONS
    # -------------------------------------------------

    def start_play_card(self, player, card):
        self.reset()

        self.mode = "play_card"
        self.player = player
        self.card = card
        self.cost = get_effective_placement_cost(player, card) or {}

        self.continue_flow()

    def start_power(self, player, card, power):
        self.reset()

        self.mode = "use_power"
        self.player = player
        self.card = card
        self.power = power
        self.cost = power.get("cost", {}) or {}

        self.continue_flow()

    # -------------------------------------------------
    # FLOW
    # -------------------------------------------------

    def continue_flow(self):
        if self.needs_x_value():
            self.open_x_panel()
            return

        if self.needs_discount_choice():
            self.open_discount_panel()
            return

        if self.needs_wild_choice():
            self.open_wild_panel()
            return


        if self.needs_gain_wild_choice():
            self.open_gain_wild_panel()
            return
        
        if self.needs_store_wild_choice():
            self.open_store_wild_panel()
            return

        if self.needs_straighten_target():
            self.open_straighten_target_panel()
            return

        if self.needs_additional_tap_target():
            self.open_additional_tap_target_panel()
            return

        self.open_final_confirm_panel()

    def handle_action(self, action):

        if action.startswith("resolver_store_"):
            essence = action.replace("resolver_store_", "")
            self.store_wild_choices.append(essence)
            self.continue_flow()
            return True
        if action == "resolver_cancel":
            self.screen.close_all_popups()
            self.reset()
            return True

        if action.startswith("resolver_x_"):
            self.x_value = int(action.replace("resolver_x_", ""))
            self.continue_flow()
            return True

        if action.startswith("resolver_discount_"):
            essence = action.replace("resolver_discount_", "")
            self.discount_choices.append(essence)
            self.continue_flow()
            return True

        if action.startswith("resolver_wild_"):
            essence = action.replace("resolver_wild_", "")
            self.wild_choices.append(essence)
            self.continue_flow()
            return True

        if action.startswith("resolver_target_"):
            index = int(action.replace("resolver_target_", ""))

            if 0 <= index < len(self.target_candidates):
                target = self.target_candidates[index]
                self.target_choices["straighten_target"] = self.screen.get_card_id(target)

            self.continue_flow()
            return True

        if action.startswith("resolver_additional_tap_"):
            index = int(action.replace("resolver_additional_tap_", ""))

            if 0 <= index < len(self.target_candidates):
                target = self.target_candidates[index]
                self.additional_tap_target_id = self.screen.get_card_id(target)

            self.continue_flow()
            return True

        if action == "resolver_confirm":
            self.execute()
            return True
        
        if action.startswith("resolver_gain_"):
            essence = action.replace("resolver_gain_", "")
            self.gain_wild_choices.append(essence)
            self.continue_flow()
            return True

        return False

    # -------------------------------------------------
    # COST HELPERS
    # -------------------------------------------------

    def get_discount_amount(self):
        discount = self.cost.get("discount", {}) or {}
        return int(discount.get("amount", 0) or 0)

    def get_wild_count_and_allowed(self):
        wild = self.cost.get("wild")

        if not wild:
            return 0, []

        if isinstance(wild, int):
            return wild, ESSENCE_ORDER

        if isinstance(wild, dict):
            count = wild.get("count", 0)
            allowed = wild.get("allowed", ESSENCE_ORDER)

            if count == "X":
                if self.x_value is None:
                    return 0, allowed
                return self.x_value, allowed

            if count == "X_plus_2":
                if self.x_value is None:
                    return 0, allowed
                return self.x_value + 2, allowed

            if isinstance(count, int):
                return count, allowed

        return 0, []

    def get_adjusted_fixed_cost(self):
        essence_cost = self.cost.get("essence", {}) or {}

        adjusted = {
            essence: int(essence_cost.get(essence, 0))
            for essence in ESSENCE_ORDER
        }

        for essence in self.discount_choices:
            if essence != "wild" and adjusted.get(essence, 0) > 0:
                adjusted[essence] -= 1

        return adjusted

    def get_adjusted_wild_count(self):
        wild_count, allowed = self.get_wild_count_and_allowed()

        wild_discount = self.discount_choices.count("wild")
        wild_count = max(0, wild_count - wild_discount)

        return wild_count, allowed

    def needs_x_value(self):
        wild = self.cost.get("wild")

        if isinstance(wild, dict):
            if wild.get("count") in ["X", "X_plus_2"] and self.x_value is None:
                return True

        if self.power:
            for effect in self.power.get("effect", []):
                if "gain_wild" in effect:
                    count = effect["gain_wild"].get("count")
                    if count in ["X", "X_plus_2"] and self.x_value is None:
                        return True

        return False

    def needs_discount_choice(self):
        return len(self.discount_choices) < self.get_discount_amount()

    def needs_wild_choice(self):
        wild_count, allowed = self.get_adjusted_wild_count()
        return len(self.wild_choices) < wild_count

    def get_gain_wild_count_and_allowed(self):
        if not self.power:
            return 0, []

        for effect in self.power.get("effect", []):
            if "gain_wild" in effect:
                payload = effect["gain_wild"]
                count = payload.get("count", 0)
                allowed = payload.get("allowed", ESSENCE_ORDER)

                if count == "X":
                    return int(self.x_value or 0), allowed

                if count == "X_plus_2":
                    return int(self.x_value or 0) + 2, allowed

                if isinstance(count, int):
                    return count, allowed

        return 0, []


    def needs_gain_wild_choice(self):
        count, allowed = self.get_gain_wild_count_and_allowed()
        return len(self.gain_wild_choices) < count


    def open_gain_wild_panel(self):
        count, allowed = self.get_gain_wild_count_and_allowed()

        actions = []

        for essence in allowed:
            actions.append(
                (
                    f"resolver_gain_{essence}",
                    f"Gain {essence.title()}"
                )
            )

        actions.append(("resolver_cancel", "Cancel"))

        self.screen.action_panel.open(
            "Choose Essence To Gain",
            f"Choose essence {len(self.gain_wild_choices) + 1} of {count}.",
            actions,
        )

    def get_discount_candidates(self):
        essence_cost = self.cost.get("essence", {}) or {}

        remaining = {
            essence: int(essence_cost.get(essence, 0))
            for essence in ["elan", "life", "calm", "death"]
        }

        wild_count, allowed = self.get_wild_count_and_allowed()

        if wild_count > 0:
            remaining["wild"] = wild_count

        for essence in self.discount_choices:
            if essence in remaining:
                remaining[essence] -= 1

        return [
            essence for essence, amount in remaining.items()
            if amount > 0
        ]

    def get_wild_candidates(self):
        fixed_cost = self.get_adjusted_fixed_cost()
        remaining_pool = dict(self.player.essence_pool)

        for essence, amount in fixed_cost.items():
            remaining_pool[essence] = remaining_pool.get(essence, 0) - amount

        for essence in self.wild_choices:
            remaining_pool[essence] = remaining_pool.get(essence, 0) - 1

        wild_count, allowed = self.get_adjusted_wild_count()

        return [
            essence for essence in allowed
            if remaining_pool.get(essence, 0) > 0
        ]

    # -------------------------------------------------
    # TARGET HELPERS
    # -------------------------------------------------

    def get_controlled_cards(self):
        cards = []

        if self.player.mage:
            cards.append(self.player.mage)

        if self.player.item:
            cards.append(self.player.item)

        cards.extend(self.player.played)
        cards.extend(self.player.monuments)
        cards.extend(self.player.places)

        return cards

    def matches_restriction(self, card, restriction):
        if not restriction:
            return True

        card_type = (
            getattr(card.definition, "card_type", None)
            or card.definition.raw_data.get("type")
        )

        tags = card.definition.raw_data.get("tags", [])

        if "type" in restriction and card_type != restriction["type"]:
            return False

        if "has_tag" in restriction and restriction["has_tag"] not in tags:
            return False

        if "not_type" in restriction and card_type == restriction["not_type"]:
            return False

        return True

    def needs_straighten_target(self):
        if not self.power:
            return False

        if "straighten_target" in self.target_choices:
            return False

        for effect in self.power.get("effect", []):
            if "straighten_target" in effect:
                payload = effect["straighten_target"]

                if payload.get("target") == "self":
                    return False

                return True

        return False

    def needs_additional_tap_target(self):
        if self.additional_tap_target_id:
            return False

        return bool(self.cost.get("tap_additional_target"))

    def get_straighten_restriction(self):
        for effect in self.power.get("effect", []):
            if "straighten_target" in effect:
                return effect["straighten_target"].get("restriction")

        return None

    def get_additional_tap_restriction(self):
        payload = self.cost.get("tap_additional_target", {}) or {}
        return payload.get("restriction")

    # -------------------------------------------------
    # PANELS
    # -------------------------------------------------

    def open_x_panel(self):
        actions = [
            ("resolver_x_1", "X = 1"),
            ("resolver_x_2", "X = 2"),
            ("resolver_x_3", "X = 3"),
            ("resolver_x_4", "X = 4"),
            ("resolver_x_5", "X = 5"),
            ("resolver_cancel", "Cancel"),
        ]

        self.screen.action_panel.open(
            "Choose X",
            "Choose X value for this action.",
            actions,
        )

    def open_discount_panel(self):
        amount = self.get_discount_amount()
        candidates = self.get_discount_candidates()

        actions = []

        for essence in candidates:
            actions.append(
                (
                    f"resolver_discount_{essence}",
                    f"Discount {essence.title()}"
                )
            )

        actions.append(("resolver_cancel", "Cancel"))

        self.screen.action_panel.open(
            "Choose Discount",
            f"Choose discount {len(self.discount_choices) + 1} of {amount}.",
            actions,
        )

    def open_wild_panel(self):
        wild_count, allowed = self.get_adjusted_wild_count()
        candidates = self.get_wild_candidates()

        actions = []

        for essence in candidates:
            actions.append(
                (
                    f"resolver_wild_{essence}",
                    f"Pay {essence.title()}"
                )
            )

        actions.append(("resolver_cancel", "Cancel"))

        self.screen.action_panel.open(
            "Choose Wild Payment",
            f"Choose payment {len(self.wild_choices) + 1} of {wild_count}.",
            actions,
        )

    def open_straighten_target_panel(self):
        restriction = self.get_straighten_restriction()

        self.target_candidates = [
            card for card in self.get_controlled_cards()
            if card.tapped
            and card is not self.card
            and self.matches_restriction(card, restriction)
        ]

        if not self.target_candidates:
            self.game.game_log.append("No valid tapped target to straighten.")
            self.screen.close_all_popups()
            self.reset()
            return

        actions = []

        for index, card in enumerate(self.target_candidates):
            actions.append(
                (
                    f"resolver_target_{index}",
                    self.screen.card_name(card)
                )
            )

        actions.append(("resolver_cancel", "Cancel"))

        self.screen.action_panel.open(
            "Choose Target",
            "Choose a tapped card to straighten.",
            actions,
        )

    def open_additional_tap_target_panel(self):
        restriction = self.get_additional_tap_restriction()

        self.target_candidates = [
            card for card in self.get_controlled_cards()
            if not card.tapped
            and card is not self.card
            and self.matches_restriction(card, restriction)
        ]

        if not self.target_candidates:
            self.game.game_log.append("No valid card available to tap.")
            self.screen.close_all_popups()
            self.reset()
            return

        actions = []

        for index, card in enumerate(self.target_candidates):
            actions.append(
                (
                    f"resolver_additional_tap_{index}",
                    self.screen.card_name(card)
                )
            )

        actions.append(("resolver_cancel", "Cancel"))

        self.screen.action_panel.open(
            "Choose Card To Tap",
            "Choose another card to tap as part of the cost.",
            actions,
        )

    def open_final_confirm_panel(self):
        if self.mode == "play_card":
            title = "Confirm Play"
            message = f"Play {self.screen.card_name(self.card)}?"

        elif self.mode == "use_power":
            title = "Confirm Power"
            message = f"Use power on {self.screen.card_name(self.card)}?"

        else:
            title = "Confirm"
            message = "Confirm action?"

        self.screen.action_panel.open(
            title,
            message,
            [
                ("resolver_confirm", "Confirm"),
                ("resolver_cancel", "Cancel"),
            ],
        )

    # -------------------------------------------------
    # EXECUTE
    # -------------------------------------------------

    def execute(self):
        try:
            state_before = snapshot_game(self.game)
            if self.mode == "play_card":
                play_card_from_hand(
                    self.game,
                    self.player,
                    self.screen.get_card_id(self.card),
                    wild_choices=self.wild_choices,
                    discount_choices=self.discount_choices,
                )

                self.game.gui_human_action_done = True
                self.game.game_log.append(
                    f"{self.player.name} played {self.screen.card_name(self.card)}."
                )
                record_move(
                    game_record=self.game.game_record,
                    game=self.game,
                    state_before=state_before,
                    player_name=self.player.name,
                    move_type="play_card",
                    description=(
                        f"{self.player.name} played "
                        f"{self.screen.card_name(self.card)}."
                    ),
                    card_name=self.screen.card_name(self.card),
                    reward_choices=list(self.wild_choices),
                    reasons=[
                        f"Discount choices: {self.discount_choices}",
                        f"Wild payment choices: {self.wild_choices}",
                    ],
                )

            elif self.mode == "use_power":
                use_power(
                    self.game,
                    self.player,
                    source_card_id=self.screen.get_card_id(self.card),
                    power_index=self.power.get("power_index"),
                    wild_choices=self.wild_choices,
                    target_choices=self.target_choices,
                    x_value=self.x_value,
                    additional_tap_target_id=self.additional_tap_target_id,
                    gain_wild_choices=self.gain_wild_choices,
                    store_wild_choices=self.store_wild_choices,

                )

                self.game.gui_human_action_done = True
                self.game.game_log.append(
                    f"{self.player.name} used power on {self.screen.card_name(self.card)}."
                )
                target_card = self.target_choices.get("straighten_target")

                record_move(
                    game_record=self.game.game_record,
                    game=self.game,
                    state_before=state_before,
                    player_name=self.player.name,
                    move_type="use_power",
                    description=(
                        f"{self.player.name} used power "
                        f"{self.power.get('power_index')} on "
                        f"{self.screen.card_name(self.card)}."
                    ),
                    card_name=self.screen.card_name(self.card),
                    reward_choices=list(self.gain_wild_choices),
                    x_value=self.x_value,
                    target_card=target_card,
                    reasons=[
                        f"Wild payment choices: {self.wild_choices}",
                        f"Gain choices: {self.gain_wild_choices}",
                        f"Store choices: {self.store_wild_choices}",
                        f"Additional tap target: {self.additional_tap_target_id}",
                    ],
                )

        except Exception as e:
            self.game.game_log.append(f"Action failed: {e}")

        self.screen.close_all_popups()
        self.reset()

    def get_store_wild_count_and_allowed(self):
        if not self.power:
            return 0, []

        for effect in self.power.get("effect", []):
            if "store_wild_on_card" in effect:
                payload = effect["store_wild_on_card"]
                count = int(payload.get("count", 1))
                allowed = payload.get("allowed", ["elan", "calm", "death"])
                return count, allowed

        return 0, []


    def needs_store_wild_choice(self):
        count, allowed = self.get_store_wild_count_and_allowed()
        return len(self.store_wild_choices) < count


    def open_store_wild_panel(self):
        count, allowed = self.get_store_wild_count_and_allowed()

        actions = []

        for essence in allowed:
            actions.append(
                (
                    f"resolver_store_{essence}",
                    f"Store {essence.title()}"
                )
            )

        actions.append(("resolver_cancel", "Cancel"))

        self.screen.action_panel.open(
            "Choose Essence To Store",
            f"Choose essence {len(self.store_wild_choices) + 1} of {count}.",
            actions,
        )