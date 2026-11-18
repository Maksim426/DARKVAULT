import builtins
import math
import os
import random
import pygame
from bosses import PLAYABLE_BOSS_KEYS, spawn_boss_for_room
from enemy import REGULAR_ENEMY_TYPES, create_enemy
from heroes import HERO_ROSTER, get_hero
from i18n import get_lang, tr_boss, tr_floor, tr_room
from items import ITEM_POOL_65, ITEM_REGISTRY, ItemPedestal, Pickup, get_item_by_id, get_random_item, tr_item_name
from room import (
    BEGGAR_TYPES,
    MACHINE_TYPES,
    NPC_KEYS,
    SHOPKEEPER_VARIANTS,
    Beggar,
    DiceFloor,
    Door,
    LoreMonolith,
    Machine,
    MysticalNPC,
    Obstacle,
    SacrificeSpike,
    Shopkeeper,
)
from settings import (
    GAME_SETTINGS,
    PALETTE,
    PLAYABLE_BOTTOM,
    PLAYABLE_LEFT,
    PLAYABLE_RIGHT,
    PLAYABLE_TOP,
    ROOM_COLOR_SCHEMES,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    clamp,
    draw_aa_circle,
    get_panel_surf,
    get_user_data_dir,
    get_view_width,
    get_world_offset_x,
    render_text_cached,
    save_user_settings,
)

EFFECT_DEFINITIONS = {
    "godmode": {
        "ru": "Бессмертие",
        "en": "Godmode",
        "desc_ru": "Полная неуязвимость ко всему урону.",
        "desc_en": "Complete immunity to all incoming damage.",
        "default_dur": 30.0,
    },
    "rage": {
        "ru": "Ярость",
        "en": "Rage",
        "desc_ru": "Урон слёз умножен на x1.65.",
        "desc_en": "Multiplies tear damage by x1.65.",
        "default_dur": 25.0,
    },
    "haste": {
        "ru": "Ускорение",
        "en": "Haste",
        "desc_ru": "+2.1 к скорости и скорострельность x1.8.",
        "desc_en": "+2.1 movement speed and x1.8 fire rate.",
        "default_dur": 25.0,
    },
    "flight": {
        "ru": "Полёт",
        "en": "Flight",
        "desc_ru": "Позволяет парить над ямами, шипами и камнями.",
        "desc_en": "Grants flight over pits, spikes, and rocks.",
        "default_dur": 35.0,
    },
    "spectral": {
        "ru": "Призрачные слёзы",
        "en": "Spectral Tears",
        "desc_ru": "Слёзы свободно проходят сквозь камни и колонны.",
        "desc_en": "Tears phase cleanly through rocks and pillars.",
        "default_dur": 30.0,
    },
    "homing": {
        "ru": "Наведение",
        "en": "Homing",
        "desc_ru": "Слёзы загибаются и преследуют ближайших врагов.",
        "desc_en": "Tears curve automatically toward nearby enemies.",
        "default_dur": 30.0,
    },
    "poison_touch": {
        "ru": "Ядовитый шлейф",
        "en": "Venom Shots",
        "desc_ru": "Каждая слеза отравляет врагов на 2.5 секунды.",
        "desc_en": "Every tear inflicts lingering poison damage.",
        "default_dur": 30.0,
    },
    "brimstone": {
        "ru": "Кровь серы",
        "en": "Brimstone Gaze",
        "desc_ru": "Слёзы пробивают врагов и наносят повышенный урон.",
        "desc_en": "High-power piercing brimstone projectiles.",
        "default_dur": 25.0,
    },
    "shield": {
        "ru": "Щит бездны",
        "en": "Abyssal Shield",
        "desc_ru": "Блокирует следующий входящий удар без потери ОЗ.",
        "desc_en": "Absorbs incoming hits with an impenetrable ward.",
        "default_dur": 20.0,
    },
    "lantern_blaze": {
        "ru": "Пылающий фонарь",
        "en": "Lantern Blaze",
        "desc_ru": "Мощный свет разгоняет тьму почти по всей комнате.",
        "desc_en": "Expands lantern illumination across nearly the entire room.",
        "default_dur": 35.0,
    },
    "magnet": {
        "ru": "Магнит",
        "en": "Magnetism",
        "desc_ru": "Притягивает бесплатные припасы и монеты по комнате.",
        "desc_en": "Pulls nearby free coins and pickups toward you.",
        "default_dur": 35.0,
    },
    "giant": {
        "ru": "Гигантизм",
        "en": "Giantism",
        "desc_ru": "Размер, отдача и урон увеличены (x1.35 DMG).",
        "desc_en": "Increases body size, tear radius, and DMG (x1.35).",
        "default_dur": 25.0,
    },
}

ENEMY_EFFECT_DEFINITIONS = {
    "burn": {"ru": "Ожог", "en": "Burn", "default_dur": 6.0},
    "poison": {"ru": "Яд", "en": "Poison", "default_dur": 6.0},
    "freeze": {"ru": "Стужа", "en": "Freeze", "default_dur": 5.0},
    "weaken": {"ru": "Слабость", "en": "Weaken", "default_dur": 8.0},
    "bleed": {"ru": "Кровоток", "en": "Bleed", "default_dur": 6.0},
}

