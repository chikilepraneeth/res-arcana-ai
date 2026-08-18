

# src/ml/neural_counter_model.py

import json
import random
import re
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset


ROOT = Path(__file__).resolve().parents[2]
MEMORY_FILE = ROOT / "memory" / "game_memory.json"
MODEL_DIR = ROOT / "models"
MODEL_FILE = MODEL_DIR / "neural_counter_model_v2.pt"

HUMAN_NAME = "Chikile"
AI_NAME = "AI Companion"

ESSENCES = ["elan", "life", "calm", "death", "gold"]

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

RANDOM_SEED = 42
NEGATIVES_PER_POSITIVE = 3
BASE_STATE_FEATURE_COUNT = 40
MOVE_FEATURE_COUNT = 12
CARD_EMBEDDING_SIZE = 16


# ============================================================
# GENERAL HELPERS
# ============================================================

def load_all_games():
    if not MEMORY_FILE.exists():
        return []

    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        return data if isinstance(data, list) else []

    except Exception as error:
        print("Could not load game memory:", error)
        return []


def is_human_game(game):
    moves = game.get("moves", [])

    if not moves:
        return False

    players = {
        move.get("player")
        for move in moves
    }

    return (
        HUMAN_NAME in players
        and AI_NAME in players
    )


def get_human_games(games=None):
    if games is None:
        games = load_all_games()

    return [
        game
        for game in games
        if is_human_game(game)
    ]


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


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def extract_power_index(move):
    if not move:
        return 0.0

    if move.get("power_index") is not None:
        return safe_float(move.get("power_index"))

    description = str(
        move.get("description", "")
    )

    match = re.search(
        r"\bpower\s+(\d+)\b",
        description,
        flags=re.IGNORECASE,
    )

    if match:
        return safe_float(match.group(1))

    return 0.0


def get_player(state, player_name):
    for player in state.get("players", []):
        if player.get("name") == player_name:
            return player

    return None


# ============================================================
# CARD VOCABULARY
# ============================================================

def collect_cards_from_player(player, output):
    for single in ["mage", "item"]:
        name = snapshot_card_name(
            player.get(single)
        )

        if name != NONE_CARD:
            output.add(name)

    for zone in [
        "hand",
        "played",
        "monuments",
        "places",
        "discard",
        "deck_top",
    ]:
        for card in player.get(zone, []):
            name = snapshot_card_name(card)

            if name != NONE_CARD:
                output.add(name)


def collect_cards_from_state(state, output):
    if not state:
        return

    for player in state.get("players", []):
        collect_cards_from_player(
            player,
            output,
        )

    for zone in [
        "market_monuments",
        "market_places",
        "items_pool",
    ]:
        for card in state.get(zone, []):
            name = snapshot_card_name(card)

            if name != NONE_CARD:
                output.add(name)


def build_card_vocab(human_games):
    names = set()

    for game in human_games:
        collect_cards_from_state(
            game.get("final_state"),
            names,
        )

        for move in game.get("moves", []):
            name = move_card_name(move)

            if name != NONE_CARD:
                names.add(name)

            target = normalize_card_name(
                move.get("target_card")
            )

            if target != NONE_CARD:
                names.add(target)

            collect_cards_from_state(
                move.get("state_before_move"),
                names,
            )

            collect_cards_from_state(
                move.get("state_after_move"),
                names,
            )

    ordered = [
        NONE_CARD,
        UNK_CARD,
        *sorted(names),
    ]

    return {
        name: index
        for index, name in enumerate(ordered)
    }


def card_index(card_name_value, card_vocab):
    name = normalize_card_name(
        card_name_value
    )

    return card_vocab.get(
        name,
        card_vocab.get(UNK_CARD, 1),
    )


# ============================================================
# BASE STATE ENCODER
# ============================================================

