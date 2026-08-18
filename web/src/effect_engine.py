import random
from collections import Counter
from models import ESSENCE_KEYS


class EffectError(Exception):
    pass


def log(game, message):
    game.game_log.append(message)


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


def ensure_stored(card):
    if not hasattr(card, "stored_essence") or card.stored_essence is None:
        card.stored_essence = {k: 0 for k in ESSENCE_KEYS}

    for essence in ESSENCE_KEYS:
        card.stored_essence.setdefault(essence, 0)


def essence_total(pool):
    return sum(int(pool.get(k, 0)) for k in ESSENCE_KEYS)


def add_essence(player, essence_delta):
    for essence in ESSENCE_KEYS:
        amount = int(essence_delta.get(essence, 0))
        player.essence_pool[essence] += amount


def remove_essence(player, essence_delta):
    for essence in ESSENCE_KEYS:
        amount = int(essence_delta.get(essence, 0))

        if amount <= 0:
            continue

        if player.essence_pool.get(essence, 0) < amount:
            raise EffectError(f"{player.name} does not have enough {essence}.")

        player.essence_pool[essence] -= amount


def can_pay_essence(player, essence_cost):
    for essence in ESSENCE_KEYS:
        required = int(essence_cost.get(essence, 0))

        if player.essence_pool.get(essence, 0) < required:
            return False

    return True


def normalize_wild(wild):
    if not wild:
        return 0, ESSENCE_KEYS

    if isinstance(wild, int):
        return wild, ESSENCE_KEYS

    if isinstance(wild, dict):
        count = wild.get("count", 0)
        allowed = wild.get("allowed", ESSENCE_KEYS)

        if isinstance(count, int):
            return count, allowed

    return 0, ESSENCE_KEYS


def can_pay_cost(player, cost, wild_choices=None):
    if not cost:
        return True

    essence_cost = cost.get("essence", {})

    if not can_pay_essence(player, essence_cost):
        return False

    remaining_pool = dict(player.essence_pool)

    for essence in ESSENCE_KEYS:
        remaining_pool[essence] -= int(essence_cost.get(essence, 0))

    wild_count, allowed = normalize_wild(cost.get("wild"))

    if wild_count <= 0:
        return True

    if wild_choices:
        if len(wild_choices) != wild_count:
            return False

        choice_counts = Counter(wild_choices)

        for essence, amount in choice_counts.items():
            if essence not in allowed:
                return False

            if remaining_pool.get(essence, 0) < amount:
                return False

        return True

    available = sum(
        remaining_pool.get(essence, 0)
        for essence in allowed
    )

    return available >= wild_count
def choose_wild_for_ai(
    player,
    cost,
    discount_choices=None,
):
    wild = cost.get("wild")

    if not wild:
        return None

    if isinstance(wild, int):
        wild_count = wild
        allowed = ESSENCE_KEYS

    elif isinstance(wild, dict):
        wild_count = wild.get("count", 0)
        allowed = wild.get(
            "allowed",
            ESSENCE_KEYS
        )

    else:
        return None

    if not isinstance(wild_count, int):
        return None

    if discount_choices:
        wild_count -= discount_choices.count(
            "wild"
        )

    wild_count = max(0, wild_count)

    if wild_count == 0:
        return []

    # Simulate fixed-cost payment first.
    temp_pool = dict(player.essence_pool)

    essence_cost = cost.get(
        "essence",
        {}
    )

    for essence in ESSENCE_KEYS:

        amount = int(
            essence_cost.get(
                essence,
                0
            )
        )

        if discount_choices:
            amount -= discount_choices.count(
                essence
            )

        amount = max(0, amount)

        temp_pool[essence] -= amount

    choices = []

    for _ in range(wild_count):

        possible = [
            essence
            for essence in allowed
            if temp_pool.get(
                essence,
                0
            ) > 0
        ]

        if not possible:
            return None

        chosen = max(
            possible,
            key=lambda essence:
                temp_pool.get(
                    essence,
                    0
                )
        )

        choices.append(chosen)
        temp_pool[chosen] -= 1

    return choices
def choose_discount_for_ai(player, cost):
    essence_cost = cost.get("essence", {})
    discount_data = cost.get("discount", {})
    discount_amount = int(discount_data.get("amount", 0))

    if discount_amount <= 0:
        return None

    adjusted = {
        essence: int(essence_cost.get(essence, 0))
        for essence in ESSENCE_KEYS
    }

    choices = []

    for _ in range(discount_amount):
        possible = [
            essence for essence in ["elan", "life", "calm", "death"]
            if adjusted.get(essence, 0) > 0
        ]

        if not possible:
            break

        # AI discounts the essence it has least available,
        # so it protects scarce resources.
        chosen = min(
            possible,
            key=lambda e: player.essence_pool.get(e, 0)
        )

        adjusted[chosen] -= 1
        choices.append(chosen)

    if len(choices) != discount_amount:
        return None

    return choices


def pay_cost(player, cost, wild_choices=None, discount_choices=None):
    if not cost:
        return True

    essence_cost = cost.get("essence", {})
    discount_data = cost.get("discount")
    discount_amount = 0

    if discount_data:
        discount_amount = int(discount_data.get("amount", 0))

    adjusted_cost = {
        essence: int(essence_cost.get(essence, 0))
        for essence in ESSENCE_KEYS
    }

    # 1. Apply discount only from given choices
    if discount_amount > 0:
        if not discount_choices:
            return False

        if len(discount_choices) != discount_amount:
            return False

        for essence in discount_choices:
            if essence == "gold":
                return False

            if essence == "wild":
                continue

            if essence not in ESSENCE_KEYS:
                return False

            if adjusted_cost.get(essence, 0) <= 0:
                return False

            adjusted_cost[essence] -= 1

    # 2. Check and pay fixed essence cost after discount
    if not can_pay_essence(player, adjusted_cost):
        return False

    remove_essence(player, adjusted_cost)

    # 3. Pay wild cost only from given choices
    wild = cost.get("wild")

    if wild:
        if isinstance(wild, int):
            wild_count = wild
            allowed = ESSENCE_KEYS

        elif isinstance(wild, dict):
            wild_count = wild.get("count", 0)
            allowed = wild.get("allowed", ESSENCE_KEYS)

        else:
            return False
        # Apply discount to wild costs
        wild_discount = 0

        if discount_choices:
            wild_discount = discount_choices.count("wild")

        wild_count = max(0, wild_count - wild_discount)
        # Variable X wild costs are handled before pay_cost
        if not isinstance(wild_count, int):
            return True

        if wild_count <= 0:
            return True

        if not wild_choices:
            return False

        if len(wild_choices) != wild_count:
            return False

        temp_pool = dict(player.essence_pool)

        for essence in wild_choices:
            if essence not in allowed:
                return False

            if temp_pool.get(essence, 0) <= 0:
                return False

            temp_pool[essence] -= 1

        for essence in wild_choices:
            player.essence_pool[essence] -= 1

    return True

