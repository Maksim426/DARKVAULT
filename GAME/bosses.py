import math
import random
import pygame
from boss_profiles import BOSS_SIGNATURE_PROFILES, get_boss_profile
from bullet import EnemyProjectile
from enemy import create_enemy
from i18n import tr_boss
from sound import play_sound
from settings import (
    GAME_SETTINGS,
    PLAYABLE_BOTTOM,
    PLAYABLE_LEFT,
    PLAYABLE_RIGHT,
    PLAYABLE_TOP,
    _prune_cache,
    clamp,
    draw_aa_circle,
    draw_aa_ellipse,
    draw_aa_poly,
    draw_aa_ring,
    draw_dynamic_shadow,
    get_disc_sprite,
    get_glow_surf,
    get_shadow_surf,
    render_4x_smooth,
)

PLAYABLE_BOSS_KEYS = [
    "monstro",
    "duke",
    "larry",
    "gemini",
    "famine",
    "steven",
    "dingle",
    "dangle",
    "little_horn",
    "haunt",
    "gurglings",
    "turdlings",
    "widow",
    "pin",
    "blight_ovum",
    "rag_man",
    "chub",
    "gurdy",
    "gurdy_jr",
    "mega_maw",
    "mega_fatty",
    "the_gate",
    "pestilence",
    "peep",
    "carrion_queen",
    "wretched",
    "husk",
    "polycephalus",
    "big_horn",
    "rag_mega",
    "sisters_vis",
    "dark_one",
    "adversary",
    "frail",
    "brownie",
    "stain",
    "forsaken",
    "fistula",
    "blastocyst",
    "war",
    "death",
    "mom",
    "moms_heart",
    "it_lives",
    "satan",
    "isaac_boss",
    "blue_baby",
    "the_lamb",
    "mega_satan",
    "hush",
    "delirium",
    "uriel",
    "gabriel",
    "fallen",
    "headless_horseman",
    "krampus",
    "lust",
    "wrath",
    "gluttony",
    "greed",
    "sloth",
    "envy",
    "pride",
    "eclipse_warden",
    "void_architect",
    "pale_seraph",
]

MINIBOSS_KEYS = ["lust", "wrath", "gluttony", "greed", "sloth", "envy", "pride"]

FLOOR_BOSS_POOLS = {
    1: [
        "monstro",
        "duke",
        "larry",
        "gemini",
        "famine",
        "steven",
        "dingle",
        "dangle",
        "little_horn",
        "haunt",
        "gurglings",
        "turdlings",
        "widow",
        "pin",
        "blight_ovum",
        "rag_man",
        "fistula",
    ],
    2: [
        "chub",
        "gurdy",
        "gurdy_jr",
        "mega_maw",
        "mega_fatty",
        "the_gate",
        "pestilence",
        "peep",
        "carrion_queen",
        "wretched",
        "husk",
        "polycephalus",
        "big_horn",
        "eclipse_warden",
    ],
    3: [
        "rag_mega",
        "sisters_vis",
        "dark_one",
        "adversary",
        "frail",
        "brownie",
        "stain",
        "forsaken",
        "blastocyst",
        "fallen",
        "headless_horseman",
        "krampus",
        "void_architect",
    ],
    4: [
        "war",
        "death",
        "mom",
        "moms_heart",
        "it_lives",
        "uriel",
        "gabriel",
        "isaac_boss",
        "blue_baby",
        "eclipse_warden",
        "void_architect",
    ],
    5: [
        "satan",
        "the_lamb",
        "mega_satan",
        "hush",
        "delirium",
        "pale_seraph",
        "void_architect",
    ],
}

BOSS_BASE_CONFIG = {
    "monstro": {"hp": 220, "radius": 38, "speed": 2.4, "style": "jumper", "lum": 196},
    "duke": {"hp": 190, "radius": 36, "speed": 1.6, "style": "summoner", "lum": 154},
    "larry": {"hp": 180, "radius": 24, "speed": 3.0, "style": "worm", "lum": 208},
    "gemini": {"hp": 210, "radius": 32, "speed": 2.2, "style": "twin", "lum": 176},
    "famine": {"hp": 240, "radius": 30, "speed": 2.8, "style": "horseman", "lum": 214},
    "steven": {"hp": 215, "radius": 32, "speed": 2.4, "style": "twin", "lum": 82},
    "dingle": {"hp": 195, "radius": 33, "speed": 2.6, "style": "charger", "lum": 144},
    "dangle": {"hp": 210, "radius": 33, "speed": 2.7, "style": "charger", "lum": 124},
    "little_horn": {"hp": 230, "radius": 31, "speed": 2.1, "style": "demon", "lum": 76},
    "haunt": {"hp": 235, "radius": 32, "speed": 2.0, "style": "ghost", "lum": 234},
    "gurglings": {"hp": 165, "radius": 25, "speed": 3.2, "style": "charger", "lum": 172},
    "turdlings": {"hp": 175, "radius": 25, "speed": 3.1, "style": "charger", "lum": 134},
    "widow": {"hp": 215, "radius": 34, "speed": 2.7, "style": "spider_boss", "lum": 86},
    "pin": {"hp": 185, "radius": 23, "speed": 3.3, "style": "worm", "lum": 224},
    "blight_ovum": {"hp": 210, "radius": 30, "speed": 2.4, "style": "twin", "lum": 158},
    "rag_man": {"hp": 225, "radius": 32, "speed": 1.8, "style": "caster", "lum": 188},
    "chub": {"hp": 290, "radius": 34, "speed": 2.8, "style": "worm", "lum": 194},
    "gurdy": {"hp": 320, "radius": 44, "speed": 0.6, "style": "turret", "lum": 178},
    "gurdy_jr": {"hp": 265, "radius": 31, "speed": 3.5, "style": "charger", "lum": 186},
    "mega_maw": {"hp": 310, "radius": 42, "speed": 1.1, "style": "demon", "lum": 110},
    "mega_fatty": {"hp": 340, "radius": 44, "speed": 1.7, "style": "jumper", "lum": 198},
    "the_gate": {"hp": 310, "radius": 38, "speed": 1.3, "style": "demon", "lum": 120},
    "pestilence": {"hp": 295, "radius": 32, "speed": 2.5, "style": "horseman", "lum": 164},
    "peep": {"hp": 315, "radius": 38, "speed": 2.0, "style": "jumper", "lum": 218},
    "carrion_queen": {"hp": 300, "radius": 32, "speed": 3.1, "style": "worm", "lum": 152},
    "wretched": {"hp": 305, "radius": 37, "speed": 2.6, "style": "spider_boss", "lum": 116},
    "husk": {"hp": 295, "radius": 36, "speed": 1.8, "style": "summoner", "lum": 138},
    "polycephalus": {"hp": 305, "radius": 35, "speed": 1.9, "style": "caster", "lum": 208},
    "big_horn": {"hp": 350, "radius": 42, "speed": 1.5, "style": "demon", "lum": 72},
    "rag_mega": {"hp": 325, "radius": 35, "speed": 2.0, "style": "caster", "lum": 168},
    "sisters_vis": {"hp": 230, "radius": 31, "speed": 2.4, "style": "twin", "lum": 176},
    "dark_one": {"hp": 310, "radius": 34, "speed": 3.2, "style": "demon", "lum": 66},
    "adversary": {"hp": 330, "radius": 35, "speed": 3.1, "style": "demon", "lum": 82},
    "frail": {"hp": 290, "radius": 28, "speed": 3.3, "style": "worm", "lum": 232},
    "brownie": {"hp": 310, "radius": 34, "speed": 2.7, "style": "jumper", "lum": 146},
    "stain": {"hp": 315, "radius": 35, "speed": 2.0, "style": "caster", "lum": 96},
    "forsaken": {"hp": 300, "radius": 34, "speed": 2.2, "style": "ghost", "lum": 224},
    "fistula": {"hp": 190, "radius": 38, "speed": 2.5, "style": "splitter", "lum": 178},
    "blastocyst": {"hp": 240, "radius": 40, "speed": 2.2, "style": "splitter", "lum": 210},
    "war": {"hp": 420, "radius": 34, "speed": 3.3, "style": "horseman", "lum": 172},
    "death": {"hp": 460, "radius": 36, "speed": 2.7, "style": "horseman", "lum": 238},
    "mom": {"hp": 490, "radius": 46, "speed": 1.6, "style": "turret", "lum": 182},
    "moms_heart": {"hp": 530, "radius": 46, "speed": 1.0, "style": "bullet_hell", "lum": 168},
    "it_lives": {"hp": 580, "radius": 48, "speed": 1.1, "style": "bullet_hell", "lum": 192},
    "satan": {"hp": 610, "radius": 44, "speed": 2.6, "style": "demon", "lum": 92},
    "isaac_boss": {"hp": 550, "radius": 36, "speed": 2.3, "style": "angel", "lum": 242},
    "blue_baby": {"hp": 570, "radius": 36, "speed": 2.5, "style": "angel", "lum": 218},
    "the_lamb": {"hp": 600, "radius": 40, "speed": 3.0, "style": "demon", "lum": 228},
    "mega_satan": {"hp": 720, "radius": 52, "speed": 1.6, "style": "bullet_hell", "lum": 78},
    "hush": {"hp": 680, "radius": 50, "speed": 1.4, "style": "bullet_hell", "lum": 200},
    "delirium": {"hp": 760, "radius": 46, "speed": 3.0, "style": "delirium", "lum": 248},
    "uriel": {"hp": 360, "radius": 34, "speed": 2.4, "style": "angel", "lum": 244},
    "gabriel": {"hp": 430, "radius": 36, "speed": 2.5, "style": "angel", "lum": 250},
    "fallen": {"hp": 310, "radius": 34, "speed": 2.8, "style": "demon", "lum": 74},
    "headless_horseman": {"hp": 290, "radius": 32, "speed": 3.1, "style": "horseman", "lum": 134},
    "krampus": {"hp": 320, "radius": 35, "speed": 2.4, "style": "demon", "lum": 88},
    "lust": {"hp": 140, "radius": 24, "speed": 3.4, "style": "charger", "lum": 208},
    "wrath": {"hp": 155, "radius": 26, "speed": 2.2, "style": "caster", "lum": 168},
    "gluttony": {"hp": 180, "radius": 30, "speed": 1.7, "style": "turret", "lum": 188},
    "greed": {"hp": 175, "radius": 26, "speed": 2.5, "style": "caster", "lum": 222},
    "sloth": {"hp": 150, "radius": 25, "speed": 1.6, "style": "summoner", "lum": 144},
    "envy": {"hp": 120, "radius": 28, "speed": 2.8, "style": "splitter", "lum": 196},
    "pride": {"hp": 170, "radius": 26, "speed": 2.4, "style": "bullet_hell", "lum": 236},
    "eclipse_warden": {"hp": 360, "radius": 42, "speed": 2.3, "style": "eclipse", "lum": 64},
    "void_architect": {"hp": 440, "radius": 44, "speed": 2.1, "style": "architect", "lum": 124},
    "pale_seraph": {"hp": 640, "radius": 44, "speed": 2.6, "style": "angel", "lum": 246},
}

_TELEPORT_BOSS_KEYS = {
    "delirium",
    "little_horn",
    "void_architect",
    "rag_man",
    "rag_mega",
    "blue_baby",
    "the_lamb",
    "forsaken",
}

_GRAVITY_PULL_KEYS = {
    "eclipse_warden",
    "void_architect",
    "hush",
    "big_horn",
}

_BOSS_BASE_CACHE = {}
_PEEP_EYE_CACHE = {}


def _get_peep_eye_sprite():
    spr = _PEEP_EYE_CACHE.get(0)
    if spr is not None:
        return spr

    def _draw(hi, hw, hh):
        cx = cy = hw * 0.5
        s = 4.0
        draw_aa_circle(hi, (16, 16, 16, 255), cx, cy, 7.0 * s)
        draw_aa_circle(hi, (246, 246, 246, 255), cx, cy, 5.0 * s)

    spr = render_4x_smooth(18, 18, _draw, blur_radius=0.2)
    _PEEP_EYE_CACHE[0] = spr
    return spr


