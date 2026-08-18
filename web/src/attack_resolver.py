# src/attack_resolver.py

ESSENCE_ORDER = ["elan", "life", "calm", "death", "gold"]
NON_LIFE_ESSENCE = ["elan", "calm", "death", "gold"]


class AttackResolver:
    def __init__(self, screen_controller):
        self.screen = screen_controller
        self.game = screen_controller.game_state
        self.reset()

    def reset(self):
        self.active = False
        self.attacker = None
        self.defender = None
        self.amount = 0
        self.source_card = None
        self.reaction_cards = []
        self.dragon_ignore_cost = None
        self.missing_life = 0
        self.extra_payment_choices = []

    def start_attack(
        self,
        attacker,
        defender,
        amount,
        source_card=None,
        dragon_ignore_cost=None,
    ):
        self.reset()

        self.active = True
        self.attacker = attacker
        self.defender = defender
        self.amount = int(amount)
        self.source_card = source_card
        self.dragon_ignore_cost = dragon_ignore_cost

        self.reaction_cards = self.find_life_loss_reactions(
            defender
        )

        self.continue_flow()

    def continue_flow(self):
        if self.reaction_cards:
            self.open_reaction_panel()
            return

        if (
            self.dragon_ignore_cost
            and self.can_pay_cost(
                self.defender,
                self.dragon_ignore_cost,
            )
        ):
            self.open_dragon_ignore_panel()
            return

        life_available = int(
            self.defender.essence_pool.get(
                "life",
                0,
            )
        )

        if life_available >= self.amount:
            self.open_pay_life_panel()
            return

        self.missing_life = (
            self.amount - life_available
        )

        if self.missing_life > 0:
            required_other_loss = (
                self.missing_life * 2
            )

            available_other_loss = sum(
                int(
                    self.defender.essence_pool.get(
                        essence,
                        0,
                    )
                )
                for essence in NON_LIFE_ESSENCE
            )

            actual_other_loss = min(
                required_other_loss,
                available_other_loss,
            )

            if (
                len(
                    self.extra_payment_choices
                )
                < actual_other_loss
            ):
                self.open_extra_payment_panel(
                    actual_other_loss
                )
                return

        self.resolve_life_loss()

    def find_life_loss_reactions(
        self,
        player,
    ):
        cards = []
        controlled = []

        if player.mage:
            controlled.append(
                player.mage
            )

        if player.item:
            controlled.append(
                player.item
            )

        controlled.extend(
            player.played
        )
        controlled.extend(
            player.monuments
        )
        controlled.extend(
            player.places
        )

        for card in controlled:
            if getattr(
                card,
                "tapped",
                False,
            ):
                continue

            react_powers = (
                card.definition.raw_data.get(
                    "react_powers",
                    [],
                )
            )

            for react in react_powers:
                for effect in react.get(
                    "effect",
                    [],
                ):
                    if (
                        "ignore_attack" in effect
                        or "ignore_life_loss"
                        in effect
                    ):
                        cards.append(
                            card
                        )
                        break

        return cards

    def can_pay_cost(
        self,
        player,
        cost,
    ):
        essence_cost = (
            cost.get(
                "essence",
                {},
            )
        )

        for essence, amount in essence_cost.items():
            if (
                player.essence_pool.get(
                    essence,
                    0,
                )
                < int(amount)
            ):
                return False

        return True

    def pay_cost(
        self,
        player,
        cost,
    ):
        essence_cost = (
            cost.get(
                "essence",
                {},
            )
        )

        for essence, amount in essence_cost.items():
            player.essence_pool[
                essence
            ] -= int(amount)

    def open_reaction_panel(self):
        actions = []

        for index, card in enumerate(
            self.reaction_cards
        ):
            name = self.screen.card_name(
                card
            )

            actions.append(
                (
                    f"attack_react_{index}",
                    f"Use {name}",
                )
            )

        actions.append(
            (
                "attack_no_reaction",
                "Do Not React",
            )
        )

        self.screen.action_panel.open(
            "Reaction Available",
            "You may use a reaction to ignore this life loss.",
            actions,
        )

    def open_dragon_ignore_panel(self):
        text = self.cost_text(
            self.dragon_ignore_cost
        )

        self.screen.action_panel.open(
            "Dragon Attack",
            f"You may pay {text} to ignore this attack.",
            [
                (
                    "attack_pay_dragon_ignore",
                    f"Pay {text}",
                ),
                (
                    "attack_no_dragon_ignore",
                    "Do Not Pay",
                ),
            ],
        )

    def open_pay_life_panel(self):
        self.screen.action_panel.open(
            "Life Loss",
            f"Pay {self.amount} life to satisfy the attack.",
            [
                (
                    "attack_pay_life",
                    f"Pay {self.amount} Life",
                ),
            ],
        )

    def open_extra_payment_panel(
        self,
        actual_other_loss,
    ):
        current = (
            len(
                self.extra_payment_choices
            )
            + 1
        )

        actions = []

        remaining_pool = dict(
            self.defender.essence_pool
        )

        life_to_pay = min(
            self.amount,
            int(
                self.defender.essence_pool.get(
                    "life",
                    0,
                )
            ),
        )

        remaining_pool["life"] = max(
            0,
            int(
                remaining_pool.get(
                    "life",
                    0,
                )
            )
            - life_to_pay,
        )

        for chosen in (
            self.extra_payment_choices
        ):
            remaining_pool[chosen] = max(
                0,
                int(
                    remaining_pool.get(
                        chosen,
                        0,
                    )
                )
                - 1,
            )

        for essence in NON_LIFE_ESSENCE:
            if (
                remaining_pool.get(
                    essence,
                    0,
                )
                > 0
            ):
                actions.append(
                    (
                        f"attack_pay_extra_{essence}",
                        essence.title(),
                    )
                )

        if not actions:
            self.resolve_life_loss()
            return

        self.screen.action_panel.open(
            "Choose Essence Loss",
            f"Choose essence {current} of {actual_other_loss}.",
            actions,
        )

    def handle_action(
        self,
        action,
    ):
        if action.startswith(
            "attack_react_"
        ):
            index = int(
                action.replace(
                    "attack_react_",
                    "",
                )
            )

            if (
                0
                <= index
                < len(
                    self.reaction_cards
                )
            ):
                card = (
                    self.reaction_cards[
                        index
                    ]
                )

                card.tapped = True

                self.game.game_log.append(
                    f"{self.defender.name} used "
                    f"{self.screen.card_name(card)} "
                    "to ignore attack."
                )

            self.finish()
            return True

        if (
            action
            == "attack_no_reaction"
        ):
            self.reaction_cards = []
            self.continue_flow()
            return True

        if (
            action
            == "attack_pay_dragon_ignore"
        ):
            self.pay_cost(
                self.defender,
                self.dragon_ignore_cost,
            )

            self.game.game_log.append(
                f"{self.defender.name} paid dragon ignore cost "
                "and ignored the attack."
            )

            self.finish()
            return True

        if (
            action
            == "attack_no_dragon_ignore"
        ):
            self.dragon_ignore_cost = None
            self.continue_flow()
            return True

        if (
            action
            == "attack_pay_life"
        ):
            self.defender.essence_pool[
                "life"
            ] -= self.amount

            self.game.game_log.append(
                f"{self.defender.name} paid "
                f"{self.amount} life."
            )

            self.finish()
            return True

        if action.startswith(
            "attack_pay_extra_"
        ):
            essence = action.replace(
                "attack_pay_extra_",
                "",
            )

            already_selected = (
                self.extra_payment_choices.count(
                    essence
                )
            )

            if (
                self.defender.essence_pool.get(
                    essence,
                    0,
                )
                > already_selected
            ):
                self.extra_payment_choices.append(
                    essence
                )

            self.continue_flow()
            return True

        return False

    def resolve_life_loss(self):
        life_to_pay = min(
            self.amount,
            int(
                self.defender.essence_pool.get(
                    "life",
                    0,
                )
            ),
        )

        if life_to_pay > 0:
            self.defender.essence_pool[
                "life"
            ] -= life_to_pay

        for essence in (
            self.extra_payment_choices
        ):
            if (
                self.defender.essence_pool.get(
                    essence,
                    0,
                )
                > 0
            ):
                self.defender.essence_pool[
                    essence
                ] -= 1

        required_other_loss = (
            max(
                0,
                self.amount - life_to_pay,
            )
            * 2
        )

        actual_other_loss = len(
            self.extra_payment_choices
        )

        if (
            actual_other_loss
            < required_other_loss
        ):
            self.game.game_log.append(
                f"{self.defender.name} had no more essence to lose. "
                "Remaining loss was ignored."
            )

        self.game.game_log.append(
            f"{self.defender.name} resolved "
            f"{self.amount} life loss."
        )

        self.finish()

    def finish(self):
        self.game.current_phase = (
            "action"
        )

        self.screen.action_panel.close()
        self.reset()

    def cost_text(
        self,
        cost,
    ):
        parts = []

        for essence, amount in (
            cost.get(
                "essence",
                {},
            ).items()
        ):
            if amount:
                parts.append(
                    f"{amount} {essence}"
                )

        return ", ".join(parts)