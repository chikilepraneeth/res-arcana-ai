# collection_phase.py
from models import ESSENCE_KEYS
from effect_engine import (
    add_essence,
    draw_cards,
    collect_all_stored_to_pool
)

NON_GOLD = ["elan", "life", "calm", "death"]


def card_name(card):
    return (
        getattr(card.definition, "name", None)
        or card.definition.raw_data.get("name_en")
        or card.definition.raw_data.get("id")
    )


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


def ensure_stored(card):
    if not hasattr(card, "stored_essence") or card.stored_essence is None:
        card.stored_essence = {k: 0 for k in ESSENCE_KEYS}

    for e in ESSENCE_KEYS:
        card.stored_essence.setdefault(e, 0)


def stored_total(card):
    ensure_stored(card)
    return sum(card.stored_essence.values())


def card_has_special_storage_collect(card):
    for entry in card.definition.raw_data.get("collect", []):
        if entry.get("timing") != "collect_phase":
            continue

        for effect in entry.get("effect", []):
            if "vault_collect_choice" in effect:
                return True
            if "windup_collect_plus2_each_type" in effect:
                return True

    return False


def start_collection_phase(game):
    game.collect_queue = []
    game.pending_collect_choice = None
    game.collect_phase_started = True

    game.game_log.append(f"=== COLLECT PHASE: ROUND {game.round_no} ===")

    for player in game.players:
        game.game_log.append(f"Checking collection cards for {player.name}.")
        for card in get_controlled_cards(player):
            game.game_log.append(f"Checking collect on {card_name(card)}.")
            collect_entries = card.definition.raw_data.get("collect", [])

            for entry in collect_entries:
                if entry.get("timing") != "collect_phase":
                    continue

                for effect in entry.get("effect", []):
                    game.collect_queue.append({
                        "type": "effect",
                        "player": player,
                        "card": card,
                        "effect": effect,
                    })

            if stored_total(card) > 0 and not card_has_special_storage_collect(card):
                game.collect_queue.append({
                    "type": "stored_choice",
                    "player": player,
                    "card": card,
                })

    process_next_collection(game)


def process_next_collection(game):
    while game.collect_queue:
        item = game.collect_queue.pop(0)

        player = item["player"]
        card = item["card"]

        if player.name.lower() != "chikile":
            resolve_ai_collection(game, item)
            continue

        if item["type"] == "stored_choice":
            game.pending_collect_choice = item
            game.current_phase = "collect_choice"
            game.game_log.append(f"{card_name(card)} has stored essence.")
            return

        effect = item["effect"]

        if "gain_to_pool" in effect:
            add_essence(player, effect["gain_to_pool"])
            game.game_log.append(
                f"{player.name} collected {effect['gain_to_pool']} from {card_name(card)}."
            )

        elif "draw" in effect:
            count = int(effect["draw"].get("count", 1))
            draw_cards(game, player, count)

        elif "gain_wild" in effect:
            payload = effect["gain_wild"]
            count = payload.get("count", 1)

            game.pending_collect_choice = {
                "type": "gain_wild",
                "player": player,
                "card": card,
                "effect": effect,
                "count": count,
                "chosen": [],
            }
            game.current_phase = "collect_choice"
            return

        elif "vault_collect_choice" in effect:
            ensure_stored(card)
            gold = card.stored_essence.get("gold", 0)

            if gold <= 0:
                continue

            game.pending_collect_choice = {
                "type": "vault_choice",
                "player": player,
                "card": card,
                "gold": gold,
                "chosen": [],
                "count": gold * 2,
            }
            game.current_phase = "collect_choice"
            return

        elif "windup_collect_plus2_each_type" in effect:
            if stored_total(card) <= 0:
                continue

            game.pending_collect_choice = {
                "type": "windup_choice",
                "player": player,
                "card": card,
            }
            game.current_phase = "collect_choice"
            return
        elif "choose_essence" in effect:
            payload = effect["choose_essence"]
            allowed = payload.get("allowed", ["elan", "life", "calm", "death"])
            count = int(payload.get("count", 1))

            game.pending_collect_choice = {
                "type": "choose_essence",
                "player": player,
                "card": card,
                "effect": effect,
                "allowed": allowed,
                "count": count,
                "chosen": [],
            }

            game.current_phase = "collect_choice"
            game.game_log.append(
                f"{card_name(card)} needs an essence choice."
            )
            return
        else:
            game.game_log.append(
                f"Unsupported collection effect skipped on {card_name(card)}: {effect}"
            )

    game.pending_collect_choice = None
    game.collect_phase_started = False
    game.current_phase = "action"
    import pygame

    game.phase_banner_title = "ACTION PHASE"
    game.phase_banner_message = "Players now take actions until both pass."
    game.phase_banner_until = pygame.time.get_ticks() + 5000
    game.game_log.append("Collect phase finished.")
    game.game_log.append(f"=== ROUND {game.round_no} ACTION PHASE ===")


