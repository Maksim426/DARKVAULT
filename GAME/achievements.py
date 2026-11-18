import time
import pygame

from settings import GAME_SETTINGS, clamp, get_panel_surf, render_text_cached, fit_text_surf


ACHIEVEMENT_CATEGORIES = (
    "all",
    "combat",
    "boss",
    "explore",
    "economy",
    "heroes",
    "mastery",
    "daily",
    "coop",
    "mode",
)


def _tier_for_index(idx, total):
    ratio = idx / float(max(1, total - 1))
    if ratio < 0.35:
        return "common"
    if ratio < 0.65:
        return "rare"
    if ratio < 0.88:
        return "epic"
    return "mythic"


def _build_achievement_defs():
    defs = [
        {
            "id": "first_blood",
            "tier": "common",
            "cat": "combat",
            "ru": "Первая тень",
            "en": "First Shadow",
            "desc_ru": "Одолейте 10 врагов в подземелье",
            "desc_en": "Slay 10 dungeon enemies",
            "stat": "kills",
            "target": 10,
        },
        {
            "id": "slayer_100",
            "tier": "rare",
            "cat": "combat",
            "ru": "Охотник Бездны",
            "en": "Abyss Hunter",
            "desc_ru": "Одолейте 100 врагов за карьеру",
            "desc_en": "Slay 100 enemies across runs",
            "stat": "kills",
            "target": 100,
        },
        {
            "id": "slayer_500",
            "tier": "mythic",
            "cat": "combat",
            "ru": "Жнец Подземелья",
            "en": "Vault Reaper",
            "desc_ru": "Одолейте 500 врагов за карьеру",
            "desc_en": "Slay 500 enemies across runs",
            "stat": "kills",
            "target": 500,
        },
        {
            "id": "boss_bane_1",
            "tier": "common",
            "cat": "boss",
            "ru": "Убийца Стража",
            "en": "Warden Breaker",
            "desc_ru": "Победите первого босса",
            "desc_en": "Defeat your first floor boss",
            "stat": "bosses_killed",
            "target": 1,
        },
        {
            "id": "boss_bane_15",
            "tier": "epic",
            "cat": "boss",
            "ru": "Покоритель Кошмаров",
            "en": "Nightmare Conqueror",
            "desc_ru": "Победите 15 боссов за карьеру",
            "desc_en": "Defeat 15 bosses across runs",
            "stat": "bosses_killed",
            "target": 15,
        },
        {
            "id": "victory_classic",
            "tier": "rare",
            "cat": "mastery",
            "ru": "Выход из Тьмы",
            "en": "Out of the Vault",
            "desc_ru": "Одержите первую победу в забеге",
            "desc_en": "Complete a winning run",
            "stat": "wins",
            "target": 1,
        },
        {
            "id": "victory_5",
            "tier": "mythic",
            "cat": "mastery",
            "ru": "Хранитель Монолита",
            "en": "Monolith Warden",
            "desc_ru": "Одержите 5 побед за разные забеги",
            "desc_en": "Win 5 complete runs",
            "stat": "wins",
            "target": 5,
        },
        {
            "id": "floor_3",
            "tier": "common",
            "cat": "explore",
            "ru": "Спуск в Катакомбы",
            "en": "Into Catacombs",
            "desc_ru": "Доберитесь до 3-го яруса подземелья",
            "desc_en": "Reach Dungeon Floor 3",
            "stat": "best_floor",
            "target": 3,
        },
        {
            "id": "floor_5",
            "tier": "rare",
            "cat": "explore",
            "ru": "Дно Бездны",
            "en": "Abyss Bottom",
            "desc_ru": "Доберитесь до 5-го яруса или глубже",
            "desc_en": "Reach Floor 5 or deeper",
            "stat": "best_floor",
            "target": 5,
        },
        {
            "id": "endless_10",
            "tier": "epic",
            "cat": "mode",
            "ru": "Бесконечный Шторм",
            "en": "Endless Storm",
            "desc_ru": "Переживите 10 волн в Бесконечной Бездне",
            "desc_en": "Survive 10 waves in Endless Abyss",
            "stat": "best_wave",
            "target": 10,
        },
        {
            "id": "ambush_master",
            "tier": "rare",
            "cat": "combat",
            "ru": "Призрачный Клинок",
            "en": "Phantom Ambush",
            "desc_ru": "Убейте 15 врагов ударом из невидимости [V]",
            "desc_en": "Eliminate 15 foes via stealth ambush [V]",
            "stat": "ambush_kills",
            "target": 15,
        },
        {
            "id": "sky_breaker",
            "tier": "rare",
            "cat": "combat",
            "ru": "Небесный Удар",
            "en": "Sky Breaker",
            "desc_ru": "Поразите 15 врагов приземлением прыжка [F]",
            "desc_en": "Crush 15 enemies with Jump-Slam [F]",
            "stat": "slam_kills",
            "target": 15,
        },
        {
            "id": "demolitionist",
            "tier": "common",
            "cat": "combat",
            "ru": "Подрывник Склепа",
            "en": "Vault Sapper",
            "desc_ru": "Уничтожьте 20 врагов взрывами бомб и слёз",
            "desc_en": "Defeat 20 foes with blasts and bombs",
            "stat": "explosion_kills",
            "target": 20,
        },
        {
            "id": "secret_seeker",
            "tier": "common",
            "cat": "explore",
            "ru": "Тайный Взломщик",
            "en": "Secret Breacher",
            "desc_ru": "Вскройте бомбой 3 тайные комнаты",
            "desc_en": "Breach 3 secret rooms with bombs",
            "stat": "secrets_found",
            "target": 3,
        },
        {
            "id": "flawless_floor",
            "tier": "epic",
            "cat": "mastery",
            "ru": "Неприкасаемый",
            "en": "Untouchable",
            "desc_ru": "Пройдите целый ярус, не потеряв здоровья",
            "desc_en": "Clear an entire floor without taking damage",
            "stat": "flawless_floors",
            "target": 1,
        },
        {
            "id": "coop_brothers",
            "tier": "epic",
            "cat": "coop",
            "ru": "Плечом к Плечу",
            "en": "Side by Side",
            "desc_ru": "Одержите победу вдвоём в локальном коопе",
            "desc_en": "Win a run in 2-Player Same-Screen Co-op",
            "stat": "coop_wins",
            "target": 1,
        },
        {
            "id": "merchant_patron",
            "tier": "common",
            "cat": "economy",
            "ru": "Постоялец Лавки",
            "en": "Merchant Patron",
            "desc_ru": "Совершите 12 покупок в лавке",
            "desc_en": "Purchase 12 goods in dungeon shops",
            "stat": "shop_purchases",
            "target": 12,
        },
        {
            "id": "arcade_shark",
            "tier": "rare",
            "cat": "economy",
            "ru": "Король Аркады",
            "en": "Arcade Shark",
            "desc_ru": "Используйте игровые автоматы 15 раз",
            "desc_en": "Operate dungeon machines 15 times",
            "stat": "machine_uses",
            "target": 15,
        },
        {
            "id": "generous_soul",
            "tier": "common",
            "cat": "economy",
            "ru": "Щедрая Душа",
            "en": "Generous Soul",
            "desc_ru": "Помогите нищим 8 раз",
            "desc_en": "Make 8 offerings to beggars",
            "stat": "beggar_uses",
            "target": 8,
        },
        {
            "id": "collector_30",
            "tier": "rare",
            "cat": "explore",
            "ru": "Собиратель Реликвий",
            "en": "Relic Collector",
            "desc_ru": "Соберите 30 артефактов с пьедесталов",
            "desc_en": "Collect 30 relics from pedestals",
            "stat": "items_collected",
            "target": 30,
        },
        {
            "id": "hoarder_200",
            "tier": "rare",
            "cat": "economy",
            "ru": "Звон Монет",
            "en": "Coin Hoarder",
            "desc_ru": "Соберите 200 монет за карьеру",
            "desc_en": "Collect 200 coins across runs",
            "stat": "coins_collected",
            "target": 200,
        },
        {
            "id": "graduate",
            "tier": "common",
            "cat": "mastery",
            "ru": "Готовый к Тьме",
            "en": "Vault Initiate",
            "desc_ru": "Пройдите интерактивное обучение",
            "desc_en": "Complete the interactive Training Vault",
            "stat": "tutorial_done",
            "target": 1,
        },
        {
            "id": "versatile_hero",
            "tier": "epic",
            "cat": "heroes",
            "ru": "Многоликий",
            "en": "Many Faces",
            "desc_ru": "Победите за 3 разных персонажей",
            "desc_en": "Win runs with 3 different heroes",
            "stat": "len:heroes_won",
            "target": 3,
        },
        {
            "id": "mode_explorer",
            "tier": "rare",
            "cat": "mode",
            "ru": "Испытатель Режимов",
            "en": "Mode Explorer",
            "desc_ru": "Сыграйте в 4 разных режима игры",
            "desc_en": "Play at least 4 distinct game modes",
            "stat": "len:modes_played",
            "target": 4,
        },
        {
            "id": "boss_encyclopedia",
            "tier": "mythic",
            "cat": "boss",
            "ru": "Хроникёр Стражей",
            "en": "Warden Chronicler",
            "desc_ru": "Повергните 10 уникальных видов боссов",
            "desc_en": "Defeat 10 distinct boss types",
            "stat": "len:boss_types_killed",
            "target": 10,
        },
        {
            "id": "ash_breaker",
            "tier": "epic",
            "cat": "boss",
            "ru": "Пепельный Колосс повержен",
            "en": "Ash Extinguisher",
            "desc_ru": "Одолейте Пепельного Колосса",
            "desc_en": "Defeat the Ash Colossus",
            "stat": "contains:boss_types_killed:ash_colossus",
            "target": 1,
        },
        {
            "id": "mirror_shatter",
            "tier": "mythic",
            "cat": "boss",
            "ru": "Осколки Короны",
            "en": "Shattered Reflections",
            "desc_ru": "Одолейте Королеву Зеркал или Хроно-Жнеца",
            "desc_en": "Defeat either Mirror Queen or Chrono Reaper",
            "stat": "any_contains:boss_types_killed:mirror_queen,chrono_reaper",
            "target": 1,
        },
        {
            "id": "backup_guardian",
            "tier": "common",
            "cat": "mastery",
            "ru": "Хранитель Архива",
            "en": "Archive Keeper",
            "desc_ru": "Создайте или восстановите резервную копию .dvbackup",
            "desc_en": "Create or restore a .dvbackup full archive",
            "stat": "manual",
            "target": 1,
        },
    ]

    used_ids = {d["id"] for d in defs}

    def _add(aid, tier, cat, ru, en, desc_ru, desc_en, stat, target):
        if aid in used_ids:
            return
        used_ids.add(aid)
        defs.append(
            {
                "id": aid,
                "tier": tier,
                "cat": cat,
                "ru": ru,
                "en": en,
                "desc_ru": desc_ru,
                "desc_en": desc_en,
                "stat": stat,
                "target": int(target),
            }
        )

    # Diverse situational, mechanical & mastery achievements
    _add(
        "terminal_dj", "common", "explore",
        "Сигнал из Бездны", "Abyssal Broadcast",
        "Переключите трек на архивном терминале", "Switch a track on an archive computer terminal",
        "computer_uses", 1,
    )
    _add(
        "vault_melomaniac", "epic", "explore",
        "Меломан Склепа", "Vault Audiophile",
        "Прослушайте все 4 трека архивных терминалов", "Listen to all 4 archive terminal tracks",
        "len:computer_tracks_heard", 4,
    )
    _add(
        "bullet_parry_1", "common", "combat",
        "Зеркальный Взмах", "Mirror Slash",
        "Отразите вражеский снаряд ударом ближнего боя", "Deflect an enemy projectile with a melee strike",
        "projectiles_deflected", 1,
    )
    _add(
        "bullet_parry_25", "rare", "combat",
        "Мастер Парирования", "Parry Virtuoso",
        "Отразите 25 вражеских снарядов за карьеру", "Deflect 25 enemy projectiles across runs",
        "projectiles_deflected", 25,
    )
    _add(
        "combo_finisher_10", "rare", "combat",
        "Сокрушительный Финал", "Combo Finisher",
        "Проведите 10 финальных ударов 3-го комбо-шага", "Land 10 third-step melee combo finishers",
        "melee_finishers", 10,
    )
    _add(
        "flawless_boss_win", "rare", "boss",
        "Чистая Дуэль", "Untouched Duel",
        "Одолейте босса, не получив урона в его комнате", "Defeat a boss without taking damage in its room",
        "boss_flawless", 1,
    )
    _add(
        "flawless_boss_5", "mythic", "boss",
        "Призрачный Палач", "Phantom Executioner",
        "Зачистите 5 комнат боссов без единого ранения", "Clear 5 boss rooms without taking any damage",
        "boss_flawless", 5,
    )
    _add(
        "low_hp_clutch", "rare", "mastery",
        "На Волоске", "On the Brink",
        "Зачистите комнату, имея не более 1 целого сердца", "Clear a room with 1 full heart or less remaining",
        "low_hp_clutches", 1,
    )
    _add(
        "brink_survivor", "epic", "mastery",
        "Упрямая Искра", "Stubborn Spark",
        "Выживите и зачистите 5 комнат на краю гибели", "Clear 5 rooms while on the brink of death",
        "low_hp_clutches", 5,
    )
    _add(
        "overkill_build", "epic", "mastery",
        "Абсолютная Мощь", "Overwhelming Force",
        "Разгоните показатель урона до 12.0+ за один забег", "Reach 12.0+ effective damage in a single run",
        "peak_dmg_x10", 120,
    )
    _add(
        "hypersonic", "rare", "mastery",
        "Ртутный Шаг", "Quicksilver Step",
        "Разгоните скорость передвижения до 7.5+ за забег", "Reach 7.5+ effective movement speed in a run",
        "peak_speed_x10", 75,
    )
    _add(
        "hoarder_10", "rare", "explore",
        "Живой Арсенал", "Living Arsenal",
        "Соберите 10+ артефактов в рамках одного забега", "Carry 10 or more artifacts in a single run",
        "max_run_items", 10,
    )
    _add(
        "coin_vault_50", "rare", "economy",
        "Полный Кошель", "Gilded Purse",
        "Накопите 50+ монет на руках за один забег", "Hold 50 or more coins at once in a single run",
        "max_run_coins", 50,
    )
    _add(
        "monolith_awakener", "rare", "explore",
        "Шёпот Обелисков", "Obelisk Whisperer",
        "Активируйте 5 древних монолитов знаний", "Activate 5 ancient lore monoliths",
        "monoliths_activated", 5,
    )
    _add(
        "devil_pact_1", "common", "economy",
        "Печать Крови", "Blood Covenant",
        "Заключите 1 сделку на пьедестале Бездны", "Make 1 deal at an Abyssal devil pedestal",
        "devil_deals", 1,
    )
    _add(
        "devil_pact_5", "epic", "economy",
        "Должник Тьмы", "Tenant of Darkness",
        "Заключите 5 сделок на пьедесталах Бездны", "Make 5 deals at Abyssal devil pedestals",
        "devil_deals", 5,
    )
    _add(
        "tinted_hunter", "common", "explore",
        "Глаз Рудокопа", "Delver's Eye",
        "Взорвите 5 меченых камней бомбами", "Blow up 5 tinted rocks with bombs",
        "tinted_rocks_bombed", 5,
    )
    _add(
        "gamble_breaker", "common", "economy",
        "Крушитель Автоматов", "Machine Breaker",
        "Взорвите 5 игровых или торговых автоматов", "Destroy 5 slot or arcade machines with bombs",
        "machines_bombed", 5,
    )
    _add(
        "library_visitor", "rare", "explore",
        "Хранитель Фолиантов", "Tome Keeper",
        "Посетите 3 комнаты-библиотеки", "Visit 3 library rooms",
        "libraries_visited", 3,
    )
    _add(
        "curse_walker", "rare", "explore",
        "Сквозь Шипы", "Through the Thorns",
        "Перешагните порог 3 проклятых комнат", "Enter 3 curse rooms",
        "curse_rooms_visited", 3,
    )
    _add(
        "special_cartographer", "epic", "explore",
        "Тайный Картограф", "Arcane Cartographer",
        "Посетите 7 различных типов особых комнат", "Visit 7 distinct special room types",
        "len:special_rooms_visited", 7,
    )
    _add(
        "chaos_drafter", "common", "mode",
        "Архитектор Хаоса", "Chaos Architect",
        "Сыграйте 3 забега в режиме Драфта Хаоса", "Draft starting artifacts 3 times in Chaos Draft",
        "chaos_drafts", 3,
    )
    _add(
        "boss_rush_clear", "mythic", "mode",
        "Повелитель Арены", "Arena Sovereign",
        "Завершите победой режим Босс-Раш", "Win a full run in Boss Rush mode",
        "boss_rush_wins", 1,
    )
    _add(
        "fading_light_win", "mythic", "mode",
        "Неугасимый Фитиль", "Undying Wick",
        "Одержите победу в режиме Гаснущего Света", "Win a full run in Fading Light mode",
        "fading_light_wins", 1,
    )
    _add(
        "lan_partner", "rare", "coop",
        "Сетевой Союз", "Network Pact",
        "Начните совместный сетевой LAN-забег", "Start a cooperative LAN multiplayer run",
        "lan_runs", 1,
    )
    _add(
        "mod_architect", "rare", "mode",
        "Исказитель Кода", "Code Sculptor",
        "Начните забег с активной пользовательской модификацией", "Start a run with an active custom mod",
        "modded_runs", 1,
    )
    _add(
        "chronicle_reader", "common", "mastery",
        "Читатель Скрижалей", "Scroll Reader",
        "Откройте Кодекс или Хронику Бездны", "Open the Codex or Vault Chronicle",
        "codex_opened", 1,
    )
    _add(
        "ethereal_triumph", "mythic", "heroes",
        "Триумф Эфира", "Ethereal Triumph",
        "Завершите победный забег за призрачного героя Потерянный", "Win a full run playing as The Lost",
        "contains:heroes_won:lost", 1,
    )

    def _add_ladder(prefix, cat, stat, targets, ru_fmt, en_fmt, desc_ru_fmt, desc_en_fmt):
        tot = len(targets)
        for idx, tgt in enumerate(targets):
            _add(
                f"{prefix}_{tgt}",
                _tier_for_index(idx, tot),
                cat,
                ru_fmt.format(n=tgt, i=idx + 1),
                en_fmt.format(n=tgt, i=idx + 1),
                desc_ru_fmt.format(n=tgt),
                desc_en_fmt.format(n=tgt),
                stat,
                tgt,
            )

    # 1. Combat ladders
    _add_ladder(
        "kills_tier", "combat", "kills",
        [5, 15, 25, 40, 60, 80, 125, 175, 250, 350, 450, 650, 850, 1100, 1500, 2000, 2800, 3600, 4800, 6500, 8500, 11000, 15000, 20000, 30000],
        "Клинок Тьмы #{i} ({n})", "Shadow Blade #{i} ({n})",
        "Победите {n} врагов за карьеру", "Defeat {n} enemies across runs",
    )
    _add_ladder(
        "ambush_tier", "combat", "ambush_kills",
        [1, 3, 5, 8, 12, 20, 30, 45, 65, 90, 125, 175, 250, 350, 500],
        "Тень Засады #{i}", "Ambush Shade #{i}",
        "Убейте {n} врагов из невидимости [V]", "Slay {n} foes from stealth [V]",
    )
    _add_ladder(
        "slam_tier", "combat", "slam_kills",
        [1, 3, 5, 8, 12, 20, 30, 45, 65, 90, 125, 175, 250, 350, 500],
        "Сейсмик #{i}", "Seismic Crusher #{i}",
        "Убейте {n} врагов приземлением [F]", "Crush {n} foes with jump slam [F]",
    )
    _add_ladder(
        "blast_tier", "combat", "explosion_kills",
        [1, 3, 6, 10, 15, 25, 35, 50, 75, 100, 140, 190, 260, 350, 500],
        "Мастер Детонации #{i}", "Blast Master #{i}",
        "Уничтожьте {n} врагов взрывами", "Destroy {n} enemies with blasts",
    )
    _add_ladder(
        "dash_tier", "combat", "dashes_used",
        [5, 15, 30, 50, 80, 120, 180, 260, 360, 500, 700, 950, 1250, 1600, 2200, 3000],
        "Призрачный Рывок #{i}", "Phantom Dash #{i}",
        "Совершите {n} рывков [Shift]", "Perform {n} dashes [Shift]",
    )
    _add_ladder(
        "stealth_tier", "combat", "stealth_uses",
        [1, 4, 8, 15, 25, 40, 60, 90, 130, 180, 250, 340, 450, 600],
        "Ходящая Тень #{i}", "Walking Shade #{i}",
        "Активируйте невидимость [V] {n} раз", "Activate stealth [V] {n} times",
    )
    _add_ladder(
        "bomb_tier", "combat", "bombs_used",
        [1, 5, 10, 18, 30, 45, 70, 100, 140, 190, 260, 350, 480, 650],
        "Пиротехник Бездны #{i}", "Abyss Sapper #{i}",
        "Заложите {n} бомб в подземелье", "Place {n} bombs in the dungeon",
    )
    _add_ladder(
        "melee_hits_tier", "combat", "melee_hits",
        [5, 20, 50, 100, 180, 300, 450, 650, 900, 1250],
        "Мастер Ближнего Боя #{i}", "Close Quarters #{i}",
        "Нанесите {n} ударов в ближнем бою", "Land {n} melee cleave strikes",
    )
    _add_ladder(
        "melee_kills_tier", "combat", "melee_kills",
        [1, 5, 12, 25, 45, 75, 120, 180, 260, 380],
        "Теневой Клинок #{i}", "Iron Cleaver #{i}",
        "Убейте {n} врагов ближним ударом", "Slay {n} enemies with melee attacks",
    )
    _add_ladder(
        "turrets_tier", "combat", "turrets_destroyed",
        [1, 3, 8, 15, 25, 40, 65, 100],
        "Охотник на Турели #{i}", "Turret Breaker #{i}",
        "Разрушьте {n} стреляющих турелей", "Destroy {n} dungeon sentry turrets",
    )
    _add_ladder(
        "obstacles_tier", "explore", "obstacles_destroyed",
        [5, 20, 50, 100, 180, 300, 450, 700],
        "Крушитель Преград #{i}", "Obstacle Smasher #{i}",
        "Разбейте {n} преград, урн и баррикад", "Smash {n} urns, barriers & obstacles",
    )
    _add_ladder(
        "active_uses_tier", "mastery", "active_uses",
        [1, 5, 12, 25, 45, 75, 120, 180, 260],
        "Пробудитель Реликвий #{i}", "Relic Channeler #{i}",
        "Активируйте реликвию {n} раз", "Activate relics {n} times",
    )

    # 2. Boss ladders + all individual bosses
    _add_ladder(
        "boss_kills_tier", "boss", "bosses_killed",
        [2, 3, 5, 7, 10, 12, 20, 25, 35, 50, 65, 85, 110, 140, 180, 225, 300, 400],
        "Гроза Стражей #{i} ({n})", "Warden Bane #{i} ({n})",
        "Победите {n} боссов за карьеру", "Defeat {n} bosses across runs",
    )
    _add_ladder(
        "boss_unique_tier", "boss", "len:boss_types_killed",
        [2, 4, 6, 8, 12, 15, 20, 25, 30, 35, 40, 50, 60, 68],
        "Коллекционер Стражей #{i}", "Boss Archivist #{i}",
        "Одолейте {n} уникальных видов боссов", "Defeat {n} unique boss species",
    )

    try:
        from i18n import TEXTS

        boss_ru_map = TEXTS.get("ru", {}).get("boss_names", {})
        boss_en_map = TEXTS.get("en", {}).get("boss_names", {})
    except Exception:
        boss_ru_map, boss_en_map = {}, {}

    # Canonical unique boss keys (skip duplicate alias keys like duke_of_flies/larry_jr if canonical exists)
    skip_aliases = {"duke_of_flies", "larry_jr"}
    for idx, bkey in enumerate(sorted(boss_ru_map.keys())):
        if bkey in skip_aliases:
            continue
        b_ru = boss_ru_map.get(bkey, bkey.upper()).title()
        b_en = boss_en_map.get(bkey, bkey.replace("_", " ").upper()).title()
        _add(
            f"boss_kill_{bkey}",
            "epic" if idx % 4 == 0 else "rare",
            "boss",
            f"Охота: {b_ru}",
            f"Slay: {b_en}",
            f"Победите босса {b_ru}",
            f"Defeat the boss {b_en}",
            f"contains:boss_types_killed:{bkey}",
            1,
        )

    # 3. Exploration ladders
    _add_ladder(
        "rooms_tier", "explore", "rooms_visited",
        [5, 15, 30, 50, 80, 120, 175, 240, 320, 420, 550, 700, 900, 1150, 1500, 2000, 2800, 3800, 5000],
        "Искатель Залов #{i}", "Chamber Explorer #{i}",
        "Исследуйте {n} новых комнат", "Explore {n} new rooms",
    )
    _add_ladder(
        "doors_tier", "explore", "doors_opened",
        [1, 3, 6, 10, 15, 22, 32, 45, 65, 90, 125, 175, 250],
        "Взломщик Замков #{i}", "Lockbreaker #{i}",
        "Откройте {n} запертых дверей", "Unlock {n} locked doors",
    )
    _add_ladder(
        "secrets_tier", "explore", "secrets_found",
        [1, 2, 5, 8, 12, 18, 25, 35, 50, 70, 100],
        "Чуткий Взор #{i}", "Secret Eye #{i}",
        "Вскройте {n} тайных комнат", "Breach {n} secret rooms",
    )
    _add_ladder(
        "floor_tier", "explore", "best_floor",
        [2, 4, 6, 7, 8, 9, 10, 12, 15, 18, 20, 25],
        "Спуск на Ярус {n}", "Depths Floor {n}",
        "Достигните {n}-го яруса подземелья", "Reach Dungeon Floor {n}",
    )
    _add_ladder(
        "relics_tier", "explore", "items_collected",
        [1, 5, 10, 18, 25, 40, 60, 85, 115, 150, 200, 260, 340, 450, 600, 800, 1000],
        "Хранитель Реликвий #{i}", "Relic Keeper #{i}",
        "Подберите {n} артефактов", "Collect {n} relics",
    )

    # 4. Economy & NPCs
    _add_ladder(
        "coins_tier", "economy", "coins_collected",
        [10, 25, 50, 90, 140, 250, 400, 600, 900, 1300, 1800, 2500, 3500, 5000, 7500, 10000],
        "Серебряная Казна #{i}", "Silver Treasury #{i}",
        "Соберите {n} монет за карьеру", "Collect {n} coins across runs",
    )
    _add_ladder(
        "shop_tier", "economy", "shop_purchases",
        [1, 3, 6, 10, 18, 25, 38, 55, 75, 100, 140, 190, 250],
        "Торговый Договор #{i}", "Merchant Guild #{i}",
        "Купите {n} товаров в лавке", "Buy {n} items in shops",
    )
    _add_ladder(
        "machine_tier", "economy", "machine_uses",
        [1, 3, 6, 10, 20, 30, 45, 65, 90, 125, 175, 240],
        "Шестерни Удачи #{i}", "Fortune Gears #{i}",
        "Используйте автоматы {n} раз", "Operate machines {n} times",
    )
    _add_ladder(
        "beggar_tier", "economy", "beggar_uses",
        [1, 3, 5, 12, 18, 28, 40, 60, 85, 120],
        "Милосердие #{i}", "Almsgiver #{i}",
        "Пожертвуйте нищим {n} раз", "Give offerings to beggars {n} times",
    )

    # 5. Mastery, Quests, Runs, Wins, Modes, Coop, Daily
    _add_ladder(
        "runs_tier", "mastery", "runs",
        [1, 3, 5, 10, 15, 25, 40, 60, 85, 120, 160, 220, 300, 400, 550],
        "Скиталец Мрака #{i}", "Dark Wanderer #{i}",
        "Начните {n} спусков в подземелье", "Embark on {n} dungeon runs",
    )
    _add_ladder(
        "wins_tier", "mastery", "wins",
        [2, 3, 7, 10, 15, 20, 30, 45, 65, 90, 125],
        "Триумф Бездны #{i}", "Abyss Triumph #{i}",
        "Одержите {n} побед в подземелье", "Achieve {n} run victories",
    )
    _add_ladder(
        "quests_tier", "mastery", "quests_completed",
        [1, 2, 4, 7, 10, 15, 22, 30, 42, 56, 75, 100, 135, 180, 240, 320],
        "Контрактник #{i} ({n})", "Bounty Hunter #{i} ({n})",
        "Выполните {n} квестов (контрактов)", "Complete {n} bounties (quests)",
    )
    _add_ladder(
        "nodmg_rooms_tier", "mastery", "no_damage_rooms",
        [1, 5, 10, 20, 35, 55, 80, 115, 160, 220, 300, 400, 550, 750, 1000],
        "Холодный Расчёт #{i}", "Untouched Tactician #{i}",
        "Зачистите {n} комнат без урона", "Clear {n} combat rooms flawlessly",
    )
    _add_ladder(
        "flawless_tier", "mastery", "flawless_floors",
        [2, 3, 5, 8, 12, 18, 25, 35],
        "Призрачный Шаг #{i}", "Flawless Stride #{i}",
        "Пройдите {n} ярусов без единого удара", "Clear {n} floors without taking hits",
    )
    _add_ladder(
        "dice_tier", "mastery", "dice_uses",
        [1, 2, 4, 7, 10, 15, 22, 30, 45],
        "Воля Кости #{i}", "Dice Fate #{i}",
        "Активируйте Зал Кости {n} раз", "Trigger Dice Rooms {n} times",
    )
    _add_ladder(
        "sacrifice_tier", "mastery", "sacrifice_uses",
        [1, 3, 6, 10, 16, 25, 38, 55, 80],
        "Алтарь Крови #{i}", "Blood Altar #{i}",
        "Принесите {n} жертв на алтаре шипов", "Make {n} sacrifices on thorn altars",
    )

    # Modes & Waves & Seeds
    _add_ladder(
        "wave_tier", "mode", "best_wave",
        [3, 5, 8, 15, 20, 25, 30, 40, 50, 65, 80, 100],
        "Шторм Волн {n}", "Endless Wave {n}",
        "Переживите {n} волн в Бесконечной Бездне", "Reach Wave {n} in Endless Abyss",
    )
    _add_ladder(
        "seed_tier", "mode", "seeded_runs",
        [1, 3, 5, 10, 18, 30, 50, 80],
        "Хроника Сидов #{i}", "Seed Chronicler #{i}",
        "Сыграйте {n} забегов по заданному сиду", "Play {n} runs with a custom or shared seed",
    )
    for m_cnt in (2, 3, 5, 6, 7):
        _add(
            f"modes_distinct_{m_cnt}",
            "rare" if m_cnt < 5 else "epic",
            "mode",
            f"Мастер Режимов ({m_cnt}/7)",
            f"Mode Veteran ({m_cnt}/7)",
            f"Сыграйте в {m_cnt} разных режимах",
            f"Play {m_cnt} distinct game modes",
            "len:modes_played",
            m_cnt,
        )

    # Coop ladder
    _add_ladder(
        "coop_tier", "coop", "coop_wins",
        [2, 3, 5, 8, 12, 20],
        "Братство Тьмы #{i}", "Dark Brotherhood #{i}",
        "Победите в коопе 2P {n} раз", "Win {n} runs in 2P co-op",
    )

    # Daily rewards ladders
    _add_ladder(
        "daily_claims_tier", "daily", "daily_claims",
        [1, 2, 4, 7, 10, 14, 21, 30, 45, 60, 90, 120],
        "Ежедневный Обет #{i}", "Daily Vow #{i}",
        "Заберите ежедневную награду {n} раз", "Claim daily rewards {n} times",
    )
    _add_ladder(
        "daily_streak_tier", "daily", "max_daily_streak",
        [2, 3, 5, 7, 10, 14, 21, 30],
        "Серия Верности: {n} дн.", "Loyalty Streak: {n}d",
        "Держите серию ежедневных наград {n} дней", "Maintain a {n}-day daily reward streak",
    )

    # Hero-specific achievements (22 heroes x 5 tiers = 110 achievements!)
    from heroes import HERO_ROSTER

    _add_ladder(
        "heroes_won_distinct", "heroes", "len:heroes_won",
        [1, 2, 5, 8, 11, 15, 18, 22],
        "Пантеон Победителей ({n}/22)", "Hero Pantheon ({n}/22)",
        "Победите за {n} разных героев", "Win a run with {n} distinct heroes",
    )

    for h in HERO_ROSTER:
        hid = h["id"]
        hru = h["name"]
        hen = h.get("name_en", h["name"])
        for rc_idx, r_tgt in enumerate((1, 5, 15)):
            _add(
                f"hero_run_{hid}_{r_tgt}",
                ("common", "rare", "epic")[rc_idx],
                "heroes",
                f"{hru}: Походы ({r_tgt})",
                f"{hen}: Runs ({r_tgt})",
                f"Совершите {r_tgt} походов за героя {hru}",
                f"Start {r_tgt} runs as {hen}",
                f"dictval:runs_by_hero:{hid}",
                r_tgt,
            )
        for wc_idx, w_tgt in enumerate((1, 3)):
            _add(
                f"hero_win_{hid}_{w_tgt}",
                ("rare", "mythic")[wc_idx],
                "heroes",
                f"{hru}: Триумф ({w_tgt})",
                f"{hen}: Triumph ({w_tgt})",
                f"Победите {w_tgt} раз за героя {hru}",
                f"Win {w_tgt} runs as {hen}",
                f"dictval:wins_by_hero:{hid}",
                w_tgt,
            )

    return defs


