# src/self_play.py

from __future__ import annotations

import random
import traceback

from main import (
    setup_game,
    ai_choose_mage,
    choose_default_item,
)

from ai_advisor import (
    execute_ai_move,
    get_ai_legal_moves,
    get_controlled_cards,
    card_id,
    choose_ai_x_value,
    choose_ai_wild_payment,
    choose_ai_wild_payment_for_cost,
    choose_ai_straighten_target,
)

from rules_engine import (
    check_victory,
    reset_round_state,
    compute_player_vp,
    use_power,
    play_card_from_hand,
    pass_turn,
    discard_card_for_resources,
    buy_monument,
    buy_place_of_power,
    get_effective_placement_cost,
)

from effect_engine import (
    run_collect_effects,
    choose_discount_for_ai,
)

from game_memory import (
    start_new_game_record,
    snapshot_game,
    record_move,
    finish_game_record,
    save_game_record,
)

from card_loader import load_all_cards
from models import (
    Player,
    GameState,
    CardInstance,
)

from lookahead import (
    clone_game_for_simulation,
    find_player_by_name,
)


MAX_ROUNDS = 30
MAX_ACTIONS_PER_ROUND = 100


def get_vp(game, player):
    """Return the player's current VP."""
    try:
        return compute_player_vp(
            player,
            game,
        )
    except Exception:
        return getattr(
            player,
            "victory_points",
            0,
        )


def print_game_state(game):
    print("-" * 70)

    for player in game.players:
        vp = get_vp(
            game,
            player,
        )

        gold = player.essence_pool.get(
            "gold",
            0,
        )

        print(
            f"{player.name:<5} | "
            f"VP: {vp:<3} | "
            f"Gold: {gold:<2} | "
            f"Hand: {len(player.hand):<2} | "
            f"Artifacts: {len(player.played):<2} | "
            f"Monuments: {len(player.monuments):<2} | "
            f"Places: {len(player.places):<2}"
        )

    print("-" * 70)

def choose_self_play_mage(
    player,
):
    options = list(
        getattr(
            player,
            "mage_options",
            [],
        )
    )

    if not options:
        return

    player.mage = ai_choose_mage(
        options,
        player.deck_hidden,
    )

    player.mage_options = []


def draw_starting_hand(
    player,
    count=3,
):
    while (
        len(player.hand) < count
        and player.deck_hidden
    ):
        player.hand.append(
            player.deck_hidden.pop(0)
        )


def choose_starting_item(
    game,
    player,
):
    if player.item is not None:
        return

    choose_default_item(
        game,
        player,
        old_item=None,
    )


def prepare_self_play_game(
    seed=None,
):
    game = setup_game(
        seed=seed
    )

    # Rename both players so the data clearly
    # represents AI-vs-AI games.
    game.players[0].name = "AI_A"
    game.players[1].name = "AI_B"

    for player in game.players:
        choose_self_play_mage(
            player
        )

        random.shuffle(
            player.deck_hidden
        )

        draw_starting_hand(
            player,
            3,
        )

    # Both AIs need starting items.
    #
    # Respect first-player order.
    first_index = next(
        (
            index
            for index, player
            in enumerate(game.players)
            if player.has_first_player_token
        ),
        0,
    )

    order = [
        first_index,
        (first_index + 1)
        % len(game.players),
    ]

    for index in order:
        choose_starting_item(
            game,
            game.players[index],
        )

    game.current_phase = "collect"
    game.current_setup_step = "setup_done"

    game.pending_item_order = []
    game.waiting_for_human_item_choice = False

    game.game_record = (
        start_new_game_record()
    )

    game.memory_saved = False

    game.self_play = True
    game.ended_by_safety_limit = False
    game.ai_move_history = []

    game.safety_debug = {
        "reason": None,
        "round": None,
        "actions_this_round": 0,
        "total_actions": 0,
        "last_moves": [],
    }

    return game


def get_next_active_player_index(
    game,
    current_index,
):
    player_count = len(
        game.players
    )

    for offset in range(
        1,
        player_count + 1,
    ):
        index = (
            current_index + offset
        ) % player_count

        if not game.players[
            index
        ].passed:
            return index

    return current_index


