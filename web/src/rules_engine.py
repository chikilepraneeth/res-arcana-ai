

from effect_engine import (
    pay_cost,
    can_pay_cost,
    apply_effects,
    run_collect_effects,
    tap_additional_target_if_needed,
    draw_cards,
)

from models import ESSENCE_KEYS, CardInstance


class RulesError(Exception):
    pass


NON_GOLD_ESSENCE = ["elan", "life", "calm", "death"]


def log(game, message):
    game.game_log.append(message)


def card_name(card):
    if not card:
        return None

    return (
        getattr(card.definition, "name", None)
        or card.definition.raw_data.get("name_en")
        or card.definition.raw_data.get("id")
    )


def card_id(card):
    return (
        getattr(card.definition, "card_id", None)
        or card.definition.raw_data.get("id")
    )


def get_all_controlled_cards(player):
    cards = []

    if player.mage:
        cards.append(player.mage)

    if player.item:
        cards.append(player.item)

    cards.extend(player.played)
    cards.extend(player.monuments)
    cards.extend(player.places)

    return cards


def find_card_in_list(cards, target_card_id):
    for index, card in enumerate(cards):
        if card_id(card) == target_card_id:
            return index, card

    return None, None


def can_pay_placement_cost(player, placement_cost):
    """
    Check whether a player can REALLY pay a placement cost.

    This uses the same discount logic that pay_cost() expects,
    so the AI does not consider cards playable and then fail
    during execution.
    """

    if not placement_cost:
        return True

    from effect_engine import choose_discount_for_ai

    discount_choices = None

    if placement_cost.get("discount"):
        discount_choices = choose_discount_for_ai(
            player,
            placement_cost
        )

        if discount_choices is None:
            return False

    # Build the actual cost after discount.
    import copy

    cost = copy.deepcopy(placement_cost)

    essence_cost = cost.get("essence", {})

    if discount_choices:
        for essence in discount_choices:
            if essence == "wild":
                continue

            if essence in essence_cost:
                essence_cost[essence] = max(
                    0,
                    int(essence_cost.get(essence, 0)) - 1
                )

    # Check fixed essence first.
    if not can_pay_cost(player, {
        "essence": essence_cost,
        "wild": cost.get("wild")
    }):
        return False

    return True


def can_play_card_from_hand(player, card):
    placement_cost = get_effective_placement_cost(player, card)
    return can_pay_placement_cost(player, placement_cost)

def get_card_tags(card):
    return card.definition.raw_data.get("tags", [])


def get_discount_from_passives(player, card):
    total_discount = 0

    card_type_value = (
        getattr(card.definition, "card_type", None)
        or card.definition.raw_data.get("type")
    )

    card_tags_value = card.definition.raw_data.get("tags", [])

    for controlled in get_all_controlled_cards(player):
        raw = controlled.definition.raw_data

        passives = raw.get("passives", [])

        for passive in passives:
            effect = passive.get("effect", passive)

            modifier = (
                effect.get("placement_cost_modifier")
                or effect.get("cost_modifier")
                or effect.get("discount")
            )

            if not modifier:
                continue

            target = modifier.get("target", {})
            discount = int(
                modifier.get("discount", modifier.get("amount", 0))
            )

            valid = False

            if target.get("type") == card_type_value:
                valid = True

            if target.get("has_tag") in card_tags_value:
                valid = True

            if target.get("card_type") == card_type_value:
                valid = True

            if target.get("type") == "artifact" and card_type_value in ["artifact", "creature", "dragon"]:
                valid = True

            if valid:
                total_discount += discount

    return total_discount


def apply_discount_to_cost(cost, discount):
    if not cost or discount <= 0:
        return cost

    import copy
    new_cost = copy.deepcopy(cost)

    essence = new_cost.get("essence", {})

    # Artificer/discount cannot reduce gold.
    allowed_discount_essence = [
        essence_type
        for essence_type in ["elan", "life", "calm", "death"]
        if int(essence.get(essence_type, 0)) > 0
    ]

    wild = new_cost.get("wild")

    if isinstance(wild, int) and wild > 0:
        allowed_discount_essence.append("wild")

    elif isinstance(wild, dict):
        count = wild.get("count", 0)
        if isinstance(count, int) and count > 0:
            allowed_discount_essence.append("wild")

    if not allowed_discount_essence:
        return new_cost

    new_cost["discount"] = {
        "amount": discount,
        "allowed": allowed_discount_essence,
        "cannot_reduce": ["gold"]
    }

    return new_cost

