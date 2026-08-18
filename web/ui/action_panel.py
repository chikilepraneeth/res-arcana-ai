import pygame


class ActionPanel:
    def __init__(self):
        self.font = pygame.font.SysFont("arial", 20)
        self.small_font = pygame.font.SysFont("arial", 15)

        self.active = False
        self.title = ""
        self.message = ""
        self.buttons = {}

    def open(self, title, message, actions):
        """
        actions example:
        [
            ("play", "Play Card"),
            ("discard_gold", "Discard for Gold"),
            ("close", "Close"),
        ]
        """
        self.active = True
        self.title = title
        self.message = message
        self.buttons = {}
        self.actions = actions

    def close(self):
        self.active = False
        self.title = ""
        self.message = ""
        self.buttons = {}

    def draw_button(self, screen, text, rect):
        pygame.draw.rect(screen, (65, 65, 65), rect)
        pygame.draw.rect(screen, (220, 220, 220), rect, 2)

        label = self.small_font.render(text, True, (255, 255, 255))
        label_rect = label.get_rect(center=rect.center)
        screen.blit(label, label_rect)

    def draw(self, screen):
        if not self.active:
            return {}

        sw = screen.get_width()
        sh = screen.get_height()

        panel_w = 520
        panel_h = 300
        x = (sw // 2) - (panel_w // 2)
        y = (sh // 2) - (panel_h // 2)

        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 130))
        screen.blit(overlay, (0, 0))

        pygame.draw.rect(screen, (35, 35, 40), (x, y, panel_w, panel_h))
        pygame.draw.rect(screen, (230, 230, 230), (x, y, panel_w, panel_h), 2)

        title_surface = self.font.render(self.title, True, (255, 255, 255))
        screen.blit(title_surface, (x + 25, y + 25))

        msg_surface = self.small_font.render(self.message, True, (220, 220, 220))
        screen.blit(msg_surface, (x + 25, y + 65))

        self.buttons = {}

        button_w = 210
        button_h = 42
        start_x = x + 35
        start_y = y + 110
        gap_y = 55

        for i, (action_key, label) in enumerate(self.actions):
            bx = start_x + (i % 2) * 240
            by = start_y + (i // 2) * gap_y

            rect = pygame.Rect(bx, by, button_w, button_h)
            self.draw_button(screen, label, rect)
            self.buttons[action_key] = rect

        return self.buttons

    def handle_click(self, mouse_pos):
        if not self.active:
            return None

        for action_key, rect in self.buttons.items():
            if rect.collidepoint(mouse_pos):
                return action_key

        return None