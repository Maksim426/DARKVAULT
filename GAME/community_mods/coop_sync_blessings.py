# Global Community Mod: Co-op Sync Blessings
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