def get_effective_placement_cost(player, card):
    original_cost = card.definition.raw_data.get("placement_cost")

    discount = get_discount_from_passives(player, card)

    return apply_discount_to_cost(original_cost, discount)

def play_card_from_hand(game, player, target_card_id, wild_choices=None, discount_choices=None):
    index, card = find_card_in_list(player.hand, target_card_id)

    if not card:
        raise RulesError(f"{player.name} does not have card in hand: {target_card_id}")

    if not can_play_card_from_hand(player, card):
        raise RulesError(f"{player.name} cannot afford to play {card_name(card)}")

    placement_cost = get_effective_placement_cost(player, card)
    if (
        placement_cost
        and placement_cost.get("discount")
        and discount_choices is None
    ):
        from effect_engine import choose_discount_for_ai

        discount_choices = choose_discount_for_ai(
            player,
            placement_cost
        )

    if placement_cost:
        paid = pay_cost(
    player,
    placement_cost,
    wild_choices=wild_choices,
    discount_choices=discount_choices
)

        if not paid:
            raise RulesError(f"{player.name} failed to pay cost for {card_name(card)}")

    player.hand.pop(index)
    player.played.append(card)

    log(game, f"{player.name} played {card_name(card)}.")

    collect_list = card.definition.raw_data.get("collect", [])

    for entry in collect_list:
        if entry.get("timing") == "on_place":
            effects = entry.get("effect", [])
            apply_effects(game, player, card, effects)

    return card



def resolve_variable_cost(cost, x_value=None):
    import copy

    new_cost = copy.deepcopy(cost)

    wild = new_cost.get("wild")

    if isinstance(wild, dict):
        count = wild.get("count")

        if count == "X":
            new_cost["wild"]["count"] = int(x_value or 0)

        elif count == "X_plus_2":
            new_cost["wild"]["count"] = int(x_value or 0) + 2

    return new_cost

def can_use_power(
    game,
    player,
    source_card,
    power,
    x_value=None,
):
    """
    Full legality check for an activated power.

    The AI should call this BEFORE putting a power
    into its legal move list.
    """

    if not source_card or not power:
        return False

    cost = power.get("cost", {}) or {}

    cost = resolve_variable_cost(
        cost,
        x_value
    )

    # --------------------------------
    # 1. Source card tap requirement
    # --------------------------------

    requires_turn = bool(
        cost.get("turn_self", False)
        or cost.get("tap_self", False)
    )

    if requires_turn and source_card.tapped:
        return False

    # --------------------------------
    # 2. Normal essence/wild cost
    # --------------------------------

    if not can_pay_cost(player, cost):
        return False

    # --------------------------------
    # 3. Discard-card cost
    # --------------------------------

    discard_cards = int(
        cost.get("discard_cards", 0) or 0
    )

    if len(player.hand) < discard_cards:
        return False

    # --------------------------------
    # 4. Additional tap target
    # --------------------------------

    tap_payload = cost.get(
        "tap_additional_target"
    )

    if tap_payload:
        restriction = tap_payload.get(
            "restriction"
        )

        valid_target = False

        for card in get_all_controlled_cards(player):

            if card is source_card:
                continue

            if card.tapped:
                continue

            from effect_engine import matches_restriction

            if not matches_restriction(
                card,
                restriction
            ):
                continue

            valid_target = True
            break

        if not valid_target:
            return False

    # --------------------------------
    # 5. Effect prerequisites
    # --------------------------------

    effects = power.get("effect", [])

    for effect in effects:

        if not isinstance(effect, dict):
            continue

        # Example: Dragon Egg
        if "play_card_from_hand" in effect:

            payload = effect[
                "play_card_from_hand"
            ]

            restriction = payload.get(
                "restriction"
            )

            from effect_engine import matches_restriction

            candidates = [
                card
                for card in player.hand
                if matches_restriction(
                    card,
                    restriction
                )
            ]

            if not candidates:
                return False

        # Athanor / Philosopher's Stone
        if "convert_one_essence_type_to_gold" in effect:

            payload = effect[
                "convert_one_essence_type_to_gold"
            ]

            stored_cost = payload.get(
                "stored_cost",
                {}
            )

            for essence, amount in stored_cost.items():

                if (
                    source_card.stored_essence.get(
                        essence,
                        0
                    )
                    < int(amount)
                ):
                    return False

    return True