def reshuffle_discard_into_deck(game, player):
    if not player.discard:
        return False

    random.shuffle(player.discard)

    player.deck_hidden = player.discard
    player.discard = []

    log(game, f"{player.name} reshuffled discard pile into draw pile.")

    return True


import random


def draw_cards(game, player, count):
    drawn_cards = []

    for _ in range(count):
        if not player.deck_hidden:
            if player.discard:
                random.shuffle(player.discard)

                player.deck_hidden = player.discard
                player.discard = []

                game.game_log.append(
                    f"{player.name} shuffled discard pile into draw pile."
                )
            else:
                game.game_log.append(
                    f"{player.name} has no cards left to draw."
                )
                break

        if player.deck_hidden:
            card = player.deck_hidden.pop(0)
            player.hand.append(card)
            drawn_cards.append(card)

    if drawn_cards:
        game.game_log.append(
            f"{player.name} drew {len(drawn_cards)} card(s)."
        )

    return drawn_cards


def get_weak_card_score(card):
    name = card_name(card)

    score_table = {
        "Dragon Bridle": 10,
        "Guard Dog": 10,
        "Mermaid": 10,
        "Windup Man": 10,

        "Nightingale": 35,
        "Flaming Pit": 35,
        "Elemental Spring": 35,
        "Celestial Horse": 35,
        "Dancing Sword": 35,
        "Hawk": 35,
        "Chalice of Life": 35,
        "Dragon Egg": 35,
        "Bone Dragon": 35,
        "Earth Dragon": 35,
        "Fire Dragon": 35,
        "Wind Dragon": 35,
        "Water Dragon": 35,
        "Sea Serpent": 35,

        "Tree of Life": 55,
        "Hand of Glory": 55,
        "Cursed Skull": 55,
        "Fountain of Youth": 55,

        "Dwarven Pickaxe": 75,
        "Crypt": 75,
        "Prism": 75,
        "Magical Shard": 75,
        "Chalice of Fire": 75,
        "Ring of Midas": 75,
        "Sacrificial Dagger": 75,
        "Treant": 75,

        "Vault": 90,
        "Athanor": 90,
        "Corrupt Altar": 90,
        "Elvish Bow": 90,

        "Horn of Plenty": 100,
        "Philosopher's Stone": 100,
    }

    return score_table.get(name, 40)


def discard_from_hand(game, player, count):
    discarded = []

    for _ in range(count):
        if not player.hand:
            break

        weakest_card = min(player.hand, key=get_weak_card_score)
        player.hand.remove(weakest_card)
        player.discard.append(weakest_card)
        discarded.append(card_name(weakest_card))

    log(game, f"{player.name} discarded {len(discarded)} card(s): {discarded}")

    return discarded


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


def matches_restriction(card, restriction):
    if not restriction:
        return True

    if "type" in restriction:
        if card_type(card) != restriction["type"]:
            return False

    if "has_tag" in restriction:
        if restriction["has_tag"] not in card_tags(card):
            return False

    if "not_type" in restriction:
        if card_type(card) == restriction["not_type"]:
            return False

    return True


def find_tapped_target(player, restriction=None, exclude_card=None):
    for card in get_controlled_cards(player):
        if exclude_card and card is exclude_card:
            continue

        if not card.tapped:
            continue

        if not matches_restriction(card, restriction):
            continue

        return card

    return None


def find_untapped_target(player, restriction=None, exclude_card=None):
    for card in get_controlled_cards(player):
        if exclude_card and card is exclude_card:
            continue

        if card.tapped:
            continue

        if not matches_restriction(card, restriction):
            continue

        return card

    return None


def choose_best_essence_for_ai(player, allowed):
    """
    Smart-ish AI essence choice.

    Priority:
    1. Essence missing for cards in hand.
    2. Essence currently lowest in pool.
    """
    need_score = {essence: 0 for essence in allowed}

    for card in player.hand:
        cost = card.definition.raw_data.get("placement_cost") or {}
        essence_cost = cost.get("essence", {})

        for essence in allowed:
            required = int(essence_cost.get(essence, 0))
            available = int(player.essence_pool.get(essence, 0))

            if required > available:
                need_score[essence] += required - available

    best_need = max(need_score.values()) if need_score else 0

    if best_need > 0:
        best_options = [
            essence for essence, score in need_score.items()
            if score == best_need
        ]

        return min(
            best_options,
            key=lambda e: player.essence_pool.get(e, 0)
        )

    return min(
        allowed,
        key=lambda e: player.essence_pool.get(e, 0)
    )


def gain_wild(game, player, payload, choices=None):
    count = payload.get("count", 0)
    allowed = payload.get("allowed", ESSENCE_KEYS)

    if isinstance(count, str):
        if count == "X":
            count = get_x_value(game, player, default=0)
        elif count == "X_plus_2":
            count = get_x_value(game, player, default=0) + 2
        else:
            log(game, f"Unsupported variable gain_wild count: {count}")
            return

    count = int(count)

    if count <= 0:
        return

    chosen = []

    if choices:
        for essence in choices:
            if essence not in allowed:
                raise EffectError(f"Invalid wild essence choice: {essence}")

            player.essence_pool[essence] += 1
            chosen.append(essence)

    elif player.name.lower() == "chikile":
        game.pending_effect_choice = {
            "type": "gain_wild",
            "player": player,
            "count": count,
            "allowed": allowed,
            "chosen": [],
        }
        game.current_phase = "effect_choice"
        return

    else:
        for _ in range(count):
            essence = choose_best_essence_for_ai(player, allowed)
            player.essence_pool[essence] += 1
            chosen.append(essence)

    log(game, f"{player.name} gained wild essence choices: {chosen}.")

def add_to_component(game, player, source_card, payload):
    ensure_stored(source_card)

    essence = payload.get("essence", {})

    for e in ESSENCE_KEYS:
        amount = int(essence.get(e, 0))
        source_card.stored_essence[e] += amount

    log(game, f"{player.name} stored essence on {card_name(source_card)}: {essence}")


