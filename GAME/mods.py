import inspect
import json
import os
import random
import re
import shutil
import subprocess
import sys
import traceback
import pygame
import bosses
import enemy
import heroes
import i18n
import items
import settings
from ai_mod_agent import (
    DEFAULT_MODELS,
    PROVIDER_CHOICES,
    ai_agent_client,
    detect_provider_from_key,
    validate_python_syntax,
)
from i18n import get_lang, tr
from settings import (
    GAME_SETTINGS,
    PALETTE,
    SCREEN_HEIGHT,
    atomic_write_json,
    blit_text_fitted,
    clamp,
    fit_text_surf,
    get_panel_surf,
    get_user_data_dir,
    get_view_width,
    get_world_offset_x,
    render_text_cached,
    safe_read_json,
)

SOURCE_FILE_LIST = [
    "heroes.py",
    "items.py",
    "player.py",
    "room.py",
    "dungeon.py",
    "enemy.py",
    "bosses.py",
    "bullet.py",
    "lighting.py",
    "settings.py",
    "saves.py",
    "mods.py",
    "ai_mod_agent.py",
    "ui.py",
    "touch_controls.py",
    "codex.py",
    "cutscene.py",
    "console.py",
    "quests.py",
    "accounts.py",
    "achievements.py",
    "sound.py",
    "i18n.py",
    "lan_coop.py",
    "main.py",
]

_EXAMPLE_QUICK_BOOST = '''# Mod Example: Run Boost & Room Blessing
MOD_NAME = "Quick Boost Example"
MOD_AUTHOR = "DarkVault"
MOD_VERSION = "1.0"
MOD_DESC = "Grants +1.0 DMG, +5 coins & heals 1 red HP on new rooms (enable to test)."


def on_register(api):
    api.log("Registered Quick Boost Example")


def on_run_start(api, game, player):
    player.damage += 1.0
    player.coins += 5


def on_room_enter(api, game, room, player):
    if player.hp < player.max_hp:
        player.hp = min(player.max_hp, player.hp + 1)
'''

_EXAMPLE_CUSTOM_CONTENT = '''# Mod Example: Custom Hero & Relic (see heroes.py & items.py)
MOD_NAME = "Abyssal Tinker Pack"
MOD_AUTHOR = "DarkVault"
MOD_VERSION = "1.0"
MOD_DESC = "Adds a custom artifact 'prism_core' and custom hero 'shade_smith'."


def on_register(api):
    api.add_item({
        "id": "prism_core",
        "name": "Ядро Призмы",
        "name_en": "Prism Core",
        "desc": "+1.8 Урон, +0.4 Скорость, +1 Орбиталь",
        "desc_en": "+1.8 DMG, +0.4 SPD, +1 Orbital",
        "type": "passive",
        "color": (240, 240, 240),
        "icon": "prism",
    })
    api.add_hero({
        "id": "shade_smith",
        "name": "Кузнец Теней",
        "name_en": "Shade Smith",
        "title": "Мастер модов",
        "desc": "Пользовательский герой из мода: +10 монет, +2 бомбы и старт с Prism Core.",
        "hp": 6,
        "max_hp": 6,
        "soul_hp": 2,
        "black_hp": 0,
        "speed": 4.4,
        "damage": 4.2,
        "fire_delay": 16,
        "tear_speed": 8.0,
        "tear_range": 430,
        "luck": 1,
        "coins": 10,
        "bombs": 2,
        "keys": 2,
        "starting_active": "wooden_nickel",
        "starting_passive": ["prism_core"],
        "has_flight": False,
        "has_piercing": False,
    })


def on_run_start(api, game, player):
    if player.hero_id == "shade_smith":
        player.orbitals += 1
'''

_NEW_MOD_TEMPLATE = '''MOD_NAME = "{title}"
MOD_AUTHOR = "Player"
MOD_VERSION = "1.0"
MOD_DESC = "Custom DarkVault mod."


def on_register(api):
    # Add heroes via api.add_hero({{...}}) or items via api.add_item({{...}})
    api.log("Mod {title} ready!")


def on_run_start(api, game, player):
    pass


def on_room_enter(api, game, room, player):
    pass


def on_update(api, game, dt):
    pass
'''

_PY_KEYWORDS = frozenset({
    "and", "as", "assert", "async", "await", "break", "class", "continue",
    "def", "del", "elif", "else", "except", "False", "finally", "for",
    "from", "global", "if", "import", "in", "is", "lambda", "None",
    "nonlocal", "not", "or", "pass", "raise", "return", "True", "try",
    "while", "with", "yield",
})

_PY_BUILTINS = frozenset({
    "api", "game", "player", "room", "math", "random", "pygame",
    "len", "range", "min", "max", "abs", "int", "float", "str", "bool",
    "list", "dict", "set", "tuple", "getattr", "hasattr", "setattr", "isinstance",
    "self", "cls", "print",
})

_TOKEN_RE = re.compile(
    r'(#.*$)|(""".*?"""|\'\'\'.*?\'\'\'|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')|\b(\d+(?:\.\d+)?)\b|\b([A-Za-z_][A-Za-z0-9_]*)\b'
)

_MONO_FONT_CACHE = {}


def _get_mono_font(size=14):
    key = int(size)
    cached = _MONO_FONT_CACHE.get(key)
    if cached is not None:
        return cached
    font = None
    try:
        font = pygame.font.SysFont("dejavusansmono,liberationmono,consolas,couriernew,monospace", key)
    except Exception:
        font = None
    if font is None:
        try:
            font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "DejaVuSans.ttf")
            if os.path.isfile(font_path):
                font = pygame.font.Font(font_path, key)
        except Exception:
            font = None
    if font is None:
        font = pygame.font.Font(None, key + 2)
    try:
        cw = max(6, int(font.size("M")[0]))
    except Exception:
        cw = 8
    _MONO_FONT_CACHE[key] = (font, cw)
    return font, cw


def _tokenize_python_line(line):
    if not line:
        return []
    tokens = []
    pos = 0
    n = len(line)
    for m in _TOKEN_RE.finditer(line):
        start, end = m.span()
        if start > pos:
            tokens.append((line[pos:start], (196, 198, 202)))
        comment_g, str_g, num_g, id_g = m.groups()
        if comment_g is not None:
            tokens.append((comment_g, (118, 124, 132)))
        elif str_g is not None:
            tokens.append((str_g, (192, 214, 190)))
        elif num_g is not None:
            tokens.append((num_g, (216, 206, 178)))
        elif id_g is not None:
            if id_g in _PY_KEYWORDS:
                tokens.append((id_g, (248, 248, 250)))
            elif id_g in _PY_BUILTINS:
                tokens.append((id_g, (198, 214, 232)))
            else:
                tokens.append((id_g, (226, 226, 226)))
        pos = end
    if pos < n:
        tokens.append((line[pos:], (196, 198, 202)))
    return tokens


def _sanitize_mod_filename(name_hint):
    stem = os.path.basename(str(name_hint or "").strip())
    if stem.lower().endswith(".py"):
        stem = stem[:-3]
    stem = re.sub(r"[^a-zA-Z0-9_\-]+", "_", stem).strip("_")
    if not stem:
        stem = "custom_mod"
    return f"{stem}.py"


class ModAPI:
    def __init__(self, manager, mod_filename):
        self._manager = manager
        self.mod_filename = mod_filename
        self.heroes = heroes
        self.items = items
        self.enemy = enemy
        self.bosses = bosses
        self.settings = settings
        self.i18n = i18n

    def log(self, message):
        self._manager.append_log(f"[{self.mod_filename}] {message}")

    def rand(self):
        return random.random()

    def add_item(self, item_dict):
        if not isinstance(item_dict, dict) or not item_dict.get("id"):
            raise ValueError("Item dict must include non-empty 'id'")
        entry = dict(item_dict)
        iid = str(entry["id"])
        entry["id"] = iid
        entry.setdefault("name", iid.replace("_", " ").title())
        entry.setdefault("name_en", entry["name"])
        entry.setdefault("desc", "Modded relic")
        entry.setdefault("desc_en", entry["desc"])
        entry.setdefault("type", "passive")
        entry.setdefault("color", (236, 236, 236))
        entry.setdefault("icon", "orb")
        if entry["type"] == "active":
            entry.setdefault("max_charge", 4)

        replaced = False
        for i, cur in enumerate(items.ITEM_POOL_65):
            if cur.get("id") == iid:
                items.ITEM_POOL_65[i] = entry
                replaced = True
                break
        if not replaced:
            items.ITEM_POOL_65.append(entry)
        items.ITEM_REGISTRY[iid] = entry
        if iid not in self._manager._mod_item_ids:
            self._manager._mod_item_ids.append(iid)
        return entry

    def add_hero(self, hero_dict):
        if not isinstance(hero_dict, dict) or not hero_dict.get("id"):
            raise ValueError("Hero dict must include non-empty 'id'")
        entry = dict(hero_dict)
        hid = str(entry["id"])
        entry["id"] = hid
        entry.setdefault("name", hid.replace("_", " ").title())
        entry.setdefault("name_en", entry["name"])
        entry.setdefault("title", "Modded Wanderer")
        entry.setdefault("desc", "Custom modded hero.")
        entry.setdefault("hp", 6)
        entry.setdefault("max_hp", int(entry.get("hp", 6)))
        entry.setdefault("soul_hp", 0)
        entry.setdefault("black_hp", 0)
        entry.setdefault("speed", 4.2)
        entry.setdefault("damage", 3.6)
        entry.setdefault("fire_delay", 17)
        entry.setdefault("tear_speed", 7.8)
        entry.setdefault("tear_range", 420)
        entry.setdefault("luck", 0)
        entry.setdefault("coins", 3)
        entry.setdefault("bombs", 1)
        entry.setdefault("keys", 1)
        entry.setdefault("starting_active", None)
        entry.setdefault("starting_passive", [])
        entry.setdefault("color_body", (226, 226, 226))
        entry.setdefault("color_cloak", (92, 92, 92))
        entry.setdefault("color_accent", (245, 245, 245))
        entry.setdefault("color_tear", (242, 242, 242))
        entry.setdefault("has_flight", False)
        entry.setdefault("has_piercing", False)

        replaced = False
        for i, cur in enumerate(heroes.HERO_ROSTER):
            if cur.get("id") == hid:
                heroes.HERO_ROSTER[i] = entry
                replaced = True
                break
        if not replaced:
            heroes.HERO_ROSTER.append(entry)
        if hid not in self._manager._mod_hero_ids:
            self._manager._mod_hero_ids.append(hid)
        return entry