def use_power(
    game,
    player,
    source_card_id,
    power_index,
    wild_choices=None,
    target_choices=None,
    x_value=None,
    additional_tap_target_id=None,
    gain_wild_choices=None,
    store_wild_choices=None
):
    controlled_cards = get_all_controlled_cards(player)

    source_card = None

    for card in controlled_cards:
        if card_id(card) == source_card_id:
            source_card = card
            break

    if not source_card:
        raise RulesError(f"{player.name} does not control card: {source_card_id}")

    powers = source_card.definition.raw_data.get("powers", [])

    selected_power = None

    for power in powers:
        if int(power.get("power_index", -1)) == int(power_index):
            selected_power = power
            break

    if not selected_power:
        raise RulesError(f"Power {power_index} not found on {card_name(source_card)}")

    cost = selected_power.get("cost", {})
    cost = resolve_variable_cost(cost, x_value)
    requires_turn = bool(
            cost.get("turn_self", False)
            or cost.get("tap_self", False)
        )

    if requires_turn and source_card.tapped:
        raise RulesError(f"{card_name(source_card)} is already tapped.")

    old_x_value = getattr(game, "current_x_value", None)

    if x_value is not None:
        game.current_x_value = x_value
    if not can_pay_cost(player, cost, wild_choices=wild_choices):
        raise RulesError(f"{player.name} cannot pay cost for {card_name(source_card)} power.")

    if not tap_additional_target_if_needed(
    game,
    player,
    source_card,
    cost,
    target_card_id=additional_tap_target_id
):
        raise RulesError(f"{player.name} cannot satisfy additional tap target for {card_name(source_card)}.")

    paid = pay_cost(player, cost, wild_choices=wild_choices)

    if not paid:
        raise RulesError(f"{player.name} failed to pay cost for {card_name(source_card)} power.")

    discard_cards = int(cost.get("discard_cards", 0) or 0)

    for _ in range(discard_cards):
        if not player.hand:
            raise RulesError(f"{player.name} does not have enough cards to discard.")

        discarded = player.hand.pop(0)
        player.discard.append(discarded)
        log(game, f"{player.name} discarded {card_name(discarded)} as power cost.")

    if requires_turn:
        source_card.tapped = True
        log(game, f"{card_name(source_card)} was tapped.")
    if cost.get("destroy_self"):
        removed = False

        for zone in [
            player.played,
            player.monuments,
            player.places,
        ]:
            if source_card in zone:
                zone.remove(source_card)
                removed = True
                break

        if player.mage is source_card:
            player.mage = None
            removed = True

        if player.item is source_card:
            player.item = None
            removed = True

        if removed:
            player.discard.append(source_card)

            log(
                game,
                f"{player.name} destroyed "
                f"{card_name(source_card)} "
                "as part of the power cost."
            )
    effects = selected_power.get("effect", [])
    apply_effects(
        game,
        player,
        source_card,
        effects,
        target_choices=target_choices,
        gain_wild_choices=gain_wild_choices,
        store_wild_choices=store_wild_choices,
    )

    log(game, f"{player.name} used power {power_index} of {card_name(source_card)}.")

    if x_value is not None:
        game.current_x_value = old_x_value
    return True


def draw_one_card_on_pass(game, player):
    draw_cards(game, player, 1)


def choose_item_for_player(game, player, item_index, old_item=None):
    if item_index < 0 or item_index >= len(game.items_pool):
        raise RulesError("Invalid item choice.")

    new_item = game.items_pool.pop(item_index)
    player.item = new_item

    if old_item:
        game.items_pool.append(old_item)

    log(game, f"{player.name} chose item: {card_name(new_item)}.")

    return new_item


def pass_turn(game, player):
    if player.passed:
        return

    player.passed = True
    log(game, f"{player.name} passed.")

    draw_one_card_on_pass(game, player)

    if game.first_player_token_available:
        for p in game.players:
            p.has_first_player_token = False

        player.has_first_player_token = True
        game.first_player_token_available = False

        log(
            game,
            f"{player.name} took the first player token worth {game.first_player_token_vp} VP."
        )


def run_collect_phase(game):
    log(game, f"=== COLLECT PHASE: ROUND {game.round_no} ===")

    for player in game.players:
        run_collect_effects(game, player)

    log(game, "Collect phase completed.")