def move_from_pool_to_component(game, player, source_card, payload):
    ensure_stored(source_card)

    count = int(payload.get("count", 1))
    allowed = payload.get("allowed", ESSENCE_KEYS)

    moved = []

    for _ in range(count):
        possible = [
            essence for essence in allowed
            if player.essence_pool.get(essence, 0) > 0
        ]

        if not possible:
            break

        essence = choose_best_essence_for_ai(player, possible)

        player.essence_pool[essence] -= 1
        source_card.stored_essence[essence] += 1
        moved.append(essence)

    log(
        game,
        f"{player.name} moved {moved} from pool to {card_name(source_card)}."
    )


def store_wild_on_card(game, player, source_card, payload, choices=None):
    ensure_stored(source_card)

    count = int(payload.get("count", 1))
    allowed = payload.get("allowed", ESSENCE_KEYS)

    chosen = []

    if choices:
        for essence in choices:
            if essence not in allowed:
                raise EffectError(f"Invalid stored essence choice: {essence}")

            source_card.stored_essence[essence] += 1
            chosen.append(essence)

    else:
        for _ in range(count):
            essence = choose_best_essence_for_ai(player, allowed)
            source_card.stored_essence[essence] += 1
            chosen.append(essence)

    log(
        game,
        f"{player.name} stored wild essence on {card_name(source_card)}: {chosen}"
    )

def straighten_target(game, player, source_card, payload, target_card_id=None):
    restriction = payload.get("restriction")
    target = payload.get("target")

    if target == "self":
        source_card.tapped = False
        log(game, f"{player.name} straightened {card_name(source_card)}.")
        return

    chosen = None

    if target_card_id:
        for card in get_controlled_cards(player):
            if card_id(card) == target_card_id:
                chosen = card
                break

        if not chosen:
            raise EffectError("Selected target was not found.")

        if not chosen.tapped:
            raise EffectError(f"{card_name(chosen)} is not tapped.")

        if not matches_restriction(chosen, restriction):
            raise EffectError(f"{card_name(chosen)} is not a valid target.")

    else:
        chosen = find_tapped_target(
            player,
            restriction=restriction,
            exclude_card=source_card
        )

    if not chosen:
        log(game, f"{player.name} had no valid tapped target to straighten.")
        return

    chosen.tapped = False
    log(game, f"{player.name} straightened {card_name(chosen)} using {card_name(source_card)}.")

def untap_self(game, player, source_card):
    source_card.tapped = False
    log(game, f"{player.name} untapped {card_name(source_card)}.")


def tap_additional_target_if_needed(game, player, source_card, cost, target_card_id=None):
    tap_payload = cost.get("tap_additional_target")

    if not tap_payload:
        return True

    restriction = tap_payload.get("restriction")
    target = None

    if target_card_id:
        for card in get_controlled_cards(player):
            if card_id(card) == target_card_id:
                target = card
                break

        if not target:
            log(game, f"Selected additional tap target was not found.")
            return False

        if target.tapped:
            log(game, f"{card_name(target)} is already tapped.")
            return False

        if not matches_restriction(target, restriction):
            log(game, f"{card_name(target)} is not a valid additional tap target.")
            return False

    else:
        target = find_untapped_target(
            player,
            restriction=restriction,
            exclude_card=source_card
        )

    if not target:
        log(
            game,
            f"{player.name} has no valid additional target to tap for {card_name(source_card)}."
        )
        return False

    target.tapped = True

    log(
        game,
        f"{player.name} tapped additional target {card_name(target)} for {card_name(source_card)}."
    )

    return True

def ignore_attack(game, player, payload):
    log(game, f"{player.name} ignored an attack.")


def remove_card_from_owner(game, owner, card):
    zones = [
        owner.played,
        owner.monuments,
        owner.places,
    ]

    for zone in zones:
        if card in zone:
            zone.remove(card)
            owner.discard.append(card)
            log(game, f"{owner.name} destroyed/discarded {card_name(card)}.")
            return True

    return False


def pay_react_cost(game, defender, source_card, cost):
    if not cost:
        return True

    if cost.get("turn_self") and source_card.tapped:
        return False

    if not can_pay_cost(defender, cost):
        return False

    if not pay_cost(defender, cost):
        return False

    discard_cards = int(cost.get("discard_cards", 0) or 0)

    if discard_cards > 0:
        discard_from_hand(game, defender, discard_cards)

    if cost.get("turn_self"):
        source_card.tapped = True

    if cost.get("destroy_self") or cost.get("destroy_owned_artifact"):
        remove_card_from_owner(game, defender, source_card)

    return True


def is_valid_defensive_reaction(card, react_power):
    raw = card.definition.raw_data
    tags = raw.get("tags", [])

    # Dragon attack cards should NOT protect their owner from rival attacks.
    if "dragon" in tags:
        return False

    # If a card itself has attack powers, don't treat it as defense.
    for power in raw.get("powers", []):
        for effect in power.get("effect", []):
            if isinstance(effect, dict) and "attack" in effect:
                return False

    trigger = (
        react_power.get("trigger")
        or react_power.get("timing")
        or react_power.get("reaction_to")
        or react_power.get("condition")
    )

    if trigger:
        trigger_text = str(trigger).lower()

        if (
            "attack" in trigger_text
            or "life_loss" in trigger_text
            or "life loss" in trigger_text
            or "defend" in trigger_text
        ):
            return True

    # fallback: allow clearly defensive cards only
    defensive_tags = [
        "defense",
        "protection",
        "reaction",
        "ignore_attack",
        "ignore_life_loss",
    ]

    return any(tag in tags for tag in defensive_tags)

def try_react_ignore_attack(game, defender, manual=False):
    available_reactions = []

    for card in get_controlled_cards(defender):
        react_powers = card.definition.raw_data.get("react_powers", [])

        for react_power in react_powers:
            if not is_valid_defensive_reaction(card, react_power):
                continue
            effects = react_power.get("effect", [])
            has_ignore = any(
                isinstance(effect, dict) and "ignore_attack" in effect
                for effect in effects
            )

            if not has_ignore:
                continue

            cost = react_power.get("cost", {})

            if cost.get("turn_self") and card.tapped:
                continue

            if not can_pay_cost(defender, cost):
                continue

            available_reactions.append((card, react_power))

    if not available_reactions:
        return False

    is_human = defender.name.lower() == "chikile"

    if manual and is_human:
        print("\nYou are being attacked.")
        print("Available reactions:")
        print("0. Do not react")

        for i, (card, react_power) in enumerate(available_reactions, start=1):
            print(f"{i}. {card_name(card)} reaction power")

        choice = input("Choose reaction: ").strip()

        if choice == "0":
            return False

        if not choice.isdigit():
            return False

        index = int(choice) - 1

        if index < 0 or index >= len(available_reactions):
            return False

        card, react_power = available_reactions[index]

    else:
        card, react_power = available_reactions[0]

    cost = react_power.get("cost", {})

    if not pay_react_cost(game, defender, card, cost):
        return False

    log(game, f"{defender.name} reacted with {card_name(card)} and ignored attack.")
    return True

