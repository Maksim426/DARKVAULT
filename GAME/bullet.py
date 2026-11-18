import math
import pygame
from settings import (
    PALETTE,
    PLAYABLE_BOTTOM,
    PLAYABLE_LEFT,
    PLAYABLE_RIGHT,
    PLAYABLE_TOP,
    _prune_cache,
    draw_aa_circle,
    draw_aa_poly,
    draw_aa_ring,
    get_disc_sprite,
    get_glow_surf,
    get_particle_surf,
    get_shadow_surf,
    gray,
    m,
    render_4x_smooth,
)


_ENEMY_PROJ_CACHE = {}


def _get_enemy_proj_sprite(r):
    ir = max(4, int(round(r)))
    surf = _ENEMY_PROJ_CACHE.get(ir)
    if surf is not None:
        return surf
    _prune_cache(_ENEMY_PROJ_CACHE, 64)
    size = (ir + 3) * 2

    def _draw(hi, hw, hh):
        cx = cy = hw * 0.5
        hr = ir * 4.0
        draw_aa_circle(hi, (244, 244, 244, 255), cx, cy, hr + 4.0)
        draw_aa_circle(hi, (22, 22, 22, 255), cx, cy, max(4.0, hr - 4.0))
        draw_aa_circle(hi, (236, 236, 236, 255), cx - hr * 0.25, cy - hr * 0.25, max(2.0, hr * 0.28))

    surf = render_4x_smooth(size, size, _draw, blur_radius=0.25)
    _ENEMY_PROJ_CACHE[ir] = surf
    return surf


class SplashParticle:
    def __init__(self, x, y, vx, vy, color, radius=3, life=16):
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.color = gray(color)
        self.radius = max(1, int(round(radius)))
        self.life = int(life)
        self.max_life = max(1, int(life))
        self.alive = True

    def update(self, dt=1.0):
        self.x += self.vx * dt
        self.y += self.vy * dt
        damp = 0.92 ** dt
        self.vx *= damp
        self.vy *= damp
        self.life -= dt
        if self.life <= 0:
            self.alive = False

    def draw(self, screen):
        if not self.alive:
            return
        ratio = max(0.0, min(1.0, self.life / self.max_life))
        r = max(1, int(round(self.radius * (0.45 + 0.55 * ratio))))
        alpha = int(230 * ratio)
        surf = get_particle_surf(r, self.color[0], alpha)
        screen.blit(surf, (int(round(self.x - surf.get_width() * 0.5)), int(round(self.y - surf.get_height() * 0.5))))


class DustParticle(SplashParticle):
    def __init__(self, x, y, vx, vy, color=(196, 196, 196), radius=3, life=24):
        super().__init__(x, y, vx, vy, color, radius, life)

    def draw(self, screen):
        if not self.alive:
            return
        ratio = max(0.0, min(1.0, self.life / self.max_life))
        r = max(1, int(round(self.radius * (0.55 + 0.45 * ratio))))
        alpha = int(165 * ratio)
        surf = get_particle_surf(r, self.color[0], alpha)
        screen.blit(surf, (int(round(self.x - surf.get_width() * 0.5)), int(round(self.y - surf.get_height() * 0.5))))


class AfterimageParticle:
    def __init__(self, x, y, radius, color=(210, 210, 210), life=12):
        self.x = float(x)
        self.y = float(y)
        self.radius = max(2, int(round(radius)))
        self.color = gray(color)
        self.life = int(life)
        self.max_life = max(1, int(life))
        self.alive = True

    def update(self, dt=1.0):
        self.life -= dt
        if self.life <= 0:
            self.alive = False

    def draw(self, screen):
        if not self.alive:
            return
        ratio = max(0.0, min(1.0, self.life / self.max_life))
        alpha = int(128 * ratio)
        surf = get_particle_surf(self.radius, self.color[0], alpha)
        screen.blit(surf, (int(round(self.x - surf.get_width() * 0.5)), int(round(self.y - surf.get_height() * 0.5))))


