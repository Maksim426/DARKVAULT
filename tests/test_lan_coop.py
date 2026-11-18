import os
import sys
import time
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GAME_DIR = os.path.join(ROOT, "GAME")
if GAME_DIR not in sys.path:
    sys.path.insert(0, GAME_DIR)

from lan_coop import (  # noqa: E402
    LanClient,
    LanHost,
    interpolate_lan_snapshot,
    parse_host_port,
    scan_lan_servers,
)


def _wait_until(predicate, timeout=2.0, step=0.02):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(step)
    return bool(predicate())


class TestLanCoop(unittest.TestCase):
    def test_parse_host_port_variants(self):
        self.assertEqual(parse_host_port("192.168.1.42"), ("192.168.1.42", 24680))
        self.assertEqual(parse_host_port("192.168.1.42:25000"), ("192.168.1.42", 25000))
        self.assertEqual(parse_host_port("", 24680), ("127.0.0.1", 24680))
        self.assertEqual(parse_host_port("10.0.0.5:bad", 24680), ("10.0.0.5", 24680))

    def test_interpolate_lan_snapshot_smooth_and_room_snap(self):
        prev_st = {
            "floor": 1,
            "coord": [0, 0],
            "p1": {"x": 100.0, "y": 200.0, "air_z": 0.0, "hero_id": "isaac"},
            "p2": {"x": 300.0, "y": 400.0, "air_z": 10.0, "hero_id": "cain"},
            "enemies": [[100.0, 100.0, 14.0, 10, 10, "gaper", 0.0]],
            "bosses": [[500.0, 300.0, 32.0, 100, 100, "BOSS", "monstro", "neutral", 0.0]],
            "tears": [[200.0, 200.0, 6.0]],
            "eproj": [[400.0, 300.0, 6.0]],
        }
        curr_st = {
            "floor": 1,
            "coord": [0, 0],
            "p1": {"x": 120.0, "y": 240.0, "air_z": 20.0, "hero_id": "isaac"},
            "p2": {"x": 340.0, "y": 420.0, "air_z": 0.0, "hero_id": "cain"},
            "enemies": [[120.0, 110.0, 14.0, 8, 10, "gaper", 2.0]],
            "bosses": [[540.0, 320.0, 32.0, 90, 100, "BOSS", "monstro", "angry", 1.0]],
            "tears": [[240.0, 200.0, 6.0]],
            "eproj": [[360.0, 300.0, 6.0]],
        }
        mid = interpolate_lan_snapshot(prev_st, curr_st, 0.5)
        self.assertAlmostEqual(mid["p1"]["x"], 110.0, places=3)
        self.assertAlmostEqual(mid["p1"]["y"], 220.0, places=3)
        self.assertAlmostEqual(mid["p1"]["air_z"], 10.0, places=3)
        self.assertAlmostEqual(mid["p2"]["x"], 320.0, places=3)
        self.assertAlmostEqual(mid["enemies"][0][0], 110.0, places=3)
        self.assertAlmostEqual(mid["bosses"][0][0], 520.0, places=3)
        self.assertAlmostEqual(mid["tears"][0][0], 220.0, places=3)

        # Room change snaps immediately without lerping across rooms
        next_room = dict(curr_st, coord=[1, 0])
        snapped = interpolate_lan_snapshot(prev_st, next_room, 0.5)
        self.assertEqual(snapped["p1"]["x"], 120.0)

    def test_udp_discovery_finds_running_host(self):
        host = LanHost()
        try:
            ok, _ = host.start(
                host_name="AuditHost",
                hero_id="isaac",
                game_mode="classic",
                port=26120,
                discovery_port=26121,
            )
            self.assertTrue(ok)
            found = scan_lan_servers(timeout=0.45, discovery_port=26121)
            matched = [s for s in found if s["port"] == host.port and s["host_name"] == "AuditHost"]
            self.assertTrue(len(matched) >= 1, f"Expected to discover AuditHost, got {found}")
        finally:
            host.stop()

    def test_tcp_handshake_hero_sync_ping_and_reliable_actions(self):
        host = LanHost()
        client = LanClient()
        try:
            ok, _ = host.start(
                host_name="TestHost",
                hero_id="isaac",
                game_mode="classic",
                port=26140,
                discovery_port=26141,
            )
            self.assertTrue(ok)
            ok_c, _ = client.connect("127.0.0.1", host.port, name="RunnerP2", hero_id="cain")
            self.assertTrue(ok_c)

            self.assertTrue(_wait_until(lambda: host.client_connected and host.client_name == "RunnerP2"))
            self.assertEqual(host.client_hero_id, "cain")
            self.assertTrue(_wait_until(lambda: client.host_name == "TestHost"))

            # Live hero switch from client -> host
            client.send_hero("azazel")
            self.assertTrue(_wait_until(lambda: host.client_hero_id == "azazel"))

            # Live lobby metadata update from host -> client
            host.update_lobby_meta(host_hero_id="judas", game_mode="hard", in_run=False)
            self.assertTrue(_wait_until(lambda: client.host_hero_id == "judas" and client.game_mode == "hard"))

            # Reliable one-shot actions must not be dropped even during burst of continuous inputs
            client.send_input(1.0, 0.0, 0.0, -1.0, dash=True, jump=True, melee=True, cycle_relic=True, confirm=True)
            for _ in range(8):
                client.send_input(0.5, 0.5, 1.0, 0.0, dash=False)

            got = {}
            def _collect():
                inp = host.consume_client_input()
                if inp:
                    for k, v in inp.items():
                        if v:
                            got[k] = v
                return all(got.get(k) for k in ("jump", "melee", "cycle_relic", "confirm"))

            self.assertTrue(_wait_until(_collect, timeout=1.5), f"Missing reliable actions: {got}")
            self.assertGreaterEqual(client.ping_ms, 0)
        finally:
            client.stop()
            host.stop()

    def test_headless_game_host_client_snapshot_and_pickup_confirm(self):
        tests_dir = os.path.dirname(os.path.abspath(__file__))
        if tests_dir not in sys.path:
            sys.path.insert(0, tests_dir)
        import test_stability

        test_stability._install_pygame_stub()
        import pygame
        for ch_i in range(ord("a"), ord("z") + 1):
            kn = f"K_{chr(ch_i)}"
            if not hasattr(pygame, kn):
                setattr(pygame, kn, ch_i)
        for kn, val in (
            ("K_KP2", 258), ("K_KP_2", 258), ("K_KP4", 260), ("K_KP_4", 260),
            ("K_KP5", 261), ("K_KP_5", 261), ("K_KP6", 262), ("K_KP_6", 262),
            ("K_KP8", 264), ("K_KP_8", 264), ("K_SLASH", 47), ("K_KP_ENTER", 271),
        ):
            if not hasattr(pygame, kn):
                setattr(pygame, kn, val)
        if not hasattr(pygame.Rect, "center"):
            pygame.Rect.center = property(lambda self: (self.centerx, self.centery))
        if not hasattr(pygame.Surface, "get_bitsize"):
            pygame.Surface.get_bitsize = lambda self: 32
        if not hasattr(pygame.Surface, "scroll"):
            pygame.Surface.scroll = lambda self, dx=0, dy=0: None
        if not hasattr(pygame.key, "start_text_input"):
            pygame.key.start_text_input = lambda: None
        if not hasattr(pygame.key, "stop_text_input"):
            pygame.key.stop_text_input = lambda: None
        pygame.transform.scale = lambda s, sz, dest=None: dest if dest is not None else pygame.Surface(sz)
        pygame.transform.smoothscale = lambda s, sz, dest=None: dest if dest is not None else pygame.Surface(sz)

        from items import ItemPedestal, get_item_by_id
        from main import Game

        host_game = Game()
        client_game = Game()
        try:
            ok, _ = host_game.lan_host.start(
                host_name="HostP1",
                hero_id="isaac",
                game_mode="classic",
                port=26160,
                discovery_port=26161,
            )
            self.assertTrue(ok)
            ok_c, _ = client_game.lan_client.connect("127.0.0.1", host_game.lan_host.port, name="ClientP2", hero_id="magdalene")
            self.assertTrue(ok_c)
            self.assertTrue(_wait_until(lambda: host_game.lan_host.client_connected))

            host_game.start_new_run()
            self.assertIsNotNone(host_game.player2)
            self.assertEqual(host_game.player2.hero_id, "magdalene")

            # Open a pedestal pickup confirmation prompt for P2 on host
            it = get_item_by_id("sad_onion") or get_item_by_id("pentagram")
            self.assertIsNotNone(it)
            ped = ItemPedestal(host_game.player2.x, host_game.player2.y, it)
            host_game.current_room.pedestals.append(ped)
            host_game._open_pedestal_prompt(ped, host_game.player2)
            host_game._push_lan_snapshot()

            # Wait for client to receive snapshot with pickup_prompt and player velocity/combo fields
            self.assertTrue(_wait_until(lambda: (client_game.lan_client.get_latest_state() or {}).get("pickup_prompt") is not None))
            st = client_game.lan_client.get_latest_state()
            self.assertIn("vx", st["p1"])
            self.assertIn("melee_combo", st["p2"])
            self.assertIsNotNone(st.get("pickup_prompt"))
            self.assertEqual(st["pickup_prompt"]["item_id"], it["id"])

            # Client renders LAN frame with modal & sends confirm back to host
            client_game.state = "LAN_CLIENT"
            client_game._lan_client_actions["confirm"] = True
            client_game._update_lan_client(1.0)
            client_game._draw_lan_client()

            # Host ticks _update_playing while prompt is open and applies P2's LAN confirm
            self.assertTrue(
                _wait_until(
                    lambda: (host_game._update_playing(1.0) or True) and host_game.pending_pedestal_prompt is None,
                    timeout=1.5,
                ),
                "Host should resolve pedestal confirmation from LAN client",
            )
            self.assertFalse(ped.alive)

            # Give P2 multiple items & a computer terminal in the current room to test host<->client parity
            from room import Machine
            it2 = get_item_by_id("pentagram")
            it3 = get_item_by_id("brimstone")
            for extra_it in (it2, it3):
                if extra_it:
                    host_game.player2.apply_item(extra_it, silent=True)
            host_game.player2.selected_inv_idx = 0

            comp = Machine(host_game.player2.x + 22, host_game.player2.y, "computer_terminal", track_idx=0, playing=True)
            host_game.current_room.machines.append(comp)
            host_game.ui.show_banner("RELIC", "Test Sub", duration=60.0, item=it)
            host_game._push_lan_snapshot()

            self.assertTrue(
                _wait_until(
                    lambda: (
                        (client_game.lan_client.get_latest_state() or {}).get("banner_seq", 0) > 0
                        and len((client_game.lan_client.get_latest_state() or {}).get("p2", {}).get("pas_ids", [])) >= 2
                        and any(m[2] == "computer_terminal" for m in (client_game.lan_client.get_latest_state() or {}).get("machines", []))
                    ),
                    timeout=1.5,
                ),
                "Snapshot should carry synced banner_seq, quests, pas_ids, and computer_terminal machine state",
            )
            st2 = client_game.lan_client.get_latest_state()
            self.assertIn("quests", st2)
            self.assertIn("pas_ids", st2["p2"])
            self.assertIn("act_items", st2["p2"])
            self.assertIn("dmg", st2["p2"])
            self.assertIn("luck", st2["p2"])

            # Verify dt-based LAN animation advances smoothly on client (1x rate, not ~35x fast)
            client_game._lan_anim.clear()
            client_game.player = None
            st2["p2"]["vx"] = 3.0
            client_game._update_lan_client(1.0)
            walk_t1 = client_game._lan_anim["player_P2"]["walk"]
            client_game._update_lan_client(1.0)
            walk_t2 = client_game._lan_anim["player_P2"]["walk"]
            self.assertAlmostEqual(walk_t2 - walk_t1, 0.26, places=3)

            # Populate an enemy, boss, tear, and projectile to verify 4x sprite parity render on client
            from bosses import spawn_boss_for_room
            from bullet import EnemyProjectile, Tear
            from enemy import create_enemy
            host_game.current_room.enemies.append(create_enemy("gaper", 360, 260, 1))
            host_game.current_room.bosses.extend(spawn_boss_for_room(host_game.current_room, "monstro", 540, 260, floor_level=1))
            host_game.tears.append(Tear(300, 300, 4.0, 0.0, homing=True))
            host_game.enemy_projectiles.append(EnemyProjectile(420, 300, -3.0, 0.0))
            host_game._push_lan_snapshot()
            self.assertTrue(_wait_until(lambda: len((client_game.lan_client.get_latest_state() or {}).get("enemies", [])) >= 1, timeout=1.5))

            # Client renders full host-parity frame + quest log modal cleanly
            client_game.quest_manager.log_open = True
            client_game._draw_lan_client()
            client_game.quest_manager.log_open = False

            # Reliable HUD slot & computer terminal interact round-trip from LAN Client -> Host
            client_game.lan_client.send_action("", inv_slot=2)
            client_game._lan_client_actions["interact"] = True
            client_game._update_lan_client(1.0)

            self.assertTrue(
                _wait_until(
                    lambda: (host_game._update_playing(1.0) or True) and comp.track_idx == 1 and host_game.player2.selected_inv_idx == 1,
                    timeout=1.5,
                ),
                f"Expected track_idx=1 & selected_inv_idx=1, got track={comp.track_idx}, inv={host_game.player2.selected_inv_idx}",
            )
        finally:
            client_game.lan_client.stop()
            host_game.lan_host.stop()

    def test_dict_entity_interpolation_matches_ids(self):
        from lan_coop import interpolate_lan_snapshot

        prev_st = {
            "floor": 1,
            "coord": [0, 0],
            "enemies": [
                {"id": 10, "x": 100.0, "y": 100.0, "type": "gaper"},
                {"id": 20, "x": 300.0, "y": 300.0, "type": "hopper", "air_z": 0.0},
            ],
            "bosses": [
                {"id": 99, "x": 400.0, "y": 200.0, "key": "monstro", "air_z": 20.0},
            ],
        }
        # Enemy 10 died, only Enemy 20 remained (shifted index 1 -> 0) + Enemy 30 spawned
        curr_st = {
            "floor": 1,
            "coord": [0, 0],
            "enemies": [
                {"id": 20, "x": 340.0, "y": 320.0, "type": "hopper", "air_z": 10.0},
                {"id": 30, "x": 500.0, "y": 500.0, "type": "fly"},
            ],
            "bosses": [
                {"id": 99, "x": 420.0, "y": 240.0, "key": "monstro", "air_z": 0.0},
            ],
        }
        mid = interpolate_lan_snapshot(prev_st, curr_st, 0.5)
        self.assertAlmostEqual(mid["enemies"][0]["x"], 320.0, places=3)
        self.assertAlmostEqual(mid["enemies"][0]["air_z"], 5.0, places=3)
        self.assertEqual(mid["enemies"][1]["x"], 500.0)
        self.assertAlmostEqual(mid["bosses"][0]["air_z"], 10.0, places=3)

    def test_computer_terminal_rooms_tracks_and_spatial_audio(self):
        tests_dir = os.path.dirname(os.path.abspath(__file__))
        if tests_dir not in sys.path:
            sys.path.insert(0, tests_dir)
        import test_stability

        test_stability._install_pygame_stub()
        from room import Machine, Room
        from sound import COMPUTER_TRACKS, SoundBank

        self.assertEqual(len(COMPUTER_TRACKS), 4)
        for rtype in ("start", "arcade", "library"):
            rm = Room((0, 0), rtype, floor_level=1, layout_key="empty", build_contents=True)
            comps = [m for m in rm.machines if m.kind == "computer_terminal"]
            self.assertGreaterEqual(len(comps), 1, f"Room type {rtype!r} must contain a computer_terminal")
            self.assertTrue(comps[0].playing)
            self.assertIsNotNone(comps[0].get_light_source())

        # Cycle through all 4 tracks -> OFF -> back to Track 0
        m = Machine(200, 200, "computer_terminal", track_idx=0, playing=True)
        for expected in (1, 2, 3):
            m.cooldown = 0.0
            self.assertTrue(m.cycle_track())
            self.assertTrue(m.playing)
            self.assertEqual(m.track_idx, expected)
        m.cooldown = 0.0
        m.cycle_track()
        self.assertFalse(m.playing)
        self.assertIsNone(m.get_light_source())
        m.cooldown = 0.0
        m.cycle_track()
        self.assertTrue(m.playing)
        self.assertEqual(m.track_idx, 0)

        # Spatial attenuation & left/right panning verification
        sb = SoundBank.__new__(SoundBank)
        g_near, l_near, r_near = sb.compute_spatial_mix(300, 300, 300, 300)
        g_far, l_far, r_far = sb.compute_spatial_mix(300, 300, 300 + 450, 300)
        g_out, l_out, r_out = sb.compute_spatial_mix(300, 300, 1200, 300)
        self.assertGreater(g_near, g_far)
        self.assertAlmostEqual(l_near, r_near, places=3)
        self.assertEqual(g_out, 0.0)
        # Computer to the right of listener -> right louder than left
        _, l_right, r_right = sb.compute_spatial_mix(500, 300, 300, 300)
        self.assertGreater(r_right, l_right)
        # Computer to the left of listener -> left louder than right
        _, l_left, r_left = sb.compute_spatial_mix(100, 300, 300, 300)
        self.assertGreater(l_left, r_left)

    def test_alpha_version_chronicle_and_calm_recovery_strings(self):
        tests_dir = os.path.dirname(os.path.abspath(__file__))
        if tests_dir not in sys.path:
            sys.path.insert(0, tests_dir)
        import test_stability

        test_stability._install_pygame_stub()
        from codex import CHRONICLE_CHAPTERS
        from i18n import TEXTS
        from settings import GAME_VERSION, TITLE

        self.assertEqual(GAME_VERSION, "Alpha 1.0")
        self.assertIn("Alpha 1.0", TITLE)
        self.assertEqual(len(CHRONICLE_CHAPTERS), 12)
        for ch in CHRONICLE_CHAPTERS:
            self.assertTrue(len(ch.get("title", "")) >= 6)
            self.assertTrue(len(ch.get("title_en", "")) >= 6)
            self.assertTrue(len(ch.get("body", "")) >= 80)
            self.assertTrue(len(ch.get("body_en", "")) >= 80)

        for lang in ("ru", "en"):
            rec = TEXTS[lang]["recovery_notice"]
            self.assertTrue(len(rec) > 5)
            self.assertNotIn("Traceback", rec)
            self.assertNotIn("Exception", rec)
            self.assertNotIn("ERROR", rec)


if __name__ == "__main__":
    unittest.main()
