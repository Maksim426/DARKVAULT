import math
import random
import pygame
from bosses import draw_boss_visual
from heroes import get_hero
from i18n import get_lang, tr_boss, tr_boss_subtitle
from settings import (
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    draw_aa_circle,
    draw_aa_ellipse,
    draw_aa_poly,
    draw_aa_ring,
    get_disc_sprite,
    get_glow_surf,
    get_particle_surf,
    get_view_width,
    gray,
    render_text_cached,
)


def draw_hero_portrait(screen, hero_id, cx, cy, scale=1.0):
    hero = get_hero(hero_id)
    r = int(round(27 * scale))
    body_lum = gray(hero["color_body"])[0]
    cloak_lum = gray(hero["color_cloak"])[0]
    acc_lum = gray(hero["color_accent"])[0]
    gl = get_glow_surf(int(r * 2.1), 236, 56)
    screen.blit(gl, (int(cx - gl.get_width() * 0.5), int(cy - gl.get_height() * 0.5)))

    if hero_id == "seraph":
        for s in (-1, 1):
            draw_aa_poly(screen, (20, 20, 20), [(cx, cy + r * 0.1), (cx + s * r * 1.45, cy - r * 0.55), (cx + s * r * 1.15, cy + r * 0.72)])
            draw_aa_poly(screen, (242, 242, 242), [(cx, cy + r * 0.15), (cx + s * r * 1.28, cy - r * 0.42), (cx + s * r * 1.0, cy + r * 0.58)])
    elif hero_id == "warden":
        for s in (-1, 1):
            draw_aa_poly(screen, (22, 22, 22), [(cx + s * r * 0.45, cy + r * 0.2), (cx + s * r * 1.08, cy + r * 0.36), (cx + s * r * 0.92, cy + r * 1.0), (cx + s * r * 0.42, cy + r * 0.95)])

    draw_aa_poly(screen, (14, 14, 14), [(cx - r * 0.85, cy + r * 1.15), (cx + r * 0.85, cy + r * 1.15), (cx + r * 0.58, cy + r * 0.2), (cx - r * 0.58, cy + r * 0.2)])
    draw_aa_poly(screen, (cloak_lum, cloak_lum, cloak_lum), [(cx - r * 0.72, cy + r * 1.08), (cx + r * 0.72, cy + r * 1.08), (cx + r * 0.48, cy + r * 0.25), (cx - r * 0.48, cy + r * 0.25)])

    if hero_id in ("azazel", "lilith"):
        for s in (-1, 1):
            draw_aa_poly(screen, (18, 18, 18), [(cx + s * r * 0.4, cy - r * 0.5), (cx + s * r * 1.18, cy - r * 1.28), (cx + s * r * 0.85, cy - r * 0.15)])
            draw_aa_poly(screen, (acc_lum, acc_lum, acc_lum), [(cx + s * r * 0.5, cy - r * 0.5), (cx + s * r * 1.0, cy - r * 1.08), (cx + s * r * 0.78, cy - r * 0.25)])
    elif hero_id in ("lost", "bethany", "lazarus", "seraph"):
        draw_aa_ellipse(screen, (246, 246, 246), cx, cy - r * 1.18, r * 0.78, r * 0.26)
        draw_aa_ellipse(screen, (16, 16, 16), cx, cy - r * 1.18, r * 0.45, r * 0.12)
    elif hero_id == "judas":
        pygame.draw.rect(screen, (16, 16, 16), (int(cx - r * 0.55), int(cy - r * 1.45), int(r * 1.1), int(r * 0.65)), border_radius=4)
        pygame.draw.rect(screen, (96, 96, 96), (int(cx - r * 0.42), int(cy - r * 1.32), int(r * 0.84), int(r * 0.42)), border_radius=3)
    elif hero_id == "nocturne":
        draw_aa_poly(screen, (240, 240, 240), [(cx - r * 0.55, cy - r * 0.72), (cx, cy - r * 1.48), (cx + r * 0.55, cy - r * 0.72), (cx, cy - r * 0.96)])
    elif hero_id == "chrono":
        pygame.draw.line(screen, (244, 244, 244), (int(cx), int(cy - r * 0.9)), (int(cx), int(cy - r * 1.38)), max(2, int(2 * scale)))

    disc = get_disc_sprite(r, body_lum, outline_lum=14, hi_lum=252)
    screen.blit(disc, (int(cx - disc.get_width() * 0.5), int(cy - disc.get_height() * 0.5)))

    eye_col = (248, 248, 248) if body_lum < 120 else (16, 16, 16)
    glint_col = (16, 16, 16) if eye_col[0] > 200 else (248, 248, 248)
    if hero_id == "keeper":
        lw = max(2, int(2 * scale))
        for sx in (-1, 1):
            ex = cx + sx * r * 0.34
            ey = cy - r * 0.08
            pygame.draw.line(screen, (16, 16, 16), (int(ex - r * 0.14), int(ey - r * 0.14)), (int(ex + r * 0.14), int(ey + r * 0.14)), lw)
            pygame.draw.line(screen, (16, 16, 16), (int(ex + r * 0.14), int(ey - r * 0.14)), (int(ex - r * 0.14), int(ey + r * 0.14)), lw)
    elif hero_id == "warden":
        pygame.draw.rect(screen, (16, 16, 16), (int(cx - r * 0.68), int(cy - r * 0.22), int(r * 1.36), max(6, int(r * 0.34))), border_radius=3)
        pygame.draw.line(screen, (244, 244, 244), (int(cx - r * 0.45), int(cy - r * 0.05)), (int(cx + r * 0.45), int(cy - r * 0.05)), max(2, int(2 * scale)))
    else:
        draw_aa_circle(screen, eye_col, cx - r * 0.34, cy - r * 0.08, max(3, r * 0.19))
        draw_aa_circle(screen, glint_col, cx - r * 0.38, cy - r * 0.14, max(1.5, r * 0.07))
        if hero_id == "cain":
            pygame.draw.line(screen, (16, 16, 16), (int(cx + r * 0.1), int(cy - r * 0.26)), (int(cx + r * 0.62), int(cy + r * 0.1)), max(3, int(4 * scale)))
        elif hero_id == "lilith":
            pygame.draw.rect(screen, (16, 16, 16), (int(cx - r * 0.72), int(cy - r * 0.24), int(r * 1.44), max(6, int(r * 0.34))), border_radius=4)
        else:
            draw_aa_circle(screen, eye_col, cx + r * 0.34, cy - r * 0.08, max(3, r * 0.19))
            draw_aa_circle(screen, glint_col, cx + r * 0.30, cy - r * 0.14, max(1.5, r * 0.07))
        if hero_id == "chrono":
            draw_aa_ring(screen, (242, 242, 242), cx + r * 0.34, cy - r * 0.08, max(4, r * 0.29), max(1, int(scale)))
        elif hero_id == "alchemist":
            draw_aa_ring(screen, (242, 242, 242), cx - r * 0.34, cy - r * 0.08, max(4, r * 0.27), max(1, int(scale)))
            draw_aa_ring(screen, (242, 242, 242), cx + r * 0.34, cy - r * 0.08, max(4, r * 0.27), max(1, int(scale)))


