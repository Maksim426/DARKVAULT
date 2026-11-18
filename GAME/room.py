from collections import deque
import math
import random
import pygame
from bullet import EnemyProjectile
from enemy import BlueFly, REGULAR_ENEMY_TYPES, create_enemy
from items import ItemPedestal, Pickup, get_random_item, tr_item_name
from settings import (
    DOOR_THICKNESS,
    DOOR_WIDTH,
    GAME_SETTINGS,
    PLAYABLE_BOTTOM,
    PLAYABLE_LEFT,
    PLAYABLE_RIGHT,
    PLAYABLE_TOP,
    ROOM_COLOR_SCHEMES,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    _finalize_alpha_surf,
    _finalize_surf,
    _prune_cache,
    clamp,
    draw_aa_circle,
    draw_aa_ellipse,
    draw_aa_poly,
    draw_aa_ring,
    draw_dynamic_shadow,
    get_disc_sprite,
    get_effects_config,
    get_floor_theme,
    get_glow_surf,
    get_particle_surf,
    get_shadow_surf,
    gray,
    render_4x_smooth,
)

BEGGAR_TYPES = [
    "coin_beggar",
    "devil_beggar",
    "key_master",
    "bomb_bum",
    "rotten_beggar",
    "battery_bum",
    "relic_beggar",
    "blood_bank_keeper",
]

SHOPKEEPER_VARIANTS = ["keeper_classic", "keeper_greedy", "keeper_silent", "keeper_twin"]

MACHINE_TYPES = [
    "slot_machine",
    "blood_donation",
    "fortune_teller",
    "restock_machine",
    "crane_game",
    "donation_box",
    "confessional",
    "computer_terminal",
]

LORE_INSCRIPTIONS = [
    (
        "МОНОЛИТ ПЕРВОГО ПЕПЛА",
        "Свет уходит туда, где камень помнит имена павших.",
        "MONOLITH OF FIRST ASH",
        "Light lingers wherever ancient stone remembers fallen names.",
    ),
    (
        "СТЕЛА ТИШИНЫ",
        "Не всякая тень враг; иные просто ищут забытый фонарь.",
        "STELE OF SILENCE",
        "Not every shadow is a foe; some merely seek a lost lantern.",
    ),
    (
        "СКРИЖАЛЬ ЗАТМЕНИЯ",
        "На пятом ярусе спит безликий Зодчий пепельных колонн.",
        "TABLET OF ECLIPSE",
        "On the fifth floor slumbers the faceless Architect of Ashen Pillars.",
    ),
    (
        "ЗНАК ОРАКУЛА",
        "Кто сохранит пламя среди руин, увидит врата бесконечной бездны.",
        "SIGN OF THE ORACLE",
        "Whoever guards their flame among ruins shall behold the Abyssal Gate.",
    ),
    (
        "ПАМЯТЬ ЛАБИРИНТА",
        "Монолиты питают фитиль странника и хранят эхо древних.",
        "MEMORY OF THE LABYRINTH",
        "Monoliths feed the wanderer's wick and preserve echoes of old.",
    ),
]

COMBAT_ROOM_THEMES = {
    "swarm_nest": {"min_floor": 1, "enemies": ("fly", "pooter"), "obstacles": ("rock", "poop", "urn")},
    "arachnid_den": {"min_floor": 1, "enemies": ("spider", "shadow_weaver"), "obstacles": ("rock", "urn", "pillar")},
    "husk_crypt": {"min_floor": 1, "enemies": ("gaper", "maggot"), "obstacles": ("rock", "pillar", "poop")},
    "mire_pit": {"min_floor": 1, "enemies": ("clot", "boil"), "obstacles": ("pit", "rock", "poop")},
    "ossuary": {"min_floor": 1, "enemies": ("bony", "horf"), "obstacles": ("pillar", "urn", "spike")},
    "leech_run": {"min_floor": 2, "enemies": ("leech", "hopper"), "obstacles": ("pit", "spike", "rock")},
    "wraith_nave": {"min_floor": 2, "enemies": ("whispering_phantom", "ash_stalker"), "obstacles": ("pillar", "brazier")},
    "vis_shrine": {"min_floor": 3, "enemies": ("vis", "bony"), "obstacles": ("pillar", "brazier", "spike")},
    "oculus_vault": {"min_floor": 3, "enemies": ("many_eyed_watcher", "hollow_bell"), "obstacles": ("pillar", "pit", "brazier")},
    "serpent_mimic": {"min_floor": 2, "enemies": ("thread_serpent", "mimic_double"), "obstacles": ("rock", "urn", "brazier")},
}


def pick_combat_theme_enemies(floor_level, rng, max_types=2):
    fl = max(1, int(floor_level))
    eligible = [
        (k, cfg) for k, cfg in COMBAT_ROOM_THEMES.items()
        if cfg["min_floor"] <= fl
    ]
    if not eligible:
        eligible = list(COMBAT_ROOM_THEMES.items())
    theme_key, cfg = rng.choice(eligible)
    pool = list(cfg["enemies"])
    if fl == 1 and theme_key == "arachnid_den":
        pool = ["spider"] if rng.random() < 0.65 else ["spider", "fly"]
    if len(pool) > max_types:
        pool = rng.sample(pool, max_types)
    if len(pool) == 2 and rng.random() < 0.28:
        pool = [rng.choice(pool)]
    return theme_key, pool


LAYOUT_TEMPLATES = {
    "empty": [],
    "pillars_4": [
        (340, 230, "pillar"),
        (940, 230, "pillar"),
        (340, 490, "pillar"),
        (940, 490, "pillar"),
    ],
    "colonnade_6": [
        (330, 225, "pillar"),
        (640, 225, "pillar"),
        (950, 225, "pillar"),
        (330, 495, "pillar"),
        (640, 495, "pillar"),
        (950, 495, "pillar"),
        (485, 360, "brazier"),
        (795, 360, "brazier"),
    ],
    "cross_rocks": [
        (460, 255, "rock"),
        (820, 255, "rock"),
        (460, 465, "rock"),
        (820, 465, "rock"),
        (270, 360, "urn"),
        (1010, 360, "urn"),
    ],
    "twin_pits": [
        (360, 240, "pit"),
        (360, 480, "pit"),
        (920, 240, "pit"),
        (920, 480, "pit"),
        (500, 360, "pillar"),
        (780, 360, "pillar"),
    ],
    "fortress": [
        (300, 210, "rock"),
        (354, 210, "rock"),
        (300, 264, "pillar"),
        (980, 210, "rock"),
        (926, 210, "rock"),
        (980, 264, "pillar"),
        (300, 510, "rock"),
        (354, 510, "rock"),
        (300, 456, "pillar"),
        (980, 510, "rock"),
        (926, 510, "rock"),
        (980, 456, "pillar"),
    ],
    "narrow_bridge": [
        (410, 170, "pit"),
        (410, 224, "pit"),
        (410, 278, "pit"),
        (410, 442, "pit"),
        (410, 496, "pit"),
        (410, 550, "pit"),
        (870, 170, "pit"),
        (870, 224, "pit"),
        (870, 278, "pit"),
        (870, 442, "pit"),
        (870, 496, "pit"),
        (870, 550, "pit"),
        (640, 220, "brazier"),
        (640, 500, "brazier"),
    ],
    "catwalk_chasm": [
        (290, 250, "pit"),
        (344, 250, "pit"),
        (290, 470, "pit"),
        (344, 470, "pit"),
        (936, 250, "pit"),
        (990, 250, "pit"),
        (936, 470, "pit"),
        (990, 470, "pit"),
        (510, 220, "pillar"),
        (770, 220, "pillar"),
        (510, 500, "pillar"),
        (770, 500, "pillar"),
    ],
    "stone_labyrinth": [
        (310, 215, "rock"),
        (364, 215, "rock"),
        (418, 215, "pillar"),
        (970, 505, "rock"),
        (916, 505, "rock"),
        (862, 505, "pillar"),
        (970, 215, "rock"),
        (970, 269, "rock"),
        (310, 505, "rock"),
        (310, 451, "rock"),
        (640, 230, "spike"),
        (640, 490, "spike"),
    ],
    "crossroads": [
        (470, 255, "pillar"),
        (470, 309, "rock"),
        (810, 255, "pillar"),
        (810, 309, "rock"),
        (470, 465, "pillar"),
        (470, 411, "rock"),
        (810, 465, "pillar"),
        (810, 411, "rock"),
        (250, 210, "urn"),
        (1030, 510, "urn"),
    ],
    "broken_sanctum": [
        (360, 220, "pillar"),
        (920, 220, "pillar"),
        (360, 500, "pillar"),
        (920, 500, "pillar"),
        (440, 360, "brazier"),
        (840, 360, "brazier"),
        (240, 250, "rock"),
        (1040, 470, "rock"),
    ],
    "diagonal": [
        (320, 220, "rock"),
        (420, 280, "spike"),
        (860, 440, "spike"),
        (960, 500, "rock"),
        (960, 220, "urn"),
        (320, 500, "urn"),
        (540, 470, "pillar"),
        (740, 250, "pillar"),
    ],
    "center_ring": [
        (480, 235, "pillar"),
        (800, 235, "pillar"),
        (480, 485, "pillar"),
        (800, 485, "pillar"),
        (640, 205, "spike"),
        (640, 515, "spike"),
    ],
    "arena_columns": [
        (290, 220, "pillar"),
        (290, 500, "pillar"),
        (500, 360, "pit"),
        (780, 360, "pit"),
        (990, 220, "pillar"),
        (990, 500, "pillar"),
    ],
    "corridor_pits": [
        (430, 230, "pit"),
        (430, 490, "pit"),
        (850, 230, "pit"),
        (850, 490, "pit"),
        (640, 230, "rock"),
        (640, 490, "rock"),
    ],
    "brazier_court": [
        (340, 240, "brazier"),
        (940, 240, "brazier"),
        (340, 480, "brazier"),
        (940, 480, "brazier"),
        (480, 360, "rock"),
        (800, 360, "rock"),
    ],
    "bastion": [
        (370, 230, "rock"),
        (424, 230, "pillar"),
        (856, 230, "pillar"),
        (910, 230, "rock"),
        (370, 490, "rock"),
        (424, 490, "pillar"),
        (856, 490, "pillar"),
        (910, 490, "rock"),
    ],
    "chambers": [
        (340, 360, "pillar"),
        (398, 360, "spike"),
        (882, 360, "spike"),
        (940, 360, "pillar"),
        (640, 215, "poop"),
        (640, 505, "poop"),
    ],
    "diamond_keep": [
        (640, 215, "pillar"),
        (640, 505, "pillar"),
        (450, 360, "pillar"),
        (830, 360, "pillar"),
        (300, 220, "urn"),
        (980, 220, "urn"),
        (300, 500, "urn"),
        (980, 500, "urn"),
    ],
    "spiral": [
        (340, 220, "pillar"),
        (540, 220, "spike"),
        (940, 260, "rock"),
        (940, 500, "pillar"),
        (740, 500, "spike"),
        (340, 460, "rock"),
    ],
}

_OBSTACLE_SPRITE_CACHE = {}
_SHOPKEEPER_CACHE = {}
_MACHINE_CACHE = {}
_BEGGAR_CACHE = {}
_MONOLITH_BODY_CACHE = {}
_DOOR_CACHE = {}
_DICE_CACHE = {}
_SACRIFICE_CACHE = {}
_FLAME_CACHE = {}
_PORTAL_CACHE = {}


def _get_flame_sprite(kind, step):
    key = (kind, int(step))
    cached = _FLAME_CACHE.get(key)
    if cached is not None:
        return cached
    _prune_cache(_FLAME_CACHE, 64)
    flick = int(step) / 5.0
    if kind == "brazier":
        r1 = 6.0 + flick * 2.0
        r2 = 3.5 + flick * 1.2
        sz = 24
        surf = pygame.Surface((sz, sz), pygame.SRCALPHA)
        cx = cy = sz // 2
        draw_aa_circle(surf, (220, 220, 220, 255), cx, cy, r1)
        draw_aa_circle(surf, (250, 250, 250, 255), cx, cy - 2, r2)
    else:
        r1 = 5.0 + flick * 1.6
        r2 = 2.5 + flick * 1.0
        sz = 20
        surf = pygame.Surface((sz, sz), pygame.SRCALPHA)
        cx = cy = sz // 2
        draw_aa_circle(surf, (215, 215, 215, 255), cx, cy, r1)
        draw_aa_circle(surf, (250, 250, 250, 255), cx, cy - 1, r2)
    surf = _finalize_alpha_surf(surf)
    _FLAME_CACHE[key] = surf
    return surf


def _get_beggar_sprite(key, s=1.0):
    s_q = max(5, int(round(s * 10)))
    ckey = (key, s_q)
    cached = _BEGGAR_CACHE.get(ckey)
    if cached is not None:
        return cached
    _prune_cache(_BEGGAR_CACHE, 64)
    sc = s_q / 10.0
    lum = {
        "coin_beggar": 212,
        "devil_beggar": 74,
        "key_master": 168,
        "bomb_bum": 150,
        "rotten_beggar": 130,
        "battery_bum": 182,
        "relic_beggar": 228,
        "blood_bank_keeper": 124,
    }.get(key, 184)
    body_lum = max(24, lum - 58)
    w = max(24, int(round(34 * sc)))
    h = max(32, int(round(44 * sc)))

    def _draw_hi(hi, hw, hh):
        cx = hw // 2
        cy = int(hh * 0.56)
        u = 4.0 * sc
        draw_aa_poly(
            hi,
            (body_lum, body_lum, body_lum, 255),
            [(cx - 13 * u, cy + 14 * u), (cx + 13 * u, cy + 14 * u), (cx + 9 * u, cy - 3 * u), (cx - 9 * u, cy - 3 * u)],
        )
        draw_aa_circle(hi, (14, 14, 14, 255), cx, cy - 10 * u, 12.5 * u)
        draw_aa_circle(hi, (lum, lum, lum, 255), cx, cy - 10 * u, 11 * u)
        draw_aa_circle(hi, (248, 248, 248, 160), cx - 3 * u, cy - 13 * u, 4.5 * u)
        eye_col = (248, 248, 248, 255) if lum < 110 else (18, 18, 18, 255)
        draw_aa_circle(hi, eye_col, cx - 4 * u, cy - 10 * u, 2 * u)
        draw_aa_circle(hi, eye_col, cx + 4 * u, cy - 10 * u, 2 * u)

    surf = render_4x_smooth(w, h, _draw_hi, blur_radius=0.25)
    _BEGGAR_CACHE[ckey] = surf
    return surf


def _get_monolith_body(s=1.0, activated=False):
    s_q = max(5, int(round(s * 10)))
    ckey = (s_q, bool(activated))
    cached = _MONOLITH_BODY_CACHE.get(ckey)
    if cached is not None:
        return cached
    _prune_cache(_MONOLITH_BODY_CACHE, 32)
    sc = s_q / 10.0
    w = max(28, int(round(42 * sc)))
    h = max(36, int(round(54 * sc)))
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    cx = w * 0.5
    cy = h * 0.58
    poly_pts = [
        (cx - 16 * sc, cy + 18 * sc),
        (cx + 16 * sc, cy + 18 * sc),
        (cx + 12 * sc, cy - 16 * sc),
        (cx, cy - 26 * sc),
        (cx - 12 * sc, cy - 16 * sc),
    ]
    draw_aa_poly(surf, (14, 14, 14, 255), poly_pts)
    draw_aa_poly(
        surf,
        (72, 72, 72, 255),
        [
            (cx - 12 * sc, cy + 15 * sc),
            (cx + 12 * sc, cy + 15 * sc),
            (cx + 9 * sc, cy - 13 * sc),
            (cx, cy - 21 * sc),
            (cx - 9 * sc, cy - 13 * sc),
        ],
    )
    glyph_lum = 248 if activated else 196
    lw = max(2, int(round(2 * sc)))
    pygame.draw.line(surf, (glyph_lum, glyph_lum, glyph_lum, 255), (int(cx), int(cy - 14 * sc)), (int(cx), int(cy + 10 * sc)), lw)
    pygame.draw.line(surf, (glyph_lum, glyph_lum, glyph_lum, 255), (int(cx - 6 * sc), int(cy - 3 * sc)), (int(cx + 6 * sc), int(cy - 3 * sc)), lw)
    surf = _finalize_alpha_surf(surf)
    res = (surf, cy)
    _MONOLITH_BODY_CACHE[ckey] = res
    return res


