import math
import random
import pygame
from bullet import EnemyProjectile
from sound import play_sound
from settings import (
    ENEMY_BASE_STATS,
    PLAYABLE_BOTTOM,
    PLAYABLE_LEFT,
    PLAYABLE_RIGHT,
    PLAYABLE_TOP,
    _prune_cache,
    angle_slerp,
    clamp,
    draw_aa_circle,
    draw_aa_ellipse,
    draw_aa_poly,
    draw_aa_ring,
    draw_dynamic_shadow,
    get_disc_sprite,
    get_glow_surf,
    get_particle_surf,
    get_shadow_surf,
    render_4x_smooth,
    spring_step,
)


_ALLY_CACHE = {}


def _get_ally_sprite(kind):
    spr = _ALLY_CACHE.get(kind)
    if spr is not None:
        return spr
    _prune_cache(_ALLY_CACHE, 16)
    s = 4.0
    if kind == "blue_fly":
        def _draw(hi, hw, hh):
            cx, cy = hw * 0.5, hh * 0.5
            draw_aa_ellipse(hi, (238, 238, 238, 255), cx - 5 * s, cy - 4 * s, 4 * s, 2 * s)
            draw_aa_ellipse(hi, (238, 238, 238, 255), cx + 5 * s, cy - 4 * s, 4 * s, 2 * s)
            draw_aa_circle(hi, (242, 242, 242, 255), cx, cy, 6 * s)
            draw_aa_circle(hi, (22, 22, 22, 255), cx, cy, 4 * s)

        spr = render_4x_smooth(22, 22, _draw, blur_radius=0.2)
    elif kind == "blue_spider":
        def _draw(hi, hw, hh):
            cx, cy = hw * 0.5, hh * 0.5
            for side in (-1, 1):
                pygame.draw.line(hi, (228, 228, 228, 255), (int(cx), int(cy)), (int(cx + side * 8 * s), int(cy - 4 * s)), int(2 * s))
                pygame.draw.line(hi, (228, 228, 228, 255), (int(cx), int(cy)), (int(cx + side * 8 * s), int(cy + 4 * s)), int(2 * s))
            draw_aa_circle(hi, (242, 242, 242, 255), cx, cy, 6 * s)
            draw_aa_circle(hi, (24, 24, 24, 255), cx, cy, 4 * s)

        spr = render_4x_smooth(22, 22, _draw, blur_radius=0.2)
    elif kind == "ghost":
        def _draw(hi, hw, hh):
            cx, cy = hw * 0.5, hh * 0.5
            draw_aa_circle(hi, (236, 236, 236, 255), cx, cy, 10 * s)
            draw_aa_ring(hi, (250, 250, 250, 255), cx, cy, 12 * s, int(s))
            draw_aa_circle(hi, (20, 20, 20, 255), cx - 3 * s, cy - 2 * s, 2 * s)
            draw_aa_circle(hi, (20, 20, 20, 255), cx + 3 * s, cy - 2 * s, 2 * s)

        spr = render_4x_smooth(28, 28, _draw, blur_radius=0.2)
    else:
        def _draw(hi, hw, hh):
            cx, cy = hw * 0.5, hh * 0.5
            draw_aa_circle(hi, (248, 248, 248, 255), cx, cy, 3.2 * s)
            draw_aa_circle(hi, (16, 16, 16, 255), cx, cy, 1.4 * s)

        spr = render_4x_smooth(10, 10, _draw, blur_radius=0.15)
    _ALLY_CACHE[kind] = spr
    return spr

REGULAR_ENEMY_TYPES = [
    "fly",
    "spider",
    "pooter",
    "gaper",
    "maggot",
    "clot",
    "hopper",
    "horf",
    "bony",
    "vis",
    "boil",
    "leech",
    "shadow_weaver",
    "whispering_phantom",
    "mimic_double",
    "many_eyed_watcher",
    "ash_stalker",
    "hollow_bell",
    "thread_serpent",
    "abyss_leaper",
    "mortar_cultist",
    "cinder_bomber",
    "pulse_sentinel",
]

