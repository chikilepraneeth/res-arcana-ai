import pygame


class ZoomViewer:
    def __init__(self, card_renderer):
        self.card_renderer = card_renderer
        self.font = pygame.font.SysFont("arial", 24)
        self.small_font = pygame.font.SysFont("arial", 16)

    def draw_text(self, screen, text, x, y, color=(255, 255, 255)):
        label = self.font.render(text, True, color)
        screen.blit(label, (x, y))

    def draw_small_text(self, screen, text, x, y, color=(220, 220, 220)):
        label = self.small_font.render(text, True, color)
        screen.blit(label, (x, y))

    def draw_button(self, screen, text, rect):
        pygame.draw.rect(screen, (70, 70, 70), rect)
        pygame.draw.rect(screen, (220, 220, 220), rect, 2)

        label = self.small_font.render(text, True, (255, 255, 255))
        label_rect = label.get_rect(center=rect.center)
        screen.blit(label, label_rect)

    def get_buttons_for_source(self, source):
        if not source:
            return ["Close"]

        if source.startswith("hand_"):
            return ["Play", "Discard Gold", "Discard Essence", "Close"]

        if source.startswith("open_monument_"):
            return ["Buy Monument", "Close"]

        if source.startswith("place_"):
            return ["Buy Place", "Close"]

        if (
            source.startswith("player_artifact_")
            or source.startswith("player_monument_")
            or source.startswith("player_place_")
            or source == "mage"
            or source == "item"
        ):
            return ["Use Power", "Close"]

        if source.startswith("ai_"):
            return ["Close"]

        return ["Close"]

    def draw(self, screen, card, source=None):
        screen_w = screen.get_width()
        screen_h = screen.get_height()

        overlay = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        card_w = 330
        card_h = 470

        card_x = (screen_w // 2) - (card_w // 2)
        card_y = 60

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
            "Esc / Backspace = Close",
            card_x,
            card_y + card_h + 10
        )

        button_names = self.get_buttons_for_source(source)

        buttons = {}

        button_w = 150
        button_h = 42
        gap = 15

        total_w = (len(button_names) * button_w) + ((len(button_names) - 1) * gap)
        start_x = (screen_w // 2) - (total_w // 2)
        button_y = card_y + card_h + 45

        for i, name in enumerate(button_names):
            rect = pygame.Rect(
                start_x + i * (button_w + gap),
                button_y,
                button_w,
                button_h
            )

            self.draw_button(screen, name, rect)

            key = name.lower().replace(" ", "_")
            buttons[key] = rect

        return buttons