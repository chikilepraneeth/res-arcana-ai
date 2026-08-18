from models import ESSENCE_KEYS
from game_memory import get_card_memory_bonus,get_strategy_memory_bonus 
from rules_engine import (
    use_power,
    play_card_from_hand,
    check_victory,
    can_play_card_from_hand,
    pass_turn,
    discard_card_for_resources,
    buy_monument,
    buy_place_of_power,
    can_afford_claim_cost,
    can_use_power,
)
from effect_engine import choose_discount_for_ai
from ai_brain import (
    apply_human_strategy_reaction,
    apply_human_like_noise,apply_memory_reaction,
)
from opponent_model import get_human_plan

from brain import BrainController

from sequence_memory import get_sequence_bonus
from lookahead import get_lookahead_bonus

NON_GOLD_ESSENCE = ["elan", "life", "calm", "death"]

def learning_enabled(player):
    return getattr(
        player,
        "learning_enabled",
        True,
    )


def reward_memory_enabled(player):
    return (
        learning_enabled(player)
        and getattr(
            player,
            "reward_memory_enabled",
            True,
        )
    )


def strategy_memory_enabled(player):
    return (
        learning_enabled(player)
        and getattr(
            player,
            "strategy_memory_enabled",
            True,
        )
    )


def sequence_memory_enabled(player):
    return (
        learning_enabled(player)
        and getattr(
            player,
            "sequence_memory_enabled",
            True,
        )
    )


def context_memory_enabled(player):
    return (
        learning_enabled(player)
        and getattr(
            player,
            "context_memory_enabled",
            True,
        )
    )


def counter_memory_enabled(player):
    return (
        learning_enabled(player)
        and getattr(
            player,
            "counter_memory_enabled",
            True,
        )
    )

_brain_controllers = {}


def get_brain_controller(player):
    key = id(player)

    if key not in _brain_controllers:
        _brain_controllers[key] = BrainController()

    return _brain_controllers[key]

def card_name(card):
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


def card_type(card):
    return (
        getattr(card.definition, "card_type", None)
        or card.definition.raw_data.get("type")
    )


def card_tags(card):
    return card.definition.raw_data.get("tags", [])


def get_controlled_cards(player):
    cards = []

    if player.mage:
        cards.append(player.mage)

    if player.item:
        cards.append(player.item)

    cards.extend(player.played)
    cards.extend(player.monuments)
    cards.extend(player.places)

    return cards


def total_pool(player):
    return sum(player.essence_pool.get(e, 0) for e in ESSENCE_KEYS)


def has_tag(card, tag):
    return tag in card_tags(card)


def matches_restriction(card, restriction):
    if not restriction:
        return True

    if "type" in restriction and card_type(card) != restriction["type"]:
        return False

    if "has_tag" in restriction and restriction["has_tag"] not in card_tags(card):
        return False

    return True


def has_valid_untapped_target(player, restriction=None, exclude_card=None):
    for card in get_controlled_cards(player):
        if exclude_card and card is exclude_card:
            continue

        if card.tapped:
            continue

        if matches_restriction(card, restriction):
            return True

    return False


def has_valid_tapped_target(player, restriction=None, exclude_card=None):
    for card in get_controlled_cards(player):
        if exclude_card and card is exclude_card:
            continue

        if not card.tapped:
            continue

        if matches_restriction(card, restriction):
            return True

    return False


def opponent_has_ready_defense(game, ai_player):
    for player in game.players:
        if player is ai_player:
            continue

        for card in get_controlled_cards(player):
            if card.tapped:
                continue

            react_powers = card.definition.raw_data.get("react_powers", [])

            for react in react_powers:
                for effect in react.get("effect", []):
                    if "ignore_attack" in effect:
                        return True

    return False


def can_pay_cost_simple(player, cost):
    if not cost:
        return True

    essence_cost = cost.get("essence", {})
    remaining_pool = dict(player.essence_pool)

    for essence in ESSENCE_KEYS:
        required = int(essence_cost.get(essence, 0))

        if remaining_pool.get(essence, 0) < required:
            return False

        remaining_pool[essence] -= required

    wild = cost.get("wild")

    if wild:
        if isinstance(wild, int):
            count = wild
            allowed = ESSENCE_KEYS

        elif isinstance(wild, dict):
            count = wild.get("count", 0)
            allowed = wild.get("allowed", ESSENCE_KEYS)

            if count == "X":
                count = 1

            elif count == "X_plus_2":
                count = 3

        else:
            count = 0
            allowed = ESSENCE_KEYS

        if isinstance(count, int):
            available = sum(remaining_pool.get(e, 0) for e in allowed)

            if available < count:
                return False

    tap_payload = cost.get("tap_additional_target")

    if tap_payload:
        restriction = tap_payload.get("restriction")

        if not has_valid_untapped_target(player, restriction=restriction):
            return False

    return True