def _boss_hash(boss_key):
    val = 2166136261
    for ch in boss_key:
        val = ((val ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return val


def _draw_boss_hi_base(hi, hw, hh, boss_key, style, lum, flash):
    cx = hw // 2
    cy = hh // 2
    hr = hw * 0.295
    bhash = _boss_hash(boss_key)
    fill_l = 250 if flash else clamp(int(lum), 44, 246)
    shade_l = 235 if flash else max(18, int(fill_l - 48))
    hi_l = 255 if flash else min(252, int(fill_l + 32))
    rim_l = 20 if fill_l > 95 else 215
    dark_eye = fill_l > 115
    eye_col = (16, 16, 16, 255) if dark_eye else (248, 248, 248, 255)
    pupil_col = (248, 248, 248, 255) if dark_eye else (16, 16, 16, 255)

    if boss_key in ("little_horn", "big_horn", "satan", "mega_satan", "adversary", "krampus", "fallen", "dark_one", "the_lamb", "mega_maw", "the_gate"):
        h_span = 1.28 if boss_key in ("big_horn", "mega_satan", "the_lamb") else 1.04
        h_top = 1.48 if boss_key in ("big_horn", "krampus", "satan", "mega_satan") else 1.24
        for s in (-1, 1):
            pts = [
                (cx + s * hr * 0.36, cy - hr * 0.62),
                (cx + s * hr * (h_span + 0.14), cy - hr * (h_top + 0.08)),
                (cx + s * hr * (h_span * 0.72), cy - hr * 0.85),
                (cx + s * hr * 0.14, cy - hr * 0.82),
            ]
            draw_aa_poly(hi, (12, 12, 12, 255), pts)
            pts_in = [(cx + (px - cx) * 0.90, cy + (py - cy) * 0.90) for px, py in pts]
            horn_l = 234 if boss_key in ("the_lamb", "the_gate") else 198
            draw_aa_poly(hi, (horn_l, horn_l, horn_l, 255), pts_in)
            pygame.draw.line(hi, (248, 248, 248, 210), (int(cx + s * hr * 0.45), int(cy - hr * 0.78)), (int(cx + s * hr * h_span), int(cy - hr * h_top)), 4)

    if boss_key in ("pride", "brownie", "carrion_queen"):
        crown_pts = []
        for ci in range(7):
            fx = cx + (ci - 3) * (hr * 0.24)
            fy = cy - hr * (1.28 if ci % 2 == 0 else 0.94)
            crown_pts.append((fx, fy))
        crown_pts.extend([(cx + hr * 0.72, cy - hr * 0.70), (cx - hr * 0.72, cy - hr * 0.70)])
        draw_aa_poly(hi, (14, 14, 14, 255), crown_pts)
        draw_aa_poly(hi, (228, 228, 228, 255), [(cx + (px - cx) * 0.88, cy + (py - cy) * 0.88) for px, py in crown_pts])

    if boss_key == "wrath":
        pygame.draw.line(hi, (242, 242, 242, 255), (int(cx), int(cy - hr * 0.92)), (int(cx + hr * 0.34), int(cy - hr * 1.44)), 10)
        draw_aa_circle(hi, (250, 250, 250, 255), cx + hr * 0.38, cy - hr * 1.48, hr * 0.16)
        draw_aa_circle(hi, (180, 180, 180, 220), cx + hr * 0.38, cy - hr * 1.48, hr * 0.25)

    if boss_key == "void_architect":
        outer = [(cx + math.cos(a) * hr * 1.14, cy + math.sin(a) * hr * 1.14) for a in (i * math.pi * 0.25 for i in range(8))]
        draw_aa_poly(hi, (12, 12, 12, 255), outer)
        mid = [(cx + math.cos(a) * hr * 1.02, cy + math.sin(a) * hr * 1.02) for a in (i * math.pi * 0.25 for i in range(8))]
        draw_aa_poly(hi, (fill_l, fill_l, fill_l, 255), mid)
        inner = [(cx, cy - hr * 0.92), (cx + hr * 0.84, cy), (cx, cy + hr * 0.92), (cx - hr * 0.84, cy)]
        draw_aa_poly(hi, (shade_l, shade_l, shade_l, 255), inner)
        pygame.draw.polygon(hi, (242, 242, 242, 230), [(int(px), int(py)) for px, py in inner], 5)
        draw_aa_ellipse(hi, (246, 246, 246, 255), cx, cy - hr * 0.08, hr * 0.44, hr * 0.26)
        draw_aa_circle(hi, (14, 14, 14, 255), cx, cy - hr * 0.08, hr * 0.16)
        draw_aa_circle(hi, (250, 250, 250, 255), cx - hr * 0.06, cy - hr * 0.13, hr * 0.06)
        return

    if boss_key == "eclipse_warden":
        draw_aa_circle(hi, (242, 242, 242, 255), cx, cy, hr * 1.10)
        draw_aa_circle(hi, (12, 12, 12, 255), cx, cy, hr * 0.96)
        draw_aa_circle(hi, (38, 38, 38, 255), cx - hr * 0.08, cy - hr * 0.08, hr * 0.82)
        draw_aa_ring(hi, (226, 226, 226, 220), cx, cy, hr * 0.72, 4)
        draw_aa_ellipse(hi, (248, 248, 248, 255), cx - hr * 0.34, cy - hr * 0.12, hr * 0.18, hr * 0.09)
        draw_aa_ellipse(hi, (248, 248, 248, 255), cx + hr * 0.34, cy - hr * 0.12, hr * 0.18, hr * 0.09)
        draw_aa_poly(hi, (238, 238, 238, 235), [(cx, cy - hr * 0.46), (cx + hr * 0.10, cy + hr * 0.18), (cx, cy + hr * 0.44), (cx - hr * 0.10, cy + hr * 0.18)])
        return

    if boss_key == "mom":
        rect = pygame.Rect(int(cx - hr * 0.78), int(cy - hr * 1.18), int(hr * 1.56), int(hr * 2.15))
        pygame.draw.rect(hi, (12, 12, 12, 255), rect.inflate(14, 14), border_radius=24)
        pygame.draw.rect(hi, (fill_l, fill_l, fill_l, 255), rect, border_radius=20)
        pygame.draw.rect(hi, (shade_l, shade_l, shade_l, 255), (rect.x + 10, rect.centery, rect.w - 20, rect.h // 2 - 8), border_radius=14)
        draw_aa_ellipse(hi, (224, 224, 224, 225), cx, rect.bottom - hr * 0.22, hr * 0.88, hr * 0.36)
        pygame.draw.line(hi, (24, 24, 24, 230), (int(cx - hr * 0.45), int(cy - hr * 0.55)), (int(cx + hr * 0.45), int(cy - hr * 0.55)), 8)
        draw_aa_circle(hi, eye_col, cx - hr * 0.28, cy - hr * 0.22, hr * 0.14)
        draw_aa_circle(hi, eye_col, cx + hr * 0.28, cy - hr * 0.22, hr * 0.14)
        return

    if boss_key in ("moms_heart", "it_lives"):
        draw_aa_ellipse(hi, (12, 12, 12, 255), cx - hr * 0.26, cy - hr * 0.08, hr * 0.74, hr * 0.94)
        draw_aa_ellipse(hi, (12, 12, 12, 255), cx + hr * 0.26, cy + hr * 0.04, hr * 0.68, hr * 0.86)
        draw_aa_ellipse(hi, (fill_l, fill_l, fill_l, 255), cx - hr * 0.24, cy - hr * 0.08, hr * 0.62, hr * 0.82)
        draw_aa_ellipse(hi, (shade_l, shade_l, shade_l, 255), cx + hr * 0.24, cy + hr * 0.04, hr * 0.58, hr * 0.74)
        for vx, vy, vx2, vy2 in (
            (-0.42, -0.82, -0.18, -0.18),
            (0.32, -0.78, 0.12, -0.10),
            (-0.18, -0.18, -0.38, 0.54),
            (0.12, -0.10, 0.34, 0.52),
        ):
            pygame.draw.line(hi, (28, 28, 28, 240), (int(cx + hr * vx), int(cy + hr * vy)), (int(cx + hr * vx2), int(cy + hr * vy2)), 9)
        if boss_key == "it_lives":
            draw_aa_circle(hi, (248, 248, 248, 255), cx, cy - hr * 0.04, hr * 0.28)
            draw_aa_circle(hi, (16, 16, 16, 255), cx, cy - hr * 0.04, hr * 0.13)
        else:
            draw_aa_circle(hi, (238, 238, 238, 200), cx - hr * 0.25, cy - hr * 0.36, hr * 0.14)
        return

    if boss_key == "delirium":
        lobe_pts = []
        for i in range(18):
            a = i * (2.0 * math.pi / 18.0)
            wob = 0.86 + 0.18 * math.sin(i * 2.3 + 0.4) + 0.08 * math.cos(i * 3.7)
            lobe_pts.append((cx + math.cos(a) * hr * wob, cy + math.sin(a) * hr * wob))
        draw_aa_poly(hi, (14, 14, 14, 255), lobe_pts)
        lobe_in = [(cx + (px - cx) * 0.90, cy + (py - cy) * 0.90) for px, py in lobe_pts]
        draw_aa_poly(hi, (246, 246, 246, 255), lobe_in)
        for ex, ey, er in ((-0.38, -0.22, 0.18), (0.32, -0.28, 0.15), (-0.04, -0.44, 0.11), (0.44, 0.08, 0.10), (-0.42, 0.14, 0.09)):
            draw_aa_circle(hi, (16, 16, 16, 255), cx + hr * ex, cy + hr * ey, hr * er)
            draw_aa_circle(hi, (250, 250, 250, 255), cx + hr * (ex - 0.03), cy + hr * (ey - 0.03), hr * er * 0.35)
        draw_aa_ellipse(hi, (16, 16, 16, 255), cx + hr * 0.04, cy + hr * 0.32, hr * 0.46, hr * 0.20)
        return

    draw_aa_circle(hi, (12, 12, 12, 255), cx, cy, hr + 12)
    if style in ("jumper", "turret", "bullet_hell") and boss_key not in ("blastocyst",):
        draw_aa_ellipse(hi, (14, 14, 14, 255), cx, cy + hr * 0.12, hr * 1.08, hr * 0.95)
        draw_aa_ellipse(hi, (fill_l, fill_l, fill_l, 255), cx, cy + hr * 0.10, hr * 0.98, hr * 0.85)
    draw_aa_circle(hi, (fill_l, fill_l, fill_l, 255), cx, cy, hr)
    draw_aa_circle(hi, (shade_l, shade_l, shade_l, 155), cx + hr * 0.15, cy + hr * 0.18, hr * 0.76)
    draw_aa_circle(hi, (hi_l, hi_l, hi_l, 175), cx - hr * 0.22, cy - hr * 0.24, hr * 0.56)
    draw_aa_circle(hi, (min(255, hi_l + 18), min(255, hi_l + 18), min(255, hi_l + 18), 220), cx - hr * 0.34, cy - hr * 0.36, hr * 0.22)

    if boss_key in ("rag_man", "rag_mega"):
        for ang, yoff in ((-0.25, -0.38), (0.18, -0.05), (-0.15, 0.28), (0.28, 0.52)):
            p1 = (cx - hr * 0.88, cy + hr * (yoff - math.sin(ang) * 0.35))
            p2 = (cx + hr * 0.88, cy + hr * (yoff + math.sin(ang) * 0.35))
            pygame.draw.line(hi, (24, 24, 24, 210), (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])), 8)
            pygame.draw.line(hi, (232, 232, 232, 160), (int(p1[0]), int(p1[1] - 5)), (int(p2[0]), int(p2[1] - 5)), 4)

    if boss_key in ("fistula", "envy", "blight_ovum", "the_gate"):
        crack_segs = [
            [(cx - hr * 0.65, cy - hr * 0.45), (cx - hr * 0.15, cy - hr * 0.08), (cx - hr * 0.35, cy + hr * 0.52)],
            [(cx + hr * 0.55, cy - hr * 0.52), (cx + hr * 0.08, cy - hr * 0.12), (cx + hr * 0.48, cy + hr * 0.36)],
        ]
        for seg in crack_segs:
            pygame.draw.lines(hi, (18, 18, 18, 235), False, [(int(px), int(py)) for px, py in seg], 7)

    if boss_key == "blastocyst":
        draw_aa_ring(hi, (248, 248, 248, 230), cx, cy, hr * 0.84, 6)
        draw_aa_circle(hi, (124, 124, 124, 210), cx - hr * 0.18, cy + hr * 0.10, hr * 0.44)
        draw_aa_circle(hi, (242, 242, 242, 200), cx - hr * 0.28, cy - hr * 0.04, hr * 0.16)

    if boss_key in ("widow", "wretched"):
        pygame.draw.line(hi, (238, 238, 238, 210), (int(cx), int(cy - hr * 0.65)), (int(cx), int(cy - hr * 0.25)), 8)
        pygame.draw.line(hi, (238, 238, 238, 210), (int(cx - hr * 0.22), int(cy - hr * 0.46)), (int(cx + hr * 0.22), int(cy - hr * 0.46)), 8)

    if boss_key in ("pestilence", "boil", "sloth", "gurdy", "carrion_queen"):
        for k in range(5):
            ang = ((bhash >> (k * 4)) % 360) * math.pi / 180.0
            dist_f = 0.42 + 0.30 * (((bhash >> (k * 3)) % 10) / 10.0)
            px = cx + math.cos(ang) * hr * dist_f
            py = cy + math.sin(ang) * hr * dist_f
            draw_aa_circle(hi, (36, 36, 36, 200), px, py, hr * 0.13)
            draw_aa_circle(hi, (226, 226, 226, 200), px - hr * 0.03, py - hr * 0.03, hr * 0.07)

    if boss_key == "pale_seraph":
        draw_aa_poly(hi, (18, 18, 18, 255), [(cx, cy - hr * 0.72), (cx + hr * 0.18, cy - hr * 0.44), (cx, cy - hr * 0.16), (cx - hr * 0.18, cy - hr * 0.44)])
        draw_aa_poly(hi, (252, 252, 252, 255), [(cx, cy - hr * 0.64), (cx + hr * 0.12, cy - hr * 0.44), (cx, cy - hr * 0.24), (cx - hr * 0.12, cy - hr * 0.44)])

    if boss_key == "hush":
        for sx in (-0.38, 0.38):
            draw_aa_ellipse(hi, (16, 16, 16, 255), cx + hr * sx, cy - hr * 0.14, hr * 0.16, hr * 0.24)
            pygame.draw.line(hi, (238, 238, 238, 180), (int(cx + hr * sx), int(cy + hr * 0.06)), (int(cx + hr * sx), int(cy + hr * 0.54)), 8)
        draw_aa_ellipse(hi, (14, 14, 14, 255), cx, cy + hr * 0.32, hr * 0.34, hr * 0.26)
        return

    if boss_key == "greed":
        for sx in (-0.34, 0.34):
            pygame.draw.rect(hi, (18, 18, 18, 255), (int(cx + hr * sx - hr * 0.08), int(cy - hr * 0.34), int(hr * 0.16), int(hr * 0.36)), border_radius=4)
    elif boss_key in ("blue_baby", "isaac_boss") and boss_key == "blue_baby":
        for sx in (-0.34, 0.34):
            ex, ey = cx + hr * sx, cy - hr * 0.16
            pygame.draw.line(hi, (16, 16, 16, 255), (int(ex - hr * 0.14), int(ey - hr * 0.14)), (int(ex + hr * 0.14), int(ey + hr * 0.14)), 9)
            pygame.draw.line(hi, (16, 16, 16, 255), (int(ex + hr * 0.14), int(ey - hr * 0.14)), (int(ex - hr * 0.14), int(ey + hr * 0.14)), 9)
    elif boss_key == "polycephalus":
        for sx, sy in ((-0.44, -0.10), (0.0, -0.36), (0.44, -0.10)):
            draw_aa_circle(hi, (16, 16, 16, 255), cx + hr * sx, cy + hr * sy, hr * 0.14)
            draw_aa_circle(hi, (248, 248, 248, 255), cx + hr * sx - hr * 0.03, cy + hr * sy - hr * 0.03, hr * 0.05)
    elif boss_key in ("adversary", "pin", "frail", "chub", "scolex", "peep"):
        if boss_key == "adversary":
            pygame.draw.rect(hi, (238, 238, 238, 240), (int(cx - hr * 0.56), int(cy - hr * 0.28), int(hr * 1.12), int(hr * 0.22)), border_radius=6)
        else:
            for sx in (-0.32, 0.32):
                draw_aa_circle(hi, eye_col, cx + hr * sx, cy - hr * 0.16, hr * 0.19)
                draw_aa_circle(hi, pupil_col, cx + hr * sx - hr * 0.04, cy - hr * 0.19, hr * 0.08)
    else:
        el_scale = 1.12 if boss_key == "monstro" else 1.0
        draw_aa_circle(hi, eye_col, cx - hr * 0.33, cy - hr * 0.15, hr * 0.20 * el_scale)
        draw_aa_circle(hi, eye_col, cx + hr * 0.33, cy - hr * 0.18, hr * 0.18)
        draw_aa_circle(hi, pupil_col, cx - hr * 0.35, cy - hr * 0.18, hr * 0.08)
        draw_aa_circle(hi, pupil_col, cx + hr * 0.31, cy - hr * 0.21, hr * 0.08)
        if boss_key == "mega_satan":
            draw_aa_circle(hi, (248, 248, 248, 255), cx, cy - hr * 0.42, hr * 0.14)
            draw_aa_circle(hi, (16, 16, 16, 255), cx, cy - hr * 0.42, hr * 0.06)

    if boss_key == "isaac_boss":
        for sx in (-0.33, 0.33):
            pygame.draw.line(hi, (246, 246, 246, 225), (int(cx + hr * sx), int(cy + hr * 0.04)), (int(cx + hr * sx), int(cy + hr * 0.48)), 7)

    if boss_key in ("gluttony", "vis"):
        draw_aa_ellipse(hi, (14, 14, 14, 255), cx, cy + hr * 0.22, hr * 0.28, hr * 0.56)
        for ti in range(-2, 3):
            ty = cy + hr * (0.22 + ti * 0.15)
            draw_aa_poly(hi, (242, 242, 242, 255), [(cx - hr * 0.22, ty - hr * 0.04), (cx - hr * 0.04, ty), (cx - hr * 0.22, ty + hr * 0.04)])
            draw_aa_poly(hi, (242, 242, 242, 255), [(cx + hr * 0.22, ty - hr * 0.04), (cx + hr * 0.04, ty), (cx + hr * 0.22, ty + hr * 0.04)])
    elif boss_key == "the_lamb":
        pygame.draw.line(hi, (18, 18, 18, 255), (int(cx), int(cy + hr * 0.06)), (int(cx), int(cy + hr * 0.52)), 9)
        pygame.draw.line(hi, (18, 18, 18, 255), (int(cx - hr * 0.20), int(cy + hr * 0.34)), (int(cx + hr * 0.20), int(cy + hr * 0.34)), 9)
    elif boss_key == "headless_horseman":
        draw_aa_circle(hi, (14, 14, 14, 255), cx, cy + hr * 0.26, hr * 0.24)
        draw_aa_circle(hi, (238, 238, 238, 255), cx, cy + hr * 0.26, hr * 0.14)
    else:
        mouth_w = hr * (0.54 if boss_key in ("monstro", "mega_maw", "mega_satan", "mega_fatty") else 0.42)
        mouth_h = hr * (0.28 if boss_key in ("monstro", "mega_maw", "mega_satan") else 0.20)
        draw_aa_ellipse(hi, (12, 12, 12, 255), cx, cy + hr * 0.28, mouth_w, mouth_h)
        if boss_key not in ("haunt", "dingle", "dangle", "isaac_boss"):
            teeth_cnt = 5 if boss_key in ("monstro", "mega_maw", "mega_satan", "chub") else 3
            for ti in range(teeth_cnt):
                frac = (ti - (teeth_cnt - 1) * 0.5) / max(1.0, teeth_cnt * 0.5)
                tx = cx + frac * mouth_w * 0.72
                draw_aa_poly(hi, (244, 244, 244, 255), [(tx - hr * 0.07, cy + hr * 0.14), (tx + hr * 0.07, cy + hr * 0.14), (tx, cy + hr * 0.31)])

    draw_aa_ring(hi, (rim_l, rim_l, rim_l, 165), cx, cy, hr * 0.92, 4)


def _get_boss_base_sprite(boss_key, r, style, lum, flash=False):
    ir = max(14, int(round(r)))
    il = int(clamp(int(lum), 0, 255))
    key = (boss_key, ir, style, il, bool(flash))
    cached = _BOSS_BASE_CACHE.get(key)
    if cached is not None:
        return cached
    _prune_cache(_BOSS_BASE_CACHE, 80)
    box_size = int(round(ir * 3.45))
    surf = render_4x_smooth(
        box_size,
        box_size,
        lambda hi, hw, hh: _draw_boss_hi_base(hi, hw, hh, boss_key, style, il, flash),
        blur_radius=0.35,
    )
    _BOSS_BASE_CACHE[key] = surf
    return surf


def _draw_boss_face_overlay(
    screen,
    x,
    dy,
    r,
    lum,
    age,
    expression="idle",
    look_x=0.0,
    look_y=1.0,
    windup_progress=0.0,
    flash=False,
):
    dark_face = (250 if flash else int(lum)) > 115
    ink = (14, 14, 14) if dark_face else (246, 246, 246)
    glow = (252, 252, 252) if dark_face else (18, 18, 18)
    eye_dx = r * 0.33
    eye_y = dy - r * 0.16
    mouth_y = dy + r * 0.28
    px_off = clamp(look_x, -1.0, 1.0) * max(1.5, r * 0.08)
    py_off = clamp(look_y, -1.0, 1.0) * max(1.5, r * 0.06)

    if expression == "hurt":
        # Tightly squinted > < eyes + grimace
        ew = max(4, int(r * 0.18))
        eh = max(3, int(r * 0.12))
        lx, rx = int(x - eye_dx), int(x + eye_dx)
        ey = int(eye_y)
        pygame.draw.lines(screen, ink, False, [(lx - ew, ey - eh), (lx + ew // 2, ey), (lx - ew, ey + eh)], 3)
        pygame.draw.lines(screen, ink, False, [(rx + ew, ey - eh), (rx - ew // 2, ey), (rx + ew, ey + eh)], 3)
        mw = max(6, int(r * 0.34))
        my = int(mouth_y)
        pygame.draw.lines(
            screen,
            glow,
            False,
            [(int(x - mw), my), (int(x - mw * 0.35), my - 4), (int(x + mw * 0.35), my + 4), (int(x + mw), my)],
            2,
        )
        return

    if expression == "windup":
        # Pre-movement / pre-attack angry coiled expression!
        pulse = 0.5 + 0.5 * math.sin(age * 16.0)
        brow_drop = r * (0.10 + 0.10 * windup_progress)
        for s in (-1, 1):
            ex = x + s * eye_dx
            # Furrowed V-shaped eyebrows
            p1 = (int(ex - s * r * 0.22), int(eye_y - r * 0.26))
            p2 = (int(ex + s * r * 0.16), int(eye_y - r * 0.08 + brow_drop * 0.45))
            pygame.draw.line(screen, (10, 10, 10), p1, p2, 5)
            pygame.draw.line(screen, (250, 250, 250), p1, p2, 2)
            # Glowing narrowed focused eye slits tracking player
            draw_aa_ellipse(screen, (252, 252, 252), ex + px_off, eye_y + py_off, r * 0.15, r * 0.07)
            draw_aa_circle(screen, (12, 12, 12), ex + px_off * 1.4, eye_y + py_off * 1.4, max(2.0, r * 0.055))
        # Clenched snarling mouth with fangs
        mw = r * (0.44 + 0.10 * pulse)
        mh = r * (0.14 + 0.08 * windup_progress)
        draw_aa_ellipse(screen, (10, 10, 10), x, mouth_y, mw, mh)
        draw_aa_ring(screen, (244, 244, 244), x, mouth_y, max(4, int(mw * 0.85)), 1)
        # Anticipation sparks near temples
        sp_r = r * (1.08 + 0.16 * (1.0 - windup_progress))
        for ang in (-2.5, -0.65):
            sx1 = x + math.cos(ang) * sp_r
            sy1 = dy + math.sin(ang) * sp_r
            sx2 = x + math.cos(ang) * (sp_r + 7)
            sy2 = dy + math.sin(ang) * (sp_r + 7)
            pygame.draw.line(screen, (248, 248, 248), (int(sx1), int(sy1)), (int(sx2), int(sy2)), 2)
        return

    if expression in ("charge", "attack", "roar"):
        # Fierce wide eyes + roaring wide open mouth!
        for s in (-1, 1):
            ex = x + s * eye_dx
            # Sharp angled brows
            p1 = (int(ex - s * r * 0.24), int(eye_y - r * 0.30))
            p2 = (int(ex + s * r * 0.14), int(eye_y - r * 0.12))
            pygame.draw.line(screen, ink, p1, p2, 3)
            # Glowing intense pupils looking at target
            draw_aa_circle(screen, (252, 252, 252), ex + px_off, eye_y + py_off, max(2.8, r * 0.095))
            draw_aa_circle(screen, (12, 12, 12), ex + px_off * 1.25, eye_y + py_off * 1.25, max(1.6, r * 0.045))
        open_scale = 1.45 if expression == "roar" else 1.22
        mw = r * 0.52 * open_scale
        mh = r * 0.30 * open_scale
        draw_aa_ellipse(screen, (10, 10, 10), x, mouth_y + r * 0.04, mw, mh)
        # Bared fangs
        for fi in (-1, 0, 1):
            fx = x + fi * mw * 0.42
            draw_aa_poly(
                screen,
                (248, 248, 248),
                [(fx - 3, mouth_y - mh * 0.55), (fx + 3, mouth_y - mh * 0.55), (fx, mouth_y + 2)],
            )
        if expression == "roar":
            roar_r = int(r * (1.25 + 0.35 * (0.5 + 0.5 * math.sin(age * 12.0))))
            draw_aa_ring(screen, (246, 246, 246), x, dy, roar_r, 2)
        return

    # Idle: subtle blink & pupil tracking toward player
    blink_cycle = age % 4.6
    if blink_cycle > 4.44:
        for s in (-1, 1):
            ex = x + s * eye_dx
            pygame.draw.line(screen, ink, (int(ex - r * 0.16), int(eye_y)), (int(ex + r * 0.16), int(eye_y)), 3)
    else:
        for s in (-1, 1):
            ex = x + s * eye_dx
            draw_aa_circle(screen, glow, ex + px_off, eye_y + py_off, max(2.2, r * 0.068))


def draw_boss_visual(
    screen,
    boss_key,
    x,
    y,
    r,
    age=0.0,
    flash=False,
    phase=1,
    air_z=0.0,
    target_x=None,
    target_y=None,
    airborne=False,
    telegraph_r=0.0,
    segments=None,
    style=None,
    lum=None,
    expression="idle",
    scale_x=1.0,
    scale_y=1.0,
    look_x=0.0,
    look_y=1.0,
    windup_progress=0.0,
    telegraph_lines=None,
):
    cfg = BOSS_BASE_CONFIG.get(boss_key, {"style": "jumper", "lum": 182})
    if style is None:
        style = cfg["style"]
    if lum is None:
        lum = int(cfg["lum"])
    r = max(14, int(round(r)))

    if telegraph_lines:
        pulse_l = int(175 + 75 * (0.5 + 0.5 * math.sin(age * 18.0)))
        line_col = (pulse_l, pulse_l, pulse_l)
        for lx1, ly1, lx2, ly2 in telegraph_lines:
            pygame.draw.line(screen, (22, 22, 22), (int(lx1), int(ly1)), (int(lx2), int(ly2)), 5)
            pygame.draw.line(screen, line_col, (int(lx1), int(ly1)), (int(lx2), int(ly2)), 2)

    if telegraph_r > 0:
        tx = target_x if airborne and target_x is not None else x
        ty = target_y if airborne and target_y is not None else y
        draw_aa_ring(screen, (238, 238, 238), tx, ty, int(telegraph_r), 2)

    if style == "worm" and segments:
        for idx in range(len(segments) - 1, -1, -1):
            sx, sy = segments[idx]
            sr = max(10, int(r * (0.86 - idx * 0.08)))
            seg_lum = 248 if flash else (228 if boss_key == "frail" else max(74, lum - idx * 14))
            seg_disc = get_disc_sprite(sr, seg_lum, outline_lum=14, hi_lum=238)
            screen.blit(seg_disc, (int(round(sx - seg_disc.get_width() * 0.5)), int(round(sy - seg_disc.get_height() * 0.5))))
            if boss_key == "frail" and idx % 2 == 0:
                draw_aa_ring(screen, (24, 24, 24), sx, sy, int(sr * 0.62), 2)

    jit_x = math.sin(age * 46.0) * (2.6 * windup_progress) if expression == "windup" else 0.0
    jit_y = math.cos(age * 52.0) * (1.8 * windup_progress) if expression == "windup" else 0.0
    draw_x = x + jit_x
    dy = y - air_z + math.sin(age * 1.6) * 2.4 + jit_y

    gl = get_glow_surf(int(r * 2.25), 240, 82 if phase >= 2 else 52)
    screen.blit(gl, (int(round(draw_x - gl.get_width() * 0.5)), int(round(dy - gl.get_height() * 0.5))))

    if phase >= 2:
        draw_aa_ring(screen, (214, 214, 214), draw_x, dy, r + 8 + int(math.sin(age * 2.6) * 2.8), 1)
    if phase >= 3:
        draw_aa_ring(screen, (248, 248, 248), draw_x, dy, r + 14 + int(math.cos(age * 3.2) * 3.0), 1)

    if style == "eclipse":
        draw_aa_ring(screen, (244, 244, 244), draw_x, dy, r + 11, 2)
        for si in range(6):
            a = age * 0.85 + si * (math.pi / 3.0)
            bx = draw_x + math.cos(a) * (r + 15)
            by = dy + math.sin(a) * (r + 15)
            draw_aa_poly(screen, (244, 244, 244), [(bx + math.cos(a) * 6, by + math.sin(a) * 6), (bx - math.sin(a) * 4, by + math.cos(a) * 4), (bx + math.sin(a) * 4, by - math.cos(a) * 4)])
    elif style == "architect":
        for s in range(4):
            a = age * 0.65 + s * (math.pi * 0.5)
            px = draw_x + math.cos(a) * (r + 16)
            py = dy + math.sin(a) * (r + 16)
            pygame.draw.rect(screen, (18, 18, 18), (int(px - 6), int(py - 9), 12, 18), border_radius=3)
            pygame.draw.rect(screen, (232, 232, 232), (int(px - 4), int(py - 7), 8, 14), border_radius=2)
    elif style in ("angel", "ghost") or boss_key in ("satan", "fallen"):
        flap_spd = 5.4 if expression in ("windup", "charge", "attack") else 2.8
        wing_spread = r * (1.82 + 0.28 * math.sin(age * flap_spd))
        w_lum = 62 if boss_key in ("satan", "fallen") else 238
        for side in (-1, 1):
            draw_aa_poly(screen, (14, 14, 14), [(draw_x, dy), (draw_x + side * wing_spread, dy - r * 0.72), (draw_x + side * wing_spread * 0.72, dy + r * 0.28)])
            draw_aa_poly(screen, (w_lum, w_lum, w_lum), [(draw_x, dy), (draw_x + side * wing_spread * 0.92, dy - r * 0.64), (draw_x + side * wing_spread * 0.65, dy + r * 0.20)])
        if style == "angel":
            draw_aa_ellipse(screen, (248, 248, 248), draw_x, dy - r * 1.18, r * 0.76, r * 0.23)
            draw_aa_ellipse(screen, (18, 18, 18), draw_x, dy - r * 1.18, r * 0.42, r * 0.10)
    elif style == "horseman":
        draw_aa_poly(screen, (18, 18, 18), [(draw_x - r * 0.96, dy), (draw_x + r * 0.96, dy), (draw_x + r * 1.24, dy + r * 0.98), (draw_x - r * 1.24, dy + r * 0.98)])
        draw_aa_poly(screen, (112, 112, 112), [(draw_x - r * 0.86, dy + 2), (draw_x + r * 0.86, dy + 2), (draw_x + r * 1.12, dy + r * 0.88), (draw_x - r * 1.12, dy + r * 0.88)])
    elif style == "spider_boss":
        leg_spd = 7.2 if expression in ("windup", "charge") else 3.2
        swing = math.sin(age * leg_spd) * 6.0
        for s in (-1, 1):
            for li in range(4):
                jx = draw_x + s * (r * 1.02)
                jy = dy + (li - 1.5) * 9 - 8
                lx = draw_x + s * (r * 1.62)
                ly = dy + (li - 1.5) * 11 + (swing if li % 2 == 0 else -swing)
                pygame.draw.line(screen, (14, 14, 14), (int(draw_x), int(dy)), (int(jx), int(jy)), 5)
                pygame.draw.line(screen, (216, 216, 216), (int(draw_x), int(dy)), (int(jx), int(jy)), 2)
                pygame.draw.line(screen, (14, 14, 14), (int(jx), int(jy)), (int(lx), int(ly)), 4)
                pygame.draw.line(screen, (184, 184, 184), (int(jx), int(jy)), (int(lx), int(ly)), 1)

    if boss_key == "mega_satan":
        fist_bob = math.sin(age * (4.0 if expression != "idle" else 1.8)) * 6.5
        for side in (-1, 1):
            fx = draw_x + side * (r * 1.35)
            fy = dy + r * 0.25 + (fist_bob if side < 0 else -fist_bob)
            f_disc = get_disc_sprite(int(r * 0.45), 76 if not flash else 245, outline_lum=12, hi_lum=190)
            screen.blit(f_disc, (int(fx - f_disc.get_width() * 0.5), int(fy - f_disc.get_height() * 0.5)))

    base = _get_boss_base_sprite(boss_key, r, style, lum, flash=flash)
    sx_f = clamp(float(scale_x), 0.72, 1.34)
    sy_f = clamp(float(scale_y), 0.72, 1.34)
    if abs(sx_f - 1.0) > 0.03 or abs(sy_f - 1.0) > 0.03:
        nw = max(12, int(round(base.get_width() * sx_f)))
        nh = max(12, int(round(base.get_height() * sy_f)))
        try:
            base = pygame.transform.smoothscale(base, (nw, nh))
        except Exception:
            base = pygame.transform.scale(base, (nw, nh))
    screen.blit(base, (int(round(draw_x - base.get_width() * 0.5)), int(round(dy - base.get_height() * 0.5))))

    # Dynamic animated facial expression & pre-movement telegraph face
    _draw_boss_face_overlay(
        screen,
        draw_x,
        dy,
        r * ((sx_f + sy_f) * 0.5),
        lum,
        age,
        expression=expression,
        look_x=look_x,
        look_y=look_y,
        windup_progress=windup_progress,
        flash=flash,
    )

    if boss_key in ("peep", "blight_ovum"):
        eye_base = _get_peep_eye_sprite()
        ehw = eye_base.get_width() * 0.5
        ehh = eye_base.get_height() * 0.5
        for ei in range(2):
            a = age * 1.5 + ei * math.pi
            ex = draw_x + math.cos(a) * (r * 1.25)
            ey = dy + math.sin(a) * (r * 1.25)
            screen.blit(eye_base, (int(round(ex - ehw)), int(round(ey - ehh))))
            draw_aa_circle(screen, (16, 16, 16), ex + math.cos(a) * 1.5, ey + math.sin(a) * 1.5, 2.2)

    if style == "delirium":
        for gi in range(3):
            ga = age * 2.2 + gi * 2.1
            draw_aa_ring(screen, (236, 236, 236), draw_x + math.cos(ga) * 3, dy + math.sin(ga) * 3, r + 4 + gi * 3, 1)


def pick_floor_boss_key(floor_level, rng=None):
    r = rng if rng is not None else random
    lv = int(floor_level)
    if lv in FLOOR_BOSS_POOLS:
        return r.choice(FLOOR_BOSS_POOLS[lv])
    endless_pool = FLOOR_BOSS_POOLS[4] + FLOOR_BOSS_POOLS[5]
    return r.choice(endless_pool)


def _scale_boss_hp(base_hp, floor_level=1, floor_modifier=None):
    mult = 1.0 + max(0, floor_level - 1) * 0.24
    if floor_modifier is not None:
        mult *= floor_modifier.get("hp_mult", 1.0)
    return int(round(base_hp * mult))


class BossBase:
    def __init__(self, x, y, boss_key, floor_level=1, split_tier=0, radius_override=None, floor_modifier=None):
        cfg = BOSS_BASE_CONFIG.get(boss_key, {"hp": 240, "radius": 34, "speed": 2.3, "style": "jumper", "lum": 180})
        self.x = float(x)
        self.y = float(y)
        self.vx = 0.0
        self.vy = 0.0
        self.boss_key = boss_key
        self.name = tr_boss(boss_key)
        self.floor_level = int(floor_level)
        self.floor_modifier = floor_modifier
        self.split_tier = int(split_tier)
        self.style = cfg["style"]
        self.lum = int(cfg["lum"])
        base_r = radius_override if radius_override is not None else cfg["radius"]
        self.radius = float(base_r)
        base_hp = _scale_boss_hp(cfg["hp"], floor_level, floor_modifier)
        if split_tier == 1:
            base_hp = max(45, int(base_hp * 0.45))
        elif split_tier >= 2:
            base_hp = max(25, int(base_hp * 0.25))
        self.hp = float(base_hp)
        self.max_hp = float(base_hp)
        spd_mult = floor_modifier.get("spd_mult", 1.0) if floor_modifier else 1.0
        self.speed = float(cfg["speed"]) * spd_mult
        self.alive = True
        self.hit_flash = 0.0
        self.poison_timer = 0.0
        self.orbital_hit_cd = 0.0
        self.age = random.uniform(0.0, 12.0)
        self.state_timer = random.randint(28, 56)
        self.blink_cd = 105.0
        self.phase = 1
        self.prev_phase = 1
        self.airborne = False
        self.air_z = 0.0
        self.target_x = self.x
        self.target_y = self.y
        self.steals_coins = boss_key == "greed"
        self.segments = [(self.x - i * 16, self.y) for i in range(6)]
        self.telegraph_r = 0.0
        self.telegraph_lines = []

        # Expressive animation & pre-movement face state
        self.expression = "idle"
        self.anim_state = "idle"
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.look_x = 0.0
        self.look_y = 1.0
        self.windup_timer = 0.0
        self.windup_max = 20.0
        self.pending_action = None
        self.pending_dir = (0.0, 1.0)
        self.attack_cycle = random.randint(0, 5)
        self.combo_rem = 0
        self.roar_timer = 0.0
        self.attack_expr_timer = 0.0
        self.dash_trail_cd = 0.0

        # Unique per-boss signature profile, dialogue, arena walls & laser beams
        self.profile = get_boss_profile(boss_key)
        self.beams = []
        self.spawned_walls = []
        self.speech_text = ""
        self.speech_timer = 0.0
        self.intro_spoken = False
        self.phase_flash_timer = 0.0
        self.sig_cd = random.uniform(72.0, 102.0)
        self.beam_cd = random.uniform(108.0, 152.0)
        self.wall_cd = random.uniform(160.0, 215.0)
        self._last_room = None

    def say(self, text_pair, duration=155.0):
        if not text_pair:
            return
        lang = GAME_SETTINGS.get("language", "ru")
        if isinstance(text_pair, (tuple, list)):
            self.speech_text = str(text_pair[0] if lang == "ru" else text_pair[1])
        else:
            self.speech_text = str(text_pair)
        self.speech_timer = max(30.0, float(duration))

    def cleanup_arena(self, room=None):
        target_room = room if room is not None else self._last_room
        if target_room is not None and self.spawned_walls:
            wall_ids = {id(w) for w in self.spawned_walls}
            for w in self.spawned_walls:
                w.alive = False
            if hasattr(target_room, "obstacles"):
                target_room.obstacles = [
                    ob for ob in target_room.obstacles
                    if id(ob) not in wall_ids and ob.alive
                ]
        self.spawned_walls = []
        self.beams = []

    def take_damage(self, dmg, kx=0.0, ky=0.0):
        self.hp -= float(dmg)
        self.hit_flash = 6.0
        self.scale_x = 1.12
        self.scale_y = 0.88
        self.x += kx * 0.32
        self.y += ky * 0.32
        if self.hp <= 0:
            self.alive = False
            self.cleanup_arena()

    def get_light_source(self):
        if not self.alive:
            return None
        rad = 210 if any(b["windup"] <= 0 for b in self.beams) else 155
        lum = 195 if any(b["windup"] <= 0 for b in self.beams) else 145
        return (self.x, self.y - self.air_z, rad, lum)

    def get_split_children(self):
        if self.boss_key in ("fistula", "blastocyst", "envy") and self.split_tier < 2:
            nr = max(14, int(self.radius * 0.65))
            c1 = BossBase(self.x - 18, self.y, self.boss_key, self.floor_level, self.split_tier + 1, nr, self.floor_modifier)
            c2 = BossBase(self.x + 18, self.y, self.boss_key, self.floor_level, self.split_tier + 1, nr, self.floor_modifier)
            c1.vx, c1.vy = -2.4, -1.5
            c2.vx, c2.vy = 2.4, 1.5
            return [c1, c2]
        return []

    def _clamp_arena(self):
        r = self.radius
        if self.x - r < PLAYABLE_LEFT:
            self.x = PLAYABLE_LEFT + r
            self.vx = abs(self.vx)
        elif self.x + r > PLAYABLE_RIGHT:
            self.x = PLAYABLE_RIGHT - r
            self.vx = -abs(self.vx)
        if self.y - r < PLAYABLE_TOP:
            self.y = PLAYABLE_TOP + r
            self.vy = abs(self.vy)
        elif self.y + r > PLAYABLE_BOTTOM:
            self.y = PLAYABLE_BOTTOM - r
            self.vy = -abs(self.vy)

    def _safe_blink(self, player):
        for _ in range(8):
            nx = random.uniform(PLAYABLE_LEFT + self.radius + 36, PLAYABLE_RIGHT - self.radius - 36)
            ny = random.uniform(PLAYABLE_TOP + self.radius + 36, PLAYABLE_BOTTOM - self.radius - 36)
            if math.hypot(nx - player.x, ny - player.y) >= 165.0:
                self.x, self.y = nx, ny
                return

    def _fire_ring(self, projectiles, count=8, spd=4.4, offset=0.0, radius=6.5, homing=False):
        for i in range(count):
            a = offset + i * (2.0 * math.pi / count)
            projectiles.append(EnemyProjectile(self.x, self.y, math.cos(a) * spd, math.sin(a) * spd, radius=radius, homing=homing))

    def _fire_aimed(self, projectiles, px, py, spread_count=3, spread_step=0.2, spd=5.2, radius=6.5):
        base = math.atan2(py - self.y, px - self.x)
        half = (spread_count - 1) / 2.0
        for i in range(spread_count):
            a = base + (i - half) * spread_step
            projectiles.append(EnemyProjectile(self.x, self.y, math.cos(a) * spd, math.sin(a) * spd, radius=radius))

    def _fire_predictive(self, projectiles, player, spread_count=3, spread_step=0.17, spd=5.8, radius=6.5):
        dist = math.hypot(player.x - self.x, player.y - self.y)
        lead_t = clamp(dist / max(3.5, spd), 4.0, 26.0)
        tx = clamp(player.x + getattr(player, "vx", 0.0) * lead_t * 0.72, PLAYABLE_LEFT + 20, PLAYABLE_RIGHT - 20)
        ty = clamp(player.y + getattr(player, "vy", 0.0) * lead_t * 0.72, PLAYABLE_TOP + 20, PLAYABLE_BOTTOM - 20)
        self._fire_aimed(projectiles, tx, ty, spread_count=spread_count, spread_step=spread_step, spd=spd, radius=radius)

    def _fire_mortar_barrage(self, projectiles, player, count=3, blast_radius=52.0):
        for i in range(count):
            spread_r = 0.0 if i == 0 else random.uniform(42.0, 118.0)
            ang = random.uniform(0.0, math.pi * 2.0)
            tx = clamp(player.x + getattr(player, "vx", 0.0) * 14.0 + math.cos(ang) * spread_r, PLAYABLE_LEFT + 26, PLAYABLE_RIGHT - 26)
            ty = clamp(player.y + getattr(player, "vy", 0.0) * 14.0 + math.sin(ang) * spread_r, PLAYABLE_TOP + 26, PLAYABLE_BOTTOM - 26)
            projectiles.append(
                EnemyProjectile(
                    self.x,
                    self.y,
                    0.0,
                    0.0,
                    radius=7.5,
                    lobbed=True,
                    target_x=tx,
                    target_y=ty,
                    blast_radius=blast_radius,
                    total_frames=42.0 + i * 5.0,
                )
            )

    def _fire_spiral(self, projectiles, arms=4, waves=2, spd=4.4):
        for w in range(waves):
            w_spd = spd + w * 0.95
            w_off = self.age * 1.15 + w * 0.28
            for i in range(arms):
                a = w_off + i * (2.0 * math.pi / arms)
                projectiles.append(EnemyProjectile(self.x, self.y, math.cos(a) * w_spd, math.sin(a) * w_spd, radius=6.5))

    def _fire_beam_cross(self, projectiles, diag=False, spd=7.6):
        base_angles = [math.pi * 0.25 + i * (math.pi * 0.5) for i in range(4)] if diag else [i * (math.pi * 0.5) for i in range(4)]
        for a in base_angles:
            ca, sa = math.cos(a), math.sin(a)
            for seg in range(4):
                s_spd = spd + seg * 0.75
                projectiles.append(EnemyProjectile(self.x + ca * (seg * 12), self.y + sa * (seg * 12), ca * s_spd, sa * s_spd, radius=7.5))

    def _fire_homing_orbs(self, projectiles, count=3, spd=3.5):
        for i in range(count):
            a = self.age + i * (2.0 * math.pi / max(1, count))
            projectiles.append(EnemyProjectile(self.x, self.y, math.cos(a) * spd, math.sin(a) * spd, radius=8.0, homing=True, max_range=620.0))

    def _fire_shockwave_ring(self, projectiles, count=10, spd=4.9):
        self._fire_ring(projectiles, count, spd, offset=self.age, radius=7.0)
        self._fire_ring(projectiles, max(6, count // 2), spd * 0.68, offset=self.age + math.pi / max(1, count), radius=6.0)

    def _begin_windup(self, action, duration, ux, uy, telegraph_mode="ring", diag=False):
        self.pending_action = action
        self.windup_max = max(10.0, float(duration))
        self.windup_timer = self.windup_max
        self.pending_dir = (ux, uy)
        self.expression = "windup"
        self.anim_state = "windup"
        self.scale_x = 1.20
        self.scale_y = 0.82
        self.telegraph_lines = []
        if telegraph_mode == "dash":
            self.telegraph_lines = [(self.x, self.y, self.x + ux * 175.0, self.y + uy * 175.0)]
        elif telegraph_mode == "beam":
            angles = [math.pi * 0.25 + i * (math.pi * 0.5) for i in range(4)] if diag else [i * (math.pi * 0.5) for i in range(4)]
            for a in angles:
                self.telegraph_lines.append((self.x, self.y, self.x + math.cos(a) * 320.0, self.y + math.sin(a) * 320.0))
        elif telegraph_mode == "ring":
            self.telegraph_r = self.radius * 1.45
        if not getattr(self, "_preview_silent", False):
            play_sound("boss_windup", min_interval=0.28)

    def _execute_pending_action(self, player, enemy_projectiles, enemies_list):
        act = self.pending_action
        self.pending_action = None
        self.telegraph_lines = []
        ux, uy = self.pending_dir
        self.attack_expr_timer = 18.0
        self.scale_x = 0.84
        self.scale_y = 1.20
        silent = bool(getattr(player, "preview_mode", False))

        if act == "dash":
            self.expression = "charge"
            self.anim_state = "dashing"
            boost = 2.65 if self.phase >= 2 else 2.35
            self.vx = ux * (self.speed * boost)
            self.vy = uy * (self.speed * boost)
            self.dash_trail_cd = 6.0
            if self.phase >= 2:
                self._fire_aimed(enemy_projectiles, player.x, player.y, 3, 0.22, 5.0)
            if not silent:
                play_sound("boss_dash", min_interval=0.16)
            self.state_timer = 26 if self.combo_rem > 0 else (36 if self.phase >= 2 else 46)
        elif act == "leap":
            self.expression = "charge"
            self.anim_state = "jumping"
            self.airborne = True
            self.target_x = clamp(player.x + getattr(player, "vx", 0.0) * 14.0, PLAYABLE_LEFT + 54, PLAYABLE_RIGHT - 54)
            self.target_y = clamp(player.y + getattr(player, "vy", 0.0) * 14.0, PLAYABLE_TOP + 54, PLAYABLE_BOTTOM - 54)
            if not silent:
                play_sound("enemy_jump", min_interval=0.18)
            self.state_timer = 32 if self.phase >= 2 else 38
        elif act == "beam_plus":
            self.expression = "attack"
            self._fire_beam_cross(enemy_projectiles, diag=False, spd=7.8 if self.phase >= 2 else 6.8)
            if not silent:
                play_sound("boss_beam", min_interval=0.22)
            self.state_timer = 40 if self.phase >= 2 else 50
        elif act == "beam_x":
            self.expression = "attack"
            self._fire_beam_cross(enemy_projectiles, diag=True, spd=7.8 if self.phase >= 2 else 6.8)
            if not silent:
                play_sound("boss_beam", min_interval=0.22)
            self.state_timer = 40 if self.phase >= 2 else 50
        elif act == "mortar":
            self.expression = "attack"
            self._fire_mortar_barrage(enemy_projectiles, player, count=4 if self.phase >= 2 else 3)
            if self.phase >= 2:
                self._fire_predictive(enemy_projectiles, player, 3, 0.20, 5.4)
            if not silent:
                play_sound("boss_mortar", min_interval=0.20)
            self.state_timer = 44 if self.phase >= 2 else 54
        elif act == "spiral":
            self.expression = "attack"
            self._fire_spiral(enemy_projectiles, arms=6 if self.phase >= 2 else 4, waves=2 if self.phase >= 2 else 1, spd=4.5)
            if not silent:
                play_sound("boss_beam", min_interval=0.24)
            self.state_timer = 36 if self.phase >= 2 else 46
        elif act == "homing":
            self.expression = "attack"
            self._fire_homing_orbs(enemy_projectiles, count=4 if self.phase >= 2 else 3, spd=3.6)
            self._fire_ring(enemy_projectiles, 8, 4.2, offset=self.age)
            if not silent:
                play_sound("boss_homing", min_interval=0.24)
            self.state_timer = 48 if self.phase >= 2 else 58
        elif act == "worm_surge":
            self.expression = "charge"
            ang = math.atan2(uy, ux) + random.uniform(-0.28, 0.28)
            self.vx = math.cos(ang) * self.speed * (1.75 if self.phase >= 2 else 1.45)
            self.vy = math.sin(ang) * self.speed * (1.75 if self.phase >= 2 else 1.45)
            self._fire_ring(enemy_projectiles, 8 if self.phase >= 2 else 6, 4.2, offset=self.age)
            if not silent:
                play_sound("boss_dash", min_interval=0.20)
            self.state_timer = 26 if self.phase >= 2 else 34
        else:
            self.expression = "attack"
            self._fire_predictive(enemy_projectiles, player, 5 if self.phase >= 2 else 3, 0.16, 5.7)
            if not silent:
                play_sound("boss_slam", min_interval=0.20)
            self.state_timer = 42 if self.phase >= 2 else 52

    def update(self, player, room, enemy_projectiles, enemies_list, dt=1.0):
        if not self.alive:
            return
        self._last_room = room
        self._preview_silent = bool(getattr(player, "preview_mode", False))
        self.age += 0.12 * dt
        if self.hit_flash > 0:
            self.hit_flash = max(0.0, self.hit_flash - dt)
        if self.orbital_hit_cd > 0:
            self.orbital_hit_cd = max(0.0, self.orbital_hit_cd - dt)
        if self.blink_cd > 0:
            self.blink_cd = max(0.0, self.blink_cd - dt)
        if self.roar_timer > 0:
            self.roar_timer = max(0.0, self.roar_timer - dt)
        if self.attack_expr_timer > 0:
            self.attack_expr_timer = max(0.0, self.attack_expr_timer - dt)
        if self.speech_timer > 0:
            self.speech_timer = max(0.0, self.speech_timer - dt)
            if self.speech_timer <= 0:
                self.speech_text = ""
        if self.phase_flash_timer > 0:
            self.phase_flash_timer = max(0.0, self.phase_flash_timer - dt)
        if self.poison_timer > 0:
            self.poison_timer -= dt
            self.hp -= 0.08 * dt
            if self.hp <= 0:
                self.alive = False
                self.cleanup_arena(room)
                return

        if not self.intro_spoken and not self._preview_silent:
            self.intro_spoken = True
            self.say(self.profile.get("taunt_p1"), duration=145.0)

        self._update_beams_and_walls(room, dt)

        dx = player.x - self.x
        dy = player.y - self.y
        dist = math.hypot(dx, dy) or 1.0
        ux, uy = dx / dist, dy / dist
        self.look_x += (ux - self.look_x) * min(1.0, 0.18 * dt)
        self.look_y += (uy - self.look_y) * min(1.0, 0.18 * dt)

        # Smooth spring-back of squash & stretch
        breath = math.sin(self.age * 2.2) * 0.035
        target_sx = 1.0 + breath
        target_sy = 1.0 - breath
        if self.windup_timer > 0:
            target_sx, target_sy = 1.18, 0.84
        self.scale_x += (target_sx - self.scale_x) * min(1.0, 0.16 * dt)
        self.scale_y += (target_sy - self.scale_y) * min(1.0, 0.16 * dt)

        if self.hp < self.max_hp * 0.35:
            self.phase = 3
        elif self.hp < self.max_hp * 0.68:
            self.phase = 2

        # Phase transition roar, dialogue, arena walls & laser beams
        if self.phase > self.prev_phase:
            self.prev_phase = self.phase
            self.roar_timer = 28.0
            self.phase_flash_timer = 22.0
            self.expression = "roar"
            self.scale_x = 1.28
            self.scale_y = 0.76
            if not self._preview_silent:
                play_sound("boss_roar", min_interval=0.35)
                taunt_key = "taunt_p3" if self.phase >= 3 else "taunt_p2"
                self.say(self.profile.get(taunt_key), duration=175.0)
            self._fire_shockwave_ring(enemy_projectiles, 12 if self.phase >= 3 else 10, 4.8)
            wall_pat = self.profile.get("wall_pattern", "none")
            wall_min = int(self.profile.get("wall_min_phase", 2))
            if wall_pat != "none" and (self.phase >= wall_min or self.floor_level >= 3):
                self.spawn_arena_walls(room, player, wall_pat)
            elif self.floor_level >= 4 and self.phase >= 2:
                self.spawn_arena_walls(room, player, "pillars")
            beam_pat = self.profile.get("beam_pattern", "none")
            beam_min = int(self.profile.get("beam_min_phase", 2))
            if beam_pat != "none" and (self.phase >= beam_min or self.floor_level >= 3):
                self.spawn_beam_pattern(player, beam_pat, room=room)
            elif self.floor_level >= 3 and self.phase >= 2:
                self.spawn_beam_pattern(player, "cross" if self.phase >= 3 else "aimed", room=room)

        # Unique per-boss signature attack, dynamic wall & beam cadence
        if not self.airborne and self.windup_timer <= 0:
            self.sig_cd -= dt * (1.0 + (self.phase - 1) * 0.16)
            if self.sig_cd <= 0:
                sig_key = f"sig_p{min(3, self.phase)}"
                sig_id = self.profile.get(sig_key, self.profile.get("sig_p1", "flame_helix"))
                self._execute_signature_attack(sig_id, player, room, enemy_projectiles, enemies_list)
                if not self._preview_silent and self.speech_timer <= 0 and random.random() < 0.48:
                    self.say(self.profile.get("sig_call"), duration=75.0)
                base_sig = 112.0 if self.phase == 1 else (88.0 if self.phase == 2 else 70.0)
                self.sig_cd = max(52.0, base_sig - min(18.0, self.floor_level * 2.5))

            beam_pat = self.profile.get("beam_pattern", "none")
            beam_min = int(self.profile.get("beam_min_phase", 2))
            beams_enabled = (beam_pat != "none" and (self.phase >= beam_min or self.floor_level >= 3)) or (self.floor_level >= 3 and self.phase >= 2)
            if beams_enabled:
                self.beam_cd -= dt * (1.0 + (self.phase - 1) * 0.12)
                if self.beam_cd <= 0 and not self.beams:
                    eff_pat = beam_pat if beam_pat != "none" else ("quad_spin" if self.floor_level >= 5 else ("cross" if self.phase >= 3 else "sweep"))
                    self.spawn_beam_pattern(player, eff_pat, room=room)
                    self.beam_cd = max(95.0, 175.0 - self.phase * 18.0 - self.floor_level * 6.0)

            wall_pat = self.profile.get("wall_pattern", "none")
            wall_min = int(self.profile.get("wall_min_phase", 2))
            walls_enabled = (wall_pat != "none" and (self.phase >= wall_min or self.floor_level >= 3)) or (self.floor_level >= 4 and self.phase >= 2)
            if walls_enabled:
                self.wall_cd -= dt
                if self.wall_cd <= 0 and len(self.spawned_walls) < 4:
                    self.spawn_arena_walls(room, player, wall_pat if wall_pat != "none" else "pillars")
                    self.wall_cd = max(165.0, 260.0 - self.phase * 20.0)

        if self.phase == 3 and self.boss_key in _TELEPORT_BOSS_KEYS and self.blink_cd <= 0 and not self.airborne and self.windup_timer <= 0:
            self._safe_blink(player)
            self._fire_shockwave_ring(enemy_projectiles, 10, 4.9)
            self.attack_expr_timer = 16.0
            self.blink_cd = 135.0

        if self.phase == 3 and self.boss_key in _GRAVITY_PULL_KEYS and 60 < dist < 245:
            pr = player.get_effective_radius()
            player.x = clamp(player.x - ux * 0.62 * dt, PLAYABLE_LEFT + pr + 2, PLAYABLE_RIGHT - pr - 2)
            player.y = clamp(player.y - uy * 0.62 * dt, PLAYABLE_TOP + pr + 2, PLAYABLE_BOTTOM - pr - 2)
            if not player.has_effective_flight() and room is not None:
                for obs in room.obstacles:
                    if not obs.alive or not obs.blocks_movement:
                        continue
                    rx = max(obs.rect.left, min(player.x, obs.rect.right))
                    ry = max(obs.rect.top, min(player.y, obs.rect.bottom))
                    ox = player.x - rx
                    oy = player.y - ry
                    od = math.hypot(ox, oy)
                    if od < pr:
                        if od > 0.001:
                            player.x += (ox / od) * (pr - od)
                            player.y += (oy / od) * (pr - od)
                        else:
                            d_left = abs(player.x - obs.rect.left)
                            d_right = abs(obs.rect.right - player.x)
                            d_top = abs(player.y - obs.rect.top)
                            d_bot = abs(obs.rect.bottom - player.y)
                            m_min = min(d_left, d_right, d_top, d_bot)
                            if m_min == d_left:
                                player.x = obs.rect.left - pr - 1.0
                            elif m_min == d_right:
                                player.x = obs.rect.right + pr + 1.0
                            elif m_min == d_top:
                                player.y = obs.rect.top - pr - 1.0
                            else:
                                player.y = obs.rect.bottom + pr + 1.0
                player.x = clamp(player.x, PLAYABLE_LEFT + pr, PLAYABLE_RIGHT - pr)
                player.y = clamp(player.y, PLAYABLE_TOP + pr, PLAYABLE_BOTTOM - pr)

        # Handle active pre-movement / pre-attack windup telegraph
        if self.windup_timer > 0:
            self.windup_timer -= dt
            self.expression = "hurt" if self.hit_flash > 3.0 else "windup"
            if self.pending_action == "dash":
                self.pending_dir = (ux, uy)
                self.telegraph_lines = [(self.x, self.y, self.x + ux * 175.0, self.y + uy * 175.0)]
            if self.windup_timer <= 0:
                self.windup_timer = 0.0
                self.telegraph_r = 0.0
                self._execute_pending_action(player, enemy_projectiles, enemies_list)
            self._clamp_arena()
            return

        self.state_timer -= dt
        self.telegraph_r = 0.0
        self.telegraph_lines = []
        phase_spd = 1.0 + (self.phase - 1) * 0.14

        if self.style == "eclipse":
            orbit_x = ux * self.speed * 0.82 * phase_spd - uy * 1.25
            orbit_y = uy * self.speed * 0.82 * phase_spd + ux * 1.25
            self.x += orbit_x * dt
            self.y += orbit_y * dt
            if self.state_timer <= 0:
                self.attack_cycle = (self.attack_cycle + 1) % 3
                if self.attack_cycle == 0:
                    self._begin_windup("beam_plus" if self.phase < 2 else "beam_x", 20, ux, uy, "beam", diag=(self.phase >= 2))
                elif self.attack_cycle == 1:
                    self._begin_windup("spiral", 16, ux, uy, "ring")
                else:
                    self._begin_windup("mortar", 18, ux, uy, "ring")

        elif self.style == "architect":
            self.x += ux * self.speed * 0.72 * phase_spd * dt
            self.y += uy * self.speed * 0.72 * phase_spd * dt
            if self.state_timer <= 0:
                self.attack_cycle = (self.attack_cycle + 1) % 3
                if self.attack_cycle == 0:
                    self._begin_windup("beam_plus", 20, ux, uy, "beam", diag=False)
                elif self.attack_cycle == 1:
                    self._begin_windup("mortar", 18, ux, uy, "ring")
                else:
                    if len(enemies_list) < 4:
                        sx = clamp(self.x + random.uniform(-34, 34), PLAYABLE_LEFT + 22, PLAYABLE_RIGHT - 22)
                        sy = clamp(self.y + random.uniform(-34, 34), PLAYABLE_TOP + 22, PLAYABLE_BOTTOM - 22)
                        enemies_list.append(create_enemy(random.choice(["shadow_weaver", "ash_stalker", "hollow_bell"]), sx, sy, self.floor_level, self.floor_modifier))
                    self._fire_homing_orbs(enemy_projectiles, 3 if self.phase >= 2 else 2, 3.6)
                    self.attack_expr_timer = 16.0
                    self.state_timer = 52 if self.phase >= 2 else 66

        elif self.style == "jumper" or (self.boss_key == "mom" and self.airborne):
            if self.airborne:
                self.x += (self.target_x - self.x) * 0.11 * dt
                self.y += (self.target_y - self.y) * 0.11 * dt
                self.air_z = max(0.0, math.sin(max(0.0, self.state_timer) / 36.0 * math.pi) * 76.0)
                self.telegraph_r = self.radius * 1.45
                if self.state_timer <= 0:
                    self.airborne = False
                    self.air_z = 0.0
                    self.scale_x = 1.28
                    self.scale_y = 0.74
                    self.roar_timer = 14.0
                    self._fire_shockwave_ring(enemy_projectiles, 12 if self.phase >= 2 else 9, 4.7)
                    if self.phase >= 2:
                        self._fire_predictive(enemy_projectiles, player, 3, 0.18, 5.4)
                    self.state_timer = 38 if self.phase >= 2 else 48
            else:
                self.x += ux * self.speed * 0.72 * phase_spd * dt
                self.y += uy * self.speed * 0.72 * phase_spd * dt
                if self.state_timer <= 0:
                    self.attack_cycle = (self.attack_cycle + 1) % 3
                    if self.attack_cycle == 0:
                        self._begin_windup("leap", 18, ux, uy, "ring")
                    elif self.attack_cycle == 1:
                        self._begin_windup("mortar", 16, ux, uy, "ring")
                    else:
                        self._begin_windup("predictive", 14, ux, uy, "ring")

        elif self.style in ("charger", "horseman"):
            speed_mag = math.hypot(self.vx, self.vy)
            if speed_mag > self.speed * 1.45:
                self.dash_trail_cd -= dt
                if self.dash_trail_cd <= 0:
                    self.dash_trail_cd = 9.0
                    enemy_projectiles.append(EnemyProjectile(self.x, self.y, -self.vx * 0.18, -self.vy * 0.18, radius=6.0))
            if self.state_timer <= 0:
                if self.combo_rem > 0:
                    self.combo_rem -= 1
                    self._begin_windup("dash", 14, ux, uy, "dash")
                else:
                    self.attack_cycle = (self.attack_cycle + 1) % 3
                    if self.attack_cycle == 0:
                        self.combo_rem = 2 if self.phase >= 3 else (1 if self.phase >= 2 else 0)
                        self._begin_windup("dash", 18, ux, uy, "dash")
                    elif self.attack_cycle == 1:
                        self._begin_windup("predictive", 15, ux, uy, "ring")
                    else:
                        if self.phase >= 2:
                            self._begin_windup("beam_x", 20, ux, uy, "beam", diag=True)
                        else:
                            self._begin_windup("mortar", 16, ux, uy, "ring")
            self.x += self.vx * dt
            self.y += self.vy * dt
            self.vx *= 0.94 ** dt
            self.vy *= 0.94 ** dt
            self.x += ux * self.speed * 0.50 * phase_spd * dt
            self.y += uy * self.speed * 0.50 * phase_spd * dt

        elif self.style == "worm":
            if self.state_timer <= 0:
                self.attack_cycle = (self.attack_cycle + 1) % 3
                if self.attack_cycle == 0:
                    self._begin_windup("worm_surge", 15, ux, uy, "dash")
                elif self.attack_cycle == 1:
                    self._begin_windup("mortar", 15, ux, uy, "ring")
                else:
                    ang = math.atan2(dy, dx) + random.uniform(-0.35, 0.35)
                    self.vx = math.cos(ang) * self.speed * 1.45 * phase_spd
                    self.vy = math.sin(ang) * self.speed * 1.45 * phase_spd
                    self._fire_predictive(enemy_projectiles, player, 3, 0.18, 5.2)
                    self.attack_expr_timer = 14.0
                    self.state_timer = 30
            self.x += self.vx * dt
            self.y += self.vy * dt
            prev = (self.x, self.y)
            new_segs = []
            for sx, sy in self.segments:
                sdx, sdy = prev[0] - sx, prev[1] - sy
                sd = math.hypot(sdx, sdy) or 1.0
                if sd > 18:
                    sx += (sdx / sd) * (sd - 18)
                    sy += (sdy / sd) * (sd - 18)
                new_segs.append((sx, sy))
                prev = (sx, sy)
            self.segments = new_segs

        elif self.style == "summoner":
            self.x += ux * self.speed * 0.62 * phase_spd * dt
            self.y += uy * self.speed * 0.62 * phase_spd * dt
            if self.state_timer <= 0:
                self.attack_cycle = (self.attack_cycle + 1) % 3
                if self.attack_cycle == 0:
                    if len(enemies_list) < 5:
                        kind = "fly" if self.boss_key in ("duke", "husk") else "spider"
                        for _ in range(2 if self.phase >= 2 else 1):
                            if len(enemies_list) >= 5:
                                break
                            sx = clamp(self.x + random.uniform(-28, 28), PLAYABLE_LEFT + 20, PLAYABLE_RIGHT - 20)
                            sy = clamp(self.y + random.uniform(-28, 28), PLAYABLE_TOP + 20, PLAYABLE_BOTTOM - 20)
                            enemies_list.append(create_enemy(kind, sx, sy, self.floor_level, self.floor_modifier))
                    self._fire_shockwave_ring(enemy_projectiles, 8, 4.3)
                    self.attack_expr_timer = 18.0
                    self.state_timer = 58
                elif self.attack_cycle == 1:
                    self._begin_windup("homing", 18, ux, uy, "ring")
                else:
                    self._begin_windup("mortar", 16, ux, uy, "ring")

        elif self.style == "turret":
            self.x += ux * self.speed * 0.44 * phase_spd * dt
            self.y += uy * self.speed * 0.44 * phase_spd * dt
            if self.state_timer <= 0:
                self.attack_cycle = (self.attack_cycle + 1) % 3
                if self.boss_key == "mom" and self.attack_cycle == 0:
                    self._begin_windup("leap", 18, ux, uy, "ring")
                elif self.attack_cycle == 1:
                    self._begin_windup("beam_plus", 20, ux, uy, "beam", diag=False)
                elif self.attack_cycle == 2:
                    self._begin_windup("mortar", 16, ux, uy, "ring")
                else:
                    self._begin_windup("spiral", 16, ux, uy, "ring")

        elif self.style == "spider_boss":
            self.x += ux * self.speed * 0.72 * phase_spd * dt
            self.y += uy * self.speed * 0.72 * phase_spd * dt
            if self.state_timer <= 0:
                self.attack_cycle = (self.attack_cycle + 1) % 3
                if self.attack_cycle == 0:
                    self._begin_windup("leap", 16, ux, uy, "ring")
                elif self.attack_cycle == 1:
                    self._begin_windup("dash", 15, ux, uy, "dash")
                else:
                    if len(enemies_list) < 4:
                        sx = clamp(self.x + random.uniform(-24, 24), PLAYABLE_LEFT + 20, PLAYABLE_RIGHT - 20)
                        sy = clamp(self.y + random.uniform(-24, 24), PLAYABLE_TOP + 20, PLAYABLE_BOTTOM - 20)
                        enemies_list.append(create_enemy("spider", sx, sy, self.floor_level, self.floor_modifier))
                    self._fire_predictive(enemy_projectiles, player, 4, 0.22, 5.4)
                    self.attack_expr_timer = 16.0
                    self.state_timer = 44

        elif self.style in ("angel", "demon", "caster", "ghost"):
            orbit_x = ux * self.speed * 0.76 * phase_spd - uy * 1.05
            orbit_y = uy * self.speed * 0.76 * phase_spd + ux * 1.05
            self.x += orbit_x * dt
            self.y += orbit_y * dt
            if self.state_timer <= 0:
                self.attack_cycle = (self.attack_cycle + 1) % 4
                if self.attack_cycle == 0:
                    diag = (self.phase >= 2 and self.boss_key in ("uriel", "gabriel", "pale_seraph", "satan", "adversary"))
                    self._begin_windup("beam_x" if diag else "beam_plus", 20, ux, uy, "beam", diag=diag)
                elif self.attack_cycle == 1:
                    self._begin_windup("homing", 16, ux, uy, "ring")
                elif self.attack_cycle == 2:
                    self._begin_windup("dash", 16, ux, uy, "dash")
                else:
                    self._begin_windup("spiral", 16, ux, uy, "ring")

        elif self.style in ("bullet_hell", "delirium"):
            self.x += ux * self.speed * 0.62 * phase_spd * dt
            self.y += uy * self.speed * 0.62 * phase_spd * dt
            if self.state_timer <= 0:
                self.attack_cycle = (self.attack_cycle + 1) % 5
                if self.attack_cycle == 0:
                    self._begin_windup("spiral", 14, ux, uy, "ring")
                elif self.attack_cycle == 1:
                    self._begin_windup("beam_plus", 18, ux, uy, "beam", diag=False)
                elif self.attack_cycle == 2:
                    self._begin_windup("mortar", 16, ux, uy, "ring")
                elif self.attack_cycle == 3:
                    self._begin_windup("beam_x", 18, ux, uy, "beam", diag=True)
                else:
                    self._begin_windup("dash" if self.style == "delirium" else "homing", 16, ux, uy, "dash" if self.style == "delirium" else "ring")

        else:
            if abs(self.vx) < 0.2 and abs(self.vy) < 0.2:
                ang = random.uniform(0, math.pi * 2)
                self.vx = math.cos(ang) * self.speed * phase_spd
                self.vy = math.sin(ang) * self.speed * phase_spd
            self.x += self.vx * dt
            self.y += self.vy * dt
            if self.state_timer <= 0:
                self.attack_cycle = (self.attack_cycle + 1) % 3
                if self.attack_cycle == 0:
                    self._begin_windup("dash", 16, ux, uy, "dash")
                elif self.attack_cycle == 1:
                    self._begin_windup("mortar", 16, ux, uy, "ring")
                else:
                    self._begin_windup("predictive", 14, ux, uy, "ring")

        # Update dynamic facial expression from current state
        if self.hit_flash > 2.5:
            self.expression = "hurt"
        elif self.roar_timer > 0:
            self.expression = "roar"
        elif self.airborne or math.hypot(self.vx, self.vy) > self.speed * 1.45:
            self.expression = "charge"
        elif self.attack_expr_timer > 0:
            self.expression = "attack"
        else:
            self.expression = "idle"

        self._clamp_arena()

    def draw(self, screen, light_sources=None):
        if not self.alive:
            return
        r = max(16, int(round(self.radius)))
        draw_dynamic_shadow(
            screen,
            self.x,
            self.y + r * 0.85,
            int(r * 2.6 * self.scale_x),
            max(10, int(r * 0.92)),
            light_sources=light_sources,
            air_z=self.air_z,
            alpha=82 if self.airborne else 136,
        )
        wp = 1.0 - (self.windup_timer / max(1.0, self.windup_max)) if self.windup_timer > 0 else 0.0
        draw_boss_visual(
            screen,
            self.boss_key,
            self.x,
            self.y,
            r,
            age=self.age,
            flash=self.hit_flash > 0,
            phase=self.phase,
            air_z=self.air_z,
            target_x=self.target_x,
            target_y=self.target_y,
            airborne=self.airborne,
            telegraph_r=self.telegraph_r,
            segments=self.segments,
            style=self.style,
            lum=self.lum,
            expression=self.expression,
            scale_x=self.scale_x,
            scale_y=self.scale_y,
            look_x=self.look_x,
            look_y=self.look_y,
            windup_progress=wp,
            telegraph_lines=self.telegraph_lines,
        )

    def _raycast_beam_end(self, ox, oy, ang, max_len=1150.0, room=None):
        ca, sa = math.cos(ang), math.sin(ang)
        step = 12.0
        dist = 18.0
        obstacles = [
            ob for ob in (getattr(room, "obstacles", []) if room is not None else [])
            if getattr(ob, "alive", False) and getattr(ob, "kind", "") in ("pillar", "barrier", "rock")
        ]
        ex, ey = ox, oy
        while dist <= max_len:
            px = ox + ca * dist
            py = oy + sa * dist
            if px <= PLAYABLE_LEFT + 4 or px >= PLAYABLE_RIGHT - 4 or py <= PLAYABLE_TOP + 4 or py >= PLAYABLE_BOTTOM - 4:
                ex = clamp(px, PLAYABLE_LEFT + 4, PLAYABLE_RIGHT - 4)
                ey = clamp(py, PLAYABLE_TOP + 4, PLAYABLE_BOTTOM - 4)
                return ex, ey, True
            hit_obs = False
            for ob in obstacles:
                if ob.rect.collidepoint(int(px), int(py)):
                    ex, ey = px, py
                    hit_obs = True
                    break
            if hit_obs:
                return ex, ey, True
            ex, ey = px, py
            dist += step
        return ex, ey, False

    def spawn_beam_pattern(self, player, pattern="cross", room=None):
        if not pattern or pattern == "none":
            return
        base_ang = math.atan2(player.y - self.y, player.x - self.x)
        windup = max(34.0, 52.0 - self.phase * 4.0)
        active = 50.0 + self.phase * 8.0
        width = 13.0 if self.phase < 3 else 16.0
        specs = []
        if pattern == "aimed":
            specs.append((base_ang, 0.0, width))
        elif pattern == "sweep":
            sweep_dir = 1.0 if random.random() < 0.5 else -1.0
            specs.append((base_ang - sweep_dir * 0.52, sweep_dir * (0.017 + self.phase * 0.003), width))
        elif pattern == "twin_sweep":
            specs.append((base_ang - 0.45, 0.014 + self.phase * 0.002, width))
            specs.append((base_ang + 0.45, -(0.014 + self.phase * 0.002), width))
        elif pattern == "cross":
            for i in range(4):
                specs.append((i * (math.pi * 0.5), 0.0, width))
        elif pattern == "x_cross":
            for i in range(4):
                specs.append((math.pi * 0.25 + i * (math.pi * 0.5), 0.0, width))
        elif pattern == "quad_spin":
            spin = (0.013 + self.phase * 0.0025) * (1.0 if random.random() < 0.5 else -1.0)
            off = random.choice((0.0, math.pi * 0.25))
            for i in range(4):
                specs.append((off + i * (math.pi * 0.5), spin, width))
        elif pattern == "prism_star":
            spin = (0.010 + self.phase * 0.002) * (1.0 if random.random() < 0.5 else -1.0)
            count = 6 if self.phase >= 2 else 4
            for i in range(count):
                specs.append((i * (2.0 * math.pi / count), spin, max(11.0, width - 2.0)))
        else:
            specs.append((base_ang, 0.0, width))

        for ang, sweep, w in specs:
            ex, ey, hit = self._raycast_beam_end(self.x, self.y, ang, room=room)
            self.beams.append(
                {
                    "angle": ang,
                    "sweep": sweep,
                    "width": w,
                    "windup": windup,
                    "windup_max": windup,
                    "active": active,
                    "active_max": active,
                    "end_x": ex,
                    "end_y": ey,
                    "hit_wall": hit,
                }
            )
        if not self._preview_silent:
            play_sound("boss_windup", min_interval=0.25)

    def spawn_arena_walls(self, room, player, pattern="pillars"):
        if room is None or not hasattr(room, "obstacles") or not pattern or pattern == "none":
            return []
        from room import Obstacle

        # Clean dead refs first
        self.spawned_walls = [w for w in self.spawned_walls if getattr(w, "alive", False) and w in room.obstacles]
        max_walls = 8
        cx = (PLAYABLE_LEFT + PLAYABLE_RIGHT) * 0.5
        cy = (PLAYABLE_TOP + PLAYABLE_BOTTOM) * 0.5
        coords = []
        if pattern == "pillars":
            coords = [(cx - 210, cy - 115), (cx + 210, cy - 115), (cx - 210, cy + 115), (cx + 210, cy + 115)]
        elif pattern == "corridor":
            coords = [(cx - 180, cy - 90), (cx - 180, cy + 90), (cx + 180, cy - 90), (cx + 180, cy + 90)]
        elif pattern == "cross_cover":
            coords = [(cx - 150, cy), (cx + 150, cy), (cx, cy - 120), (cx, cy + 120)]
        elif pattern == "cage":
            coords = [
                (cx - 230, cy - 125), (cx + 230, cy - 125),
                (cx - 230, cy + 125), (cx + 230, cy + 125),
                (cx, cy - 135), (cx, cy + 135),
            ]
        elif pattern == "fortress":
            coords = [
                (cx - 250, cy - 90), (cx - 250, cy + 90),
                (cx + 250, cy - 90), (cx + 250, cy + 90),
                (cx - 95, cy - 130), (cx + 95, cy + 130),
            ]
        elif pattern == "labyrinth":
            coords = [
                (cx - 240, cy - 110), (cx - 140, cy - 110),
                (cx + 140, cy + 110), (cx + 240, cy + 110),
                (cx + 180, cy - 115), (cx - 180, cy + 115),
            ]
        elif pattern == "ring":
            for i in range(6):
                a = i * (math.pi / 3.0) + self.age * 0.25
                coords.append((cx + math.cos(a) * 215.0, cy + math.sin(a) * 132.0))
        else:
            coords = [(cx - 180, cy - 100), (cx + 180, cy + 100)]

        created = []
        for wx, wy in coords:
            if len(self.spawned_walls) >= max_walls:
                break
            wx = clamp(wx, PLAYABLE_LEFT + 92, PLAYABLE_RIGHT - 92)
            wy = clamp(wy, PLAYABLE_TOP + 86, PLAYABLE_BOTTOM - 86)
            if player is not None and math.hypot(wx - player.x, wy - player.y) < 96.0:
                continue
            if math.hypot(wx - self.x, wy - self.y) < self.radius + 46.0:
                continue
            too_close = False
            for ob in room.obstacles:
                if ob.alive and math.hypot(wx - ob.rect.centerx, wy - ob.rect.centery) < 52.0:
                    too_close = True
                    break
            if too_close:
                continue
            ob = Obstacle(int(wx), int(wy), kind="barrier", size=46)
            ob.hp = 6 + self.phase
            ob.max_hp = ob.hp
            ob.is_boss_wall = True
            ob.boss_wall_ttl = 580.0
            room.obstacles.append(ob)
            self.spawned_walls.append(ob)
            created.append(ob)
        return created

    def _update_beams_and_walls(self, room, dt):
        # Update temporary boss walls
        if self.spawned_walls:
            alive_walls = []
            expired_ids = set()
            for w in self.spawned_walls:
                if not getattr(w, "alive", False):
                    continue
                ttl = getattr(w, "boss_wall_ttl", 0.0) - dt
                w.boss_wall_ttl = ttl
                if ttl <= 0:
                    w.alive = False
                    expired_ids.add(id(w))
                else:
                    alive_walls.append(w)
            self.spawned_walls = alive_walls
            if expired_ids and room is not None and hasattr(room, "obstacles"):
                room.obstacles = [ob for ob in room.obstacles if id(ob) not in expired_ids and ob.alive]

        # Update telegraphing / active beams
        if not self.beams:
            return
        next_beams = []
        fired_now = False
        for b in self.beams:
            if b["windup"] > 0:
                prev_w = b["windup"]
                b["windup"] = max(0.0, b["windup"] - dt)
                if prev_w > 0 and b["windup"] <= 0:
                    fired_now = True
            else:
                b["angle"] += b["sweep"] * dt
                b["active"] -= dt
            ex, ey, hit = self._raycast_beam_end(self.x, self.y, b["angle"], room=room)
            b["end_x"] = ex
            b["end_y"] = ey
            b["hit_wall"] = hit
            if b["active"] > 0:
                next_beams.append(b)
        self.beams = next_beams
        if fired_now and not self._preview_silent:
            play_sound("boss_beam", min_interval=0.20)

    def check_beam_hits(self, players):
        """Return list of players hit by any active (post-windup) boss beam."""
        if not self.alive or not self.beams:
            return []
        hit_players = []
        ox, oy = self.x, self.y
        for b in self.beams:
            if b["windup"] > 0 or b["active"] <= 0:
                continue
            ex, ey = b["end_x"], b["end_y"]
            vx, vy = ex - ox, ey - oy
            seg_len2 = vx * vx + vy * vy
            if seg_len2 <= 1.0:
                continue
            half_w = b["width"] * 0.5
            for cp in players:
                if getattr(cp, "air_z", 0.0) > 8.0 or getattr(cp, "invuln_timer", 0.0) > 0:
                    continue
                t = clamp(((cp.x - ox) * vx + (cp.y - oy) * vy) / seg_len2, 0.0, 1.0)
                cx = ox + vx * t
                cy = oy + vy * t
                pr = cp.get_effective_radius() if hasattr(cp, "get_effective_radius") else getattr(cp, "radius", 14.0)
                if math.hypot(cp.x - cx, cp.y - cy) <= half_w + pr - 4.0:
                    if cp.take_damage(1):
                        hit_players.append(cp)
        return hit_players

    def _execute_signature_attack(self, sig_id, player, room, enemy_projectiles, enemies_list):
        dx = player.x - self.x
        dy = player.y - self.y
        dist = math.hypot(dx, dy) or 1.0
        ux, uy = dx / dist, dy / dist
        self.attack_expr_timer = 22.0
        self.scale_x = 1.18
        self.scale_y = 0.86

        if sig_id in ("volcano_leap", "seismic_stomp"):
            self._fire_shockwave_ring(enemy_projectiles, 10 + self.phase * 2, 4.9)
            self._fire_mortar_barrage(enemy_projectiles, player, count=2 + self.phase, blast_radius=54.0)
        elif sig_id in ("swarm_cough", "shell_burst"):
            self._fire_ring(enemy_projectiles, 8 + self.phase * 2, 4.3, offset=self.age)
            if len(enemies_list) < 5:
                kind = "fly" if sig_id == "swarm_cough" else "spider"
                sx = clamp(self.x + random.uniform(-34, 34), PLAYABLE_LEFT + 24, PLAYABLE_RIGHT - 24)
                sy = clamp(self.y + random.uniform(-34, 34), PLAYABLE_TOP + 24, PLAYABLE_BOTTOM - 24)
                enemies_list.append(create_enemy(kind, sx, sy, self.floor_level, self.floor_modifier))
        elif sig_id in ("burrow_trail", "juggernaut_ram", "masked_charge"):
            self.vx = ux * self.speed * (2.2 + self.phase * 0.2)
            self.vy = uy * self.speed * (2.2 + self.phase * 0.2)
            self._fire_aimed(enemy_projectiles, player.x, player.y, 3 + self.phase, 0.22, 5.2)
        elif sig_id in ("tether_whip", "twin_orbit_nova"):
            self._fire_spiral(enemy_projectiles, arms=4 + self.phase, waves=2, spd=4.4)
            self._fire_predictive(enemy_projectiles, player, 3, 0.16, 5.8)
        elif sig_id in ("locust_charge", "double_rush", "triple_dash_whistle", "ricochet_rush", "frenzy_chase"):
            self.vx = ux * self.speed * (2.5 + self.phase * 0.25)
            self.vy = uy * self.speed * (2.5 + self.phase * 0.25)
            self._fire_predictive(enemy_projectiles, player, 3 + (1 if self.phase >= 2 else 0), 0.18, 5.6)
        elif sig_id in ("slick_skid", "mire_charge", "mire_spiral"):
            self._fire_spiral(enemy_projectiles, arms=5 + self.phase, waves=2, spd=3.9)
            self._fire_mortar_barrage(enemy_projectiles, player, count=2, blast_radius=46.0)
        elif sig_id in ("void_orbs", "abyss_pits", "orbital_shields"):
            self._fire_homing_orbs(enemy_projectiles, count=2 + self.phase, spd=3.5)
            self._fire_ring(enemy_projectiles, 8, 4.4, offset=self.age)
        elif sig_id in ("ghost_barrage", "bone_ring_beam", "skeletal_beam", "forsaken"):
            self.spawn_beam_pattern(player, "quad_spin" if self.phase >= 2 else "cross", room=room)
            self._fire_ring(enemy_projectiles, 8, 4.1, offset=self.age)
        elif sig_id in ("web_snare", "silk_barrage"):
            self._fire_ring(enemy_projectiles, 10, 4.8, offset=0.0)
            self._fire_predictive(enemy_projectiles, player, 4, 0.22, 5.5)
        elif sig_id in ("ambush_erupt", "sinkhole_erupt", "tentacle_ambush"):
            self._safe_blink(player)
            self._fire_shockwave_ring(enemy_projectiles, 10 + self.phase * 2, 4.8)
        elif sig_id in ("plague_wake", "blight_mortar", "toxic_spores"):
            self._fire_mortar_barrage(enemy_projectiles, player, count=3 + self.phase, blast_radius=56.0)
            self._fire_ring(enemy_projectiles, 8, 3.6, offset=self.age)
        elif sig_id in ("necrotic_homing", "void_tears"):
            self._fire_homing_orbs(enemy_projectiles, count=3 + self.phase, spd=3.6)
            self._fire_spiral(enemy_projectiles, arms=4, waves=2, spd=4.2)
        elif sig_id in ("fortress_waves", "stomp_walls", "architect_maze"):
            self.spawn_arena_walls(room, player, self.profile.get("wall_pattern", "fortress"))
            self._fire_shockwave_ring(enemy_projectiles, 10, 4.7)
            self._fire_mortar_barrage(enemy_projectiles, player, count=2 + self.phase, blast_radius=50.0)
        elif sig_id in ("flame_helix", "heartbeat_hell", "continuum_veil"):
            self._fire_spiral(enemy_projectiles, arms=6 + self.phase, waves=2, spd=4.5)
            self._fire_ring(enemy_projectiles, 10, 3.8, offset=self.age + 0.35)
        elif sig_id in ("bone_curtain", "crimson_cross", "infernal_trident", "dark_orbit_beams"):
            self.spawn_beam_pattern(player, self.profile.get("beam_pattern", "twin_sweep"), room=room)
            self._fire_predictive(enemy_projectiles, player, 4, 0.16, 5.6)
        elif sig_id in ("bouncing_eyes", "shard_bounce", "cell_pulse", "fractal_ricochet"):
            self._fire_ring(enemy_projectiles, 8 + self.phase * 2, 5.2, offset=self.age, radius=7.5)
            self._fire_aimed(enemy_projectiles, player.x, player.y, 3, 0.26, 5.8, radius=7.5)
        elif sig_id in ("sync_lasers", "blackout_charge", "homing_brim", "glutton_beam"):
            self.spawn_beam_pattern(player, "twin_sweep" if self.phase >= 2 else "sweep", room=room)
            self._fire_aimed(enemy_projectiles, player.x, player.y, 3, 0.18, 5.4)
        elif sig_id in ("bomb_barrage", "blast_barrage"):
            self._fire_mortar_barrage(enemy_projectiles, player, count=4 + self.phase, blast_radius=62.0)
            self._fire_beam_cross(enemy_projectiles, diag=False, spd=6.8)
        elif sig_id in ("scythe_vortex", "headless_barrage", "gilded_fan"):
            self._fire_predictive(enemy_projectiles, player, 5 + self.phase, 0.15, 5.9)
            self._fire_spiral(enemy_projectiles, arms=4, waves=2, spd=4.8)
        elif sig_id in ("radiant_pillars", "archangel_cross", "seraph_x_beam", "diagonal_lasers", "krampus_spin", "twin_abyss_beam"):
            self.spawn_beam_pattern(player, self.profile.get("beam_pattern", "x_cross"), room=room)
            self._fire_shockwave_ring(enemy_projectiles, 10, 4.6)
        elif sig_id in ("cataclysm_gauntlet", "mimic_chaos", "eclipse_sanctum", "seraph_judgement"):
            self.spawn_beam_pattern(player, self.profile.get("beam_pattern", "prism_star"), room=room)
            if len(self.spawned_walls) < 4:
                self.spawn_arena_walls(room, player, self.profile.get("wall_pattern", "ring"))
            self._fire_spiral(enemy_projectiles, arms=6, waves=2, spd=4.7)
        else:
            self._fire_shockwave_ring(enemy_projectiles, 10, 4.6)

        if not self._preview_silent:
            play_sound("boss_slam", min_interval=0.22)

    def draw_post_light(self, screen, font=None):
        """Render pixel-noir laser beams (telegraph + active) and boss speech bubbles above darkness."""
        if not self.alive:
            return
        ox, oy = int(round(self.x)), int(round(self.y - self.air_z))
        # 1) Laser beams (telegraphing dashed lines & glowing pixel-stepped active beams)
        for b in self.beams:
            ex, ey = int(round(b["end_x"])), int(round(b["end_y"]))
            if b["windup"] > 0:
                prog = 1.0 - (b["windup"] / max(1.0, b["windup_max"]))
                pulse = 1 if (int(self.age * 16) % 2 == 0) else 0
                col = (238, 238, 238) if pulse else (145, 145, 145)
                # Pixel-stepped dashed warning line
                dx_b, dy_b = ex - ox, ey - oy
                seg_l = math.hypot(dx_b, dy_b) or 1.0
                steps = max(4, int(seg_l // 18))
                for i in range(0, steps, 2):
                    t0 = i / steps
                    t1 = min(1.0, (i + 1) / steps)
                    p0 = (int(ox + dx_b * t0) & ~1, int(oy + dy_b * t0) & ~1)
                    p1 = (int(ox + dx_b * t1) & ~1, int(oy + dy_b * t1) & ~1)
                    pygame.draw.line(screen, (14, 14, 14), p0, p1, 4)
                    pygame.draw.line(screen, col, p0, p1, 2)
                # Charging reticle at origin
                cr = max(4, int((1.0 - prog) * 18) + 4)
                pygame.draw.rect(screen, col, (ox - cr, oy - cr, cr * 2, cr * 2), 2)
            else:
                w = max(8, int(round(b["width"])))
                flick = 2 if (int(self.age * 24) % 2 == 0) else 0
                pygame.draw.line(screen, (12, 12, 12), (ox, oy), (ex, ey), w + 6)
                pygame.draw.line(screen, (185, 185, 185), (ox, oy), (ex, ey), w + flick)
                pygame.draw.line(screen, (250, 250, 250), (ox, oy), (ex, ey), max(4, w // 2))
                # Pixelated impact flare at wall/barrier
                if b.get("hit_wall"):
                    ir = max(6, w // 2 + flick)
                    pygame.draw.rect(screen, (14, 14, 14), (ex - ir - 2, ey - ir - 2, (ir + 2) * 2, (ir + 2) * 2))
                    pygame.draw.rect(screen, (246, 246, 246), (ex - ir, ey - ir, ir * 2, ir * 2))

        # 2) Crisp pixel-noir boss speech bubble
        if self.speech_timer > 0 and self.speech_text and font is not None:
            text_surf = font.render(self.speech_text, True, (242, 242, 242))
            pad_x, pad_y = 10, 5
            bw = text_surf.get_width() + pad_x * 2
            bh = text_surf.get_height() + pad_y * 2
            bx = int(clamp(ox - bw // 2, PLAYABLE_LEFT + 8, PLAYABLE_RIGHT - bw - 8))
            by = int(clamp(oy - int(self.radius) - bh - 20, PLAYABLE_TOP + 6, PLAYABLE_BOTTOM - bh - 8))
            # Pixel-noir double border box
            pygame.draw.rect(screen, (8, 8, 8), (bx - 2, by - 2, bw + 4, bh + 4))
            pygame.draw.rect(screen, (232, 232, 232), (bx - 1, by - 1, bw + 2, bh + 2), 1)
            pygame.draw.rect(screen, (16, 16, 16), (bx, by, bw, bh))
            # Tail pointing toward boss
            tx = int(clamp(ox, bx + 10, bx + bw - 10))
            pygame.draw.polygon(screen, (232, 232, 232), [(tx - 5, by + bh), (tx + 5, by + bh), (tx, by + bh + 6)])
            pygame.draw.polygon(screen, (16, 16, 16), [(tx - 3, by + bh - 1), (tx + 3, by + bh - 1), (tx, by + bh + 4)])
            screen.blit(text_surf, (bx + pad_x, by + pad_y))


def spawn_boss_for_room(room, boss_key, cx, cy, floor_level=1, floor_modifier=None):
    if boss_key == "gemini":
        b1 = BossBase(cx - 26, cy, "gemini", floor_level, floor_modifier=floor_modifier)
        b2 = BossBase(cx + 38, cy + 12, "steven", floor_level, radius_override=20, floor_modifier=floor_modifier)
        b2.hp = b2.max_hp = max(75, int(b1.max_hp * 0.45))
        return [b1, b2]
    if boss_key in ("gurglings", "turdlings", "sisters_vis"):
        b1 = BossBase(cx - 44, cy, boss_key, floor_level, floor_modifier=floor_modifier)
        b2 = BossBase(cx + 44, cy, boss_key, floor_level, floor_modifier=floor_modifier)
        b1.hp = b1.max_hp = max(90, int(b1.max_hp * 0.68))
        b2.hp = b2.max_hp = b1.max_hp
        return [b1, b2]
    return [BossBase(cx, cy, boss_key, floor_level, floor_modifier=floor_modifier)]
