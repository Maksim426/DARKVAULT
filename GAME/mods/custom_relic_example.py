# Mod Example: Custom Hero & Relic (see heroes.py & items.py)
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
