# ui/quantity_selector.py

from __future__ import annotations

from collections.abc import Callable

import pygame


class QuantitySelector:
    """
    Reusable modal for choosing a number.

    Example:
        selector.open(
            title="Convert To Gold",
            message="How much Elan do you want to convert?",
            minimum=0,
            maximum=22,
            initial=0,
            on_confirm=handle_result,
        )
    """

    def __init__(
        self,
        screen: pygame.Surface,
        width: int = 520,
        height: int = 330,
    ) -> None:
        self.screen = screen
        self.width = width
        self.height = height

        self.visible = False
        self.minimum = 0
        self.maximum = 0
        self.value = 0
        self.step = 1

        self.title = "Choose Amount"
        self.message = ""

        self.on_confirm: Callable[[int], None] | None = None
        self.on_cancel: Callable[[], None] | None = None

        self.font_title = pygame.font.SysFont(
            "arial",
            28,
            bold=True,
        )
        self.font_message = pygame.font.SysFont(
            "arial",
            19,
        )
        self.font_value = pygame.font.SysFont(
            "arial",
            48,
            bold=True,
        )
        self.font_button = pygame.font.SysFont(
            "arial",
            21,
            bold=True,
        )

        self.panel_rect = pygame.Rect(0, 0, width, height)
        self.minus_rect = pygame.Rect(0, 0, 80, 65)
        self.plus_rect = pygame.Rect(0, 0, 80, 65)
        self.confirm_rect = pygame.Rect(0, 0, 150, 52)
        self.cancel_rect = pygame.Rect(0, 0, 150, 52)

        self._layout()

    def _layout(self) -> None:
        screen_rect = self.screen.get_rect()

        self.panel_rect = pygame.Rect(
            screen_rect.centerx - self.width // 2,
            screen_rect.centery - self.height // 2,
            self.width,
            self.height,
        )

        value_y = self.panel_rect.y + 150

        self.minus_rect.center = (
            self.panel_rect.centerx - 135,
            value_y,
        )

        self.plus_rect.center = (
            self.panel_rect.centerx + 135,
            value_y,
        )

        button_y = self.panel_rect.bottom - 55

        self.confirm_rect.center = (
            self.panel_rect.centerx - 90,
            button_y,
        )

        self.cancel_rect.center = (
            self.panel_rect.centerx + 90,
            button_y,
        )

    def update_screen(
        self,
        screen: pygame.Surface,
    ) -> None:
        """Call this after resizing the game window."""
        self.screen = screen
        self._layout()

    def open(
        self,
        *,
        title: str,
        message: str,
        minimum: int,
        maximum: int,
        initial: int = 0,
        step: int = 1,
        on_confirm: Callable[[int], None] | None = None,
        on_cancel: Callable[[], None] | None = None,
    ) -> None:
        minimum = int(minimum)
        maximum = int(maximum)

        if maximum < minimum:
            raise ValueError(
                "QuantitySelector maximum cannot be below minimum."
            )

        self.title = title
        self.message = message

        self.minimum = minimum
        self.maximum = maximum
        self.step = max(1, int(step))

        self.value = max(
            minimum,
            min(int(initial), maximum),
        )

        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.visible = True

        self._layout()

    def close(self) -> None:
        self.visible = False
        self.on_confirm = None
        self.on_cancel = None

    def increase(self) -> None:
        self.value = min(
            self.maximum,
            self.value + self.step,
        )

    def decrease(self) -> None:
        self.value = max(
            self.minimum,
            self.value - self.step,
        )

    def confirm(self) -> None:
        callback = self.on_confirm
        selected_value = self.value

        self.close()

        if callback:
            callback(selected_value)

    def cancel(self) -> None:
        callback = self.on_cancel

        self.close()

        if callback:
            callback()

    def handle_event(
        self,
        event: pygame.event.Event,
    ) -> bool:
        """
        Returns True when the selector consumed the event.
        """

        if not self.visible:
            return False

        if event.type == pygame.KEYDOWN:
            if event.key in (
                pygame.K_LEFT,
                pygame.K_DOWN,
                pygame.K_MINUS,
                pygame.K_KP_MINUS,
            ):
                self.decrease()
                return True

            if event.key in (
                pygame.K_RIGHT,
                pygame.K_UP,
                pygame.K_PLUS,
                pygame.K_EQUALS,
                pygame.K_KP_PLUS,
            ):
                self.increase()
                return True

            if event.key in (
                pygame.K_RETURN,
                pygame.K_KP_ENTER,
            ):
                self.confirm()
                return True

            if event.key == pygame.K_ESCAPE:
                self.cancel()
                return True

        if (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
        ):
            mouse_pos = event.pos

            if self.minus_rect.collidepoint(mouse_pos):
                self.decrease()
                return True

            if self.plus_rect.collidepoint(mouse_pos):
                self.increase()
                return True

            if self.confirm_rect.collidepoint(mouse_pos):
                self.confirm()
                return True

            if self.cancel_rect.collidepoint(mouse_pos):
                self.cancel()
                return True

            # Consume all clicks while modal is open.
            return True

        return True

    def _draw_button(
        self,
        rect: pygame.Rect,
        text: str,
        enabled: bool = True,
    ) -> None:
        fill = (
            (66, 66, 72)
            if enabled
            else (42, 42, 46)
        )

        border = (
            (225, 225, 225)
            if enabled
            else (105, 105, 110)
        )

        pygame.draw.rect(
            self.screen,
            fill,
            rect,
            border_radius=8,
        )

        pygame.draw.rect(
            self.screen,
            border,
            rect,
            width=2,
            border_radius=8,
        )

        label = self.font_button.render(
            text,
            True,
            border,
        )

        self.screen.blit(
            label,
            label.get_rect(center=rect.center),
        )

    def draw(self) -> None:
        if not self.visible:
            return

        self._layout()

        # Dark transparent overlay.
        overlay = pygame.Surface(
            self.screen.get_size(),
            pygame.SRCALPHA,
        )
        overlay.fill((0, 0, 0, 155))
        self.screen.blit(overlay, (0, 0))

        # Main panel.
        pygame.draw.rect(
            self.screen,
            (31, 31, 38),
            self.panel_rect,
            border_radius=12,
        )

        pygame.draw.rect(
            self.screen,
            (230, 230, 235),
            self.panel_rect,
            width=2,
            border_radius=12,
        )

        title_surface = self.font_title.render(
            self.title,
            True,
            (245, 245, 248),
        )

        self.screen.blit(
            title_surface,
            (
                self.panel_rect.x + 28,
                self.panel_rect.y + 24,
            ),
        )

        message_surface = self.font_message.render(
            self.message,
            True,
            (205, 205, 212),
        )

        self.screen.blit(
            message_surface,
            (
                self.panel_rect.x + 28,
                self.panel_rect.y + 75,
            ),
        )

        # Quantity value.
        value_surface = self.font_value.render(
            str(self.value),
            True,
            (250, 215, 105),
        )

        self.screen.blit(
            value_surface,
            value_surface.get_rect(
                center=(
                    self.panel_rect.centerx,
                    self.panel_rect.y + 150,
                )
            ),
        )

        self._draw_button(
            self.minus_rect,
            "−",
            enabled=self.value > self.minimum,
        )

        self._draw_button(
            self.plus_rect,
            "+",
            enabled=self.value < self.maximum,
        )

        range_surface = self.font_message.render(
            f"Minimum: {self.minimum}     Maximum: {self.maximum}",
            True,
            (170, 170, 178),
        )

        self.screen.blit(
            range_surface,
            range_surface.get_rect(
                center=(
                    self.panel_rect.centerx,
                    self.panel_rect.y + 205,
                )
            ),
        )

        self._draw_button(
            self.confirm_rect,
            "CONFIRM",
        )

        self._draw_button(
            self.cancel_rect,
            "CANCEL",
        )