def lose_other_essences_for_missing_life(game, defender, missing_life, manual=False):
    required_loss = missing_life * 2
    lost = []

    if required_loss <= 0:
        return

    is_human = defender.name.lower() == "chikile"

    if manual and is_human:
        print(f"\nYou are missing {missing_life} life essence.")
        print(f"You must lose up to {required_loss} other essence.")
        print("If you do not have enough essence, the remaining loss is ignored.")
        print("Gold is allowed here.")

        for i in range(required_loss):
            available = [
                essence for essence in ESSENCE_KEYS
                if essence != "life" and defender.essence_pool.get(essence, 0) > 0
            ]

            if not available:
                print("No more essence available. Remaining loss ignored.")
                break

            while True:
                print("Current essence:", defender.essence_pool)
                print("Available:", available)

                choice = input(f"Choose essence to lose {i + 1}: ").strip().lower()

                if choice not in available:
                    print("Invalid essence.")
                    continue

                defender.essence_pool[choice] -= 1
                lost.append(choice)
                break

    else:
        order = ["elan", "calm", "death", "gold"]

        for _ in range(required_loss):
            possible = [
                essence for essence in order
                if defender.essence_pool.get(essence, 0) > 0
            ]

            if not possible:
                break

            essence = possible[0]
            defender.essence_pool[essence] -= 1
            lost.append(essence)

    log(game, f"{defender.name} lost other essences for missing life: {lost}.")

def can_pay_simple(player, cost):
    essence_cost = cost.get("essence", {})

    for essence, amount in essence_cost.items():
        if player.essence_pool.get(essence, 0) < int(amount):
            return False

    return True


def pay_simple(player, cost):
    essence_cost = cost.get("essence", {})

    for essence, amount in essence_cost.items():
        player.essence_pool[essence] -= int(amount)


def resolve_attack(game, attacker, defender, amount, source_card=None, dragon_ignore_cost=None):
    if defender.name.lower() == "chikile":
        game.pending_attack = {
            "attacker": attacker,
            "defender": defender,
            "amount": amount,
            "source_card": source_card,
            "dragon_ignore_cost": dragon_ignore_cost,
        }
        game.current_phase = "attack_choice"
        return

    if dragon_ignore_cost and can_pay_simple(defender, dragon_ignore_cost):
        pay_simple(defender, dragon_ignore_cost)
        log(game, f"{defender.name} ignored attack by paying dragon cost.")
        return

    life_available = defender.essence_pool.get("life", 0)
    pay_life = min(life_available, amount)
    defender.essence_pool["life"] -= pay_life

    missing = amount - pay_life

    for _ in range(missing * 2):
        for essence in ["elan", "calm", "death", "gold"]:
            if defender.essence_pool.get(essence, 0) > 0:
                defender.essence_pool[essence] -= 1
                break

    log(game, f"{defender.name} resolved {amount} life loss.")


def attack(game, attacker, payload, source_card=None):
    attack_type = payload.get("type", "life_loss")
    amount = int(payload.get("amount", payload.get("life_loss", 0)))

    if attack_type != "life_loss":
        log(game, f"Unsupported attack type skipped: {payload}")
        return

    if amount <= 0:
        return

    dragon_ignore_cost = payload.get("dragon_ignore_cost")

    for defender in game.players:
        if defender is attacker:
            continue

        if defender.passed:
            log(game, f"{defender.name} has passed and cannot be attacked.")
            continue

        log(game, f"{attacker.name} attacked {defender.name} for {amount} life loss.")

        resolve_attack(
            game,
            attacker,
            defender,
            amount,
            source_card=source_card,
            dragon_ignore_cost=dragon_ignore_cost,
        )
def vault_collect_choice(game, player, source_card):
    choose_vault_collect(game, player, source_card)

def windup_collect_plus2_each_type(game, player, source_card):
    choose_windup_collect(game, player, source_card)


def upkeep_choice(game, player, source_card, payload):
    option_pay = payload.get("option_pay", {})
    option_else = payload.get("option_else", {})

    if option_pay and can_pay_cost(player, option_pay):
        pay_cost(player, option_pay)
        log(game, f"{player.name} paid upkeep for {card_name(source_card)}.")
        return

    if option_else.get("turn_self"):
        source_card.tapped = True
        log(game, f"{player.name} could not pay upkeep; {card_name(source_card)} was tapped.")


def should_keep_stored_essence_on_card(card):
    raw = card.definition.raw_data

    vp = raw.get("vp", {})
    conditional_vp = vp.get("conditional", [])

    for condition in conditional_vp:
        if "per_stored_essence" in condition:
            return True

        if "per_stored_total" in condition:
            return True

        if "per_stored_types" in condition:
            return True

    collect_entries = raw.get("collect", [])

    for entry in collect_entries:
        for effect in entry.get("effect", []):
            if "vault_collect_choice" in effect:
                return True

            if "windup_collect_plus2_each_type" in effect:
                return True

    return False


def collect_stored_essence_from_card(game, player, card):
    ensure_stored(card)

    total_stored = sum(card.stored_essence.values())

    if total_stored <= 0:
        return

    is_human = player.name.lower() == "chikile"

    if is_human:
        print(f"\n{card_name(card)} has stored essence:")
        print(card.stored_essence)
        print("1. Take stored essence into your pool")
        print("2. Keep essence on the card")

        choice = input("Choose: ").strip()

        if choice == "1":
            collect_all_stored_to_pool(game, player, card)
        else:
            log(game, f"{player.name} kept stored essence on {card_name(card)}.")

        return

    # AI choice
    if should_keep_stored_essence_on_card(card):
        log(game, f"{player.name} kept stored essence on {card_name(card)}.")
    else:
        collect_all_stored_to_pool(game, player, card)

def all_rivals_gain(game, player, payload):
    essence = payload.get("essence", {})

    for rival in game.players:
        if rival is player:
            continue

        add_essence(rival, essence)
        log(game, f"{rival.name} gained rival essence: {essence}")


def gain_equal_to_rival_essence(game, player, payload):
    gain_essence = payload.get("gain_essence")
    rival_essence = payload.get("rival_essence")

    if not gain_essence or not rival_essence:
        return

    max_rival_amount = 0

    for rival in game.players:
        if rival is player:
            continue

        max_rival_amount = max(
            max_rival_amount,
            rival.essence_pool.get(rival_essence, 0)
        )

    player.essence_pool[gain_essence] += max_rival_amount

    log(
        game,
        f"{player.name} gained {max_rival_amount} {gain_essence} equal to rival {rival_essence}."
    )


