import pygame # type: ignore

from ui.player_board_layout import (
    AI_BOARD_SLOTS,
    AI_BOARD_SLOT_SIZES,
    ESSENCE_CIRCLES,
    FIRST_PLAYER_TOKEN,
)
from ui.hand_viewer import HandViewer

from pathlib import Path


class AIArea:
    def __init__(self, card_renderer):
        self.card_renderer = card_renderer
        self.font = pygame.font.SysFont("arial", 18)
        self.small_font = pygame.font.SysFont("arial", 14)
        self.hand_viewer = HandViewer(card_renderer)
        root_dir = Path(__file__).resolve().parents[1]

        self.first_token_img = self.make_white_transparent(
            pygame.image.load(
                str(root_dir / "assets" / "cards" / "First_player_token.png")
            )
        )

        self.first_token_passed_img = self.make_white_transparent(
            pygame.image.load(
                str(root_dir / "assets" / "cards" / "First_player_token_passed.png")
            )
        )
        


    def make_white_transparent(self,surface):
        surface = surface.convert_alpha()

        width = surface.get_width()
        height = surface.get_height()

        for x in range(width):
            for y in range(height):
                r, g, b, a = surface.get_at((x, y))

                if r > 240 and g > 240 and b > 240:
                    surface.set_at((x, y), (255, 255, 255, 0))

        return surface
    def draw_text(self, screen, text, x, y):
        label = self.font.render(text, True, (255, 255, 255))
        screen.blit(label, (x, y))

    def draw_small_text(self, screen, text, x, y):
        label = self.small_font.render(text, True, (220, 220, 220))
        screen.blit(label, (x, y))

    def draw_slot(self, screen, name):
        x, y = AI_BOARD_SLOTS[name]
        w, h = AI_BOARD_SLOT_SIZES[name]
        pygame.draw.rect(screen, (120, 120, 120), (x, y, w, h), 2)

    def draw_card_in_slot(self, screen, card, slot_name):
        if not card:
            return None

        actual_slot = slot_name

        if getattr(card, "tapped", False):

            tap_slot = f"{slot_name}tap"

            if tap_slot in AI_BOARD_SLOTS:

                x, y = AI_BOARD_SLOTS[tap_slot]
                w, h = AI_BOARD_SLOT_SIZES[tap_slot]

                return self.card_renderer.draw_card_with_state(
                    screen,
                    card,
                    x,
                    y,
                    w,
                    h,
                    rotate=True
                )

        x, y = AI_BOARD_SLOTS[actual_slot]
        w, h = AI_BOARD_SLOT_SIZES[actual_slot]

        return self.card_renderer.draw_card_with_state(
            screen,
            card,
            x,
            y,
            w,
            h,
            tapped=False
        )

    def get_cards(self, player, attr_name):
        return getattr(player, attr_name, [])

    def draw_essence_circles(self, screen, player):
        for essence, data in ESSENCE_CIRCLES.items():
            cx, cy, radius = data

            pygame.draw.circle(screen, (255, 180, 0), (cx, cy), radius, 2)

            value = player.essence_pool.get(essence, 0)

            label = self.small_font.render(essence, True, (255, 255, 255))
            value_text = self.font.render(str(value), True, (255, 255, 255))

            screen.blit(label, (cx - 20, cy - radius - 25))
            screen.blit(value_text, (cx - 6, cy - 10))

    def draw_first_player_token(self, screen, player):
        if not getattr(player, "has_first_player_token", False):
            return

        for name, data in FIRST_PLAYER_TOKEN.items():
            cx, cy, radius = data
            size = radius * 2

            img = (
                self.first_token_passed_img
                if getattr(player, "passed", False)
                else self.first_token_img
            )

            img = pygame.transform.smoothscale(img, (size, size))
            rect = img.get_rect(center=(cx, cy))
            screen.blit(img, rect)
            pygame.draw.circle(
                screen,
                (255, 220, 80),
                rect.center,
                size // 2,
                3
            )

    def draw_ai_board(self, screen, player):
        screen.fill((25, 30, 35))

        clickable_cards = []

        self.draw_text(screen, f"AI BOARD - {player.name}", 40, 20)
        self.draw_small_text(screen, f"VP: {player.victory_points}", 40, 45)
        self.draw_small_text(screen, f"AI Hand: {len(player.hand)} hidden card(s)", 140, 45)

        for slot_name in AI_BOARD_SLOTS:
            self.draw_slot(screen, slot_name)

        if player.mage:
            rect = self.draw_card_in_slot(screen, player.mage, "mage")
            clickable_cards.append((rect, player.mage, "ai_mage"))

        if player.item:
            rect = self.draw_card_in_slot(screen, player.item, "item")
            clickable_cards.append((rect, player.item, "ai_item"))

        self.draw_small_text(screen, f"Deck: {len(player.deck_hidden)}", *AI_BOARD_SLOTS["drawpile"])
        self.draw_small_text(screen, "Discard", *AI_BOARD_SLOTS["discardpile"])
        if player.discard:
            rect = self.draw_card_in_slot(screen, player.discard[-1], "discardpile")
            clickable_cards.append((rect, player.discard[-1], "discardpile"))

        places = self.get_cards(player, "places")
        for i, card in enumerate(places[:3], start=1):
            slot = f"place_{i}"
            rect = self.draw_card_in_slot(screen, card, slot)
            clickable_cards.append((rect, card, f"ai_{slot}"))

        monuments = self.get_cards(player, "monuments")
        for i, card in enumerate(monuments[:5], start=1):
            slot = f"monument_{i}"
            rect = self.draw_card_in_slot(screen, card, slot)
            clickable_cards.append((rect, card, f"ai_{slot}"))

        for i, card in enumerate(player.played[:8], start=1):
            slot = f"artifact_{i}"
            rect = self.draw_card_in_slot(screen, card, slot)
            clickable_cards.append((rect, card, f"ai_{slot}"))

        self.draw_essence_circles(screen, player)
        self.draw_first_player_token(screen, player)

        hand_pos = AI_BOARD_SLOTS["hand_viewer"]
        hand_size = AI_BOARD_SLOT_SIZES["hand_viewer"]

        self.hand_viewer.draw_ai_hand_count_in_slot(
            screen,
            player,
            hand_pos,
            hand_size
        )

        self.draw_small_text(
            screen,
            "Press B = Main Board | P = Player Board",
            40,
            screen.get_height() - 30,
        )

        return clickable_cards
    
    def draw_essence_table(self, screen, player, camera, wx, wy):
        essences = ["gold", "elan", "life", "calm", "death"]

        for i, essence in enumerate(essences):
            sx, sy = camera.world_to_screen(wx + i * 80, wy)
            value = player.essence_pool.get(essence, 0)

            pygame.draw.circle(screen, (255, 180, 0), (sx, sy), int(22 * camera.zoom), 2)

            text = self.small_font.render(str(value), True, (255, 255, 255))
            screen.blit(text, (sx - 5, sy + 25))


    def draw_status_table(self, screen, player, camera, wx, wy):
        sx, sy = camera.world_to_screen(wx, wy)

        text = self.font.render(f"VP: {player.victory_points}", True, (255, 255, 255))
        screen.blit(text, (sx, sy))

        token_x, token_y = camera.world_to_screen(wx + 170, wy + 10)

        if getattr(player, "has_first_player_token", False):
            img = (
                self.first_token_passed_img
                if getattr(player, "passed", False)
                else self.first_token_img
            )

            size = int(70 * camera.zoom)
            img = pygame.transform.smoothscale(img, (size, size))
            rect = img.get_rect(center=(token_x, token_y))
            screen.blit(img, rect)





    def draw_ai_table_area(self, screen, player, camera, layout, essence_renderer=None):
        clickable = []

        def draw_panel(name, color=(35, 45, 35), border=(120, 180, 120)):
            if name not in layout:
                return

            rect = camera.apply_rect(layout[name])

            pygame.draw.rect(screen, color, rect, border_radius=14)
            pygame.draw.rect(screen, border, rect, 3, border_radius=14)

            inner = rect.inflate(-12, -12)
            pygame.draw.rect(screen, (0, 0, 0), inner, 1, border_radius=10)



        def draw_empty_slot(slot_name, border=(190, 140, 55)):
            if slot_name not in layout:
                return

            rect = camera.apply_rect(layout[slot_name])

            pygame.draw.rect(screen, (10, 12, 12), rect, border_radius=6)
            pygame.draw.rect(screen, border, rect, 2, border_radius=6)

            shade = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
            shade.fill((255, 255, 255, 18))
            screen.blit(shade, rect.topleft)

        def draw_card(card, slot_name, tap_slot_name=None, source="card"):
            if not card:
                return

            real_slot = slot_name

            if getattr(card, "tapped", False) and tap_slot_name in layout:
                real_slot = tap_slot_name

            if real_slot not in layout:
                return

            slot = layout[real_slot]
            sx, sy = camera.world_to_screen(slot.x, slot.y)
            sw = int(slot.w * camera.zoom)
            sh = int(slot.h * camera.zoom)

            rect = self.card_renderer.draw_card_with_state(
                screen,
                card,
                sx,
                sy,
                sw,
                sh,
                rotate=getattr(card, "tapped", False)
            )

            clickable.append((rect, card, source))

        def draw_box(slot_name, label, count=None):
            if slot_name not in layout:
                return

            rect = camera.apply_rect(layout[slot_name])
            pygame.draw.rect(screen, (35, 35, 35), rect, border_radius=8)
            pygame.draw.rect(screen, (180, 140, 70), rect, 2, border_radius=8)

            text_value = label if count is None else f"{label}\n{count}"
            lines = text_value.split("\n")

            y = rect.centery - (len(lines) * 10)
            for line in lines:
                text = self.small_font.render(line, True, (255, 255, 255))
                screen.blit(text, text.get_rect(center=(rect.centerx, y)))
                y += 22

        def draw_circle_value(slot_name, essence):
            if essence_renderer is None:
                return

            amount = player.essence_pool.get(essence.lower(), 0)

            essence_renderer.draw_token(
                screen,
                camera,
                layout,
                slot_name,
                essence.lower(),
                amount
            )

        def draw_first_token():
            if not getattr(player, "has_first_player_token", False):
                return
            if "AIFPT" not in layout:
                return

            data = layout["AIFPT"]
            sx, sy = camera.world_to_screen(data["x"], data["y"])
            size = int(data["r"] * 2 * camera.zoom)

            img = self.first_token_passed_img if player.passed else self.first_token_img
            img = pygame.transform.smoothscale(img, (size, size))
            rect = img.get_rect(center=(sx, sy))
            screen.blit(img, rect)

            pygame.draw.circle(screen, (255, 220, 80), rect.center, size // 2, 2)

        def draw_vp():
            if "ai_vp" not in layout:
                return

            rect = camera.apply_rect(layout["ai_vp"])
            pygame.draw.rect(screen, (25, 25, 35), rect, border_radius=8)
            pygame.draw.rect(screen, (180, 140, 70), rect, 2, border_radius=8)

            text = self.font.render(f"VP: {player.victory_points}", True, (255, 255, 255))
            screen.blit(text, text.get_rect(center=rect.center))

        draw_panel("ai_area", (45, 30, 45), (160, 90, 180))
        draw_panel("ai_artifacts_area", (35, 35, 45), (120, 120, 160))
        draw_panel("ai_POP_area", (25, 35, 45), (90, 130, 180))

        # empty AI slots
        draw_empty_slot("ai_mage")
        draw_empty_slot("ai_item")
        draw_empty_slot("ai_draw_deck")
        draw_empty_slot("ai_discard")

        for i in range(1, 4):
            draw_empty_slot(f"ai_POP_{i}")
            

        for i in range(1, 13):
            draw_empty_slot(f"artifact_{i}")
            

        for i in range(1, 5):
            draw_empty_slot(f"monument_{i}")
            

            
        draw_card(player.mage, "ai_mage", "ai_mage_tap", "ai_mage")
        draw_card(player.item, "ai_item", "ai_item_tap", "ai_item")

        draw_box("ai_draw_deck", "Deck", len(player.deck_hidden))

        if player.discard:
            draw_card(player.discard[-1], "ai_discard", None, "ai_discard")
        else:
            draw_box("ai_discard", "Discard", 0)

        draw_circle_value("elan", "elan")
        draw_circle_value("calm", "calm")
        draw_circle_value("gold", "gold")
        draw_circle_value("death", "death")
        draw_circle_value("life", "life")

        draw_vp()
        draw_first_token()

        # AI places of power
        for i, card in enumerate(player.places[:3], start=1):
            draw_card(
                card,
                f"ai_POP_{i}",
                f"ai_POP_tap_{i}",
                f"ai_place_{i}"
            )

        # ---------------------------------------
        # AI ARTIFACTS + MONUMENT OVERFLOW
        # ---------------------------------------

        artifact_cards = list(
            player.played
        )

        occupied_artifact_slots = set()


        # Draw AI artifacts normally.
        for i, card in enumerate(
            artifact_cards[:12],
            start=1,
        ):
            slot_name = f"artifact_{i}"

            draw_card(
                card,
                slot_name,
                f"artifact_tap_{i}",
                f"ai_artifact_{i}",
            )

            occupied_artifact_slots.add(
                slot_name
            )


        # First 4 monuments use dedicated slots.
        for i, card in enumerate(
            player.monuments[:4],
            start=1,
        ):
            draw_card(
                card,
                f"monument_{i}",
                f"monument_tap_{i}",
                f"ai_monument_{i}",
            )


        # Monument #5 onward borrows empty
        # artifact slots backwards.
        overflow_monuments = (
            player.monuments[4:]
        )


        free_artifact_slots = []

        for i in range(12, 0, -1):
            slot_name = f"artifact_{i}"

            if (
                slot_name in layout
                and slot_name
                not in occupied_artifact_slots
            ):
                free_artifact_slots.append(i)


        for monument_index, card in enumerate(
            overflow_monuments
        ):
            if monument_index >= len(
                free_artifact_slots
            ):
                break

            slot_number = free_artifact_slots[
                monument_index
            ]

            draw_card(
                card,
                f"artifact_{slot_number}",
                f"artifact_tap_{slot_number}",
                (
                    "ai_monument_overflow_"
                    f"{monument_index + 5}"
                ),
            )
        return clickable