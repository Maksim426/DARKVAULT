import math
import random
import pygame
from bullet import AfterimageParticle, RingParticle, SplashParticle, Tear
from enemy import BlueFly
from heroes import get_hero
from items import get_item_by_id, get_random_item
from settings import (
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
    get_shadow_surf,
    gray,
    render_4x_smooth,
    spring_step,
)
from sound import play_sound


_ORB_SPRITE_CACHE = {}


def _get_orb_sprite(kind):
    spr = _ORB_SPRITE_CACHE.get(kind)
    if spr is not None:
        return spr
    _prune_cache(_ORB_SPRITE_CACHE, 16)
    if kind == "orbital":
        def _draw(hi, hw, hh):
            cx = cy = hw * 0.5
            s = 4.0
            draw_aa_circle(hi, (16, 16, 16, 255), cx, cy, 8.0 * s)
            draw_aa_circle(hi, (240, 240, 240, 255), cx, cy, 5.5 * s)

        spr = render_4x_smooth(20, 20, _draw, blur_radius=0.2)
    else:
        def _draw(hi, hw, hh):
            cx = cy = hw * 0.5
            s = 4.0
            draw_aa_circle(hi, (248, 248, 248, 255), cx, cy, 5.0 * s)
            draw_aa_circle(hi, (182, 182, 182, 255), cx, cy, 2.2 * s)

        spr = render_4x_smooth(14, 14, _draw, blur_radius=0.2)
    _ORB_SPRITE_CACHE[kind] = spr
    return spr


_PLAYER_TAG_CACHE = {}


