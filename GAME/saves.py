import datetime
import json
import os
import shutil
import sys
import traceback
import pygame
from bosses import BossBase
from enemy import BlueFly, create_enemy
from heroes import get_hero
from i18n import tr, tr_mode
from items import ItemPedestal, Pickup, get_item_by_id, get_random_item
from player import Player
from room import (
    Beggar,
    DiceFloor,
    Door,
    LoreMonolith,
    Machine,
    MysticalNPC,
    Obstacle,
    Room,
    SacrificeSpike,
    Shopkeeper,
)
from settings import (
    ENDLESS_MODIFIERS,
    GAME_SETTINGS,
    PLAYABLE_BOTTOM,
    PLAYABLE_LEFT,
    PLAYABLE_RIGHT,
    PLAYABLE_TOP,
    clear_render_caches,
    get_user_data_dir,
)

SAVE_SLOTS_COUNT = 3
SAVE_FORMAT_VERSION = 1


def get_slot_path(slot_idx):
    idx = int(slot_idx)
    if idx < 1 or idx > SAVE_SLOTS_COUNT:
        raise ValueError(f"Invalid save slot index: {slot_idx}")
    return os.path.join(get_user_data_dir(), f"save_slot_{idx}.json")


def is_slot_occupied(slot_idx):
    idx = int(slot_idx)
    path = get_slot_path(idx)
    if os.path.isfile(path) and os.path.getsize(path) > 0:
        return True
    bak = path + ".bak"
    if os.path.isfile(bak) and os.path.getsize(bak) > 0:
        return True
    tmp = path + ".tmp"
    if os.path.isfile(tmp) and os.path.getsize(tmp) > 0:
        return True
    return False


def delete_save_slot(slot_idx):
    idx = int(slot_idx)
    path = get_slot_path(idx)
    tmp_path = path + ".tmp"
    bak_path = path + ".bak"
    res = False
    for p in (path, tmp_path, bak_path):
        try:
            if os.path.exists(p):
                os.remove(p)
                res = True
        except Exception:
            pass
    return res


def _read_slot_payload(slot_idx):
    idx = int(slot_idx)
    path = get_slot_path(idx)
    bak_path = path + ".bak"
    tmp_path = path + ".tmp"

    candidates = [path]
    if os.path.isfile(bak_path):
        candidates.append(bak_path)
    if os.path.isfile(tmp_path):
        candidates.append(tmp_path)

    for p in candidates:
        if not os.path.isfile(p):
            continue
        try:
            if os.path.getsize(p) == 0:
                continue
            with open(p, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict) and isinstance(data.get("meta"), dict) and "run" in data:
                # If we read from backup or tmp because primary was corrupted or missing, heal primary!
                if p != path and not (os.path.isfile(path) and os.path.getsize(path) > 0):
                    try:
                        shutil.copy2(p, path)
                    except Exception:
                        pass
                return data
        except Exception:
            continue
    return None


def get_slot_summary(slot_idx):
    idx = int(slot_idx)
    path = get_slot_path(idx)
    bak_path = path + ".bak"
    tmp_path = path + ".tmp"

    has_files = (
        (os.path.isfile(path) and os.path.getsize(path) > 0)
        or (os.path.isfile(bak_path) and os.path.getsize(bak_path) > 0)
        or (os.path.isfile(tmp_path) and os.path.getsize(tmp_path) > 0)
    )
    if not has_files and not os.path.exists(path):
        return {"slot": idx, "empty": True, "corrupt": False}

    payload = _read_slot_payload(idx)
    if payload is not None:
        meta = dict(payload.get("meta", {}))
        meta["slot"] = idx
        meta["empty"] = False
        meta["corrupt"] = False
        return meta

    if os.path.exists(path) or os.path.exists(bak_path) or os.path.exists(tmp_path):
        return {"slot": idx, "empty": False, "corrupt": True}
    return {"slot": idx, "empty": True, "corrupt": False}


def list_save_slots():
    return [get_slot_summary(i) for i in range(1, SAVE_SLOTS_COUNT + 1)]


def _coord_key(coord):
    try:
        return f"{int(coord[0])},{int(coord[1])}"
    except Exception:
        return "0,0"


def _parse_coord(key_str):
    try:
        parts = str(key_str).split(",")
        return (int(parts[0]), int(parts[1]))
    except Exception:
        return (0, 0)


def _serialize_door(door):
    if door is None:
        return None
    try:
        tc = getattr(door, "target_coord", (0, 0)) or (0, 0)
        tc_x = int(tc[0]) if len(tc) > 0 else 0
        tc_y = int(tc[1]) if len(tc) > 1 else 0
        return {
            "direction": str(getattr(door, "direction", "N")),
            "target_coord": [tc_x, tc_y],
            "target_type": str(getattr(door, "target_type", "normal")),
            "locked": bool(getattr(door, "locked", False)),
            "secret": bool(getattr(door, "secret", False)),
            "opened": bool(getattr(door, "opened", False)),
        }
    except Exception:
        return None


def _deserialize_door(d):
    if not isinstance(d, dict):
        return Door("N", (0, 0))
    tc = d.get("target_coord", [0, 0])
    coord = (int(tc[0]) if len(tc) > 0 else 0, int(tc[1]) if len(tc) > 1 else 0)
    door = Door(
        str(d.get("direction", "N")),
        coord,
        target_type=str(d.get("target_type", "normal")),
        locked=bool(d.get("locked", False)),
        secret=bool(d.get("secret", False)),
    )
    door.opened = bool(d.get("opened", False))
    return door