def run_self_play_collection(
    game,
):
    game.current_phase = "collect"

    for player in game.players:
        run_collect_effects(
            game,
            player,
        )

    game.current_phase = "action"


def handle_self_play_pass(
    game,
    player,
):
    old_item = player.item

    if old_item:
        old_item.tapped = False

    player.item = None

    if game.items_pool:
        choose_default_item(
            game,
            player,
            old_item=old_item,
        )


def execute_self_play_turn(
    game,
    player,
):
    if player.passed:
        return None

    # Store failed moves separately
    # for each AI player.
    if not hasattr(
        game,
        "self_play_failed_moves",
    ):
        game.self_play_failed_moves = {}

    player_key = id(player)

    game.self_play_failed_moves[
        player_key
    ] = set()

    for attempt in range(20):

        move = execute_ai_move(
            game,
            player,
        )

        if not move:
            continue

        # ---------------------------------
        # FAILED MOVE
        # ---------------------------------
        if move.get("type") == "failed":

            signature = (
                move.get(
                    "failed_move_type"
                ),
                move.get(
                    "card_name"
                ),
            )

            game.self_play_failed_moves[
                player_key
            ].add(
                signature
            )

            print(
                f"{player.name}: "
                f"{signature[0]} "
                f"{signature[1]} failed. "
                f"Choosing another move..."
            )

            # SAME PLAYER tries again.
            continue

        # ---------------------------------
        # SUCCESS
        # ---------------------------------

        # The turn succeeded, so previous
        # failed-move blocks are no longer
        # needed.
        game.self_play_failed_moves.pop(
            player_key,
            None,
        )

        if move.get("type") == "pass":
            handle_self_play_pass(
                game,
                player,
            )

        return move

    raise RuntimeError(
        f"{player.name} failed to execute "
        "a valid move after 20 attempts."
    )

def untap_all(
    player,
):
    cards = []

    if player.mage:
        cards.append(
            player.mage
        )

    if player.item:
        cards.append(
            player.item
        )

    cards.extend(
        player.played
    )

    cards.extend(
        player.monuments
    )

    cards.extend(
        player.places
    )

    for card in cards:
        card.tapped = False


def start_next_self_play_round(
    game,
):
    reset_round_state(
        game
    )

    for player in game.players:
        untap_all(
            player
        )

    game.round_no += 1
    if getattr(
        game,
        "self_play_verbose",
        False,
    ):
        print()
        print("=" * 70)
        print(
            f"STARTING ROUND {game.round_no}"
        )
        print("=" * 70)

        print_game_state(game)

    first_player_index = next(
        (
            index
            for index, player
            in enumerate(game.players)
            if player.has_first_player_token
        ),
        0,
    )

    game.current_player_index = (
        first_player_index
    )

    run_self_play_collection(
        game
    )


