import asyncio
print("WEB DEBUG 1: main.py started")

import sys
print("WEB DEBUG 2: Python imports working")
print("Platform:", sys.platform)
import random
from pathlib import Path


import pygame

IS_WEB = sys.platform == "emscripten"

if IS_WEB:
    ROOT_DIR = Path(".").resolve()
else:
    ROOT_DIR = Path(__file__).resolve().parent

SRC_DIR = ROOT_DIR / "src"

sys.path.append(str(SRC_DIR))
sys.path.append(str(ROOT_DIR))

from card_loader import load_all_cards
from models import Player, GameState, CardInstance, ESSENCE_KEYS
from ui.game_screen import GameScreen
from collection_phase import start_collection_phase # type: ignore
from rules_engine import (
    check_victory,
    reset_round_state,
    choose_item_for_player,
    refresh_victory_points,
)

from effect_engine import (
    add_essence,
    draw_cards,
    run_collect_effects,
)

from ai_advisor import execute_ai_move
from victory_reactions import (
    begin_victory_reactions,
    reset_victory_reactions,
    should_ai_use_golden_statue,
    use_golden_statue,
)
from game_memory import (
    start_new_game_record,
    record_move,
    snapshot_game,
    finish_game_record,
    save_game_record,
    neural_learning_pending,
    clear_neural_learning_pending,
)
print("WEB DEBUG 3: before pygame")
import pygame
print("WEB DEBUG 4: pygame imported")

# ============================================================
# WEB PLAYER NAME
# ============================================================

WEB_PLAYER_NAME = "Chikile"


def get_web_player_name():
    if not IS_WEB:
        return "Chikile"

    try:
        from js import window

        value = (
            window.localStorage.getItem(
                "res_arcana_player_name"
            )
            or "Player"
        )

        value = str(value).strip()

        if not value:
            value = "Player"

        return value

    except Exception as error:
        print(
            "PLAYER NAME ERROR:",
            error
        )

        return "Player"

# ============================================================
# WEB FONT FIX
# ============================================================

if IS_WEB:
    _original_sysfont = pygame.font.SysFont

    def browser_sysfont(
        name,
        size,
        bold=False,
        italic=False,
    ):
        font = pygame.font.Font(
            pygame.font.get_default_font(),
            int(size)
        )

        font.set_bold(
            bool(bold)
        )

        font.set_italic(
            bool(italic)
        )

        return font

    pygame.font.SysFont = browser_sysfont

    print(
        "WEB FONT OVERRIDE ENABLED:",
        pygame.font.get_default_font()
    )

print("WEB DEBUG 5: before game imports")

# your normal imports here

print("WEB DEBUG 6: all game imports finished")

TARGET_VP = 10


def clone_card(card):
    return CardInstance(definition=card.definition)


def card_name(card):
    return (
        getattr(card.definition, "name", None)
        or card.definition.raw_data.get("name_en")
        or card.definition.raw_data.get("id")
    )


def get_cards_by_type(cards, card_type):
    return [
        c for c in cards
        if c.definition.raw_data.get("type") == card_type
        or getattr(c.definition, "card_type", None) == card_type
    ]


def get_artifact_deck(cards):
    return [
        c for c in cards
        if (
            c.definition.raw_data.get("type")
            or getattr(c.definition, "card_type", None)
        )
        in {"artifact", "creature", "dragon"}
    ]


def deal_cards(deck, count):
    dealt = []

    for _ in range(count):
        if deck:
            dealt.append(clone_card(deck.pop(0)))

    return dealt


def give_starting_essence(player):
    for essence in ESSENCE_KEYS:
        player.essence_pool[essence] = 1


def draw_starting_cards(player, count):
    for _ in range(count):
        if player.deck_hidden:
            player.hand.append(player.deck_hidden.pop(0))


def filter_places_by_side(places, side_choice="random"):
    if side_choice == "random":
        return places

    return [
        place for place in places
        if place.definition.raw_data.get("side", "unknown") == side_choice
    ]


def ai_choose_mage(mage_options, ai_deck):
    if not mage_options:
        return None

    best_mage = mage_options[0]
    best_score = -999

    deck_tags = []
    for card in ai_deck:
        deck_tags.extend(card.definition.raw_data.get("tags", []))

    for mage in mage_options:
        name = card_name(mage)
        score = 50

        if name == "Scholar":
            score += 25
        elif name == "Druid":
            score += 40 if "creature" in deck_tags else 10
        elif name == "Necromancer":
            score += 30
        elif name == "Transmuter":
            score += 25

        if score > best_score:
            best_score = score
            best_mage = mage

    return best_mage