def _serialize_room(room):
    if room is None:
        return {}
    rc = getattr(room, "coord", (0, 0)) or (0, 0)
    coord = [int(rc[0]) if len(rc) > 0 else 0, int(rc[1]) if len(rc) > 1 else 0]

    doors = {}
    for k, v in getattr(room, "doors", {}).items():
        sd = _serialize_door(v)
        if sd is not None:
            doors[str(k)] = sd

    devil_door = _serialize_door(getattr(room, "devil_door", None))

    obstacles = []
    for o in getattr(room, "obstacles", []):
        if not getattr(o, "alive", True):
            continue
        try:
            if hasattr(o, "rect") and o.rect is not None:
                ox = float(o.rect.centerx)
                oy = float(o.rect.centery)
            else:
                ox = float(getattr(o, "x", 0.0))
                oy = float(getattr(o, "y", 0.0))
            kind = str(getattr(o, "kind", "rock"))
            size = int(getattr(o, "size", 48))
            hp = int(getattr(o, "hp", 1))
            max_hp = int(getattr(o, "max_hp", hp))
            fire_cd = float(getattr(o, "fire_cd", 0.0))
            obstacles.append({"x": ox, "y": oy, "kind": kind, "size": size, "hp": hp, "max_hp": max_hp, "fire_cd": fire_cd, "alive": True})
        except Exception:
            continue

    pickups = []
    for p in getattr(room, "pickups", []):
        if not getattr(p, "alive", True):
            continue
        try:
            px = float(getattr(p, "x", 0.0))
            py = float(getattr(p, "y", 0.0))
            kind = str(getattr(p, "kind", "coin"))
            price = int(getattr(p, "price", 0) or 0)
            pickups.append({"x": px, "y": py, "kind": kind, "price": price, "alive": True})
        except Exception:
            continue

    pedestals = []
    for ped in getattr(room, "pedestals", []):
        if not getattr(ped, "alive", True) or getattr(ped, "item", None) is None:
            continue
        try:
            item_obj = ped.item
            if isinstance(item_obj, dict):
                iid = item_obj.get("id")
            elif isinstance(item_obj, str):
                iid = item_obj
            else:
                iid = getattr(item_obj, "id", None)
            if not iid:
                continue
            pedestals.append(
                {
                    "x": float(getattr(ped, "x", 0.0)),
                    "y": float(getattr(ped, "y", 0.0)),
                    "item_id": str(iid),
                    "price": int(getattr(ped, "price", 0) or 0),
                    "devil_cost": int(getattr(ped, "devil_cost", 0) or 0),
                    "alive": True,
                }
            )
        except Exception:
            continue

    enemies = []
    for e in getattr(room, "enemies", []):
        if not getattr(e, "alive", True):
            continue
        try:
            etype = getattr(e, "enemy_type", getattr(e, "kind", "gaper"))
            enemies.append(
                {
                    "enemy_type": str(etype),
                    "x": float(getattr(e, "x", 0.0)),
                    "y": float(getattr(e, "y", 0.0)),
                    "hp": float(getattr(e, "hp", 10.0)),
                    "max_hp": float(getattr(e, "max_hp", 10.0)),
                }
            )
        except Exception:
            continue

    bosses = []
    for b in getattr(room, "bosses", []):
        if not getattr(b, "alive", True):
            continue
        try:
            bosses.append(
                {
                    "boss_key": str(getattr(b, "boss_key", "monstro")),
                    "x": float(getattr(b, "x", 0.0)),
                    "y": float(getattr(b, "y", 0.0)),
                    "hp": float(getattr(b, "hp", 100.0)),
                    "max_hp": float(getattr(b, "max_hp", 100.0)),
                    "phase": int(getattr(b, "phase", 1)),
                    "radius": float(getattr(b, "radius", 34.0)),
                }
            )
        except Exception:
            continue

    beggars = []
    for b in getattr(room, "beggars", []):
        if not getattr(b, "alive", True):
            continue
        try:
            beggars.append(
                {
                    "x": float(getattr(b, "x", 0.0)),
                    "y": float(getattr(b, "y", 0.0)),
                    "kind": str(getattr(b, "kind", "coin_beggar")),
                    "uses": int(getattr(b, "uses", 0)),
                    "max_uses": int(getattr(b, "max_uses", 4)),
                    "paid_out": bool(getattr(b, "paid_out", False)),
                }
            )
        except Exception:
            continue

    shopkeepers = []
    for s in getattr(room, "shopkeepers", []):
        if not getattr(s, "alive", True):
            continue
        try:
            shopkeepers.append(
                {
                    "x": float(getattr(s, "x", 0.0)),
                    "y": float(getattr(s, "y", 0.0)),
                    "variant": str(getattr(s, "variant", "keeper_classic")),
                }
            )
        except Exception:
            continue

    machines = []
    for m in getattr(room, "machines", []):
        if not getattr(m, "alive", True):
            continue
        try:
            machines.append(
                {
                    "x": float(getattr(m, "x", 0.0)),
                    "y": float(getattr(m, "y", 0.0)),
                    "kind": str(getattr(m, "kind", "slot_machine")),
                    "uses": int(getattr(m, "uses", 0)),
                }
            )
        except Exception:
            continue

    monoliths = []
    for m in getattr(room, "monoliths", []):
        if not getattr(m, "alive", True):
            continue
        try:
            monoliths.append(
                {
                    "x": float(getattr(m, "x", 0.0)),
                    "y": float(getattr(m, "y", 0.0)),
                    "activated": bool(getattr(m, "activated", False)),
                    "title": str(getattr(m, "title", "") or ""),
                    "text": str(getattr(m, "text", "") or ""),
                    "title_en": str(getattr(m, "title_en", "") or ""),
                    "text_en": str(getattr(m, "text_en", "") or ""),
                }
            )
        except Exception:
            continue

    mystical_npcs = []
    for n in getattr(room, "mystical_npcs", []):
        if not getattr(n, "alive", True):
            continue
        try:
            mystical_npcs.append(
                {
                    "x": float(getattr(n, "x", 0.0)),
                    "y": float(getattr(n, "y", 0.0)),
                    "kind": str(getattr(n, "kind", "pale_wanderer")),
                    "used": bool(getattr(n, "used", False)),
                }
            )
        except Exception:
            continue

    sacrifice_spike = None
    if getattr(room, "sacrifice_spike", None) is not None:
        try:
            sp = room.sacrifice_spike
            sacrifice_spike = {"x": float(sp.x), "y": float(sp.y), "hits": int(getattr(sp, "hits", 0))}
        except Exception:
            sacrifice_spike = None

    dice_floor = None
    if getattr(room, "dice_floor", None) is not None:
        try:
            df = room.dice_floor
            dice_floor = {
                "x": float(df.x),
                "y": float(df.y),
                "pips": int(getattr(df, "pips", 1)),
                "used": bool(getattr(df, "used", False)),
            }
        except Exception:
            dice_floor = None

    trapdoor_rect = None
    if getattr(room, "trapdoor_rect", None) is not None:
        try:
            trapdoor_rect = [int(v) for v in room.trapdoor_rect]
        except Exception:
            trapdoor_rect = None

    victory_portal_rect = None
    if getattr(room, "victory_portal_rect", None) is not None:
        try:
            victory_portal_rect = [int(v) for v in room.victory_portal_rect]
        except Exception:
            victory_portal_rect = None

    fmod_id = None
    fmod = getattr(room, "floor_modifier", None)
    if isinstance(fmod, dict):
        fmod_id = fmod.get("id")
    elif isinstance(fmod, str):
        fmod_id = fmod

    return {
        "coord": coord,
        "room_type": str(getattr(room, "room_type", "normal")),
        "floor_level": int(getattr(room, "floor_level", 1)),
        "layout_key": str(getattr(room, "layout_key", "empty")),
        "game_mode": str(getattr(room, "game_mode", "classic")),
        "floor_modifier_id": fmod_id,
        "visited": bool(getattr(room, "visited", False)),
        "cleared": bool(getattr(room, "cleared", False)),
        "combat_theme": getattr(room, "combat_theme", None),
        "doors": doors,
        "devil_door": devil_door,
        "obstacles": obstacles,
        "pickups": pickups,
        "pedestals": pedestals,
        "enemies": enemies,
        "bosses": bosses,
        "beggars": beggars,
        "shopkeepers": shopkeepers,
        "machines": machines,
        "monoliths": monoliths,
        "mystical_npcs": mystical_npcs,
        "sacrifice_spike": sacrifice_spike,
        "dice_floor": dice_floor,
        "trapdoor_rect": trapdoor_rect,
        "victory_portal_rect": victory_portal_rect,
    }


