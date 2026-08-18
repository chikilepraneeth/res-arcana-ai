import json
from pathlib import Path
import torch

ROOT = Path(__file__).resolve().parents[2]

SOURCE = ROOT / "models" / "neural_counter_model_v2.pt"
OUTPUT = ROOT / "models" / "neural_counter_web.json"


def to_list(tensor):
    return tensor.detach().cpu().tolist()


def main():
    print("=" * 70)
    print("EXPORTING RES ARCANA NEURAL MODEL")
    print("=" * 70)

    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)

    checkpoint = torch.load(
        SOURCE,
        map_location="cpu"
    )

    state = checkpoint["model_state_dict"]

    payload = {
        "version": checkpoint.get("version", 2),
        "card_vocab": checkpoint["card_vocab"],
        "state_size": checkpoint["state_size"],
        "move_size": checkpoint["move_size"],
        "embedding_size": checkpoint["embedding_size"],

        "human_games": checkpoint.get("human_games"),
        "test_accuracy": checkpoint.get("test_accuracy"),
        "human_move_ranking_accuracy":
            checkpoint.get("human_move_ranking_accuracy"),

        "weights": {
            "card_embedding":
                to_list(state["card_embedding.weight"]),

            "layer1_weight":
                to_list(state["network.0.weight"]),
            "layer1_bias":
                to_list(state["network.0.bias"]),

            "layer2_weight":
                to_list(state["network.3.weight"]),
            "layer2_bias":
                to_list(state["network.3.bias"]),

            "layer3_weight":
                to_list(state["network.6.weight"]),
            "layer3_bias":
                to_list(state["network.6.bias"]),

            "output_weight":
                to_list(state["network.8.weight"]),
            "output_bias":
                to_list(state["network.8.bias"]),
        }
    }

    with open(
        OUTPUT,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            payload,
            f,
            separators=(",", ":")
        )

    print("SOURCE:", SOURCE)
    print("OUTPUT:", OUTPUT)
    print(
        "SIZE MB:",
        round(
            OUTPUT.stat().st_size / 1024 / 1024,
            3
        )
    )
    print(
        "CARD VOCAB:",
        len(payload["card_vocab"])
    )
    print(
        "STATE SIZE:",
        payload["state_size"]
    )
    print(
        "HUMAN GAMES:",
        payload["human_games"]
    )

    print("=" * 70)
    print("EXPORT SUCCESSFUL")
    print("=" * 70)


if __name__ == "__main__":
    main()