def jump_to_phase(game, player, source_card, payload):
    phase = payload.get("phase")

    if phase == "victory_check":
        game.force_victory_check = True
        log(game, f"{player.name} used {card_name(source_card)} to jump to victory check.")
    else:
        log(game, f"Unsupported jump_to_phase skipped: {payload}")

def get_x_value(game, player, default=1):
    return getattr(game, "current_x_value", default)


def gain_gold_equal_to_paid_minus(game, player, source_card, minus_value):
    x_value = get_x_value(game, player, default=0)
    gold_gain = max(0, x_value - int(minus_value))

    player.essence_pool["gold"] += gold_gain

    log(
        game,
        f"{player.name} gained {gold_gain} gold from {card_name(source_card)}."
    )


def spend_from_component_then_gain_gold(game, player, source_card, payload):
    ensure_stored(source_card)

    essence_cost = payload.get("essence", {})
    gain_gold = payload.get("gain_gold", 0)

    if isinstance(gain_gold, str) and gain_gold == "X":
        gain_gold = get_x_value(game, player, default=0)

    for essence in ESSENCE_KEYS:
        amount = int(essence_cost.get(essence, 0))

        if amount <= 0:
            continue

        if source_card.stored_essence.get(essence, 0) < amount:
            raise EffectError(
                f"{card_name(source_card)} does not have enough stored {essence}."
            )

        source_card.stored_essence[essence] -= amount

    player.essence_pool["gold"] += int(gain_gold)

    log(
        game,
        f"{player.name} spent stored essence from {card_name(source_card)} "
        f"and gained {gain_gold} gold."
    )


def collect_all_stored_to_pool(game, player, source_card):
    ensure_stored(source_card)

    collected = {}

    for essence in ESSENCE_KEYS:
        amount = source_card.stored_essence.get(essence, 0)

        if amount > 0:
            player.essence_pool[essence] += amount
            collected[essence] = amount
            source_card.stored_essence[essence] = 0

    if collected:
        log(
            game,
            f"{player.name} collected stored essence from {card_name(source_card)}: {collected}."
        )

    return collected


def should_take_stored_now(player, source_card):
    """
    Simple AI rule:
    take stored essence if player is low on resources,
    otherwise keep special storage cards growing/scoring.
    """
    if player.name.lower() == "chikile":
        return False

    pool_total = sum(player.essence_pool.get(e, 0) for e in ESSENCE_KEYS)

    if pool_total <= 3:
        return True

    return False


def choose_vault_collect(game, player, source_card):
    ensure_stored(source_card)

    gold_on_card = source_card.stored_essence.get("gold", 0)

    if gold_on_card <= 0:
        return

    is_human = player.name.lower() == "chikile"

    if is_human:
        print(f"\nVault has {gold_on_card} gold stored.")
        print("1. Take stored gold into your pool")
        print(f"2. Keep gold on Vault and gain {gold_on_card * 2} non-gold essence")

        choice = input("Choose: ").strip()

        if choice == "1":
            collect_all_stored_to_pool(game, player, source_card)
            return

        count = gold_on_card * 2
        allowed = ["elan", "life", "calm", "death"]

        gained = []

        print(f"\nChoose {count} non-gold essence to gain:")

        for i in range(count):
            while True:
                essence = input(f"Choose essence {i + 1}: ").strip().lower()

                if essence in allowed:
                    player.essence_pool[essence] += 1
                    gained.append(essence)
                    break

                print("Invalid essence.")

        log(
            game,
            f"{player.name} kept gold on Vault and gained essence: {gained}."
        )

    else:
        # AI keeps Vault gold if it is not desperate, and gains useful essence.
        count = gold_on_card * 2
        allowed = ["elan", "life", "calm", "death"]
        gained = []

        for _ in range(count):
            essence = choose_best_essence_for_ai(player, allowed)
            player.essence_pool[essence] += 1
            gained.append(essence)

        log(
            game,
            f"{player.name} kept gold on Vault and gained essence: {gained}."
        )



def choose_windup_collect(game, player, source_card):
    ensure_stored(source_card)

    total = sum(source_card.stored_essence.values())

    if total <= 0:
        return

    is_human = player.name.lower() == "chikile"

    if is_human:
        print(f"\nWindup Man has stored essence: {source_card.stored_essence}")
        print("1. Take all stored essence into your pool")
        print("2. Keep it and add +2 to each stored essence type")

        choice = input("Choose: ").strip()

        if choice == "1":
            collect_all_stored_to_pool(game, player, source_card)
            return

    for essence in ESSENCE_KEYS:
        if source_card.stored_essence.get(essence, 0) > 0:
            source_card.stored_essence[essence] += 2

    log(
        game,
        f"{player.name} kept essence on Windup Man and added +2 to each stored type."
    )

def card_cost_total(card):
    cost = card.definition.raw_data.get("placement_cost") or {}
    essence = cost.get("essence", {})
    total = sum(int(essence.get(e, 0)) for e in ESSENCE_KEYS)

    wild = cost.get("wild")

    if isinstance(wild, int):
        total += wild
    elif isinstance(wild, dict):
        count = wild.get("count", 0)
        if isinstance(count, int):
            total += count

    return total


def choose_owned_artifact_to_destroy(player, allow_self_card=None):
    candidates = []

    for card in player.played:
        if allow_self_card is not None and card is allow_self_card:
            candidates.append(card)
        elif card is not allow_self_card:
            candidates.append(card)

    if not candidates:
        return None

    if player.name.lower() == "chikile":
        print("\nChoose artifact to destroy:")
        print("0. Cancel")

        for i, card in enumerate(candidates, start=1):
            print(f"{i}. {card_name(card)}")

        choice = input("Choose: ").strip()

        if choice == "0":
            return None

        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(candidates):
                return candidates[index]

        return None

    return min(candidates, key=card_cost_total)


def destroy_card(game, player, card):
    zones = [player.played, player.monuments, player.places]

    for zone in zones:
        if card in zone:
            zone.remove(card)
            player.discard.append(card)
            log(game, f"{player.name} destroyed {card_name(card)}.")
            return card

    return None


def gain_destroyed_cost_plus(game, player, destroyed_card, plus, allowed):
    if not destroyed_card:
        return

    gain_count = card_cost_total(destroyed_card) + int(plus)
    gained = []

    for _ in range(gain_count):
        essence = choose_best_essence_for_ai(player, allowed)
        player.essence_pool[essence] += 1
        gained.append(essence)

    log(
        game,
        f"{player.name} gained essence from destroyed card cost + {plus}: {gained}."
    )


