import os
import sys
import pygame
from i18n import tr, tr_boss, tr_boss_subtitle, tr_floor, tr_mode, tr_room
from items import draw_item_icon, tr_item_desc, tr_item_name
from settings import (
    GAME_SETTINGS,
    PALETTE,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    blit_text_fitted,
    clamp,
    draw_aa_circle,
    draw_aa_poly,
    ease_out_cubic,
    fit_text_surf,
    format_key_name,
    get_keybind,
    get_panel_surf,
    get_ui_scale,
    get_view_width,
    get_world_offset_x,
    is_phone_layout,
    render_4x_smooth,
    render_text_cached,
)


_HEART_SPRITE_CACHE = {}


def _get_heart_sprite(fill_type):
    spr = _HEART_SPRITE_CACHE.get(fill_type)
    if spr is not None:
        return spr
    lum = 244 if fill_type == "red" else (196 if fill_type == "soul" else (48 if fill_type == "black" else 42))
    rim = 200 if fill_type == "black" else 16

    def _draw(hi, hw, hh):
        s = 4.0
        ox = 1.0 * s
        oy = 1.0 * s
        draw_aa_circle(hi, (rim, rim, rim, 255), ox + 5 * s, oy + 5 * s, 5.2 * s)
        draw_aa_circle(hi, (rim, rim, rim, 255), ox + 12 * s, oy + 5 * s, 5.2 * s)
        draw_aa_poly(hi, (rim, rim, rim, 255), [(ox, oy + 6 * s), (ox + 17 * s, oy + 6 * s), (ox + 8.5 * s, oy + 16 * s)])
        if fill_type == "empty":
            draw_aa_circle(hi, (26, 26, 26, 255), ox + 5 * s, oy + 5 * s, 3.6 * s)
            draw_aa_circle(hi, (26, 26, 26, 255), ox + 12 * s, oy + 5 * s, 3.6 * s)
            draw_aa_poly(hi, (26, 26, 26, 255), [(ox + 2 * s, oy + 6 * s), (ox + 15 * s, oy + 6 * s), (ox + 8.5 * s, oy + 14 * s)])
            return
        draw_aa_circle(hi, (lum, lum, lum, 255), ox + 5 * s, oy + 5 * s, 4.0 * s)
        if fill_type != "half":
            draw_aa_circle(hi, (lum, lum, lum, 255), ox + 12 * s, oy + 5 * s, 4.0 * s)
            draw_aa_poly(hi, (lum, lum, lum, 255), [(ox + 1 * s, oy + 6 * s), (ox + 16 * s, oy + 6 * s), (ox + 8.5 * s, oy + 14.5 * s)])
        else:
            draw_aa_poly(hi, (lum, lum, lum, 255), [(ox + 1 * s, oy + 6 * s), (ox + 8.5 * s, oy + 6 * s), (ox + 8.5 * s, oy + 14.5 * s)])

    spr = render_4x_smooth(20, 20, _draw, blur_radius=0.15)
    _HEART_SPRITE_CACHE[fill_type] = spr
    return spr


def _load_ui_font(size: int, bold: bool = False):
    fname = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    base_res = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    local_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(local_dir)
    cwd = os.getcwd()
    candidates = [
        os.path.join(local_dir, "fonts", fname),
        os.path.join(root_dir, "fonts", fname),
        os.path.join(root_dir, "GAME", "fonts", fname),
        os.path.join(cwd, "fonts", fname),
        os.path.join(cwd, "GAME", "fonts", fname),
        os.path.join(base_res, "fonts", fname),
        os.path.join(base_res, fname),
        os.path.join(local_dir, fname),
    ]
    for path in candidates:
        if path and os.path.exists(path):
            try:
                f = pygame.font.Font(path, size)
                if f is not None:
                    return f
            except Exception:
                pass
    try:
        f = pygame.font.SysFont("dejavusans,liberationsans,arial,helvetica,sans-serif", size, bold=bold)
        if f is not None:
            return f
    except Exception:
        pass
    try:
        return pygame.font.Font(None, max(10, size))
    except Exception:
        return pygame.Surface((size, size))


