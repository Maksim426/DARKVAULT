import hashlib
import json
import os
import time
import uuid

from settings import (
    GAME_SETTINGS,
    atomic_write_json,
    get_user_data_dir,
    load_user_settings,
    safe_read_json,
)


BACKUP_EXTENSION = ".dvbackup"
BACKUP_FORMAT = "darkvault_full_backup_v1"

EMBLEM_NAMES_RU = [
    "Око Бездны",
    "Тень Кинжала",
    "Серп Луны",
    "Корона Пепла",
    "Череп Мастера",
    "Крыло Фантома",
    "Ключ Склепа",
    "Руна Затмения",
]

EMBLEM_NAMES_EN = [
    "Abyss Eye",
    "Dagger Shade",
    "Moon Sickle",
    "Ash Crown",
    "Master Skull",
    "Phantom Wing",
    "Vault Key",
    "Eclipse Rune",
]


def _safe_read_json(path, default=None):
    return safe_read_json(path, default=default, try_backups=True, self_heal=True)


def _safe_write_json(path, data):
    ok, err = atomic_write_json(path, data, indent=2, ensure_ascii=False, backup=True, verify=True)
    if not ok:
        raise OSError(err or "atomic_write_json failed")
    return True


def _compute_payload_sha256(payload_obj):
    canonical = json.dumps(payload_obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


DAILY_REWARD_TABLE = [
    {"day": 1, "coins": 5, "bombs": 0, "keys": 0, "soul_hp": 0, "damage": 0.0, "speed": 0.0, "ru": "+5 монет на спуск", "en": "+5 Starting Coins"},
    {"day": 2, "coins": 0, "bombs": 2, "keys": 2, "soul_hp": 0, "damage": 0.0, "speed": 0.0, "ru": "+2 бомбы и +2 ключа", "en": "+2 Bombs & +2 Keys"},
    {"day": 3, "coins": 2, "bombs": 0, "keys": 0, "soul_hp": 2, "damage": 0.0, "speed": 0.0, "ru": "+1 Сердце души и +2 монеты", "en": "+1 Soul Heart & +2 Coins"},
    {"day": 4, "coins": 8, "bombs": 1, "keys": 1, "soul_hp": 0, "damage": 0.0, "speed": 0.0, "ru": "+8 монет, бомба и ключ", "en": "+8 Coins, 1 Bomb & 1 Key"},
    {"day": 5, "coins": 3, "bombs": 0, "keys": 0, "soul_hp": 0, "damage": 0.5, "speed": 0.25, "ru": "+0.5 Урона, +0.25 Скор. и +3 монеты", "en": "+0.5 DMG, +0.25 SPD & +3 Coins"},
    {"day": 6, "coins": 4, "bombs": 2, "keys": 0, "soul_hp": 4, "damage": 0.0, "speed": 0.0, "ru": "+2 Сердца души, +2 бомбы, +4 м.", "en": "+2 Soul Hearts, +2 Bombs, +4c"},
    {"day": 7, "coins": 10, "bombs": 2, "keys": 2, "soul_hp": 2, "damage": 0.8, "speed": 0.25, "ru": "+10 м., +1 Душа, +0.8 Урона!", "en": "+10c, +1 Soul Heart, +0.8 DMG!"},
]


def _default_stats():
    return {
        "runs": 0,
        "wins": 0,
        "coop_wins": 0,
        "kills": 0,
        "bosses_killed": 0,
        "best_floor": 1,
        "best_wave": 0,
        "coins_collected": 0,
        "secrets_found": 0,
        "ambush_kills": 0,
        "slam_kills": 0,
        "explosion_kills": 0,
        "shop_purchases": 0,
        "machine_uses": 0,
        "beggar_uses": 0,
        "items_collected": 0,
        "playtime_sec": 0,
        "modes_played": [],
        "heroes_won": [],
        "boss_types_killed": [],
        "tutorial_done": False,
        "flawless_floors": 0,
        "quests_completed": 0,
        "dashes_used": 0,
        "stealth_uses": 0,
        "bombs_used": 0,
        "active_uses": 0,
        "melee_hits": 0,
        "melee_kills": 0,
        "turrets_destroyed": 0,
        "obstacles_destroyed": 0,
        "doors_opened": 0,
        "rooms_visited": 0,
        "dice_uses": 0,
        "sacrifice_uses": 0,
        "no_damage_rooms": 0,
        "seeded_runs": 0,
        "daily_claims": 0,
        "daily_streak": 0,
        "max_daily_streak": 0,
        "last_daily_date": "",
        "runs_by_hero": {},
        "wins_by_hero": {},
        "computer_uses": 0,
        "computer_tracks_heard": [],
        "projectiles_deflected": 0,
        "melee_finishers": 0,
        "boss_flawless": 0,
        "low_hp_clutches": 0,
        "monoliths_activated": 0,
        "devil_deals": 0,
        "tinted_rocks_bombed": 0,
        "machines_bombed": 0,
        "special_rooms_visited": [],
        "libraries_visited": 0,
        "curse_rooms_visited": 0,
        "chaos_drafts": 0,
        "boss_rush_wins": 0,
        "fading_light_wins": 0,
        "lan_runs": 0,
        "modded_runs": 0,
        "codex_opened": 0,
        "peak_dmg_x10": 0,
        "peak_speed_x10": 0,
        "max_run_items": 0,
        "max_run_coins": 0,
    }


def _make_account(name="Скиталец", tag="DV-01", emblem=0):
    clean_name = (str(name).strip() or "Скиталец")[:20]
    clean_tag = (str(tag).strip() or "DV-01").upper()[:10]
    now = int(time.time())
    return {
        "id": uuid.uuid4().hex[:12],
        "name": clean_name,
        "tag": clean_tag,
        "emblem": int(emblem) % 8,
        "created_at": now,
        "updated_at": now,
        "stats": _default_stats(),
        "achievements": {},
        "recent_runs": [],
        "pending_daily_bonus": None,
    }


class AccountManager:
    def __init__(self, data_dir=None):
        self.data_dir = data_dir or get_user_data_dir()
        self.path = os.path.join(self.data_dir, "accounts.json")
        self.backup_dir = os.path.join(self.data_dir, "backups")
        self.accounts = []
        self.active_id = None
        self.load()

    def load(self):
        raw = _safe_read_json(self.path, None)
        if isinstance(raw, dict) and isinstance(raw.get("accounts"), list) and raw["accounts"]:
            self.accounts = []
            for acc in raw["accounts"]:
                if not isinstance(acc, dict) or not acc.get("id"):
                    continue
                st = _default_stats()
                if isinstance(acc.get("stats"), dict):
                    for k, v in acc["stats"].items():
                        if k in st:
                            if isinstance(st[k], dict):
                                st[k] = dict(v) if isinstance(v, dict) else {}
                            elif isinstance(st[k], list):
                                st[k] = list(v) if isinstance(v, list) else []
                            else:
                                st[k] = v
                pending = acc.get("pending_daily_bonus")
                self.accounts.append(
                    {
                        "id": str(acc["id"]),
                        "name": str(acc.get("name", "Скиталец"))[:20],
                        "tag": str(acc.get("tag", "DV-01"))[:10],
                        "emblem": int(acc.get("emblem", 0)) % 8,
                        "created_at": int(acc.get("created_at", int(time.time()))),
                        "updated_at": int(acc.get("updated_at", int(time.time()))),
                        "stats": st,
                        "achievements": dict(acc.get("achievements", {})) if isinstance(acc.get("achievements"), dict) else {},
                        "recent_runs": list(acc.get("recent_runs", []))[:12] if isinstance(acc.get("recent_runs"), list) else [],
                        "pending_daily_bonus": dict(pending) if isinstance(pending, dict) else None,
                    }
                )
            self.active_id = raw.get("active_id")
        if not self.accounts:
            default_name = "Wanderer" if GAME_SETTINGS.get("language") == "en" else "Скиталец"
            acc = _make_account(default_name, "DV-01", 0)
            self.accounts = [acc]
            self.active_id = acc["id"]
            self.save()
        if not any(a["id"] == self.active_id for a in self.accounts):
            self.active_id = self.accounts[0]["id"]
            self.save()

    def save(self):
        try:
            _safe_write_json(
                self.path,
                {
                    "version": 1,
                    "active_id": self.active_id,
                    "accounts": self.accounts,
                },
            )
            return True
        except Exception:
            return False

    def get_active(self):
        for acc in self.accounts:
            if acc["id"] == self.active_id:
                return acc
        return self.accounts[0]

    def set_active(self, acc_id):
        for acc in self.accounts:
            if acc["id"] == acc_id:
                self.active_id = acc_id
                self.save()
                return True
        return False

    def create_account(self, name, tag="", emblem=0):
        idx = len(self.accounts) + 1
        auto_tag = tag.strip() if tag and tag.strip() else f"DV-{idx:02d}"
        acc = _make_account(name, auto_tag, emblem)
        self.accounts.append(acc)
        self.active_id = acc["id"]
        self.save()
        return acc

    def rename_account(self, acc_id, new_name, new_tag=None, emblem=None):
        for acc in self.accounts:
            if acc["id"] == acc_id:
                clean = str(new_name).strip()
                if clean:
                    acc["name"] = clean[:20]
                if new_tag is not None and str(new_tag).strip():
                    acc["tag"] = str(new_tag).strip().upper()[:10]
                if emblem is not None:
                    acc["emblem"] = int(emblem) % 8
                acc["updated_at"] = int(time.time())
                self.save()
                return True
        return False

    def delete_account(self, acc_id):
        if len(self.accounts) <= 1:
            return False
        kept = [a for a in self.accounts if a["id"] != acc_id]
        if len(kept) == len(self.accounts):
            return False
        self.accounts = kept
        if self.active_id == acc_id:
            self.active_id = self.accounts[0]["id"]
        self.save()
        return True

    def record_stat(self, key, delta=1, mode="add"):
        acc = self.get_active()
        st = acc["stats"]
        if mode == "max":
            st[key] = max(int(st.get(key, 0)), int(delta))
        elif mode == "set":
            st[key] = delta
        elif mode == "append_unique":
            lst = st.setdefault(key, [])
            if delta not in lst:
                lst.append(delta)
        else:
            st[key] = int(st.get(key, 0)) + int(delta)
        acc["updated_at"] = int(time.time())
        self.save()

    def record_run(self, summary):
        acc = self.get_active()
        entry = {
            "ts": int(time.time()),
            "hero": str(summary.get("hero", "")),
            "mode": str(summary.get("mode", "classic")),
            "floor": int(summary.get("floor", 1)),
            "wave": int(summary.get("wave", 0)),
            "kills": int(summary.get("kills", 0)),
            "won": bool(summary.get("won", False)),
            "coop": bool(summary.get("coop", False)),
            "seed": str(summary.get("seed", "")),
        }
        runs = acc.setdefault("recent_runs", [])
        runs.insert(0, entry)
        acc["recent_runs"] = runs[:12]
        st = acc["stats"]
        st["runs"] = int(st.get("runs", 0)) + 1
        st["best_floor"] = max(int(st.get("best_floor", 1)), entry["floor"])
        if entry["wave"] > 0:
            st["best_wave"] = max(int(st.get("best_wave", 0)), entry["wave"])
        modes = st.setdefault("modes_played", [])
        if entry["mode"] and entry["mode"] not in modes:
            modes.append(entry["mode"])
        if entry["hero"]:
            rbh = st.setdefault("runs_by_hero", {})
            if not isinstance(rbh, dict):
                rbh = {}
                st["runs_by_hero"] = rbh
            rbh[entry["hero"]] = int(rbh.get(entry["hero"], 0)) + 1
        if entry["seed"]:
            st["seeded_runs"] = int(st.get("seeded_runs", 0)) + 1
        if entry["won"]:
            st["wins"] = int(st.get("wins", 0)) + 1
            if entry["coop"]:
                st["coop_wins"] = int(st.get("coop_wins", 0)) + 1
            hw = st.setdefault("heroes_won", [])
            if entry["hero"] and entry["hero"] not in hw:
                hw.append(entry["hero"])
            if entry["hero"]:
                wbh = st.setdefault("wins_by_hero", {})
                if not isinstance(wbh, dict):
                    wbh = {}
                    st["wins_by_hero"] = wbh
                wbh[entry["hero"]] = int(wbh.get(entry["hero"], 0)) + 1
        acc["updated_at"] = int(time.time())
        self.save()

    @staticmethod
    def _today_str(today_str=None):
        if today_str:
            return str(today_str)
        return time.strftime("%Y-%m-%d")

    @staticmethod
    def _is_yesterday(prev_date, today_str):
        if not prev_date:
            return False
        try:
            import datetime as _dt

            d1 = _dt.date.fromisoformat(str(prev_date))
            d2 = _dt.date.fromisoformat(str(today_str))
            return (d2 - d1).days == 1
        except Exception:
            return False

    def get_daily_reward_info(self, today_str=None):
        acc = self.get_active()
        st = acc.get("stats", {})
        today = self._today_str(today_str)
        last_d = str(st.get("last_daily_date", "") or "")
        cur_streak = int(st.get("daily_streak", 0))
        can_claim = last_d != today
        if can_claim:
            next_streak = (cur_streak + 1) if self._is_yesterday(last_d, today) else 1
        else:
            next_streak = max(1, cur_streak)
        day_idx = (max(1, next_streak) - 1) % len(DAILY_REWARD_TABLE)
        rew = dict(DAILY_REWARD_TABLE[day_idx])
        return {
            "can_claim": can_claim,
            "today": today,
            "last_date": last_d,
            "streak": cur_streak,
            "next_streak": next_streak,
            "day_num": day_idx + 1,
            "reward": rew,
            "pending_bonus": acc.get("pending_daily_bonus"),
        }

    def can_claim_daily_reward(self, today_str=None):
        return bool(self.get_daily_reward_info(today_str=today_str)["can_claim"])

    def claim_daily_reward(self, today_str=None):
        info = self.get_daily_reward_info(today_str=today_str)
        if not info["can_claim"]:
            return {"ok": False, "reason": "already_claimed", "info": info}
        acc = self.get_active()
        st = acc["stats"]
        new_streak = info["next_streak"]
        st["last_daily_date"] = info["today"]
        st["daily_streak"] = new_streak
        st["max_daily_streak"] = max(int(st.get("max_daily_streak", 0)), new_streak)
        st["daily_claims"] = int(st.get("daily_claims", 0)) + 1

        rew = info["reward"]
        cur_b = dict(acc.get("pending_daily_bonus") or {})
        for k in ("coins", "bombs", "keys", "soul_hp"):
            cur_b[k] = int(cur_b.get(k, 0)) + int(rew.get(k, 0))
        for k in ("damage", "speed"):
            cur_b[k] = round(float(cur_b.get(k, 0.0)) + float(rew.get(k, 0.0)), 2)
        cur_b["ru"] = rew["ru"]
        cur_b["en"] = rew["en"]
        cur_b["day"] = info["day_num"]
        cur_b["streak"] = new_streak
        acc["pending_daily_bonus"] = cur_b
        acc["updated_at"] = int(time.time())
        self.save()
        return {"ok": True, "streak": new_streak, "day": info["day_num"], "reward": rew, "bonus": cur_b}

    def consume_daily_bonus(self):
        acc = self.get_active()
        bonus = acc.get("pending_daily_bonus")
        if not isinstance(bonus, dict):
            return None
        acc["pending_daily_bonus"] = None
        acc["updated_at"] = int(time.time())
        self.save()
        return bonus

    def get_roster(self):
        def _score(acc):
            ach_cnt = len(acc.get("achievements", {}))
            st = acc.get("stats", {})
            return (ach_cnt, int(st.get("wins", 0)), int(st.get("best_floor", 1)), int(st.get("kills", 0)))

        return sorted(self.accounts, key=_score, reverse=True)

    def _collect_backup_payload(self):
        game_dir = os.path.dirname(os.path.abspath(__file__))
        saves = {}
        for slot in (1, 2, 3):
            sp = os.path.join(self.data_dir, f"save_slot_{slot}.json")
            data = _safe_read_json(sp, None)
            if data is not None:
                saves[str(slot)] = data

        user_settings = _safe_read_json(os.path.join(self.data_dir, "user_settings.json"), dict(GAME_SETTINGS))
        mods_config = _safe_read_json(os.path.join(self.data_dir, "mods_config.json"), None)
        if mods_config is None:
            mods_config = _safe_read_json(os.path.join(game_dir, "mods_config.json"), {})

        mods_files = {}
        for folder in (os.path.join(self.data_dir, "mods"), os.path.join(game_dir, "mods")):
            if os.path.isdir(folder):
                for fn in sorted(os.listdir(folder)):
                    if fn.endswith(".py") and fn not in mods_files:
                        try:
                            with open(os.path.join(folder, fn), "r", encoding="utf-8") as fh:
                                mods_files[fn] = fh.read()
                        except Exception:
                            pass

        shared_seeds = _safe_read_json(os.path.join(self.data_dir, "shared_seeds.json"), None)
        if shared_seeds is None:
            shared_seeds = _safe_read_json(os.path.join(game_dir, "shared_seeds.json"), [])

        quests_state = _safe_read_json(os.path.join(self.data_dir, "quests_state.json"), None)

        return {
            "active_id": self.active_id,
            "accounts": self.accounts,
            "user_settings": user_settings,
            "saves": saves,
            "mods_config": mods_config,
            "mods_files": mods_files,
            "shared_seeds": shared_seeds,
            "quests_state": quests_state,
        }

    def export_full_backup(self, filename=None):
        os.makedirs(self.backup_dir, exist_ok=True)
        acc = self.get_active()
        safe_tag = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in acc.get("tag", "DV"))
        stamp = time.strftime("%Y%m%d_%H%M%S")
        fname = filename or f"darkvault_{safe_tag}_{stamp}{BACKUP_EXTENSION}"
        if not fname.endswith(BACKUP_EXTENSION):
            fname += BACKUP_EXTENSION
        out_path = fname if os.path.isabs(fname) else os.path.join(self.backup_dir, fname)

        payload = self._collect_backup_payload()
        checksum = _compute_payload_sha256(payload)
        bundle = {
            "format": BACKUP_FORMAT,
            "exported_at": int(time.time()),
            "app": "DarkVault",
            "sha256": checksum,
            "payload": payload,
        }
        _safe_write_json(out_path, bundle)
        return out_path

    def list_backups(self):
        if not os.path.isdir(self.backup_dir):
            return []
        files = []
        for fn in sorted(os.listdir(self.backup_dir), reverse=True):
            if fn.endswith(BACKUP_EXTENSION) or fn.endswith(".json"):
                fp = os.path.join(self.backup_dir, fn)
                info = self.inspect_backup(fp)
                files.append({"name": fn, "path": fp, "valid": info.get("ok", False), "info": info})
        return files

    def inspect_backup(self, path):
        bundle = _safe_read_json(path, None)
        if not isinstance(bundle, dict) or bundle.get("format") != BACKUP_FORMAT:
            return {"ok": False, "error": "invalid_format"}
        payload = bundle.get("payload")
        if not isinstance(payload, dict):
            return {"ok": False, "error": "missing_payload"}
        expected = bundle.get("sha256", "")
        actual = _compute_payload_sha256(payload)
        if expected != actual:
            return {"ok": False, "error": "checksum_mismatch"}
        accounts = payload.get("accounts", [])
        saves = payload.get("saves", {})
        mods = payload.get("mods_files", {})
        total_ach = sum(len(a.get("achievements", {})) for a in accounts if isinstance(a, dict))
        return {
            "ok": True,
            "exported_at": int(bundle.get("exported_at", 0)),
            "accounts_count": len(accounts),
            "saves_count": len(saves),
            "mods_count": len(mods),
            "achievements_count": total_ach,
            "sha256_short": actual[:12],
        }

    def restore_full_backup(self, path, merge_accounts=False):
        check = self.inspect_backup(path)
        if not check.get("ok"):
            return check
        bundle = _safe_read_json(path, {})
        payload = bundle["payload"]

        if merge_accounts:
            existing_ids = {a["id"]: a for a in self.accounts}
            for inc in payload.get("accounts", []):
                if not isinstance(inc, dict) or not inc.get("id"):
                    continue
                eid = inc["id"]
                if eid in existing_ids:
                    cur = existing_ids[eid]
                    cur_ach = cur.setdefault("achievements", {})
                    for k, v in (inc.get("achievements") or {}).items():
                        cur_ach[k] = min(cur_ach.get(k, v), v) if k in cur_ach else v
                    for sk, sv in (inc.get("stats") or {}).items():
                        if isinstance(sv, (int, float)) and not isinstance(sv, bool):
                            cur["stats"][sk] = max(cur["stats"].get(sk, 0), sv)
                        elif isinstance(sv, list):
                            cur_list = cur["stats"].setdefault(sk, [])
                            for elem in sv:
                                if elem not in cur_list:
                                    cur_list.append(elem)
                else:
                    self.accounts.append(inc)
        else:
            self.accounts = list(payload.get("accounts", [])) or self.accounts
            self.active_id = payload.get("active_id") or self.accounts[0]["id"]
            if not any(a["id"] == self.active_id for a in self.accounts):
                self.active_id = self.accounts[0]["id"]
        self.save()

        if not merge_accounts:
            us = payload.get("user_settings")
            if isinstance(us, dict):
                _safe_write_json(os.path.join(self.data_dir, "user_settings.json"), us)
                load_user_settings()
            saves = payload.get("saves", {})
            for slot in ("1", "2", "3"):
                sp = os.path.join(self.data_dir, f"save_slot_{slot}.json")
                if slot in saves and isinstance(saves[slot], dict):
                    _safe_write_json(sp, saves[slot])
                elif os.path.exists(sp):
                    try:
                        os.remove(sp)
                    except Exception:
                        pass
            mc = payload.get("mods_config")
            if isinstance(mc, dict):
                _safe_write_json(os.path.join(self.data_dir, "mods_config.json"), mc)
            if isinstance(payload.get("quests_state"), dict):
                _safe_write_json(os.path.join(self.data_dir, "quests_state.json"), payload["quests_state"])

        mods_files = payload.get("mods_files", {})
        if isinstance(mods_files, dict) and mods_files:
            mods_dir = os.path.join(self.data_dir, "mods")
            os.makedirs(mods_dir, exist_ok=True)
            for fn, code in mods_files.items():
                if isinstance(fn, str) and fn.endswith(".py") and "/" not in fn and "\\" not in fn and isinstance(code, str):
                    with open(os.path.join(mods_dir, fn), "w", encoding="utf-8") as fh:
                        fh.write(code)

        seeds = payload.get("shared_seeds")
        if isinstance(seeds, list):
            _safe_write_json(os.path.join(self.data_dir, "shared_seeds.json"), seeds)

        self.load()
        return {"ok": True, "restored_accounts": len(self.accounts), "saves_restored": len(payload.get("saves", {}))}