def choose_default_item(game, player, old_item=None):
    if not game.items_pool:
        return None

    try:
        return choose_item_for_player(game, player, 0, old_item=old_item)
    except Exception as e:
        game.game_log.append(f"Item choice failed for {player.name}: {e}")
        return None


def setup_game(seed=None):
    if seed is not None:
        random.seed(seed)

    all_cards = load_all_cards()

    artifact_deck = get_artifact_deck(all_cards)
    mages = get_cards_by_type(all_cards, "mage")
    items = get_cards_by_type(all_cards, "item")
    monuments = get_cards_by_type(all_cards, "monument")
    places = get_cards_by_type(all_cards, "place_of_power")

    random.shuffle(artifact_deck)
    random.shuffle(mages)
    random.shuffle(items)
    random.shuffle(monuments)
    random.shuffle(places)

    places = filter_places_by_side(places, "random")

    human = Player("Chikile")
    ai = Player("AI Companion")

    give_starting_essence(human)
    give_starting_essence(ai)

    human.deck_hidden = deal_cards(artifact_deck, 8)
    ai.deck_hidden = deal_cards(artifact_deck, 8)

    human_mage_options = deal_cards(mages, 2)
    ai_mage_options = deal_cards(mages, 2)

    human.mage = None
    human.mage_options = human_mage_options
    human.setup_artifacts = list(human.deck_hidden)

    ai.mage = ai_choose_mage(ai_mage_options, ai.deck_hidden)

    random.shuffle(human.deck_hidden)
    random.shuffle(ai.deck_hidden)

    #draw_starting_cards(human, 3)
    draw_starting_cards(ai, 3)

    monument_deck = deal_cards(monuments, len(monuments))
    visible_monuments = []

    for _ in range(2):
        if monument_deck:
            visible_monuments.append(monument_deck.pop(0))

    market_places = deal_cards(places, 5)

    game = GameState(
        players=[human, ai],
        market_monuments=visible_monuments,
        monument_deck=monument_deck,
        market_places=market_places,
        items_pool=items,
    )

    game.current_phase = "setup_show_starting_cards"
    game.current_setup_step = "choose_human_mage"
    game.current_setup_step = "show_artifacts_choose_mage"
    game.round_no = getattr(game, "round_no", 1)
    game.force_victory_check = False
    game.gui_human_action_done = False
    game.next_ai_move_time = 0
    game.ai_move_delay_ms = 1200
    reset_victory_reactions(game)

    first_player_index = random.choice([0, 1])

    human.has_first_player_token = first_player_index == 0
    ai.has_first_player_token = first_player_index == 1
    game.current_player_index = first_player_index

  
    game.current_phase = "setup_show_starting_cards"
    game.current_setup_step = "choose_human_mage"

    if human.has_first_player_token:
        game.pending_item_order = ["human", "ai"]
    else:
        game.pending_item_order = ["ai", "human"]

    game.game_log.append("Res Arcana GUI game started.")
    game.game_log.append(f"Round {game.round_no} started.")
    game.game_log.append(f"First player: {game.players[first_player_index].name}")
    game.game_log.append("Setup: check your 8 artifacts, then choose one mage.")

    return game


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


def run_gui_collect_phase(game):
    if not getattr(game, "collect_phase_started", False):
        start_collection_phase(game)

def advance_turn(game):
    """
    Move directly to the next player who has not passed.

    If every player has passed, leave the index unchanged.
    The phase manager will move to victory check.
    """
    player_count = len(game.players)

    for _ in range(player_count):
        game.current_player_index = (
            game.current_player_index + 1
        ) % player_count

        next_player = game.players[game.current_player_index]

        if not next_player.passed:
            return