def score_card_static(card):
    table = {
        "Horn of Plenty": 100,
        "Philosopher's Stone": 100,

        "Vault": 90,
        "Athanor": 90,
        "Corrupt Altar": 90,
        "Elvish Bow": 90,

        "Dwarven Pickaxe": 75,
        "Crypt": 75,
        "Prism": 75,
        "Magical Shard": 75,
        "Chalice of Fire": 75,
        "Ring of Midas": 75,
        "Sacrificial Dagger": 75,
        "Treant": 75,

        "Tree of Life": 55,
        "Hand of Glory": 55,
        "Cursed Skull": 55,
        "Fountain of Youth": 55,

        "Nightingale": 35,
        "Flaming Pit": 35,
        "Elemental Spring": 35,
        "Celestial Horse": 35,
        "Dancing Sword": 35,
        "Hawk": 35,
        "Chalice of Life": 35,
        "Dragon Egg": 35,
        "Bone Dragon": 45,
        "Earth Dragon": 45,
        "Fire Dragon": 45,
        "Wind Dragon": 45,
        "Water Dragon": 45,
        "Sea Serpent": 45,

        "Dragon Bridle": 25,
        "Guard Dog": 20,
        "Mermaid": 25,
        "Windup Man": 30,
    }

    return table.get(card_name(card), 40)


def infer_card_strategy(card):
    name = card_name(card)
    tags = card_tags(card)

    if "dragon" in tags or "dragon_support" in tags or name == "Dragon’s Lair":
        return "dragon"

    if "death_engine" in tags or name == "Catacombs of the Dead":
        return "death"

    if "life_engine" in tags or name == "Sacred Grove":
        return "life"

    if "gold_engine" in tags or "gold_generation" in tags:
        return "gold"

    if "storage" in tags or "vp_scaling" in tags:
        return "storage"

    return None

def score_play_card(card, player, game):
    score = score_card_static(card)
    reasons = []

    tags = card_tags(card)

    reasons.append(f"base card value {score}")

    if "income" in tags:
        score += 25
        reasons.append("income card helps future rounds")

    if "gold_generation" in tags or "gold" in tags:
        score += 30
        reasons.append("gold helps claim monuments")

    if "storage" in tags:
        score += 15
        reasons.append("storage card may create future value")

    if "dragon" in tags:
        if any(
            card_name(place) == "Dragon’s Lair" or card_name(place) == "Dragon's Lair"
            for place in player.places
        ):
            score += 60
            reasons.append("dragon works with Dragon’s Lair")
        else:
            score -= 10
            reasons.append("dragon is expensive without Dragon’s Lair")

    if card.definition.raw_data.get("vp", {}).get("base", 0) > 0:
        vp = card.definition.raw_data["vp"]["base"]
        score += vp * 35
        reasons.append(f"gives {vp} VP")

    if player.victory_points >= 4:
        score += 10
        reasons.append("direct board progress matters near target VP")


    memory_bonus = 0

    if reward_memory_enabled(player):
        memory_bonus = get_card_memory_bonus(
            card_name(card)
        )

    if memory_bonus != 0:
        score += memory_bonus

        if memory_bonus > 0:
            reasons.append(f"memory says {card_name(card)} performed well before")
        else:
            reasons.append(f"memory says {card_name(card)} often underperformed")


    strategy = infer_card_strategy(card)

    if strategy:
        strategy_bonus = 0

        if strategy_memory_enabled(player):
            strategy_bonus = (
                get_strategy_memory_bonus(
                    strategy
                )
            )

        if strategy_bonus != 0:
            score += strategy_bonus

            if strategy_bonus > 0:
                reasons.append(f"strategy memory favors {strategy} path")
            else:
                reasons.append(f"strategy memory dislikes {strategy} path")
    return score, reasons


def score_attack_effect(game, ai_player, amount):
    score = 20 + amount * 20
    reasons = [f"attack causes {amount} life loss"]

    if opponent_has_ready_defense(game, ai_player):
        score -= 45
        reasons.append("opponent may ignore attack")

    for opponent in game.players:
        if opponent is ai_player:
            continue

        if opponent.essence_pool.get("life", 0) < amount:
            score += 30
            reasons.append("opponent lacks enough life, attack burns extra essence")

        if total_pool(opponent) >= 8:
            score += 20
            reasons.append("opponent has many resources to disrupt")

        if opponent.victory_points >= ai_player.victory_points:
            score += 15
            reasons.append("attack slows leading/equal opponent")

    return score, reasons