def _find_floor_modifier(mod_id):
    if not mod_id:
        return None
    for mod in ENDLESS_MODIFIERS:
        if isinstance(mod, dict) and mod.get("id") == mod_id:
            return mod
    return None


def _deserialize_room(data):
    if not isinstance(data, dict):
        return Room((0, 0), room_type="normal", floor_level=1, build_contents=False)
    raw_c = data.get("coord", (0, 0))
    coord = (int(raw_c[0]) if len(raw_c) > 0 else 0, int(raw_c[1]) if len(raw_c) > 1 else 0)
    fmod = _find_floor_modifier(data.get("floor_modifier_id"))
    rm = Room(
        coord,
        room_type=str(data.get("room_type", "normal")),
        floor_level=int(data.get("floor_level", 1)),
        layout_key=str(data.get("layout_key", "empty")),
        game_mode=str(data.get("game_mode", "classic")),
        floor_modifier=fmod,
        build_contents=False,
    )
    rm.visited = bool(data.get("visited", False))
    rm.cleared = bool(data.get("cleared", False))
    rm.combat_theme = data.get("combat_theme")
    rm.doors = {k: _deserialize_door(v) for k, v in data.get("doors", {}).items() if isinstance(v, dict)}
    if data.get("devil_door"):
        rm.devil_door = _deserialize_door(data["devil_door"])

    for od in data.get("obstacles", []):
        try:
            o = Obstacle(float(od.get("x", 0)), float(od.get("y", 0)), str(od.get("kind", "rock")), size=int(od.get("size", 48)))
            o.hp = int(od.get("hp", o.hp))
            o.max_hp = int(od.get("max_hp", getattr(o, "max_hp", o.hp)))
            if "fire_cd" in od:
                o.fire_cd = float(od.get("fire_cd", 0.0))
            o.alive = bool(od.get("alive", True))
            rm.obstacles.append(o)
        except Exception:
            pass

    for pd in data.get("pickups", []):
        try:
            p = Pickup(float(pd.get("x", 0)), float(pd.get("y", 0)), str(pd.get("kind", "coin")), price=int(pd.get("price", 0)))
            p.alive = bool(pd.get("alive", True))
            rm.pickups.append(p)
        except Exception:
            pass

    for ped_d in data.get("pedestals", []):
        try:
            it = get_item_by_id(ped_d.get("item_id")) or get_random_item()
            ped = ItemPedestal(
                float(ped_d.get("x", 0)),
                float(ped_d.get("y", 0)),
                it,
                price=int(ped_d.get("price", 0)),
                devil_cost=int(ped_d.get("devil_cost", 0)),
            )
            ped.alive = bool(ped_d.get("alive", True))
            rm.pedestals.append(ped)
        except Exception:
            pass

    for ed in data.get("enemies", []):
        try:
            en = create_enemy(str(ed.get("enemy_type", "gaper")), float(ed.get("x", 0)), float(ed.get("y", 0)), rm.floor_level, rm.floor_modifier)
            en.hp = float(ed.get("hp", en.hp))
            en.max_hp = float(ed.get("max_hp", en.max_hp))
            rm.enemies.append(en)
        except Exception:
            pass

    for bd in data.get("bosses", []):
        try:
            b = BossBase(
                float(bd.get("x", 0)),
                float(bd.get("y", 0)),
                str(bd.get("boss_key", "monstro")),
                rm.floor_level,
                radius_override=bd.get("radius"),
                floor_modifier=rm.floor_modifier,
            )
            b.hp = float(bd.get("hp", b.hp))
            b.max_hp = float(bd.get("max_hp", b.max_hp))
            b.phase = int(bd.get("phase", 1))
            rm.bosses.append(b)
        except Exception:
            pass

    for bg in data.get("beggars", []):
        try:
            b_obj = Beggar(float(bg.get("x", 0)), float(bg.get("y", 0)), str(bg.get("kind", "coin_beggar")))
            b_obj.uses = int(bg.get("uses", 0))
            b_obj.max_uses = int(bg.get("max_uses", 4))
            b_obj.paid_out = bool(bg.get("paid_out", False))
            rm.beggars.append(b_obj)
        except Exception:
            pass

    for sk in data.get("shopkeepers", []):
        try:
            rm.shopkeepers.append(Shopkeeper(float(sk.get("x", 0)), float(sk.get("y", 0)), str(sk.get("variant", "keeper_classic"))))
        except Exception:
            pass

    for mc in data.get("machines", []):
        try:
            m_obj = Machine(float(mc.get("x", 0)), float(mc.get("y", 0)), str(mc.get("kind", "slot_machine")))
            m_obj.uses = int(mc.get("uses", 0))
            rm.machines.append(m_obj)
        except Exception:
            pass

    for ml in data.get("monoliths", []):
        try:
            mono = LoreMonolith(
                float(ml.get("x", 0)),
                float(ml.get("y", 0)),
                title=ml.get("title") or None,
                text=ml.get("text") or None,
                title_en=ml.get("title_en") or None,
                text_en=ml.get("text_en") or None,
            )
            mono.activated = bool(ml.get("activated", False))
            rm.monoliths.append(mono)
        except Exception:
            pass

    for np in data.get("mystical_npcs", []):
        try:
            n_obj = MysticalNPC(float(np.get("x", 0)), float(np.get("y", 0)), str(np.get("kind", "pale_wanderer")))
            if hasattr(n_obj, "used"):
                n_obj.used = bool(np.get("used", False))
            rm.mystical_npcs.append(n_obj)
        except Exception:
            pass

    if isinstance(data.get("sacrifice_spike"), dict):
        try:
            sd = data["sacrifice_spike"]
            sp = SacrificeSpike(float(sd.get("x", 0)), float(sd.get("y", 0)))
            sp.hits = int(sd.get("hits", 0))
            rm.sacrifice_spike = sp
        except Exception:
            pass

    if isinstance(data.get("dice_floor"), dict):
        try:
            dd = data["dice_floor"]
            df = DiceFloor(float(dd.get("x", 0)), float(dd.get("y", 0)), int(dd.get("pips", 1)))
            df.used = bool(dd.get("used", False))
            rm.dice_floor = df
        except Exception:
            pass

    if isinstance(data.get("trapdoor_rect"), list) and len(data["trapdoor_rect"]) == 4:
        try:
            rm.trapdoor_rect = pygame.Rect(*data["trapdoor_rect"])
        except Exception:
            pass

    if isinstance(data.get("victory_portal_rect"), list) and len(data["victory_portal_rect"]) == 4:
        try:
            rm.victory_portal_rect = pygame.Rect(*data["victory_portal_rect"])
        except Exception:
            pass

    return rm