def encode_base_state(
    state,
    ai_name,
    opponent_name,
):
    ai = get_player(state, ai_name)
    opponent = get_player(
        state,
        opponent_name,
    )

    if ai is None or opponent is None:
        return None

    features = []

    # round / current player
    features.append(
        safe_float(state.get("round", 0))
    )

    current_player = state.get(
        "current_player"
    )

    features.extend([
        1.0 if current_player == ai_name else 0.0,
        1.0 if current_player == opponent_name else 0.0,
    ])

    # VP
    ai_vp = safe_float(ai.get("vp", 0))
    opp_vp = safe_float(
        opponent.get("vp", 0)
    )

    features.extend([
        ai_vp,
        opp_vp,
        ai_vp - opp_vp,
    ])

    # essence
    ai_essence = ai.get("essence", {}) or {}
    opp_essence = (
        opponent.get("essence", {}) or {}
    )

    for essence in ESSENCES:
        features.append(
            safe_float(
                ai_essence.get(essence, 0)
            )
        )

    for essence in ESSENCES:
        features.append(
            safe_float(
                opp_essence.get(essence, 0)
            )
        )

    features.append(
        sum(
            safe_float(
                ai_essence.get(essence, 0)
            )
            for essence in ESSENCES
        )
    )

    features.append(
        sum(
            safe_float(
                opp_essence.get(essence, 0)
            )
            for essence in ESSENCES
        )
    )

    # hand/deck/discard counts
    features.extend([
        safe_float(
            ai.get(
                "hand_count",
                len(ai.get("hand", [])),
            )
        ),
        safe_float(
            opponent.get(
                "hand_count",
                len(opponent.get("hand", [])),
            )
        ),
        safe_float(
            ai.get("deck_count", 0)
        ),
        safe_float(
            opponent.get("deck_count", 0)
        ),
        safe_float(
            ai.get(
                "discard_count",
                len(ai.get("discard", [])),
            )
        ),
        safe_float(
            opponent.get(
                "discard_count",
                len(opponent.get("discard", [])),
            )
        ),
    ])

    # board sizes
    for player in [ai, opponent]:
        features.extend([
            float(len(player.get("played", []))),
            float(len(player.get("monuments", []))),
            float(len(player.get("places", []))),
        ])

    def count_tapped(player):
        count = 0

        for zone in [
            "played",
            "monuments",
            "places",
        ]:
            for card in player.get(zone, []):
                if (
                    isinstance(card, dict)
                    and card.get("tapped", False)
                ):
                    count += 1

        return count

    features.extend([
        float(count_tapped(ai)),
        float(count_tapped(opponent)),
    ])

    def stored_total(player):
        total = 0

        for zone in [
            "played",
            "monuments",
            "places",
        ]:
            for card in player.get(zone, []):
                if not isinstance(card, dict):
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
                    for value in stored.values()
                )

        return total

    features.extend([
        float(stored_total(ai)),
        float(stored_total(opponent)),
    ])

    # pass / first player
    features.extend([
        1.0 if ai.get("passed", False) else 0.0,
        1.0 if opponent.get("passed", False) else 0.0,
        1.0 if ai.get("has_first_player_token", False) else 0.0,
        1.0 if opponent.get("has_first_player_token", False) else 0.0,
    ])

    # markets
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

    if len(features) != BASE_STATE_FEATURE_COUNT:
        raise ValueError(
            "Expected "
            f"{BASE_STATE_FEATURE_COUNT} base features, "
            f"got {len(features)}."
        )

    return features


# ============================================================
# CARD-AWARE BOARD STATE
# ============================================================

def add_card_to_vector(
    vector,
    card_vocab,
    card,
):
    name = snapshot_card_name(card)
    index = card_vocab.get(name)

    if index is not None:
        vector[index] += 1.0


def encode_card_board_state(
    state,
    ai_name,
    opponent_name,
    card_vocab,
):
    ai = get_player(state, ai_name)
    opponent = get_player(
        state,
        opponent_name,
    )

    if ai is None or opponent is None:
        return None

    size = len(card_vocab)

    ai_cards = [0.0] * size
    opponent_cards = [0.0] * size
    market_cards = [0.0] * size

    # AI knows its own hand and board.
    for single in ["mage", "item"]:
        add_card_to_vector(
            ai_cards,
            card_vocab,
            ai.get(single),
        )

    for zone in [
        "hand",
        "played",
        "monuments",
        "places",
    ]:
        for card in ai.get(zone, []):
            add_card_to_vector(
                ai_cards,
                card_vocab,
                card,
            )

    # Opponent hand stays hidden.
    for single in ["mage", "item"]:
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
        for card in opponent.get(zone, []):
            add_card_to_vector(
                opponent_cards,
                card_vocab,
                card,
            )

    # Public market.
    for zone in [
        "market_monuments",
        "market_places",
        "items_pool",
    ]:
        for card in state.get(zone, []):
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

    return base + cards


# ============================================================
# MOVE ENCODER
# ============================================================

