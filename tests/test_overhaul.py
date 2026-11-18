import os
import random
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch


def _ensure_full_pygame_stub():
    pg = sys.modules.get("pygame")
    if pg is None:
        pg = types.ModuleType("pygame")
        sys.modules["pygame"] = pg

    if not hasattr(pg, "error"):
        pg.error = RuntimeError

    if not hasattr(pg, "Rect"):
        class Rect:
            def __init__(self, x, y, w=None, h=None):
                if w is None and hasattr(x, "__len__"):
                    x, y, w, h = x
                self.x = int(x)
                self.y = int(y)
                self.w = int(w)
                self.h = int(h)

            @property
            def width(self):
                return self.w

            @property
            def height(self):
                return self.h

            @property
            def left(self):
                return self.x

            @property
            def right(self):
                return self.x + self.w

            @property
            def top(self):
                return self.y

            @property
            def bottom(self):
                return self.y + self.h

            @property
            def centerx(self):
                return self.x + self.w // 2

            @property
            def centery(self):
                return self.y + self.h // 2

            @property
            def center(self):
                return (self.centerx, self.centery)

            @property
            def topleft(self):
                return (self.x, self.y)

            @property
            def size(self):
                return (self.w, self.h)

            def colliderect(self, other):
                return not (
                    self.right <= other.left
                    or self.left >= other.right
                    or self.bottom <= other.top
                    or self.top >= other.bottom
                )

            def inflate(self, dx, dy):
                return Rect(self.x - dx // 2, self.y - dy // 2, self.w + dx, self.h + dy)

            def collidepoint(self, mx, my=None):
                if my is None and hasattr(mx, "__len__"):
                    mx, my = mx
                return self.x <= mx < self.right and self.y <= my < self.bottom

            def copy(self):
                return Rect(self.x, self.y, self.w, self.h)

        pg.Rect = Rect
    else:
        if not hasattr(pg.Rect, "center"):
            pg.Rect.center = property(lambda self: (self.centerx, self.centery))
        if not hasattr(pg.Rect, "size"):
            pg.Rect.size = property(lambda self: (self.w, self.h))
        if not hasattr(pg.Rect, "copy"):
            pg.Rect.copy = lambda self: pg.Rect(self.x, self.y, self.w, self.h)

    if not hasattr(pg, "Surface"):
        class Surface:
            def __init__(self, size, *args, **kwargs):
                self._size = (max(1, int(size[0])), max(1, int(size[1])))
                self._clip = None
                self._alpha = 255
                self._fills = []
                self._draws = 0

            def fill(self, color=None, rect=None, *args, **kwargs):
                self._fills.append((color, rect))

            def blit(self, src, dest=(0, 0), *args, **kwargs):
                self._draws += 1

            def set_alpha(self, a):
                self._alpha = a

            def set_clip(self, rect):
                self._clip = rect

            def get_clip(self):
                return self._clip

            def convert(self):
                return self

            def convert_alpha(self):
                return self

            def get_size(self):
                return self._size

            def get_width(self):
                return self._size[0]

            def get_height(self):
                return self._size[1]

            def copy(self):
                s = Surface(self._size)
                s._draws = self._draws
                return s

            def subsurface(self, rect):
                r = pg.Rect(rect) if not isinstance(rect, pg.Rect) else rect
                return Surface((max(1, r.w), max(1, r.h)))

            def get_rect(self, **kwargs):
                r = pg.Rect(0, 0, self._size[0], self._size[1])
                if "center" in kwargs:
                    cx, cy = kwargs["center"]
                    r.x = int(cx - r.w // 2)
                    r.y = int(cy - r.h // 2)
                return r

            def set_at(self, pos, col):
                self._draws += 1

            def get_at(self, pos):
                return (128, 128, 128, 255)

            def get_bitsize(self):
                return 32

        pg.Surface = Surface
    else:
        for meth_name, impl in (
            ("copy", lambda self: pg.Surface(self._size)),
            ("subsurface", lambda self, rect: pg.Surface((max(1, pg.Rect(rect).w), max(1, pg.Rect(rect).h)))),
            ("get_rect", lambda self, **kw: pg.Rect(0, 0, self.get_width(), self.get_height())),
            ("set_at", lambda self, pos, col: None),
            ("get_at", lambda self, pos: (128, 128, 128, 255)),
            ("get_bitsize", lambda self: 32),
        ):
            if not hasattr(pg.Surface, meth_name):
                setattr(pg.Surface, meth_name, impl)
        if not hasattr(pg.Rect, "center"):
            pg.Rect.center = property(lambda self: (self.centerx, self.centery))
        if not hasattr(pg.Rect, "size"):
            pg.Rect.size = property(lambda self: (self.w, self.h))
        if not hasattr(pg.Rect, "copy"):
            pg.Rect.copy = lambda self: pg.Rect(self.x, self.y, self.w, self.h)

    class _FakeFont:
        def __init__(self, size=14):
            self._size = max(8, int(size or 14))

        def render(self, text, antialias, color):
            s = str(text)
            return pg.Surface((max(8, len(s) * max(5, self._size // 2)), max(10, self._size)))

        def size(self, text):
            s = str(text)
            return (max(8, len(s) * max(5, self._size // 2)), max(10, self._size))

        def get_height(self):
            return max(10, self._size)

    pg.SRCALPHA = getattr(pg, "SRCALPHA", 65536)
    pg.FULLSCREEN = getattr(pg, "FULLSCREEN", 1)
    pg.RESIZABLE = getattr(pg, "RESIZABLE", 16)
    pg.DOUBLEBUF = getattr(pg, "DOUBLEBUF", 1073741824)
    pg.SCALED = getattr(pg, "SCALED", 512)
    pg.BLEND_MULT = getattr(pg, "BLEND_MULT", 3)
    pg.BLEND_ADD = getattr(pg, "BLEND_ADD", 1)
    pg.BLEND_RGBA_ADD = getattr(pg, "BLEND_RGBA_ADD", 6)
    pg.BLEND_RGBA_MIN = getattr(pg, "BLEND_RGBA_MIN", 8)

    for ev_name, ev_val in (
        ("QUIT", 256),
        ("KEYDOWN", 768),
        ("KEYUP", 769),
        ("TEXTINPUT", 771),
        ("MOUSEMOTION", 1024),
        ("MOUSEBUTTONDOWN", 1025),
        ("MOUSEBUTTONUP", 1026),
        ("MOUSEWHEEL", 1027),
        ("VIDEORESIZE", 32770),
        ("FINGERDOWN", 1792),
        ("FINGERUP", 1793),
        ("FINGERMOTION", 1794),
        ("APP_WILLENTERBACKGROUND", 260),
        ("APP_DIDENTERFOREGROUND", 263),
    ):
        if not hasattr(pg, ev_name):
            setattr(pg, ev_name, ev_val)

    key_codes = {
        "K_BACKSPACE": 8,
        "K_TAB": 9,
        "K_RETURN": 13,
        "K_ESCAPE": 27,
        "K_SPACE": 32,
        "K_SLASH": 47,
        "K_0": 48,
        "K_1": 49,
        "K_2": 50,
        "K_3": 51,
        "K_4": 52,
        "K_5": 53,
        "K_6": 54,
        "K_7": 55,
        "K_8": 56,
        "K_9": 57,
        "K_LEFTBRACKET": 91,
        "K_RIGHTBRACKET": 93,
        "K_BACKQUOTE": 96,
        "K_a": 97,
        "K_b": 98,
        "K_c": 99,
        "K_d": 100,
        "K_e": 101,
        "K_f": 102,
        "K_g": 103,
        "K_h": 104,
        "K_i": 105,
        "K_j": 106,
        "K_k": 107,
        "K_l": 108,
        "K_m": 109,
        "K_n": 110,
        "K_o": 111,
        "K_p": 112,
        "K_q": 113,
        "K_r": 114,
        "K_s": 115,
        "K_t": 116,
        "K_u": 117,
        "K_v": 118,
        "K_w": 119,
        "K_x": 120,
        "K_y": 121,
        "K_z": 122,
        "K_DELETE": 127,
        "K_F1": 1073741882,
        "K_F2": 1073741883,
        "K_F3": 1073741884,
        "K_F4": 1073741885,
        "K_F5": 1073741886,
        "K_F8": 1073741889,
        "K_F11": 1073741892,
        "K_HOME": 1073741898,
        "K_PAGEUP": 1073741899,
        "K_END": 1073741901,
        "K_PAGEDOWN": 1073741902,
        "K_RIGHT": 1073741903,
        "K_LEFT": 1073741904,
        "K_DOWN": 1073741905,
        "K_UP": 1073741906,
        "K_KP1": 1073741913,
        "K_KP2": 1073741914,
        "K_KP_2": 1073741914,
        "K_KP3": 1073741915,
        "K_KP4": 1073741916,
        "K_KP_4": 1073741916,
        "K_KP5": 1073741917,
        "K_KP_5": 1073741917,
        "K_KP6": 1073741918,
        "K_KP_6": 1073741918,
        "K_KP8": 1073741920,
        "K_KP_8": 1073741920,
        "K_KP9": 1073741921,
        "K_KP0": 1073741922,
        "K_KP_ENTER": 1073741912,
        "K_LSHIFT": 1073742049,
        "K_RCTRL": 1073742052,
        "K_RSHIFT": 1073742053,
        "KMOD_SHIFT": 3,
        "KMOD_CTRL": 192,
        "KMOD_ALT": 768,
    }
    for kname, kval in key_codes.items():
        if not hasattr(pg, kname):
            setattr(pg, kname, kval)

    pg.init = getattr(pg, "init", lambda: (6, 0))
    pg.quit = getattr(pg, "quit", lambda: None)
    pg.get_init = getattr(pg, "get_init", lambda: True)

    if not hasattr(pg, "gfxdraw"):
        pg.gfxdraw = types.ModuleType("pygame.gfxdraw")
    for gfn in ("filled_circle", "aacircle", "filled_polygon", "aapolygon"):
        if not hasattr(pg.gfxdraw, gfn):
            setattr(pg.gfxdraw, gfn, lambda *a, **k: None)
    sys.modules["pygame.gfxdraw"] = pg.gfxdraw

    if not hasattr(pg, "font"):
        pg.font = types.SimpleNamespace()
    pg.font.get_init = getattr(pg.font, "get_init", lambda: True)
    pg.font.init = getattr(pg.font, "init", lambda: None)
    pg.font.quit = getattr(pg.font, "quit", lambda: None)
    pg.font.SysFont = getattr(pg.font, "SysFont", lambda name, size, bold=False, **k: _FakeFont(size))
    pg.font.Font = getattr(pg.font, "Font", lambda path, size=14, **k: _FakeFont(size))

    _disp_surf = [pg.Surface((1280, 720))]
    _disp_info = types.SimpleNamespace(current_w=1280, current_h=720)

    def _set_mode(size=(1280, 720), flags=0, **kwargs):
        _disp_surf[0] = pg.Surface(size)
        return _disp_surf[0]

    if not hasattr(pg, "display"):
        pg.display = types.SimpleNamespace()
    pg.display.get_init = lambda: True
    pg.display.init = lambda: None
    pg.display.quit = lambda: None
    pg.display.set_caption = lambda title, *a: None
    pg.display.set_icon = lambda icon: None
    pg.display.set_mode = _set_mode
    pg.display.get_surface = lambda: _disp_surf[0]
    pg.display.flip = lambda: None
    pg.display.update = lambda *a: None
    pg.display.Info = lambda: _disp_info

    class _FakeMixerSound:
        def __init__(self, *a, **k):
            pass

        def play(self, *a, **k):
            pass

        def set_volume(self, *a, **k):
            pass

    if not hasattr(pg, "mixer"):
        pg.mixer = types.SimpleNamespace()
    pg.mixer.get_init = getattr(pg.mixer, "get_init", lambda: False)
    pg.mixer.init = getattr(pg.mixer, "init", lambda *a, **k: None)
    pg.mixer.stop = getattr(pg.mixer, "stop", lambda: None)
    pg.mixer.quit = getattr(pg.mixer, "quit", lambda: None)
    pg.mixer.Sound = getattr(pg.mixer, "Sound", _FakeMixerSound)

    class _KeyState:
        def __getitem__(self, idx):
            return False

    if not hasattr(pg, "key"):
        pg.key = types.SimpleNamespace()
    pg.key.start_text_input = getattr(pg.key, "start_text_input", lambda: None)
    pg.key.stop_text_input = getattr(pg.key, "stop_text_input", lambda: None)
    pg.key.get_pressed = lambda: _KeyState()
    pg.key.name = lambda k: f"k_{k}"

    if not hasattr(pg, "mouse"):
        pg.mouse = types.SimpleNamespace()
    pg.mouse.get_pos = lambda: (0, 0)
    pg.mouse.get_pressed = lambda: (False, False, False)

    if not hasattr(pg, "event"):
        pg.event = types.SimpleNamespace()
    pg.event.get = lambda *a, **k: []
    pg.event.pump = lambda: None

    if not hasattr(pg, "scrap"):
        pg.scrap = types.SimpleNamespace()
    pg.scrap.get_init = getattr(pg.scrap, "get_init", lambda: False)
    pg.scrap.init = getattr(pg.scrap, "init", lambda: None)
    pg.scrap.get = getattr(pg.scrap, "get", lambda *a: None)
    pg.scrap.put = getattr(pg.scrap, "put", lambda *a: None)

    class _Clock:
        def tick(self, fps=60):
            return 16

        def get_fps(self):
            return 60.0

    if not hasattr(pg, "time"):
        pg.time = types.SimpleNamespace()
    pg.time.get_ticks = getattr(pg.time, "get_ticks", lambda: 1000)
    pg.time.Clock = _Clock

    if not hasattr(pg, "image"):
        pg.image = types.SimpleNamespace()
    pg.image.frombytes = getattr(pg.image, "frombytes", lambda buf, size, fmt: pg.Surface(size))
    pg.image.fromstring = getattr(pg.image, "fromstring", lambda buf, size, fmt: pg.Surface(size))
    pg.image.tobytes = getattr(pg.image, "tobytes", lambda surf, fmt: b"\x00" * (surf.get_width() * surf.get_height() * 4))
    pg.image.load = getattr(pg.image, "load", lambda path: pg.Surface((64, 64)))

    if not hasattr(pg, "transform"):
        pg.transform = types.SimpleNamespace()
    pg.transform.smoothscale = lambda surf, size, dest=None: dest if dest is not None else pg.Surface(size)
    pg.transform.scale = lambda surf, size, dest=None: dest if dest is not None else pg.Surface(size)
    pg.transform.rotate = getattr(pg.transform, "rotate", lambda surf, ang: surf)
    pg.transform.flip = getattr(pg.transform, "flip", lambda surf, xb, yb: surf)

    if not hasattr(pg, "draw"):
        pg.draw = types.SimpleNamespace()
    for dfn in ("rect", "line", "lines", "circle", "ellipse", "polygon", "arc"):
        if not hasattr(pg.draw, dfn):
            setattr(pg.draw, dfn, lambda *a, **k: None)

    return _disp_info


_DISP_INFO = _ensure_full_pygame_stub()

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME_DIR = os.path.join(ROOT_DIR, "GAME")
if GAME_DIR not in sys.path:
    sys.path.insert(0, GAME_DIR)

import pygame  # noqa: E402
import settings  # noqa: E402
import i18n  # noqa: E402
import accounts  # noqa: E402
import achievements  # noqa: E402
import heroes  # noqa: E402
import items  # noqa: E402
import dungeon  # noqa: E402
import player as player_mod  # noqa: E402
import room as room_mod  # noqa: E402
import touch_controls  # noqa: E402
import ui as ui_mod  # noqa: E402
import ai_mod_agent  # noqa: E402
import mods  # noqa: E402
import saves  # noqa: E402
import main as main_mod  # noqa: E402


class _IsolatedDataMixin:
    def _enter_temp_data(self):
        self._td = tempfile.TemporaryDirectory()
        self._old_data_dir = settings._CACHED_USER_DATA_DIR
        self._old_settings = dict(settings.GAME_SETTINGS)
        self._old_keybinds = dict(settings.GAME_SETTINGS.get("keybinds", {}))
        self._old_touch_offsets = dict(settings.GAME_SETTINGS.get("touch_offsets", {}))
        self._old_disp_w = _DISP_INFO.current_w
        self._old_disp_h = _DISP_INFO.current_h
        settings._CACHED_USER_DATA_DIR = self._td.name
        settings.set_view_width(settings.BASE_WIDTH)

    def _exit_temp_data(self):
        settings.GAME_SETTINGS.clear()
        settings.GAME_SETTINGS.update(self._old_settings)
        settings.GAME_SETTINGS["keybinds"] = dict(self._old_keybinds)
        settings.GAME_SETTINGS["touch_offsets"] = dict(self._old_touch_offsets)
        settings._CACHED_USER_DATA_DIR = self._old_data_dir
        settings.set_view_width(settings.BASE_WIDTH)
        _DISP_INFO.current_w = self._old_disp_w
        _DISP_INFO.current_h = self._old_disp_h
        self._td.cleanup()


class TestAndroidResolutionAndMobileUI(unittest.TestCase, _IsolatedDataMixin):
    def setUp(self):
        self._enter_temp_data()

    def tearDown(self):
        self._exit_temp_data()

    def test_android_hides_local_coop_and_keeps_native_resolution(self):
        ui = ui_mod.UI()
        ui.sync_font_scale(False)
        desktop_med = ui.font_med._size
        desktop_big = ui.font_big._size

        _DISP_INFO.current_w = 2400
        _DISP_INFO.current_h = 1080
        with patch.dict(os.environ, {"ANDROID_ARGUMENT": "/data/app"}, clear=False):
            self.assertTrue(settings.is_android())
            w, h = settings.get_native_display_size()
            self.assertEqual((w, h), (2400, 1080))
            self.assertGreaterEqual(settings.get_ui_scale(True), 1.25)

            game = main_mod.Game()
            self.assertFalse(game.coop_enabled)
            self.assertEqual(game._menu_coop_rects(), (None, None))
            game._toggle_coop_setting()
            self.assertFalse(game.coop_enabled)

            # Mobile UI font scale is ~25-28% larger than desktop
            ui.sync_font_scale(True)
            phone_med = ui.font_med._size
            phone_big = ui.font_big._size
            self.assertGreater(phone_med, desktop_med)
            self.assertGreater(phone_big, desktop_big)
            self.assertGreaterEqual(phone_med / desktop_med, 1.24)


class TestMenuPauseLanAndSeed(unittest.TestCase, _IsolatedDataMixin):
    def setUp(self):
        self._enter_temp_data()

    def tearDown(self):
        self._exit_temp_data()

    def test_main_menu_has_no_lan_and_pause_menu_has_lan(self):
        game = main_mod.Game()
        self.assertNotIn("lan", game._menu_button_rects())

        pause_rects = game.ui.get_pause_rects()
        self.assertEqual(len(pause_rects), 7)
        game.state = "PAUSED"
        game._activate_pause_item(4)
        self.assertEqual(game.state, "LAN_LOBBY")
        self.assertEqual(game.prev_state, "PAUSED")

    def test_preview_low_power_throttles_and_caps_particles(self):
        sim = main_mod.TitlePreviewSimulator()
        sim.particles = [types.SimpleNamespace(alive=True, update=lambda dt: None) for _ in range(40)]
        t_before = sim.demo_player.x
        sim.update(dt=1.0, low_power=True)
        # First tick skipped while accumulating dt
        self.assertEqual(sim.demo_player.x, t_before)
        self.assertEqual(len(sim.particles), 40)
        sim.update(dt=1.0, low_power=True)
        # Second tick advances and caps particles <= 18
        self.assertLessEqual(len(sim.particles), 18)

    def test_custom_seed_determinism_and_stat(self):
        g1 = dungeon.DungeonGenerator(floor_level=1, seed="DARK-999").generate_floor()
        g2 = dungeon.DungeonGenerator(floor_level=1, seed="DARK-999").generate_floor()
        self.assertEqual(sorted(g1.keys()), sorted(g2.keys()))
        for coord in g1:
            self.assertEqual(g1[coord].room_type, g2[coord].room_type)

        game = main_mod.Game()
        game.custom_seed = "SEED777"
        game.selected_hero_idx = 0  # starter Isaac
        game.start_new_run()
        self.assertEqual(game.state, "PLAYING")
        self.assertEqual(game.active_seed, "SEED777")
        acc = game.account_manager.get_active()
        self.assertGreaterEqual(acc["stats"].get("seeded_runs", 0), 1)


class TestProgressionHeroesAchievementsDaily(unittest.TestCase, _IsolatedDataMixin):
    def setUp(self):
        self._enter_temp_data()

    def tearDown(self):
        self._exit_temp_data()

    def test_only_three_starter_heroes_and_locked_run_blocked(self):
        mgr = accounts.AccountManager(data_dir=self._td.name)
        acc = mgr.get_active()
        unlocked_ids = [h["id"] for h in heroes.HERO_ROSTER if heroes.is_hero_unlocked(h["id"], acc)]
        self.assertEqual(set(unlocked_ids), {"isaac", "magdalene", "cain"})
        self.assertEqual(len(unlocked_ids), 3)

        game = main_mod.Game()
        locked_idx = next(i for i, h in enumerate(heroes.HERO_ROSTER) if not heroes.is_hero_unlocked(h["id"], game.account_manager.get_active()))
        game.selected_hero_idx = locked_idx
        game.start_new_run()
        self.assertEqual(game.state, "MENU")
        self.assertTrue(bool(game.menu_notice))

    def test_500_plus_achievements_and_realtime_unlock(self):
        self.assertGreaterEqual(len(achievements.ACHIEVEMENT_DEFS), 500)
        mgr = accounts.AccountManager(data_dir=self._td.name)
        am = achievements.AchievementManager(mgr)
        mgr.record_stat("kills", 15, mode="max")
        newly = am.evaluate()
        self.assertTrue(any(a["id"] == "first_blood" for a in newly))
        self.assertTrue(am.is_unlocked("first_blood"))

    def test_daily_rewards_and_profile_roster_crud(self):
        mgr = accounts.AccountManager(data_dir=self._td.name)
        res1 = mgr.claim_daily_reward(today_str="2026-03-01")
        self.assertTrue(res1["ok"])
        self.assertEqual(res1["streak"], 1)
        res_dup = mgr.claim_daily_reward(today_str="2026-03-01")
        self.assertFalse(res_dup["ok"])

        res2 = mgr.claim_daily_reward(today_str="2026-03-02")
        self.assertTrue(res2["ok"])
        self.assertEqual(res2["streak"], 2)

        bonus = mgr.consume_daily_bonus()
        self.assertIsNotNone(bonus)
        self.assertGreater(bonus.get("coins", 0), 0)
        self.assertIsNone(mgr.consume_daily_bonus())

        # Profile CRUD
        p2 = mgr.create_account("ShadowTest", "DV-99", emblem=3)
        self.assertEqual(len(mgr.accounts), 2)
        self.assertTrue(mgr.rename_account(p2["id"], "BladeRunner", "BL-02", emblem=5))
        self.assertEqual(mgr.get_active()["emblem"], 5)
        self.assertGreaterEqual(len(mgr.get_roster()), 2)
        self.assertTrue(mgr.delete_account(p2["id"]))
        self.assertEqual(len(mgr.accounts), 1)


class TestMeleeCooldownsAndArtifactCap(unittest.TestCase, _IsolatedDataMixin):
    def setUp(self):
        self._enter_temp_data()

    def tearDown(self):
        self._exit_temp_data()

    def test_rebalanced_cooldowns_and_bomb_cd(self):
        p = player_mod.Player(400.0, 360.0, "isaac")
        self.assertEqual(p.dash_max_cd, 95.0)
        self.assertEqual(p.jump_max_cd, 120.0)
        self.assertEqual(p.invis_max_cd, 360.0)
        self.assertEqual(p.bomb_max_cd, 75.0)
        self.assertTrue(p.can_place_bomb())
        p.trigger_bomb_cd()
        self.assertFalse(p.can_place_bomb())

    def test_melee_damages_enemies_deflects_shots_and_breaks_turrets(self):
        p = player_mod.Player(400.0, 360.0, "isaac")
        p.invis_timer = 40.0  # ambush multiplier test
        rm = room_mod.Room((0, 0), room_type="normal", floor_level=1, layout_key="empty")
        turret = room_mod.Obstacle(445, 360, kind="turret")
        turret.hp = 2
        rm.obstacles.append(turret)

        class _DummyEnemy:
            def __init__(self, x, y):
                self.x = x
                self.y = y
                self.radius = 16.0
                self.hp = 5.0
                self.alive = True
                self.knockback_x = 0.0
                self.knockback_y = 0.0

            def take_damage(self, dmg):
                self.hp -= dmg
                if self.hp <= 0:
                    self.alive = False

        foe = _DummyEnemy(435.0, 360.0)
        shot = types.SimpleNamespace(x=430.0, y=360.0, alive=True)
        particles = []
        res = p.try_melee(1.0, 0.0, rm, [foe], [shot], particles)
        self.assertTrue(res["hit"])
        self.assertEqual(res["enemies_hit"], 1)
        self.assertEqual(res["deflected"], 1)
        self.assertEqual(res["turrets_broken"], 1)
        self.assertFalse(shot.alive)
        self.assertFalse(turret.alive)
        self.assertGreater(foe.knockback_x, 0.0)

    def test_max_3_artifacts_per_floor(self):
        for seed in range(1, 15):
            for fl in (1, 3, 5):
                rooms = dungeon.DungeonGenerator(floor_level=fl, seed=seed).generate_floor()
                ped_count = sum(
                    1
                    for rm in rooms.values()
                    for ped in getattr(rm, "pedestals", [])
                    if getattr(ped, "alive", True)
                )
                self.assertLessEqual(ped_count, dungeon.MAX_ARTIFACTS_PER_FLOOR)


class TestItemsObstaclesTurretsAndShadows(unittest.TestCase):
    def test_all_124_items_render_icons_and_cache_capped(self):
        items.ICON_CACHE.clear()
        self.assertGreaterEqual(len(items.ITEM_POOL_65), 120)
        surf = pygame.Surface((64, 64), pygame.SRCALPHA)
        for item in items.ITEM_POOL_65:
            items.draw_item_icon(surf, item, 32, 32, size=24)
        self.assertGreater(len(items.ICON_CACHE), 0)
        self.assertLessEqual(len(items.ICON_CACHE), 512)

    def test_turret_fires_and_dynamic_lights(self):
        rm = room_mod.Room((0, 0), room_type="normal", floor_level=2, layout_key="empty")
        rm.cleared = False
        turret = room_mod.Obstacle(400, 360, kind="turret")
        turret.fire_cd = 0.0
        rm.obstacles.append(turret)
        p = player_mod.Player(520.0, 360.0, "isaac")
        shots = []
        rm.update_turrets(dt=1.0, players=[p], enemy_projectiles=shots)
        self.assertEqual(len(shots), 1)
        lights = rm.get_dynamic_light_sources([p])
        self.assertGreaterEqual(len(lights), 2)
        surf = pygame.Surface((640, 480), pygame.SRCALPHA)
        settings.draw_dynamic_shadow(surf, p.x, p.y, 28, 12, light_sources=lights, air_z=8.0)


class TestTouchControlsKeybindsAndAIAgent(unittest.TestCase, _IsolatedDataMixin):
    def setUp(self):
        self._enter_temp_data()

    def tearDown(self):
        self._exit_temp_data()

    def test_touch_controls_no_overlap_and_customizer(self):
        tc = touch_controls.TouchControls()
        tc.touch_seen = True
        tc._sync_layout()
        btns = ["melee", "stealth", "dash", "jump", "bomb", "relic", "pause"]
        for i in range(len(btns)):
            for j in range(i + 1, len(btns)):
                c1 = getattr(tc, f"{btns[i]}_center")
                r1 = getattr(tc, f"{btns[i]}_radius")
                c2 = getattr(tc, f"{btns[j]}_center")
                r2 = getattr(tc, f"{btns[j]}_radius")
                dist = ((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2) ** 0.5
                self.assertGreaterEqual(dist, r1 + r2 - 1.0, f"Overlap between {btns[i]} and {btns[j]}")

        self.assertEqual(tc.cycle_preset(), "raised")
        node = tc.get_customizer_nodes()[0]  # (id, label, center, radius)
        cx, cy = node[2]
        tc.handle_customizer_pointer("down", (cx, cy))
        tc.handle_customizer_pointer("move", (cx + 24, cy - 18))
        tc.handle_customizer_pointer("up", (cx + 24, cy - 18))
        self.assertEqual(settings.GAME_SETTINGS.get("touch_layout_preset"), "custom")
        tc.reset_custom_offsets()
        self.assertEqual(settings.GAME_SETTINGS.get("touch_layout_preset"), "wide")

    def test_keybind_conflict_swap_and_reset(self):
        old_melee = settings.get_keybind("melee")
        old_jump = settings.get_keybind("jump")
        settings.set_keybind("melee", old_jump)
        self.assertEqual(settings.get_keybind("melee"), old_jump)
        self.assertEqual(settings.get_keybind("jump"), old_melee)
        settings.reset_keybinds()
        self.assertEqual(settings.get_keybind("melee"), settings.DEFAULT_KEYBINDS["melee"])

    def test_ai_agent_watchdog_and_mod_editor_key_bar(self):
        agent = ai_mod_agent.AIModAgentClient()
        self.assertEqual(agent.REQUEST_TIMEOUT, 25)
        agent.busy = True
        agent._request_started_at = time.monotonic() - 35.0
        triggered = agent.check_watchdog(32.0, lang="en")
        self.assertTrue(triggered)
        self.assertFalse(agent.busy)
        self.assertIn("timed out", agent.error_text.lower())

        mb = mods.ModBrowserScreen()
        mb.ai_open = True
        rc = mb._rects()
        self.assertIn("ai_key_bar", rc)
        self.assertIn("ai_key_save", rc)
        self.assertFalse(rc["ai_key_bar"].colliderect(rc["ai_key_save"]))

    def test_ai_watchdog_none_sentinel_and_low_monotonic(self):
        agent = ai_mod_agent.AIModAgentClient()
        agent.busy = True
        agent._request_started_at = None
        self.assertFalse(agent.check_watchdog(10.0, lang="en"))
        agent._request_started_at = -30.0
        self.assertTrue(agent.check_watchdog(6.0, lang="en"))
        self.assertIsNone(agent._request_started_at)
        self.assertFalse(agent.busy)

    def test_mods_source_list_privacy_and_info_modal_safety(self):
        self.assertIn("i18n.py", mods.SOURCE_FILE_LIST)
        self.assertIn("lan_coop.py", mods.SOURCE_FILE_LIST)
        for lang in ("ru", "en"):
            for k, v in i18n.TEXTS[lang].items():
                low = str(v).lower()
                self.assertNotIn("gmail.com", low, f"Email leaked in i18n[{lang}][{k}]")
                self.assertNotIn("maksim", low, f"Personal name leaked in i18n[{lang}][{k}]")
                self.assertNotIn("polienko", low, f"Personal surname leaked in i18n[{lang}][{k}]")

        mods_src_path = os.path.join(GAME_DIR, "mods.py")
        with open(mods_src_path, "r", encoding="utf-8") as fh:
            mods_src = fh.read().lower()
        self.assertNotIn("gmail.com", mods_src)
        self.assertNotIn("polienko", mods_src)

        mb = mods.ModBrowserScreen()
        ui = ui_mod.UI()
        surf = pygame.Surface((1280, 720))
        mb._trigger_button("btn_contacts")
        self.assertTrue(mb.contacts_modal_open)
        mb.draw(surf, ui)
        rc = mb._rects()
        self.assertIn("close_contacts", rc)
        mb.handle_event(types.SimpleNamespace(type=pygame.MOUSEMOTION, pos=rc["close_contacts"].center))
        mb.handle_event(types.SimpleNamespace(type=pygame.MOUSEBUTTONDOWN, button=1, pos=rc["close_contacts"].center))
        self.assertFalse(mb.contacts_modal_open)


class TestHeadlessGameSmoke(unittest.TestCase, _IsolatedDataMixin):
    def setUp(self):
        self._enter_temp_data()

    def tearDown(self):
        self._exit_temp_data()

    def test_headless_game_step_frames_all_screens(self):
        game = main_mod.Game()
        for state in ("MENU", "SETTINGS", "TUTORIAL", "TOUCH_EDIT", "ACCOUNTS"):
            game.state = state
            game.step_frame(1.0)
        game.selected_hero_idx = 0
        game.start_new_run()
        self.assertEqual(game.state, "PLAYING")
        for _ in range(3):
            game.step_frame(1.0)
        game._trigger_melee(game.player, 1.0, 0.0)
        game.state = "PAUSED"
        game.step_frame(1.0)

    def test_active_bomb_owner_and_save_load_state_reset(self):
        game = main_mod.Game()
        game.selected_hero_idx = 0
        game.start_new_run()
        p2 = player_mod.Player(game.player.x + 20, game.player.y, "cain")
        bomb = main_mod.ActiveBomb(game.player.x, game.player.y, owner=p2)
        self.assertIs(bomb.owner, p2)

        game.floor_took_damage = True
        game.room_took_damage = True
        saved_ok, saved_msg = saves.save_run_to_slot(1, game)
        self.assertTrue(saved_ok, saved_msg)
        game.run_recorded = True
        game.cutscene = object()
        game.floor_took_damage = False
        game.room_took_damage = False

        ok, err = saves.load_run_from_slot(1, game)
        self.assertTrue(ok, err)
        self.assertFalse(game.run_recorded)
        self.assertIsNone(game.cutscene)
        self.assertTrue(game.floor_took_damage)
        self.assertTrue(game.room_took_damage)

    def test_fit_text_surf_and_blit_text_fitted_bounds(self):
        ui = ui_mod.UI()
        surf = pygame.Surface((400, 120))
        long_ru = "ОЧЕНЬ ДЛИННОЕ НАЗВАНИЕ КНОПКИ ПРОФИЛИ И ДОСТИЖЕНИЯ ПРОВЕРКА ПЕРЕНОСА"
        ts = settings.fit_text_surf(ui.font_med, long_ru, (240, 240, 240), max_w=160, min_scale=0.50)
        self.assertLessEqual(ts.get_width(), 160)
        rect = pygame.Rect(20, 20, 140, 34)
        res = settings.blit_text_fitted(surf, rect, ui.font_med, long_ru, (240, 240, 240), pad_x=8)
        self.assertLessEqual(res.get_width(), 124)

    def test_grounded_dynamic_shadow_and_touch_customizer_wide_offsets(self):
        surf = pygame.Surface((320, 240), pygame.SRCALPHA)
        settings.draw_dynamic_shadow(surf, 160, 120, 38, 13, light_sources=[(130, 120, 220, 1.0)], air_z=0.0, alpha=120)
        self.assertGreater(surf._draws, 0)

        tc = touch_controls.TouchControls()
        tc.touch_seen = True
        tc._sync_layout()
        node = tc.get_customizer_nodes()[0]
        cx, cy = node[2]
        tc.handle_customizer_pointer("down", (cx, cy))
        tc.handle_customizer_pointer("motion", (cx + 420, cy - 260))
        tc.handle_customizer_pointer("up", (cx + 420, cy - 260))
        self.assertEqual(settings.GAME_SETTINGS.get("touch_layout_preset"), "custom")
        settings.save_user_settings()
        settings.load_user_settings()
        off = settings.GAME_SETTINGS.get("touch_custom_offsets", {}).get(node[0], [0.0, 0.0])
        self.assertGreater(abs(off[0]), 300.0)
        self.assertGreater(abs(off[1]), 200.0)

    def test_settings_keybinds_row_and_achievements_touch_scrolling(self):
        game = main_mod.Game()
        self.assertEqual(game._settings_row_count(), 16)
        self.assertEqual(len(game._settings_rects()), 16)

        game.prev_state = "PAUSED"
        game.state = "SETTINGS"
        prev_music = settings.GAME_SETTINGS.get("music_enabled", True)
        game._activate_settings_row(2)
        self.assertEqual(settings.GAME_SETTINGS.get("music_enabled"), not prev_music)
        game._activate_settings_row(2)
        self.assertEqual(settings.GAME_SETTINGS.get("music_enabled"), prev_music)

        game._activate_settings_row(14)
        self.assertEqual(game.state, "TUTORIAL")
        self.assertEqual(game.ctrl_tab, 1)
        self.assertEqual(game.tutorial_return_state, "SETTINGS")

        # Return to SETTINGS via Escape
        with patch.object(pygame.event, "get", return_value=[types.SimpleNamespace(type=pygame.KEYDOWN, key=pygame.K_ESCAPE)]):
            game.handle_events()
        self.assertEqual(game.state, "SETTINGS")

        # Opening Tutorial from Main Menu returns to MENU
        game._activate_menu_item(4)
        self.assertEqual(game.state, "TUTORIAL")
        self.assertEqual(game.tutorial_return_state, "MENU")

        # Achievements touch swipe + scroll buttons
        game.state = "ACCOUNTS"
        game.acc_tab = 0
        game.acc_scroll = 0
        vw = settings.get_view_width()
        list_rect, sb_up_rc, sb_dn_rc, _, _ = game._accounts_scroll_rects()
        # Tap ▼ button via synthetic FINGERDOWN
        dn_ev = types.SimpleNamespace(
            type=pygame.FINGERDOWN,
            x=sb_dn_rc.centerx / float(vw),
            y=sb_dn_rc.centery / float(settings.SCREEN_HEIGHT),
            finger_id=1,
        )
        with patch.object(pygame.event, "get", return_value=[dn_ev]):
            game.handle_events()
        self.assertGreaterEqual(game.acc_scroll, 5)
        scrolled_after_btn = game.acc_scroll

        # Swipe finger UP inside achievement list to scroll further down
        sw_events = [
            types.SimpleNamespace(type=pygame.FINGERDOWN, x=list_rect.centerx / float(vw), y=(list_rect.centery + 90) / float(settings.SCREEN_HEIGHT), finger_id=2),
            types.SimpleNamespace(type=pygame.FINGERMOTION, x=list_rect.centerx / float(vw), y=(list_rect.centery - 90) / float(settings.SCREEN_HEIGHT), finger_id=2),
            types.SimpleNamespace(type=pygame.FINGERUP, x=list_rect.centerx / float(vw), y=(list_rect.centery - 90) / float(settings.SCREEN_HEIGHT), finger_id=2),
        ]
        with patch.object(pygame.event, "get", return_value=sw_events):
            game.handle_events()
        self.assertGreater(game.acc_scroll, scrolled_after_btn)

        # Tap ▲ button to scroll back up
        up_ev = types.SimpleNamespace(
            type=pygame.FINGERDOWN,
            x=sb_up_rc.centerx / float(vw),
            y=sb_up_rc.centery / float(settings.SCREEN_HEIGHT),
            finger_id=3,
        )
        with patch.object(pygame.event, "get", return_value=[up_ev]):
            game.handle_events()
        self.assertLess(game.acc_scroll, scrolled_after_btn + 6)

    def test_mobile_terminal_interact_button_and_hint_tap(self):
        tc = touch_controls.TouchControls()
        tc.touch_seen = True
        tc._sync_layout()
        btns = ["melee", "stealth", "dash", "jump", "bomb", "relic", "interact", "pause"]
        for i in range(len(btns)):
            for j in range(i + 1, len(btns)):
                c1 = getattr(tc, f"{btns[i]}_center")
                r1 = getattr(tc, f"{btns[i]}_radius")
                c2 = getattr(tc, f"{btns[j]}_center")
                r2 = getattr(tc, f"{btns[j]}_radius")
                dist = ((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2) ** 0.5
                self.assertGreaterEqual(dist, r1 + r2 - 1.0, f"Overlap between {btns[i]} and {btns[j]}")

        self.assertEqual(tc.cycle_preset(), "raised")
        for i in range(len(btns)):
            for j in range(i + 1, len(btns)):
                c1 = getattr(tc, f"{btns[i]}_center")
                r1 = getattr(tc, f"{btns[i]}_radius")
                c2 = getattr(tc, f"{btns[j]}_center")
                r2 = getattr(tc, f"{btns[j]}_radius")
                dist = ((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2) ** 0.5
                self.assertGreaterEqual(dist, r1 + r2 - 1.0, f"Raised preset overlap between {btns[i]} and {btns[j]}")

        nodes = tc.get_customizer_nodes()
        term_nodes = [n for n in nodes if n[0] == "interact" and n[1] == "TERM"]
        self.assertEqual(len(term_nodes), 1)

        tc.reset()
        tc.handle_finger_down(77, tc.interact_center)
        acts = tc.consume_actions()
        self.assertTrue(acts.get("interact"))

        game = main_mod.Game()
        game.selected_hero_idx = 0
        game.start_new_run()
        game.touch.touch_seen = True
        game.touch._sync_layout()
        mac = room_mod.Machine(game.player.x + 24.0, game.player.y, kind="computer_terminal", track_idx=0, playing=False)
        game.current_room.machines.append(mac)
        hint = game._get_nearby_computer_hint(game.current_room, game.player)
        self.assertTrue(bool(hint))
        game.step_frame(1.0)
        comp_rc = game.ui.get_computer_hint_rect()
        self.assertIsNotNone(comp_rc)

        # Tapping the computer hint banner toggles the terminal track
        vw = settings.get_view_width()
        tap_hint = types.SimpleNamespace(
            type=pygame.FINGERDOWN,
            x=comp_rc.centerx / float(vw),
            y=comp_rc.centery / float(settings.SCREEN_HEIGHT),
            finger_id=12,
        )
        with patch.object(pygame.event, "get", return_value=[tap_hint]):
            game.handle_events()
        self.assertTrue(mac.playing)

        # Tapping the circular interact button also cycles the terminal track
        prev_idx = mac.track_idx
        game.touch.handle_finger_down(13, game.touch.interact_center)
        game._update_playing(1.0)
        self.assertNotEqual(mac.track_idx, prev_idx)

        # LAN Client touch interact propagates into _lan_client_actions / send_input
        game.state = "LAN_CLIENT"
        with patch.object(pygame.event, "get", return_value=[tap_hint]):
            game.handle_events()
        self.assertTrue(game._lan_client_actions.get("interact"))

    def test_phone_scale_layout_no_overlap(self):
        game = main_mod.Game()
        game.touch.touch_seen = True
        game.ui.sync_font_scale(True)

        # Main Menu title / alpha badge & mode panel spacing
        game.state = "MENU"
        game.step_frame(1.0)
        m_rects = game._menu_mode_rects()
        seed_rc = game._menu_seed_rect()
        roll_rc = game._menu_seed_roll_rect()
        self.assertFalse(seed_rc.colliderect(roll_rc))
        for mrc in m_rects:
            self.assertGreaterEqual(mrc.top, 474)
            self.assertLessEqual(mrc.bottom, 600)

        # HUD + Quests + computer hint + coop under phone font scaling
        game.coop_enabled = True
        game.start_new_run()
        game.game_mode = "fading_light"
        game.current_room.machines.append(room_mod.Machine(game.player.x + 20.0, game.player.y, kind="computer_terminal"))
        game.step_frame(1.0)
        q_hud = game.quest_manager.get_hud_rect(True)
        coop_lay = game.ui.get_coop_hud_layout(touch_active=True, game_mode="fading_light")
        minimap_r = coop_lay["minimap"]
        self.assertLessEqual(minimap_r.bottom, q_hud.top)
        self.assertFalse(coop_lay["p1"].colliderect(coop_lay["p2"]))
        self.assertFalse(coop_lay["p2"].colliderect(minimap_r))

        comp_rc = game.ui.get_computer_hint_rect()
        self.assertIsNotNone(comp_rc)
        slots, _ = game.ui.get_inventory_slot_rects(True)
        for s_rc in slots:
            self.assertFalse(comp_rc.colliderect(s_rc), "Computer hint overlaps inventory slot")

        # Accounts filter bar & scroll list non-overlap
        game.state = "ACCOUNTS"
        game.acc_tab = 0
        game.step_frame(1.0)
        cat_prev, cat_box, cat_next, unl_rc = game._accounts_filter_rects()
        list_rect, _, _, _, _ = game._accounts_scroll_rects()
        for f_rc in (cat_prev, cat_box, cat_next, unl_rc):
            self.assertLessEqual(f_rc.bottom, list_rect.top)
        self.assertFalse(cat_next.colliderect(unl_rc))

    def test_menu_preview_cache_and_dimmed_optimization(self):
        sim = main_mod.TitlePreviewSimulator()
        light_sys = main_mod.LightingSystem(settings.BASE_WIDTH, settings.SCREEN_HEIGHT)
        screen = pygame.Surface((settings.get_view_width(), settings.SCREEN_HEIGHT))
        render_calls = []
        orig_render = light_sys.render

        def _spy_render(*args, **kwargs):
            render_calls.append(kwargs.get("preview_mode", False))
            return orig_render(*args, **kwargs)

        with patch.object(light_sys, "render", side_effect=_spy_render):
            sim.fade_alpha = 0.0
            sim._dirty = True
            sim._render_tick = 0
            sim.draw(screen, lighting=light_sys, low_power=False, menu_dimmed=True)
            # Second frame immediately with _dirty=False and even tick reuses _cached_surf
            sim._dirty = False
            sim.draw(screen, lighting=light_sys, low_power=False, menu_dimmed=True)
            self.assertEqual(len(render_calls), 1)
            self.assertTrue(render_calls[0])

            # Fade surface is cached across ticks when fade_alpha > 1.0
            sim.fade_alpha = 120.0
            sim.draw(screen, lighting=light_sys, low_power=False, menu_dimmed=True)
            fade_obj = sim._fade_surf
            self.assertIsNotNone(fade_obj)
            sim.fade_alpha = 90.0
            sim.draw(screen, lighting=light_sys, low_power=False, menu_dimmed=True)
            self.assertIs(sim._fade_surf, fade_obj)

    def test_diverse_achievements_and_accounts_filters(self):
        mgr = accounts.AccountManager(data_dir=self._td.name)
        am = achievements.AchievementManager(mgr)

        # Verify diverse stats unlock the new achievements
        mgr.record_stat("computer_uses", 1)
        mgr.record_stat("computer_tracks_heard", "0", mode="append_unique")
        mgr.record_stat("computer_tracks_heard", "1", mode="append_unique")
        mgr.record_stat("computer_tracks_heard", "2", mode="append_unique")
        mgr.record_stat("computer_tracks_heard", "3", mode="append_unique")
        mgr.record_stat("projectiles_deflected", 1)
        mgr.record_stat("boss_flawless", 1)
        mgr.record_stat("monoliths_activated", 5)
        mgr.record_stat("devil_deals", 1)
        mgr.record_stat("tinted_rocks_bombed", 5)
        mgr.record_stat("peak_dmg_x10", 200, mode="max")
        mgr.record_stat("peak_speed_x10", 75, mode="max")
        mgr.record_stat("heroes_won", "lost", mode="append_unique")
        newly = am.evaluate()
        unlocked_ids = {a["id"] for a in newly}
        for expected in (
            "terminal_dj",
            "vault_melomaniac",
            "bullet_parry_1",
            "flawless_boss_win",
            "monolith_awakener",
            "devil_pact_1",
            "tinted_hunter",
            "overkill_build",
            "hypersonic",
            "ethereal_triumph",
        ):
            self.assertIn(expected, unlocked_ids)

        # Category and unlocked-only filters in AchievementManager & Game
        game = main_mod.Game()
        game.account_manager = mgr
        game.achievement_manager = am
        game.acc_cat_filter = "explore"
        game.acc_only_unlocked = False
        explore_items = game._filtered_achievements()
        self.assertTrue(any(a["id"] == "terminal_dj" for a in explore_items))
        self.assertTrue(all(a["cat"] == "explore" for a in explore_items))

        game.acc_only_unlocked = True
        explore_unlocked = game._filtered_achievements()
        self.assertTrue({"terminal_dj", "vault_melomaniac"}.issubset({a["id"] for a in explore_unlocked}))

        # Clicking category next cycles categories and clicking unlocked toggle flips flag
        cat_prev, _, cat_next, unl_rc = game._accounts_filter_rects()
        game.state = "ACCOUNTS"
        game.acc_tab = 0
        game._handle_accounts_click(cat_next.centerx, cat_next.centery)
        self.assertNotEqual(game.acc_cat_filter, "explore")
        game._handle_accounts_click(cat_prev.centerx, cat_prev.centery)
        self.assertEqual(game.acc_cat_filter, "explore")
        game._handle_accounts_click(unl_rc.centerx, unl_rc.centery)
        self.assertFalse(game.acc_only_unlocked)


if __name__ == "__main__":
    unittest.main()