def reset_round_state(game):
    for player in game.players:
        player.passed = False

        # Golden Statue reaction only lasts for
        # one victory check.
        player.victory_check_bonus = 0
        player.golden_statue_used_this_check = False

        for card in get_all_controlled_cards(player):
            card.tapped = False

    game.first_player_token_available = True
    game.force_victory_check = False

    for index, player in enumerate(game.players):
        if player.has_first_player_token:
            game.current_player_index = index
            break

    log(game, "Round state reset: all players unpassed and cards straightened.")


def next_round(game):
    game.round_no += 1
    reset_round_state(game)
    run_collect_phase(game)


def compute_card_vp(card):
    raw = card.definition.raw_data
    vp = raw.get("vp", {})

    total = int(vp.get("base", 0))
    conditional = vp.get("conditional", [])

    for condition in conditional:
        if "per_stored_essence" in condition:
            data = condition["per_stored_essence"]

            essence = data.get("essence_type") or data.get("essence")
            vp_per = int(data.get("vp_per", data.get("mult", 1)))

            if essence:
                total += card.stored_essence.get(essence, 0) * vp_per

        elif "per_stored_total" in condition:
            data = condition["per_stored_total"]
            mult = int(data.get("mult", 1))
            total += sum(card.stored_essence.values()) * mult

        elif "per_stored_types" in condition:
            data = condition["per_stored_types"]
            mult = int(data.get("mult", 1))
            stored_types = sum(
                1 for value in card.stored_essence.values()
                if value > 0
            )
            total += stored_types * mult

    return total


def compute_player_vp(player, game=None):
    total = 0

    # Artifact / creature / dragon VP
    for card in player.played:
        total += compute_card_vp(card)

    # Monument VP
    # Golden Statue's normal 1 VP is already
    # counted here from its card data.
    for card in player.monuments:
        total += compute_card_vp(card)

    # Places of Power VP
    for card in player.places:
        total += compute_card_vp(card)

    # First Player Token VP
    if game and player.has_first_player_token:
        total += game.first_player_token_vp

    # Victory-check-only reaction bonus.
    # Golden Statue adds +3 here after the player
    # spends 3 gold during the victory check.
    victory_check_bonus = int(
        getattr(
            player,
            "victory_check_bonus",
            0,
        )
    )

    total += victory_check_bonus

    return total

def refresh_victory_points(game):
    scores = {}

    for player in game.players:
        score = compute_player_vp(
            player,
            game,
        )

        player.victory_points = score
        scores[player.name] = score

    return scores
def check_victory(game):
    """
    Victory points are refreshed continuously by main.py.

    This function is still the ONLY place that declares a winner.
    """
    scores = refresh_victory_points(game)

    for name, score in scores.items():
        log(
            game,
            f"{name} VP = {score}"
        )

    winners = [
        player
        for player in game.players
        if player.victory_points >= 10
    ]

    if winners:
        winner = max(
            winners,
            key=lambda player:
                player.victory_points,
        )

        game.game_over = True
        game.winner = winner.name

        log(
            game,
            f"GAME OVER. Winner: {winner.name}"
        )

    return scores

def reveal_human_card(game, player, target_card_id, cards_by_id):
    index, card = find_card_in_list(player.hand, target_card_id)

    if card:
        played_card = player.hand.pop(index)
        player.played.append(played_card)

        log(game, f"{player.name} revealed/played {card_name(played_card)} from known hand.")

        return played_card

    if target_card_id not in cards_by_id:
        raise RulesError(f"Unknown card id: {target_card_id}")

    template_card = cards_by_id[target_card_id]
    played_card = CardInstance(definition=template_card.definition)

    player.played.append(played_card)

    log(game, f"{player.name} revealed/played {card_name(played_card)} and AI registered it.")

    return played_card


def reveal_human_mage(game, player, mage_card_id, cards_by_id):
    if mage_card_id not in cards_by_id:
        raise RulesError(f"Unknown mage id: {mage_card_id}")

    template_card = cards_by_id[mage_card_id]
    player.mage = CardInstance(definition=template_card.definition)

    log(game, f"{player.name} chose mage: {card_name(player.mage)}")

    return player.mage


def reveal_human_item(game, player, item_card_id, cards_by_id):
    if item_card_id not in cards_by_id:
        raise RulesError(f"Unknown item id: {item_card_id}")

    template_card = cards_by_id[item_card_id]
    player.item = CardInstance(definition=template_card.definition)

    log(game, f"{player.name} took item: {card_name(player.item)}")

    return player.item