def run_ai_turn(game):
    ai = game.players[1]

    if ai.passed:
        advance_turn(game)
        return

    try:
        state_before = snapshot_game(game)
        essence_before = dict(ai.essence_pool)

        move = execute_ai_move(game, ai)

        essence_after = dict(ai.essence_pool)

        game.game_log.append(
            f"AI MOVE DEBUG: {move.get('type')} | "
            f"{move.get('card_name')} | "
            f"before={essence_before} | "
            f"after={essence_after}"
        )
        
        move_type = move.get("type")
        card = move.get("card_name")

        if move_type == "play_card":
            game.game_log.append(f"AI played {card}.")

        elif move_type == "use_power":
            game.game_log.append(
                f"AI used {card} power {move.get('power_index')}."
            )

        elif move_type == "discard":
            game.game_log.append(
                f"AI discarded {card} for {move.get('reward_type')}."
            )

        elif move_type == "buy_monument":
            game.game_log.append(f"AI bought monument {card}.")

        elif move_type == "buy_place_of_power":
            game.game_log.append(f"AI bought Place of Power {card}.")

        elif move_type == "pass":
            old_item = ai.item

            if old_item:
                old_item.tapped = False

            ai.item = None
            choose_default_item(game, ai, old_item=old_item)
            game.game_log.append("AI passed and chose a new item.")

        else:
            game.game_log.append(f"AI performed action: {move_type}")
        record_move(
            game_record=game.game_record,
            game=game,
            state_before=state_before,
            player_name=ai.name,
            move_type=move.get("type"),
            description=move.get("explanation", "AI completed a move."),
            card_name=move.get("card_name"),
            move_score=move.get("score"),
            reasons=move.get("reasons", []),
            reward_type=move.get("reward_type"),
            reward_choices=move.get("choices"),
            x_value=move.get("x_value"),
            target_card=move.get("target_card"),
        )


    except Exception as e:
        game.game_log.append(f"AI action failed: {e}")

    
    advance_turn(game)


def run_victory_phase(game):
    if not getattr(
        game,
        "victory_banner_shown",
        False,
    ):
        game.victory_banner_shown = True

        game.game_log.append(
            f"=== VICTORY CHECK: "
            f"ROUND {game.round_no} ==="
        )

        game.phase_banner_title = (
            "VICTORY CHECK"
        )

        game.phase_banner_message = (
            "Resolve victory reactions, "
            "then calculate final points."
        )

        game.phase_banner_until = (
            pygame.time.get_ticks()
            + 4000
        )

        return

    # Start the reaction queue once.
    if not getattr(
        game,
        "victory_reaction_started",
        False,
    ):
        begin_victory_reactions(game)

    # Resolve every eligible player's
    # Golden Statue before check_victory().
    if not getattr(
        game,
        "victory_reaction_finished",
        False,
    ):
        # Wait while the human prompt is open.
        if getattr(
            game,
            "pending_golden_statue_player",
            None,
        ) is not None:
            return

        queue = getattr(
            game,
            "victory_reaction_queue",
            [],
        )

        if queue:
            player = queue.pop(0)

            human = game.players[0]
            ai = game.players[1]

            if player is ai:
                if should_ai_use_golden_statue(
                    game,
                    ai,
                ):
                    if use_golden_statue(ai):
                        game.game_log.append(
                            f"{ai.name} spent "
                            "3 Gold with Golden "
                            "Statue for +3 VP."
                        )
                else:
                    game.game_log.append(
                        f"{ai.name} chose not "
                        "to use Golden Statue."
                    )

                return

            if player is human:
                game.pending_golden_statue_player = (
                    human
                )

                game.show_golden_statue_prompt = True
                return

        game.victory_reaction_finished = True

    # Only calculate final victory after all
    # Golden Statue reactions are resolved.
    check_victory(game)

    game.victory_banner_shown = False

    if game.game_over:
        game.current_phase = "end"

        game.game_log.append(
            f"GAME OVER. Winner: "
            f"{game.winner}"
        )

        if not getattr(
            game,
            "memory_saved",
            False,
        ):
            finish_game_record(
                game.game_record,
                game,
            )

            save_game_record(
                game.game_record
            )

            game.memory_saved = True

            game.game_log.append(
                "Game memory saved."
            )

        return

    reset_victory_reactions(game)
    game.current_phase = "end_round"
def untap_all_player_cards(player):
    cards = []

    if player.mage:
        cards.append(player.mage)

    if player.item:
        cards.append(player.item)

    cards.extend(player.played)
    cards.extend(player.monuments)
    cards.extend(player.places)

    for card in cards:
        card.tapped = False

def run_end_round(game):
    reset_round_state(game)

    for player in game.players:
        untap_all_player_cards(player)

    game.collect_phase_started = False
    game.collect_queue = []
    game.pending_collect_choice = None

    for index, player in enumerate(game.players):
        if player.has_first_player_token:
            game.current_player_index = index
            break

    game.round_no += 1
    game.current_phase = "collect"
    game.gui_human_action_done = False

    game.game_log.append(f"=== ROUND {game.round_no} STARTED ===")
    game.game_log.append("All cards untapped.")
    game.phase_banner_title = "COLLECTION PHASE"
    game.phase_banner_message = "Collect essence from mage, item, artifacts, monuments, and places."
    game.phase_banner_until = pygame.time.get_ticks() + 4000