def score_power(card, power, player, game):
    score = 0
    reasons = []

    cost = power.get("cost", {})

    requires_turn = bool(
        cost.get("turn_self", False)
        or cost.get("tap_self", False)
    )

    if requires_turn and card.tapped:
        return -999, ["source is already tapped"]

    if not can_pay_cost_simple(player, cost):
        return -999, ["cannot pay cost or satisfy extra tap target"]

    effects = power.get("effect", [])

    for effect in effects:
        if "gain_to_pool" in effect:
            gain = effect["gain_to_pool"]
            total_gain = sum(int(gain.get(e, 0)) for e in ESSENCE_KEYS)

            score += total_gain * 18
            reasons.append(f"gains {total_gain} essence")

            if gain.get("gold", 0) > 0:
                score += 25
                reasons.append("gold gain helps monuments")

        elif "gain_wild" in effect:
            payload = effect["gain_wild"]
            count = payload.get("count", 0)

            if isinstance(count, int):
                score += count * 18
                reasons.append(f"gains {count} flexible essence")
            else:
                score += 25
                reasons.append("variable wild gain can be useful")

        elif "draw" in effect:
            count = int(effect["draw"].get("count", 1))
            score += count * 22
            reasons.append(f"draws {count} card(s)")

        elif "discard" in effect:
            count = int(effect["discard"].get("count", 1))
            score -= count * 5
            reasons.append(f"filters/discards {count} card(s)")

        elif "add_to_component" in effect:
            essence = effect["add_to_component"].get("essence", {})
            total_stored = sum(int(essence.get(e, 0)) for e in ESSENCE_KEYS)

            score += total_stored * 18
            reasons.append(f"stores {total_stored} essence on card")

            if essence.get("gold", 0) > 0:
                score += 35
                reasons.append("stored gold may score VP on Places of Power")

        elif "move_from_pool_to_component" in effect:
            score += 25
            reasons.append("moves essence onto storage card")

        elif "store_wild_on_card" in effect:
            count = int(effect["store_wild_on_card"].get("count", 1))
            score += count * 15
            reasons.append(f"stores {count} chosen essence")

        elif "straighten_target" in effect:
            payload = effect["straighten_target"]
            restriction = payload.get("restriction")

            if has_valid_tapped_target(player, restriction=restriction, exclude_card=card):
                score += 50
                reasons.append("can untap a valid useful target")
            else:
                score -= 100
                reasons.append("no valid tapped target to untap")

        elif "untap_self" in effect:
            if card.tapped:
                score += 40
                reasons.append("untaps itself")
            else:
                score -= 20
                reasons.append("self is not tapped")

        elif "attack" in effect:
            payload = effect["attack"]
            amount = int(payload.get("amount", payload.get("life_loss", 0)))

            attack_score, attack_reasons = score_attack_effect(game, player, amount)
            score += attack_score
            reasons.extend(attack_reasons)

        elif "all_rivals_gain" in effect:
            score -= 15
            reasons.append("also gives rival resources")

        elif "gain_equal_to_rival_essence" in effect:
            payload = effect["gain_equal_to_rival_essence"]
            rival_essence = payload.get("rival_essence")
            gain_essence = payload.get("gain_essence")

            best = 0

            for opponent in game.players:
                if opponent is player:
                    continue
                best = max(best, opponent.essence_pool.get(rival_essence, 0))

            score += best * 16
            reasons.append(f"can gain {gain_essence} based on rival {rival_essence}")

        elif "jump_to_phase" in effect:
            if player.victory_points >= 5:
                score += 100
                reasons.append("can force victory check while ahead")
            else:
                score -= 10
                reasons.append("victory check is not useful yet")

        elif "play_card_from_hand" in effect:
            score += 45
            reasons.append("can cheat/play a card from hand")

        elif "ignore_attack" in effect:
            score += 10
            reasons.append("defensive effect")

        elif "gain_gold_equal_to_paid_minus" in effect:
            score += 45
            reasons.append("can convert many essences into gold")

        elif "spend_from_component_then_gain_gold" in effect:
            score += 50
            reasons.append("can convert stored essence into gold")

        elif "play_card_from_discard" in effect:
            if player.discard:
                score += 45
                reasons.append("can replay a card from discard")
            else:
                score -= 50
                reasons.append("discard pile is empty")

        elif "gain_equals_destroyed_artifact_cost_plus" in effect:
            if player.played:
                score += 45
                reasons.append("can destroy weak artifact for essence profit")
            else:
                score -= 50
                reasons.append("no artifact to destroy")

        elif "gain_equals_discarded_card_cost" in effect:
            if player.hand:
                score += 35
                reasons.append("can discard card for cost value")
            else:
                score -= 50
                reasons.append("no card in hand to discard")

        elif "store_on_target_card" in effect:
            score += 30
            reasons.append("can store essence on a useful target")
        
        elif "gain_gold_equal_to_paid_minus" in effect:
            score += 45
            reasons.append("can convert many essences into gold")

        elif "spend_from_component_then_gain_gold" in effect:
            score += 50
            reasons.append("can convert stored essence into gold")

        elif "play_card_from_discard" in effect:
            if player.discard:
                score += 45
                reasons.append("can replay a card from discard")
            else:
                score -= 50
                reasons.append("discard pile is empty")

        elif "gain_equals_destroyed_artifact_cost_plus" in effect:
            if player.played:
                score += 45
                reasons.append("can destroy weak artifact for essence profit")
            else:
                score -= 50
                reasons.append("no artifact to destroy")

        elif "gain_equals_discarded_card_cost" in effect:
            if player.hand:
                score += 35
                reasons.append("can discard card for cost value")
            else:
                score -= 50
                reasons.append("no card in hand to discard")

        elif "store_on_target_card" in effect:
            score += 30
            reasons.append("can store essence on a useful target")
        
        else:
            score += 5
            reasons.append(f"unknown effect may still help: {effect}")

    if cost.get("tap_additional_target"):
        restriction = cost["tap_additional_target"].get("restriction", {})
        score += 20
        reasons.append(f"uses additional tapped target with restriction {restriction}")

    if cost.get("turn_self"):
        score -= 5
        reasons.append("uses/taps the source")


    memory_bonus = 0

    if reward_memory_enabled(player):
        memory_bonus = get_card_memory_bonus(
            card_name(card)
        )

    if memory_bonus != 0:
        score += memory_bonus

        if memory_bonus > 0:
            reasons.append(
                "memory favors this card power"
            )
        else:
            reasons.append(
                "memory dislikes this card power"
            )

      

    strategy = infer_card_strategy(card)

    if strategy:
        strategy_bonus = 0

        if strategy_memory_enabled(player):
            strategy_bonus = (
                get_strategy_memory_bonus(
                    strategy
                )
            )

        if strategy_bonus != 0:
            score += strategy_bonus

            if strategy_bonus > 0:
                reasons.append(f"strategy memory favors {strategy} power")
            else:
                reasons.append(f"strategy memory dislikes {strategy} power")
    return score, reasons