def run_single_self_play_game(
    seed=None,
    verbose=False,
    save_memory=True,
):
    game = prepare_self_play_game(
        seed=seed
    )
    game.self_play_verbose = verbose

    if verbose:
        print()
        print("=" * 70)
        print("SELF-PLAY GAME")
        print(
            f"{game.players[0].name} "
            f"VS "
            f"{game.players[1].name}"
        )
        print("=" * 70)

        print_game_state(game)

    run_self_play_collection(
        game
    )

    action_count = 0

    while (
        not game.game_over
        and game.round_no
        <= MAX_ROUNDS
    ):
        # -------------------------
        # ACTION PHASE
        # -------------------------

        actions_this_round = 0

        while (
            not game.game_over
            and not all(
                player.passed
                for player
                in game.players
            )
        ):
            actions_this_round += 1
            action_count += 1

            if (
                actions_this_round
                > MAX_ACTIONS_PER_ROUND
            ):
                game.ended_by_safety_limit = True

                game.safety_debug[
                    "reason"
                ] = "max_actions_per_round"

                game.safety_debug[
                    "round"
                ] = game.round_no

                game.safety_debug[
                    "actions_this_round"
                ] = actions_this_round

                game.safety_debug[
                    "total_actions"
                ] = action_count

                game.game_log.append(
                    "Self-play exceeded "
                    "MAX_ACTIONS_PER_ROUND."
                )

                break

            current_player = (
                game.players[
                    game.current_player_index
                ]
            )

            if current_player.passed:
                game.current_player_index = (
                    get_next_active_player_index(
                        game,
                        game.current_player_index,
                    )
                )

                continue

            move = (
                execute_self_play_turn(
                    game,
                    current_player,
                )
            )
            if move:
                game.safety_debug[
                    "last_moves"
                ].append({
                    "round": game.round_no,
                    "player": current_player.name,
                    "type": move.get("type"),
                    "card": move.get("card_name"),
                    "vp": get_vp(
                        game,
                        current_player,
                    ),
                    "passed": current_player.passed,
                })

                game.safety_debug[
                    "last_moves"
                ] = (
                    game.safety_debug[
                        "last_moves"
                    ][-20:]
                )

            if verbose and move:

                move_type = move.get(
                    "type",
                    "unknown",
                )

                card = move.get(
                    "card_name"
                )

                if move_type == "pass":
                    action_text = "PASS"

                elif card:
                    action_text = (
                        f"{move_type} -> {card}"
                    )

                else:
                    action_text = move_type

                print(
                    f"Round {game.round_no:02d} | "
                    f"{current_player.name} -> "
                    f"{action_text}"
                )

                print_game_state(game)

            if getattr(
                game,
                "force_victory_check",
                False,
            ):
                break

            game.current_player_index = (
                get_next_active_player_index(
                    game,
                    game.current_player_index,
                )
            )

        if getattr(
            game,
            "ended_by_safety_limit",
            False,
        ):
            break

        # -------------------------
        # VICTORY CHECK
        # -------------------------

        check_victory(
            game
        )

        if game.game_over:
            break

        start_next_self_play_round(
            game
        )

    if not game.game_over:
        # Safety fallback.
        #
        # If we hit the round limit,
        # select the current VP leader
        # instead of producing no result.

        if not getattr(
            game,
            "ended_by_safety_limit",
            False,
        ):
            game.ended_by_safety_limit = True

            game.safety_debug[
                "reason"
            ] = "max_rounds"

            game.safety_debug[
                "round"
            ] = game.round_no

            game.safety_debug[
                "total_actions"
            ] = action_count
        scores = check_victory(
            game
        )

        leader = max(
            game.players,
            key=lambda p:
                p.victory_points,
        )

        game.game_over = True
        game.winner = leader.name
        game.ended_by_safety_limit = True

        game.game_log.append(
            "Self-play ended by "
            "round safety limit."
        )

    finish_game_record(
        game.game_record,
        game,
    )

    if save_memory:
        save_game_record(
            game.game_record
        )
    if verbose:
        print()
        print("=" * 70)
        print("GAME OVER")
        print("=" * 70)

        print_game_state(game)

        print(
            f"WINNER: {game.winner}"
        )

        print(
            f"Rounds played: {game.round_no}"
        )

        print(
            f"Total actions: {action_count}"
        )

        print("=" * 70)
    return {
        "winner": game.winner,
        "rounds": game.round_no,
        "actions": action_count,
        "scores": {
            player.name:
                player.victory_points
            for player in game.players
        },
        "game_record": game.game_record,
        "ended_by_safety_limit": getattr(
            game,
            "ended_by_safety_limit",
            False,
        ),
        "safety_debug": getattr(
            game,
            "safety_debug",
            {},
        ),
    }



# ============================================================
# COUNTERFACTUAL / HISTORICAL SIMULATION
# ============================================================

def _card_name(card):
    if card is None:
        return None

    return (
        getattr(
            card.definition,
            "name",
            None,
        )
        or card.definition.raw_data.get(
            "name_en"
        )
        or card.definition.raw_data.get(
            "id"
        )
    )


def _definition_id(card):
    if card is None:
        return None

    return (
        getattr(
            card.definition,
            "card_id",
            None,
        )
        or card.definition.raw_data.get(
            "id"
        )
    )


