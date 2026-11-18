import glob
import os
import random
import re
import sys
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME_DIR = os.path.join(ROOT_DIR, "GAME")
TESTS_DIR = os.path.join(ROOT_DIR, "tests")
if GAME_DIR not in sys.path:
    sys.path.insert(0, GAME_DIR)
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)

import test_stability

test_stability._install_pygame_stub()

import pygame

if not hasattr(pygame.Rect, "center"):
    pygame.Rect.center = property(lambda self: (self.centerx, self.centery))
if not hasattr(pygame.Surface, "get_bitsize"):
    pygame.Surface.get_bitsize = lambda self: 32
pygame.transform.scale = lambda s, sz, dest=None: dest if dest is not None else pygame.Surface(sz)
pygame.transform.smoothscale = lambda s, sz, dest=None: dest if dest is not None else pygame.Surface(sz)

import accounts
import achievements
import bosses
import enemy
import heroes
import i18n
import items
import lighting
import main as gm
import room as room_mod
import settings
import sound
import ui as ui_mod
from bullet import EnemyProjectile
from player import Player


class FullProjectAuditTests(unittest.TestCase):
    def test_i18n_ru_en_parity_and_boss_translations(self):
        ru = set(i18n.TEXTS["ru"].keys())
        en = set(i18n.TEXTS["en"].keys())
        self.assertEqual(ru - en, set(), f"Keys in RU missing from EN: {sorted(ru - en)}")
        self.assertEqual(en - ru, set(), f"Keys in EN missing from RU: {sorted(en - ru)}")
        self.assertIn("settings_music", ru)
        self.assertIn("settings_music", en)

        for bk in bosses.BOSS_BASE_CONFIG:
            self.assertNotEqual(i18n.tr_boss(bk), bk, f"Boss {bk} missing translation")

    def test_sound_keys_and_procedural_ost(self):
        with open(os.path.join(GAME_DIR, "sound.py"), "r", encoding="utf-8") as fh:
            sound_src = fh.read()
        defined = set(re.findall(r'self\.sounds\["([^"]+)"\]', sound_src))
        used = set()
        for p in glob.glob(os.path.join(GAME_DIR, "*.py")):
            with open(p, "r", encoding="utf-8") as fh:
                src = fh.read()
            for m in re.finditer(r'play_sound\(\s*["\']([^"\']+)["\']', src):
                used.add(m.group(1))
        self.assertEqual(used - defined, set(), f"Undefined sound keys: {sorted(used - defined)}")

        sb = sound.SoundBank()
        self.assertIsNotNone(sb)
        for mode in ("menu", "combat", "boss", "none"):
            sound.update_music(mode)
        sound.play_sound("melee_combo")
        sound.play_sound("melee_deflect")
        sound.play_sound("block_break")
        sound.play_sound("boss_beam")
        sound.play_sound("hero_unlock")

    def test_melee_three_hit_combo_reflection_and_hud(self):
        rm = room_mod.Room((0, 0), room_type="normal", floor_level=3, layout_key="empty")
        p = Player(400, 360, "isaac")
        tears = []
        particles = []
        eprojs = [EnemyProjectile(440, 360, -4.0, 0.0, 1, 5.0)]

        r1 = p.try_melee(1.0, 0.0, rm, [], eprojs, particles, tears=tears)
        self.assertTrue(r1["hit"])
        self.assertEqual(r1["combo"], 1)
        self.assertFalse(r1["finisher"])
        self.assertEqual(r1["deflected"], 1)
        self.assertEqual(len(tears), 1)

        p.melee_cd = 0.0
        r2 = p.try_melee(1.0, 0.0, rm, [], [], particles, tears=tears)
        self.assertEqual(r2["combo"], 2)
        self.assertFalse(r2["finisher"])

        p.melee_cd = 0.0
        r3 = p.try_melee(1.0, 0.0, rm, [], [], particles, tears=tears)
        self.assertEqual(r3["combo"], 3)
        self.assertTrue(r3["finisher"])

        hud = ui_mod.UI()
        surf = pygame.Surface((1280, 720))
        hud.draw_hud(surf, p, {(0, 0): rm}, (0, 0), rm, 3)

    def test_all_heroes_and_all_items_stability(self):
        rm = room_mod.Room((0, 0), room_type="normal", floor_level=2, layout_key="pillars_4")
        surf = pygame.Surface((1280, 720))
        self.assertEqual(len(heroes.HERO_ROSTER), 22)
        for h in heroes.HERO_ROSTER:
            p = Player(400, 360, h["id"])
            p.update(1.0, 0.0, rm, [], 1.0)
            p.shoot(1.0, 0.0, [])
            p.draw(surf)

        self.assertEqual(len(items.ITEM_POOL_65), 123)
        for it in items.ITEM_POOL_65:
            p = Player(400, 360, "isaac")
            p.apply_item(it)
            if it.get("type") == "active":
                p.active_charge = p.max_charge
                p.use_active(rm, [], [], [])

    def test_all_enemies_higher_floors_and_all_bosses(self):
        rm = room_mod.Room((0, 0), room_type="normal", floor_level=4, layout_key="empty")
        p = Player(400, 360, "isaac")
        surf = pygame.Surface((1280, 720))

        total_hi_projs = 0
        for et in settings.ENEMY_BASE_STATS:
            for fl in (1, 4):
                en = enemy.create_enemy(et, 700, 360, fl)
                projs = []
                for _ in range(95):
                    en.update(p, rm, projs, 1.0)
                en.draw(surf)
                if fl == 4:
                    total_hi_projs += len(projs)
        self.assertGreater(total_hi_projs, 20)

        boss_room = room_mod.Room((0, 0), room_type="boss", floor_level=4, layout_key="empty")
        self.assertEqual(len(bosses.BOSS_BASE_CONFIG), 66)
        for bk in bosses.BOSS_BASE_CONFIG:
            bs = bosses.spawn_boss_for_room(boss_room, bk, 700, 360, 4)
            projs = []
            minions = []
            for b in bs:
                for step in range(60):
                    if step == 30:
                        b.hp = max(1.0, b.max_hp * 0.4)
                    b.update(p, boss_room, projs, minions, 1.0)
                b.draw(surf)

    def test_new_blocks_ten_percent_drop_chance(self):
        game = gm.Game.__new__(gm.Game)
        game.current_room = room_mod.Room((0, 0), room_type="normal", floor_level=2, layout_key="empty")
        game.player = Player(400, 360, "isaac")
        game.player2 = None
        game.coop_enabled = False
        game.particles = []

        random.seed(12345)
        drops = 0
        trials = 600
        for kind in ("barrier", "turret", "rock"):
            for _ in range(trials // 3):
                game.current_room.pickups.clear()
                obs = room_mod.Obstacle(500, 350, kind)
                game._on_obstacle_shattered(obs)
                if game.current_room.pickups:
                    drops += 1
        rate = drops / float(trials)
        self.assertGreaterEqual(rate, 0.05)
        self.assertLessEqual(rate, 0.16)

    def test_hero_unlocks_and_achievement_stat_wiring(self):
        acc = {"stats": {"no_damage_rooms": 14}}
        unl, cur, tgt = heroes.get_hero_unlock_progress("chrono", acc)
        self.assertFalse(unl)
        self.assertEqual((cur, tgt), (14, 15))

        acc["stats"]["no_damage_rooms"] = 15
        unl2, cur2, tgt2 = heroes.get_hero_unlock_progress("chrono", acc)
        self.assertTrue(unl2)
        self.assertTrue(heroes.is_hero_unlocked("chrono", acc))

        with open(os.path.join(GAME_DIR, "main.py"), "r", encoding="utf-8") as fh:
            main_src = fh.read()
        for stat_key in ("no_damage_rooms", "rooms_visited", "doors_opened", "sacrifice_uses", "dice_uses"):
            self.assertIn(f'record_stat("{stat_key}"', main_src, f"Missing record_stat for {stat_key}")

    def test_lighting_secondary_shadows_and_android_optimizations(self):
        rm = room_mod.Room((0, 0), room_type="normal", floor_level=2, layout_key="empty")
        rm.obstacles.append(room_mod.Obstacle(520, 360, "brazier"))
        rm.obstacles.append(room_mod.Obstacle(600, 360, "rock"))
        surf = pygame.Surface((1280, 720))
        ls = lighting.LightingSystem(1280, 720)
        ls.render(surf, 400, 360, rm, time_acc=15.0)

        prev = gm.TitlePreviewSimulator()
        prev.update(1.0, low_power=True)
        prev.draw(surf, ls, low_power=True)
        prev.update(1.0, low_power=True)
        prev.draw(surf, ls, low_power=True)
        self.assertIsNotNone(prev._cached_surf)

        old_env = os.environ.get("ANDROID_ARGUMENT")
        old_wide = settings.GAME_SETTINGS.get("wide_mode", "auto")
        os.environ["ANDROID_ARGUMENT"] = "1"
        settings.GAME_SETTINGS["wide_mode"] = "auto"
        try:
            # Phones must use their wide landscape aspect ratio (not forced 16:9 PC width)
            self.assertEqual(settings.compute_wide_view_width(2400, 1080), 1600)
            self.assertEqual(settings.compute_wide_view_width(1080, 2400), 1600)
            self.assertEqual(settings.compute_wide_view_width(2340, 1080), 1560)
            self.assertEqual(settings.compute_wide_view_width(2520, 1080), 1680)
            self.assertEqual(settings.compute_wide_view_width(1920, 1080), 1280)
            acfg = settings.get_effects_config()
            self.assertFalse(acfg["smooth_scale"])
            self.assertFalse(acfg["bloom"])
            self.assertLessEqual(acfg["light_w"], 360)
        finally:
            settings.GAME_SETTINGS["wide_mode"] = old_wide
            if old_env is None:
                os.environ.pop("ANDROID_ARGUMENT", None)
            else:
                os.environ["ANDROID_ARGUMENT"] = old_env

    def test_android_touch_controls_and_mouse_fallback(self):
        import types
        from touch_controls import TouchControls

        old_env = os.environ.get("ANDROID_ARGUMENT")
        old_wide = settings.GAME_SETTINGS.get("wide_mode", "auto")
        old_tc_mode = settings.GAME_SETTINGS.get("touch_controls", "auto")
        os.environ["ANDROID_ARGUMENT"] = "1"
        settings.GAME_SETTINGS["wide_mode"] = "auto"
        settings.GAME_SETTINGS["touch_controls"] = "auto"
        try:
            # Simulate a 2400x1080 (20:9) Android display surface
            g = gm.Game.__new__(gm.Game)
            g.display_surf = pygame.Surface((2400, 1080))
            g.screen = None
            g._menu_dim = None
            g._present_rect = pygame.Rect(0, 0, 1280, 720)
            g._present_display_size = (0, 0)
            g._present_buf = None
            g._present_scale_buf = None
            g._scaled_mode = False
            g._finger_events_seen = False
            g.touch = TouchControls()
            g.ui = None
            g._update_present_rect()

            self.assertEqual(settings.get_view_width(), 1600)
            self.assertEqual((g._present_rect.x, g._present_rect.y, g._present_rect.w, g._present_rect.h), (0, 0, 2400, 1080))
            self.assertTrue(g.touch.is_active())

            # Normalized 0..1 finger coordinates map across the full 1600x720 wide screen
            self.assertEqual(g._finger_to_logical(0.5, 0.5), (800, 360))
            # Pixel coordinates fallback (> 1.5) also maps cleanly
            self.assertEqual(g._finger_to_logical(1200.0, 540.0), (800, 360))

            # Touch-mouse fallback: when no FINGER* events have arrived yet, touch=True mouse events are NOT dropped
            raw_tm = types.SimpleNamespace(type=getattr(pygame, "MOUSEBUTTONDOWN", 1025), pos=(1200, 540), button=1, touch=True)
            self.assertTrue(g._is_raw_touch_mouse_event(raw_tm))
            self.assertFalse(g._is_touch_mouse_event(raw_tm))
            # Once real FINGER* events arrive, duplicate touch-mouse events ARE suppressed
            g._finger_events_seen = True
            self.assertTrue(g._is_touch_mouse_event(raw_tm))

            # Direct move & aim stick touches (including low-edge thumb placement) engage cleanly
            mx, my = g.touch.move_base_default
            self.assertTrue(g.touch.handle_finger_down(0, (mx + 25, my + 55)))
            self.assertEqual(g.touch.move_finger, 0)
            self.assertGreater(abs(g.touch.move_vec[0]) + abs(g.touch.move_vec[1]), 0.1)

            ax, ay = g.touch.aim_base_default
            self.assertTrue(g.touch.handle_finger_down(1, (ax - 30, ay)))
            self.assertEqual(g.touch.aim_finger, 1)
            self.assertEqual(g.touch.aim_dir, (-1, 0))

            # Multi-touch release
            self.assertTrue(g.touch.handle_finger_up(0))
            self.assertTrue(g.touch.handle_finger_up(1))
            self.assertIsNone(g.touch.move_finger)
            self.assertIsNone(g.touch.aim_finger)
            # Edge-to-edge fill on non-multiple-of-8 phone screen (e.g. 2388x1080) and ultra-tall 22:9 (2640x1080)
            g.display_surf = pygame.Surface((2388, 1080))
            g._update_present_rect()
            self.assertEqual((g._present_rect.x, g._present_rect.y, g._present_rect.w, g._present_rect.h), (0, 0, 2388, 1080))
            self.assertEqual(settings.compute_wide_view_width(2640, 1080), 1760)

            # Pixelated shadow surface + 1/4-res pixelated obstacle shadow buffer
            sh_surf = settings.get_shadow_surf(36, 14, 120)
            self.assertEqual(sh_surf.get_size(), (36, 14))
            ls = lighting.LightingSystem(1280, 720)
            self.assertEqual(ls.shadow_buf.get_size(), (320, 180))
        finally:
            settings.GAME_SETTINGS["wide_mode"] = old_wide
            settings.GAME_SETTINGS["touch_controls"] = old_tc_mode
            settings.set_view_width(settings.BASE_WIDTH)
            if old_env is None:
                os.environ.pop("ANDROID_ARGUMENT", None)
            else:
                os.environ["ANDROID_ARGUMENT"] = old_env

    def test_apk_marker_binds_android_mode_only_to_apk(self):
        marker_path = os.path.join(GAME_DIR, "android_build.json")
        had_marker = os.path.exists(marker_path)
        old_env_vals = {k: os.environ.pop(k, None) for k in ("ANDROID_ARGUMENT", "ANDROID_PRIVATE", "ANDROID_BOOTLOGO", "ANDROID_ROOT", "ANDROID_DATA", "ANDROID_STORAGE", "P4A_BOOTSTRAP")}
        try:
            if not had_marker:
                self.assertFalse(settings.is_android_apk())
                self.assertFalse(settings.is_android())
                self.assertFalse(settings.is_phone_layout(False))
            with open(marker_path, "w", encoding="utf-8") as fh:
                fh.write('{"target":"android_apk","fullscreen":true,"ui_scale":"phone","touch_controls":"on","wide_mode":"auto"}')
            self.assertTrue(settings.is_android_apk())
            self.assertTrue(settings.is_android())
            self.assertTrue(settings.is_phone_layout(False))
        finally:
            if not had_marker and os.path.exists(marker_path):
                os.remove(marker_path)
            for k, v in old_env_vals.items():
                if v is not None:
                    os.environ[k] = v

    def test_settings_panel_rows_fit_cleanly(self):
        game = gm.Game.__new__(gm.Game)
        count = game._settings_row_count()
        rects = game._settings_rects()
        self.assertEqual(count, 16)
        self.assertEqual(len(rects), 16)
        panel_top = settings.SCREEN_HEIGHT // 2 - 332
        panel_bottom = panel_top + 664
        self.assertGreaterEqual(rects[0].y, panel_top + 48)
        self.assertLessEqual(rects[-1].y + rects[-1].h, panel_bottom - 8)

    def test_installers_and_buildozer_consistency(self):
        with open(os.path.join(GAME_DIR, "build_common.py"), "r", encoding="utf-8") as fh:
            bc_src = fh.read()
        for p in glob.glob(os.path.join(GAME_DIR, "*.py")):
            mod_name = os.path.splitext(os.path.basename(p))[0]
            if mod_name in ("main", "build_common"):
                continue
            self.assertIn(mod_name, bc_src, f"Module {mod_name} missing from GAME/build_common.py")

        with open(os.path.join(ROOT_DIR, "buildozer.spec"), "r", encoding="utf-8") as fh:
            spec_root = fh.read()
        with open(os.path.join(ROOT_DIR, "Android installer", "buildozer.spec"), "r", encoding="utf-8") as fh:
            spec_and = fh.read()
        for line_key in ("package.name =", "package.domain =", "requirements =", "orientation =", "fullscreen =", "android.display_cutout =", "android.api ="):
            r_line = [ln.strip() for ln in spec_root.splitlines() if ln.strip().startswith(line_key)]
            a_line = [ln.strip() for ln in spec_and.splitlines() if ln.strip().startswith(line_key)]
            self.assertTrue(r_line, f"Missing {line_key} in root buildozer.spec")
            self.assertEqual(r_line, a_line, f"Mismatch in buildozer.spec for {line_key}")

    def test_all_66_bosses_have_unique_profiles_and_dialogues(self):
        import bosses
        import boss_profiles

        self.assertEqual(len(bosses.PLAYABLE_BOSS_KEYS), 66)
        for bk in bosses.PLAYABLE_BOSS_KEYS:
            self.assertIn(bk, boss_profiles.BOSS_SIGNATURE_PROFILES, f"Missing profile for boss {bk}")
            prof = boss_profiles.BOSS_SIGNATURE_PROFILES[bk]
            for k in ("sig_p1", "sig_p2", "sig_p3", "wall_pattern", "beam_pattern", "taunt_p1", "taunt_p2", "taunt_p3", "sig_call"):
                self.assertIn(k, prof, f"Missing key {k} in profile for {bk}")
            for tk in ("taunt_p1", "taunt_p2", "taunt_p3", "sig_call"):
                self.assertEqual(len(prof[tk]), 2)
                self.assertTrue(prof[tk][0].strip() and prof[tk][1].strip())

    def test_boss_multistage_dialogue_walls_and_laser_beams(self):
        import bosses
        import player as pl_mod
        import room as rm_mod

        room = rm_mod.Room((0, 0), "boss", floor_level=4)
        room.obstacles = []
        p = pl_mod.Player(220, 360, "isaac")
        boss = bosses.BossBase(640, 360, "void_architect", floor_level=4)
        projs = []
        enemies = []

        # Phase 1 intro triggers dialogue
        boss.update(p, room, projs, enemies, dt=1.0)
        self.assertTrue(boss.speech_text)
        self.assertGreater(boss.speech_timer, 0.0)

        # Drop to Phase 2 -> triggers Phase 2 dialogue, spawns safe walls & telegraphing beams
        boss.hp = boss.max_hp * 0.55
        boss.update(p, room, projs, enemies, dt=1.0)
        self.assertEqual(boss.phase, 2)
        self.assertGreater(len(boss.spawned_walls), 0)
        self.assertGreater(len(boss.beams), 0)
        for w in boss.spawned_walls:
            dist_p = ((w.rect.centerx - p.x) ** 2 + (w.rect.centery - p.y) ** 2) ** 0.5
            self.assertGreaterEqual(dist_p, 90.0, "Boss wall spawned too close to player")

        # Advance past beam windup so beams become active and can draw cleanly
        surf = pygame.Surface((1280, 720))
        font = pygame.font.Font(None, 18)
        boss.draw_post_light(surf, font)
        for _ in range(55):
            boss._update_beams_and_walls(room, dt=1.0)
        self.assertTrue(any(b["windup"] <= 0 and b["active"] > 0 for b in boss.beams))
        boss.draw_post_light(surf, font)

        # Place a target directly on an active beam and verify beam damage
        active_b = next(b for b in boss.beams if b["windup"] <= 0 and b["active"] > 0)
        p.x = (boss.x + active_b["end_x"]) * 0.5
        p.y = (boss.y + active_b["end_y"]) * 0.5
        p.invuln_timer = 0.0
        hp_before = p.hp
        hits = boss.check_beam_hits([p])
        self.assertEqual(len(hits), 1)
        self.assertLess(p.hp, hp_before)

        # Killing the boss cleans up all spawned arena walls and beams
        boss.take_damage(boss.hp + 999)
        self.assertFalse(boss.alive)
        self.assertEqual(len(boss.spawned_walls), 0)
        self.assertEqual(len(boss.beams), 0)
        self.assertFalse(any(getattr(ob, "is_boss_wall", False) for ob in room.obstacles))

    def test_heroes_renamed_from_isaac_and_differentiated(self):
        import heroes
        import player as pl_mod

        forbidden_en = {
            "isaac", "magdalene", "cain", "lazarus", "samson", "eve", "judas",
            "bethany", "apollyon", "the keeper", "lilith", "the forgotten",
            "eden", "azazel", "the lost",
        }
        forbidden_ru = {
            "исаак", "магдалина", "каин", "лазарь", "самсон", "ева", "иуда",
            "вифания", "аполлион", "хранитель", "лилит", "забытый",
            "эдем", "азазель", "потерянный",
        }
        self.assertEqual(len(heroes.HERO_ROSTER), 22)
        seen_names_ru = set()
        seen_names_en = set()
        for h in heroes.HERO_ROSTER:
            n_ru = h["name"].strip().lower()
            n_en = h["name_en"].strip().lower()
            self.assertNotIn(n_ru, forbidden_ru, f"Isaac-derived RU name still present: {h['name']}")
            self.assertNotIn(n_en, forbidden_en, f"Isaac-derived EN name still present: {h['name_en']}")
            self.assertNotIn(n_ru, seen_names_ru)
            self.assertNotIn(n_en, seen_names_en)
            seen_names_ru.add(n_ru)
            seen_names_en.add(n_en)
            # Every hero must construct cleanly in Player
            pl = pl_mod.Player(640, 360, h["id"])
            self.assertEqual(pl.hero_id, h["id"])

        # Verify distinct new abilities wired into Player
        corvin = pl_mod.Player(640, 360, "isaac")
        self.assertEqual(corvin.ash_bolt_every, 4)
        vex = pl_mod.Player(640, 360, "cain")
        self.assertTrue(vex.has_bouncing)
        self.assertGreater(vex.crit_chance, 0.0)
        midas = pl_mod.Player(640, 360, "keeper")
        midas.coins = 25
        self.assertGreater(midas.get_effective_damage(), midas.damage)
        obsidian = pl_mod.Player(640, 360, "apollyon")
        self.assertTrue(obsidian.has_vortex)
        self.assertTrue(obsidian.has_piercing)
        morok = pl_mod.Player(640, 360, "azazel")
        self.assertTrue(morok.has_chain_arc)


if __name__ == "__main__":
    unittest.main()

