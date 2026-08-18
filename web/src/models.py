from dataclasses import dataclass, field
from typing import Dict, List, Optional


ESSENCE_KEYS = ["elan", "life", "calm", "death", "gold"]


def empty_essence_pool():
    return {k: 0 for k in ESSENCE_KEYS}


@dataclass
class CardDefinition:
    card_id: str
    name: str
    card_type: str
    raw_data: dict


@dataclass
class CardInstance:
    definition: CardDefinition
    tapped: bool = False
    stored_essence: Dict[str, int] = field(default_factory=empty_essence_pool)

    def __str__(self):
        return self.definition.name


@dataclass
class Player:
    name: str

    essence_pool: Dict[str, int] = field(default_factory=empty_essence_pool)

    hand: List[CardInstance] = field(default_factory=list)
    deck_hidden: List[CardInstance] = field(default_factory=list)
    discard: List[CardInstance] = field(default_factory=list)

    played: List[CardInstance] = field(default_factory=list)
    monuments: List[CardInstance] = field(default_factory=list)
    places: List[CardInstance] = field(default_factory=list)

    mage: Optional[CardInstance] = None
    item: Optional[CardInstance] = None

    passed: bool = False
    victory_points: int = 0

    has_first_player_token: bool = False


@dataclass
class GameState:
    players: List[Player]

    # Only 2 monuments are visible at a time
    market_monuments: List[CardInstance] = field(default_factory=list)

    # Hidden monument deck used to refill market_monuments
    monument_deck: List[CardInstance] = field(default_factory=list)

    # Only 5 Places of Power are used in the game
    market_places: List[CardInstance] = field(default_factory=list)

    # Available magic items
    items_pool: List[CardInstance] = field(default_factory=list)

    round_no: int = 1
    current_player_index: int = 0

    first_player_token_available: bool = True
    first_player_token_vp: int = 1

    game_over: bool = False
    winner: Optional[str] = None

    game_log: List[str] = field(default_factory=list)

    def current_player(self):
        return self.players[self.current_player_index]

    def next_player(self):
        self.current_player_index = (
            self.current_player_index + 1
        ) % len(self.players)