def _get_player_tag_surf(tag):
    cached = _PLAYER_TAG_CACHE.get(tag)
    if cached is not None:
        return cached
    _prune_cache(_PLAYER_TAG_CACHE, 16)
    is_p2 = str(tag) == "P2"
    w, h = 26, 14
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    bg = (16, 16, 16, 224) if is_p2 else (238, 238, 238, 230)
    border = (242, 242, 242, 255) if is_p2 else (14, 14, 14, 255)
    fg = (244, 244, 244) if is_p2 else (12, 12, 12)
    pygame.draw.rect(surf, bg, (0, 0, w, h), border_radius=4)
    pygame.draw.rect(surf, border, (0, 0, w, h), 1, border_radius=4)
    try:
        font = pygame.font.Font(None, 15)
        txt = font.render(str(tag), True, fg)
        surf.blit(txt, (w // 2 - txt.get_width() // 2, h // 2 - txt.get_height() // 2))
    except Exception:
        pass
    _PLAYER_TAG_CACHE[tag] = surf
    return surf


class Player:
    def __init__(self, x, y, hero_id="isaac"):
        self.x = float(x)
        self.y = float(y)
        self.vx = 0.0
        self.vy = 0.0
        self.hero_id = hero_id
        hero = get_hero(hero_id)
        self.hero = hero
        self.radius = 15.0
        self.hp = int(hero["hp"])
        self.max_hp = int(hero["max_hp"])
        self.soul_hp = int(hero["soul_hp"])
        self.black_hp = int(hero["black_hp"])
        self.speed = float(hero["speed"])
        self.damage = float(hero["damage"])
        self.fire_delay = float(hero["fire_delay"])
        self.tear_speed = float(hero["tear_speed"])
        self.tear_range = float(hero["tear_range"])
        self.luck = int(hero["luck"])
        self.coins = int(hero["coins"])
        self.bombs = int(hero["bombs"])
        self.keys = int(hero["keys"])

        self.has_flight = bool(hero.get("has_flight", False))
        self.has_piercing = bool(hero.get("has_piercing", False))
        self.has_homing = bool(hero.get("has_homing", False))
        self.has_bouncing = bool(hero.get("has_bouncing", False))
        self.has_splitting = bool(hero.get("has_splitting", False))
        self.has_spectral = bool(hero.get("has_spectral", False))
        self.has_poison = bool(hero.get("has_poison", False))
        self.has_holy = bool(hero.get("has_holy", False))
        self.has_bone = hero_id == "forgotten"
        self.has_brimstone = hero_id == "azazel"
        self.has_boomerang = False
        self.has_coal = False
        self.has_wafer = False
        self.has_pyromaniac = False
        self.has_steam_sale = False
        self.has_moms_key = False
        self.has_sad_bombs = False
        self.has_skatole = False
        self.has_relic = False
        self.has_dark_bum = False
        self.has_placenta = False
        self.has_infamy = False
        self.has_whore = False
        self.has_lazarus_revive = False
        self.has_bloody_lust = False
        self.bloody_lust_stacks = 0
        self.dark_bum_counter = 0
        self.keeper_coin_counter = 0
        self.seraph_room_counter = 0
        self.last_active_status = ("ok", "")

        self.lantern_fuel = 1.0
        self.lantern_bonus = float(hero.get("lantern_bonus", 1.0))
        self.slow_projectiles = bool(hero.get("slow_projectiles", False))
        self.dodge_chance = 0.0
        self.free_locks = False
        self.compass_reveal = False
        self.eclipse_aura = False

        self.multi_shot = int(hero.get("multi_shot", 1))
        self.orbitals = int(hero.get("orbitals", 0))
        self.orbital_angle = 0.0
        self.incubus_count = 0
        self.incubus_pos = (self.x - 32.0, self.y + 12.0)
        self.wisps = 0
        self.wisp_angle = 0.0
        self.holy_mantle = False
        self.mantle_broken_room = False

        self.active_items = []
        self.active_slot = 0
        self.inventory_page = 0
        self.selected_inv_idx = 0
        self.void_absorbed = 0

        self.collected_items = []
        self.collected_ids = set()

        self.active_effects = {}
        self.noclip = False

        self.shoot_cd = 0.0
        self.shoot_anim = 0.0
        self.invuln_timer = 0.0
        self.book_shadows_timer = 0.0
        self.room_dmg_bonus = 0.0
        self.room_extra_familiars = 0
        self.room_extra_orbitals = 0
        self.room_extra_wisps = 0
        self.dash_timer = 0.0
        self.dash_cd = 0.0
        self.dash_max_cd = float(hero.get("dash_max_cd", 95.0))
        self.dash_vx = 0.0
        self.dash_vy = 0.0
        self.walk_phase = 0.0
        self.idle_phase = 0.0
        self.facing = (0.0, 1.0)
        self.face_angle = math.pi * 0.5
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.scale_vel = 0.0
        self.cloak_nodes = [(self.x, self.y + i * 3.5) for i in range(7)]
        self.hurt_flash = 0.0
        self.kills = 0
        self.shots_fired = 0
        self.allies = []
        self.player_tag = ""

        self.air_z = 0.0
        self.air_vz = 0.0
        self.jump_cd = 0.0
        self.jump_max_cd = 120.0
        self.jump_empowered = False
        self.jump_slam_pending = None
        self.bomb_cd = 0.0
        self.bomb_max_cd = 75.0
        self.melee_cd = 0.0
        self.melee_max_cd = 22.0
        self.melee_slash_timer = 0.0
        self.melee_slash_angle = 0.0
        self.melee_slash_arc = 1.9
        self.melee_combo_step = 0
        self.melee_combo_timer = 0.0
        self.melee_slash_dir = 1
        self.melee_is_finisher = False
        self.melee_hits = 0
        self.melee_kills = 0
        self.has_explosive_tears = False
        self.has_lobbed_tears = False
        self.has_seismic_boots = False
        self.has_shock_core = False
        self.has_vortex = bool(hero.get("has_vortex", False))
        self.has_chain_arc = bool(hero.get("has_chain_arc", False))
        self.has_dash_strike = bool(hero.get("has_dash_strike", False))
        self.ash_bolt_every = int(hero.get("ash_bolt_every", 0))
        self.crit_chance = float(hero.get("crit_chance", 0.0))
        self.coin_dmg_scale = float(hero.get("coin_dmg_scale", 0.0))
        self.invis_timer = 0.0
        self.invis_cd = 0.0
        self.invis_max_cd = float(hero.get("invis_max_cd", 360.0))
        self.ambush_mult = float(hero.get("ambush_mult", 2.0))

        if hero["starting_active"]:
            act = get_item_by_id(hero["starting_active"])
            if act:
                self._equip_active(act)

        for pid in hero["starting_passive"]:
            it = get_item_by_id(pid)
            if it:
                self.apply_item(it, silent=True)

        if hero_id == "eden":
            self.damage += random.uniform(-0.4, 1.4)
            self.speed += random.uniform(-0.3, 0.7)
            self.fire_delay = max(10.0, self.fire_delay + random.uniform(-3.0, 2.0))
            oracle_gift = random.choice(("has_homing", "has_bouncing", "has_splitting", "has_piercing", "has_chain_arc"))
            setattr(self, oracle_gift, True)
            rand_p = get_random_item(item_type="passive")
            rand_a = get_random_item(item_type="active")
            if rand_p:
                self.apply_item(rand_p, silent=True)
            if rand_a:
                self._equip_active(rand_a)

        if hero_id == "bethany":
            self.wisps = 3
        elif hero_id == "keeper":
            self.multi_shot = max(3, self.multi_shot)
        elif hero_id == "seraph":
            self.wisps = max(2, self.wisps)

    def _clamp_active_slot(self):
        if not self.active_items:
            self.active_slot = 0
            return False
        if self.active_slot < 0 or self.active_slot >= len(self.active_items):
            self.active_slot = max(0, min(self.active_slot, len(self.active_items) - 1))
        return True

    @property
    def active_item(self):
        if self._clamp_active_slot():
            return self.active_items[self.active_slot]["item"]
        return None

    @active_item.setter
    def active_item(self, item_data):
        if item_data is None:
            return
        self._equip_active(item_data)

    @property
    def max_charge(self):
        if self._clamp_active_slot():
            return self.active_items[self.active_slot]["max_charge"]
        return 0

    @max_charge.setter
    def max_charge(self, val):
        if self._clamp_active_slot():
            self.active_items[self.active_slot]["max_charge"] = max(0, int(val))

    @property
    def active_charge(self):
        if self._clamp_active_slot():
            return self.active_items[self.active_slot]["charge"]
        return 0

    @active_charge.setter
    def active_charge(self, val):
        if self._clamp_active_slot():
            mc = self.active_items[self.active_slot]["max_charge"]
            self.active_items[self.active_slot]["charge"] = int(clamp(int(val), 0, mc))

    @property
    def red_hp(self):
        return self.hp

    @red_hp.setter
    def red_hp(self, val):
        self.hp = int(max(0, val))

    @property
    def max_red_hp(self):
        return self.max_hp

    @max_red_hp.setter
    def max_red_hp(self, val):
        self.max_hp = int(max(0, val))

    @property
    def dash_cd_max(self):
        return self.dash_max_cd

    @dash_cd_max.setter
    def dash_cd_max(self, val):
        self.dash_max_cd = float(max(12.0, val))

    @property
    def invis_cd_max(self):
        return self.invis_max_cd

    @invis_cd_max.setter
    def invis_cd_max(self, val):
        self.invis_max_cd = float(max(60.0, val))

    def _equip_active(self, item_data):
        if not item_data or not item_data.get("id"):
            return
        iid = item_data["id"]
        mc = max(0, int(item_data.get("max_charge", 4)))
        for idx, slot in enumerate(self.active_items):
            if slot["item"]["id"] == iid:
                self.active_slot = idx
                slot["charge"] = mc
                self.selected_inv_idx = idx
                self.inventory_page = idx // 9
                return
        if len(self.active_items) < 9:
            self.active_items.append({"item": item_data, "charge": mc, "max_charge": mc})
            self.active_slot = len(self.active_items) - 1
            self.collected_ids.add(iid)
        else:
            self._clamp_active_slot()
            self.active_items[self.active_slot] = {"item": item_data, "charge": mc, "max_charge": mc}
            self.collected_ids.add(iid)
        self.selected_inv_idx = self.active_slot
        self.inventory_page = self.selected_inv_idx // 9

    def is_active_ready(self):
        if not self._clamp_active_slot():
            return False
        slot = self.active_items[self.active_slot]
        return slot["max_charge"] <= 0 or slot["charge"] >= slot["max_charge"]

    def add_charge(self, amount=1):
        if not self._clamp_active_slot():
            return False
        amt = int(max(1, amount))
        slot = self.active_items[self.active_slot]
        if slot["charge"] < slot["max_charge"]:
            slot["charge"] = min(slot["max_charge"], slot["charge"] + amt)
            return True
        for alt in self.active_items:
            if alt["charge"] < alt["max_charge"]:
                alt["charge"] = min(alt["max_charge"], alt["charge"] + amt)
                return True
        return False

    def recharge_active(self, full=True):
        if not self.active_items:
            return False
        slot = self.active_items[self.active_slot]
        if full:
            changed = slot["charge"] < slot["max_charge"]
            slot["charge"] = slot["max_charge"]
            if not changed:
                for alt in self.active_items:
                    if alt["charge"] < alt["max_charge"]:
                        alt["charge"] = alt["max_charge"]
                        return True
            return True
        return self.add_charge(1)

    def get_inventory_entries(self):
        entries = []
        for idx, slot in enumerate(self.active_items):
            entries.append(("active", idx, slot["item"], slot["charge"], slot["max_charge"]))
        for idx, it in enumerate(self.collected_items):
            entries.append(("passive", idx, it, 0, 0))
        return entries

    def get_inventory_page_count(self):
        total = len(self.get_inventory_entries())
        return max(1, (total + 8) // 9)

    def get_inventory_page_entries(self):
        entries = self.get_inventory_entries()
        pc = self.get_inventory_page_count()
        self.inventory_page = int(clamp(self.inventory_page, 0, pc - 1))
        start = self.inventory_page * 9
        return entries[start:start + 9], start

    def cycle_inventory_page(self, delta=1):
        pc = self.get_inventory_page_count()
        self.inventory_page = (self.inventory_page + int(delta)) % pc
        return self.inventory_page

    def get_selected_inventory_entry(self):
        entries = self.get_inventory_entries()
        if not entries:
            return None
        if 0 <= self.selected_inv_idx < len(entries):
            return entries[self.selected_inv_idx]
        if self._clamp_active_slot():
            self.selected_inv_idx = self.active_slot
            return entries[self.selected_inv_idx]
        self.selected_inv_idx = len(entries) - 1
        return entries[self.selected_inv_idx]

    def select_inventory_slot(self, slot_1_to_9):
        entries = self.get_inventory_entries()
        abs_idx = self.inventory_page * 9 + (int(slot_1_to_9) - 1)
        if abs_idx < 0 or abs_idx >= len(entries):
            return None
        self.selected_inv_idx = abs_idx
        kind, sub_idx, it, _, _ = entries[abs_idx]
        if kind == "active":
            self.active_slot = sub_idx
        return it

    def add_effect(self, eid, duration_sec=20.0):
        frames = 9999999.0 if duration_sec <= 0 else float(duration_sec) * 60.0
        self.active_effects[eid] = max(self.active_effects.get(eid, 0.0), frames)

    def clear_effects(self, eid=None):
        if eid is None:
            self.active_effects.clear()
        else:
            self.active_effects.pop(eid, None)

    def has_effect(self, eid):
        return self.active_effects.get(eid, 0.0) > 0.0

    def has_effective_flight(self):
        return bool(self.has_flight or self.noclip or self.has_effect("flight"))

    def reset_for_new_room(self):
        self.room_dmg_bonus = 0.0
        self.room_extra_familiars = 0
        self.room_extra_orbitals = 0
        self.room_extra_wisps = 0
        self.mantle_broken_room = False
        self.air_z = 0.0
        self.air_vz = 0.0
        self.jump_empowered = False
        self.jump_slam_pending = None
        self.incubus_pos = (self.x - 32.0, self.y + 12.0)
        self.cloak_nodes = [(self.x, self.y + i * 3.5) for i in range(7)]

    def reset_for_new_floor(self):
        self.bloody_lust_stacks = 0

    def get_effective_damage(self):
        dmg = self.damage + self.room_dmg_bonus
        if self.has_bloody_lust:
            dmg += self.bloody_lust_stacks * 0.75
        if self.has_whore and self.hp <= 2:
            dmg += 1.85
        if self.coin_dmg_scale > 0.0 and self.coins > 0:
            dmg += min(2.0, self.coins * self.coin_dmg_scale)
        if self.has_effect("rage"):
            dmg *= 1.65
        if self.has_effect("giant"):
            dmg *= 1.35
        return max(1.0, dmg)

    def get_effective_speed(self):
        spd = self.speed
        if self.has_whore and self.hp <= 2:
            spd += 0.75
        if self.has_effect("haste"):
            spd += 2.1
        return max(2.0, min(9.8, spd))

    def get_effective_fire_delay(self):
        fd = self.fire_delay
        if self.has_effect("haste"):
            fd *= 0.55
        return max(4.0, fd)

    def get_effective_radius(self):
        return self.radius * (1.42 if self.has_effect("giant") else 1.0)

    def apply_item(self, item_data, silent=False):
        if not item_data or not isinstance(item_data, dict) or not item_data.get("id"):
            return
        iid = item_data["id"]
        if item_data.get("type") == "active":
            self._equip_active(item_data)
            self.scale_vel += 0.16
            if not silent:
                play_sound("item")
            return

        self.collected_items.append(item_data)
        self.collected_ids.add(iid)
        self.scale_vel += 0.18

        if iid == "eclipse_shard":
            self.damage += 2.0
            self.orbitals += 1
            self.eclipse_aura = True
        elif iid == "bone_compass":
            self.speed += 0.8
            self.has_homing = True
            self.compass_reveal = True
        elif iid == "frozen_hourglass":
            self.fire_delay = max(5.0, self.fire_delay - 2.5)
            self.slow_projectiles = True
        elif iid == "crown_of_ash":
            self.damage += 2.2
            self.black_hp += 4
            self.holy_mantle = True
        elif iid == "mask_of_void":
            self.damage += 1.2
            self.dodge_chance = min(0.6, self.dodge_chance + 0.28)
        elif iid == "monolith_tear":
            self.has_piercing = True
            self.has_spectral = True
            self.tear_range += 90.0
        elif iid == "seers_skull":
            self.luck += 2
            self.damage += 1.5
            self.lantern_bonus += 0.35
            self.lantern_fuel = min(1.4, self.lantern_fuel + 0.35)
        elif iid == "key_of_abyss":
            self.keys += 5
            self.damage += 0.9
            self.free_locks = True
        elif iid == "spoon_bender":
            self.has_homing = True
        elif iid == "sad_onion":
            self.fire_delay = max(6.0, self.fire_delay - 3.0)
        elif iid == "crickets_head":
            self.damage = (self.damage + 2.2) * 1.25
        elif iid == "cricket_body":
            self.has_splitting = True
            self.fire_delay = max(6.0, self.fire_delay - 1.5)
        elif iid == "the_belt":
            self.speed += 0.9
        elif iid == "mutant_spider":
            self.multi_shot = max(self.multi_shot, 4)
            self.fire_delay += 5.0
        elif iid == "inner_eye":
            self.multi_shot = max(self.multi_shot, 3)
            self.fire_delay += 3.0
        elif iid == "twin_lens":
            self.multi_shot = max(self.multi_shot, 2)
        elif iid == "my_reflection":
            self.has_boomerang = True
            self.tear_range += 80.0
        elif iid == "number_one":
            self.fire_delay = max(5.0, self.fire_delay - 5.0)
            self.tear_range = max(240.0, self.tear_range - 70.0)
        elif iid == "phantom_blade":
            self.has_piercing = True
            self.has_spectral = True
        elif iid == "twilight_prism":
            self.damage += 1.0
            self.tear_range += 80.0
            self.fire_delay = max(6.0, self.fire_delay - 2.0)
        elif iid == "guardian_shard":
            self.orbitals += 1
        elif iid == "twin_orbitals":
            self.orbitals += 2
        elif iid == "blood_ruby":
            self.max_hp += 2
            self.hp = min(self.max_hp, self.hp + 2)
            self.damage += 1.2
        elif iid == "shadow_cloak":
            self.speed += 0.6
            self.dash_max_cd = max(26.0, self.dash_max_cd - 20.0)
        elif iid == "rubber_cement":
            self.has_bouncing = True
        elif iid in ("dinner", "breakfast", "rotten_meat", "lunch", "dessert", "snack"):
            self.max_hp += 2
            self.hp = min(self.max_hp, self.hp + 2)
            if iid == "snack":
                self.speed += 0.4
        elif iid == "magic_mushroom":
            self.max_hp += 2
            self.hp = self.max_hp
            self.damage = (self.damage + 1.0) * 1.25
            self.speed += 0.5
            self.tear_range += 60.0
        elif iid in ("brimstone", "brimstone_pact"):
            self.has_brimstone = True
            self.has_piercing = True
            self.damage += 3.2 if iid == "brimstone" else 2.4
            if iid == "brimstone_pact":
                self.black_hp += 4
        elif iid == "polyphemus":
            self.damage = (self.damage + 3.5) * 1.35
            self.fire_delay += 6.0
        elif iid in ("holy_mantle", "holy_mantle_shield"):
            self.holy_mantle = True
        elif iid == "pentagram":
            self.damage += 1.6
        elif iid == "halo":
            self.max_hp += 2
            self.hp = min(self.max_hp, self.hp + 2)
            self.damage += 0.8
            self.speed += 0.4
            self.fire_delay = max(6.0, self.fire_delay - 1.5)
        elif iid == "meat":
            self.max_hp += 2
            self.hp = min(self.max_hp, self.hp + 2)
            self.damage += 0.6
        elif iid == "the_pact":
            self.damage += 1.2
            self.fire_delay = max(6.0, self.fire_delay - 2.0)
            self.black_hp += 4
        elif iid == "the_mark":
            self.damage += 1.4
            self.speed += 0.6
            self.black_hp += 2
        elif iid == "lord_of_the_pit":
            self.has_flight = True
            self.speed += 0.7
        elif iid == "tooth_picks":
            self.fire_delay = max(6.0, self.fire_delay - 2.5)
            self.tear_speed += 1.2
        elif iid in ("steven", "blood_martyr", "tough_love", "cat_head"):
            self.damage += 1.4
        elif iid == "sacred_heart":
            self.damage = (self.damage + 1.2) * 1.4
            self.has_homing = True
            self.has_holy = True
            self.max_hp += 2
            self.hp = self.max_hp
        elif iid == "godhead":
            self.damage = (self.damage + 1.5) * 1.35
            self.has_homing = True
            self.has_holy = True
        elif iid == "cancer":
            self.fire_delay = max(4.0, self.fire_delay - 4.0)
        elif iid == "mini_mush":
            self.radius = max(11.0, self.radius - 2.5)
            self.speed += 0.8
        elif iid in ("cat_o_nine_tails", "iron_bar", "synthoil", "jesus_juice", "growth_hormones", "stigmata"):
            self.damage += 0.9
            self.tear_speed += 0.8
            self.tear_range += 35.0
        elif iid in ("moms_heels", "roid_rage", "wooden_spoon", "speed_ball"):
            self.speed += 0.65
            self.tear_range += 50.0
        elif iid == "wire_coat_hanger":
            self.fire_delay = max(5.0, self.fire_delay - 3.0)
        elif iid == "skeleton_key":
            self.keys += 12
        elif iid == "pyro":
            self.bombs += 12
        elif iid == "pyromaniac":
            self.has_pyromaniac = True
            self.bombs += 5
        elif iid == "a_dollar":
            self.coins += 30
        elif iid == "magic_8_ball":
            self.tear_speed += 1.0
            self.luck += 1
        elif iid in ("rosary", "mitre"):
            self.soul_hp += 4
            self.fire_delay = max(6.0, self.fire_delay - 1.5)
        elif iid == "capricorn":
            self.damage += 0.8
            self.speed += 0.4
            self.coins += 1
            self.bombs += 1
            self.keys += 1
        elif iid == "scorpio":
            self.has_poison = True
        elif iid == "super_bandage":
            self.max_hp += 2
            self.hp = min(self.max_hp, self.hp + 2)
            self.soul_hp += 4
        elif iid == "infamy":
            self.has_infamy = True
        elif iid == "the_relic":
            self.has_relic = True
        elif iid == "the_wafer":
            self.has_wafer = True
        elif iid == "whore_of_babylon":
            self.has_whore = True
        elif iid == "dark_bum":
            self.has_dark_bum = True
        elif iid == "stem_cells":
            self.max_hp += 2
            self.hp = min(self.max_hp, self.hp + 2)
            self.tear_speed += 0.8
        elif iid == "black_lotus":
            self.max_hp += 2
            self.hp = min(self.max_hp, self.hp + 2)
            self.soul_hp += 2
            self.black_hp += 2
        elif iid == "iron_maiden":
            self.damage += 1.4
            self.speed = max(2.2, self.speed - 0.2)
            self.soul_hp += 2
        elif iid == "torn_photo":
            self.tear_speed += 1.2
            self.fire_delay = max(6.0, self.fire_delay - 2.0)
        elif iid == "blood_bag":
            self.max_hp += 2
            self.hp = min(self.max_hp, self.hp + 4)
            self.speed += 0.5
        elif iid == "lucky_foot":
            self.luck += 2
        elif iid == "skatole":
            self.has_skatole = True
        elif iid == "abaddon":
            self.damage += 2.5
            self.black_hp += 8
            self.speed += 0.5
        elif iid == "spirit_night":
            self.has_flight = True
            self.has_spectral = True
        elif iid == "raw_liver":
            self.max_hp += 4
            self.hp = self.max_hp
        elif iid == "placenta":
            self.max_hp += 2
            self.hp = min(self.max_hp, self.hp + 2)
            self.has_placenta = True
        elif iid == "steam_sale":
            self.has_steam_sale = True
        elif iid == "moms_key":
            self.keys += 2
            self.has_moms_key = True
        elif iid == "sad_bombs":
            self.has_sad_bombs = True
        elif iid == "bloody_lust":
            self.has_bloody_lust = True
        elif iid == "lazarus_rags":
            self.has_lazarus_revive = True
        elif iid == "incubus":
            self.incubus_count += 1
        elif iid == "bone_club":
            self.has_bone = True
            self.has_piercing = True
            self.damage += 1.4
        elif iid == "lump_of_coal":
            self.has_coal = True
        elif iid == "blast_tear":
            self.has_explosive_tears = True
            self.damage += 1.2
        elif iid == "mortar_eye":
            self.has_lobbed_tears = True
            self.tear_range += 80.0
            self.damage += 0.9
        elif iid == "seismic_boots":
            self.has_seismic_boots = True
            self.jump_max_cd = max(40.0, self.jump_max_cd - 20.0)
            self.speed += 0.45
        elif iid == "shock_core":
            self.has_shock_core = True
            self.fire_delay = max(5.0, self.fire_delay - 1.5)
        elif iid == "phantom_cloak":
            self.invis_max_cd = max(120.0, self.invis_max_cd * 0.72)
            self.ambush_mult += 0.5
            self.dodge_chance = min(0.65, self.dodge_chance + 0.12)
        elif iid == "singularity_orb":
            self.has_vortex = True
            self.damage += 1.0
        elif iid == "chain_coil":
            self.has_chain_arc = True
            self.fire_delay = max(5.0, self.fire_delay - 1.5)
        elif iid == "storm_greaves":
            self.has_dash_strike = True
            self.speed += 0.45
            self.dash_max_cd = max(28.0, self.dash_max_cd - 10.0)

        if not silent:
            play_sound("item")

    def use_active(self, room, tears, enemies, particles):
        if self.active_item is None:
            self.last_active_status = ("no_item", "")
            return False
        if self.active_charge < self.max_charge:
            self.last_active_status = ("no_charge", f"{self.active_charge}/{self.max_charge}")
            return False
        iid = self.active_item["id"]
        if iid == "yum_heart":
            if self.max_hp > 0:
                if self.hp >= self.max_hp:
                    self.last_active_status = ("hp_full", "")
                    return False
                self.hp = min(self.max_hp, self.hp + 2)
            else:
                if self.soul_hp >= 12:
                    self.last_active_status = ("hp_full", "")
                    return False
                self.soul_hp += 1
        elif iid == "guppys_head":
            for i in range(3):
                if len(self.allies) < 14:
                    self.allies.append(BlueFly(self.x + (i - 1) * 16, self.y - 16, self.get_effective_damage() * 1.5))
        elif iid == "the_d6":
            changed = False
            for ped in room.pedestals:
                if ped.alive:
                    ex = set(self.collected_ids)
                    if ped.item and ped.item.get("id"):
                        ex.add(ped.item["id"])
                    ped.item = get_random_item(ex)
                    changed = True
            if not changed:
                self.last_active_status = ("no_pedestals", "")
                return False
        elif iid == "book_of_belial":
            self.room_dmg_bonus += 2.5
        elif iid == "book_of_shadows":
            self.book_shadows_timer = 480.0
        elif iid == "razor_blade":
            if self.hp + self.soul_hp + self.black_hp <= 1:
                self.last_active_status = ("low_hp", "")
                return False
            if self.hp > 1 or (self.hp > 0 and (self.soul_hp + self.black_hp) > 0):
                self.hp -= 1
            elif self.black_hp > 0:
                self.black_hp -= 1
            elif self.soul_hp > 0:
                self.soul_hp -= 1
            self.hurt_flash = 10.0
            play_sound("hurt")
            self.room_dmg_bonus += 1.6
        elif iid == "box_of_friends":
            self.room_extra_familiars += 1
            if self.orbitals > 0:
                self.room_extra_orbitals += 1
            if self.wisps > 0:
                self.room_extra_wisps += 2
            existing_flies = [a for a in self.allies if getattr(a, "alive", True)]
            if existing_flies:
                for fl in list(existing_flies):
                    if len(self.allies) >= 14:
                        break
                    self.allies.append(BlueFly(fl.x + random.uniform(-14, 14), fl.y + random.uniform(-14, 14), self.get_effective_damage() * 1.4))
            else:
                for i in range(2):
                    self.allies.append(BlueFly(self.x + (i - 0.5) * 16, self.y - 14, self.get_effective_damage() * 1.4))
        elif iid == "void":
            absorbed = False
            for ped in room.pedestals:
                if ped.alive:
                    ped.alive = False
                    self.void_absorbed += 1
                    self.damage += 0.8
                    self.speed += 0.25
                    self.fire_delay = max(5.0, self.fire_delay - 1.0)
                    absorbed = True
            if not absorbed:
                self.last_active_status = ("no_pedestals", "")
                return False
        elif iid == "book_of_virtues":
            self.wisps = min(8, self.wisps + 3)
        elif iid == "krampus_head":
            for dir_x, dir_y in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                tears.append(
                    Tear(
                        self.x,
                        self.y,
                        dir_x * 9.5,
                        dir_y * 9.5,
                        damage=self.get_effective_damage() * 1.8,
                        max_range=520.0,
                        radius=12.0,
                        piercing=True,
                        brimstone=True,
                        owner_x=self.x,
                        owner_y=self.y,
                    )
                )
        elif iid == "the_poop":
            from room import Obstacle
            px = clamp(self.x - self.facing[0] * 44.0, PLAYABLE_LEFT + 34, PLAYABLE_RIGHT - 34)
            py = clamp(self.y - self.facing[1] * 44.0, PLAYABLE_TOP + 34, PLAYABLE_BOTTOM - 34)
            dcx = (PLAYABLE_LEFT + PLAYABLE_RIGHT) * 0.5
            dcy = (PLAYABLE_TOP + PLAYABLE_BOTTOM) * 0.5
            for dx_pos, dy_pos in (
                (dcx, PLAYABLE_TOP),
                (dcx, PLAYABLE_BOTTOM),
                (PLAYABLE_LEFT, dcy),
                (PLAYABLE_RIGHT, dcy),
            ):
                dist_d = math.hypot(px - dx_pos, py - dy_pos)
                if dist_d < 84.0:
                    nx = (dcx - dx_pos) if abs(dx_pos - dcx) > 1.0 else 0.0
                    ny = (dcy - dy_pos) if abs(dy_pos - dcy) > 1.0 else 0.0
                    nl = math.hypot(nx, ny) or 1.0
                    px = clamp(px + (nx / nl) * (86.0 - dist_d), PLAYABLE_LEFT + 34, PLAYABLE_RIGHT - 34)
                    py = clamp(py + (ny / nl) * (86.0 - dist_d), PLAYABLE_TOP + 34, PLAYABLE_BOTTOM - 34)
            room.obstacles.append(Obstacle(px, py, "poop"))
        elif iid == "wooden_nickel":
            from items import Pickup
            roll = random.random()
            if roll < 0.65:
                kind = "nickel" if random.random() < 0.2 else "coin"
                px = clamp(self.x + random.uniform(-22, 22), PLAYABLE_LEFT + 24, PLAYABLE_RIGHT - 24)
                py = clamp(self.y + 24, PLAYABLE_TOP + 24, PLAYABLE_BOTTOM - 24)
                room.pickups.append(Pickup(px, py, kind))
            else:
                self.soul_hp = min(14, self.soul_hp + 1)
        elif iid == "chrono_pocket":
            for e in enemies:
                if getattr(e, "alive", True):
                    e.freeze_timer = max(getattr(e, "freeze_timer", 0.0), 240.0)
            self.add_effect("haste", 5.0)
        elif iid == "philosopher_vial":
            from items import Pickup
            dmg = self.get_effective_damage() * 1.15
            for i in range(8):
                a = i * (math.pi / 4.0)
                tears.append(
                    Tear(
                        self.x,
                        self.y,
                        math.cos(a) * (self.tear_speed * 0.95),
                        math.sin(a) * (self.tear_speed * 0.95),
                        damage=dmg,
                        max_range=self.tear_range * 0.95,
                        radius=7.5,
                        poison=True,
                        spectral=True,
                        owner_x=self.x,
                        owner_y=self.y,
                    )
                )
            px = clamp(self.x + random.uniform(-26, 26), PLAYABLE_LEFT + 24, PLAYABLE_RIGHT - 24)
            py = clamp(self.y + 22, PLAYABLE_TOP + 24, PLAYABLE_BOTTOM - 24)
            room.pickups.append(Pickup(px, py, random.choice(["coin", "bomb", "key", "half_heart"])))
        elif iid == "iron_bastion":
            self.room_extra_orbitals += 2
            for e in enemies:
                if getattr(e, "alive", True):
                    dx_e = e.x - self.x
                    dy_e = e.y - self.y
                    dist_e = math.hypot(dx_e, dy_e)
                    if dist_e < 165.0:
                        nd = dist_e or 1.0
                        e.take_damage(10.0, (dx_e / nd) * 9.0, (dy_e / nd) * 9.0)
        elif iid == "seraph_bell":
            self.holy_mantle = True
            self.mantle_broken_room = False
            dmg = self.get_effective_damage() * 1.25
            for i in range(8):
                a = i * (math.pi / 4.0)
                tears.append(
                    Tear(
                        self.x,
                        self.y,
                        math.cos(a) * self.tear_speed,
                        math.sin(a) * self.tear_speed,
                        damage=dmg,
                        max_range=self.tear_range * 1.1,
                        radius=7.5,
                        homing=True,
                        holy=True,
                        spectral=True,
                        owner_x=self.x,
                        owner_y=self.y,
                    )
                )
        elif iid == "cluster_detonator":
            dmg = self.get_effective_damage() * 1.45
            for i in range(6):
                a = i * (math.pi / 3.0)
                tears.append(
                    Tear(
                        self.x,
                        self.y,
                        math.cos(a) * (self.tear_speed * 0.85),
                        math.sin(a) * (self.tear_speed * 0.85),
                        damage=dmg,
                        max_range=min(280.0, self.tear_range * 0.78),
                        radius=8.5,
                        explosive=True,
                        lobbed=True,
                        shockwave=True,
                        blast_radius=72.0,
                        owner_x=self.x,
                        owner_y=self.y,
                    )
                )
        elif iid == "comet_leap":
            self.try_jump(self.facing[0], self.facing[1], particles, empowered=True, ignore_cd=True)
            self.invuln_timer = max(self.invuln_timer, 38.0)
        else:
            for e in enemies:
                if getattr(e, "alive", True):
                    e.take_damage(4.0)

        self.active_charge = 0
        self.last_active_status = ("ok", iid)
        self.scale_vel += 0.14
        play_sound("pickup")
        for _ in range(10):
            ang = random.uniform(0.0, math.pi * 2.0)
            particles.append(SplashParticle(self.x, self.y, math.cos(ang) * 2.6, math.sin(ang) * 2.6, (238, 238, 238), 3, 18))
        return True

    def heal_red(self, amount=1):
        if self.hp >= self.max_hp:
            return False
        self.hp = min(self.max_hp, self.hp + int(max(1, amount)))
        return True

    def try_dash(self, mx, my, particles, tears=None, enemies=None):
        if self.dash_cd > 0 or self.dash_timer > 0:
            return False
        dx, dy = (mx, my) if (mx != 0 or my != 0) else self.facing
        d = math.hypot(dx, dy) or 1.0
        self.dash_vx = (dx / d) * 11.5
        self.dash_vy = (dy / d) * 11.5
        self.dash_timer = 11.0
        self.dash_cd = self.dash_max_cd * (0.6 if self.has_effect("haste") else 1.0)
        self.invuln_timer = max(self.invuln_timer, 14.0)
        self.scale_vel += 0.20
        play_sound("teleport")
        for _ in range(6):
            particles.append(AfterimageParticle(self.x, self.y, int(self.get_effective_radius() + 3), (228, 228, 228), 14))
        if self.hero_id == "nocturne" or self.has_dash_strike:
            if tears is not None:
                dmg = self.get_effective_damage() * (0.95 if self.has_dash_strike else 0.9)
                for a in (0.0, math.pi * 0.5, math.pi, math.pi * 1.5):
                    tears.append(
                        Tear(
                            self.x,
                            self.y,
                            math.cos(a) * 8.4,
                            math.sin(a) * 8.4,
                            damage=dmg,
                            max_range=260.0,
                            radius=6.0,
                            spectral=True,
                            bouncing=True,
                            chain_arc=self.has_chain_arc,
                            owner_x=self.x,
                            owner_y=self.y,
                        )
                    )
            if enemies is not None:
                for e in enemies:
                    if getattr(e, "alive", True) and math.hypot(e.x - self.x, e.y - self.y) <= (112.0 if self.has_dash_strike else 95.0):
                        e.take_damage(max(5.5, self.get_effective_damage() * (1.6 if self.has_dash_strike else 1.4)))
            if self.has_dash_strike:
                particles.append(RingParticle(self.x, self.y, 110, (242, 242, 242), 16, width=2))
        return True

    def try_jump(self, mx, my, particles, empowered=False, ignore_cd=False):
        if self.air_z > 0.0:
            return False
        if not ignore_cd and self.jump_cd > 0.0:
            return False
        self.air_z = 2.0
        self.air_vz = 8.4 if empowered else 6.8
        self.jump_empowered = bool(empowered)
        if not ignore_cd:
            self.jump_cd = self.jump_max_cd * (0.6 if self.has_effect("haste") else 1.0)
        dx, dy = (mx, my) if (mx != 0 or my != 0) else (self.facing if empowered else (0.0, 0.0))
        d = math.hypot(dx, dy)
        if d > 0.01:
            boost = 5.4 if empowered else 2.8
            self.vx += (dx / d) * boost
            self.vy += (dy / d) * boost
        self.invuln_timer = max(self.invuln_timer, 38.0 if empowered else 22.0)
        self.scale_vel -= 0.18
        play_sound("teleport")
        particles.append(RingParticle(self.x, self.y + 8, 34, (215, 215, 215), 14, width=2))
        return True

    def try_stealth(self, particles):
        if self.invis_cd > 0.0 or self.invis_timer > 0.0:
            return False
        self.invis_timer = 135.0
        self.invis_cd = self.invis_max_cd * (0.65 if self.has_effect("haste") else 1.0)
        self.scale_vel += 0.14
        play_sound("teleport")
        particles.append(RingParticle(self.x, self.y, 46, (210, 210, 210), 16, width=1))
        for _ in range(4):
            particles.append(AfterimageParticle(self.x, self.y, int(self.get_effective_radius() + 2), (200, 200, 200), 14))
        return True

    def can_place_bomb(self):
        return self.bombs > 0 and self.bomb_cd <= 0.0

    def trigger_bomb_cd(self):
        haste_mult = 0.65 if self.has_effect("haste") else 1.0
        self.bomb_cd = self.bomb_max_cd * haste_mult

    def try_melee(self, aim_x, aim_y, room, enemies, enemy_projectiles, particles, tears=None):
        if self.melee_cd > 0.0:
            return {"hit": False, "enemies_hit": 0, "kills": 0, "deflected": 0, "obstacles_broken": 0, "turrets_broken": 0, "combo": 0}
        dx, dy = (aim_x, aim_y) if (aim_x != 0 or aim_y != 0) else self.facing
        d = math.hypot(dx, dy) or 1.0
        ux, uy = dx / d, dy / d
        self.facing = (ux, uy)
        self.face_angle = math.atan2(uy, ux)

        # 3-hit rhythmic combo: 1 (L->R), 2 (R->L), 3 (Empowered wide cleave finisher)
        if self.melee_combo_timer > 0.0:
            self.melee_combo_step = (self.melee_combo_step % 3) + 1
        else:
            self.melee_combo_step = 1
        self.melee_combo_timer = 52.0
        self.melee_is_finisher = self.melee_combo_step == 3
        self.melee_slash_dir = -1 if self.melee_combo_step == 2 else 1

        haste_mult = 0.65 if self.has_effect("haste") else 1.0
        cd_mult = 1.18 if self.melee_is_finisher else 0.90
        self.melee_cd = self.melee_max_cd * haste_mult * cd_mult
        self.melee_slash_timer = 14.0 if self.melee_is_finisher else 11.0
        self.melee_slash_angle = self.face_angle
        self.melee_slash_arc = 2.45 if self.melee_is_finisher else 1.95
        self.scale_vel += 0.22 if self.melee_is_finisher else 0.16

        # Subtle forward micro-lunge for crisp melee feel (respects room walls)
        lunge = 7.5 if self.melee_is_finisher else 4.5
        pr = self.get_effective_radius()
        self.x = clamp(self.x + ux * lunge, PLAYABLE_LEFT + pr + 2, PLAYABLE_RIGHT - pr - 2)
        self.y = clamp(self.y + uy * lunge, PLAYABLE_TOP + pr + 2, PLAYABLE_BOTTOM - pr - 2)

        play_sound("melee_combo" if self.melee_is_finisher else "melee_swing", min_interval=0.04)

        reach = (88.0 + (14.0 if self.hero_id == "forgotten" else 0.0)) + (18.0 if self.melee_is_finisher else 0.0)
        half_arc = 1.32 if self.melee_is_finisher else 1.10
        is_ambush = self.invis_timer > 0.0
        combo_dmg_mul = 1.38 if self.melee_is_finisher else (1.12 if self.melee_combo_step == 2 else 1.0)
        dmg = self.get_effective_damage() * (1.60 if self.hero_id == "forgotten" else 1.38) * combo_dmg_mul * (self.ambush_mult if is_ambush else 1.0)
        if is_ambush:
            self.invis_timer = min(self.invis_timer, 10.0)

        enemies_hit = 0
        kills = 0
        kb_force = 11.0 if self.melee_is_finisher else 7.8
        if enemies is not None:
            for e in enemies:
                if not getattr(e, "alive", True):
                    continue
                ex = e.x - self.x
                ey = e.y - self.y
                ed = math.hypot(ex, ey)
                if ed > reach + getattr(e, "radius", 14.0):
                    continue
                ang_diff = abs((math.atan2(ey, ex) - self.face_angle + math.pi) % (2.0 * math.pi) - math.pi)
                if ed <= 38.0 or ang_diff <= half_arc:
                    was_alive = getattr(e, "alive", True)
                    e.take_damage(dmg)
                    kx = (ex / (ed or 1.0)) * kb_force
                    ky = (ey / (ed or 1.0)) * kb_force
                    if hasattr(e, "knockback_x"):
                        e.knockback_x += kx
                        e.knockback_y += ky
                    else:
                        e.x += kx * 2.0
                        e.y += ky * 2.0
                    enemies_hit += 1
                    self.melee_hits += 1
                    if was_alive and not getattr(e, "alive", True):
                        kills += 1
                        self.melee_kills += 1
                        self.kills += 1
                    for _ in range(6 if self.melee_is_finisher else 4):
                        pa = self.face_angle + random.uniform(-0.7, 0.7)
                        particles.append(SplashParticle(e.x, e.y, math.cos(pa) * 3.4, math.sin(pa) * 3.4, (248, 248, 248), 3, 15))

        deflected = 0
        if enemy_projectiles is not None:
            for ep in list(enemy_projectiles):
                if not getattr(ep, "alive", True):
                    continue
                px = ep.x - self.x
                py = ep.y - self.y
                pd = math.hypot(px, py)
                if pd > reach + 12.0:
                    continue
                ang_diff = abs((math.atan2(py, px) - self.face_angle + math.pi) % (2.0 * math.pi) - math.pi)
                if pd <= 36.0 or ang_diff <= half_arc + 0.18:
                    ep.alive = False
                    deflected += 1
                    # Reflect deflected projectile back as a high-speed friendly tear!
                    if tears is not None:
                        spd = max(8.5, math.hypot(getattr(ep, "vx", 0.0), getattr(ep, "vy", 0.0)) * 1.45)
                        tears.append(
                            Tear(
                                ep.x,
                                ep.y,
                                ux * spd,
                                uy * spd,
                                damage=max(4.5, self.get_effective_damage() * 1.25),
                                max_range=360.0,
                                radius=7.0,
                                spectral=True,
                                owner_x=self.x,
                                owner_y=self.y,
                            )
                        )
                    particles.append(SplashParticle(ep.x, ep.y, ux * 3.6, uy * 3.6, (254, 254, 254), 3, 14))

        obstacles_broken = 0
        turrets_broken = 0
        obs_dmg = 3 if self.melee_is_finisher else 2
        if room is not None and hasattr(room, "obstacles"):
            for obs in room.obstacles:
                if not getattr(obs, "alive", True):
                    continue
                ox = obs.rect.centerx - self.x
                oy = obs.rect.centery - self.y
                od = math.hypot(ox, oy)
                if od > reach + obs.size * 0.5:
                    continue
                ang_diff = abs((math.atan2(oy, ox) - self.face_angle + math.pi) % (2.0 * math.pi) - math.pi)
                if od <= 42.0 or ang_diff <= half_arc:
                    if hasattr(obs, "damage") and obs.damage(obs_dmg):
                        obstacles_broken += 1
                        if obs.kind == "turret":
                            turrets_broken += 1
                        for _ in range(6):
                            pa = random.uniform(0.0, math.pi * 2.0)
                            particles.append(SplashParticle(obs.rect.centerx, obs.rect.centery, math.cos(pa) * 2.4, math.sin(pa) * 2.4, (210, 210, 210), 3, 16))

        if enemies_hit > 0:
            play_sound("melee_hit", min_interval=0.05)
        if deflected > 0:
            play_sound("melee_deflect", min_interval=0.06)
        if obstacles_broken > 0:
            play_sound("block_break", min_interval=0.06)

        sx = self.x + ux * 40.0
        sy = self.y + uy * 40.0
        particles.append(RingParticle(sx, sy, 56 if self.melee_is_finisher else 42, (248, 248, 248), 12 if self.melee_is_finisher else 10, width=3 if self.melee_is_finisher else 2))
        return {
            "hit": True,
            "enemies_hit": enemies_hit,
            "kills": kills,
            "deflected": deflected,
            "obstacles_broken": obstacles_broken,
            "turrets_broken": turrets_broken,
            "combo": self.melee_combo_step,
            "finisher": self.melee_is_finisher,
        }

    def take_damage(self, amount=1, ignore_invuln=False):
        if not ignore_invuln and (self.has_effect("godmode") or self.has_effect("shield")):
            return False
        if not ignore_invuln and (self.invuln_timer > 0 or self.book_shadows_timer > 0):
            return False
        if not ignore_invuln and self.dodge_chance > 0.0 and random.random() < self.dodge_chance:
            self.invuln_timer = 26.0
            self.scale_vel += 0.18
            return False
        if not ignore_invuln and self.holy_mantle and not self.mantle_broken_room:
            self.mantle_broken_room = True
            self.invuln_timer = 45.0
            self.scale_vel += 0.16
            play_sound("door")
            return False
        if not ignore_invuln and self.has_infamy and random.random() < 0.35:
            self.invuln_timer = 35.0
            return False

        dmg = 1 if self.has_wafer else int(max(1, amount))
        if self.has_bloody_lust:
            self.bloody_lust_stacks += 1

        while dmg > 0:
            if self.black_hp > 0:
                self.black_hp -= 1
            elif self.soul_hp > 0:
                self.soul_hp -= 1
            elif self.hp > 0:
                self.hp -= 1
            dmg -= 1

        self.invuln_timer = 55.0
        self.hurt_flash = 14.0
        self.scale_vel -= 0.24
        play_sound("hurt")

        if self.hp + self.soul_hp + self.black_hp <= 0 and self.has_lazarus_revive:
            self.has_lazarus_revive = False
            self.max_hp = max(2, self.max_hp)
            self.hp = self.max_hp
            self.soul_hp = 2
            self.damage += 1.5
            self.invuln_timer = 90.0
            play_sound("item")
        return True

    def is_dead(self):
        return (self.hp + self.soul_hp + self.black_hp) <= 0

    def _spawn_salvo(self, sx, sy, aim_x, aim_y, tears, scale_dmg=1.0):
        base_ang = math.atan2(aim_y, aim_x)
        count = self.multi_shot
        spread = 0.16 if count <= 3 else 0.14
        half = (count - 1) / 2.0
        is_ambush = self.invis_timer > 0.0
        is_ash_bolt = (self.ash_bolt_every > 0 and self.shots_fired > 0 and (self.shots_fired % self.ash_bolt_every == 0))
        is_crit = (self.crit_chance > 0.0 and random.random() < self.crit_chance)
        dmg = self.get_effective_damage() * scale_dmg * (self.ambush_mult if is_ambush else 1.0)
        if is_ash_bolt:
            dmg *= 1.45
        if is_crit:
            dmg *= 1.75
        rad = 7.0 + min(6.0, max(0.0, (dmg - 3.5) * 0.7))
        if is_ambush or is_ash_bolt or is_crit:
            rad += 2.2
        if self.has_effect("giant"):
            rad *= 1.35
        eff_homing = self.has_homing or self.has_effect("homing")
        eff_spectral = self.has_spectral or self.has_effect("spectral")
        eff_poison = self.has_poison or self.has_effect("poison_touch")
        eff_brim = self.has_brimstone or self.has_effect("brimstone")
        eff_pierce = self.has_piercing or eff_brim or is_ash_bolt
        for i in range(count):
            a = base_ang + (i - half) * spread
            vx = math.cos(a) * self.tear_speed + self.vx * 0.22
            vy = math.sin(a) * self.tear_speed + self.vy * 0.22
            tears.append(
                Tear(
                    sx,
                    sy,
                    vx,
                    vy,
                    damage=dmg,
                    max_range=self.tear_range,
                    radius=rad,
                    color=self.hero["color_tear"],
                    piercing=eff_pierce,
                    bouncing=self.has_bouncing,
                    homing=eff_homing,
                    splitting=self.has_splitting,
                    spectral=eff_spectral,
                    poison=eff_poison,
                    holy=self.has_holy,
                    bone=self.has_bone,
                    brimstone=eff_brim,
                    boomerang=self.has_boomerang,
                    coal=self.has_coal,
                    explosive=self.has_explosive_tears,
                    lobbed=self.has_lobbed_tears,
                    shockwave=self.has_shock_core,
                    vortex=self.has_vortex,
                    chain_arc=self.has_chain_arc,
                    ambush=is_ambush,
                    blast_radius=(74.0 if self.has_shock_core else 58.0),
                    owner_x=sx,
                    owner_y=sy,
                )
            )

    def shoot(self, aim_x, aim_y, tears):
        if self.shoot_cd > 0 or (aim_x == 0 and aim_y == 0):
            return False
        was_ambush = self.invis_timer > 0.0
        self.shoot_cd = self.get_effective_fire_delay()
        self.shoot_anim = 10.0
        self.shots_fired += 1
        self.scale_vel -= 0.09
        d = math.hypot(aim_x, aim_y) or 1.0
        self.facing = (aim_x / d, aim_y / d)
        self.face_angle = math.atan2(self.facing[1], self.facing[0])
        play_sound("shoot")
        if self.hero_id == "lilith":
            ix, iy = self.incubus_pos
            self._spawn_salvo(ix, iy, aim_x, aim_y, tears, 1.0)
            for _ in range(self.room_extra_familiars):
                self._spawn_salvo(ix + 10, iy - 8, aim_x, aim_y, tears, 0.85)
        else:
            self._spawn_salvo(self.x, self.y - 4.0, aim_x, aim_y, tears, 1.0)
            total_inc = self.incubus_count + self.room_extra_familiars
            if total_inc > 0:
                ix, iy = self.incubus_pos
                for inc_i in range(min(4, total_inc)):
                    off_x = (inc_i % 2) * 10 - 5
                    off_y = -(inc_i // 2) * 8
                    self._spawn_salvo(ix + off_x, iy + off_y, aim_x, aim_y, tears, 0.75)
        if was_ambush:
            self.invis_timer = min(self.invis_timer, 10.0)

        wisp_pts = self.get_wisp_positions()
        if wisp_pts:
            ux, uy = aim_x / d, aim_y / d
            wisp_dmg = max(1.5, self.get_effective_damage() * 0.45)
            for wx, wy in wisp_pts[:8]:
                tears.append(
                    Tear(
                        wx,
                        wy,
                        ux * (self.tear_speed * 1.05),
                        uy * (self.tear_speed * 1.05),
                        damage=wisp_dmg,
                        max_range=self.tear_range * 0.78,
                        radius=4.5,
                        color=(250, 250, 250),
                        spectral=True,
                        holy=self.has_holy,
                        owner_x=wx,
                        owner_y=wy,
                    )
                )
        return True

    def update(self, mx, my, room, particles, dt=1.0):
        self.idle_phase += 0.08 * dt
        expired = []
        for eid, rem in self.active_effects.items():
            if rem < 9000000.0:
                nrem = rem - dt
                if nrem <= 0.0:
                    expired.append(eid)
                else:
                    self.active_effects[eid] = nrem
        for eid in expired:
            self.active_effects.pop(eid, None)

        if self.shoot_cd > 0:
            self.shoot_cd = max(0.0, self.shoot_cd - dt)
        if self.shoot_anim > 0:
            self.shoot_anim = max(0.0, self.shoot_anim - dt)
        if self.invuln_timer > 0:
            self.invuln_timer = max(0.0, self.invuln_timer - dt)
        if self.book_shadows_timer > 0:
            self.book_shadows_timer = max(0.0, self.book_shadows_timer - dt)
        if self.hurt_flash > 0:
            self.hurt_flash = max(0.0, self.hurt_flash - dt)
        if self.dash_cd > 0:
            self.dash_cd = max(0.0, self.dash_cd - dt)
        if self.jump_cd > 0:
            self.jump_cd = max(0.0, self.jump_cd - dt)
        if self.bomb_cd > 0:
            self.bomb_cd = max(0.0, self.bomb_cd - dt)
        if self.melee_cd > 0:
            self.melee_cd = max(0.0, self.melee_cd - dt)
        if self.melee_slash_timer > 0:
            self.melee_slash_timer = max(0.0, self.melee_slash_timer - dt)
        if self.melee_combo_timer > 0:
            self.melee_combo_timer = max(0.0, self.melee_combo_timer - dt)
            if self.melee_combo_timer <= 0.0:
                self.melee_combo_step = 0
        if self.invis_timer > 0:
            self.invis_timer = max(0.0, self.invis_timer - dt)
        if self.invis_cd > 0:
            self.invis_cd = max(0.0, self.invis_cd - dt)

        just_landed = False
        land_empowered = False
        if self.air_z > 0.0 or self.air_vz > 0.0:
            self.air_z += self.air_vz * dt
            self.air_vz -= 0.42 * dt
            if self.air_z <= 0.0:
                self.air_z = 0.0
                self.air_vz = 0.0
                just_landed = True
                land_empowered = self.jump_empowered
                self.jump_empowered = False

        self.orbital_angle += 0.075 * dt
        self.wisp_angle += 0.055 * dt
        self.scale_x, self.scale_vel = spring_step(self.scale_x, self.scale_vel, 1.0, 0.22, 0.72, dt)
        self.scale_x = clamp(self.scale_x, 0.78, 1.24)
        self.scale_y = 2.0 - self.scale_x

        if self.dash_timer > 0:
            self.dash_timer = max(0.0, self.dash_timer - dt)
            self.vx = self.dash_vx
            self.vy = self.dash_vy
            if int(self.dash_timer) % 2 == 0:
                particles.append(AfterimageParticle(self.x, self.y, int(self.get_effective_radius() + 2), (225, 225, 225), 11))
        else:
            d = math.hypot(mx, my)
            spd = self.get_effective_speed()
            if d > 0.01:
                ux, uy = mx / d, my / d
                target_ang = math.atan2(uy, ux)
                self.face_angle = angle_slerp(self.face_angle, target_ang, 0.26 * dt)
                self.facing = (math.cos(self.face_angle), math.sin(self.face_angle))
                self.vx += (ux * spd - self.vx) * clamp(0.32 * dt, 0.0, 1.0)
                self.vy += (uy * spd - self.vy) * clamp(0.32 * dt, 0.0, 1.0)
                self.walk_phase += 0.26 * dt
            else:
                self.vx *= 0.72 ** dt
                self.vy *= 0.72 ** dt

        self.x += self.vx * dt
        self.y += self.vy * dt

        r = self.get_effective_radius()
        self.x = max(PLAYABLE_LEFT + r, min(PLAYABLE_RIGHT - r, self.x))
        self.y = max(PLAYABLE_TOP + r, min(PLAYABLE_BOTTOM - r, self.y))

        if not self.has_effective_flight() and self.air_z <= 8.0 and room is not None:
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

        if just_landed:
            self.scale_vel -= 0.24
            slam_rad = 112.0 if land_empowered else (96.0 if self.has_seismic_boots else 74.0)
            slam_dmg = max(5.0, self.get_effective_damage() * (2.35 if land_empowered else (1.75 if self.has_seismic_boots else 1.15)))
            self.jump_slam_pending = {
                "x": self.x,
                "y": self.y,
                "radius": slam_rad,
                "damage": slam_dmg,
                "explosive": bool(land_empowered or self.has_seismic_boots or self.has_explosive_tears),
            }
            particles.append(RingParticle(self.x, self.y + 6, int(slam_rad), (242, 242, 242), 20, width=2))

        prev = (self.x - self.facing[0] * 5.0, self.y + 4.0)
        new_nodes = []
        for idx, (nx, ny) in enumerate(self.cloak_nodes):
            sway = math.sin(self.walk_phase * 0.8 + self.idle_phase * 0.7 + idx * 0.65) * 0.6
            tx = nx + (prev[0] - nx) * clamp(0.35 * dt, 0.0, 1.0) + sway
            ty = ny + (prev[1] + 2.8 - ny) * clamp(0.35 * dt, 0.0, 1.0)
            dx_n, dy_n = tx - prev[0], ty - prev[1]
            nd = math.hypot(dx_n, dy_n) or 1.0
            if nd > 6.2:
                tx = prev[0] + (dx_n / nd) * 6.2
                ty = prev[1] + (dy_n / nd) * 6.2
            new_nodes.append((tx, ty))
            prev = (tx, ty)
        self.cloak_nodes = new_nodes

        target_ix = self.x - self.facing[0] * 32.0
        target_iy = self.y - self.facing[1] * 32.0 + 6.0
        ix, iy = self.incubus_pos
        self.incubus_pos = (ix + (target_ix - ix) * 0.14 * dt, iy + (target_iy - iy) * 0.14 * dt)

    def get_orbital_positions(self):
        pts = []
        total = self.orbitals + self.room_extra_orbitals
        for i in range(total):
            a = self.orbital_angle + i * (2.0 * math.pi / max(1, total))
            pts.append((self.x + math.cos(a) * 44.0, self.y + math.sin(a) * 44.0))
        return pts

    def get_wisp_positions(self):
        pts = []
        total = self.wisps + self.room_extra_wisps
        for i in range(total):
            a = self.wisp_angle + i * (2.0 * math.pi / max(1, total))
            pts.append((self.x + math.cos(a) * 56.0, self.y + math.sin(a) * 56.0))
        return pts

    def draw(self, screen, light_sources=None):
        blink = (
            self.invuln_timer > 0
            and int(self.invuln_timer) % 4 < 2
            and self.book_shadows_timer <= 0
            and not getattr(self, "preview_mode", False)
        )
        draw_dynamic_shadow(
            screen,
            self.x,
            self.y + 15,
            38,
            13,
            light_sources=light_sources,
            air_z=self.air_z,
            alpha=88 if self.air_z > 4.0 else 132,
        )
        if self.melee_slash_timer > 0:
            max_t = 14.0 if self.melee_is_finisher else 11.0
            frac = clamp(self.melee_slash_timer / max_t, 0.0, 1.0)
            arc_span = self.melee_slash_arc if self.melee_slash_arc > 0 else 1.95
            half_a = arc_span * 0.5
            r_base = 86.0 if self.melee_is_finisher else 74.0
            r_out = r_base * (1.08 - 0.14 * frac)
            r_in = 30.0 if self.melee_is_finisher else 34.0
            steps = 11
            sdir = self.melee_slash_dir
            arc_pts_out = []
            arc_pts_in = []
            for si in range(steps):
                u = si / float(max(1, steps - 1))  # 0..1 along sweep
                t = (-half_a + arc_span * u) * sdir
                ang = self.melee_slash_angle + t
                arc_pts_out.append((self.x + math.cos(ang) * r_out, self.y - self.air_z + math.sin(ang) * r_out))
            for si in range(steps - 1, -1, -1):
                u = si / float(max(1, steps - 1))
                t = (-half_a + arc_span * u) * sdir
                ang = self.melee_slash_angle + t
                # Tapered blade: thickest near leading edge (u -> 1)
                taper = (0.20 + 0.80 * (u ** 0.7)) * (1.0 - abs(u - 0.62) * 0.55)
                ri = r_out - (r_out - r_in) * max(0.16, taper) * frac
                arc_pts_in.append((self.x + math.cos(ang) * ri, self.y - self.air_z + math.sin(ang) * ri))
            crescent = arc_pts_out + arc_pts_in
            if len(crescent) >= 4:
                lum = int(178 + 76 * frac)
                draw_aa_poly(screen, (lum, lum, lum), crescent)
                pygame.draw.lines(screen, (254, 254, 254), False, [(int(px), int(py)) for px, py in arc_pts_out], 3 if self.melee_is_finisher else 2)
                if self.melee_is_finisher:
                    outer_r = r_out + 10.0 * (1.0 - frac)
                    outer_pts = [
                        (int(self.x + math.cos(self.melee_slash_angle + (-half_a + arc_span * (si / 10.0)) * sdir) * outer_r),
                         int(self.y - self.air_z + math.sin(self.melee_slash_angle + (-half_a + arc_span * (si / 10.0)) * sdir) * outer_r))
                        for si in range(11)
                    ]
                    pygame.draw.lines(screen, (220, 220, 220), False, outer_pts, 1)
        if self.player_tag == "P1":
            draw_aa_ring(screen, (218, 218, 218), self.x, self.y + 14, 19, 1)
        elif self.player_tag == "P2":
            draw_aa_ring(screen, (244, 244, 244), self.x, self.y + 14, 21, 1)
            draw_aa_ring(screen, (118, 118, 118), self.x, self.y + 14, 17, 1)
        if self.air_z > 2.0:
            draw_aa_ring(screen, (212, 212, 212), self.x, self.y + 14, max(8, int(18 - self.air_z * 0.14)), 1)

        if (
            self.book_shadows_timer > 0
            or (self.holy_mantle and not self.mantle_broken_room)
            or self.has_effect("godmode")
            or self.has_effect("shield")
        ):
            gl = get_glow_surf(42, 248, 92)
            screen.blit(gl, (int(self.x - gl.get_width() * 0.5), int(self.y - 4 - self.air_z - gl.get_height() * 0.5)))
            draw_aa_ring(screen, (248, 248, 248), self.x, self.y - 4 - self.air_z, 29, 2)

        if self.has_effect("rage"):
            draw_aa_ring(screen, (232, 232, 232), self.x, self.y - 4 - self.air_z, 24, 1)
        if self.has_effect("magnet"):
            draw_aa_ring(screen, (168, 168, 168), self.x, self.y - self.air_z, 34 + int(math.sin(self.idle_phase * 2.0) * 3), 1)

        if self.invis_timer > 0:
            pulse_r = 21 + int(math.sin(self.idle_phase * 2.5) * 2)
            draw_aa_ring(screen, (176, 176, 176), self.x, self.y - 4 - self.air_z, pulse_r, 1)

        body_lum = gray(self.hero["color_body"])[0]
        cloak_lum = gray(self.hero["color_cloak"])[0]
        acc_lum = gray(self.hero["color_accent"])[0]
        if self.invis_timer > 0:
            body_lum = max(36, int(body_lum * 0.42))
            cloak_lum = max(24, int(cloak_lum * 0.42))
            acc_lum = max(48, int(acc_lum * 0.50))
        if self.hurt_flash > 0:
            body_lum = cloak_lum = 250

        gscale = 1.28 if self.has_effect("giant") else 1.0
        moving = abs(self.vx) + abs(self.vy) > 0.35
        hover = -5.0 + math.sin(self.walk_phase + self.idle_phase) * 2.4 if self.has_effective_flight() else math.sin(self.idle_phase) * 0.8
        step = math.sin(self.walk_phase * 2.0) * 3.0 if moving else 0.0
        sway_x = math.sin(self.walk_phase) * 2.0 if moving else 0.0
        recoil = (self.shoot_anim / 10.0) * 2.2
        dy = self.y + hover - self.air_z

        if not blink:
            left_pts = []
            right_pts = []
            for idx, (cx, cy) in enumerate(self.cloak_nodes):
                half_w = max(2.5, (11.5 - idx * 1.45) * gscale)
                left_pts.append((cx - half_w, cy + hover + 2 - self.air_z))
                right_pts.append((cx + half_w, cy + hover + 2 - self.air_z))
            ribbon = left_pts + list(reversed(right_pts))
            if len(ribbon) >= 4:
                draw_aa_poly(screen, (14, 14, 14), ribbon)
                inner_left = [(px + 2.0, py) for px, py in left_pts[:-1]]
                inner_right = [(px - 2.0, py) for px, py in right_pts[:-1]]
                if len(inner_left) >= 2:
                    c_in = max(24, cloak_lum - 16)
                    draw_aa_poly(screen, (c_in, c_in, c_in), inner_left + list(reversed(inner_right)))
                    c_hi = min(244, cloak_lum + 18)
                    pygame.draw.line(screen, (c_hi, c_hi, c_hi), (int(inner_left[0][0] + 1), int(inner_left[0][1])), (int(inner_left[-1][0] + 1), int(inner_left[-1][1])), 1)

            if self.hero_id in ("azazel", "lilith") or self.has_effect("flight"):
                flap = math.sin(self.walk_phase * 1.8 + self.idle_phase) * 3.0
                for s in (-1, 1):
                    wing = [(self.x, dy - 2), (self.x + s * 28, dy - 12 - flap), (self.x + s * 21, dy + 10)]
                    draw_aa_poly(screen, (14, 14, 14), wing)
                    wing_in = [(self.x, dy - 2), (self.x + s * 23, dy - 9 - flap), (self.x + s * 17, dy + 7)]
                    draw_aa_poly(screen, (52, 52, 52), wing_in)
            elif self.hero_id == "seraph":
                flap = math.sin(self.walk_phase * 1.8 + self.idle_phase) * 3.2
                for s in (-1, 1):
                    wing = [(self.x, dy - 2), (self.x + s * 30, dy - 14 - flap), (self.x + s * 22, dy + 10)]
                    draw_aa_poly(screen, (20, 20, 20), wing)
                    wing_in = [(self.x, dy - 2), (self.x + s * 25, dy - 10 - flap), (self.x + s * 18, dy + 7)]
                    draw_aa_poly(screen, (242, 242, 242), wing_in)
            elif self.hero_id == "lost":
                draw_aa_poly(screen, (186, 186, 186), [(self.x - 13, dy + 2), (self.x + 13, dy + 2), (self.x, dy + 26 + math.sin(self.idle_phase) * 2)])

            tw = max(18, int(round(23 * self.scale_x * gscale)))
            th = max(13, int(round(16 * self.scale_y * gscale)))
            torso_rect = pygame.Rect(int(self.x - tw * 0.5 + sway_x), int(dy - 1), tw, th)
            pygame.draw.rect(screen, (14, 14, 14), torso_rect.inflate(4, 4), border_radius=7)
            pygame.draw.rect(screen, (cloak_lum, cloak_lum, cloak_lum), torso_rect, border_radius=6)
            t_hi = min(248, cloak_lum + 42)
            t_sh = max(18, cloak_lum - 26)
            pygame.draw.line(screen, (t_hi, t_hi, t_hi), (torso_rect.left + 4, torso_rect.top + 2), (torso_rect.right - 4, torso_rect.top + 2), 1)
            pygame.draw.line(screen, (t_sh, t_sh, t_sh), (torso_rect.left + 2, torso_rect.bottom - 4), (torso_rect.right - 2, torso_rect.bottom - 4), 2)
            pygame.draw.rect(screen, (min(242, acc_lum + 20), min(242, acc_lum + 20), min(242, acc_lum + 20)), (torso_rect.centerx - 2, torso_rect.bottom - 5, 4, 3), border_radius=1)
            if not self.has_effective_flight():
                draw_aa_ellipse(screen, (14, 14, 14), self.x - 5.5, dy + 15.5 + step, 4.4, 3.6)
                draw_aa_ellipse(screen, (14, 14, 14), self.x + 5.5, dy + 15.5 - step, 4.4, 3.6)
                draw_aa_ellipse(screen, (158, 158, 158), self.x - 5.5, dy + 14.8 + step, 2.8, 2.0)
                draw_aa_ellipse(screen, (158, 158, 158), self.x + 5.5, dy + 14.8 - step, 2.8, 2.0)

            hand_swing = math.sin(self.walk_phase * 2.0) * 3.5 if moving else math.sin(self.idle_phase) * 1.2
            h_hi = min(252, body_lum + 22)
            draw_aa_circle(screen, (18, 18, 18), self.x - 14 * gscale + sway_x, dy + 6 - hand_swing, 4.2)
            draw_aa_circle(screen, (body_lum, body_lum, body_lum), self.x - 14 * gscale + sway_x, dy + 6 - hand_swing, 2.9)
            draw_aa_circle(screen, (h_hi, h_hi, h_hi), self.x - 14.5 * gscale + sway_x, dy + 5.2 - hand_swing, 1.3)
            draw_aa_circle(screen, (18, 18, 18), self.x + 14 * gscale + sway_x, dy + 6 + hand_swing, 4.2)
            draw_aa_circle(screen, (body_lum, body_lum, body_lum), self.x + 14 * gscale + sway_x, dy + 6 + hand_swing, 2.9)
            draw_aa_circle(screen, (h_hi, h_hi, h_hi), self.x + 13.5 * gscale + sway_x, dy + 5.2 + hand_swing, 1.3)

            if self.hero_id == "forgotten":
                pygame.draw.line(screen, (242, 242, 242), (int(self.x + 14), int(dy + 6 + hand_swing)), (int(self.x + 25), int(dy - 12)), 4)
                draw_aa_circle(screen, (246, 246, 246), self.x + 25, dy - 13, 4.5)

            head_r = max(13, int(round(16.5 * (0.55 + 0.45 * self.scale_x) * gscale)))
            head_cx = self.x + sway_x * 0.5 - self.facing[0] * recoil
            head_cy = dy - 12 * gscale - self.facing[1] * recoil
            head = get_disc_sprite(head_r, body_lum, outline_lum=14, hi_lum=254)
            screen.blit(head, (int(round(head_cx - head.get_width() * 0.5)), int(round(head_cy - head.get_height() * 0.5))))

            eye_y = head_cy + self.facing[1] * 2.8
            eye_x_off = self.facing[0] * 2.8
            eye_col = (250, 250, 250) if body_lum < 120 or self.dash_timer > 0 else (16, 16, 16)
            if self.hero_id == "cain":
                draw_aa_circle(screen, eye_col, head_cx - 5.2 + eye_x_off, eye_y, 3.4)
                draw_aa_circle(screen, (248, 248, 248) if eye_col[0] < 100 else (24, 24, 24), head_cx - 5.6 + eye_x_off, eye_y - 0.8, 1.2)
                pygame.draw.line(screen, (14, 14, 14), (int(head_cx + 1), int(eye_y - 4)), (int(head_cx + 10), int(eye_y + 3)), 4)
            elif self.hero_id == "lilith":
                pygame.draw.rect(screen, (16, 16, 16), (int(head_cx - 12 + eye_x_off * 0.5), int(eye_y - 4), 24, 7), border_radius=3)
            elif self.hero_id == "warden":
                pygame.draw.rect(screen, (16, 16, 16), (int(head_cx - 11 + eye_x_off * 0.4), int(eye_y - 3), 22, 6), border_radius=2)
                pygame.draw.line(screen, (244, 244, 244), (int(head_cx - 7 + eye_x_off * 0.4), int(eye_y)), (int(head_cx + 7 + eye_x_off * 0.4), int(eye_y)), 2)
            elif self.hero_id == "keeper":
                for sx_o in (-5.5, 5.5):
                    pygame.draw.line(screen, (16, 16, 16), (int(head_cx + sx_o - 2.5 + eye_x_off), int(eye_y - 2.5)), (int(head_cx + sx_o + 2.5 + eye_x_off), int(eye_y + 2.5)), 2)
                    pygame.draw.line(screen, (16, 16, 16), (int(head_cx + sx_o + 2.5 + eye_x_off), int(eye_y - 2.5)), (int(head_cx + sx_o - 2.5 + eye_x_off), int(eye_y + 2.5)), 2)
            else:
                draw_aa_circle(screen, eye_col, head_cx - 5.5 + eye_x_off, eye_y, 3.4)
                draw_aa_circle(screen, eye_col, head_cx + 5.5 + eye_x_off, eye_y, 3.4)
                glint = (250, 250, 250) if eye_col[0] < 100 else (16, 16, 16)
                draw_aa_circle(screen, glint, head_cx - 6.0 + eye_x_off, eye_y - 0.8, 1.2)
                draw_aa_circle(screen, glint, head_cx + 5.0 + eye_x_off, eye_y - 0.8, 1.2)
                tear_col = (244, 244, 244) if body_lum < 120 else (178, 178, 178)
                pygame.draw.line(screen, tear_col, (int(head_cx - 5.5 + eye_x_off), int(eye_y + 3)), (int(head_cx - 5.5 + eye_x_off), int(eye_y + 9)), 2)
                pygame.draw.line(screen, tear_col, (int(head_cx + 5.5 + eye_x_off), int(eye_y + 3)), (int(head_cx + 5.5 + eye_x_off), int(eye_y + 9)), 2)

            if self.hero_id in ("azazel", "lilith"):
                for s in (-1, 1):
                    draw_aa_poly(screen, (16, 16, 16), [(head_cx + s * 7, head_cy - 12), (head_cx + s * 16, head_cy - 23), (head_cx + s * 12, head_cy - 8)])
                    draw_aa_poly(screen, (acc_lum, acc_lum, acc_lum), [(head_cx + s * 8, head_cy - 12), (head_cx + s * 14, head_cy - 20), (head_cx + s * 10, head_cy - 9)])
            elif self.hero_id == "judas":
                pygame.draw.rect(screen, (14, 14, 14), (int(head_cx - 9), int(head_cy - 22), 18, 11), border_radius=2)
                pygame.draw.rect(screen, (96, 96, 96), (int(head_cx - 7), int(head_cy - 20), 14, 7), border_radius=2)
            elif self.hero_id in ("lost", "bethany", "lazarus", "seraph"):
                draw_aa_ellipse(screen, (248, 248, 248), head_cx, head_cy - 21, 12, 4.2)
                draw_aa_ellipse(screen, (18, 18, 18), head_cx, head_cy - 21, 6.5, 2.0)
            elif self.hero_id == "eden":
                draw_aa_poly(screen, (244, 244, 244), [(head_cx - 11, head_cy - 12), (head_cx - 5, head_cy - 22), (head_cx, head_cy - 14), (head_cx + 6, head_cy - 23), (head_cx + 11, head_cy - 12)])
            elif self.hero_id == "magdalene":
                draw_aa_circle(screen, (242, 242, 242), head_cx - 13, head_cy - 6, 4.5)
                draw_aa_circle(screen, (242, 242, 242), head_cx + 13, head_cy - 6, 4.5)
            elif self.hero_id == "samson":
                pygame.draw.rect(screen, (238, 238, 238), (int(head_cx - 14), int(head_cy - 11), 28, 4), border_radius=2)
            elif self.hero_id == "nocturne":
                draw_aa_poly(screen, (244, 244, 244), [(head_cx - 10, head_cy - 12), (head_cx, head_cy - 25), (head_cx + 10, head_cy - 12), (head_cx, head_cy - 16)])
            elif self.hero_id == "chrono":
                draw_aa_ring(screen, (242, 242, 242), head_cx + 5.5 + eye_x_off, eye_y, 5.2, 1)
                pygame.draw.line(screen, (242, 242, 242), (int(head_cx), int(head_cy - 16)), (int(head_cx), int(head_cy - 24)), 2)
            elif self.hero_id == "alchemist":
                draw_aa_ring(screen, (240, 240, 240), head_cx - 5.5 + eye_x_off, eye_y, 4.8, 1)
                draw_aa_ring(screen, (240, 240, 240), head_cx + 5.5 + eye_x_off, eye_y, 4.8, 1)

        if self.hero_id == "lilith" or self.incubus_count > 0:
            ix, iy = self.incubus_pos
            inc = get_disc_sprite(10, 56, outline_lum=14, hi_lum=218)
            screen.blit(inc, (int(round(ix - inc.get_width() * 0.5)), int(round(iy - inc.get_height() * 0.5))))
            draw_aa_circle(screen, (246, 246, 246), ix - 3.2, iy - 1, 2.0)
            draw_aa_circle(screen, (246, 246, 246), ix + 3.2, iy - 1, 2.0)

        orb_pts = self.get_orbital_positions()
        if orb_pts:
            orb_spr = _get_orb_sprite("orbital")
            ohw = orb_spr.get_width() * 0.5
            ohh = orb_spr.get_height() * 0.5
            for ox, oy in orb_pts:
                screen.blit(orb_spr, (int(round(ox - ohw)), int(round(oy - ohh))))

        wisp_pts = self.get_wisp_positions()
        if wisp_pts:
            gl = get_glow_surf(18, 248, 86)
            ghw = gl.get_width() * 0.5
            ghh = gl.get_height() * 0.5
            wisp_spr = _get_orb_sprite("wisp")
            whw = wisp_spr.get_width() * 0.5
            whh = wisp_spr.get_height() * 0.5
            for wx, wy in wisp_pts:
                screen.blit(gl, (int(wx - ghw), int(wy - ghh)))
                screen.blit(wisp_spr, (int(round(wx - whw)), int(round(wy - whh))))

        for ally in self.allies:
            ally.draw(screen)

        if self.player_tag in ("P1", "P2") and not getattr(self, "preview_mode", False):
            tag_surf = _get_player_tag_surf(self.player_tag)
            screen.blit(tag_surf, (int(round(self.x - tag_surf.get_width() * 0.5)), int(round(dy - 46 * gscale))))


def draw_network_hero_character(
    screen,
    hero_id,
    x,
    y,
    air_z=0.0,
    facing=(0.0, 1.0),
    is_moving=False,
    player_tag="P1",
    invis=False,
    hurt_flash=0.0,
    melee_anim=0.0,
    melee_ang=0.0,
    time_acc=0.0,
    light_sources=None,
    walk_phase=None,
    idle_phase=None,
    cloak_nodes=None,
    shield_active=False,
    invuln=0.0,
):
    hero = get_hero(hero_id)
    fx, fy = (facing[0], facing[1]) if facing and (facing[0] != 0 or facing[1] != 0) else (0.0, 1.0)
    mag = math.hypot(fx, fy) or 1.0
    fx, fy = fx / mag, fy / mag
    # Match Player.update phase accumulation rates (0.26*dt walk, 0.08*dt idle)
    w_phase = float(walk_phase) if walk_phase is not None else (time_acc * 0.26 if is_moving else 0.0)
    i_phase = float(idle_phase) if idle_phase is not None else (time_acc * 0.08)

    draw_dynamic_shadow(
        screen,
        x,
        y + 15,
        38,
        13,
        light_sources=light_sources,
        air_z=air_z,
        alpha=88 if air_z > 4.0 else 132,
    )

    if melee_anim > 0.0:
        frac = clamp(melee_anim / 11.0, 0.0, 1.0)
        arc_pts_out = []
        arc_pts_in = []
        r_out = 72.0 * (1.06 - 0.14 * frac)
        r_in = 34.0
        steps = 9
        for si in range(steps):
            t = -0.95 + (1.90 * si / max(1, steps - 1))
            ang = melee_ang + t
            arc_pts_out.append((x + math.cos(ang) * r_out, y - air_z + math.sin(ang) * r_out))
        for si in range(steps - 1, -1, -1):
            t = -0.95 + (1.90 * si / max(1, steps - 1))
            ang = melee_ang + t
            mid_fade = 1.0 - abs(t) / 1.1
            ri = r_out - (r_out - r_in) * max(0.18, mid_fade) * frac
            arc_pts_in.append((x + math.cos(ang) * ri, y - air_z + math.sin(ang) * ri))
        crescent = arc_pts_out + arc_pts_in
        if len(crescent) >= 4:
            lum = int(170 + 82 * frac)
            draw_aa_poly(screen, (lum, lum, lum), crescent)
            pygame.draw.lines(screen, (252, 252, 252), False, [(int(px), int(py)) for px, py in arc_pts_out], 2)

    if player_tag == "P1":
        draw_aa_ring(screen, (218, 218, 218), x, y + 14, 19, 1)
    elif player_tag == "P2":
        draw_aa_ring(screen, (244, 244, 244), x, y + 14, 21, 1)
        draw_aa_ring(screen, (118, 118, 118), x, y + 14, 17, 1)
    if air_z > 2.0:
        draw_aa_ring(screen, (212, 212, 212), x, y + 14, max(8, int(18 - air_z * 0.14)), 1)

    if shield_active:
        gl = get_glow_surf(42, 248, 92)
        screen.blit(gl, (int(x - gl.get_width() * 0.5), int(y - 4 - air_z - gl.get_height() * 0.5)))
        draw_aa_ring(screen, (248, 248, 248), x, y - 4 - air_z, 29, 2)

    if invis:
        pulse_r = 21 + int(math.sin(i_phase * 2.5) * 2)
        draw_aa_ring(screen, (176, 176, 176), x, y - 4 - air_z, pulse_r, 1)

    blink = invuln > 0.0 and int(invuln / 4.0) % 2 == 0 and hurt_flash <= 0.0

    body_lum = gray(hero["color_body"])[0]
    cloak_lum = gray(hero["color_cloak"])[0]
    acc_lum = gray(hero["color_accent"])[0]
    if invis:
        body_lum = max(36, int(body_lum * 0.42))
        cloak_lum = max(24, int(cloak_lum * 0.42))
        acc_lum = max(48, int(acc_lum * 0.50))
    if hurt_flash > 0:
        body_lum = cloak_lum = 250

    moving = bool(is_moving)
    has_flight = hero_id in ("lost", "azazel", "seraph")
    hover = -5.0 + math.sin(w_phase + i_phase) * 2.4 if has_flight else math.sin(i_phase) * 0.8
    step = math.sin(w_phase * 2.0) * 3.0 if moving else 0.0
    sway_x = math.sin(w_phase) * 2.0 if moving else 0.0
    dy = y + hover - air_z

    if not blink:
        if cloak_nodes and len(cloak_nodes) >= 2:
            left_pts = []
            right_pts = []
            for idx, (cx, cy) in enumerate(cloak_nodes):
                half_w = max(2.5, 11.5 - idx * 1.45)
                left_pts.append((cx - half_w, cy + hover + 2 - air_z))
                right_pts.append((cx + half_w, cy + hover + 2 - air_z))
            ribbon = left_pts + list(reversed(right_pts))
            if len(ribbon) >= 4:
                draw_aa_poly(screen, (14, 14, 14), ribbon)
                inner_left = [(px + 2.0, py) for px, py in left_pts[:-1]]
                inner_right = [(px - 2.0, py) for px, py in right_pts[:-1]]
                if len(inner_left) >= 2:
                    c_in = max(24, cloak_lum - 16)
                    draw_aa_poly(screen, (c_in, c_in, c_in), inner_left + list(reversed(inner_right)))
                    c_hi = min(244, cloak_lum + 18)
                    pygame.draw.line(screen, (c_hi, c_hi, c_hi), (int(inner_left[0][0] + 1), int(inner_left[0][1])), (int(inner_left[-1][0] + 1), int(inner_left[-1][1])), 1)

        if hero_id in ("azazel", "lilith"):
            flap = math.sin(w_phase * 1.8 + i_phase) * 3.0
            for s in (-1, 1):
                wing = [(x, dy - 2), (x + s * 28, dy - 12 - flap), (x + s * 21, dy + 10)]
                draw_aa_poly(screen, (14, 14, 14), wing)
                wing_in = [(x, dy - 2), (x + s * 23, dy - 9 - flap), (x + s * 17, dy + 7)]
                draw_aa_poly(screen, (52, 52, 52), wing_in)
        elif hero_id == "seraph":
            flap = math.sin(w_phase * 1.8 + i_phase) * 3.2
            for s in (-1, 1):
                wing = [(x, dy - 2), (x + s * 30, dy - 14 - flap), (x + s * 22, dy + 10)]
                draw_aa_poly(screen, (20, 20, 20), wing)
                wing_in = [(x, dy - 2), (x + s * 25, dy - 10 - flap), (x + s * 18, dy + 7)]
                draw_aa_poly(screen, (242, 242, 242), wing_in)
        elif hero_id == "lost":
            draw_aa_poly(screen, (186, 186, 186), [(x - 13, dy + 2), (x + 13, dy + 2), (x, dy + 26 + math.sin(i_phase) * 2)])

        tw, th = 23, 16
        torso_rect = pygame.Rect(int(x - tw * 0.5 + sway_x), int(dy - 1), tw, th)
        pygame.draw.rect(screen, (14, 14, 14), torso_rect.inflate(4, 4), border_radius=7)
        pygame.draw.rect(screen, (cloak_lum, cloak_lum, cloak_lum), torso_rect, border_radius=6)
        t_hi = min(248, cloak_lum + 42)
        t_sh = max(18, cloak_lum - 26)
        pygame.draw.line(screen, (t_hi, t_hi, t_hi), (torso_rect.left + 4, torso_rect.top + 2), (torso_rect.right - 4, torso_rect.top + 2), 1)
        pygame.draw.line(screen, (t_sh, t_sh, t_sh), (torso_rect.left + 2, torso_rect.bottom - 4), (torso_rect.right - 2, torso_rect.bottom - 4), 2)
        pygame.draw.rect(screen, (min(242, acc_lum + 20), min(242, acc_lum + 20), min(242, acc_lum + 20)), (torso_rect.centerx - 2, torso_rect.bottom - 5, 4, 3), border_radius=1)

        if not has_flight:
            draw_aa_ellipse(screen, (14, 14, 14), x - 5.5, dy + 15.5 + step, 4.4, 3.6)
            draw_aa_ellipse(screen, (14, 14, 14), x + 5.5, dy + 15.5 - step, 4.4, 3.6)
            draw_aa_ellipse(screen, (158, 158, 158), x - 5.5, dy + 14.8 + step, 2.8, 2.0)
            draw_aa_ellipse(screen, (158, 158, 158), x + 5.5, dy + 14.8 - step, 2.8, 2.0)

        hand_swing = math.sin(w_phase * 2.0) * 3.5 if moving else math.sin(i_phase) * 1.2
        draw_aa_circle(screen, (18, 18, 18), x - 14 + sway_x, dy + 6 - hand_swing, 4.2)
        draw_aa_circle(screen, (body_lum, body_lum, body_lum), x - 14 + sway_x, dy + 6 - hand_swing, 2.9)
        draw_aa_circle(screen, (18, 18, 18), x + 14 + sway_x, dy + 6 + hand_swing, 4.2)
        draw_aa_circle(screen, (body_lum, body_lum, body_lum), x + 14 + sway_x, dy + 6 + hand_swing, 2.9)

        if hero_id == "forgotten":
            pygame.draw.line(screen, (242, 242, 242), (int(x + 14), int(dy + 6 + hand_swing)), (int(x + 25), int(dy - 12)), 4)
            draw_aa_circle(screen, (246, 246, 246), x + 25, dy - 13, 4.5)

        head_r = 16
        head_cx = x + sway_x * 0.5
        head_cy = dy - 12
        head = get_disc_sprite(head_r, body_lum, outline_lum=14, hi_lum=254)
        screen.blit(head, (int(round(head_cx - head.get_width() * 0.5)), int(round(head_cy - head.get_height() * 0.5))))

        eye_y = head_cy + fy * 2.8
        eye_x_off = fx * 2.8
        eye_col = (250, 250, 250) if body_lum < 120 else (16, 16, 16)
        if hero_id == "cain":
            draw_aa_circle(screen, eye_col, head_cx - 5.2 + eye_x_off, eye_y, 3.4)
            draw_aa_circle(screen, (248, 248, 248) if eye_col[0] < 100 else (24, 24, 24), head_cx - 5.6 + eye_x_off, eye_y - 0.8, 1.2)
            pygame.draw.line(screen, (14, 14, 14), (int(head_cx + 1), int(eye_y - 4)), (int(head_cx + 10), int(eye_y + 3)), 4)
        elif hero_id == "lilith":
            pygame.draw.rect(screen, (16, 16, 16), (int(head_cx - 12 + eye_x_off * 0.5), int(eye_y - 4), 24, 7), border_radius=3)
        elif hero_id == "warden":
            pygame.draw.rect(screen, (16, 16, 16), (int(head_cx - 11 + eye_x_off * 0.4), int(eye_y - 3), 22, 6), border_radius=2)
            pygame.draw.line(screen, (244, 244, 244), (int(head_cx - 7 + eye_x_off * 0.4), int(eye_y)), (int(head_cx + 7 + eye_x_off * 0.4), int(eye_y)), 2)
        elif hero_id == "keeper":
            for sx_o in (-5.5, 5.5):
                pygame.draw.line(screen, (16, 16, 16), (int(head_cx + sx_o - 2.5 + eye_x_off), int(eye_y - 2.5)), (int(head_cx + sx_o + 2.5 + eye_x_off), int(eye_y + 2.5)), 2)
                pygame.draw.line(screen, (16, 16, 16), (int(head_cx + sx_o + 2.5 + eye_x_off), int(eye_y - 2.5)), (int(head_cx + sx_o - 2.5 + eye_x_off), int(eye_y + 2.5)), 2)
        else:
            draw_aa_circle(screen, eye_col, head_cx - 5.5 + eye_x_off, eye_y, 3.4)
            draw_aa_circle(screen, eye_col, head_cx + 5.5 + eye_x_off, eye_y, 3.4)
            glint = (250, 250, 250) if eye_col[0] < 100 else (16, 16, 16)
            draw_aa_circle(screen, glint, head_cx - 6.0 + eye_x_off, eye_y - 0.8, 1.2)
            draw_aa_circle(screen, glint, head_cx + 5.0 + eye_x_off, eye_y - 0.8, 1.2)
            tear_col = (244, 244, 244) if body_lum < 120 else (178, 178, 178)
            pygame.draw.line(screen, tear_col, (int(head_cx - 5.5 + eye_x_off), int(eye_y + 3)), (int(head_cx - 5.5 + eye_x_off), int(eye_y + 9)), 2)
            pygame.draw.line(screen, tear_col, (int(head_cx + 5.5 + eye_x_off), int(eye_y + 3)), (int(head_cx + 5.5 + eye_x_off), int(eye_y + 9)), 2)

        if hero_id in ("azazel", "lilith"):
            for s in (-1, 1):
                draw_aa_poly(screen, (16, 16, 16), [(head_cx + s * 7, head_cy - 12), (head_cx + s * 16, head_cy - 23), (head_cx + s * 12, head_cy - 8)])
                draw_aa_poly(screen, (acc_lum, acc_lum, acc_lum), [(head_cx + s * 8, head_cy - 12), (head_cx + s * 14, head_cy - 20), (head_cx + s * 10, head_cy - 9)])
        elif hero_id == "judas":
            pygame.draw.rect(screen, (14, 14, 14), (int(head_cx - 9), int(head_cy - 22), 18, 11), border_radius=2)
            pygame.draw.rect(screen, (96, 96, 96), (int(head_cx - 7), int(head_cy - 20), 14, 7), border_radius=2)
        elif hero_id in ("lost", "bethany", "lazarus", "seraph"):
            draw_aa_ellipse(screen, (248, 248, 248), head_cx, head_cy - 21, 12, 4.2)
            draw_aa_ellipse(screen, (18, 18, 18), head_cx, head_cy - 21, 6.5, 2.0)
        elif hero_id == "eden":
            draw_aa_poly(screen, (244, 244, 244), [(head_cx - 11, head_cy - 12), (head_cx - 5, head_cy - 22), (head_cx, head_cy - 14), (head_cx + 6, head_cy - 23), (head_cx + 11, head_cy - 12)])
        elif hero_id == "magdalene":
            draw_aa_circle(screen, (242, 242, 242), head_cx - 13, head_cy - 6, 4.5)
            draw_aa_circle(screen, (242, 242, 242), head_cx + 13, head_cy - 6, 4.5)
        elif hero_id == "samson":
            pygame.draw.rect(screen, (238, 238, 238), (int(head_cx - 14), int(head_cy - 11), 28, 4), border_radius=2)
        elif hero_id == "nocturne":
            draw_aa_poly(screen, (244, 244, 244), [(head_cx - 10, head_cy - 12), (head_cx, head_cy - 25), (head_cx + 10, head_cy - 12), (head_cx, head_cy - 16)])
        elif hero_id == "chrono":
            draw_aa_ring(screen, (242, 242, 242), head_cx + 5.5 + eye_x_off, eye_y, 5.2, 1)
            pygame.draw.line(screen, (242, 242, 242), (int(head_cx), int(head_cy - 16)), (int(head_cx), int(head_cy - 24)), 2)
        elif hero_id == "alchemist":
            draw_aa_ring(screen, (240, 240, 240), head_cx - 5.5 + eye_x_off, eye_y, 4.8, 1)
            draw_aa_ring(screen, (240, 240, 240), head_cx + 5.5 + eye_x_off, eye_y, 4.8, 1)

    label_surf = _get_player_tag_surf(player_tag)
    screen.blit(label_surf, (int(round(x - label_surf.get_width() * 0.5)), int(round(dy - 46))))