def missing_resources_for_best_card(player):
    best_card = None
    best_score = -999
    best_missing = []

    for card in player.hand:
        cost = card.definition.raw_data.get("placement_cost") or {}
        essence_cost = cost.get("essence", {})

        missing = []

        for essence in ESSENCE_KEYS:
            required = int(essence_cost.get(essence, 0))
            available = int(player.essence_pool.get(essence, 0))

            if required > available:
                missing.extend([essence] * (required - available))

        score = score_card_static(card)

        if missing and score > best_score:
            best_score = score
            best_card = card
            best_missing = missing

    return best_card, best_missing


def choose_discard_reward(player):
    best_card, missing = missing_resources_for_best_card(player)

    filtered = [
        essence for essence in missing
        if essence in NON_GOLD_ESSENCE
    ]

    if len(filtered) >= 2:
        return "essence", filtered[:2]

    if len(filtered) == 1:
        return "essence", [filtered[0], filtered[0]]

    if "gold" in missing:
        return "gold", None

    if player.essence_pool.get("gold", 0) < 2:
        return "gold", None

    return "essence", ["elan", "life"]


def score_discard_card(card, player):
    score = 0
    reasons = []

    static_score = score_card_static(card)

    if static_score <= 35:
        score += 60
        reasons.append("low-tier card is better as resources")
    elif static_score <= 55:
        score += 30
        reasons.append("medium card can be discarded if resources are needed")
    else:
        score -= 25
        reasons.append("strong card should usually be kept")

    reward_type, choices = choose_discard_reward(player)

    if reward_type == "gold":
        score += 25
        reasons.append("gold helps buy monuments")
    else:
        score += 20
        reasons.append(f"essence reward helps future card costs: {choices}")

    return score, reasons, reward_type, choices


def score_market_card(card, player, game, card_kind):
    score = 0
    reasons = []

    raw = card.definition.raw_data
    vp = int(raw.get("vp", {}).get("base", 0))
    conditional = raw.get("vp", {}).get("conditional", [])

    if vp > 0:
        score += vp * 55
        reasons.append(f"gives {vp} base VP")

    for condition in conditional:
        if "per_stored_essence" in condition:
            score += 70
            reasons.append("can score from stored essence")

    tags = raw.get("tags", [])

    if "vp_scaling" in tags:
        score += 60
        reasons.append("scales into VP")

    if "gold_engine" in tags:
        score += 40
        reasons.append("supports gold engine")

    if "dragon_support" in tags:
        has_dragons = any(
            "dragon" in card_tags(c)
            for c in player.hand + player.played
        )

        if has_dragons:
            score += 70
            reasons.append("matches AI dragon cards")
        else:
            score += 10
            reasons.append("dragon support may help later")

    if card_kind == "place":
        score += 40
        reasons.append("Place of Power is a main win condition")

    name = card_name(card)

    if name in ["Dragon’s Lair", "Dragon's Lair"]:
        score += 200
        reasons.append("Dragon's Lair is a learned priority target")

    if name == "Catacombs of the Dead":
        score += 200
        reasons.append("Catacombs is a learned priority target")
    if card_kind == "monument":
        score += 30
        reasons.append("monument gives direct scoring")

    if player.victory_points >= 5:
        score += 30
        reasons.append("direct VP matters near the end")


    strategy = infer_card_strategy(card)

    if strategy:
        strategy_bonus = 0

        if strategy_memory_enabled(player):
            strategy_bonus = (
                get_strategy_memory_bonus(
                    strategy
                )
            )

        # Stronger memory influence on win conditions
        if card_kind == "place":
            strategy_bonus *= 4

        elif card_kind == "monument":
            strategy_bonus *= 2

        score += strategy_bonus

        if strategy_bonus > 0:
            reasons.append(
                f"memory strongly favors "
                f"{strategy} strategy"
            )

        elif strategy_bonus < 0:
            reasons.append(
                f"memory dislikes "
                f"{strategy} strategy"
            )

        
    return score, reasons

