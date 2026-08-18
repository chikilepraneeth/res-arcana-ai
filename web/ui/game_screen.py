import pygame # type: ignore

from ui.card_renderer import CardRenderer
from ui.board import Board
from ui.player_area import PlayerArea
from ui.ai_area import AIArea
from ui.zoom_viewer import ZoomViewer
from ui.action_panel import ActionPanel
from src.collection_phase import resolve_collection_action
from action_resolver import ActionResolver # type: ignore
from attack_resolver import AttackResolver # type: ignore
from ui.camera import Camera
import json
from pathlib import Path
from ui.essence_renderer import EssenceRenderer
from game_memory import record_move, snapshot_game
from victory_reactions import (
    can_use_golden_statue,
    use_golden_statue,
)
from ui.quantity_selector import QuantitySelector

from gui_actions import ( # type: ignore
    gui_play_card,
    gui_buy_monument,
    gui_buy_place,
    gui_discard_for_gold,
    gui_discard_for_essence,
)

from rules_engine import (
    use_power,
    pass_turn,
    check_victory,
    choose_item_for_player,
)


ESSENCE_KEYS_LOCAL = ["gold", "elan", "life", "calm", "death"]


class GameScreen:
    def __init__(self, screen, game_state, assets_dir):
        self.screen = screen
        self.game_state = game_state
        self.assets_dir = assets_dir

        self.current_screen = "board"

        self.card_renderer = CardRenderer(assets_dir)

        self.board = Board(self.card_renderer)
        self.player_area = PlayerArea(self.card_renderer)
        self.ai_area = AIArea(self.card_renderer)

        self.zoom_viewer = ZoomViewer(self.card_renderer)
        self.action_panel = ActionPanel()
        self.action_resolver = ActionResolver(self)
        self.attack_resolver = AttackResolver(self)

        self.clickable_cards = []

        self.zoomed_card = None
        self.zoom_source = None
        self.zoom_buttons = {}

        self.selected_card = None
        self.selected_source = None

        self.pending_essence_choices = []
        self.selected_power = None
        self.pending_x_value = None
        self.pending_target_choices = {}
        self.pending_additional_tap_target_id = None
        self.target_candidates = []
        self.pass_old_item = None
        self.setup_panel_opened = False
        self.pending_play_card = None
        self.pending_play_cost = None
        self.pending_discount_choices = []
        self.pending_wild_choices = []
        self.pending_power_wild_choices = []
        self.essence_renderer = EssenceRenderer()
        self.essence_renderer.load_images()
        from pathlib import Path

        root_dir = Path(__file__).resolve().parents[1]

        self.first_player_token_img = pygame.image.load(
            str(root_dir / "assets" / "cards" / "First_player_token.png")
        ).convert_alpha()

        self.first_player_token_passed_img = pygame.image.load(
            str(root_dir / "assets" / "cards" / "First_player_token_passed.png")
        ).convert_alpha()


        self.camera = Camera()
        self.current_screen = "table"

        layout_path = Path("data/custom_table_layout.json")

        with open(layout_path, "r", encoding="utf-8") as f:
            raw_layout = json.load(f)

        self.table_layout = {}

        for obj in raw_layout:
            if obj["type"] == "rect":
                self.table_layout[obj["name"]] = pygame.Rect(
                    obj["x"],
                    obj["y"],
                    obj["w"],
                    obj["h"]
                )

            elif obj["type"] == "circle":
                self.table_layout[obj["name"]] = obj

        self.table_world_bounds = self.calculate_table_world_bounds()
        self.camera.set_world_bounds(self.table_world_bounds)
        self.camera.fit_to_world(
            self.screen.get_width(),
            self.screen.get_height(),
            padding=50,
        )

        self.mouse_down_pos = None
        self.mouse_dragged = False
        self.hover_hand_index = None
        self.hover_hand_card = None
        self.hover_hand_area_rect = None



        self.essence_icon_panel_active = False
        self.essence_icon_panel_title = ""
        self.essence_icon_panel_message = ""
        self.essence_icon_panel_actions = []
        self.essence_icon_panel_buttons = []

        self.quantity_selector = QuantitySelector(
            self.screen
        )
        self.golden_statue_yes_rect = pygame.Rect(
            0,
            0,
            190,
            58,
        )

        self.golden_statue_no_rect = pygame.Rect(
            0,
            0,
            190,
            58,
        )
        # ============================================================
        # AI BRAIN PANEL
        # ============================================================

        self.ai_brain_panel_visible = True
        self.ai_brain_scroll = 0
    def calculate_table_world_bounds(self):
        bounds = []

        for value in self.table_layout.values():
            if isinstance(value, pygame.Rect):
                bounds.append(pygame.Rect(value))
                continue

            if isinstance(value, dict) and value.get("type") == "circle":
                cx = float(value.get("x", value.get("cx", 0)))
                cy = float(value.get("y", value.get("cy", 0)))

                radius = float(
                    value.get(
                        "r",
                        value.get(
                            "radius",
                            value.get("w", value.get("size", 0)) / 2,
                        ),
                    )
                )

                bounds.append(
                    pygame.Rect(
                        int(cx - radius),
                        int(cy - radius),
                        max(1, int(radius * 2)),
                        max(1, int(radius * 2)),
                    )
                )

        if not bounds:
            return pygame.Rect(0, 0, 1720, 880)

        world_bounds = bounds[0].copy()

        for rect in bounds[1:]:
            world_bounds.union_ip(rect)

        return world_bounds

    def refit_table_to_window(self):
        self.camera.set_world_bounds(self.table_world_bounds)
        self.camera.fit_to_world(
            self.screen.get_width(),
            self.screen.get_height(),
            padding=50,
        )

    def open_essence_icon_panel(self, title, message, actions):
        self.essence_icon_panel_active = True
        self.essence_icon_panel_title = title
        self.essence_icon_panel_message = message
        self.essence_icon_panel_actions = actions
        self.essence_icon_panel_buttons = []

        self.action_panel.close()


    def handle_essence_icon_panel_click(self, mouse_pos):
        if not self.essence_icon_panel_active:
            return False

        for rect, action in self.essence_icon_panel_buttons:
            if rect.collidepoint(mouse_pos):
                if action.startswith("disabled_"):
                    return True

                self.essence_icon_panel_active = False
                self.handle_action_panel_click_from_icon(action)
                return True

        return True
    
    def handle_action_panel_click_from_icon(self, action):
        class FakePanel:
            active = False

            def handle_click(self_inner, mouse_pos):
                return action

            def close(self_inner):
                pass

        old_panel = self.action_panel
        self.action_panel = FakePanel()

        self.handle_action_panel_click((0, 0))

        self.action_panel = old_panel
    def draw_essence_icon_panel(self):
        if not self.essence_icon_panel_active:
            return

        sw = self.screen.get_width()
        sh = self.screen.get_height()

        panel_w = 520
        panel_h = 260

        panel = pygame.Rect(
            sw // 2 - panel_w // 2,
            sh // 2 - panel_h // 2,
            panel_w,
            panel_h
        )

        pygame.draw.rect(self.screen, (25, 22, 18), panel, border_radius=16)
        pygame.draw.rect(self.screen, (190, 140, 60), panel, 3, border_radius=16)

        title_font = pygame.font.SysFont("arial", 24, bold=True)
        msg_font = pygame.font.SysFont("arial", 16)
        small_font = pygame.font.SysFont("arial", 14, bold=True)

        title = title_font.render(self.essence_icon_panel_title, True, (255, 255, 255))
        self.screen.blit(title, title.get_rect(center=(panel.centerx, panel.y + 35)))

        msg = msg_font.render(self.essence_icon_panel_message, True, (220, 220, 220))
        self.screen.blit(msg, msg.get_rect(center=(panel.centerx, panel.y + 68)))

        self.essence_icon_panel_buttons = []

        icon_size = 62
        gap = 22

        total_w = len(self.essence_icon_panel_actions) * icon_size + (len(self.essence_icon_panel_actions) - 1) * gap
        start_x = panel.centerx - total_w // 2
        y = panel.y + 105

        for i, action_data in enumerate(self.essence_icon_panel_actions):
            action, essence = action_data

            x = start_x + i * (icon_size + gap)
            rect = pygame.Rect(x, y, icon_size, icon_size)

            disabled = action.startswith("disabled_")

            pygame.draw.rect(
                self.screen,
                (60, 50, 35) if not disabled else (35, 35, 35),
                rect.inflate(12, 12),
                border_radius=12
            )

            pygame.draw.rect(
                self.screen,
                (210, 160, 70) if not disabled else (80, 80, 80),
                rect.inflate(12, 12),
                2,
                border_radius=12
            )

            if essence in self.essence_renderer.images:
                img = self.essence_renderer.images[essence]

                crop_rect = img.get_bounding_rect()
                img = img.subsurface(crop_rect).copy()

                img = pygame.transform.smoothscale(img, (icon_size, icon_size))

                if disabled:
                    img.set_alpha(90)

                self.screen.blit(img, rect)

            label = small_font.render(essence.title(), True, (230, 230, 230))
            self.screen.blit(label, label.get_rect(center=(rect.centerx, rect.bottom + 22)))

            self.essence_icon_panel_buttons.append((rect.inflate(16, 16), action))

        cancel_rect = pygame.Rect(panel.centerx - 45, panel.bottom - 45, 90, 28)
        pygame.draw.rect(self.screen, (55, 45, 35), cancel_rect, border_radius=8)
        pygame.draw.rect(self.screen, (190, 140, 60), cancel_rect, 2, border_radius=8)

        cancel_text = small_font.render("Cancel", True, (255, 255, 255))
        self.screen.blit(cancel_text, cancel_text.get_rect(center=cancel_rect.center))

        self.essence_icon_panel_buttons.append((cancel_rect, "cancel"))
    def get_card_id(self, card):
        return (
            getattr(card.definition, "card_id", None)
            or card.definition.raw_data.get("id")
        )

    def card_name(self, card):
        return (
            getattr(card.definition, "name", None)
            or card.definition.raw_data.get("name_en")
            or card.definition.raw_data.get("id")
        )
    def continue_setup_item_order(self):
        human = self.game_state.players[0]
        ai = self.game_state.players[1]

        while self.game_state.pending_item_order:
            next_player = self.game_state.pending_item_order[0]

            if next_player == "ai":
                try:
                    choose_item_for_player(
                        self.game_state,
                        ai,
                        0,
                        old_item=None
                    )
                    self.game_state.game_log.append(
                        f"AI chose item: {self.card_name(ai.item)}"
                    )
                except Exception as e:
                    self.log_error(e)

                self.game_state.pending_item_order.pop(0)

            elif next_player == "human":
                self.game_state.current_setup_step = "choose_human_item"
                self.game_state.waiting_for_human_item_choice = True
                self.game_state.game_log.append("Choose your starting item by clicking one from the market.")
                return
                

        self.game_state.current_setup_step = "setup_done"
        self.game_state.current_phase = "collect"
        self.game_state.collect_phase_started = False

        self.game_state.game_log.append("Setup complete.")
        self.game_state.game_log.append(f"=== ROUND {self.game_state.round_no} COLLECTION PHASE ===")

        self.show_phase_banner(
            "COLLECTION PHASE",
            "Collect essence from mage, item, artifacts, monuments, and places.",
            4
        )




    def get_power_wild_count_and_allowed(self):
        cost = self.selected_power.get("cost", {})
        wild = cost.get("wild")

        if not wild:
            return 0, []

        if isinstance(wild, int):
            return wild, ["elan", "life", "calm", "death", "gold"]

        if isinstance(wild, dict):
            count = wild.get("count", 0)
            allowed = wild.get("allowed", ["elan", "life", "calm", "death", "gold"])

            if isinstance(count, int):
                return count, allowed

        return 0, []


    def power_needs_wild_payment(self):
        count, allowed = self.get_power_wild_count_and_allowed()
        return len(self.pending_power_wild_choices) < count


    def get_power_wild_candidates(self):
        player = self.game_state.players[0]
        cost = self.selected_power.get("cost", {})
        essence_cost = cost.get("essence", {})

        remaining_pool = dict(player.essence_pool)

        for essence, amount in essence_cost.items():
            remaining_pool[essence] = remaining_pool.get(essence, 0) - int(amount)

        for chosen in self.pending_power_wild_choices:
            remaining_pool[chosen] = remaining_pool.get(chosen, 0) - 1

        count, allowed = self.get_power_wild_count_and_allowed()

        return [
            essence for essence in allowed
            if remaining_pool.get(essence, 0) > 0
        ]


    def open_power_wild_panel(self):
        count, allowed = self.get_power_wild_count_and_allowed()
        candidates = self.get_power_wild_candidates()

        actions = []

        for essence in candidates:
            actions.append((f"power_wild_{essence}", f"Pay {essence.title()}"))

        actions.append(("cancel", "Cancel"))

        self.action_panel.open(
            "Choose Power Payment",
            f"Choose essence payment {len(self.pending_power_wild_choices) + 1} of {count}.",
            actions,
        )
    def log_error(self, error):
        self.game_state.game_log.append(f"Action failed: {error}")
    def phase_banner_active(self):
        
        return pygame.time.get_ticks() < getattr(self.game_state, "phase_banner_until", 0)


    def show_phase_banner(self, title, message, seconds):
        
        self.game_state.phase_banner_title = title
        self.game_state.phase_banner_message = message
        self.game_state.phase_banner_until = pygame.time.get_ticks() + int(seconds * 1000)


    def draw_phase_banner(self):
        if not self.phase_banner_active():
            return

        sw = self.screen.get_width()
        sh = self.screen.get_height()

        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))

        font = pygame.font.SysFont("arial", 58, bold=True)
        small_font = pygame.font.SysFont("arial", 26)

        title = getattr(self.game_state, "phase_banner_title", "")
        message = getattr(self.game_state, "phase_banner_message", "")

        title_surf = font.render(title, True, (255, 255, 255))
        msg_surf = small_font.render(message, True, (230, 230, 230))

        self.screen.blit(
            title_surf,
            title_surf.get_rect(center=(sw // 2, sh // 2 - 40))
        )

        self.screen.blit(
            msg_surf,
            msg_surf.get_rect(center=(sw // 2, sh // 2 + 35))
        )




    def draw_table_screen(self):
        self.screen.fill((18, 14, 10))
        self.clickable_cards = []

        human = self.game_state.players[0]
        ai = self.game_state.players[1]
        layout = self.table_layout

        self.clickable_cards.extend(
        self.ai_area.draw_ai_table_area(
            self.screen,
            ai,
            self.camera,
            layout,
            self.essence_renderer
        )
        )

        self.clickable_cards.extend(
            self.board.draw_main_table_area(
                self.screen,
                self.game_state,
                self.camera,
                layout
            )
        )

        self.game_state.essence_renderer = self.essence_renderer

        self.clickable_cards.extend(
            self.player_area.draw_player_table_area(
                self.screen,
                human,
                self.game_state,
                self.camera,
                layout,
                self.essence_renderer
            )
        )
        self.draw_game_log_table()
        self.draw_player_hand_table()

    def draw_player_hand_table(self):
        hand_key = "player_hand"

        if hand_key not in self.table_layout:
            hand_key = "player hand"

        if hand_key not in self.table_layout:
            return

        player = self.game_state.players[0]
        area = self.camera.apply_rect(self.table_layout[hand_key])

        pygame.draw.rect(self.screen, (18, 22, 26), area, border_radius=10)
        pygame.draw.rect(self.screen, (120, 120, 160), area, 2, border_radius=10)

        font = pygame.font.SysFont("arial", 16, bold=True)
        small_font = pygame.font.SysFont("arial", 13, bold=True)

        title = font.render(f"Hand: {len(player.hand)} card(s)", True, (255, 255, 255))
        self.screen.blit(title, (area.x + 12, area.y + 10))

        mouse_pos = pygame.mouse.get_pos()

        x = area.x + 12
        y = area.y + 40

        card_w = max(45, int(70 * self.camera.zoom))
        card_h = max(65, int(100 * self.camera.zoom))
        gap = max(8, int(12 * self.camera.zoom))


        mouse_pos = pygame.mouse.get_pos()
        active_hover_index = None
        active_hover_card = None
        active_hover_area = None


        for i, card in enumerate(player.hand[:7]):
            card_x = x + i * (card_w + gap)

            temp_rect = pygame.Rect(card_x, y, card_w, card_h)

            hover_area = pygame.Rect(
                    temp_rect.x - 20,
                    temp_rect.y - 20,
                    temp_rect.w + 80,
                    temp_rect.h + 150
                )
            is_hovered = hover_area.collidepoint(mouse_pos)

            draw_w = int(card_w * 1.15) if is_hovered else card_w
            draw_h = int(card_h * 1.15) if is_hovered else card_h

            draw_x = card_x - (draw_w - card_w) // 2
            draw_y = y - (draw_h - card_h) // 2

            rect = self.card_renderer.draw_card_with_state(
                self.screen,
                card,
                draw_x,
                draw_y,
                draw_w,
                draw_h,
                rotate=False
            )

            #self.clickable_cards.append((rect, card, f"hand_zoom_{i}"))

            if (
                is_hovered
                and self.game_state.current_phase == "action"
                and self.is_human_turn()
                and not player.passed
            ):
                btn_y = rect.bottom + 5
                btn_w = 76
                btn_h = 24

                play_rect = pygame.Rect(rect.x, btn_y, btn_w, btn_h)
                

                discard_rect = pygame.Rect(rect.x, btn_y + 28, btn_w, btn_h)

                buttons = [
                    (play_rect, "Play", f"hand_play_{i}"),
                    (discard_rect, "Discard", f"hand_discard_{i}"),
                ]

                for b_rect, label, source in buttons:
                    pygame.draw.rect(self.screen, (45, 35, 25), b_rect, border_radius=6)
                    pygame.draw.rect(self.screen, (190, 140, 55), b_rect, 2, border_radius=6)

                    text = small_font.render(label, True, (255, 255, 255))
                    self.screen.blit(text, text.get_rect(center=b_rect.center))

                    self.clickable_cards.append((b_rect, card, source))

        if (
            self.game_state.current_phase == "action"
            and self.is_human_turn()
            and not player.passed
        ):
            pass_rect = pygame.Rect(area.right - 95, area.y + 12, 80, 34)

            pygame.draw.rect(
                self.screen,
                (60, 45, 25),
                pass_rect,
                border_radius=8
            )
            pygame.draw.rect(
                self.screen,
                (190, 140, 55),
                pass_rect,
                2,
                border_radius=8
            )

            text = font.render("PASS", True, (255, 255, 255))
            self.screen.blit(text, text.get_rect(center=pass_rect.center))

            self.clickable_cards.append(
                (pass_rect, None, "hand_pass")
            )
    def draw_game_log_table(self):
        if "Gamelog" not in self.table_layout:
            return

        rect = self.camera.apply_rect(self.table_layout["Gamelog"])

        pygame.draw.rect(self.screen, (18, 22, 26), rect, border_radius=10)
        pygame.draw.rect(self.screen, (120, 120, 160), rect, 2, border_radius=10)

        title_font = pygame.font.SysFont("arial", max(12, int(18 * self.camera.zoom)), bold=True)
        log_font = pygame.font.SysFont("arial", max(10, int(14 * self.camera.zoom)))

        title = title_font.render("Game Log", True, (255, 255, 255))
        self.screen.blit(title, (rect.x + 12, rect.y + 10))

        logs = getattr(self.game_state, "game_log", [])[-6:]

        y = rect.y + 38
        max_width = rect.w - 24

        for line in logs:
            text_line = str(line)

            while len(text_line) > 0:
                cut = len(text_line)

                while cut > 0 and log_font.size(text_line[:cut])[0] > max_width:
                    cut -= 1

                part = text_line[:cut]
                text_line = text_line[cut:]

                text = log_font.render(part, True, (220, 220, 220))
                self.screen.blit(text, (rect.x + 12, y))

                y += int(18 * self.camera.zoom)

                if y > rect.bottom - 18:
                    return
    
    def draw_floating_hand(self):
        return
    

    def draw_turn_banner(self):
        if self.game_state.current_phase != "action":
            return

        current_player = self.game_state.players[self.game_state.current_player_index]
        human = self.game_state.players[0]

        if current_player is human:
            text_value = "YOUR TURN"
            color = (40, 120, 60)
        else:
            text_value = "AI TURN"
            color = (120, 50, 50)

        font = pygame.font.SysFont("arial", 24, bold=True)

        text = font.render(text_value, True, (255, 255, 255))
        rect = pygame.Rect(20, 20, 170, 42)

        pygame.draw.rect(self.screen, color, rect, border_radius=10)
        pygame.draw.rect(self.screen, (240, 220, 160), rect, 2, border_radius=10)

        self.screen.blit(text, text.get_rect(center=rect.center))


    def draw_ai_brain_panel(self):
        if not self.ai_brain_panel_visible:
            return

        ai_move = getattr(
            self.game_state,
            "last_ai_move",
            None,
        )

        sw = self.screen.get_width()
        sh = self.screen.get_height()

        # --------------------------------------------------------
        # PANEL SIZE
        # --------------------------------------------------------

        panel_w = min(
            460,
            max(360, sw // 4),
        )

        panel_h = min(
            520,
            sh - 100,
        )

        panel = pygame.Rect(
            sw - panel_w - 20,
            70,
            panel_w,
            panel_h,
        )

        # Semi-transparent background
        surface = pygame.Surface(
            (panel.w, panel.h),
            pygame.SRCALPHA,
        )

        surface.fill(
            (16, 18, 22, 235)
        )

        self.screen.blit(
            surface,
            panel.topleft,
        )

        pygame.draw.rect(
            self.screen,
            (190, 145, 65),
            panel,
            width=2,
            border_radius=12,
        )

        # --------------------------------------------------------
        # FONTS
        # --------------------------------------------------------

        title_font = pygame.font.SysFont(
            "arial",
            22,
            bold=True,
        )

        section_font = pygame.font.SysFont(
            "arial",
            16,
            bold=True,
        )

        text_font = pygame.font.SysFont(
            "arial",
            14,
        )

        small_font = pygame.font.SysFont(
            "arial",
            13,
        )

        # --------------------------------------------------------
        # TITLE
        # --------------------------------------------------------

        title = title_font.render(
            "AI BRAIN",
            True,
            (255, 215, 110),
        )

        self.screen.blit(
            title,
            (
                panel.x + 18,
                panel.y + 14,
            ),
        )

        hint = small_font.render(
            "Press B to hide",
            True,
            (150, 150, 150),
        )

        self.screen.blit(
            hint,
            (
                panel.right
                - hint.get_width()
                - 15,
                panel.y + 19,
            ),
        )

        pygame.draw.line(
            self.screen,
            (90, 80, 60),
            (
                panel.x + 15,
                panel.y + 48,
            ),
            (
                panel.right - 15,
                panel.y + 48,
            ),
            1,
        )

        y = panel.y + 62

        # --------------------------------------------------------
        # NO DECISION YET
        # --------------------------------------------------------

        if not ai_move:

            waiting = text_font.render(
                "Waiting for the AI's first decision...",
                True,
                (210, 210, 210),
            )

            self.screen.blit(
                waiting,
                (
                    panel.x + 18,
                    y,
                ),
            )

            return

        # --------------------------------------------------------
        # HELPER FOR WRAPPED TEXT
        # --------------------------------------------------------

        def draw_wrapped_text(
            text,
            x,
            y_pos,
            font,
            color=(220, 220, 220),
            max_width=None,
            line_gap=4,
        ):
            if max_width is None:
                max_width = panel.w - 36

            words = str(text).split()

            lines = []
            current_line = ""

            for word in words:

                test_line = (
                    current_line + " " + word
                ).strip()

                if (
                    font.size(test_line)[0]
                    <= max_width
                ):
                    current_line = test_line

                else:
                    if current_line:
                        lines.append(
                            current_line
                        )

                    current_line = word

            if current_line:
                lines.append(
                    current_line
                )

            for line in lines:

                rendered = font.render(
                    line,
                    True,
                    color,
                )

                self.screen.blit(
                    rendered,
                    (
                        x,
                        y_pos,
                    ),
                )

                y_pos += (
                    font.get_height()
                    + line_gap
                )

            return y_pos

        # --------------------------------------------------------
        # GOAL
        # --------------------------------------------------------

        goal = ai_move.get(
            "brain_goal",
            "Unknown",
        )

        label = section_font.render(
            "Goal",
            True,
            (120, 190, 255),
        )

        self.screen.blit(
            label,
            (
                panel.x + 18,
                y,
            ),
        )

        y += 23

        y = draw_wrapped_text(
            goal,
            panel.x + 18,
            y,
            text_font,
        )

        y += 10

        # --------------------------------------------------------
        # PLAN
        # --------------------------------------------------------

        plan = ai_move.get(
            "brain_plan",
            "Unknown",
        )

        label = section_font.render(
            "Plan",
            True,
            (120, 190, 255),
        )

        self.screen.blit(
            label,
            (
                panel.x + 18,
                y,
            ),
        )

        y += 23

        y = draw_wrapped_text(
            plan,
            panel.x + 18,
            y,
            text_font,
        )

        y += 10

        # --------------------------------------------------------
        # STRATEGY
        # --------------------------------------------------------

        strategy = ai_move.get(
            "strategy",
            "Unknown",
        )

        label = section_font.render(
            "Strategy",
            True,
            (120, 190, 255),
        )

        self.screen.blit(
            label,
            (
                panel.x + 18,
                y,
            ),
        )

        y += 23

        y = draw_wrapped_text(
            str(strategy).title(),
            panel.x + 18,
            y,
            text_font,
        )

        y += 10

        # --------------------------------------------------------
        # DECISION
        # --------------------------------------------------------

        move_type = ai_move.get(
            "type",
            "unknown",
        )

        card = ai_move.get(
            "card_name",
            None,
        )

        if card:
            decision = (
                f"{move_type}: {card}"
            )
        else:
            decision = move_type

        label = section_font.render(
            "Decision",
            True,
            (120, 190, 255),
        )

        self.screen.blit(
            label,
            (
                panel.x + 18,
                y,
            ),
        )

        y += 23

        y = draw_wrapped_text(
            decision,
            panel.x + 18,
            y,
            text_font,
            color=(255, 235, 170),
        )

        y += 4

        score = ai_move.get(
            "score",
            None,
        )

        if score is not None:

            score_text = text_font.render(
                f"Decision score: {score}",
                True,
                (170, 170, 170),
            )

            self.screen.blit(
                score_text,
                (
                    panel.x + 18,
                    y,
                ),
            )

            y += 25

        # --------------------------------------------------------
        # THOUGHTS
        # --------------------------------------------------------

        thoughts = ai_move.get(
            "brain_thoughts",
            [],
        )

        if thoughts:

            label = section_font.render(
                "Thoughts",
                True,
                (120, 190, 255),
            )

            self.screen.blit(
                label,
                (
                    panel.x + 18,
                    y,
                ),
            )

            y += 24

            for thought in thoughts[:5]:

                if y > panel.bottom - 40:
                    break

                y = draw_wrapped_text(
                    "• " + str(thought),
                    panel.x + 18,
                    y,
                    small_font,
                    max_width=(
                        panel.w - 36
                    ),
                    line_gap=3,
                )

                y += 5

        # --------------------------------------------------------
        # REFLECTION
        # --------------------------------------------------------

        reflection = ai_move.get(
            "brain_reflection",
            None,
        )

        if (
            reflection
            and y < panel.bottom - 65
        ):

            y += 5

            label = section_font.render(
                "Reflection",
                True,
                (120, 190, 255),
            )

            self.screen.blit(
                label,
                (
                    panel.x + 18,
                    y,
                ),
            )

            y += 23

            if isinstance(
                reflection,
                dict,
            ):

                reflection_text = (
                    reflection.get(
                        "message"
                    )
                    or reflection.get(
                        "reflection"
                    )
                    or str(reflection)
                )

            else:

                reflection_text = str(
                    reflection
                )

            draw_wrapped_text(
                reflection_text,
                panel.x + 18,
                y,
                small_font,
                max_width=(
                    panel.w - 36
                ),
                color=(
                    190,
                    210,
                    190,
                ),
            )
    def golden_statue_prompt_visible(
        self,
    ) -> bool:
        return bool(
            getattr(
                self.game_state,
                "show_golden_statue_prompt",
                False,
            )
            and getattr(
                self.game_state,
                "pending_golden_statue_player",
                None,
            ) is not None
        )


    def finish_golden_statue_prompt(
        self,
    ) -> None:
        self.game_state.pending_golden_statue_player = None
        self.game_state.show_golden_statue_prompt = False


    def handle_golden_statue_event(
        self,
        event,
    ) -> bool:
        if not self.golden_statue_prompt_visible():
            return False

        if event.type == pygame.KEYDOWN:
            
            if event.key == pygame.K_ESCAPE:
                player = (
                    self.game_state
                    .pending_golden_statue_player
                )

                self.game_state.game_log.append(
                    f"{player.name} chose not to "
                    "use Golden Statue."
                )

                self.finish_golden_statue_prompt()
                return True

        if (
            event.type
            == pygame.MOUSEBUTTONDOWN
            and event.button == 1
        ):
            if self.golden_statue_yes_rect.collidepoint(
                event.pos
            ):
                player = (
                    self.game_state
                    .pending_golden_statue_player
                )

                if can_use_golden_statue(player):
                    if use_golden_statue(player):
                        self.game_state.game_log.append(
                            f"{player.name} spent "
                            "3 Gold with Golden "
                            "Statue for +3 VP."
                        )

                self.finish_golden_statue_prompt()
                return True

            if self.golden_statue_no_rect.collidepoint(
                event.pos
            ):
                player = (
                    self.game_state
                    .pending_golden_statue_player
                )

                self.game_state.game_log.append(
                    f"{player.name} chose not "
                    "to use Golden Statue."
                )

                self.finish_golden_statue_prompt()
                return True

        # Block every other event while open.
        return True
    def handle_event(self, event):
        if event.type == pygame.VIDEORESIZE:
            self.refit_table_to_window()
            return

        if (
            event.type == pygame.KEYDOWN
            and event.key == pygame.K_b
        ):
            self.ai_brain_panel_visible = (
                not self.ai_brain_panel_visible
            )
            return
        if self.golden_statue_prompt_visible():
            self.handle_golden_statue_event(event)
            return
        if self.quantity_selector.visible:
            self.quantity_selector.handle_event(event)
            return
        self.camera.handle_event(event)
        if self.game_state.current_phase == "end":
            return
        if self.phase_banner_active():
            return
        if event.type == pygame.KEYDOWN:

            if event.key in [pygame.K_ESCAPE, pygame.K_BACKSPACE]:
                self.close_all_popups()

      

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                self.mouse_down_pos = event.pos
                self.mouse_dragged = False

        if event.type == pygame.MOUSEMOTION:
            if self.mouse_down_pos:
                dx = abs(event.pos[0] - self.mouse_down_pos[0])
                dy = abs(event.pos[1] - self.mouse_down_pos[1])
                if dx > 5 or dy > 5:
                    self.mouse_dragged = True

        if event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                if self.mouse_dragged:
                    self.mouse_down_pos = None
                    self.mouse_dragged = False
                    return

                mouse_pos = event.pos
                
                if (
                        self.game_state.current_phase == "action"
                        and not self.is_human_turn()
                    ):
                        return
                if self.essence_icon_panel_active:
                    self.handle_essence_icon_panel_click(mouse_pos)
                    return
                if self.action_panel.active:
                    self.handle_action_panel_click(mouse_pos)
                    return

                if self.zoomed_card:
                    self.handle_zoom_click(mouse_pos)
                    return

                self.handle_card_click(mouse_pos)

                self.mouse_down_pos = None
                self.mouse_dragged = False

    def close_all_popups(self):
        self.essence_icon_panel_active = False
        self.essence_icon_panel_actions = []
        self.essence_icon_panel_buttons = []
        self.zoomed_card = None
        self.zoom_source = None
        self.zoom_buttons = {}

        self.selected_card = None
        self.selected_source = None

        self.pending_essence_choices = []
        self.selected_power = None
        self.pending_x_value = None
        self.pending_target_choices = {}
        self.pending_additional_tap_target_id = None
        self.target_candidates = []
        if not getattr(self.game_state, "waiting_for_human_item_choice", False):
            self.pass_old_item = None
        self.pending_play_card = None
        self.pending_play_cost = None
        self.pending_discount_choices = []
        self.pending_wild_choices = []
        self.pending_power_wild_choices = []

        self.action_panel.close()

    def close_only_panels(self):
        self.zoomed_card = None
        self.zoom_source = None
        self.zoom_buttons = {}
        self.action_panel.close()


    def open_collect_essence_icon_panel(self, title, message, allowed):
        actions = []

        for essence in allowed:
            essence = essence.lower()
            actions.append((f"collection_gain_{essence}", essence))

        self.open_essence_icon_panel(
            title,
            message,
            actions
        )

     
    def open_discard_choice_wheel(self):
        actions = []

        if len(self.pending_essence_choices) == 0:
            actions.append(("confirm_discard_gold", "gold"))
        else:
            actions.append(("disabled_gold", "gold"))

        for essence in ["elan", "life", "calm", "death"]:
            actions.append((f"choose_{essence}", essence))

        if len(self.pending_essence_choices) == 0:
            message = "Choose 1 gold OR 2 non-gold essences."
        else:
            message = f"Chosen: {', '.join(self.pending_essence_choices)}. Choose one more."

        self.open_essence_icon_panel(
            "Discard Card",
            message,
            actions
        )
    def handle_card_click(self, mouse_pos):
        player = self.game_state.players[0]
        if self.game_state.current_phase in [
            "collect",
            "collect_choice",
            "effect_choice",
            "attack_choice",
            "deck_choice",
        ]:
            return

        if self.game_state.current_phase == "action" and not self.is_human_turn():
            self.game_state.game_log.append("AI turn. Please wait.")
            return
        for rect, card, source in self.clickable_cards:
            if rect and rect.collidepoint(mouse_pos):

                # SETUP: choose mage by clicking mage card
                if source.startswith("setup_mage_"):
                    index = int(source.split("_")[-1])
                    mage_options = getattr(player, "mage_options", [])

                    if 0 <= index < len(mage_options):
                        player.mage = mage_options[index]

                        self.game_state.game_log.append(
                            f"{player.name} chose mage: {self.card_name(player.mage)}"
                        )

                        import random
                        random.shuffle(player.deck_hidden)

                        for _ in range(3):
                            if player.deck_hidden:
                                player.hand.append(player.deck_hidden.pop(0))

                        player.setup_artifacts = []
                        self.action_panel.close()
                        self.setup_panel_opened = False
                        self.game_state.current_phase = "setup"
                        self.game_state.current_setup_step = "choose_human_item"
                        self.game_state.waiting_for_human_item_choice = True

                        self.game_state.game_log.append(
                            f"{player.name} drew 3 cards after mage selection."
                        )

                        self.continue_setup_item_order()

                    return

                # If player already passed, block hand actions
                if player.passed and source.startswith("hand_"):
                    self.game_state.game_log.append(
                        "You already passed. Waiting for AI."
                    )
                    return
              
                if source.startswith("hand_play_"):
                    self.selected_card = card
                    self.selected_source = source
                    self.open_play_panel()
                    return

                if source.startswith("hand_discard_"):
                    self.selected_card = card
                    self.selected_source = source
                    self.pending_essence_choices = []
                    self.open_discard_choice_wheel()
                    return

                if source == "hand_pass":
                    self.open_pass_panel()
                    return


                if source.startswith("item_"):
                    if getattr(self.game_state, "waiting_for_human_item_choice", False):
                        self.selected_card = card
                        self.selected_source = source
                        self.open_choose_item_confirm_panel(card, source)
                        return
                if source.startswith("monument_"):
                    self.selected_card = card
                    self.selected_source = source
                    self.open_buy_monument_panel()
                    return

                if source.startswith("place_"):
                    self.selected_card = card
                    self.selected_source = source
                    self.open_buy_place_panel()
                    return
                

                
                if card is None:
                    return

                self.zoomed_card = card
                self.zoom_source = source
                self.selected_card = card
                self.selected_source = source
                return
    def handle_zoom_click(self, mouse_pos):
        for action_name, rect in self.zoom_buttons.items():
            if not rect.collidepoint(mouse_pos):
                continue

            if action_name == "close":
                self.close_all_popups()

            elif action_name == "buy_monument":
                self.open_buy_monument_panel()

            elif action_name == "buy_place":
                self.open_buy_place_panel()

            elif action_name == "use_power":
                self.open_choose_power_panel()

            break
    def confirm_convert_to_gold_amount(
        self,
        amount: int,
    ) -> None:
        choice = getattr(
            self.game_state,
            "pending_effect_choice",
            None,
        )

        if not choice:
            return

        if choice.get("type") != "convert_to_gold":
            return

        player = choice["player"]
        essence = choice.get("selected_essence")

        if not essence:
            self.game_state.game_log.append(
                "Conversion failed: no essence type selected."
            )
            return

        amount = int(amount)

        available = int(
            player.essence_pool.get(
                essence,
                0,
            )
        )

        if amount < 0 or amount > available:
            self.game_state.game_log.append(
                "Conversion failed: invalid amount."
            )
            return

        player.essence_pool[essence] -= amount
        player.essence_pool["gold"] += amount

        self.game_state.game_log.append(
            f"{player.name} converted "
            f"{amount} {essence} into "
            f"{amount} gold."
        )

        self.game_state.pending_effect_choice = None
        self.game_state.current_phase = "action"
        self.game_state.gui_human_action_done = True

        self.action_panel.close()
        self.quantity_selector.close()


    def cancel_convert_to_gold_amount(
        self,
    ) -> None:
        choice = getattr(
            self.game_state,
            "pending_effect_choice",
            None,
        )

        if choice:
            choice["selected_essence"] = None

        self.quantity_selector.close()
        self.action_panel.close()

        # Return to the essence-type selection.
        self.open_effect_choice_panel()
    def handle_effect_choice(self, action):
        choice = getattr(self.game_state, "pending_effect_choice", None)

        if not choice:
            return

        player = choice["player"]

        if choice["type"] == "gain_wild":
            essence = action.replace("effect_gain_", "")

            if essence not in choice["allowed"]:
                return

            player.essence_pool[essence] += 1
            choice["chosen"].append(essence)

            if len(choice["chosen"]) >= choice["count"]:
                self.game_state.game_log.append(
                    f"{player.name} gained {choice['chosen']}."
                )
                self.game_state.pending_effect_choice = None
                self.game_state.current_phase = "action"
                self.action_panel.close()
            else:
                self.action_panel.close()
                self.open_effect_choice_panel()

            return

        if choice["type"] == "convert_to_gold":
            if action.startswith("effect_convert_type_"):
                essence = action.replace("effect_convert_type_", "")
                choice["selected_essence"] = essence
                self.action_panel.close()
                self.open_effect_choice_panel()
                return

            
            

    def is_human_turn(self):
        game = self.game_state

        if game.current_phase != "action":
            return True

        current_player = game.players[game.current_player_index]
        human = game.players[0]

        return current_player is human
    def handle_action_panel_click(self, mouse_pos):
       
        action = self.action_panel.handle_click(mouse_pos)

        if not action:
            return

        player = self.game_state.players[0]



        if action.startswith("effect_"):
            self.handle_effect_choice(action)
            return

        if action.startswith("deck_source_"):
            self.handle_deck_source_choice(action)
            return

        if action.startswith("deck_order_"):
            self.handle_deck_order_choice(action)
            return
        if action.startswith("attack_"):
            self.attack_resolver.handle_action(action)
            return

        if action.startswith("resolver_"):
            self.action_resolver.handle_action(action)
            return

        if action.startswith("collection_"):
            resolve_collection_action(self.game_state, action)
            self.action_panel.close()
            return
        
        if action.startswith("choose_mage_"):
            index = int(action.split("_")[-1])
            mage_options = getattr(player, "mage_options", [])

            if 0 <= index < len(mage_options):
                player.mage = mage_options[index]
                import random

                random.shuffle(player.deck_hidden)

                for _ in range(3):
                    if player.deck_hidden:
                        player.hand.append(player.deck_hidden.pop(0))

                player.setup_artifacts = []

                self.game_state.current_phase = "setup_choose_item"
                self.game_state.current_setup_step = "choose_human_item"

                self.open_choose_item_panel(setup_mode=True)
                self.game_state.game_log.append(f"{player.name} chose mage: {self.card_name(player.mage)}")
                
                self.game_state.current_setup_step = "choose_human_item"
                self.open_choose_item_panel(setup_mode=True)

            return

        if action == "cancel":
            self.essence_icon_panel_active = False
            self.close_all_popups()
            return
        if action == "disabled_gold":
            return
        if action in ["choose_elan", "choose_life", "choose_calm", "choose_death"]:
            essence = action.replace("choose_", "")

            self.pending_essence_choices.append(essence)

            if len(self.pending_essence_choices) == 2:
                gui_discard_for_essence(
                    self.game_state,
                    player,
                    self.selected_card,
                    choices=self.pending_essence_choices,
                )
                self.close_all_popups()
                return

            self.open_discard_choice_wheel()
            return

        if action.startswith("choose_item_"):
            index = int(action.split("_")[-1])

            try:
                visible_items = getattr(self, "visible_item_choices", [])

                if index < 0 or index >= len(visible_items):
                    self.game_state.game_log.append("Invalid item choice.")
                    return

                chosen_item = visible_items[index]

                if chosen_item not in self.game_state.items_pool:
                    self.game_state.game_log.append(
                        f"{self.card_name(chosen_item)} is no longer available."
                    )
                    return

                real_index = self.game_state.items_pool.index(chosen_item)

                choose_item_for_player(
                    self.game_state,
                    player,
                    real_index,
                    old_item=self.pass_old_item
                )

                self.game_state.game_log.append(
                    f"{player.name} chose item: {self.card_name(player.item)}"
                )

                self.game_state.waiting_for_human_item_choice = False

                is_setup_item_choice = self.game_state.current_phase in [
                    "setup_show_starting_cards",
                    "setup_choose_item",
                ]

                if is_setup_item_choice:
                    if (
                        self.game_state.pending_item_order
                        and self.game_state.pending_item_order[0] == "human"
                    ):
                        self.game_state.pending_item_order.pop(0)

                    self.action_panel.close()
                    self.continue_setup_item_order()
                    return

                self.game_state.gui_human_action_done = True
                self.pass_old_item = None
                self.close_all_popups()
                return

            except Exception as e:
                self.game_state.waiting_for_human_item_choice = False
                self.log_error(e)
                self.close_all_popups()
                return
        if action.startswith("choose_power_"):
            index = int(action.split("_")[-1])
            powers = self.selected_card.definition.raw_data.get("powers", [])

            if 0 <= index < len(powers):
                self.selected_power = powers[index]
                self.action_resolver.start_power(player, self.selected_card, self.selected_power)
            return

        if action.startswith("choose_x_"):
            self.pending_x_value = int(action.split("_")[-1])
            self.start_power_resolution()
            return

        if action.startswith("choose_target_"):
            index = int(action.split("_")[-1])

            if 0 <= index < len(self.target_candidates):
                target_card = self.target_candidates[index]
                self.pending_target_choices["straighten_target"] = self.get_card_id(target_card)

            self.start_power_resolution()
            return

        if action.startswith("choose_additional_tap_"):
            index = int(action.split("_")[-1])

            if 0 <= index < len(self.target_candidates):
                target_card = self.target_candidates[index]
                self.pending_additional_tap_target_id = self.get_card_id(target_card)

            self.start_power_resolution()
            return

        if action == "confirm_play":
            self.action_resolver.start_play_card(player, self.selected_card)
            return

        if action == "confirm_discard_gold":
            gui_discard_for_gold(self.game_state, player, self.selected_card)
            self.close_all_popups()
            return

        if action == "confirm_buy_monument":
            gui_buy_monument(self.game_state, player, self.selected_source)
            self.close_all_popups()
            return

        if action == "confirm_buy_place":
            gui_buy_place(self.game_state, player, self.selected_source)
            self.close_all_popups()
            return
        if action.startswith("play_discount_"):
            essence = action.replace("play_discount_", "")
            self.pending_discount_choices.append(essence)
            self.continue_play_cost_flow()
            return

        if action.startswith("play_wild_"):
            essence = action.replace("play_wild_", "")
            self.pending_wild_choices.append(essence)
            self.continue_play_cost_flow()
            return

        if action == "play_final_confirm":
            self.execute_play_with_choices()
            return
        if action == "confirm_pass":
            self.confirm_pass_and_choose_item()
            return
        if action.startswith("power_wild_"):
            essence = action.replace("power_wild_", "")
            self.pending_power_wild_choices.append(essence)
            self.start_power_resolution()
            return
        
        if action == "confirm_clicked_item":
            player = self.game_state.players[0]

            try:
                if self.selected_card not in self.game_state.items_pool:
                    raise ValueError("Selected item is no longer available.")

                item_index = self.game_state.items_pool.index(self.selected_card)

                choose_item_for_player(
                    self.game_state,
                    player,
                    item_index,
                    old_item=self.pass_old_item
                )

                self.game_state.game_log.append(
                    f"{player.name} chose item: {self.card_name(player.item)}"
                )

                self.pass_old_item = None
                self.game_state.waiting_for_human_item_choice = False

                if self.game_state.current_phase == "setup":
                    if (
                        self.game_state.pending_item_order
                        and self.game_state.pending_item_order[0] == "human"
                    ):
                        self.game_state.pending_item_order.pop(0)

                    self.close_all_popups()
                    self.continue_setup_item_order()
                    return

                self.game_state.gui_human_action_done = True

                # after choosing item from pass, let phase manager continue
                if player.passed:
                    self.game_state.waiting_for_human_item_choice = False

                self.close_all_popups()
                return

            except Exception as e:
                self.log_error(e)
                self.close_all_popups()
                return
    def open_choose_item_confirm_panel(self, card, source):
        self.action_panel.open(
            "Choose Item",
            f"Select {self.card_name(card)}?",
            [
                ("confirm_clicked_item", "Select"),
                ("cancel", "Cancel"),
            ],
        )
    def open_play_panel(self):
        self.action_panel.open(
            "Play Card",
            "Do you want to play this card from your hand?",
            [
                ("confirm_play", "Play Card"),
                ("cancel", "Cancel"),
            ],
        )

    def start_play_cost_flow(self):
        from rules_engine import get_effective_placement_cost

        self.pending_play_card = self.selected_card
        self.pending_play_cost = get_effective_placement_cost(
            self.game_state.players[0],
            self.pending_play_card
        )

        self.pending_discount_choices = []
        self.pending_wild_choices = []

        self.continue_play_cost_flow()


    def continue_play_cost_flow(self):
        if not self.pending_play_card:
            return

        cost = self.pending_play_cost or {}

        if self.needs_more_discount_choices(cost):
            self.open_play_discount_panel(cost)
            return

        if self.needs_more_wild_choices(cost):
            self.open_play_wild_panel(cost)
            return

        self.open_play_final_confirm_panel()


    def get_discount_amount(self, cost):
        discount = cost.get("discount", {})
        return int(discount.get("amount", 0) or 0)


    def needs_more_discount_choices(self, cost):
        discount_amount = self.get_discount_amount(cost)
        return len(self.pending_discount_choices) < discount_amount


    def get_discount_candidates(self, cost):
        essence_cost = cost.get("essence", {})

        remaining = {
            essence: int(essence_cost.get(essence, 0))
            for essence in ["elan", "life", "calm", "death"]
        }

        wild = cost.get("wild")
        wild_count, _ = self.get_wild_count_and_allowed(cost)

        if wild_count > 0:
            remaining["wild"] = wild_count

        for chosen in self.pending_discount_choices:
            if chosen in remaining:
                remaining[chosen] -= 1

        return [
            essence for essence, amount in remaining.items()
            if amount > 0
        ]

    def open_play_discount_panel(self, cost):
        discount_amount = self.get_discount_amount(cost)
        candidates = self.get_discount_candidates(cost)

        actions = []

        for essence in candidates:
            actions.append(
                (
                    f"play_discount_{essence}",
                    f"Discount {essence.title()}"
                )
            )

        actions.append(("cancel", "Cancel"))

        self.action_panel.open(
            "Choose Discount",
            f"Choose discount {len(self.pending_discount_choices) + 1} of {discount_amount}.",
            actions,
        )


    def get_adjusted_cost_after_discount(self, cost):
        essence_cost = cost.get("essence", {})

        adjusted = {
            essence: int(essence_cost.get(essence, 0))
            for essence in ["elan", "life", "calm", "death", "gold"]
        }

        wild_count, allowed = self.get_wild_count_and_allowed(cost)

        adjusted["wild"] = wild_count

        for essence in self.pending_discount_choices:
            if essence in adjusted and adjusted[essence] > 0:
                adjusted[essence] -= 1

        return adjusted


    def get_wild_count_and_allowed(self, cost):
        wild = cost.get("wild")

        if not wild:
            return 0, []

        if isinstance(wild, int):
            return wild, ["elan", "life", "calm", "death", "gold"]

        if isinstance(wild, dict):
            count = wild.get("count", 0)
            allowed = wild.get(
                "allowed",
                ["elan", "life", "calm", "death", "gold"]
            )

            if isinstance(count, int):
                return count, allowed

        return 0, []


    def needs_more_wild_choices(self, cost):
        adjusted = self.get_adjusted_cost_after_discount(cost)
        wild_count = adjusted.get("wild", 0)
        return len(self.pending_wild_choices) < wild_count


    def get_wild_candidates(self, cost):
        player = self.game_state.players[0]

        wild_count, allowed = self.get_wild_count_and_allowed(cost)

        adjusted_cost = self.get_adjusted_cost_after_discount(cost)

        remaining_pool = dict(player.essence_pool)

        for essence, amount in adjusted_cost.items():
            remaining_pool[essence] = remaining_pool.get(essence, 0) - amount

        for chosen in self.pending_wild_choices:
            remaining_pool[chosen] = remaining_pool.get(chosen, 0) - 1

        candidates = []

        for essence in allowed:
            if remaining_pool.get(essence, 0) > 0:
                candidates.append(essence)

        return candidates


    def open_play_wild_panel(self, cost):
        adjusted = self.get_adjusted_cost_after_discount(cost)
        wild_count = adjusted.get("wild", 0)

        candidates = self.get_wild_candidates(cost)

        actions = []

        for essence in candidates:
            actions.append(
                (
                    f"play_wild_{essence}",
                    f"Pay {essence.title()}"
                )
            )

        actions.append(("cancel", "Cancel"))

        self.action_panel.open(
            "Choose Wild Payment",
            f"Choose wild payment {len(self.pending_wild_choices) + 1} of {wild_count}.",
            actions,
        )


    def open_play_final_confirm_panel(self):
        discount_text = (
            ", ".join(self.pending_discount_choices)
            if self.pending_discount_choices
            else "None"
        )

        wild_text = (
            ", ".join(self.pending_wild_choices)
            if self.pending_wild_choices
            else "None"
        )

        self.action_panel.open(
            "Confirm Play",
            f"Discount: {discount_text} | Wild payment: {wild_text}",
            [
                ("play_final_confirm", "Play Card"),
                ("cancel", "Cancel"),
            ],
        )


    def execute_play_with_choices(self):
        player = self.game_state.players[0]

        try:
            from rules_engine import play_card_from_hand

            card_id = self.get_card_id(self.pending_play_card)

            play_card_from_hand(
                self.game_state,
                player,
                card_id,
                wild_choices=self.pending_wild_choices,
                discount_choices=self.pending_discount_choices,
            )

            self.game_state.gui_human_action_done = True

            self.game_state.game_log.append(
                f"{player.name} played {self.card_name(self.pending_play_card)}."
            )

        except Exception as e:
            self.log_error(e)

        self.pending_play_card = None
        self.pending_play_cost = None
        self.pending_discount_choices = []
        self.pending_wild_choices = []

        self.close_all_popups()

    def open_discard_gold_panel(self):
        self.action_panel.open(
            "Discard Card",
            "Discard this card to gain 1 gold?",
            [
                ("confirm_discard_gold", "Discard for Gold"),
                ("cancel", "Cancel"),
            ],
        )

    def open_discard_essence_panel(self):
        self.pending_essence_choices = []

        self.action_panel.open(
            "Choose 2 Essences",
            "Choose exactly 2 non-gold essences.",
            [
                ("choose_elan", "Elan"),
                ("choose_life", "Life"),
                ("choose_calm", "Calm"),
                ("choose_death", "Death"),
                ("cancel", "Cancel"),
            ],
        )

    def open_buy_monument_panel(self):
        self.action_panel.open(
            "Buy Monument",
            "Claim this monument for 4 gold?",
            [
                ("confirm_buy_monument", "Buy Monument"),
                ("cancel", "Cancel"),
            ],
        )

    def open_buy_place_panel(self):
        self.action_panel.open(
            "Buy Place of Power",
            "Buy this Place of Power?",
            [
                ("confirm_buy_place", "Buy Place"),
                ("cancel", "Cancel"),
            ],
        )

    def open_pass_panel(self):
        self.action_panel.open(
            "Pass",
            "Pass, draw 1 card, and choose a new item?",
            [
                ("confirm_pass", "Pass"),
                ("cancel", "Cancel"),
            ],
        )

    def confirm_pass_and_choose_item(self):
        player = self.game_state.players[0]

        try:
            state_before = snapshot_game(self.game_state)
            self.pass_old_item = player.item

            if self.pass_old_item:
                self.pass_old_item.tapped = False

            player.item = None

            pass_turn(self.game_state, player)
            record_move(
                game_record=self.game_state.game_record,
                game=self.game_state,
                state_before=state_before,
                player_name=player.name,
                move_type="pass",
                description=f"{player.name} passed.",
                card_name=self.card_name(self.pass_old_item) if self.pass_old_item else None,
            )

            self.game_state.waiting_for_human_item_choice = True
            self.game_state.game_log.append("Choose a new item by clicking one from the market.")
            self.close_all_popups()

        except Exception as e:
            self.log_error(e)
            self.close_all_popups()

    def open_choose_mage_panel(self):
        player = self.game_state.players[0]
        mage_options = getattr(player, "mage_options", [])

        actions = []

        for index, mage in enumerate(mage_options):
            actions.append((f"choose_mage_{index}", self.card_name(mage)))

        if not actions:
            self.game_state.current_setup_step = "choose_human_item"
            self.open_choose_item_panel(setup_mode=True)
            return

        self.action_panel.open(
            "Choose Mage",
            "Choose one mage to start the game.",
            actions,
        )

    def open_choose_item_panel(self, setup_mode=False):
        self.visible_item_choices = list(self.game_state.items_pool[:8])

        actions = []

        for index, item in enumerate(self.visible_item_choices):
            actions.append((f"choose_item_{index}", self.card_name(item)))

        if not actions:
            if setup_mode:
                self.game_state.current_setup_step = "setup_done"
            else:
                self.game_state.gui_human_action_done = True

            self.close_all_popups()
            return

        title = "Choose Starting Item" if setup_mode else "Choose New Item"
        message = "Select your item." if setup_mode else "Select one item after passing."

        self.action_panel.open(title, message, actions)
    def open_choose_power_panel(self):
        if not self.selected_card:
            return

        powers = self.selected_card.definition.raw_data.get("powers", [])

        if not powers:
            self.game_state.game_log.append(f"{self.card_name(self.selected_card)} has no power.")
            self.close_all_popups()
            return

        actions = []

        for index, power in enumerate(powers):
            power_index = power.get("power_index", index)
            actions.append((f"choose_power_{index}", f"Power {power_index}"))

        actions.append(("cancel", "Cancel"))

        self.action_panel.open(
            "Choose Power",
            f"Choose power on {self.card_name(self.selected_card)}.",
            actions,
        )

    def start_power_resolution(self):
        if not self.selected_card or not self.selected_power:
            return

        if self.power_needs_x_value() and self.pending_x_value is None:
            self.open_x_value_panel()
            return
        if self.power_needs_wild_payment():
            self.open_power_wild_panel()
            return

        if self.power_needs_straighten_target() and "straighten_target" not in self.pending_target_choices:
            self.open_straighten_target_panel()
            return

        if self.power_needs_additional_tap_target() and self.pending_additional_tap_target_id is None:
            self.open_additional_tap_target_panel()
            return

        self.execute_selected_power()

    def power_needs_x_value(self):
        power = self.selected_power

        cost = power.get("cost", {})
        wild = cost.get("wild")

        if isinstance(wild, dict) and wild.get("count") in ["X", "X_plus_2"]:
            return True

        for effect in power.get("effect", []):
            if "gain_wild" in effect:
                count = effect["gain_wild"].get("count")
                if count in ["X", "X_plus_2"]:
                    return True

        return False
    def draw_game_over_screen(self):
        self.screen.fill((20, 20, 25))

        font = pygame.font.SysFont("arial", 54, bold=True)
        small_font = pygame.font.SysFont("arial", 28)

        winner = getattr(self.game_state, "winner", "Unknown")

        title = font.render("GAME OVER", True, (255, 255, 255))
        winner_text = small_font.render(
            f"Winner: {winner}",
            True,
            (255, 255, 255)
        )

        title_rect = title.get_rect(
            center=(self.screen.get_width() // 2, self.screen.get_height() // 2 - 60)
        )

        winner_rect = winner_text.get_rect(
            center=(self.screen.get_width() // 2, self.screen.get_height() // 2 + 10)
        )

        self.screen.blit(title, title_rect)
        self.screen.blit(winner_text, winner_rect)

        logs = getattr(self.game_state, "game_log", [])[-8:]

        y = self.screen.get_height() // 2 + 70

        for line in logs:
            log_text = pygame.font.SysFont("arial", 18).render(
                line[:90],
                True,
                (220, 220, 220)
            )
            self.screen.blit(log_text, (80, y))
            y += 26
    def open_x_value_panel(self):
        actions = [
            ("choose_x_1", "X = 1"),
            ("choose_x_2", "X = 2"),
            ("choose_x_3", "X = 3"),
            ("choose_x_4", "X = 4"),
            ("choose_x_5", "X = 5"),
            ("cancel", "Cancel"),
        ]

        self.action_panel.open(
            "Choose X Value",
            "Choose X for this power.",
            actions,
        )

    def power_needs_straighten_target(self):
        for effect in self.selected_power.get("effect", []):
            if "straighten_target" in effect:
                return True
        return False

    def power_needs_additional_tap_target(self):
        cost = self.selected_power.get("cost", {})
        return bool(cost.get("tap_additional_target"))

    def get_controlled_cards(self, player):
        cards = []

        if player.mage:
            cards.append(player.mage)

        if player.item:
            cards.append(player.item)

        cards.extend(player.played)
        cards.extend(player.monuments)
        cards.extend(player.places)

        return cards

    def matches_restriction(self, card, restriction):
        if not restriction:
            return True

        card_type = (
            getattr(card.definition, "card_type", None)
            or card.definition.raw_data.get("type")
        )

        tags = card.definition.raw_data.get("tags", [])

        if "type" in restriction and card_type != restriction["type"]:
            return False

        if "has_tag" in restriction and restriction["has_tag"] not in tags:
            return False

        if "not_type" in restriction and card_type == restriction["not_type"]:
            return False

        return True

    def open_straighten_target_panel(self):
        player = self.game_state.players[0]

        restriction = None

        for effect in self.selected_power.get("effect", []):
            if "straighten_target" in effect:
                restriction = effect["straighten_target"].get("restriction")

        self.target_candidates = [
            card for card in self.get_controlled_cards(player)
            if card.tapped and self.matches_restriction(card, restriction)
        ]

        if not self.target_candidates:
            self.game_state.game_log.append("No valid tapped target to straighten.")
            self.close_all_popups()
            return

        actions = []

        for index, card in enumerate(self.target_candidates):
            actions.append((f"choose_target_{index}", self.card_name(card)))

        actions.append(("cancel", "Cancel"))

        self.action_panel.open(
            "Choose Target",
            "Choose card to straighten.",
            actions,
        )

    def open_additional_tap_target_panel(self):
        player = self.game_state.players[0]

        cost = self.selected_power.get("cost", {})
        payload = cost.get("tap_additional_target", {})
        restriction = payload.get("restriction")

        self.target_candidates = [
            card for card in self.get_controlled_cards(player)
            if not card.tapped
            and card is not self.selected_card
            and self.matches_restriction(card, restriction)
        ]

        if not self.target_candidates:
            self.game_state.game_log.append("No valid card available to tap.")
            self.close_all_popups()
            return

        actions = []

        for index, card in enumerate(self.target_candidates):
            actions.append((f"choose_additional_tap_{index}", self.card_name(card)))

        actions.append(("cancel", "Cancel"))

        self.action_panel.open(
            "Choose Card To Tap",
            "This power needs another card to tap.",
            actions,
        )
    def open_collect_choice_panel(self):
        choice = getattr(self.game_state, "pending_collect_choice", None)

        if not choice:
            return

        ctype = choice.get("type")
        card = choice.get("card")

        if ctype == "stored_choice":
            self.action_panel.open(
                "Stored Essence",
                f"{self.card_name(card)} has stored essence.",
                [
                    ("collection_take_stored", "Take To Pool"),
                    ("collection_keep_stored", "Keep On Card"),
                ],
            )

        elif ctype == "vault_choice":
            actions = [
                ("collection_vault_take_gold", "Take Gold")
            ]

            for essence in ["elan", "life", "calm", "death"]:
                actions.append(
                    (
                        f"collection_gain_{essence}",
                        essence.title()
                    )
                )

            self.action_panel.open(
                "Vault Collection",
                "Take stored gold OR leave it and gain non-gold essence.",
                actions,
            )

        elif ctype == "windup_choice":
            self.action_panel.open(
                "Windup Man",
                "Take stored essence or leave it and add +2 to each stored type.",
                [
                    (
                        "collection_windup_take",
                        "Take Stored Essence"
                    ),
                    (
                        "collection_windup_keep",
                        "Keep And Add +2"
                    ),
                ],
            )

        elif ctype == "gain_wild":
            allowed = (
                choice.get("effect", {})
                .get("gain_wild", {})
                .get("allowed", ["elan", "life", "calm", "death"])
            )

            self.open_collect_essence_icon_panel(
                "Choose Essence",
                "Choose one essence to gain.",
                allowed
            )

        elif ctype == "choose_essence":
            allowed = choice.get(
                "allowed",
                ["elan", "life", "calm", "death"]
            )

            self.open_collect_essence_icon_panel(
                "Choose Essence",
                f"Choose essence from {self.card_name(card)}.",
                allowed
            )
        else:
            self.game_state.game_log.append(
                f"Unknown collection choice type: {ctype}"
            )
    def execute_selected_power(self):
        player = self.game_state.players[0]

        try:
            use_power(
                self.game_state,
                player,
                source_card_id=self.get_card_id(self.selected_card),
                power_index=self.selected_power.get("power_index"),
                wild_choices=self.pending_power_wild_choices,
                x_value=self.pending_x_value,
                target_choices=self.pending_target_choices,
                additional_tap_target_id=self.pending_additional_tap_target_id,
            )

            self.game_state.gui_human_action_done = True

            self.game_state.game_log.append(
                f"{player.name} used power on {self.card_name(self.selected_card)}."
            )

           

        except Exception as e:
            self.log_error(e)

        self.close_all_popups()
    def open_effect_choice_panel(self):
        choice = getattr(self.game_state, "pending_effect_choice", None)

        if not choice:
            return

        if choice["type"] == "gain_wild":
            allowed = choice["allowed"]
            count = choice["count"]
            chosen = choice["chosen"]

            actions = []

            for essence in allowed:
                actions.append((f"effect_gain_{essence}", essence.title()))

            self.action_panel.open(
                "Choose Essence",
                f"Choose essence {len(chosen) + 1} of {count}.",
                actions,
            )

        elif choice["type"] == "convert_to_gold":
            player = choice["player"]
            allowed = choice["allowed"]

            if choice["selected_essence"] is None:
                actions = []

                for essence in allowed:
                    if player.essence_pool.get(essence, 0) > 0:
                        actions.append((f"effect_convert_type_{essence}", essence.title()))

                self.action_panel.open(
                    "Convert To Gold",
                    "Choose one essence type to convert.",
                    actions,
                )
            else:
                essence = choice["selected_essence"]

                max_amount = int(
                    player.essence_pool.get(
                        essence,
                        0,
                    )
                )

                self.action_panel.close()

                self.quantity_selector.open(
                    title="Convert To Gold",
                    message=(
                        f"How much {essence.title()} "
                        "do you want to convert?"
                    ),
                    minimum=0,
                    maximum=max_amount,
                    initial=0,
                    step=1,
                    on_confirm=(
                        self.confirm_convert_to_gold_amount
                    ),
                    on_cancel=(
                        self.cancel_convert_to_gold_amount
                    ),
                )

    def draw_golden_statue_prompt(
        self,
    ) -> None:
        if not self.golden_statue_prompt_visible():
            return

        player = (
            self.game_state
            .pending_golden_statue_player
        )

        screen_rect = self.screen.get_rect()

        overlay = pygame.Surface(
            screen_rect.size,
            pygame.SRCALPHA,
        )

        overlay.fill((0, 0, 0, 175))

        self.screen.blit(
            overlay,
            (0, 0),
        )

        panel = pygame.Rect(
            0,
            0,
            600,
            320,
        )

        panel.center = screen_rect.center

        pygame.draw.rect(
            self.screen,
            (31, 29, 24),
            panel,
            border_radius=14,
        )

        pygame.draw.rect(
            self.screen,
            (230, 190, 75),
            panel,
            width=3,
            border_radius=14,
        )

        title_font = pygame.font.SysFont(
            "arial",
            30,
            bold=True,
        )

        text_font = pygame.font.SysFont(
            "arial",
            20,
        )

        button_font = pygame.font.SysFont(
            "arial",
            18,
            bold=True,
        )

        title = title_font.render(
            "Golden Statue",
            True,
            (255, 220, 105),
        )

        message = text_font.render(
            "Spend 3 Gold to gain "
            "+3 VP for this victory check?",
            True,
            (245, 245, 245),
        )

        current_gold = int(
            player.essence_pool.get(
                "gold",
                0,
            )
        )

        current_vp = int(
            getattr(
                player,
                "victory_points",
                0,
            )
        )

        status = text_font.render(
            f"Current VP: {current_vp}   "
            f"Gold: {current_gold}   "
            f"Possible VP: {current_vp + 3}",
            True,
            (210, 210, 210),
        )

        self.screen.blit(
            title,
            title.get_rect(
                center=(
                    panel.centerx,
                    panel.y + 55,
                )
            ),
        )

        self.screen.blit(
            message,
            message.get_rect(
                center=(
                    panel.centerx,
                    panel.y + 120,
                )
            ),
        )

        self.screen.blit(
            status,
            status.get_rect(
                center=(
                    panel.centerx,
                    panel.y + 165,
                )
            ),
        )

        self.golden_statue_yes_rect = pygame.Rect(
            0,
            0,
            200,
            58,
        )

        self.golden_statue_no_rect = pygame.Rect(
            0,
            0,
            160,
            58,
        )

        self.golden_statue_yes_rect.center = (
            panel.centerx - 120,
            panel.bottom - 70,
        )

        self.golden_statue_no_rect.center = (
            panel.centerx + 120,
            panel.bottom - 70,
        )

        buttons = [
            (
                self.golden_statue_yes_rect,
                "SPEND 3 GOLD",
            ),
            (
                self.golden_statue_no_rect,
                "SKIP",
            ),
        ]

        for rect, label in buttons:
            pygame.draw.rect(
                self.screen,
                (65, 57, 38),
                rect,
                border_radius=9,
            )

            pygame.draw.rect(
                self.screen,
                (235, 205, 110),
                rect,
                width=2,
                border_radius=9,
            )

            text = button_font.render(
                label,
                True,
                (255, 255, 255),
            )

            self.screen.blit(
                text,
                text.get_rect(
                    center=rect.center
                ),
            )
    def draw(self):
        if self.game_state.current_phase == "end":
            self.draw_game_over_screen()
            return
        
        if self.game_state.current_phase == "effect_choice":
            if (
                not self.action_panel.active
                and not self.essence_icon_panel_active
                and not self.quantity_selector.visible
            ):
                self.open_effect_choice_panel()

        if self.game_state.current_phase == "collect_choice":
            if (
                not self.action_panel.active
                and not self.essence_icon_panel_active
            ):
                self.open_collect_choice_panel()
        if self.game_state.current_phase == "deck_choice":
            if not self.action_panel.active:
                self.open_deck_choice_panel()
        if self.game_state.current_phase == "attack_choice":
            pending = getattr(self.game_state, "pending_attack", None)

            if pending and not self.action_panel.active:
                self.attack_resolver.start_attack(
                    pending["attacker"],
                    pending["defender"],
                    pending["amount"],
                    source_card=pending.get("source_card"),
                    dragon_ignore_cost=pending.get("dragon_ignore_cost"),
                )

                self.game_state.pending_attack = None
        
          


        self.clickable_cards = []

        if self.current_screen == "table":
            self.draw_table_screen()

        elif self.current_screen == "board":
            self.clickable_cards = self.board.draw(
                self.screen,
                self.game_state,
            )

        elif self.current_screen == "player_board":
            player = self.game_state.players[0]
            self.clickable_cards = self.player_area.draw_player_board(
                self.screen,
                player,
                self.game_state
            )

        elif self.current_screen == "ai_board":
            ai_player = self.game_state.players[1]
            self.clickable_cards = self.ai_area.draw_ai_board(
                self.screen,
                ai_player,
            )

        if self.zoomed_card:
            self.zoom_buttons = self.zoom_viewer.draw(
                self.screen,
                self.zoomed_card,
                self.zoom_source,
            )

        # AI brain is fixed to screen and does not
        # move when the table camera zooms/pans.
        self.draw_ai_brain_panel()

        self.action_panel.draw(self.screen)
        self.draw_essence_icon_panel()
        self.draw_turn_banner()
        self.draw_phase_banner()

        self.quantity_selector.draw()
        self.draw_golden_statue_prompt()


    def open_deck_choice_panel(self):
        choice = getattr(self.game_state, "pending_deck_choice", None)

        if not choice:
            return

        ctype = choice.get("type")

        if ctype == "choose_deck_source":
            self.action_panel.open(
                "Choose Deck",
                "Choose which deck to look at.",
                [
                    ("deck_source_your_deck", "Your Deck"),
                    ("deck_source_monument_deck", "Monument Deck"),
                ],
            )

        elif ctype == "reorder_top_cards":
            cards = choice.get("cards", [])
            selected_order = choice.get("selected_order", [])

            actions = []

            for index, card in enumerate(cards):
                if index not in selected_order:
                    actions.append(
                        (
                            f"deck_order_{index}",
                            self.card_name(card)
                        )
                    )

            self.action_panel.open(
                "Reorder Cards",
                f"Choose card {len(selected_order) + 1} of {len(cards)} to place on top.",
                actions,
            )





    def handle_deck_source_choice(self, action):
        choice = getattr(self.game_state, "pending_deck_choice", None)

        if not choice:
            return

        if action == "deck_source_your_deck":
            deck_source = "your_deck"
        else:
            deck_source = "monument_deck"

        from effect_engine import get_deck_list, card_name

        player = choice["player"]
        source_card = choice["source_card"]
        payload = choice["payload"]

        count = int(payload.get("count", 1))
        from effect_engine import prepare_deck_for_look

        deck = prepare_deck_for_look(
            self.game_state,
            player,
            deck_source,
            count
        )

        looked = deck[:count]
        self.game_state.current_look_context = {
            "player_name": player.name,
            "source_card_id": self.get_card_id(source_card),
            "deck_source": deck_source,
            "cards": looked,
        }

        self.game_state.game_log.append(
            f"{player.name} looked at top {len(looked)} card(s) from {deck_source}."
        )

        self.game_state.pending_deck_choice = None
        self.action_panel.close()

        # Now immediately ask reorder
        self.game_state.pending_deck_choice = {
            "type": "reorder_top_cards",
            "player": player,
            "source_card": source_card,
            "payload": payload,
            "context": self.game_state.current_look_context,
            "cards": looked,
            "selected_order": [],
        }
        self.game_state.current_phase = "deck_choice"


    def handle_deck_order_choice(self, action):
        choice = getattr(self.game_state, "pending_deck_choice", None)

        if not choice:
            return

        index = int(action.replace("deck_order_", ""))
        selected_order = choice["selected_order"]

        if index not in selected_order:
            selected_order.append(index)

        cards = choice["cards"]

        if len(selected_order) < len(cards):
            self.action_panel.close()
            self.open_deck_choice_panel()
            return

        reordered = [cards[i] for i in selected_order]
        context = choice["context"]
        context["cards"] = reordered

        from effect_engine import get_deck_list

        deck_source = context.get("deck_source", "your_deck")
        player = choice["player"]
        deck = get_deck_list(self.game_state, player, deck_source)

        for card in cards:
            if card in deck:
                deck.remove(card)

        for card in reversed(reordered):
            deck.insert(0, card)

        self.game_state.current_look_context = None
        self.game_state.pending_deck_choice = None
        self.game_state.current_phase = "action"
        self.action_panel.close()

        self.game_state.game_log.append(
            f"{player.name} reordered top {len(cards)} card(s)."
        )