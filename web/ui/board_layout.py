# ui/board_layout.py

MAIN_BOARD_BG = "assets/boards/Main_borad.webp"
PLAYER_BOARD_BG = "assets/boards/player board.webp"
AI_BOARD_BG = "assets/boards/ai board.webp"


MAIN_BOARD_SLOTS = {
    "place_1": (470, 60),
    "place_2": (730, 60),
    "place_3": (990, 60),
    "place_4": (1245, 60),
    "place_5": (1505, 60),

    "open_monument_1": (254, 55),
    "open_monument_2": (254, 350),
    "monument_deck": (40, 212),

    "item_1": (465, 420),
    "item_2": (627, 420),
    "item_3": (790, 420),
    "item_4": (951, 420),
    "item_5": (1111, 420),
    "item_6": (1278, 420),
    "item_7": (1441, 420),
    "item_8": (1602, 420),
}


MAIN_BOARD_SLOT_SIZES = {
    "place_1": (250, 350),
    "place_2": (250, 350),
    "place_3": (250, 350),
    "place_4": (250, 350),
    "place_5": (250, 350),

    "open_monument_1": (201, 285),
    "open_monument_2": (201, 285),
    "monument_deck": (201, 285),

    "item_1": (153, 214),
    "item_2": (153, 214),
    "item_3": (153, 214),
    "item_4": (153, 214),
    "item_5": (153, 214),
    "item_6": (153, 214),
    "item_7": (153, 214),
    "item_8": (153, 214),
}


def get_main_slot_size(slot_name):
    return MAIN_BOARD_SLOT_SIZES[slot_name]


def get_ordered_slots(slot_dict, prefix):
    matching = []

    for name, pos in slot_dict.items():
        if name.startswith(prefix + "_"):
            number = int(name.split("_")[-1])
            matching.append((number, name, pos))

    matching.sort(key=lambda x: x[0])

    return [(name, pos) for _, name, pos in matching]