def _get_portal_sprite(step):
    cached = _PORTAL_CACHE.get(step)
    if cached is not None:
        return cached
    _prune_cache(_PORTAL_CACHE, 16)
    pulse = step / 5.0
    gl = get_glow_surf(int(36 + 6 * pulse), 248, 90)
    w = max(64, gl.get_width())
    h = max(64, gl.get_height())
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    cx, cy = w // 2, h // 2
    surf.blit(gl, (cx - gl.get_width() // 2, cy - gl.get_height() // 2))
    draw_aa_circle(surf, (242, 242, 242, 255), cx, cy, 22)
    draw_aa_circle(surf, (28, 28, 28, 255), cx, cy, 15)
    draw_aa_circle(surf, (250, 250, 250, 255), cx, cy, 8 + int(pulse * 3))
    surf = _finalize_alpha_surf(surf)
    _PORTAL_CACHE[step] = surf
    return surf


def _draw_obstacle_hi(hi, hw, hh, kind, lum_base, lum_hi):
    cx = hw // 2
    cy = hh // 2
    if kind == "pit":
        pygame.draw.rect(hi, (46, 46, 46, 230), (6, 6, hw - 12, hh - 12), border_radius=26)
        pygame.draw.rect(hi, (22, 22, 22, 245), (14, 14, hw - 28, hh - 28), border_radius=22)
        pygame.draw.rect(hi, (4, 4, 4, 255), (22, 22, hw - 44, hh - 44), border_radius=18)
        pygame.draw.rect(hi, (72, 72, 72, 210), (10, 10, hw - 20, hh - 20), 5, border_radius=24)
        pygame.draw.line(hi, (96, 96, 96, 175), (26, 16), (hw - 26, 16), 3)
    elif kind == "spike":
        pygame.draw.rect(hi, (24, 24, 24, 248), (12, 12, hw - 24, hh - 24), border_radius=16)
        pygame.draw.rect(hi, (88, 88, 88, 225), (12, 12, hw - 24, hh - 24), 4, border_radius=16)
        for sx in (cx - 38, cx + 38):
            for sy in (cy - 38, cy + 38):
                draw_aa_poly(hi, (12, 12, 12, 255), [(sx - 22, sy + 22), (sx + 22, sy + 22), (sx, sy - 28)])
                draw_aa_poly(hi, (206, 206, 206, 255), [(sx - 15, sy + 15), (sx + 15, sy + 15), (sx, sy - 22)])
                draw_aa_poly(hi, (246, 246, 246, 230), [(sx - 7, sy + 12), (sx, sy + 12), (sx, sy - 20)])
    elif kind == "pillar":
        pygame.draw.rect(hi, (14, 14, 14, 255), (16, 16, hw - 32, hh - 24), border_radius=18)
        pygame.draw.rect(hi, (max(24, lum_base - 18), max(24, lum_base - 18), max(24, lum_base - 18), 255), (22, 26, hw - 44, hh - 40), border_radius=12)
        for fx in range(-36, 40, 18):
            pygame.draw.line(hi, (36, 36, 36, 180), (cx + fx, 48), (cx + fx, hh - 24), 4)
        pygame.draw.rect(hi, (lum_base, lum_base, lum_base, 255), (18, 14, hw - 36, 52), border_radius=12)
        pygame.draw.rect(hi, (lum_hi, lum_hi, lum_hi, 235), (24, 18, hw - 48, 36), border_radius=8)
        pygame.draw.rect(hi, (min(255, lum_hi + 28), min(255, lum_hi + 28), min(255, lum_hi + 28), 210), (26, 20, hw - 52, 8), border_radius=4)
        pygame.draw.line(hi, (22, 22, 22, 190), (cx - 18, 28), (cx + 12, 48), 3)
    elif kind == "brazier":
        draw_aa_circle(hi, (14, 14, 14, 255), cx, cy + 8, 66)
        draw_aa_circle(hi, (62, 62, 62, 255), cx, cy + 6, 56)
        draw_aa_circle(hi, (18, 18, 18, 255), cx, cy + 2, 42)
        draw_aa_circle(hi, (158, 158, 158, 230), cx, cy, 26)
        pygame.draw.rect(hi, (112, 112, 112, 240), (cx - 54, cy, 108, 10), border_radius=4)
    elif kind == "urn":
        # Classical amphora vase with handles, pedestal foot, ornamental band, and specular rim
        # Left & right ceramic handles
        draw_aa_ring(hi, (12, 12, 12, 255), cx - 36, cy - 8, 22, 10)
        draw_aa_ring(hi, (max(48, lum_base + 12), max(48, lum_base + 12), max(48, lum_base + 12), 255), cx - 36, cy - 8, 18, 5)
        draw_aa_ring(hi, (12, 12, 12, 255), cx + 36, cy - 8, 22, 10)
        draw_aa_ring(hi, (max(48, lum_base + 12), max(48, lum_base + 12), max(48, lum_base + 12), 255), cx + 36, cy - 8, 18, 5)
        # Pedestal foot
        draw_aa_ellipse(hi, (12, 12, 12, 255), cx, cy + 62, 30, 12)
        draw_aa_ellipse(hi, (max(44, lum_base), max(44, lum_base), max(44, lum_base), 255), cx, cy + 60, 24, 8)
        # Outer amphora silhouette & tapered vessel body
        draw_aa_ellipse(hi, (12, 12, 12, 255), cx, cy + 12, 46, 52)
        body_lum = min(230, lum_base + 22)
        draw_aa_ellipse(hi, (body_lum, body_lum, body_lum, 255), cx, cy + 10, 40, 46)
        # Subtle lower-right shadow crescent
        dark_lum = max(28, body_lum - 36)
        draw_aa_ellipse(hi, (dark_lum, dark_lum, dark_lum, 130), cx + 10, cy + 20, 28, 34)
        # Carved ornamental horizontal band + geometric ticks
        band_lum = min(244, lum_hi + 16)
        pygame.draw.rect(hi, (26, 26, 26, 210), (cx - 38, cy + 4, 76, 14), border_radius=4)
        pygame.draw.line(hi, (band_lum, band_lum, band_lum, 235), (cx - 36, cy + 6), (cx + 36, cy + 6), 2)
        pygame.draw.line(hi, (band_lum, band_lum, band_lum, 235), (cx - 36, cy + 16), (cx + 36, cy + 16), 2)
        for dx in range(-28, 29, 14):
            draw_aa_poly(hi, (band_lum, band_lum, band_lum, 220), [(cx + dx, cy + 7), (cx + dx + 5, cy + 11), (cx + dx, cy + 15), (cx + dx - 5, cy + 11)])
        # Top-left ceramic gloss highlight + crack detail
        gl_lum = min(252, lum_hi + 42)
        draw_aa_ellipse(hi, (gl_lum, gl_lum, gl_lum, 225), cx - 14, cy - 8, 12, 18)
        draw_aa_ellipse(hi, (252, 252, 252, 180), cx - 17, cy - 16, 5, 8)
        pygame.draw.lines(hi, (20, 20, 20, 200), False, [(cx + 14, cy - 14), (cx + 8, cy - 2), (cx + 18, cy + 22), (cx + 12, cy + 34)], 3)
        # Sculpted neck collar & flanged rim
        pygame.draw.rect(hi, (12, 12, 12, 255), (cx - 20, cy - 42, 40, 14), border_radius=4)
        pygame.draw.rect(hi, (body_lum, body_lum, body_lum, 255), (cx - 15, cy - 40, 30, 10), border_radius=3)
        draw_aa_ellipse(hi, (12, 12, 12, 255), cx, cy - 44, 30, 12)
        draw_aa_ellipse(hi, (band_lum, band_lum, band_lum, 255), cx, cy - 45, 25, 9)
        draw_aa_ellipse(hi, (8, 8, 8, 255), cx, cy - 45, 16, 5)
    elif kind == "poop":
        draw_aa_ellipse(hi, (18, 18, 18, 255), cx, cy + 28, 68, 44)
        draw_aa_ellipse(hi, (lum_base, lum_base, lum_base, 255), cx, cy + 24, 60, 36)
        draw_aa_ellipse(hi, (lum_hi, lum_hi, lum_hi, 255), cx, cy - 4, 44, 28)
        hi_l = min(255, lum_hi + 28)
        draw_aa_circle(hi, (hi_l, hi_l, hi_l, 255), cx - 8, cy - 28, 24)
    elif kind == "barrier":
        # Reinforced iron-banded noir barricade
        pygame.draw.rect(hi, (14, 14, 14, 255), (14, 20, hw - 28, hh - 34), border_radius=14)
        plank_l = max(44, lum_base - 8)
        pygame.draw.rect(hi, (plank_l, plank_l, plank_l, 255), (20, 26, hw - 40, hh - 46), border_radius=10)
        band_l = min(236, lum_hi + 34)
        pygame.draw.rect(hi, (26, 26, 26, 240), (20, cy - 16, hw - 40, 32), border_radius=4)
        pygame.draw.line(hi, (band_l, band_l, band_l, 240), (24, cy - 12), (hw - 24, cy - 12), 4)
        pygame.draw.line(hi, (band_l, band_l, band_l, 240), (24, cy + 12), (hw - 24, cy + 12), 4)
        for rx in (cx - 46, cx, cx + 46):
            draw_aa_circle(hi, (14, 14, 14, 255), rx, cy, 8)
            draw_aa_circle(hi, (band_l, band_l, band_l, 255), rx, cy, 5)
        for sx in (cx - 44, cx + 44):
            draw_aa_poly(hi, (14, 14, 14, 255), [(sx - 12, 28), (sx + 12, 28), (sx, 6)])
            draw_aa_poly(hi, (band_l, band_l, band_l, 255), [(sx - 7, 26), (sx + 7, 26), (sx, 11)])
    elif kind == "turret":
        # Heavy octagonal stone monolith base for firing turret
        pts = [(cx - 56, cy + 54), (cx - 72, cy), (cx - 50, cy - 56), (cx + 50, cy - 56), (cx + 72, cy), (cx + 56, cy + 54)]
        draw_aa_poly(hi, (14, 14, 14, 255), pts)
        pts_in = [(cx + (px - cx) * 0.84, cy + (py - cy) * 0.84) for px, py in pts]
        draw_aa_poly(hi, (max(48, lum_base), max(48, lum_base), max(48, lum_base), 255), pts_in)
        draw_aa_circle(hi, (18, 18, 18, 255), cx, cy, 42)
        draw_aa_circle(hi, (min(220, lum_hi + 18), min(220, lum_hi + 18), min(220, lum_hi + 18), 255), cx, cy, 34)
        draw_aa_circle(hi, (26, 26, 26, 255), cx, cy, 22)
    else:
        pts = [
            (cx - 68, cy + 40),
            (cx - 76, cy - 16),
            (cx - 36, cy - 68),
            (cx + 44, cy - 64),
            (cx + 76, cy - 12),
            (cx + 64, cy + 48),
            (cx - 12, cy + 68),
        ]
        draw_aa_poly(hi, (14, 14, 14, 255), pts)
        pts_in = [(cx + (px - cx) * 0.86, cy + (py - cy) * 0.86) for px, py in pts]
        draw_aa_poly(hi, (lum_base, lum_base, lum_base, 255), pts_in)
        facet = [(cx - 52, cy - 12), (cx - 24, cy - 52), (cx + 32, cy - 48), (cx + 4, cy - 8)]
        draw_aa_poly(hi, (lum_hi, lum_hi, lum_hi, 255), facet)
        rim_l = min(255, lum_hi + 26)
        pygame.draw.line(hi, (rim_l, rim_l, rim_l, 210), (cx - 42, cy - 22), (cx + 24, cy - 46), 4)
        pygame.draw.line(hi, (24, 24, 24, 190), (cx + 8, cy - 10), (cx + 38, cy + 24), 4)
        if kind == "tinted_rock":
            pygame.draw.line(hi, (244, 244, 244, 245), (cx - 20, cy - 20), (cx + 20, cy + 20), 8)
            pygame.draw.line(hi, (244, 244, 244, 245), (cx + 20, cy - 20), (cx - 20, cy + 20), 8)


def _get_obstacle_sprite(kind, lum_base, lum_hi, size=48):
    key = (kind, int(lum_base), int(lum_hi), int(size))
    cached = _OBSTACLE_SPRITE_CACHE.get(key)
    if cached is not None:
        return cached
    surf = render_4x_smooth(
        size,
        size,
        lambda hi, hw, hh: _draw_obstacle_hi(hi, hw, hh, kind, lum_base, lum_hi),
        blur_radius=0.35,
    )
    _OBSTACLE_SPRITE_CACHE[key] = surf
    return surf


def _draw_shopkeeper_hi(hi, hw, hh, variant):
    cx = hw // 2
    cy = int(hh * 0.58)
    draw_aa_poly(
        hi,
        (14, 14, 14, 255),
        [(cx - 64, cy + 62), (cx + 64, cy + 62), (cx + 46, cy - 16), (cx - 46, cy - 16)],
    )
    robe_lum = 56 if variant == "keeper_silent" else (72 if variant == "keeper_greedy" else 64)
    draw_aa_poly(
        hi,
        (robe_lum, robe_lum, robe_lum, 255),
        [(cx - 56, cy + 56), (cx + 56, cy + 56), (cx + 40, cy - 10), (cx - 40, cy - 10)],
    )
    draw_aa_poly(
        hi,
        (198, 198, 198, 235),
        [(cx - 24, cy - 8), (cx, cy + 44), (cx + 24, cy - 8)],
    )
    draw_aa_circle(hi, (22, 22, 22, 255), cx, cy + 12, 6)
    draw_aa_circle(hi, (22, 22, 22, 255), cx, cy + 32, 6)

    if variant == "keeper_twin":
        for off_x, r_h in ((-24, 34), (24, 30)):
            draw_aa_circle(hi, (14, 14, 14, 255), cx + off_x, cy - 42, r_h + 6)
            draw_aa_circle(hi, (186, 186, 186, 255), cx + off_x, cy - 42, r_h)
            draw_aa_circle(hi, (222, 222, 222, 200), cx + off_x - 8, cy - 52, r_h * 0.5)
            draw_aa_circle(hi, (18, 18, 18, 255), cx + off_x - 10, cy - 44, 6)
            draw_aa_circle(hi, (18, 18, 18, 255), cx + off_x + 10, cy - 44, 6)
            draw_aa_ellipse(hi, (16, 16, 16, 255), cx + off_x, cy - 26, 12, 5)
        return

    draw_aa_circle(hi, (12, 12, 12, 255), cx, cy - 46, 48)
    head_lum = 196 if variant != "keeper_silent" else 174
    draw_aa_circle(hi, (head_lum, head_lum, head_lum, 255), cx, cy - 46, 42)
    draw_aa_circle(hi, (238, 238, 238, 190), cx - 12, cy - 58, 16)

    if variant == "keeper_classic":
        pygame.draw.rect(hi, (14, 14, 14, 255), (cx - 48, cy - 90, 96, 14), border_radius=5)
        pygame.draw.rect(hi, (26, 26, 26, 255), (cx - 32, cy - 134, 64, 48), border_radius=6)
        pygame.draw.rect(hi, (216, 216, 216, 255), (cx - 32, cy - 98, 64, 10), border_radius=2)
        draw_aa_circle(hi, (16, 16, 16, 255), cx - 15, cy - 48, 8)
        draw_aa_circle(hi, (16, 16, 16, 255), cx + 15, cy - 48, 8)
        draw_aa_ring(hi, (244, 244, 244, 255), cx + 15, cy - 48, 12, 3)
        pygame.draw.line(hi, (212, 212, 212, 220), (cx + 26, cy - 42), (cx + 34, cy - 14), 3)
        draw_aa_ellipse(hi, (18, 18, 18, 255), cx, cy - 24, 14, 6)
    elif variant == "keeper_greedy":
        draw_aa_poly(
            hi,
            (236, 236, 236, 255),
            [(cx - 34, cy - 82), (cx - 26, cy - 116), (cx - 8, cy - 92), (cx, cy - 122), (cx + 8, cy - 92), (cx + 26, cy - 116), (cx + 34, cy - 82)],
        )
        pygame.draw.rect(hi, (14, 14, 14, 255), (cx - 22, cy - 58, 10, 22), border_radius=3)
        pygame.draw.rect(hi, (14, 14, 14, 255), (cx + 12, cy - 58, 10, 22), border_radius=3)
        draw_aa_ellipse(hi, (22, 22, 22, 255), cx, cy - 24, 22, 9)
        pygame.draw.line(hi, (236, 236, 236, 255), (cx - 12, cy - 24), (cx + 12, cy - 24), 4)
        draw_aa_circle(hi, (196, 196, 196, 255), cx - 54, cy + 44, 18)
        draw_aa_circle(hi, (196, 196, 196, 255), cx + 54, cy + 44, 18)
    else:
        draw_aa_poly(
            hi,
            (32, 32, 32, 255),
            [(cx - 48, cy - 30), (cx - 38, cy - 92), (cx, cy - 112), (cx + 38, cy - 92), (cx + 48, cy - 30)],
        )
        pygame.draw.rect(hi, (236, 236, 236, 255), (cx - 36, cy - 56, 72, 16), border_radius=4)
        pygame.draw.line(hi, (20, 20, 20, 255), (cx - 14, cy - 24), (cx + 14, cy - 24), 4)
        for sx in (-8, 0, 8):
            pygame.draw.line(hi, (20, 20, 20, 255), (cx + sx, cy - 30), (cx + sx, cy - 18), 3)


def _get_shopkeeper_sprite(variant):
    cached = _SHOPKEEPER_CACHE.get(variant)
    if cached is not None:
        return cached
    surf = render_4x_smooth(
        48,
        56,
        lambda hi, hw, hh: _draw_shopkeeper_hi(hi, hw, hh, variant),
        blur_radius=0.32,
    )
    _SHOPKEEPER_CACHE[variant] = surf
    return surf


def _draw_machine_hi(hi, hw, hh, kind):
    cx = hw // 2
    cy = hh // 2
    # Outer chassis silhouette & base plinth
    pygame.draw.rect(hi, (10, 10, 10, 255), (14, 10, hw - 28, hh - 16), border_radius=24)
    pygame.draw.rect(hi, (36, 36, 36, 255), (20, hh - 26, hw - 40, 14), border_radius=6)

    if kind == "slot_machine":
        pygame.draw.rect(hi, (172, 172, 172, 255), (20, 16, hw - 40, hh - 30), border_radius=18)
        pygame.draw.rect(hi, (212, 212, 212, 255), (24, 18, hw - 48, hh - 40), border_radius=15)
        # Bevel trim + corner rivets
        pygame.draw.rect(hi, (246, 246, 246, 200), (26, 20, hw - 52, 10), border_radius=5)
        for rx_c, ry_c in ((30, 28), (hw - 30, 28), (30, hh - 30), (hw - 30, hh - 30)):
            draw_aa_circle(hi, (48, 48, 48, 255), rx_c, ry_c, 3)
        # Header marquee
        pygame.draw.rect(hi, (28, 28, 28, 255), (30, 26, hw - 60, 24), border_radius=8)
        pygame.draw.rect(hi, (240, 240, 240, 235), (34, 30, hw - 68, 16), border_radius=6)
        for mx in (cx - 28, cx, cx + 28):
            draw_aa_circle(hi, (24, 24, 24, 255), mx, 38, 4)
        # Recessed reel window + 3 drums
        pygame.draw.rect(hi, (18, 18, 18, 255), (32, 54, hw - 64, 58), border_radius=10)
        for idx, rx in enumerate((cx - 32, cx, cx + 32)):
            pygame.draw.rect(hi, (242, 242, 242, 255), (rx - 13, 60, 26, 46), border_radius=4)
            pygame.draw.line(hi, (186, 186, 186, 220), (rx - 12, 70), (rx + 12, 70), 2)
            pygame.draw.line(hi, (186, 186, 186, 220), (rx - 12, 96), (rx + 12, 96), 2)
            if idx == 1:
                draw_aa_poly(hi, (20, 20, 20, 255), [(rx - 6, 75), (rx + 7, 75), (rx - 2, 92)])
            else:
                draw_aa_circle(hi, (22, 22, 22, 255), rx, 83, 7)
                draw_aa_circle(hi, (242, 242, 242, 255), rx - 2, 81, 2)
        # Lower coin tray & buttons
        pygame.draw.rect(hi, (56, 56, 56, 255), (34, 120, hw - 68, 16), border_radius=5)
        for bx in (cx - 24, cx, cx + 24):
            draw_aa_circle(hi, (236, 236, 236, 255), bx, 128, 5)
        pygame.draw.rect(hi, (22, 22, 22, 255), (cx - 30, hh - 48, 60, 20), border_radius=6)
        pygame.draw.rect(hi, (96, 96, 96, 255), (cx - 24, hh - 42, 48, 8), border_radius=3)
        # Mechanical arm + ball knob
        pygame.draw.rect(hi, (72, 72, 72, 255), (hw - 20, 82, 10, 22), border_radius=4)
        pygame.draw.line(hi, (14, 14, 14, 255), (hw - 14, 88), (hw - 4, 44), 10)
        pygame.draw.line(hi, (236, 236, 236, 255), (hw - 14, 88), (hw - 4, 44), 6)
        draw_aa_circle(hi, (16, 16, 16, 255), hw - 4, 40, 14)
        draw_aa_circle(hi, (246, 246, 246, 255), hw - 4, 40, 10)
        draw_aa_circle(hi, (255, 255, 255, 230), hw - 7, 37, 3)

    elif kind == "blood_donation":
        pygame.draw.rect(hi, (118, 118, 118, 255), (22, 18, hw - 44, hh - 32), border_radius=18)
        pygame.draw.rect(hi, (152, 152, 152, 255), (26, 22, hw - 52, hh - 40), border_radius=14)
        pygame.draw.line(hi, (216, 216, 216, 175), (30, 24), (hw - 30, 24), 4)
        # Glass fluid cylinder + graduation marks
        pygame.draw.rect(hi, (16, 16, 16, 255), (36, 32, hw - 72, 62), border_radius=12)
        pygame.draw.rect(hi, (228, 228, 228, 255), (42, 54, hw - 84, 34), border_radius=8)
        pygame.draw.rect(hi, (250, 250, 250, 200), (44, 54, hw - 88, 6), border_radius=3)
        for gy in (42, 56, 70, 82):
            pygame.draw.line(hi, (150, 150, 150, 220), (42, gy), (52, gy), 3)
        pygame.draw.line(hi, (250, 250, 250, 170), (hw - 48, 38), (hw - 48, 86), 4)
        # Medical cross badge + screws
        draw_aa_circle(hi, (22, 22, 22, 255), cx, cy + 32, 22)
        draw_aa_circle(hi, (244, 244, 244, 255), cx, cy + 32, 18)
        pygame.draw.line(hi, (16, 16, 16, 255), (cx - 9, cy + 32), (cx + 9, cy + 32), 6)
        pygame.draw.line(hi, (16, 16, 16, 255), (cx, cy + 23), (cx, cy + 41), 6)
        # Intake braided tube & nozzle
        pygame.draw.line(hi, (16, 16, 16, 255), (12, 66), (40, 66), 10)
        pygame.draw.line(hi, (236, 236, 236, 255), (14, 66), (38, 66), 5)
        draw_aa_circle(hi, (214, 214, 214, 255), 14, 66, 6)

    elif kind == "fortune_teller":
        # Ornate carved wooden cabinet pedestal
        pygame.draw.rect(hi, (68, 68, 68, 255), (26, hh - 74, hw - 52, 52), border_radius=12)
        pygame.draw.rect(hi, (112, 112, 112, 255), (30, hh - 70, hw - 60, 44), 3, border_radius=10)
        pygame.draw.rect(hi, (186, 186, 186, 255), (36, hh - 64, hw - 72, 14), border_radius=5)
        pygame.draw.rect(hi, (18, 18, 18, 255), (cx - 22, hh - 42, 44, 14), border_radius=4)
        pygame.draw.rect(hi, (226, 226, 226, 255), (cx - 14, hh - 38, 28, 6), border_radius=2)
        # Clawed orb cradle
        draw_aa_poly(hi, (164, 164, 164, 255), [(cx - 38, cy + 22), (cx - 22, cy + 8), (cx + 22, cy + 8), (cx + 38, cy + 22)])
        # Crystal ball + mystical eye/aura
        draw_aa_ring(hi, (236, 236, 236, 190), cx, cy - 20, 56, 4)
        draw_aa_circle(hi, (14, 14, 14, 255), cx, cy - 20, 50)
        draw_aa_circle(hi, (196, 196, 196, 255), cx, cy - 20, 44)
        draw_aa_circle(hi, (232, 232, 232, 240), cx - 6, cy - 24, 32)
        draw_aa_ellipse(hi, (36, 36, 36, 210), cx, cy - 18, 18, 9)
        draw_aa_circle(hi, (248, 248, 248, 255), cx, cy - 18, 6)
        draw_aa_circle(hi, (254, 254, 254, 245), cx - 16, cy - 36, 10)

    elif kind == "restock_machine":
        pygame.draw.rect(hi, (156, 156, 156, 255), (22, 18, hw - 44, hh - 32), border_radius=16)
        pygame.draw.rect(hi, (206, 206, 206, 255), (28, 22, hw - 56, 10), border_radius=4)
        for rx_c, ry_c in ((32, 28), (hw - 32, 28), (32, hh - 28), (hw - 32, hh - 28)):
            draw_aa_circle(hi, (32, 32, 32, 255), rx_c, ry_c, 4)
        pygame.draw.rect(hi, (28, 28, 28, 255), (36, 36, hw - 72, hh - 64), border_radius=12)
        draw_aa_ring(hi, (96, 96, 96, 255), cx, cy - 2, 34, 3)
        draw_aa_ring(hi, (244, 244, 244, 255), cx, cy - 2, 26, 7)
        draw_aa_circle(hi, (210, 210, 210, 255), cx, cy - 2, 8)
        draw_aa_poly(hi, (250, 250, 250, 255), [(cx + 14, cy - 36), (cx + 38, cy - 24), (cx + 22, cy - 8)])
        draw_aa_poly(hi, (250, 250, 250, 255), [(cx - 14, cy + 32), (cx - 38, cy + 20), (cx - 22, cy + 4)])

    elif kind == "crane_game":
        pygame.draw.rect(hi, (156, 156, 156, 255), (20, 16, hw - 40, hh - 28), border_radius=16)
        pygame.draw.rect(hi, (220, 220, 220, 255), (28, 20, hw - 56, 14), border_radius=5)
        # Glass cabinet interior
        pygame.draw.rect(hi, (18, 18, 18, 255), (30, 36, hw - 60, 76), border_radius=8)
        pygame.draw.rect(hi, (96, 96, 96, 180), (30, 36, hw - 60, 76), 3, border_radius=8)
        # Diagonal glass sheen
        pygame.draw.line(hi, (230, 230, 230, 90), (40, 44), (66, 96), 6)
        # Winch & 3-prong claw + orbs
        pygame.draw.rect(hi, (176, 176, 176, 255), (cx - 12, 36, 24, 10), border_radius=3)
        pygame.draw.line(hi, (232, 232, 232, 255), (cx, 44), (cx, 66), 4)
        pygame.draw.line(hi, (232, 232, 232, 255), (cx, 64), (cx - 18, 82), 4)
        pygame.draw.line(hi, (232, 232, 232, 255), (cx, 64), (cx + 18, 82), 4)
        draw_aa_circle(hi, (246, 246, 246, 255), cx, 92, 12)
        draw_aa_circle(hi, (186, 186, 186, 255), cx - 24, 96, 9)
        draw_aa_circle(hi, (160, 160, 160, 255), cx + 26, 98, 8)
        # Control panel + joystick + chute
        pygame.draw.rect(hi, (48, 48, 48, 255), (32, 118, hw - 64, 24), border_radius=6)
        pygame.draw.line(hi, (232, 232, 232, 255), (cx - 24, 128), (cx - 24, 114), 4)
        draw_aa_circle(hi, (248, 248, 248, 255), cx - 24, 112, 6)
        draw_aa_circle(hi, (220, 220, 220, 255), cx + 20, 126, 6)
        pygame.draw.rect(hi, (20, 20, 20, 255), (cx - 20, 148, 40, 22), border_radius=5)

    elif kind == "donation_box":
        pygame.draw.rect(hi, (132, 132, 132, 255), (22, 32, hw - 44, hh - 46), border_radius=14)
        pygame.draw.rect(hi, (206, 206, 206, 255), (26, 34, hw - 52, 26), border_radius=10)
        pygame.draw.line(hi, (246, 246, 246, 210), (32, 38), (hw - 32, 38), 4)
        # Beveled coin slot
        pygame.draw.rect(hi, (62, 62, 62, 255), (cx - 28, 42, 56, 14), border_radius=4)
        pygame.draw.rect(hi, (10, 10, 10, 255), (cx - 22, 46, 44, 7), border_radius=2)
        # Iron corner bands & embossed seal
        pygame.draw.rect(hi, (68, 68, 68, 255), (26, 64, 10, hh - 82), border_radius=3)
        pygame.draw.rect(hi, (68, 68, 68, 255), (hw - 36, 64, 10, hh - 82), border_radius=3)
        draw_aa_circle(hi, (24, 24, 24, 255), cx, cy + 20, 20)
        draw_aa_circle(hi, (242, 242, 242, 255), cx, cy + 20, 16)
        pygame.draw.line(hi, (20, 20, 20, 255), (cx, cy + 11), (cx, cy + 29), 5)
        draw_aa_circle(hi, (20, 20, 20, 255), cx, cy + 16, 4)

    elif kind == "computer_terminal":
        # Monochrome CRT workstation + twin tape deck + keyboard console
        pygame.draw.rect(hi, (68, 68, 68, 255), (18, hh - 76, hw - 36, 60), border_radius=12)
        pygame.draw.rect(hi, (132, 132, 132, 255), (18, hh - 76, hw - 36, 14), border_radius=6)
        pygame.draw.line(hi, (224, 224, 224, 190), (24, hh - 73), (hw - 24, hh - 73), 3)
        # Tape drive bay & reels
        pygame.draw.rect(hi, (22, 22, 22, 255), (30, hh - 40, hw - 60, 18), border_radius=5)
        draw_aa_ring(hi, (200, 200, 200, 255), 52, hh - 31, 6, 2)
        draw_aa_ring(hi, (200, 200, 200, 255), 82, hh - 31, 6, 2)
        pygame.draw.rect(hi, (236, 236, 236, 255), (hw - 56, hh - 35, 16, 8), border_radius=2)
        # Keyboard deck
        pygame.draw.rect(hi, (28, 28, 28, 255), (34, hh - 62, hw - 68, 16), border_radius=4)
        for kx in range(42, hw - 44, 12):
            pygame.draw.rect(hi, (192, 192, 192, 240), (kx, hh - 58, 7, 4), border_radius=1)
        # CRT Monitor chassis
        pygame.draw.rect(hi, (152, 152, 152, 255), (24, 14, hw - 48, 108), border_radius=16)
        pygame.draw.rect(hi, (224, 224, 224, 220), (30, 18, hw - 60, 8), border_radius=4)
        pygame.draw.rect(hi, (16, 16, 16, 255), (36, 28, hw - 72, 76), border_radius=10)
        pygame.draw.rect(hi, (78, 78, 78, 220), (36, 28, hw - 72, 76), 3, border_radius=10)
        # Subtle glass scanlines & phosphor sheen
        for sy in range(36, 98, 10):
            pygame.draw.line(hi, (42, 42, 42, 180), (42, sy), (hw - 42, sy), 2)
        pygame.draw.line(hi, (236, 236, 236, 90), (44, 34), (62, 56), 4)
        draw_aa_circle(hi, (246, 246, 246, 255), hw - 42, 112, 4)

    else:
        # Confessional gothic booth
        pygame.draw.rect(hi, (56, 56, 56, 255), (22, 14, hw - 44, hh - 24), border_radius=16)
        pygame.draw.rect(hi, (124, 124, 124, 255), (28, 20, hw - 56, hh - 36), 5, border_radius=12)
        pygame.draw.rect(hi, (176, 176, 176, 255), (26, 20, hw - 52, 10), border_radius=4)
        # Carved grille lattice window
        pygame.draw.rect(hi, (18, 18, 18, 255), (cx - 26, 38, 52, 42), border_radius=8)
        for gx in range(cx - 16, cx + 18, 10):
            pygame.draw.line(hi, (164, 164, 164, 210), (gx, 42), (gx, 76), 2)
        for gy in (48, 59, 70):
            pygame.draw.line(hi, (164, 164, 164, 210), (cx - 22, gy), (cx + 22, gy), 2)
        # Bright cross emblem & curtain drape
        pygame.draw.line(hi, (246, 246, 246, 255), (cx, 44), (cx, 74), 5)
        pygame.draw.line(hi, (246, 246, 246, 255), (cx - 12, 55), (cx + 12, 55), 5)
        pygame.draw.rect(hi, (18, 18, 18, 255), (cx - 22, 92, 44, 52), border_radius=6)
        pygame.draw.line(hi, (88, 88, 88, 200), (cx - 8, 96), (cx - 8, 140), 3)
        pygame.draw.line(hi, (88, 88, 88, 200), (cx + 8, 96), (cx + 8, 140), 3)


def _get_machine_sprite(kind):
    cached = _MACHINE_CACHE.get(kind)
    if cached is not None:
        return cached
    surf = render_4x_smooth(
        48,
        52,
        lambda hi, hw, hh: _draw_machine_hi(hi, hw, hh, kind),
        blur_radius=0.32,
    )
    _MACHINE_CACHE[kind] = surf
    return surf


class Obstacle:
    def __init__(self, x, y, kind="rock", size=48):
        self.kind = kind
        self.size = int(size)
        self.rect = pygame.Rect(int(x - size // 2), int(y - size // 2), int(size), int(size))
        self.alive = True
        if kind == "turret":
            self.hp = 8
        elif kind == "barrier":
            self.hp = 5
        elif kind == "poop":
            self.hp = 3
        elif kind == "urn":
            self.hp = 3
        else:
            self.hp = 1
        self.max_hp = int(self.hp)
        self.fire_cd = random.uniform(70.0, 120.0) if kind == "turret" else 0.0
        self.aim_angle = 0.0
        self.fire_flash = 0.0
        self.blocks_movement = kind in ("rock", "tinted_rock", "pillar", "brazier", "urn", "poop", "pit", "barrier", "turret")
        self.blocks_tears = kind in ("rock", "tinted_rock", "pillar", "urn", "poop", "barrier", "turret")
        self.destructible = kind in ("rock", "tinted_rock", "urn", "poop", "barrier", "turret")
        self.casts_shadow = kind in ("rock", "tinted_rock", "pillar", "brazier", "urn", "poop", "barrier", "turret")
        self.age = (int(x) * 0.13 + int(y) * 0.07) % 6.28

    def damage(self, amount=1):
        if self.kind in ("poop", "urn", "barrier", "turret"):
            self.hp -= amount
            if self.hp <= 0:
                self.alive = False
                return True
        return False

    def explode(self):
        if self.destructible:
            self.alive = False
            return True
        return False

    def draw(self, screen, theme, time_acc=0.0, light_sources=None):
        if not self.alive:
            return
        if self.casts_shadow:
            if self.kind == "pillar":
                sw, sh_h, sy_off = int(self.size * 0.94), 20, -4
            elif self.kind == "urn":
                sw, sh_h, sy_off = int(self.size * 0.64), 14, -3
            elif self.kind == "poop":
                sw, sh_h, sy_off = int(self.size * 0.78), 16, -4
            elif self.kind == "brazier":
                sw, sh_h, sy_off = int(self.size * 0.76), 16, -4
            else:
                sw, sh_h, sy_off = int(self.size * 0.82), 16, -5
            draw_dynamic_shadow(
                screen,
                self.rect.centerx,
                self.rect.bottom + sy_off,
                sw,
                sh_h,
                light_sources=light_sources,
                air_z=0.0,
                alpha=128,
            )
        lum_base = gray(theme.get("poop" if self.kind == "poop" else "rock", (82, 82, 82)))[0]
        lum_hi = gray(theme.get("rock_hi", (126, 126, 126)))[0]
        if self.kind == "tinted_rock":
            lum_base = min(220, lum_base + 24)
            lum_hi = min(245, lum_hi + 28)
        spr = _get_obstacle_sprite(self.kind, lum_base, lum_hi, self.size)
        screen.blit(spr, self.rect.topleft)
        if self.kind == "brazier":
            flick = 0.5 + 0.5 * math.sin(time_acc * 0.24 + self.age)
            step = int(clamp(round(flick * 5.0), 0, 5))
            fl_spr = _get_flame_sprite("brazier", step)
            screen.blit(fl_spr, (self.rect.centerx - fl_spr.get_width() // 2, self.rect.centery - 2 - fl_spr.get_height() // 2))
        elif self.kind == "turret":
            cx, cy = self.rect.center
            bx = cx + math.cos(self.aim_angle) * (self.size * 0.44)
            by = cy + math.sin(self.aim_angle) * (self.size * 0.44)
            pygame.draw.line(screen, (14, 14, 14), (cx, cy), (int(bx), int(by)), 8)
            pygame.draw.line(screen, (218, 218, 218), (cx, cy), (int(bx), int(by)), 4)
            eye_lum = 252 if self.fire_flash > 0 else int(175 + 55 * (0.5 + 0.5 * math.sin(time_acc * 0.16 + self.age)))
            draw_aa_circle(screen, (eye_lum, eye_lum, eye_lum), cx, cy, 5.0)
        if self.kind in ("barrier", "turret") and self.hp < self.max_hp:
            bw = max(24, self.size - 8)
            bx = self.rect.centerx - bw // 2
            by = self.rect.top - 7
            pygame.draw.rect(screen, (16, 16, 16), (bx - 1, by - 1, bw + 2, 5))
            fw = max(1, int(bw * max(0.0, self.hp / max(1, self.max_hp))))
            pygame.draw.rect(screen, (228, 228, 228), (bx, by, fw, 3))


NPC_KEYS = [
    "pale_wanderer",
    "silent_shadow",
    "ancient_oracle",
    "lore_monolith",
    "coin_beggar",
    "devil_beggar",
    "key_master",
    "bomb_bum",
    "rotten_beggar",
    "battery_bum",
    "relic_beggar",
    "blood_bank_keeper",
    "shopkeeper",
    "slot_machine",
    "blood_donation",
    "fortune_teller",
    "restock_machine",
    "crane_game",
    "donation_box",
    "confessional",
    "computer_terminal",
]


def draw_computer_screen_fx(screen, x, y, scale=1.0, age=0.0, playing=True, track_idx=0):
    s = float(scale)
    sx0 = int(round(x - 12 * s))
    sy0 = int(round(y - 16 * s))
    sw = max(8, int(round(24 * s)))
    sh = max(6, int(round(13 * s)))
    if playing:
        gl = get_glow_surf(max(12, int(round(34 * s))), 242, 62)
        screen.blit(gl, (int(round(x - gl.get_width() * 0.5)), int(round(y - 10 * s - gl.get_height() * 0.5))))
        bars = 5
        bw = max(2, int(round(3 * s)))
        gap = max(3, int(round(4.6 * s)))
        bx_start = int(round(x - ((bars - 1) * gap) * 0.5))
        base_y = sy0 + sh - 1
        for bi in range(bars):
            phase = age * (1.8 + 0.35 * (track_idx % 3)) + bi * 1.15 + track_idx * 0.9
            val = 0.28 + 0.72 * (0.5 + 0.5 * math.sin(phase))
            bh = max(2, int(round((sh - 2) * val)))
            bx = bx_start + bi * gap - bw // 2
            lum = 212 + (bi % 2) * 34
            pygame.draw.rect(screen, (lum, lum, lum), (bx, base_y - bh, bw, bh), border_radius=1)
    else:
        if int(age * 1.8) % 2 == 0:
            pygame.draw.rect(screen, (148, 148, 148), (sx0 + 3, sy0 + 4, max(3, int(4 * s)), max(2, int(2 * s))))


def draw_npc_visual(screen, key, x, y, scale=1.0, age=0.0, activated=False):
    s = float(scale)
    if key == "lore_monolith":
        pulse = 0.5 + 0.5 * math.sin(age * 2.0)
        gl_r = int(round((36 + 6 * round(pulse * 4.0) * 0.25) * s))
        gl = get_glow_surf(gl_r, 240, 88 if activated else 58)
        screen.blit(gl, (int(round(x - gl.get_width() * 0.5)), int(round(y - 6 * s - gl.get_height() * 0.5))))
        body, cy_off = _get_monolith_body(s, activated)
        screen.blit(body, (int(round(x - body.get_width() * 0.5)), int(round(y - cy_off))))
        return

    if key in ("pale_wanderer", "silent_shadow", "ancient_oracle"):
        hover = math.sin(age * 1.4) * 2.5 * s
        dy = y + hover
        gl = get_glow_surf(int(round(34 * s)), 240, 68 if not activated else 36)
        screen.blit(gl, (int(round(x - gl.get_width() * 0.5)), int(round(dy - 6 * s - gl.get_height() * 0.5))))
        if key == "silent_shadow":
            lum = 44
        elif key == "ancient_oracle":
            lum = 150
        else:
            lum = 216
        draw_aa_poly(screen, (20, 20, 20), [(x - 14 * s, dy + 16 * s), (x + 14 * s, dy + 16 * s), (x + 9 * s, dy - 4 * s), (x - 9 * s, dy - 4 * s)])
        draw_aa_poly(screen, (lum, lum, lum), [(x - 11 * s, dy + 14 * s), (x + 11 * s, dy + 14 * s), (x + 7 * s, dy - 2 * s), (x - 7 * s, dy - 2 * s)])
        head = get_disc_sprite(max(8, int(round(11 * s))), lum, outline_lum=14, hi_lum=248)
        screen.blit(head, (int(round(x - head.get_width() * 0.5)), int(round(dy - 10 * s - head.get_height() * 0.5))))
        if key == "pale_wanderer":
            pygame.draw.line(screen, (220, 220, 220), (int(x + 13 * s), int(dy + 15 * s)), (int(x + 13 * s), int(dy - 18 * s)), max(2, int(round(2 * s))))
            draw_aa_circle(screen, (248, 248, 248), x + 13 * s, dy - 18 * s, 4 * s)
        elif key == "ancient_oracle":
            draw_aa_ring(screen, (242, 242, 242), x, dy - 12 * s, int(round(16 * s)), max(1, int(round(s))))
        eye_c = (248, 248, 248) if lum < 100 else (18, 18, 18)
        draw_aa_circle(screen, eye_c, x - 4 * s, dy - 10 * s, 2 * s)
        draw_aa_circle(screen, eye_c, x + 4 * s, dy - 10 * s, 2 * s)
        return

    if key in BEGGAR_TYPES:
        spr = _get_beggar_sprite(key, s)
        screen.blit(spr, (int(round(x - spr.get_width() * 0.5)), int(round(y - spr.get_height() * 0.56))))
        return

    if key in ("shopkeeper", "keeper_classic", "keeper_greedy", "keeper_silent", "keeper_twin"):
        variant = "keeper_classic" if key == "shopkeeper" else key
        spr = _get_shopkeeper_sprite(variant)
        if abs(s - 1.0) > 0.04:
            spr = pygame.transform.smoothscale(spr, (max(8, int(round(spr.get_width() * s))), max(8, int(round(spr.get_height() * s)))))
        bob = math.sin(age * 1.4) * 1.4 * s
        screen.blit(spr, (int(round(x - spr.get_width() * 0.5)), int(round(y - spr.get_height() * 0.56 + bob))))
        return

    mkey = key if key in MACHINE_TYPES else "slot_machine"
    spr = _get_machine_sprite(mkey)
    if abs(s - 1.0) > 0.04:
        spr = pygame.transform.smoothscale(spr, (max(8, int(round(spr.get_width() * s))), max(8, int(round(spr.get_height() * s)))))
    screen.blit(spr, (int(round(x - spr.get_width() * 0.5)), int(round(y - spr.get_height() * 0.5))))
    if mkey == "fortune_teller":
        pulse = 0.5 + 0.5 * math.sin(age * 2.2)
        draw_aa_circle(screen, (250, 250, 250), x, y - 4 * s, (2.4 + pulse * 1.4) * s)
    elif mkey == "computer_terminal" and activated:
        draw_computer_screen_fx(screen, x, y, scale=s, age=age, playing=True, track_idx=0)


class LoreMonolith:
    def __init__(self, x, y, title=None, text=None, title_en=None, text_en=None):
        self.x = float(x)
        self.y = float(y)
        self.radius = 24.0
        self.alive = True
        self.activated = False
        self.age = random.uniform(0.0, 6.28)
        chosen = random.choice(LORE_INSCRIPTIONS)
        self.title = title or chosen[0]
        self.text = text or chosen[1]
        self.title_en = title_en or chosen[2]
        self.text_en = text_en or chosen[3]

    def update(self, dt=1.0):
        self.age += 0.065 * dt

    def interact(self, player):
        if not self.alive:
            return None
        first = not self.activated
        self.activated = True
        player.lantern_fuel = min(1.35, getattr(player, "lantern_fuel", 1.0) + (0.50 if first else 0.12))
        if first:
            if hasattr(player, "add_charge"):
                player.add_charge(1)
            else:
                player.active_charge = min(player.max_charge, player.active_charge + 1)
            if GAME_SETTINGS.get("language", "ru") == "en":
                return (self.title_en, self.text_en)
            return (self.title, self.text)
        return None

    def get_light_source(self):
        if not self.alive:
            return None
        rad = 120 if self.activated else 96
        return (self.x, self.y - 8, rad, 175 if self.activated else 135)

    def draw(self, screen):
        if not self.alive:
            return
        sh = get_shadow_surf(44, 16, 128)
        screen.blit(sh, (int(round(self.x - sh.get_width() * 0.5)), int(round(self.y + 18 - sh.get_height() * 0.5))))
        draw_npc_visual(screen, "lore_monolith", self.x, self.y, scale=1.0, age=self.age, activated=self.activated)


class MysticalNPC:
    def __init__(self, x, y, kind="pale_wanderer"):
        self.x = float(x)
        self.y = float(y)
        self.kind = kind
        self.radius = 22.0
        self.alive = True
        self.used = False
        self.age = random.uniform(0.0, 6.28)
        self.cooldown = 0.0

    def update(self, dt=1.0):
        self.age += 0.075 * dt
        if self.cooldown > 0:
            self.cooldown = max(0.0, self.cooldown - dt)

    def get_light_source(self):
        if not self.alive:
            return None
        return (self.x, self.y - 8, 108, 150)

    def interact(self, player, room):
        if not self.alive or self.used or self.cooldown > 0:
            return None
        self.cooldown = 36.0
        en = GAME_SETTINGS.get("language", "ru") == "en"
        if self.kind == "pale_wanderer":
            self.used = True
            player.lantern_fuel = min(1.4, getattr(player, "lantern_fuel", 1.0) + 0.6)
            room.pickups.append(Pickup(self.x, self.y + 34, "soul_heart"))
            if en:
                return ("PALE WANDERER", "May his lantern brighten your path. (+Soul Heart & Fuel)")
            return ("БЛЕДНЫЙ СТРАННИК", "Пусть его фонарь осветит вам шаг. (+Душа и Пламя)")
        if self.kind == "silent_shadow":
            if player.coins < 2 and player.hp <= 2:
                return None
            if player.coins >= 2:
                player.coins -= 2
            else:
                player.take_damage(1, ignore_invuln=True)
            self.used = True
            player.damage += 0.85
            player.black_hp += 2
            if en:
                return ("SILENT SHADOW", "Silence tempered your edge. (+0.85 DMG & Black Heart)")
            return ("МОЛЧАЛИВАЯ ТЕНЬ", "Тишина укрепила клинок. (+0.85 Урон и Чёрное сердце)")
        self.used = True
        player.compass_reveal = True
        it = get_random_item(player.collected_ids, "passive")
        room.pedestals.append(ItemPedestal(self.x, self.y + 42, it))
        if en:
            return ("ANCIENT ORACLE", "Hidden paths stand revealed before your sight.")
        return ("ДРЕВНИЙ ОРАКУЛ", "Тайные пути открыты взору.")

    def explode(self, room):
        if not self.alive:
            return
        self.alive = False
        room.pickups.append(Pickup(self.x, self.y, "soul_heart" if self.kind != "silent_shadow" else "black_heart"))

    def draw(self, screen):
        if not self.alive:
            return
        sh = get_shadow_surf(42, 16, 120)
        screen.blit(sh, (int(round(self.x - sh.get_width() * 0.5)), int(round(self.y + 18 - sh.get_height() * 0.5))))
        draw_npc_visual(screen, self.kind, self.x, self.y, scale=1.0, age=self.age, activated=self.used)


class Beggar:
    def __init__(self, x, y, kind="coin_beggar"):
        self.x = float(x)
        self.y = float(y)
        self.kind = kind
        self.radius = 20.0
        self.alive = True
        self.uses = 0
        self.max_uses = random.randint(3, 6)
        self.age = random.uniform(0.0, 6.28)
        self.paid_out = False

    def update(self, dt=1.0):
        self.age += 0.08 * dt

    def interact(self, player, room):
        if not self.alive or self.paid_out:
            return None
        if self.kind in ("coin_beggar", "rotten_beggar"):
            if player.coins < 1:
                return None
            player.coins -= 1
        elif self.kind == "key_master":
            if player.keys < 1:
                return None
            player.keys -= 1
        elif self.kind == "bomb_bum":
            if player.bombs < 1:
                return None
            player.bombs -= 1
        elif self.kind in ("devil_beggar", "blood_bank_keeper"):
            if player.hp + player.soul_hp + player.black_hp <= 1:
                return None
            player.take_damage(1, ignore_invuln=True)
        elif self.kind == "battery_bum":
            if player.coins < 2:
                return None
            player.coins -= 2
            if hasattr(player, "recharge_active"):
                player.recharge_active(True)
            else:
                player.active_charge = player.max_charge
        elif self.kind == "relic_beggar":
            if player.coins < 2:
                return None
            player.coins -= 2
        else:
            if player.coins < 1:
                return None
            player.coins -= 1

        self.uses += 1
        payout_chance = 0.36 if self.kind == "relic_beggar" else 0.28
        if self.uses >= self.max_uses or random.random() < payout_chance:
            self.paid_out = True
            self.alive = False
            itype = "active" if self.kind == "battery_bum" and random.random() < 0.5 else "passive"
            it = get_random_item(player.collected_ids, itype)
            room.pedestals.append(ItemPedestal(self.x, self.y, it))
            return tr_item_name(it)

        if self.kind == "rotten_beggar":
            for i in range(2):
                if len(player.allies) < 12:
                    player.allies.append(BlueFly(self.x + (i - 0.5) * 18, self.y + 20, player.get_effective_damage() * 1.4))
            if random.random() < 0.45:
                room.pickups.append(Pickup(self.x + random.uniform(-20, 20), self.y + 26, "heart"))
            return "blue_flies"
        if self.kind == "blood_bank_keeper":
            for _ in range(random.randint(1, 2)):
                room.pickups.append(Pickup(self.x + random.uniform(-22, 22), self.y + 26, "coin"))
            return "coin"
        drop = random.choice(["heart", "soul_heart", "bomb", "key", "coin"])
        room.pickups.append(Pickup(self.x + random.uniform(-24, 24), self.y + 26, drop))
        return drop

    def explode(self, room):
        if not self.alive:
            return
        self.alive = False
        for _ in range(2):
            room.pickups.append(Pickup(self.x + random.uniform(-20, 20), self.y + 18, random.choice(["coin", "soul_heart", "key"])))

    def draw(self, screen):
        if not self.alive:
            return
        sh = get_shadow_surf(36, 14, 110)
        screen.blit(sh, (int(self.x - sh.get_width() // 2), int(self.y + 14)))
        draw_npc_visual(screen, self.kind, self.x, self.y, scale=1.0, age=self.age)


class Shopkeeper:
    def __init__(self, x, y, variant="keeper_classic"):
        self.x = float(x)
        self.y = float(y)
        self.variant = variant
        self.alive = True
        self.age = 0.0

    def update(self, dt=1.0):
        self.age += 0.065 * dt

    def explode(self, room):
        if not self.alive:
            return
        self.alive = False
        if random.random() < 0.55:
            for _ in range(2):
                room.pickups.append(Pickup(self.x + random.uniform(-22, 22), self.y + 14, random.choice(["coin", "nickel"])))
        else:
            room.enemies.append(create_enemy("spider", self.x - 16, self.y + 10, room.floor_level, room.floor_modifier))
            room.enemies.append(create_enemy("spider", self.x + 16, self.y + 10, room.floor_level, room.floor_modifier))

    def draw(self, screen):
        if not self.alive:
            return
        sh = get_shadow_surf(44, 16, 122)
        screen.blit(sh, (int(self.x - sh.get_width() // 2), int(self.y + 16)))
        draw_npc_visual(screen, self.variant, self.x, self.y, scale=1.0, age=self.age)


class Machine:
    def __init__(self, x, y, kind="slot_machine", track_idx=None, playing=None):
        self.x = float(x)
        self.y = float(y)
        self.kind = kind
        self.radius = 22.0
        self.alive = True
        self.uses = 0
        self.cooldown = 0.0
        self.age = random.uniform(0.0, 6.28)
        self.track_idx = int(track_idx) % 4 if track_idx is not None else random.randint(0, 3)
        self.playing = bool(playing) if playing is not None else (kind == "computer_terminal")

    def update(self, dt=1.0):
        self.age += 0.08 * dt
        if self.cooldown > 0:
            self.cooldown = max(0.0, self.cooldown - dt)

    def cycle_track(self):
        if self.kind != "computer_terminal" or not self.alive:
            return False
        if not self.playing:
            self.playing = True
            self.track_idx = 0
        elif self.track_idx < 3:
            self.track_idx += 1
        else:
            self.playing = False
        self.uses += 1
        self.cooldown = 20.0
        return True

    def get_light_source(self):
        if self.alive and self.kind == "computer_terminal" and self.playing:
            return (self.x, self.y - 6.0, 155.0, 0.72)
        return None

    def interact(self, player, room):
        if not self.alive or self.cooldown > 0:
            return False
        if self.kind == "computer_terminal":
            if not self.playing:
                self.playing = True
                self.cooldown = 36.0
                self.uses += 1
                from sound import play_sound

                play_sound("computer_beep")
                return True
            return False
        self.cooldown = 20.0
        if self.kind == "blood_donation":
            if player.hp + player.soul_hp + player.black_hp <= 1:
                return False
            player.take_damage(1, ignore_invuln=True)
            for _ in range(random.randint(1, 3)):
                room.pickups.append(Pickup(self.x + random.uniform(-24, 24), self.y + 30, "coin"))
        elif self.kind == "restock_machine":
            if player.coins < 3:
                return False
            player.coins -= 3
            for ped in room.pedestals:
                if ped.alive:
                    ped.item = get_random_item(player.collected_ids)
        elif self.kind == "crane_game":
            if player.coins < 3:
                return False
            player.coins -= 3
            if random.random() < 0.35:
                it = get_random_item(player.collected_ids, "passive")
                room.pedestals.append(ItemPedestal(self.x, self.y + 32, it))
                self.alive = False
            else:
                room.pickups.append(Pickup(self.x + random.uniform(-20, 20), self.y + 30, random.choice(["soul_heart", "key", "bomb"])))
        elif self.kind == "fortune_teller":
            if player.coins < 1:
                return False
            player.coins -= 1
            player.compass_reveal = True
            if random.random() < 0.5:
                room.pickups.append(Pickup(self.x + random.uniform(-20, 20), self.y + 30, random.choice(["soul_heart", "card", "coin"])))
        elif self.kind == "donation_box":
            if player.coins < 1:
                return False
            player.coins -= 1
            player.luck += 0.25
            if random.random() < 0.35:
                room.pickups.append(Pickup(self.x + random.uniform(-20, 20), self.y + 30, "soul_heart"))
        elif self.kind == "confessional":
            if player.coins < 1:
                return False
            player.coins -= 1
            if player.hp < player.max_hp:
                player.heal_red(1)
            elif random.random() < 0.4:
                room.pickups.append(Pickup(self.x + random.uniform(-20, 20), self.y + 30, "soul_heart"))
            if hasattr(player, "add_charge"):
                player.add_charge(1)
        else:
            if player.coins < 1:
                return False
            player.coins -= 1
            roll = random.random()
            if roll < 0.40:
                drop = random.choice(["coin", "heart", "soul_heart", "bomb", "key", "battery"])
                room.pickups.append(Pickup(self.x + random.uniform(-20, 20), self.y + 30, drop))
            elif roll < 0.48:
                it = get_random_item(player.collected_ids, "passive")
                room.pedestals.append(ItemPedestal(self.x, self.y + 32, it))
        self.uses += 1
        return True

    def explode(self, player, room):
        if not self.alive:
            return False
        if self.kind == "restock_machine":
            for ped in room.pedestals:
                if ped.alive:
                    ped.item = get_random_item(player.collected_ids)
        self.alive = False
        for _ in range(random.randint(2, 4)):
            room.pickups.append(Pickup(self.x + random.uniform(-24, 24), self.y + random.uniform(-10, 24), random.choice(["coin", "coin", "heart", "bomb"])))
        return True

    def draw(self, screen):
        if not self.alive:
            return
        sh_outer = get_shadow_surf(58, 22, 96)
        sh_core = get_shadow_surf(44, 14, 162)
        screen.blit(sh_outer, (int(self.x - sh_outer.get_width() // 2), int(self.y + 16)))
        screen.blit(sh_core, (int(self.x - sh_core.get_width() // 2), int(self.y + 19)))
        draw_npc_visual(screen, self.kind, self.x, self.y, scale=1.0, age=self.age, activated=False)
        if self.kind == "computer_terminal":
            draw_computer_screen_fx(screen, self.x, self.y, scale=1.0, age=self.age, playing=self.playing, track_idx=self.track_idx)


class SacrificeSpike:
    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        self.radius = 24.0
        self.hits = 0
        self.cooldown = 0.0

    def update(self, dt=1.0):
        if self.cooldown > 0:
            self.cooldown = max(0.0, self.cooldown - dt)

    def trigger(self, player, room):
        if self.cooldown > 0:
            return None
        self.cooldown = 36.0
        self.hits += 1
        h = self.hits
        if h in (1, 2):
            if random.random() < 0.5:
                room.pickups.append(Pickup(self.x + 42, self.y, "coin"))
        elif h in (3, 4):
            room.pickups.append(Pickup(self.x - 42, self.y, "soul_heart"))
        elif h == 5:
            for i in range(3):
                room.pickups.append(Pickup(self.x + (i - 1) * 28, self.y + 42, "coin"))
        elif h == 6:
            room.pickups.append(Pickup(self.x, self.y + 44, "soul_heart"))
        elif h == 7:
            it = get_random_item(player.collected_ids, "passive")
            room.pedestals.append(ItemPedestal(self.x, self.y - 54, it))
        elif h == 8:
            for i in range(4):
                room.pickups.append(Pickup(self.x + (i - 1.5) * 24, self.y + 42, "bomb" if i % 2 == 0 else "key"))
        elif h == 9:
            return "uriel"
        elif h == 10:
            for i in range(5):
                room.pickups.append(Pickup(self.x + (i - 2) * 22, self.y + 42, "soul_heart" if i == 0 else "coin"))
        elif h == 11:
            return "gabriel"
        else:
            room.pickups.append(Pickup(self.x, self.y + 44, "soul_heart"))
        return None

    def draw(self, screen):
        cached = _SACRIFICE_CACHE.get(0)
        if cached is None:
            gl = get_glow_surf(36, 224, 48)
            sz = max(76, gl.get_width())
            surf = pygame.Surface((sz, sz), pygame.SRCALPHA)
            cx = cy = sz // 2
            surf.blit(gl, (cx - gl.get_width() // 2, cy - gl.get_height() // 2))
            draw_aa_ring(surf, (186, 186, 186, 255), cx, cy, 26, 2)
            spr = _get_obstacle_sprite("spike", 48, 220, 48)
            surf.blit(spr, (cx - 24, cy - 24))
            cached = _finalize_alpha_surf(surf)
            _SACRIFICE_CACHE[0] = cached
        screen.blit(cached, (int(self.x - cached.get_width() // 2), int(self.y - cached.get_height() // 2)))


class DiceFloor:
    def __init__(self, x, y, pips=None):
        self.x = float(x)
        self.y = float(y)
        self.pips = pips if pips is not None else random.randint(1, 6)
        self.used = False
        self.radius = 44.0

    def draw(self, screen):
        key = (int(self.pips), bool(self.used))
        cached = _DICE_CACHE.get(key)
        if cached is None:
            surf = pygame.Surface((92, 92), pygame.SRCALPHA)
            rect = pygame.Rect(4, 4, 84, 84)
            col = (64, 64, 64, 255) if self.used else (224, 224, 224, 255)
            pygame.draw.rect(surf, (18, 18, 18, 255), rect.inflate(6, 6), border_radius=12)
            pygame.draw.rect(surf, col, rect, border_radius=10)
            pygame.draw.rect(surf, (36, 36, 36, 255), rect, 2, border_radius=10)
            dot_col = (128, 128, 128, 255) if self.used else (18, 18, 18, 255)
            offsets = {
                1: [(0, 0)],
                2: [(-18, -18), (18, 18)],
                3: [(-18, -18), (0, 0), (18, 18)],
                4: [(-18, -18), (18, -18), (-18, 18), (18, 18)],
                5: [(-18, -18), (18, -18), (0, 0), (-18, 18), (18, 18)],
                6: [(-18, -20), (18, -20), (-18, 0), (18, 0), (-18, 20), (18, 20)],
            }[self.pips]
            for ox, oy in offsets:
                draw_aa_circle(surf, dot_col, 46 + ox, 46 + oy, 6)
            cached = _finalize_alpha_surf(surf)
            _DICE_CACHE[key] = cached
        screen.blit(cached, (int(self.x - 46), int(self.y - 46)))


class Door:
    def __init__(self, direction, target_coord, target_type="normal", locked=False, secret=False):
        self.direction = direction
        self.target_coord = target_coord
        self.target_type = target_type
        self.locked = bool(locked)
        self.secret = bool(secret)
        self.opened = False
        cx = (PLAYABLE_LEFT + PLAYABLE_RIGHT) // 2
        cy = (PLAYABLE_TOP + PLAYABLE_BOTTOM) // 2
        if direction == "N":
            self.rect = pygame.Rect(cx - DOOR_WIDTH // 2, PLAYABLE_TOP - DOOR_THICKNESS, DOOR_WIDTH, DOOR_THICKNESS + 10)
        elif direction == "S":
            self.rect = pygame.Rect(cx - DOOR_WIDTH // 2, PLAYABLE_BOTTOM - 10, DOOR_WIDTH, DOOR_THICKNESS + 10)
        elif direction == "W":
            self.rect = pygame.Rect(PLAYABLE_LEFT - DOOR_THICKNESS, cy - DOOR_WIDTH // 2, DOOR_THICKNESS + 10, DOOR_WIDTH)
        else:
            self.rect = pygame.Rect(PLAYABLE_RIGHT - 10, cy - DOOR_WIDTH // 2, DOOR_THICKNESS + 10, DOOR_WIDTH)

    def draw(self, screen, open_flag, force_curse_spikes=False):
        if self.secret and not self.opened:
            return
        is_open = bool(open_flag and not self.locked)
        is_curse_spikes = (self.target_type == "curse") or bool(force_curse_spikes)
        key = (self.direction, self.target_type, is_open, bool(self.locked), is_curse_spikes, self.rect.w, self.rect.h)
        cached = _DOOR_CACHE.get(key)
        if cached is None:
            _prune_cache(_DOOR_CACHE, 128)
            pad = 14
            surf = pygame.Surface((self.rect.w + pad * 2, self.rect.h + pad * 2), pygame.SRCALPHA)
            local_rect = pygame.Rect(pad, pad, self.rect.w, self.rect.h)
            frame_lum = 228 if (self.target_type in ("boss", "devil", "curse") or is_curse_spikes) else (216 if self.target_type in ("treasure", "shop", "library") else 148)
            inner_lum = 5 if is_open else 40
            pygame.draw.rect(surf, (10, 10, 10, 255), local_rect.inflate(12, 12), border_radius=8)
            pygame.draw.rect(surf, (frame_lum, frame_lum, frame_lum, 255), local_rect, border_radius=5)
            inner = local_rect.inflate(-10, -10)
            pygame.draw.rect(surf, (inner_lum, inner_lum, inner_lum, 255), inner, border_radius=3)
            if is_open:
                pygame.draw.rect(surf, (210, 210, 210, 255), inner, 1, border_radius=3)
            else:
                pygame.draw.line(surf, (158, 158, 158, 255), (inner.left, inner.top), (inner.right, inner.bottom), 2)
                pygame.draw.line(surf, (158, 158, 158, 255), (inner.right, inner.top), (inner.left, inner.bottom), 2)

            rcx, rcy = local_rect.centerx, local_rect.centery
            if self.target_type == "devil":
                draw_aa_poly(surf, (236, 236, 236, 255), [(rcx - 16, local_rect.top), (rcx - 24, local_rect.top - 12), (rcx - 6, local_rect.top - 2)])
                draw_aa_poly(surf, (236, 236, 236, 255), [(rcx + 16, local_rect.top), (rcx + 24, local_rect.top - 12), (rcx + 6, local_rect.top - 2)])
            elif self.target_type == "boss":
                draw_aa_circle(surf, (242, 242, 242, 255), rcx, rcy, 6)
                draw_aa_circle(surf, (16, 16, 16, 255), rcx - 2, rcy - 1, 1.5)
                draw_aa_circle(surf, (16, 16, 16, 255), rcx + 2, rcy - 1, 1.5)
            elif self.target_type == "shop":
                draw_aa_circle(surf, (240, 240, 240, 255), rcx, rcy, 5.5)
                pygame.draw.line(surf, (20, 20, 20, 255), (rcx, rcy - 3), (rcx, rcy + 3), 2)
            elif self.target_type == "treasure":
                draw_aa_poly(surf, (248, 248, 248, 255), [(rcx, rcy - 6), (rcx + 6, rcy), (rcx, rcy + 6), (rcx - 6, rcy)])
            if is_curse_spikes:
                for off in (-18, -6, 6, 18):
                    if self.direction in ("N", "S"):
                        draw_aa_poly(surf, (232, 232, 232, 255), [(rcx + off - 4, rcy + 5), (rcx + off + 4, rcy + 5), (rcx + off, rcy - 7)])
                        draw_aa_poly(surf, (232, 232, 232, 255), [(rcx + off - 4, rcy - 5), (rcx + off + 4, rcy - 5), (rcx + off, rcy + 7)])
                    else:
                        draw_aa_poly(surf, (232, 232, 232, 255), [(rcx - 5, rcy + off - 4), (rcx - 5, rcy + off + 4), (rcx + 7, rcy + off)])
                        draw_aa_poly(surf, (232, 232, 232, 255), [(rcx + 5, rcy + off - 4), (rcx + 5, rcy + off + 4), (rcx - 7, rcy + off)])
            if self.locked:
                draw_aa_circle(surf, (244, 244, 244, 255), inner.centerx, inner.centery, 6)
                draw_aa_circle(surf, (16, 16, 16, 255), inner.centerx, inner.centery, 2.5)
            cached = _finalize_alpha_surf(surf)
            _DOOR_CACHE[key] = cached
        screen.blit(cached, (self.rect.x - 14, self.rect.y - 14))


class Room:
    def __init__(self, coord, room_type="normal", floor_level=1, layout_key=None, game_mode="classic", floor_modifier=None, seed=None, build_contents=True):
        self.coord = coord
        self.room_type = room_type
        self.floor_level = int(floor_level)
        self.game_mode = game_mode
        self.floor_modifier = floor_modifier
        self.doors = {}
        self.obstacles = []
        self.enemies = []
        self.bosses = []
        self.pickups = []
        self.pedestals = []
        self.beggars = []
        self.shopkeepers = []
        self.machines = []
        self.monoliths = []
        self.mystical_npcs = []
        self.sacrifice_spike = None
        self.dice_floor = None
        self.trapdoor_rect = None
        self.victory_portal_rect = None
        self.devil_door = None
        self.visited = False
        self.cleared = room_type in ("start", "treasure", "shop", "arcade", "sacrifice", "library", "dice", "secret", "devil")
        self.combat_theme = None
        self.theme = get_floor_theme(floor_level)
        if floor_modifier is not None:
            self.theme["ambient"] = clamp(self.theme["ambient"] * floor_modifier.get("ambient_mult", 1.0), 0.16, 0.45)
        self.scheme = ROOM_COLOR_SCHEMES.get(room_type, ROOM_COLOR_SCHEMES["normal"])
        self.rng = random.Random(seed) if seed is not None else random.Random()
        self.layout_key = layout_key or self.rng.choice(list(LAYOUT_TEMPLATES.keys()) + ["procedural"] * 4)
        self.torch_positions = [
            (PLAYABLE_LEFT + 28, PLAYABLE_TOP + 26),
            (PLAYABLE_RIGHT - 28, PLAYABLE_TOP + 26),
            (PLAYABLE_LEFT + 28, PLAYABLE_BOTTOM - 26),
            (PLAYABLE_RIGHT - 28, PLAYABLE_BOTTOM - 26),
        ]
        self.dust_motes = [
            {
                "x": self.rng.uniform(PLAYABLE_LEFT + 30, PLAYABLE_RIGHT - 30),
                "y": self.rng.uniform(PLAYABLE_TOP + 30, PLAYABLE_BOTTOM - 30),
                "vx": self.rng.uniform(-0.18, 0.18),
                "vy": self.rng.uniform(-0.22, -0.05),
                "r": self.rng.choice([1, 2]),
                "lum": self.rng.randint(176, 236),
                "alpha": self.rng.randint(36, 108),
            }
            for _ in range(22)
        ]
        self._baked_bg = None
        if build_contents:
            self._build_contents()

    @property
    def center_x(self):
        return (PLAYABLE_LEFT + PLAYABLE_RIGHT) // 2

    @property
    def center_y(self):
        return (PLAYABLE_TOP + PLAYABLE_BOTTOM) // 2

    def spawn_pickup(self, x, y, kind="coin", price=0):
        px = clamp(float(x), PLAYABLE_LEFT + 22, PLAYABLE_RIGHT - 22)
        py = clamp(float(y), PLAYABLE_TOP + 22, PLAYABLE_BOTTOM - 22)
        p = Pickup(px, py, kind, price=price)
        self.pickups.append(p)
        return p

    def _is_safe_spawn(self, ox, oy):
        cx = (PLAYABLE_LEFT + PLAYABLE_RIGHT) // 2
        cy = (PLAYABLE_TOP + PLAYABLE_BOTTOM) // 2
        if math.hypot(ox - cx, oy - cy) < 80:
            return False
        door_centers = [
            (cx, PLAYABLE_TOP),
            (cx, PLAYABLE_BOTTOM),
            (PLAYABLE_LEFT, cy),
            (PLAYABLE_RIGHT, cy),
        ]
        for dx, dy in door_centers:
            if math.hypot(ox - dx, oy - dy) < 104:
                return False
        return True

    def _doors_connected(self, obs_list):
        cell = 16
        cols = max(5, (PLAYABLE_RIGHT - PLAYABLE_LEFT) // cell)
        rows = max(5, (PLAYABLE_BOTTOM - PLAYABLE_TOP) // cell)
        grid = bytearray(cols * rows)
        for obs in obs_list:
            if not getattr(obs, "alive", True) or not obs.blocks_movement:
                continue
            infl = obs.rect.inflate(34, 34)
            gx0 = max(0, (infl.left - PLAYABLE_LEFT) // cell)
            gx1 = min(cols - 1, (infl.right - PLAYABLE_LEFT) // cell)
            gy0 = max(0, (infl.top - PLAYABLE_TOP) // cell)
            gy1 = min(rows - 1, (infl.bottom - PLAYABLE_TOP) // cell)
            for gy in range(gy0, gy1 + 1):
                py = PLAYABLE_TOP + (gy + 0.5) * cell
                if infl.top <= py <= infl.bottom:
                    row_off = gy * cols
                    for gx in range(gx0, gx1 + 1):
                        px = PLAYABLE_LEFT + (gx + 0.5) * cell
                        if infl.left <= px <= infl.right:
                            grid[row_off + gx] = 1

        cx = (PLAYABLE_LEFT + PLAYABLE_RIGHT) // 2
        cy = (PLAYABLE_TOP + PLAYABLE_BOTTOM) // 2
        def _pt_cell(px, py):
            return (
                int(clamp((px - PLAYABLE_LEFT) // cell, 0, cols - 1)),
                int(clamp((py - PLAYABLE_TOP) // cell, 0, rows - 1)),
            )

        center = _pt_cell(cx, cy)
        targets = (
            _pt_cell(cx, PLAYABLE_TOP + 26),
            _pt_cell(cx, PLAYABLE_BOTTOM - 26),
            _pt_cell(PLAYABLE_LEFT + 26, cy),
            _pt_cell(PLAYABLE_RIGHT - 26, cy),
        )
        if grid[center[1] * cols + center[0]]:
            return False
        for tx, ty in targets:
            if grid[ty * cols + tx]:
                return False

        visited = bytearray(cols * rows)
        visited[center[1] * cols + center[0]] = 1
        q = deque([center])
        while q:
            x, y = q.popleft()
            if x + 1 < cols:
                idx = y * cols + (x + 1)
                if not grid[idx] and not visited[idx]:
                    visited[idx] = 1
                    q.append((x + 1, y))
            if x - 1 >= 0:
                idx = y * cols + (x - 1)
                if not grid[idx] and not visited[idx]:
                    visited[idx] = 1
                    q.append((x - 1, y))
            if y + 1 < rows:
                idx = (y + 1) * cols + x
                if not grid[idx] and not visited[idx]:
                    visited[idx] = 1
                    q.append((x, y + 1))
            if y - 1 >= 0:
                idx = (y - 1) * cols + x
                if not grid[idx] and not visited[idx]:
                    visited[idx] = 1
                    q.append((x, y - 1))
        return all(visited[ty * cols + tx] for tx, ty in targets)

    def _procedural_points(self, theme_obs):
        cx = (PLAYABLE_LEFT + PLAYABLE_RIGHT) // 2
        cy = (PLAYABLE_TOP + PLAYABLE_BOTTOM) // 2
        pattern = self.rng.choice(["clusters", "colonnade_jitter", "chasm_islands", "l_barricades", "altar_ring"])
        pts = []
        if pattern == "clusters":
            for _ in range(self.rng.randint(3, 5)):
                bx = self.rng.randrange(PLAYABLE_LEFT + 130, PLAYABLE_RIGHT - 130, 56)
                by = self.rng.randrange(PLAYABLE_TOP + 110, PLAYABLE_BOTTOM - 110, 56)
                k_main = self.rng.choice(theme_obs)
                pts.append((bx, by, k_main))
                for _ in range(self.rng.randint(1, 2)):
                    dx, dy = self.rng.choice([(54, 0), (-54, 0), (0, 54), (0, -54)])
                    pts.append((bx + dx, by + dy, self.rng.choice(theme_obs)))
        elif pattern == "colonnade_jitter":
            cols = self.rng.sample([310, 450, 640, 830, 970], self.rng.randint(2, 4))
            rows = [230 + self.rng.randint(-18, 18), 490 + self.rng.randint(-18, 18)]
            for x in cols:
                for y in rows:
                    if self.rng.random() < 0.78:
                        pts.append((x + self.rng.randint(-16, 16), y, self.rng.choice(["pillar", theme_obs[0]])))
            pts.append((cx + self.rng.choice([-190, 190]), cy, "brazier"))
        elif pattern == "chasm_islands":
            pit_x = self.rng.sample([320, 420, 860, 960], 2)
            for x in pit_x:
                base_y = self.rng.choice([210, 250, 430, 470])
                for step in range(self.rng.randint(2, 3)):
                    pts.append((x + step * 54, base_y, "pit"))
            for _ in range(self.rng.randint(2, 4)):
                pts.append((self.rng.randrange(PLAYABLE_LEFT + 140, PLAYABLE_RIGHT - 140, 56), self.rng.randrange(PLAYABLE_TOP + 110, PLAYABLE_BOTTOM - 110, 56), self.rng.choice(["pillar", "rock", "urn"])))
        elif pattern == "l_barricades":
            for sx, sy in ((-1, -1), (1, 1), (-1, 1), (1, -1)):
                if self.rng.random() < 0.65:
                    ax = cx + sx * self.rng.randint(150, 290)
                    ay = cy + sy * self.rng.randint(95, 160)
                    k = self.rng.choice(["rock", "pillar"])
                    pts.append((ax, ay, k))
                    pts.append((ax - sx * 54, ay, k))
                    pts.append((ax, ay - sy * 54, self.rng.choice(["urn", "brazier", k])))
        else:
            rad_x = self.rng.randint(150, 230)
            rad_y = self.rng.randint(100, 145)
            n = self.rng.randint(5, 8)
            phase = self.rng.uniform(0.0, math.pi)
            for i in range(n):
                a = phase + i * (math.pi * 2.0 / n)
                px = int(cx + math.cos(a) * rad_x)
                py = int(cy + math.sin(a) * rad_y)
                pts.append((px, py, self.rng.choice(theme_obs)))
        return pts

    def _build_normal_obstacles(self, theme_obs=None):
        theme_obs = list(theme_obs or ("rock", "pillar", "urn", "brazier"))
        use_proc = self.layout_key == "procedural" or (self.layout_key != "empty" and self.rng.random() < 0.52)
        if use_proc:
            raw_pts = self._procedural_points(theme_obs)
            flip_x = False
            flip_y = False
            jitter = 10
        else:
            raw_pts = list(LAYOUT_TEMPLATES.get(self.layout_key, []))
            flip_x = self.rng.choice((False, True))
            flip_y = self.rng.choice((False, True))
            jitter = 14

        built = []
        for ox, oy, kind in raw_pts:
            px = (SCREEN_WIDTH - ox if flip_x else ox) + self.rng.randint(-jitter, jitter)
            py = (SCREEN_HEIGHT - oy if flip_y else oy) + self.rng.randint(-jitter, jitter)
            px = clamp(px, PLAYABLE_LEFT + 62, PLAYABLE_RIGHT - 62)
            py = clamp(py, PLAYABLE_TOP + 58, PLAYABLE_BOTTOM - 58)
            if not self._is_safe_spawn(px, py):
                continue
            if any(o.rect.inflate(14, 14).collidepoint(px, py) for o in built):
                continue
            if kind == "rock" and self.rng.random() < 0.14:
                kind = "tinted_rock"
            elif kind == "rock" and self.floor_level >= 3 and self.rng.random() < 0.25:
                kind = "pillar"
            elif kind == "rock" and "poop" in theme_obs and self.rng.random() < 0.22:
                kind = "poop"
            cand = Obstacle(px, py, kind)
            if not cand.blocks_movement or self._doors_connected(built + [cand]):
                built.append(cand)

        extra_slots = self.rng.randint(2, 5)
        turret_count = 0
        for _ in range(extra_slots):
            ex = self.rng.randrange(PLAYABLE_LEFT + 110, PLAYABLE_RIGHT - 110, 56)
            ey = self.rng.randrange(PLAYABLE_TOP + 96, PLAYABLE_BOTTOM - 96, 56)
            if not self._is_safe_spawn(ex, ey):
                continue
            if any(o.rect.inflate(16, 16).collidepoint(ex, ey) for o in built):
                continue
            if self.floor_level >= 2 and turret_count < 1 and self.rng.random() < 0.22:
                ekind = "turret"
                turret_count += 1
            elif self.rng.random() < 0.28:
                ekind = "barrier"
            else:
                ekind = self.rng.choice(theme_obs + ["urn", "brazier"])
            cand = Obstacle(ex, ey, ekind)
            if not cand.blocks_movement or self._doors_connected(built + [cand]):
                built.append(cand)

        if not self._doors_connected(built):
            built = [o for o in built if o.kind in ("brazier", "urn")]
        self.obstacles = built

    def _build_contents(self):
        cx = (PLAYABLE_LEFT + PLAYABLE_RIGHT) // 2
        cy = (PLAYABLE_TOP + PLAYABLE_BOTTOM) // 2

        if self.game_mode == "endless_abyss":
            for px, py, kind in LAYOUT_TEMPLATES["pillars_4"]:
                self.obstacles.append(Obstacle(px, py, kind))
            self.obstacles.append(Obstacle(cx - 260, cy, "brazier"))
            self.obstacles.append(Obstacle(cx + 260, cy, "brazier"))
            self.cleared = False
            return

        if self.room_type == "normal":
            theme_key, enemy_pool = pick_combat_theme_enemies(self.floor_level, self.rng, max_types=2)
            self.combat_theme = theme_key
            theme_obs = COMBAT_ROOM_THEMES.get(theme_key, {}).get("obstacles", ("rock", "pillar", "urn", "brazier"))
            self._build_normal_obstacles(theme_obs)
            if self.game_mode == "free_roam" and self.rng.random() < 0.40:
                self.cleared = True
                if self.rng.random() < 0.72:
                    self.monoliths.append(LoreMonolith(cx, cy))
                if self.rng.random() < 0.56:
                    npc_kind = self.rng.choice(["pale_wanderer", "silent_shadow", "ancient_oracle"])
                    self.mystical_npcs.append(MysticalNPC(cx - 120, cy + 40, npc_kind))
            else:
                base_cnt = 3 + min(3, (self.floor_level + 1) // 2)
                count = self.rng.randint(base_cnt, base_cnt + 2)
                for _ in range(count):
                    for _attempt in range(14):
                        ex = self.rng.uniform(PLAYABLE_LEFT + 92, PLAYABLE_RIGHT - 92)
                        ey = self.rng.uniform(PLAYABLE_TOP + 82, PLAYABLE_BOTTOM - 82)
                        if not self._is_safe_spawn(ex, ey):
                            continue
                        if any(obs.rect.inflate(34, 34).collidepoint(ex, ey) for obs in self.obstacles):
                            continue
                        et = self.rng.choice(enemy_pool)
                        self.enemies.append(create_enemy(et, ex, ey, self.floor_level, self.floor_modifier))
                        break
                if self.rng.random() < 0.12:
                    npc_kind = self.rng.choice(["pale_wanderer", "silent_shadow", "ancient_oracle"])
                    self.mystical_npcs.append(MysticalNPC(cx - 140, cy, npc_kind))
            if self.game_mode == "fading_light" and not self.monoliths and self.rng.random() < 0.58:
                self.monoliths.append(LoreMonolith(cx - 210, cy))

        elif self.room_type == "start":
            self.obstacles.append(Obstacle(cx - 250, cy - 135, "brazier"))
            self.obstacles.append(Obstacle(cx + 250, cy - 135, "brazier"))

        elif self.room_type == "treasure":
            ped_dx = self.rng.choice([0, -24, 24])
            ped_type = "active" if self.rng.random() < 0.30 else "passive"
            self.pedestals.append(ItemPedestal(cx + ped_dx, cy, get_random_item(item_type=ped_type)))
            p_dx = self.rng.randint(155, 195)
            p_dy = self.rng.randint(105, 130)
            for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                self.obstacles.append(Obstacle(cx + sx * p_dx, cy + sy * p_dy, "pillar"))
            self.obstacles.append(Obstacle(cx - 255, cy, "brazier"))
            self.obstacles.append(Obstacle(cx + 255, cy, "brazier"))
            if self.rng.random() < 0.45:
                self.pickups.append(Pickup(cx + self.rng.choice([-110, 110]), cy + 68, self.rng.choice(["coin", "key", "bomb"])))
            if self.game_mode in ("free_roam", "fading_light"):
                self.monoliths.append(LoreMonolith(cx, cy - 140))

        elif self.room_type == "shop":
            self.shopkeepers.append(Shopkeeper(cx, cy - 125, self.rng.choice(SHOPKEEPER_VARIANTS)))
            mac_kind = self.rng.choice(["restock_machine", "donation_box", "crane_game"])
            mac_side = self.rng.choice([-210, 210])
            self.machines.append(Machine(cx + mac_side, cy - 120, mac_kind))
            self.pedestals.append(ItemPedestal(cx - 120, cy + 15, get_random_item(), price=15))
            self.pedestals.append(ItemPedestal(cx + 120, cy + 15, get_random_item(), price=15))
            p1 = self.rng.choice(["soul_heart", "heart", "battery"])
            p2 = self.rng.choice(["bomb", "key", "nickel"])
            self.pickups.append(Pickup(cx - 42, cy + 48, p1, price=5))
            self.pickups.append(Pickup(cx + 42, cy + 48, p2, price=5))
            self.obstacles.append(Obstacle(cx - 280, cy + 120, "urn"))
            self.obstacles.append(Obstacle(cx + 280, cy + 120, "urn"))

        elif self.room_type == "curse":
            self.pedestals.append(ItemPedestal(cx, cy - 25, get_random_item(item_type="passive"), devil_cost=1))
            self.pickups.append(Pickup(cx - 110, cy + 40, "black_heart"))
            self.pickups.append(Pickup(cx + 110, cy + 40, self.rng.choice(["black_heart", "soul_heart"])))
            for bx, by in ((-220, -110), (220, 110)):
                self.obstacles.append(Obstacle(cx + bx, cy + by, "brazier"))

        elif self.room_type == "arcade":
            m1, m2 = self.rng.sample(["slot_machine", "blood_donation", "fortune_teller", "crane_game", "confessional", "donation_box"], 2)
            self.machines.append(Machine(cx - 140, cy - 40, m1))
            self.machines.append(Machine(cx + 140, cy - 40, m2))
            self.beggars.append(Beggar(cx, cy + 75, self.rng.choice(BEGGAR_TYPES)))

        elif self.room_type == "sacrifice":
            self.sacrifice_spike = SacrificeSpike(cx, cy)
            for sx, sy in ((-200, -120), (200, -120), (-200, 120), (200, 120)):
                self.obstacles.append(Obstacle(cx + sx, cy + sy, "brazier"))

        elif self.room_type == "library":
            self.pedestals.append(ItemPedestal(cx - 110, cy, get_random_item(item_type="active")))
            self.pedestals.append(ItemPedestal(cx + 110, cy, get_random_item(item_type="active")))
            self.monoliths.append(LoreMonolith(cx, cy - 135))
            self.obstacles.append(Obstacle(cx - 240, cy - 115, "pillar"))
            self.obstacles.append(Obstacle(cx + 240, cy - 115, "pillar"))

        elif self.room_type == "dice":
            self.dice_floor = DiceFloor(cx, cy, self.rng.randint(1, 6))

        elif self.room_type == "secret":
            for i in range(4):
                self.pickups.append(Pickup(cx + (i - 1.5) * 42, cy - 20, self.rng.choice(["coin", "nickel", "bomb", "key"])))
            self.pedestals.append(ItemPedestal(cx, cy + 45, get_random_item()))
            side = self.rng.choice([-210, 210])
            self.obstacles.append(Obstacle(cx + side, cy - 110, "urn"))
            self.obstacles.append(Obstacle(cx + side, cy + 110, "urn"))

        if self.obstacles and not self._doors_connected(self.obstacles):
            self.obstacles = [o for o in self.obstacles if not o.blocks_movement]

    def _draw_wall_masonry(self, surf, outer_rect, arena, wall, wall_top, trim):
        pygame.draw.rect(surf, wall, outer_rect, border_radius=12)
        top_face = pygame.Rect(outer_rect.x, outer_rect.y, outer_rect.w, arena.y - outer_rect.y)
        pygame.draw.rect(surf, wall_top, top_face, border_top_left_radius=12, border_top_right_radius=12)

        mortar = (max(4, wall_top[0] - 14), max(4, wall_top[1] - 14), max(4, wall_top[2] - 14))
        hi_brick = (min(220, wall_top[0] + 12), min(220, wall_top[1] + 12), min(220, wall_top[2] + 12))
        row_h = 18
        for row_i, by in enumerate(range(outer_rect.y + 4, arena.y - 4, row_h)):
            offset = 28 if row_i % 2 == 1 else 0
            pygame.draw.line(surf, mortar, (outer_rect.x + 8, by), (outer_rect.right - 8, by), 1)
            for bx in range(outer_rect.x + 12 + offset, outer_rect.right - 16, 62):
                bw = min(56, outer_rect.right - 12 - bx)
                if bw > 14:
                    shade = wall_top[0] + self.rng.randint(-4, 5)
                    pygame.draw.rect(surf, (shade, shade, shade), (bx + 1, by + 1, bw - 2, min(row_h - 2, arena.y - by - 2)), border_radius=2)
                    pygame.draw.line(surf, hi_brick, (bx + 2, by + 1), (bx + bw - 3, by + 1), 1)
                    pygame.draw.line(surf, mortar, (bx, by), (bx, min(by + row_h, arena.y)), 1)

        for sx in (arena.x - 36, arena.right):
            for by in range(arena.y, arena.bottom - 8, 28):
                shade = wall[0] + self.rng.randint(3, 11)
                pygame.draw.rect(surf, (shade, shade, shade), (sx + 2, by + 1, 32, 26), border_radius=2)
                pygame.draw.line(surf, hi_brick, (sx + 3, by + 2), (sx + 32, by + 2), 1)

        for bx in range(arena.x, arena.right - 12, 54):
            shade = wall[0] + self.rng.randint(4, 12)
            pygame.draw.rect(surf, (shade, shade, shade), (bx + 1, arena.bottom + 2, 50, 32), border_radius=2)
            pygame.draw.line(surf, hi_brick, (bx + 2, arena.bottom + 3), (bx + 48, arena.bottom + 3), 1)

        if self.floor_level >= 3:
            for cx_link in range(arena.x + 120, arena.right - 80, 210):
                for cy_link in range(outer_rect.y + 8, arena.y - 2, 7):
                    pygame.draw.circle(surf, (58, 58, 58), (cx_link, cy_link), 3, 1)

        if self.room_type == "shop":
            for bx in range(arena.x + 80, arena.right - 80, 120):
                pts = [(bx - 16, arena.y - 28), (bx + 16, arena.y - 28), (bx, arena.y - 6)]
                draw_aa_poly(surf, (168, 168, 168), pts)
                pygame.draw.polygon(surf, (42, 42, 42), pts, 1)

        pygame.draw.rect(surf, trim, outer_rect, 2, border_radius=12)

    def _draw_floor_masonry(self, surf, arena, fa, fb):
        pygame.draw.rect(surf, fb, arena)
        style = self.theme.get("tile_style", "ashlar")
        base_lum = (fa[0] + fb[0]) // 2
        row_h = 46 if style in ("ashlar", "catacomb") else 40
        y = arena.y
        row_idx = 0
        while y < arena.bottom:
            th = min(row_h, arena.bottom - y)
            x = arena.x - ((row_idx % 2) * 34 if style != "catacomb" else (row_idx % 3) * 24)
            while x < arena.right:
                span = self.rng.choice([64, 78, 92]) if style in ("ashlar", "obsidian") else self.rng.choice([52, 66, 80])
                sx = max(arena.x, x)
                ex = min(arena.right, x + span)
                tw = ex - sx
                if tw > 6:
                    dx_n = abs((sx + tw * 0.5) - arena.centerx) / max(1.0, arena.w * 0.5)
                    dy_n = abs((y + th * 0.5) - arena.centery) / max(1.0, arena.h * 0.5)
                    rad_n = min(1.0, math.hypot(dx_n, dy_n) * 0.78)
                    center_lift = int(round(5.0 * (1.0 - rad_n * rad_n)))
                    jitter = self.rng.randint(-4, 4)
                    lum = int(clamp(base_lum + jitter + center_lift, 8, 220))
                    pygame.draw.rect(surf, (lum, lum, lum), (sx + 1, y + 1, tw - 2, th - 2), border_radius=4)
                    hi = min(230, lum + 5)
                    lo = max(4, lum - 7)
                    pygame.draw.line(surf, (hi, hi, hi), (sx + 3, y + 2), (sx + tw - 4, y + 2), 1)
                    pygame.draw.line(surf, (lo, lo, lo), (sx + 3, y + th - 2), (sx + tw - 4, y + th - 2), 1)

                    roll = self.rng.random()
                    if roll < 0.24:
                        cx1 = sx + self.rng.randint(8, max(9, tw - 12))
                        cy1 = y + self.rng.randint(8, max(9, th - 10))
                        cx2 = clamp(cx1 + self.rng.randint(-14, 14), sx + 3, sx + tw - 4)
                        cy2 = clamp(cy1 + self.rng.randint(-9, 9), y + 3, y + th - 4)
                        pygame.draw.line(surf, (lo, lo, lo), (cx1, cy1), (cx2, cy2), 1)
                        if self.rng.random() < 0.45:
                            pygame.draw.line(surf, (lo, lo, lo), (cx2, cy2), (cx2 + self.rng.randint(-7, 7), cy2 + self.rng.randint(-5, 5)), 1)
                    elif roll < 0.30 and tw > 28:
                        pygame.draw.circle(surf, (lo + 2, lo + 2, lo + 2), (sx + tw // 2, y + th // 2), 4, 1)
                x += span
            y += row_h
            row_idx += 1

        if self.room_type == "shop":
            rug = pygame.Rect(arena.centerx - 246, arena.centery - 134, 492, 268)
            pygame.draw.rect(surf, (36, 36, 36), rug, border_radius=12)
            pygame.draw.rect(surf, (108, 108, 108), rug.inflate(-14, -14), 2, border_radius=9)
            pygame.draw.rect(surf, (68, 68, 68), rug.inflate(-30, -30), 1, border_radius=6)
            for ty in range(rug.top + 12, rug.bottom - 10, 18):
                pygame.draw.line(surf, (132, 132, 132), (rug.left - 8, ty), (rug.left, ty), 2)
                pygame.draw.line(surf, (132, 132, 132), (rug.right, ty), (rug.right + 8, ty), 2)
            draw_aa_ring(surf, (124, 124, 124), arena.centerx, arena.centery, 46, 1)
            counter = pygame.Rect(arena.centerx - 165, arena.centery - 92, 330, 18)
            pygame.draw.rect(surf, (22, 22, 22), counter.inflate(4, 4), border_radius=5)
            pygame.draw.rect(surf, (92, 92, 92), counter, border_radius=4)
            pygame.draw.line(surf, (164, 164, 164), (counter.left + 4, counter.top + 2), (counter.right - 4, counter.top + 2), 1)
        elif self.room_type == "library":
            rug = pygame.Rect(arena.centerx - 220, arena.centery - 120, 440, 240)
            pygame.draw.rect(surf, (38, 38, 38), rug, border_radius=12)
            pygame.draw.rect(surf, (88, 88, 88), rug.inflate(-16, -16), 2, border_radius=9)
            pygame.draw.rect(surf, (58, 58, 58), rug.inflate(-32, -32), 1, border_radius=6)
        elif self.room_type in ("boss", "sacrifice", "curse", "devil") or self.game_mode == "endless_abyss":
            draw_aa_ring(surf, (76, 76, 76), arena.centerx, arena.centery, 134, 2)
            draw_aa_ring(surf, (54, 54, 54), arena.centerx, arena.centery, 92, 1)
            for k in range(8):
                a = k * (math.pi / 4.0)
                x1 = arena.centerx + math.cos(a) * 92
                y1 = arena.centery + math.sin(a) * 92
                x2 = arena.centerx + math.cos(a) * 134
                y2 = arena.centery + math.sin(a) * 134
                pygame.draw.line(surf, (62, 62, 62), (int(x1), int(y1)), (int(x2), int(y2)), 1)

    def _bake_background(self):
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        bg = gray(self.theme["bg"])
        wall = gray(self.scheme["wall"])
        wall_top = gray(self.theme["wall_top"])
        trim = gray(self.scheme["trim"])
        fa = gray(self.scheme["floor_a"])
        fb = gray(self.scheme["floor_b"])
        surf.fill(bg)

        outer_rect = pygame.Rect(PLAYABLE_LEFT - 38, PLAYABLE_TOP - 46, PLAYABLE_RIGHT - PLAYABLE_LEFT + 76, PLAYABLE_BOTTOM - PLAYABLE_TOP + 86)
        arena = pygame.Rect(PLAYABLE_LEFT, PLAYABLE_TOP, PLAYABLE_RIGHT - PLAYABLE_LEFT, PLAYABLE_BOTTOM - PLAYABLE_TOP)

        # Layered outer brick masonry flanking the chamber so 16:9 and wide wings match seamlessly
        outer_bw, outer_bh = 64, 38
        outer_hi = min(60, wall_top[0] + 10)
        for row_i, by in enumerate(range(0, SCREEN_HEIGHT, outer_bh)):
            shift = (row_i % 2) * (outer_bw // 2)
            for bx in range(-shift, SCREEN_WIDTH, outer_bw):
                if outer_rect.left + 8 <= bx and bx + outer_bw <= outer_rect.right - 8 and outer_rect.top + 8 <= by and by + outer_bh <= outer_rect.bottom - 8:
                    continue
                lum = int(clamp(bg[0] + 8 + self.rng.randint(-2, 6), 6, 44))
                rc = pygame.Rect(bx + 2, by + 2, outer_bw - 4, outer_bh - 4)
                pygame.draw.rect(surf, (lum, lum, lum), rc, border_radius=3)
                pygame.draw.line(surf, (outer_hi, outer_hi, outer_hi), (rc.left + 2, rc.top + 1), (rc.right - 2, rc.top + 1), 1)
                pygame.draw.line(surf, (max(4, lum - 5), max(4, lum - 5), max(4, lum - 5)), (rc.left + 2, rc.bottom - 1), (rc.right - 2, rc.bottom - 1), 1)

        self._draw_wall_masonry(surf, outer_rect, arena, wall, wall_top, trim)
        self._draw_floor_masonry(surf, arena, fa, fb)

        ao = pygame.Surface((arena.w, arena.h), pygame.SRCALPHA)
        for i in range(30):
            a = int(146 * ((30 - i) / 30.0) ** 2.1)
            pygame.draw.rect(ao, (0, 0, 0, a), (i, i, max(1, arena.w - i * 2), max(1, arena.h - i * 2)), 1)
        surf.blit(ao, arena.topleft)
        pygame.draw.rect(surf, trim, arena, 2)

        for tx, ty in self.torch_positions:
            draw_aa_circle(surf, (16, 16, 16), tx, ty, 12)
            draw_aa_circle(surf, (78, 78, 78), tx, ty, 8)
            draw_aa_circle(surf, (148, 148, 148), tx, ty, 4)

        if pygame.display.get_init() and pygame.display.get_surface() is not None:
            surf = surf.convert()
        self._baked_bg = surf

    def release_baked_bg(self):
        self._baked_bg = None

    def update(self, dt=1.0):
        for p in self.pickups:
            p.update(dt)
        for ped in self.pedestals:
            ped.update(dt)
        for b in self.beggars:
            b.update(dt)
        for sk in self.shopkeepers:
            if hasattr(sk, "update"):
                sk.update(dt)
        for m in self.machines:
            m.update(dt)
        for mon in self.monoliths:
            mon.update(dt)
        for npc in self.mystical_npcs:
            npc.update(dt)
        if self.sacrifice_spike is not None:
            self.sacrifice_spike.update(dt)
        for dm in self.dust_motes:
            dm["x"] += dm["vx"] * dt
            dm["y"] += dm["vy"] * dt
            if dm["y"] < PLAYABLE_TOP + 10:
                dm["y"] = PLAYABLE_BOTTOM - 12
                dm["x"] = random.uniform(PLAYABLE_LEFT + 30, PLAYABLE_RIGHT - 30)

    def update_turrets(self, dt=1.0, players=None, enemy_projectiles=None):
        if not players or enemy_projectiles is None or self.cleared:
            return
        active_targets = [
            p for p in players
            if p is not None and not getattr(p, "is_dead", lambda: False)() and getattr(p, "invis_timer", 0.0) <= 0.0
        ]
        for obs in self.obstacles:
            if not obs.alive or obs.kind != "turret":
                continue
            if obs.fire_flash > 0.0:
                obs.fire_flash = max(0.0, obs.fire_flash - dt)
            if not active_targets:
                continue
            cx, cy = obs.rect.center
            target = min(active_targets, key=lambda p: (p.x - cx) ** 2 + (p.y - cy) ** 2)
            obs.aim_angle = math.atan2(target.y - cy, target.x - cx)
            obs.fire_cd -= dt
            if obs.fire_cd <= 0.0:
                sx = cx + math.cos(obs.aim_angle) * (obs.size * 0.48)
                sy = cy + math.sin(obs.aim_angle) * (obs.size * 0.48)
                spd = 4.2 + min(1.8, self.floor_level * 0.25)
                enemy_projectiles.append(EnemyProjectile(sx, sy, math.cos(obs.aim_angle) * spd, math.sin(obs.aim_angle) * spd, radius=5.5))
                obs.fire_flash = 10.0
                obs.fire_cd = max(58.0, 108.0 - self.floor_level * 5.0)

    def get_dynamic_light_sources(self, players=None):
        lights = []
        for tx, ty in self.torch_positions:
            lights.append((float(tx), float(ty), 230.0, 0.95))
        for obs in self.obstacles:
            if not obs.alive:
                continue
            if obs.kind == "brazier":
                lights.append((float(obs.rect.centerx), float(obs.rect.centery), 250.0, 1.1))
            elif obs.kind == "turret":
                lights.append((float(obs.rect.centerx), float(obs.rect.centery), 150.0, 0.55))
        for mon in self.monoliths:
            if getattr(mon, "alive", True):
                lights.append((float(mon.x), float(mon.y), 190.0, 0.7))
        for m in self.machines:
            ls = m.get_light_source() if hasattr(m, "get_light_source") else None
            if ls is not None:
                lights.append((ls[0], ls[1], ls[2], ls[3]))
        for p in (players or ()):
            if p is not None and not getattr(p, "is_dead", lambda: False)():
                rad = 260.0 * clamp(float(getattr(p, "lantern_fuel", 1.0)), 0.45, 1.6)
                lights.append((float(p.x), float(p.y), rad, 1.15))
        return lights

    def draw(self, screen, time_acc=0.0, light_sources=None):
        if self._baked_bg is None:
            self._bake_background()
        screen.blit(self._baked_bg, (0, 0))

        for idx, (tx, ty) in enumerate(self.torch_positions):
            flicker = 0.5 + 0.5 * math.sin(time_acc * 0.18 + idx * 1.7)
            step = int(clamp(round(flicker * 5.0), 0, 5))
            t_spr = _get_flame_sprite("torch", step)
            screen.blit(t_spr, (tx - t_spr.get_width() // 2, ty - 1 - t_spr.get_height() // 2))

        dust_mult = float(get_effects_config().get("dust_mult", 1.0))
        max_dust = max(0, int(round(len(self.dust_motes) * dust_mult)))
        for dm in self.dust_motes[:max_dust]:
            p_surf = get_particle_surf(dm["r"], dm["lum"], dm["alpha"])
            screen.blit(p_surf, (int(round(dm["x"] - p_surf.get_width() * 0.5)), int(round(dm["y"] - p_surf.get_height() * 0.5))))

        if self.dice_floor is not None:
            self.dice_floor.draw(screen)
        if self.sacrifice_spike is not None:
            self.sacrifice_spike.draw(screen)
        if self.trapdoor_rect is not None:
            pygame.draw.rect(screen, (216, 216, 216), self.trapdoor_rect.inflate(8, 8), border_radius=8)
            pygame.draw.rect(screen, (10, 10, 10), self.trapdoor_rect, border_radius=6)
            for ry in range(self.trapdoor_rect.top + 8, self.trapdoor_rect.bottom - 4, 9):
                pygame.draw.line(screen, (148, 148, 148), (self.trapdoor_rect.left + 8, ry), (self.trapdoor_rect.right - 8, ry), 2)
        if self.victory_portal_rect is not None:
            vcx, vcy = self.victory_portal_rect.center
            pulse = 0.5 + 0.5 * math.sin(time_acc * 0.14)
            step = int(clamp(round(pulse * 5.0), 0, 5))
            p_spr = _get_portal_sprite(step)
            screen.blit(p_spr, (vcx - p_spr.get_width() // 2, vcy - p_spr.get_height() // 2))

        if light_sources is None:
            light_sources = self.get_dynamic_light_sources()
        for obs in self.obstacles:
            obs.draw(screen, self.theme, time_acc, light_sources=light_sources)
        for mon in self.monoliths:
            mon.draw(screen)
        for npc in self.mystical_npcs:
            npc.draw(screen)
        is_curse_room = self.room_type == "curse"
        for door in self.doors.values():
            door.draw(screen, self.cleared, force_curse_spikes=is_curse_room)
        if self.devil_door is not None:
            self.devil_door.draw(screen, True, force_curse_spikes=False)
        for sk in self.shopkeepers:
            sk.draw(screen)
        for m in self.machines:
            m.draw(screen)
        for b in self.beggars:
            b.draw(screen)


_WIDE_BACKDROP_CACHE = {}


def draw_wide_backdrop(screen, view_w, world_ox, theme=None, extra_pad=28):
    if world_ox <= 0 or view_w <= SCREEN_WIDTH:
        return
    th = theme if isinstance(theme, dict) else get_floor_theme(1)
    bg = gray(th.get("bg", (8, 8, 8)))
    wall = gray(th.get("wall", (14, 14, 14)))
    wall_top = gray(th.get("wall_top", (30, 30, 30)))
    wall_trim = gray(th.get("wall_trim", (74, 74, 74)))
    pad = max(0, int(extra_pad))
    key = (int(view_w), int(world_ox), pad, int(bg[0]), int(wall[0]), int(wall_top[0]), int(wall_trim[0]))
    cached = _WIDE_BACKDROP_CACHE.get(key)
    if cached is not None:
        left_wing, right_wing = cached
        screen.blit(left_wing, (0, 0))
        screen.blit(right_wing, (max(0, world_ox + SCREEN_WIDTH - pad), 0))
        return

    _prune_cache(_WIDE_BACKDROP_CACHE, 24)
    wing_w = world_ox + pad
    right_x = max(0, world_ox + SCREEN_WIDTH - pad)
    right_w = max(1, view_w - right_x)

    def _build_wing(w_px, is_right):
        s = pygame.Surface((max(1, w_px), SCREEN_HEIGHT))
        s.fill(bg)
        rng = random.Random(4201 if not is_right else 4202)

        # Layer 1 (Back depth): larger chiseled stone masonry blocks
        brick_w = 72
        brick_h = 44
        for row_i, by in enumerate(range(0, SCREEN_HEIGHT, brick_h)):
            shift = (row_i % 2) * (brick_w // 2)
            for bx in range(-shift, w_px, brick_w):
                lum = int(clamp(bg[0] + 7 + rng.randint(-2, 6), 6, 40))
                rc = pygame.Rect(bx + 2, by + 2, brick_w - 4, brick_h - 4)
                pygame.draw.rect(s, (lum, lum, lum), rc, border_radius=4)
                hi = min(58, lum + 9)
                lo = max(4, lum - 5)
                pygame.draw.line(s, (hi, hi, hi), (rc.left + 3, rc.top + 1), (rc.right - 3, rc.top + 1), 1)
                pygame.draw.line(s, (lo, lo, lo), (rc.left + 3, rc.bottom - 1), (rc.right - 3, rc.bottom - 1), 1)

        # Layer 2 (Foreground relief): stepped inner stone buttress wall framing the dungeon chamber
        inner_span = min(w_px, max(44, int((w_px - pad) * 0.48) + pad))
        layer_x = 0 if is_right else max(0, w_px - inner_span)
        fg_bw = 62
        fg_bh = 38
        for row_i, by in enumerate(range(0, SCREEN_HEIGHT, fg_bh)):
            shift = ((row_i + 1) % 2) * (fg_bw // 2)
            for bx in range(layer_x - shift, layer_x + inner_span, fg_bw):
                x0 = max(layer_x, bx + 2)
                x1 = min(layer_x + inner_span, bx + fg_bw - 2)
                if x1 - x0 < 10:
                    continue
                lum = int(clamp(wall[0] + 8 + rng.randint(-2, 5), 10, 48))
                rc = pygame.Rect(x0, by + 2, x1 - x0, fg_bh - 4)
                pygame.draw.rect(s, (lum, lum, lum), rc, border_radius=3)
                hi = min(68, lum + 11)
                pygame.draw.line(s, (hi, hi, hi), (rc.left + 2, rc.top + 1), (rc.right - 2, rc.top + 1), 1)

        # Architectural pilaster molding separating outer masonry from the stepped inner course
        pil_x = (layer_x + inner_span - 8) if is_right else layer_x
        pygame.draw.rect(s, (max(8, wall[0]), max(8, wall[0]), max(8, wall[0])), (pil_x, 0, 8, SCREEN_HEIGHT))
        pygame.draw.line(s, (min(88, wall_trim[0]), min(88, wall_trim[0]), min(88, wall_trim[0])), (pil_x, 0), (pil_x, SCREEN_HEIGHT), 1)
        pygame.draw.line(s, (min(88, wall_trim[0]), min(88, wall_trim[0]), min(88, wall_trim[0])), (pil_x + 7, 0), (pil_x + 7, SCREEN_HEIGHT), 1)

        # Soft vignette gradient toward the outer screen edges (never hides brick detail completely)
        fade = pygame.Surface((max(1, w_px), SCREEN_HEIGHT), pygame.SRCALPHA)
        visible_w = max(1, w_px - pad)
        for x in range(w_px):
            if is_right:
                dist_edge = max(0, w_px - 1 - x)
            else:
                dist_edge = max(0, x)
            outer_t = 1.0 - min(1.0, dist_edge / float(visible_w))
            a = int(clamp(16 + (outer_t ** 1.4) * 124, 0, 155))
            pygame.draw.line(fade, (bg[0], bg[1], bg[2], a), (x, 0), (x, SCREEN_HEIGHT))
        seam_x = pad if is_right else max(0, w_px - 1 - pad)
        pygame.draw.line(fade, (wall_top[0], wall_top[1], wall_top[2], 96), (seam_x, 0), (seam_x, SCREEN_HEIGHT), 2)
        s.blit(fade, (0, 0))
        return _finalize_surf(s)

    pair = (_build_wing(wing_w, False), _build_wing(right_w, True))
    _WIDE_BACKDROP_CACHE[key] = pair
    screen.blit(pair[0], (0, 0))
    screen.blit(pair[1], (right_x, 0))
