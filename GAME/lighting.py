import math
import pygame
import settings as _settings
from settings import SCREEN_HEIGHT, SCREEN_WIDTH, clamp

_LOCAL_RADIAL_CACHE = {}
_LOCAL_VIGNETTE_CACHE = {}


def _radial_light_surf(radius, peak_lum=235):
    fn = getattr(_settings, "get_radial_light_surf", None)
    if fn is not None:
        return fn(radius, peak_lum)
    ir = max(12, int(round(radius)))
    il = int(clamp((int(peak_lum) // 8) * 8, 8, 255))
    key = (ir, il)
    cached = _LOCAL_RADIAL_CACHE.get(key)
    if cached is not None:
        return cached
    gs = 96
    buf = bytearray(gs * gs * 4)
    half = gs * 0.5
    inv_r = 1.0 / half
    for y in range(gs):
        dy = (y + 0.5 - half) * inv_r
        dy2 = dy * dy
        row_off = y * gs * 4
        for x in range(gs):
            dx = (x + 0.5 - half) * inv_r
            d2 = dx * dx + dy2
            if d2 < 1.0:
                d = math.sqrt(d2)
                smooth = 1.0 - d * d * (3.0 - 2.0 * d)
                val = int(il * (smooth ** 1.5))
                if val > 0:
                    idx = row_off + x * 4
                    buf[idx] = val
                    buf[idx + 1] = val
                    buf[idx + 2] = val
                    buf[idx + 3] = 255
    if hasattr(pygame.image, "frombytes"):
        raw_surf = pygame.image.frombytes(bytes(buf), (gs, gs), "RGBA")
    else:
        raw_surf = pygame.image.fromstring(bytes(buf), (gs, gs), "RGBA")
    scaled = pygame.transform.smoothscale(raw_surf, (ir * 2, ir * 2))
    out = pygame.Surface((ir * 2, ir * 2))
    if pygame.display.get_init() and pygame.display.get_surface() is not None:
        out = out.convert()
    out.fill((0, 0, 0))
    out.blit(scaled, (0, 0))
    _LOCAL_RADIAL_CACHE[key] = out
    return out


def _vignette_surf(w, h, strength):
    fn = getattr(_settings, "get_vignette_surf", None)
    if fn is not None:
        return fn(w, h, strength)
    ist = int(clamp((int(strength) // 8) * 8, 40, 235))
    key = (int(w), int(h), ist)
    cached = _LOCAL_VIGNETTE_CACHE.get(key)
    if cached is not None:
        return cached
    bw, bh = 160, 90
    buf = bytearray(bw * bh * 4)
    inv_hx = 1.0 / (bw * 0.56)
    inv_hy = 1.0 / (bh * 0.58)
    for y in range(bh):
        dy = (y + 0.5 - bh * 0.5) * inv_hy
        dy2 = dy * dy
        row_off = y * bw * 4
        for x in range(bw):
            dx = (x + 0.5 - bw * 0.5) * inv_hx
            r = math.sqrt(dx * dx + dy2)
            t = clamp((r - 0.52) / 0.74, 0.0, 1.0)
            s = t * t * (3.0 - 2.0 * t)
            a = int(ist * (s ** 1.35))
            if a > 0:
                buf[row_off + x * 4 + 3] = a
    if hasattr(pygame.image, "frombytes"):
        raw_surf = pygame.image.frombytes(bytes(buf), (bw, bh), "RGBA")
    else:
        raw_surf = pygame.image.fromstring(bytes(buf), (bw, bh), "RGBA")
    surf = pygame.transform.smoothscale(raw_surf, (int(w), int(h)))
    if pygame.display.get_init() and pygame.display.get_surface() is not None:
        surf = surf.convert_alpha()
    _LOCAL_VIGNETTE_CACHE[key] = surf
    return surf


class LightingSystem:
    def __init__(self, width=SCREEN_WIDTH, height=SCREEN_HEIGHT):
        self.width = int(width)
        self.height = int(height)
        cfg = _settings.get_effects_config()
        self.lw = int(cfg["light_w"])
        self.lh = int(cfg["light_h"])
        self.sx = self.lw / float(self.width)
        self.sy = self.lh / float(self.height)
        self.light_buf = pygame.Surface((self.lw, self.lh))
        self.shadow_px_w = max(160, self.width // 4)
        self.shadow_px_h = max(90, self.height // 4)
        self.shadow_buf = pygame.Surface((self.shadow_px_w, self.shadow_px_h), pygame.SRCALPHA)
        self._shadow_scaled_buf = pygame.Surface((self.lw, self.lh), pygame.SRCALPHA)
        self._scaled_light = pygame.Surface((self.width, self.height))
        self._display_converted = False
        self._ensure_display_formats()

    def _sync_quality_buffers(self):
        cfg = _settings.get_effects_config()
        r_scale = _settings.get_resolution_light_scale() if hasattr(_settings, "get_resolution_light_scale") else 1.0
        nw = int(clamp(round(cfg["light_w"] * r_scale), 192, self.width))
        nh = int(clamp(round(cfg["light_h"] * r_scale), 108, self.height))
        if nw != self.lw or nh != self.lh:
            self.lw = nw
            self.lh = nh
            self.sx = self.lw / float(self.width)
            self.sy = self.lh / float(self.height)
            self.light_buf = pygame.Surface((self.lw, self.lh))
            self._shadow_scaled_buf = pygame.Surface((self.lw, self.lh), pygame.SRCALPHA)
            self._display_converted = False
        return cfg

    def resize(self, width, height):
        nw = max(320, int(width))
        nh = max(240, int(height))
        if nw == self.width and nh == self.height:
            return
        self.width = nw
        self.height = nh
        self.sx = self.lw / float(self.width)
        self.sy = self.lh / float(self.height)
        self.shadow_px_w = max(160, self.width // 4)
        self.shadow_px_h = max(90, self.height // 4)
        self.shadow_buf = pygame.Surface((self.shadow_px_w, self.shadow_px_h), pygame.SRCALPHA)
        self._scaled_light = pygame.Surface((self.width, self.height))
        self._display_converted = False

    def reset_display_formats(self):
        self._display_converted = False

    def _ensure_display_formats(self):
        if self._display_converted:
            return
        try:
            if pygame.display.get_init() and pygame.display.get_surface() is not None:
                self.light_buf = self.light_buf.convert()
                self.shadow_buf = self.shadow_buf.convert_alpha()
                self._shadow_scaled_buf = self._shadow_scaled_buf.convert_alpha()
                self._scaled_light = self._scaled_light.convert()
                self._display_converted = True
        except Exception:
            self._display_converted = False

    def _blit_light(self, x, y, rad_px, peak_lum):
        lr = max(10, int(round(rad_px * self.sx)))
        lsurf = _radial_light_surf(lr, peak_lum)
        self.light_buf.blit(
            lsurf,
            (int(round(x * self.sx - lr)), int(round(y * self.sy - lr))),
            special_flags=pygame.BLEND_ADD,
        )


    @staticmethod
    def _chaikin_smooth(pts, iterations=1):
        out = list(pts)
        for _ in range(iterations):
            nxt = []
            n = len(out)
            for i in range(n):
                ax, ay = out[i]
                bx, by = out[(i + 1) % n]
                nxt.append((ax * 0.75 + bx * 0.25, ay * 0.75 + by * 0.25))
                nxt.append((ax * 0.25 + bx * 0.75, ay * 0.25 + by * 0.75))
            out = nxt
        return out

    def _get_obstacle_silhouette(self, obs, sx, sy):
        """Return convex silhouette matching the actual drawn sprite contour (not the square collision rect)."""
        r = obs.rect
        cx = r.centerx * sx
        cy = r.centery * sy
        # Sprite coordinates in _draw_obstacle_hi live in [-96..+96] around (96, 96)
        ux = max(3.5, (r.width * 0.5) * sx)
        uy = max(3.5, (r.height * 0.5) * sy)
        kind = getattr(obs, "kind", "rock")

        if kind in ("rock", "tinted_rock"):
            # Exact 7-vertex boulder from _draw_obstacle_hi, Chaikin-smoothed into a 14-point rounded dome
            raw = [
                (-68.0 / 96.0, 40.0 / 96.0),
                (-76.0 / 96.0, -16.0 / 96.0),
                (-36.0 / 96.0, -68.0 / 96.0),
                (44.0 / 96.0, -64.0 / 96.0),
                (76.0 / 96.0, -12.0 / 96.0),
                (64.0 / 96.0, 48.0 / 96.0),
                (-12.0 / 96.0, 68.0 / 96.0),
            ]
            pts = [(cx + px * ux, cy + py * uy) for px, py in raw]
            return self._chaikin_smooth(pts, iterations=1)

        if kind == "poop":
            # Rounded conical mound matching _draw_obstacle_hi
            raw = [
                (-0.24, -0.52),
                (0.24, -0.52),
                (0.52, -0.10),
                (0.66, 0.28),
                (0.50, 0.62),
                (0.0, 0.70),
                (-0.50, 0.62),
                (-0.66, 0.28),
                (-0.52, -0.10),
            ]
            return [(cx + px * ux, cy + py * uy) for px, py in raw]

        if kind == "urn":
            # Rounded amphora vessel silhouette (narrower than collision rect)
            steps = 12
            rx = ux * 0.50
            ry = uy * 0.58
            ocy = cy + uy * 0.08
            return [
                (cx + math.cos(i * 2.0 * math.pi / steps) * rx,
                 ocy + math.sin(i * 2.0 * math.pi / steps) * ry)
                for i in range(steps)
            ]

        if kind == "pillar":
            # Rounded stone column silhouette matching _draw_obstacle_hi
            steps = 12
            rx = ux * 0.76
            ry = uy * 0.78
            return [
                (cx + math.copysign(abs(math.cos(a)) ** 0.72, math.cos(a)) * rx,
                 cy + math.copysign(abs(math.sin(a)) ** 0.72, math.sin(a)) * ry)
                for a in (i * 2.0 * math.pi / steps for i in range(steps))
            ]

        if kind == "turret":
            # Exact hexagonal stone monolith base from _draw_obstacle_hi
            raw = [
                (-56.0 / 96.0, 54.0 / 96.0),
                (-72.0 / 96.0, 0.0),
                (-50.0 / 96.0, -56.0 / 96.0),
                (50.0 / 96.0, -56.0 / 96.0),
                (72.0 / 96.0, 0.0),
                (56.0 / 96.0, 54.0 / 96.0),
            ]
            return [(cx + px * ux, cy + py * uy) for px, py in raw]

        if kind == "barrier":
            # Rounded iron-banded barricade matching _draw_obstacle_hi
            steps = 12
            rx = ux * 0.80
            ry = uy * 0.72
            return [
                (cx + math.copysign(abs(math.cos(a)) ** 0.65, math.cos(a)) * rx,
                 cy + math.copysign(abs(math.sin(a)) ** 0.65, math.sin(a)) * ry)
                for a in (i * 2.0 * math.pi / steps for i in range(steps))
            ]

        # Default: smooth 12-point ellipse matching sprite core
        steps = 12
        rx = ux * 0.72
        ry = uy * 0.72
        return [
            (cx + math.cos(i * 2.0 * math.pi / steps) * rx,
             cy + math.sin(i * 2.0 * math.pi / steps) * ry)
            for i in range(steps)
        ]

    @staticmethod
    def _build_shadow_layers(slx, sly, scx, scy, pts, extrude):
        """Build 3 unified shadow polygons (penumbra, mid, umbra) starting from the object's center terminator."""
        n = len(pts)
        if n < 3:
            return None
        vx = scx - slx
        vy = scy - sly
        dist = math.hypot(vx, vy)
        if dist < 1e-3:
            return None
        dir_x = vx / dist
        dir_y = vy / dist

        min_ang = 1e9
        max_ang = -1e9
        idx_min = 0
        idx_max = 0
        for i, (px, py) in enumerate(pts):
            rx = px - slx
            ry = py - sly
            dot = rx * dir_x + ry * dir_y
            cross = dir_x * ry - dir_y * rx
            ang = math.atan2(cross, dot)
            if ang < min_ang:
                min_ang = ang
                idx_min = i
            if ang > max_ang:
                max_ang = ang
                idx_max = i

        # Skip if light is effectively inside the silhouette
        if max_ang - min_ang >= math.pi * 0.96 or max_ang - min_ang < 0.02:
            return None

        # Determine which arc between idx_max and idx_min is the BACK (far side away from light)
        path_fwd = []
        i = idx_max
        while True:
            path_fwd.append(pts[i])
            if i == idx_min:
                break
            i = (i + 1) % n

        path_rev = []
        i = idx_max
        while True:
            path_rev.append(pts[i])
            if i == idx_min:
                break
            i = (i - 1) % n

        def _avg_proj(path):
            return sum((px - slx) * dir_x + (py - sly) * dir_y for px, py in path) / max(1, len(path))

        back_arc = path_fwd if _avg_proj(path_fwd) >= _avg_proj(path_rev) else path_rev

        p_left = pts[idx_min]
        p_right = pts[idx_max]

        def _extrude_pt(px, py, length, spread_rad=0.0):
            rx = px - slx
            ry = py - sly
            d = math.hypot(rx, ry) or 1.0
            ux = rx / d
            uy = ry / d
            if spread_rad != 0.0:
                cs = math.cos(spread_rad)
                sn = math.sin(spread_rad)
                ux, uy = ux * cs - uy * sn, ux * sn + uy * cs
            return (px + ux * length, py + uy * length)

        # Anchor terminator directly through the exact center (scx, scy) of the obstacle
        # so the lit front half stays bright and the shadow begins smoothly from the very middle.
        center = (scx, scy)
        m = len(back_arc)

        # 1. Penumbra (soft outer halo, slightly fanned on outer edges)
        pen_far = []
        for k, (bx, by) in enumerate(back_arc):
            t = (k / float(max(1, m - 1))) * 2.0 - 1.0  # -1 at P_R, +1 at P_L
            spread = -t * 0.055
            pen_far.append(_extrude_pt(bx, by, extrude * 1.24, spread))
        poly_pen = [p_left, center, p_right] + pen_far

        # 2. Mid shadow (exact tangent projection following silhouette shape)
        mid_far = [_extrude_pt(bx, by, extrude * 0.78) for bx, by in back_arc]
        poly_mid = [p_left, center, p_right] + mid_far

        # 3. Core umbra (slightly inset toward center so sides soften into mid/penumbra)
        p_left_in = (scx + (p_left[0] - scx) * 0.86, scy + (p_left[1] - scy) * 0.86)
        p_right_in = (scx + (p_right[0] - scx) * 0.86, scy + (p_right[1] - scy) * 0.86)
        umb_far = [
            _extrude_pt(
                scx + (bx - scx) * 0.88,
                scy + (by - scy) * 0.88,
                extrude * 0.40,
            )
            for bx, by in back_arc
        ]
        poly_umb = [p_left_in, center, p_right_in] + umb_far

        return poly_pen, poly_mid, poly_umb

    def _cast_obstacle_shadows(self, lx, ly, obstacles, shadow_reach=340.0, intensity=1.0):
        # Rasterize shadows onto a 1/4-res pixel grid (4x4 pixel blocks) for crisp pixel-art edges
        psx = self.shadow_px_w / float(self.width)
        psy = self.shadow_px_h / float(self.height)
        slx = lx * psx
        sly = ly * psy
        reach_sq = shadow_reach * shadow_reach
        inten = clamp(float(intensity), 0.15, 1.25)
        kind_scale = {
            "pillar": 1.42,
            "urn": 1.12,
            "rock": 1.04,
            "tinted_rock": 1.06,
            "poop": 0.82,
            "turret": 1.16,
            "barrier": 1.08,
        }

        pen_batch = []
        mid_batch = []
        umb_batch = []

        for obs in obstacles:
            if not obs.alive:
                continue
            # Braziers emit their own firelight; don't cast a dark shadow cone through them
            if obs.kind == "brazier":
                continue
            if not getattr(obs, "casts_shadow", obs.kind in ("rock", "tinted_rock", "pillar", "poop", "urn", "turret", "barrier")):
                continue
            r = obs.rect
            ocx, ocy = r.centerx, r.centery
            dx = ocx - lx
            dy = ocy - ly
            dist_sq = dx * dx + dy * dy
            if dist_sq > reach_sq or dist_sq < 64.0:
                continue

            dist = math.sqrt(dist_sq)
            atten = clamp(1.0 - dist / shadow_reach, 0.22, 1.0)
            k_mul = kind_scale.get(obs.kind, 1.0)
            extrude = (42.0 + 62.0 * atten) * psx * 1.25 * k_mul
            umbra_alpha = int(128 * atten * inten)
            mid_alpha = int(76 * atten * inten)
            penumbra_alpha = int(34 * atten * inten)

            pts = self._get_obstacle_silhouette(obs, psx, psy)
            layers = self._build_shadow_layers(slx, sly, ocx * psx, ocy * psy, pts, extrude)
            if layers is None:
                continue
            poly_pen, poly_mid, poly_umb = layers
            pen_batch.append((penumbra_alpha, [(int(round(px)), int(round(py))) for px, py in poly_pen]))
            mid_batch.append((mid_alpha, [(int(round(px)), int(round(py))) for px, py in poly_mid]))
            umb_batch.append((umbra_alpha, [(int(round(px)), int(round(py))) for px, py in poly_umb]))

        if not pen_batch:
            return

        self.shadow_buf.fill((0, 0, 0, 0))
        # Draw in 3 strict back-to-front alpha passes on the low-res pixel grid
        for alpha, poly in pen_batch:
            pygame.draw.polygon(self.shadow_buf, (0, 0, 0, alpha), poly)
        for alpha, poly in mid_batch:
            pygame.draw.polygon(self.shadow_buf, (0, 0, 0, alpha), poly)
        for alpha, poly in umb_batch:
            pygame.draw.polygon(self.shadow_buf, (0, 0, 0, alpha), poly)

        # Nearest-neighbor scale preserves crisp pixel-art shadow steps on light_buf
        if self._shadow_scaled_buf.get_size() == (self.lw, self.lh) and self._shadow_scaled_buf.get_bitsize() == self.shadow_buf.get_bitsize():
            pygame.transform.scale(self.shadow_buf, (self.lw, self.lh), self._shadow_scaled_buf)
            self.light_buf.blit(self._shadow_scaled_buf, (0, 0))
        else:
            scaled_sh = pygame.transform.scale(self.shadow_buf, (self.lw, self.lh))
            self.light_buf.blit(scaled_sh, (0, 0))

    def render(
        self,
        screen,
        focus_x,
        focus_y,
        room,
        time_acc=0.0,
        lantern_fuel=1.0,
        aim_dir=(0.0, 0.0),
        extra_lights=None,
        preview_mode=False,
    ):
        cfg = self._sync_quality_buffers()
        self._ensure_display_formats()
        fuel = clamp(lantern_fuel, 0.14, 1.75)
        base_amb = room.theme.get("ambient", 0.34)
        amb = int(clamp(round(255 * base_amb * (0.42 + 0.58 * min(1.0, fuel))), 18, 136))
        if not cfg.get("vignette", True):
            amb = min(160, amb + 28)
        self.light_buf.fill((amb, amb, amb))

        flicker = 1.0 + 0.03 * math.sin(time_acc * 0.19) + 0.015 * math.sin(time_acc * 0.47)
        main_rad = clamp(325.0 * fuel * flicker, 135.0, 590.0)
        main_lum = int(clamp(228 * (0.48 + 0.52 * min(1.0, fuel)), 105, 245))
        self._blit_light(focus_x, focus_y, main_rad, main_lum)
        if cfg.get("smooth_scale", True):
            self._blit_light(focus_x, focus_y, main_rad * 0.52, int(main_lum * 0.4))

        ax, ay = aim_dir
        if ax != 0.0 or ay != 0.0:
            ad = math.hypot(ax, ay) or 1.0
            cx = focus_x + (ax / ad) * 110.0 * fuel
            cy = focus_y + (ay / ad) * 110.0 * fuel
            self._blit_light(cx, cy, main_rad * 0.65, int(110 * min(1.0, fuel)))

        if cfg.get("shadows", True):
            self._cast_obstacle_shadows(focus_x, focus_y, room.obstacles, shadow_reach=330.0 * fuel, intensity=1.0)
            if not preview_mode and not _settings.is_android():
                sec_casts = 0
                for obs in room.obstacles:
                    if obs.alive and obs.kind == "brazier":
                        self._cast_obstacle_shadows(
                            obs.rect.centerx,
                            obs.rect.centery,
                            room.obstacles,
                            shadow_reach=185.0,
                            intensity=0.42,
                        )
                        sec_casts += 1
                        if sec_casts >= 2:
                            break

        for idx, (tx, ty) in enumerate(room.torch_positions):
            tf = 0.90 + 0.10 * math.sin(time_acc * 0.17 + idx * 1.9)
            self._blit_light(tx, ty, 195.0 * tf, int(162 * tf))

        for obs in room.obstacles:
            if obs.alive and obs.kind == "brazier":
                bf = 0.92 + 0.08 * math.sin(time_acc * 0.23 + obs.rect.x * 0.05)
                self._blit_light(obs.rect.centerx, obs.rect.centery, 175.0 * bf, int(152 * bf))

        for door in room.doors.values():
            if not door.secret or door.opened:
                self._blit_light(door.rect.centerx, door.rect.centery, 118.0, 74)

        for mon in getattr(room, "monoliths", ()):
            if mon.alive:
                m_pulse = 0.88 + 0.12 * math.sin(time_acc * 0.11)
                self._blit_light(mon.x, mon.y - 8, 180.0 * m_pulse, 165)

        for ped in room.pedestals:
            if ped.alive:
                self._blit_light(ped.x, ped.y - 8, 130.0, 120)

        if extra_lights:
            for lx, ly, lrad, lalpha in extra_lights:
                self._blit_light(lx, ly, max(85.0, lrad * 1.25), int(clamp(lalpha * 0.78, 40, 185)))

        if cfg.get("vignette", True):
            vig_str = int(clamp(168 - 34 * min(1.0, fuel), 115, 195))
            self.light_buf.blit(_vignette_surf(self.lw, self.lh, vig_str), (0, 0))

        if self.lw == self.width and self.lh == self.height:
            screen.blit(self.light_buf, (0, 0), special_flags=pygame.BLEND_MULT)
        else:
            use_smooth = bool(cfg.get("smooth_scale", True)) and not _settings.is_android()
            scale_fn = pygame.transform.smoothscale if use_smooth else pygame.transform.scale
            if self._scaled_light.get_bitsize() == self.light_buf.get_bitsize():
                scale_fn(self.light_buf, (self.width, self.height), self._scaled_light)
            else:
                self._scaled_light = scale_fn(self.light_buf, (self.width, self.height))
            screen.blit(self._scaled_light, (0, 0), special_flags=pygame.BLEND_MULT)

        if cfg.get("bloom", False) and not preview_mode:
            glow_fn = getattr(_settings, "get_glow_surf", None)
            if glow_fn is not None:
                p_glow = glow_fn(78, 224, 34)
                screen.blit(
                    p_glow,
                    (int(round(focus_x - p_glow.get_width() * 0.5)), int(round(focus_y - p_glow.get_height() * 0.5))),
                    special_flags=pygame.BLEND_ADD,
                )
                t_glow = glow_fn(52, 236, 42)
                hw_g = t_glow.get_width() * 0.5
                hh_g = t_glow.get_height() * 0.5
                for tx, ty in room.torch_positions:
                    screen.blit(t_glow, (int(round(tx - hw_g)), int(round(ty - hh_g))), special_flags=pygame.BLEND_ADD)
                for obs in room.obstacles:
                    if obs.alive and obs.kind == "brazier":
                        screen.blit(
                            t_glow,
                            (int(round(obs.rect.centerx - hw_g)), int(round(obs.rect.centery - hh_g))),
                            special_flags=pygame.BLEND_ADD,
                        )