def choose_ai_x_value(power, ai_player):
    cost = power.get("cost", {})
    wild = cost.get("wild")

    if isinstance(wild, dict):
        count = wild.get("count")

        if count == "X":
            allowed = wild.get("allowed", ESSENCE_KEYS)
            available = sum(ai_player.essence_pool.get(e, 0) for e in allowed)
            return max(1, min(available, 3))

        if count == "X_plus_2":
            allowed = wild.get("allowed", ESSENCE_KEYS)
            available = sum(ai_player.essence_pool.get(e, 0) for e in allowed)
            return max(1, min(available - 2, 3))

    for effect in power.get("effect", []):
        if "gain_wild" in effect:
            count = effect["gain_wild"].get("count")

            if count == "X":
                return 2

            if count == "X_plus_2":
                return 2

    return None

def choose_ai_straighten_target(ai_player, source_card, power):
    restriction = None
    needs_target = False

    for effect in power.get("effect", []):
        if "straighten_target" in effect:
            needs_target = True
            restriction = effect["straighten_target"].get("restriction")

    if not needs_target:
        return None

    candidates = []

    for card in get_controlled_cards(ai_player):
        if card is source_card:
            continue

        if not card.tapped:
            continue

        if matches_restriction(card, restriction):
            candidates.append(card)

    if not candidates:
        return None

    def target_score(card):
        score = score_card_static(card)

        raw = card.definition.raw_data

        if raw.get("powers"):
            score += 30

        if raw.get("vp", {}).get("base", 0) > 0:
            score += raw["vp"]["base"] * 20

        if "gold_generation" in card_tags(card):
            score += 25

        if "income" in card_tags(card):
            score += 15

        return score

    best = max(candidates, key=target_score)
    return card_id(best)

def choose_ai_wild_payment(ai_player, power):
    cost = power.get("cost", {})
    wild = cost.get("wild")

    if not wild:
        return None

    if isinstance(wild, int):
        count = wild
        allowed = ESSENCE_KEYS
    elif isinstance(wild, dict):
        count = wild.get("count", 0)
        allowed = wild.get("allowed", ESSENCE_KEYS)
    else:
        return None

    if count == "X":
        x_value = choose_ai_x_value(power, ai_player)
        count = x_value

    elif count == "X_plus_2":
        x_value = choose_ai_x_value(power, ai_player)
        count = x_value + 2

    if not isinstance(count, int) or count <= 0:
        return None

    choices = []

    for _ in range(count):
        possible = [
            e for e in allowed
            if ai_player.essence_pool.get(e, 0) > choices.count(e)
        ]

        if not possible:
            break

        # pay the essence AI has most of
        chosen = max(possible, key=lambda e: ai_player.essence_pool.get(e, 0))
        choices.append(chosen)

    if len(choices) != count:
        return None

    return choices


def choose_ai_wild_payment_for_cost(
    ai_player,
    cost,
    discount_choices=None,
):
    wild = cost.get("wild")

    if not wild:
        return None

    if isinstance(wild, int):
        count = wild
        allowed = ESSENCE_KEYS

    elif isinstance(wild, dict):
        count = wild.get("count", 0)
        allowed = wild.get(
            "allowed",
            ESSENCE_KEYS,
        )

    else:
        return None

    if not isinstance(count, int):
        return None

    # Discount may reduce part of the wild cost.
    if discount_choices:
        count -= discount_choices.count(
            "wild"
        )

    count = max(0, count)

    if count == 0:
        return []

    # Simulate fixed essence payment first.
    temp_pool = dict(
        ai_player.essence_pool
    )

    essence_cost = cost.get(
        "essence",
        {},
    )

    for essence in ESSENCE_KEYS:
        fixed_amount = int(
            essence_cost.get(
                essence,
                0,
            )
        )

        # Placement discount may reduce
        # this fixed essence cost.
        if discount_choices:
            fixed_amount -= (
                discount_choices.count(
                    essence
                )
            )

        fixed_amount = max(
            0,
            fixed_amount,
        )

        temp_pool[essence] = (
            temp_pool.get(
                essence,
                0,
            )
            - fixed_amount
        )

    choices = []

    for _ in range(count):
        possible = [
            essence
            for essence in allowed
            if temp_pool.get(
                essence,
                0,
            ) > 0
        ]

        if not possible:
            return None

        chosen = max(
            possible,
            key=lambda essence:
                temp_pool.get(
                    essence,
                    0,
                ),
        )

        choices.append(chosen)

        temp_pool[chosen] -= 1

    return choices


def choose_ai_strategy(game, ai_player):
    scores = {
        "death": 0,
        "dragon": 0,
        "gold": 0,
        "life": 0,
        "storage": 0
    }

    all_cards = ai_player.hand + ai_player.played + ai_player.places + ai_player.monuments

    for card in all_cards:
        strategy = infer_card_strategy(card)

        if strategy in scores:
            scores[strategy] += 20

    for place in game.market_places:
        strategy = infer_card_strategy(place)

        if strategy in scores:
            scores[strategy] += 30

    if strategy_memory_enabled(
        ai_player
    ):

        for strategy in scores:
            scores[strategy] += (
                get_strategy_memory_bonus(
                    strategy
                ) * 5
            )

        memory_bonus = (
            get_strategy_memory_bonus(
                "death"
            )
        )

        if memory_bonus > 0:
            scores["death"] += 100

        memory_bonus = (
            get_strategy_memory_bonus(
                "dragon"
            )
        )

        if memory_bonus > 0:
            scores["dragon"] += 100

    return max(
        scores,
        key=scores.get,
    )