def encode_move(move):
    if move is None:
        move = {}

    features = []

    move_type = (
        move.get("move_type")
        or move.get("type")
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
        1.0 if reward_type == "gold" else 0.0,
        1.0 if reward_type == "essence" else 0.0,
    ])

    choices = (
        move.get("reward_choices")
        or move.get("choices")
        or []
    )

    features.append(
        float(len(choices))
    )

    features.append(
        safe_float(
            move.get("x_value"),
            0.0,
        )
    )

    features.append(
        1.0
        if move.get("target_card")
        else 0.0
    )

    features.append(
        extract_power_index(move)
    )

    if len(features) != MOVE_FEATURE_COUNT:
        raise ValueError(
            f"Expected {MOVE_FEATURE_COUNT} move features, "
            f"got {len(features)}."
        )

    return features


# ============================================================
# HUMAN SEQUENCE HELPERS
# ============================================================

def previous_move_by_player(
    moves,
    start_index,
    player_name,
):
    for index in range(
        start_index - 1,
        -1,
        -1,
    ):
        move = moves[index]

        if move.get("player") == player_name:
            return move

    return None


def same_action_signature(
    left,
    right,
):
    left_type = (
        left.get("move_type")
        or left.get("type")
    )

    right_type = (
        right.get("move_type")
        or right.get("type")
    )

    return (
        left_type == right_type
        and move_card_name(left)
        == move_card_name(right)
        and extract_power_index(left)
        == extract_power_index(right)
    )


def build_action_pool(games):
    seen = set()
    pool = []

    for game in games:
        for move in game.get("moves", []):
            if move.get("player") != HUMAN_NAME:
                continue

            key = (
                move.get("move_type")
                or move.get("type"),
                move_card_name(move),
                extract_power_index(move),
                move.get("reward_type"),
            )

            if key in seen:
                continue

            seen.add(key)

            pool.append({
                "move_type":
                    move.get("move_type")
                    or move.get("type"),

                "card_name":
                    move.get("card_name"),

                "power_index":
                    extract_power_index(move),

                "reward_type":
                    move.get("reward_type"),

                "reward_choices":
                    move.get("reward_choices")
                    or [],

                "x_value":
                    move.get("x_value"),

                "target_card":
                    move.get("target_card"),
            })

    return pool


# ============================================================
# TRAINING EXAMPLES
# ============================================================

def generate_examples(
    selected_games,
    action_pool,
    card_vocab,
    negatives_per_positive,
    seed,
):
    rng = random.Random(seed)

    output = {
        "states": [],
        "previous_human_moves": [],
        "previous_ai_moves": [],
        "candidate_moves": [],
        "previous_human_cards": [],
        "previous_ai_cards": [],
        "candidate_cards": [],
        "labels": [],
        "group_ids": [],
        "positive_count": 0,
        "negative_count": 0,
    }

    group_id = 0

    for game in selected_games:
        moves = game.get("moves", [])

        for index, human_move in enumerate(moves):
            if human_move.get("player") != HUMAN_NAME:
                continue

            # This is the exact scenario in which
            # Chikile chose the current move.
            state = human_move.get(
                "state_before_move"
            )

            if not state:
                continue

            state_vector = encode_state(
                state,
                AI_NAME,
                HUMAN_NAME,
                card_vocab,
            )

            if state_vector is None:
                continue

            # Learn the sequence:
            # previous human move -> AI response -> next human move.
            previous_human = (
                previous_move_by_player(
                    moves,
                    index,
                    HUMAN_NAME,
                )
            )

            previous_ai = (
                previous_move_by_player(
                    moves,
                    index,
                    AI_NAME,
                )
            )

            previous_human_vector = (
                encode_move(
                    previous_human
                )
            )

            previous_ai_vector = (
                encode_move(
                    previous_ai
                )
            )

            previous_human_card = card_index(
                move_card_name(
                    previous_human
                ),
                card_vocab,
            )

            previous_ai_card = card_index(
                move_card_name(
                    previous_ai
                ),
                card_vocab,
            )

            def add_example(
                candidate,
                label,
            ):
                output[
                    "states"
                ].append(
                    state_vector
                )

                output[
                    "previous_human_moves"
                ].append(
                    previous_human_vector
                )

                output[
                    "previous_ai_moves"
                ].append(
                    previous_ai_vector
                )

                output[
                    "candidate_moves"
                ].append(
                    encode_move(candidate)
                )

                output[
                    "previous_human_cards"
                ].append(
                    previous_human_card
                )

                output[
                    "previous_ai_cards"
                ].append(
                    previous_ai_card
                )

                output[
                    "candidate_cards"
                ].append(
                    card_index(
                        move_card_name(candidate),
                        card_vocab,
                    )
                )

                output[
                    "labels"
                ].append(
                    float(label)
                )

                output[
                    "group_ids"
                ].append(
                    group_id
                )

            # What Chikile actually did.
            add_example(
                human_move,
                1.0,
            )

            output[
                "positive_count"
            ] += 1

            # Alternatives from historical human action vocabulary.
            alternatives = [
                action
                for action in action_pool
                if not same_action_signature(
                    action,
                    human_move,
                )
            ]

            if alternatives:
                count = min(
                    negatives_per_positive,
                    len(alternatives),
                )

                for negative in rng.sample(
                    alternatives,
                    count,
                ):
                    add_example(
                        negative,
                        0.0,
                    )

                    output[
                        "negative_count"
                    ] += 1

            group_id += 1

    return output