class UI:
    def __init__(self):
        self.font_huge = _load_ui_font(36, bold=True)
        self.font_big = _load_ui_font(24, bold=True)
        self.font_med = _load_ui_font(16, bold=True)
        self.font_small = _load_ui_font(13, bold=False)
        self.font_tiny = _load_ui_font(11, bold=True)
        self.boss_hp_trail = 1.0
        self.dash_smooth = 1.0
        self.p2_dash_smooth = 1.0
        self.fuel_smooth = 1.0
        self.banner_text = ""
        self.banner_sub = ""
        self.banner_item = None
        self.banner_timer = 0.0
        self.banner_max_timer = 125.0
        self.banner_queue = []
        self._dim_overlay = None
        self._fade_surf = None
        self._minimap_key = None
        self._minimap_surf = None
        self._touch_active = False
        self._font_scale = 1.0
        self._last_active_relic_rect = None
        self._last_p2_active_relic_rect = None
        self._last_computer_hint_rect = None

    def sync_font_scale(self, phone=None):
        if phone is None:
            phone = self._phone_mode(self._touch_active)
        target = get_ui_scale(phone)
        if abs(target - self._font_scale) < 0.02:
            return
        self._font_scale = target
        s = target
        self.font_huge = _load_ui_font(max(24, int(round(36 * min(s, 1.20)))), bold=True)
        self.font_big = _load_ui_font(max(19, int(round(24 * min(s, 1.24)))), bold=True)
        self.font_med = _load_ui_font(max(15, int(round(16 * min(s, 1.35)))), bold=True)
        self.font_small = _load_ui_font(max(13, int(round(13 * min(s, 1.28)))), bold=False)
        self.font_tiny = _load_ui_font(max(11, int(round(11 * min(s, 1.28)))), bold=True)

    def get_active_relic_rect(self):
        return self._last_active_relic_rect

    def get_p2_active_relic_rect(self):
        return self._last_p2_active_relic_rect


    def _font_row_heights(self):
        try:
            tiny_h = max(14, int(self.font_tiny.get_height()))
        except Exception:
            tiny_h = 15
        try:
            med_h = max(18, int(self.font_med.get_height()))
        except Exception:
            med_h = 20
        try:
            small_h = max(15, int(self.font_small.get_height()))
        except Exception:
            small_h = 16
        return tiny_h, med_h, small_h

    def get_coop_hud_layout(self, vw=None, touch_active=None, extra_rows=0, p2_extra_rows=0, p2_dead=False, game_mode="classic", p2_present=True, has_banner_item=False):
        if vw is None:
            vw = get_view_width()
        ta = self._touch_active if touch_active is None else bool(touch_active)
        phone = is_phone_layout(ta)
        tiny_h, med_h, small_h = self._font_row_heights()
        p1_w = 298 if p2_present else (352 if phone else 326)
        hy_rel = max(24, 5 + tiny_h + 2)
        res_rel = hy_rel + (max(0, int(extra_rows)) + 1) * 18 + 3
        stat_rel = res_rel + med_h + 2
        dash_rel = stat_rel + tiny_h + 3
        abil_rel = dash_rel + tiny_h + 3
        fuel_rel = abil_rel + tiny_h + 3
        p1_h = (fuel_rel + tiny_h + 7) if game_mode == "fading_light" else (abil_rel + tiny_h + 7)
        p1_rect = pygame.Rect(14, 12, p1_w, p1_h)

        mm_x = vw - 196
        minimap_rect = pygame.Rect(mm_x, 12, 182, 170)

        p2_rect = None
        if p2_present:
            p2_w = 298
            p2_right_limit = (vw - 262) if ta else mm_x
            p2_x = max(p1_rect.right + 20, p2_right_limit - p2_w - 10)
            if p2_dead:
                p2_h = max(88, 27 + small_h + 2 + tiny_h * 2 + 12)
            else:
                hy2_rel = max(24, 7 + tiny_h + 2)
                p2_res_rel = hy2_rel + (max(0, int(p2_extra_rows)) + 1) * 18 + 3
                p2_stat_rel = p2_res_rel + med_h + 2
                p2_abil_rel = p2_stat_rel + tiny_h + 3
                p2_act_rel = p2_abil_rel + tiny_h + 3
                p2_h = p2_act_rel + max(28, tiny_h + 15) + 6
            p2_rect = pygame.Rect(p2_x, 12, p2_w, p2_h)

        desired_bw = 510 if has_banner_item else 460
        if p2_rect is not None:
            gap_left = p1_rect.right + 10
            gap_right = p2_rect.left - 10
            avail_w = max(240, gap_right - gap_left)
            if desired_bw <= avail_w and (vw // 2 - desired_bw // 2) >= gap_left and (vw // 2 + desired_bw // 2) <= gap_right:
                bw = desired_bw
                bx = vw // 2 - bw // 2
            else:
                bw = min(desired_bw, avail_w)
                bx = gap_left + max(0, (avail_w - bw) // 2)
        else:
            bw = desired_bw
            bx = vw // 2 - bw // 2

        return {
            "p1": p1_rect,
            "p2": p2_rect,
            "minimap": minimap_rect,
            "banner_x": bx,
            "banner_w": bw,
        }

    def get_active_banner_bottom(self):
        if self.banner_timer > 0 and self.banner_text:
            elapsed = self.banner_max_timer - self.banner_timer
            enter_t = ease_out_cubic(min(1.0, elapsed / 14.0))
            exit_t = ease_out_cubic(min(1.0, self.banner_timer / 16.0))
            slide = min(enter_t, exit_t)
            bh = 64
            by = int(-24 + slide * 48)
            return by + bh
        return 0

    def show_banner(self, title, subtitle="", duration=125.0, item=None):
        if self.banner_timer > 0 and self.banner_text:
            if len(self.banner_queue) < 6:
                self.banner_queue.append((title, subtitle, float(duration), item))
            return
        self.banner_text = title
        self.banner_sub = subtitle
        self.banner_item = item
        self.banner_timer = float(duration)
        self.banner_max_timer = max(1.0, float(duration))

    def update(self, dt=1.0):
        if self.banner_timer > 0:
            self.banner_timer = max(0.0, self.banner_timer - dt)
            if self.banner_timer <= 0 and self.banner_queue:
                nxt_title, nxt_sub, nxt_dur, nxt_item = self.banner_queue.pop(0)
                self.banner_text = nxt_title
                self.banner_sub = nxt_sub
                self.banner_item = nxt_item
                self.banner_timer = nxt_dur
                self.banner_max_timer = max(1.0, nxt_dur)

    def _get_dim_overlay(self):
        vw = get_view_width()
        if self._dim_overlay is None or self._dim_overlay.get_width() != vw:
            surf = pygame.Surface((vw, SCREEN_HEIGHT), pygame.SRCALPHA)
            surf.fill((4, 4, 4, 186))
            if pygame.display.get_init() and pygame.display.get_surface() is not None:
                surf = surf.convert_alpha()
            self._dim_overlay = surf
        return self._dim_overlay

    def draw_fade(self, screen, alpha):
        a = int(clamp(alpha, 0, 255))
        if a <= 1:
            return
        vw = get_view_width()
        if self._fade_surf is None or self._fade_surf.get_width() != vw:
            surf = pygame.Surface((vw, SCREEN_HEIGHT))
            surf.fill((4, 4, 4))
            if pygame.display.get_init() and pygame.display.get_surface() is not None:
                surf = surf.convert()
            self._fade_surf = surf
        self._fade_surf.set_alpha(a)
        screen.blit(self._fade_surf, (0, 0))

    def _draw_heart(self, screen, x, y, fill_type):
        spr = _get_heart_sprite(fill_type)
        screen.blit(spr, (int(x - 1), int(y - 1)))

    def _draw_minimap_symbol(self, screen, room_type, cx, cy, is_cur=False):
        col = (20, 20, 20) if is_cur else (238, 238, 238)
        bg = (234, 234, 234) if is_cur else (18, 18, 18)
        if room_type == "boss":
            draw_aa_circle(screen, col, cx, cy, 4)
            draw_aa_circle(screen, bg, cx - 1.5, cy - 1, 1)
            draw_aa_circle(screen, bg, cx + 1.5, cy - 1, 1)
        elif room_type == "treasure":
            draw_aa_poly(screen, col, [(cx, cy - 5), (cx + 4, cy), (cx, cy + 5), (cx - 4, cy)])
        elif room_type == "shop":
            draw_aa_circle(screen, col, cx, cy, 4)
            draw_aa_circle(screen, bg, cx, cy, 2)
        elif room_type in ("curse", "devil"):
            pygame.draw.line(screen, col, (cx - 3, cy - 3), (cx + 3, cy + 3), 2)
            pygame.draw.line(screen, col, (cx + 3, cy - 3), (cx - 3, cy + 3), 2)
        elif room_type == "sacrifice":
            pygame.draw.line(screen, col, (cx, cy - 4), (cx, cy + 4), 2)
            pygame.draw.line(screen, col, (cx - 3, cy - 1), (cx + 3, cy - 1), 2)
        elif room_type == "secret":
            q = render_text_cached(self.font_tiny, "?", col)
            screen.blit(q, (cx - q.get_width() // 2, cy - q.get_height() // 2))
        elif room_type in ("library", "dice", "arcade", "miniboss"):
            pygame.draw.rect(screen, col, (cx - 3, cy - 3, 6, 6), 1)

    def _phone_mode(self, touch_active=None):
        ta = self._touch_active if touch_active is None else bool(touch_active)
        return is_phone_layout(ta)

    def get_inventory_slot_rects(self, touch_active=None):
        vw = get_view_width()
        if self._phone_mode(touch_active):
            br_x = vw // 2 - 224
            slot_rects = [pygame.Rect(br_x + 17 + i * 46, SCREEN_HEIGHT - 88, 42, 42) for i in range(9)]
            page_rect = pygame.Rect(br_x + 332, SCREEN_HEIGHT - 114, 102, 20)
            return slot_rects, page_rect
        br_x = vw - 408
        slot_rects = [pygame.Rect(br_x + 10 + i * 42, SCREEN_HEIGHT - 83, 37, 37) for i in range(9)]
        page_rect = pygame.Rect(br_x + 308, SCREEN_HEIGHT - 107, 76, 18)
        return slot_rects, page_rect

    def get_inventory_use_rect(self):
        return getattr(self, "_last_inv_use_rect", None)

    def draw_hud(
        self,
        screen,
        player,
        dungeon_rooms,
        current_coord,
        current_room,
        floor_level,
        fps_val=0,
        show_fps=False,
        game_mode="classic",
        wave_num=0,
        lantern_fuel=1.0,
        editor_active=False,
        timescale=1.0,
        touch_active=False,
        p2=None,
        primary_tag="P1",
        coop_tag="P2",
        coop_mode_label="CO-OP",
        computer_hint=None,
    ):
        self._touch_active = bool(touch_active)
        phone = self._phone_mode(touch_active)
        self.sync_font_scale(phone)
        lang = GAME_SETTINGS.get("language", "ru")
        vw = get_view_width()
        tiny_h, med_h, small_h = self._font_row_heights()

        containers = max(0, player.max_hp // 2)
        soul_slots = (player.soul_hp + 1) // 2
        black_slots = (player.black_hp + 1) // 2
        per_row = 12 if p2 is not None else 13
        total_heart_slots = max(1, containers + soul_slots + black_slots)
        heart_rows = max(1, (total_heart_slots + per_row - 1) // per_row)
        extra_rows = heart_rows - 1

        p2_extra_rows = 0
        p2_dead = False
        if p2 is not None:
            p2_dead = bool(p2.is_dead())
            if not p2_dead:
                p2_slots = max(1, max(0, p2.max_hp // 2) + ((p2.soul_hp + 1) // 2) + ((p2.black_hp + 1) // 2))
                p2_rows = max(1, (p2_slots + 11) // 12)
                p2_extra_rows = p2_rows - 1

        hud_layout = self.get_coop_hud_layout(
            vw=vw,
            touch_active=touch_active,
            extra_rows=extra_rows,
            p2_extra_rows=p2_extra_rows,
            p2_dead=p2_dead,
            game_mode=game_mode,
            p2_present=(p2 is not None),
            has_banner_item=(self.banner_item is not None),
        )
        p1_rc = hud_layout["p1"]
        tl_w, tl_h = p1_rc.w, p1_rc.h
        tl_panel = get_panel_surf(tl_w, tl_h, fill_lum=12, fill_alpha=206, border_lum=90, radius=10)
        screen.blit(tl_panel, p1_rc.topleft)

        hdr_x = 26
        if p2 is not None:
            pygame.draw.rect(screen, (238, 238, 238), (26, 18, 24, 14), border_radius=4)
            p1_tag = fit_text_surf(self.font_tiny, str(primary_tag)[:3], (12, 12, 12), 22, max_h=13)
            screen.blit(p1_tag, (26 + 12 - p1_tag.get_width() // 2, 18))
            hdr_x = 56
        shield_w = 0
        shield_lbl = None
        if player.holy_mantle and not player.mantle_broken_room:
            shield_lbl = fit_text_surf(self.font_tiny, "[SHIELD]", PALETTE["text_main"], 84, max_h=tiny_h)
            shield_w = shield_lbl.get_width() + 8
        life_max_w = max(72, p1_rc.right - hdr_x - 12 - shield_w)
        life_lbl = fit_text_surf(self.font_tiny, f"- {tr('hud_life')} -", PALETTE["text_muted"], life_max_w, max_h=tiny_h)
        screen.blit(life_lbl, (hdr_x, 17))
        if shield_lbl is not None:
            screen.blit(shield_lbl, (p1_rc.right - shield_lbl.get_width() - 12, 17))

        hy_rel = max(24, 5 + tiny_h + 2)
        hx, hy = 26, p1_rc.y + hy_rel
        hx_limit = p1_rc.right - 26
        heart_seq = []
        for i in range(containers):
            slot_hp = player.hp - i * 2
            ft = "red" if slot_hp >= 2 else ("half" if slot_hp == 1 else "empty")
            heart_seq.append(ft)
        for _ in range(soul_slots):
            heart_seq.append("soul")
        for _ in range(black_slots):
            heart_seq.append("black")
        for ft in heart_seq:
            self._draw_heart(screen, hx, hy, ft)
            hx += 21
            if hx > hx_limit:
                hx = 26
                hy += 18

        res_y = p1_rc.y + hy_rel + (extra_rows + 1) * 18 + 3
        stat_y = res_y + med_h + 2
        dash_y = stat_y + tiny_h + 3
        abil_y = dash_y + tiny_h + 3
        fuel_y = abil_y + tiny_h + 3
        bar_right = p1_rc.right - 14

        res_txt = fit_text_surf(self.font_med, f"¢ {player.coins:02d}   B {player.bombs:02d}   K {player.keys:02d}", PALETTE["text_main"], p1_rc.w - 30, max_h=med_h)
        screen.blit(res_txt, (26, res_y))

        stat_txt = fit_text_surf(
            self.font_tiny,
            f"DMG {player.get_effective_damage():.1f} · SPD {player.get_effective_speed():.1f} · LCK {player.luck} · KILLS {player.kills}",
            PALETTE["text_muted"],
            p1_rc.w - 30,
            max_h=tiny_h,
        )
        screen.blit(stat_txt, (26, stat_y))

        dash_ratio = 1.0 if player.dash_cd <= 0 else max(0.0, 1.0 - player.dash_cd / max(1.0, player.dash_max_cd))
        self.dash_smooth += (dash_ratio - self.dash_smooth) * 0.24
        dash_key = format_key_name(get_keybind("dash"))[:6]
        dash_lbl = fit_text_surf(self.font_tiny, f"{tr('hud_dash')} [{dash_key}]", PALETTE["text_dim"], 130, max_h=tiny_h)
        screen.blit(dash_lbl, (26, dash_y))
        dash_bar_x = max(124, 26 + dash_lbl.get_width() + 8)
        dash_bar_w = max(72, bar_right - dash_bar_x)
        dash_bar_y = dash_y + max(3, (tiny_h - 6) // 2)
        pygame.draw.rect(screen, (32, 32, 32), (dash_bar_x, dash_bar_y, dash_bar_w, 6), border_radius=3)
        pygame.draw.rect(screen, (238, 238, 238) if self.dash_smooth >= 0.98 else (142, 142, 142), (dash_bar_x, dash_bar_y, int(dash_bar_w * self.dash_smooth), 6), border_radius=3)
        pygame.draw.rect(screen, (72, 72, 72), (dash_bar_x, dash_bar_y, dash_bar_w, 6), 1, border_radius=3)

        jmp_ratio = 1.0 if getattr(player, "jump_cd", 0.0) <= 0 else max(0.0, 1.0 - player.jump_cd / max(1.0, getattr(player, "jump_max_cd", 120.0)))
        jmp_key = format_key_name(get_keybind("jump"))[:4]
        jmp_lbl = fit_text_surf(self.font_tiny, f"[{jmp_key}]", PALETTE["text_dim"], 52, max_h=tiny_h)

        inv_t = getattr(player, "invis_timer", 0.0)
        if inv_t > 0:
            inv_ratio = min(1.0, inv_t / 135.0)
            inv_col = (248, 248, 248)
        else:
            inv_ratio = 1.0 if getattr(player, "invis_cd", 0.0) <= 0 else max(0.0, 1.0 - player.invis_cd / max(1.0, getattr(player, "invis_max_cd", 360.0)))
            inv_col = (224, 224, 224) if inv_ratio >= 0.98 else (118, 118, 118)
        inv_key = format_key_name(get_keybind("stealth"))[:4]
        inv_lbl = fit_text_surf(self.font_tiny, f"[{inv_key}]", (248, 248, 248) if inv_t > 0 else PALETTE["text_dim"], 52, max_h=tiny_h)

        melee_cd = getattr(player, "melee_cd", 0.0)
        melee_max = max(1.0, getattr(player, "melee_max_cd", 22.0))
        melee_ratio = 1.0 if melee_cd <= 0 else max(0.0, 1.0 - melee_cd / melee_max)
        combo_step = int(getattr(player, "melee_combo_step", 0)) if getattr(player, "melee_combo_timer", 0.0) > 0 else 0
        finisher_ready = combo_step == 2 and melee_ratio >= 0.98
        atk_key = format_key_name(get_keybind("melee"))[:4]
        atk_lbl = fit_text_surf(
            self.font_tiny,
            f"[{atk_key}]",
            (255, 255, 255) if finisher_ready else ((240, 240, 240) if melee_ratio >= 0.98 else PALETTE["text_dim"]),
            52,
            max_h=tiny_h,
        )

        pip_total_w = 24
        fixed_abil_w = jmp_lbl.get_width() + inv_lbl.get_width() + atk_lbl.get_width() + pip_total_w + 28
        rem_bars = max(72, (bar_right - 26) - fixed_abil_w)
        bw1 = max(24, int(rem_bars * 0.34))
        bw2 = max(24, int(rem_bars * 0.34))
        bw3 = max(24, rem_bars - bw1 - bw2)
        abil_bar_y = abil_y + max(3, (tiny_h - 6) // 2)

        cx_ab = 26
        screen.blit(jmp_lbl, (cx_ab, abil_y))
        bx1 = cx_ab + jmp_lbl.get_width() + 4
        pygame.draw.rect(screen, (32, 32, 32), (bx1, abil_bar_y, bw1, 6), border_radius=3)
        pygame.draw.rect(screen, (230, 230, 230) if jmp_ratio >= 0.98 else (130, 130, 130), (bx1, abil_bar_y, int(bw1 * jmp_ratio), 6), border_radius=3)
        pygame.draw.rect(screen, (70, 70, 70), (bx1, abil_bar_y, bw1, 6), 1, border_radius=3)

        cx_ab = bx1 + bw1 + 6
        screen.blit(inv_lbl, (cx_ab, abil_y))
        bx2 = cx_ab + inv_lbl.get_width() + 4
        pygame.draw.rect(screen, (32, 32, 32), (bx2, abil_bar_y, bw2, 6), border_radius=3)
        pygame.draw.rect(screen, inv_col, (bx2, abil_bar_y, int(bw2 * inv_ratio), 6), border_radius=3)
        pygame.draw.rect(screen, (70, 70, 70), (bx2, abil_bar_y, bw2, 6), 1, border_radius=3)

        cx_ab = bx2 + bw2 + 6
        screen.blit(atk_lbl, (cx_ab, abil_y))
        atk_bar_x = cx_ab + atk_lbl.get_width() + 4
        pygame.draw.rect(screen, (32, 32, 32), (atk_bar_x, abil_bar_y, bw3, 6), border_radius=3)
        bar_col = (255, 255, 255) if finisher_ready else ((236, 236, 236) if melee_ratio >= 0.98 else (128, 128, 128))
        pygame.draw.rect(screen, bar_col, (atk_bar_x, abil_bar_y, int(bw3 * melee_ratio), 6), border_radius=3)
        pygame.draw.rect(screen, (96, 96, 96) if finisher_ready else (70, 70, 70), (atk_bar_x, abil_bar_y, bw3, 6), 1, border_radius=3)
        pip_x0 = atk_bar_x + bw3 + 5
        for pi in range(3):
            lit = pi < combo_step or (finisher_ready and pi == 2)
            p_col = (255, 255, 255) if lit else (46, 46, 46)
            pygame.draw.rect(screen, p_col, (pip_x0 + pi * 7, abil_bar_y, 5, 6), border_radius=2)
            if finisher_ready and pi == 2:
                pygame.draw.rect(screen, (255, 255, 255), (pip_x0 + pi * 7 - 1, abil_bar_y - 1, 7, 8), 1, border_radius=2)

        if game_mode == "fading_light":
            fuel_r = clamp(lantern_fuel / max(1.0, getattr(player, "lantern_bonus", 1.0)), 0.0, 1.0)
            self.fuel_smooth += (fuel_r - self.fuel_smooth) * 0.2
            fuel_lbl = fit_text_surf(self.font_tiny, tr("fuel_label")[:12], PALETTE["text_main"] if fuel_r > 0.25 else (238, 238, 238), 110, max_h=tiny_h)
            screen.blit(fuel_lbl, (26, fuel_y))
            fuel_bar_x = max(122, 26 + fuel_lbl.get_width() + 8)
            fuel_bar_w = max(64, bar_right - fuel_bar_x)
            fuel_bar_y = fuel_y + max(3, (tiny_h - 6) // 2)
            pygame.draw.rect(screen, (28, 28, 28), (fuel_bar_x, fuel_bar_y, fuel_bar_w, 6), border_radius=3)
            fill_l = 244 if fuel_r > 0.35 else (196 if int(self.banner_timer + pygame.time.get_ticks() * 0.02) % 2 == 0 else 112)
            pygame.draw.rect(screen, (fill_l, fill_l, fill_l), (fuel_bar_x, fuel_bar_y, int(fuel_bar_w * self.fuel_smooth), 6), border_radius=3)

        mm_rc = hud_layout["minimap"]
        mm_panel = get_panel_surf(mm_rc.w, mm_rc.h, fill_lum=12, fill_alpha=206, border_lum=90, radius=10)
        mm_x = mm_rc.x
        mm_y = mm_rc.y
        screen.blit(mm_panel, (mm_x, mm_y))
        room_lbl = fit_text_surf(self.font_tiny, tr_room(current_room.room_type), PALETTE["text_main"], 166, max_h=14)
        screen.blit(room_lbl, (mm_x + 91 - room_lbl.get_width() // 2, mm_y + 6))
        mode_lbl = fit_text_surf(self.font_tiny, tr_mode(game_mode), PALETTE["text_dim"], 166, max_h=13)
        screen.blit(mode_lbl, (mm_x + 91 - mode_lbl.get_width() // 2, mm_y + 21))
        if game_mode == "endless_abyss":
            w_title = fit_text_surf(self.font_big, f"{tr('wave_label')} {max(1, wave_num)}", PALETTE["text_main"], 164, max_h=30)
            screen.blit(w_title, (mm_x + 91 - w_title.get_width() // 2, mm_y + 66))
            alive_cnt = len([e for e in current_room.enemies if e.alive]) + len([b for b in current_room.bosses if b.alive])
            c_lbl = fit_text_surf(self.font_tiny, f"ENEMIES: {alive_cnt}", PALETTE["text_muted"], 164, max_h=14)
            screen.blit(c_lbl, (mm_x + 91 - c_lbl.get_width() // 2, mm_y + 104))
        else:
            cx_coord, cy_coord = current_coord
            cell_w, cell_h = 26, 20
            grid_x0 = mm_x + 20
            grid_y0 = mm_y + 37
            reveal_all = bool(getattr(player, "compass_reveal", False))
            visited_sig = sum(1 for rm in dungeon_rooms.values() if rm.visited)
            mm_key = (id(dungeon_rooms), len(dungeon_rooms), current_coord, current_room.room_type, visited_sig, reveal_all)
            if mm_key != self._minimap_key or self._minimap_surf is None:
                mm_grid = pygame.Surface((146, 118), pygame.SRCALPHA)
                vis_coords = set()
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        coord = (cx_coord + dx, cy_coord + dy)
                        if coord == current_coord and coord not in dungeon_rooms:
                            vis_coords.add(coord)
                            continue
                        rm = dungeon_rooms.get(coord)
                        if rm is None:
                            continue
                        if rm.room_type == "secret" and not rm.visited and not reveal_all:
                            continue
                        if rm.visited or reveal_all:
                            vis_coords.add(coord)
                            continue
                        cx0, cy0 = coord
                        if (
                            ((cx0 + 1, cy0) in dungeon_rooms and dungeon_rooms[(cx0 + 1, cy0)].visited)
                            or ((cx0 - 1, cy0) in dungeon_rooms and dungeon_rooms[(cx0 - 1, cy0)].visited)
                            or ((cx0, cy0 + 1) in dungeon_rooms and dungeon_rooms[(cx0, cy0 + 1)].visited)
                            or ((cx0, cy0 - 1) in dungeon_rooms and dungeon_rooms[(cx0, cy0 - 1)].visited)
                        ):
                            vis_coords.add(coord)

                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        coord = (cx_coord + dx, cy_coord + dy)
                        if coord not in vis_coords or coord not in dungeon_rooms:
                            continue
                        rx = (dx + 2) * (cell_w + 3)
                        ry = (dy + 2) * (cell_h + 3)
                        if dx < 2:
                            rc = (cx_coord + dx + 1, cy_coord + dy)
                            if rc in dungeon_rooms and rc in vis_coords:
                                pygame.draw.line(mm_grid, (96, 96, 96), (rx + cell_w, ry + cell_h // 2), (rx + cell_w + 3, ry + cell_h // 2), 2)
                        if dy < 2:
                            bc = (cx_coord + dx, cy_coord + dy + 1)
                            if bc in dungeon_rooms and bc in vis_coords:
                                pygame.draw.line(mm_grid, (96, 96, 96), (rx + cell_w // 2, ry + cell_h), (rx + cell_w // 2, ry + cell_h + 3), 2)

                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        coord = (cx_coord + dx, cy_coord + dy)
                        if coord not in vis_coords:
                            continue
                        rm = dungeon_rooms.get(coord)
                        rx = (dx + 2) * (cell_w + 3)
                        ry = (dy + 2) * (cell_h + 3)
                        is_cur = coord == current_coord
                        fill_c = (234, 234, 234) if is_cur else ((84, 84, 84) if (rm and rm.visited) else (30, 30, 30))
                        border_c = (252, 252, 252) if is_cur else ((154, 154, 154) if (rm and rm.visited) else (64, 64, 64))
                        pygame.draw.rect(mm_grid, fill_c, (rx, ry, cell_w, cell_h), border_radius=4)
                        pygame.draw.rect(mm_grid, border_c, (rx, ry, cell_w, cell_h), 1, border_radius=4)
                        rtype = current_room.room_type if is_cur else rm.room_type
                        self._draw_minimap_symbol(mm_grid, rtype, rx + cell_w // 2, ry + cell_h // 2, is_cur=is_cur)

                if pygame.display.get_init() and pygame.display.get_surface() is not None:
                    mm_grid = mm_grid.convert_alpha()
                self._minimap_key = mm_key
                self._minimap_surf = mm_grid
            screen.blit(self._minimap_surf, (grid_x0, grid_y0))

        if show_fps:
            fps_lbl = fit_text_surf(self.font_tiny, f"{int(fps_val)} FPS", PALETTE["text_muted"], 96, max_h=13)
            screen.blit(fps_lbl, (mm_x + 12, mm_y + mm_rc.h - 17))

        has_mod = getattr(current_room, "floor_modifier", None) is not None and game_mode != "endless_abyss"
        bl_w = 362
        bl_h = 112 if has_mod else 96
        bl_panel = get_panel_surf(bl_w, bl_h, fill_lum=12, fill_alpha=206, border_lum=90, radius=10)
        bl_x, bl_y = 14, SCREEN_HEIGHT - bl_h - 10
        screen.blit(bl_panel, (bl_x, bl_y))

        sub_tag = f"{tr('wave_label')} {max(1, wave_num)}" if game_mode == "endless_abyss" else f"{tr('floor_label')} {floor_level}"
        hero_name = player.hero.get("name_en", player.hero["name"]) if lang == "en" else player.hero["name"]
        hero_txt = fit_text_surf(self.font_med, f"{hero_name.upper()}  ·  {sub_tag}", PALETTE["text_main"], bl_w - 24, max_h=22)
        screen.blit(hero_txt, (bl_x + 12, bl_y + 7))
        fl_sub = fit_text_surf(self.font_tiny, tr_mode(game_mode) if game_mode != "classic" else tr_floor(floor_level), PALETTE["text_muted"], bl_w - 24, max_h=15)
        screen.blit(fl_sub, (bl_x + 12, bl_y + 30))

        item_y = bl_y + 48
        if has_mod:
            mod = current_room.floor_modifier
            mod_name = mod.get(lang, mod.get("ru", ""))
            mod_lbl = fit_text_surf(self.font_tiny, f"[{mod_name.upper()}]", (226, 226, 226), bl_w - 24, max_h=14)
            screen.blit(mod_lbl, (bl_x + 12, bl_y + 46))
            item_y = bl_y + 64

        if player.active_item is not None:
            self._last_active_relic_rect = pygame.Rect(bl_x + 8, item_y - 3, bl_w - 16, 38)
            box = pygame.Rect(bl_x + 12, item_y, 32, 32)
            ready = player.is_active_ready() if hasattr(player, "is_active_ready") else (player.max_charge <= 0 or player.active_charge >= player.max_charge)
            pygame.draw.rect(screen, (42, 42, 42) if ready else (26, 26, 26), box, border_radius=6)
            pygame.draw.rect(screen, (250, 250, 250) if ready else (148, 148, 148), box, 2 if ready else 1, border_radius=6)
            draw_item_icon(screen, player.active_item, box.centerx, box.centery, 24)
            act_name = tr_item_name(player.active_item)
            relic_key = format_key_name(get_keybind("relic"))[:5]
            act_count_s = f" ({player.active_slot + 1}/{len(player.active_items)})" if len(player.active_items) > 1 else ""
            act_lbl = fit_text_surf(self.font_tiny, f"{act_name}{act_count_s} [{relic_key}]", (252, 252, 252) if ready else PALETTE["text_main"], bl_w - 64, max_h=15)
            screen.blit(act_lbl, (bl_x + 50, item_y))
            mc = player.max_charge
            if mc <= 0:
                pygame.draw.rect(screen, (240, 240, 240), (bl_x + 50, item_y + 19, 84, 7), border_radius=3)
                inf_s = fit_text_surf(self.font_tiny, "∞", (246, 246, 246), 24, max_h=14)
                screen.blit(inf_s, (bl_x + 140, item_y + 15))
            elif mc <= 6:
                for p_i in range(mc):
                    px = bl_x + 50 + p_i * 14
                    py = item_y + 19
                    lit = p_i < player.active_charge
                    pygame.draw.rect(screen, (240, 240, 240) if lit else (42, 42, 42), (px, py, 11, 7), border_radius=2)
            else:
                bar_w = 132
                pygame.draw.rect(screen, (36, 36, 36), (bl_x + 50, item_y + 19, bar_w, 7), border_radius=3)
                fill_w = int(bar_w * clamp(player.active_charge / float(mc), 0.0, 1.0))
                pygame.draw.rect(screen, (240, 240, 240), (bl_x + 50, item_y + 19, fill_w, 7), border_radius=3)
                chg_s = fit_text_surf(self.font_tiny, f"{player.active_charge}/{mc}", PALETTE["text_muted"], 64, max_h=14)
                screen.blit(chg_s, (bl_x + 50 + bar_w + 8, item_y + 15))
        else:
            self._last_active_relic_rect = None
            no_act = "NO ACTIVE RELIC" if lang == "en" else "НЕТ АКТИВНОЙ РЕЛИКВИИ"
            screen.blit(fit_text_surf(self.font_tiny, no_act, PALETTE["text_dim"], bl_w - 24, max_h=16), (bl_x + 12, item_y + 8))

        tags = []
        if editor_active:
            tags.append("[EDITOR F2]")
        if getattr(player, "noclip", False):
            tags.append("[NOCLIP]")
        if abs(timescale - 1.0) > 0.05:
            tags.append(f"[TIME x{timescale:.1f}]")
        for eid, rem in list(getattr(player, "active_effects", {}).items())[:4]:
            if rem <= 0:
                continue
            sec_s = "∞" if rem > 900000 else f"{int(rem // 60)}s"
            tags.append(f"{eid.upper()} {sec_s}")
        if tags:
            tag_y = bl_y - 22
            tag_x = bl_x
            for tg in tags[:5]:
                ts = fit_text_surf(self.font_tiny, tg, (244, 244, 244), 130, max_h=14)
                pw = ts.get_width() + 12
                pygame.draw.rect(screen, (22, 22, 22), (tag_x, tag_y, pw, 17), border_radius=4)
                pygame.draw.rect(screen, (118, 118, 118), (tag_x, tag_y, pw, 17), 1, border_radius=4)
                screen.blit(ts, (tag_x + 6, tag_y + (17 - ts.get_height()) // 2))
                tag_x += pw + 6

        if phone:
            br_w, br_h = 448, 114
            br_x, br_y = vw // 2 - br_w // 2, SCREEN_HEIGHT - 120
            br_hdr_x = br_x + 17
            desc_x = br_x + 17
            desc_y = SCREEN_HEIGHT - 38
        else:
            br_w, br_h = 394, 104
            br_x, br_y = vw - 408, SCREEN_HEIGHT - 112
            br_hdr_x = br_x + 10
            desc_x = br_x + 10
            desc_y = SCREEN_HEIGHT - 38
        br_panel = get_panel_surf(br_w, br_h, fill_lum=12, fill_alpha=206, border_lum=90, radius=10)
        screen.blit(br_panel, (br_x, br_y))
        slot_rects, page_rect = self.get_inventory_slot_rects(touch_active)
        entries, start_idx = player.get_inventory_page_entries()
        page_cnt = player.get_inventory_page_count()

        sel_entry = player.get_selected_inventory_entry() if hasattr(player, "get_selected_inventory_entry") else None
        sel_item = sel_entry[2] if sel_entry is not None else None
        sel_kind = sel_entry[0] if sel_entry is not None else None
        sel_chg = sel_entry[3] if sel_entry is not None else 0
        sel_mchg = sel_entry[4] if sel_entry is not None else 0

        use_w = 96 if phone else 86
        if sel_kind == "active":
            use_rect = pygame.Rect(page_rect.left - use_w - 6, page_rect.y, use_w, page_rect.h)
            self._last_inv_use_rect = use_rect
            sel_ready = (sel_mchg <= 0) or (sel_chg >= sel_mchg)
            pygame.draw.rect(screen, (238, 238, 238) if sel_ready else (34, 34, 34), use_rect, border_radius=4)
            pygame.draw.rect(screen, (255, 255, 255) if sel_ready else (112, 112, 112), use_rect, 1, border_radius=4)
            use_col = (14, 14, 14) if sel_ready else PALETTE["text_muted"]
            blit_text_fitted(screen, use_rect, self.font_tiny, tr("inv_use_btn"), use_col, pad_x=4, pad_y=1)
            hdr_max_w = max(84, use_rect.left - br_hdr_x - 6)
        else:
            self._last_inv_use_rect = None
            hdr_max_w = max(110, page_rect.left - br_hdr_x - 8)

        hdr_lbl = fit_text_surf(self.font_tiny, f"{tr('hud_artifacts')} [1–9]", PALETTE["text_muted"], hdr_max_w, max_h=16)
        screen.blit(hdr_lbl, (br_hdr_x, br_y + (7 if phone else 6)))
        pygame.draw.rect(screen, (28, 28, 28), page_rect, border_radius=4)
        pygame.draw.rect(screen, (96, 96, 96), page_rect, 1, border_radius=4)
        blit_text_fitted(screen, page_rect, self.font_tiny, f"PG {player.inventory_page + 1}/{page_cnt} [0]", PALETTE["text_main"], pad_x=4, pad_y=1)

        for i, rc in enumerate(slot_rects):
            abs_idx = start_idx + i
            entry = entries[i] if i < len(entries) else None
            is_sel = entry is not None and abs_idx == player.selected_inv_idx
            is_equipped_act = entry is not None and entry[0] == "active" and entry[1] == player.active_slot
            fill_c = (44, 44, 44) if is_sel else ((28, 28, 28) if is_equipped_act else (20, 20, 20))
            border_c = (248, 248, 248) if is_sel else ((196, 196, 196) if is_equipped_act else (62, 62, 62))
            pygame.draw.rect(screen, fill_c, rc, border_radius=5)
            pygame.draw.rect(screen, border_c, rc, 2 if is_sel else 1, border_radius=5)
            num_s = fit_text_surf(self.font_tiny, str(i + 1), (226, 226, 226) if entry else (86, 86, 86), 14, max_h=12)
            screen.blit(num_s, (rc.x + 2, rc.y + 1))
            if entry is not None:
                kind, _, it, chg, mchg = entry
                draw_item_icon(screen, it, rc.centerx, rc.centery + 1, 26 if phone else 22)
                if kind == "active":
                    atag = fit_text_surf(self.font_tiny, "A", (250, 250, 250), 12, max_h=12)
                    screen.blit(atag, (rc.right - atag.get_width() - 2, rc.y + 1))
                    if mchg <= 0:
                        pygame.draw.rect(screen, (242, 242, 242), (rc.x + 3, rc.bottom - 4, rc.w - 6, 2))
                    else:
                        cw = int((rc.w - 6) * clamp(chg / float(mchg), 0.0, 1.0))
                        pygame.draw.rect(screen, (36, 36, 36), (rc.x + 3, rc.bottom - 4, rc.w - 6, 2))
                        pygame.draw.rect(screen, (242, 242, 242), (rc.x + 3, rc.bottom - 4, cw, 2))
                else:
                    ptag = fit_text_surf(self.font_tiny, "P", (132, 132, 132), 12, max_h=12)
                    screen.blit(ptag, (rc.right - ptag.get_width() - 2, rc.y + 1))

        if sel_item is not None:
            s_name = tr_item_name(sel_item)
            s_desc = tr_item_desc(sel_item)
            if sel_kind == "active":
                if sel_mchg <= 0 or sel_chg >= sel_mchg:
                    badge = f"[{tr('inv_active_ready')}]"
                else:
                    badge = f"[{tr('inv_active_charge')} {sel_chg}/{sel_mchg}]"
            else:
                badge = f"[{tr('inv_passive_tag')}]"
            line_s = f"{badge} {s_name}: {s_desc}"
            desc_surf = fit_text_surf(self.font_tiny, line_s, PALETTE["text_main"], br_w - 28, max_h=17 if phone else 16)
            screen.blit(desc_surf, (desc_x, desc_y))
        else:
            empty_s = "Empty inventory" if lang == "en" else "Инвентарь пуст"
            screen.blit(fit_text_surf(self.font_tiny, empty_s, PALETTE["text_dim"], br_w - 28, max_h=17 if phone else 16), (desc_x, desc_y))

        if current_room.victory_portal_rect is not None and current_room.trapdoor_rect is not None:
            world_ox = get_world_offset_x()
            t_txt = "ГЛУБЖЕ В БЕЗДНУ" if lang == "ru" else "DEEPER ABYSS"
            v_txt = "ВРАТА РАССВЕТА" if lang == "ru" else "DAWN PORTAL"
            t_lbl = fit_text_surf(self.font_tiny, t_txt, (226, 226, 226), 140, max_h=16)
            v_lbl = fit_text_surf(self.font_tiny, v_txt, (246, 246, 246), 140, max_h=16)
            screen.blit(t_lbl, (world_ox + current_room.trapdoor_rect.centerx - t_lbl.get_width() // 2, current_room.trapdoor_rect.top - 20))
            screen.blit(v_lbl, (world_ox + current_room.victory_portal_rect.centerx - v_lbl.get_width() // 2, current_room.victory_portal_rect.top - 22))

        alive_bosses = [b for b in current_room.bosses if getattr(b, "alive", True)]
        if alive_bosses:
            total_hp = sum(max(0.0, b.hp) for b in alive_bosses)
            total_max = max(1.0, sum(b.max_hp for b in alive_bosses))
            ratio = max(0.0, min(1.0, total_hp / total_max))
            self.boss_hp_trail += (ratio - self.boss_hp_trail) * 0.12

            bw = 440
            bx = vw // 2 - bw // 2
            by = SCREEN_HEIGHT - 156 if phone else SCREEN_HEIGHT - 54
            boss_panel = get_panel_surf(bw + 24, 44, fill_lum=10, fill_alpha=212, border_lum=102, radius=8)
            screen.blit(boss_panel, (bx - 12, by - 14))

            b_name = tr_boss(alive_bosses[0].boss_key)
            b_lbl = fit_text_surf(self.font_med, f"{b_name}  —  {tr_boss_subtitle(alive_bosses[0].boss_key)}", PALETTE["text_main"], bw + 8, max_h=19)
            screen.blit(b_lbl, (vw // 2 - b_lbl.get_width() // 2, by - 10))

            pygame.draw.rect(screen, (28, 28, 28), (bx, by + 12, bw, 11), border_radius=5)
            pygame.draw.rect(screen, (112, 112, 112), (bx, by + 12, int(bw * self.boss_hp_trail), 11), border_radius=5)
            pygame.draw.rect(screen, (242, 242, 242), (bx, by + 12, int(bw * ratio), 11), border_radius=5)
            pygame.draw.rect(screen, (186, 186, 186), (bx, by + 12, bw, 11), 1, border_radius=5)
        else:
            self.boss_hp_trail = 1.0

        if self.banner_timer > 0 and self.banner_text:
            elapsed = self.banner_max_timer - self.banner_timer
            enter_t = ease_out_cubic(min(1.0, elapsed / 14.0))
            exit_t = ease_out_cubic(min(1.0, self.banner_timer / 16.0))
            slide = min(enter_t, exit_t)
            bw = hud_layout["banner_w"]
            bh = 64
            bx = hud_layout["banner_x"]
            by = int(-24 + slide * 48)
            bp = get_panel_surf(bw, bh, fill_lum=14, fill_alpha=220, border_lum=156, radius=10)
            screen.blit(bp, (bx, by))
            b_clip = screen.get_clip()
            screen.set_clip(pygame.Rect(bx + 8, by + 4, bw - 16, bh - 8))
            if self.banner_item is not None:
                icon_box = pygame.Rect(bx + 12, by + 9, 46, 46)
                pygame.draw.rect(screen, (26, 26, 26), icon_box, border_radius=7)
                pygame.draw.rect(screen, (152, 152, 152), icon_box, 1, border_radius=7)
                draw_item_icon(screen, self.banner_item, icon_box.centerx, icon_box.centery, 34)
                max_tw = max(80, bw - 84)
                t1 = fit_text_surf(self.font_big, self.banner_text, PALETTE["text_main"], max_tw, max_h=28)
                screen.blit(t1, (bx + 70, by + 8))
                if self.banner_sub:
                    t2 = fit_text_surf(self.font_tiny, self.banner_sub, PALETTE["text_muted"], max_tw, max_h=16)
                    screen.blit(t2, (bx + 70, by + 39))
            else:
                max_tw = max(80, bw - 28)
                t1 = fit_text_surf(self.font_big, self.banner_text, PALETTE["text_main"], max_tw, max_h=28)
                screen.blit(t1, (bx + bw // 2 - t1.get_width() // 2, by + 8))
                if self.banner_sub:
                    t2 = fit_text_surf(self.font_tiny, self.banner_sub, PALETTE["text_muted"], max_tw, max_h=16)
                    screen.blit(t2, (bx + bw // 2 - t2.get_width() // 2, by + 39))
            screen.set_clip(b_clip)

        if p2 is not None:
            p2_rc = hud_layout["p2"]
            p2_x, p2_y, p2_w, p2_h = p2_rc.x, p2_rc.y, p2_rc.w, p2_rc.h
            p2_panel = get_panel_surf(p2_w, p2_h, fill_lum=12, fill_alpha=210, border_lum=116 if not p2_dead else 74, radius=10)
            screen.blit(p2_panel, (p2_x, p2_y))

            pygame.draw.rect(screen, (238, 238, 238) if not p2_dead else (96, 96, 96), (p2_x + 12, p2_y + 7, 24, 14), border_radius=4)
            p2_badge = fit_text_surf(self.font_tiny, str(coop_tag)[:3], (12, 12, 12), 22, max_h=13)
            screen.blit(p2_badge, (p2_x + 24 - p2_badge.get_width() // 2, p2_y + 7))

            if p2_dead:
                st_txt = tr("coop_ko")
                st_col = (188, 188, 188)
            elif p2.holy_mantle and not p2.mantle_broken_room:
                st_txt = "[SHIELD]"
                st_col = PALETTE["text_main"]
            else:
                st_txt = str(coop_mode_label)[:10]
                st_col = PALETTE["text_muted"]
            st_lbl = fit_text_surf(self.font_tiny, st_txt, st_col, 92, max_h=tiny_h)
            screen.blit(st_lbl, (p2_rc.right - st_lbl.get_width() - 12, p2_y + 7))

            p2_name = p2.hero.get("name_en", p2.hero["name"]) if lang == "en" else p2.hero["name"]
            p2_name_max_w = max(60, p2_w - 60 - st_lbl.get_width())
            p2_name_s = fit_text_surf(self.font_tiny, p2_name.upper()[:16], PALETTE["text_main"] if not p2_dead else (172, 172, 172), p2_name_max_w, max_h=tiny_h)
            screen.blit(p2_name_s, (p2_x + 42, p2_y + 7))

            if p2_dead:
                self._last_p2_active_relic_rect = None
                down_txt = f"{coop_tag} {tr('coop_ko')}" if coop_tag != "P2" else tr("p2_down")
                ko_lbl = fit_text_surf(self.font_small, down_txt, (232, 232, 232), p2_w - 24, max_h=small_h)
                ko_y = p2_y + 27
                rev_y = ko_y + small_h + 2
                k_y = rev_y + tiny_h + 2
                screen.blit(ko_lbl, (p2_x + 12, ko_y))
                rev_lbl = fit_text_surf(self.font_tiny, tr("p2_revive_hint"), PALETTE["text_muted"], p2_w - 24, max_h=tiny_h)
                screen.blit(rev_lbl, (p2_x + 12, rev_y))
                k_lbl = fit_text_surf(self.font_tiny, f"KILLS {p2.kills} · ITEMS {len(p2.collected_items)}", PALETTE["text_dim"], p2_w - 24, max_h=tiny_h)
                screen.blit(k_lbl, (p2_x + 12, k_y))
            else:
                p2_seq = []
                p2_cont = max(0, p2.max_hp // 2)
                for i in range(p2_cont):
                    shp = p2.hp - i * 2
                    p2_seq.append("red" if shp >= 2 else ("half" if shp == 1 else "empty"))
                for _ in range((p2.soul_hp + 1) // 2):
                    p2_seq.append("soul")
                for _ in range((p2.black_hp + 1) // 2):
                    p2_seq.append("black")
                hy2_rel = max(24, 7 + tiny_h + 2)
                hx2 = p2_x + 12
                hy2 = p2_y + hy2_rel
                hx2_limit = p2_rc.right - 26
                for ft in p2_seq:
                    self._draw_heart(screen, hx2, hy2, ft)
                    hx2 += 21
                    if hx2 > hx2_limit:
                        hx2 = p2_x + 12
                        hy2 += 18

                p2_res_y = p2_y + hy2_rel + (p2_extra_rows + 1) * 18 + 3
                p2_stat_y = p2_res_y + med_h + 2
                p2_abil_y = p2_stat_y + tiny_h + 3
                p2_act_y = p2_abil_y + tiny_h + 3

                p2_res = fit_text_surf(self.font_med, f"¢ {p2.coins:02d}   B {p2.bombs:02d}   K {p2.keys:02d}", PALETTE["text_main"], p2_w - 24, max_h=med_h)
                screen.blit(p2_res, (p2_x + 12, p2_res_y))

                p2_stat = fit_text_surf(
                    self.font_tiny,
                    f"DMG {p2.get_effective_damage():.1f} · SPD {p2.get_effective_speed():.1f} · KILLS {p2.kills}",
                    PALETTE["text_muted"],
                    p2_w - 24,
                    max_h=tiny_h,
                )
                screen.blit(p2_stat, (p2_x + 12, p2_stat_y))

                p2_dash_r = 1.0 if p2.dash_cd <= 0 else max(0.0, 1.0 - p2.dash_cd / max(1.0, p2.dash_max_cd))
                self.p2_dash_smooth += (p2_dash_r - self.p2_dash_smooth) * 0.24
                rsh_lbl = fit_text_surf(self.font_tiny, "[RSH]", PALETTE["text_dim"], 52, max_h=tiny_h)
                m_lbl = fit_text_surf(self.font_tiny, "[M]", PALETTE["text_dim"], 36, max_h=tiny_h)
                p2_inv_t = getattr(p2, "invis_timer", 0.0)
                if p2_inv_t > 0:
                    p2_inv_r = min(1.0, p2_inv_t / 135.0)
                    p2_inv_col = (248, 248, 248)
                else:
                    p2_inv_r = 1.0 if getattr(p2, "invis_cd", 0.0) <= 0 else max(0.0, 1.0 - p2.invis_cd / max(1.0, getattr(p2, "invis_max_cd", 300.0)))
                    p2_inv_col = (224, 224, 224) if p2_inv_r >= 0.98 else (118, 118, 118)
                n_lbl = fit_text_surf(self.font_tiny, "[N]", (248, 248, 248) if p2_inv_t > 0 else PALETTE["text_dim"], 36, max_h=tiny_h)

                p2_fixed = rsh_lbl.get_width() + m_lbl.get_width() + n_lbl.get_width() + 24
                p2_rem = max(72, (p2_w - 24) - p2_fixed)
                pw1 = max(24, int(p2_rem * 0.36))
                pw2 = max(24, int(p2_rem * 0.30))
                pw3 = max(24, p2_rem - pw1 - pw2)
                p2_bar_y = p2_abil_y + max(3, (tiny_h - 6) // 2)

                cx2 = p2_x + 12
                screen.blit(rsh_lbl, (cx2, p2_abil_y))
                pb1 = cx2 + rsh_lbl.get_width() + 4
                pygame.draw.rect(screen, (36, 36, 36), (pb1, p2_bar_y, pw1, 6), border_radius=3)
                pygame.draw.rect(screen, (238, 238, 238) if self.p2_dash_smooth >= 0.98 else (142, 142, 142), (pb1, p2_bar_y, int(pw1 * self.p2_dash_smooth), 6), border_radius=3)

                p2_jmp_r = 1.0 if getattr(p2, "jump_cd", 0.0) <= 0 else max(0.0, 1.0 - p2.jump_cd / max(1.0, getattr(p2, "jump_max_cd", 54.0)))
                cx2 = pb1 + pw1 + 6
                screen.blit(m_lbl, (cx2, p2_abil_y))
                pb2 = cx2 + m_lbl.get_width() + 4
                pygame.draw.rect(screen, (36, 36, 36), (pb2, p2_bar_y, pw2, 6), border_radius=3)
                pygame.draw.rect(screen, (230, 230, 230) if p2_jmp_r >= 0.98 else (130, 130, 130), (pb2, p2_bar_y, int(pw2 * p2_jmp_r), 6), border_radius=3)

                cx2 = pb2 + pw2 + 6
                screen.blit(n_lbl, (cx2, p2_abil_y))
                pb3 = cx2 + n_lbl.get_width() + 4
                pygame.draw.rect(screen, (36, 36, 36), (pb3, p2_bar_y, pw3, 6), border_radius=3)
                pygame.draw.rect(screen, p2_inv_col, (pb3, p2_bar_y, int(pw3 * p2_inv_r), 6), border_radius=3)

                if p2.active_item is not None:
                    self._last_p2_active_relic_rect = pygame.Rect(p2_x + 10, p2_act_y - 2, p2_w - 20, 30)
                    p2_box = pygame.Rect(p2_x + 12, p2_act_y, 26, 26)
                    p2_ready = p2.active_charge >= p2.max_charge
                    pygame.draw.rect(screen, (36, 36, 36) if p2_ready else (24, 24, 24), p2_box, border_radius=5)
                    pygame.draw.rect(screen, (246, 246, 246) if p2_ready else (142, 142, 142), p2_box, 2 if p2_ready else 1, border_radius=5)
                    draw_item_icon(screen, p2.active_item, p2_box.centerx, p2_box.centery, 20)
                    p2_act_name = tr_item_name(p2.active_item)
                    p2_act_lbl = fit_text_surf(self.font_tiny, f"{p2_act_name[:18]} [O]", (252, 252, 252) if p2_ready else PALETTE["text_main"], p2_w - 58, max_h=tiny_h)
                    screen.blit(p2_act_lbl, (p2_x + 44, p2_act_y - 1))
                    mc2 = max(1, p2.max_charge)
                    p2_chg_y = p2_act_y + max(15, tiny_h + 1)
                    if mc2 <= 6:
                        for p_i in range(mc2):
                            px2 = p2_x + 44 + p_i * 14
                            lit2 = p_i < p2.active_charge
                            pygame.draw.rect(screen, (240, 240, 240) if lit2 else (42, 42, 42), (px2, p2_chg_y, 11, 6), border_radius=2)
                    else:
                        bar_w2 = 128
                        pygame.draw.rect(screen, (36, 36, 36), (p2_x + 44, p2_chg_y, bar_w2, 6), border_radius=3)
                        fill_w2 = int(bar_w2 * clamp(p2.active_charge / float(mc2), 0.0, 1.0))
                        pygame.draw.rect(screen, (240, 240, 240), (p2_x + 44, p2_chg_y, fill_w2, 6), border_radius=3)
                        chg_s2 = fit_text_surf(self.font_tiny, f"{p2.active_charge}/{mc2}", PALETTE["text_muted"], 56, max_h=14)
                        screen.blit(chg_s2, (p2_x + 44 + bar_w2 + 8, p2_chg_y - 3))
                else:
                    self._last_p2_active_relic_rect = None
                    no_act2 = "NO RELIC" if lang == "en" else "НЕТ РЕЛИКВИИ"
                    screen.blit(fit_text_surf(self.font_tiny, no_act2, PALETTE["text_dim"], p2_w - 24, max_h=tiny_h), (p2_x + 12, p2_act_y + 5))
        else:
            self._last_p2_active_relic_rect = None


    def get_chaos_draft_rects(self, count=3):
        vw = get_view_width()
        n = max(1, min(3, int(count)))
        pw, ph = 860, 444
        px, py = vw // 2 - pw // 2, SCREEN_HEIGHT // 2 - ph // 2
        card_w, card_h, gap = 246, 256, 26
        start_x = px + (pw - (card_w * n + gap * (n - 1))) // 2
        return [pygame.Rect(start_x + i * (card_w + gap), py + 118, card_w, card_h) for i in range(n)]

    def draw_chaos_draft(self, screen, options, selected_idx, hover_idx=-1):
        vw = get_view_width()
        screen.blit(self._get_dim_overlay(), (0, 0))
        pw, ph = 860, 444
        px, py = vw // 2 - pw // 2, SCREEN_HEIGHT // 2 - ph // 2
        screen.blit(get_panel_surf(pw, ph, 12, 242, 146, 12), (px, py))

        title = fit_text_surf(self.font_huge, tr("draft_title"), PALETTE["text_main"], pw - 64, max_h=40)
        sub = fit_text_surf(self.font_small, tr("draft_sub"), PALETTE["accent_soft"], pw - 64, max_h=20)
        screen.blit(title, (vw // 2 - title.get_width() // 2, py + 22))
        screen.blit(sub, (vw // 2 - sub.get_width() // 2, py + 72))

        rects = self.get_chaos_draft_rects(len(options))
        for idx, rc in enumerate(rects):
            if idx >= len(options):
                continue
            it = options[idx]
            sel = idx == selected_idx
            hov = idx == hover_idx
            fill = (36, 36, 36) if sel else ((28, 28, 28) if hov else (18, 18, 18))
            border = (252, 252, 252) if sel else ((180, 180, 180) if hov else (78, 78, 78))
            pygame.draw.rect(screen, fill, rc, border_radius=10)
            pygame.draw.rect(screen, border, rc, 2 if sel else 1, border_radius=10)

            key_s = fit_text_surf(self.font_tiny, f"[{idx + 1}]", (244, 244, 244) if sel else PALETTE["text_dim"], 44, max_h=15)
            screen.blit(key_s, (rc.x + 12, rc.y + 10))

            icon_box = pygame.Rect(rc.centerx - 34, rc.y + 34, 68, 68)
            pygame.draw.rect(screen, (24, 24, 24), icon_box, border_radius=10)
            pygame.draw.rect(screen, (140, 140, 140) if sel else (76, 76, 76), icon_box, 1, border_radius=10)
            draw_item_icon(screen, it, icon_box.centerx, icon_box.centery, 48)

            nm = tr_item_name(it)
            nm_s = fit_text_surf(self.font_med, nm, PALETTE["text_main"], rc.w - 22, max_h=24)
            screen.blit(nm_s, (rc.centerx - nm_s.get_width() // 2, rc.y + 114))

            desc = tr_item_desc(it)
            words = desc.split()
            lines = []
            cur = ""
            for w in words:
                cand = f"{cur} {w}".strip()
                if len(cand) > 26:
                    lines.append(cur)
                    cur = w
                else:
                    cur = cand
            if cur:
                lines.append(cur)
            for li, ln in enumerate(lines[:4]):
                ds = fit_text_surf(self.font_tiny, ln, PALETTE["text_muted"], rc.w - 20, max_h=16)
                screen.blit(ds, (rc.centerx - ds.get_width() // 2, rc.y + 150 + li * 20))

        hint = fit_text_surf(self.font_small, tr("draft_hint"), PALETTE["text_dim"], pw - 48, max_h=20)
        screen.blit(hint, (vw // 2 - hint.get_width() // 2, py + ph - 36))

    def get_pause_rects(self, touch_active=None):
        vw = get_view_width()
        phone = self._phone_mode(touch_active)
        pw, ph = (480, 504) if phone else (418, 434)
        px, py = vw // 2 - pw // 2, SCREEN_HEIGHT // 2 - ph // 2
        row_h = 46 if phone else 36
        row_step = 54 if phone else 43
        top_off = 94 if phone else 90
        return [pygame.Rect(px + 32, py + top_off + i * row_step, pw - 64, row_h) for i in range(7)]

    def draw_pause(self, screen, selected_idx, hover_idx=-1, touch_active=None):
        vw = get_view_width()
        screen.blit(self._get_dim_overlay(), (0, 0))
        phone = self._phone_mode(touch_active)
        pw, ph = (480, 504) if phone else (418, 434)
        px, py = vw // 2 - pw // 2, SCREEN_HEIGHT // 2 - ph // 2
        screen.blit(get_panel_surf(pw, ph, 14, 238, 128, 12), (px, py))
        title = fit_text_surf(self.font_huge, tr("pause_title"), PALETTE["text_main"], pw - 48)
        screen.blit(title, (vw // 2 - title.get_width() // 2, py + 24))
        opts = [
            tr("pause_resume"),
            tr("pause_saves"),
            tr("pause_restart"),
            tr("pause_codex"),
            tr("pause_lan"),
            tr("pause_settings"),
            tr("pause_menu"),
        ]
        rects = self.get_pause_rects(touch_active)
        for i, (lbl, rc) in enumerate(zip(opts, rects)):
            sel = i == selected_idx
            hov = i == hover_idx
            fill = (234, 234, 234) if sel else ((54, 54, 54) if hov else (28, 28, 28))
            border = (252, 252, 252) if sel else ((146, 146, 146) if hov else (68, 68, 68))
            pygame.draw.rect(screen, fill, rc, border_radius=6)
            pygame.draw.rect(screen, border, rc, 1, border_radius=6)
            blit_text_fitted(screen, rc, self.font_med, lbl, (12, 12, 12) if sel else PALETTE["text_main"], pad_x=12)

    def get_end_rects(self, touch_active=None, is_coop=False):
        vw = get_view_width()
        phone = self._phone_mode(touch_active)
        if is_coop:
            pw, ph = (656, 392) if phone else (608, 360)
        else:
            pw, ph = (636, 358) if phone else (588, 328)
        px, py = vw // 2 - pw // 2, SCREEN_HEIGHT // 2 - ph // 2
        bh = 54 if phone else 44
        by = py + ph - bh - 30
        return (
            pygame.Rect(px + 38, by, pw // 2 - 52, bh),
            pygame.Rect(px + pw // 2 + 14, by, pw // 2 - 52, bh),
        )

    def draw_end_screen(self, screen, victory, player, floor_level, boss_key="", game_mode="classic", wave_num=0, hover_btn=-1, touch_active=None, p2=None):
        vw = get_view_width()
        screen.blit(self._get_dim_overlay(), (0, 0))
        phone = self._phone_mode(touch_active)
        is_coop = p2 is not None
        pw, ph = ((656, 392) if is_coop else (636, 358)) if phone else ((608, 360) if is_coop else (588, 328))
        px, py = vw // 2 - pw // 2, SCREEN_HEIGHT // 2 - ph // 2
        screen.blit(get_panel_surf(pw, ph, 12, 240, 148, 12), (px, py))
        title_txt = tr("victory_title") if victory else tr("gameover_title")
        title = fit_text_surf(self.font_huge, title_txt, PALETTE["text_main"], pw - 48, max_h=40)
        screen.blit(title, (vw // 2 - title.get_width() // 2, py + 22))
        prog = f"{tr('wave_label')} {max(1, wave_num)}" if game_mode == "endless_abyss" else f"{tr('floor_label')} {floor_level}"
        lang = GAME_SETTINGS.get("language", "ru")
        h_name = player.hero.get("name_en", player.hero["name"]) if lang == "en" else player.hero["name"]
        if is_coop:
            p2_name = p2.hero.get("name_en", p2.hero["name"]) if lang == "en" else p2.hero["name"]
            total_kills = player.kills + p2.kills
            info1 = fit_text_surf(
                self.font_med,
                f"[P1] {h_name}: KILLS {player.kills} · ITEMS {len(player.collected_items)}",
                PALETTE["text_main"],
                pw - 56,
                max_h=24,
            )
            info2 = fit_text_surf(
                self.font_med,
                f"[P2] {p2_name}: KILLS {p2.kills} · ITEMS {len(p2.collected_items)}",
                PALETTE["text_muted"],
                pw - 56,
                max_h=24,
            )
            sum_lbl = fit_text_surf(
                self.font_small,
                f"{prog}  ·  {tr_mode(game_mode)}  ·  CO-OP KILLS {total_kills}",
                PALETTE["text_dim"],
                pw - 56,
                max_h=20,
            )
            screen.blit(info1, (vw // 2 - info1.get_width() // 2, py + 86))
            screen.blit(info2, (vw // 2 - info2.get_width() // 2, py + 118))
            screen.blit(sum_lbl, (vw // 2 - sum_lbl.get_width() // 2, py + 152))
            boss_y = py + 186
        else:
            info = fit_text_surf(
                self.font_med,
                f"{h_name}  ·  {prog}  ·  KILLS {player.kills}  ·  ITEMS {len(player.collected_items)}",
                PALETTE["text_muted"],
                pw - 56,
                max_h=24,
            )
            screen.blit(info, (vw // 2 - info.get_width() // 2, py + 98))
            mode_lbl = fit_text_surf(self.font_small, tr_mode(game_mode), PALETTE["text_dim"], pw - 56, max_h=20)
            screen.blit(mode_lbl, (vw // 2 - mode_lbl.get_width() // 2, py + 132))
            boss_y = py + 166
        if boss_key:
            bl = fit_text_surf(self.font_med, tr_boss(boss_key), PALETTE["accent_soft"], pw - 56, max_h=24)
            screen.blit(bl, (vw // 2 - bl.get_width() // 2, boss_y))

        btn_r, btn_m = self.get_end_rects(touch_active, is_coop=is_coop)
        lbl_r = "НОВЫЙ СПУСК [R]" if lang == "ru" else "NEW DESCENT [R]"
        lbl_m = "ГЛАВНОЕ МЕНЮ [ESC]" if lang == "ru" else "MAIN MENU [ESC]"
        for idx, (rc, txt_s) in enumerate(((btn_r, lbl_r), (btn_m, lbl_m))):
            hov = idx == hover_btn
            pygame.draw.rect(screen, (236, 236, 236) if hov else (28, 28, 28), rc, border_radius=7)
            pygame.draw.rect(screen, (252, 252, 252) if hov else (112, 112, 112), rc, 1, border_radius=7)
            blit_text_fitted(screen, rc, self.font_med if phone else self.font_small, txt_s, (12, 12, 12) if hov else PALETTE["text_main"], pad_x=10)

    def get_pickup_confirm_rects(self, touch_active=None):
        vw = get_view_width()
        phone = self._phone_mode(touch_active)
        pw, ph = (560, 318) if phone else (500, 286)
        px, py = vw // 2 - pw // 2, SCREEN_HEIGHT // 2 - ph // 2
        bh = 52 if phone else 44
        by = py + ph - bh - 26
        bw = pw // 2 - 42
        confirm_rc = pygame.Rect(px + 28, by, bw, bh)
        cancel_rc = pygame.Rect(px + pw // 2 + 14, by, bw, bh)
        return pygame.Rect(px, py, pw, ph), confirm_rc, cancel_rc

    def draw_pickup_confirm_modal(self, screen, prompt_state, touch_active=None):
        if not prompt_state:
            return
        ped = prompt_state.get("pedestal")
        cp = prompt_state.get("player")
        if ped is None or not getattr(ped, "alive", True) or not getattr(ped, "item", None):
            return
        it = ped.item
        sel = int(prompt_state.get("selected", 0))
        can_afford = bool(prompt_state.get("can_afford", True))
        cost_text = prompt_state.get("cost_text", "")
        phone = self._phone_mode(touch_active)
        vw = get_view_width()

        screen.blit(self._get_dim_overlay(), (0, 0))
        panel_rc, confirm_rc, cancel_rc = self.get_pickup_confirm_rects(touch_active)
        px, py, pw, ph = panel_rc.x, panel_rc.y, panel_rc.w, panel_rc.h
        screen.blit(get_panel_surf(pw, ph, fill_lum=12, fill_alpha=244, border_lum=178, radius=12), (px, py))

        title_s = fit_text_surf(self.font_med, tr("pickup_confirm_title"), PALETTE["text_muted"], pw - 40, max_h=22)
        screen.blit(title_s, (vw // 2 - title_s.get_width() // 2, py + 16))

        # Item icon frame
        icon_box = pygame.Rect(px + 28, py + 52, 74, 74)
        pygame.draw.rect(screen, (26, 26, 26), icon_box, border_radius=10)
        pygame.draw.rect(screen, (216, 216, 216), icon_box, 2, border_radius=10)
        draw_item_icon(screen, it, icon_box.centerx, icon_box.centery, 54)

        tx = icon_box.right + 18
        tw = pw - (tx - px) - 24
        is_act = it.get("type") == "active"
        type_lbl = tr("pickup_type_active") if is_act else tr("pickup_type_passive")
        type_col = (248, 248, 248) if is_act else (188, 188, 188)
        badge_surf = fit_text_surf(self.font_tiny, f"[{type_lbl}]", type_col, tw, max_h=16)
        screen.blit(badge_surf, (tx, py + 50))

        name_surf = fit_text_surf(self.font_big if phone else self.font_med, tr_item_name(it).upper(), PALETTE["text_main"], tw, max_h=26)
        screen.blit(name_surf, (tx, py + 72))

        desc_surf = fit_text_surf(self.font_small, tr_item_desc(it), PALETTE["text_muted"], tw, max_h=22)
        screen.blit(desc_surf, (tx, py + 106))

        if cost_text:
            c_col = (242, 242, 242) if can_afford else (196, 128, 128)
            c_txt = cost_text if can_afford else f"{cost_text} — {tr('pickup_cant_afford')}"
            c_surf = fit_text_surf(self.font_small, c_txt, c_col, pw - 56, max_h=22)
            screen.blit(c_surf, (vw // 2 - c_surf.get_width() // 2, py + 146))

        hint_s = fit_text_surf(self.font_tiny, tr("pickup_hint_keys"), PALETTE["text_dim"], pw - 48, max_h=16)
        screen.blit(hint_s, (vw // 2 - hint_s.get_width() // 2, confirm_rc.top - 22))

        for idx, (rc, label, enabled) in enumerate((
            (confirm_rc, tr("pickup_confirm_btn"), can_afford),
            (cancel_rc, tr("pickup_cancel_btn"), True),
        )):
            active_btn = (idx == sel) and enabled
            if not enabled:
                bg, bd, fg = (22, 22, 22), (72, 72, 72), (104, 104, 104)
            elif active_btn:
                bg, bd, fg = (242, 242, 242), (255, 255, 255), (12, 12, 12)
            else:
                bg, bd, fg = (30, 30, 30), (126, 126, 126), PALETTE["text_main"]
            pygame.draw.rect(screen, bg, rc, border_radius=8)
            pygame.draw.rect(screen, bd, rc, 2 if active_btn else 1, border_radius=8)
            blit_text_fitted(screen, rc, self.font_med if phone else self.font_small, label, fg, pad_x=10)