def resolve_ai_collection(game, item):
    player = item["player"]
    card = item["card"]

    if item["type"] == "stored_choice":
        collect_all_stored_to_pool(game, player, card)
        return

    effect = item["effect"]

    if "gain_to_pool" in effect:
        add_essence(player, effect["gain_to_pool"])

    elif "draw" in effect:
        draw_cards(game, player, int(effect["draw"].get("count", 1)))

    elif "gain_wild" in effect:
        payload = effect["gain_wild"]
        count = int(payload.get("count", 1))
        allowed = payload.get("allowed", NON_GOLD)

        for i in range(count):
            choice = allowed[i % len(allowed)]
            player.essence_pool[choice] += 1

    elif "vault_collect_choice" in effect:
        ensure_stored(card)
        gold = card.stored_essence.get("gold", 0)
        for i in range(gold * 2):
            player.essence_pool[NON_GOLD[i % 4]] += 1

    elif "windup_collect_plus2_each_type" in effect:
        ensure_stored(card)
        for e in ESSENCE_KEYS:
            if card.stored_essence.get(e, 0) > 0:
                card.stored_essence[e] += 2


def resolve_collection_action(game, action):
    choice = getattr(game, "pending_collect_choice", None)

    if not choice:
        return

    player = choice["player"]
    card = choice["card"]
    choice_type = choice["type"]
    if choice_type == "choose_essence" and action.startswith("collection_gain_"):
        essence = action.replace("collection_gain_", "")

        allowed = choice.get("allowed", ["elan", "life", "calm", "death"])

        if essence not in allowed:
            game.game_log.append(f"Invalid essence choice: {essence}")
            return

        player.essence_pool[essence] += 1
        choice["chosen"].append(essence)

        if len(choice["chosen"]) >= choice["count"]:
            game.game_log.append(
                f"{player.name} gained {choice['chosen']} from {card_name(card)}."
            )

            game.pending_collect_choice = None
            game.current_phase = "collect"
            process_next_collection(game)

        return

    if action == "collection_take_stored":
        collect_all_stored_to_pool(game, player, card)
        game.pending_collect_choice = None
        game.current_phase = "collect"
        process_next_collection(game)
        return

    if action == "collection_keep_stored":
        game.game_log.append(f"{player.name} kept essence on {card_name(card)}.")
        game.pending_collect_choice = None
        game.current_phase = "collect"
        process_next_collection(game)
        return

    if choice_type == "vault_choice":
        if action == "collection_vault_take_gold":
            collect_all_stored_to_pool(game, player, card)
            game.pending_collect_choice = None
            game.current_phase = "collect"
            process_next_collection(game)
            return

        if action.startswith("collection_gain_"):
            essence = action.replace("collection_gain_", "")
            player.essence_pool[essence] += 1
            choice["chosen"].append(essence)

            if len(choice["chosen"]) >= choice["count"]:
                game.game_log.append(
                    f"{player.name} kept gold on Vault and gained {choice['chosen']}."
                )
                game.pending_collect_choice = None
                game.current_phase = "collect"
                process_next_collection(game)

            return

    if choice_type == "windup_choice":
        if action == "collection_windup_take":
            collect_all_stored_to_pool(game, player, card)

        elif action == "collection_windup_keep":
            ensure_stored(card)
            for e in ESSENCE_KEYS:
                if card.stored_essence.get(e, 0) > 0:
                    card.stored_essence[e] += 2

            game.game_log.append(
                f"{player.name} kept essence on Windup Man and added +2 to each stored type."
            )

        game.pending_collect_choice = None
        game.current_phase = "collect"
        process_next_collection(game)
        return

    if choice_type == "gain_wild" and action.startswith("collection_gain_"):
        essence = action.replace("collection_gain_", "")
        player.essence_pool[essence] += 1
        choice["chosen"].append(essence)

        if len(choice["chosen"]) >= choice["count"]:
            game.pending_collect_choice = None
            game.current_phase = "collect"
            process_next_collection(game)