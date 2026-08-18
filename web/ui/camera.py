import pygame


class Camera:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0

        self.zoom = 1.0
        self.min_zoom = 0.45
        self.max_zoom = 3.00
        self.zoom_speed = 1.15

        self.dragging = False
        self.last_mouse_pos = None
        self.drag_started = False

        self.world_bounds = pygame.Rect(0, 0, 1, 1)
        self.viewport_width = 1720
        self.viewport_height = 880
        self.padding = 50

    def set_world_bounds(self, rect):
        self.world_bounds = pygame.Rect(rect)

    def set_viewport_size(self, width, height):
        self.viewport_width = max(1, int(width))
        self.viewport_height = max(1, int(height))

    def fit_to_world(self, width=None, height=None, padding=None):
        if width is not None and height is not None:
            self.set_viewport_size(width, height)

        if padding is None:
            padding = self.padding

        bounds = self.world_bounds

        if bounds.w <= 0 or bounds.h <= 0:
            return

        available_w = max(1, self.viewport_width - padding * 2)
        available_h = max(1, self.viewport_height - padding * 2)

        zoom_x = available_w / bounds.w
        zoom_y = available_h / bounds.h

        self.zoom = min(zoom_x, zoom_y, self.max_zoom)
        self.zoom = max(self.min_zoom, self.zoom)

        self.center_on_world()

    def center_on_world(self):
        bounds = self.world_bounds

        visible_world_w = self.viewport_width / self.zoom
        visible_world_h = self.viewport_height / self.zoom

        self.x = bounds.centerx - visible_world_w / 2
        self.y = bounds.centery - visible_world_h / 2

        self.clamp()

    def clamp(self):
        bounds = self.world_bounds

        visible_world_w = self.viewport_width / self.zoom
        visible_world_h = self.viewport_height / self.zoom

        if visible_world_w >= bounds.w:
            self.x = bounds.centerx - visible_world_w / 2
        else:
            min_x = bounds.left
            max_x = bounds.right - visible_world_w
            self.x = max(min_x, min(self.x, max_x))

        if visible_world_h >= bounds.h:
            self.y = bounds.centery - visible_world_h / 2
        else:
            min_y = bounds.top
            max_y = bounds.bottom - visible_world_h
            self.y = max(min_y, min(self.y, max_y))

    def world_to_screen(self, wx, wy):
        return (
            int((wx - self.x) * self.zoom),
            int((wy - self.y) * self.zoom),
        )

    def screen_to_world(self, sx, sy):
        return (
            sx / self.zoom + self.x,
            sy / self.zoom + self.y,
        )

    def apply_rect(self, rect):
        x, y = self.world_to_screen(rect.x, rect.y)
        return pygame.Rect(
            x,
            y,
            int(rect.w * self.zoom),
            int(rect.h * self.zoom),
        )

    def handle_event(self, event):
        self.drag_started = False

        if event.type == pygame.MOUSEWHEEL:
            mx, my = pygame.mouse.get_pos()
            before_x, before_y = self.screen_to_world(mx, my)

            if event.y > 0:
                self.zoom *= self.zoom_speed
            elif event.y < 0:
                self.zoom /= self.zoom_speed

            self.zoom = max(self.min_zoom, min(self.zoom, self.max_zoom))

            after_x, after_y = self.screen_to_world(mx, my)

            self.x += before_x - after_x
            self.y += before_y - after_y
            self.clamp()

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.dragging = True
            self.last_mouse_pos = event.pos

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False
            self.last_mouse_pos = None

        if event.type == pygame.MOUSEMOTION:
            if self.dragging and self.last_mouse_pos:
                mx, my = event.pos
                lx, ly = self.last_mouse_pos

                dx = mx - lx
                dy = my - ly

                if abs(dx) > 2 or abs(dy) > 2:
                    self.drag_started = True

                self.x -= dx / self.zoom
                self.y -= dy / self.zoom
                self.clamp()

                self.last_mouse_pos = event.pos