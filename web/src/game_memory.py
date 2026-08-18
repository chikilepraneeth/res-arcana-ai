import json
import asyncio
import sys
import asyncio
import sys
from pathlib import Path
from datetime import datetime
from counter_memory import build_counter_memory
from context_memory import build_context_memory
from reward_engine import calculate_move_reward
from reward_memory import build_reward_memory
from sequence_memory import build_sequence_memory

try:
    from web_storage import save_game_online
except ImportError:
    save_game_online = None

MEMORY_DIR = Path(__file__).resolve().parents[1] / "memory"
MEMORY_FILE = MEMORY_DIR / "game_memory.json"
NEURAL_LEARNING_PENDING_FILE = MEMORY_DIR / "neural_learning_pending.json"

# ============================================================
# IN-MEMORY CACHE
# ============================================================

_MEMORY_CACHE = None


def clear_memory_cache():
    global _MEMORY_CACHE
    _MEMORY_CACHE = None


def is_real_human_game_record(game_record):
    players = {
        move.get("player")
        for move in game_record.get("moves", [])
        if isinstance(move, dict)
    }

    return (
        "Chikile" in players
        and "AI Companion" in players
    )


def mark_neural_learning_pending(game_record):
    if not is_real_human_game_record(game_record):
        return False

    MEMORY_DIR.mkdir(exist_ok=True)

    payload = {
        "pending": True,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "winner": game_record.get("winner"),
        "human_moves": sum(
            1
            for move in game_record.get("moves", [])
            if move.get("player") == "Chikile"
        ),
    }

    NEURAL_LEARNING_PENDING_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return True


def neural_learning_pending():
    if not NEURAL_LEARNING_PENDING_FILE.exists():
        return False

    try:
        data = json.loads(
            NEURAL_LEARNING_PENDING_FILE.read_text(encoding="utf-8")
        )
        return bool(data.get("pending", False))
    except Exception:
        return True


def clear_neural_learning_pending():
    try:
        if NEURAL_LEARNING_PENDING_FILE.exists():
            NEURAL_LEARNING_PENDING_FILE.unlink()
    except Exception as error:
        print(
            "Warning: neural-learning marker "
            f"could not be cleared: {error}"
        )

def ensure_memory_file():
    MEMORY_DIR.mkdir(exist_ok=True)

    if not MEMORY_FILE.exists():
        MEMORY_FILE.write_text("[]", encoding="utf-8")


def card_name(card):
    if not card:
        return None

    return (
        getattr(card.definition, "name", None)
        or card.definition.raw_data.get("name_en")
        or card.definition.raw_data.get("id")
    )
def card_id(card):
    if not card:
        return None

    return (
        getattr(card.definition, "card_id", None)
        or card.definition.raw_data.get("id")
    )

def snapshot_card(card):
    if not card:
        return None

    return {
        "card_id": card_id(card),
        "name": card_name(card),
        "tapped": bool(getattr(card, "tapped", False)),
        "stored_essence": dict(
            getattr(card, "stored_essence", {}) or {}
        ),
    }


def infer_strategy_from_player(player):
    death_total = 0
    life_total = 0
    calm_total = 0
    elan_total = 0
    gold_total = 0

    all_cards = (
        player.played
        + player.monuments
        + player.places
    )

    for card in all_cards:
        tags = card.definition.raw_data.get("tags", [])

        if "dragon_support" in tags:
            gold_total += 3

        if "gold_engine" in tags:
            gold_total += 2

        if "life_engine" in tags:
            life_total += 2

        if "death_engine" in tags:
            death_total += 2

        if "storage" in tags:
            death_total += 1

    scores = {
        "death": death_total,
        "life": life_total,
        "calm": calm_total,
        "elan": elan_total,
        "gold": gold_total
    }

    return max(scores, key=scores.get)


def load_memory(
    force_reload=False,
):
    global _MEMORY_CACHE

    if (
        _MEMORY_CACHE is not None
        and not force_reload
    ):
        return _MEMORY_CACHE

    ensure_memory_file()

    try:
        text = MEMORY_FILE.read_text(
            encoding="utf-8"
        )

        if not text.strip():
            _MEMORY_CACHE = []
            return _MEMORY_CACHE

        data = json.loads(text)

        if not isinstance(data, list):
            data = []

        _MEMORY_CACHE = data

        return _MEMORY_CACHE

    except Exception:
        _MEMORY_CACHE = []
        return _MEMORY_CACHE
    