def draw_enemy_visual(screen, enemy_type, x, y, r, age=0.0, flash=False, facing_angle=0.0, disguised=False, trail=None, slam_ring=0.0, air_z=0.0, light_sources=None):
    ir = max(10, int(round(r)))
    flying = enemy_type in ("fly", "pooter", "boil", "whispering_phantom", "many_eyed_watcher", "hollow_bell", "pulse_sentinel")
    hover_y = (-6.0 + math.sin(age * 2.0) * 3.0) if flying else math.sin(age * 1.8) * 1.1
    draw_dynamic_shadow(
        screen,
        x,
        y + ir + 3,
        int(ir * 2.35),
        max(8, int(ir * 0.85)),
        light_sources=light_sources,
        air_z=air_z + (12.0 if flying else 0.0),
        alpha=92 if (flying or air_z > 4) else 128,
    )
    dy = y + hover_y - air_z

    if slam_ring > 0:
        ring_r = int((24 - slam_ring) * 3.2) + ir
        draw_aa_ring(screen, (238, 238, 238), x, dy, ring_r, 2)

    if enemy_type == "shadow_weaver":
        for side in (-1, 1):
            for leg_i in range(3):
                phase = age * 2.5 + leg_i * 1.2 + (0.0 if side == 1 else 1.4)
                jx = x + side * (ir * 1.05)
                jy = dy - 5 + math.sin(phase) * 3.0
                fx = x + side * (ir * 1.42)
                fy = dy + (leg_i - 1) * 7 + math.cos(phase) * 3.0
                pygame.draw.line(screen, (18, 18, 18), (int(x), int(dy)), (int(jx), int(jy)), 3)
                pygame.draw.line(screen, (18, 18, 18), (int(jx), int(jy)), (int(fx), int(fy)), 2)
        body = get_disc_sprite(ir, 245 if flash else 48, outline_lum=12, hi_lum=210)
        screen.blit(body, (int(round(x - body.get_width() * 0.5)), int(round(dy - body.get_height() * 0.5))))
        draw_aa_circle(screen, (245, 245, 245), x - ir * 0.28, dy - ir * 0.14, max(2, ir * 0.17))
        draw_aa_circle(screen, (245, 245, 245), x + ir * 0.28, dy - ir * 0.14, max(2, ir * 0.17))

    elif enemy_type == "whispering_phantom":
        if trail:
            for idx, (tx, ty) in enumerate(reversed(trail)):
                frac = (idx + 1) / (len(trail) + 1)
                ps = get_particle_surf(max(2, int(ir * 0.72 * frac)), 222, int(112 * frac))
                screen.blit(ps, (int(round(tx - ps.get_width() * 0.5)), int(round(ty + hover_y - ps.get_height() * 0.5))))
        gl = get_glow_surf(int(ir * 1.85), 242, 66)
        screen.blit(gl, (int(round(x - gl.get_width() * 0.5)), int(round(dy - gl.get_height() * 0.5))))
        body = get_disc_sprite(ir, 250 if flash else 224, outline_lum=18, hi_lum=255)
        screen.blit(body, (int(round(x - body.get_width() * 0.5)), int(round(dy - body.get_height() * 0.5))))
        draw_aa_circle(screen, (20, 20, 20), x - ir * 0.30, dy - ir * 0.16, 3)
        draw_aa_circle(screen, (20, 20, 20), x + ir * 0.30, dy - ir * 0.16, 3)
        draw_aa_circle(screen, (20, 20, 20), x, dy + ir * 0.24, 3)

    elif enemy_type == "mimic_double":
        lum = 248 if flash else (136 if disguised else 172)
        body = get_disc_sprite(ir, lum, outline_lum=14, hi_lum=248)
        screen.blit(body, (int(round(x - body.get_width() * 0.5)), int(round(dy - body.get_height() * 0.5))))
        if disguised:
            draw_aa_ring(screen, (226, 226, 226), x, dy, ir + 5, 1)
            draw_aa_circle(screen, (238, 238, 238), x, dy, max(3, ir * 0.3))
        else:
            draw_aa_circle(screen, (250, 250, 250), x - ir * 0.32, dy - ir * 0.16, max(2, ir * 0.16))
            draw_aa_circle(screen, (250, 250, 250), x + ir * 0.32, dy - ir * 0.16, max(2, ir * 0.16))
            for ti in range(-2, 3):
                tx = x + ti * (ir * 0.18)
                draw_aa_poly(screen, (245, 245, 245), [(tx - 2, dy + ir * 0.12), (tx + 2, dy + ir * 0.12), (tx, dy + ir * 0.38)])

    elif enemy_type == "many_eyed_watcher":
        gl = get_glow_surf(int(ir * 2.0), 240, 72)
        screen.blit(gl, (int(round(x - gl.get_width() * 0.5)), int(round(dy - gl.get_height() * 0.5))))
        body = get_disc_sprite(ir, 248 if flash else 48, outline_lum=12, hi_lum=200)
        screen.blit(body, (int(round(x - body.get_width() * 0.5)), int(round(dy - body.get_height() * 0.5))))
        eye_spr = _get_ally_sprite("watcher_eye")
        ehw = eye_spr.get_width() * 0.5
        ehh = eye_spr.get_height() * 0.5
        for ei in range(8):
            a = age * 0.42 + ei * (2.0 * math.pi / 8.0)
            ex = x + math.cos(a) * (ir * 1.15)
            ey = dy + math.sin(a) * (ir * 1.15)
            screen.blit(eye_spr, (int(round(ex - ehw)), int(round(ey - ehh))))
        draw_aa_circle(screen, (248, 248, 248), x - ir * 0.22, dy - ir * 0.10, 3.2)
        draw_aa_circle(screen, (248, 248, 248), x + ir * 0.22, dy - ir * 0.10, 3.2)

    elif enemy_type == "hollow_bell":
        draw_aa_poly(
            screen,
            (14, 14, 14),
            [(x - ir * 0.9, dy + ir * 0.78), (x + ir * 0.9, dy + ir * 0.78), (x + ir * 0.56, dy - ir * 0.85), (x - ir * 0.56, dy - ir * 0.85)],
        )
        fill_lum = 248 if flash else 188
        draw_aa_poly(
            screen,
            (fill_lum, fill_lum, fill_lum),
            [(x - ir * 0.78, dy + ir * 0.68), (x + ir * 0.78, dy + ir * 0.68), (x + ir * 0.46, dy - ir * 0.74), (x - ir * 0.46, dy - ir * 0.74)],
        )
        draw_aa_circle(screen, (22, 22, 22), x, dy + ir * 0.82, max(4, ir * 0.24))
        draw_aa_circle(screen, (242, 242, 242), x, dy - ir * 0.14, max(3, ir * 0.22))

    elif enemy_type in ("thread_serpent", "ash_stalker"):
        lum = 248 if flash else (196 if enemy_type == "thread_serpent" else 68)
        if trail:
            for idx, (tx, ty) in enumerate(reversed(trail)):
                sr = max(4, int(ir * (0.45 + 0.45 * ((idx + 1) / max(1, len(trail))))))
                seg = get_disc_sprite(sr, lum, outline_lum=14, hi_lum=240)
                screen.blit(seg, (int(round(tx - seg.get_width() * 0.5)), int(round(ty - seg.get_height() * 0.5))))
        head = get_disc_sprite(ir, 250 if flash else min(230, lum + 24), outline_lum=12, hi_lum=252)
        screen.blit(head, (int(round(x - head.get_width() * 0.5)), int(round(dy - head.get_height() * 0.5))))
        eye_c = (248, 248, 248) if lum < 120 else (18, 18, 18)
        draw_aa_circle(screen, eye_c, x - ir * 0.26, dy - ir * 0.14, max(2, ir * 0.15))
        draw_aa_circle(screen, eye_c, x + ir * 0.26, dy - ir * 0.14, max(2, ir * 0.15))

    elif enemy_type in ("fly", "pooter"):
        wing_span = ir * (0.95 + 0.25 * math.sin(age * 7.5))
        draw_aa_ellipse(screen, (216, 216, 216), x - ir * 0.68, dy - ir * 0.48, wing_span * 0.54, ir * 0.32)
        draw_aa_ellipse(screen, (216, 216, 216), x + ir * 0.68, dy - ir * 0.48, wing_span * 0.54, ir * 0.32)
        lum = 248 if flash else (140 if enemy_type == "pooter" else 88)
        body = get_disc_sprite(ir, lum, outline_lum=16, hi_lum=236)
        screen.blit(body, (int(round(x - body.get_width() * 0.5)), int(round(dy - body.get_height() * 0.5))))
        draw_aa_circle(screen, (240, 240, 240), x - ir * 0.28, dy - ir * 0.14, max(2, ir * 0.19))
        draw_aa_circle(screen, (240, 240, 240), x + ir * 0.28, dy - ir * 0.14, max(2, ir * 0.19))

    elif enemy_type == "spider":
        swing_base = math.sin(age * 4.2) * (ir * 0.24)
        for side in (-1, 1):
            for leg_i in range(4):
                spread = (leg_i - 1.5) * (ir * 0.44)
                sw = swing_base if (leg_i + (0 if side == 1 else 1)) % 2 == 0 else -swing_base
                hip_x = x + side * (ir * 0.36)
                hip_y = dy + spread * 0.35
                knee_x = x + side * (ir * 1.12)
                knee_y = dy + spread * 0.92 - ir * 0.34 + sw * 0.65
                foot_x = x + side * (ir * 1.54 + (1.5 if leg_i in (1, 2) else 0.0))
                foot_y = dy + spread * 1.25 + ir * 0.22 + sw
                pygame.draw.line(screen, (16, 16, 16), (int(hip_x), int(hip_y)), (int(knee_x), int(knee_y)), max(2, int(ir * 0.22)))
                pygame.draw.line(screen, (16, 16, 16), (int(knee_x), int(knee_y)), (int(foot_x), int(foot_y)), max(2, int(ir * 0.16)))
                pygame.draw.line(screen, (96, 96, 96), (int(hip_x), int(hip_y)), (int(knee_x), int(knee_y)), 1)
                draw_aa_circle(screen, (72, 72, 72), knee_x, knee_y, max(1.4, ir * 0.10))
        ab_lum = 248 if flash else 54
        head_lum = 248 if flash else 74
        abdomen = get_disc_sprite(max(6, int(ir * 0.88)), ab_lum, outline_lum=12, hi_lum=196)
        screen.blit(abdomen, (int(round(x - abdomen.get_width() * 0.5)), int(round(dy - ir * 0.22 - abdomen.get_height() * 0.5))))
        draw_aa_poly(
            screen,
            (184, 184, 184) if not flash else (40, 40, 40),
            [(x, dy - ir * 0.54), (x + ir * 0.18, dy - ir * 0.26), (x, dy - ir * 0.02), (x - ir * 0.18, dy - ir * 0.26)],
        )
        head = get_disc_sprite(max(5, int(ir * 0.68)), head_lum, outline_lum=12, hi_lum=218)
        screen.blit(head, (int(round(x - head.get_width() * 0.5)), int(round(dy + ir * 0.20 - head.get_height() * 0.5))))
        for side in (-1, 1):
            draw_aa_poly(
                screen,
                (212, 212, 212),
                [(x + side * ir * 0.16, dy + ir * 0.62), (x + side * ir * 0.30, dy + ir * 0.66), (x + side * ir * 0.10, dy + ir * 0.94)],
            )
            draw_aa_circle(screen, (248, 248, 248), x + side * ir * 0.22, dy + ir * 0.20, max(1.8, ir * 0.15))
            draw_aa_circle(screen, (216, 216, 216), x + side * ir * 0.42, dy + ir * 0.08, max(1.2, ir * 0.09))

    elif enemy_type in ("maggot", "leech"):
        lum = 248 if flash else (196 if enemy_type == "maggot" else 84)
        seg = get_disc_sprite(ir, lum, outline_lum=16, hi_lum=244)
        screen.blit(seg, (int(round(x - seg.get_width() * 0.5)), int(round(dy - seg.get_height() * 0.5))))
        seg2 = get_disc_sprite(max(6, int(ir * 0.78)), max(48, lum - 20), outline_lum=16, hi_lum=220)
        screen.blit(
            seg2,
            (int(round(x - math.cos(facing_angle) * ir * 0.65 - seg2.get_width() * 0.5)), int(round(dy - math.sin(facing_angle) * ir * 0.65 - seg2.get_height() * 0.5))),
        )
        eye_c = (242, 242, 242) if lum < 120 else (18, 18, 18)
        draw_aa_circle(screen, eye_c, x - ir * 0.26, dy - ir * 0.12, max(2, ir * 0.14))
        draw_aa_circle(screen, eye_c, x + ir * 0.26, dy - ir * 0.12, max(2, ir * 0.14))

    elif enemy_type == "bony":
        body = get_disc_sprite(ir, 250 if flash else 234, outline_lum=14, hi_lum=255)
        screen.blit(body, (int(round(x - body.get_width() * 0.5)), int(round(dy - body.get_height() * 0.5))))
        draw_aa_circle(screen, (16, 16, 16), x - ir * 0.30, dy - ir * 0.15, max(2.5, ir * 0.18))
        draw_aa_circle(screen, (16, 16, 16), x + ir * 0.30, dy - ir * 0.15, max(2.5, ir * 0.18))
        pygame.draw.line(screen, (18, 18, 18), (int(x - 4), int(dy + 4)), (int(x + 4), int(dy + 4)), 2)

    elif enemy_type in ("vis", "boil", "clot"):
        lum = 248 if flash else (152 if enemy_type == "boil" else 132)
        body = get_disc_sprite(ir, lum, outline_lum=16, hi_lum=238)
        screen.blit(body, (int(round(x - body.get_width() * 0.5)), int(round(dy - body.get_height() * 0.5))))
        if enemy_type == "vis":
            draw_aa_circle(screen, (242, 242, 242), x, dy, max(3, ir * 0.26))
            draw_aa_circle(screen, (18, 18, 18), x, dy, max(1.5, ir * 0.12))
        elif enemy_type == "boil":
            for bx, by in ((-0.3, -0.2), (0.32, -0.1), (0.0, 0.26)):
                draw_aa_circle(screen, (224, 224, 224), x + ir * bx, dy + ir * by, max(2, ir * 0.18))
        else:
            draw_aa_circle(screen, (238, 238, 238), x - ir * 0.28, dy - ir * 0.16, max(2, ir * 0.16))
            draw_aa_circle(screen, (238, 238, 238), x + ir * 0.28, dy - ir * 0.16, max(2, ir * 0.16))

    elif enemy_type == "abyss_leaper":
        for side in (-1, 1):
            draw_aa_poly(
                screen,
                (18, 18, 18),
                [(x + side * ir * 0.35, dy - ir * 0.6), (x + side * ir * 0.95, dy - ir * 1.25), (x + side * ir * 0.72, dy - ir * 0.2)],
            )
            draw_aa_poly(
                screen,
                (230, 230, 230),
                [(x + side * ir * 0.42, dy - ir * 0.58), (x + side * ir * 0.84, dy - ir * 1.08), (x + side * ir * 0.64, dy - ir * 0.28)],
            )
        body = get_disc_sprite(ir, 250 if flash else 84, outline_lum=12, hi_lum=230)
        screen.blit(body, (int(round(x - body.get_width() * 0.5)), int(round(dy - body.get_height() * 0.5))))
        draw_aa_circle(screen, (248, 248, 248), x - ir * 0.28, dy - ir * 0.12, max(2.2, ir * 0.18))
        draw_aa_circle(screen, (248, 248, 248), x + ir * 0.28, dy - ir * 0.12, max(2.2, ir * 0.18))
        draw_aa_ring(screen, (200, 200, 200), x, y + ir * 0.4, max(6, int(ir * 0.9)), 1)

    elif enemy_type == "mortar_cultist":
        draw_aa_poly(
            screen,
            (16, 16, 16),
            [(x - ir * 0.88, dy + ir * 0.82), (x + ir * 0.88, dy + ir * 0.82), (x + ir * 0.42, dy - ir * 0.98), (x - ir * 0.42, dy - ir * 0.98)],
        )
        lum = 248 if flash else 128
        draw_aa_poly(
            screen,
            (lum, lum, lum),
            [(x - ir * 0.74, dy + ir * 0.70), (x + ir * 0.74, dy + ir * 0.70), (x + ir * 0.34, dy - ir * 0.82), (x - ir * 0.34, dy - ir * 0.82)],
        )
        draw_aa_circle(screen, (245, 245, 245), x, dy - ir * 0.85, max(4, ir * 0.34))
        draw_aa_circle(screen, (18, 18, 18), x, dy - ir * 0.85, max(2, ir * 0.18))
        draw_aa_circle(screen, (248, 248, 248), x - ir * 0.22, dy - ir * 0.12, max(1.8, ir * 0.14))
        draw_aa_circle(screen, (248, 248, 248), x + ir * 0.22, dy - ir * 0.12, max(1.8, ir * 0.14))

    elif enemy_type == "cinder_bomber":
        lum = 250 if flash else (225 if int(age * 4.0) % 2 == 0 else 72)
        body = get_disc_sprite(ir, lum, outline_lum=10, hi_lum=252)
        screen.blit(body, (int(round(x - body.get_width() * 0.5)), int(round(dy - body.get_height() * 0.5))))
        pygame.draw.line(screen, (220, 220, 220), (int(x), int(dy - ir * 0.85)), (int(x + ir * 0.45), int(dy - ir * 1.32)), 2)
        spark_r = 3.2 + math.sin(age * 9.0) * 1.4
        draw_aa_circle(screen, (255, 255, 255), x + ir * 0.48, dy - ir * 1.35, max(1.5, spark_r))
        eye_c = (18, 18, 18) if lum > 150 else (248, 248, 248)
        draw_aa_circle(screen, eye_c, x - ir * 0.28, dy - ir * 0.12, max(2.2, ir * 0.17))
        draw_aa_circle(screen, eye_c, x + ir * 0.28, dy - ir * 0.12, max(2.2, ir * 0.17))

    elif enemy_type == "pulse_sentinel":
        pulse = ir + 6 + int(math.sin(age * 3.0) * 4)
        draw_aa_ring(screen, (226, 226, 226), x, dy, pulse, 1)
        body = get_disc_sprite(ir, 250 if flash else 176, outline_lum=14, hi_lum=252)
        screen.blit(body, (int(round(x - body.get_width() * 0.5)), int(round(dy - body.get_height() * 0.5))))
        draw_aa_ring(screen, (20, 20, 20), x, dy, max(4, int(ir * 0.55)), 2)
        draw_aa_circle(screen, (248, 248, 248), x, dy, max(2.4, ir * 0.24))

    else:
        body = get_disc_sprite(ir, 250 if flash else 198, outline_lum=16, hi_lum=250)
        screen.blit(body, (int(round(x - body.get_width() * 0.5)), int(round(dy - body.get_height() * 0.5))))
        draw_aa_circle(screen, (18, 18, 18), x - ir * 0.30, dy - ir * 0.16, max(2.5, ir * 0.18))
        draw_aa_circle(screen, (18, 18, 18), x + ir * 0.30, dy - ir * 0.16, max(2.5, ir * 0.18))
        draw_aa_ellipse(screen, (18, 18, 18), x, dy + ir * 0.26, ir * 0.32, ir * 0.18)