class RingParticle:
    def __init__(self, x, y, max_radius=44, color=(240, 240, 240), life=16, width=2):
        self.x = float(x)
        self.y = float(y)
        self.max_radius = float(max_radius)
        self.color = gray(color)
        self.life = int(life)
        self.max_life = max(1, int(life))
        self.width = max(1, int(width))
        self.alive = True

    def update(self, dt=1.0):
        self.life -= dt
        if self.life <= 0:
            self.alive = False

    def draw(self, screen):
        if not self.alive:
            return
        progress = 1.0 - max(0.0, min(1.0, self.life / self.max_life))
        cur_r = max(3, int(round(4 + self.max_radius * progress)))
        lum = int(max(40, min(250, self.color[0] * (1.0 - progress * 0.65))))
        draw_aa_ring(screen, (lum, lum, lum), self.x, self.y, cur_r, self.width)


class LightningArcParticle:
    def __init__(self, x1, y1, x2, y2, life=10):
        self.x1 = float(x1)
        self.y1 = float(y1)
        self.x2 = float(x2)
        self.y2 = float(y2)
        self.life = float(life)
        self.max_life = max(1.0, float(life))
        self.alive = True
        mid_x = (self.x1 + self.x2) * 0.5
        mid_y = (self.y1 + self.y2) * 0.5
        dx = self.x2 - self.x1
        dy = self.y2 - self.y1
        perp_x = -dy * 0.22
        perp_y = dx * 0.22
        self.pts = [
            (self.x1, self.y1),
            (self.x1 * 0.65 + self.x2 * 0.35 + perp_x, self.y1 * 0.65 + self.y2 * 0.35 + perp_y),
            (mid_x - perp_x * 0.7, mid_y - perp_y * 0.7),
            (self.x1 * 0.3 + self.x2 * 0.7 + perp_x * 0.45, self.y1 * 0.3 + self.y2 * 0.7 + perp_y * 0.45),
            (self.x2, self.y2),
        ]

    def update(self, dt=1.0):
        self.life -= dt
        if self.life <= 0:
            self.alive = False

    def draw(self, screen):
        if not self.alive:
            return
        ratio = max(0.0, min(1.0, self.life / self.max_life))
        lum = int(160 + 95 * ratio)
        pygame.draw.lines(screen, (lum, lum, lum), False, [(int(px), int(py)) for px, py in self.pts], 2)