def _build_card_definition_lookup():
    cards = load_all_cards()

    by_id = {}
    by_name = {}

    for card in cards:
        definition = card.definition

        card_id_value = (
            getattr(
                definition,
                "card_id",
                None,
            )
            or definition.raw_data.get(
                "id"
            )
        )

        card_name_value = (
            getattr(
                definition,
                "name",
                None,
            )
            or definition.raw_data.get(
                "name_en"
            )
            or card_id_value
        )

        if card_id_value:
            by_id[
                str(card_id_value)
            ] = definition

        if card_name_value:
            normalized = str(
                card_name_value
            ).replace(
                "’",
                "'",
            )

            by_name[
                normalized
            ] = definition

    return (
        by_id,
        by_name,
    )


_CARD_LOOKUP_CACHE = None


def _get_card_definition_lookup():
    global _CARD_LOOKUP_CACHE

    if _CARD_LOOKUP_CACHE is None:
        _CARD_LOOKUP_CACHE = (
            _build_card_definition_lookup()
        )

    return _CARD_LOOKUP_CACHE


def _snapshot_card_to_instance(
    card_data,
):
    if not card_data:
        return None

    by_id, by_name = (
        _get_card_definition_lookup()
    )

    if isinstance(
        card_data,
        str,
    ):
        card_id_value = None
        card_name_value = card_data
        tapped = False
        stored_essence = {}

    else:
        card_id_value = (
            card_data.get(
                "card_id"
            )
        )

        card_name_value = (
            card_data.get(
                "name"
            )
            or card_data.get(
                "card_name"
            )
        )

        tapped = bool(
            card_data.get(
                "tapped",
                False,
            )
        )

        stored_essence = (
            card_data.get(
                "stored_essence",
                {},
            )
            or {}
        )

    definition = None

    if card_id_value is not None:
        definition = by_id.get(
            str(
                card_id_value
            )
        )

    if (
        definition is None
        and card_name_value
    ):
        normalized = str(
            card_name_value
        ).replace(
            "’",
            "'",
        )

        definition = by_name.get(
            normalized
        )

    if definition is None:
        raise ValueError(
            "Historical snapshot references "
            f"unknown card: {card_data}"
        )

    instance = CardInstance(
        definition=definition
    )

    instance.tapped = tapped

    for essence in instance.stored_essence:
        instance.stored_essence[
            essence
        ] = int(
            stored_essence.get(
                essence,
                0,
            )
        )

    return instance


def _snapshot_cards_to_instances(
    values,
):
    return [
        card
        for card in (
            _snapshot_card_to_instance(
                value
            )
            for value in (
                values or []
            )
        )
        if card is not None
    ]


def _known_artifact_ids_from_snapshot(
    snapshot,
):
    known = set()

    for player_data in snapshot.get(
        "players",
        [],
    ):
        for zone in [
            "hand",
            "played",
            "discard",
            "deck_top",
        ]:
            for card_data in player_data.get(
                zone,
                [],
            ):
                card = (
                    _snapshot_card_to_instance(
                        card_data
                    )
                )

                if card is not None:
                    card_id_value = (
                        _definition_id(
                            card
                        )
                    )

                    if card_id_value:
                        known.add(
                            card_id_value
                        )

    return known


def _available_artifact_templates(
    excluded_ids,
):
    candidates = []

    for card in load_all_cards():
        card_type_value = (
            getattr(
                card.definition,
                "card_type",
                None,
            )
            or card.definition.raw_data.get(
                "type"
            )
        )

        if card_type_value not in {
            "artifact",
            "creature",
            "dragon",
        }:
            continue

        card_id_value = (
            _definition_id(
                card
            )
        )

        if (
            card_id_value
            and card_id_value
            not in excluded_ids
        ):
            candidates.append(
                card
            )

    return candidates


def _available_monument_templates(
    excluded_ids,
):
    candidates = []

    for card in load_all_cards():
        card_type_value = (
            getattr(
                card.definition,
                "card_type",
                None,
            )
            or card.definition.raw_data.get(
                "type"
            )
        )

        if (
            card_type_value
            != "monument"
        ):
            continue

        card_id_value = (
            _definition_id(
                card
            )
        )

        if (
            card_id_value
            and card_id_value
            not in excluded_ids
        ):
            candidates.append(
                card
            )

    return candidates