class Enemy:
    def __init__(self, x, y, enemy_type="gaper", hp=20, speed=2.0, radius=16, flying=False, split_tier=0):
        self.x = float(x)
        self.y = float(y)
        self.vx = 0.0
        self.vy = 0.0
        self.enemy_type = enemy_type
        self.hp = float(hp)
        self.max_hp = float(hp)
        self.speed = float(speed)
        self.radius = float(radius)
        self.flying = bool(flying)
        self.split_tier = int(split_tier)
        self.alive = True
        self.hit_flash = 0.0
        self.poison_timer = 0.0
        self.knockback_x = 0.0
        self.knockback_y = 0.0
        self.age = random.uniform(0.0, 20.0)
        self.ai_timer = random.randint(20, 75)
        self.shoot_cd = random.randint(45, 110)
        self.orbital_hit_cd = 0.0
        self.dir_angle = random.uniform(0.0, math.pi * 2.0)
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.scale_vel = 0.0
        self.disguised = enemy_type == "mimic_double"
        self.trail = [(self.x, self.y) for _ in range(7)]
        self.slam_ring = 0.0
        self.air_z = 0.0
        self.jump_timer = 0.0
        self.fuse_timer = 0.0
        self.pending_slam = None
        self.pending_explosion = None
        self.pending_shockwave = None

    def take_damage(self, dmg, kx=0.0, ky=0.0):
        actual = float(dmg)
        if self.enemy_type == "maggot" and (kx != 0.0 or ky != 0.0):
            fx = math.cos(self.dir_angle)
            fy = math.sin(self.dir_angle)
            kd = math.hypot(kx, ky) or 1.0
            if (kx / kd) * fx + (ky / kd) * fy > 0.35:
                actual = max(0.5, actual * 0.55)
        self.hp -= actual
        self.hit_flash = 6.0
        self.scale_vel += 0.16
        if self.disguised:
            self.disguised = False
        self.knockback_x += kx
        self.knockback_y += ky
        if self.hp <= 0:
            self.alive = False
            if self.enemy_type == "cinder_bomber" and self.pending_explosion is None:
                self.pending_explosion = (self.x, self.y, 76.0, 1)

    def get_split_children(self):
        if self.enemy_type == "clot" and self.split_tier == 0:
            children = []
            for ox in (-16.0, 16.0):
                ch = Enemy(
                    clamp(self.x + ox, PLAYABLE_LEFT + 20, PLAYABLE_RIGHT - 20),
                    self.y,
                    enemy_type="clot",
                    hp=max(8, int(round(self.max_hp * 0.48))),
                    speed=self.speed * 1.25,
                    radius=max(10.0, self.radius * 0.72),
                    flying=False,
                    split_tier=1,
                )
                ch.knockback_x = ox * 0.18
                children.append(ch)
            return children
        return []

    def get_light_source(self):
        if not self.alive:
            return None
        if self.enemy_type in ("many_eyed_watcher", "whispering_phantom", "hollow_bell"):
            rad = 115 if self.enemy_type == "many_eyed_watcher" else 92
            return (self.x, self.y, rad, 134)
        return None

    def _move_with_room(self, room, dx, dy):
        self.x += dx
        self.y += dy
        r = self.radius
        if self.x - r < PLAYABLE_LEFT:
            self.x = PLAYABLE_LEFT + r
            self.dir_angle = math.pi - self.dir_angle
        elif self.x + r > PLAYABLE_RIGHT:
            self.x = PLAYABLE_RIGHT - r
            self.dir_angle = math.pi - self.dir_angle
        if self.y - r < PLAYABLE_TOP:
            self.y = PLAYABLE_TOP + r
            self.dir_angle = -self.dir_angle
        elif self.y + r > PLAYABLE_BOTTOM:
            self.y = PLAYABLE_BOTTOM - r
            self.dir_angle = -self.dir_angle

        if not self.flying and self.air_z < 8.0 and room is not None:
            for _pass in range(2):
                for obs in room.obstacles:
                    if not obs.alive or not obs.blocks_movement:
                        continue
                    rx = max(obs.rect.left, min(self.x, obs.rect.right))
                    ry = max(obs.rect.top, min(self.y, obs.rect.bottom))
                    ox = self.x - rx
                    oy = self.y - ry
                    dist = math.hypot(ox, oy)
                    if dist < r:
                        if dist > 0.001:
                            push = r - dist
                            self.x += (ox / dist) * push
                            self.y += (oy / dist) * push
                        else:
                            d_left = abs(self.x - obs.rect.left)
                            d_right = abs(obs.rect.right - self.x)
                            d_top = abs(self.y - obs.rect.top)
                            d_bot = abs(obs.rect.bottom - self.y)
                            m_min = min(d_left, d_right, d_top, d_bot)
                            if m_min == d_left:
                                self.x = obs.rect.left - r - 1.0
                            elif m_min == d_right:
                                self.x = obs.rect.right + r + 1.0
                            elif m_min == d_top:
                                self.y = obs.rect.top - r - 1.0
                            else:
                                self.y = obs.rect.bottom + r + 1.0
            self.x = max(PLAYABLE_LEFT + r, min(PLAYABLE_RIGHT - r, self.x))
            self.y = max(PLAYABLE_TOP + r, min(PLAYABLE_BOTTOM - r, self.y))

    def update(self, player, room, enemy_projectiles, dt=1.0, skatole_active=False):
        if not self.alive:
            return
        self.age += 0.14 * dt
        if self.hit_flash > 0:
            self.hit_flash = max(0.0, self.hit_flash - dt)
        if self.slam_ring > 0:
            self.slam_ring = max(0.0, self.slam_ring - dt)
        if self.orbital_hit_cd > 0:
            self.orbital_hit_cd = max(0.0, self.orbital_hit_cd - dt)
        if self.poison_timer > 0:
            self.poison_timer -= dt
            self.hp -= 0.08 * dt
            if self.hp <= 0:
                self.alive = False
                return

        self.scale_x, self.scale_vel = spring_step(self.scale_x, self.scale_vel, 1.0, 0.22, 0.72, dt)
        self.scale_y = 2.0 - self.scale_x

        if abs(self.knockback_x) > 0.05 or abs(self.knockback_y) > 0.05:
            self._move_with_room(room, self.knockback_x * dt, self.knockback_y * dt)
            damp = 0.78 ** dt
            self.knockback_x *= damp
            self.knockback_y *= damp

        is_cloaked = getattr(player, "invis_timer", 0.0) > 0.0
        if is_cloaked:
            wander_a = self.age * 0.45 + (id(self) % 7)
            dx = math.cos(wander_a) * 120.0
            dy = math.sin(wander_a) * 120.0
            dist = 320.0
            ux, uy = math.cos(wander_a) * 0.35, math.sin(wander_a) * 0.35
            target_ang = math.atan2(uy, ux)
            self.dir_angle = angle_slerp(self.dir_angle, target_ang, 0.04 * dt)
        else:
            dx = player.x - self.x
            dy = player.y - self.y
            dist = math.hypot(dx, dy) or 1.0
            ux, uy = dx / dist, dy / dist
            target_ang = math.atan2(dy, dx)
            self.dir_angle = angle_slerp(self.dir_angle, target_ang, 0.10 * dt)

        if self.enemy_type in ("whispering_phantom", "thread_serpent", "ash_stalker"):
            prev = (self.x, self.y)
            new_tr = []
            for tx, ty in self.trail:
                tdx, tdy = prev[0] - tx, prev[1] - ty
                td = math.hypot(tdx, tdy) or 1.0
                if td > 10.0:
                    tx += (tdx / td) * (td - 10.0)
                    ty += (tdy / td) * (td - 10.0)
                new_tr.append((tx, ty))
                prev = (tx, ty)
            self.trail = new_tr

        floor_lvl = int(getattr(room, "floor_level", 1) or 1) if room is not None else 1
        silent = bool(getattr(player, "preview_mode", False))

        if self.enemy_type == "shadow_weaver":
            orbit_x = ux * self.speed * 0.65 - uy * 0.95 * math.sin(self.age * 0.4)
            orbit_y = uy * self.speed * 0.65 + ux * 0.95 * math.sin(self.age * 0.4)
            self._move_with_room(room, orbit_x * dt, orbit_y * dt)
            if not is_cloaked:
                self.shoot_cd -= dt
                if self.shoot_cd <= 0:
                    base_a = math.atan2(dy, dx)
                    spreads = (-0.32, -0.14, 0.0, 0.14, 0.32) if floor_lvl >= 4 else (-0.24, 0.0, 0.24)
                    for idx_s, spread in enumerate(spreads):
                        a = base_a + spread
                        use_homing = floor_lvl >= 3 and (idx_s == 0 or idx_s == len(spreads) - 1)
                        enemy_projectiles.append(EnemyProjectile(self.x, self.y, math.cos(a) * 4.3, math.sin(a) * 4.3, radius=6, homing=use_homing))
                    if floor_lvl >= 3:
                        # Sidestep shadow blink after volley
                        side = 1.0 if (int(self.age * 10) % 2 == 0) else -1.0
                        self._move_with_room(room, -uy * side * 34.0, ux * side * 34.0)
                    if not silent:
                        play_sound("enemy_phantom", min_interval=0.14)
                    self.shoot_cd = random.uniform(66, 94)

        elif self.enemy_type == "whispering_phantom":
            sway = math.sin(self.age * 1.1) * 1.35
            self._move_with_room(room, (ux * self.speed - uy * sway) * dt, (uy * self.speed + ux * sway) * dt)
            if not is_cloaked:
                self.shoot_cd -= dt
                if self.shoot_cd <= 0:
                    base_a = math.atan2(dy, dx)
                    if floor_lvl >= 3:
                        # Twin homing wisps flanking player
                        for off in (-0.36, 0.36):
                            a = base_a + off
                            enemy_projectiles.append(EnemyProjectile(self.x, self.y, math.cos(a) * 4.4, math.sin(a) * 4.4, radius=6.5, homing=True))
                        self.slam_ring = 16.0
                    else:
                        enemy_projectiles.append(EnemyProjectile(self.x, self.y, ux * 4.6, uy * 4.6, radius=6.5, homing=True))
                    if not silent:
                        play_sound("enemy_phantom", min_interval=0.16)
                    self.shoot_cd = random.uniform(78, 108)

        elif self.enemy_type == "mimic_double":
            if self.disguised:
                if not is_cloaked and dist < 155.0:
                    self.disguised = False
                    self.scale_vel = 0.25
                    if not silent:
                        play_sound("enemy_dash", min_interval=0.15)
            else:
                self.ai_timer -= dt
                if self.ai_timer <= 0:
                    self.vx = ux * self.speed * 1.65
                    self.vy = uy * self.speed * 1.65
                    self.ai_timer = 30 if floor_lvl >= 3 else 34
                    if not is_cloaked:
                        offs = (-0.28, 0.0, 0.28) if floor_lvl >= 3 else (-0.2, 0.2)
                        for a_off in offs:
                            a = math.atan2(dy, dx) + a_off
                            enemy_projectiles.append(EnemyProjectile(self.x, self.y, math.cos(a) * 5.0, math.sin(a) * 5.0, radius=6))
                        if not silent:
                            play_sound("enemy_split", min_interval=0.14)
                self._move_with_room(room, self.vx * dt, self.vy * dt)
                self.vx *= 0.93 ** dt
                self.vy *= 0.93 ** dt

        elif self.enemy_type == "many_eyed_watcher":
            drift_x = math.cos(self.age * 0.28) * self.speed * 0.75 + ux * 0.45
            drift_y = math.sin(self.age * 0.34) * self.speed * 0.75 + uy * 0.45
            self._move_with_room(room, drift_x * dt, drift_y * dt)
            if not is_cloaked:
                self.shoot_cd -= dt
                if self.shoot_cd <= 0:
                    arms = 8 if floor_lvl >= 3 else 6
                    for i in range(arms):
                        a = self.age * 0.6 + i * (2.0 * math.pi / arms)
                        spd = 4.5 if (floor_lvl >= 2 and i % 2 == 0) else 3.7
                        enemy_projectiles.append(EnemyProjectile(self.x, self.y, math.cos(a) * spd, math.sin(a) * spd, radius=6))
                    if not silent:
                        play_sound("enemy_pulse", min_interval=0.16)
                    self.shoot_cd = random.uniform(58, 84)

        elif self.enemy_type == "ash_stalker":
            self.ai_timer -= dt
            if self.ai_timer <= 0:
                a = math.atan2(dy, dx) + random.uniform(-0.45, 0.45)
                self.vx = math.cos(a) * self.speed * 2.15
                self.vy = math.sin(a) * self.speed * 2.15
                self.ai_timer = random.uniform(26, 44)
                if not is_cloaked and floor_lvl >= 3:
                    # Leave rear ember fan on dash
                    back_a = a + math.pi
                    for off in (-0.35, 0.0, 0.35):
                        enemy_projectiles.append(EnemyProjectile(self.x, self.y, math.cos(back_a + off) * 3.8, math.sin(back_a + off) * 3.8, radius=5.5))
                if not silent:
                    play_sound("enemy_dash", min_interval=0.15)
            self._move_with_room(room, self.vx * dt, self.vy * dt)
            self.vx *= 0.91 ** dt
            self.vy *= 0.91 ** dt

        elif self.enemy_type == "hollow_bell":
            self._move_with_room(room, math.cos(self.age * 0.2) * 0.6 * dt, math.sin(self.age * 0.3) * 0.6 * dt)
            if not is_cloaked:
                self.shoot_cd -= dt
                if self.shoot_cd <= 0:
                    self.slam_ring = 24.0
                    cnt = 12 if floor_lvl >= 3 else 10
                    for i in range(cnt):
                        a = i * (2.0 * math.pi / cnt) + (self.age * 0.2 if floor_lvl >= 2 else 0.0)
                        spd = 4.6 if (floor_lvl >= 3 and i % 2 == 0) else 3.7
                        enemy_projectiles.append(EnemyProjectile(self.x, self.y, math.cos(a) * spd, math.sin(a) * spd, radius=6))
                    if not silent:
                        play_sound("enemy_pulse", min_interval=0.18)
                    self.shoot_cd = random.uniform(76, 104)

        elif self.enemy_type == "thread_serpent":
            wave = math.sin(self.age * 1.7) * 1.15
            ang = self.dir_angle + wave * 0.55
            self._move_with_room(room, math.cos(ang) * self.speed * dt, math.sin(ang) * self.speed * dt)
            if not is_cloaked and floor_lvl >= 3:
                self.shoot_cd -= dt
                if self.shoot_cd <= 0:
                    # Fire twin silk needles perpendicular to slither direction
                    for side in (-1.0, 1.0):
                        pa = ang + side * (math.pi * 0.5)
                        enemy_projectiles.append(EnemyProjectile(self.x, self.y, math.cos(pa) * 4.2, math.sin(pa) * 4.2, radius=5.5))
                    if not silent:
                        play_sound("enemy_split", min_interval=0.16)
                    self.shoot_cd = random.uniform(68, 96)

        elif self.enemy_type == "fly":
            if skatole_active:
                ux, uy = -ux * 0.5, -uy * 0.5
            wobble = math.sin(self.age * 1.4) * 0.9
            self.vx = (ux * self.speed + -uy * wobble) * dt
            self.vy = (uy * self.speed + ux * wobble) * dt
            self._move_with_room(room, self.vx, self.vy)

        elif self.enemy_type == "spider":
            self.ai_timer -= dt
            if self.ai_timer <= 0:
                if not is_cloaked and dist < 250 and random.random() < 0.72:
                    ang = math.atan2(dy, dx) + random.uniform(-0.42, 0.42)
                    self.vx = math.cos(ang) * self.speed * 1.55
                    self.vy = math.sin(ang) * self.speed * 1.55
                    self.ai_timer = random.uniform(18, 30)
                    if floor_lvl >= 3 and dist < 210:
                        for off in (-0.22, 0.22):
                            enemy_projectiles.append(EnemyProjectile(self.x, self.y, math.cos(ang + off) * 4.4, math.sin(ang + off) * 4.4, radius=5.0))
                        if not silent:
                            play_sound("enemy_dash", min_interval=0.16)
                else:
                    ang = random.uniform(0.0, math.pi * 2.0)
                    self.vx = math.cos(ang) * self.speed
                    self.vy = math.sin(ang) * self.speed
                    self.ai_timer = random.uniform(22, 42)
            self._move_with_room(room, self.vx * dt, self.vy * dt)
            self.vx *= 0.94 ** dt
            self.vy *= 0.94 ** dt

        elif self.enemy_type == "pooter":
            target_d = 180.0
            move = 1.0 if dist > target_d else (-0.8 if dist < 110 else 0.0)
            self._move_with_room(room, ux * self.speed * move * dt, uy * self.speed * move * dt)
            if not is_cloaked:
                self.shoot_cd -= dt
                if self.shoot_cd <= 0 and not skatole_active:
                    base_a = math.atan2(dy, dx)
                    if floor_lvl >= 3:
                        # Twin V-split arc shots on higher floors
                        for off in (-0.18, 0.18):
                            enemy_projectiles.append(EnemyProjectile(self.x, self.y, math.cos(base_a + off) * 4.6, math.sin(base_a + off) * 4.6, radius=6))
                    else:
                        enemy_projectiles.append(EnemyProjectile(self.x, self.y, ux * 4.4, uy * 4.4, radius=6))
                    if not silent:
                        play_sound("enemy_spit", min_interval=0.14)
                    self.shoot_cd = random.uniform(72, 106)

        elif self.enemy_type == "gaper":
            rage = 1.38 if (not is_cloaked and self.hp < self.max_hp * 0.65) else 1.0
            self._move_with_room(room, ux * self.speed * rage * dt, uy * self.speed * rage * dt)
            if not is_cloaked and floor_lvl >= 3 and rage > 1.0 and dist < 175.0:
                self.shoot_cd -= dt
                if self.shoot_cd <= 0:
                    self.slam_ring = 14.0
                    for i in range(4):
                        a = math.atan2(dy, dx) + i * (math.pi * 0.5)
                        enemy_projectiles.append(EnemyProjectile(self.x, self.y, math.cos(a) * 3.8, math.sin(a) * 3.8, radius=5.5))
                    if not silent:
                        play_sound("enemy_spit", min_interval=0.18)
                    self.shoot_cd = random.uniform(78, 108)

        elif self.enemy_type == "maggot":
            self.ai_timer -= dt
            if self.ai_timer <= 0:
                if abs(dx) > abs(dy):
                    self.vx = (1 if dx > 0 else -1) * self.speed
                    self.vy = 0.0
                else:
                    self.vx = 0.0
                    self.vy = (1 if dy > 0 else -1) * self.speed
                self.ai_timer = random.uniform(20, 40)
            self._move_with_room(room, self.vx * dt, self.vy * dt)

        elif self.enemy_type == "clot":
            self.ai_timer -= dt
            if self.ai_timer <= 0:
                ang = math.atan2(dy, dx) + random.uniform(-0.8, 0.8)
                self.vx = math.cos(ang) * self.speed
                self.vy = math.sin(ang) * self.speed
                self.ai_timer = 42 if floor_lvl >= 3 else 46
                if not is_cloaked:
                    # Alternate + and X cross waves on floor 2+
                    phase_rot = (math.pi * 0.25) if (floor_lvl >= 2 and (int(self.age) % 2 == 1)) else 0.0
                    for k in range(4):
                        a = k * (math.pi / 2.0) + phase_rot
                        enemy_projectiles.append(EnemyProjectile(self.x, self.y, math.cos(a) * 4.0, math.sin(a) * 4.0, radius=5.5))
                    if floor_lvl >= 3:
                        enemy_projectiles.append(EnemyProjectile(self.x, self.y, ux * 3.6, uy * 3.6, radius=6.0, homing=True))
                    if not silent:
                        play_sound("enemy_spit", min_interval=0.14)
            self._move_with_room(room, self.vx * dt, self.vy * dt)

        elif self.enemy_type == "hopper":
            if self.jump_timer > 0:
                self.jump_timer = max(0.0, self.jump_timer - dt)
                self.air_z = math.sin((self.jump_timer / 24.0) * math.pi) * 34.0
                self._move_with_room(room, self.vx * dt, self.vy * dt)
                self.vx *= 0.96 ** dt
                self.vy *= 0.96 ** dt
                if self.jump_timer <= 0.0 and floor_lvl >= 3 and not is_cloaked:
                    self.slam_ring = 16.0
                    for k in range(4):
                        a = k * (math.pi * 0.5) + math.pi * 0.25
                        enemy_projectiles.append(EnemyProjectile(self.x, self.y, math.cos(a) * 3.9, math.sin(a) * 3.9, radius=5.5))
            else:
                self.air_z = 0.0
                self.ai_timer -= dt
                if self.ai_timer <= 0:
                    ang = math.atan2(dy, dx) + random.uniform(-0.35, 0.35)
                    self.vx = math.cos(ang) * self.speed * 1.95
                    self.vy = math.sin(ang) * self.speed * 1.95
                    self.jump_timer = 24.0
                    self.ai_timer = random.uniform(24, 42)
                    if not silent:
                        play_sound("enemy_jump", min_interval=0.16)

        elif self.enemy_type == "horf":
            if not is_cloaked:
                self.shoot_cd -= dt
                if self.shoot_cd <= 0:
                    base_a = math.atan2(dy, dx)
                    if floor_lvl >= 3:
                        for off in (-0.22, 0.0, 0.22):
                            enemy_projectiles.append(EnemyProjectile(self.x, self.y, math.cos(base_a + off) * 5.0, math.sin(base_a + off) * 5.0, radius=6.2))
                    else:
                        enemy_projectiles.append(EnemyProjectile(self.x, self.y, ux * 5.0, uy * 5.0, radius=6.5))
                    if not silent:
                        play_sound("enemy_spit", min_interval=0.14)
                    self.shoot_cd = random.uniform(54, 82)

        elif self.enemy_type == "bony":
            move_mul = -0.85 if (not is_cloaked and dist < 130.0) else 0.8
            self._move_with_room(room, ux * self.speed * move_mul * dt, uy * self.speed * move_mul * dt)
            if not is_cloaked:
                self.shoot_cd -= dt
                if self.shoot_cd <= 0 and dist < 440:
                    # Lead player velocity on floor 2+ and throw twin ricochet bones on floor 3+
                    lead_t = (dist / 6.0) * (0.45 if floor_lvl >= 2 else 0.0)
                    tx = player.x + getattr(player, "vx", 0.0) * lead_t
                    ty = player.y + getattr(player, "vy", 0.0) * lead_t
                    ba = math.atan2(ty - self.y, tx - self.x)
                    if floor_lvl >= 3:
                        for off in (-0.14, 0.14):
                            enemy_projectiles.append(EnemyProjectile(self.x, self.y, math.cos(ba + off) * 5.6, math.sin(ba + off) * 5.6, radius=6.5))
                    else:
                        enemy_projectiles.append(EnemyProjectile(self.x, self.y, math.cos(ba) * 5.4, math.sin(ba) * 5.4, radius=6.5))
                    if not silent:
                        play_sound("enemy_bone", min_interval=0.14)
                    self.shoot_cd = random.uniform(48, 76)

        elif self.enemy_type == "vis":
            self._move_with_room(room, ux * self.speed * 0.6 * dt, uy * self.speed * 0.6 * dt)
            if not is_cloaked:
                self.shoot_cd -= dt
                if self.shoot_cd <= 0:
                    base_a = math.atan2(dy, dx)
                    steps = 4 if floor_lvl >= 3 else 3
                    for step_i in range(steps):
                        spd = 4.6 + step_i * 0.95
                        enemy_projectiles.append(EnemyProjectile(self.x, self.y, math.cos(base_a) * spd, math.sin(base_a) * spd, radius=7.0))
                    if floor_lvl >= 3:
                        for off in (-0.28, 0.28):
                            enemy_projectiles.append(EnemyProjectile(self.x, self.y, math.cos(base_a + off) * 5.2, math.sin(base_a + off) * 5.2, radius=6.0))
                    if not silent:
                        play_sound("enemy_pulse", min_interval=0.16)
                    self.shoot_cd = random.uniform(70, 98)

        elif self.enemy_type == "boil":
            if not is_cloaked:
                self.shoot_cd -= dt
                if self.shoot_cd <= 0:
                    self.slam_ring = 18.0
                    cnt = 8 if floor_lvl >= 3 else 6
                    for i in range(cnt):
                        a = i * (2.0 * math.pi / cnt) + self.age * 0.25
                        spd = 4.3 if (floor_lvl >= 3 and i % 2 == 0) else 3.6
                        enemy_projectiles.append(EnemyProjectile(self.x, self.y, math.cos(a) * spd, math.sin(a) * spd, radius=5.5))
                    if not silent:
                        play_sound("enemy_spit", min_interval=0.16)
                    self.shoot_cd = random.uniform(78, 108)

        elif self.enemy_type == "abyss_leaper":
            if self.jump_timer > 0:
                self.jump_timer = max(0.0, self.jump_timer - dt)
                self.air_z = math.sin((self.jump_timer / 30.0) * math.pi) * 62.0
                self._move_with_room(room, self.vx * dt, self.vy * dt)
                self.vx *= 0.97 ** dt
                self.vy *= 0.97 ** dt
                if self.jump_timer <= 0.0:
                    self.air_z = 0.0
                    self.slam_ring = 24.0
                    self.pending_slam = (self.x, self.y, 82.0, 1)
                    if floor_lvl >= 3 and not is_cloaked:
                        for i in range(6):
                            a = i * (math.pi / 3.0) + self.age * 0.3
                            enemy_projectiles.append(EnemyProjectile(self.x, self.y, math.cos(a) * 4.2, math.sin(a) * 4.2, radius=6.0))
                    if not silent:
                        play_sound("boss_slam", min_interval=0.22)
            else:
                self.air_z = 0.0
                if not is_cloaked:
                    self.ai_timer -= dt
                    if self.ai_timer <= 0:
                        ang = math.atan2(dy, dx) + random.uniform(-0.18, 0.18)
                        spd = min(8.2, max(3.6, dist / 28.0))
                        self.vx = math.cos(ang) * spd
                        self.vy = math.sin(ang) * spd
                        self.jump_timer = 30.0
                        self.ai_timer = random.uniform(40, 64)
                        if not silent:
                            play_sound("enemy_jump", min_interval=0.18)
                else:
                    self._move_with_room(room, ux * self.speed * dt, uy * self.speed * dt)

        elif self.enemy_type == "mortar_cultist":
            move_mul = -0.65 if (not is_cloaked and dist < 170.0) else (0.55 if dist > 300.0 else 0.0)
            self._move_with_room(room, ux * self.speed * move_mul * dt, uy * self.speed * move_mul * dt)
            if not is_cloaked:
                self.shoot_cd -= dt
                if self.shoot_cd <= 0:
                    shells = 2 if floor_lvl >= 3 else 1
                    for sh_i in range(shells):
                        spread_r = 24.0 if sh_i == 0 else 58.0
                        tx = clamp(player.x + random.uniform(-spread_r, spread_r), PLAYABLE_LEFT + 28, PLAYABLE_RIGHT - 28)
                        ty = clamp(player.y + random.uniform(-spread_r, spread_r), PLAYABLE_TOP + 28, PLAYABLE_BOTTOM - 28)
                        t_frames = 46.0 + sh_i * 8.0
                        pvx = (tx - self.x) / t_frames
                        pvy = (ty - self.y) / t_frames
                        enemy_projectiles.append(
                            EnemyProjectile(
                                self.x,
                                self.y,
                                pvx,
                                pvy,
                                radius=7.5,
                                lobbed=True,
                                target_x=tx,
                                target_y=ty,
                                blast_radius=56.0,
                                total_frames=t_frames,
                            )
                        )
                    if not silent:
                        play_sound("enemy_mortar", min_interval=0.18)
                    self.shoot_cd = random.uniform(74, 104)

        elif self.enemy_type == "cinder_bomber":
            spd_mul = (1.62 if floor_lvl >= 3 else 1.45) if self.fuse_timer > 0 else 1.0
            self._move_with_room(room, ux * self.speed * spd_mul * dt, uy * self.speed * spd_mul * dt)
            if not is_cloaked and self.fuse_timer <= 0.0 and dist < 102.0:
                self.fuse_timer = 42.0 if floor_lvl >= 3 else 45.0
                self.slam_ring = 22.0
                if not silent:
                    play_sound("enemy_fuse", min_interval=0.20)
                if floor_lvl >= 3:
                    for i in range(4):
                        a = i * (math.pi * 0.5)
                        enemy_projectiles.append(EnemyProjectile(self.x, self.y, math.cos(a) * 3.8, math.sin(a) * 3.8, radius=5.0))
            elif self.fuse_timer > 0.0:
                self.fuse_timer -= dt
                if self.fuse_timer <= 0.0:
                    self.alive = False
                    self.pending_explosion = (self.x, self.y, 84.0, 1)

        elif self.enemy_type == "pulse_sentinel":
            orb_x = ux * self.speed * 0.45 - uy * self.speed * 0.75 * math.sin(self.age * 0.35)
            orb_y = uy * self.speed * 0.45 + ux * self.speed * 0.75 * math.sin(self.age * 0.35)
            self._move_with_room(room, orb_x * dt, orb_y * dt)
            if not is_cloaked:
                self.shoot_cd -= dt
                if self.shoot_cd <= 0:
                    self.slam_ring = 24.0
                    self.pending_shockwave = (self.x, self.y, 134.0)
                    cnt = 8 if floor_lvl >= 3 else 6
                    for i in range(cnt):
                        a = i * (2.0 * math.pi / cnt) + self.age * 0.25
                        spd = 4.4 if (floor_lvl >= 3 and i % 2 == 0) else 3.6
                        enemy_projectiles.append(EnemyProjectile(self.x, self.y, math.cos(a) * spd, math.sin(a) * spd, radius=5.5))
                    if not silent:
                        play_sound("enemy_pulse", min_interval=0.18)
                    self.shoot_cd = random.uniform(74, 100)

        else:
            self._move_with_room(room, ux * self.speed * dt, uy * self.speed * dt)

    def draw(self, screen, light_sources=None):
        if not self.alive:
            return
        r = max(10, int(round(self.radius * 1.15 * (0.9 + 0.1 * self.scale_x))))
        draw_enemy_visual(
            screen,
            self.enemy_type,
            self.x,
            self.y,
            r,
            age=self.age,
            flash=(self.hit_flash > 0),
            facing_angle=self.dir_angle,
            disguised=self.disguised,
            trail=self.trail,
            slam_ring=self.slam_ring,
            air_z=self.air_z,
            light_sources=light_sources,
        )

        if self.hp < self.max_hp:
            hover_y = (-6.0 + math.sin(self.age * 2.0) * 3.0) if self.flying else math.sin(self.age * 1.8) * 1.1
            dy = self.y + hover_y - self.air_z
            bw = max(22, int(r * 1.85))
            bx = int(self.x - bw // 2)
            by = int(dy - r - 12)
            pygame.draw.rect(screen, (16, 16, 16), (bx - 1, by - 1, bw + 2, 5))
            fill_w = max(1, int(bw * max(0.0, self.hp / self.max_hp)))
            pygame.draw.rect(screen, (226, 226, 226), (bx, by, fill_w, 3))


class BlueFly:
    def __init__(self, x, y, damage=5.0):
        self.x = float(x)
        self.y = float(y)
        self.damage = float(damage)
        self.radius = 7.0
        self.alive = True
        self.age = random.uniform(0.0, 6.28)

    def update(self, player, enemies, dt=1.0):
        if not self.alive:
            return
        self.age += 0.24 * dt
        target = None
        best = 9999.0
        for e in enemies:
            if not getattr(e, "alive", True):
                continue
            d = math.hypot(e.x - self.x, e.y - self.y)
            if d < best:
                best = d
                target = e
        if target is not None:
            dx = target.x - self.x
            dy = target.y - self.y
            d = math.hypot(dx, dy) or 1.0
            self.x += (dx / d) * 4.5 * dt
            self.y += (dy / d) * 4.5 * dt
            if d < target.radius + self.radius + 4:
                target.take_damage(self.damage)
                self.alive = False
        else:
            ang = self.age * 0.65
            tx = player.x + math.cos(ang) * 42
            ty = player.y + math.sin(ang) * 42
            self.x += (tx - self.x) * 0.10 * dt
            self.y += (ty - self.y) * 0.10 * dt

    def draw(self, screen):
        if not self.alive:
            return
        gl = get_glow_surf(14, 240, 66)
        screen.blit(gl, (int(round(self.x - gl.get_width() * 0.5)), int(round(self.y - gl.get_height() * 0.5))))
        spr = _get_ally_sprite("blue_fly")
        screen.blit(spr, (int(round(self.x - spr.get_width() * 0.5)), int(round(self.y - spr.get_height() * 0.5))))


class BlueSpider:
    def __init__(self, x, y, damage=6.0):
        self.x = float(x)
        self.y = float(y)
        self.damage = float(damage)
        self.radius = 8.0
        self.alive = True
        self.age = random.uniform(0.0, 6.28)

    def update(self, player, enemies, dt=1.0):
        if not self.alive:
            return
        self.age += 0.25 * dt
        target = None
        best = 9999.0
        for e in enemies:
            if not getattr(e, "alive", True):
                continue
            d = math.hypot(e.x - self.x, e.y - self.y)
            if d < best:
                best = d
                target = e
        if target is not None:
            dx = target.x - self.x
            dy = target.y - self.y
            d = math.hypot(dx, dy) or 1.0
            self.x += (dx / d) * 4.2 * dt
            self.y += (dy / d) * 4.2 * dt
            if d < target.radius + self.radius + 4:
                target.take_damage(self.damage)
                self.alive = False
        else:
            tx = player.x + math.cos(self.age * 0.4) * 52
            ty = player.y + math.sin(self.age * 0.4) * 52
            self.x += (tx - self.x) * 0.08 * dt
            self.y += (ty - self.y) * 0.08 * dt

    def draw(self, screen):
        if not self.alive:
            return
        spr = _get_ally_sprite("blue_spider")
        screen.blit(spr, (int(round(self.x - spr.get_width() * 0.5)), int(round(self.y - spr.get_height() * 0.5))))


class Ghost:
    def __init__(self, x, y, damage=3.0, duration=480):
        self.x = float(x)
        self.y = float(y)
        self.damage = float(damage)
        self.duration = float(duration)
        self.radius = 12.0
        self.alive = True
        self.age = 0.0
        self.hit_cd = 0.0

    def update(self, enemies, dt=1.0):
        if not self.alive:
            return
        self.age += 0.16 * dt
        if self.hit_cd > 0:
            self.hit_cd = max(0.0, self.hit_cd - dt)
        self.duration -= dt
        if self.duration <= 0:
            self.alive = False
            return
        target = None
        best = 9999.0
        for e in enemies:
            if not getattr(e, "alive", True):
                continue
            d = math.hypot(e.x - self.x, e.y - self.y)
            if d < best:
                best = d
                target = e
        if target is not None:
            dx = target.x - self.x
            dy = target.y - self.y
            d = math.hypot(dx, dy) or 1.0
            self.x += (dx / d) * 3.6 * dt
            self.y += (dy / d) * 3.6 * dt
            if d < target.radius + self.radius and self.hit_cd <= 0:
                target.take_damage(self.damage)
                self.hit_cd = 18.0

    def draw(self, screen):
        if not self.alive:
            return
        gl = get_glow_surf(22, 245, 72)
        screen.blit(gl, (int(round(self.x - gl.get_width() * 0.5)), int(round(self.y - gl.get_height() * 0.5))))
        spr = _get_ally_sprite("ghost")
        screen.blit(spr, (int(round(self.x - spr.get_width() * 0.5)), int(round(self.y - spr.get_height() * 0.5))))


def create_enemy(enemy_type, x, y, floor_level=1, floor_modifier=None):
    stats = ENEMY_BASE_STATS.get(enemy_type, ENEMY_BASE_STATS["gaper"])
    scale = 1.0 + max(0, floor_level - 1) * 0.22
    spd_mult = 1.0
    if floor_modifier is not None:
        scale *= floor_modifier.get("hp_mult", 1.0)
        spd_mult = floor_modifier.get("spd_mult", 1.0)
    flying = enemy_type in ("fly", "pooter", "boil", "whispering_phantom", "many_eyed_watcher", "hollow_bell", "pulse_sentinel")
    return Enemy(
        x,
        y,
        enemy_type=enemy_type,
        hp=round(stats["hp"] * scale),
        speed=stats["speed"] * spd_mult,
        radius=stats["radius"],
        flying=flying,
    )