def explain_ai_strategy(strategy):
    explanations = {
        "death": "I am trying a death strategy, mainly looking for Catacombs or death storage scoring.",
        "dragon": "I am trying a dragon strategy, mainly looking for Dragon’s Lair and dragon discounts.",
        "gold": "I am trying a gold strategy, mainly buying monuments and gold-scoring cards.",
        "life": "I am trying a life strategy, mainly looking for Sacred Grove and life storage scoring.",
        "storage": "I am trying a storage strategy, keeping essence on cards that can score or grow."
    }

    return explanations.get(strategy, "I am still choosing my strategy.")

def get_ai_legal_moves(game, ai_player):
    moves = []
    ai_strategy = choose_ai_strategy(game, ai_player)

    # 1. Play cards from hand
    for card in ai_player.hand:
        if can_play_card_from_hand(ai_player, card):
            score, reasons = score_play_card(card, ai_player, game)

            moves.append({
                "type": "play_card",
                "card_id": card_id(card),
                "card_name": card_name(card),
                "score": score,
                "reasons": reasons,
            })

    # 2. Use powers
    for card in get_controlled_cards(ai_player):
        powers = card.definition.raw_data.get(
            "powers",
            [],
        )

        for power in powers:

            # Central rules-engine legality check.
            if not can_use_power(
                game,
                ai_player,
                card,
                power,
            ):
                continue

            score, reasons = score_power(
                card,
                power,
                ai_player,
                game,
            )

            if score <= -900:
                continue

            moves.append({
                "type": "use_power",
                "card_id": card_id(card),
                "card_name": card_name(card),
                "power_index": power.get(
                    "power_index"
                ),
                "score": score,
                "reasons": reasons,
            })

    # 3. Buy monuments
    for index, monument in enumerate(game.market_monuments):
        if ai_player.essence_pool.get("gold", 0) >= 4:
            score, reasons = score_market_card(
                monument,
                ai_player,
                game,
                card_kind="monument"
            )

            moves.append({
                "type": "buy_monument",
                "market_index": index,
                "card_name": card_name(monument),
                "score": score,
                "reasons": reasons,
            })

    # 4. Buy Places of Power
    for index, place in enumerate(game.market_places):
        if can_afford_claim_cost(ai_player, place):
            score, reasons = score_market_card(
                place,
                ai_player,
                game,
                card_kind="place"
            )

            moves.append({
                "type": "buy_place_of_power",
                "market_index": index,
                "card_name": card_name(place),
                "score": score,
                "reasons": reasons,
            })

    # 5. Discard cards
    for card in ai_player.hand:
        score, reasons, reward_type, choices = score_discard_card(card, ai_player)

        moves.append({
            "type": "discard",
            "card_id": card_id(card),
            "card_name": card_name(card),
            "score": score,
            "reasons": reasons,
            "reward_type": reward_type,
            "choices": choices,
        })

        # 6. Pass
    pass_score = -10
    pass_reasons = [
        "passing ends all remaining actions this round"
    ]

    useful_non_pass_moves = [
        move
        for move in moves
        if move.get("type") != "pass"
        and move.get("score", 0) > 20
    ]

    playable_cards = sum(
        1
        for move in moves
        if move.get("type") == "play_card"
    )

    usable_powers = sum(
        1
        for move in moves
        if move.get("type") == "use_power"
    )

    affordable_market_cards = sum(
        1
        for move in moves
        if move.get("type") in {
            "buy_monument",
            "buy_place_of_power",
        }
    )

    remaining_opportunities = (
        playable_cards
        + usable_powers
        + affordable_market_cards
    )

    if remaining_opportunities > 0:
        penalty = remaining_opportunities * 25
        pass_score -= penalty

        pass_reasons.append(
            f"passing would abandon "
            f"{remaining_opportunities} useful actions"
        )

    if (
        not ai_player.has_first_player_token
        and game.first_player_token_available
    ):
        # First player is useful, but should not
        # overpower engine development.
        pass_score += 12
        pass_reasons.append(
            "passing can claim first player"
        )

    if ai_player.victory_points >= 8:
        pass_score += 20
        pass_reasons.append(
            "late-game first player control may matter"
        )

    if not useful_non_pass_moves:
        pass_score += 40
        pass_reasons.append(
            "no valuable non-pass action remains"
        )

    moves.append({
        "type": "pass",
        "score": pass_score,
        "reasons": pass_reasons,
    })
    if getattr(game, "self_play", False):
        failed_moves = getattr(
            game,
            "self_play_failed_moves",
            {},
        ).get(
            id(ai_player),
            set(),
        )

        moves = [
            move
            for move in moves
            if (
                move.get("type"),
                move.get("card_name"),
            )
            not in failed_moves
        ]
    return moves