class ModManager:
    def __init__(self):
        self.loaded_mods = []
        self.mod_errors = {}
        self.logs = []
        self.enabled_map = {}
        self._mod_item_ids = []
        self._mod_hero_ids = []
        self._runtime_faulty_updates = set()
        self._examples_seeded = False

    def get_mods_dir(self):
        return os.path.join(get_user_data_dir(), "mods")

    def get_config_path(self):
        return os.path.join(get_user_data_dir(), "mods_config.json")

    def append_log(self, text):
        self.logs.append(str(text))
        if len(self.logs) > 60:
            self.logs = self.logs[-60:]

    def _community_mods_dir(self):
        bases = []
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            bases.append(os.path.join(meipass, "community_mods"))
        bases.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "community_mods"))
        for b in bases:
            if os.path.isdir(b):
                return b
        return ""

    def _ensure_storage(self):
        mods_dir = self.get_mods_dir()
        cfg_path = self.get_config_path()
        os.makedirs(mods_dir, exist_ok=True)
        existing_py = [f for f in os.listdir(mods_dir) if f.endswith(".py") and not f.startswith("_")]
        cfg_changed = False
        if not self._examples_seeded and not os.path.exists(cfg_path) and not existing_py:
            self._examples_seeded = True
            for fname, src in (
                ("quick_boost_example.py", _EXAMPLE_QUICK_BOOST),
                ("custom_relic_example.py", _EXAMPLE_CUSTOM_CONTENT),
            ):
                with open(os.path.join(mods_dir, fname), "w", encoding="utf-8") as fh:
                    fh.write(src)
                self.enabled_map[fname] = False
            cfg_changed = True
        else:
            self._load_config()

        comm_dir = self._community_mods_dir()
        if comm_dir:
            for fn in sorted(os.listdir(comm_dir)):
                if not (fn.endswith(".py") and not fn.startswith("_")):
                    continue
                src_p = os.path.join(comm_dir, fn)
                dst_p = os.path.join(mods_dir, fn)
                if not os.path.exists(dst_p):
                    try:
                        shutil.copy2(src_p, dst_p)
                        if fn not in self.enabled_map:
                            self.enabled_map[fn] = True
                            cfg_changed = True
                    except Exception:
                        pass
                elif fn not in self.enabled_map:
                    self.enabled_map[fn] = True
                    cfg_changed = True

        if cfg_changed:
            self._save_config()

    def _load_config(self):
        cfg_path = self.get_config_path()
        data = safe_read_json(cfg_path, default=None, expected_type=dict, try_backups=True, self_heal=True)
        if isinstance(data, dict) and isinstance(data.get("enabled"), dict):
            self.enabled_map = {str(k): bool(v) for k, v in data["enabled"].items()}

    def _save_config(self):
        cfg_path = self.get_config_path()
        atomic_write_json(
            cfg_path,
            {"enabled": self.enabled_map},
            indent=2,
            ensure_ascii=False,
            backup=True,
            verify=True,
        )

    def _purge_mod_content(self):
        if self._mod_item_ids:
            id_set = set(self._mod_item_ids)
            items.ITEM_POOL_65[:] = [it for it in items.ITEM_POOL_65 if it.get("id") not in id_set]
            for iid in id_set:
                items.ITEM_REGISTRY.pop(iid, None)
            self._mod_item_ids.clear()
        if self._mod_hero_ids:
            hid_set = set(self._mod_hero_ids)
            heroes.HERO_ROSTER[:] = [h for h in heroes.HERO_ROSTER if h.get("id") not in hid_set]
            self._mod_hero_ids.clear()

    def scan_mods(self):
        self._ensure_storage()
        mods_dir = self.get_mods_dir()
        files = sorted(f for f in os.listdir(mods_dir) if f.endswith(".py") and not f.startswith("_"))
        loaded_lookup = {m["filename"]: m for m in self.loaded_mods}
        out = []
        for fn in files:
            meta = loaded_lookup.get(fn, {})
            out.append(
                {
                    "filename": fn,
                    "enabled": bool(self.enabled_map.get(fn, False)),
                    "loaded": fn in loaded_lookup,
                    "error": self.mod_errors.get(fn, ""),
                    "title": meta.get("title", fn[:-3]),
                    "desc": meta.get("desc", ""),
                }
            )
        return out

    def set_enabled(self, filename, enabled):
        self._ensure_storage()
        self.enabled_map[str(filename)] = bool(enabled)
        self._save_config()
        self.reload_all()

    def reload_all(self):
        self._ensure_storage()
        self._purge_mod_content()
        self.loaded_mods = []
        self.mod_errors = {}
        self._runtime_faulty_updates.clear()

        mods_dir = self.get_mods_dir()
        files = sorted(f for f in os.listdir(mods_dir) if f.endswith(".py") and not f.startswith("_"))
        lang = get_lang()
        for fn in files:
            if not self.enabled_map.get(fn, False):
                continue
            path = os.path.join(mods_dir, fn)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    code = fh.read()
                ns = {
                    "__file__": path,
                    "__name__": f"darkvault_mod_{os.path.splitext(fn)[0]}",
                }
                compiled = compile(code, path, "exec")
                exec(compiled, ns, ns)
                api = ModAPI(self, fn)
                if callable(ns.get("on_register")):
                    ns["on_register"](api)
                meta_dict = ns.get("MOD_META") if isinstance(ns.get("MOD_META"), dict) else {}
                title = ns.get("MOD_NAME") or (
                    meta_dict.get("name_en", meta_dict.get("name")) if lang == "en" else meta_dict.get("name")
                ) or fn[:-3]
                desc = ns.get("MOD_DESC") or (
                    meta_dict.get("description_en", meta_dict.get("description")) if lang == "en" else meta_dict.get("description")
                ) or ""
                self.loaded_mods.append(
                    {
                        "filename": fn,
                        "title": str(title),
                        "desc": str(desc),
                        "ns": ns,
                        "api": api,
                    }
                )
            except Exception as exc:
                self.mod_errors[fn] = f"{type(exc).__name__}: {exc}"
                self.append_log(f"ERROR in {fn}: {self.mod_errors[fn]}")
                self.append_log(traceback.format_exc(limit=2).strip())

    def read_mod(self, filename):
        self._ensure_storage()
        safe = _sanitize_mod_filename(filename)
        path = os.path.join(self.get_mods_dir(), safe)
        if not os.path.isfile(path):
            return ""
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return fh.read()
        except Exception:
            return ""

    def save_mod(self, filename, code_text, enable=None):
        self._ensure_storage()
        safe = _sanitize_mod_filename(filename)
        path = os.path.join(self.get_mods_dir(), safe)
        tmp_path = path + ".tmp"
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(tmp_path, "w", encoding="utf-8") as fh:
                fh.write(code_text)
                fh.flush()
                try:
                    os.fsync(fh.fileno())
                except OSError:
                    pass
            try:
                os.replace(tmp_path, path)
            except OSError:
                shutil.move(tmp_path, path)
        except Exception:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass
            raise
        if enable is not None:
            self.enabled_map[safe] = bool(enable)
            self._save_config()
        self.reload_all()
        return safe

    def create_new_mod(self, name_hint="my_mod", initial_code=None):
        self._ensure_storage()
        mods_dir = self.get_mods_dir()
        base = _sanitize_mod_filename(name_hint)[:-3]
        candidate = f"{base}.py"
        idx = 2
        while os.path.exists(os.path.join(mods_dir, candidate)):
            candidate = f"{base}_{idx}.py"
            idx += 1
        code = initial_code if initial_code is not None else _NEW_MOD_TEMPLATE.format(title=candidate[:-3])
        target_path = os.path.join(mods_dir, candidate)
        tmp_path = target_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as fh:
            fh.write(code)
            fh.flush()
            try:
                os.fsync(fh.fileno())
            except OSError:
                pass
        try:
            os.replace(tmp_path, target_path)
        except OSError:
            shutil.move(tmp_path, target_path)
        self.enabled_map[candidate] = False
        self._save_config()
        return candidate

    def delete_mod(self, filename):
        self._ensure_storage()
        safe = _sanitize_mod_filename(filename)
        path = os.path.join(self.get_mods_dir(), safe)
        removed = False
        if os.path.isfile(path):
            os.remove(path)
            removed = True
        self.enabled_map.pop(safe, None)
        self.mod_errors.pop(safe, None)
        self._save_config()
        self.reload_all()
        return removed

    def read_source_file(self, fname):
        if fname not in SOURCE_FILE_LIST:
            return f"# Source file '{fname}' is not available."
        bases = []
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            bases.append(meipass)
        bases.append(os.path.dirname(os.path.abspath(__file__)))
        for base in bases:
            cand = os.path.join(base, fname)
            if os.path.isfile(cand):
                try:
                    with open(cand, "r", encoding="utf-8") as fh:
                        return fh.read()
                except Exception as exc:
                    return f"# Failed to read {fname}: {exc}"
        return f"# Could not locate {fname}."

    def _invoke_hook(self, mod, hook_name, ctx):
        fn_hook = mod["ns"].get(hook_name)
        if not callable(fn_hook):
            return
        try:
            sig = inspect.signature(fn_hook)
            params = list(sig.parameters.keys())
            args = []
            for p_name in params:
                if p_name == "api":
                    args.append(mod["api"])
                elif p_name == "game":
                    args.append(ctx.get("game"))
                elif p_name in ("player", "p1"):
                    args.append(ctx.get("player"))
                elif p_name == "room":
                    args.append(ctx.get("room"))
                elif p_name in ("floor_num", "floor", "level"):
                    args.append(ctx.get("floor_num", 1))
                elif p_name == "dt":
                    args.append(ctx.get("dt", 1.0))
                else:
                    args.append(ctx.get(p_name, mod["api"]))
            fn_hook(*args)
        except Exception as exc:
            self.mod_errors[mod["filename"]] = f"{hook_name}: {type(exc).__name__}: {exc}"
            self.append_log(self.mod_errors[mod["filename"]])
            if hook_name == "on_update":
                self._runtime_faulty_updates.add(mod["filename"])

    def dispatch_player_init(self, player):
        if player is None:
            return
        for mod in self.loaded_mods:
            self._invoke_hook(mod, "on_player_init", {"player": player})

    def dispatch_new_floor(self, floor_num, player, player2=None):
        for p in (player, player2):
            if p is None:
                continue
            for mod in self.loaded_mods:
                self._invoke_hook(mod, "on_new_floor", {"player": p, "floor_num": int(floor_num)})

    def dispatch_room_clear(self, room, player, player2=None):
        if room is None:
            return
        for p in (player, player2):
            if p is None:
                continue
            for mod in self.loaded_mods:
                self._invoke_hook(mod, "on_room_clear", {"player": p, "room": room})

    def dispatch_run_start(self, game, player):
        for mod in self.loaded_mods:
            self._invoke_hook(mod, "on_run_start", {"game": game, "player": player})

    def dispatch_room_enter(self, game, room, player):
        for mod in self.loaded_mods:
            self._invoke_hook(mod, "on_room_enter", {"game": game, "room": room, "player": player})

    def dispatch_update(self, game, dt):
        for mod in self.loaded_mods:
            fname = mod["filename"]
            if fname in self._runtime_faulty_updates:
                continue
            self._invoke_hook(mod, "on_update", {"game": game, "dt": dt})


mod_manager = ModManager()