def gain_discarded_card_cost(game, player, discarded_card, allowed):
    if not discarded_card:
        return

    gain_count = card_cost_total(discarded_card)
    gained = []

    for _ in range(gain_count):
        essence = choose_best_essence_for_ai(player, allowed)
        player.essence_pool[essence] += 1
        gained.append(essence)

    log(
        game,
        f"{player.name} gained essence from discarded card cost: {gained}."
    )


def play_card_from_hand_effect(
    game,
    player,
    payload,
):
    restriction = payload.get(
        "restriction"
    )

    pay_placement_cost = payload.get(
        "pay_placement_cost",
        True,
    )

    discount = int(
        payload.get(
            "discount",
            0,
        )
        or 0
    )

    candidates = [
        card
        for card in player.hand
        if matches_restriction(
            card,
            restriction,
        )
    ]

    if not candidates:
        log(
            game,
            f"{player.name} has no valid "
            "card in hand to play."
        )
        return False

    # ---------------------------------
    # Helper: calculate discounted cost
    # ---------------------------------
    def get_discounted_cost(card):
        import copy

        original_cost = (
            card.definition.raw_data.get(
                "placement_cost"
            )
            or {}
        )

        cost = copy.deepcopy(
            original_cost
        )

        if discount <= 0:
            return cost

        essence_cost = cost.setdefault(
            "essence",
            {},
        )

        remaining_discount = discount

        # Prefer reducing expensive
        # non-gold essence first.
        essence_order = [
            "death",
            "life",
            "calm",
            "elan",
            "gold",
        ]

        while remaining_discount > 0:
            possible = [
                essence
                for essence in essence_order
                if int(
                    essence_cost.get(
                        essence,
                        0,
                    )
                ) > 0
            ]

            if not possible:
                break

            # Reduce the essence the player
            # currently has least of first.
            chosen = min(
                possible,
                key=lambda essence:
                    player.essence_pool.get(
                        essence,
                        0,
                    ),
            )

            essence_cost[chosen] -= 1
            remaining_discount -= 1

        # If fixed essence is already zero,
        # discount wild cost as well.
        wild = cost.get("wild")

        if (
            remaining_discount > 0
            and wild
        ):
            if isinstance(wild, int):
                reduced = min(
                    wild,
                    remaining_discount,
                )

                cost["wild"] = (
                    wild - reduced
                )

                remaining_discount -= (
                    reduced
                )

            elif isinstance(wild, dict):
                count = wild.get(
                    "count",
                    0,
                )

                if isinstance(count, int):
                    reduced = min(
                        count,
                        remaining_discount,
                    )

                    wild["count"] = (
                        count - reduced
                    )

        return cost

    # ---------------------------------
    # Helper: check if player can pay
    # ---------------------------------
    def can_pay_discounted_cost(card):
        if not pay_placement_cost:
            return True

        cost = get_discounted_cost(
            card
        )

        return can_pay_cost(
            player,
            cost,
        )

    # Only keep Dragons that are
    # actually playable after discount.
    affordable_candidates = [
        card
        for card in candidates
        if can_pay_discounted_cost(card)
    ]

    if not affordable_candidates:
        log(
            game,
            f"{player.name} has no Dragon "
            f"they can afford after the "
            f"{discount} essence discount."
        )

        return False

    # ---------------------------------
    # Choose Dragon
    # ---------------------------------

    if player.name.lower() == "chikile":
        # Temporary automatic choice.
        # Later this should become a GUI card picker.
        chosen = max(
            affordable_candidates,
            key=card_cost_total,
        )

    else:
        # AI chooses the most valuable /
        # normally most expensive Dragon.
        chosen = max(
            affordable_candidates,
            key=card_cost_total,
        )

    # ---------------------------------
    # Pay discounted placement cost
    # ---------------------------------

    if pay_placement_cost:
        discounted_cost = (
            get_discounted_cost(
                chosen
            )
        )

        if discounted_cost:
            wild_choices = None

            wild = discounted_cost.get(
                "wild"
            )

            if wild:
                if isinstance(wild, int):
                    wild_count = wild
                    allowed = ESSENCE_KEYS

                else:
                    wild_count = wild.get(
                        "count",
                        0,
                    )

                    allowed = wild.get(
                        "allowed",
                        ESSENCE_KEYS,
                    )

                if (
                    isinstance(
                        wild_count,
                        int,
                    )
                    and wild_count > 0
                ):
                    wild_choices = []

                    temp_pool = dict(
                        player.essence_pool
                    )

                    fixed = (
                        discounted_cost.get(
                            "essence",
                            {},
                        )
                    )

                    for essence, amount in (
                        fixed.items()
                    ):
                        temp_pool[essence] = (
                            temp_pool.get(
                                essence,
                                0,
                            )
                            - int(amount)
                        )

                    for _ in range(
                        wild_count
                    ):
                        possible = [
                            essence
                            for essence in allowed
                            if temp_pool.get(
                                essence,
                                0,
                            ) > 0
                        ]

                        if not possible:
                            log(
                                game,
                                f"{player.name} "
                                "could not complete "
                                "Dragon payment."
                            )
                            return False

                        essence = max(
                            possible,
                            key=lambda e:
                                temp_pool.get(
                                    e,
                                    0,
                                ),
                        )

                        temp_pool[essence] -= 1
                        wild_choices.append(
                            essence
                        )

            paid = pay_cost(
                player,
                discounted_cost,
                wild_choices=wild_choices,
            )

            if not paid:
                log(
                    game,
                    f"{player.name} could not "
                    f"pay discounted cost for "
                    f"{card_name(chosen)}."
                )

                return False

    # ---------------------------------
    # Actually play Dragon
    # ---------------------------------

    player.hand.remove(
        chosen
    )

    player.played.append(
        chosen
    )

    log(
        game,
        f"{player.name} played "
        f"{card_name(chosen)} from hand "
        f"with a {discount} essence discount."
    )

    # Resolve any on-place effects.
    collect_list = (
        chosen.definition.raw_data.get(
            "collect",
            [],
        )
    )

    for entry in collect_list:
        if (
            entry.get("timing")
            == "on_place"
        ):
            apply_effects(
                game,
                player,
                chosen,
                entry.get(
                    "effect",
                    [],
                ),
            )

    return True
