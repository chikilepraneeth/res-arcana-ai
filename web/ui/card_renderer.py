from pathlib import Path
import pygame


CARD_EXTENSIONS = [".png", ".jpg", ".jpeg", ".webp"]


class CardRenderer:
    def __init__(self, assets_dir, card_size=(120, 170)):
        self.assets_dir = Path(assets_dir)
        self.cards_dir = self.assets_dir / "cards"
        self.card_size = card_size

        # Cache original images, not resized images.
        # This allows the same card to be drawn in different slot sizes.
        self.image_cache = {}

    def get_card_id(self, card):
        return (
            getattr(card.definition, "card_id", None)
            or card.definition.raw_data.get("id")
        )

    def get_card_name(self, card):
        return (
            getattr(card.definition, "name", None)
            or card.definition.raw_data.get("name_en")
            or self.get_card_id(card)
        )

    def find_card_image_path(self, card_id):
        for ext in CARD_EXTENSIONS:
            path = self.cards_dir / f"{card_id}{ext}"
            if path.exists():
                return path

        return None

    def load_card_image(self, card):
        """
        Loads original image only.
        Scaling happens in draw_card().
        """
        card_id = self.get_card_id(card)

        if card_id in self.image_cache:
            return self.image_cache[card_id]

        image_path = self.find_card_image_path(card_id)

        if image_path is None:
            image = self.create_missing_card_image(card, self.card_size)
        else:
            try:
                image = pygame.image.load(str(image_path)).convert_alpha()
            except Exception:
                image = self.create_missing_card_image(card, self.card_size)

        self.image_cache[card_id] = image
        return image

    def create_missing_card_image(self, card, size=None):
        if size is None:
            size = self.card_size

        surface = pygame.Surface(size, pygame.SRCALPHA)
        surface.fill((60, 60, 60))

        font = pygame.font.SysFont("arial", 16)
        small_font = pygame.font.SysFont("arial", 12)

        name = self.get_card_name(card)
        card_id = self.get_card_id(card)

        name_text = font.render(name[:18], True, (255, 255, 255))
        id_text = small_font.render(card_id[:20], True, (220, 220, 220))

        surface.blit(name_text, (8, 20))
        surface.blit(id_text, (8, 55))

        pygame.draw.rect(surface, (200, 200, 200), surface.get_rect(), 2)

        return surface.convert_alpha()

    def draw_card(self, screen, card, x, y, width=None, height=None, tapped=False):
        """
        Draws a card with optional custom size.

        If width/height is passed, card fits that slot.
        If tapped=True, the card is rotated horizontally.
        """
        if width is None or height is None:
            width, height = self.card_size

        image = self.load_card_image(card)

        image = pygame.transform.smoothscale(image, (width, height))

        if tapped:
            image = pygame.transform.rotate(image, -90)

        rect = image.get_rect(topleft=(x, y))
        screen.blit(image, rect)

        return rect

    def draw_card_back(self, screen, x, y, width=None, height=None):
        if width is None or height is None:
            width, height = self.card_size

        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        surface.fill((30, 30, 80))

        #pygame.draw.rect(surface, (220, 220, 220), surface.get_rect(), 2)

        #font = pygame.font.SysFont("arial", max(12, width // 8))
        #text = font.render("Hidden", True, (255, 255, 255))

        #text_rect = text.get_rect(center=(width // 2, height // 2))
        #surface.blit(text, text_rect)

        #rect = surface.get_rect(topleft=(x, y))
        #screen.blit(surface, rect)

        return #rect

    def draw_tapped_overlay(self, screen, rect):
        overlay = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        screen.blit(overlay, rect)

        font = pygame.font.SysFont("arial", 16, bold=True)
        text = font.render("TAPPED", True, (255, 255, 255))
        text_rect = text.get_rect(center=rect.center)
        screen.blit(text, text_rect)

    def draw_card_with_state(
        self,
        screen,
        card,
        x,
        y,
        width=None,
        height=None,
        tapped=None,
        rotate=False
    ):
        if tapped is None:
            tapped = getattr(card, "tapped", False)

        rect = self.draw_card(
            screen,
            card,
            x,
            y,
            width=width,
            height=height,
            tapped=False
        )

        if rotate:
            image = self.load_card_image(card)

            if width is None or height is None:
                width, height = self.card_size

            image = pygame.transform.smoothscale(image, (height, width))
            image = pygame.transform.rotate(image, -90)

            rect = image.get_rect(topleft=(x, y))
            screen.blit(image, rect)

        if tapped:
            self.draw_tapped_overlay(screen, rect)

        stored = getattr(card, "stored_essence", None)

        if stored:
            total = sum(stored.values())
            if total > 0:
                self.draw_stored_essence(screen, rect, stored)

        return rect
    def draw_stored_essence(self, screen, rect, stored):
        font = pygame.font.SysFont("arial", 13, bold=True)

        text_parts = []

        for essence, amount in stored.items():
            if amount > 0:
                text_parts.append(f"{essence}:{amount}")

        if not text_parts:
            return

        text = " ".join(text_parts)
        label = font.render(text, True, (255, 255, 255))

        bg = pygame.Surface(
            (label.get_width() + 8, label.get_height() + 6),
            pygame.SRCALPHA
        )
        bg.fill((0, 0, 0, 180))

        screen.blit(bg, (rect.x, rect.bottom - bg.get_height()))
        screen.blit(label, (rect.x + 4, rect.bottom - bg.get_height() + 3))