def examples_to_tensors(examples):
    return (
        torch.tensor(
            examples["states"],
            dtype=torch.float32,
        ),
        torch.tensor(
            examples["previous_human_moves"],
            dtype=torch.float32,
        ),
        torch.tensor(
            examples["previous_ai_moves"],
            dtype=torch.float32,
        ),
        torch.tensor(
            examples["candidate_moves"],
            dtype=torch.float32,
        ),
        torch.tensor(
            examples["previous_human_cards"],
            dtype=torch.long,
        ),
        torch.tensor(
            examples["previous_ai_cards"],
            dtype=torch.long,
        ),
        torch.tensor(
            examples["candidate_cards"],
            dtype=torch.long,
        ),
        torch.tensor(
            examples["labels"],
            dtype=torch.float32,
        ).unsqueeze(1),
    )


# ============================================================
# NEURAL NETWORK
# ============================================================

class CardLearningNetwork(nn.Module):
    def __init__(
        self,
        state_size,
        card_vocab_size,
        move_size=MOVE_FEATURE_COUNT,
        embedding_size=CARD_EMBEDDING_SIZE,
    ):
        super().__init__()

        self.card_embedding = nn.Embedding(
            card_vocab_size,
            embedding_size,
        )

        input_size = (
            state_size
            + move_size * 3
            + embedding_size * 3
        )

        self.network = nn.Sequential(
            nn.Linear(input_size, 192),
            nn.ReLU(),
            nn.Dropout(0.15),

            nn.Linear(192, 96),
            nn.ReLU(),
            nn.Dropout(0.10),

            nn.Linear(96, 48),
            nn.ReLU(),

            nn.Linear(48, 1),
        )

    def forward(
        self,
        state,
        previous_human_move,
        previous_ai_move,
        candidate_move,
        previous_human_card,
        previous_ai_card,
        candidate_card,
    ):
        previous_human_embedding = (
            self.card_embedding(
                previous_human_card
            )
        )

        previous_ai_embedding = (
            self.card_embedding(
                previous_ai_card
            )
        )

        candidate_embedding = (
            self.card_embedding(
                candidate_card
            )
        )

        combined = torch.cat(
            [
                state,
                previous_human_move,
                previous_ai_move,
                candidate_move,
                previous_human_embedding,
                previous_ai_embedding,
                candidate_embedding,
            ],
            dim=1,
        )

        return self.network(combined)


# ============================================================
# MODEL EVALUATION
# ============================================================

def forward_tensors(
    model,
    tensors,
):
    return model(
        tensors[0],
        tensors[1],
        tensors[2],
        tensors[3],
        tensors[4],
        tensors[5],
        tensors[6],
    )


def binary_metrics(
    logits,
    labels,
):
    probabilities = torch.sigmoid(
        logits
    )

    predictions = (
        probabilities >= 0.5
    ).float()

    accuracy = (
        predictions
        .eq(labels)
        .float()
        .mean()
        .item()
    )

    positive_mask = (
        labels == 1
    )

    negative_mask = (
        labels == 0
    )

    positive_accuracy = 0.0
    negative_accuracy = 0.0
    positive_score = 0.0
    negative_score = 0.0

    if positive_mask.any():
        positive_accuracy = (
            predictions[
                positive_mask
            ]
            .eq(
                labels[
                    positive_mask
                ]
            )
            .float()
            .mean()
            .item()
        )

        positive_score = (
            probabilities[
                positive_mask
            ]
            .mean()
            .item()
        )

    if negative_mask.any():
        negative_accuracy = (
            predictions[
                negative_mask
            ]
            .eq(
                labels[
                    negative_mask
                ]
            )
            .float()
            .mean()
            .item()
        )

        negative_score = (
            probabilities[
                negative_mask
            ]
            .mean()
            .item()
        )

    return {
        "accuracy": accuracy,
        "positive_accuracy":
            positive_accuracy,
        "negative_accuracy":
            negative_accuracy,
        "positive_score":
            positive_score,
        "negative_score":
            negative_score,
    }


