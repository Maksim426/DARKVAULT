export const KNOWN_MOD_HOOKS = [
  "on_register",
  "on_player_init",
  "on_run_start",
  "on_room_enter",
  "on_room_clear",
  "on_new_floor",
  "on_update",
];

export const DEFAULT_MODS = [
  {
    filename: "quick_boost_example.py",
    title: "Quick Boost Example",
    desc: "Даёт +1.0 Урон, +5 монет и лечит 1 сердце при входе в новые комнаты.",
    enabled: true,
    builtIn: true,
    code: `# Mod Example: Run Boost & Room Blessing
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
`,
  },
  {
    filename: "custom_relic_example.py",
    title: "Abyssal Tinker Pack",
    desc: "Добавляет артефакт «Ядро Призмы» (prism_core) и героя «Кузнец Теней» (shade_smith).",
    enabled: true,
    builtIn: true,
    code: `# Mod Example: Custom Hero & Relic (see heroes.py & items.py)
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
`,
  },
  {
    filename: "abyss_vortex_pack.py",
    title: "Пак Гравитационной Бездны",
    desc: "Добавляет гравитационную реликвию, стягивающую врагов, и ускоряет откат рывка и прыжка.",
    enabled: true,
    builtIn: true,
    code: `# Global Community Mod: Abyss Vortex Pack
# Automatically available to every DarkVault player in the global library.

MOD_META = {
    "id": "abyss_vortex_pack",
    "name": "Пак Гравитационной Бездны",
    "name_en": "Abyss Vortex Pack",
    "version": "1.2",
    "author": "DarkVault Global",
    "scope": "global",
    "description": "Добавляет гравитационную реликвию, стягивающую врагов, и ускоряет откат рывка и прыжка.",
    "description_en": "Adds a gravity singularity relic that pulls foes inward plus faster dash/jump cooldowns.",
}


def on_player_init(player, api):
    player.speed = min(6.2, player.speed + 0.3)
    player.dash_cd_max = max(36, int(getattr(player, "dash_cd_max", 82) * 0.85))
    if not getattr(player, "has_vortex", False):
        player.has_vortex = True


def on_room_clear(player, room, api):
    if api.rand() < 0.35:
        room.spawn_pickup(room.center_x, room.center_y + 34, "coin")
`,
  },
  {
    filename: "coop_sync_blessings.py",
    title: "Узы Двойной Тени",
    desc: "Дарует +1 Сердце души при спуске на новый ярус и цепную дугу слёз для обоих спутников.",
    enabled: true,
    builtIn: true,
    code: `# Global Community Mod: Co-op Sync Blessings
# Automatically available to every DarkVault player in the global library.

MOD_META = {
    "id": "coop_sync_blessings",
    "name": "Узы Двойной Тени",
    "name_en": "Twin Shade Blessings",
    "version": "1.1",
    "author": "ChronoSmith",
    "scope": "global",
    "description": "Дарует +1 Сердце души при спуске на новый ярус и цепную дугу слёз для обоих спутников.",
    "description_en": "Grants +1 Soul Heart on each new floor and unlocks Chain-Arc tears for solo & co-op runs.",
}


def on_player_init(player, api):
    player.has_chain_arc = True
    player.soul_hp += 2


def on_new_floor(player, floor_num, api):
    player.soul_hp += 2
    api.log(f"Twin Shade: Floor {floor_num} +1 Soul Heart")
`,
  },
  {
    filename: "stealth_phantom_challenge.py",
    title: "Испытание Фантома",
    desc: "Усиливает урон засад из невидимости [V] и снижает её перезарядку ценой уменьшения стартового здоровья.",
    enabled: true,
    builtIn: true,
    code: `# Global Community Mod: Stealth Phantom Challenge
# Automatically available to every DarkVault player in the global library.

MOD_META = {
    "id": "stealth_phantom_challenge",
    "name": "Испытание Фантома",
    "name_en": "Stealth Phantom Challenge",
    "version": "1.0",
    "author": "NightArchivist",
    "scope": "global",
    "description": "Усиливает урон засад из невидимости [V] и снижает её перезарядку ценой уменьшения стартового здоровья.",
    "description_en": "Amplifies [V] invisibility ambush crits and cooldown at the cost of -1 starting Red Heart.",
}


def on_player_init(player, api):
    if player.max_red_hp > 2:
        player.max_red_hp -= 2
        player.red_hp = min(player.red_hp, player.max_red_hp)
    player.damage += 0.8
    player.invis_cd_max = max(120, int(getattr(player, "invis_cd_max", 300) * 0.65))
    player.ambush_mult = max(2.4, float(getattr(player, "ambush_mult", 2.0)) + 0.4)
`,
  },
];

export const CODE_SNIPPETS = {
  item: `
def on_register(api):
    api.add_item({
        "id": "custom_orb",
        "name": "Сфера Тени",
        "name_en": "Shadow Orb",
        "desc": "+1.5 Урон",
        "desc_en": "+1.5 DMG",
        "type": "passive",
        "color": (235, 235, 235),
        "icon": "prism",
    })
`,
  hero: `
def on_register(api):
    api.add_hero({
        "id": "custom_walker",
        "name": "Странник Бездны",
        "name_en": "Abyss Walker",
        "title": "Новый герой",
        "desc": "Пользовательский герой с повышенной скоростью.",
        "hp": 6,
        "max_hp": 6,
        "soul_hp": 2,
        "speed": 4.6,
        "damage": 3.8,
    })
`,
  hook: `
def on_room_clear(player, room, api):
    if api.rand() < 0.25:
        room.spawn_pickup(room.center_x, room.center_y, "coin")
`,
};