def _clone_template(
    template,
):
    return CardInstance(
        definition=template.definition
    )


def restore_game_from_snapshot(
    snapshot,
    seed=0,
):
    """
    Reconstruct a playable GameState from a saved memory snapshot.

    Older memories store the exact current hand/board/discard and only
    the top three hidden-deck cards plus deck_count. The unknown hidden
    remainder is therefore sampled from unused artifacts.

    This is intentional Monte-Carlo reconstruction. Several seeds let
    counterfactual evaluation average over multiple plausible futures.
    """
    rng = random.Random(
        seed
    )

    player_snapshots = (
        snapshot.get(
            "players",
            [],
        )
    )

    if len(
        player_snapshots
    ) < 2:
        raise ValueError(
            "Historical snapshot does not "
            "contain two players."
        )

    players = []

    for player_data in (
        player_snapshots
    ):
        player = Player(
            player_data.get(
                "name",
                "Unknown",
            )
        )

        essence = (
            player_data.get(
                "essence",
                {},
            )
            or {}
        )

        for key in player.essence_pool:
            player.essence_pool[
                key
            ] = int(
                essence.get(
                    key,
                    0,
                )
            )

        player.victory_points = int(
            player_data.get(
                "vp",
                0,
            )
        )

        player.mage = (
            _snapshot_card_to_instance(
                player_data.get(
                    "mage"
                )
            )
        )

        player.item = (
            _snapshot_card_to_instance(
                player_data.get(
                    "item"
                )
            )
        )

        player.hand = (
            _snapshot_cards_to_instances(
                player_data.get(
                    "hand",
                    [],
                )
            )
        )

        player.played = (
            _snapshot_cards_to_instances(
                player_data.get(
                    "played",
                    [],
                )
            )
        )

        player.monuments = (
            _snapshot_cards_to_instances(
                player_data.get(
                    "monuments",
                    [],
                )
            )
        )

        player.places = (
            _snapshot_cards_to_instances(
                player_data.get(
                    "places",
                    [],
                )
            )
        )

        player.discard = (
            _snapshot_cards_to_instances(
                player_data.get(
                    "discard",
                    [],
                )
            )
        )

        player.deck_hidden = (
            _snapshot_cards_to_instances(
                player_data.get(
                    "deck_top",
                    [],
                )
            )
        )

        player.has_first_player_token = bool(
            player_data.get(
                "has_first_player_token",
                False,
            )
        )

        player.passed = bool(
            player_data.get(
                "passed",
                False,
            )
        )

        players.append(
            player
        )

    known_artifact_ids = (
        _known_artifact_ids_from_snapshot(
            snapshot
        )
    )

    artifact_templates = (
        _available_artifact_templates(
            known_artifact_ids
        )
    )

    rng.shuffle(
        artifact_templates
    )

    artifact_cursor = 0

    for player, player_data in zip(
        players,
        player_snapshots,
    ):
        desired_deck_count = int(
            player_data.get(
                "deck_count",
                len(
                    player.deck_hidden
                ),
            )
        )

        missing_count = max(
            0,
            desired_deck_count
            - len(
                player.deck_hidden
            ),
        )

        for _ in range(
            missing_count
        ):
            if (
                artifact_cursor
                >= len(
                    artifact_templates
                )
            ):
                break

            player.deck_hidden.append(
                _clone_template(
                    artifact_templates[
                        artifact_cursor
                    ]
                )
            )

            artifact_cursor += 1

    market_monuments = (
        _snapshot_cards_to_instances(
            snapshot.get(
                "market_monuments",
                [],
            )
        )
    )

    market_places = (
        _snapshot_cards_to_instances(
            snapshot.get(
                "market_places",
                [],
            )
        )
    )

    items_pool = (
        _snapshot_cards_to_instances(
            snapshot.get(
                "items_pool",
                [],
            )
        )
    )

    known_monument_ids = set()

    for card in market_monuments:
        card_id_value = (
            _definition_id(
                card
            )
        )

        if card_id_value:
            known_monument_ids.add(
                card_id_value
            )

    for player in players:
        for card in player.monuments:
            card_id_value = (
                _definition_id(
                    card
                )
            )

            if card_id_value:
                known_monument_ids.add(
                    card_id_value
                )

    monument_templates = (
        _available_monument_templates(
            known_monument_ids
        )
    )

    rng.shuffle(
        monument_templates
    )

    monument_deck_count = int(
        snapshot.get(
            "monument_deck_count",
            0,
        )
    )

    monument_deck = [
        _clone_template(
            template
        )
        for template
        in monument_templates[
            :monument_deck_count
        ]
    ]

    game = GameState(
        players=players,
        market_monuments=(
            market_monuments
        ),
        monument_deck=(
            monument_deck
        ),
        market_places=(
            market_places
        ),
        items_pool=(
            items_pool
        ),
    )

    game.round_no = int(
        snapshot.get(
            "round",
            1,
        )
    )

    game.current_phase = (
        snapshot.get(
            "phase",
            "action",
        )
        or "action"
    )

    game.current_player_index = int(
        snapshot.get(
            "current_player_index",
            0,
        )
    )

    if not (
        0
        <= game.current_player_index
        < len(
            game.players
        )
    ):
        game.current_player_index = 0

    game.first_player_token_available = bool(
        snapshot.get(
            "first_player_token_available",
            False,
        )
    )

    game.game_over = bool(
        snapshot.get(
            "game_over",
            False,
        )
    )

    game.winner = (
        snapshot.get(
            "winner"
        )
    )

    game.force_victory_check = False
    game.current_setup_step = (
        "setup_done"
    )

    game.pending_item_order = []
    game.waiting_for_human_item_choice = False

    game.self_play = True
    game.counterfactual_mode = True
    game.counterfactual_approximate = True

    game.ended_by_safety_limit = False
    game.ai_move_history = []

    game.safety_debug = {
        "reason": None,
        "round": None,
        "actions_this_round": 0,
        "total_actions": 0,
        "last_moves": [],
    }

    return game


