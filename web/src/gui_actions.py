from rules_engine import (
    RulesError,
    play_card_from_hand,
    buy_monument,
    buy_place_of_power,
    discard_card_for_resources,
    use_power,
    pass_turn,
    check_victory,
)
from opponent_model import update_from_human_move
from game_memory import record_move, snapshot_game\




def get_card_id(card):
    return (
        getattr(card.definition, "card_id", None)
        or card.definition.raw_data.get("id")
    )


def log_error(game, error):
    game.game_log.append(f"Action failed: {error}")


def gui_play_card(game, player, card):
    try:
        from rules_engine import get_effective_placement_cost
        state_before = snapshot_game(game)

        card_id = get_card_id(card)

        cost = get_effective_placement_cost(player, card)

        discount_choices = None
        wild_choices = None

        if cost:
            discount = cost.get("discount", {})
            discount_amount = int(discount.get("amount", 0))

            if discount_amount > 0:
                essence_cost = cost.get("essence", {})

                possible = []

                for essence in ["elan", "life", "calm", "death"]:
                    for _ in range(int(essence_cost.get(essence, 0))):
                        possible.append(essence)

                # temporary smart default:
                # discount the essence you have least of
                discount_choices = sorted(
                    possible,
                    key=lambda e: player.essence_pool.get(e, 0)
                )[:discount_amount]

            wild = cost.get("wild")

            if wild:
                if isinstance(wild, int):
                    wild_count = wild
                    allowed = ["elan", "life", "calm", "death", "gold"]
                else:
                    wild_count = wild.get("count", 0)
                    allowed = wild.get("allowed", ["elan", "life", "calm", "death", "gold"])

                if isinstance(wild_count, int) and wild_count > 0:
                    wild_choices = []

                    for _ in range(wild_count):
                        possible = [
                            e for e in allowed
                            if player.essence_pool.get(e, 0) > wild_choices.count(e)
                        ]

                        if not possible:
                            break

                        chosen = max(
                            possible,
                            key=lambda e: player.essence_pool.get(e, 0) - wild_choices.count(e)
                        )

                        wild_choices.append(chosen)

        played = play_card_from_hand(
            game,
            player,
            card_id,
            wild_choices=wild_choices,
            discount_choices=discount_choices
        )

        game.gui_human_action_done = True

        game.game_log.append(
            f"{player.name} played {card.definition.name}"
        )
        update_from_human_move(
            game,
            "play_card",
            card_name=card.definition.name
        )
  

        return played

    except RulesError as e:
        log_error(game, e)
        return None

    except Exception as e:
        log_error(game, e)
        return None


def gui_buy_monument(game, player, source):
    try:
        state_before = snapshot_game(game)
        market_index = int(source.split("_")[-1]) - 1

        bought = buy_monument(
            game,
            player,
            market_index
        )

        game.gui_human_action_done = True

        game.game_log.append(
            f"{player.name} bought monument {bought.definition.name}"
        )

        update_from_human_move(
            game,
            "buy_monument",
            card_name=bought.definition.name
        )
        record_move(
            game_record=game.game_record,
            game=game,
            state_before=state_before,
            player_name=player.name,
            move_type="buy_monument",
            description=f"{player.name} bought monument {bought.definition.name}.",
            card_name=bought.definition.name,
        )

        

        return bought

    except Exception as e:
        log_error(game, e)
        return None


def gui_buy_place(game, player, source):
    try:
        # Must be captured before buying changes the market and player state
        state_before = snapshot_game(game)

        market_index = int(source.split("_")[-1]) - 1

        bought = buy_place_of_power(
            game,
            player,
            market_index
        )

        game.gui_human_action_done = True

        game.game_log.append(
            f"{player.name} bought Place of Power {bought.definition.name}"
        )

        update_from_human_move(
            game,
            "buy_place_of_power",
            card_name=bought.definition.name
        )

        record_move(
            game_record=game.game_record,
            game=game,
            state_before=state_before,
            player_name=player.name,
            move_type="buy_place_of_power",
            description=(
                f"{player.name} bought Place of Power "
                f"{bought.definition.name}."
            ),
            card_name=bought.definition.name,
        )

        return bought

    except Exception as e:
        log_error(game, e)
        return None


def gui_discard_for_gold(game, player, card):
    try:
        # Capture hand and essence before discarding
        state_before = snapshot_game(game)

        card_id = get_card_id(card)

        discarded = discard_card_for_resources(
            game,
            player,
            card_id,
            reward_type="gold"
        )

        game.gui_human_action_done = True

        game.game_log.append(
            f"{player.name} discarded {card.definition.name} for gold"
        )

        update_from_human_move(
            game,
            "discard",
            card_name=card.definition.name,
            essence_choices=["gold"]
        )

        record_move(
            game_record=game.game_record,
            game=game,
            state_before=state_before,
            player_name=player.name,
            move_type="discard",
            description=(
                f"{player.name} discarded "
                f"{card.definition.name} for 1 gold."
            ),
            card_name=card.definition.name,
            reward_type="gold",
            reward_choices=["gold"],
        )

        return discarded

    except RulesError as e:
        log_error(game, e)
        return None

    except Exception as e:
        log_error(game, e)
        return None
    


def gui_discard_for_essence(
    game,
    player,
    card,
    choices=("elan", "life")
):
    try:
        # Capture hand and essence before discarding
        state_before = snapshot_game(game)

        card_id = get_card_id(card)

        discarded = discard_card_for_resources(
            game,
            player,
            card_id,
            reward_type="essence",
            choices=list(choices)
        )

        game.gui_human_action_done = True

        game.game_log.append(
            f"{player.name} discarded {card.definition.name} for {choices}"
        )

        update_from_human_move(
            game,
            "discard",
            card_name=card.definition.name,
            essence_choices=list(choices)
        )

        record_move(
            game_record=game.game_record,
            game=game,
            state_before=state_before,
            player_name=player.name,
            move_type="discard",
            description=(
                f"{player.name} discarded {card.definition.name} "
                f"for {', '.join(choices)}."
            ),
            card_name=card.definition.name,
            reward_type="essence",
            reward_choices=list(choices),
        )

        return discarded

    except RulesError as e:
        log_error(game, e)
        return None

    except Exception as e:
        log_error(game, e)
        return None

def gui_use_first_power(game, player, card):
    try:
        card_id = get_card_id(card)

        powers = card.definition.raw_data.get(
            "powers",
            []
        )

        if not powers:
            game.game_log.append(
                f"{card.definition.name} has no power."
            )
            return None

        power_index = powers[0].get(
            "power_index",
            0
        )

        result = use_power(
            game,
            player,
            source_card_id=card_id,
            power_index=power_index,
        )

        game.gui_human_action_done = True

        game.game_log.append(
            f"{player.name} used power on {card.definition.name}"
        )
        update_from_human_move(
            game,
            "use_power",
            card_name=card.definition.name
        )
  


        return result

    except Exception as e:
        log_error(game, e)
        return None


def gui_pass(game, player):
    try:
        # Capture state before passed status, card draw and token change
        state_before = snapshot_game(game)

        pass_turn(
            game,
            player
        )

        game.gui_human_action_done = True

        game.game_log.append(
            f"{player.name} passed."
        )

        record_move(
            game_record=game.game_record,
            game=game,
            state_before=state_before,
            player_name=player.name,
            move_type="pass",
            description=f"{player.name} passed.",
        )

        check_victory(game)

        return True

    except RulesError as e:
        log_error(game, e)
        return False

    except Exception as e:
        log_error(game, e)
        return False