def ranking_accuracy(
    probabilities,
    labels,
    group_ids,
):
    probabilities = (
        probabilities
        .detach()
        .cpu()
        .view(-1)
        .tolist()
    )

    labels = (
        labels
        .detach()
        .cpu()
        .view(-1)
        .tolist()
    )

    grouped = {}

    for probability, label, group_id in zip(
        probabilities,
        labels,
        group_ids,
    ):
        grouped.setdefault(
            group_id,
            [],
        ).append(
            (probability, label)
        )

    correct = 0
    total = 0

    for samples in grouped.values():
        positives = [
            probability
            for probability, label in samples
            if label >= 0.5
        ]

        negatives = [
            probability
            for probability, label in samples
            if label < 0.5
        ]

        if not positives or not negatives:
            continue

        total += 1

        if max(positives) > max(negatives):
            correct += 1

    if total == 0:
        return 0.0

    return correct / total


# ============================================================
# TRAIN
# ============================================================

def train_model(
    epochs=120,
    quiet=False,
):
    random.seed(RANDOM_SEED)
    torch.manual_seed(RANDOM_SEED)

    human_games = get_human_games()

    if len(human_games) < 2:
        print(
            "Not enough detailed human games "
            "for neural training."
        )
        return None

    card_vocab = build_card_vocab(
        human_games
    )

    shuffled = list(human_games)

    random.Random(
        RANDOM_SEED
    ).shuffle(shuffled)

    test_game_count = max(
        1,
        round(
            len(shuffled) * 0.25
        ),
    )

    test_games = shuffled[
        :test_game_count
    ]

    train_games = shuffled[
        test_game_count:
    ]

    action_pool = build_action_pool(
        train_games
    )

    train_examples = generate_examples(
        train_games,
        action_pool,
        card_vocab,
        NEGATIVES_PER_POSITIVE,
        RANDOM_SEED,
    )

    test_examples = generate_examples(
        test_games,
        action_pool,
        card_vocab,
        NEGATIVES_PER_POSITIVE,
        RANDOM_SEED + 1,
    )

    if not train_examples["labels"]:
        print(
            "No training examples generated."
        )
        return None

    if not test_examples["labels"]:
        print(
            "No test examples generated."
        )
        return None

    train_tensors = examples_to_tensors(
        train_examples
    )

    test_tensors = examples_to_tensors(
        test_examples
    )

    state_size = train_tensors[
        0
    ].shape[1]

    model = CardLearningNetwork(
        state_size=state_size,
        card_vocab_size=len(card_vocab),
    )

    dataset = TensorDataset(
        *train_tensors
    )

    loader = DataLoader(
        dataset,
        batch_size=min(
            64,
            len(dataset),
        ),
        shuffle=True,
    )

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=0.001,
        weight_decay=0.0005,
    )

    loss_function = (
        nn.BCEWithLogitsLoss()
    )

    best_test_loss = float("inf")
    best_state = None

    patience = 20
    without_improvement = 0

    if not quiet:
        print("=" * 76)
        print(
            "CARD-AWARE HUMAN LEARNING MODEL"
        )
        print("=" * 76)
        print(
            "Human games found:",
            len(human_games),
        )
        print(
            "Training games:",
            len(train_games),
        )
        print(
            "Test games:",
            len(test_games),
        )
        print(
            "Exact cards known:",
            len(card_vocab) - 2,
        )
        print(
            "State features:",
            state_size,
        )
        print(
            "Training real human moves:",
            train_examples[
                "positive_count"
            ],
        )
        print(
            "Training alternatives:",
            train_examples[
                "negative_count"
            ],
        )
        print(
            "Test real human moves:",
            test_examples[
                "positive_count"
            ],
        )
        print(
            "Test alternatives:",
            test_examples[
                "negative_count"
            ],
        )
        print("=" * 76)

    for epoch in range(
        1,
        epochs + 1,
    ):
        model.train()
        total_loss = 0.0

        for batch in loader:
            optimizer.zero_grad()

            logits = model(
                batch[0],
                batch[1],
                batch[2],
                batch[3],
                batch[4],
                batch[5],
                batch[6],
            )

            loss = loss_function(
                logits,
                batch[7],
            )

            loss.backward()
            optimizer.step()

            total_loss += loss.item()

        train_loss = (
            total_loss
            / max(1, len(loader))
        )

        model.eval()

        with torch.no_grad():
            test_logits = forward_tensors(
                model,
                test_tensors,
            )

            test_loss = loss_function(
                test_logits,
                test_tensors[7],
            ).item()

        if test_loss < best_test_loss:
            best_test_loss = test_loss

            best_state = {
                key:
                    value
                    .detach()
                    .cpu()
                    .clone()
                for key, value
                in model.state_dict().items()
            }

            without_improvement = 0

        else:
            without_improvement += 1

        if (
            not quiet
            and (
                epoch == 1
                or epoch % 10 == 0
            )
        ):
            print(
                f"Epoch {epoch:3d}/{epochs}"
                f" | Train BCE: {train_loss:.5f}"
                f" | Test BCE: {test_loss:.5f}"
            )

        if without_improvement >= patience:
            if not quiet:
                print(
                    "Early stopping at "
                    f"epoch {epoch}."
                )

            break

    if best_state is not None:
        model.load_state_dict(
            best_state
        )

    model.eval()

    with torch.no_grad():
        train_logits = forward_tensors(
            model,
            train_tensors,
        )

        test_logits = forward_tensors(
            model,
            test_tensors,
        )

    train_metrics = binary_metrics(
        train_logits,
        train_tensors[7],
    )

    test_metrics = binary_metrics(
        test_logits,
        test_tensors[7],
    )

    test_probabilities = torch.sigmoid(
        test_logits
    )

    rank_accuracy = ranking_accuracy(
        test_probabilities,
        test_tensors[7],
        test_examples["group_ids"],
    )

    MODEL_DIR.mkdir(
        exist_ok=True
    )

    checkpoint = {
        "version": 2,
        "model_state_dict":
            model.state_dict(),
        "card_vocab":
            card_vocab,
        "state_size":
            state_size,
        "move_size":
            MOVE_FEATURE_COUNT,
        "embedding_size":
            CARD_EMBEDDING_SIZE,
        "human_games":
            len(human_games),
        "best_test_bce":
            best_test_loss,
        "train_accuracy":
            train_metrics["accuracy"],
        "test_accuracy":
            test_metrics["accuracy"],
        "human_move_ranking_accuracy":
            rank_accuracy,
    }

    torch.save(
        checkpoint,
        MODEL_FILE,
    )

    if not quiet:
        print()
        print("=" * 76)
        print(
            "CARD-LEARNING EVALUATION"
        )
        print("=" * 76)
        print(
            f"Best Test BCE: "
            f"{best_test_loss:.5f}"
        )
        print(
            "Train classification accuracy: "
            f"{train_metrics['accuracy'] * 100:.2f}%"
        )
        print(
            "Test classification accuracy:  "
            f"{test_metrics['accuracy'] * 100:.2f}%"
        )
        print(
            "Test real-human-move accuracy:  "
            f"{test_metrics['positive_accuracy'] * 100:.2f}%"
        )
        print(
            "Test alternative accuracy:      "
            f"{test_metrics['negative_accuracy'] * 100:.2f}%"
        )
        print(
            "Human move ranking accuracy:    "
            f"{rank_accuracy * 100:.2f}%"
        )
        print()
        print(
            "Average score, real human move: "
            f"{test_metrics['positive_score']:.3f}"
        )
        print(
            "Average score, alternatives:    "
            f"{test_metrics['negative_score']:.3f}"
        )
        print()
        print(
            "Model saved:"
        )
        print(MODEL_FILE)
        print("=" * 76)

    return checkpoint


