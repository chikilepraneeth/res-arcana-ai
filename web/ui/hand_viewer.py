import pygame
import textwrap


class HandViewer:
    def __init__(self, card_renderer):
        self.card_renderer = card_renderer
        self.font = pygame.font.SysFont("arial", 22)
        self.small_font = pygame.font.SysFont("arial", 16)
        self.selected_index = 0

    def handle_event(self, event, player):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RIGHT:
                self.next_card(player)
            elif event.key == pygame.K_LEFT:
                self.previous_card(player)

    def next_card(self, player):
        if player.hand:
            self.selected_index = (self.selected_index + 1) % len(player.hand)

    def previous_card(self, player):
        if player.hand:
            self.selected_index = (self.selected_index - 1) % len(player.hand)

    def draw_text(self, screen, text, x, y):
        label = self.font.render(text, True, (255, 255, 255))
        screen.blit(label, (x, y))

    def draw_small_text(self, screen, text, x, y):
        label = self.small_font.render(text, True, (220, 220, 220))
        screen.blit(label, (x, y))

    def draw_button(self, screen, text, rect):
        pygame.draw.rect(screen, (70, 70, 70), rect)
        pygame.draw.rect(screen, (220, 220, 220), rect, 2)

        label = self.small_font.render(text, True, (255, 255, 255))
        label_rect = label.get_rect(center=rect.center)
        screen.blit(label, label_rect)

    def draw_wrapped_log(self, screen, logs, x, y, max_width_chars, line_height, max_y):
        current_y = y

        for log in logs:
            wrapped_lines = textwrap.wrap(log, width=max_width_chars)

            for line in wrapped_lines:
                if current_y + line_height > max_y:
                    return

                self.draw_small_text(screen, line, x, current_y)
                current_y += line_height

            current_y += 6

    def draw_player_hand_in_slot(self, screen, player, slot_pos, slot_size, game=None):
        x, y = slot_pos
        w, h = slot_size

        left_w = int(w * 0.60)
        right_w = w - left_w

        left_x = x
        right_x = x + left_w

        pygame.draw.rect(screen, (120, 120, 120), (x, y, w, h), 2)
        pygame.draw.line(screen, (120, 120, 120), (right_x, y), (right_x, y + h), 2)

        self.draw_text(screen, "Your Hand", left_x + 20, y + 15)
        self.draw_text(screen, "Game Log", right_x + 20, y + 15)

        clickables = []

        if player.hand:
            if self.selected_index >= len(player.hand):
                self.selected_index = 0

            card = player.hand[self.selected_index]

            card_w = 180
            card_h = 255

            card_x = left_x + 25
            card_y = y + 65

            self.card_renderer.draw_card_with_state(
                screen,
                card,
                card_x,
                card_y,
                card_w,
                card_h
            )

            self.draw_small_text(
                screen,
                f"{self.selected_index + 1} / {len(player.hand)}",
                card_x + 70,
                card_y + card_h + 10
            )

            play_rect = pygame.Rect(left_x + 230, y + 85, 150, 38)
            discard_gold_rect = pygame.Rect(left_x + 230, y + 135, 150, 38)
            discard_essence_rect = pygame.Rect(left_x + 230, y + 185, 150, 38)
            pass_rect = pygame.Rect(left_x + 230, y + 250, 150, 42)

            self.draw_button(screen, "Play", play_rect)
            self.draw_button(screen, "Discard Gold", discard_gold_rect)
            self.draw_button(screen, "Discard Essence", discard_essence_rect)
            self.draw_button(screen, "Pass", pass_rect)

            clickables.extend([
                (play_rect, card, f"hand_play_{self.selected_index}"),
                (discard_gold_rect, card, f"hand_discard_gold_{self.selected_index}"),
                (discard_essence_rect, card, f"hand_discard_essence_{self.selected_index}"),
                (pass_rect, card, "hand_pass"),
            ])
        else:
            self.draw_text(screen, "No cards", left_x + 40, y + 100)

            pass_rect = pygame.Rect(left_x + 230, y + 120, 150, 42)
            self.draw_button(screen, "Pass", pass_rect)
            clickables.append((pass_rect, None, "hand_pass"))

        logs = []

        if game and hasattr(game, "game_log"):
            logs = game.game_log[-20:]

        logs = logs[-8:]

        log_x = right_x + 20
        log_y = y + 60
        max_log_y = y + h - 20

        if not logs:
            self.draw_small_text(screen, "No AI actions yet.", log_x, log_y)
        else:
            self.draw_wrapped_log(
                screen,
                logs,
                log_x,
                log_y,
                max_width_chars=32,
                line_height=20,
                max_y=max_log_y
            )

        return clickables

    def draw_ai_hand_count_in_slot(self, screen, ai_player, slot_pos, slot_size):
        x, y = slot_pos
        w, h = slot_size

        pygame.draw.rect(screen, (120, 120, 120), (x, y, w, h), 2)

        self.draw_text(screen, "AI Hand", x + 30, y + 40)
        self.draw_text(screen, f"{len(ai_player.hand)} hidden card(s)", x + 30, y + 90)

        return []