def play_card_from_discard_effect(game, player, payload):
    if not player.discard:
        log(game, f"{player.name} has no discard card to play.")
        return

    chosen = player.discard[0]

    if player.name.lower() == "chikile":
        print("\nChoose card from discard to play:")
        print("0. Cancel")

        for i, card in enumerate(player.discard, start=1):
            print(f"{i}. {card_name(card)}")

        choice = input("Choose: ").strip()

        if choice == "0":
            return

        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(player.discard):
                chosen = player.discard[index]

    cost = chosen.definition.raw_data.get("placement_cost")

    if payload.get("pay_placement_cost", True):
        if cost and not pay_cost(player, cost):
            log(game, f"{player.name} could not pay cost for {card_name(chosen)}.")
            return

    player.discard.remove(chosen)
    player.played.append(chosen)

    log(game, f"{player.name} played {card_name(chosen)} from discard.")

def choose_deck_source(game, player, source_name):
    if source_name == "your_deck":
        return "your_deck"

    if source_name == "monument_deck":
        return "monument_deck"

    if source_name == "your_deck_or_monument_deck":
        if player.name.lower() == "chikile":
            game.pending_deck_choice = {
                "type": "choose_deck_source",
                "player": player,
                "source_name": source_name,
            }
            game.current_phase = "deck_choice"
            return None

        if len(player.deck_hidden) <= 1 and game.monument_deck:
            return "monument_deck"

        return "your_deck"

    return "your_deck"


def get_deck_list(game, player, deck_source):
    if deck_source == "monument_deck":
        return game.monument_deck

    return player.deck_hidden


def prepare_deck_for_look(game, player, deck_source, count):
    deck = get_deck_list(game, player, deck_source)

    if deck_source != "your_deck":
        return deck

    while len(deck) < count and player.discard:
        random.shuffle(player.discard)

        deck.extend(player.discard)
        player.discard = []

        game.game_log.append(
            f"{player.name} shuffled discard pile into draw pile for deck look."
        )

    return deck

def look_at_top_cards(game, player, source_card, payload):
    source_name = payload.get("from", "your_deck")
    count = int(payload.get("count", 1))

    deck_source = choose_deck_source(game, player, source_name)

    if deck_source is None:
        game.pending_deck_choice["source_card"] = source_card
        game.pending_deck_choice["payload"] = payload
        return

    deck = prepare_deck_for_look(
            game,
            player,
            deck_source,
            count
        )

    looked = deck[:count]

    game.current_look_context = {
        "player_name": player.name,
        "source_card_id": card_id(source_card),
        "deck_source": deck_source,
        "cards": looked,
    }

    if player.name.lower() == "chikile":
        print(f"\n{card_name(source_card)} looked at top {len(looked)} card(s) from {deck_source}:")
        for i, card in enumerate(looked, start=1):
            print(f"{i}. {card_name(card)}")

    log(
        game,
        f"{player.name} looked at top {len(looked)} card(s) from {deck_source}."
    )


def reorder_top_cards(game, player, source_card, payload):
    context = getattr(game, "current_look_context", None)

    if not context:
        log(game, "No look context found for reorder_top_cards.")
        return

    cards = context.get("cards", [])

    if not cards:
        return

    if player.name.lower() == "chikile":
        game.pending_deck_choice = {
            "type": "reorder_top_cards",
            "player": player,
            "source_card": source_card,
            "payload": payload,
            "context": context,
            "cards": cards,
            "selected_order": [],
        }
        game.current_phase = "deck_choice"
        return

    else:
        # AI: keep strongest card first
        context["cards"] = sorted(
            cards,
            key=lambda c: c.definition.raw_data.get("vp", {}).get("base", 0),
            reverse=True
        )

    log(game, f"{player.name} reordered top cards using {card_name(source_card)}.")


def put_back_top_cards(game, player, source_card, payload):
    context = getattr(game, "current_look_context", None)

    if not context:
        log(game, "No look context found for put_back_top_cards.")
        return

    deck_source = context.get("deck_source", "your_deck")
    cards = context.get("cards", [])

    deck = get_deck_list(game, player, deck_source)

    # remove the same cards from the current top area first
    for card in cards:
        if card in deck:
            deck.remove(card)

    # put reordered cards back on top
    for card in reversed(cards):
        deck.insert(0, card)

    game.current_look_context = None

    log(
        game,
        f"{player.name} put {len(cards)} card(s) back on top of {deck_source}."
    )
