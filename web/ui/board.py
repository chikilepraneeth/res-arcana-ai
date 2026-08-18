import pygame  # type: ignore
from pathlib import Path

from ui.board_layout import (
    MAIN_BOARD_SLOTS,
    get_main_slot_size,
    MAIN_BOARD_BG,
)


class Board:
    def __init__(self, card_renderer):
        self.card_renderer = card_renderer

        self.font = pygame.font.SysFont(
            "arial",
            18,
        )

        self.small_font = pygame.font.SysFont(
            "arial",
            14,
        )

        root_dir = Path(__file__).resolve().parents[1]

        bg_path = root_dir / MAIN_BOARD_BG

        # --------------------------------------------------------
        # WEB / PYGBAG SAFE BACKGROUND LOADING
        # --------------------------------------------------------

        # Prefer PNG when available because WebP support can fail
        # in the browser/WebAssembly version of pygame.
        png_path = bg_path.with_suffix(".png")

        if png_path.exists():
            bg_path = png_path

        try:
            self.bg = pygame.image.load(
                str(bg_path)
            ).convert()

            print(
                "Board background loaded:",
                bg_path,
            )

        except Exception as error:
            print(
                "WARNING: Board background failed to load:",
                bg_path,
            )
            print(
                "Reason:",
                error,
            )

            # Do not allow a missing/unsupported background image
            # to crash the whole browser game.
            self.bg = pygame.Surface(
                (1720, 880)
            )

            self.bg.fill(
                (18, 14, 10)
            )

    def draw_small_text(
        self,
        screen,
        text,
        x,
        y,
    ):
        label = self.small_font.render(
            text,
            True,
            (255, 255, 255),
        )

        screen.blit(
            label,
            (x, y),
        )

    def draw_card_in_slot(
        self,
        screen,
        card,
        slot_name,
    ):
        if not card:
            return None

        x, y = MAIN_BOARD_SLOTS[
            slot_name
        ]

        w, h = get_main_slot_size(
            slot_name
        )

        return self.card_renderer.draw_card_with_state(
            screen,
            card,
            x,
            y,
            w,
            h,
        )

    def draw_card_back_in_slot(
        self,
        screen,
        slot_name,
        label_text="Deck",
    ):
        x, y = MAIN_BOARD_SLOTS[
            slot_name
        ]

        w, h = get_main_slot_size(
            slot_name
        )

        rect = self.card_renderer.draw_card_back(
            screen,
            x,
            y,
            w,
            h,
        )

        if rect is not None:
            self.draw_small_text(
                screen,
                label_text,
                x + 10,
                y + h + 5,
            )

        return rect

    def draw_debug_slots(
        self,
        screen,
    ):
        for (
            name,
            (slot_x, slot_y),
        ) in MAIN_BOARD_SLOTS.items():

            slot_w, slot_h = (
                get_main_slot_size(
                    name
                )
            )

            pygame.draw.rect(
                screen,
                (255, 0, 0),
                (
                    slot_x,
                    slot_y,
                    slot_w,
                    slot_h,
                ),
                2,
            )

            self.draw_small_text(
                screen,
                name,
                slot_x,
                slot_y - 18,
            )

    def draw(
        self,
        screen,
        game,
    ):
        # Old board-screen mode.
        screen.blit(
            self.bg,
            (0, 0),
        )

        clickable_cards = []

        # --------------------------------------------------------
        # MONUMENT DECK
        # --------------------------------------------------------

        if getattr(
            game,
            "monument_deck",
            [],
        ):
            self.draw_card_back_in_slot(
                screen,
                "monument_deck",
                f"Deck: {len(game.monument_deck)}",
            )

        # --------------------------------------------------------
        # OPEN MONUMENTS
        # --------------------------------------------------------

        for index, card in enumerate(
            getattr(
                game,
                "market_monuments",
                [],
            )[:2],
            start=1,
        ):
            slot_name = (
                f"open_monument_{index}"
            )

            rect = (
                self.draw_card_in_slot(
                    screen,
                    card,
                    slot_name,
                )
            )

            if rect is not None:
                clickable_cards.append(
                    (
                        rect,
                        card,
                        slot_name,
                    )
                )

        # --------------------------------------------------------
        # PLACES OF POWER
        # --------------------------------------------------------

        for index, card in enumerate(
            getattr(
                game,
                "market_places",
                [],
            )[:5],
            start=1,
        ):
            slot_name = (
                f"place_{index}"
            )

            rect = (
                self.draw_card_in_slot(
                    screen,
                    card,
                    slot_name,
                )
            )

            if rect is not None:
                clickable_cards.append(
                    (
                        rect,
                        card,
                        slot_name,
                    )
                )

        # --------------------------------------------------------
        # MAGIC ITEMS
        # --------------------------------------------------------

        for index, card in enumerate(
            getattr(
                game,
                "items_pool",
                [],
            )[:8],
            start=1,
        ):
            slot_name = (
                f"item_{index}"
            )

            rect = (
                self.draw_card_in_slot(
                    screen,
                    card,
                    slot_name,
                )
            )

            if rect is not None:
                clickable_cards.append(
                    (
                        rect,
                        card,
                        slot_name,
                    )
                )

        return clickable_cards

    # ============================================================
    # MAIN CUSTOM TABLE
    # ============================================================

    def draw_main_table_area(
        self,
        screen,
        game,
        camera,
        layout,
    ):
        clickable = []

        # --------------------------------------------------------
        # HELPERS
        # --------------------------------------------------------

        def draw_panel(
            name,
            color=(50, 42, 28),
            border=(190, 140, 60),
        ):
            if name not in layout:
                return

            rect = camera.apply_rect(
                layout[name]
            )

            pygame.draw.rect(
                screen,
                color,
                rect,
                border_radius=14,
            )

            pygame.draw.rect(
                screen,
                border,
                rect,
                3,
                border_radius=14,
            )

            inner = rect.inflate(
                -14,
                -14,
            )

            pygame.draw.rect(
                screen,
                (0, 0, 0),
                inner,
                1,
                border_radius=10,
            )

        def draw_empty_slot(
            slot_name,
            border=(190, 140, 55),
        ):
            if slot_name not in layout:
                return

            rect = camera.apply_rect(
                layout[slot_name]
            )

            pygame.draw.rect(
                screen,
                (10, 12, 12),
                rect,
                border_radius=6,
            )

            pygame.draw.rect(
                screen,
                border,
                rect,
                2,
                border_radius=6,
            )

            shade = pygame.Surface(
                (
                    max(1, rect.w),
                    max(1, rect.h),
                ),
                pygame.SRCALPHA,
            )

            shade.fill(
                (
                    255,
                    255,
                    255,
                    18,
                )
            )

            screen.blit(
                shade,
                rect.topleft,
            )

        def draw_card(
            card,
            slot_name,
            source,
        ):
            if (
                not card
                or slot_name not in layout
            ):
                return

            slot = layout[
                slot_name
            ]

            sx, sy = (
                camera.world_to_screen(
                    slot.x,
                    slot.y,
                )
            )

            sw = max(
                1,
                int(
                    slot.w
                    * camera.zoom
                ),
            )

            sh = max(
                1,
                int(
                    slot.h
                    * camera.zoom
                ),
            )

            try:
                rect = (
                    self.card_renderer
                    .draw_card_with_state(
                        screen,
                        card,
                        sx,
                        sy,
                        sw,
                        sh,
                        rotate=False,
                    )
                )

            except Exception as error:
                print(
                    "WARNING: Failed drawing card:",
                    getattr(
                        card.definition,
                        "name",
                        None,
                    )
                    or card.definition.raw_data.get(
                        "name_en",
                        "Unknown",
                    ),
                )

                print(
                    "Reason:",
                    error,
                )

                # Browser-safe fallback rectangle
                rect = pygame.Rect(
                    sx,
                    sy,
                    sw,
                    sh,
                )

                pygame.draw.rect(
                    screen,
                    (60, 60, 60),
                    rect,
                )

                pygame.draw.rect(
                    screen,
                    (180, 180, 180),
                    rect,
                    2,
                )

            clickable.append(
                (
                    rect,
                    card,
                    source,
                )
            )

        def draw_deck_box(
            slot_name,
            label,
            count,
        ):
            if slot_name not in layout:
                return

            rect = camera.apply_rect(
                layout[slot_name]
            )

            pygame.draw.rect(
                screen,
                (35, 30, 25),
                rect,
                border_radius=8,
            )

            pygame.draw.rect(
                screen,
                (180, 140, 70),
                rect,
                2,
                border_radius=8,
            )

            text = pygame.font.SysFont(
                "arial",
                18,
            ).render(
                f"{label}: {count}",
                True,
                (255, 255, 255),
            )

            screen.blit(
                text,
                text.get_rect(
                    center=rect.center
                ),
            )

        # --------------------------------------------------------
        # MAIN TABLE
        # --------------------------------------------------------

        draw_panel(
            "main",
            (50, 42, 28),
            (180, 140, 70),
        )

        # Places
        for i in range(
            1,
            6,
        ):
            draw_empty_slot(
                f"POP_{i}"
            )

        # Open monuments
        for i in range(
            1,
            3,
        ):
            draw_empty_slot(
                f"OpenMonument_{i}"
            )

        # Items
        for i in range(
            1,
            9,
        ):
            draw_empty_slot(
                f"Item_{i}"
            )

        # Monument deck
        draw_empty_slot(
            "MonumentDeck"
        )

        # --------------------------------------------------------
        # PLACES OF POWER
        # --------------------------------------------------------

        places = getattr(
            game,
            "market_places",
            [],
        )

        for i, card in enumerate(
            places[:5],
            start=1,
        ):
            draw_card(
                card,
                f"POP_{i}",
                f"place_{i}",
            )

        # --------------------------------------------------------
        # MONUMENTS
        # --------------------------------------------------------

        monuments = getattr(
            game,
            "market_monuments",
            [],
        )

        for i, card in enumerate(
            monuments[:2],
            start=1,
        ):
            draw_card(
                card,
                f"OpenMonument_{i}",
                f"monument_{i}",
            )

        draw_deck_box(
            "MonumentDeck",
            "Deck",
            len(
                getattr(
                    game,
                    "monument_deck",
                    [],
                )
            ),
        )

        # --------------------------------------------------------
        # MAGIC ITEMS
        # --------------------------------------------------------

        item_slot_order = {
            "calm / elan": 1,
            "death / life": 2,
            "research": 3,
            "protection": 4,
            "reanimate": 5,
            "alchemy": 6,
            "transmutation": 7,
            "divination": 8,
        }

        items = getattr(
            game,
            "items_pool",
            [],
        )

        for (
            real_index,
            card,
        ) in enumerate(items):

            name = (
                getattr(
                    card.definition,
                    "name",
                    "",
                )
                or card.definition.raw_data.get(
                    "name_en",
                    "",
                )
                or ""
            ).lower()

            slot_index = None

            for (
                key,
                slot_no,
            ) in item_slot_order.items():

                if key in name:
                    slot_index = (
                        slot_no
                    )
                    break

            if slot_index is None:
                continue

            draw_card(
                card,
                f"Item_{slot_index}",
                f"item_{real_index}",
            )

        return clickable