def execute_move_for_simulation(
    game,
    ai_player,
    move,
):
    move_type = move.get("type")

    if move_type == "play_card":
        source_card = next(
            (
                card
                for card in ai_player.hand
                if card_id(card)
                == move.get("card_id")
            ),
            None,
        )

        if source_card is None:
            return False

        from rules_engine import (
            get_effective_placement_cost,
        )

        placement_cost = (
            get_effective_placement_cost(
                ai_player,
                source_card,
            )
        )

        wild_choices = None
        discount_choices = None

        if placement_cost:
            discount_choices = (
                choose_discount_for_ai(
                    ai_player,
                    placement_cost,
                )
            )

            wild_choices = (
                choose_ai_wild_payment_for_cost(
                    ai_player,
                    placement_cost,
                    discount_choices=discount_choices,
                )
            )

        play_card_from_hand(
            game,
            ai_player,
            move["card_id"],
            wild_choices=wild_choices,
            discount_choices=discount_choices,
        )

        return True

    if move_type == "discard":
        discard_card_for_resources(
            game,
            ai_player,
            move["card_id"],
            move["reward_type"],
            move.get("choices"),
        )

        return True

    if move_type == "buy_monument":
        buy_monument(
            game,
            ai_player,
            move["market_index"],
        )

        return True

    if move_type == "buy_place_of_power":
        buy_place_of_power(
            game,
            ai_player,
            move["market_index"],
        )

        return True

    if move_type == "pass":
        pass_turn(
            game,
            ai_player,
        )

        return True

    # Complex power simulation will be added later.
    if move_type == "use_power":
        return False

    return False

def choose_best_move(game, ai_player):
    moves = get_ai_legal_moves(game, ai_player)

    if not moves:
        return {
            "type": "pass",
            "score": 0,
            "reasons": ["no legal moves"],
        }, []

    human_plan, confidence, model = get_human_plan(game)

    final_moves = []

    for move in moves:
        score = move.get("score", 0)
        reasons = list(move.get("reasons", []))
        recent_moves = getattr(
            game,
            "ai_move_history",
            [],
        )

        sequence_bonus = 0
        sequence_reason = None

        if sequence_memory_enabled(
            ai_player
        ):
            sequence_bonus, sequence_reason = (
                get_sequence_bonus(
                    recent_moves,
                    move,
                )
            )

        score += sequence_bonus

        if sequence_reason:
            reasons.append(sequence_reason)

        if confidence >= 5:
            if human_plan == "place_rush" and move["type"] == "buy_place_of_power":
                score += 250
                reasons.append("AI sees Chikile rushing Places of Power")

            if human_plan == "death" and move.get("card_name") == "Catacombs of the Dead":
                score += 350
                reasons.append("AI blocks Chikile's death plan")

            if human_plan == "dragon" and move.get("card_name") in ["Dragon’s Lair", "Dragon's Lair"]:
                score += 350
                reasons.append("AI blocks Chikile's dragon plan")

            if human_plan == "monument_rush" and move["type"] == "buy_monument":
                score += 180
                reasons.append("AI keeps up with monument race")

        score, reasons = apply_human_strategy_reaction(
            move,
            score,
            reasons,
            game,
            ai_player
        )
        score, reasons = apply_memory_reaction(
            move,
            score,
            reasons,
            game=game,
            ai_player=ai_player,

            use_reward=(
                reward_memory_enabled(
                    ai_player
                )
            ),

            use_context=(
                context_memory_enabled(
                    ai_player
                )
            ),

            use_counter=(
                counter_memory_enabled(
                    ai_player
                )
            ),
        )
        if move.get("type") != "use_power":
            lookahead_bonus, lookahead_reason = (
                get_lookahead_bonus(
                    game,
                    ai_player,
                    move,
                    execute_move_for_simulation,
                )
            )

            score += lookahead_bonus

            if lookahead_reason:
                reasons.append(
                    lookahead_reason
                )
        score = apply_human_like_noise(score, difficulty="normal")

        move["score"] = score
        move["reasons"] = reasons

        final_moves.append(move)

    final_moves = sorted(
        final_moves,
        key=lambda m: m["score"],
        reverse=True
    )

    return final_moves[0], final_moves

def explain_move(move):
    reasons = move.get("reasons", [])
    reason_text = ", ".join(reasons)

    move_type = move.get("type")

    if move_type == "play_card":
        return f"I played {move['card_name']} because {reason_text}. Score: {move['score']}."

    if move_type == "use_power":
        return f"I used {move['card_name']} power {move['power_index']} because {reason_text}. Score: {move['score']}."

    if move_type == "discard":
        return f"I discarded {move['card_name']} because {reason_text}. Score: {move['score']}."

    if move_type == "buy_monument":
        return f"I bought monument {move['card_name']} because {reason_text}. Score: {move['score']}."

    if move_type == "buy_place_of_power":
        return f"I bought Place of Power {move['card_name']} because {reason_text}. Score: {move['score']}."

    if move_type == "pass":
        return f"I passed because {reason_text}. Score: {move['score']}."
    

    return f"I chose {move_type} because {reason_text}. Score: {move.get('score')}."