def discard_card_for_resources(game, player, target_card_id, reward_type, choices=None):
    index, card = find_card_in_list(player.hand, target_card_id)

    if not card:
        raise RulesError(f"{player.name} does not have card in hand: {target_card_id}")

    discarded_card = player.hand.pop(index)
    player.discard.append(discarded_card)

    if reward_type == "gold":
        player.essence_pool["gold"] += 1
        log(game, f"{player.name} discarded {card_name(discarded_card)} for 1 gold.")

    elif reward_type == "essence":
        if not choices or len(choices) != 2:
            raise RulesError("You must choose exactly 2 non-gold essences.")

        for essence in choices:
            if essence not in NON_GOLD_ESSENCE:
                raise RulesError("Discard essence reward cannot include gold.")

            player.essence_pool[essence] += 1

        log(
            game,
            f"{player.name} discarded {card_name(discarded_card)} for 2 essences: {choices}."
        )

    else:
        raise RulesError("reward_type must be 'gold' or 'essence'.")

    return discarded_card


def can_afford_claim_cost(player, card):
    claim_cost = card.definition.raw_data.get("claim_cost")

    if not claim_cost:
        return True

    return can_pay_cost(player, claim_cost)


def refill_monument_market(game):
    while len(game.market_monuments) < 2 and game.monument_deck:
        game.market_monuments.append(game.monument_deck.pop(0))


def buy_monument(game, player, market_index):
    if market_index < 0 or market_index >= len(game.market_monuments):
        raise RulesError("Invalid monument choice.")

    monument = game.market_monuments[market_index]

    if player.essence_pool.get("gold", 0) < 4:
        raise RulesError(f"{player.name} needs 4 gold to claim {card_name(monument)}.")

    player.essence_pool["gold"] -= 4

    bought = game.market_monuments.pop(market_index)
    player.monuments.append(bought)

    log(game, f"{player.name} claimed monument: {card_name(bought)} for 4 gold.")

    collect_list = bought.definition.raw_data.get("collect", [])

    for entry in collect_list:
        if entry.get("timing") == "on_place":
            effects = entry.get("effect", [])
            apply_effects(game, player, bought, effects)

    refill_monument_market(game)

    return bought


def buy_place_of_power(game, player, market_index):
    if market_index < 0 or market_index >= len(game.market_places):
        raise RulesError("Invalid Place of Power choice.")

    place = game.market_places[market_index]

    if not can_afford_claim_cost(player, place):
        raise RulesError(f"{player.name} cannot afford {card_name(place)}.")

    claim_cost = place.definition.raw_data.get("claim_cost")

    if claim_cost:
        paid = pay_cost(player, claim_cost)

        if not paid:
            raise RulesError(f"{player.name} failed to pay for {card_name(place)}.")

    bought = game.market_places.pop(market_index)
    player.places.append(bought)

    log(game, f"{player.name} bought Place of Power: {card_name(bought)}.")

    return bought


def show_market(game):
    print("\n========== MONUMENT MARKET ==========")

    if not game.market_monuments:
        print("No monuments available.")
    else:
        for i, card in enumerate(game.market_monuments, start=1):
            vp = card.definition.raw_data.get("vp", {}).get("base", 0)
            print(f"{i}. {card_name(card)} | VP: {vp} | Cost: 4 gold")

    print("\n========== PLACES OF POWER ==========")

    if not game.market_places:
        print("No Places of Power available.")
    else:
        for i, card in enumerate(game.market_places, start=1):
            claim_cost = card.definition.raw_data.get("claim_cost")
            vp = card.definition.raw_data.get("vp", {}).get("base", 0)
            side = card.definition.raw_data.get("side", "unknown")

            print(
                f"{i}. {card_name(card)} | Side: {side} | VP: {vp} | Cost: {claim_cost}"
            )


def show_player_state(player):
    print(f"\nPLAYER: {player.name}")
    print("Essence:", player.essence_pool)
    print("Mage:", card_name(player.mage) if player.mage else None)
    print("Item:", card_name(player.item) if player.item else None)
    print("Passed:", player.passed)
    print("First Player Token:", player.has_first_player_token)
    print("VP:", player.victory_points)

    print("Hand:", [card_name(c) for c in player.hand])
    print("Played:", [card_name(c) for c in player.played])
    print("Monuments:", [card_name(c) for c in player.monuments])
    print("Places:", [card_name(c) for c in player.places])


def show_game_state(game):
    print("\n================ GAME STATE ================")

    for player in game.players:
        show_player_state(player)

    print("============================================")
