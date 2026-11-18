import pygame
from settings import GAME_SETTINGS, PALETTE, SCREEN_HEIGHT, clamp, fit_text_surf, get_panel_surf, get_view_width, is_phone_layout, render_text_cached
from sound import play_sound


QUEST_TIERS = {
    "slayer": [
        {
            "event": "kill",
            "title_ru": "Охота на Теней I",
            "title_en": "Shadow Slayer I",
            "desc_ru": "Победите 12 врагов.",
            "desc_en": "Defeat 12 enemies.",
            "target": 12,
            "reward": "coins",
            "reward_amount": 6,
            "reward_ru": "+6 монет",
            "reward_en": "+6 coins",
        },
        {
            "event": "kill",
            "title_ru": "Охота на Теней II",
            "title_en": "Shadow Slayer II",
            "desc_ru": "Победите 25 врагов.",
            "desc_en": "Defeat 25 enemies.",
            "target": 25,
            "reward": "soul",
            "reward_amount": 2,
            "reward_ru": "+1 сердце души",
            "reward_en": "+1 Soul Heart",
        },
        {
            "event": "kill",
            "title_ru": "Истребитель Бездны III",
            "title_en": "Abyss Exterminator III",
            "desc_ru": "Победите 45 врагов.",
            "desc_en": "Defeat 45 enemies.",
            "target": 45,
            "reward": "dmg",
            "reward_amount": 0.9,
            "reward_ru": "+0.9 урона",
            "reward_en": "+0.9 Damage",
        },
        {
            "event": "kill",
            "title_ru": "Бич Катакомб IV",
            "title_en": "Catacomb Scourge IV",
            "desc_ru": "Победите 85 врагов.",
            "desc_en": "Defeat 85 enemies.",
            "target": 85,
            "reward": "item",
            "reward_amount": 1,
            "reward_ru": "Случайный предмет",
            "reward_en": "Random Item",
        },
    ],
    "acrobat": [
        {
            "event": "jump_slam",
            "title_ru": "Сейсмический Прыжок I",
            "title_en": "Seismic Leap I",
            "desc_ru": "Совершите 5 прыжков с ударом о пол [F].",
            "desc_en": "Perform 5 jump slams [F].",
            "target": 5,
            "reward": "bombs",
            "reward_amount": 3,
            "reward_ru": "+3 бомбы",
            "reward_en": "+3 bombs",
        },
        {
            "event": "jump_slam",
            "title_ru": "Молот Падения II",
            "title_en": "Drop Hammer II",
            "desc_ru": "Совершите 12 прыжков с ударом о пол.",
            "desc_en": "Perform 12 jump slams.",
            "target": 12,
            "reward": "speed",
            "reward_amount": 0.45,
            "reward_ru": "+0.45 скорости",
            "reward_en": "+0.45 Speed",
        },
        {
            "event": "jump_slam",
            "title_ru": "Удар Метеора III",
            "title_en": "Meteor Slam III",
            "desc_ru": "Совершите 24 прыжка с ударом о пол.",
            "desc_en": "Perform 24 jump slams.",
            "target": 24,
            "reward": "dmg",
            "reward_amount": 0.8,
            "reward_ru": "+0.8 урона",
            "reward_en": "+0.8 Damage",
        },
    ],
    "demolitionist": [
        {
            "event": "explosion_hit",
            "title_ru": "Подрывник I",
            "title_en": "Powder Keg I",
            "desc_ru": "Поразите 4 врага или объекта взрывом.",
            "desc_en": "Hit 4 enemies or props with blasts.",
            "target": 4,
            "reward": "bombs",
            "reward_amount": 3,
            "reward_ru": "+3 бомбы",
            "reward_en": "+3 bombs",
        },
        {
            "event": "obstacle_destroyed",
            "title_ru": "Крушитель Камней II",
            "title_en": "Stonebreaker II",
            "desc_ru": "Разрушьте 8 преград взрывами или ударом.",
            "desc_en": "Destroy 8 obstacles by blasts or slams.",
            "target": 8,
            "reward": "coins",
            "reward_amount": 8,
            "reward_ru": "+8 монет",
            "reward_en": "+8 coins",
        },
        {
            "event": "explosion_hit",
            "title_ru": "Пиромант III",
            "title_en": "Pyromancer III",
            "desc_ru": "Поразите 12 врагов или объектов взрывами.",
            "desc_en": "Hit 12 targets with explosions.",
            "target": 12,
            "reward": "bombs",
            "reward_amount": 5,
            "reward_ru": "+5 бомб",
            "reward_en": "+5 bombs",
        },
    ],
    "explorer": [
        {
            "event": "room_visit",
            "title_ru": "Картограф Бездны I",
            "title_en": "Abyss Cartographer I",
            "desc_ru": "Исследуйте 8 новых комнат.",
            "desc_en": "Explore 8 new rooms.",
            "target": 8,
            "reward": "keys",
            "reward_amount": 2,
            "reward_ru": "+2 ключа",
            "reward_en": "+2 keys",
        },
        {
            "event": "room_visit",
            "title_ru": "Странник Глубин II",
            "title_en": "Deep Wanderer II",
            "desc_ru": "Исследуйте 16 новых комнат.",
            "desc_en": "Explore 16 new rooms.",
            "target": 16,
            "reward": "soul",
            "reward_amount": 2,
            "reward_ru": "+1 сердце души",
            "reward_en": "+1 Soul Heart",
        },
        {
            "event": "room_visit",
            "title_ru": "Первопроходец III",
            "title_en": "Pathfinder III",
            "desc_ru": "Исследуйте 28 новых комнат.",
            "desc_en": "Explore 28 new rooms.",
            "target": 28,
            "reward": "keys",
            "reward_amount": 4,
            "reward_ru": "+4 ключа",
            "reward_en": "+4 keys",
        },
    ],
    "untouchable": [
        {
            "event": "room_flawless",
            "title_ru": "Безупречный Бой I",
            "title_en": "Flawless Combat I",
            "desc_ru": "Зачистите 3 боевые комнаты без урона.",
            "desc_en": "Clear 3 combat rooms without taking damage.",
            "target": 3,
            "reward": "charge",
            "reward_amount": 2,
            "reward_ru": "Заряд реликвии",
            "reward_en": "Relic charge",
        },
        {
            "event": "room_flawless",
            "title_ru": "Призрачный Клинок II",
            "title_en": "Phantom Edge II",
            "desc_ru": "Зачистите 6 боевых комнат без урона.",
            "desc_en": "Clear 6 combat rooms without taking damage.",
            "target": 6,
            "reward": "item",
            "reward_amount": 1,
            "reward_ru": "Случайный предмет",
            "reward_en": "Random Item",
        },
        {
            "event": "room_flawless",
            "title_ru": "Неуловимый III",
            "title_en": "Elusive Master III",
            "desc_ru": "Зачистите 12 боевых комнат без урона.",
            "desc_en": "Clear 12 combat rooms flawlessly.",
            "target": 12,
            "reward": "soul",
            "reward_amount": 4,
            "reward_ru": "+2 сердца души",
            "reward_en": "+2 Soul Hearts",
        },
    ],
    "boss_hunter": [
        {
            "event": "boss_kill",
            "title_ru": "Охотник на Владык I",
            "title_en": "Lord Slayer I",
            "desc_ru": "Победите босса этажа.",
            "desc_en": "Defeat a floor boss.",
            "target": 1,
            "reward": "item",
            "reward_amount": 1,
            "reward_ru": "Реликвия босса",
            "reward_en": "Boss Relic",
        },
        {
            "event": "boss_kill",
            "title_ru": "Каратель Бездны II",
            "title_en": "Abyss Scourge II",
            "desc_ru": "Победите ещё 2 боссов этажей.",
            "desc_en": "Defeat 2 more floor bosses.",
            "target": 2,
            "reward": "dmg",
            "reward_amount": 1.25,
            "reward_ru": "+1.25 урона",
            "reward_en": "+1.25 Damage",
        },
        {
            "event": "boss_kill",
            "title_ru": "Палач Стражей III",
            "title_en": "Warden Executioner III",
            "desc_ru": "Победите ещё 3 боссов этажей.",
            "desc_en": "Defeat 3 more floor bosses.",
            "target": 3,
            "reward": "item",
            "reward_amount": 1,
            "reward_ru": "Реликвия + заряд",
            "reward_en": "Relic Item",
        },
    ],
    "dasher": [
        {
            "event": "dash",
            "title_ru": "Теневой Рывок I",
            "title_en": "Shadow Dash I",
            "desc_ru": "Совершите 10 рывков [Shift].",
            "desc_en": "Perform 10 dashes [Shift].",
            "target": 10,
            "reward": "speed",
            "reward_amount": 0.25,
            "reward_ru": "+0.25 скорости",
            "reward_en": "+0.25 Speed",
        },
        {
            "event": "dash",
            "title_ru": "Вихрь Уклонения II",
            "title_en": "Evasion Gale II",
            "desc_ru": "Совершите 25 рывков.",
            "desc_en": "Perform 25 dashes.",
            "target": 25,
            "reward": "coins",
            "reward_amount": 7,
            "reward_ru": "+7 монет",
            "reward_en": "+7 coins",
        },
    ],
    "phantom": [
        {
            "event": "stealth_use",
            "title_ru": "Покров Тьмы I",
            "title_en": "Shroud of Night I",
            "desc_ru": "Уйдите в невидимость [V] 4 раза.",
            "desc_en": "Activate stealth [V] 4 times.",
            "target": 4,
            "reward": "dmg",
            "reward_amount": 0.6,
            "reward_ru": "+0.6 урона",
            "reward_en": "+0.6 Damage",
        },
        {
            "event": "stealth_use",
            "title_ru": "Ассасин Склепа II",
            "title_en": "Crypt Assassin II",
            "desc_ru": "Используйте невидимость 10 раз.",
            "desc_en": "Use stealth 10 times.",
            "target": 10,
            "reward": "soul",
            "reward_amount": 2,
            "reward_ru": "+1 сердце души",
            "reward_en": "+1 Soul Heart",
        },
    ],
    "shopper": [
        {
            "event": "shop_buy",
            "title_ru": "Завсегдатай Лавки I",
            "title_en": "Shop Regular I",
            "desc_ru": "Купите 3 товара в лавках.",
            "desc_en": "Buy 3 goods in shops.",
            "target": 3,
            "reward": "coins",
            "reward_amount": 6,
            "reward_ru": "+6 монет",
            "reward_en": "+6 coins",
        },
        {
            "event": "shop_buy",
            "title_ru": "Золотой Клиент II",
            "title_en": "VIP Patron II",
            "desc_ru": "Купите 7 товаров в лавках.",
            "desc_en": "Buy 7 goods in shops.",
            "target": 7,
            "reward": "keys",
            "reward_amount": 3,
            "reward_ru": "+3 ключа",
            "reward_en": "+3 keys",
        },
    ],
    "tinkerer": [
        {
            "event": "machine_use",
            "title_ru": "Игрок Аркады I",
            "title_en": "Arcade Gambler I",
            "desc_ru": "Активируйте автоматы 4 раза.",
            "desc_en": "Use dungeon machines 4 times.",
            "target": 4,
            "reward": "coins",
            "reward_amount": 5,
            "reward_ru": "+5 монет",
            "reward_en": "+5 coins",
        },
        {
            "event": "machine_use",
            "title_ru": "Мастер Механизмов II",
            "title_en": "Gearwright II",
            "desc_ru": "Активируйте автоматы 10 раз.",
            "desc_en": "Use dungeon machines 10 times.",
            "target": 10,
            "reward": "charge",
            "reward_amount": 3,
            "reward_ru": "Полный заряд",
            "reward_en": "Full Charge",
        },
    ],
    "relic_seeker": [
        {
            "event": "item_collect",
            "title_ru": "Искатель Реликвий I",
            "title_en": "Relic Seeker I",
            "desc_ru": "Подберите 4 артефакта.",
            "desc_en": "Collect 4 relics.",
            "target": 4,
            "reward": "dmg",
            "reward_amount": 0.7,
            "reward_ru": "+0.7 урона",
            "reward_en": "+0.7 Damage",
        },
        {
            "event": "item_collect",
            "title_ru": "Архивариус II",
            "title_en": "Vault Archivist II",
            "desc_ru": "Подберите 8 артефактов.",
            "desc_en": "Collect 8 relics.",
            "target": 8,
            "reward": "soul",
            "reward_amount": 2,
            "reward_ru": "+1 сердце души",
            "reward_en": "+1 Soul Heart",
        },
    ],
    "collector_coins": [
        {
            "event": "coin_gain",
            "title_ru": "Сборщик Серебра I",
            "title_en": "Silver Hoarder I",
            "desc_ru": "Подберите 20 монет.",
            "desc_en": "Pick up 20 coins.",
            "target": 20,
            "reward": "bombs",
            "reward_amount": 2,
            "reward_ru": "+2 бомбы",
            "reward_en": "+2 bombs",
        },
        {
            "event": "coin_gain",
            "title_ru": "Казначей Бездны II",
            "title_en": "Vault Treasurer II",
            "desc_ru": "Подберите 50 монет.",
            "desc_en": "Pick up 50 coins.",
            "target": 50,
            "reward": "item",
            "reward_amount": 1,
            "reward_ru": "Случайный предмет",
            "reward_en": "Random Item",
        },
    ],
}