def _serialize_player(player):
    if player is None:
        return {}
    hero_id = str(getattr(player, "hero_id", "isaac"))

    active_items = []
    for slot in getattr(player, "active_items", []):
        if not isinstance(slot, dict):
            continue
        item_obj = slot.get("item")
        item_id = None
        if isinstance(item_obj, dict):
            item_id = item_obj.get("id")
        elif isinstance(item_obj, str):
            item_id = item_obj
        else:
            item_id = getattr(item_obj, "id", None)
        if not item_id:
            continue
        chg = int(slot.get("charge", 0) or 0)
        mchg = int(slot.get("max_charge", 4) or 4)
        active_items.append({"id": str(item_id), "charge": chg, "max_charge": mchg})

    collected_item_ids = []
    for it in getattr(player, "collected_items", []):
        if isinstance(it, dict) and it.get("id"):
            collected_item_ids.append(str(it["id"]))
        elif isinstance(it, str) and it:
            collected_item_ids.append(it)
        elif hasattr(it, "id") and getattr(it, "id", None):
            collected_item_ids.append(str(getattr(it, "id")))

    raw_cids = getattr(player, "collected_ids", set()) or set()
    collected_ids = sorted([str(x) for x in raw_cids if x is not None])

    active_effects = {}
    for k, v in getattr(player, "active_effects", {}).items():
        try:
            active_effects[str(k)] = float(v)
        except (TypeError, ValueError):
            pass

    allies = []
    for a in getattr(player, "allies", []):
        if not getattr(a, "alive", True):
            continue
        try:
            ax = float(getattr(a, "x", getattr(player, "x", 640.0)))
            ay = float(getattr(a, "y", getattr(player, "y", 360.0)))
            adm = float(getattr(a, "damage", 4.0))
            allies.append({"x": ax, "y": ay, "damage": adm})
        except Exception:
            continue

    return {
        "hero_id": hero_id,
        "x": float(getattr(player, "x", 640.0)),
        "y": float(getattr(player, "y", 360.0)),
        "hp": int(getattr(player, "hp", 6)),
        "max_hp": int(getattr(player, "max_hp", 6)),
        "soul_hp": int(getattr(player, "soul_hp", 0)),
        "black_hp": int(getattr(player, "black_hp", 0)),
        "speed": float(getattr(player, "speed", 4.0)),
        "damage": float(getattr(player, "damage", 3.5)),
        "fire_delay": float(getattr(player, "fire_delay", 14.0)),
        "tear_speed": float(getattr(player, "tear_speed", 9.0)),
        "tear_range": float(getattr(player, "tear_range", 420.0)),
        "luck": float(getattr(player, "luck", 0.0)),
        "coins": int(getattr(player, "coins", 0)),
        "bombs": int(getattr(player, "bombs", 1)),
        "keys": int(getattr(player, "keys", 1)),
        "radius": float(getattr(player, "radius", 18.0)),
        "has_flight": bool(getattr(player, "has_flight", False)),
        "has_piercing": bool(getattr(player, "has_piercing", False)),
        "has_homing": bool(getattr(player, "has_homing", False)),
        "has_bouncing": bool(getattr(player, "has_bouncing", False)),
        "has_splitting": bool(getattr(player, "has_splitting", False)),
        "has_spectral": bool(getattr(player, "has_spectral", False)),
        "has_poison": bool(getattr(player, "has_poison", False)),
        "has_holy": bool(getattr(player, "has_holy", False)),
        "has_bone": bool(getattr(player, "has_bone", False)),
        "has_brimstone": bool(getattr(player, "has_brimstone", False)),
        "has_boomerang": bool(getattr(player, "has_boomerang", False)),
        "has_coal": bool(getattr(player, "has_coal", False)),
        "has_wafer": bool(getattr(player, "has_wafer", False)),
        "has_pyromaniac": bool(getattr(player, "has_pyromaniac", False)),
        "has_steam_sale": bool(getattr(player, "has_steam_sale", False)),
        "has_moms_key": bool(getattr(player, "has_moms_key", False)),
        "has_sad_bombs": bool(getattr(player, "has_sad_bombs", False)),
        "has_skatole": bool(getattr(player, "has_skatole", False)),
        "has_relic": bool(getattr(player, "has_relic", False)),
        "has_dark_bum": bool(getattr(player, "has_dark_bum", False)),
        "has_placenta": bool(getattr(player, "has_placenta", False)),
        "has_infamy": bool(getattr(player, "has_infamy", False)),
        "has_whore": bool(getattr(player, "has_whore", False)),
        "has_lazarus_revive": bool(getattr(player, "has_lazarus_revive", False)),
        "has_bloody_lust": bool(getattr(player, "has_bloody_lust", False)),
        "bloody_lust_stacks": int(getattr(player, "bloody_lust_stacks", 0)),
        "dark_bum_counter": int(getattr(player, "dark_bum_counter", 0)),
        "keeper_coin_counter": int(getattr(player, "keeper_coin_counter", 0)),
        "seraph_room_counter": int(getattr(player, "seraph_room_counter", 0)),
        "lantern_fuel": float(getattr(player, "lantern_fuel", 1.0)),
        "lantern_bonus": float(getattr(player, "lantern_bonus", 1.0)),
        "slow_projectiles": bool(getattr(player, "slow_projectiles", False)),
        "dodge_chance": float(getattr(player, "dodge_chance", 0.0)),
        "free_locks": bool(getattr(player, "free_locks", False)),
        "compass_reveal": bool(getattr(player, "compass_reveal", False)),
        "eclipse_aura": bool(getattr(player, "eclipse_aura", False)),
        "multi_shot": int(getattr(player, "multi_shot", 1)),
        "orbitals": int(getattr(player, "orbitals", 0)),
        "incubus_count": int(getattr(player, "incubus_count", 0)),
        "wisps": int(getattr(player, "wisps", 0)),
        "holy_mantle": bool(getattr(player, "holy_mantle", False)),
        "mantle_broken_room": bool(getattr(player, "mantle_broken_room", False)),
        "has_explosive_tears": bool(getattr(player, "has_explosive_tears", False)),
        "has_lobbed_tears": bool(getattr(player, "has_lobbed_tears", False)),
        "has_seismic_boots": bool(getattr(player, "has_seismic_boots", False)),
        "has_shock_core": bool(getattr(player, "has_shock_core", False)),
        "has_vortex": bool(getattr(player, "has_vortex", False)),
        "has_chain_arc": bool(getattr(player, "has_chain_arc", False)),
        "has_dash_strike": bool(getattr(player, "has_dash_strike", False)),
        "invis_timer": float(getattr(player, "invis_timer", 0.0)),
        "invis_cd": float(getattr(player, "invis_cd", 0.0)),
        "invis_max_cd": float(getattr(player, "invis_max_cd", 360.0)),
        "ambush_mult": float(getattr(player, "ambush_mult", 2.0)),
        "dash_cd": float(getattr(player, "dash_cd", 0.0)),
        "dash_max_cd": float(getattr(player, "dash_max_cd", 95.0)),
        "jump_cd": float(getattr(player, "jump_cd", 0.0)),
        "jump_max_cd": float(getattr(player, "jump_max_cd", 120.0)),
        "bomb_cd": float(getattr(player, "bomb_cd", 0.0)),
        "bomb_max_cd": float(getattr(player, "bomb_max_cd", 75.0)),
        "melee_cd": float(getattr(player, "melee_cd", 0.0)),
        "melee_max_cd": float(getattr(player, "melee_max_cd", 26.0)),
        "melee_hits": int(getattr(player, "melee_hits", 0)),
        "melee_kills": int(getattr(player, "melee_kills", 0)),
        "active_items": active_items,
        "active_slot": int(getattr(player, "active_slot", 0)),
        "inventory_page": int(getattr(player, "inventory_page", 0)),
        "selected_inv_idx": int(getattr(player, "selected_inv_idx", 0)),
        "void_absorbed": int(getattr(player, "void_absorbed", 0)),
        "collected_item_ids": collected_item_ids,
        "collected_ids": collected_ids,
        "active_effects": active_effects,
        "room_dmg_bonus": float(getattr(player, "room_dmg_bonus", 0.0)),
        "room_extra_familiars": int(getattr(player, "room_extra_familiars", 0)),
        "room_extra_orbitals": int(getattr(player, "room_extra_orbitals", 0)),
        "room_extra_wisps": int(getattr(player, "room_extra_wisps", 0)),
        "kills": int(getattr(player, "kills", 0)),
        "shots_fired": int(getattr(player, "shots_fired", 0)),
        "allies": allies,
    }


