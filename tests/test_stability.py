import ast
import json
import os
import sys
import tempfile
import types
import unittest


def _install_pygame_stub():
    if "pygame" in sys.modules:
        return
    pg = types.ModuleType("pygame")

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
        def topleft(self):
            return (self.x, self.y)

        def colliderect(self, other):
            return not (
                self.right <= other.left
                or self.left >= other.right
                or self.bottom <= other.top
                or self.top >= other.bottom
            )

        def inflate(self, dx, dy):
            return Rect(self.x - dx // 2, self.y - dy // 2, self.w + dx, self.h + dy)

        def collidepoint(self, mx, my):
            return self.x <= mx < self.right and self.y <= my < self.bottom

    class Surface:
        def __init__(self, size, *args, **kwargs):
            self._size = (max(1, int(size[0])), max(1, int(size[1])))
            self._clip = None
            self._alpha = 255

        def fill(self, *args, **kwargs):
            pass

        def blit(self, *args, **kwargs):
            pass

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

    class FakeFont:
        def __init__(self, size=14):
            self._size = max(8, int(size or 14))

        def render(self, text, antialias, color):
            s = str(text)
            return Surface((max(8, len(s) * max(5, self._size // 2)), max(10, self._size)))

        def size(self, text):
            s = str(text)
            return (max(8, len(s) * max(5, self._size // 2)), max(10, self._size))

        def get_height(self):
            return max(10, self._size)

    pg.Rect = Rect
    pg.Surface = Surface
    pg.SRCALPHA = 65536
    pg.FULLSCREEN = 1
    pg.RESIZABLE = 16
    pg.DOUBLEBUF = 1073741824
    pg.SCALED = 512
    pg.BLEND_MULT = 3
    pg.BLEND_ADD = 1
    pg.BLEND_RGBA_ADD = 6
    pg.BLEND_RGBA_MIN = 8
    for k_name in (
        "K_c", "K_RETURN", "K_ESCAPE", "K_SPACE", "K_UP", "K_DOWN",
        "K_LEFT", "K_RIGHT", "K_w", "K_a", "K_s", "K_d", "K_r", "K_e",
        "K_LSHIFT", "K_RSHIFT", "K_LCTRL", "K_RCTRL", "K_TAB", "K_q", "K_x"
    ):
        if not hasattr(pg, k_name):
            setattr(pg, k_name, ord(k_name[-1].lower()) if len(k_name) == 3 else 1000)
    pg.gfxdraw = types.ModuleType("pygame.gfxdraw")
    pg.gfxdraw.filled_circle = lambda *a, **k: None
    pg.gfxdraw.aacircle = lambda *a, **k: None
    pg.gfxdraw.filled_polygon = lambda *a, **k: None
    pg.gfxdraw.aapolygon = lambda *a, **k: None
    pg.font = types.SimpleNamespace(
        get_init=lambda: True,
        init=lambda: None,
        quit=lambda: None,
        SysFont=lambda name, size, bold=False, **k: FakeFont(size),
        Font=lambda path, size=14, **k: FakeFont(size),
    )
    pg.error = Exception
    pg.display = types.SimpleNamespace(
        get_init=lambda: False,
        init=lambda: None,
        quit=lambda: None,
        get_surface=lambda: None,
        set_caption=lambda title: None,
        set_mode=lambda size, *a, **k: Surface(size),
        flip=lambda: None,
        update=lambda *a, **k: None,
    )
    pg.mixer = types.SimpleNamespace(get_init=lambda: False, stop=lambda: None, quit=lambda: None)
    class KeyPressedDict(dict):
        def __missing__(self, key):
            return 0
    pg.key = types.SimpleNamespace(
        start_text_input=lambda: None,
        stop_text_input=lambda: None,
        get_pressed=lambda: KeyPressedDict(),
    )
    pg.scrap = types.SimpleNamespace(get_init=lambda: False, init=lambda: None)
    pg.time = types.SimpleNamespace(
        get_ticks=lambda: 1000,
        Clock=lambda: types.SimpleNamespace(tick=lambda fps=60: 16, get_fps=lambda: 60.0),
    )
    pg.image = types.SimpleNamespace(
        frombytes=lambda buf, size, fmt: Surface(size),
        fromstring=lambda buf, size, fmt: Surface(size),
        tobytes=lambda surf, fmt: b"\x00" * (surf.get_width() * surf.get_height() * 4),
    )
    pg.transform = types.SimpleNamespace(
        smoothscale=lambda surf, size: Surface(size),
        scale=lambda surf, size: Surface(size),
        rotate=lambda surf, ang: surf,
        flip=lambda surf, xbool, ybool: surf,
    )
    pg.draw = types.SimpleNamespace(
        rect=lambda *a, **k: None,
        line=lambda *a, **k: None,
        lines=lambda *a, **k: None,
        circle=lambda *a, **k: None,
        ellipse=lambda *a, **k: None,
        polygon=lambda *a, **k: None,
        arc=lambda *a, **k: None,
    )
    sys.modules["pygame"] = pg
    sys.modules["pygame.gfxdraw"] = pg.gfxdraw


_install_pygame_stub()

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME_DIR = os.path.join(ROOT_DIR, "GAME")
if GAME_DIR not in sys.path:
    sys.path.insert(0, GAME_DIR)

import settings  # noqa: E402
import i18n  # noqa: E402
import accounts  # noqa: E402
import ai_mod_agent  # noqa: E402
import mods  # noqa: E402
import saves  # noqa: E402
import ui as ui_mod  # noqa: E402
import player as player_mod  # noqa: E402


class TestAtomicJsonAndRecovery(unittest.TestCase):
    def test_atomic_write_and_corrupt_recovery(self):
        with tempfile.TemporaryDirectory() as td:
            target = os.path.join(td, "state.json")
            ok1, err1 = settings.atomic_write_json(target, {"step": 1, "name": "Тест"})
            self.assertTrue(ok1, err1)
            self.assertFalse(os.path.exists(target + ".tmp"))

            ok2, err2 = settings.atomic_write_json(target, {"step": 2, "name": "Второй"})
            self.assertTrue(ok2, err2)
            self.assertTrue(os.path.exists(target + ".bak"))

            # Corrupt primary file cleanly
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("{corrupt json")

            recovered = settings.safe_read_json(target, expected_type=dict, try_backups=True, self_heal=True)
            self.assertEqual(recovered, {"step": 1, "name": "Тест"})

            # Primary should now be self-healed
            with open(target, "r", encoding="utf-8") as fh:
                healed = json.load(fh)
            self.assertEqual(healed, {"step": 1, "name": "Тест"})

    def test_safe_read_handles_missing_and_wrong_type(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "list.json")
            settings.atomic_write_json(p, {"not": "a list"})
            res = settings.safe_read_json(p, default=["fallback"], expected_type=list)
            self.assertEqual(res, ["fallback"])
            self.assertIsNone(settings.safe_read_json(os.path.join(td, "absent.json"), default=None))

    def test_accounts_and_ai_agent_atomic_json(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = accounts.AccountManager(data_dir=td)
            self.assertGreaterEqual(len(mgr.accounts), 1)
            self.assertTrue(os.path.isfile(mgr.path))
            self.assertFalse(os.path.exists(mgr.path + ".tmp"))

            # Corrupt accounts.json and reload -> should recover without crashing
            with open(mgr.path, "w", encoding="utf-8") as fh:
                fh.write("<<<invalid>>>")
            mgr2 = accounts.AccountManager(data_dir=td)
            self.assertGreaterEqual(len(mgr2.accounts), 1)

            agent = ai_mod_agent.AIModAgentClient()
            agent.config_path = os.path.join(td, "ai_cfg.json")
            agent.save("gemini", "gemini-2.5-flash", "secret-test", "")
            self.assertTrue(os.path.isfile(agent.config_path))
            self.assertFalse(os.path.exists(agent.config_path + ".tmp"))


class TestSaveCrashProtection(unittest.TestCase):
    def test_serialize_and_atomic_save_slot_handles_edge_cases(self):
        with tempfile.TemporaryDirectory() as td:
            old_dir = settings._CACHED_USER_DATA_DIR
            settings._CACHED_USER_DATA_DIR = td
            try:
                fake_player = types.SimpleNamespace(
                    hero_id="isaac",
                    x=640.0,
                    y=360.0,
                    hp=6,
                    max_hp=6,
                    soul_hp=2,
                    black_hp=0,
                    speed=4.0,
                    damage=3.5,
                    fire_delay=12.0,
                    tear_speed=8.0,
                    tear_range=400.0,
                    luck=1,
                    coins=10,
                    bombs=2,
                    keys=1,
                    kills=5,
                    active_items=[{"item": "not_a_dict", "charge": 2, "max_charge": 4}, {"item": {"id": "wooden_nickel"}, "charge": 1, "max_charge": 2}],
                    active_slot=0,
                    collected_items=["string_item", {"id": "prism_core"}],
                    collected_ids={1, "a", None},
                    active_effects={"bad": "not_a_float", "rage": 12.5},
                    allies=[types.SimpleNamespace(kind="familiar", x=100, y=100, hp=3, angle=0.5)],
                    is_dead=lambda: False,
                )
                fake_obstacle = types.SimpleNamespace(kind="rock", rect=None, destructible=True, hp=2)
                fake_room = types.SimpleNamespace(
                    coord=(0, 0),
                    room_type="combat",
                    cleared=False,
                    visited=True,
                    wave_spawns_left=0,
                    ambush_triggered=False,
                    theme={"ambient": 0.35},
                    doors={},
                    obstacles=[fake_obstacle],
                    pickups=[],
                    pedestals=[],
                    enemies=[],
                    bosses=[],
                    beggars=[],
                    shopkeepers=[],
                    machines=[],
                    monoliths=[],
                    mystical_npcs=[],
                    sacrifice_spikes=None,
                    dice_floor=None,
                    trapdoor=None,
                    devil_portal=None,
                )
                fake_game = types.SimpleNamespace(
                    player=fake_player,
                    player2=None,
                    coop_enabled=False,
                    game_mode="classic",
                    floor_level=1,
                    floor_modifier=None,
                    wave_num=1,
                    wave_break_timer=0.0,
                    darkness_tick=0.0,
                    placenta_tick=0.0,
                    active_seed=None,
                    boss_rush_wave=1,
                    current_coord=(0, 0),
                    devil_return_coord=(0, 0),
                    current_room=fake_room,
                    rooms={(0, 0): fake_room},
                    devil_room=None,
                    quest_manager=None,
                )
                ok, reason = saves.save_run_to_slot(1, fake_game)
                self.assertTrue(ok, reason)
                slot_p = saves.get_slot_path(1)
                self.assertTrue(os.path.isfile(slot_p))
                self.assertFalse(os.path.exists(slot_p + ".tmp"))
                summary = saves.get_slot_summary(1)
                self.assertFalse(summary["empty"])
                self.assertFalse(summary["corrupt"])

                # Delete -> re-save -> corrupt primary -> verify backup recovery
                with open(slot_p + ".bak", "w", encoding="utf-8") as bf:
                    with open(slot_p, "r", encoding="utf-8") as sf:
                        bf.write(sf.read())
                with open(slot_p, "w", encoding="utf-8") as sf:
                    sf.write("{broken_json")
                self.assertIsNotNone(saves._read_slot_payload(1))
                summary2 = saves.get_slot_summary(1)
                self.assertFalse(summary2["corrupt"])
            finally:
                settings._CACHED_USER_DATA_DIR = old_dir


class TestLocalizationAndLayout(unittest.TestCase):
    def test_rebranding_and_contacts_keys(self):
        self.assertEqual(i18n.TEXTS["ru"]["menu_mods"], "РЕДАКТОР КОДА")
        self.assertEqual(i18n.TEXTS["en"]["menu_mods"], "CODE EDITOR")
        self.assertEqual(i18n.TEXTS["ru"]["mods_title"], "РЕДАКТОР КОДА И МОДОВ")
        self.assertEqual(i18n.TEXTS["en"]["mods_title"], "CODE EDITOR & MODS")
        for lang in ("ru", "en"):
            for k in ("mods_contacts_btn", "mods_contacts_title", "mods_contacts_email", "mods_contacts_github"):
                self.assertIn(k, i18n.TEXTS[lang])
            serialized = json.dumps(i18n.TEXTS[lang], ensure_ascii=False).lower()
            self.assertNotIn("браузер модификаций", serialized)
            self.assertNotIn("mod browser", serialized)

    def test_code_editor_rects_no_overlap(self):
        screen = mods.ModBrowserScreen()
        for vw in (1280, 1600):
            settings.set_view_width(vw)
            for ai_open in (True, False):
                screen.ai_open = ai_open
                rc = screen._rects()
                # Row 2 tools must not overlap each other
                row2 = [rc["tab_mods"], rc["tab_sources"], rc["btn_find"], rc["btn_undo"], rc["btn_redo"], rc["btn_copy"], rc["btn_paste"], rc["reload"]]
                for i in range(len(row2) - 1):
                    self.assertLessEqual(row2[i].right, row2[i + 1].left, f"Row 2 overlap at vw={vw} ai={ai_open} idx={i}")
                # Row 1 right buttons must stay above Row 2 and not overlap each other
                row1 = [rc["btn_contacts"], rc["ai_toggle"], rc["back"]]
                for i in range(len(row1) - 1):
                    self.assertLessEqual(row1[i].right, row1[i + 1].left)
                for b in row1:
                    self.assertLess(b.bottom, rc["tab_mods"].top)
                # Bottom editor actions must stay clear of ai_panel when open
                if ai_open:
                    self.assertLessEqual(rc["snip_buff"].right, rc["ai_panel"].left)
        settings.set_view_width(1280)

    def test_main_has_signal_handlers_and_sdl_cleanup(self):
        main_path = os.path.join(GAME_DIR, "main.py")
        with open(main_path, "r", encoding="utf-8") as fh:
            src = fh.read()
        tree = ast.parse(src)
        func_names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        self.assertIn("_install_signal_handlers", func_names)
        self.assertIn("_cleanup_sdl_resources", func_names)
        self.assertIn("_init_sdl_subsystems", func_names)
        self.assertIn("sys.exit(", src)
        self.assertIn("SIGINT", src)
        self.assertIn("SIGTERM", src)
        self.assertIn("atexit.register", src)


class TestCoopInterfaceAndGameplay(unittest.TestCase):
    def test_coop_localization_keys_complete(self):
        coop_keys = (
            "coop_ko",
            "p2_down",
            "p2_revived",
            "p2_revive_hint",
            "coop_controls_line1",
            "coop_controls_line2",
            "coop_controls_hint",
            "coop_on",
            "coop_off",
            "menu_p2_hero",
            "menu_coop_toggle",
        )
        for lang in ("ru", "en"):
            for k in coop_keys:
                self.assertIn(k, i18n.TEXTS[lang], f"Missing {k} for {lang}")
                self.assertTrue(str(i18n.TEXTS[lang][k]).strip(), f"Empty {k} for {lang}")
                self.assertNotEqual(i18n.TEXTS[lang][k], k)

    def test_coop_hud_layout_no_overlap_across_viewports(self):
        ui = ui_mod.UI()
        import pygame as pg

        for vw in (1280, 1680):
            for touch_active in (False, True):
                for has_banner_item in (False, True):
                    for p2_dead in (False, True):
                        lay = ui.get_coop_hud_layout(
                            vw=vw,
                            touch_active=touch_active,
                            extra_rows=1,
                            p2_extra_rows=1,
                            p2_dead=p2_dead,
                            game_mode="fading_light",
                            p2_present=True,
                            has_banner_item=has_banner_item,
                        )
                        p1 = lay["p1"]
                        p2 = lay["p2"]
                        mm = lay["minimap"]
                        banner = pg.Rect(lay["banner_x"], 24, lay["banner_w"], 64)

                        self.assertIsNotNone(p2)
                        self.assertFalse(p1.colliderect(p2), f"P1/P2 overlap vw={vw} touch={touch_active}")
                        self.assertFalse(p2.colliderect(mm), f"P2/minimap overlap vw={vw} touch={touch_active}")
                        self.assertFalse(banner.colliderect(p1), f"Banner/P1 overlap vw={vw} touch={touch_active}")
                        self.assertFalse(banner.colliderect(p2), f"Banner/P2 overlap vw={vw} touch={touch_active}")
                        self.assertFalse(banner.colliderect(mm), f"Banner/minimap overlap vw={vw} touch={touch_active}")
                        if touch_active:
                            pause_rect = pg.Rect(vw - 254, 16, 44, 44)
                            self.assertFalse(p2.colliderect(pause_rect), f"P2/touch pause overlap vw={vw}")

    def test_chaos_draft_and_end_rects(self):
        ui = ui_mod.UI()
        for cnt in (1, 2, 3):
            rects = ui.get_chaos_draft_rects(cnt)
            self.assertEqual(len(rects), cnt)
            for i in range(len(rects) - 1):
                self.assertLess(rects[i].right, rects[i + 1].left)
        for ta in (False, True):
            for is_coop in (False, True):
                b1, b2 = ui.get_end_rects(touch_active=ta, is_coop=is_coop)
                self.assertFalse(b1.colliderect(b2))

    def test_coop_hud_player_draw_and_end_screen_smoke(self):
        import pygame as pg

        ui = ui_mod.UI()
        screen = pg.Surface((1280, 720))
        p1 = player_mod.Player(400, 360, "isaac")
        p1.player_tag = "P1"
        p2 = player_mod.Player(480, 360, "cain")
        p2.player_tag = "P2"

        p1.draw(screen)
        p2.draw(screen)

        fake_room = types.SimpleNamespace(
            room_type="combat",
            visited=True,
            enemies=[],
            bosses=[],
            floor_modifier=None,
            victory_portal_rect=None,
            trapdoor_rect=None,
        )
        ui.show_banner("CO-OP TEST", "SUBTITLE", duration=80.0, item=p1.collected_items[0] if p1.collected_items else None)
        ui.draw_hud(screen, p1, {(0, 0): fake_room}, (0, 0), fake_room, 1, p2=p2, game_mode="classic")
        if p2.active_item is not None:
            self.assertIsNotNone(ui.get_p2_active_relic_rect())

        # Verify fallen P2 HUD clears active relic rect cleanly
        p2.hp = 0
        p2.soul_hp = 0
        p2.black_hp = 0
        ui.draw_hud(screen, p1, {(0, 0): fake_room}, (0, 0), fake_room, 1, p2=p2, game_mode="classic")
        self.assertIsNone(ui.get_p2_active_relic_rect())

        ui.draw_end_screen(screen, True, p1, 3, boss_key="", game_mode="classic", p2=p2)

    def test_coop_save_when_p1_ko_and_p2_alive_restores_tags(self):
        with tempfile.TemporaryDirectory() as td:
            old_dir = settings._CACHED_USER_DATA_DIR
            settings._CACHED_USER_DATA_DIR = td
            try:
                p1 = player_mod.Player(500, 360, "isaac")
                p1.player_tag = "P1"
                p1.hp = 0
                p1.soul_hp = 0
                p1.black_hp = 0
                p1.kills = 4

                p2 = player_mod.Player(540, 360, "azazel")
                p2.player_tag = "P2"
                p2.kills = 7

                fake_room = types.SimpleNamespace(
                    coord=(0, 0),
                    room_type="combat",
                    cleared=True,
                    visited=True,
                    wave_spawns_left=0,
                    ambush_triggered=False,
                    theme={"ambient": 0.35},
                    doors={},
                    obstacles=[],
                    pickups=[],
                    pedestals=[],
                    enemies=[],
                    bosses=[],
                    beggars=[],
                    shopkeepers=[],
                    machines=[],
                    monoliths=[],
                    mystical_npcs=[],
                    sacrifice_spikes=None,
                    dice_floor=None,
                    trapdoor=None,
                    devil_portal=None,
                )
                fake_game = types.SimpleNamespace(
                    player=p1,
                    player2=p2,
                    coop_enabled=True,
                    game_mode="classic",
                    floor_level=2,
                    floor_modifier=None,
                    wave_num=1,
                    wave_break_timer=0.0,
                    darkness_tick=0.0,
                    placenta_tick=0.0,
                    active_seed=12345,
                    boss_rush_wave=1,
                    current_coord=(0, 0),
                    devil_return_coord=(0, 0),
                    current_room=fake_room,
                    rooms={(0, 0): fake_room},
                    devil_room=None,
                    quest_manager=None,
                )
                ok, reason = saves.save_run_to_slot(2, fake_game)
                self.assertTrue(ok, reason)
                summary = saves.get_slot_summary(2)
                self.assertTrue(summary["coop_enabled"])
                self.assertEqual(summary["kills"], 11)
                self.assertTrue(bool(summary.get("p2_hero_name")))

                # Verify load restores player_tag on both players
                from room import Room

                class FakeGameForLoad:
                    def __init__(self):
                        self.player = None
                        self.player2 = None
                        self.coop_enabled = False
                        self.game_mode = "classic"
                        self.floor_level = 1
                        self.floor_modifier = None
                        self.wave_num = 1
                        self.wave_break_timer = 0.0
                        self.darkness_tick = 0.0
                        self.placenta_tick = 0.0
                        self.active_seed = None
                        self.boss_rush_wave = 1
                        self.current_coord = (0, 0)
                        self.devil_return_coord = (0, 0)
                        self.rooms = {(0, 0): Room((0, 0), "start", 1)}
                        self.current_room = self.rooms[(0, 0)]
                        self.devil_room = None
                        self.quest_manager = None
                        self.tears = []
                        self.enemy_projectiles = []
                        self.particles = []
                        self.bombs = []
                        self.editor = types.SimpleNamespace(active=False)
                        self.console = types.SimpleNamespace(open=False)
                        self.ui = ui_mod.UI()

                fg = FakeGameForLoad()
                ok_load, load_msg = saves.load_run_from_slot(2, fg)
                self.assertTrue(ok_load, load_msg)
                self.assertTrue(fg.coop_enabled)
                self.assertIsNotNone(fg.player)
                self.assertIsNotNone(fg.player2)
                self.assertEqual(fg.player.player_tag, "P1")
                self.assertEqual(fg.player2.player_tag, "P2")
            finally:
                settings._CACHED_USER_DATA_DIR = old_dir

    def test_main_coop_symbols_present_and_valid_ast(self):
        main_path = os.path.join(GAME_DIR, "main.py")
        with open(main_path, "r", encoding="utf-8") as fh:
            src = fh.read()
        tree = ast.parse(src)
        func_names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        for fn in ("_toggle_coop_setting", "_cycle_p2_hero", "_nudge_clear_of_obstacles", "_all_players_dead"):
            self.assertIn(fn, func_names)
        self.assertIn("K_F4", src)
        self.assertIn("K_SLASH", src)
        self.assertIn("get_p2_active_relic_rect", src)
        self.assertIn("coop_controls_line1", src)
        self.assertIn("coop_controls_line2", src)


class TestTouchStealthBricksAndLan(unittest.TestCase):
    def test_touch_stealth_button_anchored_sticks_and_non_overlapping(self):
        import math
        import pygame as pg
        from touch_controls import TouchControls

        tc = TouchControls()
        old_mode = settings.GAME_SETTINGS.get("touch_controls", "auto")
        settings.GAME_SETTINGS["touch_controls"] = "on"
        try:
            for vw in (1280, 1600):
                settings.set_view_width(vw)
                tc.reset()
                tc._sync_layout()
                buttons = [
                    ("dash", tc.dash_center, tc.dash_radius),
                    ("jump", tc.jump_center, tc.jump_radius),
                    ("bomb", tc.bomb_center, tc.bomb_radius),
                    ("stealth", tc.stealth_center, tc.stealth_radius),
                    ("relic", tc.relic_center, tc.relic_radius),
                    ("pause", tc.pause_center, tc.pause_radius),
                ]
                for i in range(len(buttons)):
                    n1, c1, r1 = buttons[i]
                    for j in range(i + 1, len(buttons)):
                        n2, c2, r2 = buttons[j]
                        dist = math.hypot(c1[0] - c2[0], c1[1] - c2[1])
                        self.assertGreaterEqual(dist, r1 + r2 + 4, f"Touch buttons {n1}/{n2} overlap at vw={vw}")

                # Tap stealth button
                self.assertTrue(tc.handle_finger_down(10, tc.stealth_center))
                acts = tc.consume_actions()
                self.assertTrue(acts["stealth"])
                self.assertFalse(tc.consume_actions()["stealth"])
                tc.handle_finger_up(10)

                # Tap left stick region: move_base must stay anchored at move_base_default
                tap_x = tc.move_base_default[0] + 24
                tap_y = tc.move_base_default[1] - 18
                self.assertTrue(tc.handle_finger_down(11, (tap_x, tap_y)))
                self.assertEqual(tc.move_base, tc.move_base_default)
                tc.handle_finger_up(11)

                # Draw stealth state variants without crashing
                ui = ui_mod.UI()
                p = player_mod.Player(400, 360, "isaac")
                surf = pg.Surface((vw, settings.SCREEN_HEIGHT))
                tc.draw(surf, p, ui)
                p.invis_timer = 60.0
                tc.draw(surf, p, ui)
                p.invis_timer = 0.0
                p.invis_cd = 120.0
                tc.draw(surf, p, ui)
        finally:
            settings.GAME_SETTINGS["touch_controls"] = old_mode
            settings.set_view_width(1280)

    def test_wide_brick_backdrop_and_room_bake_smoke(self):
        import pygame as pg
        import room as room_mod

        surf = pg.Surface((1600, settings.SCREEN_HEIGHT))
        room_mod.draw_wide_backdrop(surf, 1600, 160, extra_pad=32)
        rm = room_mod.Room((0, 0), "combat", 1)
        rm._bake_background()
        self.assertIsNotNone(rm._baked_bg)

    def test_lan_coop_host_client_loopback_sync(self):
        import time
        from lan_coop import LanClient, LanHost, parse_host_port

        self.assertEqual(parse_host_port("192.168.1.42:25000"), ("192.168.1.42", 25000))
        self.assertEqual(parse_host_port("192.168.1.42"), ("192.168.1.42", 24680))

        host = LanHost()
        client = LanClient()
        try:
            ok_h, msg_h = host.start(host_name="TestHost", hero_id="isaac", game_mode="classic", port=24780)
            self.assertTrue(ok_h, msg_h)
            ok_c, msg_c = client.connect("127.0.0.1", host.port, name="PhoneP2", hero_id="cain")
            self.assertTrue(ok_c, msg_c)

            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline and not host.client_connected:
                time.sleep(0.02)
            self.assertTrue(host.client_connected)

            client.send_input(1.0, -0.5, 0.0, 1.0, dash=True, jump=True, stealth=True, bomb=False, relic=True)
            got_in = None
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                cand = host.consume_client_input()
                if cand is not None and (cand["mx"] > 0.5 or cand["stealth"]):
                    got_in = cand
                    break
                time.sleep(0.02)
            self.assertIsNotNone(got_in)
            self.assertAlmostEqual(got_in["mx"], 1.0, places=2)
            self.assertTrue(got_in["jump"])
            self.assertTrue(got_in["stealth"])
            self.assertTrue(got_in["relic"])

            host.send_snapshot({"type": "state", "in_run": True, "floor": 3, "room_type": "boss"})
            snap = None
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                snap = client.get_latest_state()
                if snap is not None and snap.get("floor") == 3:
                    break
                time.sleep(0.02)
            self.assertIsNotNone(snap)
            self.assertTrue(snap["in_run"])
            self.assertEqual(snap["room_type"], "boss")
        finally:
            client.stop()
            host.stop()

    def test_split_menu_geometry_and_lan_i18n_keys(self):
        for lang in ("ru", "en"):
            for k in ("menu_lan_btn", "touch_inv", "lan_title", "lan_host_btn", "lan_scan_btn", "lan_join_btn", "lan_back_btn"):
                self.assertIn(k, i18n.TEXTS[lang])
                self.assertNotEqual(i18n.TEXTS[lang][k], k)

        main_path = os.path.join(GAME_DIR, "main.py")
        with open(main_path, "r", encoding="utf-8") as fh:
            src = fh.read()
        tree = ast.parse(src)
        func_names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        for fn in ("_menu_card_metrics", "_menu_p2_hero_rects", "_draw_hero_select_card", "_lan_lobby_rects", "_draw_lan_lobby", "_draw_lan_client", "_build_lan_snapshot"):
            self.assertIn(fn, func_names)
        self.assertIn("extra_pad=", src)
        self.assertIn('t_actions.get("stealth")', src)
        self.assertIn("K_F5", src)

        # Verify 3-column menu geometry has zero overlap for 1280 and 1600
        for vw in (1280, 1600):
            hero_w, menu_w, gap = (420, 436, 20) if vw >= 1440 else (392, 408, 14)
            total_w = hero_w * 2 + menu_w + gap * 2
            sx = max(12, (vw - total_w) // 2)
            p1_right = sx + hero_w
            menu_left = sx + hero_w + gap
            menu_right = menu_left + menu_w
            p2_left = menu_right + gap
            p2_right = p2_left + hero_w
            self.assertLess(p1_right, menu_left)
            self.assertLess(menu_right, p2_left)
            self.assertLessEqual(p2_right, vw - 12)


if __name__ == "__main__":
    unittest.main()