CONSOLE_DOC_ENTRIES = [
    {
        "id": "console_basics",
        "icon_kind": "terminal",
        "name": "Консоль Разработчика",
        "name_en": "Developer Console",
        "sub": "ОТЛАДКА · БЫСТРЫЕ КОМАНДЫ",
        "sub_en": "DEBUG · QUICK COMMANDS",
        "lore": "Сначала включите в Настройках («Консоль разработчика: ВКЛ»), затем вызывайте в игре клавишей [ё] / [`] / [F1]. Поддерживает историю команд (↑/↓) и автодополнение [Tab].",
        "lore_en": "Enable in Settings ('Developer Console: ON') first, then toggle in-game with [`] / [~] / [F1]. Supports command history (Up/Down) and [Tab] autocompletion.",
        "ability_ru": "НАСТРОЙКИ → Консоль ВКЛ  |  [` / ё / F1] открыть  |  [Tab] дополнение  |  [Enter] ввод",
        "ability_en": "SETTINGS → Console ON  |  [` / ~ / F1] Toggle  |  [Tab] Autocomplete  |  [Enter] Execute",
        "stats_rows_ru": [("ОТКРЫТИЕ", "` / ~ / ё / F1"), ("ИСТОРИЯ", "↑ / ↓"), ("ДОПОЛНЕНИЕ", "TAB"), ("ДОКУМЕНТ", "CONSOLE_COMMANDS.txt")],
        "stats_rows_en": [("TOGGLE", "` / ~ / F1"), ("HISTORY", "UP / DOWN"), ("COMPLETE", "TAB"), ("DOC FILE", "CONSOLE_COMMANDS.txt")],
        "footer_ru": "Все команды работают без перезапуска забега",
        "footer_en": "All commands apply live without restarting your run",
    },
    {
        "id": "editor_mode",
        "icon_kind": "editor",
        "name": "Режим Редактора Комнат",
        "name_en": "Room Editor Mode",
        "sub": "СПАВН · ПОСТРОЙКА · СЕТКА",
        "sub_en": "SPAWN · ARCHITECT · SNAP GRID",
        "lore": "Активируется командой «editor on» в консоли (затем переключается по [F2]). Позволяет ставить препятствия, врагов, боссов, НПС, пьедесталы и менять тип зала мышью.",
        "lore_en": "Unlocked via 'editor on' in console (thereafter toggleable with [F2]). Place or erase obstacles, enemies, bosses, NPCs, pedestals, and convert room types live.",
        "ability_ru": "ЛКМ — поставить · ПКМ — удалить ближайший объект · [1-6] — категория · [[]/[]]/Колесо — объект · [P] — пауза ИИ · [G] — сетка",
        "ability_en": "LMB Place · RMB Erase nearest · [1-6] Category · [[]/[]]/Wheel Cycle item · [P] Freeze AI · [G] Grid snap",
        "stats_rows_ru": [("АКТИВАЦИЯ", "editor on / F2"), ("КАТЕГОРИИ", "Клавиши 1–6"), ("ЗАМОРОЗКА ИИ", "Клавиша P"), ("ОЧИСТКА ЗАЛА", "Клавиша C")],
        "stats_rows_en": [("ACTIVATE", "editor on / F2"), ("CATEGORIES", "Keys 1–6"), ("FREEZE AI", "Key P"), ("CLEAR ROOM", "Key C")],
        "footer_ru": "Команды редактора: editor on | editor off",
        "footer_en": "Console toggle: editor on | editor off",
    },
    {
        "id": "effect_commands",
        "icon_kind": "effect",
        "name": "Эффекты Игрока и Врагов",
        "name_en": "Player & Enemy Effects",
        "sub": "СТАТУС-ЭФФЕКТЫ · ВРЕМЕННЫЕ БАФФЫ",
        "sub_en": "STATUS EFFECTS · TIMED BUFFS",
        "lore": "Команда «effect give <id> [сек]» накладывает временный или вечный (0 сек) эффект: godmode, rage, haste, flight, spectral, homing, poison_touch, brimstone, shield, lantern_blaze, magnet, giant.",
        "lore_en": "Use 'effect give <id> [sec]' for timed or permanent (0 sec) buffs: godmode, rage, haste, flight, spectral, homing, poison_touch, brimstone, shield, lantern_blaze, magnet, giant.",
        "ability_ru": "ПРИМЕР: effect give godmode 0  |  effect enemy freeze 8  |  effect clear  |  effect list",
        "ability_en": "EXAMPLES: effect give godmode 0  |  effect enemy freeze 8  |  effect clear  |  effect list",
        "stats_rows_ru": [("ДЛЯ ИГРОКА", "effect give <id> [sec]"), ("СНЯТИЕ", "effect clear [id]"), ("ДЛЯ ВРАГОВ", "effect enemy <id> [sec]"), ("СПИСОК", "effect list")],
        "stats_rows_en": [("PLAYER BUFF", "effect give <id> [sec]"), ("CLEAR BUFFS", "effect clear [id]"), ("ENEMY STATUS", "effect enemy <id> [sec]"), ("LIST ALL", "effect list")],
        "footer_ru": "Эффекты врагов: burn, poison, freeze, weaken, bleed",
        "footer_en": "Enemy effects: burn, poison, freeze, weaken, bleed",
    },
    {
        "id": "player_commands",
        "icon_kind": "relic",
        "name": "Команды Героя и Реликвий",
        "name_en": "Hero & Relic Commands",
        "sub": "АРТЕФАКТЫ · СТАТЫ · ЛЕЧЕНИЕ",
        "sub_en": "RELICS · STATS · HEALING",
        "lore": "Выдавайте любые реликвии командой «give <id|random> [кол-во]», настраивайте характеристики через «stat <имя> <число>» и переключайте героев командой «hero <id>».",
        "lore_en": "Grant any relic via 'give <id|random> [count]', tune stats with 'stat <field> <value>', heal completely with 'heal', or morph into any hero via 'hero <id>'.",
        "ability_ru": "ПОЛЯ STAT: hp, max_hp, soul, black, coins, bombs, keys, dmg, spd, luck, charge",
        "ability_en": "STAT FIELDS: hp, max_hp, soul, black, coins, bombs, keys, dmg, spd, luck, charge",
        "stats_rows_ru": [("АРТЕФАКТЫ", "give godhead 1"), ("ПОЛУЧИТЬ", "give random 3"), ("СТАТЫ", "stat dmg 18"), ("ЛЕЧЕНИЕ / СМЕНА", "heal  |  hero azazel")],
        "stats_rows_en": [("GRANT RELIC", "give godhead 1"), ("RANDOM PACK", "give random 3"), ("SET STAT", "stat dmg 18"), ("HEAL / HERO", "heal  |  hero azazel")],
        "footer_ru": "Включите сквозь стены командой noclip",
        "footer_en": "Toggle wall/obstacle phasing with noclip",
    },
    {
        "id": "world_commands",
        "icon_kind": "world",
        "name": "Команды Мира и Спавна",
        "name_en": "World & Spawn Commands",
        "sub": "ЯРУСЫ · КОМНАТЫ · СУЩНОСТИ",
        "sub_en": "FLOORS · ROOMS · ENTITIES",
        "lore": "Управляйте подземельем на лету: переходите на любой ярус («floor 5»), преобразуйте комнату («room devil»), открывайте всю карту («reveal»), зачищайте врагов («killall») или спавните боссов.",
        "lore_en": "Control the dungeon on the fly: jump to any floor ('floor 5'), convert room type ('room devil'), reveal minimap ('reveal'), wipe foes ('killall'), or spawn anything.",
        "ability_ru": "СПАВН: spawn enemy/boss/pickup/pedestal/npc/machine/beggar/monolith [id] [x y]  |  timescale 1.5",
        "ability_en": "SPAWN: spawn enemy/boss/pickup/pedestal/npc/machine/beggar/monolith [id] [x y]  |  timescale 1.5",
        "stats_rows_ru": [("СПАВН БОССА", "spawn boss satan"), ("СМЕНА ЗАЛА", "room treasure"), ("ЯРУС / ТП", "floor 4 | tp 640 360"), ("ВРЕМЯ / КАРТА", "timescale 0.5 | reveal")],
        "stats_rows_en": [("SPAWN BOSS", "spawn boss satan"), ("CONVERT ROOM", "room treasure"), ("FLOOR / TP", "floor 4 | tp 640 360"), ("TIME / MAP", "timescale 0.5 | reveal")],
        "footer_ru": "killall убирает врагов и открывает двери · clearroom чистит зал",
        "footer_en": "killall slays foes & opens doors · clearroom wipes room props",
    },
]

COMMAND_NAMES = [
    "help",
    "clear",
    "editor",
    "effect",
    "give",
    "stat",
    "heal",
    "spawn",
    "room",
    "floor",
    "tp",
    "reveal",
    "killall",
    "clearroom",
    "timescale",
    "noclip",
    "hero",
    "play",
    "mode",
    "coop",
    "preview",
    "exec",
    "writefile",
    "savefile",
    "readfile",
    "cat",
    "ls",
    "files",
    "restart",
    "menu",
    "sound",
    "lang",
    "screen",
    "info",
    "status",
    "unlock_all",
    "seed",
    "stats",
    "reload",
    "freeze",
    "dump",
    "zoom",
    "fly",
    "kill",
]

ROOM_TYPE_LIST = [
    "normal",
    "treasure",
    "shop",
    "curse",
    "arcade",
    "sacrifice",
    "library",
    "dice",
    "secret",
    "boss",
    "devil",
]

PICKUP_TYPES = [
    "coin",
    "nickel",
    "dime",
    "heart",
    "half_heart",
    "soul_heart",
    "black_heart",
    "bomb",
    "key",
    "battery",
]


def _default_room_center():
    return (PLAYABLE_LEFT + PLAYABLE_RIGHT) // 2, (PLAYABLE_TOP + PLAYABLE_BOTTOM) // 2


