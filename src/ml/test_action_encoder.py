from src.ml.action_encoder import (
    encode_move,
    action_feature_count,
)


def main():

    test_move = {
        "move_type": "use_power",
        "card_name": "Dragon's Lair",
        "reward_type": None,
        "reward_choices": [],
        "x_value": 2,
        "target_card": None,
    }

    vector = encode_move(
        test_move
    )

    print(
        "Action feature count:",
        len(vector),
    )

    print(
        "Expected:",
        action_feature_count(),
    )

    print(
        "Vector:",
        vector,
    )


if __name__ == "__main__":
    main()