def execute_forced_candidate_move(
    game,
    player,
    move,
):
    """
    Execute one specific candidate, including use_power.
    """
    move_type = (
        move.get(
            "type"
        )
        or move.get(
            "move_type"
        )
    )

    if move_type == "play_card":
        source_card = next(
            (
                card
                for card
                in player.hand
                if card_id(
                    card
                )
                == move.get(
                    "card_id"
                )
            ),
            None,
        )

        if source_card is None:
            return False

        placement_cost = (
            get_effective_placement_cost(
                player,
                source_card,
            )
        )

        discount_choices = None
        wild_choices = None

        if placement_cost:
            discount_choices = (
                choose_discount_for_ai(
                    player,
                    placement_cost,
                )
            )

            wild_choices = (
                choose_ai_wild_payment_for_cost(
                    player,
                    placement_cost,
                    discount_choices=(
                        discount_choices
                    ),
                )
            )

        play_card_from_hand(
            game,
            player,
            move[
                "card_id"
            ],
            wild_choices=(
                wild_choices
            ),
            discount_choices=(
                discount_choices
            ),
        )

        return True

    if move_type == "use_power":
        source_card = next(
            (
                card
                for card
                in get_controlled_cards(
                    player
                )
                if card_id(
                    card
                )
                == move.get(
                    "card_id"
                )
            ),
            None,
        )

        if source_card is None:
            return False

        selected_power = None

        for power in (
            source_card.definition.raw_data.get(
                "powers",
                [],
            )
        ):
            if int(
                power.get(
                    "power_index",
                    -1,
                )
            ) == int(
                move.get(
                    "power_index",
                    -2,
                )
            ):
                selected_power = power
                break

        if selected_power is None:
            return False

        x_value = (
            choose_ai_x_value(
                selected_power,
                player,
            )
        )

        wild_choices = (
            choose_ai_wild_payment(
                player,
                selected_power,
            )
        )

        target_choices = {}

        target_card_id = (
            choose_ai_straighten_target(
                player,
                source_card,
                selected_power,
            )
        )

        if target_card_id:
            target_choices[
                "straighten_target"
            ] = target_card_id

        use_power(
            game,
            player,
            move[
                "card_id"
            ],
            move[
                "power_index"
            ],
            wild_choices=(
                wild_choices
            ),
            target_choices=(
                target_choices
            ),
            x_value=(
                x_value
            ),
        )

        return True

    if move_type == "discard":
        reward_type = (
            move.get(
                "reward_type"
            )
            or "essence"
        )

        choices = (
            move.get(
                "choices"
            )
            or move.get(
                "reward_choices"
            )
        )

        if (
            reward_type
            == "essence"
            and not choices
        ):
            choices = [
                "elan",
                "life",
            ]

        discard_card_for_resources(
            game,
            player,
            move[
                "card_id"
            ],
            reward_type,
            choices,
        )

        return True

    if move_type == "buy_monument":
        buy_monument(
            game,
            player,
            move[
                "market_index"
            ],
        )

        return True

    if (
        move_type
        == "buy_place_of_power"
    ):
        buy_place_of_power(
            game,
            player,
            move[
                "market_index"
            ],
        )

        return True

    if move_type == "pass":
        pass_turn(
            game,
            player,
        )

        handle_self_play_pass(
            game,
            player,
        )

        return True

    return False