def apply_single_effect(game, player, source_card, effect, target_choices=None, gain_wild_choices=None, store_wild_choices=None):
    if not isinstance(effect, dict):
        return

    if "gain_to_pool" in effect:
        add_essence(player, effect["gain_to_pool"])
        log(game, f"{player.name} gained essence: {effect['gain_to_pool']}")

    elif "gain_wild" in effect:
        gain_wild(game, player, effect["gain_wild"], choices=gain_wild_choices)

    elif "draw" in effect:
        payload = effect["draw"]
        draw_cards(game, player, int(payload.get("count", 1)))

    elif "discard" in effect:
        payload = effect["discard"]
        discard_from_hand(game, player, int(payload.get("count", 1)))

    elif "add_to_component" in effect:
        add_to_component(game, player, source_card, effect["add_to_component"])

    elif "store_wild_on_card" in effect:
        store_wild_on_card(
            game,
            player,
            source_card,
            effect["store_wild_on_card"],
            choices=store_wild_choices
        )

    elif "move_from_pool_to_component" in effect:
        move_from_pool_to_component(
            game,
            player,
            source_card,
            effect["move_from_pool_to_component"]
        )

    
    elif "straighten_target" in effect:
        target_card_id = None

        if target_choices:
            target_card_id = target_choices.get("straighten_target")

        straighten_target(
            game,
            player,
            source_card,
            effect["straighten_target"],
            target_card_id=target_card_id
        )

    elif "untap_self" in effect:
        untap_self(game, player, source_card)

    elif "ignore_attack" in effect:
        ignore_attack(game, player, effect["ignore_attack"])

    elif "attack" in effect:
        attack(
            game,
            player,
            effect["attack"],
            source_card=source_card,
        )

    elif "vault_collect_choice" in effect:
        vault_collect_choice(game, player, source_card)

    elif "windup_collect_plus2_each_type" in effect:
        windup_collect_plus2_each_type(game, player, source_card)

    elif "upkeep_choice" in effect:
        upkeep_choice(game, player, source_card, effect["upkeep_choice"])

    elif "all_rivals_gain" in effect:
        all_rivals_gain(game, player, effect["all_rivals_gain"])

    elif "gain_equal_to_rival_essence" in effect:
        gain_equal_to_rival_essence(game, player, effect["gain_equal_to_rival_essence"])

    elif "jump_to_phase" in effect:
        jump_to_phase(game, player, source_card, effect["jump_to_phase"])


    elif "gain_gold_equal_to_paid_minus" in effect:
        gain_gold_equal_to_paid_minus(
            game,
            player,
            source_card,
            effect["gain_gold_equal_to_paid_minus"]
        )

    elif "spend_from_component_then_gain_gold" in effect:
        spend_from_component_then_gain_gold(
            game,
            player,
            source_card,
            effect["spend_from_component_then_gain_gold"]
        )

    elif "play_card_from_hand" in effect:
        play_card_from_hand_effect(
            game,
            player,
            effect["play_card_from_hand"]
        )

    elif "play_card_from_discard" in effect:
        play_card_from_discard_effect(
            game,
            player,
            effect["play_card_from_discard"]
        )

    elif "gain_equals_destroyed_artifact_cost_plus" in effect:
        payload = effect["gain_equals_destroyed_artifact_cost_plus"]
        destroyed = choose_owned_artifact_to_destroy(player, allow_self_card=source_card)

        if destroyed:
            destroyed_card = destroy_card(game, player, destroyed)
            gain_destroyed_cost_plus(
                game,
                player,
                destroyed_card,
                payload.get("plus", 0),
                payload.get("allowed", ["elan", "life", "calm", "death"])
            )

    elif "gain_equals_destroyed_card_cost_plus" in effect:
        payload = effect["gain_equals_destroyed_card_cost_plus"]
        destroyed = choose_owned_artifact_to_destroy(player, allow_self_card=source_card)

        if destroyed:
            destroyed_card = destroy_card(game, player, destroyed)
            gain_destroyed_cost_plus(
                game,
                player,
                destroyed_card,
                payload.get("plus", 0),
                payload.get("allowed", ["elan", "life", "calm", "death"])
            )

    elif "gain_equals_discarded_card_cost" in effect:
        payload = effect["gain_equals_discarded_card_cost"]

        if player.hand:
            discarded = player.hand.pop(0)
            player.discard.append(discarded)

            gain_discarded_card_cost(
                game,
                player,
                discarded,
                payload.get("allowed", ["elan", "life", "calm", "death"])
            )

    elif "store_on_target_card" in effect:
        payload = effect["store_on_target_card"]
        allowed = payload.get("essence_choice", ESSENCE_KEYS)
        count = int(payload.get("count", 1))

        targets = get_controlled_cards(player)

        if not targets:
            return

        target = targets[0]

        if player.name.lower() == "chikile":
            print("\nChoose target card to store essence:")
            for i, card in enumerate(targets, start=1):
                print(f"{i}. {card_name(card)}")

            choice = input("Choose: ").strip()

            if choice.isdigit():
                index = int(choice) - 1
                if 0 <= index < len(targets):
                    target = targets[index]

        ensure_stored(target)

        for _ in range(count):
            essence = choose_best_essence_for_ai(player, allowed)
            target.stored_essence[essence] += 1

        log(game, f"{player.name} stored essence on {card_name(target)}.")
    
    
    elif "look_at_top_cards" in effect:
        look_at_top_cards(
            game,
            player,
            source_card,
            effect["look_at_top_cards"]
        )

    elif "reorder_top_cards" in effect:
        reorder_top_cards(
            game,
            player,
            source_card,
            effect["reorder_top_cards"]
        )

    elif "put_back_top_cards" in effect:
        put_back_top_cards(
            game,
            player,
            source_card,
            effect["put_back_top_cards"]
        )
    
    elif "convert_one_essence_type_to_gold" in effect:
        convert_one_essence_type_to_gold(
            game,
            player,
            source_card,
            effect["convert_one_essence_type_to_gold"]
        )


    else:
        log(game, f"Unsupported effect skipped: {effect}")


def convert_one_essence_type_to_gold(game, player, source_card, payload):
    """
    Generic effect:
    - optional stored essence cost from the source card
    - optional pool essence cost
    - then choose ONE essence type from player pool
    - spend any amount of that one type
    - gain same amount of gold

    Used by:
    - Athanor
    - Philosopher's Stone
    - similar cards
    """

    ensure_stored(source_card)

    stored_cost = payload.get("stored_cost", {})
    pool_cost = payload.get("pool_cost", {})
    allowed_convert = payload.get(
        "allowed_convert",
        ["elan", "life", "calm", "death"]
    )

    # 1. Pay stored cost from source card
    for essence, amount in stored_cost.items():
        amount = int(amount)

        if source_card.stored_essence.get(essence, 0) < amount:
            raise EffectError(
                f"{card_name(source_card)} needs {amount} stored {essence}."
            )

    for essence, amount in stored_cost.items():
        source_card.stored_essence[essence] -= int(amount)

    # 2. Pay normal pool cost
    for essence, amount in pool_cost.items():
        amount = int(amount)

        if player.essence_pool.get(essence, 0) < amount:
            raise EffectError(
                f"{player.name} does not have enough {essence}."
            )

    for essence, amount in pool_cost.items():
        player.essence_pool[essence] -= int(amount)

    # 3. Choose ONE essence type to convert
    is_human = player.name.lower() == "chikile"

    if is_human:
        game.pending_effect_choice = {
            "type": "convert_to_gold",
            "player": player,
            "source_card": source_card,
            "allowed": allowed_convert,
            "selected_essence": None,
        }
        game.current_phase = "effect_choice"
        return
    else:
        essence_type = max(
            allowed_convert,
            key=lambda e: player.essence_pool.get(e, 0)
        )
        amount = player.essence_pool.get(essence_type, 0)

    # 4. Convert selected essence into gold
    player.essence_pool[essence_type] -= amount
    player.essence_pool["gold"] += amount

    log(
        game,
        f"{player.name} used {card_name(source_card)}: converted "
        f"{amount} {essence_type} into {amount} gold."
    )

def apply_effects(game, player, source_card, effects, target_choices=None, gain_wild_choices=None,store_wild_choices=None):
    for effect in effects:
        apply_single_effect(
            game,
            player,
            source_card,
            effect,
            target_choices=target_choices,
            gain_wild_choices=gain_wild_choices,
            store_wild_choices=store_wild_choices
        )

def run_collect_effects(game, player):
    for card in get_controlled_cards(player):
        collect_entries = card.definition.raw_data.get("collect", [])

        for collect_entry in collect_entries:
            timing = collect_entry.get("timing")

            if timing != "collect_phase":
                continue

            effects = collect_entry.get("effect", [])
            apply_effects(game, player, card, effects)

        collect_stored_essence_from_card(game, player, card)