QUEST_ORDER = [
    "slayer",
    "acrobat",
    "demolitionist",
    "explorer",
    "untouchable",
    "boss_hunter",
    "dasher",
    "phantom",
    "shopper",
    "tinkerer",
    "relic_seeker",
    "collector_coins",
]


def _build_track(qid, tier=0):
    tiers = QUEST_TIERS[qid]
    t = min(max(0, int(tier)), len(tiers) - 1)
    spec = tiers[t]
    return {
        "id": qid,
        "tier": t,
        "max_tier": len(tiers) - 1,
        "event": spec["event"],
        "title_ru": spec["title_ru"],
        "title_en": spec["title_en"],
        "desc_ru": spec["desc_ru"],
        "desc_en": spec["desc_en"],
        "target": int(spec["target"]),
        "progress": 0,
        "completed": False,
        "reward": spec["reward"],
        "reward_amount": spec["reward_amount"],
        "reward_ru": spec["reward_ru"],
        "reward_en": spec["reward_en"],
    }


class QuestManager:
    def __init__(self):
        self.quests = [_build_track(qid, 0) for qid in QUEST_ORDER]
        self.log_open = False
        self.completed_total = 0

    def reset(self):
        self.quests = [_build_track(qid, 0) for qid in QUEST_ORDER]
        self.log_open = False
        self.completed_total = 0

    def trigger(self, game, event_type, amount=1):
        amt = max(1, int(amount))
        lang = GAME_SETTINGS.get("language", "ru")
        for idx, q in enumerate(self.quests):
            if q["completed"] or q["event"] != event_type:
                continue
            q["progress"] = min(q["target"], q["progress"] + amt)
            if q["progress"] >= q["target"]:
                self._grant_reward(game, q)
                self.completed_total += 1
                if game is not None and getattr(game, "account_manager", None) is not None:
                    game.account_manager.record_stat("quests_completed", 1)
                    if getattr(game, "achievement_manager", None) is not None:
                        game.achievement_manager.evaluate()
                title_t = q["title_ru"] if lang == "ru" else q["title_en"]
                rew_t = q["reward_ru"] if lang == "ru" else q["reward_en"]
                msg = f"ЗАДАНИЕ: {title_t}" if lang == "ru" else f"BOUNTY: {title_t}"
                sub = f"Награда: {rew_t}" if lang == "ru" else f"Reward: {rew_t}"
                if game and getattr(game, "ui", None):
                    game.ui.show_banner(msg, sub, 125.0)
                play_sound("pickup")
                if q["tier"] < q["max_tier"]:
                    self.quests[idx] = _build_track(q["id"], q["tier"] + 1)
                else:
                    q["completed"] = True

    def _grant_reward(self, game, q):
        if not game or not getattr(game, "player", None):
            return
        p = game.player
        r = q["reward"]
        amt = q["reward_amount"]
        if r == "coins":
            p.coins += int(amt)
        elif r == "bombs":
            p.bombs += int(amt)
        elif r == "keys":
            p.keys += int(amt)
        elif r == "soul":
            p.soul_hp += int(amt)
        elif r == "dmg":
            p.damage += float(amt)
        elif r == "speed":
            p.speed = min(9.5, p.speed + float(amt))
        elif r == "charge":
            p.add_charge(int(amt))
        elif r == "item":
            from items import get_random_item

            it = get_random_item(exclude_ids=p.collected_ids, item_type="passive")
            if it:
                p.apply_item(it, silent=True)

    def serialize(self):
        return {
            "completed_total": int(self.completed_total),
            "tracks": [
                {
                    "id": q["id"],
                    "tier": int(q["tier"]),
                    "progress": int(q["progress"]),
                    "completed": bool(q["completed"]),
                }
                for q in self.quests
            ],
        }

    def deserialize(self, data):
        self.reset()
        if isinstance(data, list):
            for d in data:
                if not isinstance(d, dict):
                    continue
                qid = d.get("id")
                for idx, q in enumerate(self.quests):
                    if q["id"] == qid:
                        q["progress"] = int(clamp(int(d.get("progress", 0)), 0, q["target"]))
                        q["completed"] = bool(d.get("completed", False))
            return
        if not isinstance(data, dict):
            return
        self.completed_total = int(data.get("completed_total", 0))
        for d in data.get("tracks", []):
            if not isinstance(d, dict):
                continue
            qid = d.get("id")
            if qid not in QUEST_TIERS:
                continue
            tier = int(d.get("tier", 0))
            tr = _build_track(qid, tier)
            tr["progress"] = int(clamp(int(d.get("progress", 0)), 0, tr["target"]))
            tr["completed"] = bool(d.get("completed", False))
            for idx, existing in enumerate(self.quests):
                if existing["id"] == qid:
                    self.quests[idx] = tr
                    break

    def get_hud_rect(self, phone_layout=None):
        vw = get_view_width()
        phone = is_phone_layout(None) if phone_layout is None else bool(phone_layout)
        return pygame.Rect(vw - 196, 188 if phone else 184, 182, 62 if phone else 58)

    def get_modal_rect(self):
        vw = get_view_width()
        panel_w, panel_h = 840, 544
        return pygame.Rect((vw - panel_w) // 2, (SCREEN_HEIGHT - panel_h) // 2, panel_w, panel_h)

    def _primary_quest(self):
        active = [q for q in self.quests if not q["completed"]]
        if not active:
            return None
        return max(active, key=lambda q: (q["progress"] / max(1, q["target"]), q["tier"]))

    def draw_hud_widget(self, screen, ui, lang="ru"):
        rect = self.get_hud_rect()
        panel = get_panel_surf(rect.w, rect.h, fill_lum=12, fill_alpha=210, border_lum=74, radius=8)
        screen.blit(panel, rect.topleft)

        hdr = f"[TAB] КВЕСТЫ ({self.completed_total})" if lang == "ru" else f"[TAB] QUESTS ({self.completed_total})"
        hdr_s = fit_text_surf(ui.font_tiny, hdr, PALETTE["text_dim"], rect.w - 20, max_h=15, min_scale=0.58)
        screen.blit(hdr_s, (rect.x + 10, rect.y + 6))

        q = self._primary_quest()
        if q is None:
            done_txt = "Все контракты закрыты" if lang == "ru" else "All bounties cleared"
            ds = fit_text_surf(ui.font_tiny, done_txt, (230, 230, 230), rect.w - 20, max_h=15, min_scale=0.58)
            screen.blit(ds, (rect.x + 10, rect.y + 26))
            return

        title = q["title_ru"] if lang == "ru" else q["title_en"]
        prog_txt = f"{q['progress']}/{q['target']}"
        cnt = fit_text_surf(ui.font_tiny, prog_txt, (236, 236, 236), 54, max_h=15, min_scale=0.58)
        lbl = fit_text_surf(ui.font_tiny, title, PALETTE["text_main"], max(40, rect.w - 28 - cnt.get_width()), max_h=15, min_scale=0.55)
        screen.blit(lbl, (rect.x + 10, rect.y + 25))
        screen.blit(cnt, (rect.right - 10 - cnt.get_width(), rect.y + 25))

        bar_x, bar_y, bar_w, bar_h = rect.x + 10, rect.bottom - 10, rect.w - 20, 5
        pygame.draw.rect(screen, (28, 28, 28), (bar_x, bar_y, bar_w, bar_h), border_radius=2)
        ratio = clamp(float(q["progress"]) / float(max(1, q["target"])), 0.0, 1.0)
        fill_w = max(0, int(bar_w * ratio))
        if fill_w > 0:
            pygame.draw.rect(screen, (232, 232, 232), (bar_x, bar_y, fill_w, bar_h), border_radius=2)

    def draw_log_modal(self, screen, ui, lang="ru"):
        rect = self.get_modal_rect()
        px, py, panel_w, panel_h = rect.x, rect.y, rect.w, rect.h
        panel = get_panel_surf(panel_w, panel_h, fill_lum=12, fill_alpha=238, border_lum=108, radius=12)
        screen.blit(panel, (px, py))

        title_s = fit_text_surf(
            ui.font_big,
            f"КОНТРАКТЫ ({self.completed_total})" if lang == "ru" else f"BOUNTY LOG ({self.completed_total})",
            PALETTE["text_main"],
            panel_w - 48,
            max_h=30,
        )
        screen.blit(title_s, (px + (panel_w - title_s.get_width()) // 2, py + 12))

        hint_txt = "[TAB] / [ESC] Закрыть журнал" if lang == "ru" else "[TAB] / [ESC] Close Quest Log"
        hint = fit_text_surf(ui.font_tiny, hint_txt, PALETTE["text_dim"], panel_w - 48, max_h=16)
        screen.blit(hint, (px + (panel_w - hint.get_width()) // 2, py + panel_h - 24))

        col_w = (panel_w - 58) // 2
        row_h = 72
        for idx, q in enumerate(self.quests[:12]):
            col = idx % 2
            row = idx // 2
            cx = px + 22 + col * (col_w + 14)
            cy = py + 54 + row * row_h
            card = pygame.Rect(cx, cy, col_w, 64)
            pygame.draw.rect(screen, (22, 22, 22) if q["completed"] else (17, 17, 17), card, border_radius=7)
            pygame.draw.rect(screen, (140, 140, 140) if q["completed"] else (58, 58, 58), card, 1, border_radius=7)

            title = q["title_ru"] if lang == "ru" else q["title_en"]
            desc = q["desc_ru"] if lang == "ru" else q["desc_en"]
            rew = q["reward_ru"] if lang == "ru" else q["reward_en"]
            status = ("OK" if lang == "ru" else "DONE") if q["completed"] else f"{q['progress']}/{q['target']}"

            st_s = fit_text_surf(ui.font_tiny, f"[{status}] · {rew}", (226, 226, 226) if q["completed"] else (188, 188, 188), col_w // 2 - 14, max_h=15, min_scale=0.55)
            ts = fit_text_surf(ui.font_small, title, (244, 244, 244) if q["completed"] else PALETTE["text_main"], max(80, col_w - 28 - st_s.get_width()), max_h=17, min_scale=0.55)
            screen.blit(ts, (cx + 10, cy + 7))
            screen.blit(st_s, (cx + col_w - 10 - st_s.get_width(), cy + 8))

            ds = fit_text_surf(ui.font_tiny, desc, PALETTE["text_muted"], col_w - 20, max_h=15, min_scale=0.55)
            screen.blit(ds, (cx + 10, cy + 29))

            bar_w, bar_h = col_w - 20, 5
            bx, by = cx + 10, cy + 51
            pygame.draw.rect(screen, (28, 28, 28), (bx, by, bar_w, bar_h), border_radius=3)
            ratio = clamp(float(q["progress"]) / float(max(1, q["target"])), 0.0, 1.0)
            fill_c = (246, 246, 246) if q["completed"] else (188, 188, 188)
            pygame.draw.rect(screen, fill_c, (bx, by, int(bar_w * ratio), bar_h), border_radius=3)