def _rollout_score(
    game,
    player_name,
):
    player = find_player_by_name(
        game,
        player_name,
    )

    if player is None:
        return -999.0

    opponents = [
        other
        for other in game.players
        if other.name
        != player_name
    ]

    opponent = (
        opponents[
            0
        ]
        if opponents
        else None
    )

    player_vp = get_vp(
        game,
        player,
    )

    opponent_vp = (
        get_vp(
            game,
            opponent,
        )
        if opponent
        else 0
    )

    score = float(
        player_vp
        - opponent_vp
    )

    if game.game_over:
        if (
            game.winner
            == player_name
        ):
            score += 10.0

        elif game.winner:
            score -= 10.0

    return score


def continue_counterfactual_rollout(
    game,
    max_actions=120,
    max_additional_rounds=8,
):
    starting_round = (
        game.round_no
    )

    action_count = 0

    while (
        not game.game_over
        and action_count
        < max_actions
        and game.round_no
        <= (
            starting_round
            + max_additional_rounds
        )
    ):
        if all(
            player.passed
            for player in game.players
        ):
            check_victory(
                game
            )

            if game.game_over:
                break

            start_next_self_play_round(
                game
            )

            continue

        current_player = (
            game.players[
                game.current_player_index
            ]
        )

        if current_player.passed:
            game.current_player_index = (
                get_next_active_player_index(
                    game,
                    game.current_player_index,
                )
            )

            continue

        try:
            execute_self_play_turn(
                game,
                current_player,
            )

        except Exception:
            break

        action_count += 1

        if getattr(
            game,
            "force_victory_check",
            False,
        ):
            check_victory(
                game
            )

            if game.game_over:
                break

            game.force_victory_check = (
                False
            )

        game.current_player_index = (
            get_next_active_player_index(
                game,
                game.current_player_index,
            )
        )

    if not game.game_over:
        check_victory(
            game
        )

    return action_count