def update_phase_manager(game):
    # Block all automatic phase movement while phase display is showing
    if pygame.time.get_ticks() < getattr(game, "phase_banner_until", 0):
        return

    if game.game_over:
        game.current_phase = "end"
        return

    human = game.players[0]
    ai = game.players[1]

    # Collection choice popup is handled by GameScreen
    if game.current_phase == "collect_choice":
        return
    
    if getattr(game, "waiting_for_human_item_choice", False):
        return

    # Setup is handled by GUI
    if game.current_phase in [
        "setup_show_starting_cards",
        "setup_choose_mage",
        "setup_choose_item",
    ]:
        return

    # COLLECTION PHASE
    if game.current_phase == "collect":
        run_gui_collect_phase(game)
        return

    # ACTION PHASE
    if game.current_phase == "action":

        if human.passed and ai.passed:
            game.current_phase = "victory"
            game.victory_banner_shown = False
            return

        if game.force_victory_check:
            game.current_phase = "victory"
            game.victory_banner_shown = False
            return

        current_player = game.players[game.current_player_index]

        if current_player.passed:
            advance_turn(game)
            return

        if current_player is ai:
            now = pygame.time.get_ticks()

            if now < getattr(game, "next_ai_move_time", 0):
                return

            run_ai_turn(game)

            game.next_ai_move_time = (
                pygame.time.get_ticks()
                + getattr(game, "ai_move_delay_ms", 1200)
            )
            return

        if current_player is human and game.gui_human_action_done:
            game.gui_human_action_done = False

            advance_turn(game)

            game.next_ai_move_time = (
                pygame.time.get_ticks()
                + getattr(game, "ai_move_delay_ms", 1200)
            )
            return
    # VICTORY CHECK PHASE
    if game.current_phase == "victory":
        run_victory_phase(game)
        return

    # END ROUND PHASE
    if game.current_phase == "end_round":
        run_end_round(game)
        return

def update_neural_learning_if_needed():
    if not neural_learning_pending():
        return

    print()
    print("=" * 70)
    print("UPDATING AI FROM YOUR LAST HUMAN GAME")
    print("=" * 70)

    try:
        from ml.neural_counter_model import update_after_human_game

        result = update_after_human_game(quiet=True)

        if result is None:
            print(
                "Neural learning did not complete. "
                "The update will be retried next startup."
            )
            return

        clear_neural_learning_pending()

        print("Neural learning updated successfully.")
        print("The new game will use the updated model.")

    except Exception as error:
        print("Neural learning update failed:")
        print(error)
        print(
            "The update marker was kept, so it "
            "will retry next startup."
        )

    print("=" * 70)
    print()


async def main():
    update_neural_learning_if_needed()

    pygame.init()

    assets_dir = ROOT_DIR / "assets"

    window_width = 1720
    window_height = 880

    pygame.display.set_caption(
        "Res Arcana AI - Web"
    )

    pygame_screen = pygame.display.set_mode(
        (window_width, window_height)
    )

    clock = pygame.time.Clock()

    global WEB_PLAYER_NAME

    WEB_PLAYER_NAME = get_web_player_name()

    print(
        "WEB PLAYER:",
        WEB_PLAYER_NAME
    )

    print("WEB DEBUG 7: before setup_game")

    game = setup_game()

    print("WEB DEBUG 8: setup_game finished")

    game.game_record = start_new_game_record()

    # Internal player remains "Chikile" for neural-training
    # compatibility. This stores the real web player's name.
    game.game_record["player_name"] = WEB_PLAYER_NAME
    game.game_record["human_internal_name"] = "Chikile"
    game.web_player_name = WEB_PLAYER_NAME

    print(
        "GAME RECORD PLAYER:",
        WEB_PLAYER_NAME
    )

    game.memory_saved = False

    print("WEB DEBUG 9: before GameScreen")

    game_screen = GameScreen(
        pygame_screen,
        game,
        assets_dir,
    )

    print("WEB DEBUG 10: GameScreen finished")

    running = True

    print("WEB DEBUG 11: entering game loop")

    while running:

        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                running = False

            game_screen.handle_event(event)

        refresh_victory_points(game)

        update_phase_manager(game)

        game_screen.draw()

        if not hasattr(
            game,
            "_web_first_frame_debug",
        ):
            print(
                "WEB DEBUG 12: FIRST FRAME DRAWN"
            )

            game._web_first_frame_debug = True

        pygame.display.flip()

        clock.tick(60)

        # Critical for PyScript:
        # give control back to the browser every frame.
        await asyncio.sleep(0)

    pygame.quit()

if __name__ == "__main__":
    asyncio.run(main())