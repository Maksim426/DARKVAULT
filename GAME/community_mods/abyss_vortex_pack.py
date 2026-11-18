# Global Community Mod: Abyss Vortex Pack
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