class Tear:
    def __init__(
        self,
        x,
        y,
        vx,
        vy,
        damage=3.5,
        max_range=420.0,
        radius=7.0,
        color=None,
        piercing=False,
        bouncing=False,
        homing=False,
        splitting=False,
        spectral=False,
        poison=False,
        holy=False,
        bone=False,
        brimstone=False,
        boomerang=False,
        coal=False,
        explosive=False,
        lobbed=False,
        shockwave=False,
        blast_radius=62.0,
        vortex=False,
        chain_arc=False,
        ambush=False,
        owner_x=None,
        owner_y=None,
    ):
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.damage = float(damage)
        self.max_range = float(max_range)
        self.radius = float(radius)
        self.color = gray(color) if color else PALETTE["tears"]
        self.piercing = bool(piercing)
        self.bouncing = bool(bouncing)
        self.homing = bool(homing)
        self.splitting = bool(splitting)
        self.spectral = bool(spectral)
        self.poison = bool(poison)
        self.holy = bool(holy)
        self.bone = bool(bone)
        self.brimstone = bool(brimstone)
        self.boomerang = bool(boomerang)
        self.coal = bool(coal)
        self.explosive = bool(explosive)
        self.lobbed = bool(lobbed)
        self.shockwave = bool(shockwave)
        self.blast_radius = float(blast_radius)
        self.vortex = bool(vortex)
        self.chain_arc = bool(chain_arc)
        self.ambush = bool(ambush)
        self.explode_on_death = bool(self.explosive or self.lobbed)
        self.should_explode = False
        self.air_z = 0.0
        self.lob_peak = min(84.0, max(44.0, self.max_range * 0.16)) if self.lobbed else 0.0
        self.owner_x = x if owner_x is None else owner_x
        self.owner_y = y if owner_y is None else owner_y
        self.traveled = 0.0
        self.age = 0.0
        self.alive = True
        self.hit_ids = set()
        self.bounces_left = 2 if bouncing else 0
        self.trail = []
        self.spin = 0.0

    def update(self, room, enemies=None, dt=1.0, player_pos=None):
        if not self.alive:
            return
        self.age += dt
        self.spin += 0.25 * dt
        if len(self.trail) >= 5:
            self.trail.pop(0)
        self.trail.append((self.x, self.y))

        if self.homing and enemies:
            best_e = None
            best_d = 210.0
            for e in enemies:
                if not getattr(e, "alive", True) or id(e) in self.hit_ids:
                    continue
                d = math.hypot(e.x - self.x, e.y - self.y)
                if d < best_d:
                    best_d = d
                    best_e = e
            if best_e is not None:
                spd = math.hypot(self.vx, self.vy) or 6.5
                ang_cur = math.atan2(self.vy, self.vx)
                ang_tar = math.atan2(best_e.y - self.y, best_e.x - self.x)
                diff = (ang_tar - ang_cur + math.pi) % (2.0 * math.pi) - math.pi
                ang_new = ang_cur + max(-0.09 * dt, min(0.09 * dt, diff))
                self.vx = math.cos(ang_new) * spd
                self.vy = math.sin(ang_new) * spd

        if self.vortex and enemies:
            for e in enemies:
                if not getattr(e, "alive", True):
                    continue
                dx = self.x - e.x
                dy = self.y - e.y
                d2 = dx * dx + dy * dy
                if 16.0 < d2 < 145.0 * 145.0:
                    d = math.sqrt(d2)
                    pull = (1.0 - d / 145.0) * 1.45 * dt
                    e.x = max(PLAYABLE_LEFT + 16, min(PLAYABLE_RIGHT - 16, e.x + (dx / d) * pull))
                    e.y = max(PLAYABLE_TOP + 16, min(PLAYABLE_BOTTOM - 16, e.y + (dy / d) * pull))

        if self.boomerang and self.traveled > self.max_range * 0.40 and player_pos is not None:
            px, py = player_pos
            dx, dy = px - self.x, py - self.y
            d = math.hypot(dx, dy) or 1.0
            cur_spd = max(6.8, math.hypot(self.vx, self.vy))
            self.vx += (dx / d) * 0.65 * dt
            self.vy += (dy / d) * 0.65 * dt
            ns = math.hypot(self.vx, self.vy) or 1.0
            if ns > cur_spd * 1.15:
                scale = (cur_spd * 1.15) / ns
                self.vx *= scale
                self.vy *= scale

        nx = self.x + self.vx * dt
        ny = self.y + self.vy * dt
        self.traveled += math.hypot(nx - self.x, ny - self.y)
        self.x = nx
        self.y = ny

        if self.lobbed:
            prog = min(1.0, self.traveled / max(1.0, self.max_range))
            self.air_z = math.sin(prog * math.pi) * self.lob_peak
        else:
            self.air_z = 0.0

        hit_wall = False
        if self.x - self.radius < PLAYABLE_LEFT:
            self.x = PLAYABLE_LEFT + self.radius
            if self.bounces_left > 0:
                self.vx = abs(self.vx)
                self.bounces_left -= 1
            else:
                hit_wall = True
        elif self.x + self.radius > PLAYABLE_RIGHT:
            self.x = PLAYABLE_RIGHT - self.radius
            if self.bounces_left > 0:
                self.vx = -abs(self.vx)
                self.bounces_left -= 1
            else:
                hit_wall = True

        if self.y - self.radius < PLAYABLE_TOP:
            self.y = PLAYABLE_TOP + self.radius
            if self.bounces_left > 0:
                self.vy = abs(self.vy)
                self.bounces_left -= 1
            else:
                hit_wall = True
        elif self.y + self.radius > PLAYABLE_BOTTOM:
            self.y = PLAYABLE_BOTTOM - self.radius
            if self.bounces_left > 0:
                self.vy = -abs(self.vy)
                self.bounces_left -= 1
            else:
                hit_wall = True

        if not self.spectral and self.air_z < 12.0 and not hit_wall and room is not None:
            for obs in room.obstacles:
                if not obs.alive or not obs.blocks_tears:
                    continue
                if obs.rect.collidepoint(self.x, self.y):
                    if obs.kind in ("poop", "urn"):
                        obs.damage(1)
                    if self.bounces_left > 0:
                        if abs(self.x - obs.rect.centerx) > abs(self.y - obs.rect.centery):
                            self.vx = -self.vx
                            self.x += 4.0 if self.vx > 0 else -4.0
                        else:
                            self.vy = -self.vy
                            self.y += 4.0 if self.vy > 0 else -4.0
                        self.bounces_left -= 1
                    else:
                        hit_wall = True
                    break

        if hit_wall or self.traveled >= self.max_range:
            if self.explode_on_death:
                self.should_explode = True
            self.alive = False

    def get_effective_damage(self):
        dmg = self.damage
        if self.coal:
            dmg *= 1.0 + min(1.4, self.traveled / 340.0)
        return dmg

    def draw(self, screen):
        if not self.alive:
            return
        r = max(4, int(round(self.radius)))
        progress = min(1.0, self.traveled / max(1.0, self.max_range))
        drop_y = ((progress ** 2.2) * 8.0) if not self.lobbed else (-self.air_z)
        sh_scale = max(0.55, 1.0 - self.air_z / 120.0)
        sh = get_shadow_surf(int(r * 2.1 * sh_scale), max(4, int(r * 0.9 * sh_scale)), 88)
        screen.blit(sh, (int(round(self.x - sh.get_width() * 0.5)), int(round(self.y + r + 5 - sh.get_height() * 0.5))))

        if self.lobbed:
            prog = min(1.0, self.traveled / max(1.0, self.max_range))
            rem = max(0.0, self.max_range - self.traveled)
            spd = max(0.01, math.hypot(self.vx, self.vy))
            tx = max(PLAYABLE_LEFT + 12, min(PLAYABLE_RIGHT - 12, self.x + (self.vx / spd) * rem))
            ty = max(PLAYABLE_TOP + 12, min(PLAYABLE_BOTTOM - 12, self.y + (self.vy / spd) * rem))
            ring_lum = int(130 + 115 * prog)
            draw_aa_ring(screen, (ring_lum, ring_lum, ring_lum), tx, ty, max(8, int(round(self.blast_radius * 0.38))), 1)

        for idx, (tx, ty) in enumerate(self.trail):
            frac = (idx + 1) / (len(self.trail) + 1)
            tr_r = max(1, int(r * 0.45 * frac))
            p_surf = get_particle_surf(tr_r, 224, int(110 * frac))
            screen.blit(p_surf, (int(round(tx - p_surf.get_width() * 0.5)), int(round(ty + drop_y - p_surf.get_height() * 0.5))))

        draw_y = self.y + drop_y
        glow_r = int(r * (2.8 if (self.holy or self.explosive) else 2.3))
        gl = get_glow_surf(glow_r, 245, 92 if (self.holy or self.explosive) else 54)
        screen.blit(gl, (int(round(self.x - gl.get_width() * 0.5)), int(round(draw_y - gl.get_height() * 0.5))))

        if self.holy:
            draw_aa_ring(screen, (250, 250, 250), self.x, draw_y, r + 9, 1)
        if self.shockwave:
            draw_aa_ring(screen, (224, 224, 224), self.x, draw_y, r + 4 + int((self.age * 0.5) % 4), 1)
        if self.vortex:
            draw_aa_ring(screen, (206, 206, 206), self.x, draw_y, r + 6 + int(2 * math.sin(self.age * 0.25)), 1)
            sa = self.spin * 1.5
            draw_aa_circle(screen, (242, 242, 242), self.x + math.cos(sa) * (r + 5), draw_y + math.sin(sa) * (r + 5), 2)
            draw_aa_circle(screen, (164, 164, 164), self.x - math.cos(sa) * (r + 5), draw_y - math.sin(sa) * (r + 5), 2)
        if self.chain_arc:
            a1 = self.spin * 2.1
            pygame.draw.line(
                screen,
                (244, 244, 244),
                (int(self.x - math.cos(a1) * (r + 4)), int(draw_y - math.sin(a1) * (r + 4))),
                (int(self.x + math.cos(a1) * (r + 4)), int(draw_y + math.sin(a1) * (r + 4))),
                1,
            )
        if self.ambush:
            draw_aa_ring(screen, (254, 254, 254), self.x, draw_y, r + 5, 2)

        if self.bone:
            cos_a = math.cos(self.spin)
            sin_a = math.sin(self.spin)
            hl = r * 1.35
            x1, y1 = self.x - cos_a * hl, draw_y - sin_a * hl
            x2, y2 = self.x + cos_a * hl, draw_y + sin_a * hl
            pygame.draw.line(screen, (18, 18, 18), (int(x1), int(y1)), (int(x2), int(y2)), max(4, r))
            pygame.draw.line(screen, (242, 242, 242), (int(x1), int(y1)), (int(x2), int(y2)), max(2, r - 2))
            for kx, ky in ((x1, y1), (x2, y2)):
                draw_aa_circle(screen, (20, 20, 20), kx, ky, max(3, r * 0.62))
                draw_aa_circle(screen, (245, 245, 245), kx, ky, max(2, r * 0.45))
            return

        if self.brimstone:
            ang = math.atan2(self.vy, self.vx)
            pts = []
            for i in range(6):
                a = ang + i * (math.pi / 3.0) + self.spin * 0.4
                rad = r * (1.5 if i % 2 == 0 else 0.72)
                pts.append((self.x + math.cos(a) * rad, draw_y + math.sin(a) * rad))
            draw_aa_poly(screen, (20, 20, 20), pts)
            draw_aa_circle(screen, (238, 238, 238), self.x, draw_y, max(2, int(r * 0.65)))
            return

        lum = 252 if self.ambush else (246 if self.holy else (218 if self.brimstone else max(226, self.color[0])))
        disc = get_disc_sprite(r, lum, outline_lum=18, hi_lum=255)
        screen.blit(disc, (int(round(self.x - disc.get_width() * 0.5)), int(round(draw_y - disc.get_height() * 0.5))))
        if self.explosive or self.lobbed:
            draw_aa_circle(screen, (24, 24, 24), self.x, draw_y, max(2, int(r * 0.48)))
            spark_l = 255 if int(self.age * 0.5) % 2 == 0 else 190
            draw_aa_circle(screen, (spark_l, spark_l, spark_l), self.x + r * 0.2, draw_y - r * 0.2, max(1.5, r * 0.25))
        if self.homing:
            draw_aa_ring(screen, m(252), self.x, draw_y, r + 2, 1)