# ============================================================
# LOAD / PREDICT
# ============================================================

def load_model_bundle():
    if not MODEL_FILE.exists():
        return None

    try:
        checkpoint = torch.load(
            MODEL_FILE,
            map_location="cpu",
        )

        if checkpoint.get("version") != 2:
            return None

        card_vocab = checkpoint[
            "card_vocab"
        ]

        model = CardLearningNetwork(
            state_size=checkpoint[
                "state_size"
            ],
            card_vocab_size=len(
                card_vocab
            ),
            move_size=checkpoint[
                "move_size"
            ],
            embedding_size=checkpoint[
                "embedding_size"
            ],
        )

        model.load_state_dict(
            checkpoint[
                "model_state_dict"
            ]
        )

        model.eval()

        return {
            "model": model,
            "card_vocab": card_vocab,
            "checkpoint": checkpoint,
        }

    except Exception as error:
        print(
            "Could not load neural model:",
            error,
        )

        return None


def predict_human_style_score(
    state,
    candidate_move,
    previous_human_move=None,
    previous_ai_move=None,
    model_bundle=None,
):
    """
    Returns 0.0 -> 1.0.

    Higher means:
    "This legal candidate resembles how Chikile learned
    to use cards in this kind of state and sequence."

    Legality is NOT checked here.
    """

    if model_bundle is None:
        model_bundle = (
            load_model_bundle()
        )

    if model_bundle is None:
        return 0.0

    model = model_bundle["model"]
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

    with torch.no_grad():
        logit = model(
            torch.tensor(
                [state_vector],
                dtype=torch.float32,
            ),
            torch.tensor(
                [encode_move(previous_human_move)],
                dtype=torch.float32,
            ),
            torch.tensor(
                [encode_move(previous_ai_move)],
                dtype=torch.float32,
            ),
            torch.tensor(
                [encode_move(candidate_move)],
                dtype=torch.float32,
            ),
            torch.tensor(
                [
                    card_index(
                        move_card_name(
                            previous_human_move
                        ),
                        card_vocab,
                    )
                ],
                dtype=torch.long,
            ),
            torch.tensor(
                [
                    card_index(
                        move_card_name(
                            previous_ai_move
                        ),
                        card_vocab,
                    )
                ],
                dtype=torch.long,
            ),
            torch.tensor(
                [
                    card_index(
                        move_card_name(
                            candidate_move
                        ),
                        card_vocab,
                    )
                ],
                dtype=torch.long,
            ),
        )

        return float(
            torch.sigmoid(
                logit
            ).item()
        )