export function sanitizeModFilename(rawName, existingFilenames = []) {
  const cleaned = String(rawName || "")
    .trim()
    .toLowerCase()
    .replace(/\.py$/i, "")
    .replace(/[^a-z0-9_-]+/g, "_")
    .replace(/^_+|_+$/g, "");
  const base = cleaned || "custom_mod";
  let candidate = `${base}.py`;
  const taken = new Set(existingFilenames.map((f) => String(f).toLowerCase()));
  if (!taken.has(candidate.toLowerCase())) {
    return candidate;
  }
  let idx = 2;
  while (taken.has(`${base}_${idx}.py`.toLowerCase())) {
    idx += 1;
  }
  return `${base}_${idx}.py`;
}

export function parseModMetadata(code, fallbackFilename = "custom_mod.py") {
  const src = String(code || "");
  const nameMatch =
    src.match(/MOD_NAME\s*=\s*["']([^"'\n]+)["']/) ||
    src.match(/["']name["']\s*:\s*["']([^"'\n]+)["']/);
  const descMatch =
    src.match(/MOD_DESC\s*=\s*["']([^"'\n]+)["']/) ||
    src.match(/["']description["']\s*:\s*["']([^"'\n]+)["']/);

  const fallbackTitle = String(fallbackFilename || "custom_mod.py")
    .replace(/\.py$/i, "")
    .replace(/[_-]+/g, " ")
    .trim();

  return {
    title: nameMatch ? nameMatch[1].trim() : fallbackTitle || "Custom Mod",
    desc: descMatch ? descMatch[1].trim() : "Пользовательский Python-скрипт для DarkVault.",
  };
}

export function validatePythonLikeSyntax(code) {
  const src = String(code || "");
  if (!src.trim()) {
    return { valid: false, errors: ["Код мода не может быть пустым."], hooks: [], lines: 0 };
  }

  const errors = [];
  const stack = [];
  const pairs = { ")": "(", "]": "[", "}": "{" };
  const opening = new Set(["(", "[", "{"]);
  const lines = src.split(/\r?\n/);

  for (let lineIdx = 0; lineIdx < lines.length; lineIdx += 1) {
    const line = lines[lineIdx];
    let i = 0;
    let inString = null;
    while (i < line.length) {
      const ch = line[i];
      if (!inString && ch === "#") {
        break;
      }
      if (!inString && (ch === '"' || ch === "'")) {
        if (line.slice(i, i + 3) === ch.repeat(3)) {
          // Triple-quoted strings can span multiple lines; skip basic per-line check cleanly.
          inString = ch.repeat(3);
          i += 3;
          const endTriple = line.indexOf(inString, i);
          if (endTriple !== -1) {
            inString = null;
            i = endTriple + 3;
            continue;
          }
          break;
        }
        inString = ch;
        i += 1;
        continue;
      }
      if (inString && inString.length === 1) {
        if (ch === "\\") {
          i += 2;
          continue;
        }
        if (ch === inString) {
          inString = null;
        }
        i += 1;
        continue;
      }
      if (!inString) {
        if (opening.has(ch)) {
          stack.push({ ch, line: lineIdx + 1 });
        } else if (pairs[ch]) {
          const top = stack.pop();
          if (!top || top.ch !== pairs[ch]) {
            errors.push(`Строка ${lineIdx + 1}: лишняя или непарная скобка '${ch}'.`);
          }
        }
      }
      i += 1;
    }
    if (inString && inString.length === 1) {
      errors.push(`Строка ${lineIdx + 1}: незакрытая кавычка ${inString}.`);
    }
  }

  if (stack.length > 0) {
    const unclosed = stack[stack.length - 1];
    errors.push(`Строка ${unclosed.line}: незакрытая скобка '${unclosed.ch}'.`);
  }

  const hooks = [];
  for (const hook of KNOWN_MOD_HOOKS) {
    const re = new RegExp(`^\\s*def\\s+${hook}\\s*\\(`, "m");
    if (re.test(src)) {
      hooks.push(hook);
    }
  }

  return {
    valid: errors.length === 0,
    errors,
    hooks,
    lines: lines.length,
  };
}

export function mergeStoredMods(storedList, defaults = DEFAULT_MODS) {
  const defaultMap = new Map(defaults.map((d) => [d.filename, { ...d }]));
  if (!Array.isArray(storedList) || storedList.length === 0) {
    return defaults.map((d) => ({ ...d }));
  }

  const merged = [];
  const seen = new Set();

  for (const item of storedList) {
    if (!item || typeof item !== "object" || !item.filename || typeof item.code !== "string") {
      continue;
    }
    if (seen.has(item.filename)) {
      continue;
    }
    seen.add(item.filename);
    const meta = parseModMetadata(item.code, item.filename);
    merged.push({
      filename: String(item.filename),
      title: String(item.title || meta.title),
      desc: String(item.desc || meta.desc),
      enabled: Boolean(item.enabled),
      builtIn: defaultMap.has(item.filename) || Boolean(item.builtIn),
      code: item.code,
    });
  }

  for (const def of defaults) {
    if (!seen.has(def.filename)) {
      merged.push({ ...def });
    }
  }
  return merged;
}

export function filterModsList(mods, query) {
  const q = String(query || "").toLowerCase().trim();
  if (!q) {
    return [...mods];
  }
  return mods.filter(
    (m) =>
      String(m.title || "").toLowerCase().includes(q) ||
      String(m.desc || "").toLowerCase().includes(q) ||
      String(m.filename || "").toLowerCase().includes(q)
  );
}
