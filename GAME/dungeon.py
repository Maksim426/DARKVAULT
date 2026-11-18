from collections import deque
import random
from bosses import MINIBOSS_KEYS, pick_floor_boss_key, spawn_boss_for_room
from items import ItemPedestal, Pickup, get_random_item
from room import Door, LAYOUT_TEMPLATES, Room
from settings import ENDLESS_MODIFIERS, PLAYABLE_BOTTOM, PLAYABLE_LEFT, PLAYABLE_RIGHT, PLAYABLE_TOP


DIRS = [
    ("N", (0, -1), "S"),
    ("S", (0, 1), "N"),
    ("E", (1, 0), "W"),
    ("W", (-1, 0), "E"),
]

MAX_ARTIFACTS_PER_FLOOR = 3


def enforce_floor_artifact_cap(rooms, rng=None, limit=MAX_ARTIFACTS_PER_FLOOR):
    """Strictly limit pedestals/artifacts spawned per floor (default max 3)."""
    if not isinstance(rooms, dict) or limit < 0:
        return 0
    _rng = rng if rng is not None else random.Random()
    priority = {"treasure": 0, "library": 1, "shop": 2, "secret": 3, "curse": 4}
    entries = []
    for coord, rm in rooms.items():
        rt = getattr(rm, "room_type", "normal")
        rank = priority.get(rt, 5)
        for ped in getattr(rm, "pedestals", []):
            if getattr(ped, "alive", True):
                entries.append((rank, rm, ped))
    if len(entries) <= limit:
        return len(entries)
    entries.sort(key=lambda e: e[0])
    kept = set(id(e[2]) for e in entries[:limit])
    for _, rm, ped in entries[limit:]:
        if id(ped) in kept:
            continue
        if ped in rm.pedestals:
            rm.pedestals.remove(ped)
        rm.pickups.append(Pickup(ped.x, ped.y, _rng.choice(["coin", "soul_heart", "key"])))
    return limit


