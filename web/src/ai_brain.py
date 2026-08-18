 # src/ai_brain.py

import json
import random
from collections import Counter
from pathlib import Path
from counter_memory import get_counter_bonus
from context_memory import get_context_bonus
from reward_memory import get_reward_memory_bonus

ROOT_DIR = Path(__file__).resolve().parents[1]
MEMORY_FILE = ROOT_DIR / "memory" / "game_memory.json"

_GAME_MEMORY_CACHE = None


def clear_game_memory_cache():
    global _GAME_MEMORY_CACHE
    _GAME_MEMORY_CACHE = None

def load_game_memory(
    force_reload=False,
):
    global _GAME_MEMORY_CACHE

    if (
        _GAME_MEMORY_CACHE is not None
        and not force_reload
    ):
        return _GAME_MEMORY_CACHE

    if not MEMORY_FILE.exists():
        _GAME_MEMORY_CACHE = []
        return _GAME_MEMORY_CACHE

    try:
        with open(
            MEMORY_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        if isinstance(data, list):
            _GAME_MEMORY_CACHE = data
        else:
            _GAME_MEMORY_CACHE = []

        return _GAME_MEMORY_CACHE

    except (
        OSError,
        json.JSONDecodeError,
    ):
        _GAME_MEMORY_CACHE = []
        return _GAME_MEMORY_CACHE

def analyze_game_memory():
    games = load_game_memory()

    summary = {
        "games_played": len(games),
        "human_wins": 0,
        "ai_wins": 0,
        "move_counts": {},
        "card_counts": {},
        "human_card_counts": {},
        "ai_card_counts": {},
        "strategy_counts": {},
    }

    move_counter = Counter()
    card_counter = Counter()
    human_card_counter = Counter()
    ai_card_counter = Counter()
    strategy_counter = Counter()

    for game in games:
        winner = game.get("winner")

        if winner == "Chikile":
            summary["human_wins"] += 1
        elif winner == "AI Companion":
            summary["ai_wins"] += 1

        for strategy_data in game.get("strategies", []):
            strategy = strategy_data.get("strategy")

            if strategy:
                strategy_counter[strategy] += 1

        for move in game.get("moves", []):
            move_type = move.get("move_type")
            card = move.get("card_name")
            player = move.get("player")

            if move_type:
                move_counter[move_type] += 1

            if card:
                card_counter[card] += 1

                if player == "Chikile":
                    human_card_counter[card] += 1

                elif player == "AI Companion":
                    ai_card_counter[card] += 1

    summary["move_counts"] = dict(move_counter)
    summary["card_counts"] = dict(card_counter)
    summary["human_card_counts"] = dict(human_card_counter)
    summary["ai_card_counts"] = dict(ai_card_counter)
    summary["strategy_counts"] = dict(strategy_counter)

    return summary


def get_human_memory_profile():
    games = load_game_memory()
    games_with_moves = sum(
        1
        for game in games
        if game.get("moves")
    )

    card_counter = Counter()
    move_counter = Counter()
    strategy_counter = Counter()
    item_counter = Counter()
    mage_counter = Counter()

    for game in games:
        for move in game.get("moves", []):
            if move.get("player") != "Chikile":
                continue

            move_type = move.get("move_type")
            card_name_value = move.get("card_name")

            if move_type:
                move_counter[move_type] += 1

            if card_name_value:
                card_counter[card_name_value] += 1

        final_state = game.get("final_state", {})

        for player in final_state.get("players", []):
            if player.get("name") != "Chikile":
                continue

            mage = player.get("mage")
            item = player.get("item")

            if isinstance(mage, dict):
                mage = mage.get("name")

            if isinstance(item, dict):
                item = item.get("name")

            if mage:
                mage_counter[mage] += 1

            if item:
                item_counter[item] += 1

        for strategy_data in game.get("strategies", []):
            if strategy_data.get("player") == "Chikile":
                strategy = strategy_data.get("strategy")

                if strategy:
                    strategy_counter[strategy] += 1

    return {
        "favorite_cards": card_counter.most_common(10),
        "favorite_moves": move_counter.most_common(),
        "favorite_strategies": strategy_counter.most_common(),
        "favorite_items": item_counter.most_common(5),
        "favorite_mages": mage_counter.most_common(5),
        "games_with_moves": games_with_moves,
    }




def card_name(card):
    if not card:
        return ""

    return (
        getattr(card.definition, "name", None)
        or card.definition.raw_data.get("name_en")
        or card.definition.raw_data.get("id")
        or ""
    )


def card_tags(card):
    if not card:
        return []

    return card.definition.raw_data.get("tags", [])


def get_human_cards(human):
    cards = []

    if human.mage:
        cards.append(human.mage)

    if human.item:
        cards.append(human.item)

    cards.extend(human.played)
    cards.extend(human.places)
    cards.extend(human.monuments)
    cards.extend(human.discard)

    return cards


def detect_human_strategy(game):
    human = game.players[0]

    scores = {
        "death": 0,
        "dragon": 0,
        "gold": 0,
        "life": 0,
        "storage": 0,
    }

    scores["death"] += human.essence_pool.get("death", 0) * 2
    scores["life"] += human.essence_pool.get("life", 0)
    scores["gold"] += human.essence_pool.get("gold", 0) * 2

    for card in get_human_cards(human):
        name = card_name(card)
        tags = card_tags(card)

        if name == "Catacombs of the Dead":
            scores["death"] += 10
            scores["storage"] += 6

        if name in ["Dragon’s Lair", "Dragon's Lair"]:
            scores["dragon"] += 10

        if name == "Sacred Grove":
            scores["life"] += 10

        if name in ["Vault", "Athanor"]:
            scores["death"] += 4
            scores["storage"] += 4

        if "dragon" in tags or "dragon_support" in tags:
            scores["dragon"] += 4

        if "death_engine" in tags:
            scores["death"] += 4

        if "storage" in tags or "vp_scaling" in tags:
            scores["storage"] += 3

        if "gold_engine" in tags or "gold_generation" in tags:
            scores["gold"] += 4

        if "life_engine" in tags:
            scores["life"] += 4

    visible_places = [card_name(place) for place in game.market_places]

    if "Catacombs of the Dead" in visible_places:
        if human.essence_pool.get("death", 0) >= 3:
            scores["death"] += 6

    if "Dragon’s Lair" in visible_places or "Dragon's Lair" in visible_places:
        if (
            human.essence_pool.get("death", 0)
            + human.essence_pool.get("life", 0)
            + human.essence_pool.get("calm", 0)
        ) >= 4:
            scores["dragon"] += 6

    best_strategy = max(scores, key=scores.get)
    confidence = scores[best_strategy]

    return best_strategy, confidence, scores


def choose_ai_personality(game):
    if not hasattr(game, "ai_personality"):
        game.ai_personality = random.choice([
            "balanced",
            "blocker",
            "greedy",
            "engine_builder",
        ])

    return game.ai_personality


def apply_human_like_noise(score, difficulty="normal"):
    if difficulty == "easy":
        return score + random.randint(-35, 25)

    if difficulty == "hard":
        return score + random.randint(-8, 8)

    return score + random.randint(-5, 5)


def apply_human_strategy_reaction(move, score, reasons, game, ai_player):
    human_strategy, confidence, _ = detect_human_strategy(game)
    personality = choose_ai_personality(game)

    if confidence < 5:
        return score, reasons

    move_type = move.get("type")
    move_card = move.get("card_name", "")

    reasons.append(
        f"AI suspects Chikile is building {human_strategy} strategy"
    )

    block_multiplier = 2 if personality == "blocker" else 1

    if human_strategy == "death":
        if move_type == "buy_place_of_power" and move_card == "Catacombs of the Dead":
            score += 180 * block_multiplier
            reasons.append("blocks Chikile's likely Catacombs plan")

        if move_type == "discard":
            choices = move.get("choices") or []

            if "death" in choices or "life" in choices:
                score += 35
                reasons.append("collects resources for death strategy")

    if human_strategy == "dragon":
        if move_type == "buy_place_of_power" and move_card in ["Dragon’s Lair", "Dragon's Lair"]:
            score += 180 * block_multiplier
            reasons.append("blocks Chikile's likely Dragon's Lair plan")

        if move_type == "discard":
            choices = move.get("choices") or []

            if (
                "death" in choices
                or "life" in choices
                or "calm" in choices
            ):
                score += 30
                reasons.append("collects dragon resources")

    if human_strategy == "gold":
        if move_type == "buy_monument":
            score += 80
            reasons.append("keeps up with Chikile's monument race")

    if human_strategy == "storage":
        if move_type == "buy_place_of_power":
            score += 70
            reasons.append("competes for storage scoring")

    if personality == "greedy":
        if move_type in ["play_card", "use_power"]:
            score += 15
            reasons.append("greedy AI prefers engine growth")

    elif personality == "engine_builder":
        if move_type == "play_card":
            score += 20
            reasons.append("engine-builder AI likes developing board")

    elif personality == "balanced":
        if move_type in ["buy_place_of_power", "buy_monument"]:
            score += 20
            reasons.append("balanced AI values scoring progress")

    return score, reasons

def apply_memory_reaction(
    move,
    score,
    reasons,
    game=None,
    ai_player=None,
    use_reward=True,
    use_context=True,
    use_counter=True,
):
    """
    Apply learned-memory bonuses independently.

    This allows ablation testing of:
        - reward memory
        - context memory
        - counter/opponent memory

    Normal training self-play does not use these
    reaction memories while generating games.

    Evaluation mode is allowed to use them.
    """

    # ========================================================
    # TRAINING SELF-PLAY
    # ========================================================

    # Do not allow these memories to influence normal
    # training self-play unless this is an evaluation game.
    if (
        game is not None
        and getattr(
            game,
            "self_play",
            False,
        )
        and not getattr(
            game,
            "evaluation_mode",
            False,
        )
    ):
        return score, reasons

    # ========================================================
    # COUNTER / HUMAN HISTORY MEMORY
    # ========================================================

    # Historical information about the opponent belongs
    # with counter/opponent memory for the ablation study.
    if use_counter:

        profile = get_human_memory_profile()

        if profile.get(
            "games_with_moves",
            0,
        ) >= 5:

            favorite_strategies = (
                profile.get(
                    "favorite_strategies",
                    [],
                )
            )

            favorite_cards = (
                profile.get(
                    "favorite_cards",
                    [],
                )
            )

            favorite_moves = (
                profile.get(
                    "favorite_moves",
                    [],
                )
            )

            move_type = move.get(
                "type"
            )

            move_card = move.get(
                "card_name",
                "",
            )

            top_strategy = (
                favorite_strategies[0][0]
                if favorite_strategies
                else None
            )

            top_cards = {
                card_name_value
                for card_name_value, count
                in favorite_cards[:5]
            }

            top_move = (
                favorite_moves[0][0]
                if favorite_moves
                else None
            )

            if top_strategy:

                reasons.append(
                    f"memory says opponent often "
                    f"uses {top_strategy} strategy"
                )

            if top_strategy == "dragon":

                if (
                    move_type
                    == "buy_place_of_power"
                    and move_card
                    in [
                        "Dragon’s Lair",
                        "Dragon's Lair",
                    ]
                ):

                    score += 90

                    reasons.append(
                        "historical memory suggests "
                        "denying Dragon's Lair"
                    )

            elif top_strategy == "death":

                if (
                    move_type
                    == "buy_place_of_power"
                    and move_card
                    == "Catacombs of the Dead"
                ):

                    score += 90

                    reasons.append(
                        "historical memory suggests "
                        "denying Catacombs"
                    )

            elif top_strategy == "gold":

                if (
                    move_type
                    == "buy_monument"
                ):

                    score += 40

                    reasons.append(
                        "historical memory suggests "
                        "competing in monument race"
                    )

            if move_card in top_cards:

                reasons.append(
                    f"opponent frequently uses "
                    f"{move_card}"
                )

            if (
                top_move
                == "buy_monument"
                and move_type
                == "buy_monument"
            ):

                score += 20

                reasons.append(
                    "memory shows opponent often "
                    "buys monuments"
                )

    # ========================================================
    # NEED GAME STATE FOR REMAINING MEMORIES
    # ========================================================

    if (
        game is None
        or ai_player is None
    ):
        return score, reasons

    human_strategy, confidence, _ = (
        detect_human_strategy(
            game
        )
    )

    # ========================================================
    # REWARD MEMORY
    # ========================================================

    if use_reward:

        reward_bonus, reward_reason = (
            get_reward_memory_bonus(
                move
            )
        )

        score += reward_bonus

        if reward_reason:
            reasons.append(
                reward_reason
            )

    # ========================================================
    # COUNTER MEMORY
    # ========================================================

    if (
        use_counter
        and confidence >= 5
    ):

        counter_bonus, counter_reason = (
            get_counter_bonus(
                human_strategy,
                move,
            )
        )

        score += counter_bonus

        if counter_reason:
            reasons.append(
                counter_reason
            )

    # ========================================================
    # CONTEXT MEMORY
    # ========================================================

    if (
        use_context
        and confidence >= 5
    ):

        context_bonus, context_reason = (
            get_context_bonus(
                human_strategy,
                game,
                ai_player,
                move,
            )
        )

        score += context_bonus

        if context_reason:
            reasons.append(
                context_reason
            )

    return score, reasons