def evaluate_counterfactual_responses(
    snapshot,
    responding_player_name="AI Companion",
    samples_per_move=3,
    max_actions=120,
    seed=50000,
):
    """
    Historical counterfactual evaluator.

    For one saved state it:
      - reconstructs a plausible live state,
      - generates all legal moves,
      - tries each move,
      - plays forward,
      - measures VP/win outcome,
      - repeats with different plausible hidden-deck completions.

    Old snapshots do not contain the full hidden deck, so this is a
    Monte-Carlo estimate rather than an exact reconstruction.
    """
    first_game = (
        restore_game_from_snapshot(
            snapshot,
            seed=seed,
        )
    )

    first_player = (
        find_player_by_name(
            first_game,
            responding_player_name,
        )
    )

    if first_player is None:
        return []

    legal_moves = (
        get_ai_legal_moves(
            first_game,
            first_player,
        )
    )

    results = []

    for move in legal_moves:
        rollout_scores = []
        successful_rollouts = 0

        for sample_index in range(
            samples_per_move
        ):
            sample_seed = (
                seed
                + sample_index
            )

            base_game = (
                restore_game_from_snapshot(
                    snapshot,
                    seed=sample_seed,
                )
            )

            copied_game, copy_error = (
                clone_game_for_simulation(
                    base_game
                )
            )

            if copied_game is None:
                continue

            copied_player = (
                find_player_by_name(
                    copied_game,
                    responding_player_name,
                )
            )

            if copied_player is None:
                continue

            try:
                success = (
                    execute_forced_candidate_move(
                        copied_game,
                        copied_player,
                        move,
                    )
                )

            except Exception:
                success = False

            if not success:
                continue

            copied_game.current_player_index = (
                get_next_active_player_index(
                    copied_game,
                    copied_game.current_player_index,
                )
            )

            continue_counterfactual_rollout(
                copied_game,
                max_actions=(
                    max_actions
                ),
            )

            rollout_scores.append(
                _rollout_score(
                    copied_game,
                    responding_player_name,
                )
            )

            successful_rollouts += 1

        if rollout_scores:
            average_score = (
                sum(
                    rollout_scores
                )
                / len(
                    rollout_scores
                )
            )

            minimum_score = min(
                rollout_scores
            )

            maximum_score = max(
                rollout_scores
            )

        else:
            average_score = -999.0
            minimum_score = -999.0
            maximum_score = -999.0

        results.append({
            "move": move,
            "average_rollout_score": round(
                average_score,
                3,
            ),
            "minimum_rollout_score": round(
                minimum_score,
                3,
            ),
            "maximum_rollout_score": round(
                maximum_score,
                3,
            ),
            "successful_rollouts": (
                successful_rollouts
            ),
            "samples_requested": (
                samples_per_move
            ),
        })

    results.sort(
        key=lambda item:
            item[
                "average_rollout_score"
            ],
        reverse=True,
    )

    return results

def run_self_play_batch(
    games=1,
    starting_seed=1000,
    verbose=False,
):
    results = []

    wins = {
        "AI_A": 0,
        "AI_B": 0,
    }

    failures = 0

    for game_number in range(
        1,
        games + 1,
    ):
        seed = (
            starting_seed
            + game_number
        )

        try:
            result = (
                run_single_self_play_game(
                    seed=seed,
                    verbose=verbose,
                )
            )

            results.append(
                result
            )

            winner = result[
                "winner"
            ]

            wins[winner] = (
                wins.get(
                    winner,
                    0,
                )
                + 1
            )

            print(
                f"[{game_number}/{games}] "
                f"Winner={winner} | "
                f"Rounds={result['rounds']} | "
                f"Actions={result['actions']} | "
                f"Scores={result['scores']}"
            )

        except Exception as error:
            failures += 1

            print(
                "\nSELF-PLAY GAME FAILED"
            )

            print(
                f"Game: {game_number}"
            )

            print(
                f"Seed: {seed}"
            )

            print(
                f"Error: {error}"
            )

            traceback.print_exc()

    print(
        "\n"
        + "=" * 60
    )

    print(
        "SELF-PLAY SUMMARY"
    )

    print(
        "=" * 60
    )

    print(
        f"Games requested: {games}"
    )
 
    print(
        f"Games completed: "
        f"{len(results)}"
    )

    print(
        f"Failures: {failures}"
    )

    print(
        f"AI_A wins: "
        f"{wins.get('AI_A', 0)}"
    )

    print(
        f"AI_B wins: "
        f"{wins.get('AI_B', 0)}"
    )

    if results:
        average_rounds = (
            sum(
                result["rounds"]
                for result in results
            )
            / len(results)
        )

        average_actions = (
            sum(
                result["actions"]
                for result in results
            )
            / len(results)
        )

        print(
            f"Average rounds: "
            f"{average_rounds:.2f}"
        )

        print(
            f"Average actions: "
            f"{average_actions:.2f}"
        )

    print(
        "=" * 60
    )

    return results


if __name__ == "__main__":
    run_self_play_batch(
        games=100,
        starting_seed=1000,
        verbose=False,
    )