import atexit
import json
import math
import os
import random
import signal
import sys
import threading
import time
import traceback

os.environ.setdefault("SDL_HINT_RENDER_SCALE_QUALITY", "1")
os.environ.setdefault("SDL_HINT_ANDROID_TRAP_BACK_BUTTON", "1")
os.environ.setdefault("SDL_VIDEO_ALLOW_SCREENSAVER", "1")
os.environ.setdefault("SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS", "0")
if sys.platform.startswith("linux"):
    os.environ.setdefault("SDL_APP_NAME", "DarkVault")
    os.environ.setdefault("SDL_VIDEO_X11_WMCLASS", "DarkVault")
    os.environ.setdefault("SDL_VIDEO_WAYLAND_WMCLASS", "DarkVault")

import pygame
from accounts import AccountManager, DAILY_REWARD_TABLE, EMBLEM_NAMES_EN, EMBLEM_NAMES_RU
from achievements import ACHIEVEMENT_CATEGORIES, ACHIEVEMENT_DEFS, AchievementManager, TIER_LUM
from bosses import PLAYABLE_BOSS_KEYS, draw_boss_visual, pick_floor_boss_key, spawn_boss_for_room
from bullet import EnemyProjectile, LightningArcParticle, RingParticle, SplashParticle, Tear
from codex import ChronicleScreen, CodexScreen, HERO_EXTRA_EN
from console import DevConsole, RoomEditor
from cutscene import BossCutscene, draw_hero_portrait
from dungeon import DungeonGenerator, MAX_ARTIFACTS_PER_FLOOR, spawn_devil_deal_room
from enemy import REGULAR_ENEMY_TYPES, create_enemy, draw_enemy_visual
from heroes import HERO_ROSTER, count_unlocked_heroes, get_hero, get_hero_unlock_progress, get_hero_unlock_text, is_hero_unlocked
from i18n import tr, tr_floor, tr_mode, tr_mode_desc, tr_room
from items import ItemPedestal, Pickup, draw_item_icon, get_item_by_id, get_random_item, tr_item_desc, tr_item_name
from lan_coop import DEFAULT_TCP_PORT, LanClient, LanHost, get_local_ip, parse_host_port, scan_lan_servers
from lighting import LightingSystem
from mods import ModBrowserScreen, mod_manager
from quests import QuestManager
from player import Player, draw_network_hero_character
from room import (
    DiceFloor,
    Door,
    Room,
    SacrificeSpike,
    _get_flame_sprite,
    _get_obstacle_sprite,
    _get_portal_sprite,
    draw_computer_screen_fx,
    draw_npc_visual,
    draw_wide_backdrop,
    pick_combat_theme_enemies,
)
from saves import delete_save_slot, is_slot_occupied, list_save_slots, load_run_from_slot, save_run_to_slot
from settings import (
    BASE_WIDTH,
    DEFAULT_KEYBINDS,
    EFFECTS_CHOICES,
    FPS,
    GAME_MODES,
    GAME_SETTINGS,
    GAME_VERSION,
    KEYBIND_ACTIONS,
    PALETTE,
    PLAYABLE_BOTTOM,
    PLAYABLE_LEFT,
    PLAYABLE_RIGHT,
    PLAYABLE_TOP,
    RESOLUTION_CHOICES,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    TARGET_FLOOR_COUNT,
    TITLE,
    TOUCH_LAYOUT_PRESETS,
    UI_SCALE_CHOICES,
    WIDE_MODE_CHOICES,
    append_crash_log,
    apply_safe_boot_settings,
    blit_text_fitted,
    clamp,
    clear_boot_marker,
    clear_render_caches,
    compute_wide_view_width,
    draw_aa_circle,
    draw_aa_ring,
    draw_dynamic_shadow,
    draw_monochrome_shadow,
    ease_in_out,
    fit_text_surf,
    format_key_name,
    get_disc_sprite,
    get_effects_config,
    get_glow_surf,
    get_keybind,
    get_native_display_size,
    get_panel_surf,
    get_particle_surf,
    get_resolution_choice,
    get_shadow_surf,
    get_user_data_dir,
    get_view_width,
    get_world_offset_x,
    gray,
    is_android,
    is_phone_layout,
    mark_boot_start,
    render_text_cached,
    reset_keybinds,
    safe_read_json,
    save_user_settings,
    set_keybind,
    set_view_width,
    was_unclean_boot,
)
from sound import COMPUTER_TRACKS, consume_recent_sfx, play_sound, stop_computer_audio, update_computer_audio, update_music
from touch_controls import TouchControls
from ui import UI

_SHUTDOWN_REQUESTED = False
_SDL_CLEANED_UP = False
_ACTIVE_GAME = None


def _request_shutdown(signum=None, frame=None):
    global _SHUTDOWN_REQUESTED
    _SHUTDOWN_REQUESTED = True


def _install_signal_handlers():
    for sig_name in ("SIGINT", "SIGTERM", "SIGHUP"):
        sig = getattr(signal, sig_name, None)
        if sig is not None:
            try:
                signal.signal(sig, _request_shutdown)
            except (OSError, RuntimeError, ValueError):
                pass


def _cleanup_sdl_resources():
    global _SDL_CLEANED_UP
    if _SDL_CLEANED_UP:
        return
    _SDL_CLEANED_UP = True
    try:
        if _ACTIVE_GAME is not None:
            for attr in ("lan_host", "lan_client"):
                obj = getattr(_ACTIVE_GAME, attr, None)
                if obj is not None:
                    try:
                        obj.stop()
                    except Exception:
                        pass
            save_user_settings()
    except Exception:
        pass
    try:
        if pygame.get_init():
            try:
                pygame.key.stop_text_input()
            except Exception:
                pass
            try:
                pygame.event.set_grab(False)
            except Exception:
                pass
            try:
                if pygame.mixer.get_init():
                    pygame.mixer.stop()
                    pygame.mixer.quit()
            except Exception:
                pass
            try:
                if pygame.font.get_init():
                    pygame.font.quit()
            except Exception:
                pass
            try:
                if pygame.display.get_init():
                    pygame.display.quit()
            except Exception:
                pass
            pygame.quit()
    except Exception:
        pass


def _init_sdl_subsystems():
    """Initialize SDL/Pygame reliably on Linux (Arch/Hyprland Wayland & X11) and other platforms."""
    if sys.platform.startswith("linux") and "SDL_VIDEODRIVER" not in os.environ:
        drivers = []
        if os.environ.get("WAYLAND_DISPLAY"):
            drivers.extend(["wayland", "x11"])
        elif os.environ.get("DISPLAY"):
            drivers.extend(["x11", "wayland"])
        else:
            drivers.extend(["wayland", "x11"])

        initialized = False
        try:
            pygame.display.init()
            initialized = pygame.display.get_init()
        except pygame.error:
            initialized = False

        if not initialized:
            for drv in drivers:
                try:
                    os.environ["SDL_VIDEODRIVER"] = drv
                    pygame.display.quit()
                    pygame.display.init()
                    if pygame.display.get_init():
                        initialized = True
                        break
                except pygame.error:
                    continue
            if not initialized:
                os.environ.pop("SDL_VIDEODRIVER", None)

    try:
        pygame.init()
    except Exception:
        # On Linux, PipeWire/PulseAudio/ALSA failure during pygame.init can abort startup;
        # fall back to dummy audio while keeping video/input intact.
        if sys.platform.startswith("linux"):
            os.environ["SDL_AUDIODRIVER"] = "dummy"
            try:
                pygame.mixer.quit()
            except Exception:
                pass
            try:
                pygame.init()
            except Exception:
                pass
        if not pygame.display.get_init():
            pygame.display.init()
    try:
        if not pygame.font.get_init():
            pygame.font.init()
    except Exception:
        pass


def _load_shared_seeds():
    base_res = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    local_dir = os.path.dirname(os.path.abspath(__file__))
    for cand in (
        os.path.join(get_user_data_dir(), "shared_seeds.json"),
        os.path.join(base_res, "shared_seeds.json"),
        os.path.join(local_dir, "shared_seeds.json"),
    ):
        data = safe_read_json(cand, default=None, expected_type=list, try_backups=True, self_heal=False)
        if isinstance(data, list) and data:
            return data
    return [
        {
            "id": "vault_genesis",
            "seed": "DV-GENESIS-001",
            "title_ru": "Серия #001 · Первый разлом",
            "title_en": "Seed #001 · First Breach",
            "desc_ru": "Сбалансированный сид с единой картой.",
            "desc_en": "Balanced deterministic run.",
        }
    ]


EERIE_WAVE_POOL = [
    "shadow_weaver",
    "whispering_phantom",
    "mimic_double",
    "many_eyed_watcher",
    "ash_stalker",
    "hollow_bell",
    "thread_serpent",
]


class _MappedEvent:
    def __init__(self, event, mapped_pos):
        self._event = event
        self.type = event.type
        self.pos = mapped_pos

    def __getattr__(self, name):
        return getattr(self._event, name)


class ActiveBomb:
    def __init__(self, x, y, sad_bombs=False, owner=None):
        self.x = float(x)
        self.y = float(y)
        self.timer = 90.0
        self.alive = True
        self.sad_bombs = bool(sad_bombs)
        self.owner = owner

    def update(self, dt=1.0):
        self.timer -= dt
        if self.timer <= 0:
            self.alive = False

    def draw(self, screen):
        if not self.alive:
            return
        sh = get_shadow_surf(26, 10, 105)
        screen.blit(sh, (int(self.x - sh.get_width() // 2), int(self.y + 8)))
        pulse = 1.0 if int(self.timer) % 8 < 4 else 0.65
        lum = int(244 * pulse)
        draw_aa_circle(screen, (16, 16, 16), self.x, self.y, 12)
        draw_aa_circle(screen, (lum, lum, lum), self.x, self.y, 9)
        draw_aa_circle(screen, (250, 250, 250), self.x + 6, self.y - 9, 3)


class _ClientPlayerProxy:
    """Lightweight player adapter allowing UI.draw_hud to render complete HUD for LAN clients."""

    def __init__(self, pdata):
        d = pdata or {}
        self.x = float(d.get("x", 0.0))
        self.y = float(d.get("y", 0.0))
        self.hero_id = str(d.get("hero_id", "isaac"))
        self.hero = get_hero(self.hero_id)
        self.facing = (float(d.get("fx", 0.0)), float(d.get("fy", 1.0)))
        self.hp = int(d.get("hp", 0))
        self.max_hp = int(d.get("max_hp", 0))
        self.soul_hp = int(d.get("soul_hp", 0))
        self.black_hp = int(d.get("black_hp", 0))
        self.coins = int(d.get("coins", 0))
        self.bombs = int(d.get("bombs", 0))
        self.keys = int(d.get("keys", 0))
        self.kills = int(d.get("kills", 0))
        self.luck = float(d.get("luck", 0))
        self._dmg = float(d.get("dmg", self.hero.get("damage", 3.5)))
        self._spd = float(d.get("spd", self.hero.get("speed", 3.5)))
        self.holy_mantle = bool(d.get("holy_mantle", False))
        self.mantle_broken_room = bool(d.get("mantle_broken", False))
        self.lantern_fuel = float(d.get("lantern_fuel", 1.0))
        self.lantern_bonus = float(d.get("lantern_bonus", 1.0))
        self.has_steam_sale = bool(d.get("has_steam_sale", False))
        self.compass_reveal = bool(d.get("compass_reveal", False))
        self.noclip = bool(d.get("noclip", False))
        self.dash_cd = float(d.get("dash_cd", 0.0))
        self.dash_max_cd = float(d.get("dash_max_cd", 95.0))
        self.jump_cd = float(d.get("jump_cd", 0.0))
        self.jump_max_cd = float(d.get("jump_max_cd", 120.0))
        self.invis_timer = float(d.get("invis_timer", 0.0))
        self.invis_cd = float(d.get("invis_cd", 0.0))
        self.invis_max_cd = float(d.get("invis_max_cd", 360.0))
        self.melee_cd = float(d.get("melee_cd", 0.0))
        self.melee_max_cd = float(d.get("melee_max_cd", 22.0))
        self.melee_combo_step = int(d.get("melee_combo", 0))
        self.melee_combo_timer = float(d.get("melee_combo_timer", 0.0))
        self.active_effects = dict(d.get("effects", {}) or {})

        self.active_items = []
        for slot in d.get("act_items", ()):
            if isinstance(slot, dict) and slot.get("id"):
                it = get_item_by_id(slot["id"])
                if it is not None:
                    self.active_items.append(
                        {
                            "item": it,
                            "charge": int(slot.get("c", 0)),
                            "max_charge": int(slot.get("m", it.get("max_charge", 1))),
                        }
                    )
        self.active_slot = int(d.get("act_slot", 0))
        if self.active_items:
            self.active_slot = max(0, min(self.active_slot, len(self.active_items) - 1))
            self.active_item = self.active_items[self.active_slot]["item"]
            self.active_charge = int(self.active_items[self.active_slot]["charge"])
            self.max_charge = int(self.active_items[self.active_slot]["max_charge"])
        else:
            self.active_slot = 0
            self.active_item = None
            self.active_charge = int(d.get("charge", 0))
            self.max_charge = int(d.get("max_charge", 1))

        self.collected_items = []
        for iid in d.get("pas_ids", ()):
            it = get_item_by_id(iid)
            if it is not None:
                self.collected_items.append(it)

        self.inventory_page = int(d.get("inv_page", 0))
        self.selected_inv_idx = int(d.get("sel_inv", 0))

    def is_dead(self):
        return (self.hp + self.soul_hp + self.black_hp) <= 0

    def is_active_ready(self):
        return self.active_item is not None and (self.max_charge <= 0 or self.active_charge >= self.max_charge)

    def get_effective_damage(self):
        return self._dmg

    def get_effective_speed(self):
        return self._spd

    def get_inventory_entries(self):
        entries = []
        for idx, slot in enumerate(self.active_items):
            entries.append(("active", idx, slot["item"], slot["charge"], slot["max_charge"]))
        for idx, it in enumerate(self.collected_items):
            entries.append(("passive", idx, it, 0, 0))
        return entries

    def get_inventory_page_count(self):
        return max(1, (len(self.get_inventory_entries()) + 8) // 9)

    def get_inventory_page_entries(self):
        entries = self.get_inventory_entries()
        pc = self.get_inventory_page_count()
        self.inventory_page = int(clamp(self.inventory_page, 0, pc - 1))
        start = self.inventory_page * 9
        return entries[start:start + 9], start

    def get_selected_inventory_entry(self):
        entries = self.get_inventory_entries()
        if not entries:
            return None
        if 0 <= self.selected_inv_idx < len(entries):
            return entries[self.selected_inv_idx]
        if self.active_items:
            idx = max(0, min(self.active_slot, len(self.active_items) - 1))
            return entries[idx]
        return entries[-1]


class TitlePreviewSimulator:
    SCENES = ["combat", "treasure", "shop", "arcade", "sacrifice", "boss"]

    def __init__(self):
        self.scene_idx = 0
        self.timer = 0.0
        self.fade_alpha = 170.0
        self.room = None
        self.demo_player = None
        self.projectiles = []
        self.tears = []
        self.particles = []
        self._skip_acc = 0.0
        self._cached_surf = None
        self._cached_vw = 0
        self._fade_surf = None
        self._fade_vw = 0
        self._render_tick = 0
        self._dirty = True
        self.load_scene(0)

    def load_scene(self, idx):
        self.scene_idx = idx % len(self.SCENES)
        self.timer = 0.0
        self.fade_alpha = 180.0
        self.projectiles.clear()
        self.tears.clear()
        self.particles.clear()
        self._dirty = True
        sc = self.SCENES[self.scene_idx]
        cx = (PLAYABLE_LEFT + PLAYABLE_RIGHT) // 2
        cy = (PLAYABLE_TOP + PLAYABLE_BOTTOM) // 2

        if sc == "combat":
            self.room = Room((0, 0), room_type="normal", floor_level=1, layout_key="pillars_4")
            self.room.enemies = [
                create_enemy("shadow_weaver", cx - 190, cy - 85, 1),
                create_enemy("many_eyed_watcher", cx + 195, cy + 80, 1),
                create_enemy("shadow_weaver", cx + 145, cy - 95, 1),
            ]
        elif sc == "treasure":
            self.room = Room((0, 0), room_type="treasure", floor_level=1, layout_key="empty", game_mode="free_roam")
        elif sc == "shop":
            self.room = Room((0, 0), room_type="shop", floor_level=1, layout_key="empty")
        elif sc == "arcade":
            self.room = Room((0, 0), room_type="arcade", floor_level=2, layout_key="empty")
        elif sc == "sacrifice":
            self.room = Room((0, 0), room_type="sacrifice", floor_level=2, layout_key="empty")
        else:
            self.room = Room((0, 0), room_type="boss", floor_level=3, layout_key="empty")
            self.room.bosses = spawn_boss_for_room(self.room, "eclipse_warden", cx + 135, cy - 25, 1)

        self.demo_player = Player(cx - 125, cy + 45, "isaac")
        self.demo_player.invuln_timer = 9999.0
        self.demo_player.preview_mode = True

    def update(self, dt=1.0, low_power=False):
        self.timer += dt
        if self.fade_alpha > 0.0:
            self.fade_alpha = max(0.0, self.fade_alpha - 10.0 * dt)
        if self.timer >= 540.0:
            self.load_scene((self.scene_idx + 1) % len(self.SCENES))
            return

        if low_power:
            self._skip_acc += dt
            if self._skip_acc < 2.0:
                return
            step_dt = min(2.6, self._skip_acc)
            self._skip_acc = 0.0
            self._dirty = True
        else:
            step_dt = dt
            self._dirty = True

        cx = (PLAYABLE_LEFT + PLAYABLE_RIGHT) * 0.5
        cy = (PLAYABLE_TOP + PLAYABLE_BOTTOM) * 0.5
        t = self.timer * 0.032

        # Smooth kiting figure-eight kept safely inside walls and away from obstacles
        target_x = cx + math.cos(t) * 210.0
        target_y = cy + math.sin(t * 1.45) * 105.0
        dx = target_x - self.demo_player.x
        dy = target_y - self.demo_player.y
        dist = math.hypot(dx, dy)
        mx = dx / dist if dist > 6.0 else 0.0
        my = dy / dist if dist > 6.0 else 0.0

        # Soft obstacle / threat avoidance so the preview hero does not get stuck
        for obs in self.room.obstacles:
            if obs.alive:
                ox, oy = obs.rect.center
                odx = self.demo_player.x - ox
                ody = self.demo_player.y - oy
                od = math.hypot(odx, ody)
                if 1.0 < od < 56.0:
                    w = (56.0 - od) / 56.0
                    mx += (odx / od) * w * 1.4
                    my += (ody / od) * w * 1.4

        mlen = math.hypot(mx, my)
        if mlen > 1.0:
            mx /= mlen
            my /= mlen

        self.demo_player.invuln_timer = 120.0
        self.demo_player.update(mx, my, self.room, self.particles, step_dt)

        # Shoot toward nearest live foe or in a slow expressive orbit
        targets = [e for e in self.room.enemies if getattr(e, "alive", True)] + [
            b for b in self.room.bosses if getattr(b, "alive", True)
        ]
        if targets:
            nearest = min(targets, key=lambda ent: math.hypot(ent.x - self.demo_player.x, ent.y - self.demo_player.y))
            adx = nearest.x - self.demo_player.x
            ady = nearest.y - self.demo_player.y
            alen = max(1.0, math.hypot(adx, ady))
            if self.demo_player.shoot_cd <= 0:
                self.demo_player.shoot(adx / alen, ady / alen, self.tears)
        elif int(self.timer) % 28 == 0:
            self.demo_player.shoot(math.cos(t + 0.6), math.sin(t + 0.6), self.tears)

        for e in self.room.enemies:
            e.update(self.demo_player, self.room, self.projectiles, step_dt)
            e.hp = e.max_hp
        for b in self.room.bosses:
            b.update(self.demo_player, self.room, self.projectiles, self.room.enemies, step_dt)
            b.hp = b.max_hp

        for tr_obj in self.tears:
            tr_obj.update(self.room, self.room.enemies + self.room.bosses, step_dt, (self.demo_player.x, self.demo_player.y))
        self.tears = [x for x in self.tears if x.alive][-(32 if low_power else 70):]

        for pr in self.projectiles:
            pr.update(self.room, step_dt, (self.demo_player.x, self.demo_player.y))
        self.projectiles = [x for x in self.projectiles if x.alive][-(32 if low_power else 70):]

        for pt in self.particles:
            pt.update(step_dt)
        eff_q = GAME_SETTINGS.get("effects_quality", "high")
        max_pt = 18 if low_power else (45 if eff_q == "low" else (85 if eff_q == "medium" else 130))
        self.particles = [x for x in self.particles if x.alive][-max_pt:]
        self.room.update(step_dt)

    def draw(self, screen, lighting=None, font=None, world_surf=None, low_power=False, menu_dimmed=False):
        vw = get_view_width()
        use_cache = bool(low_power or menu_dimmed)
        fast_preview = bool(low_power or menu_dimmed)
        self._render_tick = (self._render_tick + 1) % 1000000
        if use_cache:
            if self._cached_surf is None or self._cached_vw != vw:
                self._cached_surf = pygame.Surface((vw, SCREEN_HEIGHT))
                if pygame.display.get_init() and pygame.display.get_surface() is not None:
                    try:
                        self._cached_surf = self._cached_surf.convert()
                    except Exception:
                        pass
                self._cached_vw = vw
                self._dirty = True
            if low_power:
                should_render = bool(self._dirty)
            else:
                should_render = bool(self._dirty or self.fade_alpha > 1.0 or (self._render_tick % 2 == 1))
            if not should_render:
                screen.blit(self._cached_surf, (0, 0))
                return
            self._dirty = False
            draw_dst = self._cached_surf
        else:
            draw_dst = screen

        world_ox = get_world_offset_x()
        use_buf = world_ox > 0 and world_surf is not None
        target = world_surf if use_buf else draw_dst
        light_srcs = None if fast_preview else (self.room.get_dynamic_light_sources([self.demo_player]) if hasattr(self.room, "get_dynamic_light_sources") else None)

        self.room.draw(target, self.timer, light_sources=light_srcs)
        for p in self.room.pickups:
            p.draw(target, font=font, discount=False)
        for ped in self.room.pedestals:
            ped.draw(target, font=font, discount=False)
        for e in self.room.enemies:
            e.draw(target, light_sources=light_srcs)
        for b in self.room.bosses:
            b.draw(target, light_sources=light_srcs)
        self.demo_player.draw(target, light_sources=light_srcs)
        for tr_obj in self.tears:
            tr_obj.draw(target)
        for pr in self.projectiles:
            pr.draw(target)
        for pt in self.particles:
            pt.draw(target)

        if lighting is not None:
            extras = []
            if not fast_preview:
                for ent in self.room.enemies + self.room.bosses + self.room.monoliths + self.room.mystical_npcs:
                    if hasattr(ent, "get_light_source"):
                        ls = ent.get_light_source()
                        if ls is not None:
                            extras.append(ls)
            lighting.render(
                target,
                self.demo_player.x,
                self.demo_player.y,
                self.room,
                time_acc=self.timer,
                lantern_fuel=1.08,
                aim_dir=self.demo_player.facing,
                extra_lights=extras,
                preview_mode=fast_preview,
            )

        if use_buf:
            draw_dst.fill((6, 6, 6))
            draw_wide_backdrop(draw_dst, vw, world_ox, self.room.theme, extra_pad=32)
            draw_dst.blit(target, (world_ox, 0))

        if self.fade_alpha > 1.0:
            if self._fade_surf is None or self._fade_vw != vw:
                self._fade_surf = pygame.Surface((vw, SCREEN_HEIGHT))
                if pygame.display.get_init() and pygame.display.get_surface() is not None:
                    try:
                        self._fade_surf = self._fade_surf.convert()
                    except Exception:
                        pass
                self._fade_surf.fill((6, 6, 6))
                self._fade_vw = vw
            self._fade_surf.set_alpha(int(clamp(self.fade_alpha, 0, 255)))
            draw_dst.blit(self._fade_surf, (0, 0))

        if use_cache:
            screen.blit(self._cached_surf, (0, 0))


class Game:
    def __init__(self):
        global _ACTIVE_GAME
        _ACTIVE_GAME = self
        if sys.platform == "win32":
            try:
                import ctypes

                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("DarkVault.Game.1")
            except Exception:
                pass
        else:
            os.environ.setdefault("SDL_VIDEO_X11_WMCLASS", "DarkVault")
            os.environ.setdefault("SDL_VIDEO_WAYLAND_WMCLASS", "DarkVault")

        _init_sdl_subsystems()
        pygame.display.set_caption(TITLE)
        try:
            icon = None
            base_res = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
            for cand in (
                os.path.join(base_res, "darkvault.png"),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "darkvault.png"),
            ):
                if os.path.exists(cand):
                    icon = pygame.image.load(cand)
                    break
            if icon is None:
                icon = pygame.Surface((64, 64), pygame.SRCALPHA)
                icon.fill((12, 12, 12, 255))
                pygame.draw.rect(icon, (230, 230, 230), (2, 2, 60, 60), 3, border_radius=8)
                pygame.draw.circle(icon, (242, 242, 242), (32, 23), 10)
                pygame.draw.polygon(icon, (242, 242, 242), [(26, 30), (38, 30), (42, 52), (22, 52)])
                pygame.draw.circle(icon, (14, 14, 14), (32, 23), 4)
                pygame.draw.polygon(icon, (14, 14, 14), [(30, 28), (34, 28), (36, 47), (28, 47)])
            pygame.display.set_icon(icon)
        except Exception:
            pass
        self.display_surf = None
        self.screen = None
        self._menu_dim = None
        self._present_rect = pygame.Rect(0, 0, BASE_WIDTH, SCREEN_HEIGHT)
        self._present_display_size = (0, 0)
        self._present_buf = None
        self._present_scale_buf = None
        self._scaled_mode = False
        self._finger_events_seen = False
        self.app_in_background = False
        start_fs = bool(GAME_SETTINGS.get("fullscreen", False)) or is_android()
        self._apply_display_mode(start_fs, persist=False)
        self._sync_view_size(
            *(self.display_surf.get_size() if self.display_surf is not None else (get_view_width(), SCREEN_HEIGHT))
        )

        self.clock = pygame.time.Clock()
        self.ui = UI()
        self._loading_art_surf = None
        self._loading_art_w = 0
        self._render_loading(0.14, "loading_init")

        self.touch = TouchControls()
        self.ui.sync_font_scale(is_phone_layout(self.touch.is_active()))
        self.lighting = LightingSystem(BASE_WIDTH, SCREEN_HEIGHT)
        self._render_loading(0.32, "loading_mods")
        mod_manager.reload_all()
        self.account_manager = AccountManager()
        self.achievement_manager = AchievementManager(self.account_manager)
        self._render_loading(0.56, "loading_mods")
        self.codex = CodexScreen()
        self.chronicle = ChronicleScreen()
        self.mod_browser = ModBrowserScreen()
        self._render_loading(0.78, "loading_world")
        self.preview = TitlePreviewSimulator()
        self.console = DevConsole()
        self.editor = RoomEditor()
        self.quest_manager = QuestManager()
        self.shared_seeds = _load_shared_seeds()
        self._render_loading(1.0, "loading_init")

        self.state = "MENU"
        self.prev_state = "MENU"
        self.touch_edit_return_state = "SETTINGS"
        self.tutorial_return_state = "MENU"
        self.selected_hero_idx = 0
        saved_p2_id = str(GAME_SETTINGS.get("p2_hero_id", "magdalene"))
        p2_idx = next((i for i, h in enumerate(HERO_ROSTER) if h["id"] == saved_p2_id), 1 if len(HERO_ROSTER) > 1 else 0)
        self.selected_p2_hero_idx = p2_idx
        self.coop_enabled = False if is_android() else bool(GAME_SETTINGS.get("coop_enabled", False))
        self.selected_mode_idx = 0
        self.selected_seed_idx = 0
        self.custom_seed = ""
        self.seed_input_active = False
        self.active_seed = None
        self.game_mode = GAME_MODES[0]
        self.menu_idx = 0
        self.pause_idx = 0
        self.settings_idx = 0
        self.saves_idx = 0
        self.saves_feedback = ""
        self.saves_feedback_timer = 0.0
        self.menu_notice = ""
        self.menu_notice_timer = 0.0
        self.hide_menu_ui = False

        self.hover_hero_arrow = 0
        self.hover_p2_hero_arrow = 0
        self.hover_menu_btn = -1
        self.hover_mode_pill = -1
        self.hover_console_btn = False
        self.hover_coop_btn = False
        self.hover_lan_btn = False
        self.hover_p2_btn = False
        self.hover_seed_btn = False
        self.hover_seed_roll_btn = False
        self.hover_daily_btn = False
        self.hover_preview_tab = -1
        self.hover_hide_ui = False
        self.hover_pause_btn = -1
        self.hover_settings_row = -1
        self.hover_tutorial_back = False
        self.hover_ctrl_btn = ""
        self.ctrl_tab = 0 if (is_android() or self.touch.is_active()) else 1
        self.ctrl_rebind_action = None
        self.ctrl_scroll = 0
        self.hover_end_btn = -1
        self.hover_saves_btn = (-1, "")

        self.lan_host = LanHost()
        self.lan_client = LanClient()
        self.lan_ip_input = get_local_ip()
        self.lan_discovered = []
        self.lan_status = ""
        self.lan_hover_btn = ""
        self.lan_net_tick = 0
        self._lan_scanning = False
        self._lan_last_sfx_seq = -1
        self._lan_client_shake = 0.0
        self._lan_client_prev_hp = None
        self._lan_room_cache = {}
        self._lan_anim = {}
        self._lan_banner_seq = 0
        self._banner_seq = 0
        self._last_banner_tracked = None
        self._lan_quests_sig = None
        self._lan_last_room_key = None
        self._lan_client_actions = {
            "jump": False,
            "stealth": False,
            "melee": False,
            "bomb": False,
            "relic": False,
            "cycle_relic": False,
            "confirm": False,
            "cancel": False,
            "interact": False,
        }
        self._error_streak = 0
        self._last_error_ts = 0.0
        self._safe_boot_active = False

        self.draft_options = []
        self.draft_idx = 0
        self.hover_draft_idx = -1

        self.acc_tab = 0
        self.acc_cat_filter = "all"
        self.acc_only_unlocked = False
        self.acc_scroll = 0
        self._acc_touch_drag = None
        self._acc_mouse_drag = None
        self.acc_roster_scroll = 0
        self.acc_sel_idx = 0
        self.acc_backup_idx = 0
        self.acc_input_mode = ""
        self.acc_input_buf = ""
        self.acc_status = ""
        self.acc_status_timer = 0.0
        self.acc_emblem_pick = 0
        self.hover_acc_btn = ""

        self.floor_level = 1
        self.floor_pedestals_spawned = 0
        self.floor_modifier = None
        self.wave_num = 1
        self.boss_rush_wave = 1
        self.wave_break_timer = 0.0
        self.darkness_tick = 0.0
        self.placenta_tick = 0.0
        self.timescale = 1.0
        self.floor_took_damage = False
        self.room_took_damage = False
        self._known_unlocked_heroes = None
        self._known_acc_id = ""
        self.run_recorded = False
        self.rooms = {}
        self.current_coord = (0, 0)
        self.devil_return_coord = (0, 0)
        self.current_room = None
        self.player = None
        self.player2 = None
        self.tears = []
        self.enemy_projectiles = []
        self.bombs = []
        self.particles = []
        self.cutscene = None
        self.boss_for_cutscene = ""
        self.pending_pedestal_prompt = None
        self._dismissed_pedestals = set()

        self.shake_timer = 0.0
        self.shake_power = 0.0
        self.cam_x = 0.0
        self.cam_y = 0.0
        self.fade_alpha = 220.0
        self.time_acc = 0.0
        self.fps_val = 60.0

        self._world_surf = pygame.Surface((BASE_WIDTH, SCREEN_HEIGHT))
        if pygame.display.get_surface() is not None:
            try:
                self._world_surf = self._world_surf.convert()
            except Exception:
                pass

    def _sync_view_size(self, dw=0, dh=0):
        if dw <= 0 or dh <= 0:
            dw, dh = get_native_display_size((BASE_WIDTH, SCREEN_HEIGHT))
        target_vw = compute_wide_view_width(dw, dh)
        set_view_width(target_vw)
        if self.screen is None or self.screen.get_width() != target_vw or self.screen.get_height() != SCREEN_HEIGHT:
            self.screen = pygame.Surface((target_vw, SCREEN_HEIGHT))
            if pygame.display.get_surface() is not None:
                try:
                    self.screen = self.screen.convert()
                except Exception:
                    pass
        if self._menu_dim is None or self._menu_dim.get_width() != target_vw or self._menu_dim.get_height() != SCREEN_HEIGHT:
            self._menu_dim = pygame.Surface((target_vw, SCREEN_HEIGHT), pygame.SRCALPHA)
            self._menu_dim.fill((6, 6, 6, 132))
            if pygame.display.get_surface() is not None:
                try:
                    self._menu_dim = self._menu_dim.convert_alpha()
                except Exception:
                    pass
        if hasattr(self, "touch") and self.touch is not None:
            self.touch._sync_layout()
            if hasattr(self, "ui") and self.ui is not None:
                self.ui.sync_font_scale(is_phone_layout(self.touch.is_active()))

    def _ensure_display_synced(self):
        cur_surf = pygame.display.get_surface()
        if cur_surf is not None and cur_surf is not self.display_surf:
            self.display_surf = cur_surf
            self._update_present_rect()
            return
        if self.display_surf is not None:
            try:
                cur_sz = self.display_surf.get_size()
            except Exception:
                cur_sz = self._present_display_size
            if cur_sz != self._present_display_size:
                self._update_present_rect()

    def _update_present_rect(self):
        self._present_buf = None
        self._present_scale_buf = None
        if self.display_surf is None:
            self._sync_view_size(0, 0)
            vw = get_view_width()
            self._present_rect = pygame.Rect(0, 0, vw, SCREEN_HEIGHT)
            self._present_display_size = (vw, SCREEN_HEIGHT)
            return
        try:
            dw, dh = self.display_surf.get_size()
        except Exception:
            dw, dh = get_view_width(), SCREEN_HEIGHT
        self._present_display_size = (dw, dh)
        self._sync_view_size(dw, dh)
        vw = get_view_width()
        if dw <= 0 or dh <= 0:
            self._present_rect = pygame.Rect(0, 0, vw, SCREEN_HEIGHT)
            return
        if (
            is_android()
            and GAME_SETTINGS.get("wide_mode", "auto") == "auto"
            and dw > dh
            and abs((dw / float(dh)) - (vw / float(SCREEN_HEIGHT))) <= 0.045
        ):
            rx, ry, rw, rh = 0, 0, dw, dh
        else:
            scale = min(dw / float(vw), dh / float(SCREEN_HEIGHT))
            rw = max(1, int(round(vw * scale)))
            rh = max(1, int(round(SCREEN_HEIGHT * scale)))
            rx = (dw - rw) // 2
            ry = (dh - rh) // 2
        self._present_rect = pygame.Rect(rx, ry, rw, rh)
        res_choice = get_resolution_choice()
        if res_choice is not None:
            cw = max(320, min(rw, int(round(res_choice[0] * (vw / float(BASE_WIDTH))))))
            ch = max(180, min(rh, res_choice[1]))
            if cw < rw or ch < rh:
                try:
                    self._present_scale_buf = pygame.Surface((cw, ch)).convert(self.display_surf)
                except Exception:
                    self._present_scale_buf = pygame.Surface((cw, ch))
        if dw != vw or dh != SCREEN_HEIGHT or rx != 0 or ry != 0:
            try:
                self._present_buf = pygame.Surface((rw, rh)).convert(self.display_surf)
            except Exception:
                self._present_buf = pygame.Surface((rw, rh))

    def _apply_display_mode(self, fullscreen, persist=True):
        if is_android():
            fullscreen = True
            GAME_SETTINGS["resolution"] = "auto"
        GAME_SETTINGS["fullscreen"] = bool(fullscreen)
        self._scaled_mode = False
        scaled_flag = getattr(pygame, "SCALED", 0)
        res_choice = None if is_android() else get_resolution_choice()
        nat_w, nat_h = get_native_display_size((BASE_WIDTH, SCREEN_HEIGHT))
        wide_vw = compute_wide_view_width(nat_w, nat_h)
        use_scaled = bool(scaled_flag) and (not is_android()) and os.environ.get("SDL_VIDEODRIVER", "") != "dummy"
        if is_android():
            # Native 32-bit fullscreen avoids SDL_Renderer / SCALED EGL context-loss crashes and 16-bit banding
            android_tries = [
                ((0, 0), pygame.FULLSCREEN, 32),
                ((0, 0), pygame.FULLSCREEN, 0),
                ((nat_w, nat_h), pygame.FULLSCREEN, 32),
                ((nat_w, nat_h), 0, 0),
                ((0, 0), 0, 0),
            ]
            for sz, flags, depth in android_tries:
                try:
                    if depth:
                        self.display_surf = pygame.display.set_mode(sz, flags, depth)
                    else:
                        self.display_surf = pygame.display.set_mode(sz, flags)
                    if self.display_surf is not None:
                        break
                except Exception:
                    self.display_surf = None
        elif fullscreen:
            if GAME_SETTINGS.get("wide_mode", "auto") == "auto" and res_choice is None:
                target_size = (0, 0)
            else:
                target_size = res_choice if res_choice is not None else (wide_vw, SCREEN_HEIGHT)
            if use_scaled and res_choice is None and wide_vw == BASE_WIDTH and GAME_SETTINGS.get("wide_mode", "auto") != "auto":
                try:
                    self.display_surf = pygame.display.set_mode((BASE_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN | scaled_flag, 32)
                    self._scaled_mode = True
                except Exception:
                    self.display_surf = None
            if self.display_surf is None:
                for size, flags in ((target_size, pygame.FULLSCREEN | pygame.DOUBLEBUF), ((0, 0), pygame.FULLSCREEN), ((BASE_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN)):
                    try:
                        self.display_surf = pygame.display.set_mode(size, flags, 32)
                        break
                    except Exception:
                        try:
                            self.display_surf = pygame.display.set_mode(size, flags)
                            break
                        except Exception:
                            self.display_surf = None
        else:
            if res_choice is not None:
                win_size = res_choice
            else:
                win_w, win_h = wide_vw, SCREEN_HEIGHT
                try:
                    info = pygame.display.Info()
                    if info.current_w > 320 and win_w > info.current_w - 40:
                        scale_w = (info.current_w - 40) / float(win_w)
                        win_w = int(round(win_w * scale_w))
                        win_h = max(360, int(round(win_h * scale_w)))
                except Exception:
                    pass
                win_size = (win_w, win_h)
            if use_scaled and win_size == (BASE_WIDTH, SCREEN_HEIGHT):
                try:
                    self.display_surf = pygame.display.set_mode(win_size, pygame.RESIZABLE | scaled_flag, 32)
                    self._scaled_mode = True
                except Exception:
                    self.display_surf = None
            if self.display_surf is None:
                try:
                    self.display_surf = pygame.display.set_mode(win_size, pygame.RESIZABLE, 32)
                except Exception:
                    try:
                        self.display_surf = pygame.display.set_mode(win_size, pygame.RESIZABLE)
                    except Exception:
                        self.display_surf = None
        if self.display_surf is None:
            # Bulletproof recovery for Linux / Wayland / X11 / headless
            GAME_SETTINGS["fullscreen"] = False
            GAME_SETTINGS["resolution"] = "auto"
            for fb_sz, fb_flg in (((BASE_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE), ((BASE_WIDTH, SCREEN_HEIGHT), 0), ((800, 600), 0)):
                try:
                    self.display_surf = pygame.display.set_mode(fb_sz, fb_flg)
                    if self.display_surf is not None:
                        break
                except Exception:
                    self.display_surf = None
        self._update_present_rect()
        if hasattr(self, "lighting") and self.lighting is not None:
            self.lighting.reset_display_formats()
        if persist:
            save_user_settings()

    def _to_logical_pos(self, pos):
        self._ensure_display_synced()
        vw = get_view_width()
        pr = self._present_rect
        lx = (pos[0] - pr.x) * (vw / max(1.0, float(pr.w)))
        ly = (pos[1] - pr.y) * (SCREEN_HEIGHT / max(1.0, float(pr.h)))
        return (int(clamp(round(lx), 0, vw - 1)), int(clamp(round(ly), 0, SCREEN_HEIGHT - 1)))

    def _finger_to_logical(self, fx, fy):
        self._ensure_display_synced()
        vw = get_view_width()
        # Some Android/SDL wrappers deliver pixel coordinates (> 1.5) instead of normalized 0..1
        if fx > 1.5 or fy > 1.5:
            return self._to_logical_pos((fx, fy))
        if self._scaled_mode and hasattr(pygame.display, "get_window_size"):
            try:
                ww, wh = pygame.display.get_window_size()
            except Exception:
                ww, wh = self.display_surf.get_size() if self.display_surf is not None else (vw, SCREEN_HEIGHT)
            if ww > 0 and wh > 0:
                scale = min(ww / float(vw), wh / float(SCREEN_HEIGHT))
                rw = max(1.0, vw * scale)
                rh = max(1.0, SCREEN_HEIGHT * scale)
                rx = (ww - rw) * 0.5
                ry = (wh - rh) * 0.5
                lx = (fx * ww - rx) * (vw / rw)
                ly = (fy * wh - ry) * (SCREEN_HEIGHT / rh)
                return (int(clamp(round(lx), 0, vw - 1)), int(clamp(round(ly), 0, SCREEN_HEIGHT - 1)))
        if self.display_surf is not None:
            dw, dh = self.display_surf.get_size()
        else:
            dw, dh = vw, SCREEN_HEIGHT
        return self._to_logical_pos((fx * dw, fy * dh))

    def _is_raw_touch_mouse_event(self, event):
        tmid = getattr(pygame, "TOUCH_MOUSEID", None)
        w = getattr(event, "which", None)
        return bool(getattr(event, "touch", False) or (tmid is not None and w == tmid) or w == 4294967295)

    def _is_touch_mouse_event(self, event):
        # Only suppress SDL's synthetic touch-mouse events when real FINGER* events are arriving;
        # if a device/driver only delivers touch-emulated mouse events, let them drive UI & touch controls.
        return bool(getattr(self, "_finger_events_seen", False) and self._is_raw_touch_mouse_event(event))

    def _make_synthetic_click(self, logical_pos):
        return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=logical_pos, button=1, synthetic=True)

    def _present_frame(self):
        self._ensure_display_synced()
        if self.display_surf is None:
            return
        vw = get_view_width()
        dw, dh = self.display_surf.get_size()
        pr = self._present_rect
        if dw == vw and dh == SCREEN_HEIGHT and pr.topleft == (0, 0):
            self.display_surf.blit(self.screen, (0, 0))
        else:
            if pr.x > 0:
                self.display_surf.fill((4, 4, 4), (0, 0, pr.x, dh))
            if pr.right < dw:
                self.display_surf.fill((4, 4, 4), (pr.right, 0, dw - pr.right, dh))
            if pr.y > 0:
                self.display_surf.fill((4, 4, 4), (0, 0, dw, pr.y))
            if pr.bottom < dh:
                self.display_surf.fill((4, 4, 4), (0, pr.bottom, dw, dh - pr.bottom))
            scale_fn = pygame.transform.scale if is_android() else pygame.transform.smoothscale
            if self._present_scale_buf is not None:
                sw, sh = self._present_scale_buf.get_size()
                scale_fn(self.screen, (sw, sh), self._present_scale_buf)
                if self._present_buf is not None and self._present_buf.get_bitsize() == self._present_scale_buf.get_bitsize():
                    scale_fn(self._present_scale_buf, (pr.w, pr.h), self._present_buf)
                    self.display_surf.blit(self._present_buf, pr.topleft)
                else:
                    scaled = scale_fn(self._present_scale_buf, (pr.w, pr.h))
                    self.display_surf.blit(scaled, pr.topleft)
            elif self._present_buf is not None and self._present_buf.get_bitsize() == self.screen.get_bitsize():
                scale_fn(self.screen, (pr.w, pr.h), self._present_buf)
                self.display_surf.blit(self._present_buf, pr.topleft)
            else:
                scaled = scale_fn(self.screen, (pr.w, pr.h))
                self.display_surf.blit(scaled, pr.topleft)

    def _get_loading_art(self, vw):
        max_w = max(320, min(920, int(vw * 0.76)))
        if self._loading_art_surf is not None and self._loading_art_w == max_w:
            return self._loading_art_surf
        base_res = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        local_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(local_dir)
        cand_paths = [
            os.path.join(base_res, "preview.jpg"),
            os.path.join(local_dir, "preview.jpg"),
            os.path.join(root_dir, "preview.jpg"),
            os.path.join(base_res, "darkvault_presplash.jpg"),
            os.path.join(local_dir, "darkvault_presplash.jpg"),
        ]
        art_path = next((p for p in cand_paths if p and os.path.isfile(p)), "")
        surf = None
        if art_path:
            try:
                from PIL import Image, ImageDraw, ImageFilter

                pv = Image.open(art_path).convert("RGBA")
                pv.thumbnail((max_w, 410), Image.Resampling.LANCZOS)
                mask = Image.new("L", pv.size, 0)
                draw = ImageDraw.Draw(mask)
                pad_x = max(24, min(48, pv.width // 10))
                pad_y = max(22, min(44, pv.height // 8))
                draw.rounded_rectangle(
                    [pad_x, pad_y, pv.width - pad_x, pv.height - pad_y],
                    radius=28,
                    fill=255,
                )
                mask = mask.filter(ImageFilter.GaussianBlur(24))
                pv.putalpha(mask)
                surf = pygame.image.fromstring(pv.tobytes(), pv.size, "RGBA")
                if pygame.display.get_surface() is not None:
                    try:
                        surf = surf.convert_alpha()
                    except Exception:
                        pass
            except Exception:
                try:
                    raw = pygame.image.load(art_path)
                    rw, rh = raw.get_size()
                    scale = min(max_w / max(1.0, float(rw)), 410.0 / max(1.0, float(rh)), 1.0)
                    surf = pygame.transform.smoothscale(raw, (max(1, int(rw * scale)), max(1, int(rh * scale))))
                except Exception:
                    surf = None
        self._loading_art_surf = surf
        self._loading_art_w = max_w
        return surf

    def _render_loading(self, progress, label_key="loading_init", detail=""):
        if self.screen is None:
            return
        try:
            pygame.event.pump()
        except Exception:
            pass
        vw = get_view_width()
        bg_col = PALETTE.get("bg_dark", (5, 5, 5))
        self.screen.fill(bg_col)
        art = self._get_loading_art(vw)
        if art is not None:
            ax = (vw - art.get_width()) // 2
            ay = max(28, (SCREEN_HEIGHT - art.get_height()) // 2 - 46)
            self.screen.blit(art, (ax, ay))
        else:
            title_s = render_text_cached(self.ui.font_huge, tr("game_title"), PALETTE["text_main"])
            self.screen.blit(title_s, ((vw - title_s.get_width()) // 2, SCREEN_HEIGHT // 2 - 90))

        bar_w = min(540, max(240, vw - 160))
        bar_h = 8
        bar_x = (vw - bar_w) // 2
        bar_y = SCREEN_HEIGHT - 104

        lbl_s = render_text_cached(self.ui.font_med, tr(label_key), (218, 218, 218))
        self.screen.blit(lbl_s, ((vw - lbl_s.get_width()) // 2, bar_y - 30))

        pygame.draw.rect(self.screen, (20, 20, 20), (bar_x, bar_y, bar_w, bar_h), border_radius=4)
        pygame.draw.rect(self.screen, (68, 68, 68), (bar_x, bar_y, bar_w, bar_h), 1, border_radius=4)
        p = clamp(float(progress), 0.0, 1.0)
        fill_w = max(0, int(round((bar_w - 2) * p)))
        if fill_w > 0:
            pygame.draw.rect(self.screen, (236, 236, 236), (bar_x + 1, bar_y + 1, fill_w, bar_h - 2), border_radius=3)

        pct_txt = f"{int(round(p * 100))}%"
        if detail:
            pct_txt = f"{detail}  ·  {pct_txt}"
        pct_s = render_text_cached(self.ui.font_tiny, pct_txt, (146, 146, 146))
        self.screen.blit(pct_s, ((vw - pct_s.get_width()) // 2, bar_y + 16))

        try:
            self._present_frame()
            pygame.display.flip()
        except pygame.error:
            pass

    def _get_active_players(self):
        players = []
        if self.player is not None and not self.player.is_dead():
            players.append(self.player)
        if self.coop_enabled and self.player2 is not None and not self.player2.is_dead():
            players.append(self.player2)
        return players

    def _all_players_dead(self):
        return len(self._get_active_players()) == 0

    def _primary_alive_player(self):
        if self.player is not None and not self.player.is_dead():
            return self.player
        if self.coop_enabled and self.player2 is not None and not self.player2.is_dead():
            return self.player2
        return self.player

    def _nearest_alive_player(self, x, y):
        alive = self._get_active_players()
        if not alive:
            return self.player
        if len(alive) == 1:
            return alive[0]
        return min(alive, key=lambda p: (p.x - x) ** 2 + (p.y - y) ** 2)

    def _toggle_coop_setting(self, force=None):
        if is_android() and force is None:
            self.coop_enabled = False
            return
        self.coop_enabled = (not self.coop_enabled) if force is None else bool(force)
        if not is_android():
            GAME_SETTINGS["coop_enabled"] = self.coop_enabled
            save_user_settings()

    def _cycle_p2_hero(self, step=1):
        self.selected_p2_hero_idx = (self.selected_p2_hero_idx + int(step)) % len(HERO_ROSTER)
        hid = HERO_ROSTER[self.selected_p2_hero_idx]["id"]
        GAME_SETTINGS["p2_hero_id"] = hid
        if getattr(self, "lan_client", None) is not None and self.lan_client.connected:
            self.lan_client.send_hero(hid)
        save_user_settings()

    def _nudge_clear_of_obstacles(self, player_obj, room):
        if player_obj is None or room is None or player_obj.has_effective_flight():
            return
        r = player_obj.get_effective_radius()
        for _ in range(3):
            for obs in room.obstacles:
                if not obs.alive or not obs.blocks_movement:
                    continue
                rx = clamp(player_obj.x, obs.rect.left, obs.rect.right)
                ry = clamp(player_obj.y, obs.rect.top, obs.rect.bottom)
                ox = player_obj.x - rx
                oy = player_obj.y - ry
                dist = math.hypot(ox, oy)
                if dist < r + 2.0:
                    if dist > 0.001:
                        push = (r + 3.0) - dist
                        player_obj.x += (ox / dist) * push
                        player_obj.y += (oy / dist) * push
                    else:
                        player_obj.y += r + 16.0
        player_obj.x = clamp(player_obj.x, PLAYABLE_LEFT + r + 4, PLAYABLE_RIGHT - r - 4)
        player_obj.y = clamp(player_obj.y, PLAYABLE_TOP + r + 4, PLAYABLE_BOTTOM - r - 4)

    def _revive_fallen_coop_player(self, heal_frac=0.5):
        if not self.coop_enabled or self.player is None or self.player2 is None:
            return
        revived = False
        anchor = self._primary_alive_player()
        for fallen in (self.player, self.player2):
            if fallen is not None and fallen.is_dead():
                if fallen.max_hp > 0:
                    fallen.hp = max(2, int(round(fallen.max_hp * heal_frac)))
                else:
                    fallen.soul_hp = max(2, fallen.soul_hp)
                fallen.invuln_timer = 75.0
                if anchor is not None and not anchor.is_dead():
                    fallen.x = clamp(anchor.x + 26, PLAYABLE_LEFT + 28, PLAYABLE_RIGHT - 28)
                    fallen.y = clamp(anchor.y, PLAYABLE_TOP + 28, PLAYABLE_BOTTOM - 28)
                self.particles.append(RingParticle(fallen.x, fallen.y, 44, (242, 242, 242), 18, 2))
                revived = True
        if revived:
            self.ui.show_banner(tr("p2_revived"), duration=75.0)

    def _record_peak_player_stats(self, cp):
        if cp is None:
            return
        self.account_manager.record_stat("max_run_items", len(getattr(cp, "collected_ids", ())) + len(getattr(cp, "active_items", ())), mode="max")
        self.account_manager.record_stat("peak_dmg_x10", int(round(cp.get_effective_damage() * 10)), mode="max")
        self.account_manager.record_stat("peak_speed_x10", int(round(cp.get_effective_speed() * 10)), mode="max")
        self.account_manager.record_stat("max_run_coins", int(getattr(cp, "coins", 0)), mode="max")

    def _filtered_achievements(self):
        return self.achievement_manager.get_filtered(
            self.acc_cat_filter,
            only_unlocked=bool(getattr(self, "acc_only_unlocked", False)),
        )

    def _on_run_end(self, won=False):
        if not self.run_recorded:
            self.run_recorded = True
            if self.player is not None:
                self._record_peak_player_stats(self.player)
            if self.coop_enabled and self.player2 is not None:
                self._record_peak_player_stats(self.player2)
            if bool(won):
                if self.game_mode == "boss_rush":
                    self.account_manager.record_stat("boss_rush_wins", 1)
                elif self.game_mode == "fading_light":
                    self.account_manager.record_stat("fading_light_wins", 1)
            hero_id = self.player.hero_id if self.player is not None else HERO_ROSTER[self.selected_hero_idx]["id"]
            kills_total = (self.player.kills if self.player is not None else 0) + (
                self.player2.kills if (self.coop_enabled and self.player2 is not None) else 0
            )
            self.account_manager.record_run(
                {
                    "hero": hero_id,
                    "mode": self.game_mode,
                    "floor": self.floor_level,
                    "wave": self.wave_num if self.game_mode == "endless_abyss" else (self.boss_rush_wave if self.game_mode == "boss_rush" else 0),
                    "kills": kills_total,
                    "won": bool(won),
                    "coop": bool(self.coop_enabled and self.player2 is not None),
                    "seed": str(self.active_seed or ""),
                }
            )
            self.achievement_manager.evaluate()
            self._check_hero_unlocks()
        self.touch.reset()
        self.state = "VICTORY" if won else "GAME_OVER"
        if self.lan_host.running:
            self.lan_host.update_lobby_meta(in_run=True)
            self._push_lan_snapshot()
        play_sound("win" if won else "die")

    def _prepare_chaos_draft(self):
        pool_items = []
        seen = set(self.player.collected_ids) if self.player else set()
        if self.player and self.player.active_item:
            seen.add(self.player.active_item.get("id"))
        for _ in range(18):
            if len(pool_items) >= 3:
                break
            it = get_random_item(seen)
            if it and it["id"] not in seen:
                seen.add(it["id"])
                pool_items.append(it)
        self.draft_options = pool_items[:3]
        self.draft_idx = 0
        self.hover_draft_idx = -1

    def _pick_chaos_draft(self, idx):
        if not self.draft_options or idx < 0 or idx >= len(self.draft_options):
            self.state = "PLAYING"
            return
        picked = self.draft_options[idx]
        if self.player is not None:
            self.player.apply_item(picked)
            self.account_manager.record_stat("items_collected", 1)
            self.account_manager.record_stat("chaos_drafts", 1)
            self._record_peak_player_stats(self.player)
            self.achievement_manager.evaluate()
        if self.coop_enabled and self.player2 is not None:
            other = [it for i, it in enumerate(self.draft_options) if i != idx]
            p2_it = random.choice(other) if other else get_random_item(self.player2.collected_ids)
            if p2_it:
                self.player2.apply_item(p2_it)
                self._record_peak_player_stats(self.player2)
        self.draft_options = []
        self.state = "PLAYING"
        self.ui.show_banner(tr_item_name(picked).upper(), tr_item_desc(picked), duration=120.0, item=picked)
        play_sound("item")

    def start_new_run(self):
        lang = GAME_SETTINGS.get("language", "ru")
        active_acc = self.account_manager.get_active()
        hero_id = HERO_ROSTER[self.selected_hero_idx]["id"]
        if not is_hero_unlocked(hero_id, active_acc):
            play_sound("hurt")
            req = get_hero_unlock_text(hero_id, lang)
            self.menu_notice = f"{tr('menu_hero_locked')}: {req}" if req else tr("menu_hero_locked")
            self.menu_notice_timer = 180.0
            return

        if is_android() and not (self.lan_host.running and self.lan_host.client_connected):
            self.coop_enabled = False

        if self.coop_enabled and not (self.lan_host.running and self.lan_host.client_connected):
            p2_hid_check = HERO_ROSTER[self.selected_p2_hero_idx % len(HERO_ROSTER)]["id"]
            if not is_hero_unlocked(p2_hid_check, active_acc):
                play_sound("hurt")
                req2 = get_hero_unlock_text(p2_hid_check, lang)
                self.menu_notice = f"[P2] {tr('menu_hero_locked')}: {req2}" if req2 else f"[P2] {tr('menu_hero_locked')}"
                self.menu_notice_timer = 180.0
                return

        self.seed_input_active = False
        try:
            pygame.key.stop_text_input()
        except Exception:
            pass
        self._render_loading(0.20, "loading_world")
        self.touch.reset()
        self.quest_manager.reset()
        self.game_mode = GAME_MODES[self.selected_mode_idx]
        custom_s = self.custom_seed.strip()
        if custom_s:
            self.active_seed = custom_s
            self.account_manager.record_stat("seeded_runs", 1)
        elif self.game_mode == "shared_seed" and self.shared_seeds:
            seed_entry = self.shared_seeds[self.selected_seed_idx % len(self.shared_seeds)]
            self.active_seed = str(seed_entry.get("seed", "DV-GENESIS-001"))
        else:
            self.active_seed = None
        if self.active_seed:
            random.seed(str(self.active_seed))

        cx = (PLAYABLE_LEFT + PLAYABLE_RIGHT) // 2
        cy = (PLAYABLE_TOP + PLAYABLE_BOTTOM) // 2
        self.floor_level = 1
        self.wave_num = 1
        self.boss_rush_wave = 1
        self.wave_break_timer = 0.0
        self.darkness_tick = 0.0
        self.placenta_tick = 0.0
        self.timescale = 1.0
        self.floor_took_damage = False
        self.room_took_damage = False
        self.run_recorded = False
        self.editor.active = False
        self.editor.freeze_ai = False
        self.console.open = False

        if self.lan_host.running and self.lan_host.client_connected:
            self.coop_enabled = True
            p2_hid = getattr(self.lan_host, "client_hero_id", "")
            for idx, h in enumerate(HERO_ROSTER):
                if h["id"] == p2_hid:
                    self.selected_p2_hero_idx = idx
                    break

        p1_x = cx - 34 if self.coop_enabled else cx
        self.player = Player(p1_x, cy, hero_id)
        daily_bonus = self.account_manager.consume_daily_bonus()
        if daily_bonus:
            self.player.coins += int(daily_bonus.get("coins", 0))
            self.player.bombs += int(daily_bonus.get("bombs", 0))
            self.player.keys += int(daily_bonus.get("keys", 0))
            self.player.soul_hp += int(daily_bonus.get("soul_hp", 0))
            self.player.damage += float(daily_bonus.get("damage", 0.0))
            self.player.speed += float(daily_bonus.get("speed", 0.0))

        if self.coop_enabled:
            p2_hero_id = HERO_ROSTER[self.selected_p2_hero_idx % len(HERO_ROSTER)]["id"]
            self.player2 = Player(cx + 34, cy, p2_hero_id)
            self.player.player_tag = "P1"
            self.player2.player_tag = "P2"
        else:
            self.player.player_tag = ""
            self.player2 = None

        self._generate_floor(1)
        for cp in (self.player, self.player2):
            if cp is not None:
                self._nudge_clear_of_obstacles(cp, self.current_room)
        if self.lan_host.running and self.lan_host.client_connected:
            self.account_manager.record_stat("lan_runs", 1)
        if any(mod_manager.enabled_map.values()):
            self.account_manager.record_stat("modded_runs", 1)
        self._record_peak_player_stats(self.player)
        self.achievement_manager.evaluate()
        mod_manager.dispatch_run_start(self, self.player)
        mod_manager.dispatch_player_init(self.player)
        if self.player2 is not None:
            mod_manager.dispatch_player_init(self.player2)
        mod_manager.dispatch_new_floor(self.floor_level, self.player, self.player2)
        mod_manager.dispatch_room_enter(self, self.current_room, self.player)

        if self.game_mode == "chaos_draft":
            self._prepare_chaos_draft()
            self.fade_alpha = 180.0
            self.state = "CHAOS_DRAFT"
        elif self.game_mode == "endless_abyss":
            self._spawn_endless_wave(1)
            self.ui.show_banner(f"{tr('wave_label')} 1", tr_mode(self.game_mode))
            self.fade_alpha = 240.0
            self.state = "PLAYING"
        else:
            sub = self.active_seed if self.active_seed else tr_mode(self.game_mode)
            self.ui.show_banner(f"{tr('floor_label')} 1", sub)
            self.fade_alpha = 240.0
            self.state = "PLAYING"
        if self.lan_host.running:
            self.lan_host.update_lobby_meta(host_hero_id=hero_id, game_mode=self.game_mode, in_run=True)
            self._push_lan_snapshot()
        play_sound("door")

    def _generate_floor(self, level):
        self._render_loading(0.45, "loading_floor", f"{tr('floor_label')} {int(level)}")
        clear_render_caches(include_text=False)
        self.floor_level = int(level)
        floor_seed = f"{self.active_seed}:F{self.floor_level}" if self.active_seed else None
        if floor_seed:
            random.seed(floor_seed)
        gen = DungeonGenerator(self.floor_level, seed=floor_seed, game_mode=self.game_mode)
        self.floor_modifier = gen.floor_modifier
        self.rooms = gen.generate_floor()
        self.floor_pedestals_spawned = sum(
            len([ped for ped in getattr(rm, "pedestals", []) if getattr(ped, "alive", True)])
            for rm in self.rooms.values()
        )
        self.current_coord = (0, 0)
        self.current_room = self.rooms[self.current_coord]
        self.tears.clear()
        self.enemy_projectiles.clear()
        self.bombs.clear()
        self.particles.clear()
        for cp in (self.player, self.player2):
            if cp is not None:
                cp.reset_for_new_floor()
                cp.reset_for_new_room()
        self._revive_fallen_coop_player(0.5)
        self.floor_took_damage = False
        self.room_took_damage = False
        self._render_loading(0.95, "loading_floor", f"{tr('floor_label')} {int(level)}")
        self.fade_alpha = 240.0
        if getattr(self, "lan_host", None) is not None and self.lan_host.running:
            self.lan_host.update_lobby_meta(in_run=True)
            self._push_lan_snapshot()

    def _spawn_endless_wave(self, wave):
        if self.current_room is None:
            return
        self.current_room.cleared = False
        self.current_room.enemies.clear()
        self.current_room.bosses.clear()
        scale_floor = 1 + (wave - 1) // 3
        if wave % 5 == 0:
            boss_choices = ["eclipse_warden", "void_architect", "pale_seraph", "monstro", "famine", "war", "death", "satan", "delirium", "ash_colossus"]
            bk = random.choice(boss_choices)
            cx = (PLAYABLE_LEFT + PLAYABLE_RIGHT) // 2
            cy = (PLAYABLE_TOP + PLAYABLE_BOTTOM) // 2
            self.current_room.bosses = spawn_boss_for_room(self.current_room, bk, cx, cy - 110, scale_floor)
        _, pool = pick_combat_theme_enemies(scale_floor, random, max_types=2)
        count = 3 + min(8, wave)
        anchor = self._primary_alive_player() or self.player
        for _ in range(count):
            for _attempt in range(16):
                ex = random.uniform(PLAYABLE_LEFT + 70, PLAYABLE_RIGHT - 70)
                ey = random.uniform(PLAYABLE_TOP + 70, PLAYABLE_BOTTOM - 70)
                if anchor is not None and math.hypot(ex - anchor.x, ey - anchor.y) < 160:
                    continue
                if any(obs.rect.inflate(18, 18).collidepoint(ex, ey) for obs in self.current_room.obstacles):
                    continue
                et = random.choice(pool)
                self.current_room.enemies.append(create_enemy(et, ex, ey, scale_floor))
                break

    def _enter_room(self, target_coord, from_dir):
        if self.current_room is not None and hasattr(self.current_room, "release_baked_bg"):
            self.current_room.release_baked_bg()
        if target_coord == (99, 99):
            self.devil_return_coord = self.current_coord if self.current_coord in self.rooms else (0, 0)
            exit_dir = {"N": "S", "S": "N", "E": "W", "W": "E"}.get(from_dir, "S")
            seen_ids = set(self.player.collected_ids)
            if self.coop_enabled and self.player2 is not None:
                seen_ids |= set(self.player2.collected_ids)
            self.current_room = spawn_devil_deal_room(
                self.floor_level,
                seen_ids,
                return_coord=self.devil_return_coord,
                exit_dir=exit_dir,
            )
            self.current_coord = (99, 99)
        else:
            if target_coord not in self.rooms:
                target_coord = (0, 0)
            self.current_coord = target_coord
            self.current_room = self.rooms[target_coord]

        was_visited = bool(self.current_room.visited)
        if not was_visited:
            self.account_manager.record_stat("rooms_visited", 1)
            if self.current_room.room_type in ("treasure", "shop", "library", "arcade", "curse", "sacrifice", "dice", "secret", "devil"):
                self.account_manager.record_stat("special_rooms_visited", self.current_room.room_type, mode="append_unique")
            if self.current_room.room_type == "library":
                self.account_manager.record_stat("libraries_visited", 1)
            elif self.current_room.room_type == "curse":
                self.account_manager.record_stat("curse_rooms_visited", 1)
            self.achievement_manager.evaluate()
            self.quest_manager.trigger(self, "room_visit")
        self.current_room.visited = True
        self.room_took_damage = False
        self.tears.clear()
        self.enemy_projectiles.clear()
        self.bombs.clear()
        self.particles.clear()
        self.pending_pedestal_prompt = None
        self._dismissed_pedestals.clear()
        for cp in (self.player, self.player2):
            if cp is not None:
                cp.reset_for_new_room()
        self.fade_alpha = 210.0

        cx = (PLAYABLE_LEFT + PLAYABLE_RIGHT) // 2
        cy = (PLAYABLE_TOP + PLAYABLE_BOTTOM) // 2
        if from_dir == "N":
            sx, sy = cx, PLAYABLE_BOTTOM - 38
        elif from_dir == "S":
            sx, sy = cx, PLAYABLE_TOP + 38
        elif from_dir == "E":
            sx, sy = PLAYABLE_LEFT + 38, cy
        else:
            sx, sy = PLAYABLE_RIGHT - 38, cy

        if self.coop_enabled and self.player2 is not None:
            if from_dir in ("N", "S"):
                self.player.x = clamp(sx - 20, PLAYABLE_LEFT + 30, PLAYABLE_RIGHT - 30)
                self.player.y = sy
                self.player2.x = clamp(sx + 20, PLAYABLE_LEFT + 30, PLAYABLE_RIGHT - 30)
                self.player2.y = sy
            else:
                self.player.x = sx
                self.player.y = clamp(sy - 20, PLAYABLE_TOP + 30, PLAYABLE_BOTTOM - 30)
                self.player2.x = sx
                self.player2.y = clamp(sy + 20, PLAYABLE_TOP + 30, PLAYABLE_BOTTOM - 30)
            for cp in (self.player, self.player2):
                self._nudge_clear_of_obstacles(cp, self.current_room)
        else:
            self.player.x = sx
            self.player.y = sy
            self._nudge_clear_of_obstacles(self.player, self.current_room)

        if not was_visited:
            for cp in self._get_active_players():
                if cp.hero_id == "seraph":
                    cp.seraph_room_counter += 1
                    if cp.seraph_room_counter >= 2:
                        cp.seraph_room_counter = 0
                        cp.soul_hp = min(14, cp.soul_hp + 1)

        mod_manager.dispatch_room_enter(self, self.current_room, self._primary_alive_player() or self.player)

        alive_bosses = [b for b in self.current_room.bosses if b.alive]
        if alive_bosses and self.current_room.room_type == "boss":
            self.boss_for_cutscene = alive_bosses[0].boss_key
            self.cutscene = BossCutscene(self.player.hero_id, self.boss_for_cutscene)
            self.state = "CUTSCENE"
            play_sound("boss")
        elif self.current_room.room_type != "normal":
            self.ui.show_banner(tr_room(self.current_room.room_type))

        if getattr(self, "lan_host", None) is not None and self.lan_host.running:
            self.lan_host.update_lobby_meta(in_run=True)
            self._push_lan_snapshot()

    def _trigger_shake(self, power=5.0, duration=12.0):
        if GAME_SETTINGS.get("shake_enabled", True):
            self.shake_power = max(self.shake_power, float(power))
            self.shake_timer = max(self.shake_timer, float(duration))

    def _check_hero_unlocks(self, silent=False):
        acc = self.account_manager.get_active()
        acc_id = str((acc or {}).get("id", ""))
        cur_unlocked = {h["id"] for h in HERO_ROSTER if is_hero_unlocked(h["id"], acc)}
        if self._known_unlocked_heroes is None or self._known_acc_id != acc_id:
            self._known_unlocked_heroes = set(cur_unlocked)
            self._known_acc_id = acc_id
            return []
        newly = [h for h in HERO_ROSTER if h["id"] in cur_unlocked and h["id"] not in self._known_unlocked_heroes]
        if newly:
            self._known_unlocked_heroes |= cur_unlocked
            if not silent:
                lang = GAME_SETTINGS.get("language", "ru")
                play_sound("hero_unlock")
                for h in newly:
                    hname = h.get("name_en", h["name"]) if lang == "en" else h["name"]
                    hdr = "HERO UNLOCKED!" if lang == "en" else "ГЕРОЙ РАЗБЛОКИРОВАН!"
                    self.ui.show_banner(hdr, hname.upper(), duration=135.0)
        return newly

    def _on_obstacle_shattered(self, obs):
        ox, oy = obs.rect.center
        play_sound("block_break")
        for _ in range(7):
            ang = random.uniform(0.0, math.pi * 2.0)
            spd = random.uniform(1.2, 3.6)
            self.particles.append(SplashParticle(ox, oy, math.cos(ang) * spd, math.sin(ang) * spd, (212, 212, 212), 3, 16))
        if obs.kind == "urn":
            roll = random.random()
            has_mk = any(cp.has_moms_key for cp in self._get_active_players())
            chance = 0.52 if has_mk else 0.34
            if roll < chance:
                self.current_room.pickups.append(Pickup(ox, oy, random.choice(["coin", "coin", "half_heart", "key"])))
        elif obs.kind == "poop":
            if random.random() < 0.22:
                self.current_room.pickups.append(Pickup(ox, oy, random.choice(["coin", "half_heart"])))
        elif obs.kind in ("barrier", "turret", "rock"):
            # 10% loot drop chance from shattered new/destructible blocks
            if random.random() < 0.10:
                self.current_room.pickups.append(Pickup(ox, oy, random.choice(["coin", "coin", "half_heart", "key", "bomb"])))

    def _explode_bomb(self, bx, by, sad_bombs=False, owner=None):
        play_sound("bomb")
        self._trigger_shake(8.5, 18.0)
        self.particles.append(RingParticle(bx, by, 108, (244, 244, 244), 18, 3))
        for _ in range(18):
            ang = random.uniform(0.0, math.pi * 2.0)
            spd = random.uniform(1.8, 5.8)
            self.particles.append(SplashParticle(bx, by, math.cos(ang) * spd, math.sin(ang) * spd, (230, 230, 230), 4, 22))

        blast_r = 104.0
        for obs in self.current_room.obstacles:
            if obs.alive and math.hypot(obs.rect.centerx - bx, obs.rect.centery - by) <= blast_r:
                if obs.explode():
                    self.quest_manager.trigger(self, "obstacle_destroyed")
                    if obs.kind == "tinted_rock":
                        self.current_room.pickups.append(Pickup(obs.rect.centerx, obs.rect.centery, "soul_heart"))
                        self.account_manager.record_stat("tinted_rocks_bombed", 1)
                        self.achievement_manager.evaluate()
                    else:
                        self._on_obstacle_shattered(obs)

        for door in self.current_room.doors.values():
            if door.secret and not door.opened and math.hypot(door.rect.centerx - bx, door.rect.centery - by) <= blast_r + 34.0:
                door.opened = True
                self.account_manager.record_stat("secrets_found", 1)
                self.account_manager.record_stat("doors_opened", 1)
                self.achievement_manager.evaluate()
                nb = self.rooms.get(door.target_coord)
                if nb is not None:
                    for nb_door in nb.doors.values():
                        if nb_door.target_coord == self.current_coord:
                            nb_door.opened = True
                play_sound("door")

        for mac in self.current_room.machines:
            if mac.alive and math.hypot(mac.x - bx, mac.y - by) <= blast_r:
                if mac.explode(self._primary_alive_player() or self.player, self.current_room):
                    self.account_manager.record_stat("machines_bombed", 1)
                    self.achievement_manager.evaluate()
        for beg in self.current_room.beggars:
            if beg.alive and math.hypot(beg.x - bx, beg.y - by) <= blast_r:
                beg.explode(self.current_room)
        for sk in self.current_room.shopkeepers:
            if sk.alive and math.hypot(sk.x - bx, sk.y - by) <= blast_r:
                sk.explode(self.current_room)
        for npc in self.current_room.mystical_npcs:
            if npc.alive and math.hypot(npc.x - bx, npc.y - by) <= blast_r:
                npc.explode(self.current_room)

        for e in self.current_room.enemies:
            if e.alive and math.hypot(e.x - bx, e.y - by) <= blast_r:
                e.take_damage(42.0)
                if not e.alive:
                    self.account_manager.record_stat("explosion_kills", 1)
        for b in self.current_room.bosses:
            if b.alive and math.hypot(b.x - bx, b.y - by) <= blast_r + b.radius:
                b.take_damage(42.0)
                if not b.alive:
                    self.account_manager.record_stat("explosion_kills", 1)
        self.quest_manager.trigger(self, "explosion_hit")

        for cp in self._get_active_players():
            if math.hypot(cp.x - bx, cp.y - by) <= blast_r:
                if cp.has_pyromaniac:
                    if cp.max_hp > 0:
                        cp.hp = min(cp.max_hp, cp.hp + 2)
                    else:
                        cp.soul_hp = min(14, cp.soul_hp + 1)
                else:
                    if cp.take_damage(2):
                        self.floor_took_damage = True
                        self.room_took_damage = True

        if sad_bombs:
            src_p = owner if owner is not None else self.player
            for i in range(8):
                a = i * (math.pi / 4.0)
                self.tears.append(
                    Tear(
                        bx,
                        by,
                        math.cos(a) * 7.2,
                        math.sin(a) * 7.2,
                        damage=src_p.get_effective_damage(),
                        max_range=src_p.tear_range,
                        piercing=(src_p.has_piercing or src_p.has_effect("brimstone")),
                        bouncing=src_p.has_bouncing,
                        homing=(src_p.has_homing or src_p.has_effect("homing")),
                        splitting=src_p.has_splitting,
                        spectral=(src_p.has_spectral or src_p.has_effect("spectral")),
                        poison=(src_p.has_poison or src_p.has_effect("poison_touch")),
                        holy=src_p.has_holy,
                        bone=src_p.has_bone,
                        brimstone=(src_p.has_brimstone or src_p.has_effect("brimstone")),
                        boomerang=src_p.has_boomerang,
                        coal=src_p.has_coal,
                        radius=6.0 * (1.3 if src_p.has_effect("giant") else 1.0),
                    )
                )

    def _spawn_split_tears(self, src_tear, exclude_id=None):
        children = []
        for i in range(4):
            ang = math.pi * 0.25 + i * (math.pi * 0.5)
            child = Tear(
                src_tear.x,
                src_tear.y,
                math.cos(ang) * 5.8,
                math.sin(ang) * 5.8,
                damage=max(1.0, src_tear.damage * 0.45),
                max_range=140.0,
                piercing=src_tear.piercing,
                bouncing=src_tear.bouncing,
                spectral=src_tear.spectral,
                homing=src_tear.homing,
                poison=src_tear.poison,
                holy=src_tear.holy,
                bone=src_tear.bone,
                brimstone=src_tear.brimstone,
                splitting=False,
                radius=max(3.5, src_tear.radius * 0.6),
            )
            if exclude_id is not None:
                child.hit_ids.add(exclude_id)
            children.append(child)
        return children

    def _detonate_tear(self, t_obj, all_targets):
        bx, by = t_obj.x, t_obj.y
        br = max(36.0, float(getattr(t_obj, "blast_radius", 62.0)))
        self._trigger_shake(4.2, 8.0)
        self.particles.append(RingParticle(bx, by, int(br), (242, 242, 242), 16, 2))
        if getattr(t_obj, "shockwave", False):
            self.particles.append(RingParticle(bx, by, int(br * 1.45), (195, 195, 195), 20, 1))
        for _ in range(9):
            ang = random.uniform(0.0, math.pi * 2.0)
            spd = random.uniform(1.4, 4.2)
            self.particles.append(SplashParticle(bx, by, math.cos(ang) * spd, math.sin(ang) * spd, (232, 232, 232), 3, 16))
        dmg = max(2.0, t_obj.get_effective_damage() * 0.85)
        for tgt in all_targets:
            if tgt.alive and math.hypot(tgt.x - bx, tgt.y - by) <= br + tgt.radius:
                was_alive_t = tgt.alive
                dx = tgt.x - bx
                dy = tgt.y - by
                dist = math.hypot(dx, dy) or 1.0
                kb = 5.0 if getattr(t_obj, "shockwave", False) else 2.6
                tgt.take_damage(dmg, (dx / dist) * kb, (dy / dist) * kb)
                if not tgt.alive and was_alive_t:
                    self.account_manager.record_stat("explosion_kills", 1)
        self.quest_manager.trigger(self, "explosion_hit")

    def _tick_enemy_statuses(self, tgt, sim_dt):
        burn_t = getattr(tgt, "burn_timer", 0.0)
        if burn_t > 0.0:
            tgt.burn_timer = max(0.0, burn_t - sim_dt)
            tgt.take_damage(0.08 * sim_dt)
        bleed_t = getattr(tgt, "bleed_timer", 0.0)
        if bleed_t > 0.0:
            tgt.bleed_timer = max(0.0, bleed_t - sim_dt)
            tgt.take_damage(0.06 * sim_dt)
        weaken_t = getattr(tgt, "weaken_timer", 0.0)
        if weaken_t > 0.0:
            tgt.weaken_timer = max(0.0, weaken_t - sim_dt)
        freeze_t = getattr(tgt, "freeze_timer", 0.0)
        if freeze_t > 0.0:
            tgt.freeze_timer = max(0.0, freeze_t - sim_dt)
            return sim_dt * 0.35
        return sim_dt

    def _trigger_active_item(self, cp=None):
        target_p = cp if cp is not None else self.player
        if target_p is None or self.current_room is None:
            return False
        ok = target_p.use_active(
            self.current_room,
            self.tears,
            self.current_room.enemies + self.current_room.bosses,
            self.particles,
        )
        if ok:
            self.account_manager.record_stat("active_uses", 1)
            self.achievement_manager.evaluate()
            it = target_p.active_item
            if it:
                self.ui.show_banner(tr_item_name(it).upper(), tr_item_desc(it), duration=70.0, item=it)
            return True
        code, extra = getattr(target_p, "last_active_status", ("", ""))
        it = target_p.active_item
        if code == "no_charge" and it is not None:
            self.ui.show_banner(tr("relic_no_charge"), f"{tr_item_name(it)} ({extra})", duration=55.0)
        elif code == "no_pedestals":
            self.ui.show_banner(tr("relic_no_pedestals"), tr_item_name(it) if it else "", duration=55.0)
        elif code == "hp_full":
            self.ui.show_banner(tr("relic_hp_full"), tr_item_name(it) if it else "", duration=55.0)
        elif code == "low_hp":
            self.ui.show_banner(tr("relic_low_hp"), tr_item_name(it) if it else "", duration=55.0)
        return False

    def _trigger_melee(self, cp, aim_x=0.0, aim_y=0.0):
        if cp is None or self.current_room is None or cp.is_dead():
            return False
        targets = [e for e in self.current_room.enemies if e.alive] + [b for b in self.current_room.bosses if b.alive]
        was_obs = {id(obs): obs for obs in self.current_room.obstacles if obs.alive}
        res = cp.try_melee(aim_x, aim_y, self.current_room, targets, self.enemy_projectiles, self.particles, tears=self.tears)
        if not res.get("hit"):
            return False
        if res["enemies_hit"] > 0 or res["obstacles_broken"] > 0 or res["deflected"] > 0:
            self._trigger_shake(5.2 if res.get("finisher") else 4.0, 10.0 if res.get("finisher") else 8.0)
        if res["enemies_hit"] > 0:
            self.account_manager.record_stat("melee_hits", res["enemies_hit"])
        if res["kills"] > 0:
            self.account_manager.record_stat("melee_kills", res["kills"])
            self.account_manager.record_stat("kills", res["kills"])
            self.quest_manager.trigger(self, "kill", res["kills"])
        if res["obstacles_broken"] > 0:
            self.account_manager.record_stat("obstacles_destroyed", res["obstacles_broken"])
            self.quest_manager.trigger(self, "obstacle_destroyed", res["obstacles_broken"])
            for oid, obs in was_obs.items():
                if not obs.alive:
                    self._on_obstacle_shattered(obs)
        if res["turrets_broken"] > 0:
            self.account_manager.record_stat("turrets_destroyed", res["turrets_broken"])
        if res.get("deflected", 0) > 0:
            self.account_manager.record_stat("projectiles_deflected", res["deflected"])
        if res.get("finisher"):
            self.account_manager.record_stat("melee_finishers", 1)
        self.achievement_manager.evaluate()
        self._check_hero_unlocks()
        return True

    def _check_pedestal_affordability(self, ped, cp):
        if ped is None or cp is None or not getattr(ped, "alive", True):
            return False, ""
        if ped.devil_cost > 0:
            can = (
                cp.max_hp >= ped.devil_cost * 2
                or cp.soul_hp >= 4
                or cp.black_hp >= 4
                or cp.hero_id == "lost"
            )
            return can, tr("pickup_cost_devil").format(cost=ped.devil_cost)
        if ped.price > 0:
            cost = max(1, ped.price // 2) if cp.has_steam_sale else ped.price
            return cp.coins >= cost, tr("pickup_cost_coins").format(cost=cost)
        return True, ""

    def _open_pedestal_prompt(self, ped, cp):
        can_afford, cost_text = self._check_pedestal_affordability(ped, cp)
        self.touch.reset()
        self.pending_pedestal_prompt = {
            "pedestal": ped,
            "player": cp,
            "selected": 0 if can_afford else 1,
            "can_afford": can_afford,
            "cost_text": cost_text,
        }

    def _confirm_pedestal_pickup(self):
        prompt = self.pending_pedestal_prompt
        if not prompt:
            return False
        ped = prompt.get("pedestal")
        cp = prompt.get("player")
        if ped is None or cp is None or not getattr(ped, "alive", True):
            self.pending_pedestal_prompt = None
            return False
        can_afford, _ = self._check_pedestal_affordability(ped, cp)
        if not can_afford:
            play_sound("hurt")
            return False
        if ped.devil_cost > 0:
            if cp.max_hp >= ped.devil_cost * 2:
                cp.max_hp -= ped.devil_cost * 2
                cp.hp = min(cp.hp, cp.max_hp)
            elif cp.soul_hp >= 4:
                cp.soul_hp -= 4
            elif cp.black_hp >= 4:
                cp.black_hp -= 4
            elif cp.hero_id == "lost":
                pass
            else:
                return False
            self.account_manager.record_stat("devil_deals", 1)
        elif ped.price > 0:
            cost = max(1, ped.price // 2) if cp.has_steam_sale else ped.price
            if cp.coins < cost:
                return False
            cp.coins -= cost
            self.account_manager.record_stat("shop_purchases", 1)
        cp.apply_item(ped.item)
        self.account_manager.record_stat("items_collected", 1)
        self._record_peak_player_stats(cp)
        self.achievement_manager.evaluate()
        self.ui.show_banner(tr_item_name(ped.item).upper(), tr_item_desc(ped.item), duration=135.0, item=ped.item)
        ped.alive = False
        if self.current_room is not None:
            self.current_room.pedestals = [p for p in self.current_room.pedestals if p.alive]
        self._dismissed_pedestals.discard(id(ped))
        self.pending_pedestal_prompt = None
        return True

    def _cancel_pedestal_pickup(self):
        prompt = self.pending_pedestal_prompt
        if prompt and prompt.get("pedestal") is not None:
            self._dismissed_pedestals.add(id(prompt["pedestal"]))
        self.pending_pedestal_prompt = None

    def _handle_pickup_prompt_event(self, event):
        prompt = self.pending_pedestal_prompt
        if not prompt:
            return False
        _, confirm_rc, cancel_rc = self.ui.get_pickup_confirm_rects(self.touch.is_active())
        if event.type == pygame.FINGERDOWN:
            pos = self._finger_to_logical(event.x, event.y)
            if confirm_rc.inflate(10, 10).collidepoint(pos[0], pos[1]):
                self._confirm_pedestal_pickup()
            elif cancel_rc.inflate(10, 10).collidepoint(pos[0], pos[1]):
                self._cancel_pedestal_pickup()
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._is_touch_mouse_event(event):
                return True
            mx_pos, my_pos = self._to_logical_pos(event.pos)
            if confirm_rc.collidepoint(mx_pos, my_pos):
                self._confirm_pedestal_pickup()
            elif cancel_rc.collidepoint(mx_pos, my_pos):
                self._cancel_pedestal_pickup()
            return True
        if event.type == pygame.MOUSEMOTION:
            if self._is_touch_mouse_event(event):
                return True
            mx_pos, my_pos = self._to_logical_pos(event.pos)
            if confirm_rc.collidepoint(mx_pos, my_pos) and prompt.get("can_afford", True):
                prompt["selected"] = 0
            elif cancel_rc.collidepoint(mx_pos, my_pos):
                prompt["selected"] = 1
            return True
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE, pygame.K_n):
                self._cancel_pedestal_pickup()
                return True
            if event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_a, pygame.K_d, pygame.K_TAB):
                if prompt.get("can_afford", True):
                    prompt["selected"] = 1 - int(prompt.get("selected", 0))
                else:
                    prompt["selected"] = 1
                return True
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_e, pygame.K_y):
                if int(prompt.get("selected", 0)) == 0 and prompt.get("can_afford", True):
                    self._confirm_pedestal_pickup()
                else:
                    self._cancel_pedestal_pickup()
                return True
            return True
        return False

    def _select_or_use_inventory_slot(self, slot_1_to_9, trigger_if_already_selected=True, cp=None):
        target_p = cp if cp is not None else self.player
        if target_p is None:
            return None
        prev_idx = target_p.selected_inv_idx
        prev_act_id = target_p.active_item["id"] if target_p.active_item else None
        picked = target_p.select_inventory_slot(slot_1_to_9)
        if picked is None:
            return None
        if picked.get("type") == "active":
            already_sel = (prev_idx == target_p.selected_inv_idx and prev_act_id == picked.get("id"))
            if trigger_if_already_selected and (already_sel or len(target_p.active_items) <= 1):
                self._trigger_active_item(target_p)
            else:
                self.ui.show_banner(
                    tr_item_name(picked).upper(),
                    f"{tr('inv_equipped_hint')} · {tr_item_desc(picked)}",
                    duration=85.0,
                    item=picked,
                )
        else:
            self.ui.show_banner(
                tr_item_name(picked).upper(),
                f"[{tr('inv_passive_hint')}] {tr_item_desc(picked)}",
                duration=85.0,
                item=picked,
            )
        return picked

    def _find_nearby_computer(self, room, cp):
        if room is None or cp is None:
            return None
        best = None
        best_d = 1e9
        max_reach = float(getattr(cp, "radius", 15.0)) + 58.0
        for mac in getattr(room, "machines", ()):
            if not getattr(mac, "alive", True) or getattr(mac, "kind", "") != "computer_terminal":
                continue
            d = math.hypot(mac.x - cp.x, mac.y - cp.y)
            if d <= max_reach and d < best_d:
                best_d = d
                best = mac
        return best

    def _get_nearby_computer_hint(self, room, cp):
        mac = self._find_nearby_computer(room, cp)
        if mac is None:
            return None
        if getattr(mac, "playing", False):
            tid = int(getattr(mac, "track_idx", 0)) % max(1, len(COMPUTER_TRACKS))
            return tr("computer_prompt").format(track=tr(f"comp_track_{tid}"))
        return tr("computer_off_prompt")

    def _interact_computer_terminal(self, room, cp):
        mac = self._find_nearby_computer(room, cp)
        if mac is None:
            return False
        if mac.cycle_track():
            play_sound("computer_switch" if mac.playing else "computer_beep")
            self.account_manager.record_stat("computer_uses", 1)
            if mac.playing:
                tid = int(mac.track_idx) % max(1, len(COMPUTER_TRACKS))
                self.account_manager.record_stat("computer_tracks_heard", str(tid), mode="append_unique")
                self.ui.show_banner(
                    "ARCHIVE TERMINAL" if GAME_SETTINGS.get("language", "ru") == "en" else "АРХИВНЫЙ ТЕРМИНАЛ",
                    tr("computer_playing_fmt").format(track=tr(f"comp_track_{tid}")),
                    duration=65.0,
                )
            else:
                self.ui.show_banner(
                    "ARCHIVE TERMINAL" if GAME_SETTINGS.get("language", "ru") == "en" else "АРХИВНЫЙ ТЕРМИНАЛ",
                    tr("computer_off"),
                    duration=55.0,
                )
            self.achievement_manager.evaluate()
            return True
        return False

    def _sync_room_computer_audio(self, room, listener_p):
        if room is None or listener_p is None:
            stop_computer_audio()
            return
        best = None
        best_d2 = 1e12
        for mac in getattr(room, "machines", ()):
            if not getattr(mac, "alive", True) or getattr(mac, "kind", "") != "computer_terminal":
                continue
            if not getattr(mac, "playing", False):
                continue
            d2 = (mac.x - listener_p.x) ** 2 + (mac.y - listener_p.y) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best = mac
        if best is not None:
            update_computer_audio(True, best.track_idx, best.x, best.y, listener_p.x, listener_p.y)
        else:
            stop_computer_audio()

    def _update_playing(self, dt):
        self.ui.update(dt)
        if self.pending_pedestal_prompt is not None:
            ped = self.pending_pedestal_prompt.get("pedestal")
            if ped is None or not getattr(ped, "alive", True):
                self.pending_pedestal_prompt = None
            else:
                if self.lan_host.running and self.lan_host.client_connected:
                    net_p = self.lan_host.consume_client_input()
                    if net_p is not None:
                        if net_p.get("confirm"):
                            self._confirm_pedestal_pickup()
                        elif net_p.get("cancel"):
                            self._cancel_pedestal_pickup()
                    self.lan_net_tick = (self.lan_net_tick + 1) % 10000
                    if self.lan_net_tick % 4 == 0:
                        self._push_lan_snapshot()
                return
        sim_dt = dt * self.timescale
        all_targets_dash = [e for e in self.current_room.enemies if e.alive] + [b for b in self.current_room.bosses if b.alive]
        if self.lan_host.running and self.lan_host.client_connected:
            if not self.coop_enabled or self.player2 is None:
                self.coop_enabled = True
                if self.player is not None:
                    self.player.player_tag = "P1"
                p2_hid = getattr(self.lan_host, "client_hero_id", "") or HERO_ROSTER[self.selected_p2_hero_idx % len(HERO_ROSTER)]["id"]
                spawn_x = (self.player.x + 36) if self.player else (PLAYABLE_LEFT + PLAYABLE_RIGHT) // 2
                spawn_y = self.player.y if self.player else (PLAYABLE_TOP + PLAYABLE_BOTTOM) // 2
                self.player2 = Player(spawn_x, spawn_y, p2_hid)
                self.player2.player_tag = "P2"
                self._nudge_clear_of_obstacles(self.player2, self.current_room)
                mod_manager.dispatch_player_init(self.player2)
        p2_active = bool(self.coop_enabled and self.player2 is not None and not self.player2.is_dead())
        p1_alive = self.player is not None and not self.player.is_dead()

        if self.console.open:
            mx = my = ax = ay = 0
            p2_mx = p2_my = p2_ax = p2_ay = 0
        else:
            keys = pygame.key.get_pressed()
            k_up = get_keybind("up")
            k_dn = get_keybind("down")
            k_lt = get_keybind("left")
            k_rt = get_keybind("right")
            k_fup = get_keybind("fire_up")
            k_fdn = get_keybind("fire_down")
            k_flt = get_keybind("fire_left")
            k_frt = get_keybind("fire_right")
            k_dash = get_keybind("dash")
            mx = (1 if keys[k_rt] else 0) - (1 if keys[k_lt] else 0)
            my = (1 if keys[k_dn] else 0) - (1 if keys[k_up] else 0)
            ax = (1 if keys[k_frt] else 0) - (1 if keys[k_flt] else 0)
            ay = (1 if keys[k_fdn] else 0) - (1 if keys[k_fup] else 0)

            if self.touch.is_active() and p1_alive:
                tmx, tmy = self.touch.move_vec
                if mx == 0 and my == 0 and (abs(tmx) > 0.01 or abs(tmy) > 0.01):
                    mx, my = tmx, tmy
                tax, tay = self.touch.aim_dir
                if ax == 0 and ay == 0 and (tax != 0 or tay != 0):
                    ax, ay = tax, tay
                if self.touch.dash_pressed and not self.editor.active:
                    if self.player.try_dash(mx, my, self.particles, tears=self.tears, enemies=all_targets_dash):
                        self.account_manager.record_stat("dashes_used", 1)
                t_actions = self.touch.consume_actions()
                if t_actions.get("pause"):
                    self.touch.reset()
                    self.pause_idx = 0
                    self.state = "PAUSED"
                    return
                if t_actions.get("jump") and not self.editor.active:
                    if self.player.try_jump(mx, my, self.particles):
                        self.account_manager.record_stat("jumps_used", 1)
                if t_actions.get("stealth") and not self.editor.active:
                    if self.player.try_stealth(self.particles):
                        self.account_manager.record_stat("stealth_uses", 1)
                if t_actions.get("melee") and not self.editor.active:
                    self._trigger_melee(self.player, ax, ay)
                if t_actions.get("bomb") and self.player.can_place_bomb():
                    self.player.bombs -= 1
                    self.player.trigger_bomb_cd()
                    self.bombs.append(ActiveBomb(self.player.x, self.player.y, self.player.has_sad_bombs, owner=self.player))
                    self.account_manager.record_stat("bombs_used", 1)
                if t_actions.get("relic"):
                    self._trigger_active_item(self.player)
                if t_actions.get("interact") and not self.editor.active:
                    self._interact_computer_terminal(self.current_room, self.player)

            p1_dash_keys = keys[k_dash] or keys[pygame.K_c] or (not self.coop_enabled and keys[pygame.K_RSHIFT])
            if p1_alive and p1_dash_keys and not self.editor.active:
                if self.player.try_dash(mx, my, self.particles, tears=self.tears, enemies=all_targets_dash):
                    self.account_manager.record_stat("dashes_used", 1)

            if p2_active:
                p2_mx = (1 if keys[pygame.K_l] else 0) - (1 if keys[pygame.K_j] else 0)
                p2_my = (1 if keys[pygame.K_k] else 0) - (1 if keys[pygame.K_i] else 0)
                p2_right = keys[pygame.K_KP6] or keys[getattr(pygame, "K_KP_6", pygame.K_KP6)]
                p2_left = keys[pygame.K_KP4] or keys[getattr(pygame, "K_KP_4", pygame.K_KP4)]
                p2_up = keys[pygame.K_KP8] or keys[getattr(pygame, "K_KP_8", pygame.K_KP8)]
                p2_down = keys[pygame.K_KP5] or keys[getattr(pygame, "K_KP_5", pygame.K_KP5)] or keys[pygame.K_KP2] or keys[getattr(pygame, "K_KP_2", pygame.K_KP2)]
                p2_ax = (1 if p2_right else 0) - (1 if p2_left else 0)
                p2_ay = (1 if p2_down else 0) - (1 if p2_up else 0)
                if p2_ax == 0 and p2_ay == 0 and (keys[pygame.K_RCTRL] or keys[pygame.K_SLASH]):
                    if all_targets_dash:
                        nt = min(all_targets_dash, key=lambda t: (t.x - self.player2.x) ** 2 + (t.y - self.player2.y) ** 2)
                        dx_t, dy_t = nt.x - self.player2.x, nt.y - self.player2.y
                        d_t = math.hypot(dx_t, dy_t) or 1.0
                        p2_ax, p2_ay = dx_t / d_t, dy_t / d_t
                    else:
                        p2_ax, p2_ay = self.player2.facing
                if keys[pygame.K_RSHIFT] and not self.editor.active:
                    self.player2.try_dash(p2_mx, p2_my, self.particles, tears=self.tears, enemies=all_targets_dash)

                if self.lan_host.running and self.lan_host.client_connected:
                    net_in = self.lan_host.consume_client_input()
                    if net_in is not None:
                        if p2_mx == 0 and p2_my == 0 and (abs(net_in["mx"]) > 0.01 or abs(net_in["my"]) > 0.01):
                            p2_mx, p2_my = net_in["mx"], net_in["my"]
                        if p2_ax == 0 and p2_ay == 0 and (abs(net_in["ax"]) > 0.01 or abs(net_in["ay"]) > 0.01):
                            p2_ax, p2_ay = net_in["ax"], net_in["ay"]
                        if net_in.get("dash") and not self.editor.active:
                            self.player2.try_dash(p2_mx, p2_my, self.particles, tears=self.tears, enemies=all_targets_dash)
                        if net_in.get("jump") and not self.editor.active:
                            if self.player2.try_jump(p2_mx, p2_my, self.particles):
                                self.account_manager.record_stat("jumps_used", 1)
                        if net_in.get("stealth") and not self.editor.active:
                            if self.player2.try_stealth(self.particles):
                                self.account_manager.record_stat("stealth_uses", 1)
                        if net_in.get("melee") and not self.editor.active:
                            self._trigger_melee(self.player2, p2_ax, p2_ay)
                        if net_in.get("bomb") and self.player2.can_place_bomb():
                            self.player2.bombs -= 1
                            self.player2.trigger_bomb_cd()
                            self.bombs.append(ActiveBomb(self.player2.x, self.player2.y, self.player2.has_sad_bombs, owner=self.player2))
                            self.account_manager.record_stat("bombs_used", 1)
                        if net_in.get("relic"):
                            self._trigger_active_item(self.player2)
                        if net_in.get("cycle_relic"):
                            if hasattr(self.player2, "cycle_active_item") and self.player2.cycle_active_item(1):
                                play_sound("pickup")
                        if net_in.get("interact") and not self.editor.active:
                            self._interact_computer_terminal(self.current_room, self.player2)
                        for s_num in net_in.get("inv_slots", ()):
                            self._select_or_use_inventory_slot(s_num, trigger_if_already_selected=True, cp=self.player2)
                        for p_delta in net_in.get("inv_pages", ()):
                            if hasattr(self.player2, "cycle_inventory_page"):
                                self.player2.cycle_inventory_page(p_delta)
            else:
                p2_mx = p2_my = p2_ax = p2_ay = 0

        if p1_alive:
            self.player.update(mx, my, self.current_room, self.particles, sim_dt)
            if ax != 0 or ay != 0:
                self.player.shoot(ax, ay, self.tears)
        if p2_active:
            self.player2.update(p2_mx, p2_my, self.current_room, self.particles, sim_dt)
            if p2_ax != 0 or p2_ay != 0:
                self.player2.shoot(p2_ax, p2_ay, self.tears)

        # Jump-Slam landing AoE shockwave check
        for cp in self._get_active_players():
            slam = getattr(cp, "jump_slam_pending", None)
            if slam is not None:
                cp.jump_slam_pending = None
                if isinstance(slam, dict):
                    sx = float(slam.get("x", cp.x))
                    sy = float(slam.get("y", cp.y))
                    s_rad = float(slam.get("radius", 74.0))
                    s_dmg = float(slam.get("damage", 5.0))
                    is_explosive = bool(slam.get("explosive", False))
                else:
                    sx, sy, s_rad, s_dmg = slam
                    is_explosive = False
                self._trigger_shake(6.2 if (cp.jump_empowered or is_explosive) else 4.2, 12.0)
                self.particles.append(RingParticle(sx, sy, int(s_rad), (242, 242, 242), 16, width=2))
                for obs in self.current_room.obstacles:
                    if obs.alive and (obs.kind in ("poop", "urn") or (is_explosive and obs.kind == "rock")) and math.hypot(obs.rect.centerx - sx, obs.rect.centery - sy) <= s_rad:
                        if obs.explode():
                            self.quest_manager.trigger(self, "obstacle_destroyed")
                            self._on_obstacle_shattered(obs)
                for tgt in all_targets_dash:
                    if tgt.alive and math.hypot(tgt.x - sx, tgt.y - sy) <= s_rad + tgt.radius:
                        was_alive_t = tgt.alive
                        dx_s, dy_s = tgt.x - sx, tgt.y - sy
                        d_s = math.hypot(dx_s, dy_s) or 1.0
                        tgt.take_damage(s_dmg, (dx_s / d_s) * 4.5, (dy_s / d_s) * 4.5)
                        self.quest_manager.trigger(self, "jump_slam")
                        if not tgt.alive and was_alive_t:
                            self.account_manager.record_stat("slam_kills", 1)

        mod_manager.dispatch_update(self, sim_dt)

        alive_players = self._get_active_players()
        if not alive_players:
            self._on_run_end(won=False)
            return

        # Floor spikes damage check for grounded players
        for obs in self.current_room.obstacles:
            if not obs.alive or obs.kind != "spike":
                continue
            hit_rect = obs.rect.inflate(-8, -8)
            for cp in alive_players:
                if not cp.has_effective_flight() and cp.air_z <= 8.0 and not cp.noclip:
                    p_box = pygame.Rect(
                        int(cp.x - cp.radius * 0.72),
                        int(cp.y - cp.radius * 0.72),
                        max(6, int(cp.radius * 1.44)),
                        max(6, int(cp.radius * 1.44)),
                    )
                    if hit_rect.colliderect(p_box):
                        if cp.take_damage(1):
                            self._trigger_shake(4.5, 10.0)
                            self.floor_took_damage = True
                            self.room_took_damage = True

        if any(cp.has_placenta and cp.hp < cp.max_hp for cp in alive_players):
            self.placenta_tick += sim_dt
            if self.placenta_tick >= 480.0:
                self.placenta_tick = 0.0
                for cp in alive_players:
                    if cp.has_placenta and cp.hp < cp.max_hp:
                        cp.hp = min(cp.max_hp, cp.hp + 1)

        if self.game_mode == "fading_light":
            lead_p = self._primary_alive_player() or self.player
            lead_p.lantern_fuel = max(0.14, lead_p.lantern_fuel - 0.00055 * sim_dt)
            for tx, ty in self.current_room.torch_positions:
                if any(math.hypot(cp.x - tx, cp.y - ty) < 76.0 for cp in alive_players):
                    lead_p.lantern_fuel = min(lead_p.lantern_bonus * 0.85, max(lead_p.lantern_fuel, lead_p.lantern_fuel + 0.004 * sim_dt))
            for cp in alive_players:
                cp.lantern_fuel = lead_p.lantern_fuel
            if lead_p.lantern_fuel <= 0.145:
                self.darkness_tick += sim_dt
                if self.darkness_tick >= 150.0:
                    self.darkness_tick = 0.0
                    for cp in alive_players:
                        if cp.take_damage(1):
                            self.floor_took_damage = True
                            self.room_took_damage = True
            else:
                self.darkness_tick = 0.0

        was_alive = {id(obs) for obs in self.current_room.obstacles if obs.alive and obs.kind in ("poop", "urn", "barrier", "turret", "rock")}

        for b_obj in self.bombs:
            b_obj.update(sim_dt)
            if not b_obj.alive:
                self._explode_bomb(b_obj.x, b_obj.y, b_obj.sad_bombs, owner=getattr(b_obj, "owner", None))
        self.bombs = [b for b in self.bombs if b.alive]

        all_targets = [e for e in self.current_room.enemies if e.alive] + [b for b in self.current_room.bosses if b.alive]
        primary_p = self._primary_alive_player() or self.player

        split_spawned = []
        for t_obj in self.tears:
            t_obj.update(self.current_room, all_targets, sim_dt, (primary_p.x, primary_p.y))
            if getattr(t_obj, "should_explode", False):
                t_obj.should_explode = False
                self._detonate_tear(t_obj, all_targets)
            if t_obj.holy and t_obj.alive:
                t_obj._holy_cd = getattr(t_obj, "_holy_cd", 0.0) - sim_dt
                if t_obj._holy_cd <= 0.0:
                    t_obj._holy_cd = 10.0
                    aura_dmg = max(0.8, t_obj.get_effective_damage() * 0.28)
                    for tgt in all_targets:
                        if tgt.alive and math.hypot(tgt.x - t_obj.x, tgt.y - t_obj.y) <= t_obj.radius + 28.0 + tgt.radius:
                            tgt.take_damage(aura_dmg)
            if not t_obj.alive:
                if t_obj.splitting:
                    t_obj.splitting = False
                    split_spawned.extend(self._spawn_split_tears(t_obj))
                continue
            for tgt in all_targets:
                if not tgt.alive or id(tgt) in t_obj.hit_ids:
                    continue
                if math.hypot(tgt.x - t_obj.x, tgt.y - t_obj.y) <= tgt.radius + t_obj.radius:
                    t_obj.hit_ids.add(id(tgt))
                    dmg = t_obj.get_effective_damage()
                    if getattr(tgt, "weaken_timer", 0.0) > 0.0:
                        dmg *= 1.35
                    was_alive_t = tgt.alive
                    tgt.take_damage(dmg, t_obj.vx * 0.25, t_obj.vy * 0.25)
                    if not tgt.alive and was_alive_t and getattr(t_obj, "ambush", False):
                        self.account_manager.record_stat("ambush_kills", 1)
                    if t_obj.poison:
                        tgt.poison_timer = 150.0
                    if getattr(t_obj, "chain_arc", False):
                        arcs = 0
                        for tgt2 in all_targets:
                            if tgt2 is tgt or not tgt2.alive or id(tgt2) in t_obj.hit_ids:
                                continue
                            if math.hypot(tgt2.x - tgt.x, tgt2.y - tgt.y) <= 160.0:
                                tgt2.take_damage(max(1.2, dmg * 0.48))
                                self.particles.append(LightningArcParticle(tgt.x, tgt.y, tgt2.x, tgt2.y, 10))
                                arcs += 1
                                if arcs >= 2:
                                    break
                    if getattr(t_obj, "explode_on_death", False) or getattr(t_obj, "explosive", False):
                        t_obj.should_explode = False
                        self._detonate_tear(t_obj, all_targets)
                    play_sound("hit")
                    for _ in range(4):
                        ang = random.uniform(0.0, math.pi * 2.0)
                        self.particles.append(SplashParticle(t_obj.x, t_obj.y, math.cos(ang) * 2.4, math.sin(ang) * 2.4, (240, 240, 240), 2, 12))
                    if t_obj.splitting:
                        t_obj.splitting = False
                        split_spawned.extend(self._spawn_split_tears(t_obj, exclude_id=id(tgt)))
                    if not t_obj.piercing:
                        t_obj.alive = False
                        break

        self.tears = [t for t in self.tears if t.alive] + split_spawned
        if len(self.tears) > 160:
            self.tears = self.tears[-140:]

        for obs in self.current_room.obstacles:
            if not obs.alive and id(obs) in was_alive:
                self._on_obstacle_shattered(obs)

        orb_pts = []
        wisp_pts = []
        for cp in alive_players:
            orb_pts.extend(cp.get_orbital_positions())
            wisp_pts.extend(cp.get_wisp_positions())
        ai_frozen = self.editor.active and self.editor.freeze_ai
        any_slow_proj = any(cp.slow_projectiles for cp in alive_players)
        proj_dt = 0.0 if ai_frozen else (sim_dt * 0.56 if any_slow_proj else sim_dt)

        if not ai_frozen:
            if hasattr(self.current_room, "update_turrets"):
                self.current_room.update_turrets(sim_dt, alive_players, self.enemy_projectiles)
            for pr in self.enemy_projectiles:
                np = self._nearest_alive_player(pr.x, pr.y)
                pr.update(self.current_room, proj_dt, (np.x, np.y))
                if not pr.alive:
                    if getattr(pr, "just_landed", False):
                        pr.just_landed = False
                        self.particles.append(RingParticle(pr.x, pr.y, int(getattr(pr, "blast_radius", 52)), (236, 236, 236), 14, width=2))
                        br_p = float(getattr(pr, "blast_radius", 52.0))
                        for cp in alive_players:
                            if cp.air_z <= 8.0 and math.hypot(cp.x - pr.x, cp.y - pr.y) <= br_p + cp.radius * 0.6:
                                if cp.take_damage(pr.damage):
                                    self._trigger_shake(5.0, 12.0)
                                    self.floor_took_damage = True
                                    self.room_took_damage = True
                    continue
                blocked = False
                for ox, oy in orb_pts + wisp_pts:
                    if math.hypot(pr.x - ox, pr.y - oy) <= pr.radius + 9.0:
                        pr.alive = False
                        blocked = True
                        break
                if blocked:
                    continue
                for cp in alive_players:
                    if cp.air_z <= 8.0 and math.hypot(pr.x - cp.x, pr.y - cp.y) <= pr.radius + cp.radius - 2:
                        if cp.take_damage(pr.damage):
                            self._trigger_shake(5.5, 12.0)
                            self.floor_took_damage = True
                            self.room_took_damage = True
                        pr.alive = False
                        break
        self.enemy_projectiles = [pr for pr in self.enemy_projectiles if pr.alive]
        if len(self.enemy_projectiles) > 120:
            self.enemy_projectiles = self.enemy_projectiles[-100:]

        for cp in alive_players:
            for ally in cp.allies:
                ally.update(cp, all_targets, sim_dt)
            cp.allies = [a for a in cp.allies if a.alive]

        if not ai_frozen:
            for e in self.current_room.enemies:
                if e.alive:
                    e_dt = self._tick_enemy_statuses(e, sim_dt)
                    if e.alive:
                        tgt_p = self._nearest_alive_player(e.x, e.y)
                        e.update(tgt_p, self.current_room, self.enemy_projectiles, e_dt, tgt_p.has_skatole)
                # Drain pending enemy AoE attacks before dead removal (e.g. cinder bomber explosion on death)
                ps = getattr(e, "pending_slam", None)
                if ps is not None:
                    e.pending_slam = None
                    sx, sy, s_r = ps[0], ps[1], ps[2]
                    s_dmg = ps[3] if len(ps) > 3 else 1
                    self._trigger_shake(5.5, 12.0)
                    self.particles.append(RingParticle(sx, sy, int(s_r), (236, 236, 236), 16, width=2))
                    for cp in alive_players:
                        if cp.air_z <= 8.0 and math.hypot(cp.x - sx, cp.y - sy) <= s_r + cp.radius * 0.5:
                            if cp.take_damage(s_dmg):
                                self.floor_took_damage = True
                                self.room_took_damage = True
                pe = getattr(e, "pending_explosion", None)
                if pe is not None:
                    e.pending_explosion = None
                    ex, ey, er = pe[0], pe[1], pe[2]
                    self._trigger_shake(7.0, 14.0)
                    self.particles.append(RingParticle(ex, ey, int(er), (244, 244, 244), 18, width=3))
                    for _ in range(12):
                        ang = random.uniform(0.0, math.pi * 2.0)
                        spd = random.uniform(1.6, 4.8)
                        self.particles.append(SplashParticle(ex, ey, math.cos(ang) * spd, math.sin(ang) * spd, (226, 226, 226), 3, 18))
                    for obs in self.current_room.obstacles:
                        if obs.alive and obs.kind in ("poop", "urn", "barrier", "turret", "rock") and math.hypot(obs.rect.centerx - ex, obs.rect.centery - ey) <= er:
                            if obs.explode():
                                self._on_obstacle_shattered(obs)
                    for cp in alive_players:
                        if math.hypot(cp.x - ex, cp.y - ey) <= er + cp.radius * 0.5:
                            if cp.take_damage(1):
                                self.floor_took_damage = True
                                self.room_took_damage = True
                pw = getattr(e, "pending_shockwave", None)
                if pw is not None:
                    e.pending_shockwave = None
                    wx, wy, wr = pw[0], pw[1], pw[2]
                    self.particles.append(RingParticle(wx, wy, int(wr), (220, 220, 220), 16, width=2))
                    for cp in alive_players:
                        if cp.air_z <= 8.0 and math.hypot(cp.x - wx, cp.y - wy) <= wr + cp.radius * 0.5:
                            if cp.take_damage(1):
                                self._trigger_shake(4.5, 10.0)
                                self.floor_took_damage = True
                                self.room_took_damage = True

                if not e.alive:
                    continue
                for cp in alive_players:
                    if cp.air_z <= 8.0 and math.hypot(e.x - cp.x, e.y - cp.y) <= e.radius + cp.radius - 2:
                        if cp.take_damage(1):
                            self._trigger_shake(5.0, 12.0)
                            self.floor_took_damage = True
                            self.room_took_damage = True
                orb_dmg = 4.0 if any(cp.eclipse_aura for cp in alive_players) else 2.5
                if getattr(e, "orbital_hit_cd", 0.0) <= 0:
                    for ox, oy in orb_pts:
                        if math.hypot(e.x - ox, e.y - oy) <= e.radius + 9.0:
                            e.take_damage(orb_dmg)
                            e.orbital_hit_cd = 12.0
                            break

        dead_enemies = [e for e in self.current_room.enemies if not e.alive]
        spawned_children = []
        if dead_enemies:
            primary_p.kills += len(dead_enemies)
            self.quest_manager.trigger(self, "kill", len(dead_enemies))
            self.account_manager.record_stat("kills", len(dead_enemies))
            if self.game_mode == "fading_light":
                refill_p = primary_p
                refill_p.lantern_fuel = min(refill_p.lantern_bonus + 0.3, refill_p.lantern_fuel + 0.09 * len(dead_enemies))
                for cp in alive_players:
                    cp.lantern_fuel = refill_p.lantern_fuel
            for de in dead_enemies:
                self.particles.append(RingParticle(de.x, de.y, 26, (236, 236, 236), 12, 2))
                if primary_p.hero_id == "keeper" and random.random() < 0.32:
                    px = clamp(de.x + random.uniform(-10, 10), PLAYABLE_LEFT + 22, PLAYABLE_RIGHT - 22)
                    py = clamp(de.y + random.uniform(-10, 10), PLAYABLE_TOP + 22, PLAYABLE_BOTTOM - 22)
                    self.current_room.pickups.append(Pickup(px, py, "coin"))
                if hasattr(de, "get_split_children"):
                    spawned_children.extend(de.get_split_children())
            self.achievement_manager.evaluate()
        self.current_room.enemies = [e for e in self.current_room.enemies if e.alive] + spawned_children

        new_bosses = []
        orb_dmg = 4.0 if any(cp.eclipse_aura for cp in alive_players) else 2.5
        for b in self.current_room.bosses:
            if not b.alive:
                if hasattr(b, "cleanup_arena"):
                    b.cleanup_arena(self.current_room)
                primary_p.kills += 1
                self.quest_manager.trigger(self, "boss_kill")
                self.account_manager.record_stat("kills", 1)
                self.account_manager.record_stat("bosses_killed", 1)
                self.account_manager.record_stat("boss_types_killed", b.boss_key, mode="append_unique")
                self.achievement_manager.evaluate()
                if self.game_mode == "fading_light":
                    refill_p = primary_p
                    refill_p.lantern_fuel = min(refill_p.lantern_bonus + 0.4, refill_p.lantern_fuel + 0.45)
                    for cp in alive_players:
                        cp.lantern_fuel = refill_p.lantern_fuel
                self.particles.append(RingParticle(b.x, b.y, 64, (246, 246, 246), 18, 3))
                children = b.get_split_children()
                new_bosses.extend(children)
                continue
            if not ai_frozen:
                b_dt = self._tick_enemy_statuses(b, sim_dt)
                if not b.alive:
                    if hasattr(b, "cleanup_arena"):
                        b.cleanup_arena(self.current_room)
                    primary_p.kills += 1
                    self.quest_manager.trigger(self, "boss_kill")
                    self.account_manager.record_stat("kills", 1)
                    self.account_manager.record_stat("bosses_killed", 1)
                    self.account_manager.record_stat("boss_types_killed", b.boss_key, mode="append_unique")
                    self.achievement_manager.evaluate()
                    new_bosses.extend(b.get_split_children())
                    continue
                tgt_b = self._nearest_alive_player(b.x, b.y)
                b.update(tgt_b, self.current_room, self.enemy_projectiles, self.current_room.enemies, b_dt)
                if hasattr(b, "check_beam_hits"):
                    beam_hits = b.check_beam_hits(alive_players)
                    if beam_hits:
                        self._trigger_shake(7.0, 15.0)
                        self.floor_took_damage = True
                        self.room_took_damage = True
                if getattr(b, "orbital_hit_cd", 0.0) <= 0:
                    for ox, oy in orb_pts:
                        if math.hypot(b.x - ox, b.y - oy) <= b.radius + 9.0:
                            b.take_damage(orb_dmg)
                            b.orbital_hit_cd = 12.0
                            break
                if not b.airborne:
                    for cp in alive_players:
                        if cp.air_z <= 8.0 and math.hypot(b.x - cp.x, b.y - cp.y) <= b.radius + cp.radius - 3:
                            if b.steals_coins and cp.coins > 0 and cp.invuln_timer <= 0:
                                cp.coins -= 1
                            if cp.take_damage(1):
                                self._trigger_shake(6.5, 14.0)
                                self.floor_took_damage = True
                                self.room_took_damage = True
            new_bosses.append(b)
        self.current_room.bosses = new_bosses

        if self.game_mode == "endless_abyss" and not self.editor.active:
            if not self.current_room.enemies and not self.current_room.bosses:
                if self.wave_break_timer <= 0:
                    self.wave_break_timer = 110.0
                    cx = (PLAYABLE_LEFT + PLAYABLE_RIGHT) // 2
                    cy = (PLAYABLE_TOP + PLAYABLE_BOTTOM) // 2
                    self._revive_fallen_coop_player(0.5)
                    for cp in self._get_active_players():
                        cp.add_charge(1)
                    self.current_room.pickups.append(Pickup(cx - 48, cy + 40, random.choice(["heart", "soul_heart", "coin", "battery"])))
                    if self.wave_num % 2 == 0:
                        if self.floor_pedestals_spawned < MAX_ARTIFACTS_PER_FLOOR:
                            seen_endless = set(self.player.collected_ids)
                            if self.coop_enabled and self.player2 is not None:
                                seen_endless |= set(self.player2.collected_ids)
                            self.current_room.pedestals.append(ItemPedestal(cx, cy - 30, get_random_item(seen_endless, "passive")))
                            self.floor_pedestals_spawned += 1
                        else:
                            self.current_room.pickups.append(Pickup(cx, cy - 30, random.choice(["soul_heart", "battery", "nickel"])))
                    self.account_manager.record_stat("best_wave", self.wave_num, mode="max")
                    self.achievement_manager.evaluate()
                    self.ui.show_banner(f"{tr('wave_label')} {self.wave_num}", "ВОЛНА ЗАЧИЩЕНА" if GAME_SETTINGS["language"] == "ru" else "WAVE CLEARED", 90.0)
                else:
                    self.wave_break_timer -= sim_dt
                    if self.wave_break_timer <= 0:
                        self.wave_num += 1
                        self._spawn_endless_wave(self.wave_num)
                        self.ui.show_banner(f"{tr('wave_label')} {self.wave_num}", tr_mode(self.game_mode), 95.0)
        elif not self.current_room.cleared and not self.current_room.enemies and not self.current_room.bosses and not self.editor.active:
            self.current_room.cleared = True
            if not self.room_took_damage:
                self.account_manager.record_stat("no_damage_rooms", 1)
                if self.current_room.room_type == "boss":
                    self.account_manager.record_stat("boss_flawless", 1)
            alive_cls = self._get_active_players()
            if any((cp.hp + cp.soul_hp + cp.black_hp) <= 2 for cp in alive_cls):
                self.account_manager.record_stat("low_hp_clutches", 1)
            for cp in alive_cls:
                self._record_peak_player_stats(cp)
            self.achievement_manager.evaluate()
            self._check_hero_unlocks()
            play_sound("door")
            self._revive_fallen_coop_player(0.5)
            for cp in self._get_active_players():
                cp.add_charge(1)
            mod_manager.dispatch_room_clear(self.current_room, self.player, self.player2)
            room_owners = self._get_active_players() or [self.player]
            anchor_p = room_owners[0]
            if any(cp.has_relic for cp in room_owners) and random.random() < 0.35:
                px = clamp(anchor_p.x + 28, PLAYABLE_LEFT + 22, PLAYABLE_RIGHT - 22)
                py = clamp(anchor_p.y, PLAYABLE_TOP + 22, PLAYABLE_BOTTOM - 22)
                self.current_room.pickups.append(Pickup(px, py, "soul_heart"))
            if any(cp.has_dark_bum for cp in room_owners) and random.random() < 0.30:
                px = clamp(anchor_p.x - 28, PLAYABLE_LEFT + 22, PLAYABLE_RIGHT - 22)
                py = clamp(anchor_p.y, PLAYABLE_TOP + 22, PLAYABLE_BOTTOM - 22)
                self.current_room.pickups.append(Pickup(px, py, random.choice(["soul_heart", "black_heart"])))
            if any(cp.has_moms_key for cp in room_owners) and random.random() < 0.25:
                px = clamp(anchor_p.x, PLAYABLE_LEFT + 22, PLAYABLE_RIGHT - 22)
                py = clamp(anchor_p.y + 28, PLAYABLE_TOP + 22, PLAYABLE_BOTTOM - 22)
                self.current_room.pickups.append(Pickup(px, py, "key"))
            if self.current_room.room_type == "boss":
                cx = (PLAYABLE_LEFT + PLAYABLE_RIGHT) // 2
                cy = (PLAYABLE_TOP + PLAYABLE_BOTTOM) // 2
                if self.floor_level >= TARGET_FLOOR_COUNT and self.game_mode != "free_roam":
                    self.current_room.trapdoor_rect = pygame.Rect(cx - 114, cy - 26, 52, 52)
                    self.current_room.victory_portal_rect = pygame.Rect(cx + 62, cy - 26, 52, 52)
                    lang = GAME_SETTINGS.get("language", "ru")
                    sub_b = tr("boss_rush_next") if self.game_mode == "boss_rush" else (
                        "Врата Рассвета (справа) или Бездна (слева)" if lang == "ru" else "Dawn Portal (Right) or Deeper Abyss (Left)"
                    )
                    self.ui.show_banner("СТРАЖ ПОВЕРЖЕН" if lang == "ru" else "WARDEN VANQUISHED", sub_b, 160.0)
                else:
                    self.current_room.trapdoor_rect = pygame.Rect(cx - 26, cy - 26, 52, 52)
                    if self.game_mode == "boss_rush":
                        self.ui.show_banner(tr("boss_rush_next"), f"{tr('wave_label')} {self.floor_level + 1}", 130.0)
                seen_boss_ids = set(self.player.collected_ids)
                if self.coop_enabled and self.player2 is not None:
                    seen_boss_ids |= set(self.player2.collected_ids)
                if self.floor_pedestals_spawned < MAX_ARTIFACTS_PER_FLOOR:
                    self.current_room.pedestals.append(ItemPedestal(cx, cy + 56, get_random_item(seen_boss_ids, "passive")))
                    self.floor_pedestals_spawned += 1
                else:
                    self.current_room.pickups.append(Pickup(cx - 18, cy + 56, "soul_heart"))
                    self.current_room.pickups.append(Pickup(cx + 18, cy + 56, "nickel"))
                if random.random() < 0.65:
                    avail_dirs = [d for d in ("N", "E", "W", "S") if d not in self.current_room.doors]
                    if avail_dirs:
                        self.current_room.devil_door = Door(avail_dirs[0], (99, 99), target_type="devil", locked=False)
            elif self.current_room.room_type == "normal" and random.random() < 0.48:
                cx = (PLAYABLE_LEFT + PLAYABLE_RIGHT) // 2
                cy = (PLAYABLE_TOP + PLAYABLE_BOTTOM) // 2
                self.current_room.pickups.append(Pickup(cx, cy, random.choice(["coin", "heart", "bomb", "key"])))

        alive_players = self._get_active_players()
        magnet_active = any(cp.has_effect("magnet") for cp in alive_players)
        extra_pickups = []
        for p_obj in self.current_room.pickups:
            if not p_obj.alive:
                continue
            if magnet_active and p_obj.price == 0:
                np = self._nearest_alive_player(p_obj.x, p_obj.y)
                mdx = np.x - p_obj.x
                mdy = np.y - p_obj.y
                mdist = math.hypot(mdx, mdy)
                if 8.0 < mdist < 240.0:
                    p_obj.x += (mdx / mdist) * 3.8 * sim_dt
                    p_obj.y += (mdy / mdist) * 3.8 * sim_dt
            for cp in alive_players:
                if not p_obj.alive:
                    break
                if math.hypot(p_obj.x - cp.x, p_obj.y - cp.y) > cp.radius + 14.0:
                    continue
                cost = max(1, p_obj.price // 2) if cp.has_steam_sale else p_obj.price
                if p_obj.price > 0 and cp.coins < cost:
                    continue
                if p_obj.kind == "heart":
                    if cp.hp >= cp.max_hp:
                        if p_obj.price == 0 and cp.has_dark_bum:
                            cp.dark_bum_counter += 2
                            p_obj.alive = False
                            play_sound("pickup")
                            while cp.dark_bum_counter >= 3:
                                cp.dark_bum_counter -= 3
                                extra_pickups.append(
                                    Pickup(
                                        clamp(p_obj.x + random.uniform(-16, 16), PLAYABLE_LEFT + 22, PLAYABLE_RIGHT - 22),
                                        clamp(p_obj.y + random.uniform(-16, 16), PLAYABLE_TOP + 22, PLAYABLE_BOTTOM - 22),
                                        random.choice(["soul_heart", "black_heart"]),
                                    )
                                )
                        continue
                    cp.hp = min(cp.max_hp, cp.hp + 2)
                elif p_obj.kind == "half_heart":
                    if cp.hp >= cp.max_hp:
                        if p_obj.price == 0 and cp.has_dark_bum:
                            cp.dark_bum_counter += 1
                            p_obj.alive = False
                            play_sound("pickup")
                            while cp.dark_bum_counter >= 3:
                                cp.dark_bum_counter -= 3
                                extra_pickups.append(
                                    Pickup(
                                        clamp(p_obj.x + random.uniform(-16, 16), PLAYABLE_LEFT + 22, PLAYABLE_RIGHT - 22),
                                        clamp(p_obj.y + random.uniform(-16, 16), PLAYABLE_TOP + 22, PLAYABLE_BOTTOM - 22),
                                        random.choice(["soul_heart", "black_heart"]),
                                    )
                                )
                        continue
                    cp.hp = min(cp.max_hp, cp.hp + 1)
                elif p_obj.kind == "soul_heart":
                    cp.soul_hp += 2
                elif p_obj.kind == "black_heart":
                    cp.black_hp += 2
                elif p_obj.kind in ("coin", "nickel", "dime"):
                    val = 1 if p_obj.kind == "coin" else (5 if p_obj.kind == "nickel" else 10)
                    cp.coins += val
                    self.account_manager.record_stat("coins_collected", val)
                    self._record_peak_player_stats(cp)
                    self.achievement_manager.evaluate()
                    if cp.hero_id == "keeper":
                        cp.keeper_coin_counter += val
                        while cp.keeper_coin_counter >= 5:
                            cp.keeper_coin_counter -= 5
                            cp.soul_hp = min(14, cp.soul_hp + 1)
                elif p_obj.kind == "bomb":
                    cp.bombs += 1
                elif p_obj.kind == "key":
                    cp.keys += 1
                elif p_obj.kind == "battery":
                    cp.recharge_active(full=True)
                    cp.lantern_fuel = min(cp.lantern_bonus + 0.4, cp.lantern_fuel + 0.55)
                if p_obj.price > 0:
                    cp.coins -= cost
                    self.account_manager.record_stat("shop_purchases", 1)
                    self.achievement_manager.evaluate()
                p_obj.alive = False
                play_sound("pickup")
        self.current_room.pickups = [p for p in self.current_room.pickups if p.alive] + extra_pickups

        for ped in self.current_room.pedestals:
            if not ped.alive:
                continue
            pid = id(ped)
            any_close = False
            for cp in alive_players:
                dist_ped = math.hypot(ped.x - cp.x, ped.y - cp.y)
                if dist_ped <= cp.radius + 44.0:
                    any_close = True
                if dist_ped <= cp.radius + 22.0 and pid not in self._dismissed_pedestals:
                    self._open_pedestal_prompt(ped, cp)
                    break
            if not any_close and pid in self._dismissed_pedestals:
                self._dismissed_pedestals.discard(pid)
            if self.pending_pedestal_prompt is not None:
                break
        self.current_room.pedestals = [p for p in self.current_room.pedestals if p.alive]

        for mon in self.current_room.monoliths:
            if mon.alive:
                for cp in alive_players:
                    if math.hypot(mon.x - cp.x, mon.y - cp.y) <= cp.radius + mon.radius:
                        res = mon.interact(cp)
                        if res:
                            self.account_manager.record_stat("monoliths_activated", 1)
                            self.achievement_manager.evaluate()
                            play_sound("pickup")
                            self.ui.show_banner(res[0], res[1], 140.0)
                            break

        for npc in self.current_room.mystical_npcs:
            if npc.alive:
                for cp in alive_players:
                    if math.hypot(npc.x - cp.x, npc.y - cp.y) <= cp.radius + npc.radius:
                        res = npc.interact(cp, self.current_room)
                        if res:
                            play_sound("item")
                            self.ui.show_banner(res[0], res[1], 140.0)
                            break

        for beg in self.current_room.beggars:
            if beg.alive:
                for cp in alive_players:
                    if math.hypot(beg.x - cp.x, beg.y - cp.y) <= cp.radius + beg.radius:
                        res = beg.interact(cp, self.current_room)
                        if res:
                            self.account_manager.record_stat("beggar_uses", 1)
                            self.achievement_manager.evaluate()
                            play_sound("beggar")
                            break

        for mac in self.current_room.machines:
            if mac.alive:
                for cp in alive_players:
                    if math.hypot(mac.x - cp.x, mac.y - cp.y) <= cp.radius + mac.radius:
                        if mac.interact(cp, self.current_room):
                            self.account_manager.record_stat("machine_uses", 1)
                            self.achievement_manager.evaluate()
                        break

        if self.current_room.sacrifice_spike is not None:
            sp = self.current_room.sacrifice_spike
            for cp in alive_players:
                if math.hypot(sp.x - cp.x, sp.y - cp.y) <= cp.radius + 22.0 and sp.cooldown <= 0:
                    if cp.take_damage(1, ignore_invuln=True):
                        self.floor_took_damage = True
                        self.room_took_damage = True
                        self.account_manager.record_stat("sacrifice_uses", 1)
                        self.achievement_manager.evaluate()
                        summon = sp.trigger(cp, self.current_room)
                        if summon:
                            cx = (PLAYABLE_LEFT + PLAYABLE_RIGHT) // 2
                            cy = (PLAYABLE_TOP + PLAYABLE_BOTTOM) // 2
                            self.current_room.bosses = spawn_boss_for_room(self.current_room, summon, cx, cy - 80, self.floor_level)
                            self.current_room.cleared = False
                        break

        if self.current_room.dice_floor is not None and not self.current_room.dice_floor.used:
            df = self.current_room.dice_floor
            for cp in alive_players:
                if math.hypot(df.x - cp.x, df.y - cp.y) <= df.radius:
                    df.used = True
                    self.account_manager.record_stat("dice_uses", 1)
                    self.achievement_manager.evaluate()
                    play_sound("dice")
                    if df.pips >= 5:
                        self._generate_floor(self.floor_level)
                        return
                    for ped in self.current_room.pedestals:
                        if ped.alive:
                            ped.item = get_random_item(cp.collected_ids)
                    cp.active_charge = cp.max_charge
                    self.ui.show_banner(f"DICE ROOM [{df.pips}]")
                    break

        if self.current_room.victory_portal_rect is not None:
            if any(self.current_room.victory_portal_rect.collidepoint(cp.x, cp.y) for cp in alive_players):
                if not self.floor_took_damage:
                    self.account_manager.record_stat("flawless_floors", 1)
                self._on_run_end(won=True)
                return

        if self.current_room.trapdoor_rect is not None:
            if any(self.current_room.trapdoor_rect.collidepoint(cp.x, cp.y) for cp in alive_players):
                if not self.floor_took_damage:
                    self.account_manager.record_stat("flawless_floors", 1)
                next_lvl = self.floor_level + 1
                self.account_manager.record_stat("best_floor", next_lvl, mode="max")
                self.achievement_manager.evaluate()
                if self.game_mode == "boss_rush":
                    self.boss_rush_wave = next_lvl
                self._generate_floor(next_lvl)
                mod_manager.dispatch_new_floor(self.floor_level, self.player, self.player2)
                sub_s = tr_floor(self.floor_level)
                if self.floor_modifier is not None:
                    lang = GAME_SETTINGS.get("language", "ru")
                    sub_s = f"{sub_s} · {self.floor_modifier.get(lang, '')}"
                self.ui.show_banner(f"{tr('floor_label')} {self.floor_level}", sub_s)
                play_sound("door")
                return

        if self.current_room.cleared and self.game_mode != "endless_abyss":
            for cp in alive_players:
                p_rect = pygame.Rect(int(cp.x - cp.radius), int(cp.y - cp.radius), int(cp.radius * 2), int(cp.radius * 2))
                if self.current_room.devil_door is not None and self.current_room.devil_door.rect.colliderect(p_rect):
                    self._enter_room((99, 99), self.current_room.devil_door.direction)
                    return
                for d_name, door in self.current_room.doors.items():
                    if door.secret and not door.opened:
                        continue
                    if door.rect.colliderect(p_rect):
                        if door.locked:
                            if cp.free_locks or self.player.free_locks:
                                door.locked = False
                                self.account_manager.record_stat("doors_opened", 1)
                                self.achievement_manager.evaluate()
                            elif cp.keys > 0:
                                cp.keys -= 1
                                door.locked = False
                                self.account_manager.record_stat("doors_opened", 1)
                                self.achievement_manager.evaluate()
                            elif self.player.keys > 0:
                                self.player.keys -= 1
                                door.locked = False
                                self.account_manager.record_stat("doors_opened", 1)
                                self.achievement_manager.evaluate()
                            else:
                                continue
                        is_curse_door = (door.target_type == "curse") or (self.current_room.room_type == "curse")
                        curse_hit = False
                        if is_curse_door:
                            for hp_p in alive_players:
                                if (
                                    not hp_p.has_effective_flight()
                                    and not hp_p.noclip
                                    and not hp_p.has_effect("godmode")
                                    and not hp_p.has_effect("shield")
                                    and hp_p.book_shadows_timer <= 0
                                ):
                                    if hp_p.take_damage(1, ignore_invuln=True):
                                        curse_hit = True
                                        self.floor_took_damage = True
                            if curse_hit:
                                self._trigger_shake(5.5, 12.0)
                                for _ in range(10):
                                    ang = random.uniform(0.0, math.pi * 2.0)
                                    spd = random.uniform(1.5, 4.2)
                                    self.particles.append(SplashParticle(cp.x, cp.y, math.cos(ang) * spd, math.sin(ang) * spd, (238, 238, 238), 3, 16))
                            if self._all_players_dead():
                                self._on_run_end(won=False)
                                return
                        self._enter_room(door.target_coord, d_name)
                        if curse_hit:
                            self.ui.show_banner(tr("curse_thorns"), duration=65.0)
                        return

        self.current_room.update(dt)
        for pt in self.particles:
            pt.update(dt)
        self.particles = [p for p in self.particles if p.alive]
        max_p = int(get_effects_config().get("max_particles", 140))
        if len(self.particles) > max_p:
            self.particles = self.particles[-max_p:]

        cx = (PLAYABLE_LEFT + PLAYABLE_RIGHT) // 2
        cy = (PLAYABLE_TOP + PLAYABLE_BOTTOM) // 2
        alive_cam = self._get_active_players()
        if len(alive_cam) >= 2:
            focus_x = sum(p.x for p in alive_cam) / len(alive_cam)
            focus_y = sum(p.y for p in alive_cam) / len(alive_cam)
        elif alive_cam:
            focus_x, focus_y = alive_cam[0].x, alive_cam[0].y
        else:
            focus_x, focus_y = cx, cy
        target_cam_x = clamp(-(focus_x - cx) * 0.04, -18.0, 18.0)
        target_cam_y = clamp(-(focus_y - cy) * 0.04, -12.0, 12.0)
        self.cam_x += (target_cam_x - self.cam_x) * 0.12 * dt
        self.cam_y += (target_cam_y - self.cam_y) * 0.12 * dt

        if self.shake_timer > 0:
            self.shake_timer = max(0.0, self.shake_timer - dt)
        else:
            self.shake_power = 0.0

        if self.lan_host.running and self.lan_host.client_connected:
            self.lan_net_tick = (self.lan_net_tick + 1) % 10000
            if self.lan_net_tick % 2 == 0:
                self._push_lan_snapshot()

        listener_p = self.player if p1_alive else self._primary_alive_player()
        self._sync_room_computer_audio(self.current_room, listener_p)

        if self._all_players_dead():
            self._on_run_end(won=False)

    def _collect_lights(self, room):
        extras = []
        for ent in room.enemies + room.bosses + room.monoliths + room.mystical_npcs:
            if hasattr(ent, "get_light_source"):
                ls = ent.get_light_source()
                if ls is not None:
                    extras.append(ls)
        return extras

    def _draw_playing(self):
        if self.current_room is None:
            self.screen.fill(COLOR_BLACK)
            return
        vw = get_view_width()
        world_ox = get_world_offset_x()
        ox = self.cam_x + (random.uniform(-self.shake_power, self.shake_power) if self.shake_timer > 0 else 0.0)
        oy = self.cam_y + (random.uniform(-self.shake_power, self.shake_power) if self.shake_timer > 0 else 0.0)
        ix = int(round(ox))
        iy = int(round(oy))
        use_world_buf = ix != 0 or iy != 0 or world_ox != 0
        world = self._world_surf if use_world_buf else self.screen

        active_pls = self._get_active_players()
        light_srcs = self.current_room.get_dynamic_light_sources(active_pls) if hasattr(self.current_room, "get_dynamic_light_sources") else None

        self.current_room.draw(world, self.time_acc, light_sources=light_srcs)
        has_sale = any(cp.has_steam_sale for cp in active_pls)
        for p in self.current_room.pickups:
            p.draw(world, self.ui.font_tiny, has_sale)
        for ped in self.current_room.pedestals:
            ped.draw(world, self.ui.font_tiny, has_sale)
        for b_obj in self.bombs:
            b_obj.draw(world)
        for e in self.current_room.enemies:
            e.draw(world, light_sources=light_srcs)
        for b in self.current_room.bosses:
            b.draw(world, light_sources=light_srcs)
        for cp in active_pls:
            cp.draw(world, light_sources=light_srcs)
        for t_obj in self.tears:
            t_obj.draw(world)
        for pr in self.enemy_projectiles:
            pr.draw(world)
        for pt in self.particles:
            pt.draw(world)

        focus_p = self._primary_alive_player() or self.player
        fuel = focus_p.lantern_fuel * focus_p.lantern_bonus if self.game_mode == "fading_light" else focus_p.lantern_bonus
        if focus_p.has_effect("lantern_blaze"):
            fuel = max(fuel * 1.45, 1.65)
        extra_lights = self._collect_lights(self.current_room)
        if self.coop_enabled and self.player2 is not None and not self.player2.is_dead() and self.player2 is not focus_p:
            p2_fuel = self.player2.lantern_fuel * self.player2.lantern_bonus if self.game_mode == "fading_light" else self.player2.lantern_bonus
            if self.player2.has_effect("lantern_blaze"):
                p2_fuel = max(p2_fuel * 1.45, 1.65)
            p2_rad = clamp(250.0 * p2_fuel, 130.0, 420.0)
            p2_lum = int(clamp(205 * min(1.15, p2_fuel), 115, 232))
            extra_lights.append((self.player2.x, self.player2.y, p2_rad, p2_lum))
            p2_fx, p2_fy = self.player2.facing
            if p2_fx != 0.0 or p2_fy != 0.0:
                extra_lights.append((self.player2.x + p2_fx * 72.0, self.player2.y + p2_fy * 72.0, p2_rad * 0.6, int(p2_lum * 0.55)))
        self.lighting.render(
            world,
            focus_p.x,
            focus_p.y,
            self.current_room,
            time_acc=self.time_acc,
            lantern_fuel=fuel,
            aim_dir=focus_p.facing,
            extra_lights=extra_lights,
        )
        for b in self.current_room.bosses:
            if hasattr(b, "draw_post_light"):
                b.draw_post_light(world, self.ui.font_tiny)
        if use_world_buf:
            # Always clear main frame buffer so moving HUD/touch sticks never smear over camera seams
            self.screen.fill((5, 5, 5))
            if world_ox > 0:
                draw_wide_backdrop(self.screen, vw, world_ox, self.current_room.theme, extra_pad=max(32, abs(ix) + 16))
            self.screen.blit(self._world_surf, (world_ox + ix, iy))

        comp_hint = self._get_nearby_computer_hint(self.current_room, focus_p)
        self.ui.draw_hud(
            self.screen,
            self.player,
            self.rooms,
            self.current_coord,
            self.current_room,
            self.floor_level,
            self.fps_val,
            GAME_SETTINGS.get("show_fps", False),
            game_mode=self.game_mode,
            wave_num=self.wave_num,
            lantern_fuel=focus_p.lantern_fuel,
            editor_active=self.editor.active,
            timescale=self.timescale,
            touch_active=self.touch.is_active(),
            p2=self.player2 if self.coop_enabled else None,
            computer_hint=comp_hint,
        )
        if self.state == "PLAYING" and not self.editor.active and not self.console.open:
            self.touch.draw(self.screen, self.player, self.ui, near_terminal=bool(comp_hint))
        if self.editor.active and self.state == "PLAYING":
            self.editor.draw(self.screen, self.ui, self)
        if self.console.open:
            self.console.draw(self.screen, self.ui)

        lang = GAME_SETTINGS.get("language", "ru")
        self.quest_manager.draw_hud_widget(self.screen, self.ui, lang)
        if self.quest_manager.log_open:
            self.quest_manager.draw_log_modal(self.screen, self.ui, lang)
        if self.pending_pedestal_prompt is not None:
            self.ui.draw_pickup_confirm_modal(self.screen, self.pending_pedestal_prompt, self.touch.is_active())

    def _menu_side_margin(self):
        vw = get_view_width()
        return 54 if vw >= 1440 else 72

    def _menu_card_metrics(self):
        vw = get_view_width()
        if self.coop_enabled:
            if vw >= 1440:
                hero_w, menu_w, gap = 420, 436, 20
            else:
                hero_w, menu_w, gap = 392, 408, 14
            total_w = hero_w * 2 + menu_w + gap * 2
            sx = max(12, (vw - total_w) // 2)
            p1_x = sx
            menu_x = sx + hero_w + gap
            p2_x = menu_x + menu_w + gap
            return p1_x, menu_x, p2_x, hero_w, menu_w
        margin = self._menu_side_margin()
        return margin, vw - margin - 450, vw, 450, 450

    def _menu_hero_rects(self):
        hx, _, _, hero_w, _ = self._menu_card_metrics()
        hy = 114
        phone = is_phone_layout(self.touch.is_active())
        aw, ah = (50, 58) if phone else (38, 44)
        pad = 16 if hero_w < 430 else 20
        return (
            pygame.Rect(hx, hy, hero_w, 352),
            pygame.Rect(hx + pad, hy + 68, aw, ah),
            pygame.Rect(hx + hero_w - pad - aw, hy + 68, aw, ah),
        )

    def _menu_p2_hero_rects(self):
        if not self.coop_enabled:
            return None, None, None
        _, _, p2x, hero_w, _ = self._menu_card_metrics()
        hy = 114
        phone = is_phone_layout(self.touch.is_active())
        aw, ah = (50, 58) if phone else (38, 44)
        pad = 16 if hero_w < 430 else 20
        return (
            pygame.Rect(p2x, hy, hero_w, 352),
            pygame.Rect(p2x + pad, hy + 68, aw, ah),
            pygame.Rect(p2x + hero_w - pad - aw, hy + 68, aw, ah),
        )

    def _menu_button_rects(self):
        _, mx, _, _, menu_w = self._menu_card_metrics()
        my = 114
        if self.coop_enabled:
            pad = 16
            iw = menu_w - pad * 2
            bw = (iw - 10) // 2
            col1 = mx + pad
            col2 = col1 + bw + 10
            return [
                pygame.Rect(col1, my + 12, iw, 38),
                pygame.Rect(col1, my + 56, bw, 36),
                pygame.Rect(col2, my + 56, bw, 36),
                pygame.Rect(col1, my + 98, bw, 36),
                pygame.Rect(col2, my + 98, bw, 36),
                pygame.Rect(col1, my + 140, bw, 36),
                pygame.Rect(col2, my + 140, bw, 36),
                pygame.Rect(col1, my + 182, bw, 36),
                pygame.Rect(col2, my + 182, bw, 36),
            ]
        return [
            pygame.Rect(mx + 26, my + 14, 398, 42),   # 0: Start
            pygame.Rect(mx + 26, my + 64, 194, 40),   # 1: Saves (3)
            pygame.Rect(mx + 230, my + 64, 194, 40),  # 2: Profiles & Achievements
            pygame.Rect(mx + 26, my + 112, 194, 40),  # 3: Code Editor
            pygame.Rect(mx + 230, my + 112, 194, 40), # 4: Tutorial
            pygame.Rect(mx + 26, my + 160, 194, 40),  # 5: Codex
            pygame.Rect(mx + 230, my + 160, 194, 40), # 6: Chronicle
            pygame.Rect(mx + 26, my + 208, 194, 40),  # 7: Settings
            pygame.Rect(mx + 230, my + 208, 194, 40), # 8: Quit
        ]

    def _menu_coop_rects(self):
        if is_android():
            self.coop_enabled = False
            return (None, None)
        _, mx, _, _, menu_w = self._menu_card_metrics()
        my = 114
        btn_w = min(230, menu_w - 40)
        bx = mx + (menu_w - btn_w) // 2
        if self.coop_enabled:
            return (pygame.Rect(bx, my + 228, btn_w, 32), None)
        return (pygame.Rect(bx, my + 262, btn_w, 34), None)

    def _menu_console_rect(self):
        vw = get_view_width()
        return pygame.Rect(vw - 166, 20, 140, 34)

    def _menu_daily_rect(self):
        return pygame.Rect(20, 20, 276, 46)

    def _menu_mode_rects(self):
        vw = get_view_width()
        mpx, mpy = vw // 2 - 568, 474
        rects = []
        for idx in range(len(GAME_MODES)):
            row = idx // 4
            col = idx % 4
            rects.append(pygame.Rect(mpx + 18 + col * 276, mpy + 27 + row * 34, 266, 28))
        return rects

    def _menu_seed_rect(self):
        vw = get_view_width()
        mpx, mpy = vw // 2 - 568, 474
        return pygame.Rect(mpx + 18 + 3 * 276, mpy + 61, 234, 28)

    def _menu_seed_roll_rect(self):
        vw = get_view_width()
        mpx, mpy = vw // 2 - 568, 474
        return pygame.Rect(mpx + 18 + 3 * 276 + 238, mpy + 61, 28, 28)

    def _menu_preview_rects(self):
        vw = get_view_width()
        bx, by = vw // 2 - 410, SCREEN_HEIGHT - 54
        return (
            [pygame.Rect(bx + 12 + idx * 112, by + 6, 106, 26) for idx in range(6)],
            pygame.Rect(bx + 686, by + 6, 122, 26),
        )

    def _settings_row_count(self):
        return 16

    def _settings_rects(self):
        vw = get_view_width()
        px, py = vw // 2 - 345, SCREEN_HEIGHT // 2 - 332
        return [pygame.Rect(px + 34, py + 56 + i * 37, 622, 32) for i in range(self._settings_row_count())]

    def _tutorial_layout(self):
        vw = get_view_width()
        pw, ph = 980, 586
        px, py = vw // 2 - pw // 2, SCREEN_HEIGHT // 2 - ph // 2
        tabs = [
            pygame.Rect(px + 42, py + 76, 276, 36),
            pygame.Rect(px + 330, py + 76, 310, 36),
        ]
        reset_rc = pygame.Rect(px + pw - 252, py + 76, 210, 36)
        kb_rects = []
        col_w = (pw - 104) // 2
        row_h = 40
        for idx, act in enumerate(KEYBIND_ACTIONS):
            col = idx // 8
            row = idx % 8
            rx = px + 42 + col * (col_w + 20)
            ry = py + 128 + row * (row_h + 6)
            kb_rects.append((act, pygame.Rect(rx, ry, col_w, row_h)))
        touch_edit_rc = pygame.Rect(px + pw // 2 - 190, py + ph - 118, 380, 42)
        back_rc = pygame.Rect(vw // 2 - 140, py + ph - 58, 280, 42)
        return {
            "panel": pygame.Rect(px, py, pw, ph),
            "tabs": tabs,
            "reset": reset_rc,
            "kb_rects": kb_rects,
            "touch_edit": touch_edit_rc,
            "back": back_rc,
        }

    def _tutorial_back_rect(self):
        return self._tutorial_layout()["back"]

    def _saves_layout_rects(self):
        vw = get_view_width()
        cx = vw // 2 - 420
        cards = [pygame.Rect(cx, 152 + i * 136, 840, 118) for i in range(3)]
        back_r = pygame.Rect(vw // 2 - 130, 588, 260, 44)
        return cards, back_r

    def _saves_card_buttons(self, card_rc, summary):
        if summary.get("empty", True):
            return {"save": pygame.Rect(card_rc.right - 236, card_rc.y + 34, 212, 48)}
        return {
            "load": pygame.Rect(card_rc.right - 294, card_rc.y + 34, 140, 48),
            "delete": pygame.Rect(card_rc.right - 144, card_rc.y + 34, 120, 48),
        }

    def _draw_hero_select_card(self, card_rc, left_arr, right_arr, hero_idx, hover_arrow, tag_prefix, key_hint, title_lbl):
        lang = GAME_SETTINGS.get("language", "ru")
        hero = HERO_ROSTER[hero_idx % len(HERO_ROSTER)]
        active_acc = self.account_manager.get_active()
        unlocked = is_hero_unlocked(hero["id"], active_acc)
        unlocked_tot = count_unlocked_heroes(active_acc)
        h_panel = get_panel_surf(card_rc.w, card_rc.h, 12, 224, 104, 12)
        self.screen.blit(h_panel, card_rc.topleft)

        hdr_str = f"{tag_prefix}< {key_hint} >  {title_lbl} ({hero_idx % len(HERO_ROSTER) + 1}/{len(HERO_ROSTER)}) · {unlocked_tot}/{len(HERO_ROSTER)}"
        h_hdr = fit_text_surf(self.ui.font_tiny, hdr_str, PALETTE["text_muted"], card_rc.w - 24, max_h=15, min_scale=0.58)
        self.screen.blit(h_hdr, (card_rc.centerx - h_hdr.get_width() // 2, card_rc.y + 10))

        for dir_val, arc, a_txt in ((-1, left_arr, "<"), (1, right_arr, ">")):
            hov = hover_arrow == dir_val
            pygame.draw.rect(self.screen, (236, 236, 236) if hov else (28, 28, 28), arc, border_radius=6)
            pygame.draw.rect(self.screen, (250, 250, 250) if hov else (90, 90, 90), arc, 1, border_radius=6)
            blit_text_fitted(self.screen, arc, self.ui.font_big, a_txt, (12, 12, 12) if hov else PALETTE["text_main"], pad_x=4)

        draw_hero_portrait(self.screen, hero["id"], card_rc.centerx, card_rc.y + 92, scale=1.74 if card_rc.w < 430 else 1.80)
        if not unlocked:
            lock_badge = fit_text_surf(self.ui.font_tiny, f"[ {tr('menu_hero_locked')} ]", (236, 236, 236), card_rc.w - 40, max_h=15, min_scale=0.58)
            lb_rc = pygame.Rect(card_rc.centerx - lock_badge.get_width() // 2 - 8, card_rc.y + 126, lock_badge.get_width() + 16, 20)
            pygame.draw.rect(self.screen, (16, 16, 16), lb_rc, border_radius=5)
            pygame.draw.rect(self.screen, (186, 186, 186), lb_rc, 1, border_radius=5)
            self.screen.blit(lock_badge, (lb_rc.x + 8, lb_rc.centery - lock_badge.get_height() // 2))

        h_disp_name = hero.get("name_en", hero["name"]) if lang == "en" else hero["name"]
        ex_hero = HERO_EXTRA_EN.get(hero["id"], (hero["title"], hero["desc"]))
        h_disp_title = ex_hero[0] if lang == "en" else hero["title"]
        h_disp_desc = ex_hero[1] if lang == "en" else hero["desc"]

        name_col = PALETTE["text_main"] if unlocked else (162, 162, 162)
        h_name = fit_text_surf(self.ui.font_big, h_disp_name.upper(), name_col, card_rc.w - 28, max_h=24, min_scale=0.56)
        self.screen.blit(h_name, (card_rc.centerx - h_name.get_width() // 2, card_rc.y + 152))
        h_title = fit_text_surf(self.ui.font_small, h_disp_title, PALETTE["accent_soft"] if unlocked else (126, 126, 126), card_rc.w - 28, max_h=16, min_scale=0.56)
        self.screen.blit(h_title, (card_rc.centerx - h_title.get_width() // 2, card_rc.y + 182))

        stats_line = f"HP {(hero['hp'] + hero['soul_hp'] + hero['black_hp']) / 2:.0f}  ·  DMG {hero['damage']:.1f}  ·  SPD {hero['speed']:.1f}"
        st_surf = fit_text_surf(self.ui.font_med if card_rc.w >= 410 else self.ui.font_small, stats_line, name_col, card_rc.w - 28, max_h=18, min_scale=0.56)
        self.screen.blit(st_surf, (card_rc.centerx - st_surf.get_width() // 2, card_rc.y + 206))

        if not unlocked:
            _unl, cur_p, tgt_p = get_hero_unlock_progress(hero["id"], active_acc)
            req_txt = get_hero_unlock_text(hero["id"], lang)
            req_s = fit_text_surf(self.ui.font_tiny, f"{req_txt} ({cur_p}/{tgt_p})", (220, 220, 220), card_rc.w - 28, max_h=16, min_scale=0.52)
            self.screen.blit(req_s, (card_rc.centerx - req_s.get_width() // 2, card_rc.y + 240))
            bar_w = min(280, card_rc.w - 48)
            bx, by = card_rc.centerx - bar_w // 2, card_rc.y + 266
            pygame.draw.rect(self.screen, (30, 30, 30), (bx, by, bar_w, 8), border_radius=4)
            pygame.draw.rect(self.screen, (96, 96, 96), (bx, by, bar_w, 8), 1, border_radius=4)
            fill_w = int(bar_w * clamp(cur_p / float(max(1, tgt_p)), 0.0, 1.0))
            if fill_w > 0:
                pygame.draw.rect(self.screen, (226, 226, 226), (bx + 1, by + 1, max(1, fill_w - 2), 6), border_radius=3)
            dl = fit_text_surf(self.ui.font_tiny, h_disp_desc, PALETTE["text_dim"], card_rc.w - 32, max_h=16, min_scale=0.54)
            self.screen.blit(dl, (card_rc.centerx - dl.get_width() // 2, card_rc.y + 286))
        else:
            max_line_w = card_rc.w - 38
            words = h_disp_desc.split()
            lines = []
            line = ""
            for w in words:
                test = f"{line} {w}".strip()
                if self.ui.font_small.size(test)[0] > max_line_w:
                    if line:
                        lines.append(line)
                    line = w
                else:
                    line = test
            if line:
                lines.append(line)
            for li, ln in enumerate(lines[:3]):
                dl = fit_text_surf(self.ui.font_small, ln, PALETTE["text_muted"], card_rc.w - 28, max_h=17, min_scale=0.54)
                self.screen.blit(dl, (card_rc.centerx - dl.get_width() // 2, card_rc.y + 242 + li * 24))

    def _draw_menu(self):
        vw = get_view_width()
        lang = GAME_SETTINGS.get("language", "ru")
        self.ui.sync_font_scale(is_phone_layout(self.touch.is_active()))
        low_pwr = bool(is_android() or is_phone_layout(self.touch.is_active()))
        self.preview.draw(
            self.screen,
            self.lighting,
            font=self.ui.font_tiny,
            world_surf=self._world_surf,
            low_power=low_pwr,
            menu_dimmed=(not self.hide_menu_ui),
        )

        if not self.hide_menu_ui:
            self.screen.blit(self._menu_dim, (0, 0))

            # Daily Reward badge top-left
            d_rc = self._menu_daily_rect()
            d_info = self.account_manager.get_daily_reward_info()
            can_claim = bool(d_info.get("can_claim"))
            d_fill = (232, 232, 232) if (can_claim and self.hover_daily_btn) else ((32, 32, 32) if can_claim else (18, 18, 18))
            d_border = (250, 250, 250) if can_claim else (74, 74, 74)
            pygame.draw.rect(self.screen, d_fill, d_rc, border_radius=8)
            pygame.draw.rect(self.screen, d_border, d_rc, 1, border_radius=8)
            d_txt_col = (12, 12, 12) if (can_claim and self.hover_daily_btn) else (PALETTE["text_main"] if can_claim else PALETTE["text_muted"])
            rw_lbl = d_info["reward"].get("label_en" if lang == "en" else "label_ru", "")
            d_hdr = f"{tr('daily_title')} · {tr('daily_streak_fmt').format(n=d_info.get('next_day', 1))}"
            d_sub = f"{tr('daily_claim')}: {rw_lbl}" if can_claim else tr("daily_claimed")
            self.screen.blit(fit_text_surf(self.ui.font_tiny, d_hdr, d_txt_col, d_rc.w - 20, max_h=15, min_scale=0.54), (d_rc.x + 10, d_rc.y + 5))
            self.screen.blit(fit_text_surf(self.ui.font_tiny, d_sub, d_txt_col, d_rc.w - 20, max_h=15, min_scale=0.54), (d_rc.x + 10, d_rc.y + 24))

            title_panel = get_panel_surf(680, 92, 10, 212, 118, 12)
            self.screen.blit(title_panel, (vw // 2 - 340, 14))
            alpha_s = fit_text_surf(self.ui.font_tiny, tr("alpha_badge"), (238, 238, 238), 140, max_h=15, min_scale=0.58)
            ab_w = alpha_s.get_width() + 14
            ab_rect = pygame.Rect(vw // 2 + 340 - ab_w - 14, 22, ab_w, 20)
            title_max_w = max(260, 680 - (ab_w + 28) * 2)
            t_surf = fit_text_surf(self.ui.font_huge, tr("game_title"), PALETTE["text_main"], title_max_w, max_h=38, min_scale=0.58)
            self.screen.blit(t_surf, (vw // 2 - t_surf.get_width() // 2, 22))
            pygame.draw.rect(self.screen, (28, 28, 28), ab_rect, border_radius=5)
            pygame.draw.rect(self.screen, (148, 148, 148), ab_rect, 1, border_radius=5)
            self.screen.blit(alpha_s, (ab_rect.x + 7, ab_rect.centery - alpha_s.get_height() // 2))
            sub_surf = fit_text_surf(self.ui.font_tiny, tr("game_subtitle"), PALETTE["text_muted"], 652, max_h=16, min_scale=0.58)
            self.screen.blit(sub_surf, (vw // 2 - sub_surf.get_width() // 2, 68))

            p1_box, p1_left_arr, p1_right_arr = self._menu_hero_rects()
            self._draw_hero_select_card(
                p1_box,
                p1_left_arr,
                p1_right_arr,
                self.selected_hero_idx,
                self.hover_hero_arrow,
                "[P1] " if self.coop_enabled else "",
                "A/D",
                tr("menu_hero_select"),
            )

            _, mx, _, _, menu_w = self._menu_card_metrics()
            my = 114
            m_panel = get_panel_surf(menu_w, 352, 12, 224, 104, 12)
            self.screen.blit(m_panel, (mx, my))
            menu_items = [
                tr("menu_start"),
                tr("menu_saves"),
                tr("menu_accounts"),
                tr("menu_mods"),
                tr("menu_tutorial"),
                tr("menu_codex"),
                tr("menu_chronicle"),
                tr("menu_settings"),
                tr("menu_quit"),
            ]
            for i, (lbl, rc) in enumerate(zip(menu_items, self._menu_button_rects())):
                sel = i == self.menu_idx
                hov = i == self.hover_menu_btn
                fill = (238, 238, 238) if sel else ((54, 54, 54) if hov else (26, 26, 26))
                border = (252, 252, 252) if sel else ((146, 146, 146) if hov else (78, 78, 78))
                pygame.draw.rect(self.screen, fill, rc, border_radius=8)
                pygame.draw.rect(self.screen, border, rc, 1, border_radius=8)
                font_btn = self.ui.font_med if rc.w > 260 else self.ui.font_small
                blit_text_fitted(
                    self.screen,
                    rc,
                    font_btn,
                    lbl,
                    (12, 12, 12) if sel else PALETTE["text_main"],
                    pad_x=10,
                    min_scale=0.50,
                )

            coop_rc, _ = self._menu_coop_rects()
            c_on = self.coop_enabled
            lan_active = self.lan_host.running or self.lan_client.connected
            if coop_rc is not None:
                c_fill = (232, 232, 232) if c_on else ((48, 48, 48) if self.hover_coop_btn else (22, 22, 22))
                c_border = (252, 252, 252) if (c_on or self.hover_coop_btn) else (78, 78, 78)
                pygame.draw.rect(self.screen, c_fill, coop_rc, border_radius=7)
                pygame.draw.rect(self.screen, c_border, coop_rc, 1, border_radius=7)
                c_lbl = tr("coop_min_on") if c_on else tr("coop_min_off")
                blit_text_fitted(self.screen, coop_rc, self.ui.font_tiny, c_lbl, (12, 12, 12) if c_on else PALETTE["text_main"], pad_x=8)

            m_center = mx + menu_w // 2
            if c_on and not is_android():
                c1_s = fit_text_surf(self.ui.font_tiny, tr("coop_controls_line1"), (206, 206, 206), menu_w - 24, min_scale=0.55)
                c2_s = fit_text_surf(self.ui.font_tiny, tr("coop_controls_line2"), (164, 164, 164), menu_w - 24, min_scale=0.55)
                self.screen.blit(c1_s, (m_center - c1_s.get_width() // 2, my + 274))
                self.screen.blit(c2_s, (m_center - c2_s.get_width() // 2, my + 294))
                if self.lan_host.running:
                    net_txt = f"LAN {self.lan_host.local_ip}:{self.lan_host.port} · " + ("P2 OK" if self.lan_host.client_connected else tr("lan_status_wait"))
                elif self.lan_client.connected:
                    net_txt = f"LAN P2 → {self.lan_client.host_addr}"
                else:
                    p2h = HERO_ROSTER[self.selected_p2_hero_idx % len(HERO_ROSTER)]
                    p2n = p2h.get("name_en", p2h["name"]) if lang == "en" else p2h["name"]
                    net_txt = f"P1 + P2 ({p2n}) [F4]"
                net_s = fit_text_surf(self.ui.font_tiny, net_txt, (220, 220, 220) if lan_active else (142, 142, 142), menu_w - 24, min_scale=0.55)
                self.screen.blit(net_s, (m_center - net_s.get_width() // 2, my + 318))

                p2_box, p2_left_arr, p2_right_arr = self._menu_p2_hero_rects()
                self._draw_hero_select_card(
                    p2_box,
                    p2_left_arr,
                    p2_right_arr,
                    self.selected_p2_hero_idx,
                    self.hover_p2_hero_arrow,
                    "[P2] ",
                    "F4",
                    tr("menu_p2_hero"),
                )
            else:
                acc = self.account_manager.get_active()
                un_cnt, tot_cnt = self.achievement_manager.summary()
                acc_line = f"[{acc.get('tag', 'DV-01')}] {acc.get('name', '')}  ·  ★ {un_cnt}/{tot_cnt}"
                acc_s = fit_text_surf(self.ui.font_tiny, acc_line, (182, 182, 182), menu_w - 28, min_scale=0.56)
                self.screen.blit(acc_s, (m_center - acc_s.get_width() // 2, my + 314))

            if GAME_SETTINGS.get("console_enabled", False):
                c_rc = self._menu_console_rect()
                c_fill = (236, 236, 236) if self.hover_console_btn else (24, 24, 24)
                c_border = (252, 252, 252) if self.hover_console_btn else (130, 130, 130)
                pygame.draw.rect(self.screen, c_fill, c_rc, border_radius=6)
                pygame.draw.rect(self.screen, c_border, c_rc, 1, border_radius=6)
                blit_text_fitted(self.screen, c_rc, self.ui.font_tiny, tr("menu_console_btn"), (12, 12, 12) if self.hover_console_btn else PALETTE["text_main"], pad_x=8)

            mode_panel = get_panel_surf(1136, 126, 12, 224, 104, 12)
            mpx, mpy = vw // 2 - 568, 474
            self.screen.blit(mode_panel, (mpx, mpy))
            m_hdr = fit_text_surf(self.ui.font_tiny, tr("menu_mode_select"), PALETTE["text_muted"], 1100, max_h=15, min_scale=0.58)
            self.screen.blit(m_hdr, (mpx + 18, mpy + 7))
            for idx, (mkey, rc) in enumerate(zip(GAME_MODES, self._menu_mode_rects())):
                active = idx == self.selected_mode_idx
                hov = idx == self.hover_mode_pill
                fill = (238, 238, 238) if active else ((54, 54, 54) if hov else (26, 26, 26))
                border = (252, 252, 252) if active else ((150, 150, 150) if hov else (84, 84, 84))
                pygame.draw.rect(self.screen, fill, rc, border_radius=6)
                pygame.draw.rect(self.screen, border, rc, 1, border_radius=6)
                blit_text_fitted(self.screen, rc, self.ui.font_tiny, tr_mode(mkey), (12, 12, 12) if active else PALETTE["text_main"], pad_x=8, min_scale=0.52)

            seed_rc = self._menu_seed_rect()
            roll_rc = self._menu_seed_roll_rect()
            seed_entry = self.shared_seeds[self.selected_seed_idx % len(self.shared_seeds)] if self.shared_seeds else {}
            seed_code = str(seed_entry.get("seed", "DV-GENESIS-001"))
            is_seed_mode = GAME_MODES[self.selected_mode_idx] == "shared_seed"
            has_custom_seed = bool(self.custom_seed.strip())
            s_fill = (38, 38, 38) if (self.seed_input_active or self.hover_seed_btn) else ((30, 30, 30) if (is_seed_mode or has_custom_seed) else (18, 18, 18))
            s_border = (252, 252, 252) if self.seed_input_active else ((214, 214, 214) if (is_seed_mode or has_custom_seed) else ((136, 136, 136) if self.hover_seed_btn else (68, 68, 68)))
            pygame.draw.rect(self.screen, s_fill, seed_rc, border_radius=6)
            pygame.draw.rect(self.screen, s_border, seed_rc, 1, border_radius=6)
            cursor_ch = "_" if (self.seed_input_active and int(self.time_acc // 20) % 2 == 0) else ""
            if self.seed_input_active or has_custom_seed:
                disp_seed = f"{tr('menu_seed_custom_lbl')}: {self.custom_seed}{cursor_ch}"
                s_col = PALETTE["text_main"]
            elif is_seed_mode:
                disp_seed = f"{tr('menu_seed_btn')}: {seed_code}"
                s_col = PALETTE["text_main"]
            else:
                disp_seed = tr("menu_seed_placeholder")
                s_col = PALETTE["text_muted"]
            blit_text_fitted(self.screen, seed_rc, self.ui.font_tiny, disp_seed, s_col, align="left", pad_x=8, min_scale=0.52)

            r_fill = (232, 232, 232) if self.hover_seed_roll_btn else (28, 28, 28)
            r_border = (250, 250, 250) if self.hover_seed_roll_btn else (88, 88, 88)
            pygame.draw.rect(self.screen, r_fill, roll_rc, border_radius=6)
            pygame.draw.rect(self.screen, r_border, roll_rc, 1, border_radius=6)
            blit_text_fitted(self.screen, roll_rc, self.ui.font_tiny, "✕" if has_custom_seed else "↻", (12, 12, 12) if self.hover_seed_roll_btn else PALETTE["text_main"], pad_x=2)

            cur_mode = GAME_MODES[self.selected_mode_idx]
            mdesc_txt = seed_entry.get("desc_en" if lang == "en" else "desc_ru", tr_mode_desc(cur_mode)) if cur_mode == "shared_seed" and seed_entry else tr_mode_desc(cur_mode)
            mdesc = fit_text_surf(self.ui.font_small, mdesc_txt, PALETTE["accent_soft"], 1100, max_h=18, min_scale=0.56)
            self.screen.blit(mdesc, (vw // 2 - mdesc.get_width() // 2, mpy + 96))

            if self.menu_notice_timer > 0.0 and self.menu_notice:
                nt_s = fit_text_surf(self.ui.font_small, self.menu_notice, (250, 250, 250), min(1040, vw - 80), max_h=18, min_scale=0.58)
                nt_rc = pygame.Rect(vw // 2 - nt_s.get_width() // 2 - 16, 608, nt_s.get_width() + 32, 26)
                pygame.draw.rect(self.screen, (24, 24, 24), nt_rc, border_radius=6)
                pygame.draw.rect(self.screen, (226, 226, 226), nt_rc, 1, border_radius=6)
                self.screen.blit(nt_s, (nt_rc.x + 16, nt_rc.centery - nt_s.get_height() // 2))
            else:
                hint = fit_text_surf(self.ui.font_small, tr("menu_hint"), PALETTE["text_muted"], min(1140, vw - 48), max_h=18, min_scale=0.56)
                self.screen.blit(hint, (vw // 2 - hint.get_width() // 2, 612))

        bar = get_panel_surf(820, 38, 10, 206, 86, 8)
        bx, by = vw // 2 - 410, SCREEN_HEIGHT - 54
        self.screen.blit(bar, (bx, by))
        scene_keys = ["preview_combat", "preview_treasure", "preview_shop", "preview_arcade", "preview_sacrifice", "preview_boss"]
        tab_rects, hide_rect = self._menu_preview_rects()
        for idx, (sk, rc) in enumerate(zip(scene_keys, tab_rects)):
            active = idx == self.preview.scene_idx
            hov = idx == self.hover_preview_tab
            fill = (236, 236, 236) if active else ((54, 54, 54) if hov else (26, 26, 26))
            pygame.draw.rect(self.screen, fill, rc, border_radius=5)
            blit_text_fitted(self.screen, rc, self.ui.font_tiny, f"{idx + 1} {tr(sk)}", (12, 12, 12) if active else PALETTE["text_muted"], pad_x=5, min_scale=0.50)

        pygame.draw.rect(self.screen, (236, 236, 236) if self.hover_hide_ui else (28, 28, 28), hide_rect, border_radius=5)
        pygame.draw.rect(self.screen, (250, 250, 250) if self.hover_hide_ui else (88, 88, 88), hide_rect, 1, border_radius=5)
        toggle_lbl = tr("preview_show_ui") if self.hide_menu_ui else tr("preview_hide_ui")
        blit_text_fitted(self.screen, hide_rect, self.ui.font_tiny, toggle_lbl, (12, 12, 12) if self.hover_hide_ui else PALETTE["text_main"], pad_x=6, min_scale=0.50)

    def _activate_settings_row(self, row_idx, step=1):
        if row_idx == 0:
            GAME_SETTINGS["language"] = "en" if GAME_SETTINGS["language"] == "ru" else "ru"
            save_user_settings()
        elif row_idx == 1:
            GAME_SETTINGS["sound_enabled"] = not GAME_SETTINGS["sound_enabled"]
            self._sync_music()
            save_user_settings()
        elif row_idx == 2:
            GAME_SETTINGS["music_enabled"] = not GAME_SETTINGS.get("music_enabled", True)
            self._sync_music()
            save_user_settings()
        elif row_idx == 3:
            GAME_SETTINGS["shake_enabled"] = not GAME_SETTINGS["shake_enabled"]
            save_user_settings()
        elif row_idx == 4:
            GAME_SETTINGS["show_fps"] = not GAME_SETTINGS["show_fps"]
            save_user_settings()
        elif row_idx == 5:
            cur = GAME_SETTINGS.get("effects_quality", "high")
            nxt = EFFECTS_CHOICES[(EFFECTS_CHOICES.index(cur) + step) % len(EFFECTS_CHOICES)] if cur in EFFECTS_CHOICES else "high"
            GAME_SETTINGS["effects_quality"] = nxt
            clear_render_caches(include_text=False)
            save_user_settings()
        elif row_idx == 6:
            cur = GAME_SETTINGS.get("resolution", "auto")
            nxt = RESOLUTION_CHOICES[(RESOLUTION_CHOICES.index(cur) + step) % len(RESOLUTION_CHOICES)] if cur in RESOLUTION_CHOICES else "auto"
            GAME_SETTINGS["resolution"] = nxt
            self._apply_display_mode(GAME_SETTINGS.get("fullscreen", False))
        elif row_idx == 7:
            cur = GAME_SETTINGS.get("wide_mode", "auto")
            nxt = WIDE_MODE_CHOICES[(WIDE_MODE_CHOICES.index(cur) + step) % len(WIDE_MODE_CHOICES)] if cur in WIDE_MODE_CHOICES else "auto"
            GAME_SETTINGS["wide_mode"] = nxt
            if is_android():
                self._update_present_rect()
            else:
                self._apply_display_mode(GAME_SETTINGS.get("fullscreen", False))
            save_user_settings()
        elif row_idx == 8:
            cur = GAME_SETTINGS.get("ui_scale", "auto")
            nxt = UI_SCALE_CHOICES[(UI_SCALE_CHOICES.index(cur) + step) % len(UI_SCALE_CHOICES)] if cur in UI_SCALE_CHOICES else "auto"
            GAME_SETTINGS["ui_scale"] = nxt
            self.touch._sync_layout()
            self.ui.sync_font_scale(is_phone_layout(self.touch.is_active()))
            save_user_settings()
        elif row_idx == 9:
            self._apply_display_mode(not GAME_SETTINGS.get("fullscreen", False))
        elif row_idx == 10:
            GAME_SETTINGS["console_enabled"] = not GAME_SETTINGS.get("console_enabled", False)
            if not GAME_SETTINGS["console_enabled"]:
                self.console.toggle(False)
                self.editor.active = False
            save_user_settings()
        elif row_idx == 11:
            order = ("auto", "on", "off")
            cur = GAME_SETTINGS.get("touch_controls", "auto")
            nxt = order[(order.index(cur) + step) % len(order)] if cur in order else "auto"
            GAME_SETTINGS["touch_controls"] = nxt
            if nxt == "off":
                self.touch.reset()
            else:
                self.touch._sync_layout()
            self.ui.sync_font_scale(is_phone_layout(self.touch.is_active()))
            save_user_settings()
        elif row_idx == 12:
            self.touch.cycle_preset()
            save_user_settings()
        elif row_idx == 13:
            self.touch_edit_return_state = "SETTINGS"
            self.touch.invalidate_layout()
            self.state = "TOUCH_EDIT"
        elif row_idx == 14:
            self.tutorial_return_state = "SETTINGS"
            self.ctrl_tab = 1
            self.ctrl_rebind_action = None
            self.state = "TUTORIAL"
        else:
            self.state = self.prev_state

    def _draw_settings(self):
        vw = get_view_width()
        self.ui.sync_font_scale(is_phone_layout(self.touch.is_active()))
        self.screen.fill((8, 8, 8))
        panel = get_panel_surf(690, 664, 14, 240, 114, 12)
        px, py = vw // 2 - 345, SCREEN_HEIGHT // 2 - 332
        self.screen.blit(panel, (px, py))
        title = fit_text_surf(self.ui.font_huge, tr("settings_title"), PALETTE["text_main"], 620, min_scale=0.60)
        self.screen.blit(title, (vw // 2 - title.get_width() // 2, py + 10))

        screen_val = tr("settings_fullscreen") if GAME_SETTINGS.get("fullscreen", False) else tr("settings_windowed")
        touch_mode = GAME_SETTINGS.get("touch_controls", "auto")
        touch_lbl = tr(f"touch_{touch_mode}") if touch_mode in ("auto", "on", "off") else tr("touch_auto")
        preset_v = GAME_SETTINGS.get("touch_layout_preset", "wide")
        if preset_v not in TOUCH_LAYOUT_PRESETS:
            preset_v = "wide"
        preset_lbl = tr(f"touch_preset_{preset_v}")
        eff_q = GAME_SETTINGS.get("effects_quality", "high")
        eff_lbl = tr(f"effects_{eff_q}") if eff_q in EFFECTS_CHOICES else tr("effects_high")
        res_v = GAME_SETTINGS.get("resolution", "auto")
        res_lbl = tr("res_auto") if res_v == "auto" else res_v.upper()
        wide_v = GAME_SETTINGS.get("wide_mode", "auto")
        wide_lbl = tr(f"wide_{wide_v}") if wide_v in WIDE_MODE_CHOICES else tr("wide_auto")
        if wide_v == "auto":
            wide_lbl = f"{wide_lbl} ({vw}x{SCREEN_HEIGHT})"
        ui_s = GAME_SETTINGS.get("ui_scale", "auto")
        ui_lbl = tr(f"ui_scale_{ui_s}") if ui_s in UI_SCALE_CHOICES else tr("ui_scale_auto")
        rows = [
            (tr("settings_lang"), GAME_SETTINGS["language"].upper()),
            (tr("settings_sound"), tr("on") if GAME_SETTINGS["sound_enabled"] else tr("off")),
            (tr("settings_music"), tr("on") if GAME_SETTINGS.get("music_enabled", True) else tr("off")),
            (tr("settings_shake"), tr("on") if GAME_SETTINGS["shake_enabled"] else tr("off")),
            (tr("settings_fps"), tr("on") if GAME_SETTINGS["show_fps"] else tr("off")),
            (tr("settings_effects"), eff_lbl),
            (tr("settings_resolution"), res_lbl),
            (tr("settings_wide_mode"), wide_lbl),
            (tr("settings_ui_scale"), ui_lbl),
            (tr("settings_screen"), screen_val),
            (tr("settings_console"), tr("on") if GAME_SETTINGS.get("console_enabled", False) else tr("off")),
            (tr("settings_touch"), touch_lbl),
            (tr("settings_touch_preset"), preset_lbl),
            (tr("settings_touch_customize"), "▸"),
            (tr("settings_keybinds"), "▸"),
            (tr("settings_back"), ""),
        ]
        for i, ((k_lbl, v_lbl), rc) in enumerate(zip(rows, self._settings_rects())):
            sel = i == self.settings_idx
            hov = i == self.hover_settings_row
            fill = (238, 238, 238) if sel else ((54, 54, 54) if hov else (26, 26, 26))
            border = (252, 252, 252) if sel else ((144, 144, 144) if hov else (72, 72, 72))
            pygame.draw.rect(self.screen, fill, rc, border_radius=8)
            pygame.draw.rect(self.screen, border, rc, 1, border_radius=8)
            if sel:
                pygame.draw.rect(self.screen, (14, 14, 14), (rc.x + 5, rc.y + 6, 4, rc.h - 12), border_radius=2)
            txt_c = (12, 12, 12) if sel else PALETTE["text_main"]
            if v_lbl:
                v_surf = fit_text_surf(self.ui.font_small, v_lbl, txt_c if sel else PALETTE["accent_soft"], 250, min_scale=0.58)
                self.screen.blit(v_surf, (rc.right - v_surf.get_width() - 18, rc.centery - v_surf.get_height() // 2))
                max_k_w = max(120, rc.w - v_surf.get_width() - 48)
                k_surf = fit_text_surf(self.ui.font_small, k_lbl, txt_c, max_k_w, min_scale=0.56)
                self.screen.blit(k_surf, (rc.x + 18, rc.centery - k_surf.get_height() // 2))
            else:
                blit_text_fitted(self.screen, rc, self.ui.font_small, k_lbl, txt_c, pad_x=18, min_scale=0.58)

    def _draw_tutorial(self):
        vw = get_view_width()
        lang = GAME_SETTINGS.get("language", "ru")
        self.ui.sync_font_scale(is_phone_layout(self.touch.is_active()))
        self.screen.fill((8, 8, 8))
        lay = self._tutorial_layout()
        pr = lay["panel"]
        panel = get_panel_surf(pr.w, pr.h, 14, 240, 114, 12)
        self.screen.blit(panel, pr.topleft)
        title = fit_text_surf(self.ui.font_big, tr("ctrl_title"), PALETTE["text_main"], pr.w - 60, max_h=30, min_scale=0.58)
        self.screen.blit(title, (vw // 2 - title.get_width() // 2, pr.y + 18))

        for t_idx, (tk, t_rc) in enumerate(zip(("ctrl_tab_mobile", "ctrl_tab_pc"), lay["tabs"])):
            sel = self.ctrl_tab == t_idx
            hov = self.hover_ctrl_btn == f"tab_{t_idx}"
            fill = (238, 238, 238) if sel else ((54, 54, 54) if hov else (24, 24, 24))
            border = (252, 252, 252) if sel else ((140, 140, 140) if hov else (76, 76, 76))
            pygame.draw.rect(self.screen, fill, t_rc, border_radius=7)
            pygame.draw.rect(self.screen, border, t_rc, 1, border_radius=7)
            blit_text_fitted(self.screen, t_rc, self.ui.font_tiny, tr(tk), (12, 12, 12) if sel else PALETTE["text_main"], pad_x=10, min_scale=0.54)

        if self.ctrl_tab == 1:
            r_rc = lay["reset"]
            r_hov = self.hover_ctrl_btn == "reset"
            pygame.draw.rect(self.screen, (238, 238, 238) if r_hov else (26, 26, 26), r_rc, border_radius=7)
            pygame.draw.rect(self.screen, (252, 252, 252) if r_hov else (104, 104, 104), r_rc, 1, border_radius=7)
            blit_text_fitted(self.screen, r_rc, self.ui.font_tiny, tr("ctrl_reset_keys"), (12, 12, 12) if r_hov else PALETTE["text_main"], pad_x=10, min_scale=0.54)

            for act, krc in lay["kb_rects"]:
                waiting = self.ctrl_rebind_action == act
                hov = self.hover_ctrl_btn == f"kb_{act}"
                fill = (44, 44, 44) if waiting else ((36, 36, 36) if hov else (20, 20, 20))
                border = (252, 252, 252) if waiting else ((168, 168, 168) if hov else (68, 68, 68))
                pygame.draw.rect(self.screen, fill, krc, border_radius=7)
                pygame.draw.rect(self.screen, border, krc, 1, border_radius=7)

                key_str = tr("ctrl_waiting_key") if waiting else f"[ {format_key_name(get_keybind(act))} ]"
                k_col = (252, 252, 252) if waiting else PALETTE["accent_soft"]
                k_surf = fit_text_surf(self.ui.font_small, key_str, k_col, min(185, krc.w // 2 - 12), max_h=krc.h - 10, min_scale=0.56)
                self.screen.blit(k_surf, (krc.right - 14 - k_surf.get_width(), krc.centery - k_surf.get_height() // 2))

                act_max_w = max(100, krc.w - k_surf.get_width() - 38)
                act_lbl = fit_text_surf(self.ui.font_small, tr(f"kb_{act}"), PALETTE["text_main"], act_max_w, max_h=krc.h - 10, min_scale=0.54)
                self.screen.blit(act_lbl, (krc.x + 14, krc.centery - act_lbl.get_height() // 2))

            pc_note = fit_text_surf(self.ui.font_tiny, tr("ctrl_pc_desc"), PALETTE["text_muted"], pr.w - 60, max_h=18, min_scale=0.56)
            self.screen.blit(pc_note, (vw // 2 - pc_note.get_width() // 2, pr.bottom - 94))
        else:
            mob_lines = (
                [
                    "• Left Dual-Stick: Move around the crypt smoothly",
                    "• Right Dual-Stick: Directional tear firing",
                    "• MELEE [X] Button: Sweeping melee cleave + deflect projectiles",
                    "• DASH / JUMP / CLOAK: Evade traps & trigger Stealth Ambush x1.65",
                    "• TERM / BOMB / RELIC / PAUSE: Quick-access circular controls",
                    f"• Active Preset: {tr('touch_preset_' + str(GAME_SETTINGS.get('touch_layout_preset', 'wide')))}",
                ]
                if lang == "en"
                else [
                    "• Левый стик: Плавное передвижение по залам склепа",
                    "• Правый стик: Прицельная стрельба во все стороны",
                    "• Кнопка МЕЧ [X]: Ближний удар по дуге + отбивание пуль",
                    "• РЫВОК / ПРЫЖОК / ТЕНЬ: Уклонение и скрытная атака x1.65",
                    "• ТЕРМ / БОМБА / РЕЛИКВИЯ / ПАУЗА: Крупные кнопки для пальцев",
                    f"• Текущий пресет: {tr('touch_preset_' + str(GAME_SETTINGS.get('touch_layout_preset', 'wide')))}",
                ]
            )
            for li, ln in enumerate(mob_lines):
                ls = fit_text_surf(self.ui.font_med, ln, PALETTE["text_main"] if li < 5 else PALETTE["accent_soft"], pr.w - 96, max_h=24, min_scale=0.56)
                self.screen.blit(ls, (pr.x + 48, pr.y + 138 + li * 40))

            te_rc = lay["touch_edit"]
            te_hov = self.hover_ctrl_btn == "touch_edit"
            pygame.draw.rect(self.screen, (238, 238, 238) if te_hov else (32, 32, 32), te_rc, border_radius=8)
            pygame.draw.rect(self.screen, (252, 252, 252) if te_hov else (130, 130, 130), te_rc, 1, border_radius=8)
            blit_text_fitted(self.screen, te_rc, self.ui.font_small, tr("settings_touch_customize"), (12, 12, 12) if te_hov else PALETTE["text_main"], pad_x=12, min_scale=0.55)

        back_r = lay["back"]
        pygame.draw.rect(self.screen, (238, 238, 238) if self.hover_tutorial_back else (28, 28, 28), back_r, border_radius=8)
        pygame.draw.rect(self.screen, (252, 252, 252) if self.hover_tutorial_back else (112, 112, 112), back_r, 1, border_radius=8)
        blit_text_fitted(self.screen, back_r, self.ui.font_med, tr("tutorial_back"), (12, 12, 12) if self.hover_tutorial_back else PALETTE["text_main"], pad_x=12, min_scale=0.55)

    def _draw_saves(self):
        vw = get_view_width()
        self.screen.fill((8, 8, 8))
        panel = get_panel_surf(920, 624, 14, 240, 114, 12)
        px, py = vw // 2 - 460, 48
        self.screen.blit(panel, (px, py))

        title = fit_text_surf(self.ui.font_big, tr("saves_title"), PALETTE["text_main"], 860, max_h=30, min_scale=0.58)
        self.screen.blit(title, (vw // 2 - title.get_width() // 2, py + 16))
        rule = fit_text_surf(self.ui.font_small, tr("saves_rule"), PALETTE["accent_soft"], 860, max_h=18, min_scale=0.56)
        self.screen.blit(rule, (vw // 2 - rule.get_width() // 2, py + 52))

        lang = GAME_SETTINGS.get("language", "ru")
        slots = list_save_slots()
        cards, back_r = self._saves_layout_rects()
        has_active_run = self.current_room is not None and not self._all_players_dead()

        for i, (rc, sm) in enumerate(zip(cards, slots)):
            sel = i == self.saves_idx
            pygame.draw.rect(self.screen, (26, 26, 26) if sel else (18, 18, 18), rc, border_radius=8)
            pygame.draw.rect(self.screen, (238, 238, 238) if sel else (76, 76, 76), rc, 2 if sel else 1, border_radius=8)

            slot_num = sm["slot"]
            btns = self._saves_card_buttons(rc, sm)
            if sm.get("empty", True):
                s_lbl = fit_text_surf(self.ui.font_med, f"{slot_num}. {tr('saves_empty')}", PALETTE["text_muted"], max(180, btns["save"].left - rc.x - 42), max_h=24, min_scale=0.56)
                self.screen.blit(s_lbl, (rc.x + 28, rc.centery - s_lbl.get_height() // 2))
                b_rc = btns["save"]
                hov = self.hover_saves_btn == (slot_num, "save")
                fill = (238, 238, 238) if (has_active_run and hov) else ((38, 38, 38) if has_active_run else (20, 20, 20))
                border = (248, 248, 248) if (has_active_run and hov) else ((150, 150, 150) if has_active_run else (64, 64, 64))
                txt_col = (12, 12, 12) if (has_active_run and hov) else (PALETTE["text_main"] if has_active_run else PALETTE["text_dim"])
                pygame.draw.rect(self.screen, fill, b_rc, border_radius=6)
                pygame.draw.rect(self.screen, border, b_rc, 1, border_radius=6)
                blit_text_fitted(self.screen, b_rc, self.ui.font_small, tr("saves_save_btn") if has_active_run else tr("saves_need_run"), txt_col, pad_x=10, min_scale=0.52)
            else:
                if not sm.get("corrupt", False):
                    draw_hero_portrait(self.screen, sm.get("hero_id", "isaac"), rc.x + 52, rc.centery, scale=1.0)
                    h_name = sm.get("hero_name_en", sm.get("hero_name", "")) if lang == "en" else sm.get("hero_name", "")
                    coop_tag = ""
                    if sm.get("coop_enabled"):
                        p2h = sm.get("p2_hero_name_en", sm.get("p2_hero_name", "")) if lang == "en" else sm.get("p2_hero_name", "")
                        coop_tag = f" + {p2h.upper()} [2P]" if p2h else " [2P]"
                    hdr = f"#{slot_num} · {h_name.upper()}{coop_tag} · {tr('floor_label')} {sm.get('floor_level', 1)}"
                    if sm.get("game_mode") == "endless_abyss":
                        hdr += f" ({tr('wave_label')} {sm.get('wave_num', 1)})"
                    sub1 = f"{tr_mode(sm.get('game_mode', 'classic'))}  ·  HP {sm.get('hp', 0)}/{sm.get('max_hp', 0)} +{sm.get('soul_hp', 0)}S +{sm.get('black_hp', 0)}B"
                    sub2 = f"¢ {sm.get('coins', 0)}  ·  {tr('hud_artifacts')}: {sm.get('items_count', 0)}  ·  {sm.get('saved_at', '')}"
                else:
                    hdr = f"#{slot_num} · CORRUPT SAVE"
                    sub1 = tr("saves_need_delete")
                    sub2 = ""
                max_txt_w = max(240, btns["load"].left - rc.x - 114)
                self.screen.blit(fit_text_surf(self.ui.font_med, hdr, PALETTE["text_main"], max_txt_w, max_h=22, min_scale=0.56), (rc.x + 98, rc.y + 16))
                self.screen.blit(fit_text_surf(self.ui.font_small, sub1, PALETTE["text_muted"], max_txt_w, max_h=18, min_scale=0.56), (rc.x + 98, rc.y + 46))
                if sub2:
                    self.screen.blit(fit_text_surf(self.ui.font_tiny, sub2, PALETTE["accent_soft"], max_txt_w, max_h=16, min_scale=0.56), (rc.x + 98, rc.y + 72))

                for act_k, lbl in (("load", tr("saves_load_btn")), ("delete", tr("saves_delete_btn"))):
                    b_rc = btns[act_k]
                    hov = self.hover_saves_btn == (slot_num, act_k)
                    fill = (238, 238, 238) if hov else ((38, 38, 38) if act_k == "load" else (28, 28, 28))
                    border = (252, 252, 252) if hov else ((168, 168, 168) if act_k == "load" else (112, 112, 112))
                    pygame.draw.rect(self.screen, fill, b_rc, border_radius=6)
                    pygame.draw.rect(self.screen, border, b_rc, 1, border_radius=6)
                    blit_text_fitted(self.screen, b_rc, self.ui.font_small, lbl, (12, 12, 12) if hov else PALETTE["text_main"], pad_x=8, min_scale=0.54)

        if self.saves_feedback_timer > 0 and self.saves_feedback:
            fb = fit_text_surf(self.ui.font_small, self.saves_feedback, (245, 245, 245), 860, min_scale=0.60)
            self.screen.blit(fb, (vw // 2 - fb.get_width() // 2, 554))

        hov_b = self.hover_saves_btn == (-1, "back")
        pygame.draw.rect(self.screen, (238, 238, 238) if hov_b else (28, 28, 28), back_r, border_radius=8)
        pygame.draw.rect(self.screen, (252, 252, 252) if hov_b else (112, 112, 112), back_r, 1, border_radius=8)
        blit_text_fitted(self.screen, back_r, self.ui.font_med, tr("saves_back"), (12, 12, 12) if hov_b else PALETTE["text_main"], pad_x=10, min_scale=0.55)

    def _open_lan_lobby(self, prev_state="MENU"):
        self.touch.reset()
        self.prev_state = prev_state
        self.state = "LAN_LOBBY"
        self.fade_alpha = 180.0
        if not self.lan_ip_input:
            self.lan_ip_input = get_local_ip()
        try:
            pygame.key.start_text_input()
        except Exception:
            pass
        if not self.lan_host.running and not self.lan_client.connected:
            self._lan_scan_servers(async_mode=True)

    def _lan_lobby_rects(self):
        vw = get_view_width()
        pw, ph = 960, 590
        px, py = vw // 2 - pw // 2, 65
        lx, lw = px + 24, 442
        rx, rw = px + pw - 24 - 442, 442
        rows = [pygame.Rect(rx + 18, py + 124 + i * 30, rw - 36, 26) for i in range(3)]
        keypad = []
        row1 = ("1", "2", "3", "4", "5", "6", "7")
        row2 = ("8", "9", "0", ".", ":", "⌫")
        for i, ch in enumerate(row1):
            keypad.append((ch, pygame.Rect(rx + 18 + i * 58, py + 298, 54, 30)))
        kx = rx + 18
        for ch in row2:
            kw = 112 if ch == "⌫" else 54
            keypad.append((ch, pygame.Rect(kx, py + 332, kw, 30)))
            kx += kw + 4
        return {
            "panel": pygame.Rect(px, py, pw, ph),
            "left": pygame.Rect(lx, py + 76, lw, 420),
            "right": pygame.Rect(rx, py + 76, rw, 420),
            "host_toggle": pygame.Rect(lx + 18, py + 248, lw - 36, 46),
            "host_start": pygame.Rect(lx + 18, py + 308, lw - 36, 48),
            "scan": pygame.Rect(rx + 18, py + 84, rw - 36, 32),
            "rows": rows,
            "p2_prev": pygame.Rect(rx + 18, py + 220, 34, 28),
            "p2_next": pygame.Rect(rx + rw - 52, py + 220, 34, 28),
            "p2_box": pygame.Rect(rx + 56, py + 220, rw - 112, 28),
            "ip_box": pygame.Rect(rx + 18, py + 256, rw - 36, 34),
            "keypad": keypad,
            "join_toggle": pygame.Rect(rx + 18, py + 372, rw - 36, 44),
            "back": pygame.Rect(vw // 2 - 140, py + ph - 58, 280, 42),
        }

    def _lan_cycle_p2_hero(self, step=1):
        self.selected_p2_hero_idx = (self.selected_p2_hero_idx + int(step)) % len(HERO_ROSTER)
        hid = HERO_ROSTER[self.selected_p2_hero_idx]["id"]
        if self.lan_client.connected:
            self.lan_client.send_hero(hid)
        play_sound("pickup")

    def _lan_host_start_stop(self):
        if self.lan_host.running:
            self.lan_host.stop()
            self.lan_status = tr("lan_status_off")
            play_sound("hit")
        else:
            self.lan_client.stop()
            acc = self.account_manager.get_active()
            h_id = HERO_ROSTER[self.selected_hero_idx]["id"]
            mode = GAME_MODES[self.selected_mode_idx]
            ok, msg = self.lan_host.start(host_name=acc.get("name", "Host"), hero_id=h_id, game_mode=mode)
            if ok:
                self._toggle_coop_setting(True)
                has_active_run = bool(
                    self.prev_state == "PAUSED"
                    and self.player is not None
                    and self.current_room is not None
                    and not self._all_players_dead()
                )
                if has_active_run:
                    if self.player2 is None:
                        p2_hid = HERO_ROSTER[self.selected_p2_hero_idx % len(HERO_ROSTER)]["id"]
                        self.player.player_tag = "P1"
                        self.player2 = Player(self.player.x + 36, self.player.y, p2_hid)
                        self.player2.player_tag = "P2"
                        self._nudge_clear_of_obstacles(self.player2, self.current_room)
                    self.lan_host.update_lobby_meta(host_hero_id=self.player.hero_id, game_mode=self.game_mode, in_run=True)
                self.lan_status = f"{tr('lan_status_wait')} ({msg})"
                play_sound("pickup")
            else:
                self.lan_status = msg
                play_sound("hurt")

    def _lan_scan_servers(self, async_mode=True):
        if self._lan_scanning:
            return
        self._lan_scanning = True
        self.lan_status = tr("lan_scanning")

        def _worker():
            try:
                found = scan_lan_servers(0.35)
                self.lan_discovered = found
                if found:
                    s0 = found[0]
                    if not self.lan_client.connected:
                        self.lan_ip_input = f"{s0['ip']}:{s0['port']}"
                    self.lan_status = f"{tr('lan_found_label')} ({len(found)})"
                else:
                    self.lan_status = tr("lan_no_servers")
            finally:
                self._lan_scanning = False

        if async_mode:
            threading.Thread(target=_worker, daemon=True, name="DarkVaultLanScan").start()
        else:
            _worker()

    def _lan_connect_disconnect(self):
        if self.lan_client.connected:
            self.lan_client.stop()
            self.lan_status = tr("lan_disc_btn")
            play_sound("hit")
            return
        self.lan_host.stop()
        ip, port = parse_host_port(self.lan_ip_input, DEFAULT_TCP_PORT)
        acc = self.account_manager.get_active()
        p2_id = HERO_ROSTER[self.selected_p2_hero_idx % len(HERO_ROSTER)]["id"]
        ok, info = self.lan_client.connect(ip, port, name=acc.get("name", "P2"), hero_id=p2_id)
        if ok:
            self._toggle_coop_setting(True)
            self._lan_last_sfx_seq = -1
            self._lan_client_prev_hp = None
            self.lan_status = f"{tr('lan_status_client')}: {info}"
            play_sound("pickup")
        else:
            self.lan_status = info
            play_sound("hurt")

    def _draw_lan_lobby(self):
        vw = get_view_width()
        world_ox = get_world_offset_x()
        self.screen.fill((6, 6, 6))
        if world_ox > 0:
            draw_wide_backdrop(self.screen, vw, world_ox, extra_pad=32)

        rc = self._lan_lobby_rects()
        pr = rc["panel"]
        panel = get_panel_surf(pr.w, pr.h, 14, 244, 114, 12)
        self.screen.blit(panel, pr.topleft)

        t_s = fit_text_surf(self.ui.font_big, tr("lan_title"), PALETTE["text_main"], pr.w - 48, max_h=28, min_scale=0.58)
        self.screen.blit(t_s, (vw // 2 - t_s.get_width() // 2, pr.y + 14))
        sub_s = fit_text_surf(self.ui.font_tiny, tr("lan_sub"), PALETTE["text_muted"], pr.w - 48, max_h=16, min_scale=0.56)
        self.screen.blit(sub_s, (vw // 2 - sub_s.get_width() // 2, pr.y + 46))

        # Left column: Host
        l_box = rc["left"]
        pygame.draw.rect(self.screen, (16, 16, 16), l_box, border_radius=10)
        pygame.draw.rect(self.screen, (180, 180, 180) if self.lan_host.running else (72, 72, 72), l_box, 1, border_radius=10)

        h_ip_s = fit_text_surf(self.ui.font_med, f"{tr('lan_ip_label')}: {self.lan_host.local_ip}:{self.lan_host.port}", PALETTE["text_main"], l_box.w - 36, max_h=22, min_scale=0.54)
        self.screen.blit(h_ip_s, (l_box.x + 18, l_box.y + 16))

        if not self.lan_host.running:
            st_str = tr("lan_status_off")
            st_col = PALETTE["text_muted"]
        elif not self.lan_host.client_connected:
            st_str = tr("lan_status_wait")
            st_col = (224, 224, 224)
        else:
            ping_s = f" · {self.lan_host.ping_ms} ms" if self.lan_host.ping_ms > 0 else ""
            st_str = f"{tr('lan_status_ready')}: {self.lan_host.client_name}{ping_s}"
            st_col = (250, 250, 250)
        self.screen.blit(fit_text_surf(self.ui.font_small, st_str, st_col, l_box.w - 36, max_h=18, min_scale=0.54), (l_box.x + 18, l_box.y + 46))

        p1_h = HERO_ROSTER[self.selected_hero_idx]["id"]
        p2_h = self.lan_host.client_hero_id if (self.lan_host.running and self.lan_host.client_connected) else HERO_ROSTER[self.selected_p2_hero_idx]["id"]
        draw_hero_portrait(self.screen, p1_h, l_box.x + 58, l_box.y + 118, scale=1.0)
        self.screen.blit(fit_text_surf(self.ui.font_tiny, f"P1: {p1_h.upper()}", PALETTE["text_main"], 150, max_h=16, min_scale=0.56), (l_box.x + 92, l_box.y + 110))
        draw_hero_portrait(self.screen, p2_h, l_box.x + 258, l_box.y + 118, scale=1.0)
        self.screen.blit(fit_text_surf(self.ui.font_tiny, f"P2: {p2_h.upper()}", PALETTE["text_main"] if self.lan_host.client_connected else PALETTE["text_dim"], 136, max_h=16, min_scale=0.56), (l_box.x + 292, l_box.y + 110))

        for bk, lbl in (("host_toggle", tr("lan_stop_btn") if self.lan_host.running else tr("lan_host_btn")), ("host_start", tr("lan_start_btn"))):
            brc = rc[bk]
            hov = self.lan_hover_btn == bk
            active = (bk == "host_start" and self.lan_host.running) or (bk == "host_toggle" and self.lan_host.running)
            fill = (238, 238, 238) if (hov or (bk == "host_start" and self.lan_host.client_connected)) else ((44, 44, 44) if active else (26, 26, 26))
            border = (252, 252, 252) if (hov or active) else (92, 92, 92)
            pygame.draw.rect(self.screen, fill, brc, border_radius=8)
            pygame.draw.rect(self.screen, border, brc, 1, border_radius=8)
            blit_text_fitted(self.screen, brc, self.ui.font_small, lbl, (12, 12, 12) if (fill[0] > 180) else PALETTE["text_main"], pad_x=10, min_scale=0.54)

        # Right column: Join
        r_box = rc["right"]
        pygame.draw.rect(self.screen, (16, 16, 16), r_box, border_radius=10)
        pygame.draw.rect(self.screen, (180, 180, 180) if self.lan_client.connected else (72, 72, 72), r_box, 1, border_radius=10)

        sc_rc = rc["scan"]
        sc_hov = self.lan_hover_btn == "scan"
        pygame.draw.rect(self.screen, (236, 236, 236) if sc_hov else (32, 32, 32), sc_rc, border_radius=7)
        pygame.draw.rect(self.screen, (250, 250, 250) if sc_hov else (112, 112, 112), sc_rc, 1, border_radius=7)
        sc_lbl = tr("lan_scanning") if self._lan_scanning else tr("lan_scan_btn")
        blit_text_fitted(self.screen, sc_rc, self.ui.font_small, sc_lbl, (12, 12, 12) if sc_hov else PALETTE["text_main"], pad_x=10, min_scale=0.54)

        if self.lan_client.connected:
            c_ping = f" · {self.lan_client.ping_ms} ms" if self.lan_client.ping_ms > 0 else ""
            c_info = f"{self.lan_client.host_name or 'Host'} ({tr_mode(self.lan_client.game_mode)}){c_ping}"
            info_rc = pygame.Rect(r_box.x + 18, rc["rows"][0].y + 8, r_box.w - 36, 54)
            pygame.draw.rect(self.screen, (28, 28, 28), info_rc, border_radius=7)
            pygame.draw.rect(self.screen, (210, 210, 210), info_rc, 1, border_radius=7)
            blit_text_fitted(self.screen, pygame.Rect(info_rc.x, info_rc.y + 4, info_rc.w, 24), self.ui.font_small, c_info, (248, 248, 248), pad_x=10, min_scale=0.54)
            blit_text_fitted(self.screen, pygame.Rect(info_rc.x, info_rc.y + 28, info_rc.w, 22), self.ui.font_tiny, tr("lan_status_client"), PALETTE["text_muted"], pad_x=10, min_scale=0.54)
        elif not self.lan_discovered:
            ns_s = fit_text_surf(self.ui.font_tiny, tr("lan_no_servers"), PALETTE["text_dim"], r_box.w - 32, min_scale=0.56)
            self.screen.blit(ns_s, (r_box.centerx - ns_s.get_width() // 2, rc["rows"][1].y + 4))
        else:
            for idx, r_rc in enumerate(rc["rows"]):
                if idx >= len(self.lan_discovered):
                    break
                srv = self.lan_discovered[idx]
                hov = self.lan_hover_btn == f"row_{idx}"
                sel = self.lan_ip_input == f"{srv['ip']}:{srv['port']}"
                pygame.draw.rect(self.screen, (48, 48, 48) if (sel or hov) else (24, 24, 24), r_rc, border_radius=6)
                pygame.draw.rect(self.screen, (216, 216, 216) if sel else (78, 78, 78), r_rc, 1, border_radius=6)
                run_tag = " [IN-RUN]" if srv.get("in_run") else ""
                r_txt = f"{srv.get('host_name', 'Host')}  ·  {srv['ip']}:{srv['port']}  ({srv.get('players', 1)}/2){run_tag}"
                blit_text_fitted(self.screen, r_rc, self.ui.font_tiny, r_txt, PALETTE["text_main"], align="left", pad_x=10, min_scale=0.54)

        # P2 Hero Picker in LAN Lobby
        p2_pick_h = HERO_ROSTER[self.selected_p2_hero_idx % len(HERO_ROSTER)]
        for pk_key, pk_lbl in (("p2_prev", "<"), ("p2_next", ">")):
            pk_rc = rc[pk_key]
            pk_h = self.lan_hover_btn == pk_key
            pygame.draw.rect(self.screen, (236, 236, 236) if pk_h else (30, 30, 30), pk_rc, border_radius=6)
            pygame.draw.rect(self.screen, (250, 250, 250) if pk_h else (96, 96, 96), pk_rc, 1, border_radius=6)
            blit_text_fitted(self.screen, pk_rc, self.ui.font_small, pk_lbl, (12, 12, 12) if pk_h else PALETTE["text_main"], pad_x=4)
        p2_brc = rc["p2_box"]
        pygame.draw.rect(self.screen, (22, 22, 22), p2_brc, border_radius=6)
        pygame.draw.rect(self.screen, (112, 112, 112), p2_brc, 1, border_radius=6)
        p2_h_name = p2_pick_h.get("name_ru" if GAME_SETTINGS.get("language", "ru") == "ru" else "name_en", p2_pick_h["id"]).upper()
        blit_text_fitted(self.screen, p2_brc, self.ui.font_tiny, f"{tr('lan_p2_hero')} {p2_h_name}", PALETTE["text_main"], pad_x=8, min_scale=0.54)

        ip_rc = rc["ip_box"]
        pygame.draw.rect(self.screen, (10, 10, 10), ip_rc, border_radius=7)
        pygame.draw.rect(self.screen, (214, 214, 214), ip_rc, 1, border_radius=7)
        blit_text_fitted(self.screen, ip_rc, self.ui.font_med, f"IP: {self.lan_ip_input}_", (245, 245, 245), align="left", pad_x=12, min_scale=0.56)

        for ch, krc in rc["keypad"]:
            kh = self.lan_hover_btn == f"kp_{ch}"
            pygame.draw.rect(self.screen, (236, 236, 236) if kh else (30, 30, 30), krc, border_radius=6)
            pygame.draw.rect(self.screen, (250, 250, 250) if kh else (84, 84, 84), krc, 1, border_radius=6)
            blit_text_fitted(self.screen, krc, self.ui.font_small, ch, (12, 12, 12) if kh else PALETTE["text_main"], pad_x=4)

        j_rc = rc["join_toggle"]
        j_hov = self.lan_hover_btn == "join_toggle"
        j_act = self.lan_client.connected
        j_fill = (238, 238, 238) if (j_hov or j_act) else (28, 28, 28)
        pygame.draw.rect(self.screen, j_fill, j_rc, border_radius=8)
        pygame.draw.rect(self.screen, (252, 252, 252) if (j_hov or j_act) else (120, 120, 120), j_rc, 1, border_radius=8)
        j_lbl = tr("lan_disc_btn") if j_act else tr("lan_join_btn")
        blit_text_fitted(self.screen, j_rc, self.ui.font_small, j_lbl, (12, 12, 12) if (j_hov or j_act) else PALETTE["text_main"], pad_x=10, min_scale=0.54)

        hint_s = fit_text_surf(self.ui.font_tiny, self.lan_status or tr("lan_hint"), (218, 218, 218) if self.lan_status else PALETTE["text_muted"], pr.w - 48, max_h=16, min_scale=0.54)
        self.screen.blit(hint_s, (vw // 2 - hint_s.get_width() // 2, pr.bottom - 86))

        bk_rc = rc["back"]
        bk_h = self.lan_hover_btn == "back"
        pygame.draw.rect(self.screen, (238, 238, 238) if bk_h else (28, 28, 28), bk_rc, border_radius=8)
        pygame.draw.rect(self.screen, (252, 252, 252) if bk_h else (112, 112, 112), bk_rc, 1, border_radius=8)
        blit_text_fitted(self.screen, bk_rc, self.ui.font_med, tr("lan_back_btn"), (12, 12, 12) if bk_h else PALETTE["text_main"], pad_x=10, min_scale=0.55)

    def _push_lan_snapshot(self):
        if getattr(self, "lan_host", None) is None or not self.lan_host.running or not self.lan_host.client_connected:
            return
        try:
            snap = self._build_lan_snapshot()
            if snap:
                self.lan_host.send_snapshot(snap)
        except Exception as exc:
            append_crash_log("LAN snapshot error", f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}")

    def _build_lan_snapshot(self):
        rm = self.current_room

        def _ser_p(p):
            if p is None:
                return None
            act_it = getattr(p, "active_item", None)
            act_name = tr_item_name(act_it) if isinstance(act_it, dict) else ""
            return {
                "x": round(p.x, 1),
                "y": round(p.y, 1),
                "vx": round(float(getattr(p, "vx", 0.0)), 2),
                "vy": round(float(getattr(p, "vy", 0.0)), 2),
                "r": round(getattr(p, "radius", 14.0), 1),
                "hp": int(p.hp),
                "max_hp": int(p.max_hp),
                "soul_hp": int(p.soul_hp),
                "black_hp": int(p.black_hp),
                "coins": int(p.coins),
                "bombs": int(p.bombs),
                "keys": int(p.keys),
                "kills": int(p.kills),
                "hero_id": str(p.hero_id),
                "fx": round(float(p.facing[0]), 2),
                "fy": round(float(p.facing[1]), 2),
                "air_z": round(float(getattr(p, "air_z", 0.0)), 1),
                "dmg": round(float(p.get_effective_damage()), 2),
                "spd": round(float(p.get_effective_speed()), 2),
                "luck": float(getattr(p, "luck", 0)),
                "holy_mantle": bool(getattr(p, "holy_mantle", False)),
                "mantle_broken": bool(getattr(p, "mantle_broken_room", False)),
                "lantern_fuel": round(float(getattr(p, "lantern_fuel", 1.0)), 3),
                "lantern_bonus": round(float(getattr(p, "lantern_bonus", 1.0)), 3),
                "has_steam_sale": bool(getattr(p, "has_steam_sale", False)),
                "compass_reveal": bool(getattr(p, "compass_reveal", False)),
                "noclip": bool(getattr(p, "noclip", False)),
                "hurt_flash": round(float(getattr(p, "hurt_flash", 0.0)), 1),
                "dash_cd": round(float(getattr(p, "dash_cd", 0.0)), 1),
                "dash_max_cd": round(float(getattr(p, "dash_max_cd", 95.0)), 1),
                "jump_cd": round(float(getattr(p, "jump_cd", 0.0)), 1),
                "jump_max_cd": round(float(getattr(p, "jump_max_cd", 120.0)), 1),
                "invis_timer": round(float(getattr(p, "invis_timer", 0.0)), 1),
                "invis_cd": round(float(getattr(p, "invis_cd", 0.0)), 1),
                "invis_max_cd": round(float(getattr(p, "invis_max_cd", 360.0)), 1),
                "melee_cd": round(float(getattr(p, "melee_cd", 0.0)), 1),
                "melee_max_cd": round(float(getattr(p, "melee_max_cd", 22.0)), 1),
                "melee_combo": int(getattr(p, "melee_combo_step", 0)),
                "melee_combo_timer": round(float(getattr(p, "melee_combo_timer", 0.0)), 1),
                "melee_slash": round(float(getattr(p, "melee_slash_timer", 0.0)), 1),
                "melee_ang": round(float(getattr(p, "melee_slash_angle", 0.0)), 2),
                "charge": int(getattr(p, "active_charge", 0)),
                "max_charge": int(getattr(p, "max_charge", 1)),
                "has_relic": act_it is not None,
                "relic_name": str(act_name)[:24],
                "invuln": round(float(getattr(p, "invuln_timer", 0.0)), 1),
                "effects": {
                    str(ek): round(float(ev), 1)
                    for ek, ev in getattr(p, "active_effects", {}).items()
                    if ev > 0.0
                },
                "act_items": [
                    {
                        "id": str(sl["item"].get("id", "")),
                        "c": int(sl.get("charge", 0)),
                        "m": int(sl.get("max_charge", 1)),
                    }
                    for sl in getattr(p, "active_items", ())
                    if isinstance(sl, dict) and isinstance(sl.get("item"), dict) and sl["item"].get("id")
                ],
                "act_slot": int(getattr(p, "active_slot", 0)),
                "pas_ids": [
                    str(it.get("id", ""))
                    for it in getattr(p, "collected_items", ())
                    if isinstance(it, dict) and it.get("id")
                ],
                "inv_page": int(getattr(p, "inventory_page", 0)),
                "sel_inv": int(getattr(p, "selected_inv_idx", 0)),
            }

        doors_data = []
        if rm:
            for d in rm.doors.values():
                if not d.secret or d.opened:
                    doors_data.append([d.direction, d.rect.x, d.rect.y, d.rect.w, d.rect.h, bool(d.locked), bool(d.opened), False, str(getattr(d, "target_type", "normal"))])
            if getattr(rm, "devil_door", None) is not None:
                dd = rm.devil_door
                doors_data.append([dd.direction, dd.rect.x, dd.rect.y, dd.rect.w, dd.rect.h, False, True, True, "devil"])

        minimap_data = []
        if isinstance(getattr(self, "rooms", None), dict):
            for coord, r_obj in self.rooms.items():
                r_type = str(getattr(r_obj, "room_type", "normal"))
                is_vis = bool(getattr(r_obj, "visited", False) or coord == self.current_coord)
                if is_vis:
                    minimap_data.append([int(coord[0]), int(coord[1]), r_type, bool(getattr(r_obj, "cleared", True)), True])
                elif r_type != "secret":
                    cx0, cy0 = coord
                    has_vis_nb = any(
                        getattr(self.rooms.get(nb_c), "visited", False)
                        for nb_c in ((cx0 + 1, cy0), (cx0 - 1, cy0), (cx0, cy0 + 1), (cx0, cy0 - 1))
                    )
                    if has_vis_nb:
                        minimap_data.append([int(coord[0]), int(coord[1]), r_type, bool(getattr(r_obj, "cleared", True)), False])

        banner_on = getattr(self.ui, "banner_timer", 0.0) > 0.0
        banner_txt = str(getattr(self.ui, "banner_text", "") or "") if banner_on else ""
        banner_sub = str(getattr(self.ui, "banner_sub", "") or "") if banner_on else ""
        banner_item = getattr(self.ui, "banner_item", None) if banner_on else None
        banner_item_id = str(banner_item.get("id", "")) if isinstance(banner_item, dict) else ""
        banner_dur = round(float(getattr(self.ui, "banner_max_timer", 125.0)), 1) if banner_on else 0.0
        if banner_on and banner_txt:
            sig_b = (banner_txt, banner_sub, banner_item_id)
            if sig_b != self._last_banner_tracked or getattr(self.ui, "banner_timer", 0.0) >= getattr(self.ui, "banner_max_timer", 1.0) - 2.5:
                if sig_b != self._last_banner_tracked:
                    self._banner_seq += 1
                    self._last_banner_tracked = sig_b
        else:
            self._last_banner_tracked = None

        npcs_data = []
        machines_data = []
        beggars_data = []
        keepers_data = []
        if rm:
            for n in getattr(rm, "mystical_npcs", []):
                if getattr(n, "alive", True):
                    npcs_data.append([round(float(getattr(n, "x", 0)), 1), round(float(getattr(n, "y", 0)), 1), str(getattr(n, "kind", "pale_wanderer")), bool(getattr(n, "used", False))])
            for m_obj in getattr(rm, "machines", []):
                if getattr(m_obj, "alive", True):
                    machines_data.append(
                        [
                            round(float(getattr(m_obj, "x", 0)), 1),
                            round(float(getattr(m_obj, "y", 0)), 1),
                            str(getattr(m_obj, "kind", "slot_machine")),
                            bool(getattr(m_obj, "playing", False)),
                            int(getattr(m_obj, "track_idx", 0)),
                        ]
                    )
            for bg in getattr(rm, "beggars", []):
                if getattr(bg, "alive", True):
                    beggars_data.append([round(float(getattr(bg, "x", 0)), 1), round(float(getattr(bg, "y", 0)), 1), str(getattr(bg, "kind", "coin_beggar"))])
            for sk in getattr(rm, "shopkeepers", []):
                if getattr(sk, "alive", True):
                    keepers_data.append([round(float(getattr(sk, "x", 0)), 1), round(float(getattr(sk, "y", 0)), 1), str(getattr(sk, "variant", "keeper_classic"))])

        trap_r = getattr(rm, "trapdoor_rect", None) if rm else None
        vic_r = getattr(rm, "victory_portal_rect", None) if rm else None
        sac_sp = getattr(rm, "sacrifice_spike", None) if rm else None
        dice_fl = getattr(rm, "dice_floor", None) if rm else None

        prompt_data = None
        if self.pending_pedestal_prompt is not None:
            ped_p = self.pending_pedestal_prompt.get("pedestal")
            cp_p = self.pending_pedestal_prompt.get("player")
            if ped_p is not None and getattr(ped_p, "alive", True) and getattr(ped_p, "item", None):
                prompt_data = {
                    "item_id": str(ped_p.item.get("id", "")),
                    "selected": int(self.pending_pedestal_prompt.get("selected", 0)),
                    "can_afford": bool(self.pending_pedestal_prompt.get("can_afford", True)),
                    "cost_text": str(self.pending_pedestal_prompt.get("cost_text", "")),
                    "player_tag": str(getattr(cp_p, "player_tag", "P1") or "P1"),
                }

        def _pack_tear_flags(t_obj):
            f = []
            if getattr(t_obj, "bone", False):
                f.append("b")
            if getattr(t_obj, "brimstone", False):
                f.append("r")
            if getattr(t_obj, "homing", False):
                f.append("h")
            if getattr(t_obj, "holy", False):
                f.append("o")
            if getattr(t_obj, "explosive", False):
                f.append("e")
            if getattr(t_obj, "lobbed", False):
                f.append("l")
            if getattr(t_obj, "shockwave", False):
                f.append("s")
            if getattr(t_obj, "vortex", False):
                f.append("v")
            if getattr(t_obj, "chain_arc", False):
                f.append("c")
            if getattr(t_obj, "ambush", False):
                f.append("a")
            return "".join(f)

        enemies_data = []
        if rm:
            for e in rm.enemies:
                if e.alive:
                    enemies_data.append(
                        {
                            "id": int(id(e)),
                            "x": round(e.x, 1),
                            "y": round(e.y, 1),
                            "vx": round(float(getattr(e, "vx", 0.0)), 2),
                            "vy": round(float(getattr(e, "vy", 0.0)), 2),
                            "r": round(e.radius, 1),
                            "hp": int(e.hp),
                            "max_hp": int(max(1, e.max_hp)),
                            "type": str(getattr(e, "enemy_type", "gaper")),
                            "hit_flash": round(float(getattr(e, "hit_flash", 0.0)), 1),
                            "dir": round(float(getattr(e, "dir_angle", 0.0)), 2),
                            "disguised": bool(getattr(e, "disguised", False)),
                            "air_z": round(float(getattr(e, "air_z", 0.0)), 1),
                            "slam_ring": round(float(getattr(e, "slam_ring_timer", 0.0)), 1),
                            "trail": [[round(float(tx), 1), round(float(ty), 1)] for tx, ty in list(getattr(e, "trail", ()))[-5:]],
                        }
                    )

        bosses_data = []
        if rm:
            for b in rm.bosses:
                if b.alive:
                    w_max = max(1.0, float(getattr(b, "windup_max", 1.0)))
                    w_cur = float(getattr(b, "windup_timer", 0.0))
                    wp = round(1.0 - (w_cur / w_max), 2) if w_cur > 0 else 0.0
                    bosses_data.append(
                        {
                            "id": int(id(b)),
                            "x": round(b.x, 1),
                            "y": round(b.y, 1),
                            "r": round(b.radius, 1),
                            "hp": int(b.hp),
                            "max_hp": int(max(1, b.max_hp)),
                            "name": str(getattr(b, "name", "BOSS")),
                            "key": str(getattr(b, "boss_key", "")),
                            "style": str(getattr(b, "style", "jumper")),
                            "lum": int(getattr(b, "lum", 182)),
                            "phase": int(getattr(b, "phase", 1)),
                            "expr": str(getattr(b, "expression", "idle")),
                            "hit_flash": round(float(getattr(b, "hit_flash", 0.0)), 1),
                            "air_z": round(float(getattr(b, "air_z", 0.0)), 1),
                            "airborne": bool(getattr(b, "airborne", False)),
                            "tx": round(float(getattr(b, "target_x", b.x)), 1),
                            "ty": round(float(getattr(b, "target_y", b.y)), 1),
                            "tr": round(float(getattr(b, "telegraph_r", 0.0)), 1),
                            "tlines": [[int(l[0]), int(l[1]), int(l[2]), int(l[3])] for l in getattr(b, "telegraph_lines", ())],
                            "segs": [[round(float(sx), 1), round(float(sy), 1)] for sx, sy in getattr(b, "segments", ())],
                            "sx": round(float(getattr(b, "scale_x", 1.0)), 2),
                            "sy": round(float(getattr(b, "scale_y", 1.0)), 2),
                            "lx": round(float(getattr(b, "look_x", 0.0)), 2),
                            "ly": round(float(getattr(b, "look_y", 1.0)), 2),
                            "wp": wp,
                        }
                    )

        tears_data = [
            {
                "id": int(id(t)),
                "x": round(t.x, 1),
                "y": round(t.y, 1),
                "vx": round(float(t.vx), 2),
                "vy": round(float(t.vy), 2),
                "r": round(getattr(t, "radius", 6.0), 1),
                "air_z": round(float(getattr(t, "air_z", 0.0)), 1),
                "max_r": round(float(getattr(t, "max_range", 420.0)), 1),
                "trav": round(float(getattr(t, "traveled", 0.0)), 1),
                "br": round(float(getattr(t, "blast_radius", 62.0)), 1),
                "lum": int(t.color[0]) if getattr(t, "color", None) else 242,
                "flags": _pack_tear_flags(t),
            }
            for t in self.tears
            if t.alive
        ]

        eproj_data = [
            {
                "id": int(id(pr)),
                "x": round(pr.x, 1),
                "y": round(pr.y, 1),
                "vx": round(float(getattr(pr, "vx", 0.0)), 2),
                "vy": round(float(getattr(pr, "vy", 0.0)), 2),
                "r": round(getattr(pr, "radius", 6.0), 1),
                "air_z": round(float(getattr(pr, "air_z", 0.0)), 1),
                "lob": bool(getattr(pr, "lobbed", False)),
                "tx": round(float(getattr(pr, "target_x", pr.x)), 1),
                "ty": round(float(getattr(pr, "target_y", pr.y)), 1),
                "br": round(float(getattr(pr, "blast_radius", 52.0)), 1),
                "el": round(float(getattr(pr, "elapsed", 0.0)), 1),
                "tf": round(float(getattr(pr, "total_frames", 46.0)), 1),
            }
            for pr in self.enemy_projectiles
            if pr.alive
        ]

        return {
            "type": "state",
            "in_run": self.state in ("PLAYING", "PAUSED", "CHAOS_DRAFT", "CUTSCENE", "GAME_OVER", "VICTORY") or (self.state == "LAN_LOBBY" and self.prev_state == "PAUSED"),
            "state": str(self.state),
            "floor": int(self.floor_level),
            "floor_label": str(tr_floor(self.floor_level)),
            "floor_modifier": dict(self.floor_modifier) if isinstance(self.floor_modifier, dict) else None,
            "mode": str(self.game_mode),
            "wave": int(self.wave_num),
            "timescale": round(float(self.timescale), 2),
            "coord": [int(self.current_coord[0]), int(self.current_coord[1])],
            "cleared": bool(rm.cleared) if rm else True,
            "room_type": str(rm.room_type) if rm else "start",
            "torches": [[int(tx), int(ty)] for tx, ty in getattr(rm, "torch_positions", [])] if rm else [],
            "p1": _ser_p(self.player),
            "p2": _ser_p(self.player2),
            "obstacles": [
                [int(obs.rect.centerx), int(obs.rect.centery), int(obs.size), str(obs.kind), round(float(getattr(obs, "aim_angle", 0.0)), 2)]
                for obs in (rm.obstacles if rm else [])
                if getattr(obs, "alive", True)
            ],
            "doors": doors_data,
            "trapdoor": [trap_r.x, trap_r.y, trap_r.w, trap_r.h] if trap_r is not None else None,
            "victory_portal": [vic_r.x, vic_r.y, vic_r.w, vic_r.h] if vic_r is not None else None,
            "sacrifice_spike": [round(float(sac_sp.x), 1), round(float(sac_sp.y), 1)] if sac_sp is not None else None,
            "dice_floor": [round(float(dice_fl.x), 1), round(float(dice_fl.y), 1), int(dice_fl.pips), bool(dice_fl.used)] if dice_fl is not None else None,
            "monoliths": [[round(float(m_o.x), 1), round(float(m_o.y), 1), bool(getattr(m_o, "activated", False))] for m_o in getattr(rm, "monoliths", []) if getattr(m_o, "alive", True)] if rm else [],
            "npcs": npcs_data,
            "machines": machines_data,
            "beggars": beggars_data,
            "shopkeepers": keepers_data,
            "enemies": enemies_data,
            "bosses": bosses_data,
            "pickups": [
                [round(p.x, 1), round(p.y, 1), str(getattr(p, "kind", "coin")), int(getattr(p, "price", 0))]
                for p in (rm.pickups if rm else [])
                if p.alive
            ],
            "pedestals": [
                [round(ped.x, 1), round(ped.y, 1), str(ped.item.get("id", "")) if ped.item else "", str(tr_item_name(ped.item)) if ped.item else "", int(getattr(ped, "price", 0)), int(getattr(ped, "devil_cost", 0))]
                for ped in (rm.pedestals if rm else [])
                if ped.alive
            ],
            "bombs": [[round(b.x, 1), round(b.y, 1), round(float(getattr(b, "timer", 60.0)), 1)] for b in self.bombs],
            "tears": tears_data,
            "eproj": eproj_data,
            "minimap": minimap_data,
            "quests": self.quest_manager.serialize(),
            "banner": banner_txt,
            "banner_sub": banner_sub,
            "banner_item_id": banner_item_id,
            "banner_dur": banner_dur,
            "banner_seq": int(self._banner_seq),
            "pickup_prompt": prompt_data,
            "sfx": consume_recent_sfx(),
        }

    def _update_lan_client(self, dt):
        self.ui.update(dt)
        if not self.lan_client.connected:
            stop_computer_audio()
            self.touch.reset()
            self.lan_status = self.lan_client.last_error or tr("lan_status_off")
            self.state = "LAN_LOBBY"
            return
        if self._lan_client_shake > 0.0:
            self._lan_client_shake = max(0.0, self._lan_client_shake - dt)
        st = self.lan_client.get_latest_state()
        if st is not None:
            host_state = str(st.get("state", "PLAYING"))
            if not st.get("in_run", True) or host_state == "MENU":
                stop_computer_audio()
                self.touch.reset()
                self.state = "LAN_LOBBY"
                return
            seq = int(st.get("seq", -1))
            if seq != self._lan_last_sfx_seq:
                self._lan_last_sfx_seq = seq
                for sfx_name in st.get("sfx", ()):
                    play_sound(str(sfx_name))
                    if sfx_name in ("bomb", "boss"):
                        self._lan_client_shake = max(self._lan_client_shake, 8.0)
                p2_d = st.get("p2")
                if p2_d:
                    cur_hp = int(p2_d.get("hp", 0)) + int(p2_d.get("soul_hp", 0)) + int(p2_d.get("black_hp", 0))
                    if self._lan_client_prev_hp is not None and cur_hp < self._lan_client_prev_hp:
                        self._lan_client_shake = max(self._lan_client_shake, 10.0)
                    self._lan_client_prev_hp = cur_hp

            b_seq = int(st.get("banner_seq", 0))
            b_txt = str(st.get("banner", "") or "")
            if b_seq > 0 and b_seq != self._lan_banner_seq and b_txt:
                self._lan_banner_seq = b_seq
                b_it = get_item_by_id(st.get("banner_item_id", "")) if st.get("banner_item_id") else None
                b_dur = max(35.0, float(st.get("banner_dur", 120.0) or 120.0))
                self.ui.show_banner(b_txt, str(st.get("banner_sub", "") or ""), duration=b_dur, item=b_it)

            q_data = st.get("quests")
            if isinstance(q_data, dict):
                q_sig = (
                    q_data.get("completed_total", 0),
                    tuple((tr_q.get("id"), tr_q.get("tier"), tr_q.get("progress"), tr_q.get("completed")) for tr_q in q_data.get("tracks", ())),
                )
                if q_sig != self._lan_quests_sig:
                    self._lan_quests_sig = q_sig
                    self.quest_manager.deserialize(q_data)

            # Spatial audio for active computer terminals relative to LAN client's listener position
            if host_state == "PLAYING":
                listener = st.get("p2") or st.get("p1")
                best_comp = None
                if listener:
                    lx = float(listener.get("x", 0.0))
                    ly = float(listener.get("y", 0.0))
                    best_d2 = 1e12
                    for m_entry in st.get("machines", ()):
                        if len(m_entry) >= 5 and str(m_entry[2]) == "computer_terminal" and bool(m_entry[3]):
                            d2 = (float(m_entry[0]) - lx) ** 2 + (float(m_entry[1]) - ly) ** 2
                            if d2 < best_d2:
                                best_d2 = d2
                                best_comp = m_entry
                if best_comp is not None and listener:
                    update_computer_audio(True, int(best_comp[4]), float(best_comp[0]), float(best_comp[1]), float(listener["x"]), float(listener["y"]))
                else:
                    stop_computer_audio()
            else:
                stop_computer_audio()

            # Smooth delta-time animation accumulation matching host rates
            floor = int(st.get("floor", 1))
            coord = tuple(st.get("coord", [0, 0]))
            rtype = str(st.get("room_type", "normal"))
            rkey = (floor, coord, rtype)
            if rkey != self._lan_last_room_key:
                self._lan_last_room_key = rkey
                self._lan_anim.clear()

            sim_dt = dt * float(st.get("timescale", 1.0) or 1.0) if host_state == "PLAYING" else 0.0
            for tag, pd in (("P1", st.get("p1")), ("P2", st.get("p2"))):
                if not isinstance(pd, dict):
                    continue
                ak = f"player_{tag}"
                ast = self._lan_anim.get(ak)
                px = float(pd.get("x", 0.0))
                py = float(pd.get("y", 0.0))
                fx = float(pd.get("fx", 0.0))
                fy = float(pd.get("fy", 1.0))
                vx = float(pd.get("vx", 0.0))
                vy = float(pd.get("vy", 0.0))
                moving = (vx * vx + vy * vy) > 0.04
                if ast is None:
                    ast = {
                        "walk": 0.0,
                        "idle": 0.0,
                        "cloak": [(px, py + i * 3.5) for i in range(7)],
                    }
                    self._lan_anim[ak] = ast
                ast["idle"] += 0.08 * dt
                if moving and sim_dt > 0.0:
                    ast["walk"] += 0.26 * sim_dt
                if sim_dt > 0.0 or moving:
                    nodes = ast["cloak"]
                    nodes[0] = (px - fx * 4.0, py - fy * 4.0)
                    follow = min(0.85, 0.42 * max(0.2, dt))
                    for ci in range(1, len(nodes)):
                        tx, ty = nodes[ci - 1]
                        cx_n, cy_n = nodes[ci]
                        nodes[ci] = (
                            cx_n + (tx - cx_n) * follow,
                            cy_n + (ty + 3.2 - cy_n) * follow,
                        )

            active_eids = set()
            for e_entry in st.get("enemies", ()):
                if isinstance(e_entry, dict):
                    ek = f"enemy_{e_entry.get('id')}"
                    active_eids.add(ek)
                    self._lan_anim[ek] = self._lan_anim.get(ek, 0.0) + 0.14 * sim_dt
            for b_entry in st.get("bosses", ()):
                if isinstance(b_entry, dict):
                    bk = f"boss_{b_entry.get('id')}"
                    active_eids.add(bk)
                    self._lan_anim[bk] = self._lan_anim.get(bk, 0.0) + 0.12 * sim_dt
            rm_cached = self._lan_room_cache.get(rkey)
            if rm_cached is not None and hasattr(rm_cached, "update"):
                rm_cached.update(dt)

        keys = pygame.key.get_pressed()
        mx = (1 if keys[get_keybind("right")] else 0) - (1 if keys[get_keybind("left")] else 0)
        my = (1 if keys[get_keybind("down")] else 0) - (1 if keys[get_keybind("up")] else 0)
        ax = (1 if keys[get_keybind("fire_right")] else 0) - (1 if keys[get_keybind("fire_left")] else 0)
        ay = (1 if keys[get_keybind("fire_down")] else 0) - (1 if keys[get_keybind("fire_up")] else 0)
        dash = bool(keys[get_keybind("dash")] or keys[pygame.K_c])
        jump = self._lan_client_actions.pop("jump", False)
        stealth = self._lan_client_actions.pop("stealth", False)
        melee = self._lan_client_actions.pop("melee", False)
        bomb = self._lan_client_actions.pop("bomb", False)
        relic = self._lan_client_actions.pop("relic", False)
        cycle_relic = self._lan_client_actions.pop("cycle_relic", False)
        confirm = self._lan_client_actions.pop("confirm", False)
        cancel = self._lan_client_actions.pop("cancel", False)
        interact = self._lan_client_actions.pop("interact", False)
        if self.touch.is_active():
            tmx, tmy = self.touch.move_vec
            if mx == 0 and my == 0 and (abs(tmx) > 0.01 or abs(tmy) > 0.01):
                mx, my = tmx, tmy
            tax, tay = self.touch.aim_dir
            if ax == 0 and ay == 0 and (tax != 0 or tay != 0):
                ax, ay = tax, tay
            if self.touch.dash_pressed:
                dash = True
            t_act = self.touch.consume_actions()
            if t_act.get("pause"):
                stop_computer_audio()
                self.touch.reset()
                self.state = "LAN_LOBBY"
                return
            jump = jump or bool(t_act.get("jump"))
            stealth = stealth or bool(t_act.get("stealth"))
            melee = melee or bool(t_act.get("melee"))
            bomb = bomb or bool(t_act.get("bomb"))
            relic = relic or bool(t_act.get("relic"))
            interact = interact or bool(t_act.get("interact"))
        self.lan_client.send_input(
            mx,
            my,
            ax,
            ay,
            dash=dash,
            jump=jump,
            stealth=stealth,
            bomb=bomb,
            relic=relic,
            melee=melee,
            cycle_relic=cycle_relic,
            confirm=confirm,
            cancel=cancel,
            interact=interact,
        )

    def _draw_lan_client(self):
        import types as _types
        vw = get_view_width()
        world_ox = get_world_offset_x()
        self.screen.fill((5, 5, 5))
        st = self.lan_client.get_interpolated_state() or self.lan_client.get_latest_state()
        if not st:
            if world_ox > 0:
                draw_wide_backdrop(self.screen, vw, world_ox, extra_pad=32)
            wt = render_text_cached(self.ui.font_big, tr("lan_status_wait"), PALETTE["text_main"])
            self.screen.blit(wt, (vw // 2 - wt.get_width() // 2, SCREEN_HEIGHT // 2 - 20))
            return

        floor = int(st.get("floor", 1))
        coord = tuple(st.get("coord", [0, 0]))
        rtype = str(st.get("room_type", "normal"))
        gmode = str(st.get("mode", "classic"))
        fmod = st.get("floor_modifier") if isinstance(st.get("floor_modifier"), dict) else None
        ckey = (floor, coord, rtype)
        rm = self._lan_room_cache.get(ckey)
        if rm is None:
            if len(self._lan_room_cache) >= 6:
                self._lan_room_cache.clear()
            rm = Room(coord, rtype, floor, layout_key="empty", game_mode=gmode, floor_modifier=fmod, build_contents=False)
            rm.obstacles = []
            rm.enemies = []
            rm.bosses = []
            rm.pickups = []
            rm.pedestals = []
            rm.machines = []
            rm.monoliths = []
            rm.mystical_npcs = []
            self._lan_room_cache[ckey] = rm
        rm.floor_modifier = fmod
        rm.cleared = bool(st.get("cleared", True))
        synced_torches = st.get("torches")
        if isinstance(synced_torches, list) and synced_torches:
            rm.torch_positions = [(int(t[0]), int(t[1])) for t in synced_torches]

        world = self._world_surf if world_ox > 0 else self.screen
        if rm._baked_bg is None:
            rm._bake_background()
        world.blit(rm._baked_bg, (0, 0))

        # Torches from host room
        for idx, (tx, ty) in enumerate(rm.torch_positions):
            flicker = 0.5 + 0.5 * math.sin(self.time_acc * 0.18 + idx * 1.7)
            step = int(clamp(round(flicker * 5.0), 0, 5))
            t_spr = _get_flame_sprite("torch", step)
            world.blit(t_spr, (tx - t_spr.get_width() // 2, ty - 1 - t_spr.get_height() // 2))

        # Ambient floating dust motes synced to effects setting
        dust_mult = float(get_effects_config().get("dust_mult", 1.0))
        max_dust = max(0, int(round(len(rm.dust_motes) * dust_mult)))
        for dm in rm.dust_motes[:max_dust]:
            p_surf = get_particle_surf(dm["r"], dm["lum"], dm["alpha"])
            world.blit(p_surf, (int(round(dm["x"] - p_surf.get_width() * 0.5)), int(round(dm["y"] - p_surf.get_height() * 0.5))))

        # Dice floor & Sacrifice spike
        dice_d = st.get("dice_floor")
        if isinstance(dice_d, (list, tuple)) and len(dice_d) >= 4:
            df = DiceFloor(dice_d[0], dice_d[1], pips=int(dice_d[2]))
            df.used = bool(dice_d[3])
            df.draw(world)
        sac_d = st.get("sacrifice_spike")
        if isinstance(sac_d, (list, tuple)) and len(sac_d) >= 2:
            SacrificeSpike(sac_d[0], sac_d[1]).draw(world)

        # Doors using crisp cached Door sprites
        is_curse_room = (rtype == "curse")
        cleared_flag = bool(st.get("cleared", True))
        for d in st.get("doors", []):
            dir_s, dx, dy, dw, dh, locked, opened = d[:7]
            is_devil = bool(d[7]) if len(d) > 7 else False
            ttype = str(d[8]) if len(d) > 8 else "normal"
            d_obj = Door(dir_s, (0, 0), target_type=("devil" if is_devil else ttype), locked=bool(locked), secret=False)
            d_obj.rect = pygame.Rect(int(dx), int(dy), int(dw), int(dh))
            d_obj.opened = bool(opened)
            d_obj.draw(world, True if is_devil else cleared_flag, force_curse_spikes=is_curse_room and not is_devil)

        # Trapdoor & Victory Portal matching host visuals
        trap_r = st.get("trapdoor")
        if trap_r:
            trect = pygame.Rect(int(trap_r[0]), int(trap_r[1]), int(trap_r[2]), int(trap_r[3]))
            rm.trapdoor_rect = trect
            pygame.draw.rect(world, (216, 216, 216), trect.inflate(8, 8), border_radius=8)
            pygame.draw.rect(world, (10, 10, 10), trect, border_radius=6)
            for ry in range(trect.top + 8, trect.bottom - 4, 9):
                pygame.draw.line(world, (148, 148, 148), (trect.left + 8, ry), (trect.right - 8, ry), 2)
        else:
            rm.trapdoor_rect = None
        vic_r = st.get("victory_portal")
        if vic_r:
            vrect = pygame.Rect(int(vic_r[0]), int(vic_r[1]), int(vic_r[2]), int(vic_r[3]))
            rm.victory_portal_rect = vrect
            vcx, vcy = vrect.center
            pulse = 0.5 + 0.5 * math.sin(self.time_acc * 0.14)
            step = int(clamp(round(pulse * 5.0), 0, 5))
            p_spr = _get_portal_sprite(step)
            world.blit(p_spr, (vcx - p_spr.get_width() // 2, vcy - p_spr.get_height() // 2))
        else:
            rm.victory_portal_rect = None

        p1 = st.get("p1")
        p2 = st.get("p2")
        light_srcs = [(float(tx), float(ty), 230.0, 0.95) for tx, ty in rm.torch_positions]
        extra_lights = []
        for pl_d in (p1, p2):
            if pl_d and (pl_d.get("hp", 0) + pl_d.get("soul_hp", 0) + pl_d.get("black_hp", 0)) > 0:
                light_srcs.append((float(pl_d["x"]), float(pl_d["y"]), 255.0, 1.15))

        obs_list = st.get("obstacles", [])
        for obs_entry in obs_list:
            if len(obs_entry) >= 5 and isinstance(obs_entry[3], str) and obs_entry[3] == "brazier":
                light_srcs.append((float(obs_entry[0]), float(obs_entry[1]), 220.0, 1.0))

        # Obstacles with real 4x sprites, dynamic shadows, and synced proxies for LightingSystem
        lum_base = gray(rm.theme.get("rock", (82, 82, 82)))[0]
        lum_hi = gray(rm.theme.get("rock_hi", (126, 126, 126)))[0]
        rm_obs_proxies = []
        for obs_entry in obs_list:
            if len(obs_entry) >= 5 and isinstance(obs_entry[3], str):
                ocx, ocy, osize, okind = int(obs_entry[0]), int(obs_entry[1]), int(obs_entry[2]), obs_entry[3]
                aim_ang = float(obs_entry[4]) if len(obs_entry) > 4 else 0.0
                ox, oy, ow, oh = ocx - osize // 2, ocy - osize // 2, osize, osize
            else:
                ox, oy, ow, oh, okind = int(obs_entry[0]), int(obs_entry[1]), int(obs_entry[2]), int(obs_entry[3]), str(obs_entry[4])
                ocx, ocy = ox + ow // 2, oy + oh // 2
                osize = max(24, min(ow, oh))
                aim_ang = 0.0
            rm_obs_proxies.append(
                _types.SimpleNamespace(
                    alive=True,
                    kind=okind,
                    size=osize,
                    rect=pygame.Rect(ox, oy, ow, oh),
                    blocks_light=okind in ("rock", "tinted_rock", "pillar", "urn", "barrier", "turret"),
                )
            )
            lb = min(220, lum_base + 24) if okind == "tinted_rock" else lum_base
            lh = min(245, lum_hi + 28) if okind == "tinted_rock" else lum_hi
            spr = _get_obstacle_sprite(okind, lb, lh, osize)
            if okind in ("rock", "tinted_rock", "pillar", "brazier", "urn", "poop", "barrier", "turret"):
                draw_dynamic_shadow(world, ocx, oy + oh - 5, osize + 14, 18, light_sources=light_srcs, air_z=0.0, alpha=130)
            world.blit(spr, (ox, oy))
            if okind == "brazier":
                step = int(clamp(round((0.5 + 0.5 * math.sin(self.time_acc * 0.24 + ocx)) * 5.0), 0, 5))
                fl_spr = _get_flame_sprite("brazier", step)
                world.blit(fl_spr, (ocx - fl_spr.get_width() // 2, ocy - 2 - fl_spr.get_height() // 2))
            elif okind == "turret":
                bx2 = ocx + int(math.cos(aim_ang) * (osize * 0.42))
                by2 = ocy + int(math.sin(aim_ang) * (osize * 0.42))
                pygame.draw.line(world, (238, 238, 238), (ocx, ocy), (bx2, by2), 4)
                pygame.draw.circle(world, (246, 246, 246), (bx2, by2), 3)
        rm.obstacles = rm_obs_proxies

        # Monoliths, Mystical NPCs, Shopkeepers, Machines & Computer Terminals, Beggars
        npc_age = self.time_acc * 0.08
        for mx_m, my_m, mused in st.get("monoliths", []):
            sh = get_shadow_surf(44, 16, 128)
            world.blit(sh, (int(round(mx_m - sh.get_width() * 0.5)), int(round(my_m + 18 - sh.get_height() * 0.5))))
            draw_npc_visual(world, "lore_monolith", mx_m, my_m, scale=1.0, age=npc_age, activated=bool(mused))
            extra_lights.append((float(mx_m), float(my_m) - 8.0, 120.0 if mused else 96.0, 175 if mused else 135))

        for n_entry in st.get("npcs", []):
            nx, ny, nkind = float(n_entry[0]), float(n_entry[1]), str(n_entry[2])
            nused = bool(n_entry[3]) if len(n_entry) > 3 else False
            sh = get_shadow_surf(42, 16, 120)
            world.blit(sh, (int(round(nx - sh.get_width() * 0.5)), int(round(ny + 18 - sh.get_height() * 0.5))))
            draw_npc_visual(world, nkind, nx, ny, scale=1.0, age=npc_age, activated=nused)
            extra_lights.append((nx, ny - 8.0, 108.0, 150))

        for sk_entry in st.get("shopkeepers", []):
            sx_k, sy_k, svar = float(sk_entry[0]), float(sk_entry[1]), str(sk_entry[2])
            sh = get_shadow_surf(44, 16, 122)
            world.blit(sh, (int(sx_k - sh.get_width() // 2), int(sy_k + 16)))
            draw_npc_visual(world, svar, sx_k, sy_k, scale=1.0, age=npc_age)

        for m_entry in st.get("machines", []):
            mx_c, my_c, mkind = float(m_entry[0]), float(m_entry[1]), str(m_entry[2])
            mplay = bool(m_entry[3]) if len(m_entry) > 3 else False
            mtrk = int(m_entry[4]) if len(m_entry) > 4 else 0
            sh_outer = get_shadow_surf(58, 22, 96)
            sh_core = get_shadow_surf(44, 14, 162)
            world.blit(sh_outer, (int(mx_c - sh_outer.get_width() // 2), int(my_c + 16)))
            world.blit(sh_core, (int(mx_c - sh_core.get_width() // 2), int(my_c + 19)))
            draw_npc_visual(world, mkind, mx_c, my_c, scale=1.0, age=npc_age, activated=False)
            if mkind == "computer_terminal":
                draw_computer_screen_fx(world, mx_c, my_c, scale=1.0, age=npc_age, playing=mplay, track_idx=mtrk)
                if mplay:
                    light_srcs.append((mx_c, my_c - 6.0, 155.0, 0.72))

        for b_entry in st.get("beggars", []):
            bx_g, by_g, bkind = float(b_entry[0]), float(b_entry[1]), str(b_entry[2])
            sh = get_shadow_surf(36, 14, 110)
            world.blit(sh, (int(bx_g - sh.get_width() // 2), int(by_g + 14)))
            draw_npc_visual(world, bkind, bx_g, by_g, scale=1.0, age=npc_age)

        has_sale = any(bool(pl and pl.get("has_steam_sale")) for pl in (p1, p2))
        for p_entry in st.get("pickups", []):
            px, py, pkind = float(p_entry[0]), float(p_entry[1]), str(p_entry[2])
            pprice = int(p_entry[3]) if len(p_entry) > 3 else 0
            pk = Pickup(px, py, pkind, price=pprice)
            pk.age = self.time_acc * 0.075 + (px + py) * 0.02
            pk.draw(world, self.ui.font_tiny, has_sale)

        for ped_entry in st.get("pedestals", []):
            px, py = float(ped_entry[0]), float(ped_entry[1])
            iid = str(ped_entry[2]) if len(ped_entry) > 2 else ""
            pprice = int(ped_entry[4]) if len(ped_entry) > 4 else 0
            dcost = int(ped_entry[5]) if len(ped_entry) > 5 else 0
            it_obj = get_item_by_id(iid) if iid else None
            if it_obj is not None:
                ped = ItemPedestal(px, py, it_obj, price=pprice, devil_cost=dcost)
                ped.bob = self.time_acc * 0.055 + px * 0.03
                ped.draw(world, self.ui.font_tiny, has_sale)
            else:
                draw_monochrome_shadow(world, int(px), int(py) + 13, 44, 15, 128)
                pygame.draw.circle(world, (240, 240, 240), (int(px), int(py) - 13), 8)

        for b_entry in st.get("bombs", []):
            bx_p, by_p = float(b_entry[0]), float(b_entry[1])
            btimer = float(b_entry[2]) if len(b_entry) > 2 else 60.0
            bm = ActiveBomb(bx_p, by_p)
            bm.timer = btimer
            bm.draw(world)

        for e_entry in st.get("enemies", []):
            if isinstance(e_entry, dict):
                ex = float(e_entry.get("x", 0.0))
                ey = float(e_entry.get("y", 0.0))
                er = float(e_entry.get("r", 14.0))
                ehp = int(e_entry.get("hp", 1))
                emax = int(max(1, e_entry.get("max_hp", 1)))
                ekind = str(e_entry.get("type", "gaper")) or "gaper"
                hflash = float(e_entry.get("hit_flash", 0.0)) > 0.0
                edir = float(e_entry.get("dir", 0.0))
                edisg = bool(e_entry.get("disguised", False))
                eair = float(e_entry.get("air_z", 0.0))
                eslam = float(e_entry.get("slam_ring", 0.0))
                etrail = e_entry.get("trail") or None
                eage = float(self._lan_anim.get(f"enemy_{e_entry.get('id')}", self.time_acc * 0.14))
            else:
                ex, ey, er, ehp, emax = float(e_entry[0]), float(e_entry[1]), float(e_entry[2]), int(e_entry[3]), int(e_entry[4])
                ekind = str(e_entry[5]) if (len(e_entry) > 5 and e_entry[5]) else "gaper"
                hflash = float(e_entry[6]) > 0.0 if len(e_entry) > 6 else False
                edir = 0.0
                edisg = False
                eair = 0.0
                eslam = 0.0
                etrail = None
                eage = self.time_acc * 0.14
            draw_enemy_visual(
                world,
                ekind,
                ex,
                ey,
                er,
                age=eage,
                flash=hflash,
                facing_angle=edir,
                disguised=edisg,
                trail=etrail,
                slam_ring=eslam,
                air_z=eair,
                light_sources=light_srcs,
            )
            r_px = max(10, int(round(er)))
            if emax > 0 and ehp < emax:
                bw = r_px * 2
                by_hp = int(ey - eair - r_px - 10)
                pygame.draw.rect(world, (24, 24, 24), (int(ex) - r_px, by_hp, bw, 4))
                pygame.draw.rect(world, (238, 238, 238), (int(ex) - r_px, by_hp, int(bw * clamp(ehp / float(emax), 0.0, 1.0)), 4))

        for b_entry in st.get("bosses", []):
            if isinstance(b_entry, dict):
                bx = float(b_entry.get("x", 0.0))
                by = float(b_entry.get("y", 0.0))
                br = float(b_entry.get("r", 30.0))
                bkey = str(b_entry.get("key", "monstro"))
                bstyle = str(b_entry.get("style", "")) or None
                blum = int(b_entry.get("lum", 182))
                bphase = int(b_entry.get("phase", 1))
                bexpr = str(b_entry.get("expr", "idle"))
                bflash = float(b_entry.get("hit_flash", 0.0)) > 0.0
                bair_z = float(b_entry.get("air_z", 0.0))
                bairborne = bool(b_entry.get("airborne", False))
                btx = float(b_entry.get("tx", bx))
                bty = float(b_entry.get("ty", by))
                btr = float(b_entry.get("tr", 0.0))
                btlines = b_entry.get("tlines") or None
                bsegs = b_entry.get("segs") or None
                bsx = float(b_entry.get("sx", 1.0))
                bsy = float(b_entry.get("sy", 1.0))
                blx = float(b_entry.get("lx", 0.0))
                bly = float(b_entry.get("ly", 1.0))
                bwp = float(b_entry.get("wp", 0.0))
                bage = float(self._lan_anim.get(f"boss_{b_entry.get('id')}", self.time_acc * 0.12))
            else:
                bx, by, br = float(b_entry[0]), float(b_entry[1]), float(b_entry[2])
                bkey = str(b_entry[6]) if len(b_entry) > 6 else "monstro"
                bstyle = None
                blum = None
                bphase = 1
                bexpr = str(b_entry[7]) if len(b_entry) > 7 else "idle"
                bflash = float(b_entry[8]) > 0.0 if len(b_entry) > 8 else False
                bair_z = 0.0
                bairborne = False
                btx, bty, btr = bx, by, 0.0
                btlines = bsegs = None
                bsx = bsy = 1.0
                blx, bly, bwp = 0.0, 1.0, 0.0
                bage = self.time_acc * 0.12
            r_px = max(16, int(round(br)))
            draw_dynamic_shadow(
                world,
                bx,
                by + r_px * 0.85,
                int(r_px * 2.6 * bsx),
                max(10, int(r_px * 0.92)),
                light_sources=light_srcs,
                air_z=bair_z,
                alpha=82 if bairborne else 136,
            )
            draw_boss_visual(
                world,
                bkey,
                bx,
                by,
                r_px,
                age=bage,
                flash=bflash,
                phase=bphase,
                air_z=bair_z,
                target_x=btx,
                target_y=bty,
                airborne=bairborne,
                telegraph_r=btr,
                segments=bsegs,
                style=bstyle,
                lum=blum,
                expression=bexpr,
                scale_x=bsx,
                scale_y=bsy,
                look_x=blx,
                look_y=bly,
                windup_progress=bwp,
                telegraph_lines=btlines,
            )

        for tag, pdata in (("P1", p1), ("P2", p2)):
            if not pdata:
                continue
            dead = (pdata.get("hp", 0) + pdata.get("soul_hp", 0) + pdata.get("black_hp", 0)) <= 0
            if dead:
                continue
            air_z = float(pdata.get("air_z", 0.0))
            px = float(pdata["x"])
            py = float(pdata["y"])
            fx = float(pdata.get("fx", 0.0))
            fy = float(pdata.get("fy", 1.0))
            vx = float(pdata.get("vx", 0.0))
            vy = float(pdata.get("vy", 0.0))
            is_moving = (vx * vx + vy * vy) > 0.04
            inv_a = pdata.get("invis_timer", 0.0) > 0.0
            melee_slash = float(pdata.get("melee_slash", 0.0))
            melee_ang = float(pdata.get("melee_ang", 0.0))
            hurt_fl = float(pdata.get("hurt_flash", 0.0))
            invuln_t = float(pdata.get("invuln", 0.0))
            shield_on = bool(pdata.get("holy_mantle")) and not bool(pdata.get("mantle_broken"))
            anim_st = self._lan_anim.get(f"player_{tag}")
            draw_network_hero_character(
                world,
                pdata.get("hero_id", "isaac"),
                px,
                py,
                air_z=air_z,
                facing=(fx, fy),
                is_moving=is_moving,
                player_tag=tag,
                invis=inv_a,
                hurt_flash=hurt_fl,
                melee_anim=melee_slash,
                melee_ang=melee_ang,
                time_acc=self.time_acc,
                light_sources=light_srcs,
                walk_phase=anim_st["walk"] if anim_st else None,
                idle_phase=anim_st["idle"] if anim_st else None,
                cloak_nodes=anim_st["cloak"] if anim_st else None,
                shield_active=shield_on,
                invuln=invuln_t,
            )

        for t_entry in st.get("tears", []):
            if isinstance(t_entry, dict):
                flg = str(t_entry.get("flags", ""))
                lum = int(t_entry.get("lum", 242))
                t_obj = Tear(
                    t_entry.get("x", 0.0),
                    t_entry.get("y", 0.0),
                    t_entry.get("vx", 0.0),
                    t_entry.get("vy", 0.0),
                    max_range=t_entry.get("max_r", 420.0),
                    radius=t_entry.get("r", 6.0),
                    color=(lum, lum, lum),
                    homing=("h" in flg),
                    holy=("o" in flg),
                    bone=("b" in flg),
                    brimstone=("r" in flg),
                    explosive=("e" in flg),
                    lobbed=("l" in flg),
                    shockwave=("s" in flg),
                    blast_radius=t_entry.get("br", 62.0),
                    vortex=("v" in flg),
                    chain_arc=("c" in flg),
                    ambush=("a" in flg),
                )
                t_obj.air_z = float(t_entry.get("air_z", 0.0))
                t_obj.traveled = float(t_entry.get("trav", 0.0))
                t_obj.age = self.time_acc
                t_obj.spin = self.time_acc * 0.25
                t_obj.draw(world)
            else:
                tx, ty, tr_r = float(t_entry[0]), float(t_entry[1]), float(t_entry[2])
                r_t = max(4, int(round(tr_r)))
                gl = get_glow_surf(int(r_t * 2.3), 245, 54)
                world.blit(gl, (int(round(tx - gl.get_width() * 0.5)), int(round(ty - gl.get_height() * 0.5))))
                disc = get_disc_sprite(r_t, 242, outline_lum=18, hi_lum=255)
                world.blit(disc, (int(round(tx - disc.get_width() * 0.5)), int(round(ty - disc.get_height() * 0.5))))

        for pr_entry in st.get("eproj", []):
            if isinstance(pr_entry, dict):
                pr_obj = EnemyProjectile(
                    pr_entry.get("x", 0.0),
                    pr_entry.get("y", 0.0),
                    pr_entry.get("vx", 0.0),
                    pr_entry.get("vy", 0.0),
                    radius=pr_entry.get("r", 6.0),
                    lobbed=bool(pr_entry.get("lob", False)),
                    target_x=pr_entry.get("tx", pr_entry.get("x", 0.0)),
                    target_y=pr_entry.get("ty", pr_entry.get("y", 0.0)),
                    blast_radius=pr_entry.get("br", 52.0),
                    total_frames=pr_entry.get("tf", 46.0),
                )
                pr_obj.air_z = float(pr_entry.get("air_z", 0.0))
                pr_obj.elapsed = float(pr_entry.get("el", 0.0))
                pr_obj.age = self.time_acc
                pr_obj.draw(world)
            else:
                px_e, py_e, pr_r = float(pr_entry[0]), float(pr_entry[1]), float(pr_entry[2])
                EnemyProjectile(px_e, py_e, 0.0, 0.0, radius=pr_r).draw(world)

        p2_alive = bool(p2 and (p2.get("hp", 0) + p2.get("soul_hp", 0) + p2.get("black_hp", 0)) > 0)
        focus = p2 if p2_alive else p1
        other_p = p1 if (focus is p2) else None
        if other_p and (other_p.get("hp", 0) + other_p.get("soul_hp", 0) + other_p.get("black_hp", 0)) > 0:
            o_fuel = float(other_p.get("lantern_fuel", 1.0)) * float(other_p.get("lantern_bonus", 1.0)) if gmode == "fading_light" else float(other_p.get("lantern_bonus", 1.0))
            o_rad = clamp(250.0 * o_fuel, 130.0, 420.0)
            o_lum = int(clamp(205 * min(1.15, o_fuel), 115, 232))
            extra_lights.append((float(other_p["x"]), float(other_p["y"]), o_rad, o_lum))
            ofx, ofy = float(other_p.get("fx", 0.0)), float(other_p.get("fy", 1.0))
            if ofx != 0.0 or ofy != 0.0:
                extra_lights.append((float(other_p["x"]) + ofx * 72.0, float(other_p["y"]) + ofy * 72.0, o_rad * 0.6, int(o_lum * 0.55)))
        if focus:
            f_fuel = float(focus.get("lantern_fuel", 1.0)) * float(focus.get("lantern_bonus", 1.0)) if gmode == "fading_light" else float(focus.get("lantern_bonus", 1.0))
            f_fx_eff = focus.get("effects", {})
            if isinstance(f_fx_eff, dict) and f_fx_eff.get("lantern_blaze", 0.0) > 0.0:
                f_fuel = max(f_fuel * 1.45, 1.65)
            self.lighting.render(
                world,
                focus["x"],
                focus["y"],
                rm,
                time_acc=self.time_acc,
                lantern_fuel=f_fuel,
                aim_dir=(focus.get("fx", 0.0), focus.get("fy", 1.0)),
                extra_lights=extra_lights,
            )

        sh_x = int(random.uniform(-3.5, 3.5)) if self._lan_client_shake > 0.0 else 0
        sh_y = int(random.uniform(-3.5, 3.5)) if self._lan_client_shake > 0.0 else 0
        if world_ox > 0:
            draw_wide_backdrop(self.screen, vw, world_ox, rm.theme, extra_pad=32)
            self.screen.blit(world, (world_ox + sh_x, sh_y))
        elif sh_x != 0 or sh_y != 0:
            self.screen.scroll(sh_x, sh_y)

        # Build host-parity minimap room dict and full Boss proxies for UI.draw_hud
        mm_rooms = {}
        for mm_e in st.get("minimap", []):
            mc = (int(mm_e[0]), int(mm_e[1]))
            mvis = bool(mm_e[4]) if len(mm_e) > 4 else True
            mm_rooms[mc] = _types.SimpleNamespace(room_type=str(mm_e[2]), visited=mvis)
        if coord not in mm_rooms:
            mm_rooms[coord] = _types.SimpleNamespace(room_type=rtype, visited=True)

        boss_proxies = []
        for b_entry in st.get("bosses", []):
            if isinstance(b_entry, dict):
                boss_proxies.append(
                    _types.SimpleNamespace(
                        alive=True,
                        boss_key=str(b_entry.get("key", "monstro")),
                        hp=int(b_entry.get("hp", 1)),
                        max_hp=int(max(1, b_entry.get("max_hp", 1))),
                    )
                )
            else:
                boss_proxies.append(
                    _types.SimpleNamespace(
                        alive=True,
                        boss_key=str(b_entry[6]) if len(b_entry) > 6 else "monstro",
                        hp=int(b_entry[3]),
                        max_hp=int(max(1, b_entry[4])),
                    )
                )
        rm.bosses = boss_proxies

        p2_proxy = _ClientPlayerProxy(p2 or p1)
        p1_proxy = _ClientPlayerProxy(p1) if p1 is not None else None
        timesc = float(st.get("timescale", 1.0) or 1.0)
        lan_ping = int(getattr(self.lan_client, "ping_ms", 0) or 0)
        coop_lbl = f"LAN {lan_ping}ms" if lan_ping > 0 else "LAN P1"
        comp_hint = None
        if focus:
            best_c = None
            best_d = 1e9
            reach = float(focus.get("r", 15.0)) + 58.0
            for m_entry in st.get("machines", []):
                if len(m_entry) >= 5 and str(m_entry[2]) == "computer_terminal":
                    d = math.hypot(float(m_entry[0]) - float(focus["x"]), float(m_entry[1]) - float(focus["y"]))
                    if d <= reach and d < best_d:
                        best_d = d
                        best_c = m_entry
            if best_c is not None:
                if bool(best_c[3]):
                    tid = int(best_c[4]) % max(1, len(COMPUTER_TRACKS))
                    comp_hint = tr("computer_prompt").format(track=tr(f"comp_track_{tid}"))
                else:
                    comp_hint = tr("computer_off_prompt")

        self.ui.draw_hud(
            self.screen,
            p2_proxy,
            mm_rooms,
            coord,
            rm,
            floor,
            self.fps_val,
            show_fps=GAME_SETTINGS.get("show_fps", False),
            game_mode=gmode,
            wave_num=int(st.get("wave", 1)),
            lantern_fuel=p2_proxy.lantern_fuel,
            editor_active=False,
            timescale=timesc,
            touch_active=self.touch.is_active(),
            p2=p1_proxy,
            primary_tag="P2",
            coop_tag="P1",
            coop_mode_label=coop_lbl,
            computer_hint=comp_hint,
        )

        lang = GAME_SETTINGS.get("language", "ru")
        self.quest_manager.draw_hud_widget(self.screen, self.ui, lang)
        if self.quest_manager.log_open:
            self.quest_manager.draw_log_modal(self.screen, self.ui, lang)

        if not self.touch.is_active():
            ctrl_s = fit_text_surf(self.ui.font_tiny, tr("lan_client_controls"), (132, 132, 132), vw - 40, min_scale=0.58)
            self.screen.blit(ctrl_s, (vw // 2 - ctrl_s.get_width() // 2, SCREEN_HEIGHT - 22))

        host_state = str(st.get("state", "PLAYING"))
        if host_state in ("PAUSED", "VICTORY", "GAME_OVER", "CHAOS_DRAFT", "CUTSCENE"):
            dim = self.ui._get_dim_overlay()
            self.screen.blit(dim, (0, 0))
            if host_state == "PAUSED":
                ov_txt = tr("pause_title")
            elif host_state == "VICTORY":
                ov_txt = tr("victory_title")
            elif host_state == "GAME_OVER":
                ov_txt = tr("gameover_title")
            elif host_state == "CHAOS_DRAFT":
                ov_txt = tr("lan_draft_wait")
            else:
                ov_txt = tr("lan_cutscene_wait")
            ov_s = fit_text_surf(self.ui.font_big, ov_txt, (248, 248, 248), vw - 120, min_scale=0.60)
            panel_w = max(360, ov_s.get_width() + 56)
            panel_h = 84
            px_o = vw // 2 - panel_w // 2
            py_o = SCREEN_HEIGHT // 2 - panel_h // 2
            self.screen.blit(get_panel_surf(panel_w, panel_h, 14, 236, 150, 10), (px_o, py_o))
            self.screen.blit(ov_s, (vw // 2 - ov_s.get_width() // 2, py_o + 18))
            sub_o = f"{tr('floor_label')} {floor} · {tr_floor(floor)}"
            if host_state in ("VICTORY", "GAME_OVER"):
                sub_o = f"{sub_o} · {tr('hud_life')}: P2 ★{p2_proxy.kills}"
            sub_s = fit_text_surf(self.ui.font_tiny, sub_o, PALETTE["text_muted"], panel_w - 32, min_scale=0.60)
            self.screen.blit(sub_s, (vw // 2 - sub_s.get_width() // 2, py_o + 52))

        # Synced pedestal pickup confirmation modal on LAN Client
        pp_data = st.get("pickup_prompt")
        if isinstance(pp_data, dict) and pp_data.get("item_id"):
            it_m = get_item_by_id(pp_data["item_id"])
            if it_m is not None:
                proxy_prompt = {
                    "pedestal": _types.SimpleNamespace(alive=True, item=it_m),
                    "player": None,
                    "selected": int(pp_data.get("selected", 0)),
                    "can_afford": bool(pp_data.get("can_afford", True)),
                    "cost_text": str(pp_data.get("cost_text", "")),
                }
                self.ui.draw_pickup_confirm_modal(self.screen, proxy_prompt, self.touch.is_active())

        self.touch.draw(self.screen, p2_proxy, self.ui, near_terminal=bool(comp_hint))

    def _set_acc_status(self, msg, sec=3.5):
        self.acc_status = str(msg)
        self.acc_status_timer = sec * 60.0

    def _accounts_layout(self):
        vw = get_view_width()
        px, py = vw // 2 - 520, 42
        pw, ph = 1040, 634
        tabs = [pygame.Rect(px + 28 + i * 490, py + 72, 480, 32) for i in range(2)]
        back_rc = pygame.Rect(px + pw - 190, py + ph - 52, 162, 36)
        return px, py, pw, ph, tabs, back_rc

    def _accounts_filter_rects(self):
        px, py, pw, _, _, _ = self._accounts_layout()
        fy = py + 112
        cat_prev_rc = pygame.Rect(px + 28, fy, 32, 28)
        cat_box_rc = pygame.Rect(px + 64, fy, 250, 28)
        cat_next_rc = pygame.Rect(px + 318, fy, 32, 28)
        unl_rc = pygame.Rect(px + 368, fy, 210, 28)
        return cat_prev_rc, cat_box_rc, cat_next_rc, unl_rc

    def _accounts_scroll_rects(self):
        px, py, pw, _, _, _ = self._accounts_layout()
        items = self._filtered_achievements()
        content_y = py + 148
        per_page = 6
        list_h = per_page * 68 - 8
        list_rect = pygame.Rect(px + 28, content_y, pw - 108, list_h)
        sb_x = px + pw - 28 - 44
        sb_up_rc = pygame.Rect(sb_x, content_y, 44, 44)
        sb_dn_rc = pygame.Rect(sb_x, content_y + list_h - 44, 44, 44)
        sb_track_rc = pygame.Rect(sb_x + 6, sb_up_rc.bottom + 8, 32, max(40, sb_dn_rc.top - sb_up_rc.bottom - 16))
        max_scroll = max(0, len(items) - per_page)
        if max_scroll > 0:
            thumb_h = max(36, int(round(sb_track_rc.h * (per_page / float(max(1, len(items)))))))
            thumb_h = min(sb_track_rc.h, thumb_h)
            frac = clamp(self.acc_scroll / float(max_scroll), 0.0, 1.0)
            thumb_y = sb_track_rc.y + int(round((sb_track_rc.h - thumb_h) * frac))
            sb_thumb_rc = pygame.Rect(sb_track_rc.x - 2, thumb_y, sb_track_rc.w + 4, thumb_h)
        else:
            sb_thumb_rc = pygame.Rect(sb_track_rc.x - 2, sb_track_rc.y, sb_track_rc.w + 4, sb_track_rc.h)
        return list_rect, sb_up_rc, sb_dn_rc, sb_track_rc, sb_thumb_rc

    def _accounts_set_scroll_from_y(self, y_pos):
        _, _, _, sb_track_rc, sb_thumb_rc = self._accounts_scroll_rects()
        items = self._filtered_achievements()
        max_scroll = max(0, len(items) - 6)
        if max_scroll <= 0:
            self.acc_scroll = 0
            return
        span = max(1, sb_track_rc.h - sb_thumb_rc.h)
        frac = clamp((float(y_pos) - (sb_track_rc.y + sb_thumb_rc.h * 0.5)) / float(span), 0.0, 1.0)
        self.acc_scroll = int(round(frac * max_scroll))

    def _cycle_acc_category(self, step=1):
        cats = list(ACHIEVEMENT_CATEGORIES)
        cur = self.acc_cat_filter if self.acc_cat_filter in cats else "all"
        nxt = cats[(cats.index(cur) + int(step)) % len(cats)]
        self.acc_cat_filter = nxt
        self.acc_scroll = 0

    def _handle_accounts_click(self, mx_pos, my_pos):
        px, py, pw, ph, tabs, back_rc = self._accounts_layout()
        content_y = py + 148
        if back_rc.collidepoint(mx_pos, my_pos):
            self.state = self.prev_state
            return True
        for i, rc in enumerate(tabs):
            if rc.collidepoint(mx_pos, my_pos):
                self.acc_tab = i
                return True
        if self.acc_tab == 0:
            cat_prev_rc, cat_box_rc, cat_next_rc, unl_rc = self._accounts_filter_rects()
            if cat_prev_rc.collidepoint(mx_pos, my_pos):
                self._cycle_acc_category(-1)
                return True
            if cat_next_rc.collidepoint(mx_pos, my_pos) or cat_box_rc.collidepoint(mx_pos, my_pos):
                self._cycle_acc_category(1)
                return True
            if unl_rc.collidepoint(mx_pos, my_pos):
                self.acc_only_unlocked = not bool(getattr(self, "acc_only_unlocked", False))
                self.acc_scroll = 0
                return True
            _, sb_up_rc, sb_dn_rc, sb_track_rc, _ = self._accounts_scroll_rects()
            max_scroll = max(0, len(self._filtered_achievements()) - 6)
            if sb_up_rc.collidepoint(mx_pos, my_pos):
                self.acc_scroll = max(0, self.acc_scroll - 5)
                return True
            if sb_dn_rc.collidepoint(mx_pos, my_pos):
                self.acc_scroll = min(max_scroll, self.acc_scroll + 5)
                return True
            if sb_track_rc.collidepoint(mx_pos, my_pos):
                self._accounts_set_scroll_from_y(my_pos)
                return True
        elif self.acc_tab == 1:
            backups = self.account_manager.list_backups()
            btn_y = py + ph - 104
            if pygame.Rect(px + 28, content_y, 340, 40).collidepoint(mx_pos, my_pos):
                out_p = self.account_manager.export_full_backup()
                self.achievement_manager.unlock("backup_guardian")
                self._set_acc_status(f"Exported: {os.path.basename(out_p)}")
            else:
                for row_i in range(min(5, len(backups))):
                    if pygame.Rect(px + 28, content_y + 56 + row_i * 64, pw - 56, 56).collidepoint(mx_pos, my_pos):
                        self.acc_backup_idx = row_i
                        break
                if backups and 0 <= self.acc_backup_idx < len(backups):
                    bpath = backups[self.acc_backup_idx]["path"]
                    if pygame.Rect(px + 28, btn_y, 210, 38).collidepoint(mx_pos, my_pos):
                        res = self.account_manager.restore_full_backup(bpath, merge_accounts=False)
                        if res.get("ok"):
                            self.achievement_manager.unlock("backup_guardian")
                            mod_manager.reload_all()
                            self._set_acc_status("Backup restored")
                    elif pygame.Rect(px + 248, btn_y, 210, 38).collidepoint(mx_pos, my_pos):
                        res = self.account_manager.restore_full_backup(bpath, merge_accounts=True)
                        if res.get("ok"):
                            self.achievement_manager.unlock("backup_guardian")
                            self._set_acc_status("Backup merged into roster")
        return False

    def _draw_accounts(self):
        vw = get_view_width()
        lang = GAME_SETTINGS.get("language", "ru")
        self.ui.sync_font_scale(is_phone_layout(self.touch.is_active()))
        self.screen.fill((5, 5, 5))
        px, py, pw, ph, tabs, back_rc = self._accounts_layout()
        panel = get_panel_surf(pw, ph, 14, 244, 114, 12)
        self.screen.blit(panel, (px, py))

        title = fit_text_surf(self.ui.font_big, tr("profiles_title"), PALETTE["text_main"], pw - 56, max_h=28, min_scale=0.58)
        self.screen.blit(title, (px + 28, py + 12))

        active_acc = self.account_manager.get_active()
        un_cnt, tot_cnt = self.achievement_manager.summary()
        emb_names = EMBLEM_NAMES_EN if lang == "en" else EMBLEM_NAMES_RU
        emb_lbl = emb_names[active_acc.get("emblem", 0) % len(emb_names)]
        cur_s = fit_text_surf(
            self.ui.font_tiny,
            f"[{active_acc.get('tag', 'DV-01')}] {active_acc.get('name', '')} · {emb_lbl} · ★ {un_cnt}/{tot_cnt}",
            (204, 204, 204),
            pw - 56,
            max_h=16,
            min_scale=0.56,
        )
        self.screen.blit(cur_s, (px + 28, py + 44))

        tab_keys = ("tab_achievements", "tab_backup")
        for i, (tk, rc) in enumerate(zip(tab_keys, tabs)):
            sel = i == self.acc_tab
            hov = self.hover_acc_btn == f"tab_{i}"
            fill = (238, 238, 238) if sel else ((48, 48, 48) if hov else (24, 24, 24))
            border = (252, 252, 252) if sel else ((140, 140, 140) if hov else (74, 74, 74))
            pygame.draw.rect(self.screen, fill, rc, border_radius=7)
            pygame.draw.rect(self.screen, border, rc, 1, border_radius=7)
            lbl = tr(tk)
            if i == 0:
                lbl = f"{lbl} ({un_cnt}/{tot_cnt})"
            blit_text_fitted(self.screen, rc, self.ui.font_tiny, lbl, (12, 12, 12) if sel else PALETTE["text_main"], pad_x=10, min_scale=0.54)

        content_y = py + 148
        if self.acc_tab == 0:
            cat_prev_rc, cat_box_rc, cat_next_rc, unl_rc = self._accounts_filter_rects()
            for bk_k, b_rc, ch in (("cat_prev", cat_prev_rc, "<"), ("cat_next", cat_next_rc, ">")):
                hov = self.hover_acc_btn == bk_k
                pygame.draw.rect(self.screen, (238, 238, 238) if hov else (28, 28, 28), b_rc, border_radius=6)
                pygame.draw.rect(self.screen, (252, 252, 252) if hov else (98, 98, 98), b_rc, 1, border_radius=6)
                blit_text_fitted(self.screen, b_rc, self.ui.font_small, ch, (12, 12, 12) if hov else PALETTE["text_main"], pad_x=4)

            pygame.draw.rect(self.screen, (22, 22, 22), cat_box_rc, border_radius=6)
            pygame.draw.rect(self.screen, (112, 112, 112), cat_box_rc, 1, border_radius=6)
            cat_name = tr(f"ach_cat_{self.acc_cat_filter}") if self.acc_cat_filter in ACHIEVEMENT_CATEGORIES else self.acc_cat_filter.upper()
            blit_text_fitted(self.screen, cat_box_rc, self.ui.font_tiny, f"{tr('ach_cat_lbl')}: {cat_name}", PALETTE["text_main"], pad_x=8, min_scale=0.52)

            u_on = bool(getattr(self, "acc_only_unlocked", False))
            u_hov = self.hover_acc_btn == "unl_only"
            u_fill = (236, 236, 236) if u_on else ((46, 46, 46) if u_hov else (24, 24, 24))
            u_border = (252, 252, 252) if (u_on or u_hov) else (90, 90, 90)
            pygame.draw.rect(self.screen, u_fill, unl_rc, border_radius=6)
            pygame.draw.rect(self.screen, u_border, unl_rc, 1, border_radius=6)
            u_lbl = f"{tr('ach_unlocked_only')}: {tr('on') if u_on else tr('off')}"
            blit_text_fitted(self.screen, unl_rc, self.ui.font_tiny, u_lbl, (12, 12, 12) if u_on else PALETTE["text_main"], pad_x=8, min_scale=0.52)

            items = self._filtered_achievements()
            per_page = 6
            max_scroll = max(0, len(items) - per_page)
            self.acc_scroll = int(clamp(self.acc_scroll, 0, max_scroll))
            list_rect, sb_up_rc, sb_dn_rc, sb_track_rc, sb_thumb_rc = self._accounts_scroll_rects()
            if not items:
                empty_msg = "Нет открытых достижений в этой категории" if lang == "ru" else "No unlocked achievements in this category"
                em_s = fit_text_surf(self.ui.font_med, empty_msg, PALETTE["text_muted"], list_rect.w - 32, max_h=24, min_scale=0.58)
                self.screen.blit(em_s, (list_rect.centerx - em_s.get_width() // 2, list_rect.centery - em_s.get_height() // 2))
            else:
                visible = items[self.acc_scroll : self.acc_scroll + per_page]
                for row_i, ach in enumerate(visible):
                    rc = pygame.Rect(list_rect.x, content_y + row_i * 68, list_rect.w, 60)
                    unlocked = self.achievement_manager.is_unlocked(ach["id"])
                    cur_p, tgt_p = self.achievement_manager.get_progress(ach)
                    lum = TIER_LUM.get(ach["tier"], 200)
                    pygame.draw.rect(self.screen, (26, 26, 26) if unlocked else (17, 17, 17), rc, border_radius=8)
                    pygame.draw.rect(self.screen, (lum, lum, lum) if unlocked else (62, 62, 62), rc, 2 if unlocked else 1, border_radius=8)
                    name_s = ach["en"] if lang == "en" else ach["ru"]
                    desc_s = ach["desc_en"] if lang == "en" else ach["desc_ru"]
                    badge = f"[{ach['tier'].upper()}] {'✓' if unlocked else f'{cur_p}/{tgt_p}'}"
                    left_max_w = max(180, rc.w - 236)
                    self.screen.blit(
                        fit_text_surf(self.ui.font_med, name_s, (248, 248, 248) if unlocked else (190, 190, 190), left_max_w, max_h=22, min_scale=0.56),
                        (rc.x + 16, rc.y + 8),
                    )
                    self.screen.blit(
                        fit_text_surf(self.ui.font_tiny, desc_s, (200, 200, 200) if unlocked else PALETTE["text_dim"], left_max_w, max_h=16, min_scale=0.54),
                        (rc.x + 16, rc.y + 34),
                    )
                    bs = fit_text_surf(self.ui.font_small, badge, (lum, lum, lum) if unlocked else (140, 140, 140), 186, max_h=17, min_scale=0.56)
                    self.screen.blit(bs, (rc.right - 16 - bs.get_width(), rc.y + 8))
                    bar_w = 180
                    bx, by = rc.right - 16 - bar_w, rc.y + 38
                    pygame.draw.rect(self.screen, (34, 34, 34), (bx, by, bar_w, 6), border_radius=3)
                    fill_w = int(bar_w * clamp(cur_p / float(max(1, tgt_p)), 0.0, 1.0))
                    if fill_w > 0:
                        pygame.draw.rect(self.screen, (lum, lum, lum) if unlocked else (164, 164, 164), (bx, by, fill_w, 6), border_radius=3)

            # Interactive touch & mouse scrollbar + ▲/▼ buttons
            for bk_k, b_rc, b_ch in (("sb_up", sb_up_rc, "▲"), ("sb_dn", sb_dn_rc, "▼")):
                hov = self.hover_acc_btn == bk_k
                pygame.draw.rect(self.screen, (238, 238, 238) if hov else (28, 28, 28), b_rc, border_radius=8)
                pygame.draw.rect(self.screen, (252, 252, 252) if hov else (104, 104, 104), b_rc, 1, border_radius=8)
                blit_text_fitted(self.screen, b_rc, self.ui.font_small, b_ch, (12, 12, 12) if hov else PALETTE["text_main"], pad_x=4)

            pygame.draw.rect(self.screen, (20, 20, 20), sb_track_rc, border_radius=8)
            pygame.draw.rect(self.screen, (68, 68, 68), sb_track_rc, 1, border_radius=8)
            thumb_hov = self.hover_acc_btn == "sb_thumb" or bool(self._acc_mouse_drag == "thumb") or (
                isinstance(self._acc_touch_drag, dict) and self._acc_touch_drag.get("mode") == "thumb"
            )
            pygame.draw.rect(self.screen, (234, 234, 234) if thumb_hov else (142, 142, 142), sb_thumb_rc, border_radius=8)

            if max_scroll > 0:
                sc_txt = f"{self.acc_scroll + 1}-{min(len(items), self.acc_scroll + per_page)} / {len(items)} · {tr('ach_scroll_hint')}"
                sc_s = fit_text_surf(self.ui.font_tiny, sc_txt, PALETTE["text_dim"], pw - 260, max_h=16, min_scale=0.56)
                self.screen.blit(sc_s, (px + 28, py + ph - 44))

        else:
            exp_rc = pygame.Rect(px + 28, content_y, 340, 40)
            hov_e = self.hover_acc_btn == "export"
            pygame.draw.rect(self.screen, (238, 238, 238) if hov_e else (32, 32, 32), exp_rc, border_radius=7)
            pygame.draw.rect(self.screen, (252, 252, 252) if hov_e else (130, 130, 130), exp_rc, 1, border_radius=7)
            blit_text_fitted(self.screen, exp_rc, self.ui.font_tiny, tr("btn_export_backup"), (12, 12, 12) if hov_e else PALETTE["text_main"], pad_x=10, min_scale=0.54)

            backups = self.account_manager.list_backups()
            self.acc_backup_idx = int(clamp(self.acc_backup_idx, 0, max(0, len(backups) - 1)))
            if not backups:
                nb_s = fit_text_surf(self.ui.font_med, tr("acc_no_backups"), PALETTE["text_muted"], pw - 56, max_h=24, min_scale=0.58)
                self.screen.blit(nb_s, (px + 28, content_y + 70))
            else:
                for row_i, bk in enumerate(backups[:5]):
                    rc = pygame.Rect(px + 28, content_y + 56 + row_i * 64, pw - 56, 56)
                    sel = row_i == self.acc_backup_idx
                    pygame.draw.rect(self.screen, (28, 28, 28) if sel else (18, 18, 18), rc, border_radius=8)
                    pygame.draw.rect(self.screen, (238, 238, 238) if sel else (68, 68, 68), rc, 2 if sel else 1, border_radius=8)
                    info = bk.get("info", {})
                    meta = (
                        f"OK · Accounts: {info.get('accounts_count', 0)} · Saves: {info.get('saves_count', 0)} · Mods: {info.get('mods_count', 0)} · SHA:{info.get('sha256_short', '')}"
                        if bk.get("valid")
                        else f"INVALID ({info.get('error', 'err')})"
                    )
                    self.screen.blit(fit_text_surf(self.ui.font_small, bk["name"], PALETTE["text_main"], rc.w - 28, max_h=18, min_scale=0.56), (rc.x + 14, rc.y + 8))
                    self.screen.blit(fit_text_surf(self.ui.font_tiny, meta, PALETTE["text_muted"], rc.w - 28, max_h=16, min_scale=0.56), (rc.x + 14, rc.y + 31))
                btn_y = py + ph - 104
                for act_k, lbl_k, bx_off in (("restore", "btn_restore_backup", 28), ("merge", "btn_merge_backup", 248)):
                    brc = pygame.Rect(px + bx_off, btn_y, 210, 38)
                    hov = self.hover_acc_btn == act_k
                    pygame.draw.rect(self.screen, (238, 238, 238) if hov else (28, 28, 28), brc, border_radius=7)
                    pygame.draw.rect(self.screen, (252, 252, 252) if hov else (104, 104, 104), brc, 1, border_radius=7)
                    blit_text_fitted(self.screen, brc, self.ui.font_tiny, tr(lbl_k), (12, 12, 12) if hov else PALETTE["text_main"], pad_x=10, min_scale=0.54)

        if self.acc_status_timer > 0 and self.acc_status:
            st_s = fit_text_surf(self.ui.font_small, self.acc_status, (244, 244, 244), pw - 260, max_h=18, min_scale=0.56)
            self.screen.blit(st_s, (px + 28, py + ph - 44))

        hov_bk = self.hover_acc_btn == "back"
        pygame.draw.rect(self.screen, (238, 238, 238) if hov_bk else (28, 28, 28), back_rc, border_radius=7)
        pygame.draw.rect(self.screen, (252, 252, 252) if hov_bk else (112, 112, 112), back_rc, 1, border_radius=7)
        blit_text_fitted(self.screen, back_rc, self.ui.font_small, tr("mods_back"), (12, 12, 12) if hov_bk else PALETTE["text_main"], pad_x=10, min_scale=0.54)

    def _handle_saves_action(self, slot_num, action):
        lang = GAME_SETTINGS.get("language", "ru")
        try:
            if action == "save":
                ok, reason = save_run_to_slot(slot_num, self)
                if ok:
                    play_sound("pickup")
                    self._set_saves_feedback(f"Прогресс записан в слот {slot_num}" if lang == "ru" else f"Saved run to Slot {slot_num}")
                elif reason == "occupied":
                    play_sound("hurt")
                    self._set_saves_feedback(tr("saves_need_delete"))
                elif reason == "no_active_run":
                    play_sound("hurt")
                    self._set_saves_feedback(tr("saves_need_run"))
                else:
                    play_sound("hurt")
                    err_msg = f"Ошибка записи ({reason})" if lang == "ru" else f"Save failed ({reason})"
                    self._set_saves_feedback(err_msg)
            elif action == "load":
                self._render_loading(0.35, "loading_save")
                ok, _ = load_run_from_slot(slot_num, self)
                if ok:
                    self._render_loading(1.0, "loading_save")
                    self.coop_enabled = bool(self.player2 is not None)
                    self.run_recorded = False
                    self.floor_took_damage = False
                    play_sound("door")
                else:
                    play_sound("hurt")
                    self._set_saves_feedback("Ошибка чтения слота — удалите файл" if lang == "ru" else "Failed to load slot")
            elif action == "delete":
                if delete_save_slot(slot_num):
                    play_sound("hit")
                    self._set_saves_feedback(
                        f"Слот {slot_num} удалён — теперь можно записать" if lang == "ru" else f"Slot {slot_num} deleted — ready to save"
                    )
                else:
                    play_sound("hurt")
                    self._set_saves_feedback("Не удалось удалить слот" if lang == "ru" else "Failed to delete slot")
        except Exception as exc:
            play_sound("hurt")
            self._set_saves_feedback(f"Ошибка сохранения: {exc}" if lang == "ru" else f"Save error: {exc}")

    def _activate_menu_item(self, idx):
        self.menu_idx = idx
        if idx == 0:
            self.start_new_run()
        elif idx == 1:
            self.prev_state = "MENU"
            self.saves_feedback = ""
            self.saves_feedback_timer = 0.0
            self.state = "SAVES"
            self.fade_alpha = 180.0
        elif idx == 2:
            self.prev_state = "MENU"
            self.acc_input_mode = ""
            self.acc_input_buf = ""
            self.acc_status = ""
            self.state = "ACCOUNTS"
            self.fade_alpha = 180.0
        elif idx == 3:
            self.prev_state = "MENU"
            self.mod_browser.on_enter()
            self.state = "MODS"
            self.fade_alpha = 180.0
        elif idx == 4:
            self.prev_state = "MENU"
            self.tutorial_return_state = "MENU"
            self.state = "TUTORIAL"
            self.fade_alpha = 180.0
        elif idx == 5:
            self.prev_state = "MENU"
            self.account_manager.record_stat("codex_opened", 1)
            self.achievement_manager.evaluate()
            self.state = "CODEX"
            self.fade_alpha = 180.0
        elif idx == 6:
            self.prev_state = "MENU"
            self.account_manager.record_stat("codex_opened", 1)
            self.achievement_manager.evaluate()
            self.state = "CHRONICLE"
            self.fade_alpha = 180.0
        elif idx == 7:
            self.prev_state = "MENU"
            self.state = "SETTINGS"
            self.fade_alpha = 180.0
        else:
            return False
        return True

    def _activate_pause_item(self, idx):
        self.pause_idx = idx
        if idx == 0:
            self.state = "PLAYING"
        elif idx == 1:
            self.prev_state = "PAUSED"
            self.saves_feedback = ""
            self.saves_feedback_timer = 0.0
            self.state = "SAVES"
        elif idx == 2:
            self.start_new_run()
        elif idx == 3:
            self.prev_state = "PAUSED"
            self.account_manager.record_stat("codex_opened", 1)
            self.achievement_manager.evaluate()
            self.state = "CODEX"
        elif idx == 4:
            self._open_lan_lobby(prev_state="PAUSED")
        elif idx == 5:
            self.prev_state = "PAUSED"
            self.state = "SETTINGS"
        else:
            self.state = "MENU"

    def handle_events(self):
        self._ensure_display_synced()
        events = pygame.event.get()
        finger_types = (pygame.FINGERDOWN, pygame.FINGERMOTION, pygame.FINGERUP)
        resize_types = tuple(
            t
            for t in (
                pygame.VIDEORESIZE,
                getattr(pygame, "WINDOWSIZECHANGED", None),
                getattr(pygame, "WINDOWRESIZED", None),
            )
            if t is not None
        )
        touch_detected = False
        for ev_scan in events:
            if ev_scan.type in finger_types:
                self._finger_events_seen = True
                touch_detected = True
                break
            if ev_scan.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION, pygame.MOUSEBUTTONUP) and self._is_raw_touch_mouse_event(ev_scan):
                touch_detected = True
        if touch_detected and hasattr(self, "touch") and self.touch is not None and not self.touch.touch_seen:
            self.touch.touch_seen = True
            self.touch._sync_layout()
            if hasattr(self, "ui") and self.ui is not None:
                self.ui.sync_font_scale(is_phone_layout(self.touch.is_active()))

        for event in events:
            if event.type == pygame.QUIT:
                return False

            if event.type in resize_types:
                cur_s = pygame.display.get_surface()
                if cur_s is not None:
                    self.display_surf = cur_s
                self._update_present_rect()
                continue

            if event.type in (
                getattr(pygame, "APP_WILLENTERBACKGROUND", -1),
                getattr(pygame, "APP_DIDENTERBACKGROUND", -1),
            ):
                self.app_in_background = True
                if self.state == "PLAYING":
                    self.touch.reset()
                    self.pause_idx = 0
                    self.state = "PAUSED"
                continue

            if event.type == getattr(pygame, "APP_DIDENTERFOREGROUND", -1):
                self.app_in_background = False
                self.touch.reset()
                if is_android():
                    self._apply_display_mode(True, persist=False)
                else:
                    self._update_present_rect()
                continue

            if event.type == pygame.KEYDOWN:
                ac_back = getattr(pygame, "K_AC_BACK", None)
                if ac_back is not None and event.key == ac_back:
                    if self.state == "PLAYING":
                        self.touch.reset()
                        self.pause_idx = 0
                        self.state = "PAUSED"
                    elif self.state == "PAUSED":
                        self.state = "PLAYING"
                    elif self.state in ("CODEX", "CHRONICLE", "TUTORIAL", "SETTINGS", "SAVES", "ACCOUNTS", "LAN_LOBBY"):
                        if self.state == "TUTORIAL":
                            self.account_manager.record_stat("tutorial_done", True, mode="set")
                            self.achievement_manager.evaluate()
                        elif self.state == "LAN_LOBBY":
                            try:
                                pygame.key.stop_text_input()
                            except Exception:
                                pass
                        self.state = self.prev_state
                    elif self.state == "LAN_CLIENT":
                        self.touch.reset()
                        self.state = "LAN_LOBBY"
                    elif self.state == "CHAOS_DRAFT":
                        self._pick_chaos_draft(self.draft_idx)
                    elif self.state == "MODS":
                        self.mod_browser.on_exit()
                        self.state = self.prev_state
                    elif self.state in ("GAME_OVER", "VICTORY", "CUTSCENE"):
                        self.state = "MENU"
                    elif self.state == "MENU":
                        return False
                    continue
                mods = getattr(event, "mod", 0)
                if event.key == pygame.K_F11 or (event.key == pygame.K_RETURN and (mods & pygame.KMOD_ALT)):
                    self._apply_display_mode(not GAME_SETTINGS.get("fullscreen", False))
                    continue

            if GAME_SETTINGS.get("console_enabled", False) and self.state != "MODS" and self.console.is_toggle_key(event):
                self.console.toggle()
                continue

            if self.console.open:
                if event.type == pygame.FINGERDOWN:
                    ev_c = self._make_synthetic_click(self._finger_to_logical(event.x, event.y))
                elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION, pygame.MOUSEBUTTONUP) and self._is_touch_mouse_event(event):
                    continue
                elif hasattr(event, "pos"):
                    ev_c = _MappedEvent(event, self._to_logical_pos(event.pos))
                else:
                    ev_c = event
                self.console.handle_event(ev_c, self)
                continue

            if self.state == "MENU":
                if event.type == pygame.FINGERDOWN:
                    event = self._make_synthetic_click(self._finger_to_logical(event.x, event.y))
                elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION) and self._is_touch_mouse_event(event):
                    continue

                if event.type == pygame.KEYDOWN:
                    if self.seed_input_active:
                        if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER):
                            self.seed_input_active = False
                            try:
                                pygame.key.stop_text_input()
                            except Exception:
                                pass
                        elif event.key == pygame.K_BACKSPACE:
                            self.custom_seed = self.custom_seed[:-1]
                        else:
                            ch = getattr(event, "unicode", "")
                            if ch and (ch.isalnum() or ch in "-_") and len(self.custom_seed) < 22:
                                self.custom_seed += ch.upper()
                        continue
                    if event.key == pygame.K_h:
                        self.hide_menu_ui = not self.hide_menu_ui
                    elif event.key == pygame.K_F3 and not is_android():
                        self._toggle_coop_setting()
                    elif event.key == pygame.K_F4 and not is_android():
                        if not self.coop_enabled:
                            self._toggle_coop_setting(True)
                        else:
                            self._cycle_p2_hero(1)
                    elif pygame.K_1 <= event.key <= pygame.K_6:
                        self.preview.load_scene(event.key - pygame.K_1)
                    elif event.key == pygame.K_q:
                        self.selected_mode_idx = (self.selected_mode_idx - 1) % len(GAME_MODES)
                        self.game_mode = GAME_MODES[self.selected_mode_idx]
                    elif event.key == pygame.K_e:
                        self.selected_mode_idx = (self.selected_mode_idx + 1) % len(GAME_MODES)
                        self.game_mode = GAME_MODES[self.selected_mode_idx]
                    elif event.key in (pygame.K_a, pygame.K_LEFT):
                        self.selected_hero_idx = (self.selected_hero_idx - 1) % len(HERO_ROSTER)
                    elif event.key in (pygame.K_d, pygame.K_RIGHT):
                        self.selected_hero_idx = (self.selected_hero_idx + 1) % len(HERO_ROSTER)
                    elif event.key in (pygame.K_w, pygame.K_UP):
                        self.menu_idx = (self.menu_idx - 1) % 9
                    elif event.key in (pygame.K_s, pygame.K_DOWN):
                        self.menu_idx = (self.menu_idx + 1) % 9
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if not self._activate_menu_item(self.menu_idx):
                            return False
                elif event.type == pygame.MOUSEMOTION:
                    mx_pos, my_pos = self._to_logical_pos(event.pos)
                    tab_rects, hide_rect = self._menu_preview_rects()
                    self.hover_preview_tab = next((i for i, rc in enumerate(tab_rects) if rc.collidepoint(mx_pos, my_pos)), -1)
                    self.hover_hide_ui = hide_rect.collidepoint(mx_pos, my_pos)
                    self.hover_console_btn = bool(GAME_SETTINGS.get("console_enabled", False) and self._menu_console_rect().collidepoint(mx_pos, my_pos))
                    self.hover_hero_arrow = 0
                    self.hover_p2_hero_arrow = 0
                    self.hover_menu_btn = -1
                    self.hover_mode_pill = -1
                    self.hover_coop_btn = False
                    self.hover_lan_btn = False
                    self.hover_p2_btn = False
                    self.hover_seed_btn = False
                    self.hover_seed_roll_btn = False
                    self.hover_daily_btn = False
                    if not self.hide_menu_ui:
                        self.hover_daily_btn = self._menu_daily_rect().collidepoint(mx_pos, my_pos)
                        _, left_arr, right_arr = self._menu_hero_rects()
                        if left_arr.collidepoint(mx_pos, my_pos):
                            self.hover_hero_arrow = -1
                        elif right_arr.collidepoint(mx_pos, my_pos):
                            self.hover_hero_arrow = 1
                        p2_box, p2_left, p2_right = self._menu_p2_hero_rects()
                        if p2_box is not None:
                            self.hover_p2_btn = p2_box.collidepoint(mx_pos, my_pos)
                            if p2_left.collidepoint(mx_pos, my_pos):
                                self.hover_p2_hero_arrow = -1
                            elif p2_right.collidepoint(mx_pos, my_pos):
                                self.hover_p2_hero_arrow = 1
                        for i, rc in enumerate(self._menu_button_rects()):
                            if rc.collidepoint(mx_pos, my_pos):
                                self.hover_menu_btn = i
                                self.menu_idx = i
                                break
                        coop_rc, _ = self._menu_coop_rects()
                        self.hover_coop_btn = bool(coop_rc is not None and coop_rc.collidepoint(mx_pos, my_pos))
                        for idx, rc in enumerate(self._menu_mode_rects()):
                            if rc.collidepoint(mx_pos, my_pos):
                                self.hover_mode_pill = idx
                                break
                        self.hover_seed_btn = self._menu_seed_rect().collidepoint(mx_pos, my_pos)
                        self.hover_seed_roll_btn = self._menu_seed_roll_rect().collidepoint(mx_pos, my_pos)
                elif event.type == pygame.MOUSEWHEEL:
                    delta = -1 if event.y > 0 else 1
                    if self.hover_p2_btn and self.coop_enabled:
                        self._cycle_p2_hero(delta)
                    else:
                        self.selected_hero_idx = (self.selected_hero_idx + delta) % len(HERO_ROSTER)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button in (4, 5):
                        delta = -1 if event.button == 4 else 1
                        if self.hover_p2_btn and self.coop_enabled:
                            self._cycle_p2_hero(delta)
                        else:
                            self.selected_hero_idx = (self.selected_hero_idx + delta) % len(HERO_ROSTER)
                    elif event.button == 3 and not self.hide_menu_ui:
                        mx_pos, my_pos = self._to_logical_pos(event.pos)
                        p2_box, _, _ = self._menu_p2_hero_rects()
                        if p2_box is not None and p2_box.collidepoint(mx_pos, my_pos):
                            self._cycle_p2_hero(-1)
                    elif event.button == 1:
                        mx_pos, my_pos = event.pos if getattr(event, "synthetic", False) else self._to_logical_pos(event.pos)
                        if not self._menu_seed_rect().collidepoint(mx_pos, my_pos):
                            self.seed_input_active = False
                            try:
                                pygame.key.stop_text_input()
                            except Exception:
                                pass
                        if GAME_SETTINGS.get("console_enabled", False) and self._menu_console_rect().collidepoint(mx_pos, my_pos):
                            self.console.toggle(True)
                            continue
                        tab_rects, hide_rect = self._menu_preview_rects()
                        for idx, rc in enumerate(tab_rects):
                            if rc.collidepoint(mx_pos, my_pos):
                                self.preview.load_scene(idx)
                                break
                        if hide_rect.collidepoint(mx_pos, my_pos):
                            self.hide_menu_ui = not self.hide_menu_ui
                        elif not self.hide_menu_ui:
                            if self._menu_daily_rect().collidepoint(mx_pos, my_pos):
                                res_d = self.account_manager.claim_daily_reward()
                                if res_d.get("ok"):
                                    play_sound("item")
                                    self.achievement_manager.evaluate()
                                    lang_d = GAME_SETTINGS.get("language", "ru")
                                    rw_lbl = res_d["reward"].get("label_en" if lang_d == "en" else "label_ru", "")
                                    self.menu_notice = f"{tr('daily_title')}: {rw_lbl}"
                                    self.menu_notice_timer = 180.0
                                else:
                                    self.menu_notice = tr("daily_claimed")
                                    self.menu_notice_timer = 120.0
                                continue
                            hero_box, left_arr, right_arr = self._menu_hero_rects()
                            if left_arr.collidepoint(mx_pos, my_pos):
                                self.selected_hero_idx = (self.selected_hero_idx - 1) % len(HERO_ROSTER)
                            elif right_arr.collidepoint(mx_pos, my_pos):
                                self.selected_hero_idx = (self.selected_hero_idx + 1) % len(HERO_ROSTER)
                            elif hero_box.collidepoint(mx_pos, my_pos):
                                step = -1 if mx_pos < hero_box.centerx else 1
                                self.selected_hero_idx = (self.selected_hero_idx + step) % len(HERO_ROSTER)
                            p2_box, p2_left, p2_right = self._menu_p2_hero_rects()
                            if p2_box is not None:
                                if p2_left.collidepoint(mx_pos, my_pos):
                                    self._cycle_p2_hero(-1)
                                elif p2_right.collidepoint(mx_pos, my_pos):
                                    self._cycle_p2_hero(1)
                                elif p2_box.collidepoint(mx_pos, my_pos):
                                    step = -1 if mx_pos < p2_box.centerx else 1
                                    self._cycle_p2_hero(step)
                            coop_rc, _ = self._menu_coop_rects()
                            if coop_rc is not None and coop_rc.collidepoint(mx_pos, my_pos):
                                self._toggle_coop_setting()
                            elif self._menu_seed_rect().collidepoint(mx_pos, my_pos):
                                self.seed_input_active = True
                                try:
                                    pygame.key.start_text_input()
                                except Exception:
                                    pass
                            elif self._menu_seed_roll_rect().collidepoint(mx_pos, my_pos):
                                if self.custom_seed.strip():
                                    self.custom_seed = ""
                                elif self.shared_seeds:
                                    self.selected_seed_idx = (self.selected_seed_idx + 1) % len(self.shared_seeds)
                            for idx, rc in enumerate(self._menu_mode_rects()):
                                if rc.collidepoint(mx_pos, my_pos):
                                    self.selected_mode_idx = idx
                                    self.game_mode = GAME_MODES[idx]
                                    break
                            for i, rc in enumerate(self._menu_button_rects()):
                                if rc.collidepoint(mx_pos, my_pos):
                                    if not self._activate_menu_item(i):
                                        return False
                                    break

            elif self.state == "LAN_LOBBY":
                if event.type == pygame.FINGERDOWN:
                    event = self._make_synthetic_click(self._finger_to_logical(event.x, event.y))
                elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION) and self._is_touch_mouse_event(event):
                    continue
                lrc = self._lan_lobby_rects()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        try:
                            pygame.key.stop_text_input()
                        except Exception:
                            pass
                        self.state = self.prev_state
                    elif event.key == pygame.K_BACKSPACE:
                        self.lan_ip_input = self.lan_ip_input[:-1]
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        self._lan_connect_disconnect()
                    elif event.key == pygame.K_LEFT:
                        self._lan_cycle_p2_hero(-1)
                    elif event.key == pygame.K_RIGHT:
                        self._lan_cycle_p2_hero(1)
                    else:
                        ch = getattr(event, "unicode", "")
                        if ch in "0123456789.:" and len(self.lan_ip_input) < 22:
                            self.lan_ip_input += ch
                elif event.type == pygame.MOUSEMOTION:
                    mx_pos, my_pos = self._to_logical_pos(event.pos)
                    self.lan_hover_btn = ""
                    for bk in ("host_toggle", "host_start", "scan", "p2_prev", "p2_next", "join_toggle", "back"):
                        if lrc[bk].collidepoint(mx_pos, my_pos):
                            self.lan_hover_btn = bk
                            break
                    if not self.lan_hover_btn:
                        for i, r_rc in enumerate(lrc["rows"]):
                            if i < len(self.lan_discovered) and r_rc.collidepoint(mx_pos, my_pos):
                                self.lan_hover_btn = f"row_{i}"
                                break
                    if not self.lan_hover_btn:
                        for ch, krc in lrc["keypad"]:
                            if krc.collidepoint(mx_pos, my_pos):
                                self.lan_hover_btn = f"kp_{ch}"
                                break
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx_pos, my_pos = event.pos if getattr(event, "synthetic", False) else self._to_logical_pos(event.pos)
                    if lrc["back"].collidepoint(mx_pos, my_pos):
                        try:
                            pygame.key.stop_text_input()
                        except Exception:
                            pass
                        self.state = self.prev_state
                    elif lrc["host_toggle"].collidepoint(mx_pos, my_pos):
                        self._lan_host_start_stop()
                    elif lrc["host_start"].collidepoint(mx_pos, my_pos):
                        if not self.lan_host.running:
                            self._lan_host_start_stop()
                        self._toggle_coop_setting(True)
                        try:
                            pygame.key.stop_text_input()
                        except Exception:
                            pass
                        if self.prev_state == "PAUSED" and self.player is not None and self.current_room is not None and not self._all_players_dead():
                            self.state = "PLAYING"
                            self.lan_host.update_lobby_meta(in_run=True)
                            self._push_lan_snapshot()
                        else:
                            self.start_new_run()
                    elif lrc["scan"].collidepoint(mx_pos, my_pos):
                        self._lan_scan_servers(async_mode=True)
                    elif lrc["p2_prev"].collidepoint(mx_pos, my_pos):
                        self._lan_cycle_p2_hero(-1)
                    elif lrc["p2_next"].collidepoint(mx_pos, my_pos):
                        self._lan_cycle_p2_hero(1)
                    elif lrc["join_toggle"].collidepoint(mx_pos, my_pos):
                        self._lan_connect_disconnect()
                    else:
                        picked_row = False
                        for i, r_rc in enumerate(lrc["rows"]):
                            if i < len(self.lan_discovered) and r_rc.collidepoint(mx_pos, my_pos):
                                srv = self.lan_discovered[i]
                                self.lan_ip_input = f"{srv['ip']}:{srv['port']}"
                                picked_row = True
                                break
                        if not picked_row:
                            for ch, krc in lrc["keypad"]:
                                if krc.collidepoint(mx_pos, my_pos):
                                    if ch == "⌫":
                                        self.lan_ip_input = self.lan_ip_input[:-1]
                                    elif len(self.lan_ip_input) < 22:
                                        self.lan_ip_input += ch
                                    break

            elif self.state == "LAN_CLIENT":
                st_cur = self.lan_client.get_latest_state()
                has_prompt = bool(st_cur and isinstance(st_cur.get("pickup_prompt"), dict) and st_cur["pickup_prompt"].get("item_id"))
                if event.type == pygame.FINGERDOWN:
                    fpos = self._finger_to_logical(event.x, event.y)
                    if has_prompt:
                        _, c_rc, x_rc = self.ui.get_pickup_confirm_rects(self.touch.is_active())
                        if c_rc.inflate(10, 10).collidepoint(fpos[0], fpos[1]):
                            self._lan_client_actions["confirm"] = True
                            continue
                        if x_rc.inflate(10, 10).collidepoint(fpos[0], fpos[1]):
                            self._lan_client_actions["cancel"] = True
                            continue
                    act_rc = self.ui.get_active_relic_rect()
                    if act_rc is not None and act_rc.collidepoint(fpos[0], fpos[1]):
                        self._lan_client_actions["relic"] = True
                        continue
                    inv_use_rc = self.ui.get_inventory_use_rect()
                    if inv_use_rc is not None and inv_use_rc.inflate(14, 12).collidepoint(fpos[0], fpos[1]):
                        self._lan_client_actions["relic"] = True
                        continue
                    comp_rc = self.ui.get_computer_hint_rect()
                    if comp_rc is not None and comp_rc.inflate(14, 10).collidepoint(fpos[0], fpos[1]):
                        self._lan_client_actions["interact"] = True
                        continue
                    slot_rects, page_rect = self.ui.get_inventory_slot_rects(self.touch.is_active())
                    if page_rect.inflate(16, 14).collidepoint(fpos[0], fpos[1]):
                        self.lan_client.send_action("", inv_page=1)
                        continue
                    tapped_slot = False
                    for i, rc in enumerate(slot_rects):
                        if rc.inflate(6, 8).collidepoint(fpos[0], fpos[1]):
                            self.lan_client.send_action("", inv_slot=i + 1)
                            tapped_slot = True
                            break
                    if tapped_slot:
                        continue
                    self.touch.handle_finger_down(event.finger_id, fpos)
                    continue
                elif event.type == pygame.FINGERMOTION:
                    fpos = self._finger_to_logical(event.x, event.y)
                    self.touch.handle_finger_motion(event.finger_id, fpos)
                    continue
                elif event.type == pygame.FINGERUP:
                    self.touch.handle_finger_up(event.finger_id)
                    continue
                elif event.type == pygame.KEYDOWN:
                    if has_prompt:
                        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_e, pygame.K_SPACE):
                            self._lan_client_actions["confirm"] = True
                            continue
                        elif event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                            self._lan_client_actions["cancel"] = True
                            continue
                    if event.key == pygame.K_ESCAPE:
                        if self.quest_manager.log_open:
                            self.quest_manager.log_open = False
                        else:
                            stop_computer_audio()
                            self.touch.reset()
                            self.state = "LAN_LOBBY"
                    elif event.key in (get_keybind("quests"), pygame.K_q):
                        self.quest_manager.log_open = not self.quest_manager.log_open
                    elif event.key == get_keybind("jump"):
                        self._lan_client_actions["jump"] = True
                    elif event.key == get_keybind("stealth"):
                        self._lan_client_actions["stealth"] = True
                    elif event.key == get_keybind("melee"):
                        self._lan_client_actions["melee"] = True
                    elif event.key == get_keybind("bomb"):
                        self._lan_client_actions["bomb"] = True
                    elif event.key == get_keybind("relic"):
                        self._lan_client_actions["relic"] = True
                    elif event.key == pygame.K_r:
                        self._lan_client_actions["cycle_relic"] = True
                    elif event.key in (pygame.K_g, pygame.K_RETURN, pygame.K_KP_ENTER):
                        self._lan_client_actions["interact"] = True
                    elif pygame.K_1 <= event.key <= pygame.K_9:
                        self.lan_client.send_action("", inv_slot=(event.key - pygame.K_1 + 1))
                    elif pygame.K_KP1 <= event.key <= pygame.K_KP9:
                        self.lan_client.send_action("", inv_slot=(event.key - pygame.K_KP1 + 1))
                    elif event.key in (pygame.K_0, pygame.K_KP0, pygame.K_RIGHTBRACKET):
                        self.lan_client.send_action("", inv_page=1)
                    elif event.key == pygame.K_LEFTBRACKET:
                        self.lan_client.send_action("", inv_page=-1)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if not self._is_touch_mouse_event(event):
                        mpos = self._to_logical_pos(event.pos)
                        if has_prompt:
                            _, c_rc, x_rc = self.ui.get_pickup_confirm_rects(self.touch.is_active())
                            if c_rc.collidepoint(mpos[0], mpos[1]):
                                self._lan_client_actions["confirm"] = True
                                continue
                            if x_rc.collidepoint(mpos[0], mpos[1]):
                                self._lan_client_actions["cancel"] = True
                                continue
                        act_rc = self.ui.get_active_relic_rect()
                        if act_rc is not None and act_rc.collidepoint(mpos[0], mpos[1]):
                            self._lan_client_actions["relic"] = True
                            continue
                        inv_use_rc = self.ui.get_inventory_use_rect()
                        if inv_use_rc is not None and inv_use_rc.collidepoint(mpos[0], mpos[1]):
                            self._lan_client_actions["relic"] = True
                            continue
                        comp_rc = self.ui.get_computer_hint_rect()
                        if comp_rc is not None and comp_rc.inflate(10, 8).collidepoint(mpos[0], mpos[1]):
                            self._lan_client_actions["interact"] = True
                            continue
                        slot_rects, page_rect = self.ui.get_inventory_slot_rects(self.touch.is_active())
                        if page_rect.collidepoint(mpos[0], mpos[1]):
                            self.lan_client.send_action("", inv_page=1)
                            continue
                        clicked_slot = False
                        for i, rc in enumerate(slot_rects):
                            if rc.collidepoint(mpos[0], mpos[1]):
                                self.lan_client.send_action("", inv_slot=i + 1)
                                clicked_slot = True
                                break
                        if clicked_slot:
                            continue
                        if self.touch.is_active():
                            self.touch.handle_finger_down(-1, mpos)
                elif event.type == pygame.MOUSEMOTION:
                    if not self._is_touch_mouse_event(event) and self.touch.is_active() and (event.buttons[0] or -1 in self.touch.btn_fingers or self.touch.move_finger == -1 or self.touch.aim_finger == -1):
                        self.touch.handle_finger_motion(-1, self._to_logical_pos(event.pos))
                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    if not self._is_touch_mouse_event(event) and self.touch.is_active():
                        self.touch.handle_finger_up(-1)

            elif self.state == "CHAOS_DRAFT":
                if event.type == pygame.FINGERDOWN:
                    event = self._make_synthetic_click(self._finger_to_logical(event.x, event.y))
                elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION) and self._is_touch_mouse_event(event):
                    continue
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_1, pygame.K_KP1):
                        self._pick_chaos_draft(0)
                    elif event.key in (pygame.K_2, pygame.K_KP2):
                        self._pick_chaos_draft(1)
                    elif event.key in (pygame.K_3, pygame.K_KP3):
                        self._pick_chaos_draft(2)
                    elif event.key in (pygame.K_a, pygame.K_LEFT):
                        self.draft_idx = (self.draft_idx - 1) % max(1, len(self.draft_options))
                    elif event.key in (pygame.K_d, pygame.K_RIGHT):
                        self.draft_idx = (self.draft_idx + 1) % max(1, len(self.draft_options))
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self._pick_chaos_draft(self.draft_idx)
                elif event.type == pygame.MOUSEMOTION:
                    mx_pos, my_pos = self._to_logical_pos(event.pos)
                    self.hover_draft_idx = next(
                        (i for i, rc in enumerate(self.ui.get_chaos_draft_rects(len(self.draft_options))) if rc.collidepoint(mx_pos, my_pos)),
                        -1,
                    )
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx_pos, my_pos = event.pos if getattr(event, "synthetic", False) else self._to_logical_pos(event.pos)
                    for i, rc in enumerate(self.ui.get_chaos_draft_rects(len(self.draft_options))):
                        if rc.collidepoint(mx_pos, my_pos):
                            self._pick_chaos_draft(i)
                            break

            elif self.state == "PLAYING":
                if GAME_SETTINGS.get("console_enabled", False) and self.console.is_toggle_key(event):
                    self.console.toggle(True)
                    continue
                if GAME_SETTINGS.get("console_enabled", False) and event.type == pygame.KEYDOWN and event.key == pygame.K_F2 and (self.console.editor_unlocked or self.editor.unlocked):
                    self.editor.active = not self.editor.active
                    continue
                if self.editor.active and self.editor.handle_event(event, self):
                    continue
                if self.pending_pedestal_prompt is not None and self._handle_pickup_prompt_event(event):
                    continue
                if event.type == pygame.FINGERDOWN:
                    fpos = self._finger_to_logical(event.x, event.y)
                    act_rc = self.ui.get_active_relic_rect()
                    if act_rc is not None and act_rc.collidepoint(fpos[0], fpos[1]) and not self.player.is_dead():
                        self._trigger_active_item(self.player)
                        continue
                    inv_use_rc = self.ui.get_inventory_use_rect()
                    if inv_use_rc is not None and inv_use_rc.inflate(14, 12).collidepoint(fpos[0], fpos[1]) and not self.player.is_dead():
                        self._trigger_active_item(self.player)
                        continue
                    comp_rc = self.ui.get_computer_hint_rect()
                    if comp_rc is not None and comp_rc.inflate(14, 10).collidepoint(fpos[0], fpos[1]) and not self.player.is_dead():
                        self._interact_computer_terminal(self.current_room, self.player)
                        continue
                    slot_rects, page_rect = self.ui.get_inventory_slot_rects(self.touch.is_active())
                    if page_rect.inflate(16, 14).collidepoint(fpos[0], fpos[1]):
                        self.player.cycle_inventory_page(1)
                        continue
                    tapped_slot = False
                    for i, rc in enumerate(slot_rects):
                        if rc.inflate(6, 8).collidepoint(fpos[0], fpos[1]):
                            self._select_or_use_inventory_slot(i + 1, trigger_if_already_selected=True)
                            tapped_slot = True
                            break
                    if tapped_slot:
                        continue
                    self.touch.handle_finger_down(event.finger_id, fpos)
                    continue
                elif event.type == pygame.FINGERMOTION:
                    fpos = self._finger_to_logical(event.x, event.y)
                    self.touch.handle_finger_motion(event.finger_id, fpos)
                    continue
                elif event.type == pygame.FINGERUP:
                    self.touch.handle_finger_up(event.finger_id)
                    continue
                if event.type == pygame.KEYDOWN:
                    keys = pygame.key.get_pressed()
                    cur_mx = (1 if keys[get_keybind("right")] else 0) - (1 if keys[get_keybind("left")] else 0)
                    cur_my = (1 if keys[get_keybind("down")] else 0) - (1 if keys[get_keybind("up")] else 0)
                    cur_ax = (1 if keys[get_keybind("fire_right")] else 0) - (1 if keys[get_keybind("fire_left")] else 0)
                    cur_ay = (1 if keys[get_keybind("fire_down")] else 0) - (1 if keys[get_keybind("fire_up")] else 0)
                    if event.key in (pygame.K_ESCAPE, pygame.K_p):
                        if self.quest_manager.log_open:
                            self.quest_manager.log_open = False
                        else:
                            self.touch.reset()
                            self.pause_idx = 0
                            self.state = "PAUSED"
                    elif event.key == get_keybind("relic") and not self.player.is_dead():
                        self._trigger_active_item(self.player)
                    elif event.key in (pygame.K_g, pygame.K_RETURN, pygame.K_KP_ENTER) and not self.player.is_dead():
                        self._interact_computer_terminal(self.current_room, self.player)
                    elif event.key in (get_keybind("quests"), pygame.K_q) or (event.key == pygame.K_j and not self.coop_enabled):
                        self.quest_manager.log_open = not self.quest_manager.log_open
                    elif event.key == get_keybind("jump") and not self.editor.active and not self.player.is_dead():
                        if self.player.try_jump(cur_mx, cur_my, self.particles):
                            self.account_manager.record_stat("jumps_used", 1)
                    elif event.key == get_keybind("stealth") and not self.editor.active and not self.player.is_dead():
                        if self.player.try_stealth(self.particles):
                            self.account_manager.record_stat("stealth_uses", 1)
                    elif event.key == get_keybind("melee") and not self.editor.active and not self.player.is_dead():
                        self._trigger_melee(self.player, cur_ax, cur_my if (cur_ax == 0 and cur_ay == 0 and (cur_mx != 0 or cur_my != 0)) else cur_ay)
                    elif event.key == get_keybind("bomb") and self.player.can_place_bomb() and not self.player.is_dead():
                        self.player.bombs -= 1
                        self.player.trigger_bomb_cd()
                        self.bombs.append(ActiveBomb(self.player.x, self.player.y, self.player.has_sad_bombs, owner=self.player))
                        self.account_manager.record_stat("bombs_used", 1)
                    elif self.coop_enabled and self.player2 is not None and not self.player2.is_dead():
                        p2_mx = (1 if keys[pygame.K_l] else 0) - (1 if keys[pygame.K_j] else 0)
                        p2_my = (1 if keys[pygame.K_k] else 0) - (1 if keys[pygame.K_i] else 0)
                        if event.key == pygame.K_m and not self.editor.active:
                            self.player2.try_jump(p2_mx, p2_my, self.particles)
                        elif event.key == pygame.K_n and not self.editor.active:
                            self.player2.try_stealth(self.particles)
                        elif event.key == pygame.K_b and self.player2.can_place_bomb():
                            self.player2.bombs -= 1
                            self.player2.trigger_bomb_cd()
                            self.bombs.append(ActiveBomb(self.player2.x, self.player2.y, self.player2.has_sad_bombs, owner=self.player2))
                        elif event.key == pygame.K_o:
                            self._trigger_active_item(self.player2)
                    if (pygame.K_1 <= event.key <= pygame.K_9) or (pygame.K_KP1 <= event.key <= pygame.K_KP9 and not self.coop_enabled):
                        slot_num = (event.key - pygame.K_1 + 1) if event.key <= pygame.K_9 else (event.key - pygame.K_KP1 + 1)
                        self._select_or_use_inventory_slot(slot_num, trigger_if_already_selected=True)
                    elif event.key in (pygame.K_0, pygame.K_KP0, pygame.K_RIGHTBRACKET):
                        self.player.cycle_inventory_page(1)
                    elif event.key == pygame.K_LEFTBRACKET:
                        self.player.cycle_inventory_page(-1)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self._is_touch_mouse_event(event):
                        continue
                    mx_pos, my_pos = self._to_logical_pos(event.pos)
                    act_rc = self.ui.get_active_relic_rect()
                    if act_rc is not None and act_rc.collidepoint(mx_pos, my_pos) and not self.player.is_dead():
                        self._trigger_active_item(self.player)
                        continue
                    inv_use_rc = self.ui.get_inventory_use_rect()
                    if inv_use_rc is not None and inv_use_rc.collidepoint(mx_pos, my_pos) and not self.player.is_dead():
                        self._trigger_active_item(self.player)
                        continue
                    p2_act_rc = self.ui.get_p2_active_relic_rect() if (self.coop_enabled and self.player2 is not None) else None
                    if p2_act_rc is not None and p2_act_rc.collidepoint(mx_pos, my_pos) and not self.player2.is_dead():
                        self._trigger_active_item(self.player2)
                        continue
                    comp_rc = self.ui.get_computer_hint_rect()
                    if comp_rc is not None and comp_rc.inflate(10, 8).collidepoint(mx_pos, my_pos) and not self.player.is_dead():
                        self._interact_computer_terminal(self.current_room, self.player)
                        continue
                    slot_rects, page_rect = self.ui.get_inventory_slot_rects(self.touch.is_active())
                    if page_rect.collidepoint(mx_pos, my_pos):
                        self.player.cycle_inventory_page(1)
                        continue
                    clicked_slot = False
                    for i, rc in enumerate(slot_rects):
                        if rc.collidepoint(mx_pos, my_pos):
                            self._select_or_use_inventory_slot(i + 1, trigger_if_already_selected=True)
                            clicked_slot = True
                            break
                    if clicked_slot:
                        continue
                    if self.touch.is_active() and not self.touch.has_active_fingers() and self.touch.handle_finger_down(-1, (mx_pos, my_pos)):
                        continue
                elif event.type == pygame.MOUSEMOTION:
                    if self._is_touch_mouse_event(event):
                        continue
                    if self.touch.is_active() and not self.touch.has_active_fingers() and (event.buttons[0] or -1 in self.touch.btn_fingers or self.touch.move_finger == -1 or self.touch.aim_finger == -1):
                        self.touch.handle_finger_motion(-1, self._to_logical_pos(event.pos))
                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    if self._is_touch_mouse_event(event):
                        continue
                    if self.touch.is_active():
                        self.touch.handle_finger_up(-1)

            elif self.state == "CUTSCENE":
                if (event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE)) or (
                    event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                ) or event.type == pygame.FINGERDOWN:
                    self.cutscene.skip()
                    self.state = "PLAYING"

            elif self.state == "PAUSED":
                if event.type == pygame.FINGERDOWN:
                    event = self._make_synthetic_click(self._finger_to_logical(event.x, event.y))
                elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION) and self._is_touch_mouse_event(event):
                    continue
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_p):
                        self.state = "PLAYING"
                    elif event.key == pygame.K_F5:
                        self._open_lan_lobby(prev_state="PAUSED")
                    elif event.key in (pygame.K_w, pygame.K_UP):
                        self.pause_idx = (self.pause_idx - 1) % 7
                    elif event.key in (pygame.K_s, pygame.K_DOWN):
                        self.pause_idx = (self.pause_idx + 1) % 7
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self._activate_pause_item(self.pause_idx)
                elif event.type == pygame.MOUSEMOTION:
                    mx_pos, my_pos = self._to_logical_pos(event.pos)
                    self.hover_pause_btn = -1
                    for i, rc in enumerate(self.ui.get_pause_rects(self.touch.is_active())):
                        if rc.collidepoint(mx_pos, my_pos):
                            self.hover_pause_btn = i
                            self.pause_idx = i
                            break
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx_pos, my_pos = event.pos if getattr(event, "synthetic", False) else self._to_logical_pos(event.pos)
                    for i, rc in enumerate(self.ui.get_pause_rects(self.touch.is_active())):
                        if rc.collidepoint(mx_pos, my_pos):
                            self._activate_pause_item(i)
                            break

            elif self.state == "ACCOUNTS":
                px, py, pw, ph, tabs, back_rc = self._accounts_layout()
                content_y = py + 148
                items = self._filtered_achievements()
                max_scroll = max(0, len(items) - 6)
                if event.type == pygame.FINGERDOWN:
                    fx, fy = self._finger_to_logical(event.x, event.y)
                    if self.acc_tab == 0:
                        cat_prev_rc, cat_box_rc, cat_next_rc, unl_rc = self._accounts_filter_rects()
                        if (
                            cat_prev_rc.collidepoint(fx, fy)
                            or cat_box_rc.collidepoint(fx, fy)
                            or cat_next_rc.collidepoint(fx, fy)
                            or unl_rc.collidepoint(fx, fy)
                        ):
                            self._handle_accounts_click(fx, fy)
                            self._acc_touch_drag = None
                            continue
                        _, sb_up_rc, sb_dn_rc, sb_track_rc, sb_thumb_rc = self._accounts_scroll_rects()
                        if sb_up_rc.collidepoint(fx, fy):
                            self.acc_scroll = max(0, self.acc_scroll - 5)
                            self._acc_touch_drag = None
                            continue
                        if sb_dn_rc.collidepoint(fx, fy):
                            self.acc_scroll = min(max_scroll, self.acc_scroll + 5)
                            self._acc_touch_drag = None
                            continue
                        if sb_thumb_rc.collidepoint(fx, fy) or sb_track_rc.collidepoint(fx, fy):
                            self._accounts_set_scroll_from_y(fy)
                            self._acc_touch_drag = {
                                "id": getattr(event, "finger_id", None),
                                "mode": "thumb",
                                "start_x": fx,
                                "start_y": fy,
                                "last_y": fy,
                                "accum_y": 0.0,
                                "moved": True,
                            }
                            continue
                        self._acc_touch_drag = {
                            "id": getattr(event, "finger_id", None),
                            "mode": "swipe",
                            "start_x": fx,
                            "start_y": fy,
                            "last_y": fy,
                            "accum_y": 0.0,
                            "moved": False,
                        }
                        continue
                    self._handle_accounts_click(fx, fy)
                    continue
                elif event.type == pygame.FINGERMOTION:
                    if isinstance(self._acc_touch_drag, dict):
                        fid = getattr(event, "finger_id", None)
                        if self._acc_touch_drag.get("id") in (None, fid):
                            fx, fy = self._finger_to_logical(event.x, event.y)
                            mode = self._acc_touch_drag.get("mode")
                            if mode == "thumb":
                                self._accounts_set_scroll_from_y(fy)
                            elif mode == "swipe":
                                if abs(fy - self._acc_touch_drag["start_y"]) > 10 or abs(fx - self._acc_touch_drag["start_x"]) > 10:
                                    self._acc_touch_drag["moved"] = True
                                dy = fy - self._acc_touch_drag["last_y"]
                                self._acc_touch_drag["last_y"] = fy
                                self._acc_touch_drag["accum_y"] += dy
                                while self._acc_touch_drag["accum_y"] <= -28.0:
                                    self.acc_scroll = min(max_scroll, self.acc_scroll + 1)
                                    self._acc_touch_drag["accum_y"] += 28.0
                                while self._acc_touch_drag["accum_y"] >= 28.0:
                                    self.acc_scroll = max(0, self.acc_scroll - 1)
                                    self._acc_touch_drag["accum_y"] -= 28.0
                    continue
                elif event.type == pygame.FINGERUP:
                    if isinstance(self._acc_touch_drag, dict):
                        fid = getattr(event, "finger_id", None)
                        if self._acc_touch_drag.get("id") in (None, fid):
                            fx, fy = self._finger_to_logical(event.x, event.y)
                            drag = self._acc_touch_drag
                            self._acc_touch_drag = None
                            if not drag.get("moved", False):
                                self._handle_accounts_click(fx, fy)
                    continue
                elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION, pygame.MOUSEBUTTONUP) and self._is_touch_mouse_event(event):
                    continue

                if event.type == pygame.KEYDOWN:
                    if self.acc_input_mode:
                        if event.key == pygame.K_ESCAPE:
                            self.acc_input_mode = ""
                            self.acc_input_buf = ""
                        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                            txt = self.acc_input_buf.strip()
                            if txt:
                                if self.acc_input_mode == "new":
                                    self.account_manager.create_account(txt)
                                    self._set_acc_status(f"Created profile: {txt}")
                                elif self.acc_input_mode == "rename":
                                    roster = self.account_manager.get_roster()
                                    if 0 <= self.acc_sel_idx < len(roster):
                                        self.account_manager.rename_account(roster[self.acc_sel_idx]["id"], txt)
                                        self._set_acc_status(f"Renamed to: {txt}")
                            self.acc_input_mode = ""
                            self.acc_input_buf = ""
                        elif event.key == pygame.K_BACKSPACE:
                            self.acc_input_buf = self.acc_input_buf[:-1]
                        elif getattr(event, "unicode", "") and len(self.acc_input_buf) < 20 and event.unicode.isprintable():
                            self.acc_input_buf += event.unicode
                        continue
                    if event.key == pygame.K_ESCAPE:
                        self.state = self.prev_state
                    elif event.key == pygame.K_TAB or event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                        step = -1 if event.key == pygame.K_LEFT else 1
                        self.acc_tab = (self.acc_tab + step) % 2
                    elif event.key in (pygame.K_w, pygame.K_UP):
                        if self.acc_tab == 0:
                            self.acc_scroll = max(0, self.acc_scroll - 1)
                        else:
                            self.acc_backup_idx = max(0, self.acc_backup_idx - 1)
                    elif event.key in (pygame.K_s, pygame.K_DOWN):
                        if self.acc_tab == 0:
                            self.acc_scroll = min(max_scroll, self.acc_scroll + 1)
                        else:
                            self.acc_backup_idx = min(max(0, len(self.account_manager.list_backups()) - 1), self.acc_backup_idx + 1)
                    elif event.key == pygame.K_PAGEUP and self.acc_tab == 0:
                        self.acc_scroll = max(0, self.acc_scroll - 6)
                    elif event.key == pygame.K_PAGEDOWN and self.acc_tab == 0:
                        self.acc_scroll = min(max_scroll, self.acc_scroll + 6)
                elif event.type == pygame.MOUSEWHEEL:
                    if self.acc_tab == 0:
                        self.acc_scroll = int(clamp(self.acc_scroll - event.y * 2, 0, max_scroll))
                elif event.type == pygame.MOUSEMOTION:
                    mx_pos, my_pos = self._to_logical_pos(event.pos)
                    left_down = bool(
                        getattr(event, "buttons", (0,))[0]
                        or (pygame.mouse.get_pressed()[0] if hasattr(pygame.mouse, "get_pressed") else False)
                    )
                    if self.acc_tab == 0 and self._acc_mouse_drag:
                        if not left_down:
                            self._acc_mouse_drag = None
                        elif self._acc_mouse_drag == "thumb":
                            self._accounts_set_scroll_from_y(my_pos)
                        elif isinstance(self._acc_mouse_drag, dict):
                            dy = my_pos - self._acc_mouse_drag["last_y"]
                            self._acc_mouse_drag["last_y"] = my_pos
                            self._acc_mouse_drag["accum_y"] += dy
                            while self._acc_mouse_drag["accum_y"] <= -28.0:
                                self.acc_scroll = min(max_scroll, self.acc_scroll + 1)
                                self._acc_mouse_drag["accum_y"] += 28.0
                            while self._acc_mouse_drag["accum_y"] >= 28.0:
                                self.acc_scroll = max(0, self.acc_scroll - 1)
                                self._acc_mouse_drag["accum_y"] -= 28.0
                    self.hover_acc_btn = "back" if back_rc.collidepoint(mx_pos, my_pos) else ""
                    for i, rc in enumerate(tabs):
                        if rc.collidepoint(mx_pos, my_pos):
                            self.hover_acc_btn = f"tab_{i}"
                            break
                    if not self.hover_acc_btn and self.acc_tab == 0:
                        cat_prev_rc, cat_box_rc, cat_next_rc, unl_rc = self._accounts_filter_rects()
                        _, sb_up_rc, sb_dn_rc, _, sb_thumb_rc = self._accounts_scroll_rects()
                        if cat_prev_rc.collidepoint(mx_pos, my_pos):
                            self.hover_acc_btn = "cat_prev"
                        elif cat_next_rc.collidepoint(mx_pos, my_pos) or cat_box_rc.collidepoint(mx_pos, my_pos):
                            self.hover_acc_btn = "cat_next"
                        elif unl_rc.collidepoint(mx_pos, my_pos):
                            self.hover_acc_btn = "unl_only"
                        elif sb_up_rc.collidepoint(mx_pos, my_pos):
                            self.hover_acc_btn = "sb_up"
                        elif sb_dn_rc.collidepoint(mx_pos, my_pos):
                            self.hover_acc_btn = "sb_dn"
                        elif sb_thumb_rc.collidepoint(mx_pos, my_pos):
                            self.hover_acc_btn = "sb_thumb"
                    elif not self.hover_acc_btn and self.acc_tab == 1:
                        btn_y = py + ph - 104
                        if pygame.Rect(px + 28, content_y, 340, 40).collidepoint(mx_pos, my_pos):
                            self.hover_acc_btn = "export"
                        else:
                            for act_k, x0 in (("restore", px + 28), ("merge", px + 248)):
                                if pygame.Rect(x0, btn_y, 210, 38).collidepoint(mx_pos, my_pos):
                                    self.hover_acc_btn = act_k
                                    break
                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    self._acc_mouse_drag = None
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx_pos, my_pos = event.pos if getattr(event, "synthetic", False) else self._to_logical_pos(event.pos)
                    if self.acc_tab == 0:
                        list_rect, _, _, sb_track_rc, sb_thumb_rc = self._accounts_scroll_rects()
                        if sb_thumb_rc.collidepoint(mx_pos, my_pos) or sb_track_rc.collidepoint(mx_pos, my_pos):
                            self._acc_mouse_drag = "thumb"
                        elif list_rect.collidepoint(mx_pos, my_pos):
                            self._acc_mouse_drag = {"last_y": my_pos, "accum_y": 0.0}
                    self._handle_accounts_click(mx_pos, my_pos)

            elif self.state == "SAVES":
                if event.type == pygame.FINGERDOWN:
                    event = self._make_synthetic_click(self._finger_to_logical(event.x, event.y))
                elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION) and self._is_touch_mouse_event(event):
                    continue
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.state = self.prev_state
                    elif event.key in (pygame.K_w, pygame.K_UP):
                        self.saves_idx = (self.saves_idx - 1) % 3
                    elif event.key in (pygame.K_s, pygame.K_DOWN):
                        self.saves_idx = (self.saves_idx + 1) % 3
                    elif pygame.K_1 <= event.key <= pygame.K_3:
                        self.saves_idx = event.key - pygame.K_1
                    elif event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
                        if is_slot_occupied(self.saves_idx + 1):
                            self._handle_saves_action(self.saves_idx + 1, "delete")
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        slot_num = self.saves_idx + 1
                        self._handle_saves_action(slot_num, "load" if is_slot_occupied(slot_num) else "save")
                elif event.type == pygame.MOUSEMOTION:
                    mx_pos, my_pos = self._to_logical_pos(event.pos)
                    self.hover_saves_btn = (-1, "")
                    cards, back_r = self._saves_layout_rects()
                    if back_r.collidepoint(mx_pos, my_pos):
                        self.hover_saves_btn = (-1, "back")
                    else:
                        slots = list_save_slots()
                        for i, (rc, sm) in enumerate(zip(cards, slots)):
                            if rc.collidepoint(mx_pos, my_pos):
                                self.saves_idx = i
                            for act_k, b_rc in self._saves_card_buttons(rc, sm).items():
                                if b_rc.collidepoint(mx_pos, my_pos):
                                    self.hover_saves_btn = (sm["slot"], act_k)
                                    break
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx_pos, my_pos = event.pos if getattr(event, "synthetic", False) else self._to_logical_pos(event.pos)
                    cards, back_r = self._saves_layout_rects()
                    if back_r.collidepoint(mx_pos, my_pos):
                        self.state = self.prev_state
                    else:
                        slots = list_save_slots()
                        for i, (rc, sm) in enumerate(zip(cards, slots)):
                            if rc.collidepoint(mx_pos, my_pos):
                                self.saves_idx = i
                            for act_k, b_rc in self._saves_card_buttons(rc, sm).items():
                                if b_rc.collidepoint(mx_pos, my_pos):
                                    self._handle_saves_action(sm["slot"], act_k)
                                    break

            elif self.state == "MODS":
                if event.type == pygame.FINGERDOWN:
                    ev = self._make_synthetic_click(self._finger_to_logical(event.x, event.y))
                elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION) and self._is_touch_mouse_event(event):
                    continue
                elif hasattr(event, "pos"):
                    ev = _MappedEvent(event, self._to_logical_pos(event.pos))
                else:
                    ev = event
                if self.mod_browser.handle_event(ev) == "back":
                    self.state = self.prev_state

            elif self.state == "CODEX":
                if event.type == pygame.FINGERDOWN:
                    ev = self._make_synthetic_click(self._finger_to_logical(event.x, event.y))
                elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION, pygame.MOUSEBUTTONUP) and self._is_touch_mouse_event(event):
                    continue
                elif hasattr(event, "pos"):
                    ev = _MappedEvent(event, self._to_logical_pos(event.pos))
                else:
                    ev = event
                if self.codex.handle_event(ev) == "back":
                    self.state = self.prev_state

            elif self.state == "CHRONICLE":
                if event.type == pygame.FINGERDOWN:
                    ev = self._make_synthetic_click(self._finger_to_logical(event.x, event.y))
                elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION, pygame.MOUSEBUTTONUP) and self._is_touch_mouse_event(event):
                    continue
                elif hasattr(event, "pos"):
                    ev = _MappedEvent(event, self._to_logical_pos(event.pos))
                else:
                    ev = event
                if self.chronicle.handle_event(ev) == "back":
                    self.state = self.prev_state

            elif self.state == "TUTORIAL":
                if event.type == pygame.FINGERDOWN:
                    event = self._make_synthetic_click(self._finger_to_logical(event.x, event.y))
                elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION) and self._is_touch_mouse_event(event):
                    continue
                lay = self._tutorial_layout()
                if event.type == pygame.KEYDOWN:
                    if self.ctrl_rebind_action is not None:
                        if event.key == pygame.K_ESCAPE:
                            self.ctrl_rebind_action = None
                        else:
                            set_keybind(self.ctrl_rebind_action, event.key)
                            save_user_settings()
                            play_sound("pickup")
                            self.ctrl_rebind_action = None
                        continue
                    if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                        self.account_manager.record_stat("tutorial_done", True, mode="set")
                        self.achievement_manager.evaluate()
                        self.state = self.tutorial_return_state
                    elif event.key in (pygame.K_TAB, pygame.K_LEFT, pygame.K_RIGHT):
                        self.ctrl_tab = (self.ctrl_tab + 1) % 2
                elif event.type == pygame.MOUSEMOTION:
                    mx_pos, my_pos = self._to_logical_pos(event.pos)
                    self.hover_tutorial_back = lay["back"].collidepoint(mx_pos, my_pos)
                    self.hover_ctrl_btn = ""
                    for ti, trc in enumerate(lay["tabs"]):
                        if trc.collidepoint(mx_pos, my_pos):
                            self.hover_ctrl_btn = f"tab_{ti}"
                            break
                    if not self.hover_ctrl_btn and self.ctrl_tab == 1:
                        if lay["reset"].collidepoint(mx_pos, my_pos):
                            self.hover_ctrl_btn = "reset"
                        else:
                            for act, krc in lay["kb_rects"]:
                                if krc.collidepoint(mx_pos, my_pos):
                                    self.hover_ctrl_btn = f"kb_{act}"
                                    break
                    elif not self.hover_ctrl_btn and self.ctrl_tab == 0:
                        if lay["touch_edit"].collidepoint(mx_pos, my_pos):
                            self.hover_ctrl_btn = "touch_edit"
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx_pos, my_pos = event.pos if getattr(event, "synthetic", False) else self._to_logical_pos(event.pos)
                    if lay["back"].collidepoint(mx_pos, my_pos):
                        self.ctrl_rebind_action = None
                        self.account_manager.record_stat("tutorial_done", True, mode="set")
                        self.achievement_manager.evaluate()
                        self.state = self.tutorial_return_state
                        continue
                    tab_hit = False
                    for ti, trc in enumerate(lay["tabs"]):
                        if trc.collidepoint(mx_pos, my_pos):
                            self.ctrl_tab = ti
                            self.ctrl_rebind_action = None
                            tab_hit = True
                            break
                    if tab_hit:
                        continue
                    if self.ctrl_tab == 1:
                        if lay["reset"].collidepoint(mx_pos, my_pos):
                            reset_keybinds()
                            save_user_settings()
                            play_sound("pickup")
                            self.ctrl_rebind_action = None
                        else:
                            for act, krc in lay["kb_rects"]:
                                if krc.collidepoint(mx_pos, my_pos):
                                    self.ctrl_rebind_action = act
                                    break
                    else:
                        if lay["touch_edit"].collidepoint(mx_pos, my_pos):
                            self.touch_edit_return_state = "TUTORIAL"
                            self.touch.invalidate_layout()
                            self.state = "TOUCH_EDIT"

            elif self.state == "TOUCH_EDIT":
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        save_user_settings()
                        self.state = self.touch_edit_return_state
                        continue
                elif event.type == pygame.FINGERDOWN:
                    res_te = self.touch.handle_customizer_pointer("down", self._finger_to_logical(event.x, event.y))
                    if res_te == "back":
                        save_user_settings()
                        self.state = self.touch_edit_return_state
                    elif res_te in ("preset", "reset"):
                        save_user_settings()
                    continue
                elif event.type == pygame.FINGERMOTION:
                    self.touch.handle_customizer_pointer("move", self._finger_to_logical(event.x, event.y))
                    continue
                elif event.type == pygame.FINGERUP:
                    res_te = self.touch.handle_customizer_pointer("up", self._finger_to_logical(event.x, event.y))
                    if res_te == "drop":
                        save_user_settings()
                    continue
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not self._is_touch_mouse_event(event):
                    res_te = self.touch.handle_customizer_pointer("down", self._to_logical_pos(event.pos))
                    if res_te == "back":
                        save_user_settings()
                        self.state = self.touch_edit_return_state
                    elif res_te in ("preset", "reset"):
                        save_user_settings()
                elif event.type == pygame.MOUSEMOTION and not self._is_touch_mouse_event(event):
                    if getattr(event, "buttons", (0,))[0] or (pygame.mouse.get_pressed()[0] if hasattr(pygame.mouse, "get_pressed") else False):
                        self.touch.handle_customizer_pointer("move", self._to_logical_pos(event.pos))
                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and not self._is_touch_mouse_event(event):
                    res_te = self.touch.handle_customizer_pointer("up", self._to_logical_pos(event.pos))
                    if res_te == "drop":
                        save_user_settings()

            elif self.state == "SETTINGS":
                if event.type == pygame.FINGERDOWN:
                    event = self._make_synthetic_click(self._finger_to_logical(event.x, event.y))
                elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION) and self._is_touch_mouse_event(event):
                    continue
                row_cnt = self._settings_row_count()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.state = self.prev_state
                    elif event.key in (pygame.K_w, pygame.K_UP):
                        self.settings_idx = (self.settings_idx - 1) % row_cnt
                    elif event.key in (pygame.K_s, pygame.K_DOWN):
                        self.settings_idx = (self.settings_idx + 1) % row_cnt
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_LEFT, pygame.K_RIGHT):
                        step = -1 if event.key == pygame.K_LEFT else 1
                        self._activate_settings_row(self.settings_idx, step=step)
                elif event.type == pygame.MOUSEMOTION:
                    mx_pos, my_pos = self._to_logical_pos(event.pos)
                    self.hover_settings_row = -1
                    for i, rc in enumerate(self._settings_rects()):
                        if rc.collidepoint(mx_pos, my_pos):
                            self.hover_settings_row = i
                            self.settings_idx = i
                            break
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx_pos, my_pos = event.pos if getattr(event, "synthetic", False) else self._to_logical_pos(event.pos)
                    for i, rc in enumerate(self._settings_rects()):
                        if rc.collidepoint(mx_pos, my_pos):
                            self.settings_idx = i
                            self._activate_settings_row(i)
                            break

            elif self.state in ("GAME_OVER", "VICTORY"):
                if event.type == pygame.FINGERDOWN:
                    event = self._make_synthetic_click(self._finger_to_logical(event.x, event.y))
                elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION) and self._is_touch_mouse_event(event):
                    continue
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_r:
                        self.start_new_run()
                    elif event.key == pygame.K_ESCAPE:
                        self.state = "MENU"
                elif event.type == pygame.MOUSEMOTION:
                    mx_pos, my_pos = self._to_logical_pos(event.pos)
                    is_coop_end = bool(self.coop_enabled and self.player2 is not None)
                    btn_r, btn_m = self.ui.get_end_rects(self.touch.is_active(), is_coop=is_coop_end)
                    self.hover_end_btn = 0 if btn_r.collidepoint(mx_pos, my_pos) else (1 if btn_m.collidepoint(mx_pos, my_pos) else -1)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx_pos, my_pos = event.pos if getattr(event, "synthetic", False) else self._to_logical_pos(event.pos)
                    is_coop_end = bool(self.coop_enabled and self.player2 is not None)
                    btn_r, btn_m = self.ui.get_end_rects(self.touch.is_active(), is_coop=is_coop_end)
                    if btn_r.collidepoint(mx_pos, my_pos):
                        self.start_new_run()
                    elif btn_m.collidepoint(mx_pos, my_pos):
                        self.state = "MENU"
        return True

    def _sync_music(self):
        if self.app_in_background:
            update_music("none")
            stop_computer_audio()
            return
        if self.state == "LAN_CLIENT":
            st = self.lan_client.get_latest_state() if getattr(self, "lan_client", None) else None
            has_live_boss = bool(st and st.get("bosses"))
            update_music("boss" if has_live_boss else "combat")
        elif self.state in ("PLAYING", "CHAOS_DRAFT", "CUTSCENE"):
            has_live_boss = bool(
                self.current_room is not None
                and any(getattr(b, "alive", False) for b in getattr(self.current_room, "bosses", ()))
            )
            update_music("boss" if has_live_boss else "combat")
        elif self.state in ("MENU", "SETTINGS", "ACCOUNTS", "SAVES", "MODS", "CODEX", "CHRONICLE", "TUTORIAL", "LAN_LOBBY", "PAUSED", "GAME_OVER", "VICTORY"):
            stop_computer_audio()
            update_music("menu")
        else:
            stop_computer_audio()
            update_music("none")

    def step_frame(self, dt=1.0):
        self.time_acc += dt
        if self.fade_alpha > 0.0:
            self.fade_alpha = max(0.0, self.fade_alpha - 14.0 * dt)
        if self.saves_feedback_timer > 0.0:
            self.saves_feedback_timer = max(0.0, self.saves_feedback_timer - dt)
        if self.acc_status_timer > 0.0:
            self.acc_status_timer = max(0.0, self.acc_status_timer - dt)
        if self.menu_notice_timer > 0.0:
            self.menu_notice_timer = max(0.0, self.menu_notice_timer - dt)
        self.achievement_manager.update(dt)
        self._sync_music()

        if self.state == "MENU":
            if self.lan_host.running:
                self.lan_host.update_lobby_meta(
                    host_hero_id=HERO_ROSTER[self.selected_hero_idx]["id"],
                    game_mode=GAME_MODES[self.selected_mode_idx],
                    in_run=False,
                )
            elif self.lan_client.connected:
                st_net = self.lan_client.get_latest_state()
                if st_net and st_net.get("in_run"):
                    self.touch.reset()
                    self.state = "LAN_CLIENT"
            low_pwr = bool(is_android() or is_phone_layout(self.touch.is_active()))
            self.preview.update(dt, low_power=low_pwr)
            self._draw_menu()
        elif self.state == "LAN_LOBBY":
            if self.lan_host.running:
                in_active_run = bool(
                    self.prev_state == "PAUSED"
                    and self.player is not None
                    and self.current_room is not None
                    and not self._all_players_dead()
                )
                self.lan_host.update_lobby_meta(
                    host_hero_id=HERO_ROSTER[self.selected_hero_idx]["id"],
                    game_mode=GAME_MODES[self.selected_mode_idx],
                    in_run=in_active_run,
                )
                if in_active_run and self.lan_host.client_connected:
                    self.lan_net_tick = (self.lan_net_tick + 1) % 10000
                    if self.lan_net_tick % 6 == 0:
                        self._push_lan_snapshot()
            elif self.lan_client.connected:
                st_net = self.lan_client.get_latest_state()
                if (st_net and st_net.get("in_run")) or getattr(self.lan_client, "host_in_run", False):
                    try:
                        pygame.key.stop_text_input()
                    except Exception:
                        pass
                    self.touch.reset()
                    self.state = "LAN_CLIENT"
            if self.state == "LAN_LOBBY":
                self._draw_lan_lobby()
        elif self.state == "LAN_CLIENT":
            self._update_lan_client(dt)
            if self.state == "LAN_CLIENT":
                self._draw_lan_client()
        elif self.state == "PLAYING":
            self._update_playing(dt)
            if self.state == "PLAYING":
                self._draw_playing()
        elif self.state == "CHAOS_DRAFT":
            self._draw_playing()
            self.ui.draw_chaos_draft(self.screen, self.draft_options, self.draft_idx, self.hover_draft_idx)
            if self.lan_host.running and self.lan_host.client_connected:
                self.lan_net_tick = (self.lan_net_tick + 1) % 10000
                if self.lan_net_tick % 6 == 0:
                    self._push_lan_snapshot()
        elif self.state == "CUTSCENE":
            self.cutscene.update(dt)
            self.cutscene.draw(self.screen, self.ui.font_huge, self.ui.font_big, self.ui.font_med)
            if self.cutscene.finished:
                self.state = "PLAYING"
            if self.lan_host.running and self.lan_host.client_connected:
                self.lan_net_tick = (self.lan_net_tick + 1) % 10000
                if self.lan_net_tick % 4 == 0:
                    self._push_lan_snapshot()
        elif self.state == "PAUSED":
            self._draw_playing()
            self.ui.draw_pause(self.screen, self.pause_idx, hover_idx=self.hover_pause_btn, touch_active=self.touch.is_active())
            if self.lan_host.running and self.lan_host.client_connected:
                self.lan_net_tick = (self.lan_net_tick + 1) % 10000
                if self.lan_net_tick % 6 == 0:
                    self._push_lan_snapshot()
        elif self.state == "ACCOUNTS":
            self._draw_accounts()
        elif self.state == "SAVES":
            self._draw_saves()
        elif self.state == "MODS":
            self.mod_browser.update(dt)
            self.mod_browser.draw(self.screen, self.ui)
        elif self.state == "CODEX":
            self.codex.update(dt)
            self.codex.draw(self.screen, self.ui)
        elif self.state == "CHRONICLE":
            self.chronicle.update(dt)
            self.chronicle.draw(self.screen, self.ui)
        elif self.state == "TUTORIAL":
            self._draw_tutorial()
        elif self.state == "TOUCH_EDIT":
            self.touch.draw_customizer(self.screen, self.ui)
        elif self.state == "SETTINGS":
            self._draw_settings()
        elif self.state in ("GAME_OVER", "VICTORY"):
            self._draw_playing()
            self.ui.draw_end_screen(
                self.screen,
                self.state == "VICTORY",
                self.player,
                self.floor_level,
                self.boss_for_cutscene,
                game_mode=self.game_mode,
                wave_num=self.wave_num,
                hover_btn=self.hover_end_btn,
                touch_active=self.touch.is_active(),
                p2=self.player2 if self.coop_enabled else None,
            )
            if self.lan_host.running and self.lan_host.client_connected:
                self.lan_net_tick = (self.lan_net_tick + 1) % 10000
                if self.lan_net_tick % 8 == 0:
                    self._push_lan_snapshot()

        if self.console.open:
            self.console.draw(self.screen, self.ui)

        if self.fade_alpha > 1.0:
            self.ui.draw_fade(self.screen, ease_in_out(clamp(self.fade_alpha / 255.0, 0.0, 1.0)) * 255.0)

        self.achievement_manager.draw_toast(self.screen, self.ui.font_tiny, self.ui.font_med, ui=self.ui)

    def _recover_from_error(self, exc: Exception, phase: str = "frame"):
        tb_txt = traceback.format_exc()
        log_path = append_crash_log(f"Recovered error in {phase} (state={self.state})", tb_txt)
        now = time.monotonic()
        if (now - self._last_error_ts) < 2.5:
            self._error_streak += 1
        else:
            self._error_streak = 1
        self._last_error_ts = now

        self.fade_alpha = 0.0
        self.shake_timer = 0.0
        self.shake_power = 0.0
        try:
            pygame.key.stop_text_input()
        except Exception:
            pass
        try:
            self.touch.reset()
        except Exception:
            pass

        if phase == "present":
            try:
                clear_render_caches(include_text=True)
                self._apply_display_mode(False, persist=False)
                return
            except Exception:
                pass

        if self.state in ("LAN_CLIENT", "LAN_LOBBY"):
            self.lan_status = tr("recovery_network")
            self.state = "MENU" if self._error_streak >= 2 else "LAN_LOBBY"
        elif self.state in ("PLAYING", "PAUSED", "CUTSCENE", "CHAOS_DRAFT"):
            if self._error_streak < 2 and self.player is not None and self.current_room is not None:
                self.state = "PAUSED"
                self.pause_idx = 0
                try:
                    self.ui.show_banner(tr("recovery_run"), tr("recovery_notice"), duration=90.0)
                except Exception:
                    pass
            else:
                self.state = "MENU"
        else:
            if self._error_streak >= 3:
                apply_safe_boot_settings()
                try:
                    clear_render_caches(include_text=True)
                    self._apply_display_mode(False, persist=False)
                except Exception:
                    pass
            self.state = "MENU"

        self.menu_notice = tr("recovery_notice")
        self.menu_notice_timer = 240.0

    def run(self):
        running = True
        clean_frames = 0
        boot_cleared = False
        try:
            while running and not _SHUTDOWN_REQUESTED:
                ms = self.clock.tick(FPS)
                dt = min(2.5, max(0.25, ms / 16.6667))
                self.fps_val = self.clock.get_fps()
                try:
                    running = self.handle_events()
                except Exception as exc:
                    self._recover_from_error(exc, phase="events")
                    continue
                if not running or _SHUTDOWN_REQUESTED:
                    break
                if self.app_in_background:
                    pygame.time.wait(50)
                    continue
                try:
                    self.step_frame(dt)
                except Exception as exc:
                    self._recover_from_error(exc, phase="step")
                    continue
                try:
                    self._present_frame()
                    pygame.display.flip()
                except pygame.error:
                    try:
                        self._apply_display_mode(False, persist=False)
                    except Exception:
                        pass
                except Exception as exc:
                    self._recover_from_error(exc, phase="present")
                    continue

                clean_frames += 1
                if not boot_cleared and clean_frames >= 3:
                    boot_cleared = True
                    clear_boot_marker()
                if clean_frames >= 30:
                    self._error_streak = 0
        except KeyboardInterrupt:
            pass
        finally:
            clear_boot_marker()
            _cleanup_sdl_resources()
        sys.exit(0)


def _enable_windows_dpi_awareness():
    if sys.platform != "win32":
        return
    try:
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _show_fatal_error(exc: Exception):
    err_text = traceback.format_exc()
    log_path = append_crash_log(f"Fatal startup error: {type(exc).__name__}: {exc}", err_text)
    msg = f"DarkVault error: {exc}"
    if log_path:
        msg += f"\n\nCrash log saved to:\n{log_path}"
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, msg, "DarkVault", 0x10)
        except Exception:
            pass
    elif sys.platform.startswith("linux"):
        try:
            sys.stderr.write(msg + "\n")
        except Exception:
            pass
        try:
            import shutil as _shutil
            import subprocess as _sp

            if _shutil.which("zenity") and (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
                _sp.Popen(["zenity", "--error", "--title=DarkVault", f"--text={msg}"])
        except Exception:
            pass


def _install_thread_excepthook():
    if hasattr(threading, "excepthook"):
        def _on_thread_exc(args):
            try:
                tb = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
                append_crash_log(f"Thread error ({getattr(args.thread, 'name', 'worker')})", tb)
            except Exception:
                pass
        threading.excepthook = _on_thread_exc


if __name__ == "__main__":
    _enable_windows_dpi_awareness()
    _install_signal_handlers()
    _install_thread_excepthook()
    atexit.register(_cleanup_sdl_resources)
    exit_code = 0
    unclean_prev = was_unclean_boot()
    if unclean_prev:
        apply_safe_boot_settings()
    mark_boot_start()
    try:
        game = None
        try:
            game = Game()
        except Exception as init_exc:
            append_crash_log("Init failed, retrying in safe mode", traceback.format_exc())
            apply_safe_boot_settings()
            if sys.platform.startswith("linux"):
                os.environ.pop("SDL_VIDEODRIVER", None)
                os.environ["SDL_AUDIODRIVER"] = "dummy"
            game = Game()
        if unclean_prev and game is not None:
            game._safe_boot_active = True
            game.menu_notice = tr("safe_boot_notice")
            game.menu_notice_timer = 240.0
        game.run()
    except SystemExit as exit_exc:
        exit_code = int(exit_exc.code) if isinstance(exit_exc.code, int) else 0
    except KeyboardInterrupt:
        exit_code = 0
    except Exception as fatal_exc:
        exit_code = 1
        _show_fatal_error(fatal_exc)
    finally:
        clear_boot_marker()
        _cleanup_sdl_resources()
    sys.exit(exit_code)
