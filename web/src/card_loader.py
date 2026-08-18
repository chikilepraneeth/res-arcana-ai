import json
from pathlib import Path

from models import (
    CardDefinition,
    CardInstance,
)


CURRENT_FILE = Path(__file__).resolve()

# src/card_loader.py
# Project root is one level above src/
PROJECT_ROOT = CURRENT_FILE.parents[1]

DEFAULT_CARDS_FOLDER = (
    PROJECT_ROOT
    / "data"
    / "cards"
)


def load_json_file(path):
    with open(
        path,
        "r",
        encoding="utf-8",
    ) as f:
        return json.load(f)


def extract_cards_from_json(
    raw_data,
):
    if (
        isinstance(raw_data, dict)
        and "cards" in raw_data
    ):
        return raw_data[
            "cards"
        ]

    if isinstance(
        raw_data,
        list,
    ):
        return raw_data

    return []


def build_card_instances(
    card_list,
):
    cards = []

    for raw in card_list:
        card_def = CardDefinition(
            card_id=raw.get(
                "id"
            ),
            name=raw.get(
                "name_en",
                raw.get("id"),
            ),
            card_type=raw.get(
                "type",
                "unknown",
            ),
            raw_data=raw,
        )

        cards.append(
            CardInstance(
                definition=card_def
            )
        )

    return cards


def load_all_cards(
    cards_folder=None,
):
    all_cards = []

    if cards_folder is None:
        cards_folder = (
            DEFAULT_CARDS_FOLDER
        )
    else:
        cards_folder = Path(
            cards_folder
        )

    print(
        "Loading cards from:",
        cards_folder,
    )

    json_files = [
        "res_arcana_cards.json",
        "mages_cards.json",
        "monuments_cards.json",
        "places_of_power.json",
        "ra_items.json",
    ]

    for file_name in json_files:
        full_path = (
            cards_folder
            / file_name
        )

        if not full_path.exists():
            print(
                "Missing file:",
                full_path,
            )
            continue

        try:
            raw_data = load_json_file(
                full_path
            )

            card_list = (
                extract_cards_from_json(
                    raw_data
                )
            )

            built_cards = (
                build_card_instances(
                    card_list
                )
            )

            all_cards.extend(
                built_cards
            )

            print(
                f"Loaded {len(built_cards)} cards from "
                f"{file_name}"
            )

        except Exception as error:
            print(
                "Failed loading:",
                full_path,
            )

            print(
                "Reason:",
                error,
            )

    print(
        "Total cards loaded:",
        len(all_cards),
    )

    return all_cards


def build_cards_by_id(
    card_instances,
):
    result = {}

    for card in card_instances:
        result[
            card.definition.card_id
        ] = card

    return result