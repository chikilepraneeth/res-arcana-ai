import pygame # type: ignore


class EssenceRenderer:
    def __init__(self):
        self.images = {}
        self.font = pygame.font.SysFont("arial", 22, bold=True)

    def load_images(self):
        paths = {
            "gold": "assets/cards/gold.png",
            "elan": "assets/cards/elan.png",
            "life": "assets/cards/life.png",
            "calm": "assets/cards/calm.png",
            "death": "assets/cards/death.png",
        }

        for name, path in paths.items():
            self.images[name] = pygame.image.load(path).convert_alpha()

    def draw_token(self, screen, camera, layout, slot_name, essence_name, amount):
        if essence_name not in self.images:
            return

        if slot_name not in layout:
            return

        data = layout[slot_name]

        cx, cy = camera.world_to_screen(data["x"], data["y"])
        r = int(data["r"] * camera.zoom)

        base_img = self.images[essence_name]

        # crop transparent empty space
        crop_rect = base_img.get_bounding_rect()
        cropped = base_img.subsurface(crop_rect).copy()

        # same visual box for all essences
        box_size = int(r * 4.5)

        cw, ch = cropped.get_size()
        scale = min(box_size / cw, box_size / ch)

        new_w = int(cw * scale)
        new_h = int(ch * scale)

        img = pygame.transform.smoothscale(cropped, (new_w, new_h))
        rect = img.get_rect(center=(cx, cy))

        # outline around actual shape
        mask = pygame.mask.from_surface(img)
        outline = mask.to_surface(
            setcolor=(255, 255, 255, 255),
            unsetcolor=(0, 0, 0, 0)
        ).convert_alpha()

        for dx, dy in [
            (-1, 0), (1, 0), (0, -1), (0, 1)
        ]:
            screen.blit(outline, (rect.x + dx, rect.y + dy))

        screen.blit(img, rect)

        # count badge attached to token
        badge_radius = 10
        badge_center = (
                rect.centerx,
                rect.bottom
            )

        pygame.draw.circle(screen, (25, 25, 25), badge_center, badge_radius)
        pygame.draw.circle(screen, (255, 255, 255), badge_center, badge_radius, 2)

        font = pygame.font.SysFont("arial", 16, bold=True)
        text = font.render(str(amount), True, (255, 255, 255))
        screen.blit(text, text.get_rect(center=badge_center))