class ModBrowserScreen:
    VISIBLE_LIST_ROWS = 10
    LINE_HEIGHT = 20

    def __init__(self):
        self.tab = 0  # 0 = MODS, 1 = SOURCES
        self.selected_mod_idx = 0
        self.selected_src_idx = 0
        self.list_scroll = 0
        self.code_scroll = 0
        self.h_scroll = 0

        self.lines = [""]
        self.cursor_line = 0
        self.cursor_col = 0
        self.sel_anchor = None  # None or (line, col)
        self.dragging_code = False

        self.undo_stack = []
        self.redo_stack = []
        self._clipboard = ""

        self.dirty = False
        self.focus_target = "none"  # "none" | "code" | "find" | "ai_prompt" | "ai_model" | "ai_key" | "ai_key_bar" | "ai_endpoint"
        self.editing_focused = False
        self._text_input_active = False
        self.active_filename = ""
        self.status_msg = ""
        self.status_timer = 0.0
        self.cursor_blink = 0.0

        self.syntax_ok = True
        self.syntax_msg = ""
        self.syntax_err_line = 0

        self.find_open = False
        self.find_query = ""
        self.find_matches = []
        self.find_match_idx = -1

        self.ai_open = not settings.is_phone_layout(False)
        self.ai_cfg_mode = False
        self.ai_action = "generate"
        self.ai_prompt = ""
        self.ai_out_scroll = 0
        self.ai_provider = ai_agent_client.provider
        self.ai_model_buf = ai_agent_client.model
        self.ai_key_buf = ai_agent_client.api_key
        self.ai_endpoint_buf = ai_agent_client.endpoint
        self.ai_show_key = False

        self.hover_btn = ""
        self.hover_row = -1
        self.contacts_modal_open = False
        self._load_active_file(force=True)

    def on_enter(self):
        self.ai_provider = ai_agent_client.provider
        self.ai_model_buf = ai_agent_client.model
        self.ai_key_buf = ai_agent_client.api_key
        self.ai_endpoint_buf = ai_agent_client.endpoint
        self.refresh_list(keep_selection=True)
        self._sync_text_input()
        self._sync_scrap()

    def on_exit(self):
        self.contacts_modal_open = False
        self._set_focus("none")

    def _sync_scrap(self):
        try:
            if hasattr(pygame, "scrap") and not pygame.scrap.get_init():
                pygame.scrap.init()
        except Exception:
            pass

    def _copy_clipboard(self, text):
        if text is None:
            return
        self._clipboard = str(text)
        try:
            self._sync_scrap()
            if hasattr(pygame, "scrap") and pygame.scrap.get_init():
                scrap_type = getattr(pygame, "SCRAP_TEXT", "text/plain")
                pygame.scrap.put(scrap_type, self._clipboard.encode("utf-8"))
        except Exception:
            pass
        for cmd in (["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]):
            try:
                if shutil.which(cmd[0]):
                    subprocess.run(cmd, input=self._clipboard.encode("utf-8"), timeout=0.6, check=False)
                    break
            except Exception:
                pass

    def _paste_clipboard(self):
        try:
            self._sync_scrap()
            if hasattr(pygame, "scrap") and pygame.scrap.get_init():
                scrap_type = getattr(pygame, "SCRAP_TEXT", "text/plain")
                raw = pygame.scrap.get(scrap_type)
                if raw:
                    decoded = raw.decode("utf-8", errors="ignore").replace("\x00", "")
                    if decoded:
                        self._clipboard = decoded
                        return decoded
        except Exception:
            pass
        for cmd in (["wl-paste", "-n"], ["xclip", "-o", "-selection", "clipboard"], ["xsel", "--clipboard", "--output"]):
            try:
                if shutil.which(cmd[0]):
                    res = subprocess.run(cmd, capture_output=True, timeout=0.6, check=False)
                    txt = res.stdout.decode("utf-8", errors="ignore").replace("\x00", "")
                    if txt:
                        self._clipboard = txt
                        return txt
            except Exception:
                pass
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            txt = root.clipboard_get()
            root.destroy()
            if txt:
                self._clipboard = str(txt)
                return self._clipboard
        except Exception:
            pass
        return self._clipboard

    def _set_focus(self, target):
        if target == "code" and self.tab != 0:
            target = "none"
        self.focus_target = target
        self.editing_focused = target == "code"
        self._sync_text_input()

    def _sync_text_input(self):
        want = self.focus_target != "none"
        try:
            if want:
                pygame.key.start_text_input()
                self._text_input_active = True
            else:
                pygame.key.stop_text_input()
                self._text_input_active = False
        except Exception:
            self._text_input_active = False

    def _set_status(self, msg, sec=4.0):
        self.status_msg = str(msg)
        self.status_timer = sec * 60.0

    def _refresh_syntax(self):
        if self.tab != 0 or not self.active_filename:
            self.syntax_ok, self.syntax_msg, self.syntax_err_line = True, "", 0
            return
        code = "\n".join(self.lines)
        self.syntax_ok, self.syntax_msg, self.syntax_err_line = validate_python_syntax(code)

    def _push_undo(self):
        snap = (list(self.lines), self.cursor_line, self.cursor_col, self.sel_anchor)
        if self.undo_stack and self.undo_stack[-1][0] == snap[0]:
            return
        self.undo_stack.append(snap)
        if len(self.undo_stack) > 120:
            self.undo_stack = self.undo_stack[-120:]
        self.redo_stack.clear()

    def _undo(self):
        if self.tab != 0 or not self.undo_stack:
            return
        cur = (list(self.lines), self.cursor_line, self.cursor_col, self.sel_anchor)
        self.redo_stack.append(cur)
        lines, cl, cc, anch = self.undo_stack.pop()
        self.lines = list(lines) if lines else [""]
        self.cursor_line = int(clamp(cl, 0, len(self.lines) - 1))
        self.cursor_col = int(clamp(cc, 0, len(self.lines[self.cursor_line])))
        self.sel_anchor = anch
        self.dirty = True
        self._refresh_syntax()
        self._ensure_cursor_visible()

    def _redo(self):
        if self.tab != 0 or not self.redo_stack:
            return
        cur = (list(self.lines), self.cursor_line, self.cursor_col, self.sel_anchor)
        self.undo_stack.append(cur)
        lines, cl, cc, anch = self.redo_stack.pop()
        self.lines = list(lines) if lines else [""]
        self.cursor_line = int(clamp(cl, 0, len(self.lines) - 1))
        self.cursor_col = int(clamp(cc, 0, len(self.lines[self.cursor_line])))
        self.sel_anchor = anch
        self.dirty = True
        self._refresh_syntax()
        self._ensure_cursor_visible()

    def _get_selection_bounds(self):
        if self.sel_anchor is None:
            return None
        p1 = self.sel_anchor
        p2 = (self.cursor_line, self.cursor_col)
        if p1 == p2:
            return None
        return (p1, p2) if p1 <= p2 else (p2, p1)

    def _get_selected_text(self):
        bounds = self._get_selection_bounds()
        if not bounds:
            return ""
        (l1, c1), (l2, c2) = bounds
        if l1 == l2:
            return self.lines[l1][c1:c2]
        out = [self.lines[l1][c1:]]
        for li in range(l1 + 1, l2):
            out.append(self.lines[li])
        out.append(self.lines[l2][:c2])
        return "\n".join(out)

    def _delete_selection(self):
        bounds = self._get_selection_bounds()
        if not bounds:
            return False
        (l1, c1), (l2, c2) = bounds
        head = self.lines[l1][:c1]
        tail = self.lines[l2][c2:]
        self.lines[l1 : l2 + 1] = [head + tail]
        self.cursor_line = l1
        self.cursor_col = c1
        self.sel_anchor = None
        self.dirty = True
        return True

    def refresh_list(self, keep_selection=True):
        mods = mod_manager.scan_mods()
        if mods:
            self.selected_mod_idx = int(clamp(self.selected_mod_idx, 0, len(mods) - 1))
        else:
            self.selected_mod_idx = 0
        self.selected_src_idx = int(clamp(self.selected_src_idx, 0, len(SOURCE_FILE_LIST) - 1))
        if not keep_selection or not self.active_filename:
            self._load_active_file(force=True)

    def _current_entries(self):
        if self.tab == 0:
            return mod_manager.scan_mods()
        return [{"filename": fn} for fn in SOURCE_FILE_LIST]

    def _selected_idx(self):
        return self.selected_mod_idx if self.tab == 0 else self.selected_src_idx

    def _set_selected_idx(self, idx):
        entries = self._current_entries()
        if not entries:
            idx = 0
        else:
            idx = int(clamp(idx, 0, len(entries) - 1))
        if self.tab == 0:
            self.selected_mod_idx = idx
        else:
            self.selected_src_idx = idx
        if idx < self.list_scroll:
            self.list_scroll = idx
        elif idx >= self.list_scroll + self.VISIBLE_LIST_ROWS:
            self.list_scroll = idx - self.VISIBLE_LIST_ROWS + 1
        self._load_active_file(force=True)

    def _load_active_file(self, force=False):
        entries = self._current_entries()
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.sel_anchor = None
        if not entries:
            self.active_filename = ""
            self.lines = ["# No mods yet. Click [+ NEW MOD]."]
            self.cursor_line = 0
            self.cursor_col = 0
            self.code_scroll = 0
            self.dirty = False
            self._refresh_syntax()
            return
        idx = int(clamp(self._selected_idx(), 0, len(entries) - 1))
        fn = entries[idx]["filename"]
        if not force and fn == self.active_filename:
            return
        self.active_filename = fn
        if self.tab == 0:
            content = mod_manager.read_mod(fn)
        else:
            content = mod_manager.read_source_file(fn)
        raw_lines = content.splitlines()
        self.lines = raw_lines if raw_lines else [""]
        self.cursor_line = 0
        self.cursor_col = 0
        self.code_scroll = 0
        self.h_scroll = 0
        self.dirty = False
        self._refresh_syntax()
        self._update_find_matches()

    def _visible_code_lines(self):
        cbox = self._rects()["code_box"]
        top_pad = 36 if self.find_open else 10
        return max(10, (cbox.h - top_pad - 10) // self.LINE_HEIGHT)

    def _visible_cols(self):
        cbox = self._rects()["code_box"]
        _, cw = _get_mono_font(14)
        return max(28, (cbox.w - 64) // max(6, cw))

    def _ensure_cursor_visible(self):
        self.cursor_line = int(clamp(self.cursor_line, 0, max(0, len(self.lines) - 1)))
        self.cursor_col = int(clamp(self.cursor_col, 0, len(self.lines[self.cursor_line])))
        vis_lines = self._visible_code_lines()
        if self.cursor_line < self.code_scroll:
            self.code_scroll = self.cursor_line
        elif self.cursor_line >= self.code_scroll + vis_lines:
            self.code_scroll = self.cursor_line - vis_lines + 1
        self.code_scroll = int(clamp(self.code_scroll, 0, max(0, len(self.lines) - vis_lines)))
        max_cols = self._visible_cols() - 2
        if self.cursor_col < self.h_scroll:
            self.h_scroll = self.cursor_col
        elif self.cursor_col > self.h_scroll + max_cols:
            self.h_scroll = self.cursor_col - max_cols

    def _move_cursor(self, new_line, new_col, selecting=False):
        if selecting:
            if self.sel_anchor is None:
                self.sel_anchor = (self.cursor_line, self.cursor_col)
        else:
            self.sel_anchor = None
        self.cursor_line = int(clamp(new_line, 0, max(0, len(self.lines) - 1)))
        self.cursor_col = int(clamp(new_col, 0, len(self.lines[self.cursor_line])))
        self._ensure_cursor_visible()

    def _insert_text(self, text, record_undo=True, auto_indent=False):
        if self.tab != 0 or not self.active_filename or not text:
            return
        if record_undo:
            self._push_undo()
        self._delete_selection()
        self.dirty = True
        for ch in text:
            if ch == "\r":
                continue
            if ch == "\n":
                cur = self.lines[self.cursor_line]
                before = cur[: self.cursor_col]
                after = cur[self.cursor_col :]
                self.lines[self.cursor_line] = before
                indent = ""
                if auto_indent:
                    m = re.match(r"^[ \t]*", before)
                    indent = m.group(0).replace("\t", "    ") if m else ""
                    if before.rstrip().endswith(":"):
                        indent += "    "
                self.lines.insert(self.cursor_line + 1, indent + after)
                self.cursor_line += 1
                self.cursor_col = len(indent)
            elif ch == "\t":
                cur = self.lines[self.cursor_line]
                self.lines[self.cursor_line] = cur[: self.cursor_col] + "    " + cur[self.cursor_col :]
                self.cursor_col += 4
            elif ch.isprintable():
                cur = self.lines[self.cursor_line]
                self.lines[self.cursor_line] = cur[: self.cursor_col] + ch + cur[self.cursor_col :]
                self.cursor_col += 1
        self._refresh_syntax()
        self._update_find_matches()
        self._ensure_cursor_visible()

    def _indent_selection(self, unindent=False):
        if self.tab != 0 or not self.active_filename:
            return
        bounds = self._get_selection_bounds()
        self._push_undo()
        self.dirty = True
        if not bounds:
            if not unindent:
                cur = self.lines[self.cursor_line]
                self.lines[self.cursor_line] = cur[: self.cursor_col] + "    " + cur[self.cursor_col :]
                self.cursor_col += 4
            else:
                cur = self.lines[self.cursor_line]
                rem = 4 if cur.startswith("    ") else (len(cur) - len(cur.lstrip(" ")))
                rem = min(4, rem)
                if rem > 0:
                    self.lines[self.cursor_line] = cur[rem:]
                    self.cursor_col = max(0, self.cursor_col - rem)
        else:
            (l1, _), (l2, c2) = bounds
            end_l = l2 - 1 if (l2 > l1 and c2 == 0) else l2
            for li in range(l1, end_l + 1):
                cur = self.lines[li]
                if not unindent:
                    self.lines[li] = "    " + cur
                else:
                    rem = 4 if cur.startswith("    ") else (len(cur) - len(cur.lstrip(" ")))
                    rem = min(4, rem)
                    self.lines[li] = cur[rem:]
            if self.cursor_line in range(l1, end_l + 1):
                self.cursor_col = min(len(self.lines[self.cursor_line]), self.cursor_col + (-4 if unindent else 4))
                self.cursor_col = max(0, self.cursor_col)
        self._refresh_syntax()
        self._ensure_cursor_visible()

    def _toggle_comment(self):
        if self.tab != 0 or not self.active_filename:
            return
        bounds = self._get_selection_bounds()
        self._push_undo()
        self.dirty = True
        if bounds:
            (l1, _), (l2, c2) = bounds
            end_l = l2 - 1 if (l2 > l1 and c2 == 0) else l2
        else:
            l1 = end_l = self.cursor_line
        non_empty = [self.lines[li] for li in range(l1, end_l + 1) if self.lines[li].strip()]
        all_commented = bool(non_empty) and all(ln.lstrip().startswith("#") for ln in non_empty)
        for li in range(l1, end_l + 1):
            cur = self.lines[li]
            if all_commented:
                self.lines[li] = re.sub(r"^([ \t]*)#\s?", r"\1", cur, count=1)
            elif cur.strip():
                self.lines[li] = "# " + cur
        self.cursor_col = int(clamp(self.cursor_col, 0, len(self.lines[self.cursor_line])))
        self._refresh_syntax()
        self._ensure_cursor_visible()

    def _update_find_matches(self):
        q = (self.find_query or "").lower()
        self.find_matches = []
        if not q:
            self.find_match_idx = -1
            return
        qlen = len(q)
        for li, line in enumerate(self.lines):
            low = line.lower()
            pos = 0
            while True:
                idx = low.find(q, pos)
                if idx < 0:
                    break
                self.find_matches.append((li, idx, idx + qlen))
                pos = idx + max(1, qlen)
        if not self.find_matches:
            self.find_match_idx = -1
        else:
            self.find_match_idx = int(clamp(self.find_match_idx, 0, len(self.find_matches) - 1))

    def _jump_find_match(self, step=1):
        if not self.find_matches:
            self._update_find_matches()
        if not self.find_matches:
            return
        self.find_match_idx = (self.find_match_idx + step) % len(self.find_matches)
        li, c1, c2 = self.find_matches[self.find_match_idx]
        self.sel_anchor = (li, c1)
        self.cursor_line = li
        self.cursor_col = c2
        self._ensure_cursor_visible()

    def _insert_snippet(self, kind):
        if self.tab != 0:
            return
        if not self.active_filename:
            fn = mod_manager.create_new_mod("custom_mod")
            self.refresh_list(keep_selection=False)
            self._select_mod_by_name(fn)
        snippet = ""
        if kind == "hero":
            snippet = (
                "\n# Custom Hero snippet\n"
                "def on_register(api):\n"
                "    api.add_hero({\n"
                "        'id': 'custom_hero',\n"
                "        'name': 'Тень Мода',\n"
                "        'name_en': 'Mod Shade',\n"
                "        'title': 'Custom Hero',\n"
                "        'desc': 'Added via Code Editor!',\n"
                "        'hp': 6, 'max_hp': 6, 'damage': 4.5, 'speed': 4.4,\n"
                "    })\n"
            )
        elif kind == "item":
            snippet = (
                "\n# Custom Relic snippet\n"
                "def on_register(api):\n"
                "    api.add_item({\n"
                "        'id': 'mod_relic',\n"
                "        'name': 'Реликвия Мода',\n"
                "        'name_en': 'Mod Relic',\n"
                "        'desc': 'Custom relic artifact',\n"
                "        'type': 'passive', 'icon': 'star',\n"
                "    })\n"
            )
        elif kind == "buff":
            snippet = (
                "\n# Run start buff snippet\n"
                "def on_run_start(api, game, player):\n"
                "    player.damage += 1.5\n"
                "    player.coins += 10\n"
            )
        self.sel_anchor = None
        self.cursor_line = len(self.lines) - 1
        self.cursor_col = len(self.lines[self.cursor_line])
        self._insert_text(snippet)
        self._set_focus("code")
        self._set_status("Snippet inserted — click SAVE & APPLY", 3.5)

    def _select_mod_by_name(self, fname):
        mods = mod_manager.scan_mods()
        for i, m in enumerate(mods):
            if m["filename"] == fname:
                self._set_selected_idx(i)
                return

    def _save_current_mod(self, enable=True):
        if self.tab != 0 or not self.active_filename:
            return
        code = "\n".join(self.lines) + "\n"
        self._refresh_syntax()
        mod_manager.save_mod(self.active_filename, code, enable=enable)
        self.dirty = False
        err = mod_manager.mod_errors.get(self.active_filename, "")
        if err:
            self._set_status(err[:76], 6.0)
        else:
            lang = get_lang()
            self._set_status(
                f"Сохранено и применено: {self.active_filename}" if lang == "ru" else f"Saved & applied: {self.active_filename}",
                3.5,
            )

    def _apply_ai_result(self, mode="replace"):
        txt = (ai_agent_client.last_response or "").strip()
        if not txt:
            return
        lang = get_lang()
        if mode == "new_mod":
            hint = "ai_mod"
            m = re.search(r'MOD_NAME\s*=\s*["\']([^"\']+)["\']', txt)
            if m:
                hint = m.group(1)
            fn = mod_manager.create_new_mod(hint, initial_code=txt + "\n")
            self.tab = 0
            self.refresh_list(keep_selection=False)
            self._select_mod_by_name(fn)
            self._set_focus("code")
            self._set_status(f"AI: создан {fn}" if lang == "ru" else f"AI: created {fn}", 4.0)
            return

        if self.tab != 0 or not self.active_filename:
            self._apply_ai_result(mode="new_mod")
            if mode == "apply_run":
                self._save_current_mod(enable=True)
            return

        self._push_undo()
        self.lines = txt.splitlines() or [""]
        self.cursor_line = 0
        self.cursor_col = 0
        self.code_scroll = 0
        self.sel_anchor = None
        self.dirty = True
        self._refresh_syntax()
        self._update_find_matches()
        if mode == "apply_run":
            self._save_current_mod(enable=True)
        else:
            self._set_status("AI код вставлен в редактор" if lang == "ru" else "AI code applied to editor", 3.5)

    def _sync_ai_key_from_buf(self, persist=False):
        raw_key = str(self.ai_key_buf or "").strip()
        if raw_key:
            detected = detect_provider_from_key(raw_key, self.ai_provider)
            if detected != self.ai_provider and raw_key.startswith(("AIza", "sk-ant-")):
                prev_def = DEFAULT_MODELS.get(self.ai_provider, "")
                self.ai_provider = detected
                if not self.ai_model_buf.strip() or self.ai_model_buf.strip() == prev_def:
                    self.ai_model_buf = DEFAULT_MODELS.get(detected, self.ai_model_buf)
        ai_agent_client.set_api_key(
            raw_key,
            provider=self.ai_provider,
            model=self.ai_model_buf,
            endpoint=self.ai_endpoint_buf,
            persist=bool(persist and raw_key),
        )

    def _run_ai_action(self):
        lang = get_lang()
        if ai_agent_client.busy:
            ai_agent_client.cancel(lang=lang)
            return
        self._sync_ai_key_from_buf(persist=bool(self.ai_key_buf.strip()))
        if not ai_agent_client.api_key and self.ai_provider != "custom":
            self.ai_cfg_mode = True
            self._set_focus("ai_key")
            msg = "Введите API ключ (Gemini / OpenAI / Claude)" if lang == "ru" else "Enter your API key (Gemini / OpenAI / Claude)"
            ai_agent_client.error_text = msg
            ai_agent_client.status_text = msg
            self._set_status(msg, 4.0)
            return
        code_txt = "\n".join(self.lines)
        diag = self.syntax_msg or mod_manager.mod_errors.get(self.active_filename, "")
        prompt_txt = self.ai_prompt.strip()
        if not prompt_txt:
            if self.ai_action == "fix":
                prompt_txt = "Fix all errors and harden this DarkVault mod."
            elif self.ai_action == "explain":
                prompt_txt = "Explain how this code works and highlight potential issues."
            elif self.ai_action == "edit":
                prompt_txt = "Cleanly enhance this mod with better mechanics and safety checks."
            else:
                self._set_status(tr("ai_prompt_hint"), 3.0)
                self._set_focus("ai_prompt")
                return
        self.ai_out_scroll = 0
        ai_agent_client.start_request(
            prompt_txt,
            action=self.ai_action,
            current_code=code_txt,
            filename=self.active_filename,
            diagnostics=diag,
            lang=lang,
            api_key=self.ai_key_buf,
            provider=self.ai_provider,
            model=self.ai_model_buf,
            endpoint=self.ai_endpoint_buf,
        )

    def _rects(self):
        vw = get_view_width()
        ox = get_world_offset_x()
        px = max(22, ox // 2 + 22)
        pw = vw - px * 2
        py = 24
        ph = 672

        top_y = py + 12
        tool_y = py + 58
        cont_y = py + 98

        # Sidebar on left
        sb_x = px + 14
        sb_w = 246
        # Optional AI dock on right
        ai_w = 376 if self.ai_open else 0
        ai_gap = 12 if self.ai_open else 0
        ai_x = px + pw - 14 - ai_w
        # Code area in center
        ed_x = sb_x + sb_w + 12
        ed_w = (px + pw - 14 - ai_w - ai_gap) - ed_x

        back_w = 118
        ai_tog_w = 110
        contacts_w = 116
        right_end = px + pw - 14

        cbox_y = cont_y + 40
        cbox_h = 436
        act_y = cbox_y + cbox_h + 10

        out = {
            "panel": pygame.Rect(px, py, pw, ph),
            # Row 1: Right utility buttons (Title + developer subtitle are cleanly on the left)
            "btn_contacts": pygame.Rect(right_end - back_w - ai_tog_w - contacts_w - 16, top_y, contacts_w, 32),
            "ai_toggle": pygame.Rect(right_end - back_w - ai_tog_w - 8, top_y, ai_tog_w, 32),
            "back": pygame.Rect(right_end - back_w, top_y, back_w, 32),
            # Row 2: Tabs above sidebar + Editor toolbar across full right width
            "tab_mods": pygame.Rect(sb_x, tool_y, 118, 30),
            "tab_sources": pygame.Rect(sb_x + 124, tool_y, 122, 30),
            "btn_find": pygame.Rect(ed_x, tool_y, 140, 30),
            "btn_undo": pygame.Rect(ed_x + 146, tool_y, 84, 30),
            "btn_redo": pygame.Rect(ed_x + 236, tool_y, 84, 30),
            "btn_copy": pygame.Rect(ed_x + 326, tool_y, 82, 30),
            "btn_paste": pygame.Rect(ed_x + 414, tool_y, 82, 30),
            "reload": pygame.Rect(right_end - 114, tool_y, 114, 30),

            "scroll_up": pygame.Rect(sb_x + sb_w - 30, cont_y, 28, 22),
            "scroll_dn": pygame.Rect(sb_x + sb_w - 30, cont_y + 412, 28, 22),
            "new_mod": pygame.Rect(sb_x, cont_y + 444, sb_w, 38),

            "info_bar": pygame.Rect(ed_x, cont_y, ed_w, 34),
            "code_box": pygame.Rect(ed_x, cbox_y, ed_w - 26, cbox_h),
            "find_input": pygame.Rect(ed_x + 8, cbox_y + 6, max(120, ed_w - 224), 26),
            "find_prev": pygame.Rect(ed_x + ed_w - 208, cbox_y + 6, 46, 26),
            "find_next": pygame.Rect(ed_x + ed_w - 156, cbox_y + 6, 46, 26),
            "find_close": pygame.Rect(ed_x + ed_w - 104, cbox_y + 6, 32, 26),
            "code_up": pygame.Rect(ed_x + ed_w - 22, cbox_y + 2, 22, 26),
            "code_dn": pygame.Rect(ed_x + ed_w - 22, cbox_y + cbox_h - 28, 22, 26),
            "code_sb_track": pygame.Rect(ed_x + ed_w - 20, cbox_y + 32, 18, cbox_h - 64),

            "btn_save": pygame.Rect(ed_x, act_y, 138, 36),
            "btn_toggle": pygame.Rect(ed_x + 144, act_y, 108, 36),
            "btn_del": pygame.Rect(ed_x + 258, act_y, 92, 36),
            "snip_hero": pygame.Rect(ed_x + 358, act_y, 78, 36),
            "snip_item": pygame.Rect(ed_x + 442, act_y, 78, 36),
            "snip_buff": pygame.Rect(ed_x + 526, act_y, 78, 36),
            "copy_mod": pygame.Rect(ed_x, act_y, 260, 36),
        }

        # Ensure Row 2 toolbar buttons never overlap each other or reload
        if out["btn_paste"].right > out["reload"].left - 8:
            t_specs = [("btn_find", 0.24), ("btn_undo", 0.14), ("btn_redo", 0.14), ("btn_copy", 0.14), ("btn_paste", 0.14), ("reload", 0.20)]
            avail_t = (right_end - ed_x) - 6 * (len(t_specs) - 1)
            tx = ed_x
            for key, frac in t_specs:
                bw = int(avail_t * frac)
                out[key] = pygame.Rect(tx, tool_y, bw, 30)
                tx += bw + 6

        if out["snip_buff"].right > ed_x + ed_w:
            widths = [("btn_save", 0.24), ("btn_toggle", 0.19), ("btn_del", 0.15), ("snip_hero", 0.14), ("snip_item", 0.14), ("snip_buff", 0.14)]
            cx = ed_x
            gap = 6
            avail = ed_w - gap * (len(widths) - 1)
            for key, frac in widths:
                bw = int(avail * frac)
                out[key] = pygame.Rect(cx, act_y, bw, 36)
                cx += bw + gap

        if self.ai_open:
            ay = cont_y
            ah = ph - 114
            out["ai_panel"] = pygame.Rect(ai_x, ay, ai_w, ah)
            out["ai_cfg_btn"] = pygame.Rect(ai_x + ai_w - 86, ay + 8, 76, 26)
            cfg_y = ay + 48
            for pi, prov in enumerate(PROVIDER_CHOICES):
                out[f"ai_prov_{prov}"] = pygame.Rect(ai_x + 12 + (pi % 3) * 118, cfg_y + (pi // 3) * 32, 112, 26)
            out["ai_model"] = pygame.Rect(ai_x + 12, cfg_y + 88, ai_w - 24, 30)
            out["ai_key"] = pygame.Rect(ai_x + 12, cfg_y + 144, ai_w - 134, 30)
            out["ai_key_show"] = pygame.Rect(ai_x + ai_w - 116, cfg_y + 144, 50, 30)
            out["ai_key_paste"] = pygame.Rect(ai_x + ai_w - 60, cfg_y + 144, 48, 30)
            out["ai_endpoint"] = pygame.Rect(ai_x + 12, cfg_y + 200, ai_w - 24, 30)
            out["ai_save_cfg"] = pygame.Rect(ai_x + 12, cfg_y + 250, ai_w - 24, 36)
            act_w = (ai_w - 36) // 4
            for idx, act_key in enumerate(("generate", "edit", "fix", "explain")):
                out[f"ai_act_{act_key}"] = pygame.Rect(ai_x + 12 + idx * (act_w + 4), ay + 42, act_w, 26)
            out["ai_prompt"] = pygame.Rect(ai_x + 12, ay + 74, ai_w - 24, 76)
            out["ai_run"] = pygame.Rect(ai_x + 12, ay + 156, ai_w - 144, 30)
            out["ai_prompt_paste"] = pygame.Rect(ai_x + ai_w - 126, ay + 156, 60, 30)
            out["ai_prompt_clr"] = pygame.Rect(ai_x + ai_w - 60, ay + 156, 48, 30)
            out["ai_key_bar"] = pygame.Rect(ai_x + 12, ay + 192, ai_w - 96, 24)
            out["ai_key_save"] = pygame.Rect(ai_x + ai_w - 78, ay + 192, 66, 24)
            out["ai_output"] = pygame.Rect(ai_x + 12, ay + 238, ai_w - 24, ah - 288)
            bw = (ai_w - 36) // 3
            oy_b = ay + ah - 42
            out["ai_apply"] = pygame.Rect(ai_x + 12, oy_b, bw, 32)
            out["ai_new_mod"] = pygame.Rect(ai_x + 18 + bw, oy_b, bw, 32)
            out["ai_apply_run"] = pygame.Rect(ai_x + 24 + bw * 2, oy_b, bw, 32)

        # Editor Info Modal Rects
        mw, mh = 580, 336
        mx = vw // 2 - mw // 2
        my = py + (ph - mh) // 2
        out["contacts_panel"] = pygame.Rect(mx, my, mw, mh)
        out["close_contacts"] = pygame.Rect(mx + mw - 166, my + mh - 56, 144, 36)
        return out

    def _list_row_rects(self, count):
        rc_p = self._rects()["panel"]
        sb_x = rc_p.x + 14
        row_y = rc_p.y + 98 + 26
        return [pygame.Rect(sb_x, row_y + i * 38, 246, 34) for i in range(count)]

    def _pixel_to_code_pos(self, mx, my):
        cbox = self._rects()["code_box"]
        _, cw = _get_mono_font(14)
        top_pad = 36 if self.find_open else 10
        row_off = max(0, (my - (cbox.y + top_pad)) // self.LINE_HEIGHT)
        line = int(clamp(self.code_scroll + row_off, 0, max(0, len(self.lines) - 1)))
        code_x0 = cbox.x + 44
        col_off = max(0, int(round((mx - code_x0) / max(6, float(cw)))))
        col = int(clamp(self.h_scroll + col_off, 0, len(self.lines[line])))
        return line, col

    def update(self, dt=1.0):
        self.cursor_blink += dt
        if self.status_timer > 0:
            self.status_timer = max(0.0, self.status_timer - dt)
        ai_agent_client.check_watchdog(max_sec=32.0, lang=get_lang())

    def _trigger_button(self, bkey):
        lang = get_lang()
        if bkey == "back":
            self.on_exit()
            return "back"
        if bkey == "btn_contacts":
            self.contacts_modal_open = not self.contacts_modal_open
            self._set_focus("none")
        elif bkey == "close_contacts":
            self.contacts_modal_open = False
        elif bkey == "tab_mods":
            self.tab = 0
            self.list_scroll = 0
            self._load_active_file(force=True)
            self._set_focus("none")
        elif bkey == "tab_sources":
            self.tab = 1
            self._set_focus("none")
            self.list_scroll = 0
            self._load_active_file(force=True)
        elif bkey == "ai_toggle":
            self.ai_open = not self.ai_open
            if not self.ai_open and self.focus_target.startswith("ai_"):
                self._set_focus("none")
        elif bkey == "btn_find":
            self.find_open = not self.find_open
            if self.find_open:
                self._set_focus("find")
            elif self.focus_target == "find":
                self._set_focus("code" if self.tab == 0 else "none")
        elif bkey == "find_close":
            self.find_open = False
            self._set_focus("code" if self.tab == 0 else "none")
        elif bkey == "find_prev":
            self._jump_find_match(-1)
        elif bkey == "find_next":
            self._jump_find_match(1)
        elif bkey == "btn_undo":
            self._undo()
        elif bkey == "btn_redo":
            self._redo()
        elif bkey == "btn_copy":
            sel_txt = self._get_selected_text()
            if not sel_txt:
                sel_txt = "\n".join(self.lines)
            self._copy_clipboard(sel_txt)
            self._set_status("Скопировано" if lang == "ru" else "Copied to clipboard", 2.0)
        elif bkey == "btn_paste":
            if self.tab == 0 and self.active_filename:
                pasted = self._paste_clipboard()
                if pasted:
                    self._insert_text(pasted)
                    self._set_focus("code")
        elif bkey == "reload":
            mod_manager.reload_all()
            self.refresh_list(keep_selection=True)
            self._refresh_syntax()
            self._set_status("Моды перезагружены" if lang == "ru" else "Mods reloaded", 3.0)
        elif bkey == "scroll_up":
            self.list_scroll = max(0, self.list_scroll - 2)
        elif bkey == "scroll_dn":
            max_s = max(0, len(self._current_entries()) - self.VISIBLE_LIST_ROWS)
            self.list_scroll = min(max_s, self.list_scroll + 2)
        elif bkey == "code_up":
            self.code_scroll = max(0, self.code_scroll - 5)
        elif bkey == "code_dn":
            vis_l = self._visible_code_lines()
            self.code_scroll = min(max(0, len(self.lines) - vis_l), self.code_scroll + 5)
        elif bkey == "new_mod":
            self.tab = 0
            fn = mod_manager.create_new_mod("my_mod")
            self.refresh_list(keep_selection=False)
            self._select_mod_by_name(fn)
            self._set_focus("code")
            self._set_status(f"Создан {fn}" if lang == "ru" else f"Created {fn}", 3.0)
        elif bkey == "btn_save" and self.tab == 0:
            self._save_current_mod(enable=True)
        elif bkey == "btn_toggle" and self.tab == 0 and self.active_filename:
            cur_en = bool(mod_manager.enabled_map.get(self.active_filename, False))
            if not cur_en and self.dirty:
                self._save_current_mod(enable=True)
            else:
                mod_manager.set_enabled(self.active_filename, not cur_en)
            err = mod_manager.mod_errors.get(self.active_filename, "")
            if err:
                self._set_status(err[:76], 6.0)
        elif bkey == "btn_del" and self.tab == 0 and self.active_filename:
            deleted = self.active_filename
            mod_manager.delete_mod(deleted)
            self.refresh_list(keep_selection=False)
            self._set_status(f"Удалён {deleted}" if lang == "ru" else f"Deleted {deleted}", 3.0)
        elif bkey == "snip_hero":
            self._insert_snippet("hero")
        elif bkey == "snip_item":
            self._insert_snippet("item")
        elif bkey == "snip_buff":
            self._insert_snippet("buff")
        elif bkey == "copy_mod" and self.tab == 1 and self.active_filename:
            stem = os.path.splitext(self.active_filename)[0]
            hdr = (
                f"# Mod based on {self.active_filename}\n"
                f"MOD_NAME = '{stem.title()} Mod'\n"
                "MOD_DESC = 'Custom mod created from source reference'\n\n"
                "def on_register(api):\n"
                f"    # Reference module: api.{stem} (see {self.active_filename})\n"
                "    pass\n\n"
                "def on_run_start(api, game, player):\n"
                "    pass\n"
            )
            fn = mod_manager.create_new_mod(f"{stem}_mod", initial_code=hdr)
            self.tab = 0
            self.refresh_list(keep_selection=False)
            self._select_mod_by_name(fn)
            self._set_focus("code")
            self._set_status(f"Создан шаблон {fn}" if lang == "ru" else f"Created {fn}", 3.5)
        # AI Agent controls
        elif bkey == "ai_cfg_btn":
            self.ai_cfg_mode = not self.ai_cfg_mode
            self._set_focus("none")
        elif bkey.startswith("ai_prov_"):
            prov = bkey[8:]
            if prov in PROVIDER_CHOICES:
                prev_def = DEFAULT_MODELS.get(self.ai_provider, "")
                self.ai_provider = prov
                if not self.ai_model_buf or self.ai_model_buf == prev_def:
                    self.ai_model_buf = DEFAULT_MODELS.get(prov, "gpt-4o-mini")
        elif bkey == "ai_key_show":
            self.ai_show_key = not self.ai_show_key
        elif bkey == "ai_key_paste":
            p = self._paste_clipboard().strip()
            if p:
                self.ai_key_buf = p
                self._sync_ai_key_from_buf(persist=True)
                self._set_focus("ai_key")
                self._set_status("API ключ вставлен" if lang == "ru" else "API key pasted", 2.5)
        elif bkey == "ai_save_cfg":
            self._sync_ai_key_from_buf(persist=True)
            ai_agent_client.save(self.ai_provider, self.ai_model_buf, self.ai_key_buf, self.ai_endpoint_buf)
            self.ai_provider = ai_agent_client.provider
            self.ai_model_buf = ai_agent_client.model
            self.ai_cfg_mode = False
            self._set_focus("ai_prompt")
            self._set_status("API настройки сохранены" if lang == "ru" else "API config saved", 3.0)
        elif bkey.startswith("ai_act_"):
            self.ai_action = bkey[7:]
        elif bkey == "ai_prompt_paste":
            p = self._paste_clipboard()
            if p:
                self.ai_prompt += p
                self._set_focus("ai_prompt")
        elif bkey == "ai_prompt_clr":
            self.ai_prompt = ""
            self._set_focus("ai_prompt")
        elif bkey == "ai_key_save":
            self._sync_ai_key_from_buf(persist=True)
            ai_agent_client.save(self.ai_provider, self.ai_model_buf, self.ai_key_buf, self.ai_endpoint_buf)
            self.ai_provider = ai_agent_client.provider
            self.ai_model_buf = ai_agent_client.model
            self._set_status("API ключ сохранён" if lang == "ru" else "API key saved", 3.0)
        elif bkey == "ai_run":
            self._run_ai_action()
        elif bkey == "ai_apply":
            self._apply_ai_result("replace")
        elif bkey == "ai_new_mod":
            self._apply_ai_result("new_mod")
        elif bkey == "ai_apply_run":
            self._apply_ai_result("apply_run")
        return None

    def _handle_small_field_key(self, event):
        mods_key = getattr(event, "mod", 0)
        ctrl = bool(mods_key & pygame.KMOD_CTRL)
        attr_map = {
            "find": "find_query",
            "ai_prompt": "ai_prompt",
            "ai_model": "ai_model_buf",
            "ai_key": "ai_key_buf",
            "ai_key_bar": "ai_key_buf",
            "ai_endpoint": "ai_endpoint_buf",
        }
        attr = attr_map.get(self.focus_target)
        if not attr:
            return False
        val = getattr(self, attr)

        if event.key == pygame.K_RETURN:
            if self.focus_target == "find":
                self._jump_find_match(1)
            elif self.focus_target == "ai_prompt":
                if ctrl:
                    self._run_ai_action()
                else:
                    setattr(self, attr, val + "\n")
            elif self.focus_target in ("ai_model", "ai_key", "ai_endpoint"):
                self._trigger_button("ai_save_cfg")
            elif self.focus_target == "ai_key_bar":
                self._trigger_button("ai_key_save")
            return True
        if event.key == pygame.K_BACKSPACE:
            setattr(self, attr, val[:-1])
            if self.focus_target == "find":
                self._update_find_matches()
            elif self.focus_target in ("ai_key", "ai_key_bar"):
                self._sync_ai_key_from_buf(persist=False)
            return True
        if ctrl and event.key == pygame.K_v:
            p = self._paste_clipboard()
            if p:
                if self.focus_target != "ai_prompt":
                    p = p.replace("\r", "").replace("\n", "")
                if self.focus_target in ("ai_key", "ai_key_bar"):
                    setattr(self, attr, p.strip() if not val else (val + p.strip()))
                    self._sync_ai_key_from_buf(persist=True)
                else:
                    setattr(self, attr, val + p)
                if self.focus_target == "find":
                    self._update_find_matches()
            return True
        if ctrl and event.key == pygame.K_c:
            self._copy_clipboard(val)
            return True
        if ctrl and event.key == pygame.K_BACKSPACE:
            setattr(self, attr, "")
            if self.focus_target == "find":
                self._update_find_matches()
            elif self.focus_target in ("ai_key", "ai_key_bar"):
                self._sync_ai_key_from_buf(persist=False)
            return True
        if not self._text_input_active:
            uc = getattr(event, "unicode", "")
            if uc and uc.isprintable() and not (mods_key & (pygame.KMOD_CTRL | pygame.KMOD_ALT)):
                setattr(self, attr, val + uc)
                if self.focus_target == "find":
                    self._update_find_matches()
                elif self.focus_target in ("ai_key", "ai_key_bar"):
                    self._sync_ai_key_from_buf(persist=False)
                return True
        return True

    def _insert_small_field_text(self, txt):
        attr_map = {
            "find": "find_query",
            "ai_prompt": "ai_prompt",
            "ai_model": "ai_model_buf",
            "ai_key": "ai_key_buf",
            "ai_key_bar": "ai_key_buf",
            "ai_endpoint": "ai_endpoint_buf",
        }
        attr = attr_map.get(self.focus_target)
        if not attr or not txt:
            return
        clean = txt.replace("\r", "")
        if self.focus_target != "ai_prompt":
            clean = clean.replace("\n", "")
        setattr(self, attr, getattr(self, attr) + clean)
        if self.focus_target == "find":
            self._update_find_matches()
        elif self.focus_target in ("ai_key", "ai_key_bar"):
            self._sync_ai_key_from_buf(persist=False)

    def handle_event(self, event):
        rc_map = self._rects()
        entries = self._current_entries()
        vis = entries[self.list_scroll : self.list_scroll + self.VISIBLE_LIST_ROWS]
        row_rects = self._list_row_rects(len(vis))

        if event.type == pygame.TEXTINPUT and self.focus_target != "none":
            txt = getattr(event, "text", "")
            if txt:
                if self.focus_target == "code" and self.tab == 0 and self.active_filename:
                    self._insert_text(txt)
                else:
                    self._insert_small_field_text(txt)
            return None

        if event.type == pygame.KEYDOWN:
            mods_key = getattr(event, "mod", 0)
            ctrl = bool(mods_key & pygame.KMOD_CTRL)
            shift = bool(mods_key & pygame.KMOD_SHIFT)

            if event.key == pygame.K_ESCAPE:
                if self.contacts_modal_open:
                    self.contacts_modal_open = False
                    return None
                if self.focus_target != "none":
                    self._set_focus("none")
                    return None
                if self.find_open:
                    self.find_open = False
                    return None
                self.on_exit()
                return "back"

            if self.contacts_modal_open:
                return None

            if ctrl and event.key == pygame.K_s and self.tab == 0 and self.active_filename:
                self._save_current_mod(enable=True)
                return None

            if ctrl and event.key == pygame.K_f:
                self.find_open = True
                self._set_focus("find")
                return None

            if self.focus_target in ("find", "ai_prompt", "ai_model", "ai_key", "ai_key_bar", "ai_endpoint"):
                self._handle_small_field_key(event)
                return None

            if self.tab == 0 and self.focus_target == "code" and self.active_filename:
                if ctrl and event.key == pygame.K_z:
                    if shift:
                        self._redo()
                    else:
                        self._undo()
                    return None
                if ctrl and event.key == pygame.K_y:
                    self._redo()
                    return None
                if ctrl and event.key == pygame.K_a:
                    self.sel_anchor = (0, 0)
                    self.cursor_line = len(self.lines) - 1
                    self.cursor_col = len(self.lines[self.cursor_line])
                    self._ensure_cursor_visible()
                    return None
                if ctrl and event.key == pygame.K_c:
                    sel = self._get_selected_text() or self.lines[self.cursor_line]
                    self._copy_clipboard(sel)
                    self._set_status("Copied" if get_lang() == "en" else "Скопировано", 1.8)
                    return None
                if ctrl and event.key == pygame.K_x:
                    sel = self._get_selected_text()
                    if sel:
                        self._copy_clipboard(sel)
                        self._push_undo()
                        self._delete_selection()
                        self._refresh_syntax()
                        self._ensure_cursor_visible()
                    return None
                if ctrl and event.key == pygame.K_v:
                    p = self._paste_clipboard()
                    if p:
                        self._insert_text(p)
                    return None
                if ctrl and event.key == pygame.K_SLASH:
                    self._toggle_comment()
                    return None

                if event.key == pygame.K_UP:
                    self._move_cursor(self.cursor_line - 1, self.cursor_col, selecting=shift)
                    return None
                if event.key == pygame.K_DOWN:
                    self._move_cursor(self.cursor_line + 1, self.cursor_col, selecting=shift)
                    return None
                if event.key == pygame.K_LEFT:
                    if self.cursor_col > 0:
                        self._move_cursor(self.cursor_line, self.cursor_col - 1, selecting=shift)
                    elif self.cursor_line > 0:
                        pl = self.cursor_line - 1
                        self._move_cursor(pl, len(self.lines[pl]), selecting=shift)
                    return None
                if event.key == pygame.K_RIGHT:
                    if self.cursor_col < len(self.lines[self.cursor_line]):
                        self._move_cursor(self.cursor_line, self.cursor_col + 1, selecting=shift)
                    elif self.cursor_line < len(self.lines) - 1:
                        self._move_cursor(self.cursor_line + 1, 0, selecting=shift)
                    return None
                if event.key == pygame.K_HOME:
                    line_s = self.lines[self.cursor_line]
                    first_ns = len(line_s) - len(line_s.lstrip(" "))
                    tgt_c = 0 if self.cursor_col == first_ns else first_ns
                    self._move_cursor(self.cursor_line, tgt_c, selecting=shift)
                    return None
                if event.key == pygame.K_END:
                    self._move_cursor(self.cursor_line, len(self.lines[self.cursor_line]), selecting=shift)
                    return None
                if event.key == pygame.K_PAGEUP:
                    vis_l = self._visible_code_lines()
                    self._move_cursor(self.cursor_line - vis_l, self.cursor_col, selecting=shift)
                    return None
                if event.key == pygame.K_PAGEDOWN:
                    vis_l = self._visible_code_lines()
                    self._move_cursor(self.cursor_line + vis_l, self.cursor_col, selecting=shift)
                    return None
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self._insert_text("\n", auto_indent=True)
                    return None
                if event.key == pygame.K_TAB:
                    self._indent_selection(unindent=shift)
                    return None
                if event.key == pygame.K_BACKSPACE:
                    self._push_undo()
                    if not self._delete_selection():
                        self.dirty = True
                        if self.cursor_col > 0:
                            cur = self.lines[self.cursor_line]
                            self.lines[self.cursor_line] = cur[: self.cursor_col - 1] + cur[self.cursor_col :]
                            self.cursor_col -= 1
                        elif self.cursor_line > 0:
                            prev_len = len(self.lines[self.cursor_line - 1])
                            cur = self.lines.pop(self.cursor_line)
                            self.cursor_line -= 1
                            self.lines[self.cursor_line] += cur
                            self.cursor_col = prev_len
                    self._refresh_syntax()
                    self._update_find_matches()
                    self._ensure_cursor_visible()
                    return None
                if event.key == pygame.K_DELETE:
                    self._push_undo()
                    if not self._delete_selection():
                        self.dirty = True
                        cur = self.lines[self.cursor_line]
                        if self.cursor_col < len(cur):
                            self.lines[self.cursor_line] = cur[: self.cursor_col] + cur[self.cursor_col + 1 :]
                        elif self.cursor_line < len(self.lines) - 1:
                            nxt = self.lines.pop(self.cursor_line + 1)
                            self.lines[self.cursor_line] = cur + nxt
                    self._refresh_syntax()
                    self._update_find_matches()
                    self._ensure_cursor_visible()
                    return None
                if event.key == pygame.K_F8 and self.syntax_err_line > 0:
                    self._move_cursor(self.syntax_err_line - 1, 0)
                    return None
                if not self._text_input_active:
                    uc = getattr(event, "unicode", "")
                    if uc and uc.isprintable() and not (mods_key & (pygame.KMOD_CTRL | pygame.KMOD_ALT)):
                        self._insert_text(uc)
                        return None
                return None

            vis_l = self._visible_code_lines()
            if event.key in (pygame.K_w, pygame.K_UP):
                self.code_scroll = max(0, self.code_scroll - 3)
            elif event.key in (pygame.K_s, pygame.K_DOWN):
                self.code_scroll = min(max(0, len(self.lines) - vis_l), self.code_scroll + 3)
            elif event.key == pygame.K_PAGEUP:
                self.code_scroll = max(0, self.code_scroll - vis_l)
            elif event.key == pygame.K_PAGEDOWN:
                self.code_scroll = min(max(0, len(self.lines) - vis_l), self.code_scroll + vis_l)
            elif event.key in (pygame.K_a, pygame.K_LEFT):
                self._trigger_button("tab_mods")
            elif event.key in (pygame.K_d, pygame.K_RIGHT):
                self._trigger_button("tab_sources")
            return None

        if event.type == pygame.MOUSEWHEEL:
            mpos = getattr(event, "pos", pygame.mouse.get_pos())
            if self.ai_open and not self.ai_cfg_mode and rc_map.get("ai_output") and rc_map["ai_output"].collidepoint(mpos):
                self.ai_out_scroll = max(0, self.ai_out_scroll - event.y * 3)
                return None
            vis_l = self._visible_code_lines()
            self.code_scroll = int(clamp(self.code_scroll - event.y * 3, 0, max(0, len(self.lines) - vis_l)))
            return None

        if event.type == pygame.MOUSEMOTION:
            mx, my = event.pos
            if self.dragging_code and rc_map["code_box"].collidepoint(mx, my):
                line, col = self._pixel_to_code_pos(mx, my)
                if self.sel_anchor is None:
                    self.sel_anchor = (self.cursor_line, self.cursor_col)
                self.cursor_line = line
                self.cursor_col = col
                self._ensure_cursor_visible()
                return None
            if self.contacts_modal_open:
                mx, my = event.pos
                self.hover_btn = ""
                self.hover_row = -1
                if "close_contacts" in rc_map and rc_map["close_contacts"].collidepoint(mx, my):
                    self.hover_btn = "close_contacts"
                return None
            self.hover_btn = ""
            self.hover_row = -1
            for k, r in rc_map.items():
                if k not in ("panel", "code_box", "info_bar", "code_sb_track", "ai_panel", "ai_output", "contacts_panel", "close_contacts") and r.collidepoint(mx, my):
                    self.hover_btn = k
                    break
            for vi, r in enumerate(row_rects):
                if r.collidepoint(mx, my):
                    self.hover_row = self.list_scroll + vi
                    break
            return None

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging_code = False
            return None

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button in (4, 5):
                if self.contacts_modal_open:
                    return None
                step = -3 if event.button == 4 else 3
                if self.ai_open and not self.ai_cfg_mode and rc_map.get("ai_output") and rc_map["ai_output"].collidepoint(event.pos):
                    self.ai_out_scroll = max(0, self.ai_out_scroll + step)
                else:
                    vis_l = self._visible_code_lines()
                    self.code_scroll = int(clamp(self.code_scroll + step, 0, max(0, len(self.lines) - vis_l)))
                return None
            if event.button == 1:
                mx, my = event.pos
                if self.contacts_modal_open:
                    if "close_contacts" in rc_map and rc_map["close_contacts"].collidepoint(mx, my):
                        return self._trigger_button("close_contacts")
                    if not rc_map["contacts_panel"].collidepoint(mx, my):
                        self.contacts_modal_open = False
                    return None

                visible_keys = [
                    "btn_contacts", "tab_mods", "tab_sources", "btn_find", "btn_undo", "btn_redo",
                    "btn_copy", "btn_paste", "reload", "ai_toggle", "back",
                    "scroll_up", "scroll_dn", "code_up", "code_dn",
                ]
                if self.find_open:
                    visible_keys += ["find_prev", "find_next", "find_close"]
                if self.tab == 0:
                    visible_keys += ["new_mod", "btn_save", "btn_toggle", "btn_del", "snip_hero", "snip_item", "snip_buff"]
                else:
                    visible_keys += ["copy_mod"]
                if self.ai_open:
                    visible_keys.append("ai_cfg_btn")
                    if self.ai_cfg_mode:
                        visible_keys += [f"ai_prov_{p}" for p in PROVIDER_CHOICES] + ["ai_key_show", "ai_key_paste", "ai_save_cfg"]
                    else:
                        visible_keys += ["ai_act_generate", "ai_act_edit", "ai_act_fix", "ai_act_explain", "ai_run", "ai_prompt_paste", "ai_prompt_clr", "ai_key_save", "ai_apply", "ai_new_mod", "ai_apply_run"]

                for k in visible_keys:
                    if k in rc_map and rc_map[k].collidepoint(mx, my):
                        return self._trigger_button(k)

                if self.find_open and rc_map["find_input"].collidepoint(mx, my):
                    self._set_focus("find")
                    return None

                if self.ai_open:
                    if self.ai_cfg_mode:
                        for fkey in ("ai_model", "ai_key", "ai_endpoint"):
                            if rc_map[fkey].collidepoint(mx, my):
                                self._set_focus(fkey)
                                return None
                    elif rc_map["ai_prompt"].collidepoint(mx, my):
                        self._set_focus("ai_prompt")
                        return None
                    elif rc_map.get("ai_key_bar") and rc_map["ai_key_bar"].collidepoint(mx, my):
                        self._set_focus("ai_key_bar")
                        return None

                for vi, r in enumerate(row_rects):
                    if r.collidepoint(mx, my):
                        self._set_focus("none")
                        self._set_selected_idx(self.list_scroll + vi)
                        return None

                if rc_map["info_bar"].collidepoint(mx, my) and self.syntax_err_line > 0:
                    self._move_cursor(self.syntax_err_line - 1, 0)
                    self._set_focus("code")
                    return None

                if rc_map["code_box"].collidepoint(mx, my):
                    line, col = self._pixel_to_code_pos(mx, my)
                    self.sel_anchor = None
                    self.cursor_line = line
                    self.cursor_col = col
                    self.dragging_code = self.tab == 0
                    self._ensure_cursor_visible()
                    if self.tab == 0 and self.active_filename:
                        self._set_focus("code")
                    return None

                self._set_focus("none")
        return None

    def _draw_wrapped_text(self, screen, rect, font, text, color, scroll=0, max_lines=20):
        wrapped = []
        avail_w = max(40, rect.w - 16)
        for raw_line in (text or "").splitlines() or [""]:
            cur = ""
            for ch in raw_line:
                if font.size(cur + ch)[0] <= avail_w:
                    cur += ch
                else:
                    wrapped.append(cur)
                    cur = ch
            wrapped.append(cur)
        total = len(wrapped)
        scroll = int(clamp(scroll, 0, max(0, total - max_lines)))
        clip_prev = screen.get_clip()
        screen.set_clip(rect.inflate(-6, -6))
        y = rect.y + 6
        for ln in wrapped[scroll : scroll + max_lines]:
            surf = font.render(ln, True, color)
            screen.blit(surf, (rect.x + 8, y))
            fh = font.get_height() if hasattr(font, "get_height") else (font.size("Mg")[1] if hasattr(font, "size") else 16)
            y += fh + 2
        screen.set_clip(clip_prev)
        return total

    def draw(self, screen, ui):
        lang = get_lang()
        rc_map = self._rects()
        screen.fill((8, 8, 8))
        pr = rc_map["panel"]
        panel = get_panel_surf(pr.w, pr.h, 12, 242, 102, 12)
        screen.blit(panel, pr.topleft)

        # Row 1: Title & Developer subtitle cleanly separated from right buttons
        title_clip_prev = screen.get_clip()
        title_max_w = max(240, rc_map["btn_contacts"].left - (pr.x + 24))
        screen.set_clip(pygame.Rect(pr.x + 14, pr.y + 8, title_max_w, 46))
        title = render_text_cached(ui.font_big, tr("mods_title"), PALETTE["text_main"])
        screen.blit(title, (pr.x + 16, pr.y + 10))
        sub_txt = "DarkVault · Редактор кода модов (Python)" if lang == "ru" else "DarkVault · Mod Code Editor (Python)"
        sub_s = render_text_cached(ui.font_tiny, sub_txt, PALETTE["text_muted"])
        screen.blit(sub_s, (pr.x + 16, pr.y + 36))
        screen.set_clip(title_clip_prev)

        top_btns = [
            ("btn_contacts", tr("mods_contacts_btn"), self.contacts_modal_open),
            ("ai_toggle", tr("mods_ai_toggle"), self.ai_open),
            ("back", tr("mods_back"), False),
            ("tab_mods", tr("mods_tab_mods"), self.tab == 0),
            ("tab_sources", tr("mods_tab_sources"), self.tab == 1),
            ("btn_find", tr("mods_search"), self.find_open),
            ("btn_undo", tr("mods_undo"), False),
            ("btn_redo", tr("mods_redo"), False),
            ("btn_copy", tr("mods_copy"), False),
            ("btn_paste", tr("mods_paste"), False),
            ("reload", tr("mods_reload"), False),
        ]
        for key, lbl, active in top_btns:
            rc = rc_map[key]
            hov = self.hover_btn == key
            fill = (238, 238, 238) if active else ((54, 54, 54) if hov else (24, 24, 24))
            border = (252, 252, 252) if active else ((150, 150, 150) if hov else (82, 82, 82))
            pygame.draw.rect(screen, fill, rc, border_radius=5)
            pygame.draw.rect(screen, border, rc, 1, border_radius=5)
            blit_text_fitted(screen, rc, ui.font_tiny, lbl, (12, 12, 12) if active else PALETTE["text_main"], pad_x=4, pad_y=1)

        entries = self._current_entries()
        sel_idx = self._selected_idx()
        max_lscroll = max(0, len(entries) - self.VISIBLE_LIST_ROWS)
        self.list_scroll = int(clamp(self.list_scroll, 0, max_lscroll))
        vis = entries[self.list_scroll : self.list_scroll + self.VISIBLE_LIST_ROWS]
        row_rects = self._list_row_rects(len(vis))

        hdr_l = ("МОДЫ (.PY)" if self.tab == 0 else "ИСХОДНИКИ ИГРЫ") if lang == "ru" else ("MOD FILES (.PY)" if self.tab == 0 else "GAME SOURCE FILES")
        screen.blit(render_text_cached(ui.font_tiny, hdr_l, PALETTE["text_muted"]), (pr.x + 16, pr.y + 100))

        for k, sym in (("scroll_up", "▲"), ("scroll_dn", "▼")):
            rc = rc_map[k]
            hov = self.hover_btn == k
            pygame.draw.rect(screen, (230, 230, 230) if hov else (26, 26, 26), rc, border_radius=4)
            pygame.draw.rect(screen, (112, 112, 112), rc, 1, border_radius=4)
            ts = render_text_cached(ui.font_tiny, sym, (14, 14, 14) if hov else PALETTE["text_main"])
            screen.blit(ts, (rc.centerx - ts.get_width() // 2, rc.centery - ts.get_height() // 2))

        for vi, entry in enumerate(vis):
            real_idx = self.list_scroll + vi
            rc = row_rects[vi]
            sel = real_idx == sel_idx
            hov = real_idx == self.hover_row
            fill = (234, 234, 234) if sel else ((48, 48, 48) if hov else (22, 22, 22))
            pygame.draw.rect(screen, fill, rc, border_radius=6)
            pygame.draw.rect(screen, (252, 252, 252) if sel else (68, 68, 68), rc, 1, border_radius=6)
            fn = entry["filename"]
            if self.tab == 0:
                if entry.get("error"):
                    badge = "[ERR] "
                elif entry.get("enabled"):
                    badge = "[ON]  "
                else:
                    badge = "[OFF] "
                disp = badge + fn
            else:
                disp = fn
            blit_text_fitted(screen, rc, ui.font_small, disp, (12, 12, 12) if sel else PALETTE["text_main"], align="left", pad_x=8)

        if self.tab == 0:
            nm_rc = rc_map["new_mod"]
            hov = self.hover_btn == "new_mod"
            pygame.draw.rect(screen, (236, 236, 236) if hov else (32, 32, 32), nm_rc, border_radius=6)
            pygame.draw.rect(screen, (176, 176, 176), nm_rc, 1, border_radius=6)
            blit_text_fitted(screen, nm_rc, ui.font_small, tr("mods_new"), (12, 12, 12) if hov else PALETTE["text_main"], pad_x=8)

        # File header & live syntax check badge
        info_bar = rc_map["info_bar"]
        pygame.draw.rect(screen, (18, 18, 18), info_bar, border_radius=6)
        pygame.draw.rect(screen, (180, 120, 120) if not self.syntax_ok else (82, 82, 82), info_bar, 1, border_radius=6)
        if self.active_filename:
            if self.tab == 0:
                mode_tag = "EDIT" if self.focus_target == "code" else ("MODIFIED*" if self.dirty else "CLICK TO EDIT")
                syn_tag = "SYNTAX OK" if self.syntax_ok else self.syntax_msg[:34]
                hdr_txt = f"{self.active_filename}  |  {mode_tag}  |  Ln {self.cursor_line + 1}:{self.cursor_col + 1}  |  {syn_tag}"
            else:
                hdr_txt = f"GAME/{self.active_filename}  |  {'ЧТЕНИЕ' if lang == 'ru' else 'READ-ONLY'} ({len(self.lines)} lines)"
            col_hdr = (242, 195, 195) if (self.tab == 0 and not self.syntax_ok) else (232, 232, 232)
            blit_text_fitted(screen, info_bar, ui.font_tiny, hdr_txt, col_hdr, align="left", pad_x=10)

        # Code box
        cbox = rc_map["code_box"]
        pygame.draw.rect(screen, (11, 11, 11), cbox, border_radius=6)
        pygame.draw.rect(screen, (226, 226, 226) if self.focus_target == "code" else (72, 72, 72), cbox, 1, border_radius=6)

        if self.find_open:
            fbar = pygame.Rect(cbox.x + 4, cbox.y + 4, cbox.w - 8, 30)
            pygame.draw.rect(screen, (24, 24, 24), fbar, border_radius=4)
            fi = rc_map["find_input"]
            pygame.draw.rect(screen, (14, 14, 14), fi, border_radius=4)
            pygame.draw.rect(screen, (220, 220, 220) if self.focus_target == "find" else (80, 80, 80), fi, 1, border_radius=4)
            f_disp = self.find_query + ("|" if self.focus_target == "find" and int(self.cursor_blink * 0.08) % 2 == 0 else "")
            fsurf = render_text_cached(ui.font_tiny, f_disp or ("Поиск..." if lang == "ru" else "Find..."), (238, 238, 238) if self.find_query else PALETTE["text_dim"])
            screen.blit(fsurf, (fi.x + 8, fi.centery - fsurf.get_height() // 2))
            mcnt = f"{self.find_match_idx + 1}/{len(self.find_matches)}" if self.find_matches else "0"
            ms = render_text_cached(ui.font_tiny, mcnt, PALETTE["text_muted"])
            screen.blit(ms, (rc_map["find_close"].right + 8, fbar.centery - ms.get_height() // 2))
            for fk, fl in (("find_prev", "<"), ("find_next", ">"), ("find_close", "X")):
                frc = rc_map[fk]
                hov = self.hover_btn == fk
                pygame.draw.rect(screen, (230, 230, 230) if hov else (36, 36, 36), frc, border_radius=4)
                fl_s = render_text_cached(ui.font_tiny, fl, (12, 12, 12) if hov else PALETTE["text_main"])
                screen.blit(fl_s, (frc.centerx - fl_s.get_width() // 2, frc.centery - fl_s.get_height() // 2))

        mono_font, cw = _get_mono_font(14)
        vis_lines = self._visible_code_lines()
        vis_cols = self._visible_cols()
        max_cscroll = max(0, len(self.lines) - vis_lines)
        self.code_scroll = int(clamp(self.code_scroll, 0, max_cscroll))
        top_pad = 36 if self.find_open else 10
        code_x0 = cbox.x + 44
        sel_bounds = self._get_selection_bounds()

        clip_prev = screen.get_clip()
        screen.set_clip(pygame.Rect(cbox.x + 2, cbox.y + top_pad - 2, cbox.w - 4, cbox.h - top_pad - 4))
        for li in range(vis_lines):
            line_idx = self.code_scroll + li
            if line_idx >= len(self.lines):
                break
            yy = cbox.y + top_pad + li * self.LINE_HEIGHT
            is_cur = self.focus_target == "code" and line_idx == self.cursor_line
            is_err = self.tab == 0 and not self.syntax_ok and self.syntax_err_line == (line_idx + 1)
            if is_err:
                pygame.draw.rect(screen, (54, 24, 24), (cbox.x + 4, yy - 1, cbox.w - 8, self.LINE_HEIGHT - 1), border_radius=3)
            elif is_cur:
                pygame.draw.rect(screen, (24, 24, 26), (cbox.x + 4, yy - 1, cbox.w - 8, self.LINE_HEIGHT - 1), border_radius=3)

            ln_col = (232, 140, 140) if is_err else ((195, 195, 195) if is_cur else (82, 82, 82))
            ln_no = render_text_cached(ui.font_tiny, f"{line_idx + 1:03d}", ln_col)
            screen.blit(ln_no, (cbox.x + 8, yy + 2))

            raw = self.lines[line_idx]
            # Draw selection highlight behind text
            if sel_bounds:
                (sl1, sc1), (sl2, sc2) = sel_bounds
                if sl1 <= line_idx <= sl2:
                    s_col = sc1 if line_idx == sl1 else 0
                    e_col = sc2 if line_idx == sl2 else max(len(raw) + 1, s_col + 1)
                    s_vis = max(0, s_col - self.h_scroll)
                    e_vis = max(s_vis, min(vis_cols, e_col - self.h_scroll))
                    if e_vis > s_vis:
                        pygame.draw.rect(screen, (64, 72, 86), (code_x0 + s_vis * cw, yy - 1, (e_vis - s_vis) * cw, self.LINE_HEIGHT - 1))

            # Highlight find matches on this line
            for fl_i, fc1, fc2 in self.find_matches:
                if fl_i == line_idx:
                    sv = max(0, fc1 - self.h_scroll)
                    ev = max(sv, min(vis_cols, fc2 - self.h_scroll))
                    if ev > sv:
                        pygame.draw.rect(screen, (84, 78, 42), (code_x0 + sv * cw, yy, (ev - sv) * cw, self.LINE_HEIGHT - 2))

            slice_txt = raw[self.h_scroll : self.h_scroll + vis_cols]
            cx = code_x0
            for seg_txt, seg_col in _tokenize_python_line(slice_txt):
                seg_surf = mono_font.render(seg_txt, True, seg_col)
                screen.blit(seg_surf, (cx, yy))
                cx += len(seg_txt) * cw

            if is_cur and int(self.cursor_blink * 0.08) % 2 == 0:
                rel_c = max(0, min(vis_cols, self.cursor_col - self.h_scroll))
                caret_x = code_x0 + rel_c * cw
                pygame.draw.rect(screen, (246, 246, 246), (caret_x, yy, 2, self.LINE_HEIGHT - 3))
        screen.set_clip(clip_prev)

        # Scrollbar & code up/down buttons
        for k, sym in (("code_up", "▲"), ("code_dn", "▼")):
            rc = rc_map[k]
            hov = self.hover_btn == k
            pygame.draw.rect(screen, (230, 230, 230) if hov else (26, 26, 26), rc, border_radius=4)
            pygame.draw.rect(screen, (112, 112, 112), rc, 1, border_radius=4)
            ts = render_text_cached(ui.font_tiny, sym, (14, 14, 14) if hov else PALETTE["text_main"])
            screen.blit(ts, (rc.centerx - ts.get_width() // 2, rc.centery - ts.get_height() // 2))
        trk = rc_map["code_sb_track"]
        pygame.draw.rect(screen, (18, 18, 18), trk, border_radius=4)
        if len(self.lines) > vis_lines:
            thumb_h = max(24, int(trk.h * (vis_lines / float(len(self.lines)))))
            thumb_y = trk.y + int((trk.h - thumb_h) * (self.code_scroll / float(max(1, max_cscroll))))
            pygame.draw.rect(screen, (110, 110, 110), (trk.x + 3, thumb_y, trk.w - 6, thumb_h), border_radius=4)

        # Bottom action buttons
        if self.tab == 0:
            en_flag = bool(mod_manager.enabled_map.get(self.active_filename, False)) if self.active_filename else False
            tog_lbl = ("СТАТУС: ВКЛ" if en_flag else "СТАТУС: ВЫКЛ") if lang == "ru" else ("STATE: ON" if en_flag else "STATE: OFF")
            action_specs = [
                ("btn_save", tr("mods_save_run"), True),
                ("btn_toggle", tog_lbl, en_flag),
                ("btn_del", tr("mods_delete"), False),
                ("snip_hero", "+ HERO", False),
                ("snip_item", "+ ITEM", False),
                ("snip_buff", "+ BUFF", False),
            ]
            for key, lbl, hi in action_specs:
                rc = rc_map[key]
                hov = self.hover_btn == key
                fill = (236, 236, 236) if hov else ((46, 46, 46) if hi else (24, 24, 24))
                pygame.draw.rect(screen, fill, rc, border_radius=6)
                pygame.draw.rect(screen, (206, 206, 206) if (hov or hi) else (90, 90, 90), rc, 1, border_radius=6)
                blit_text_fitted(screen, rc, ui.font_tiny, lbl, (12, 12, 12) if hov else PALETTE["text_main"], pad_x=6, pad_y=1)
        else:
            rc = rc_map["copy_mod"]
            hov = self.hover_btn == "copy_mod"
            lbl = "СОЗДАТЬ МОД ПО ПРИМЕРУ" if lang == "ru" else "CREATE MOD FROM REFERENCE"
            pygame.draw.rect(screen, (236, 236, 236) if hov else (30, 30, 30), rc, border_radius=6)
            pygame.draw.rect(screen, (160, 160, 160), rc, 1, border_radius=6)
            blit_text_fitted(screen, rc, ui.font_small, lbl, (12, 12, 12) if hov else PALETTE["text_main"], pad_x=10)

        # AI Coding Agent Docked Panel
        if self.ai_open and "ai_panel" in rc_map:
            ap = rc_map["ai_panel"]
            pygame.draw.rect(screen, (15, 15, 16), ap, border_radius=8)
            pygame.draw.rect(screen, (98, 98, 102), ap, 1, border_radius=8)
            screen.blit(fit_text_surf(ui.font_small, tr("ai_title"), PALETTE["text_main"], max(80, ap.w - 92)), (ap.x + 12, ap.y + 11))

            cfg_rc = rc_map["ai_cfg_btn"]
            hov_c = self.hover_btn == "ai_cfg_btn"
            pygame.draw.rect(screen, (236, 236, 236) if (self.ai_cfg_mode or hov_c) else (30, 30, 30), cfg_rc, border_radius=5)
            pygame.draw.rect(screen, (140, 140, 140), cfg_rc, 1, border_radius=5)
            clbl = tr("ai_back_chat") if self.ai_cfg_mode else tr("ai_api_cfg")
            blit_text_fitted(screen, cfg_rc, ui.font_tiny, clbl, (12, 12, 12) if (self.ai_cfg_mode or hov_c) else PALETTE["text_main"], pad_x=4, pad_y=1)

            if self.ai_cfg_mode:
                screen.blit(render_text_cached(ui.font_tiny, tr("ai_provider"), PALETTE["text_muted"]), (ap.x + 12, ap.y + 32))
                for prov in PROVIDER_CHOICES:
                    prc = rc_map[f"ai_prov_{prov}"]
                    act = self.ai_provider == prov
                    hov = self.hover_btn == f"ai_prov_{prov}"
                    pygame.draw.rect(screen, (236, 236, 236) if act else ((52, 52, 52) if hov else (26, 26, 26)), prc, border_radius=5)
                    pygame.draw.rect(screen, (150, 150, 150) if act else (80, 80, 80), prc, 1, border_radius=5)
                    blit_text_fitted(screen, prc, ui.font_tiny, prov.upper(), (12, 12, 12) if act else PALETTE["text_main"], pad_x=4, pad_y=1)

                field_specs = [
                    ("ai_model", tr("ai_model"), self.ai_model_buf),
                    ("ai_key", tr("ai_key"), self.ai_key_buf if self.ai_show_key else ("*" * len(self.ai_key_buf))),
                    ("ai_endpoint", tr("ai_endpoint"), self.ai_endpoint_buf),
                ]
                for fk, flbl, fval in field_specs:
                    frc = rc_map[fk]
                    screen.blit(render_text_cached(ui.font_tiny, flbl, PALETTE["text_muted"]), (frc.x, frc.y - 18))
                    focused = self.focus_target == fk
                    pygame.draw.rect(screen, (10, 10, 10), frc, border_radius=5)
                    pygame.draw.rect(screen, (235, 235, 235) if focused else (84, 84, 84), frc, 1, border_radius=5)
                    disp = (fval[-36:] if len(fval) > 36 else fval) + ("|" if focused and int(self.cursor_blink * 0.08) % 2 == 0 else "")
                    blit_text_fitted(screen, frc, ui.font_tiny, disp or "—", PALETTE["text_main"] if fval else PALETTE["text_dim"], align="left", pad_x=6, pad_y=1)

                for bk, bl in (("ai_key_show", "HIDE" if self.ai_show_key else "SHOW"), ("ai_key_paste", "PASTE")):
                    brc = rc_map[bk]
                    hov = self.hover_btn == bk
                    pygame.draw.rect(screen, (230, 230, 230) if hov else (32, 32, 32), brc, border_radius=5)
                    blit_text_fitted(screen, brc, ui.font_tiny, bl, (12, 12, 12) if hov else PALETTE["text_main"], pad_x=4, pad_y=1)

                src = rc_map["ai_save_cfg"]
                hov_s = self.hover_btn == "ai_save_cfg"
                pygame.draw.rect(screen, (238, 238, 238) if hov_s else (42, 42, 42), src, border_radius=6)
                pygame.draw.rect(screen, (200, 200, 200), src, 1, border_radius=6)
                blit_text_fitted(screen, src, ui.font_small, tr("ai_save_cfg"), (12, 12, 12) if hov_s else PALETTE["text_main"], pad_x=8)
            else:
                act_labels = [
                    ("generate", tr("ai_act_gen")),
                    ("edit", tr("ai_act_edit")),
                    ("fix", tr("ai_act_fix")),
                    ("explain", tr("ai_act_explain")),
                ]
                for akey, albl in act_labels:
                    arc = rc_map[f"ai_act_{akey}"]
                    act = self.ai_action == akey
                    hov = self.hover_btn == f"ai_act_{akey}"
                    pygame.draw.rect(screen, (236, 236, 236) if act else ((52, 52, 52) if hov else (24, 24, 24)), arc, border_radius=5)
                    pygame.draw.rect(screen, (180, 180, 180) if act else (78, 78, 78), arc, 1, border_radius=5)
                    blit_text_fitted(screen, arc, ui.font_tiny, albl, (12, 12, 12) if act else PALETTE["text_main"], pad_x=4, pad_y=1)

                prc = rc_map["ai_prompt"]
                p_foc = self.focus_target == "ai_prompt"
                pygame.draw.rect(screen, (10, 10, 10), prc, border_radius=6)
                pygame.draw.rect(screen, (236, 236, 236) if p_foc else (80, 80, 80), prc, 1, border_radius=6)
                ptxt = self.ai_prompt + ("|" if p_foc and int(self.cursor_blink * 0.08) % 2 == 0 else "")
                if self.ai_prompt or p_foc:
                    self._draw_wrapped_text(screen, prc, ui.font_tiny, ptxt, (236, 236, 236), 0, 4)
                else:
                    self._draw_wrapped_text(screen, prc, ui.font_tiny, tr("ai_prompt_hint"), PALETTE["text_dim"], 0, 4)

                rrc = rc_map["ai_run"]
                hov_r = self.hover_btn == "ai_run"
                busy = ai_agent_client.busy
                pygame.draw.rect(screen, (236, 236, 236) if hov_r else ((70, 32, 32) if busy else (42, 42, 42)), rrc, border_radius=6)
                pygame.draw.rect(screen, (210, 210, 210), rrc, 1, border_radius=6)
                rlbl = tr("ai_cancel") if busy else tr("ai_run")
                blit_text_fitted(screen, rrc, ui.font_tiny, rlbl, (12, 12, 12) if hov_r else PALETTE["text_main"], pad_x=6, pad_y=1)

                for bk, bl in (("ai_prompt_paste", "PASTE"), ("ai_prompt_clr", "CLR")):
                    brc = rc_map[bk]
                    hov = self.hover_btn == bk
                    pygame.draw.rect(screen, (230, 230, 230) if hov else (28, 28, 28), brc, border_radius=6)
                    pygame.draw.rect(screen, (96, 96, 96), brc, 1, border_radius=6)
                    blit_text_fitted(screen, brc, ui.font_tiny, bl, (12, 12, 12) if hov else PALETTE["text_main"], pad_x=4, pad_y=1)

                krc = rc_map["ai_key_bar"]
                k_foc = self.focus_target == "ai_key_bar"
                pygame.draw.rect(screen, (10, 10, 10), krc, border_radius=5)
                pygame.draw.rect(screen, (235, 235, 235) if k_foc else (78, 78, 78), krc, 1, border_radius=5)
                raw_k = self.ai_key_buf.strip()
                masked_k = (raw_k[:4] + "..." + raw_k[-4:]) if len(raw_k) > 10 else ("*" * len(raw_k))
                k_disp = (masked_k if not k_foc else (masked_k + "|")) if raw_k else (("API KEY..." + ("|" if k_foc else "")) if lang == "en" else ("API КЛЮЧ..." + ("|" if k_foc else "")))
                blit_text_fitted(screen, krc, ui.font_tiny, k_disp, PALETTE["text_main"] if raw_k else PALETTE["text_dim"], align="left", pad_x=6, pad_y=1)

                ksrc = rc_map["ai_key_save"]
                hov_ks = self.hover_btn == "ai_key_save"
                pygame.draw.rect(screen, (232, 232, 232) if hov_ks else (34, 34, 34), ksrc, border_radius=5)
                pygame.draw.rect(screen, (140, 140, 140), ksrc, 1, border_radius=5)
                ks_lbl = "SAVE" if lang == "en" else "СОХР."
                blit_text_fitted(screen, ksrc, ui.font_tiny, ks_lbl, (12, 12, 12) if hov_ks else PALETTE["text_main"], pad_x=4, pad_y=1)

                st_txt = ai_agent_client.status_text or f"{self.ai_provider.upper()} · {self.ai_model_buf[:26]}"
                if busy:
                    dots = "." * (1 + int(self.cursor_blink * 0.08) % 3)
                    st_txt = f"{st_txt.rstrip('.')}{dots}"
                st_col = (232, 145, 145) if ai_agent_client.error_text else PALETTE["accent_soft"]
                screen.blit(fit_text_surf(ui.font_tiny, st_txt, st_col, ap.w - 24), (ap.x + 12, ap.y + 220))

                orc = rc_map["ai_output"]
                pygame.draw.rect(screen, (10, 10, 10), orc, border_radius=6)
                pygame.draw.rect(screen, (72, 72, 72), orc, 1, border_radius=6)
                out_txt = ai_agent_client.last_response
                if out_txt:
                    self._draw_wrapped_text(screen, orc, mono_font, out_txt, (218, 224, 218), self.ai_out_scroll, max(6, (orc.h - 12) // 18))
                elif ai_agent_client.error_text:
                    self._draw_wrapped_text(screen, orc, ui.font_tiny, ai_agent_client.error_text, (232, 165, 165), 0, max(6, (orc.h - 12) // 18))
                else:
                    empty_hint = (
                        "1. Нажмите API и вставьте ключ\n2. Опишите мод или правку\n3. ЗАПУСТИТЬ -> В РЕДАКТОР"
                        if lang == "ru"
                        else "1. Click API and paste your key\n2. Describe a mod or fix\n3. RUN -> TO EDITOR"
                    )
                    self._draw_wrapped_text(screen, orc, ui.font_tiny, empty_hint, PALETTE["text_dim"], 0, 6)

                for bk, bl in (("ai_apply", tr("ai_apply")), ("ai_new_mod", tr("ai_new_mod")), ("ai_apply_run", tr("ai_apply_run"))):
                    brc = rc_map[bk]
                    hov = self.hover_btn == bk
                    has_res = bool(out_txt)
                    fill = (236, 236, 236) if (hov and has_res) else ((36, 36, 36) if has_res else (20, 20, 20))
                    pygame.draw.rect(screen, fill, brc, border_radius=5)
                    pygame.draw.rect(screen, (140, 140, 140) if has_res else (64, 64, 64), brc, 1, border_radius=5)
                    blit_text_fitted(screen, brc, ui.font_tiny, bl, (12, 12, 12) if (hov and has_res) else (PALETTE["text_main"] if has_res else PALETTE["text_dim"]), pad_x=4, pad_y=1)

        # Status / Footer bar (clipped cleanly so status never overlaps AI panel)
        foot_y = rc_map["btn_save"].bottom + 10
        foot_rc = pygame.Rect(rc_map["info_bar"].x, foot_y - 2, rc_map["info_bar"].w, 24)
        if self.status_timer > 0 and self.status_msg:
            blit_text_fitted(screen, foot_rc, ui.font_small, self.status_msg, (244, 244, 244), align="left", pad_x=0)
        else:
            foot = (
                "Ctrl+S сохр · Ctrl+Z/Y отмена · Ctrl+C/V/X буфер · Ctrl+/ коммент · Ctrl+F поиск · Tab отступ"
                if lang == "ru"
                else "Ctrl+S Save · Ctrl+Z/Y Undo/Redo · Ctrl+C/V/X Clipboard · Ctrl+/ Comment · Ctrl+F Find · Tab Indent"
            )
            blit_text_fitted(screen, foot_rc, ui.font_tiny, foot, PALETTE["text_dim"], align="left", pad_x=0)

        # Contacts & Developer Support Modal
        if self.contacts_modal_open and "contacts_panel" in rc_map:
            dim = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            dim.fill((4, 4, 4, 185))
            screen.blit(dim, (0, 0))

            cp = rc_map["contacts_panel"]
            pygame.draw.rect(screen, (16, 16, 17), cp, border_radius=12)
            pygame.draw.rect(screen, (190, 190, 196), cp, 2, border_radius=12)

            ct_s = fit_text_surf(ui.font_big, tr("mods_contacts_title"), PALETTE["text_main"], cp.w - 44)
            screen.blit(ct_s, (cp.x + 22, cp.y + 18))
            pygame.draw.line(screen, (64, 64, 68), (cp.x + 22, cp.y + 52), (cp.right - 22, cp.y + 52), 1)

            desc_rc = pygame.Rect(cp.x + 14, cp.y + 58, cp.w - 28, 72)
            self._draw_wrapped_text(screen, desc_rc, ui.font_small, tr("mods_contacts_desc"), PALETTE["text_muted"], 0, 4)

            info_y = cp.y + 138
            for line_key in ("mods_contacts_author", "mods_contacts_email", "mods_contacts_github"):
                box = pygame.Rect(cp.x + 22, info_y, cp.w - 44, 34)
                pygame.draw.rect(screen, (24, 24, 26), box, border_radius=6)
                pygame.draw.rect(screen, (68, 68, 72), box, 1, border_radius=6)
                blit_text_fitted(screen, box, ui.font_small, tr(line_key), PALETTE["text_main"], align="left", pad_x=10)
                info_y += 42

            c_btns = [
                ("close_contacts", tr("mods_back")),
            ]
            for key, lbl in c_btns:
                if key not in rc_map:
                    continue
                brc = rc_map[key]
                hov = self.hover_btn == key
                pygame.draw.rect(screen, (238, 238, 238) if hov else (32, 32, 34), brc, border_radius=6)
                pygame.draw.rect(screen, (248, 248, 248) if hov else (126, 126, 132), brc, 1, border_radius=6)
                blit_text_fitted(screen, brc, ui.font_tiny, lbl, (12, 12, 12) if hov else PALETTE["text_main"], pad_x=6, pad_y=1)
