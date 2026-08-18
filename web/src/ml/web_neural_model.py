import json
import math
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

MODEL_FILE = (
    ROOT
    / "models"
    / "neural_counter_web.json"
)

HUMAN_NAME = "Chikile"
AI_NAME = "AI Companion"

ESSENCES = [
    "elan",
    "life",
    "calm",
    "death",
    "gold",
]

MOVE_TYPES = [
    "play_card",
    "use_power",
    "discard",
    "buy_monument",
    "buy_place_of_power",
    "pass",
]

NONE_CARD = "<NONE>"
UNK_CARD = "<UNK>"

BASE_STATE_FEATURE_COUNT = 40
MOVE_FEATURE_COUNT = 12

_MODEL = None


# ============================================================
# BASIC HELPERS
# ============================================================

def normalize_card_name(value):
    if value is None:
        return NONE_CARD

    text = str(value).strip()

    if not text:
        return NONE_CARD

    return text.replace("’", "'")


def snapshot_card_name(value):
    if value is None:
        return NONE_CARD

    if isinstance(value, str):
        return normalize_card_name(value)

    if isinstance(value, dict):
        return normalize_card_name(
            value.get("name")
            or value.get("card_name")
            or value.get("card_id")
        )

    return normalize_card_name(value)


def move_card_name(move):
    if not move:
        return NONE_CARD

    return normalize_card_name(
        move.get("card_name")
    )


def safe_float(
    value,
    default=0.0,
):
    try:
        return float(value)
    except (
        TypeError,
        ValueError,
    ):
        return default


def extract_power_index(move):
    if not move:
        return 0.0

    if move.get("power_index") is not None:
        return safe_float(
            move.get("power_index")
        )

    description = str(
        move.get(
            "description",
            "",
        )
    )

    match = re.search(
        r"\bpower\s+(\d+)\b",
        description,
        flags=re.IGNORECASE,
    )

    if match:
        return safe_float(
            match.group(1)
        )

    return 0.0


def get_player(
    state,
    player_name,
):
    for player in state.get(
        "players",
        [],
    ):
        if (
            player.get("name")
            == player_name
        ):
            return player

    return None


def card_index(
    card_name_value,
    card_vocab,
):
    name = normalize_card_name(
        card_name_value
    )

    return card_vocab.get(
        name,
        card_vocab.get(
            UNK_CARD,
            1,
        ),
    )


# ============================================================
# BASE STATE ENCODER
# EXACT SAME ORDER AS DESKTOP TRAINING MODEL
# ============================================================

