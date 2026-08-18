# src/opponent_model.py

def ensure_opponent_model(game):
    if not hasattr(game, "opponent_model"):
        game.opponent_model = {
            "death": 0,
            "dragon": 0,
            "gold": 0,
            "life": 0,
            "storage": 0,
            "place_rush": 0,
            "monument_rush": 0,
            "last_human_moves": [],
        }


def update_from_human_move(game, move_type, card_name=None, essence_choices=None):
    ensure_opponent_model(game)

    model = game.opponent_model

    model["last_human_moves"].append({
        "move_type": move_type,
        "card_name": card_name,
        "essence_choices": essence_choices or [],
    })

    model["last_human_moves"] = model["last_human_moves"][-10:]

    name = card_name or ""
    choices = essence_choices or []

    if move_type == "buy_place_of_power":
        model["place_rush"] += 12

        if name == "Catacombs of the Dead":
            model["death"] += 15
            model["storage"] += 8

        if name in ["Dragon’s Lair", "Dragon's Lair"]:
            model["dragon"] += 15

    if move_type == "buy_monument":
        model["monument_rush"] += 10
        model["gold"] += 6

    if move_type == "discard":
        for e in choices:
            if e == "death":
                model["death"] += 6
            elif e == "life":
                model["life"] += 4
            elif e == "calm":
                model["dragon"] += 3
            elif e == "gold":
                model["gold"] += 6

    if move_type == "play_card":
        if "Dragon" in name:
            model["dragon"] += 10

        if name in ["Vault", "Athanor", "Corrupt Altar", "Crypt", "Cursed Skull"]:
            model["death"] += 8
            model["storage"] += 6

        if name in ["Dwarven Pickaxe", "Ring of Midas", "Horn of Plenty"]:
            model["gold"] += 8

    if move_type == "use_power":
        if name in ["Vault", "Athanor", "Crypt", "Cursed Skull"]:
            model["storage"] += 5
            model["death"] += 5

def get_human_plan(game):
    ensure_opponent_model(game)

    model = game.opponent_model

    strategy_keys = ["death", "dragon", "gold", "life", "storage", "place_rush", "monument_rush"]

    best = max(strategy_keys, key=lambda k: model.get(k, 0))
    confidence = model.get(best, 0)

    return best, confidence, dict(model)