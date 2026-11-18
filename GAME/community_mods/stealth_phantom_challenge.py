# Global Community Mod: Stealth Phantom Challenge
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