def save_memory(memory):
    global _MEMORY_CACHE
    ensure_memory_file()
    MEMORY_FILE.write_text(
        json.dumps(memory, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    _MEMORY_CACHE = memory
    print("GAME MEMORY SAVED TO:", MEMORY_FILE)
    print("TOTAL GAMES IN MEMORY:", len(memory))

    if MEMORY_FILE.exists():
        print(
            "GAME MEMORY SIZE:",
            MEMORY_FILE.stat().st_size,
            "bytes"
        )


def snapshot_player(player):
    return {
        "name": player.name,
        "essence": dict(player.essence_pool),
        "vp": player.victory_points,

        "mage": snapshot_card(player.mage),
        "item": snapshot_card(player.item),

        "hand_count": len(player.hand),
        "hand": [
            {
                "card_id": card_id(card),
                "name": card_name(card),
            }
            for card in player.hand
        ],

        "deck_count": len(player.deck_hidden),
        "deck_top": [
            {
                "card_id": card_id(card),
                "name": card_name(card),
            }
            for card in player.deck_hidden[:3]
        ],

        "played": [
            snapshot_card(card)
            for card in player.played
        ],

        "monuments": [
            snapshot_card(card)
            for card in player.monuments
        ],

        "places": [
            snapshot_card(card)
            for card in player.places
        ],

        "discard_count": len(player.discard),
        "discard": [
            {
                "card_id": card_id(card),
                "name": card_name(card),
            }
            for card in player.discard
        ],

        "has_first_player_token": player.has_first_player_token,
        "passed": player.passed,
    }

def snapshot_game(game):
    return {
        "round": game.round_no,
        "phase": getattr(game, "current_phase", None),
        "current_player_index": game.current_player_index,
        "current_player": (
            game.players[game.current_player_index].name
            if game.players
            else None
        ),

        "players": [
            snapshot_player(player)
            for player in game.players
        ],

        "market_monuments": [
            snapshot_card(card)
            for card in game.market_monuments
        ],

        "monument_deck_count": len(game.monument_deck),

        "market_places": [
            snapshot_card(card)
            for card in game.market_places
        ],

        "items_pool": [
            snapshot_card(card)
            for card in game.items_pool
        ],

        "first_player_token_available": getattr(
            game,
            "first_player_token_available",
            False
        ),

        "game_over": game.game_over,
        "winner": game.winner,
    }


def start_new_game_record():
    return {
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "ended_at": None,
        "winner": None,
        "moves": [],
        "final_state": None,
        "learning_summary": {
            "card_success": {},
            "move_type_success": {},
            "strategy_notes": []
        }
    }


def record_move(
    game_record,
    game,
    state_before,
    player_name,
    move_type,
    description,
    card_name=None,
    move_score=None,
    reasons=None,
    reward_type=None,
    reward_choices=None,
    x_value=None,
    target_card=None,
):
    state_after = snapshot_game(game)

    opponent_name = next(
        (
            player.name
            for player in game.players
            if player.name != player_name
        ),
        None,
    )

    immediate_reward = 0.0
    reward_breakdown = []

    if opponent_name:
        immediate_reward, reward_breakdown = (
            calculate_move_reward(
                move_type=move_type,
                state_before=state_before,
                state_after=state_after,
                player_name=player_name,
                opponent_name=opponent_name,
            )
        )

    move = {
        "round": game.round_no,
        "player": player_name,
        "move_type": move_type,
        "description": description,
        "card_name": card_name,
        "move_score": move_score,
        "reasons": reasons or [],
        "reward_type": reward_type,
        "reward_choices": reward_choices,
        "x_value": x_value,
        "target_card": target_card,
        "immediate_reward": immediate_reward,
        "reward_breakdown": reward_breakdown,
        "state_before_move": state_before,
        "state_after_move": state_after,
    }

    game_record["moves"].append(move)


def finish_game_record(game_record, game):
    game_record["ended_at"] = datetime.now().isoformat(timespec="seconds")
    game_record["winner"] = game.winner
    game_record["final_state"] = snapshot_game(game)

    build_learning_summary(game_record)
    game_record["strategies"] = []

    for player in game.players:
        game_record["strategies"].append({
            "player": player.name,
            "strategy": infer_strategy_from_player(player),
            "winner": player.name == game.winner
        })


def build_learning_summary(game_record):
    winner = game_record.get("winner")

    card_success = {}
    move_type_success = {}

    for move in game_record.get("moves", []):
        player = move.get("player")
        card = move.get("card_name")
        move_type = move.get("move_type")

        won = player == winner

        if card:
            if card not in card_success:
                card_success[card] = {
                    "used": 0,
                    "wins": 0,
                    "losses": 0,
                    "avg_score": 0,
                    "scores": []
                }

            card_success[card]["used"] += 1

            if won:
                card_success[card]["wins"] += 1
            else:
                card_success[card]["losses"] += 1

            if move.get("move_score") is not None:
                card_success[card]["scores"].append(move["move_score"])

        if move_type:
            if move_type not in move_type_success:
                move_type_success[move_type] = {
                    "used": 0,
                    "wins": 0,
                    "losses": 0
                }

            move_type_success[move_type]["used"] += 1

            if won:
                move_type_success[move_type]["wins"] += 1
            else:
                move_type_success[move_type]["losses"] += 1

    for card, data in card_success.items():
        scores = data.pop("scores", [])

        if scores:
            data["avg_score"] = sum(scores) / len(scores)
        else:
            data["avg_score"] = 0

    game_record["learning_summary"]["card_success"] = card_success
    game_record["learning_summary"]["move_type_success"] = move_type_success

    notes = []

    for card, data in card_success.items():
        if data["used"] >= 2 and data["wins"] > data["losses"]:
            notes.append(f"{card} appeared useful in winning moves.")

        if data["used"] >= 2 and data["losses"] > data["wins"]:
            notes.append(f"{card} may be overvalued or used badly.")

    game_record["learning_summary"]["strategy_notes"] = notes


def save_game_record(game_record):
    memory = load_memory()
    memory.append(game_record)
    save_memory(memory)

    # WEB: permanently upload finished game to Supabase
    if (
        sys.platform == "emscripten"
        and save_game_online is not None
    ):
        try:
            asyncio.create_task(
                save_game_online(game_record)
            )

            print(
                "SUPABASE: game upload scheduled."
            )

        except Exception as error:
            print(
                "SUPABASE: upload scheduling failed:",
                error
            )

    try:
        build_counter_memory()
    except Exception as error:
        print(
            f"Warning: counter memory could not be rebuilt: {error}"
        )

    try:
        build_context_memory()
    except Exception as error:
        print(
            f"Warning: context memory could not be rebuilt: {error}"
        )
    try:
        build_reward_memory()
    except Exception as error:
        print(
            f"Warning: reward memory could not be rebuilt: {error}"
        )
    try:
        build_sequence_memory()
    except Exception as error:
        print(
            "Warning: sequence memory "
            f"could not be rebuilt: {error}"
        )

    try:
        if mark_neural_learning_pending(game_record):
            print(
                "New human game marked for "
                "neural learning on next startup."
            )
    except Exception as error:
        print(
            "Warning: neural learning could "
            f"not be marked pending: {error}"
        )


def summarize_game_memory():
    memory = load_memory()

    if not memory:
        print("\nNo game memory yet.")
        return

    total_games = len(memory)
    wins = {}

    card_stats = {}

    for game in memory:
        winner = game.get("winner")

        if winner:
            wins[winner] = wins.get(winner, 0) + 1

        summary = game.get("learning_summary", {})
        card_success = summary.get("card_success", {})

        for card, data in card_success.items():
            if card not in card_stats:
                card_stats[card] = {
                    "used": 0,
                    "wins": 0,
                    "losses": 0
                }

            card_stats[card]["used"] += data.get("used", 0)
            card_stats[card]["wins"] += data.get("wins", 0)
            card_stats[card]["losses"] += data.get("losses", 0)

    print("\n========== GAME MEMORY SUMMARY ==========")
    print("Total games stored:", total_games)
    print("Wins:", wins)

    if card_stats:
        print("\nTop learned card stats:")

        ranked = sorted(
            card_stats.items(),
            key=lambda item: (item[1]["wins"], item[1]["used"]),
            reverse=True
        )

        for card, stats in ranked[:10]:
            print(
                f"- {card}: used={stats['used']}, "
                f"wins={stats['wins']}, losses={stats['losses']}"
            )

    print("=========================================")


def get_card_memory_bonus(card_name_value):
    memory = load_memory()

    used = 0
    wins = 0
    losses = 0

    for game in memory:
        summary = game.get("learning_summary", {})
        card_success = summary.get("card_success", {})

        if card_name_value in card_success:
            data = card_success[card_name_value]
            used += data.get("used", 0)
            wins += data.get("wins", 0)
            losses += data.get("losses", 0)

    if used < 2:
        return 0

    if wins > losses:
        return min(25, (wins - losses) * 5)

    if losses > wins:
        return max(-25, (wins - losses) * 5)

    return 0


def get_strategy_memory_bonus(strategy_name):
    memory = load_memory()

    used = 0
    wins = 0

    for game in memory:
        for item in game.get("strategies", []):
            if item.get("strategy") == strategy_name:
                used += 1
                if item.get("winner"):
                    wins += 1

    if used < 2:
        return 0

    win_rate = wins / used

    if win_rate >= 0.6:
        return 25

    if win_rate <= 0.3:
        return -20

    return 0