class EnemyProjectile:
    def __init__(
        self,
        x,
        y,
        vx,
        vy,
        radius=6.0,
        damage=1,
        color=None,
        max_range=540.0,
        homing=False,
        lobbed=False,
        target_x=None,
        target_y=None,
        blast_radius=52.0,
        total_frames=46.0,
    ):
        self.x = float(x)
        self.y = float(y)
        self.start_x = float(x)
        self.start_y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.radius = float(radius)
        self.damage = int(damage)
        self.color = gray(color) if color else PALETTE["enemy_shot"]
        self.max_range = float(max_range)
        self.homing = bool(homing)
        self.lobbed = bool(lobbed)
        self.target_x = float(x if target_x is None else max(PLAYABLE_LEFT + 18, min(PLAYABLE_RIGHT - 18, target_x)))
        self.target_y = float(y if target_y is None else max(PLAYABLE_TOP + 18, min(PLAYABLE_BOTTOM - 18, target_y)))
        self.blast_radius = float(blast_radius)
        self.total_frames = max(16.0, float(total_frames))
        self.elapsed = 0.0
        self.air_z = 0.0
        self.just_landed = False
        self.traveled = 0.0
        self.alive = True
        self.age = 0.0

    def update(self, room, dt=1.0, player_pos=None):
        if not self.alive:
            return
        self.age += dt
        if self.lobbed:
            self.elapsed += dt
            prog = min(1.0, self.elapsed / self.total_frames)
            self.x = self.start_x + (self.target_x - self.start_x) * prog
            self.y = self.start_y + (self.target_y - self.start_y) * prog
            self.air_z = math.sin(prog * math.pi) * 92.0
            if prog >= 1.0:
                self.air_z = 0.0
                self.just_landed = True
                self.alive = False
            return

        if self.homing and player_pos is not None:
            px, py = player_pos
            spd = math.hypot(self.vx, self.vy) or 4.0
            ang_cur = math.atan2(self.vy, self.vx)
            ang_tar = math.atan2(py - self.y, px - self.x)
            diff = (ang_tar - ang_cur + math.pi) % (2.0 * math.pi) - math.pi
            ang_new = ang_cur + max(-0.045 * dt, min(0.045 * dt, diff))
            self.vx = math.cos(ang_new) * spd
            self.vy = math.sin(ang_new) * spd

        nx = self.x + self.vx * dt
        ny = self.y + self.vy * dt
        self.traveled += math.hypot(nx - self.x, ny - self.y)
        self.x = nx
        self.y = ny

        if (
            self.x - self.radius < PLAYABLE_LEFT
            or self.x + self.radius > PLAYABLE_RIGHT
            or self.y - self.radius < PLAYABLE_TOP
            or self.y + self.radius > PLAYABLE_BOTTOM
            or self.traveled >= self.max_range
        ):
            self.alive = False
            return

        if room is not None:
            for obs in room.obstacles:
                if obs.alive and obs.blocks_tears and obs.rect.collidepoint(self.x, self.y):
                    self.alive = False
                    return

    def draw(self, screen):
        if not self.alive:
            return
        if self.lobbed:
            prog = min(1.0, self.elapsed / max(1.0, self.total_frames))
            ring_r = max(10, int(round(self.blast_radius * (1.0 - 0.35 * prog))))
            lum = int(145 + 105 * prog)
            draw_aa_ring(screen, (lum, lum, lum), self.target_x, self.target_y, ring_r, 1)
            pygame.draw.line(screen, (lum, lum, lum), (int(self.target_x - 7), int(self.target_y)), (int(self.target_x + 7), int(self.target_y)), 1)
            pygame.draw.line(screen, (lum, lum, lum), (int(self.target_x), int(self.target_y - 7)), (int(self.target_x), int(self.target_y + 7)), 1)
        r = max(4, int(round(self.radius)))
        sh_scale = max(0.5, 1.0 - self.air_z / 130.0)
        sh = get_shadow_surf(int(r * 2.0 * sh_scale), max(4, int(r * 0.85 * sh_scale)), 92)
        screen.blit(sh, (int(round(self.x - sh.get_width() * 0.5)), int(round(self.y + r + 4 - sh.get_height() * 0.5))))

        dy = self.y - self.air_z
        pulse = round((0.5 + 0.5 * math.sin(self.age * 0.35)) * 3.0) / 3.0
        gl = get_glow_surf(int(r * 2.3), 235, int(48 + 30 * pulse))
        screen.blit(gl, (int(round(self.x - gl.get_width() * 0.5)), int(round(dy - gl.get_height() * 0.5))))

        spr = _get_enemy_proj_sprite(r)
        screen.blit(spr, (int(round(self.x - spr.get_width() * 0.5)), int(round(dy - spr.get_height() * 0.5))))