def _deserialize_player(data):
    if not isinstance(data, dict):
        return Player(640.0, 360.0, "isaac")
    hero_id = data.get("hero_id", "isaac")
    p = Player(float(data.get("x", 640.0)), float(data.get("y", 360.0)), hero_id)
    p.active_items = []
    p.collected_items = []
    p.collected_ids = set()
    for cid in data.get("collected_ids", []):
        if cid is not None:
            p.collected_ids.add(str(cid))
    p.allies = []

    scalar_keys = (
        "hp", "max_hp", "soul_hp", "black_hp", "speed", "damage", "fire_delay",
        "tear_speed", "tear_range", "luck", "coins", "bombs", "keys", "radius",
        "has_flight", "has_piercing", "has_homing", "has_bouncing", "has_splitting",
        "has_spectral", "has_poison", "has_holy", "has_bone", "has_brimstone",
        "has_boomerang", "has_coal", "has_wafer", "has_pyromaniac", "has_steam_sale",
        "has_moms_key", "has_sad_bombs", "has_skatole", "has_relic", "has_dark_bum",
        "has_placenta", "has_infamy", "has_whore", "has_lazarus_revive", "has_bloody_lust",
        "bloody_lust_stacks", "dark_bum_counter", "keeper_coin_counter", "seraph_room_counter",
        "lantern_fuel", "lantern_bonus", "slow_projectiles", "dodge_chance", "free_locks",
        "compass_reveal", "eclipse_aura", "multi_shot", "orbitals", "incubus_count",
        "wisps", "holy_mantle", "mantle_broken_room", "dash_cd", "dash_max_cd",
        "jump_cd", "jump_max_cd", "bomb_cd", "bomb_max_cd", "melee_cd", "melee_max_cd",
        "melee_hits", "melee_kills", "active_slot",
        "has_explosive_tears", "has_lobbed_tears", "has_seismic_boots", "has_shock_core",
        "has_vortex", "has_chain_arc", "has_dash_strike",
        "invis_timer", "invis_cd", "invis_max_cd", "ambush_mult",
        "inventory_page", "selected_inv_idx", "void_absorbed", "room_dmg_bonus",
        "room_extra_familiars", "room_extra_orbitals", "room_extra_wisps", "kills", "shots_fired",
    )
    for k in scalar_keys:
        if k in data:
            try:
                setattr(p, k, data[k])
            except Exception:
                pass

    for s_d in data.get("active_items", []):
        if not isinstance(s_d, dict):
            continue
        it = get_item_by_id(s_d.get("id"))
        if it:
            mc = int(s_d.get("max_charge", it.get("max_charge", 4)))
            chg = int(min(mc, max(0, s_d.get("charge", mc))))
            p.active_items.append({"item": it, "charge": chg, "max_charge": mc})
    if p.active_items:
        p.active_slot = max(0, min(p.active_slot, len(p.active_items) - 1))
    else:
        p.active_slot = 0

    for iid in data.get("collected_item_ids", []):
        it = get_item_by_id(iid)
        if it:
            p.collected_items.append(it)
            p.collected_ids.add(it["id"])

    p.active_effects = {}
    for k, v in data.get("active_effects", {}).items():
        try:
            p.active_effects[str(k)] = float(v)
        except Exception:
            pass

    for al in data.get("allies", []):
        try:
            p.allies.append(BlueFly(float(al.get("x", p.x)), float(al.get("y", p.y)), float(al.get("damage", p.get_effective_damage()))))
        except Exception:
            pass
    p.cloak_nodes = [(p.x, p.y + i * 3.5) for i in range(7)]
    p.incubus_pos = (p.x - 32.0, p.y + 12.0)
    return p


