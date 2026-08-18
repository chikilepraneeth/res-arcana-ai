from typing import Any


ESSENCES = [
    "elan",
    "life",
    "calm",
    "death",
    "gold",
]


def _get_player(
    state: dict[str, Any],
    player_name: str,
):
    for player in state.get(
        "players",
        [],
    ):
        if player.get("name") == player_name:
            return player

    return None


def _safe_len(value):
    if isinstance(value, list):
        return len(value)

    return 0


def _safe_count_cards(
    cards,
):
    if not isinstance(cards, list):
        return 0

    return len(cards)


def encode_state(
    state: dict[str, Any],
    ai_name: str,
    opponent_name: str,
) -> list[float]:

    ai = _get_player(
        state,
        ai_name,
    )

    opponent = _get_player(
        state,
        opponent_name,
    )

    if ai is None or opponent is None:
        raise ValueError(
            "Could not find both players "
            "inside state."
        )

    features = []

    # ========================================================
    # ROUND / TURN INFORMATION
    # ========================================================

    features.append(
        float(
            state.get(
                "round",
                0,
            )
        )
    )

    current_player = state.get(
        "current_player",
    )

    features.append(
        1.0
        if current_player == ai_name
        else 0.0
    )

    features.append(
        1.0
        if current_player == opponent_name
        else 0.0
    )

    # ========================================================
    # VP
    # ========================================================

    ai_vp = float(
        ai.get(
            "vp",
            0,
        )
    )

    opponent_vp = float(
        opponent.get(
            "vp",
            0,
        )
    )

    features.append(ai_vp)
    features.append(opponent_vp)

    features.append(
        ai_vp - opponent_vp
    )

    # ========================================================
    # ESSENCE
    # ========================================================

    ai_essence = ai.get(
        "essence",
        {},
    )

    opponent_essence = opponent.get(
        "essence",
        {},
    )

    for essence in ESSENCES:
        features.append(
            float(
                ai_essence.get(
                    essence,
                    0,
                )
            )
        )

    for essence in ESSENCES:
        features.append(
            float(
                opponent_essence.get(
                    essence,
                    0,
                )
            )
        )

    features.append(
        float(
            sum(
                ai_essence.get(
                    essence,
                    0,
                )
                for essence in ESSENCES
            )
        )
    )

    features.append(
        float(
            sum(
                opponent_essence.get(
                    essence,
                    0,
                )
                for essence in ESSENCES
            )
        )
    )

    # ========================================================
    # HAND / DECK / DISCARD
    # ========================================================

    features.append(
        float(
            ai.get(
                "hand_count",
                _safe_len(
                    ai.get(
                        "hand",
                        [],
                    )
                ),
            )
        )
    )

    features.append(
        float(
            opponent.get(
                "hand_count",
                _safe_len(
                    opponent.get(
                        "hand",
                        [],
                    )
                ),
            )
        )
    )

    features.append(
        float(
            ai.get(
                "deck_count",
                0,
            )
        )
    )

    features.append(
        float(
            opponent.get(
                "deck_count",
                0,
            )
        )
    )

    features.append(
        float(
            ai.get(
                "discard_count",
                _safe_len(
                    ai.get(
                        "discard",
                        [],
                    )
                ),
            )
        )
    )

    features.append(
        float(
            opponent.get(
                "discard_count",
                _safe_len(
                    opponent.get(
                        "discard",
                        [],
                    )
                ),
            )
        )
    )

    # ========================================================
    # BOARD SIZE
    # ========================================================

    ai_played = _safe_count_cards(
        ai.get(
            "played",
            [],
        )
    )

    ai_monuments = _safe_count_cards(
        ai.get(
            "monuments",
            [],
        )
    )

    ai_places = _safe_count_cards(
        ai.get(
            "places",
            [],
        )
    )

    opp_played = _safe_count_cards(
        opponent.get(
            "played",
            [],
        )
    )

    opp_monuments = _safe_count_cards(
        opponent.get(
            "monuments",
            [],
        )
    )

    opp_places = _safe_count_cards(
        opponent.get(
            "places",
            [],
        )
    )

    features.extend([
        float(ai_played),
        float(ai_monuments),
        float(ai_places),
        float(opp_played),
        float(opp_monuments),
        float(opp_places),
    ])

    # ========================================================
    # TAPPED CARD COUNTS
    # ========================================================

    def count_tapped(player):

        count = 0

        for zone_name in [
            "played",
            "monuments",
            "places",
        ]:

            for card in player.get(
                zone_name,
                [],
            ):

                if (
                    isinstance(
                        card,
                        dict,
                    )
                    and card.get(
                        "tapped",
                        False,
                    )
                ):
                    count += 1

        return count

    features.append(
        float(
            count_tapped(ai)
        )
    )

    features.append(
        float(
            count_tapped(opponent)
        )
    )

    # ========================================================
    # STORED ESSENCE
    # ========================================================

    def stored_total(player):

        total = 0

        for zone_name in [
            "played",
            "monuments",
            "places",
        ]:

            for card in player.get(
                zone_name,
                [],
            ):

                if not isinstance(
                    card,
                    dict,
                ):
                    continue

                stored = card.get(
                    "stored_essence",
                    {},
                )

                total += sum(
                    int(value)
                    for value in stored.values()
                )

        return total

    features.append(
        float(
            stored_total(ai)
        )
    )

    features.append(
        float(
            stored_total(opponent)
        )
    )

    # ========================================================
    # PASS / FIRST PLAYER
    # ========================================================

    features.append(
        1.0
        if ai.get(
            "passed",
            False,
        )
        else 0.0
    )

    features.append(
        1.0
        if opponent.get(
            "passed",
            False,
        )
        else 0.0
    )

    features.append(
        1.0
        if ai.get(
            "has_first_player_token",
            False,
        )
        else 0.0
    )

    features.append(
        1.0
        if opponent.get(
            "has_first_player_token",
            False,
        )
        else 0.0
    )

    # ========================================================
    # MARKET
    # ========================================================

    features.append(
        float(
            len(
                state.get(
                    "market_monuments",
                    [],
                )
            )
        )
    )

    features.append(
        float(
            len(
                state.get(
                    "market_places",
                    [],
                )
            )
        )
    )

    # ========================================================
    # FINAL NORMALIZATION
    # ========================================================

    return features


def feature_count():
    dummy_state = {
        "round": 1,
        "players": [
            {
                "name": "AI",
                "essence": {},
                "vp": 0,
                "played": [],
                "monuments": [],
                "places": [],
            },
            {
                "name": "HUMAN",
                "essence": {},
                "vp": 0,
                "played": [],
                "monuments": [],
                "places": [],
            },
        ],
    }

    return len(
        encode_state(
            dummy_state,
            "AI",
            "HUMAN",
        )
    )