def execute_ai_move(game, ai_player):
    if not hasattr(game, "ai_move_history"):
        game.ai_move_history = []
    brain_controller = get_brain_controller(
        ai_player
    )

    best_move, all_moves = (
        brain_controller.choose_action(
            game,
            ai_player,
        )
    )
    
    # Show detailed brain thoughts during normal games,
    # but hide them during automatic self-play.
    if not getattr(game, "self_play", False):

        print("\n" + "=" * 60)

        print(
            f"AI BRAIN DECISION — {ai_player.name}"
        )

        print("=" * 60)

        print(
            "Round:",
            getattr(game, "round_no", "?")
        )

        print(
            "Current player index:",
            getattr(
                game,
                "current_player_index",
                "?"
            )
        )

        print(
            "Goal:",
            best_move.get("brain_goal")
        )

        print(
            "Plan:",
            best_move.get("brain_plan")
        )

        print(
            "Move:",
            best_move.get("type"),
            best_move.get("card_name"),
            "Power:",
            best_move.get("power_index"),
        )

        print(
            "Score:",
            best_move.get("score")
        )

        print("Thoughts:")

        for thought in best_move.get(
            "brain_thoughts",
            [],
        ):
            print("-", thought)

        print("=" * 60)
   
    ai_strategy = choose_ai_strategy(game, ai_player)
    best_move["strategy"] = ai_strategy
    best_move["strategy_explanation"] = explain_ai_strategy(ai_strategy)

    try:
        if best_move["type"] == "play_card":
            source_card = None

            for card in ai_player.hand:
                if card_id(card) == best_move["card_id"]:
                    source_card = card
                    break

            placement_cost = None
            wild_choices = None
            discount_choices = None

            if source_card:
                from rules_engine import get_effective_placement_cost

                placement_cost = get_effective_placement_cost(
                    ai_player,
                    source_card
                )

                if placement_cost:
                    discount_choices = (
                        choose_discount_for_ai(
                            ai_player,
                            placement_cost,
                        )
                    )

                    wild_choices = (
                        choose_ai_wild_payment_for_cost(
                            ai_player,
                            placement_cost,
                            discount_choices=discount_choices,
                        )
                    )
            play_card_from_hand(
                game,
                ai_player,
                best_move["card_id"],
                wild_choices=wild_choices,
                discount_choices=discount_choices
            )

        elif best_move["type"] == "use_power":
            source_card = None
            selected_power = None

            for card in get_controlled_cards(ai_player):
                if card_id(card) == best_move["card_id"]:
                    source_card = card
                    break

            if source_card:
                for power in source_card.definition.raw_data.get("powers", []):
                    if int(power.get("power_index", -1)) == int(best_move["power_index"]):
                        selected_power = power
                        break

            x_value = None
            wild_choices = None
            target_choices = {}

            if selected_power:
                x_value = choose_ai_x_value(selected_power, ai_player)
                wild_choices = choose_ai_wild_payment(ai_player, selected_power)

                target_card_id = choose_ai_straighten_target(
                    ai_player,
                    source_card,
                    selected_power
                )

                if target_card_id:
                    target_choices["straighten_target"] = target_card_id

            use_power(
                game,
                ai_player,
                best_move["card_id"],
                best_move["power_index"],
                wild_choices=wild_choices,
                target_choices=target_choices,
                x_value=x_value
            )
        elif best_move["type"] == "discard":
            discard_card_for_resources(
                game,
                ai_player,
                best_move["card_id"],
                best_move["reward_type"],
                best_move.get("choices")
            )

        elif best_move["type"] == "buy_monument":
            buy_monument(
                game,
                ai_player,
                best_move["market_index"]
            )

        elif best_move["type"] == "buy_place_of_power":
            buy_place_of_power(
                game,
                ai_player,
                best_move["market_index"]
            )

        elif best_move["type"] == "pass":
            pass_turn(game, ai_player)

    except Exception as e:
        print(
            "AI MOVE FAILED:",
            best_move.get("type"),
            best_move.get("card_name"),
            e,
        )

        game.game_log.append(
            f"AI move failed: {e}"
        )

        return {
            "type": "failed",
            "failed_move_type": best_move.get("type"),
            "card_name": best_move.get("card_name"),
            "error": str(e),
            "score": -9999,
            "reasons": [
                f"move failed: {e}"
            ],
        }

    reflection = (
    brain_controller.reflect_after_action(
        game,
        ai_player,
        best_move,
    )
)

    best_move["brain_reflection"] = reflection

    best_move["explanation"] = explain_move(
        best_move
    )

    game.ai_move_history.append({
        "player": ai_player.name,
        "type": best_move.get("type"),
        "move_type": best_move.get("type"),
        "card_name": best_move.get(
            "card_name"
        ),
        "reward_type": best_move.get(
            "reward_type"
        ),
        "reward_choices": best_move.get(
            "choices"
        ),
        "choices": best_move.get(
            "choices"
        ),
        "vp_after": getattr(
            ai_player,
            "victory_points",
            0,
        ),
    })

    game.ai_move_history = (
        game.ai_move_history[-5:]
    )
    # Keep the latest AI decision available
    # for the Pygame brain panel.
    game.last_ai_move = best_move
    return best_move