ACHIEVEMENT_DEFS = _build_achievement_defs()
ACHIEVEMENT_MAP = {a["id"]: a for a in ACHIEVEMENT_DEFS}

TIER_LUM = {
    "common": 176,
    "rare": 212,
    "epic": 236,
    "mythic": 252,
}


class AchievementManager:
    def __init__(self, account_manager):
        self.acc_mgr = account_manager
        self.toast_queue = []
        self.toast_timer = 0.0
        self.active_toast = None

    def _stat_progress(self, stats, spec):
        if spec == "manual":
            return 0
        if spec.startswith("len:"):
            key = spec[4:]
            return len(stats.get(key, []))
        if spec.startswith("dictlen:"):
            key = spec[8:]
            d = stats.get(key)
            if isinstance(d, dict):
                return sum(1 for v in d.values() if v)
            return 0
        if spec.startswith("dictval:"):
            _, key, subkey = spec.split(":", 2)
            d = stats.get(key)
            if isinstance(d, dict):
                return int(d.get(subkey, 0) or 0)
            return 0
        if spec.startswith("contains:"):
            _, key, val = spec.split(":", 2)
            return 1 if val in (stats.get(key) or []) else 0
        if spec.startswith("any_contains:"):
            _, key, vals = spec.split(":", 2)
            cur = set(stats.get(key) or [])
            return 1 if any(v in cur for v in vals.split(",")) else 0
        v = stats.get(spec, 0)
        if isinstance(v, bool):
            return 1 if v else 0
        return int(v or 0)

    def evaluate(self, sound=None):
        acc = self.acc_mgr.get_active()
        unlocked = acc.setdefault("achievements", {})
        stats = acc.get("stats", {})
        newly = []
        for ach in ACHIEVEMENT_DEFS:
            aid = ach["id"]
            if aid in unlocked:
                continue
            if ach["stat"] == "manual":
                continue
            cur = self._stat_progress(stats, ach["stat"])
            if cur >= ach["target"]:
                unlocked[aid] = int(time.time())
                newly.append(ach)
        if newly:
            self.acc_mgr.save()
            for ach in newly:
                self.toast_queue.append(ach)
            if sound is not None and hasattr(sound, "play"):
                try:
                    sound.play("item_pickup")
                except Exception:
                    pass
        return newly

    def unlock(self, ach_id, sound=None):
        ach = ACHIEVEMENT_MAP.get(ach_id)
        if not ach:
            return False
        acc = self.acc_mgr.get_active()
        unlocked = acc.setdefault("achievements", {})
        if ach_id in unlocked:
            return False
        unlocked[ach_id] = int(time.time())
        self.acc_mgr.save()
        self.toast_queue.append(ach)
        if sound is not None and hasattr(sound, "play"):
            try:
                sound.play("item_pickup")
            except Exception:
                pass
        return True

    def is_unlocked(self, ach_id):
        acc = self.acc_mgr.get_active()
        return ach_id in acc.get("achievements", {})

    def get_progress(self, ach):
        acc = self.acc_mgr.get_active()
        aid = ach["id"]
        if aid in acc.get("achievements", {}):
            return ach["target"], ach["target"]
        cur = self._stat_progress(acc.get("stats", {}), ach["stat"])
        return min(cur, ach["target"]), ach["target"]

    def get_filtered(self, cat="all", only_unlocked=False):
        acc = self.acc_mgr.get_active()
        unlocked = acc.get("achievements", {})
        res = []
        for ach in ACHIEVEMENT_DEFS:
            if cat and cat != "all" and ach.get("cat") != cat:
                continue
            if only_unlocked and ach["id"] not in unlocked:
                continue
            res.append(ach)
        return res

    def summary(self):
        acc = self.acc_mgr.get_active()
        cnt = len(acc.get("achievements", {}))
        return cnt, len(ACHIEVEMENT_DEFS)

    def update(self, dt=1.0):
        if self.toast_timer > 0:
            self.toast_timer -= dt
            if self.toast_timer <= 0:
                self.active_toast = None
        if self.active_toast is None and self.toast_queue:
            self.active_toast = self.toast_queue.pop(0)
            self.toast_timer = 195.0

    def draw_toast(self, screen, font_sm, font_md, ui=None):
        if not self.active_toast:
            return
        ach = self.active_toast
        lang = GAME_SETTINGS.get("language", "ru")
        w, h = 360, 68
        sw = screen.get_width()
        x = (sw - w) // 2
        slide = 1.0
        if self.toast_timer > 175.0:
            slide = (195.0 - self.toast_timer) / 20.0
        elif self.toast_timer < 22.0:
            slide = self.toast_timer / 22.0
        default_y = int(14 - (1.0 - clamp(slide, 0.0, 1.0)) * 84)
        banner_bot = ui.get_active_banner_bottom() if ui is not None and hasattr(ui, "get_active_banner_bottom") else 0
        y = max(default_y, banner_bot + 10) if banner_bot > 0 else default_y

        lum = TIER_LUM.get(ach["tier"], 220)
        panel = get_panel_surf(w, h, fill_lum=12, fill_alpha=238, border_lum=lum, radius=10)
        screen.blit(panel, (x, y))

        badge = pygame.Rect(x + 12, y + 14, 40, 40)
        pygame.draw.rect(screen, (28, 28, 28), badge, border_radius=8)
        pygame.draw.rect(screen, (lum, lum, lum), badge, 2, border_radius=8)
        cx, cy = badge.center
        pygame.draw.polygon(
            screen,
            (lum, lum, lum),
            [(cx, cy - 11), (cx + 10, cy - 2), (cx + 6, cy + 10), (cx - 6, cy + 10), (cx - 10, cy - 2)],
            2,
        )
        pygame.draw.circle(screen, (lum, lum, lum), (cx, cy), 3)

        hdr = "ДОСТИЖЕНИЕ ПОЛУЧЕНО" if lang != "en" else "ACHIEVEMENT UNLOCKED"
        title = ach["en"] if lang == "en" else ach["ru"]
        desc = ach["desc_en"] if lang == "en" else ach["desc_ru"]
        max_tw = w - 76
        t_hdr = fit_text_surf(font_sm, f"{hdr} · {ach['tier'].upper()}", (168, 168, 168), max_tw)
        t_name = fit_text_surf(font_md, title, (248, 248, 248), max_tw)
        t_desc = fit_text_surf(font_sm, desc[:52], (198, 198, 198), max_tw)
        screen.blit(t_hdr, (x + 64, y + 8))
        screen.blit(t_name, (x + 64, y + 25))
        screen.blit(t_desc, (x + 64, y + 46))