def save_run_to_slot(slot_idx, game):
    """
    Safely writes progress to slot.
    Guarantees no crashes, atomic disk replacement, and automatic backup.
    """
    try:
        idx = int(slot_idx)
        if idx < 1 or idx > SAVE_SLOTS_COUNT:
            return False, "invalid_slot"
        if is_slot_occupied(idx):
            return False, "occupied"
        p1_ok = getattr(game, "player", None) is not None and not game.player.is_dead()
        p2_ok = bool(getattr(game, "coop_enabled", False) and getattr(game, "player2", None) is not None and not game.player2.is_dead())
        if game is None or getattr(game, "player", None) is None or getattr(game, "current_room", None) is None or (not p1_ok and not p2_ok):
            return False, "no_active_run"

        hero = get_hero(game.player.hero_id) or {}
        hero_name = hero.get("name", "Isaac")
        hero_name_en = hero.get("name_en", hero_name)
        is_coop_save = bool(getattr(game, "coop_enabled", False) and getattr(game, "player2", None) is not None)
        p2_hero_name = ""
        p2_hero_name_en = ""
        if is_coop_save:
            p2h = get_hero(game.player2.hero_id) or {}
            p2_hero_name = str(p2h.get("name", ""))
            p2_hero_name_en = str(p2h.get("name_en", p2_hero_name))
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        active_items_len = len(getattr(game.player, "active_items", []))
        coll_items_len = len(getattr(game.player, "collected_items", []))

        cur_coord = getattr(game, "current_coord", (0, 0)) or (0, 0)
        devil_ret = getattr(game, "devil_return_coord", (0, 0)) or (0, 0)

        fmod_id = None
        if isinstance(getattr(game, "floor_modifier", None), dict):
            fmod_id = game.floor_modifier.get("id")

        rooms_dict = {}
        for c, rm in getattr(game, "rooms", {}).items():
            try:
                rooms_dict[_coord_key(c)] = _serialize_room(rm)
            except Exception:
                pass

        devil_rm = None
        if cur_coord == (99, 99) and getattr(game, "current_room", None) is not None:
            devil_rm = _serialize_room(game.current_room)

        quests_data = []
        if hasattr(game, "quest_manager") and game.quest_manager is not None:
            try:
                quests_data = game.quest_manager.serialize()
            except Exception:
                quests_data = []

        payload = {
            "version": SAVE_FORMAT_VERSION,
            "meta": {
                "hero_id": str(game.player.hero_id),
                "hero_name": str(hero_name),
                "hero_name_en": str(hero_name_en),
                "coop_enabled": is_coop_save,
                "p2_hero_name": p2_hero_name,
                "p2_hero_name_en": p2_hero_name_en,
                "game_mode": str(getattr(game, "game_mode", "classic")),
                "floor_level": int(getattr(game, "floor_level", 1)),
                "wave_num": int(getattr(game, "wave_num", 1)),
                "kills": int(getattr(game.player, "kills", 0)) + (int(getattr(game.player2, "kills", 0)) if is_coop_save else 0),
                "hp": int(getattr(game.player, "hp", 6)),
                "max_hp": int(getattr(game.player, "max_hp", 6)),
                "soul_hp": int(getattr(game.player, "soul_hp", 0)),
                "black_hp": int(getattr(game.player, "black_hp", 0)),
                "coins": int(getattr(game.player, "coins", 0)),
                "items_count": int(coll_items_len + active_items_len),
                "saved_at": now_str,
            },
            "run": {
                "game_mode": str(getattr(game, "game_mode", "classic")),
                "floor_level": int(getattr(game, "floor_level", 1)),
                "floor_modifier_id": fmod_id,
                "wave_num": int(getattr(game, "wave_num", 1)),
                "wave_break_timer": float(getattr(game, "wave_break_timer", 0.0)),
                "darkness_tick": float(getattr(game, "darkness_tick", 0.0)),
                "placenta_tick": float(getattr(game, "placenta_tick", 0.0)),
                "shared_seed": getattr(game, "active_seed", None),
                "boss_rush_wave": int(getattr(game, "boss_rush_wave", 1)),
                "floor_pedestals_spawned": int(getattr(game, "floor_pedestals_spawned", 0)),
                "floor_took_damage": bool(getattr(game, "floor_took_damage", False)),
                "room_took_damage": bool(getattr(game, "room_took_damage", False)),
                "coop_enabled": bool(getattr(game, "coop_enabled", False) and getattr(game, "player2", None) is not None),
                "current_coord": [int(cur_coord[0]), int(cur_coord[1])],
                "devil_return_coord": [int(devil_ret[0]), int(devil_ret[1])],
                "player": _serialize_player(game.player),
                "player2": (
                    _serialize_player(game.player2)
                    if (getattr(game, "coop_enabled", False) and getattr(game, "player2", None) is not None)
                    else None
                ),
                "rooms": rooms_dict,
                "devil_room": devil_rm,
                "quests": quests_data,
            },
        }

        path = get_slot_path(idx)
        tmp_path = path + ".tmp"
        bak_path = path + ".bak"

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.flush()
            try:
                os.fsync(fh.fileno())
            except Exception:
                pass

        # Verify integrity of written JSON
        with open(tmp_path, "r", encoding="utf-8") as fh:
            v_check = json.load(fh)
        if not isinstance(v_check, dict) or "meta" not in v_check or "run" not in v_check:
            raise ValueError("Corrupt save validation check")

        # Keep existing as backup if present
        if os.path.isfile(path) and os.path.getsize(path) > 0:
            try:
                shutil.copy2(path, bak_path)
            except Exception:
                pass

        # Atomic replacement
        try:
            os.replace(tmp_path, path)
        except OSError:
            shutil.move(tmp_path, path)

        # Set friendly permissions on POSIX
        try:
            os.chmod(path, 0o666)
        except Exception:
            pass

        return True, "saved"
    except Exception as exc:
        try:
            p = get_slot_path(slot_idx)
            if os.path.exists(p + ".tmp"):
                os.remove(p + ".tmp")
            log_p = os.path.join(get_user_data_dir(), "save_crash.log")
            with open(log_p, "a", encoding="utf-8") as lf:
                lf.write(f"\n--- Save Error at {datetime.datetime.now()} ---\n")
                lf.write(traceback.format_exc())
        except Exception:
            pass
        return False, f"io_error: {exc}"


