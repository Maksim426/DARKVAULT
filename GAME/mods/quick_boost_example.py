# Mod Example: Run Boost & Room Blessing
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
