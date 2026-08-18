import pygame # type: ignore

from ui.player_board_layout import (
    PLAYER_BOARD_SLOTS,
    PLAYER_BOARD_SLOT_SIZES,
    ESSENCE_CIRCLES,
    FIRST_PLAYER_TOKEN,
)
from ui.hand_viewer import HandViewer
from pathlib import Path

class PlayerArea:
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
        x, y = PLAYER_BOARD_SLOTS[name]
        w, h = PLAYER_BOARD_SLOT_SIZES[name]
        pygame.draw.rect(screen, (120, 120, 120), (x, y, w, h), 2)

    def draw_card_in_slot(self, screen, card, slot_name):
        if not card:
            return None

        actual_slot = slot_name

        if getattr(card, "tapped", False):

            tap_slot = f"{slot_name}tap"

            if tap_slot in PLAYER_BOARD_SLOTS:

                x, y = PLAYER_BOARD_SLOTS[tap_slot]
                w, h = PLAYER_BOARD_SLOT_SIZES[tap_slot]

                return self.card_renderer.draw_card_with_state(
                    screen,
                    card,
                    x,
                    y,
                    w,
                    h,
                    rotate=True
                )

        x, y = PLAYER_BOARD_SLOTS[actual_slot]
        w, h = PLAYER_BOARD_SLOT_SIZES[actual_slot]

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

    def draw_player_board(self, screen, player, game=None):
        screen.fill((25, 30, 35))

        clickable_cards = []

        self.draw_text(screen, f"PLAYER BOARD - {player.name}", 40, 20)
        self.draw_small_text(screen, f"VP: {player.victory_points}", 40, 45)

        for slot_name in PLAYER_BOARD_SLOTS:
            self.draw_slot(screen, slot_name)

        # SETUP MODE:
        # Show all 8 starting artifacts and 2 mage options before the real game starts.
        is_setup_mage = (
            game
            and (
                game.current_phase in ["setup_show_starting_cards", "setup_choose_mage"]
                or (
                    game.current_phase == "setup"
                    and getattr(game, "current_setup_step", "") == "choose_human_mage"
                )
            )
        )

        if is_setup_mage:
            setup_cards = getattr(player, "setup_artifacts", [])

            for i, card in enumerate(setup_cards[:8], start=1):
                slot = f"artifact_{i}"
                rect = self.draw_card_in_slot(screen, card, slot)
                clickable_cards.append((rect, card, f"setup_artifact_{i}"))

            mage_options = getattr(player, "mage_options", [])

            for i, mage in enumerate(mage_options[:2], start=1):
                slot = f"monument_{i}"
                rect = self.draw_card_in_slot(screen, mage, slot)
                clickable_cards.append((rect, mage, f"setup_mage_{i - 1}"))

            self.draw_essence_circles(screen, player)
            self.draw_first_player_token(screen, player)

            self.draw_small_text(
                screen,
                "Setup: Check your 8 artifacts, then click one mage card.",
                40,
                screen.get_height() - 30,
            )

            return clickable_cards

        if player.mage:
            rect = self.draw_card_in_slot(screen, player.mage, "mage")
            clickable_cards.append((rect, player.mage, "mage"))

        if player.item:
            rect = self.draw_card_in_slot(screen, player.item, "item")
            clickable_cards.append((rect, player.item, "item"))

        self.draw_small_text(
            screen,
            f"Deck: {len(player.deck_hidden)}",
            *PLAYER_BOARD_SLOTS["drawpile"]
        )

        self.draw_small_text(
            screen,
            "Discard",
            *PLAYER_BOARD_SLOTS["discardpile"]
        )

        if player.discard:
            rect = self.draw_card_in_slot(
                screen,
                player.discard[-1],
                "discardpile"
            )
            clickable_cards.append((rect, player.discard[-1], "discardpile"))

        places = self.get_cards(player, "places")
        for i, card in enumerate(places[:3], start=1):
            slot = f"place_{i}"
            rect = self.draw_card_in_slot(screen, card, slot)
            clickable_cards.append((rect, card, f"player_{slot}"))

        monuments = self.get_cards(player, "monuments")
        played_artifacts = list(player.played)

        for i, card in enumerate(monuments[:5], start=1):
            slot = f"monument_{i}"
            rect = self.draw_card_in_slot(screen, card, slot)
            clickable_cards.append((rect, card, f"player_{slot}"))

        overflow_monuments = monuments[5:]
        artifact_slot_cards = played_artifacts + overflow_monuments

        for i, card in enumerate(artifact_slot_cards[:8], start=1):
            slot = f"artifact_{i}"
            rect = self.draw_card_in_slot(screen, card, slot)

            if card in overflow_monuments:
                source = f"player_monument_overflow_{i}"
            else:
                source = f"player_{slot}"

            clickable_cards.append((rect, card, source))

        self.draw_essence_circles(screen, player)
        self.draw_first_player_token(screen, player)

        hand_pos = PLAYER_BOARD_SLOTS["hand_viewer"]
        hand_size = PLAYER_BOARD_SLOT_SIZES["hand_viewer"]

        hand_clickables = self.hand_viewer.draw_player_hand_in_slot(
            screen,
            player,
            hand_pos,
            hand_size,
            game
        )

        clickable_cards.extend(hand_clickables)

        self.draw_small_text(
            screen,
            "Press B = Main Board | A = AI Board",
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



    def draw_player_table_area(self, screen, player, game, camera, layout, essence_renderer=None):
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
            if "PFPT" not in layout:
                return

            data = layout["PFPT"]
            sx, sy = camera.world_to_screen(data["x"], data["y"])
            size = int(data["r"] * 2 * camera.zoom)

            img = self.first_token_passed_img if player.passed else self.first_token_img
            img = pygame.transform.smoothscale(img, (size, size))
            rect = img.get_rect(center=(sx, sy))
            screen.blit(img, rect)

            pygame.draw.circle(screen, (255, 220, 80), rect.center, size // 2, 2)

        def draw_vp():
            if "player_vp" not in layout:
                return

            rect = camera.apply_rect(layout["player_vp"])
            pygame.draw.rect(screen, (25, 25, 35), rect, border_radius=8)
            pygame.draw.rect(screen, (180, 140, 70), rect, 2, border_radius=8)

            text = self.font.render(f"VP: {player.victory_points}", True, (255, 255, 255))
            screen.blit(text, text.get_rect(center=rect.center))

        # panels
        draw_panel("ai_area_copy_15", (25, 45, 30), (90, 160, 90))
        draw_panel("player_artifacts_area", (25, 35, 45), (120, 120, 160))
        draw_panel("player_POP_area", (25, 45, 35), (90, 160, 90))

        # empty player slots
        draw_empty_slot("player_mage")
        draw_empty_slot("player_item")
        draw_empty_slot("player_draw_deck")
        draw_empty_slot("player_discard")

        for i in range(1, 4):
            draw_empty_slot(f"Player_POP_{i}")
            

        for i in range(1, 13):
            draw_empty_slot(f"Artifact_{i}")
            

        for i in range(1, 5):
            draw_empty_slot(f"Monument_{i}")
            



        is_setup_mage = (
            game
            and (
                game.current_phase in ["setup_show_starting_cards", "setup_choose_mage"]
                or (
                    game.current_phase == "setup"
                    and getattr(game, "current_setup_step", "") == "choose_human_mage"
                )
            )
        )

        if is_setup_mage:
            mage_options = list(getattr(player, "mage_options", []))

            if len(mage_options) > 0:
                draw_card(mage_options[0], "Artifact_10", None, "setup_mage_0")

            if len(mage_options) > 1:
                draw_card(mage_options[1], "Artifact_11", None, "setup_mage_1")

        else:
            draw_card(player.mage, "player_mage", "player_mage_tap", "mage")
            draw_card(player.item, "player_item", "player_item_tap", "item")

        draw_box("player_draw_deck", "Deck", len(player.deck_hidden))

        if player.discard:
            draw_card(player.discard[-1], "player_discard", None, "player_discard")
        else:
            draw_box("player_discard", "Discard", 0)

        # essence
        draw_circle_value("Elan", "elan")
        draw_circle_value("Calm", "calm")
        draw_circle_value("Gold", "gold")
        draw_circle_value("Death", "death")
        draw_circle_value("Life", "life")

        draw_vp()
        draw_first_token()

        # player places of power
        for i, card in enumerate(player.places[:3], start=1):
            draw_card(
                card,
                f"Player_POP_{i}",
                f"Player_POP_tap_{i}",
                f"player_place_{i}"
            )

        # ---------------------------------------
        # PLAYER ARTIFACTS + MONUMENT OVERFLOW
        # ---------------------------------------

        is_setup_mage = (
            game
            and (
                game.current_phase in [
                    "setup_show_starting_cards",
                    "setup_choose_mage",
                ]
                or (
                    game.current_phase == "setup"
                    and getattr(
                        game,
                        "current_setup_step",
                        "",
                    ) == "choose_human_mage"
                )
            )
        )

        if is_setup_mage:
            artifact_cards = list(
                getattr(
                    player,
                    "setup_artifacts",
                    [],
                )
            )
        else:
            artifact_cards = list(
                player.played
            )


        # Keep track of artifact slots already used.
        occupied_artifact_slots = set()


        # Draw normal artifacts first.
        for i, card in enumerate(
            artifact_cards[:12],
            start=1,
        ):
            source = (
                f"setup_artifact_{i}"
                if is_setup_mage
                else f"player_artifact_{i}"
            )

            slot_name = f"Artifact_{i}"

            draw_card(
                card,
                slot_name,
                f"Artifact_tap_{i}",
                source,
            )

            occupied_artifact_slots.add(
                slot_name
            )


        # First 4 monuments use normal monument slots.
        normal_monuments = player.monuments[:4]

        for i, card in enumerate(
            normal_monuments,
            start=1,
        ):
            draw_card(
                card,
                f"Monument_{i}",
                f"Monument_tap_{i}",
                f"player_monument_{i}",
            )


        # Any monument after #4 uses empty artifact
        # slots backwards:
        #
        # Artifact_12
        # Artifact_11
        # Artifact_10
        # ...
        overflow_monuments = player.monuments[4:]


        free_artifact_slots = []

        for i in range(12, 0, -1):
            slot_name = f"Artifact_{i}"

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
                f"Artifact_{slot_number}",
                f"Artifact_tap_{slot_number}",
                (
                    "player_monument_overflow_"
                    f"{monument_index + 5}"
                ),
            )

        return clickable