class DungeonGenerator:
    def __init__(self, floor_level=1, seed=None, game_mode="classic"):
        self.floor_level = int(floor_level)
        self.game_mode = game_mode
        self.rng = random.Random(seed) if seed is not None else random.Random()
        self.topology = self.rng.choice(["branching_crypt", "sprawling_catacombs", "ring_citadel", "serpentine_depths"])
        self.floor_modifier = None
        if self.floor_level >= 6:
            self.floor_modifier = self.rng.choice(ENDLESS_MODIFIERS)

    def _build_layout_graph(self, target_count):
        coords = {(0, 0)}
        frontier = [(0, 0)]
        attempts = 0
        max_attempts = max(620, target_count * 34)

        if self.topology == "ring_citadel" and target_count >= 10:
            ring_pts = [
                (1, 0), (2, 0), (2, 1), (2, 2), (1, 2), (0, 2), (-1, 2), (-1, 1), (-1, 0),
            ]
            if self.rng.random() < 0.5:
                ring_pts = [(-x, -y) for x, y in ring_pts]
            for pt in ring_pts[: min(len(ring_pts), target_count - 2)]:
                coords.add(pt)
                frontier.append(pt)

        while len(coords) < target_count and attempts < max_attempts:
            attempts += 1
            if self.topology == "serpentine_depths":
                base = frontier[-1] if (frontier and self.rng.random() < 0.80) else self.rng.choice(frontier)
            elif self.topology == "sprawling_catacombs":
                base = self.rng.choice(frontier)
            else:
                if self.rng.random() < 0.55 and len(frontier) > 1:
                    base = frontier[-1] if self.rng.random() < 0.48 else self.rng.choice(frontier)
                else:
                    base = self.rng.choice(frontier)

            _, (dx, dy), _ = self.rng.choice(DIRS)
            cand = (base[0] + dx, base[1] + dy)
            if cand in coords:
                continue
            adj = sum(1 for _, (ox, oy), _ in DIRS if (cand[0] + ox, cand[1] + oy) in coords)
            max_adj = 2 if (self.topology == "ring_citadel" or attempts > max_attempts // 2) else 1
            if adj <= max_adj:
                coords.add(cand)
                frontier.append(cand)
        return coords

    def _bfs_distances(self, coords):
        dist = {(0, 0): 0}
        q = deque([(0, 0)])
        while q:
            cur = q.popleft()
            for _, (dx, dy), _ in DIRS:
                nb = (cur[0] + dx, cur[1] + dy)
                if nb in coords and nb not in dist:
                    dist[nb] = dist[cur] + 1
                    q.append(nb)
        return dist

    def generate_floor(self, boss_override=None):
        if self.game_mode == "endless_abyss":
            arena = Room(
                (0, 0),
                room_type="normal",
                floor_level=self.floor_level,
                layout_key="pillars_4",
                game_mode="endless_abyss",
                floor_modifier=self.floor_modifier,
                seed=self.rng.randrange(1, 2**31 - 1),
            )
            arena.visited = True
            arena.cleared = False
            return {(0, 0): arena}

        if self.game_mode == "boss_rush":
            start_rm = Room(
                (0, 0),
                room_type="start",
                floor_level=self.floor_level,
                layout_key="empty",
                game_mode="boss_rush",
                floor_modifier=self.floor_modifier,
                seed=self.rng.randrange(1, 2**31 - 1),
            )
            boss_rm = Room(
                (0, -1),
                room_type="boss",
                floor_level=self.floor_level,
                layout_key="empty",
                game_mode="boss_rush",
                floor_modifier=self.floor_modifier,
                seed=self.rng.randrange(1, 2**31 - 1),
            )
            start_rm.doors["N"] = Door("N", (0, -1), target_type="boss", locked=False)
            boss_rm.doors["S"] = Door("S", (0, 0), target_type="start", locked=False)
            cx = (PLAYABLE_LEFT + PLAYABLE_RIGHT) // 2
            cy = (PLAYABLE_TOP + PLAYABLE_BOTTOM) // 2
            boss_key = boss_override if boss_override else pick_floor_boss_key(self.floor_level, self.rng)
            boss_rm.bosses = spawn_boss_for_room(boss_rm, boss_key, cx, cy, self.floor_level, self.floor_modifier)
            boss_rm.cleared = False
            start_rm.visited = True
            start_rm.cleared = True
            return {(0, 0): start_rm, (0, -1): boss_rm}

        if self.game_mode == "free_roam":
            target_rooms = 22 + min(12, self.floor_level * 2) + self.rng.randint(-1, 3)
        else:
            target_rooms = 11 + min(14, self.floor_level * 2) + self.rng.randint(0, 3)

        coords = self._build_layout_graph(target_rooms)
        dist = self._bfs_distances(coords)

        candidates = [c for c in coords if c != (0, 0)]
        leaves = [
            c for c in candidates
            if sum(1 for _, (dx, dy), _ in DIRS if (c[0] + dx, c[1] + dy) in coords) == 1
        ]
        far_leaves = [c for c in leaves if dist.get(c, 0) >= 3]
        if far_leaves:
            boss_coord = max(far_leaves, key=lambda c: dist.get(c, 0))
        elif leaves:
            boss_coord = max(leaves, key=lambda c: dist.get(c, 0))
        else:
            boss_coord = max(candidates, key=lambda c: dist.get(c, 0))

        # Ensure enough degree-1 leaves exist for locked special rooms so bridges are never locked.
        desired_leaves = 6 if self.game_mode == "free_roam" else 4
        if len(leaves) < desired_leaves + 1:
            expand_bases = [c for c in coords if c != boss_coord]
            self.rng.shuffle(expand_bases)
            for base in expand_bases:
                if len(leaves) >= desired_leaves + 1:
                    break
                dirs_shuffled = list(DIRS)
                self.rng.shuffle(dirs_shuffled)
                for _, (dx, dy), _ in dirs_shuffled:
                    cand = (base[0] + dx, base[1] + dy)
                    if cand in coords:
                        continue
                    adj_cnt = sum(1 for _, (ox, oy), _ in DIRS if (cand[0] + ox, cand[1] + oy) in coords)
                    if adj_cnt == 1 and base not in leaves:
                        coords.add(cand)
                        leaves.append(cand)
                        dist[cand] = dist.get(base, 0) + 1
                        break

        room_types = {(0, 0): "start", boss_coord: "boss"}
        remaining = [c for c in coords if c not in room_types]
        self.rng.shuffle(remaining)
        dead_set = set(leaves)
        dead_pool = [c for c in remaining if c in dead_set]
        other_pool = [c for c in remaining if c not in dead_set]

        locked_specials = ["treasure", "shop", "library"]
        unlocked_specials = ["curse", "arcade", "sacrifice", "dice", "miniboss"]
        if self.floor_level >= 3 and self.rng.random() < 0.45:
            extra_sp = self.rng.choice(["curse", "shop", "library"])
            if extra_sp == "curse":
                unlocked_specials.append(extra_sp)
            else:
                locked_specials.append(extra_sp)
        if self.floor_level >= 4:
            unlocked_specials.append("curse")
        if self.game_mode == "free_roam":
            locked_specials.extend(["treasure", "library", "shop"])
            unlocked_specials.append("curse")

        for sp in locked_specials:
            if dead_pool:
                c = dead_pool.pop(0)
                room_types[c] = sp
            elif other_pool and self.game_mode == "free_roam":
                c = other_pool.pop(0)
                room_types[c] = sp

        assign_order = dead_pool + other_pool
        for sp in unlocked_specials:
            if assign_order:
                c = assign_order.pop(0)
                room_types[c] = sp

        secret_coord = None
        best_secret_score = -1
        base_scan = list(coords)
        self.rng.shuffle(base_scan)
        for base in base_scan:
            for _, (dx, dy), _ in DIRS:
                cand = (base[0] + dx, base[1] + dy)
                if cand in coords:
                    continue
                adj_coords = [(cand[0] + ox, cand[1] + oy) for _, (ox, oy), _ in DIRS if (cand[0] + ox, cand[1] + oy) in coords]
                if boss_coord in adj_coords:
                    continue
                if len(adj_coords) >= 2 and len(adj_coords) > best_secret_score:
                    best_secret_score = len(adj_coords)
                    secret_coord = cand

        if secret_coord is None:
            for base in base_scan:
                if base == boss_coord or room_types.get(base) in ("treasure", "shop", "library"):
                    continue
                for _, (dx, dy), _ in DIRS:
                    cand = (base[0] + dx, base[1] + dy)
                    if cand not in coords:
                        secret_coord = cand
                        break
                if secret_coord is not None:
                    break

        if secret_coord is not None:
            coords.add(secret_coord)
            room_types[secret_coord] = "secret"

        layout_keys = list(LAYOUT_TEMPLATES.keys()) + ["procedural"] * 6
        rooms = {}
        for c in coords:
            rt = room_types.get(c, "normal")
            lk = "empty" if rt != "normal" else self.rng.choice(layout_keys)
            rooms[c] = Room(
                c,
                room_type=rt,
                floor_level=self.floor_level,
                layout_key=lk,
                game_mode=self.game_mode,
                floor_modifier=self.floor_modifier,
                seed=self.rng.randrange(1, 2**31 - 1),
            )

        non_secret_deg = {}
        for c in rooms:
            non_secret_deg[c] = sum(
                1
                for _, (dx, dy), _ in DIRS
                if (c[0] + dx, c[1] + dy) in rooms and rooms[(c[0] + dx, c[1] + dy)].room_type != "secret"
            )

        for c, room in rooms.items():
            for d_name, (dx, dy), _ in DIRS:
                nb = (c[0] + dx, c[1] + dy)
                if nb not in rooms:
                    continue
                nb_room = rooms[nb]
                is_secret_link = room.room_type == "secret" or nb_room.room_type == "secret"
                is_leaf_lock_target = (
                    nb_room.room_type in ("treasure", "shop", "library")
                    and non_secret_deg.get(nb, 0) == 1
                    and not is_secret_link
                    and nb != boss_coord
                    and self.game_mode != "free_roam"
                )
                door = Door(d_name, nb, target_type=nb_room.room_type, locked=is_leaf_lock_target, secret=is_secret_link)
                if is_secret_link and room.room_type == "secret":
                    door.opened = True
                room.doors[d_name] = door

        # Safety verification: guarantee every non-secret, unlocked room (and boss room)
        # is reachable from (0, 0) with 0 keys, and every room has an unlocked exit path back.
        reachable = {(0, 0)}
        q = deque([(0, 0)])
        while q:
            cur = q.popleft()
            for door in rooms[cur].doors.values():
                if not door.locked and not door.secret and door.target_coord not in reachable:
                    reachable.add(door.target_coord)
                    q.append(door.target_coord)
        for c, rm in rooms.items():
            if rm.room_type not in ("treasure", "shop", "library", "secret") and c not in reachable:
                # Unlock any bridge doors blocking progression if an edge topology occurred.
                for rm_other in rooms.values():
                    for door in rm_other.doors.values():
                        if not door.secret and door.target_coord in rooms and rooms[door.target_coord].room_type not in ("treasure", "shop", "library"):
                            door.locked = False

        cx = (PLAYABLE_LEFT + PLAYABLE_RIGHT) // 2
        cy = (PLAYABLE_TOP + PLAYABLE_BOTTOM) // 2

        boss_room = rooms[boss_coord]
        boss_key = boss_override if boss_override else pick_floor_boss_key(self.floor_level, self.rng)
        boss_room.bosses = spawn_boss_for_room(boss_room, boss_key, cx, cy, self.floor_level, self.floor_modifier)
        boss_room.cleared = False

        for c, r in rooms.items():
            if r.room_type == "miniboss":
                mk = self.rng.choice(MINIBOSS_KEYS)
                r.bosses = spawn_boss_for_room(r, mk, cx, cy, self.floor_level, self.floor_modifier)
                r.cleared = False

        rooms[(0, 0)].visited = True
        enforce_floor_artifact_cap(rooms, self.rng, MAX_ARTIFACTS_PER_FLOOR)
        return rooms


def spawn_devil_deal_room(floor_level, taken_items=None, return_coord=(0, 0), exit_dir="S"):
    room = Room((99, 99), room_type="devil", floor_level=floor_level, layout_key="empty", seed=random.randrange(1, 2**31 - 1))
    cx = (PLAYABLE_LEFT + PLAYABLE_RIGHT) // 2
    cy = (PLAYABLE_TOP + PLAYABLE_BOTTOM) // 2
    ex = set(taken_items or ())
    it1 = get_random_item(ex, "passive")
    ex.add(it1["id"])
    it2 = get_random_item(ex, "passive")
    room.pedestals.append(ItemPedestal(cx - 110, cy, it1, devil_cost=1))
    room.pedestals.append(ItemPedestal(cx + 110, cy, it2, devil_cost=2))
    room.pickups.append(Pickup(cx, cy + 75, "black_heart"))
    edir = exit_dir if exit_dir in ("N", "S", "E", "W") else "S"
    room.doors[edir] = Door(edir, return_coord, target_type="boss")
    return room