def convert_room_type(room, rtype, player_collected_ids=None, floor_level=1):
    rtype = str(rtype).strip().lower()
    if rtype not in ROOM_COLOR_SCHEMES:
        return False
    room.room_type = rtype
    room.scheme = ROOM_COLOR_SCHEMES[rtype]
    room._baked_bg = None
    cx, cy = _default_room_center()
    if rtype in ("start", "treasure", "shop", "arcade", "sacrifice", "library", "dice", "secret", "devil"):
        room.cleared = True
    if rtype == "treasure" and not room.pedestals:
        room.pedestals.append(ItemPedestal(cx, cy, get_random_item(player_collected_ids, "passive")))
    elif rtype == "shop" and not room.pedestals and not room.pickups:
        room.pedestals.append(ItemPedestal(cx - 75, cy, get_random_item(player_collected_ids), price=15))
        room.pickups.append(Pickup(cx + 15, cy + 10, "soul_heart", price=5))
        room.pickups.append(Pickup(cx + 75, cy + 10, "key", price=5))
        room.shopkeepers.append(Shopkeeper(cx, cy - 88, random.choice(SHOPKEEPER_VARIANTS)))
    elif rtype == "sacrifice" and room.sacrifice_spike is None:
        room.sacrifice_spike = SacrificeSpike(cx, cy)
    elif rtype == "dice" and room.dice_floor is None:
        room.dice_floor = DiceFloor(cx, cy, random.randint(1, 6))
    elif rtype == "devil" and not room.pedestals:
        room.pedestals.append(ItemPedestal(cx - 70, cy + 15, get_random_item(player_collected_ids, "passive"), devil_cost=1))
        room.pedestals.append(ItemPedestal(cx + 70, cy + 15, get_random_item(player_collected_ids, "passive"), devil_cost=2))
    elif rtype == "boss" and not room.bosses:
        bk = random.choice(PLAYABLE_BOSS_KEYS)
        room.bosses = spawn_boss_for_room(room, bk, cx, cy - 80, floor_level, room.floor_modifier)
        room.cleared = False
    return True