# ============================================================
# CONTINUAL LEARNING
# ============================================================

def update_after_human_game(
    quiet=True,
):
    """
    Call only AFTER the completed human game is saved.

    For now this safely retrains on ALL detailed human games,
    so the model learns the new game without forgetting the old ones.
    With the current small dataset this is fast and more stable
    than fine-tuning on one game only.
    """

    return train_model(
        epochs=80,
        quiet=quiet,
    )


# ============================================================
# REPORT
# ============================================================

def print_learning_report():
    human_games = get_human_games()

    card_vocab = build_card_vocab(
        human_games
    )

    action_pool = build_action_pool(
        human_games
    )

    human_moves = 0
    dodge_examples = 0
    card_usage = {}

    for game in human_games:
        moves = game.get("moves", [])

        for index, move in enumerate(moves):
            if move.get("player") != HUMAN_NAME:
                continue

            human_moves += 1

            name = move_card_name(move)

            if name != NONE_CARD:
                card_usage[name] = (
                    card_usage.get(name, 0)
                    + 1
                )

            previous_human = (
                previous_move_by_player(
                    moves,
                    index,
                    HUMAN_NAME,
                )
            )

            previous_ai = (
                previous_move_by_player(
                    moves,
                    index,
                    AI_NAME,
                )
            )

            if (
                previous_human is not None
                and previous_ai is not None
            ):
                dodge_examples += 1

    print("=" * 76)
    print(
        "HUMAN CARD LEARNING REPORT"
    )
    print("=" * 76)
    print(
        "Detailed human games:",
        len(human_games),
    )
    print(
        "Human moves:",
        human_moves,
    )
    print(
        "Continuation/dodge examples:",
        dodge_examples,
    )
    print(
        "Known exact cards:",
        max(0, len(card_vocab) - 2),
    )
    print(
        "Unique human actions:",
        len(action_pool),
    )

    print()
    print(
        "Most observed human card uses:"
    )

    ranked = sorted(
        card_usage.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    for name, count in ranked[:15]:
        print(
            f"- {name}: {count}"
        )

    print("=" * 76)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print_learning_report()

    print()

    train_model(
        epochs=120,
        quiet=False,
    )