def draw_boss_portrait(screen, boss_key, cx, cy, scale=1.0, age=0.0):
    r = max(14, int(round(32 * scale)))
    draw_boss_visual(screen, boss_key, cx, cy, r, age=age, flash=False, phase=1)



class BossCutscene:
    def __init__(self, hero_id, boss_key):
        self.hero_id = hero_id
        self.boss_key = boss_key
        self.timer = 0.0
        self.duration = 145.0
        self.finished = False
        self._bg_w = 0
        self._slash_bg = None
        h_obj = get_hero(hero_id)
        self.hero_name = (h_obj.get("name_en", h_obj["name"]) if get_lang() == "en" else h_obj["name"]).upper()
        self.boss_name = tr_boss(boss_key)
        self.boss_sub = tr_boss_subtitle(boss_key)
        vw = get_view_width()
        self.ash = [
            {
                "x": random.uniform(0, vw),
                "y": random.uniform(0, SCREEN_HEIGHT),
                "vx": random.uniform(-0.8, 0.8),
                "vy": random.uniform(-1.1, -0.3),
                "r": random.choice([1, 2, 3]),
                "a": random.randint(60, 150),
            }
            for _ in range(44)
        ]
        self._ensure_bg(vw)

    def _ensure_bg(self, vw):
        if self._slash_bg is not None and self._bg_w == vw:
            return
        self._bg_w = vw
        surf = pygame.Surface((vw, SCREEN_HEIGHT))
        surf.fill((7, 7, 7))
        pygame.draw.polygon(surf, (22, 22, 22), [(0, 130), (vw, 235), (vw, 495), (0, 590)])
        pygame.draw.line(surf, (196, 196, 196), (0, 130), (vw, 235), 2)
        pygame.draw.line(surf, (196, 196, 196), (0, 590), (vw, 495), 2)
        pygame.draw.line(surf, (242, 242, 242), (vw // 2 - 44, 96), (vw // 2 + 44, 624), 3)
        self._slash_bg = surf

    def update(self, dt=1.0):
        vw = get_view_width()
        self.timer += dt
        for p in self.ash:
            p["x"] = (p["x"] + p["vx"] * dt) % vw
            p["y"] = (p["y"] + p["vy"] * dt) % SCREEN_HEIGHT
        if self.timer >= self.duration:
            self.finished = True

    def skip(self):
        self.finished = True

    def draw(self, screen, font_big, font_med, font_small):
        vw = get_view_width()
        self._ensure_bg(vw)
        screen.blit(self._slash_bg, (0, 0))
        for p in self.ash:
            ps = get_particle_surf(p["r"], 226, p["a"])
            screen.blit(ps, (int(p["x"]), int(p["y"])))

        t = min(1.0, self.timer / 28.0)
        ease = 1.0 - (1.0 - t) ** 3

        cx_mid = vw // 2
        hx = int((cx_mid - 340) - (1.0 - ease) * 420)
        bx = int((cx_mid + 340) + (1.0 - ease) * 420)
        cy = SCREEN_HEIGHT // 2

        draw_hero_portrait(screen, self.hero_id, hx, cy - 10, scale=2.3)
        draw_boss_portrait(screen, self.boss_key, bx, cy - 10, scale=2.5)

        vs_surf = render_text_cached(font_big, "VS", (248, 248, 248))
        screen.blit(vs_surf, (cx_mid - vs_surf.get_width() // 2, cy - 28))

        h_lbl = render_text_cached(font_med, self.hero_name, (226, 226, 226))
        screen.blit(h_lbl, (hx - h_lbl.get_width() // 2, cy + 98))

        b_lbl = render_text_cached(font_big, self.boss_name, (248, 248, 248))
        screen.blit(b_lbl, (bx - b_lbl.get_width() // 2, cy + 98))

        sub_lbl = render_text_cached(font_small, self.boss_sub, (176, 176, 176))
        screen.blit(sub_lbl, (bx - sub_lbl.get_width() // 2, cy + 138))