def encode_base_state(
    state,
    ai_name,
    opponent_name,
):
    ai = get_player(
        state,
        ai_name,
    )

    opponent = get_player(
        state,
        opponent_name,
    )

    if (
        ai is None
        or opponent is None
    ):
        return None

    features = []

    # Round
    features.append(
        safe_float(
            state.get(
                "round",
                0,
            )
        )
    )

    # Current player
    current_player = state.get(
        "current_player"
    )

    features.extend([
        1.0
        if current_player == ai_name
        else 0.0,

        1.0
        if current_player == opponent_name
        else 0.0,
    ])

    # VP
    ai_vp = safe_float(
        ai.get(
            "vp",
            0,
        )
    )

    opponent_vp = safe_float(
        opponent.get(
            "vp",
            0,
        )
    )

    features.extend([
        ai_vp,
        opponent_vp,
        ai_vp - opponent_vp,
    ])

    # Essences
    ai_essence = (
        ai.get(
            "essence",
            {},
        )
        or {}
    )

    opponent_essence = (
        opponent.get(
            "essence",
            {},
        )
        or {}
    )

    for essence in ESSENCES:
        features.append(
            safe_float(
                ai_essence.get(
                    essence,
                    0,
                )
            )
        )

    for essence in ESSENCES:
        features.append(
            safe_float(
                opponent_essence.get(
                    essence,
                    0,
                )
            )
        )

    features.append(
        sum(
            safe_float(
                ai_essence.get(
                    essence,
                    0,
                )
            )
            for essence in ESSENCES
        )
    )

    features.append(
        sum(
            safe_float(
                opponent_essence.get(
                    essence,
                    0,
                )
            )
            for essence in ESSENCES
        )
    )

    # Hand / deck / discard
    features.extend([
        safe_float(
            ai.get(
                "hand_count",
                len(
                    ai.get(
                        "hand",
                        [],
                    )
                ),
            )
        ),

        safe_float(
            opponent.get(
                "hand_count",
                len(
                    opponent.get(
                        "hand",
                        [],
                    )
                ),
            )
        ),

        safe_float(
            ai.get(
                "deck_count",
                0,
            )
        ),

        safe_float(
            opponent.get(
                "deck_count",
                0,
            )
        ),

        safe_float(
            ai.get(
                "discard_count",
                len(
                    ai.get(
                        "discard",
                        [],
                    )
                ),
            )
        ),

        safe_float(
            opponent.get(
                "discard_count",
                len(
                    opponent.get(
                        "discard",
                        [],
                    )
                ),
            )
        ),
    ])

    # Board sizes
    for player in [
        ai,
        opponent,
    ]:
        features.extend([
            float(
                len(
                    player.get(
                        "played",
                        [],
                    )
                )
            ),

            float(
                len(
                    player.get(
                        "monuments",
                        [],
                    )
                )
            ),

            float(
                len(
                    player.get(
                        "places",
                        [],
                    )
                )
            ),
        ])

    # Tapped cards
    def count_tapped(player):
        count = 0

        for zone in [
            "played",
            "monuments",
            "places",
        ]:
            for card in player.get(
                zone,
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

    features.extend([
        float(
            count_tapped(ai)
        ),
        float(
            count_tapped(
                opponent
            )
        ),
    ])

    # Stored essence
    def stored_total(player):
        total = 0

        for zone in [
            "played",
            "monuments",
            "places",
        ]:
            for card in player.get(
                zone,
                [],
            ):
                if not isinstance(
                    card,
                    dict,
                ):
                    continue

                stored = (
                    card.get(
                        "stored_essence",
                        {},
                    )
                    or {}
                )

                total += sum(
                    int(value)
                    for value
                    in stored.values()
                )

        return total

    features.extend([
        float(
            stored_total(ai)
        ),
        float(
            stored_total(
                opponent
            )
        ),
    ])

    # Pass / first player token
    features.extend([
        1.0
        if ai.get(
            "passed",
            False,
        )
        else 0.0,

        1.0
        if opponent.get(
            "passed",
            False,
        )
        else 0.0,

        1.0
        if ai.get(
            "has_first_player_token",
            False,
        )
        else 0.0,

        1.0
        if opponent.get(
            "has_first_player_token",
            False,
        )
        else 0.0,
    ])

    # Markets
    features.extend([
        float(
            len(
                state.get(
                    "market_monuments",
                    [],
                )
            )
        ),

        float(
            len(
                state.get(
                    "market_places",
                    [],
                )
            )
        ),
    ])

    if (
        len(features)
        != BASE_STATE_FEATURE_COUNT
    ):
        raise ValueError(
            "Expected "
            f"{BASE_STATE_FEATURE_COUNT} "
            "base state features, got "
            f"{len(features)}"
        )

    return features


# ============================================================
# CARD BOARD STATE
# ============================================================

def add_card_to_vector(
    vector,
    card_vocab,
    card,
):
    name = snapshot_card_name(
        card
    )

    index = card_vocab.get(
        name
    )

    if index is not None:
        vector[index] += 1.0


def encode_card_board_state(
    state,
    ai_name,
    opponent_name,
    card_vocab,
):
    ai = get_player(
        state,
        ai_name,
    )

    opponent = get_player(
        state,
        opponent_name,
    )

    if (
        ai is None
        or opponent is None
    ):
        return None

    size = len(card_vocab)

    ai_cards = [
        0.0
    ] * size

    opponent_cards = [
        0.0
    ] * size

    market_cards = [
        0.0
    ] * size

    # AI mage/item
    for single in [
        "mage",
        "item",
    ]:
        add_card_to_vector(
            ai_cards,
            card_vocab,
            ai.get(single),
        )

    # AI knows own hand
    for zone in [
        "hand",
        "played",
        "monuments",
        "places",
    ]:
        for card in ai.get(
            zone,
            [],
        ):
            add_card_to_vector(
                ai_cards,
                card_vocab,
                card,
            )

    # Opponent public cards
    for single in [
        "mage",
        "item",
    ]:
        add_card_to_vector(
            opponent_cards,
            card_vocab,
            opponent.get(single),
        )

    for zone in [
        "played",
        "monuments",
        "places",
    ]:
        for card in opponent.get(
            zone,
            [],
        ):
            add_card_to_vector(
                opponent_cards,
                card_vocab,
                card,
            )

    # Public market
    for zone in [
        "market_monuments",
        "market_places",
        "items_pool",
    ]:
        for card in state.get(
            zone,
            [],
        ):
            add_card_to_vector(
                market_cards,
                card_vocab,
                card,
            )

    return (
        ai_cards
        + opponent_cards
        + market_cards
    )


def encode_state(
    state,
    ai_name,
    opponent_name,
    card_vocab,
):
    base = encode_base_state(
        state,
        ai_name,
        opponent_name,
    )

    if base is None:
        return None

    cards = encode_card_board_state(
        state,
        ai_name,
        opponent_name,
        card_vocab,
    )

    if cards is None:
        return None

    result = (
        base
        + cards
    )

    return result


# ============================================================
# MOVE ENCODER
# ============================================================

def encode_move(move):
    if move is None:
        move = {}

    features = []

    move_type = (
        move.get(
            "move_type"
        )
        or move.get(
            "type"
        )
    )

    for candidate in MOVE_TYPES:
        features.append(
            1.0
            if move_type == candidate
            else 0.0
        )

    reward_type = move.get(
        "reward_type"
    )

    features.extend([
        1.0
        if reward_type == "gold"
        else 0.0,

        1.0
        if reward_type == "essence"
        else 0.0,
    ])

    choices = (
        move.get(
            "reward_choices"
        )
        or move.get(
            "choices"
        )
        or []
    )

    features.append(
        float(
            len(choices)
        )
    )

    features.append(
        safe_float(
            move.get(
                "x_value"
            ),
            0.0,
        )
    )

    features.append(
        1.0
        if move.get(
            "target_card"
        )
        else 0.0
    )

    features.append(
        extract_power_index(
            move
        )
    )

    if (
        len(features)
        != MOVE_FEATURE_COUNT
    ):
        raise ValueError(
            "Expected "
            f"{MOVE_FEATURE_COUNT} "
            "move features, got "
            f"{len(features)}"
        )

    return features


# ============================================================
# PURE-PYTHON NEURAL OPERATIONS
# ============================================================

def relu(vector):
    return [
        value
        if value > 0.0
        else 0.0
        for value in vector
    ]


def dense(
    vector,
    weights,
    bias,
):
    output = []

    for row, row_bias in zip(
        weights,
        bias,
    ):
        total = float(
            row_bias
        )

        for value, weight in zip(
            vector,
            row,
        ):
            total += (
                float(value)
                * float(weight)
            )

        output.append(
            total
        )

    return output


def sigmoid(value):
    value = float(value)

    if value >= 0:
        z = math.exp(
            -value
        )

        return (
            1.0
            / (
                1.0
                + z
            )
        )

    z = math.exp(value)

    return (
        z
        / (
            1.0
            + z
        )
    )


# ============================================================
# MODEL LOADER
# ============================================================

def load_trained_model():
    global _MODEL

    if _MODEL is not None:
        return _MODEL

    if not MODEL_FILE.exists():
        print(
            "WEB NEURAL MODEL NOT FOUND:",
            MODEL_FILE,
        )
        return None

    try:
        with open(
            MODEL_FILE,
            "r",
            encoding="utf-8-sig",
        ) as file:
            _MODEL = json.load(
                file
            )

        print(
            "WEB NEURAL MODEL LOADED:",
            MODEL_FILE,
        )

        print(
            "WEB NEURAL HUMAN GAMES:",
            _MODEL.get(
                "human_games"
            ),
        )

        print(
            "WEB NEURAL STATE SIZE:",
            _MODEL.get(
                "state_size"
            ),
        )

        return _MODEL

    except Exception as error:
        print(
            "WEB NEURAL MODEL LOAD FAILED:",
            error,
        )

        return None


# ============================================================
# REAL MODEL PREDICTION
# ============================================================

def predict_human_style_score(
    state,
    candidate_move,
    previous_human_move=None,
    previous_ai_move=None,
    model_bundle=None,
):
    if model_bundle is None:
        model_bundle = (
            load_trained_model()
        )

    if model_bundle is None:
        return 0.0

    card_vocab = model_bundle[
        "card_vocab"
    ]

    state_vector = encode_state(
        state,
        AI_NAME,
        HUMAN_NAME,
        card_vocab,
    )

    if state_vector is None:
        return 0.0

    expected_state_size = int(
        model_bundle.get(
            "state_size",
            len(
                state_vector
            ),
        )
    )

    if (
        len(state_vector)
        != expected_state_size
    ):
        raise ValueError(
            "Web neural state size mismatch: "
            f"{len(state_vector)} "
            "vs model "
            f"{expected_state_size}"
        )

    previous_human_vector = (
        encode_move(
            previous_human_move
        )
    )

    previous_ai_vector = (
        encode_move(
            previous_ai_move
        )
    )

    candidate_vector = (
        encode_move(
            candidate_move
        )
    )

    previous_human_card = card_index(
        move_card_name(
            previous_human_move
        ),
        card_vocab,
    )

    previous_ai_card = card_index(
        move_card_name(
            previous_ai_move
        ),
        card_vocab,
    )

    candidate_card = card_index(
        move_card_name(
            candidate_move
        ),
        card_vocab,
    )

    weights = model_bundle[
        "weights"
    ]

    embeddings = weights[
        "card_embedding"
    ]

    combined = (
        state_vector
        + previous_human_vector
        + previous_ai_vector
        + candidate_vector
        + embeddings[
            previous_human_card
        ]
        + embeddings[
            previous_ai_card
        ]
        + embeddings[
            candidate_card
        ]
    )

    layer1 = relu(
        dense(
            combined,
            weights[
                "layer1_weight"
            ],
            weights[
                "layer1_bias"
            ],
        )
    )

    layer2 = relu(
        dense(
            layer1,
            weights[
                "layer2_weight"
            ],
            weights[
                "layer2_bias"
            ],
        )
    )

    layer3 = relu(
        dense(
            layer2,
            weights[
                "layer3_weight"
            ],
            weights[
                "layer3_bias"
            ],
        )
    )

    output = dense(
        layer3,
        weights[
            "output_weight"
        ],
        weights[
            "output_bias"
        ],
    )

    probability = sigmoid(
        output[0]
    )

    print(
        "WEB NEURAL SCORE:",
        move_card_name(
            candidate_move
        ),
        f"{probability:.3f}",
    )

    return probability
