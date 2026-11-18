import json
import math
import os
import shutil
import sys
import tempfile
import pygame
import pygame.gfxdraw

try:
    from PIL import Image, ImageFilter
    HAS_PIL = True
except Exception:
    Image = None
    ImageFilter = None
    HAS_PIL = False

BASE_WIDTH = 1280
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60
GAME_VERSION = "Alpha 1.0"
TITLE = f"Подземелье Тьмы · DarkVault {GAME_VERSION}"

_VIEW_WIDTH = BASE_WIDTH


def get_view_width():
    return _VIEW_WIDTH


def get_view_size():
    return (_VIEW_WIDTH, SCREEN_HEIGHT)


def get_world_offset_x():
    return max(0, (_VIEW_WIDTH - BASE_WIDTH) // 2)


def set_view_width(width):
    global _VIEW_WIDTH
    nw = int(clamp(round(float(width) / 8.0) * 8, BASE_WIDTH, 1840))
    changed = nw != _VIEW_WIDTH
    _VIEW_WIDTH = nw
    return changed

TARGET_FLOOR_COUNT = 5

ROOM_MARGIN_X = 84
ROOM_MARGIN_Y = 72
PLAYABLE_LEFT = 84
PLAYABLE_RIGHT = 1196
PLAYABLE_TOP = 88
PLAYABLE_BOTTOM = 648
DOOR_WIDTH = 86
DOOR_THICKNESS = 26

BLACK = (5, 5, 5)
WHITE = (245, 245, 245)

GAME_MODES = [
    "classic",
    "fading_light",
    "endless_abyss",
    "free_roam",
    "boss_rush",
    "chaos_draft",
]

ENDLESS_MODIFIERS = [
    {"id": "ashen_mist", "ru": "Пепельный туман", "en": "Ashen Mist", "ambient_mult": 0.85, "hp_mult": 1.15, "spd_mult": 1.04},
    {"id": "abyss_frenzy", "ru": "Ярость Бездны", "en": "Abyssal Frenzy", "ambient_mult": 0.95, "hp_mult": 1.10, "spd_mult": 1.12},
    {"id": "stone_curse", "ru": "Проклятие камня", "en": "Stone Curse", "ambient_mult": 0.82, "hp_mult": 1.25, "spd_mult": 1.00},
    {"id": "echo_of_void", "ru": "Эхо Пустоты", "en": "Echo of the Void", "ambient_mult": 0.78, "hp_mult": 1.20, "spd_mult": 1.08},
]

FLOOR_THEMES = {
    1: {
        "bg": (9, 9, 9),
        "floor_a": (31, 31, 31),
        "floor_b": (26, 26, 26),
        "floor_speck": (42, 42, 42),
        "wall": (15, 15, 15),
        "wall_top": (38, 38, 38),
        "wall_trim": (78, 78, 78),
        "wall_inner": (102, 102, 102),
        "rock": (86, 86, 86),
        "rock_hi": (134, 134, 134),
        "poop": (98, 98, 98),
        "pit": (4, 4, 4),
        "fog": (156, 156, 156),
        "ambient": 0.38,
        "tile_style": "ashlar",
    },
    2: {
        "bg": (8, 8, 8),
        "floor_a": (26, 26, 26),
        "floor_b": (21, 21, 21),
        "floor_speck": (38, 38, 38),
        "wall": (13, 13, 13),
        "wall_top": (32, 32, 32),
        "wall_trim": (70, 70, 70),
        "wall_inner": (92, 92, 92),
        "rock": (78, 78, 78),
        "rock_hi": (124, 124, 124),
        "poop": (90, 90, 90),
        "pit": (4, 4, 4),
        "fog": (142, 142, 142),
        "ambient": 0.33,
        "tile_style": "cobbled",
    },
    3: {
        "bg": (7, 7, 7),
        "floor_a": (23, 23, 23),
        "floor_b": (18, 18, 18),
        "floor_speck": (34, 34, 34),
        "wall": (11, 11, 11),
        "wall_top": (28, 28, 28),
        "wall_trim": (66, 66, 66),
        "wall_inner": (88, 88, 88),
        "rock": (74, 74, 74),
        "rock_hi": (118, 118, 118),
        "poop": (84, 84, 84),
        "pit": (3, 3, 3),
        "fog": (132, 132, 132),
        "ambient": 0.29,
        "tile_style": "catacomb",
    },
    4: {
        "bg": (6, 6, 6),
        "floor_a": (20, 20, 20),
        "floor_b": (15, 15, 15),
        "floor_speck": (31, 31, 31),
        "wall": (10, 10, 10),
        "wall_top": (25, 25, 25),
        "wall_trim": (62, 62, 62),
        "wall_inner": (84, 84, 84),
        "rock": (70, 70, 70),
        "rock_hi": (114, 114, 114),
        "poop": (80, 80, 80),
        "pit": (3, 3, 3),
        "fog": (124, 124, 124),
        "ambient": 0.26,
        "tile_style": "obsidian",
    },
    5: {
        "bg": (5, 5, 5),
        "floor_a": (17, 17, 17),
        "floor_b": (12, 12, 12),
        "floor_speck": (28, 28, 28),
        "wall": (8, 8, 8),
        "wall_top": (22, 22, 22),
        "wall_trim": (58, 58, 58),
        "wall_inner": (80, 80, 80),
        "rock": (66, 66, 66),
        "rock_hi": (112, 112, 112),
        "poop": (76, 76, 76),
        "pit": (2, 2, 2),
        "fog": (116, 116, 116),
        "ambient": 0.23,
        "tile_style": "abyss",
    },
}


def get_floor_theme(level):
    lv = int(level)
    if lv in FLOOR_THEMES:
        return dict(FLOOR_THEMES[lv])
    base = dict(FLOOR_THEMES[((lv - 1) % 5) + 1])
    depth_shift = min(6, max(0, lv - 5))
    base["ambient"] = max(0.19, base["ambient"] - depth_shift * 0.008)
    return base


ROOM_COLOR_SCHEMES = {
    "start": {"floor_a": (31, 31, 31), "floor_b": (26, 26, 26), "wall": (15, 15, 15), "trim": (82, 82, 82), "accent": (218, 218, 218)},
    "normal": {"floor_a": (29, 29, 29), "floor_b": (24, 24, 24), "wall": (14, 14, 14), "trim": (72, 72, 72), "accent": (182, 182, 182)},
    "boss": {"floor_a": (22, 22, 22), "floor_b": (17, 17, 17), "wall": (10, 10, 10), "trim": (102, 102, 102), "accent": (240, 240, 240)},
    "miniboss": {"floor_a": (24, 24, 24), "floor_b": (19, 19, 19), "wall": (12, 12, 12), "trim": (90, 90, 90), "accent": (224, 224, 224)},
    "treasure": {"floor_a": (37, 37, 37), "floor_b": (32, 32, 32), "wall": (19, 19, 19), "trim": (122, 122, 122), "accent": (248, 248, 248)},
    "shop": {"floor_a": (38, 38, 38), "floor_b": (33, 33, 33), "wall": (20, 20, 20), "trim": (110, 110, 110), "accent": (232, 232, 232)},
    "curse": {"floor_a": (18, 18, 18), "floor_b": (13, 13, 13), "wall": (8, 8, 8), "trim": (92, 92, 92), "accent": (208, 208, 208)},
    "arcade": {"floor_a": (31, 31, 31), "floor_b": (26, 26, 26), "wall": (16, 16, 16), "trim": (98, 98, 98), "accent": (236, 236, 236)},
    "sacrifice": {"floor_a": (24, 24, 24), "floor_b": (19, 19, 19), "wall": (11, 11, 11), "trim": (96, 96, 96), "accent": (240, 240, 240)},
    "library": {"floor_a": (35, 35, 35), "floor_b": (30, 30, 30), "wall": (18, 18, 18), "trim": (112, 112, 112), "accent": (230, 230, 230)},
    "dice": {"floor_a": (33, 33, 33), "floor_b": (28, 28, 28), "wall": (17, 17, 17), "trim": (106, 106, 106), "accent": (242, 242, 242)},
    "secret": {"floor_a": (25, 25, 25), "floor_b": (20, 20, 20), "wall": (13, 13, 13), "trim": (86, 86, 86), "accent": (216, 216, 216)},
    "devil": {"floor_a": (15, 15, 15), "floor_b": (10, 10, 10), "wall": (6, 6, 6), "trim": (114, 114, 114), "accent": (248, 248, 248)},
}

PALETTE = {
    "bg_dark": (5, 5, 5),
    "panel_bg": (15, 15, 15),
    "panel_border": (84, 84, 84),
    "text_main": (244, 244, 244),
    "text_muted": (168, 168, 168),
    "text_dim": (112, 112, 112),
    "accent": (240, 240, 240),
    "accent_soft": (196, 196, 196),
    "heart_full": (238, 238, 238),
    "heart_empty": (46, 46, 46),
    "soul_heart": (198, 198, 198),
    "black_heart": (36, 36, 36),
    "coin": (224, 224, 224),
    "bomb": (164, 164, 164),
    "key": (210, 210, 210),
    "hud_bar": (14, 14, 14),
    "tears": (246, 246, 246),
    "tears_rim": (26, 26, 26),
    "enemy_shot": (22, 22, 22),
    "enemy_shot_rim": (244, 244, 244),
}

ENEMY_BASE_STATS = {
    "fly": {"hp": 10, "speed": 2.0, "radius": 13},
    "spider": {"hp": 12, "speed": 3.0, "radius": 13},
    "pooter": {"hp": 14, "speed": 1.4, "radius": 15},
    "gaper": {"hp": 22, "speed": 2.0, "radius": 17},
    "maggot": {"hp": 18, "speed": 2.1, "radius": 14},
    "clot": {"hp": 26, "speed": 1.3, "radius": 16},
    "hopper": {"hp": 20, "speed": 3.4, "radius": 15},
    "horf": {"hp": 22, "speed": 0.4, "radius": 17},
    "bony": {"hp": 28, "speed": 1.6, "radius": 16},
    "vis": {"hp": 34, "speed": 1.2, "radius": 19},
    "boil": {"hp": 28, "speed": 0.0, "radius": 18},
    "leech": {"hp": 20, "speed": 2.8, "radius": 13},
    "shadow_weaver": {"hp": 32, "speed": 2.3, "radius": 17},
    "whispering_phantom": {"hp": 28, "speed": 2.4, "radius": 16},
    "mimic_double": {"hp": 38, "speed": 2.9, "radius": 18},
    "many_eyed_watcher": {"hp": 40, "speed": 1.35, "radius": 19},
    "ash_stalker": {"hp": 26, "speed": 3.2, "radius": 15},
    "hollow_bell": {"hp": 36, "speed": 0.85, "radius": 18},
    "thread_serpent": {"hp": 30, "speed": 2.7, "radius": 14},
    "abyss_leaper": {"hp": 28, "speed": 2.9, "radius": 17},
    "mortar_cultist": {"hp": 26, "speed": 1.25, "radius": 16},
    "cinder_bomber": {"hp": 24, "speed": 2.35, "radius": 15},
    "pulse_sentinel": {"hp": 36, "speed": 1.1, "radius": 18},
    "mirage_stalker": {"hp": 30, "speed": 2.8, "radius": 16},
    "vortex_mage": {"hp": 32, "speed": 1.35, "radius": 17},
    "chain_warden": {"hp": 38, "speed": 1.75, "radius": 18},
}

def is_android_apk():
    """Return True when running from an APK build containing the build-time android_build.json marker."""
    try:
        marker = os.path.join(os.path.dirname(os.path.abspath(__file__)), "android_build.json")
        return os.path.isfile(marker)
    except Exception:
        return False


def is_android():
    return (
        is_android_apk()
        or "ANDROID_ARGUMENT" in os.environ
        or "ANDROID_PRIVATE" in os.environ
        or "ANDROID_BOOTLOGO" in os.environ
        or "ANDROID_ROOT" in os.environ
        or "ANDROID_DATA" in os.environ
        or "ANDROID_STORAGE" in os.environ
        or "P4A_BOOTSTRAP" in os.environ
        or sys.platform == "android"
    )


_CACHED_USER_DATA_DIR = None


def _migrate_legacy_linux_data(legacy_dir, target_dir):
    """Non-destructively copy legacy user files out of the Linux app install directory."""
    if not legacy_dir or not target_dir or os.path.abspath(legacy_dir) == os.path.abspath(target_dir):
        return
    if not os.path.isdir(legacy_dir):
        return
    import shutil

    user_items = (
        "accounts.json",
        "accounts.json.bak",
        "user_settings.json",
        "user_settings.json.bak",
        "save_slot_1.json",
        "save_slot_1.json.bak",
        "save_slot_2.json",
        "save_slot_2.json.bak",
        "save_slot_3.json",
        "save_slot_3.json.bak",
        "mods_config.json",
        "ai_agent_config.json",
        "quests_state.json",
        "shared_seeds.json",
        "crash_log.txt",
    )
    for fn in user_items:
        src = os.path.join(legacy_dir, fn)
        dst = os.path.join(target_dir, fn)
        if os.path.isfile(src) and not os.path.exists(dst):
            try:
                shutil.copy2(src, dst)
            except Exception:
                pass
    for sub in ("backups", "mods"):
        src_sub = os.path.join(legacy_dir, sub)
        dst_sub = os.path.join(target_dir, sub)
        if os.path.isdir(src_sub) and not os.path.exists(dst_sub):
            try:
                shutil.copytree(src_sub, dst_sub)
            except Exception:
                pass


def get_user_data_dir():
    global _CACHED_USER_DATA_DIR
    if _CACHED_USER_DATA_DIR and os.path.isdir(_CACHED_USER_DATA_DIR):
        try:
            test_f = os.path.join(_CACHED_USER_DATA_DIR, ".dv_w_check")
            with open(test_f, "w", encoding="utf-8") as tf:
                tf.write("1")
            if os.path.exists(test_f):
                os.remove(test_f)
            return _CACHED_USER_DATA_DIR
        except Exception:
            _CACHED_USER_DATA_DIR = None

    candidates = []
    legacy_linux_dir = ""
    if is_android():
        base = os.environ.get("ANDROID_PRIVATE") or os.path.dirname(os.path.abspath(__file__))
        candidates.append(os.path.join(base, "darkvault_data"))
        candidates.append(base)
    else:
        if sys.platform == "win32":
            base = os.environ.get("APPDATA") or os.path.expanduser("~")
            candidates.append(os.path.join(base, "DarkVault"))
        else:
            # Linux & POSIX: separate user saves/settings from ~/.local/share/DarkVault install dir
            xdg_data = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
            legacy_linux_dir = os.path.join(xdg_data, "DarkVault")
            candidates.append(os.path.join(xdg_data, "DarkVaultData"))
            xdg_cfg = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
            candidates.append(os.path.join(xdg_cfg, "DarkVault"))
            candidates.append(os.path.join(os.path.expanduser("~"), ".darkvault"))

        game_dir = os.path.dirname(os.path.abspath(__file__))
        candidates.append(game_dir)
        if getattr(sys, "frozen", False) and getattr(sys, "executable", None):
            candidates.append(os.path.dirname(os.path.abspath(sys.executable)))
        user_name = os.environ.get("USER", os.environ.get("USERNAME", "user"))
        candidates.append(os.path.join(tempfile.gettempdir(), f"DarkVault_{user_name}"))

    for cand in candidates:
        try:
            os.makedirs(cand, exist_ok=True)
            test_path = os.path.join(cand, ".dv_test_rw")
            with open(test_path, "w", encoding="utf-8") as tf:
                tf.write("rw_ok")
            if os.path.exists(test_path):
                os.remove(test_path)
            if legacy_linux_dir and os.path.isdir(legacy_linux_dir):
                _migrate_legacy_linux_data(legacy_linux_dir, cand)
            _CACHED_USER_DATA_DIR = cand
            return cand
        except Exception:
            continue

    fallback = os.path.dirname(os.path.abspath(__file__))
    _CACHED_USER_DATA_DIR = fallback
    return fallback


def append_crash_log(title, details):
    """Safely append a crash report to crash_log.txt with automatic size rotation."""
    try:
        import time as _time

        data_dir = get_user_data_dir()
        os.makedirs(data_dir, exist_ok=True)
        log_path = os.path.join(data_dir, "crash_log.txt")
        if os.path.isfile(log_path) and os.path.getsize(log_path) > 262144:
            bak = log_path + ".old"
            try:
                if os.path.exists(bak):
                    os.remove(bak)
                os.replace(log_path, bak)
            except Exception:
                pass
        stamp = _time.strftime("%Y-%m-%d %H:%M:%S")
        entry = (
            f"\n[{stamp}] [{sys.platform}] {title}\n"
            f"{str(details).rstrip()}\n"
            + ("-" * 60)
            + "\n"
        )
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(entry)
        return log_path
    except Exception:
        return ""


def _boot_marker_path():
    return os.path.join(get_user_data_dir(), ".boot_in_progress")


def was_unclean_boot():
    try:
        return os.path.isfile(_boot_marker_path())
    except Exception:
        return False


def mark_boot_start():
    try:
        p = _boot_marker_path()
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("1")
    except Exception:
        pass


def clear_boot_marker():
    try:
        p = _boot_marker_path()
        if os.path.exists(p):
            os.remove(p)
    except Exception:
        pass


def apply_safe_boot_settings():
    """Reset display/risky flags to safe windowed defaults after an unclean startup crash."""
    GAME_SETTINGS["fullscreen"] = False
    GAME_SETTINGS["resolution"] = "auto"
    GAME_SETTINGS["wide_mode"] = "auto"
    GAME_SETTINGS["effects_quality"] = "medium"
    GAME_SETTINGS["coop_enabled"] = False
    try:
        save_user_settings()
    except Exception:
        pass


_SETTINGS_PATH = os.path.join(get_user_data_dir(), "user_settings.json")

EFFECTS_CHOICES = ("low", "medium", "high", "ultra")
EFFECTS_PRESETS = {
    "low": {
        "light_w": 256,
        "light_h": 144,
        "shadows": False,
        "dust_mult": 0.25,
        "max_particles": 40,
        "glow": False,
        "vignette": False,
        "bloom": False,
        "smooth_scale": False,
    },
    "medium": {
        "light_w": 480,
        "light_h": 270,
        "shadows": False,
        "dust_mult": 0.65,
        "max_particles": 90,
        "glow": True,
        "vignette": True,
        "bloom": False,
        "smooth_scale": True,
    },
    "high": {
        "light_w": 960,
        "light_h": 540,
        "shadows": True,
        "dust_mult": 1.0,
        "max_particles": 170,
        "glow": True,
        "vignette": True,
        "bloom": False,
        "smooth_scale": True,
    },
    "ultra": {
        "light_w": 1280,
        "light_h": 720,
        "shadows": True,
        "dust_mult": 1.5,
        "max_particles": 260,
        "glow": True,
        "vignette": True,
        "bloom": True,
        "smooth_scale": True,
    },
}

RESOLUTION_CHOICES = ("auto", "854x480", "960x540", "1280x720", "1600x900", "1920x1080", "2560x1440")
UI_SCALE_CHOICES = ("auto", "standard", "phone")
WIDE_MODE_CHOICES = ("auto", "16:9", "19.5:9", "20:9", "21:9")
TOUCH_LAYOUT_PRESETS = ("wide", "raised", "custom")
_WIDE_RATIOS = {
    "16:9": 1280,
    "19.5:9": 1560,
    "20:9": 1600,
    "21:9": 1680,
}

KEYBIND_ACTIONS = (
    "up",
    "down",
    "left",
    "right",
    "fire_up",
    "fire_down",
    "fire_left",
    "fire_right",
    "dash",
    "jump",
    "stealth",
    "melee",
    "bomb",
    "relic",
    "quests",
)

DEFAULT_KEYBINDS = {
    "up": int(getattr(pygame, "K_w", 119)),
    "down": int(getattr(pygame, "K_s", 115)),
    "left": int(getattr(pygame, "K_a", 97)),
    "right": int(getattr(pygame, "K_d", 100)),
    "fire_up": int(getattr(pygame, "K_UP", 1073741906)),
    "fire_down": int(getattr(pygame, "K_DOWN", 1073741905)),
    "fire_left": int(getattr(pygame, "K_LEFT", 1073741904)),
    "fire_right": int(getattr(pygame, "K_RIGHT", 1073741903)),
    "dash": int(getattr(pygame, "K_LSHIFT", 1073742049)),
    "jump": int(getattr(pygame, "K_f", 102)),
    "stealth": int(getattr(pygame, "K_v", 118)),
    "melee": int(getattr(pygame, "K_x", 120)),
    "bomb": int(getattr(pygame, "K_e", 101)),
    "relic": int(getattr(pygame, "K_SPACE", 32)),
    "quests": int(getattr(pygame, "K_TAB", 9)),
}

_FALLBACK_KEY_NAMES = {
    9: "TAB",
    32: "SPACE",
    97: "A",
    98: "B",
    99: "C",
    100: "D",
    101: "E",
    102: "F",
    103: "G",
    113: "Q",
    114: "R",
    115: "S",
    118: "V",
    119: "W",
    120: "X",
    122: "Z",
    1073741903: "RIGHT",
    1073741904: "LEFT",
    1073741905: "DOWN",
    1073741906: "UP",
    1073742049: "LSHIFT",
    1073742053: "RSHIFT",
}

_DESKTOP_BOUNDS = (0, 0)


def capture_desktop_bounds():
    global _DESKTOP_BOUNDS
    if _DESKTOP_BOUNDS[0] > 0 and _DESKTOP_BOUNDS[1] > 0:
        return _DESKTOP_BOUNDS
    try:
        if pygame.display.get_init():
            info = pygame.display.Info()
            cw = int(getattr(info, "current_w", 0) or 0)
            ch = int(getattr(info, "current_h", 0) or 0)
            if cw >= 320 and ch >= 240:
                _DESKTOP_BOUNDS = (cw, ch)
    except Exception:
        pass
    return _DESKTOP_BOUNDS


def get_desktop_bounds():
    return _DESKTOP_BOUNDS


def get_native_display_size(fallback=(1280, 720)):
    """Return physical display resolution from pygame.display.Info() when available."""
    try:
        if pygame.display.get_init():
            info = pygame.display.Info()
            cw = int(getattr(info, "current_w", 0) or 0)
            ch = int(getattr(info, "current_h", 0) or 0)
            if cw >= 320 and ch >= 240:
                return (cw, ch)
    except Exception:
        pass
    bw, bh = _DESKTOP_BOUNDS
    if bw >= 320 and bh >= 240:
        return (bw, bh)
    return tuple(fallback)


GAME_SETTINGS = {
    "language": "ru",
    "sound_enabled": True,
    "music_enabled": True,
    "music_track": 0,
    "shake_enabled": True,
    "show_fps": False,
    "fullscreen": False,
    "console_enabled": False,
    "touch_controls": "auto",
    "touch_layout_preset": "wide",
    "touch_custom_offsets": {},
    "effects_quality": "medium" if is_android() else "high",
    "resolution": "auto",
    "ui_scale": "auto",
    "wide_mode": "auto",
    "coop_enabled": False,
    "p2_hero_id": "magdalene",
    "shared_seed": "DV-GENESIS-001",
    "github_token": "",
    "keybinds": dict(DEFAULT_KEYBINDS),
}


def get_keybind(action):
    kmap = GAME_SETTINGS.get("keybinds")
    if isinstance(kmap, dict) and action in kmap:
        try:
            return int(kmap[action])
        except Exception:
            pass
    return int(DEFAULT_KEYBINDS.get(action, 0))


def set_keybind(action, key_code):
    if action not in KEYBIND_ACTIONS:
        return False
    kmap = GAME_SETTINGS.setdefault("keybinds", dict(DEFAULT_KEYBINDS))
    if not isinstance(kmap, dict):
        kmap = dict(DEFAULT_KEYBINDS)
        GAME_SETTINGS["keybinds"] = kmap
    code = int(key_code)
    # Swap cleanly if another action already used this key
    prev_code = int(kmap.get(action, DEFAULT_KEYBINDS[action]))
    for other_act, other_code in list(kmap.items()):
        if other_act != action and int(other_code) == code:
            kmap[other_act] = prev_code
    kmap[action] = code
    return True


def reset_keybinds():
    GAME_SETTINGS["keybinds"] = dict(DEFAULT_KEYBINDS)
    return dict(DEFAULT_KEYBINDS)


def format_key_name(key_code):
    try:
        code = int(key_code)
    except Exception:
        return "?"
    if code in _FALLBACK_KEY_NAMES:
        return _FALLBACK_KEY_NAMES[code]
    try:
        if hasattr(pygame, "key") and hasattr(pygame.key, "name"):
            name = str(pygame.key.name(code)).strip()
            if name:
                return name.replace("left ", "L").replace("right ", "R").upper()[:8]
    except Exception:
        pass
    if 32 <= code <= 126:
        return chr(code).upper()
    return f"K{code}"


def compute_wide_view_width(display_w=0, display_h=0):
    mode = GAME_SETTINGS.get("wide_mode", "auto")
    if mode in _WIDE_RATIOS:
        return _WIDE_RATIOS[mode]
    if display_w > 0 and display_h > 0:
        w = float(display_w)
        h = float(display_h)
        if is_android() and h > w:
            w, h = h, w
        ratio = w / max(1.0, h)
        if ratio >= 1.79:
            raw = int(round((SCREEN_HEIGHT * ratio) / 8.0) * 8)
            return int(clamp(raw, BASE_WIDTH, 1840))
    return BASE_WIDTH


def get_effects_config():
    q = GAME_SETTINGS.get("effects_quality", "high")
    if q not in EFFECTS_PRESETS:
        q = "medium" if is_android() else "high"
    base = EFFECTS_PRESETS[q]
    if is_android():
        tuned = dict(base)
        if q != "ultra":
            tuned["light_w"] = min(int(tuned["light_w"]), 360)
            tuned["light_h"] = min(int(tuned["light_h"]), 202)
            tuned["max_particles"] = min(int(tuned["max_particles"]), 72)
            tuned["dust_mult"] = min(float(tuned["dust_mult"]), 0.45)
            tuned["bloom"] = False
        tuned["smooth_scale"] = False
        return tuned
    return base


def get_resolution_choice():
    res = str(GAME_SETTINGS.get("resolution", "auto"))
    if res == "auto" or "x" not in res:
        return None
    try:
        w_s, h_s = res.split("x", 1)
        return (max(640, int(w_s)), max(360, int(h_s)))
    except Exception:
        return None


def get_resolution_light_scale():
    rc = get_resolution_choice()
    if rc is None:
        return 0.78 if is_android() else 1.0
    rw = rc[0]
    if rw <= 860:
        return 0.72
    if rw <= 980:
        return 0.84
    if rw <= 1300:
        return 0.85 if is_android() else 1.0
    if rw <= 1620:
        return 1.15
    if rw <= 1960:
        return 1.28
    return 1.45


def is_phone_layout(touch_active=False):
    mode = GAME_SETTINGS.get("ui_scale", "auto")
    if mode == "phone":
        return True
    if mode == "standard":
        return False
    if is_android() or touch_active:
        return True
    try:
        if get_view_width() <= 860:
            return True
    except Exception:
        pass
    return False


def get_ui_scale(touch_active=False):
    """Return UI scaling factor (1.35x on mobile/phone layouts for comfortable finger taps)."""
    return 1.35 if is_phone_layout(touch_active) else 1.06


def atomic_write_json(path, data, indent=2, ensure_ascii=False, backup=True, verify=True):
    """Atomically write JSON via a .tmp file, fsync, optional verification, .bak backup, and os.replace."""
    if not path:
        return False, "empty_path"
    tmp_path = f"{path}.tmp"
    bak_path = f"{path}.bak"
    try:
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=ensure_ascii, indent=indent)
            fh.flush()
            try:
                os.fsync(fh.fileno())
            except OSError:
                pass
        if verify:
            with open(tmp_path, "r", encoding="utf-8") as vf:
                json.load(vf)
        if backup and os.path.isfile(path):
            try:
                if os.path.getsize(path) > 0:
                    shutil.copy2(path, bak_path)
            except OSError:
                pass
        try:
            os.replace(tmp_path, path)
        except OSError:
            shutil.move(tmp_path, path)
        try:
            os.chmod(path, 0o666)
        except OSError:
            pass
        return True, ""
    except (OSError, TypeError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        return False, f"{type(exc).__name__}: {exc}"
    except Exception as exc:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        return False, f"{type(exc).__name__}: {exc}"


def safe_read_json(path, default=None, expected_type=None, try_backups=True, self_heal=True):
    """Safely read JSON with fallback to .bak / .tmp backups and self-healing."""
    if not path:
        return default
    candidates = [path, f"{path}.bak", f"{path}.tmp"] if try_backups else [path]
    for idx, cand in enumerate(candidates):
        try:
            if not os.path.isfile(cand) or os.path.getsize(cand) <= 0:
                continue
            with open(cand, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if expected_type is not None and not isinstance(data, expected_type):
                continue
            if idx > 0 and self_heal:
                atomic_write_json(path, data, backup=False, verify=True)
            return data
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError):
            continue
        except Exception:
            continue
    return default


def load_user_settings():
    data = safe_read_json(_SETTINGS_PATH, default=None, expected_type=dict, try_backups=True, self_heal=True)
    if isinstance(data, dict):
        for k in (
            "language",
            "sound_enabled",
            "music_enabled",
            "shake_enabled",
            "show_fps",
            "fullscreen",
            "console_enabled",
            "touch_controls",
            "touch_layout_preset",
            "touch_custom_offsets",
            "effects_quality",
            "resolution",
            "ui_scale",
            "wide_mode",
            "coop_enabled",
            "p2_hero_id",
            "shared_seed",
            "github_token",
            "keybinds",
        ):
            if k in data:
                GAME_SETTINGS[k] = data[k]
    if GAME_SETTINGS.get("effects_quality") not in EFFECTS_PRESETS:
        GAME_SETTINGS["effects_quality"] = "medium" if is_android() else "high"
    if GAME_SETTINGS.get("resolution") not in RESOLUTION_CHOICES:
        GAME_SETTINGS["resolution"] = "auto"
    if GAME_SETTINGS.get("ui_scale") not in UI_SCALE_CHOICES:
        GAME_SETTINGS["ui_scale"] = "auto"
    if GAME_SETTINGS.get("wide_mode") not in WIDE_MODE_CHOICES:
        GAME_SETTINGS["wide_mode"] = "auto"
    if GAME_SETTINGS.get("touch_layout_preset") not in TOUCH_LAYOUT_PRESETS:
        GAME_SETTINGS["touch_layout_preset"] = "wide"
    raw_offsets = GAME_SETTINGS.get("touch_custom_offsets")
    clean_offsets = {}
    if isinstance(raw_offsets, dict):
        for k, v in raw_offsets.items():
            if isinstance(k, str) and isinstance(v, (list, tuple)) and len(v) >= 2:
                try:
                    clean_offsets[k] = [round(clamp(float(v[0]), -640.0, 640.0), 1), round(clamp(float(v[1]), -380.0, 380.0), 1)]
                except Exception:
                    pass
    GAME_SETTINGS["touch_custom_offsets"] = clean_offsets
    raw_kb = GAME_SETTINGS.get("keybinds")
    clean_kb = dict(DEFAULT_KEYBINDS)
    if isinstance(raw_kb, dict):
        for act in KEYBIND_ACTIONS:
            if act in raw_kb:
                try:
                    val = int(raw_kb[act])
                    if val > 0:
                        clean_kb[act] = val
                except Exception:
                    pass
    GAME_SETTINGS["keybinds"] = clean_kb
    if is_android():
        GAME_SETTINGS["coop_enabled"] = False
        GAME_SETTINGS["fullscreen"] = True
        GAME_SETTINGS["resolution"] = "auto"
        if is_android_apk():
            if GAME_SETTINGS.get("touch_controls", "auto") == "auto":
                GAME_SETTINGS["touch_controls"] = "on"
            if GAME_SETTINGS.get("ui_scale", "auto") == "auto":
                GAME_SETTINGS["ui_scale"] = "phone"


def save_user_settings():
    ok, _ = atomic_write_json(_SETTINGS_PATH, GAME_SETTINGS, indent=2, ensure_ascii=False, backup=True, verify=True)
    return ok


load_user_settings()

_SHADOW_CACHE = {}
_GLOW_CACHE = {}
_RADIAL_LIGHT_CACHE = {}
_DISC_CACHE = {}
_PARTICLE_CACHE = {}
_PANEL_CACHE = {}
_VIGNETTE_CACHE = {}
_TEXT_CACHE = {}


def _prune_cache(cache, max_size):
    cap = max(8, int(max_size // 2)) if is_android() else int(max_size)
    if len(cache) >= cap:
        drop = max(1, cap // 4)
        for k in list(cache.keys())[:drop]:
            cache.pop(k, None)


def clear_render_caches(include_text=False):
    for c in (
        _SHADOW_CACHE,
        _GLOW_CACHE,
        _RADIAL_LIGHT_CACHE,
        _DISC_CACHE,
        _PARTICLE_CACHE,
        _PANEL_CACHE,
        _VIGNETTE_CACHE,
    ):
        c.clear()
    if include_text:
        _TEXT_CACHE.clear()


def render_text_cached(font, text, color, antialias=True):
    s = str(text)
    if len(color) >= 3:
        ckey = (int(color[0]), int(color[1]), int(color[2]))
    else:
        ckey = (244, 244, 244)
    key = (id(font), s, ckey, bool(antialias))
    surf = _TEXT_CACHE.get(key)
    if surf is not None:
        return surf
    _prune_cache(_TEXT_CACHE, 2048)
    try:
        surf = font.render(s, bool(antialias), ckey)
    except Exception:
        try:
            def_font = pygame.font.Font(None, 16)
            surf = def_font.render(s, False, ckey)
        except Exception:
            surf = pygame.Surface((max(10, len(s) * 6), 16), pygame.SRCALPHA)
            surf.fill(ckey)
    if surf is None or surf.get_width() == 0 or surf.get_height() == 0:
        surf = pygame.Surface((max(10, len(s) * 6), 16), pygame.SRCALPHA)
        surf.fill(ckey)
    _TEXT_CACHE[key] = surf
    return surf


def fit_text_surf(font, text, color, max_w, max_h=0, min_scale=0.52, antialias=True):
    """Render text and smoothly downscale (or ellipsis-truncate past min_scale) so width <= max_w."""
    s_txt = str(text)
    base = render_text_cached(font, s_txt, color, antialias=antialias)
    mw = max(8, int(round(max_w)))
    mh = max(0, int(round(max_h)))
    tw, th = base.get_size()
    if tw <= mw and (mh <= 0 or th <= mh):
        return base
    floor_s = max(0.25, float(min_scale))
    scale_x = mw / float(max(1, tw))
    scale_y = (mh / float(max(1, th))) if mh > 0 else 1.0
    if scale_x < floor_s and len(s_txt) > 3:
        max_unscaled_w = max(mw, int(mw / floor_s))
        lo, hi = 1, len(s_txt) - 1
        best = "…"
        while lo <= hi:
            mid = (lo + hi) // 2
            cand = s_txt[:mid].rstrip() + "…"
            try:
                cw = font.size(cand)[0]
            except Exception:
                cw = len(cand) * 8
            if cw <= max_unscaled_w:
                best = cand
                lo = mid + 1
            else:
                hi = mid - 1
        s_txt = best
        base = render_text_cached(font, s_txt, color, antialias=antialias)
        tw, th = base.get_size()
        scale_x = mw / float(max(1, tw))
        scale_y = (mh / float(max(1, th))) if mh > 0 else 1.0
        if tw <= mw and (mh <= 0 or th <= mh):
            return base
    scale = min(1.0, scale_x, scale_y)
    if scale >= floor_s:
        nw = max(4, min(mw, int(round(tw * scale))))
    else:
        nw = max(4, min(mw, int(round(tw * min(1.0, scale_x)))))
    nh = max(4, int(round(th * (nw / float(max(1, tw))))))
    if mh > 0 and nh > mh:
        nh = mh
        nw = max(4, min(mw, int(round(tw * (nh / float(max(1, th)))))))
    if len(color) >= 3:
        ckey = (int(color[0]), int(color[1]), int(color[2]))
    else:
        ckey = (244, 244, 244)
    key = ("fit", id(font), s_txt, ckey, bool(antialias), nw, nh)
    cached = _TEXT_CACHE.get(key)
    if cached is not None:
        return cached
    _prune_cache(_TEXT_CACHE, 2048)
    try:
        scaled = pygame.transform.smoothscale(base, (nw, nh))
    except Exception:
        scaled = base
    _TEXT_CACHE[key] = scaled
    return scaled


def blit_text_fitted(
    surf,
    rect,
    font,
    text,
    color,
    align="center",
    pad_x=8,
    pad_y=2,
    min_scale=0.50,
    antialias=True,
):
    """Draw text guaranteed to stay within rect with smooth scaling and safe clipping."""
    box = rect if isinstance(rect, pygame.Rect) else pygame.Rect(rect)
    inner_w = max(8, box.w - pad_x * 2)
    inner_h = max(8, box.h - pad_y * 2)
    ts = fit_text_surf(font, text, color, inner_w, inner_h, min_scale=min_scale, antialias=antialias)
    if align == "left":
        tx = box.x + pad_x
    elif align == "right":
        tx = box.right - pad_x - ts.get_width()
    else:
        tx = box.centerx - ts.get_width() // 2
    ty = box.centery - ts.get_height() // 2
    clip_prev = surf.get_clip()
    clip_rc = box.inflate(-max(2, min(pad_x, box.w // 4)), -2) if box.w > 8 and box.h > 6 else box
    surf.set_clip(clip_rc)
    surf.blit(ts, (tx, ty))
    surf.set_clip(clip_prev)
    return ts


def clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def lerp(a, b, t):
    return a + (b - a) * t


def ease_in_out(t):
    t = clamp(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def ease_out_cubic(t):
    t = clamp(t, 0.0, 1.0)
    return 1.0 - (1.0 - t) ** 3


def spring_step(cur, vel, target, stiffness=0.18, damping=0.76, dt=1.0):
    force = (target - cur) * stiffness
    vel = (vel + force * dt) * (damping ** dt)
    cur = cur + vel * dt
    return cur, vel


def angle_slerp(cur_a, target_a, t):
    diff = (target_a - cur_a + math.pi) % (2.0 * math.pi) - math.pi
    return cur_a + diff * clamp(t, 0.0, 1.0)


def m(lum, alpha=None):
    g = int(clamp(round(lum), 0, 255))
    if alpha is None:
        return (g, g, g)
    return (g, g, g, int(clamp(round(alpha), 0, 255)))


def gray(col):
    if isinstance(col, (int, float)):
        return m(col)
    if len(col) == 4:
        g = int(clamp(round((col[0] + col[1] + col[2]) / 3.0), 0, 255))
        return (g, g, g, int(clamp(round(col[3]), 0, 255)))
    g = int(clamp(round((col[0] + col[1] + col[2]) / 3.0), 0, 255))
    return (g, g, g)


def _finalize_alpha_surf(surf):
    if pygame.display.get_init() and pygame.display.get_surface() is not None:
        return surf.convert_alpha()
    return surf


def _finalize_surf(surf):
    if pygame.display.get_init() and pygame.display.get_surface() is not None:
        return surf.convert()
    return surf


def _rgba_from_bytes(buf, w, h):
    if hasattr(pygame.image, "frombytes"):
        surf = pygame.image.frombytes(bytes(buf), (w, h), "RGBA")
    else:
        surf = pygame.image.fromstring(bytes(buf), (w, h), "RGBA")
    return _finalize_alpha_surf(surf)


def pil_lanczos_blur(surf, target_w, target_h, blur_radius=0.0):
    tw, th = max(1, int(target_w)), max(1, int(target_h))
    if HAS_PIL and hasattr(pygame.image, "tobytes"):
        try:
            raw = pygame.image.tobytes(surf, "RGBA")
            img = Image.frombytes("RGBA", surf.get_size(), raw)
            if blur_radius > 0.05:
                img = img.filter(ImageFilter.GaussianBlur(radius=float(blur_radius)))
            if img.size != (tw, th):
                img = img.resize((tw, th), Image.Resampling.LANCZOS)
            out = pygame.image.frombytes(img.tobytes(), (tw, th), "RGBA")
            return _finalize_alpha_surf(out)
        except Exception:
            pass
    cur = surf
    cw, ch = cur.get_size()
    while cw > tw * 2 and ch > th * 2:
        cw = max(tw, cw // 2)
        ch = max(th, ch // 2)
        cur = pygame.transform.smoothscale(cur, (cw, ch))
    if blur_radius >= 0.8 and tw > 4 and th > 4:
        down = pygame.transform.smoothscale(cur, (max(2, int(tw * 0.55)), max(2, int(th * 0.55))))
        cur = pygame.transform.smoothscale(down, (tw, th))
    elif cur.get_size() != (tw, th):
        cur = pygame.transform.smoothscale(cur, (tw, th))
    return _finalize_alpha_surf(cur)


def render_4x_smooth(target_w, target_h, draw_fn, blur_radius=0.0):
    tw, th = max(2, int(target_w)), max(2, int(target_h))
    hi = pygame.Surface((tw * 4, th * 4), pygame.SRCALPHA)
    draw_fn(hi, tw * 4, th * 4)
    return pil_lanczos_blur(hi, tw, th, blur_radius=blur_radius)


def draw_aa_circle(surf, col, cx, cy, r):
    if not (math.isfinite(cx) and math.isfinite(cy) and math.isfinite(r)):
        return
    ix, iy, ir = int(round(cx)), int(round(cy)), int(round(r))
    if ir <= 0 or ir > 4096 or abs(ix) > 8192 or abs(iy) > 8192:
        return
    c = gray(col)
    try:
        pygame.gfxdraw.filled_circle(surf, ix, iy, ir, c)
        pygame.gfxdraw.aacircle(surf, ix, iy, ir, c)
    except Exception:
        pygame.draw.circle(surf, c[:3], (ix, iy), ir)


def draw_aa_ring(surf, col, cx, cy, r, width=1):
    if not (math.isfinite(cx) and math.isfinite(cy) and math.isfinite(r)):
        return
    ix, iy, ir = int(round(cx)), int(round(cy)), int(round(r))
    if ir <= 0 or ir > 4096 or abs(ix) > 8192 or abs(iy) > 8192:
        return
    c = gray(col)
    try:
        for w in range(max(1, int(width))):
            if ir - w >= 1:
                pygame.gfxdraw.aacircle(surf, ix, iy, ir - w, c)
    except Exception:
        pygame.draw.circle(surf, c[:3], (ix, iy), ir, max(1, int(width)))


def draw_aa_ellipse(surf, col, cx, cy, rx, ry):
    if not (math.isfinite(cx) and math.isfinite(cy) and math.isfinite(rx) and math.isfinite(ry)):
        return
    ix, iy = int(round(cx)), int(round(cy))
    irx, iry = int(round(rx)), int(round(ry))
    if irx <= 0 or iry <= 0 or irx > 4096 or iry > 4096 or abs(ix) > 8192 or abs(iy) > 8192:
        return
    c = gray(col)
    try:
        pygame.gfxdraw.filled_ellipse(surf, ix, iy, irx, iry, c)
        pygame.gfxdraw.aaellipse(surf, ix, iy, irx, iry, c)
    except Exception:
        pygame.draw.ellipse(surf, c[:3], pygame.Rect(ix - irx, iy - iry, irx * 2, iry * 2))


def draw_aa_poly(surf, col, pts):
    if len(pts) < 3:
        return
    ipts = []
    for px, py in pts:
        if not (math.isfinite(px) and math.isfinite(py)):
            return
        ipx, ipy = int(round(px)), int(round(py))
        if abs(ipx) > 8192 or abs(ipy) > 8192:
            return
        ipts.append((ipx, ipy))
    xs = [p[0] for p in ipts]
    ys = [p[1] for p in ipts]
    if max(xs) - min(xs) <= 0 and max(ys) - min(ys) <= 0:
        return
    c = gray(col)
    try:
        pygame.gfxdraw.filled_polygon(surf, ipts, c)
        pygame.gfxdraw.aapolygon(surf, ipts, c)
    except Exception:
        pygame.draw.polygon(surf, c[:3], ipts)


def get_shadow_surf(w, h, alpha=110):
    """Generate a crisp pixel-art oval shadow with stepped rings and 2x2 Bayer dithering."""
    rw = max(8, int(round(w)))
    rh = max(4, int(round(h)))
    iw = rw if rw < 14 else max(8, ((rw + 1) // 2) * 2)
    ih = rh if rh < 8 else max(4, ((rh + 1) // 2) * 2)
    ia = int(clamp((int(alpha) // 16) * 16, 16, 240))
    key = (iw, ih, ia)
    cached = _SHADOW_CACHE.get(key)
    if cached is not None:
        return cached
    _prune_cache(_SHADOW_CACHE, 256)

    # Quantize onto a crisp 3px pixel-art grid (2px for tiny shadows) so shadows match pixel graphics
    px_step = 2 if (iw <= 18 or ih <= 8) else 3
    gw = max(4, int(round(iw / float(px_step))))
    gh = max(3, int(round(ih / float(px_step))))
    buf = bytearray(gw * gh * 4)
    hx = gw * 0.5
    hy = gh * 0.5
    inv_rx = 1.0 / max(1.0, hx * 0.94)
    inv_ry = 1.0 / max(1.0, hy * 0.94)
    stride = gw * 4
    a_core = ia
    a_mid = int(ia * 0.62)
    a_edge = int(ia * 0.34)
    for y in range(gh):
        dy = (y + 0.5 - hy) * inv_ry
        dy2 = dy * dy
        row = y * stride
        for x in range(gw):
            dx = (x + 0.5 - hx) * inv_rx
            d2 = dx * dx + dy2
            if d2 <= 0.44:
                a = a_core
            elif d2 <= 0.76:
                a = a_mid
            elif d2 <= 0.98 and ((x + y) & 1) == 0:
                a = a_edge
            else:
                a = 0
            if a > 0:
                buf[row + x * 4 + 3] = a
    raw_surf = _rgba_from_bytes(buf, gw, gh)
    surf = pygame.transform.scale(raw_surf, (iw, ih))
    surf = _finalize_alpha_surf(surf)
    _SHADOW_CACHE[key] = surf
    return surf


def get_glow_surf(radius, lum=235, max_alpha=90):
    rr = max(6, int(round(radius)))
    ir = rr if rr <= 16 else max(8, ((rr + 2) // 4) * 4)
    il = int(clamp((int(lum) // 16) * 16, 0, 255))
    ia = int(clamp((int(max_alpha) // 12) * 12, 12, 255))
    key = (ir, il, ia)
    cached = _GLOW_CACHE.get(key)
    if cached is not None:
        return cached
    _prune_cache(_GLOW_CACHE, 256)
    size = ir * 2 + 4
    gs = 96
    buf = bytearray(gs * gs * 4)
    half = gs * 0.5
    inv_r = 1.0 / half
    half_i = gs // 2
    stride = gs * 4
    sqrt = math.sqrt
    for y in range(half_i):
        dy = (y + 0.5 - half) * inv_r
        dy2 = dy * dy
        row_top = y * stride
        row_bot = (gs - 1 - y) * stride
        for x in range(half_i):
            dx = (x + 0.5 - half) * inv_r
            d2 = dx * dx + dy2
            if d2 < 1.0:
                t = 1.0 - sqrt(d2)
                fall = t * t * (3.0 - 2.0 * t)
                fall = fall * (0.45 + 0.55 * t)
                a = int(ia * fall)
                if a > 0:
                    lx = x * 4
                    rx = (gs - 1 - x) * 4
                    buf[row_top + lx] = il
                    buf[row_top + lx + 1] = il
                    buf[row_top + lx + 2] = il
                    buf[row_top + lx + 3] = a
                    buf[row_top + rx] = il
                    buf[row_top + rx + 1] = il
                    buf[row_top + rx + 2] = il
                    buf[row_top + rx + 3] = a
                    buf[row_bot + lx] = il
                    buf[row_bot + lx + 1] = il
                    buf[row_bot + lx + 2] = il
                    buf[row_bot + lx + 3] = a
                    buf[row_bot + rx] = il
                    buf[row_bot + rx + 1] = il
                    buf[row_bot + rx + 2] = il
                    buf[row_bot + rx + 3] = a
    raw_surf = _rgba_from_bytes(buf, gs, gs)
    surf = pil_lanczos_blur(raw_surf, size, size, blur_radius=1.0)
    _GLOW_CACHE[key] = surf
    return surf


def get_radial_light_surf(radius, peak_lum=235):
    rr = max(12, int(round(radius)))
    ir = rr if rr <= 24 else max(12, ((rr + 2) // 4) * 4)
    il = int(clamp((int(peak_lum) // 8) * 8, 8, 255))
    key = (ir, il)
    cached = _RADIAL_LIGHT_CACHE.get(key)
    if cached is not None:
        return cached
    _prune_cache(_RADIAL_LIGHT_CACHE, 256)
    gs = 128
    buf = bytearray(gs * gs * 4)
    half = gs * 0.5
    inv_r = 1.0 / half
    half_i = gs // 2
    stride = gs * 4
    sqrt = math.sqrt
    for y in range(half_i):
        dy = (y + 0.5 - half) * inv_r
        dy2 = dy * dy
        row_top = y * stride
        row_bot = (gs - 1 - y) * stride
        for x in range(half_i):
            dx = (x + 0.5 - half) * inv_r
            d2 = dx * dx + dy2
            if d2 < 1.0:
                d = sqrt(d2)
                smooth = 1.0 - d * d * (3.0 - 2.0 * d)
                val = int(il * (smooth ** 1.65))
                if val > 0:
                    lx = x * 4
                    rx = (gs - 1 - x) * 4
                    buf[row_top + lx] = val
                    buf[row_top + lx + 1] = val
                    buf[row_top + lx + 2] = val
                    buf[row_top + lx + 3] = 255
                    buf[row_top + rx] = val
                    buf[row_top + rx + 1] = val
                    buf[row_top + rx + 2] = val
                    buf[row_top + rx + 3] = 255
                    buf[row_bot + lx] = val
                    buf[row_bot + lx + 1] = val
                    buf[row_bot + lx + 2] = val
                    buf[row_bot + lx + 3] = 255
                    buf[row_bot + rx] = val
                    buf[row_bot + rx + 1] = val
                    buf[row_bot + rx + 2] = val
                    buf[row_bot + rx + 3] = 255
    raw_surf = _rgba_from_bytes(buf, gs, gs)
    scaled = pil_lanczos_blur(raw_surf, ir * 2, ir * 2, blur_radius=1.4)
    if pygame.display.get_init() and pygame.display.get_surface() is not None:
        out = pygame.Surface((ir * 2, ir * 2)).convert()
    else:
        out = pygame.Surface((ir * 2, ir * 2))
    out.fill((0, 0, 0))
    out.blit(scaled, (0, 0))
    _RADIAL_LIGHT_CACHE[key] = out
    return out


def get_disc_sprite(radius, lum=230, outline_lum=20, hi_lum=252):
    ir = max(3, int(round(radius)))
    il = int(clamp(int(lum), 0, 255))
    iol = int(clamp(int(outline_lum), 0, 255))
    ihl = int(clamp(int(hi_lum), 0, 255))
    key = (ir, il, iol, ihl)
    cached = _DISC_CACHE.get(key)
    if cached is not None:
        return cached
    _prune_cache(_DISC_CACHE, 512)
    size = (ir + 3) * 2

    def _draw(hi, hw, hh):
        cx = cy = hw // 2
        hr = ir * 4
        draw_aa_circle(hi, (iol, iol, iol, 255), cx, cy, hr + 6)
        draw_aa_circle(hi, (il, il, il, 255), cx, cy, hr)
        shade_lum = max(0, il - 44)
        draw_aa_circle(hi, (shade_lum, shade_lum, shade_lum, 130), cx + hr * 0.14, cy + hr * 0.16, max(2, hr * 0.74))
        mid_lum = int(clamp(il + 12, 0, 255))
        draw_aa_circle(hi, (mid_lum, mid_lum, mid_lum, 180), cx - hr * 0.12, cy - hr * 0.14, max(2, hr * 0.68))
        draw_aa_circle(hi, (ihl, ihl, ihl, 230), cx - hr * 0.30, cy - hr * 0.32, max(2, hr * 0.28))

    surf = render_4x_smooth(size, size, _draw, blur_radius=0.35)
    _DISC_CACHE[key] = surf
    return surf


def get_particle_surf(radius, lum, alpha):
    ir = max(1, int(round(radius)))
    il = int(clamp((int(lum) // 8) * 8, 0, 255))
    ia = int(clamp((int(alpha) // 16) * 16, 16, 255))
    key = (ir, il, ia)
    cached = _PARTICLE_CACHE.get(key)
    if cached is not None:
        return cached
    _prune_cache(_PARTICLE_CACHE, 512)
    size = ir * 2 + 4

    def _draw(hi, hw, hh):
        draw_aa_circle(hi, (il, il, il, ia), hw // 2, hh // 2, ir * 4)

    surf = render_4x_smooth(size, size, _draw, blur_radius=0.6)
    _PARTICLE_CACHE[key] = surf
    return surf


def get_panel_surf(w, h, fill_lum=14, fill_alpha=210, border_lum=86, radius=10):
    iw = max(12, int(round(w)))
    ih = max(12, int(round(h)))
    key = (iw, ih, int(fill_lum), int(fill_alpha), int(border_lum), int(radius))
    cached = _PANEL_CACHE.get(key)
    if cached is not None:
        return cached
    _prune_cache(_PANEL_CACHE, 256)
    surf = pygame.Surface((iw, ih), pygame.SRCALPHA)
    fl = int(clamp(fill_lum, 0, 255))
    fa = int(clamp(fill_alpha, 0, 255))
    bl = int(clamp(border_lum, 0, 255))
    pygame.draw.rect(surf, (fl, fl, fl, fa), (0, 0, iw, ih), border_radius=radius)
    pygame.draw.rect(surf, (bl, bl, bl, min(255, fa + 25)), (0, 0, iw, ih), 1, border_radius=radius)
    hi = min(255, bl + 44)
    if iw > radius * 2 + 8:
        pygame.draw.line(surf, (hi, hi, hi, 84), (radius + 2, 1), (iw - radius - 3, 1), 1)
    surf = _finalize_alpha_surf(surf)
    _PANEL_CACHE[key] = surf
    return surf


def get_vignette_surf(w=SCREEN_WIDTH, h=SCREEN_HEIGHT, strength=175):
    ist = int(clamp((int(strength) // 16) * 16, 48, 224))
    key = (int(w), int(h), ist)
    cached = _VIGNETTE_CACHE.get(key)
    if cached is not None:
        return cached
    _prune_cache(_VIGNETTE_CACHE, 64)
    bw, bh = 256, 144
    buf = bytearray(bw * bh * 4)
    hx = bw * 0.5
    hy = bh * 0.5
    inv_hx = 1.0 / (bw * 0.56)
    inv_hy = 1.0 / (bh * 0.58)
    half_w = bw // 2
    half_h = bh // 2
    stride = bw * 4
    sqrt = math.sqrt
    for y in range(half_h):
        dy = (y + 0.5 - hy) * inv_hy
        dy2 = dy * dy
        row_top = y * stride
        row_bot = (bh - 1 - y) * stride
        for x in range(half_w):
            dx = (x + 0.5 - hx) * inv_hx
            r = sqrt(dx * dx + dy2)
            t = clamp((r - 0.52) / 0.74, 0.0, 1.0)
            s = t * t * (3.0 - 2.0 * t)
            a = int(ist * (s ** 1.35))
            if a > 0:
                lx = x * 4 + 3
                rx = (bw - 1 - x) * 4 + 3
                buf[row_top + lx] = a
                buf[row_top + rx] = a
                buf[row_bot + lx] = a
                buf[row_bot + rx] = a
    raw_surf = _rgba_from_bytes(buf, bw, bh)
    surf = pil_lanczos_blur(raw_surf, int(w), int(h), blur_radius=2.0)
    _VIGNETTE_CACHE[key] = surf
    return surf


def draw_monochrome_shadow(surf, x, y, w, h, alpha=105):
    sh = get_shadow_surf(w, h, alpha)
    bx = int(round((x - sh.get_width() * 0.5) / 2.0)) * 2
    by = int(round((y - sh.get_height() * 0.5) / 2.0)) * 2
    surf.blit(sh, (bx, by))


def draw_dynamic_shadow(surf, x, y, w, h, light_sources=None, air_z=0.0, alpha=110):
    """Draw pixel-snapped anchored contact shadow + directional shadow reacting to nearby lights."""
    az = max(0.0, float(air_z))
    off_x = 0.0
    off_y = 1.0 if az <= 0.5 else 2.0
    eff_alpha = float(alpha)

    # 1. Grounded contact occlusion directly beneath the entity so grounded sprites never look floating
    if az < 24.0:
        contact_fade = max(0.0, 1.0 - az / 24.0)
        c_alpha = eff_alpha * 0.72 * contact_fade
        if c_alpha >= 12.0:
            cw = max(8, w * (0.86 - 0.14 * (1.0 - contact_fade)))
            ch = max(4, h * (0.80 - 0.14 * (1.0 - contact_fade)))
            csh = get_shadow_surf(cw, ch, c_alpha)
            cx = int(round((x - csh.get_width() * 0.5) / 2.0)) * 2
            cy = int(round((y + 1.0 - csh.get_height() * 0.5) / 2.0)) * 2
            surf.blit(csh, (cx, cy))

    # 2. Directional cast shadow (tightly bounded when grounded so it stays anchored)
    if light_sources:
        best_weight = 0.0
        best_dx = 0.0
        best_dy = 0.0
        for src in light_sources:
            if not src or len(src) < 2:
                continue
            lx = float(src[0])
            ly = float(src[1])
            lrad = float(src[2]) if len(src) > 2 else 220.0
            lint = float(src[3]) if len(src) > 3 else 1.0
            dx = x - lx
            dy = y - ly
            d2 = dx * dx + dy * dy
            if d2 < 4.0:
                continue
            dist = math.sqrt(d2)
            if dist > lrad * 1.45:
                continue
            falloff = max(0.0, 1.0 - dist / (lrad * 1.45)) * lint
            if falloff > best_weight:
                best_weight = falloff
                best_dx = dx / dist
                best_dy = dy / dist
        if best_weight > 0.02:
            if az <= 0.5:
                shift = min(3.8, 1.1 + best_weight * 2.5)
                off_x = best_dx * shift
                off_y = best_dy * shift * 0.52 + 1.0
            else:
                shift = min(13.0, 2.2 + best_weight * 7.5 + az * 0.14)
                off_x = best_dx * shift
                off_y = best_dy * shift * 0.68 + 1.5
            eff_alpha = min(164.0, eff_alpha * (0.82 + best_weight * 0.30))

    elev_scale = max(0.56, 1.0 - az * 0.008)
    eff_alpha *= max(0.45, 1.0 - az * 0.011)
    sw = max(8, w * elev_scale * (1.0 + min(0.14, abs(off_x) * 0.01)))
    sh_h = max(4, h * elev_scale * (1.0 + min(0.10, abs(off_y) * 0.008)))
    sh = get_shadow_surf(sw, sh_h, eff_alpha)
    bx = int(round((x + off_x - sh.get_width() * 0.5) / 2.0)) * 2
    by = int(round((y + off_y - sh.get_height() * 0.5) / 2.0)) * 2
    surf.blit(sh, (bx, by))


def draw_monochrome_glow(surf, x, y, radius, lum=235, max_alpha=80):
    if not get_effects_config().get("glow", True):
        return
    gl = get_glow_surf(radius, lum, max_alpha)
    surf.blit(gl, (int(round(x - gl.get_width() * 0.5)), int(round(y - gl.get_height() * 0.5))))