def load_run_from_slot(slot_idx, game):
    try:
        idx = int(slot_idx)
        payload = _read_slot_payload(idx)
        if not payload or not isinstance(payload, dict) or "run" not in payload:
            return False, "corrupt"

        run = payload["run"]
        clear_render_caches(include_text=False)
        if hasattr(game, "touch") and game.touch is not None:
            game.touch.reset()

        game.game_mode = str(run.get("game_mode", "classic"))
        game.floor_level = int(run.get("floor_level", 1))
        game.floor_modifier = _find_floor_modifier(run.get("floor_modifier_id"))
        game.wave_num = int(run.get("wave_num", 1))
        game.wave_break_timer = float(run.get("wave_break_timer", 0.0))
        game.darkness_tick = float(run.get("darkness_tick", 0.0))
        game.placenta_tick = float(run.get("placenta_tick", 0.0))
        game.active_seed = run.get("shared_seed")
        game.boss_rush_wave = int(run.get("boss_rush_wave", 1))
        game.floor_pedestals_spawned = int(run.get("floor_pedestals_spawned", 0))
        game.floor_took_damage = bool(run.get("floor_took_damage", False))
        game.room_took_damage = bool(run.get("room_took_damage", False))
        game.run_recorded = False
        game.cutscene = None
        game.coop_enabled = bool(run.get("coop_enabled", False) and run.get("player2"))

        cc = run.get("current_coord", (0, 0))
        game.current_coord = (int(cc[0]), int(cc[1]))
        dc = run.get("devil_return_coord", (0, 0))
        game.devil_return_coord = (int(dc[0]), int(dc[1]))

        game.player = _deserialize_player(run.get("player", {}))
        game.player2 = (
            _deserialize_player(run["player2"])
            if (game.coop_enabled and isinstance(run.get("player2"), dict))
            else None
        )
        if game.coop_enabled and game.player2 is not None:
            game.player.player_tag = "P1"
            game.player2.player_tag = "P2"
        else:
            game.player.player_tag = ""

        game.rooms = {}
        for k, v in run.get("rooms", {}).items():
            if isinstance(v, dict):
                game.rooms[_parse_coord(k)] = _deserialize_room(v)

        if hasattr(game, "quest_manager") and game.quest_manager is not None and run.get("quests"):
            try:
                game.quest_manager.deserialize(run["quests"])
            except Exception:
                pass

        if game.current_coord == (99, 99) and run.get("devil_room"):
            game.current_room = _deserialize_room(run["devil_room"])
        else:
            if game.current_coord not in game.rooms:
                game.current_coord = (0, 0)
            if (0, 0) not in game.rooms and game.rooms:
                game.current_coord = next(iter(game.rooms.keys()))
            game.current_room = game.rooms.get(game.current_coord)
            if game.current_room is None:
                game.current_room = Room(game.current_coord, room_type="normal", floor_level=game.floor_level)
                game.rooms[game.current_coord] = game.current_room

        game.tears.clear()
        game.enemy_projectiles.clear()
        game.bombs.clear()
        game.particles.clear()
        game.editor.active = False
        game.console.open = False
        game.fade_alpha = 200.0
        game.state = "PLAYING"

        lang = GAME_SETTINGS.get("language", "ru")
        title = f"ЗАГРУЖЕН СЛОТ {idx}" if lang == "ru" else f"LOADED SLOT {idx}"
        sub = f"{tr('floor_label')} {game.floor_level} · {tr_mode(game.game_mode)}"
        game.ui.show_banner(title, sub, 110.0)
        return True, "loaded"
    except Exception as exc:
        try:
            log_p = os.path.join(get_user_data_dir(), "load_crash.log")
            with open(log_p, "a", encoding="utf-8") as lf:
                lf.write(f"\n--- Load Error at {datetime.datetime.now()} ---\n")
                lf.write(traceback.format_exc())
        except Exception:
            pass
        return False, "corrupt"