class DevConsole:
    def __init__(self):
        self.open = False
        self.editor_unlocked = False
        self.input_text = ""
        self.history = []
        self.hist_idx = -1
        self.logs = []
        self.scroll_offset = 0
        self.cursor_timer = 0.0
        self.log("DarkVault Console ready. Type 'help' for commands.", 210)

    def log(self, text, lum=220):
        for line in str(text).splitlines() or [""]:
            self.logs.append((line[:116], int(clamp(lum, 90, 252))))
        if len(self.logs) > 220:
            self.logs = self.logs[-220:]
        self.scroll_offset = 0

    def is_toggle_key(self, event):
        if event.type != pygame.KEYDOWN:
            return False
        if event.key in (pygame.K_BACKQUOTE, pygame.K_F1):
            return True
        uc = getattr(event, "unicode", "")
        return uc in ("`", "~", "ё", "Ё")

    def _close_rect(self):
        panel_w = get_view_width() - 48
        px, py = 24, 16
        return pygame.Rect(px + panel_w - 42, py + 5, 30, 22)

    def toggle(self, force=None):
        self.open = (not self.open) if force is None else bool(force)
        if self.open:
            self.hist_idx = -1
            try:
                pygame.key.start_text_input()
            except Exception:
                pass
        else:
            try:
                pygame.key.stop_text_input()
            except Exception:
                pass

    def _autocomplete(self):
        raw = self.input_text
        if not raw.strip():
            return
        parts = raw.split(" ")
        if len(parts) == 1:
            pref = parts[0].lower()
            matches = [c for c in COMMAND_NAMES if c.startswith(pref)]
            if len(matches) == 1:
                self.input_text = matches[0] + " "
            elif matches:
                self.log("Commands: " + ", ".join(matches[:10]), 176)
            return

        cmd = parts[0].lower()
        pref = parts[-1].lower()
        candidates = []
        if cmd == "effect":
            if len(parts) == 2:
                candidates = ["give", "clear", "list", "enemy"]
            elif parts[1].lower() == "enemy" and len(parts) == 3:
                candidates = list(ENEMY_EFFECT_DEFINITIONS.keys())
            elif len(parts) == 3:
                candidates = list(EFFECT_DEFINITIONS.keys())
        elif cmd == "give":
            candidates = ["random"] + [it["id"] for it in ITEM_POOL_65]
        elif cmd == "editor":
            candidates = ["on", "off"]
        elif cmd == "hero":
            candidates = [h["id"] for h in HERO_ROSTER]
        elif cmd == "room":
            candidates = list(ROOM_TYPE_LIST)
        elif cmd in ("play", "mode"):
            candidates = ["classic", "fading_light", "endless_abyss", "free_roam", "boss_rush", "shared_seed", "chaos_draft"]
        elif cmd == "coop":
            candidates = ["on", "off"]
        elif cmd == "stat":
            candidates = ["hp", "max_hp", "soul", "black", "coins", "bombs", "keys", "dmg", "spd", "luck", "charge"]
        elif cmd == "spawn":
            if len(parts) == 2:
                candidates = ["enemy", "boss", "pickup", "pedestal", "npc", "machine", "beggar", "monolith"]
            elif len(parts) == 3:
                kind = parts[1].lower()
                if kind == "enemy":
                    candidates = list(REGULAR_ENEMY_TYPES)
                elif kind == "boss":
                    candidates = list(PLAYABLE_BOSS_KEYS)
                elif kind == "pickup":
                    candidates = list(PICKUP_TYPES)
                elif kind == "npc":
                    candidates = list(NPC_KEYS[:3])
                elif kind == "machine":
                    candidates = list(MACHINE_TYPES)
                elif kind == "beggar":
                    candidates = list(BEGGAR_TYPES)
                elif kind == "pedestal":
                    candidates = ["random"] + [it["id"] for it in ITEM_POOL_65]

        matches = [c for c in candidates if c.lower().startswith(pref)]
        if len(matches) == 1:
            parts[-1] = matches[0]
            self.input_text = " ".join(parts) + " "
        elif matches:
            self.log("Matches: " + ", ".join(matches[:10]), 176)

    def execute(self, cmd_str, game):
        cleaned = cmd_str.strip()
        if not cleaned:
            return
        self.log(f"> {cleaned}", 246)
        if not self.history or self.history[-1] != cleaned:
            self.history.append(cleaned)
        self.hist_idx = -1

        tokens = cleaned.split()
        cmd = tokens[0].lower()
        args = tokens[1:]
        player = game.player
        room = game.current_room

        if cmd == "help":
            if not args:
                self.log("Commands: help, clear, editor [on|off], effect <give|clear|list|enemy>, give, stat, heal,", 205)
                self.log("          spawn, room, floor, tp, reveal, killall, clearroom, timescale, noclip, hero", 205)
            else:
                sub = args[0].lower()
                helps = {
                    "editor": "editor [on|off] — Unlock/toggle live Room Editor mode [F2].",
                    "effect": "effect give <id> [sec] | effect clear [id] | effect list | effect enemy <burn|poison|freeze|weaken|bleed> [sec]",
                    "give": "give <item_id|random> [count] — Grant relic(s) immediately.",
                    "stat": "stat <hp|max_hp|soul|black|coins|bombs|keys|dmg|spd|luck|charge> <val>",
                    "spawn": "spawn <enemy|boss|pickup|pedestal|npc|machine|beggar|monolith> [id] [x y]",
                    "room": "room <type> — Convert current room type & palette.",
                    "floor": "floor <n> — Jump directly to floor n.",
                    "tp": "tp <x> <y> — Teleport player inside room.",
                    "timescale": "timescale <0.1..4.0> — Scale game simulation speed.",
                }
                self.log(helps.get(sub, f"Usage: {sub}"), 220)
            return

        if cmd == "clear":
            self.logs.clear()
            self.scroll_offset = 0
            return

        if cmd == "editor":
            if not args:
                want = not game.editor.active
            else:
                want = args[0].lower() in ("on", "1", "true", "enable")
            if want:
                self.editor_unlocked = True
                game.editor.unlocked = True
                game.editor.active = True
                self.open = False
                self.log("Room Editor ENABLED ([F2] quick toggle).", 242)
            else:
                game.editor.active = False
                self.log("Room Editor DISABLED.", 190)
            return

        if cmd in ("play", "mode"):
            if not args:
                self.log("Modes: classic, fading_light, endless_abyss, free_roam, boss_rush, shared_seed, chaos_draft", 190)
                return
            m = args[0].lower()
            mapping = {
                "classic": "classic",
                "fading_light": "fading_light",
                "endless": "endless_abyss",
                "endless_abyss": "endless_abyss",
                "free_roam": "free_roam",
                "boss_rush": "boss_rush",
                "shared_seed": "shared_seed",
                "chaos_draft": "chaos_draft",
                "normal": "classic",
            }
            if m in mapping:
                from settings import GAME_MODES

                game.game_mode = mapping[m]
                if game.game_mode in GAME_MODES:
                    game.selected_mode_idx = GAME_MODES.index(game.game_mode)
                game.start_new_run()
                self.log(f"Started run in mode '{game.game_mode}'.", 240)
            else:
                self.log(f"Unknown mode '{m}'. Use classic, fading_light, endless_abyss, free_roam, boss_rush, shared_seed, chaos_draft.", 160)
            return

        if cmd == "coop":
            want = (not getattr(game, "coop_enabled", False)) if not args else (args[0].lower() in ("on", "1", "true"))
            game.coop_enabled = bool(want)
            self.log(f"2P Co-op set to {'ON' if game.coop_enabled else 'OFF'}. Restart run to apply.", 240)
            return

        if cmd == "preview":
            if not args:
                self.log("Usage: preview <0-5>", 180)
                return
            try:
                idx = int(args[0])
                game.preview.load_scene(idx)
                self.log(f"Loaded preview scene {idx}.", 230)
            except Exception as ex:
                self.log(f"Error: {ex}", 160)
            return

        if cmd == "exec":
            if not args:
                self.log("Usage: exec <python_code>", 180)
                return
            code = cleaned[len("exec"):].strip()
            try:
                env = {
                    "game": game,
                    "player": game.player,
                    "room": game.current_room,
                    "math": math,
                    "random": random,
                    "pygame": pygame,
                }
                try:
                    res = eval(code, {"__builtins__": builtins}, env)
                    if res is not None:
                        self.log(str(res), 246)
                    else:
                        self.log("Executed expression successfully.", 232)
                except SyntaxError:
                    exec(code, {"__builtins__": builtins}, env)
                    self.log("Executed statement successfully.", 232)
            except Exception as ex:
                self.log(f"Exec error: {ex}", 165)
            return

        if cmd in ("writefile", "savefile"):
            if len(args) < 2:
                self.log("Usage: writefile <filename> <content>", 180)
                return
            fname = os.path.basename(args[0].strip())
            content = cleaned.split(maxsplit=2)[2] if len(cleaned.split(maxsplit=2)) > 2 else ""
            try:
                path = os.path.join(get_user_data_dir(), fname)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                self.log(f"Successfully wrote {len(content)} chars to '{fname}'.", 242)
            except Exception as ex:
                self.log(f"Write error: {ex}", 160)
            return

        if cmd in ("readfile", "cat"):
            if not args:
                self.log("Usage: readfile <filename>", 180)
                return
            fname = os.path.basename(args[0].strip())
            try:
                path = os.path.join(get_user_data_dir(), fname)
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    self.log(f"--- {fname} ({len(lines)} lines) ---", 210)
                    for ln in lines[:40]:
                        self.log(ln.rstrip(), 190)
                    if len(lines) > 40:
                        self.log(f"... ({len(lines) - 40} more lines truncated)", 170)
                else:
                    self.log(f"File '{fname}' not found.", 160)
            except Exception as ex:
                self.log(f"Read error: {ex}", 160)
            return

        if cmd in ("ls", "files"):
            try:
                files = [f for f in os.listdir(get_user_data_dir()) if not f.startswith(".")]
                self.log("Workspace files: " + ", ".join(sorted(files)[:30]), 215)
            except Exception as ex:
                self.log(f"Error listing files: {ex}", 160)
            return

        if cmd == "restart":
            game.start_new_run()
            self.log("Restarted run.", 240)
            return

        if cmd == "menu":
            game.state = "MENU"
            self.open = False
            self.log("Returned to Main Menu.", 230)
            return

        if cmd == "sound":
            if not args:
                self.log(f"Sound is {'ON' if GAME_SETTINGS.get('sound_enabled', True) else 'OFF'}", 200)
                return
            val = args[0].lower() in ("on", "1", "true", "yes")
            GAME_SETTINGS["sound_enabled"] = val
            save_user_settings()
            self.log(f"Sound set to {'ON' if val else 'OFF'}.", 232)
            return

        if cmd == "lang":
            if not args:
                self.log(f"Language: {GAME_SETTINGS.get('language', 'ru').upper()}", 200)
                return
            lg = args[0].lower()
            if lg in ("ru", "en"):
                GAME_SETTINGS["language"] = lg
                save_user_settings()
                self.log(f"Language switched to {lg.upper()}.", 240)
            else:
                self.log("Usage: lang <ru|en>", 160)
            return

        if cmd == "screen":
            if not args:
                self.log(f"Fullscreen: {GAME_SETTINGS.get('fullscreen', False)}", 200)
                return
            fs = args[0].lower() in ("full", "fullscreen", "1", "true")
            game._apply_display_mode(fs)
            self.log(f"Display mode -> {'Fullscreen' if fs else 'Windowed'}", 232)
            return

        if cmd in ("info", "status"):
            self.log(f"State: {game.state} | Mode: {game.game_mode} | Floor: {game.floor_level} | Timescale: {game.timescale}", 220)
            if game.player:
                self.log(f"Player HP: {game.player.hp}/{game.player.max_hp} | DMG: {game.player.damage} | Coins: {game.player.coins}", 210)
            return

        if player is None or room is None:
            self.log("Start a run first to run gameplay commands.", 165)
            return

        if cmd == "effect":
            if not args or args[0].lower() == "list":
                self.log("Player effects: " + ", ".join(EFFECT_DEFINITIONS.keys()), 210)
                self.log("Enemy effects: " + ", ".join(ENEMY_EFFECT_DEFINITIONS.keys()), 190)
                return
            sub = args[0].lower()
            if sub == "clear":
                if len(args) >= 2:
                    eid = args[1].lower()
                    player.clear_effects(eid)
                    self.log(f"Cleared effect '{eid}'.", 210)
                else:
                    player.clear_effects()
                    self.log("Cleared all active player effects.", 210)
                return
            if sub == "enemy":
                if len(args) < 2:
                    self.log("Usage: effect enemy <burn|poison|freeze|weaken|bleed> [sec]", 180)
                    return
                eid = args[1].lower()
                if eid not in ENEMY_EFFECT_DEFINITIONS:
                    self.log(f"Unknown enemy effect '{eid}'.", 160)
                    return
                dur = float(args[2]) if len(args) >= 3 else ENEMY_EFFECT_DEFINITIONS[eid]["default_dur"]
                frames = max(60.0, dur * 60.0)
                targets = [e for e in room.enemies if e.alive] + [b for b in room.bosses if b.alive]
                attr = f"{eid}_timer"
                for tgt in targets:
                    setattr(tgt, attr, max(getattr(tgt, attr, 0.0), frames))
                self.log(f"Applied '{eid}' ({dur:.1f}s) to {len(targets)} foes.", 232)
                return
            if sub == "give":
                if len(args) < 2:
                    self.log("Usage: effect give <effect_id> [sec]", 180)
                    return
                eid = args[1].lower()
                if eid not in EFFECT_DEFINITIONS:
                    self.log(f"Unknown effect '{eid}'. Try 'effect list'.", 160)
                    return
                try:
                    dur = float(args[2]) if len(args) >= 3 else EFFECT_DEFINITIONS[eid]["default_dur"]
                except ValueError:
                    dur = EFFECT_DEFINITIONS[eid]["default_dur"]
                player.add_effect(eid, dur)
                dur_lbl = "perm" if dur <= 0 else f"{dur:.1f}s"
                self.log(f"Effect '{eid}' applied ({dur_lbl}).", 240)
                return
            eid = sub
            if eid in EFFECT_DEFINITIONS:
                try:
                    dur = float(args[1]) if len(args) >= 2 else EFFECT_DEFINITIONS[eid]["default_dur"]
                except ValueError:
                    dur = EFFECT_DEFINITIONS[eid]["default_dur"]
                player.add_effect(eid, dur)
                self.log(f"Effect '{eid}' applied.", 240)
            else:
                self.log("Usage: effect <give|clear|list|enemy> [id] [sec]", 170)
            return

        if cmd == "give":
            if not args:
                self.log("Usage: give <item_id|random> [count]", 175)
                return
            iid = args[0].lower()
            try:
                cnt = int(clamp(int(args[1]), 1, 20)) if len(args) >= 2 else 1
            except ValueError:
                cnt = 1
            given = 0
            last_it = None
            for _ in range(cnt):
                if iid == "random":
                    it = get_random_item(player.collected_ids if len(player.collected_ids) < len(ITEM_POOL_65) - 2 else None)
                else:
                    it = get_item_by_id(iid)
                if it is None:
                    self.log(f"Unknown item id '{iid}'.", 160)
                    return
                player.apply_item(it)
                last_it = it
                given += 1
            if last_it is not None:
                self.log(f"Granted {given}x {tr_item_name(last_it)} [{last_it['id']}].", 240)
            return

        if cmd == "stat":
            if len(args) < 2:
                self.log("Usage: stat <hp|max_hp|soul|black|coins|bombs|keys|dmg|spd|luck|charge> <val>", 175)
                return
            key = args[0].lower()
            try:
                val = float(args[1])
            except ValueError:
                self.log("Numeric value required.", 160)
                return
            if key == "hp":
                player.max_hp = max(player.max_hp, int(clamp(val, 1, 24)))
                player.hp = int(clamp(val, 0, player.max_hp))
            elif key == "max_hp":
                player.max_hp = int(clamp(val, 0, 24))
                player.hp = min(player.hp, player.max_hp)
            elif key in ("soul", "soul_hp"):
                player.soul_hp = int(clamp(val, 0, 24))
            elif key in ("black", "black_hp"):
                player.black_hp = int(clamp(val, 0, 24))
            elif key == "coins":
                player.coins = int(clamp(val, 0, 999))
            elif key == "bombs":
                player.bombs = int(clamp(val, 0, 99))
            elif key == "keys":
                player.keys = int(clamp(val, 0, 99))
            elif key == "dmg":
                player.damage = clamp(val, 0.5, 999.0)
            elif key == "spd":
                player.speed = clamp(val, 1.5, 9.5)
            elif key == "luck":
                player.luck = int(clamp(val, -10, 50))
            elif key == "charge":
                if player.active_items:
                    player.active_charge = int(clamp(val, 0, player.max_charge))
            else:
                self.log(f"Unknown stat '{key}'.", 160)
                return
            self.log(f"Set {key} -> {val}.", 236)
            return

        if cmd == "heal":
            if player.max_hp <= 0:
                player.soul_hp = max(player.soul_hp, 6)
            else:
                player.hp = player.max_hp
            player.recharge_active(full=True)
            player.lantern_fuel = max(player.lantern_fuel, player.lantern_bonus)
            self.log("Restored full vitality, relic charge & lantern flame.", 240)
            return

        if cmd == "spawn":
            if not args:
                self.log("Usage: spawn <enemy|boss|pickup|pedestal|npc|machine|beggar|monolith> [id] [x y]", 175)
                return
            kind = args[0].lower()
            sx = clamp(player.x + 90.0, PLAYABLE_LEFT + 50, PLAYABLE_RIGHT - 50)
            sy = clamp(player.y, PLAYABLE_TOP + 50, PLAYABLE_BOTTOM - 50)
            eid = args[1].lower() if len(args) >= 2 else None
            if len(args) >= 4:
                try:
                    sx = clamp(float(args[2]), PLAYABLE_LEFT + 40, PLAYABLE_RIGHT - 40)
                    sy = clamp(float(args[3]), PLAYABLE_TOP + 40, PLAYABLE_BOTTOM - 40)
                except ValueError:
                    pass
            if kind == "enemy":
                et = eid if eid in REGULAR_ENEMY_TYPES else random.choice(REGULAR_ENEMY_TYPES)
                room.enemies.append(create_enemy(et, sx, sy, game.floor_level, game.floor_modifier))
                room.cleared = False
                self.log(f"Spawned enemy '{et}' at ({int(sx)}, {int(sy)}).", 236)
            elif kind == "boss":
                bk = eid if eid in PLAYABLE_BOSS_KEYS else random.choice(PLAYABLE_BOSS_KEYS)
                spawned = spawn_boss_for_room(room, bk, sx, sy, game.floor_level, game.floor_modifier)
                room.bosses.extend(spawned)
                room.cleared = False
                self.log(f"Spawned boss '{bk}' at ({int(sx)}, {int(sy)}).", 242)
            elif kind == "pickup":
                pk = eid if eid in PICKUP_TYPES else "soul_heart"
                room.pickups.append(Pickup(sx, sy, pk))
                self.log(f"Spawned pickup '{pk}'.", 230)
            elif kind == "pedestal":
                it = get_item_by_id(eid) if (eid and eid != "random") else get_random_item(player.collected_ids)
                if it is None:
                    self.log(f"Unknown item '{eid}'.", 160)
                    return
                room.pedestals.append(ItemPedestal(sx, sy, it))
                self.log(f"Spawned pedestal: {tr_item_name(it)} [{it['id']}].", 236)
            elif kind == "npc":
                nk = eid if eid in ("pale_wanderer", "silent_shadow", "ancient_oracle") else "pale_wanderer"
                room.mystical_npcs.append(MysticalNPC(sx, sy, nk))
                self.log(f"Spawned NPC '{nk}'.", 230)
            elif kind == "machine":
                mk = eid if eid in MACHINE_TYPES else random.choice(MACHINE_TYPES)
                room.machines.append(Machine(sx, sy, mk))
                self.log(f"Spawned machine '{mk}'.", 230)
            elif kind == "beggar":
                bg = eid if eid in BEGGAR_TYPES else random.choice(BEGGAR_TYPES)
                room.beggars.append(Beggar(sx, sy, bg))
                self.log(f"Spawned beggar '{bg}'.", 230)
            elif kind == "monolith":
                room.monoliths.append(LoreMonolith(sx, sy))
                self.log("Spawned Lore Monolith.", 230)
            else:
                self.log(f"Unknown spawn type '{kind}'.", 160)
            return

        if cmd == "room":
            if not args:
                self.log("Room types: " + ", ".join(ROOM_TYPE_LIST), 190)
                return
            rt = args[0].lower()
            if convert_room_type(room, rt, player.collected_ids, game.floor_level):
                self.log(f"Converted room to '{rt}'.", 238)
            else:
                self.log(f"Unknown room type '{rt}'.", 160)
            return

        if cmd == "floor":
            if not args:
                self.log(f"Current floor: {game.floor_level}", 200)
                return
            try:
                fl = int(clamp(int(args[0]), 1, 99))
            except ValueError:
                self.log("Floor must be an integer >= 1.", 160)
                return
            game._generate_floor(fl)
            game.ui.show_banner(f"{tr_floor(fl)}")
            self.log(f"Jumped to floor {fl}.", 240)
            return

        if cmd == "tp":
            if len(args) < 2:
                self.log("Usage: tp <x> <y>", 175)
                return
            try:
                tx = clamp(float(args[0]), PLAYABLE_LEFT + 20, PLAYABLE_RIGHT - 20)
                ty = clamp(float(args[1]), PLAYABLE_TOP + 20, PLAYABLE_BOTTOM - 20)
            except ValueError:
                self.log("Coordinates must be numbers.", 160)
                return
            player.x, player.y = tx, ty
            self.log(f"Teleported to ({int(tx)}, {int(ty)}).", 230)
            return

        if cmd == "reveal":
            player.compass_reveal = True
            for r in game.rooms.values():
                r.visited = True
                for d in r.doors.values():
                    if d.secret:
                        d.opened = True
            self.log("Revealed entire floor map and opened all secret doors.", 240)
            return

        if cmd == "killall":
            cnt = 0
            for e in room.enemies:
                if e.alive:
                    e.hp = 0.0
                    e.alive = False
                    cnt += 1
            for b in room.bosses:
                if b.alive:
                    b.hp = 0.0
                    b.alive = False
                    cnt += 1
            game.enemy_projectiles.clear()
            room.cleared = True
            self.log(f"Vanquished {cnt} active enemies/bosses.", 240)
            return

        if cmd == "clearroom":
            room.enemies.clear()
            room.bosses.clear()
            room.obstacles.clear()
            game.enemy_projectiles.clear()
            room.cleared = True
            self.log("Cleared all obstacles and enemies from current room.", 235)
            return

        if cmd == "timescale":
            if not args:
                self.log(f"Current timescale: {game.timescale:.2f}", 200)
                return
            try:
                ts = float(clamp(float(args[0]), 0.1, 4.0))
            except ValueError:
                self.log("Usage: timescale <0.1..4.0>", 160)
                return
            game.timescale = ts
            self.log(f"Timescale set to {ts:.2f}x.", 238)
            return

        if cmd == "noclip":
            player.noclip = not player.noclip
            self.log(f"Noclip {'ENABLED' if player.noclip else 'DISABLED'}.", 240)
            return

        if cmd == "hero":
            if not args:
                self.log("Heroes: " + ", ".join(h["id"] for h in HERO_ROSTER), 195)
                return
            hid = args[0].lower()
            valid = [h["id"] for h in HERO_ROSTER]
            if hid not in valid:
                self.log(f"Unknown hero '{hid}'.", 160)
                return
            h = get_hero(hid)
            player.hero = h
            player.hero_id = h["id"]
            player.damage = float(h["damage"])
            player.speed = float(h["speed"])
            player.fire_delay = float(h["fire_delay"])
            player.tear_speed = float(h["tear_speed"])
            player.tear_range = float(h["tear_range"])
            player.has_flight = bool(h["has_flight"])
            player.has_piercing = bool(h["has_piercing"])
            self.log(f"Hero switched to {h.get('name_en', h['name'])}.", 240)
            return

        if cmd == "unlock_all":
            if hasattr(game, "achievement_manager") and game.achievement_manager:
                for ach in ACHIEVEMENT_DEFS if 'ACHIEVEMENT_DEFS' in globals() else []:
                    game.achievement_manager.unlock(ach["id"])
            for it in ITEM_POOL_65:
                if it["id"] not in player.collected_ids:
                    player.collected_ids.append(it["id"])
            self.log("Unlocked all achievements and registered all items!", 245)
            return

        if cmd == "seed":
            if not args:
                self.log(f"Active run seed: {getattr(game, 'active_seed', 'N/A')}", 210)
                return
            game.active_seed = str(args[0])
            self.log(f"Seed set to '{game.active_seed}'.", 238)
            return

        if cmd == "stats":
            self.log(f"STATS -> HP: {player.hp}/{player.max_hp} | DMG: {player.damage:.2f} | SPD: {player.speed:.2f} | LUCK: {player.luck}", 220)
            self.log(f"          Coins: {player.coins} | Bombs: {player.bombs} | Keys: {player.keys} | Relics: {len(player.collected_ids)}", 210)
            return

        if cmd == "reload":
            room._baked_bg = None
            self.log("Reloaded current room graphics & cache.", 232)
            return

        if cmd == "freeze":
            game.editor.ai_paused = not getattr(game.editor, "ai_paused", False)
            self.log(f"AI & Enemies freeze {'ENABLED' if game.editor.ai_paused else 'DISABLED'}.", 240)
            return

        if cmd == "dump":
            try:
                import json
                dump_data = {
                    "floor": game.floor_level,
                    "mode": game.game_mode,
                    "hp": player.hp,
                    "max_hp": player.max_hp,
                    "dmg": player.damage,
                    "coins": player.coins,
                    "pos": [player.x, player.y],
                    "collected": player.collected_ids,
                }
                path = os.path.join(get_user_data_dir(), "dump_state.json")
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(dump_data, f, indent=2)
                self.log(f"Dumped game state to '{path}'.", 242)
            except Exception as ex:
                self.log(f"Dump error: {ex}", 165)
            return

        if cmd == "zoom":
            self.log("Zoom/scale is controlled via display & UI scale settings.", 210)
            return

        if cmd == "fly":
            player.has_flight = not player.has_flight
            self.log(f"Flight {'ENABLED' if player.has_flight else 'DISABLED'}.", 240)
            return

        if cmd == "kill":
            if args and args[0].lower() == "player":
                player.hp = 0
                self.log("Player terminated.", 180)
            else:
                cnt = 0
                for e in room.enemies:
                    if e.alive:
                        e.hp = 0.0
                        e.alive = False
                        cnt += 1
                for b in room.bosses:
                    if b.alive:
                        b.hp = 0.0
                        b.alive = False
                        cnt += 1
                self.log(f"Terminated {cnt} entities in current room.", 235)
            return

        self.log(f"Unknown command '{cmd}'. Type 'help'.", 160)

    def handle_event(self, event, game):
        if event.type == pygame.KEYDOWN:
            if self.is_toggle_key(event):
                self.toggle(False)
                return True
            if event.key == pygame.K_ESCAPE:
                self.toggle(False)
                return True
            if event.key == pygame.K_RETURN:
                cmd = self.input_text
                self.input_text = ""
                self.execute(cmd, game)
                return True
            if event.key == pygame.K_BACKSPACE:
                self.input_text = self.input_text[:-1]
                return True
            if event.key == pygame.K_TAB:
                self._autocomplete()
                return True
            if event.key == pygame.K_UP:
                if self.history:
                    self.hist_idx = len(self.history) - 1 if self.hist_idx == -1 else max(0, self.hist_idx - 1)
                    self.input_text = self.history[self.hist_idx]
                return True
            if event.key == pygame.K_DOWN:
                if self.history and self.hist_idx != -1:
                    if self.hist_idx >= len(self.history) - 1:
                        self.hist_idx = -1
                        self.input_text = ""
                    else:
                        self.hist_idx += 1
                        self.input_text = self.history[self.hist_idx]
                return True
            if event.key == pygame.K_PAGEUP:
                self.scroll_offset = min(max(0, len(self.logs) - 10), self.scroll_offset + 4)
                return True
            if event.key == pygame.K_PAGEDOWN:
                self.scroll_offset = max(0, self.scroll_offset - 4)
                return True
            uc = getattr(event, "unicode", "")
            if uc and uc.isprintable() and uc not in ("`", "~", "ё", "Ё") and len(self.input_text) < 96:
                self.input_text += uc
                return True
            return True
        if event.type == pygame.MOUSEWHEEL:
            self.scroll_offset = int(clamp(self.scroll_offset + (2 if event.y > 0 else -2), 0, max(0, len(self.logs) - 10)))
            return True
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button in (4, 5):
                delta = 2 if event.button == 4 else -2
                self.scroll_offset = int(clamp(self.scroll_offset + delta, 0, max(0, len(self.logs) - 10)))
                return True
            if event.button == 1:
                pos = getattr(event, "pos", None)
                if pos is not None:
                    panel_rect = pygame.Rect(24, 16, get_view_width() - 48, 336)
                    if self._close_rect().collidepoint(pos) or not panel_rect.collidepoint(pos):
                        self.toggle(False)
                        return True
        return True

    def draw(self, screen, ui):
        if not self.open:
            return
        self.cursor_timer += 1.0
        panel_w = get_view_width() - 48
        panel_h = 336
        px, py = 24, 16
        surf = get_panel_surf(panel_w, panel_h, fill_lum=8, fill_alpha=236, border_lum=148, radius=10)
        screen.blit(surf, (px, py))

        hdr = render_text_cached(
            ui.font_tiny,
            "DEV CONSOLE  [` / ~ / F1]   |   [TAB] AUTOCOMPLETE   |   [UP/DOWN] HISTORY   |   TYPE 'help' OR 'editor on'",
            PALETTE["text_muted"],
        )
        screen.blit(hdr, (px + 16, py + 10))
        close_rc = self._close_rect()
        pygame.draw.rect(screen, (36, 36, 36), close_rc, border_radius=4)
        pygame.draw.rect(screen, (140, 140, 140), close_rc, 1, border_radius=4)
        x_lbl = render_text_cached(ui.font_tiny, "X", (242, 242, 242))
        screen.blit(x_lbl, (close_rc.centerx - x_lbl.get_width() // 2, close_rc.centery - x_lbl.get_height() // 2))

        log_box = pygame.Rect(px + 14, py + 30, panel_w - 28, panel_h - 82)
        pygame.draw.rect(screen, (14, 14, 14), log_box, border_radius=6)
        pygame.draw.rect(screen, (64, 64, 64), log_box, 1, border_radius=6)

        max_lines = 12
        total = len(self.logs)
        end_idx = max(0, total - self.scroll_offset)
        start_idx = max(0, end_idx - max_lines)
        vis = self.logs[start_idx:end_idx]
        for i, (line, lum) in enumerate(vis):
            ts = render_text_cached(ui.font_small, line, (lum, lum, lum))
            screen.blit(ts, (log_box.x + 12, log_box.y + 8 + i * 20))

        inp_rect = pygame.Rect(px + 14, py + panel_h - 42, panel_w - 28, 30)
        pygame.draw.rect(screen, (20, 20, 20), inp_rect, border_radius=6)
        pygame.draw.rect(screen, (186, 186, 186), inp_rect, 1, border_radius=6)
        cursor_ch = "_" if int(self.cursor_timer * 0.08) % 2 == 0 else " "
        prompt_s = render_text_cached(ui.font_med, f"> {self.input_text}{cursor_ch}", PALETTE["text_main"])
        screen.blit(prompt_s, (inp_rect.x + 12, inp_rect.y + 6))


class RoomEditor:
    CATEGORIES = [
        ("OBSTACLES", "ПРЕПЯТСТВИЯ"),
        ("ENEMIES", "ВРАГИ"),
        ("BOSSES", "БОССЫ"),
        ("NPC & MACH", "НПС И МАШИНЫ"),
        ("LOOT", "ЛУТ И ПЬЕДЕСТ."),
        ("ROOM TOOLS", "ЗАЛ И ИНСТР."),
    ]

    def __init__(self):
        self.active = False
        self.unlocked = False
        self.category = 0
        self.item_idx = 0
        self.grid_snap = True
        self.freeze_ai = False
        self.hover_pos = _default_room_center()
        self.status_msg = ""

    def _category_items(self):
        if self.category == 0:
            return ["rock", "tinted_rock", "pillar", "pit", "spike", "poop", "urn", "brazier"]
        if self.category == 1:
            return list(REGULAR_ENEMY_TYPES)
        if self.category == 2:
            return list(PLAYABLE_BOSS_KEYS)
        if self.category == 3:
            return (
                [f"npc:{k}" for k in NPC_KEYS[:3]]
                + ["npc:lore_monolith"]
                + [f"beggar:{k}" for k in BEGGAR_TYPES]
                + [f"machine:{k}" for k in MACHINE_TYPES]
                + [f"keeper:{k}" for k in SHOPKEEPER_VARIANTS]
            )
        if self.category == 4:
            return PICKUP_TYPES + ["pedestal:random", "pedestal:devil", "pedestal:shop"]
        return [
            "tool:trapdoor",
            "tool:devil_door",
            "tool:sacrifice",
            "tool:dice",
            "tool:open_secrets",
        ] + [f"type:{rt}" for rt in ROOM_TYPE_LIST]

    def current_item(self):
        items = self._category_items()
        if not items:
            return "rock"
        self.item_idx = self.item_idx % len(items)
        return items[self.item_idx]

    def snap_pos(self, x, y):
        px = clamp(float(x), PLAYABLE_LEFT + 30, PLAYABLE_RIGHT - 30)
        py = clamp(float(y), PLAYABLE_TOP + 30, PLAYABLE_BOTTOM - 30)
        if self.grid_snap:
            px = PLAYABLE_LEFT + 24 + round((px - (PLAYABLE_LEFT + 24)) / 48.0) * 48.0
            py = PLAYABLE_TOP + 24 + round((py - (PLAYABLE_TOP + 24)) / 48.0) * 48.0
            px = clamp(px, PLAYABLE_LEFT + 26, PLAYABLE_RIGHT - 26)
            py = clamp(py, PLAYABLE_TOP + 26, PLAYABLE_BOTTOM - 26)
        return px, py

    def _cat_rects(self):
        ox = get_world_offset_x()
        return [pygame.Rect(ox + 210 + i * 144, 14, 138, 26) for i in range(len(self.CATEGORIES))]

    def place_at(self, game, x, y):
        room = game.current_room
        player = game.player
        if room is None or player is None:
            return False
        px, py = self.snap_pos(x, y)
        item_key = self.current_item()

        if self.category == 0:
            room.obstacles.append(Obstacle(px, py, item_key))
            self.status_msg = f"+ {item_key}"
            return True
        if self.category == 1:
            room.enemies.append(create_enemy(item_key, px, py, game.floor_level, game.floor_modifier))
            room.cleared = False
            self.status_msg = f"+ enemy {item_key}"
            return True
        if self.category == 2:
            room.bosses.extend(spawn_boss_for_room(room, item_key, px, py, game.floor_level, game.floor_modifier))
            room.cleared = False
            self.status_msg = f"+ boss {item_key}"
            return True
        if self.category == 3:
            sub_k, val = item_key.split(":", 1)
            if sub_k == "npc":
                if val == "lore_monolith":
                    room.monoliths.append(LoreMonolith(px, py))
                else:
                    room.mystical_npcs.append(MysticalNPC(px, py, val))
            elif sub_k == "beggar":
                room.beggars.append(Beggar(px, py, val))
            elif sub_k == "machine":
                room.machines.append(Machine(px, py, val))
            elif sub_k == "keeper":
                room.shopkeepers.append(Shopkeeper(px, py, val))
            self.status_msg = f"+ {val}"
            return True
        if self.category == 4:
            if item_key.startswith("pedestal:"):
                mode = item_key.split(":", 1)[1]
                it = get_random_item(player.collected_ids)
                if mode == "devil":
                    room.pedestals.append(ItemPedestal(px, py, it, devil_cost=1))
                elif mode == "shop":
                    room.pedestals.append(ItemPedestal(px, py, it, price=15))
                else:
                    room.pedestals.append(ItemPedestal(px, py, it))
                self.status_msg = f"+ {tr_item_name(it)}"
            else:
                room.pickups.append(Pickup(px, py, item_key))
                self.status_msg = f"+ {item_key}"
            return True

        sub_k, val = item_key.split(":", 1)
        if sub_k == "type":
            convert_room_type(room, val, player.collected_ids, game.floor_level)
            self.status_msg = f"room -> {val}"
        elif val == "trapdoor":
            room.trapdoor_rect = pygame.Rect(int(px - 26), int(py - 26), 52, 52)
            self.status_msg = "+ trapdoor"
        elif val == "devil_door":
            avail = [d for d in ("N", "E", "W", "S") if d not in room.doors]
            room.devil_door = Door(avail[0] if avail else "N", (99, 99), target_type="devil", locked=False)
            self.status_msg = "+ devil door"
        elif val == "sacrifice":
            room.sacrifice_spike = SacrificeSpike(px, py)
            self.status_msg = "+ sacrifice spike"
        elif val == "dice":
            room.dice_floor = DiceFloor(px, py, random.randint(1, 6))
            self.status_msg = "+ dice floor"
        elif val == "open_secrets":
            for d in room.doors.values():
                if d.secret:
                    d.opened = True
            self.status_msg = "secret doors opened"
        return True

    def remove_nearest(self, game, x, y, max_dist=52.0):
        room = game.current_room
        if room is None:
            return False
        best_dist = float(max_dist)
        best_action = None

        pools = [
            (room.obstacles, lambda o: o.rect.center),
            (room.enemies, lambda e: (e.x, e.y)),
            (room.bosses, lambda b: (b.x, b.y)),
            (room.pickups, lambda p: (p.x, p.y)),
            (room.pedestals, lambda p: (p.x, p.y)),
            (room.beggars, lambda b: (b.x, b.y)),
            (room.shopkeepers, lambda s: (s.x, s.y)),
            (room.machines, lambda m: (m.x, m.y)),
            (room.monoliths, lambda m: (m.x, m.y)),
            (room.mystical_npcs, lambda n: (n.x, n.y)),
        ]
        for lst, pos_fn in pools:
            for obj in lst:
                ox, oy = pos_fn(obj)
                d = math.hypot(ox - x, oy - y)
                if d < best_dist:
                    best_dist = d
                    best_action = (lst, obj)

        if best_action is not None:
            lst, obj = best_action
            lst.remove(obj)
            self.status_msg = "- removed object"
            return True
        if room.sacrifice_spike is not None and math.hypot(room.sacrifice_spike.x - x, room.sacrifice_spike.y - y) < max_dist:
            room.sacrifice_spike = None
            return True
        if room.dice_floor is not None and math.hypot(room.dice_floor.x - x, room.dice_floor.y - y) < max_dist:
            room.dice_floor = None
            return True
        if room.trapdoor_rect is not None and math.hypot(room.trapdoor_rect.centerx - x, room.trapdoor_rect.centery - y) < max_dist:
            room.trapdoor_rect = None
            return True
        return False

    def handle_event(self, event, game):
        ox = get_world_offset_x()
        if event.type == pygame.MOUSEMOTION:
            lx, ly = game._to_logical_pos(event.pos)
            self.hover_pos = (lx - ox, ly)
            return False
        if event.type == pygame.MOUSEWHEEL:
            items = self._category_items()
            if items:
                self.item_idx = (self.item_idx + (-1 if event.y > 0 else 1)) % len(items)
            return True
        if event.type == pygame.MOUSEBUTTONDOWN:
            mx, my = game._to_logical_pos(event.pos)
            wx = mx - ox
            self.hover_pos = (wx, my)
            if event.button == 4:
                items = self._category_items()
                if items:
                    self.item_idx = (self.item_idx - 1) % len(items)
                return True
            if event.button == 5:
                items = self._category_items()
                if items:
                    self.item_idx = (self.item_idx + 1) % len(items)
                return True
            if event.button == 1:
                for i, rc in enumerate(self._cat_rects()):
                    if rc.collidepoint(mx, my):
                        self.category = i
                        self.item_idx = 0
                        return True
                self.place_at(game, wx, my)
                return True
            if event.button == 3:
                self.remove_nearest(game, wx, my)
                return True
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_F2, pygame.K_ESCAPE):
                self.active = False
                return True
            if pygame.K_1 <= event.key <= pygame.K_6:
                self.category = event.key - pygame.K_1
                self.item_idx = 0
                return True
            if event.key == pygame.K_LEFTBRACKET:
                items = self._category_items()
                if items:
                    self.item_idx = (self.item_idx - 1) % len(items)
                return True
            if event.key == pygame.K_RIGHTBRACKET:
                items = self._category_items()
                if items:
                    self.item_idx = (self.item_idx + 1) % len(items)
                return True
            if event.key == pygame.K_g:
                self.grid_snap = not self.grid_snap
                return True
            if event.key == pygame.K_p:
                self.freeze_ai = not self.freeze_ai
                return True
            if event.key == pygame.K_c:
                if game.current_room is not None:
                    game.current_room.obstacles.clear()
                    game.current_room.enemies.clear()
                    game.current_room.bosses.clear()
                    game.current_room.cleared = True
                return True
        return False

    def draw(self, screen, ui, game):
        if not self.active:
            return
        lang = get_lang()
        ox = get_world_offset_x()
        if self.grid_snap:
            gx = PLAYABLE_LEFT + 24
            while gx < PLAYABLE_RIGHT - 16:
                pygame.draw.line(screen, (36, 36, 36), (ox + gx, PLAYABLE_TOP), (ox + gx, PLAYABLE_BOTTOM), 1)
                gx += 48
            gy = PLAYABLE_TOP + 24
            while gy < PLAYABLE_BOTTOM - 16:
                pygame.draw.line(screen, (36, 36, 36), (ox + PLAYABLE_LEFT, gy), (ox + PLAYABLE_RIGHT, gy), 1)
                gy += 48

        sx, sy = self.snap_pos(self.hover_pos[0], self.hover_pos[1])
        ghost = pygame.Rect(int(ox + sx - 22), int(sy - 22), 44, 44)
        pygame.draw.rect(screen, (220, 220, 220), ghost, 1, border_radius=5)
        draw_aa_circle(screen, (240, 240, 240), ox + sx, sy, 3.5)

        top_bar = get_panel_surf(892, 54, fill_lum=10, fill_alpha=220, border_lum=132, radius=8)
        screen.blit(top_bar, (ox + 194, 8))

        for i, ((en_lbl, ru_lbl), rc) in enumerate(zip(self.CATEGORIES, self._cat_rects())):
            sel = i == self.category
            pygame.draw.rect(screen, (236, 236, 236) if sel else (26, 26, 26), rc, border_radius=5)
            pygame.draw.rect(screen, (250, 250, 250) if sel else (82, 82, 82), rc, 1, border_radius=5)
            lbl = render_text_cached(ui.font_tiny, f"[{i + 1}] {(ru_lbl if lang == 'ru' else en_lbl)[:12]}", (12, 12, 12) if sel else PALETTE["text_main"])
            screen.blit(lbl, (rc.centerx - lbl.get_width() // 2, rc.y + 6))

        cur_key = self.current_item()
        items = self._category_items()
        ai_lbl = ("AI PAUSED [P]" if self.freeze_ai else "AI LIVE [P]") if lang == "en" else ("ИИ НА ПАУЗЕ [P]" if self.freeze_ai else "ИИ АКТИВЕН [P]")
        grid_lbl = ("GRID ON [G]" if self.grid_snap else "GRID FREE [G]") if lang == "en" else ("СЕТКА ВКЛ [G]" if self.grid_snap else "СЕТКА СВОБ [G]")
        info_txt = (
            f"ITEM [{self.item_idx + 1}/{len(items)}]: {cur_key.upper()}   |   [ / ] / Wheel   |   LMB Place  ·  RMB Erase   |   {grid_lbl}   ·   {ai_lbl}   ·   [F2] Exit"
        )
        info_s = render_text_cached(ui.font_tiny, info_txt, PALETTE["text_main"])
        screen.blit(info_s, (ox + 210, 44))
