import math
import pygame
from settings import (
    GAME_SETTINGS,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    TOUCH_LAYOUT_PRESETS,
    _finalize_alpha_surf,
    blit_text_fitted,
    clamp,
    draw_aa_circle,
    draw_aa_ring,
    fit_text_surf,
    get_panel_surf,
    get_view_width,
    is_android,
    is_phone_layout,
    render_text_cached,
    save_user_settings,
)


class TouchControls:
    def __init__(self):
        self.touch_seen = is_android()
        self.move_base_default = (158.0, 524.0)
        self.aim_base_default = (1126.0, 514.0)

        self.move_finger = None
        self.move_base = self.move_base_default
        self.move_pos = self.move_base_default
        self.move_vec = (0.0, 0.0)

        self.aim_finger = None
        self.aim_base = self.aim_base_default
        self.aim_pos = self.aim_base_default
        self.aim_dir = (0, 0)

        self.stick_radius = 64.0
        self.knob_radius = 24.0
        self.deadzone = 11.0

        self.dash_center = (938, 534)
        self.dash_radius = 31
        self.jump_center = (938, 620)
        self.jump_radius = 28
        self.bomb_center = (938, 446)
        self.bomb_radius = 28
        self.stealth_center = (972, 366)
        self.stealth_radius = 28
        self.relic_center = (1064, 366)
        self.relic_radius = 31
        self.melee_center = (1036, 608)
        self.melee_radius = 30
        self.interact_center = (864, 446)
        self.interact_radius = 28
        self.pause_center = (1038, 44)
        self.pause_radius = 26

        self.btn_fingers = {}
        self.dash_pressed = False
        self.jump_triggered = False
        self.stealth_triggered = False
        self.bomb_triggered = False
        self.relic_triggered = False
        self.melee_triggered = False
        self.interact_triggered = False
        self.pause_triggered = False

        self._ring_cache = {}
        self._knob_cache = {}
        self._btn_cache = {}
        self._bomb_icon_cache = {}
        self._bomb_badge_cache = {}
        self._layout_phone = None
        self._layout_key = None
        self.hit_pad = 10

        self.customizer_drag_node = None
        self.customizer_drag_offset = (0.0, 0.0)
        self._base_centers = {}
        self._sync_layout()

    def invalidate_layout(self):
        self._layout_key = None

    def _compute_base_layout(self, phone, vw):
        wide_extra = max(0, vw - SCREEN_WIDTH)
        left_x = 122.0 if wide_extra >= 120 else 136.0
        right_x = float(vw) - (122.0 if wide_extra >= 120 else (142.0 if phone else 138.0))
        if phone:
            stick_r = 64.0
            knob_r = 24.0
            btn_col_x = int(right_x - 190) if wide_extra >= 120 else int(right_x - 200)
            centers = {
                "move": (left_x, 488.0),
                "aim": (right_x, 490.0),
                "dash": (btn_col_x, 534),
                "jump": (btn_col_x, 620),
                "bomb": (btn_col_x, 446),
                "stealth": (int(right_x - 166), 366),
                "relic": (int(right_x - 74), 366),
                "melee": (int(right_x - 102), 608),
                "interact": (int(btn_col_x - 74), 446),
                "pause": (vw - 242, 44),
            }
            radii = {
                "move": 66,
                "aim": 66,
                "dash": 33,
                "jump": 30,
                "bomb": 30,
                "stealth": 30,
                "relic": 33,
                "melee": 32,
                "interact": 28,
                "pause": 28,
            }
            hit_pad = 16
        else:
            stick_r = 58.0
            knob_r = 22.0
            btn_col_x = int(right_x - 180)
            centers = {
                "move": (left_x, 492.0),
                "aim": (right_x, 492.0),
                "dash": (btn_col_x, 508),
                "jump": (btn_col_x, 582),
                "bomb": (int(right_x - 178), 434),
                "stealth": (int(right_x - 166), 358),
                "relic": (int(right_x - 78), 358),
                "melee": (int(right_x - 100), 576),
                "interact": (int(btn_col_x - 68), 434),
                "pause": (vw - 232, 38),
            }
            radii = {
                "move": 58,
                "aim": 58,
                "dash": 27,
                "jump": 24,
                "bomb": 25,
                "stealth": 25,
                "relic": 27,
                "melee": 26,
                "interact": 24,
                "pause": 22,
            }
            hit_pad = 10
        return centers, radii, stick_r, knob_r, hit_pad

    def _sync_layout(self):
        phone = is_phone_layout(self.is_active())
        vw = get_view_width()
        preset = str(GAME_SETTINGS.get("touch_layout_preset", "wide"))
        if preset not in TOUCH_LAYOUT_PRESETS:
            preset = "wide"
        custom_offsets = GAME_SETTINGS.get("touch_custom_offsets")
        custom_sig = tuple(sorted((str(k), tuple(v)) for k, v in custom_offsets.items() if isinstance(v, (list, tuple)) and len(v) == 2)) if (preset == "custom" and isinstance(custom_offsets, dict)) else ()
        key = (phone, vw, preset, custom_sig)
        if key == self._layout_key:
            return
        self._layout_key = key
        self._layout_phone = phone

        base_centers, radii, stick_r, knob_r, hit_pad = self._compute_base_layout(phone, vw)
        self._base_centers = dict(base_centers)
        self.stick_radius = stick_r
        self.knob_radius = knob_r
        self.deadzone = 11.0
        self.hit_pad = hit_pad

        centers = {k: (float(v[0]), float(v[1])) for k, v in base_centers.items()}
        if preset == "raised":
            for nid in ("move", "aim", "dash", "jump", "bomb", "stealth", "relic", "melee", "interact"):
                cx, cy = centers[nid]
                dx = 10.0 if nid == "move" else (-6.0 if nid != "pause" else 0.0)
                centers[nid] = (cx + dx, cy - 42.0)
        elif preset == "custom" and isinstance(custom_offsets, dict):
            for nid in centers:
                off = custom_offsets.get(nid)
                if isinstance(off, (list, tuple)) and len(off) == 2:
                    try:
                        bx, by = centers[nid]
                        centers[nid] = (bx + float(off[0]), by + float(off[1]))
                    except Exception:
                        pass

        # Clamp all controls cleanly inside the entire screen view bounds (0 to vw, 0 to SCREEN_HEIGHT)
        for nid, (cx, cy) in list(centers.items()):
            r = radii[nid]
            cx = clamp(cx, r, vw - r)
            cy = clamp(cy, r, SCREEN_HEIGHT - r)
            centers[nid] = (cx, cy)

        self.move_base_default = (float(centers["move"][0]), float(centers["move"][1]))
        self.aim_base_default = (float(centers["aim"][0]), float(centers["aim"][1]))
        self.dash_center = (int(round(centers["dash"][0])), int(round(centers["dash"][1])))
        self.dash_radius = radii["dash"]
        self.jump_center = (int(round(centers["jump"][0])), int(round(centers["jump"][1])))
        self.jump_radius = radii["jump"]
        self.bomb_center = (int(round(centers["bomb"][0])), int(round(centers["bomb"][1])))
        self.bomb_radius = radii["bomb"]
        self.stealth_center = (int(round(centers["stealth"][0])), int(round(centers["stealth"][1])))
        self.stealth_radius = radii["stealth"]
        self.relic_center = (int(round(centers["relic"][0])), int(round(centers["relic"][1])))
        self.relic_radius = radii["relic"]
        self.melee_center = (int(round(centers["melee"][0])), int(round(centers["melee"][1])))
        self.melee_radius = radii["melee"]
        self.interact_center = (int(round(centers["interact"][0])), int(round(centers["interact"][1])))
        self.interact_radius = radii["interact"]
        self.pause_center = (int(round(centers["pause"][0])), int(round(centers["pause"][1])))
        self.pause_radius = radii["pause"]

        if self.move_finger is None:
            self.move_base = self.move_base_default
            self.move_pos = self.move_base_default
        if self.aim_finger is None:
            self.aim_base = self.aim_base_default
            self.aim_pos = self.aim_base_default

    def is_active(self):
        mode = GAME_SETTINGS.get("touch_controls", "auto")
        if mode == "on":
            return True
        if mode == "off":
            return False
        if bool(self.touch_seen or is_android()):
            return True
        try:
            if get_view_width() <= 860:
                return True
        except Exception:
            pass
        return False

    def reset(self):
        self.invalidate_layout()
        self._sync_layout()
        self.move_finger = None
        self.move_base = self.move_base_default
        self.move_pos = self.move_base_default
        self.move_vec = (0.0, 0.0)
        self.aim_finger = None
        self.aim_base = self.aim_base_default
        self.aim_pos = self.aim_base_default
        self.aim_dir = (0, 0)
        self.btn_fingers.clear()
        self.dash_pressed = False
        self.jump_triggered = False
        self.stealth_triggered = False
        self.bomb_triggered = False
        self.relic_triggered = False
        self.melee_triggered = False
        self.interact_triggered = False
        self.pause_triggered = False

    def _hit_circle(self, pos, center, radius):
        return math.hypot(pos[0] - center[0], pos[1] - center[1]) <= radius + self.hit_pad

    def _update_move(self, pos):
        dx = pos[0] - self.move_base[0]
        dy = pos[1] - self.move_base[1]
        dist = math.hypot(dx, dy)
        if dist > self.stick_radius:
            scale = self.stick_radius / dist
            self.move_pos = (self.move_base[0] + dx * scale, self.move_base[1] + dy * scale)
        else:
            self.move_pos = (float(pos[0]), float(pos[1]))
        if dist < self.deadzone:
            self.move_vec = (0.0, 0.0)
        else:
            ux = dx / max(1.0, dist)
            uy = dy / max(1.0, dist)
            self.move_vec = (ux, uy)

    def _update_aim(self, pos):
        dx = pos[0] - self.aim_base[0]
        dy = pos[1] - self.aim_base[1]
        dist = math.hypot(dx, dy)
        if dist > self.stick_radius:
            scale = self.stick_radius / dist
            self.aim_pos = (self.aim_base[0] + dx * scale, self.aim_base[1] + dy * scale)
        else:
            self.aim_pos = (float(pos[0]), float(pos[1]))
        if dist < self.deadzone:
            self.aim_dir = (0, 0)
        else:
            angle = math.atan2(dy, dx)
            deg = math.degrees(angle) % 360
            if 337.5 <= deg or deg < 22.5:
                self.aim_dir = (1, 0)
            elif 22.5 <= deg < 67.5:
                self.aim_dir = (1, 1)
            elif 67.5 <= deg < 112.5:
                self.aim_dir = (0, 1)
            elif 112.5 <= deg < 157.5:
                self.aim_dir = (-1, 1)
            elif 157.5 <= deg < 202.5:
                self.aim_dir = (-1, 0)
            elif 202.5 <= deg < 247.5:
                self.aim_dir = (-1, -1)
            elif 247.5 <= deg < 292.5:
                self.aim_dir = (0, -1)
            else:
                self.aim_dir = (1, -1)

    def has_active_fingers(self):
        return (
            (self.move_finger is not None and self.move_finger != -1)
            or (self.aim_finger is not None and self.aim_finger != -1)
            or any(fid != -1 for fid in self.btn_fingers)
        )

    def handle_finger_down(self, finger_id, logical_pos):
        self.touch_seen = True
        self._sync_layout()
        if not self.is_active():
            return False

        x, y = logical_pos

        if self._hit_circle((x, y), self.pause_center, self.pause_radius):
            self.btn_fingers[finger_id] = "pause"
            self.pause_triggered = True
            return True

        if self._hit_circle((x, y), self.dash_center, self.dash_radius):
            self.btn_fingers[finger_id] = "dash"
            self.dash_pressed = True
            return True

        if self._hit_circle((x, y), self.jump_center, self.jump_radius):
            self.btn_fingers[finger_id] = "jump"
            self.jump_triggered = True
            return True

        if self._hit_circle((x, y), self.bomb_center, self.bomb_radius):
            self.btn_fingers[finger_id] = "bomb"
            self.bomb_triggered = True
            return True

        if self._hit_circle((x, y), self.stealth_center, self.stealth_radius):
            self.btn_fingers[finger_id] = "stealth"
            self.stealth_triggered = True
            return True

        if self._hit_circle((x, y), self.relic_center, self.relic_radius):
            self.btn_fingers[finger_id] = "relic"
            self.relic_triggered = True
            return True

        if self._hit_circle((x, y), self.melee_center, self.melee_radius):
            self.btn_fingers[finger_id] = "melee"
            self.melee_triggered = True
            return True

        if self._hit_circle((x, y), self.interact_center, self.interact_radius):
            self.btn_fingers[finger_id] = "interact"
            self.interact_triggered = True
            return True

        # Direct hit on Move or Aim stick always engages regardless of custom position
        if self.move_finger is None and self._hit_circle((x, y), self.move_base_default, self.stick_radius + 22):
            self.move_finger = finger_id
            self.move_base = self.move_base_default
            self._update_move((x, y))
            return True

        if self.aim_finger is None and self._hit_circle((x, y), self.aim_base_default, self.stick_radius + 22):
            self.aim_finger = finger_id
            self.aim_base = self.aim_base_default
            self._update_aim((x, y))
            return True

        vw = get_view_width()
        inv_left = vw // 2 - 236
        inv_right = vw // 2 + 236
        if self._layout_phone and inv_left <= x <= inv_right and y >= SCREEN_HEIGHT - 118:
            return False
        if not self._layout_phone and x >= vw - 420 and y >= SCREEN_HEIGHT - 118:
            return False

        if x < vw * 0.44 and 150 <= y <= SCREEN_HEIGHT - 6 and self.move_finger is None:
            self.move_finger = finger_id
            # Anchor move_base cleanly at move_base_default so the ring never jumps over seams or smears
            self.move_base = self.move_base_default
            self._update_move((x, y))
            return True

        if x >= vw * 0.56 and 150 <= y <= SCREEN_HEIGHT - 6 and self.aim_finger is None:
            self.aim_finger = finger_id
            self.aim_base = self.aim_base_default
            self._update_aim((x, y))
            return True

        return False

    def handle_finger_motion(self, finger_id, logical_pos):
        if not self.is_active():
            return False
        if finger_id == self.move_finger:
            self._update_move(logical_pos)
            return True
        if finger_id == self.aim_finger:
            self._update_aim(logical_pos)
            return True
        return finger_id in self.btn_fingers

    def handle_finger_up(self, finger_id):
        if finger_id == self.move_finger:
            self.move_finger = None
            self.move_base = self.move_base_default
            self.move_pos = self.move_base_default
            self.move_vec = (0.0, 0.0)
            return True
        if finger_id == self.aim_finger:
            self.aim_finger = None
            self.aim_base = self.aim_base_default
            self.aim_pos = self.aim_base_default
            self.aim_dir = (0, 0)
            return True
        action = self.btn_fingers.pop(finger_id, None)
        if action == "dash":
            self.dash_pressed = "dash" in self.btn_fingers.values()
            return True
        return action is not None

    def consume_actions(self):
        actions = {
            "jump": self.jump_triggered,
            "stealth": self.stealth_triggered,
            "bomb": self.bomb_triggered,
            "relic": self.relic_triggered,
            "melee": self.melee_triggered,
            "interact": self.interact_triggered,
            "pause": self.pause_triggered,
        }
        self.jump_triggered = False
        self.stealth_triggered = False
        self.bomb_triggered = False
        self.relic_triggered = False
        self.melee_triggered = False
        self.interact_triggered = False
        self.pause_triggered = False
        return actions

    # ---- Touch Layout Customizer API ----
    def cycle_preset(self):
        cur = str(GAME_SETTINGS.get("touch_layout_preset", "wide"))
        idx = (TOUCH_LAYOUT_PRESETS.index(cur) + 1) % len(TOUCH_LAYOUT_PRESETS) if cur in TOUCH_LAYOUT_PRESETS else 0
        nxt = TOUCH_LAYOUT_PRESETS[idx]
        GAME_SETTINGS["touch_layout_preset"] = nxt
        self.invalidate_layout()
        self._sync_layout()
        save_user_settings()
        return nxt

    def reset_custom_offsets(self):
        GAME_SETTINGS["touch_custom_offsets"] = {}
        GAME_SETTINGS["touch_layout_preset"] = "wide"
        self.customizer_drag_node = None
        self.invalidate_layout()
        self._sync_layout()
        save_user_settings()

    def get_customizer_nodes(self):
        self._sync_layout()
        return [
            ("move", "MOVE", (int(self.move_base_default[0]), int(self.move_base_default[1])), int(self.stick_radius)),
            ("aim", "AIM", (int(self.aim_base_default[0]), int(self.aim_base_default[1])), int(self.stick_radius)),
            ("dash", "TP", self.dash_center, self.dash_radius),
            ("jump", "JMP", self.jump_center, self.jump_radius),
            ("bomb", "BOMB", self.bomb_center, self.bomb_radius),
            ("stealth", "INV", self.stealth_center, self.stealth_radius),
            ("relic", "RELIC", self.relic_center, self.relic_radius),
            ("melee", "ATK", self.melee_center, self.melee_radius),
            ("interact", "TERM", self.interact_center, self.interact_radius),
            ("pause", "PAUSE", self.pause_center, self.pause_radius),
        ]

    def get_customizer_toolbar_rects(self):
        vw = get_view_width()
        pw, ph = min(840, vw - 28), 128
        px, py = vw // 2 - pw // 2, 16
        bw = (pw - 56) // 3
        by = py + 74
        return {
            "panel": pygame.Rect(px, py, pw, ph),
            "preset": pygame.Rect(px + 18, by, bw, 38),
            "reset": pygame.Rect(px + 28 + bw, by, bw, 38),
            "save": pygame.Rect(px + 38 + bw * 2, by, bw, 38),
        }

    def handle_customizer_pointer(self, event_type, pos):
        self._sync_layout()
        x, y = float(pos[0]), float(pos[1])
        tb = self.get_customizer_toolbar_rects()
        if event_type == "down":
            if tb["preset"].collidepoint(int(x), int(y)):
                self.cycle_preset()
                return "preset"
            if tb["reset"].collidepoint(int(x), int(y)):
                self.reset_custom_offsets()
                return "reset"
            if tb["save"].collidepoint(int(x), int(y)):
                save_user_settings()
                self.customizer_drag_node = None
                return "back"
            for nid, _, center, radius in reversed(self.get_customizer_nodes()):
                if math.hypot(x - center[0], y - center[1]) <= radius + 16:
                    self.customizer_drag_node = nid
                    self.customizer_drag_offset = (center[0] - x, center[1] - y)
                    if GAME_SETTINGS.get("touch_layout_preset") != "custom":
                        # Seed custom offsets from current positions across the entire screen
                        cur_map = {n: c for n, _, c, _ in self.get_customizer_nodes()}
                        offs = {}
                        vw = get_view_width()
                        radii_map = {n: r for n, _, _, r in self.get_customizer_nodes()}
                        for n, cur_c in cur_map.items():
                            base_c = self._base_centers.get(n, cur_c)
                            r = radii_map.get(n, 30)
                            cx_cl = clamp(cur_c[0], r, vw - r)
                            cy_cl = clamp(cur_c[1], r, SCREEN_HEIGHT - r)
                            offs[n] = [
                                round(cx_cl - base_c[0], 1),
                                round(cy_cl - base_c[1], 1),
                            ]
                        GAME_SETTINGS["touch_custom_offsets"] = offs
                        GAME_SETTINGS["touch_layout_preset"] = "custom"
                        self.invalidate_layout()
                        self._sync_layout()
                    return "drag"
            return None
        if event_type in ("move", "motion") and self.customizer_drag_node:
            nid = self.customizer_drag_node
            base_c = self._base_centers.get(nid, (x, y))
            nx = x + self.customizer_drag_offset[0]
            ny = y + self.customizer_drag_offset[1]
            vw = get_view_width()
            radii_map = {n: r for n, _, _, r in self.get_customizer_nodes()}
            r = radii_map.get(nid, 30)
            nx = clamp(nx, r, vw - r)
            ny = clamp(ny, r, SCREEN_HEIGHT - r)
            offs = GAME_SETTINGS.setdefault("touch_custom_offsets", {})
            if not isinstance(offs, dict):
                offs = {}
                GAME_SETTINGS["touch_custom_offsets"] = offs
            offs[nid] = [
                round(nx - base_c[0], 1),
                round(ny - base_c[1], 1),
            ]
            GAME_SETTINGS["touch_layout_preset"] = "custom"
            self.invalidate_layout()
            self._sync_layout()
            return "drag"
        if event_type == "up" and self.customizer_drag_node:
            self.customizer_drag_node = None
            save_user_settings()
            return "drop"
        return None

    def draw_customizer(self, screen, ui):
        from i18n import tr as _tr
        self._sync_layout()
        vw = get_view_width()
        screen.fill((10, 10, 11))
        for gx in range(40, vw, 64):
            pygame.draw.line(screen, (20, 20, 22), (gx, 0), (gx, SCREEN_HEIGHT), 1)
        for gy in range(40, SCREEN_HEIGHT, 64):
            pygame.draw.line(screen, (20, 20, 22), (0, gy), (vw, gy), 1)

        # Ghost HUD zone guide (bottom inventory area)
        phone = is_phone_layout(True)
        inv_rect = pygame.Rect(vw // 2 - 224, SCREEN_HEIGHT - 120, 448, 114) if phone else pygame.Rect(vw - 408, SCREEN_HEIGHT - 112, 394, 104)
        pygame.draw.rect(screen, (22, 22, 24), inv_rect, border_radius=10)
        pygame.draw.rect(screen, (64, 64, 68), inv_rect, 1, border_radius=10)
        blit_text_fitted(screen, inv_rect, ui.font_tiny, "HUD / ARTIFACTS", (110, 110, 116), pad_x=10)

        for nid, label, center, radius in self.get_customizer_nodes():
            is_drag = nid == self.customizer_drag_node
            if is_drag:
                pygame.draw.line(screen, (72, 72, 78), (center[0], 148), (center[0], SCREEN_HEIGHT), 1)
                pygame.draw.line(screen, (72, 72, 78), (0, center[1]), (vw, center[1]), 1)
            if nid in ("move", "aim"):
                ring = self._get_ring_surf(radius, is_drag)
                screen.blit(ring, (int(center[0] - ring.get_width() // 2), int(center[1] - ring.get_height() // 2)))
                knob = self._get_knob_surf(self.knob_radius, is_drag)
                screen.blit(knob, (int(center[0] - knob.get_width() // 2), int(center[1] - knob.get_height() // 2)))
            else:
                surf = self._get_btn_surf(radius, is_drag, True)
                screen.blit(surf, (int(center[0] - surf.get_width() // 2), int(center[1] - surf.get_height() // 2)))
            if is_drag:
                pygame.draw.circle(screen, (252, 252, 252), center, radius + 7, 2)
            lbl_s = fit_text_surf(ui.font_tiny, label, (14, 14, 14) if is_drag else (238, 238, 238), max(20, radius * 1.65))
            screen.blit(lbl_s, (int(center[0] - lbl_s.get_width() // 2), int(center[1] - lbl_s.get_height() // 2)))

        tb = self.get_customizer_toolbar_rects()
        pr = tb["panel"]
        screen.blit(get_panel_surf(pr.w, pr.h, fill_lum=14, fill_alpha=236, border_lum=126, radius=10), pr.topleft)
        blit_text_fitted(screen, pygame.Rect(pr.x + 16, pr.y + 8, pr.w - 32, 32), ui.font_big, _tr("touch_edit_title"), (244, 244, 244))
        blit_text_fitted(screen, pygame.Rect(pr.x + 16, pr.y + 42, pr.w - 32, 22), ui.font_tiny, _tr("touch_edit_hint"), (172, 172, 178))

        preset_key = f"touch_preset_{GAME_SETTINGS.get('touch_layout_preset', 'wide')}"
        btns = [
            ("preset", f"{_tr('settings_touch_preset')}: {_tr(preset_key)}"),
            ("reset", _tr("touch_edit_reset")),
            ("save", _tr("touch_edit_save")),
        ]
        for bkey, blbl in btns:
            rc = tb[bkey]
            pygame.draw.rect(screen, (30, 30, 34), rc, border_radius=6)
            pygame.draw.rect(screen, (156, 156, 162), rc, 1, border_radius=6)
            blit_text_fitted(screen, rc, ui.font_small, blbl, (242, 242, 242), pad_x=10)

    def _get_ring_surf(self, radius, active):
        key = (int(radius), bool(active))
        surf = self._ring_cache.get(key)
        if surf is not None:
            return surf
        r = int(radius)
        pad = 6
        s = (r + pad) * 2
        surf = pygame.Surface((s, s), pygame.SRCALPHA)
        cx = cy = r + pad
        fill_a = 138 if active else 96
        border_a = 210 if active else 128
        pygame.draw.circle(surf, (12, 12, 12, fill_a), (cx, cy), r)
        pygame.draw.circle(surf, (230, 230, 230, border_a), (cx, cy), r, 2)
        pygame.draw.circle(surf, (175, 175, 175, 48 if not active else 82), (cx, cy), int(r * 0.62), 1)
        for ang in (0, 90, 180, 270):
            rad = math.radians(ang)
            x1 = int(round(cx + math.cos(rad) * (r - 10)))
            y1 = int(round(cy + math.sin(rad) * (r - 10)))
            x2 = int(round(cx + math.cos(rad) * (r - 3)))
            y2 = int(round(cy + math.sin(rad) * (r - 3)))
            pygame.draw.line(surf, (220, 220, 220, 110 if not active else 185), (x1, y1), (x2, y2), 2)
        surf = _finalize_alpha_surf(surf)
        self._ring_cache[key] = surf
        return surf

    def _get_knob_surf(self, radius, active):
        key = (int(radius), bool(active))
        surf = self._knob_cache.get(key)
        if surf is not None:
            return surf
        r = int(radius)
        pad = 4
        s = (r + pad) * 2
        surf = pygame.Surface((s, s), pygame.SRCALPHA)
        cx = cy = r + pad
        pygame.draw.circle(surf, (240, 240, 240, 225 if active else 175), (cx, cy), r)
        pygame.draw.circle(surf, (24, 24, 24, 230), (cx, cy), max(2, r - 4))
        pygame.draw.circle(surf, (245, 245, 245, 210 if active else 155), (cx, cy), max(2, r - 7))
        surf = _finalize_alpha_surf(surf)
        self._knob_cache[key] = surf
        return surf

    def _get_btn_surf(self, radius, active, ready=True):
        key = (int(radius), bool(active), bool(ready))
        surf = self._btn_cache.get(key)
        if surf is not None:
            return surf
        r = int(radius)
        pad = 6
        s = (r + pad) * 2
        surf = pygame.Surface((s, s), pygame.SRCALPHA)
        cx = cy = r + pad
        if active:
            fill = (242, 242, 242, 205)
            border = (255, 255, 255, 245)
        elif ready:
            fill = (14, 14, 14, 138)
            border = (224, 224, 224, 175)
        else:
            fill = (12, 12, 12, 92)
            border = (118, 118, 118, 110)
        pygame.draw.circle(surf, fill, (cx, cy), r)
        pygame.draw.circle(surf, border, (cx, cy), r, 2)
        surf = _finalize_alpha_surf(surf)
        self._btn_cache[key] = surf
        return surf

    def _get_bomb_icon_surf(self, active, ready):
        key = (bool(active), bool(ready))
        surf = self._bomb_icon_cache.get(key)
        if surf is not None:
            return surf
        surf = pygame.Surface((32, 32), pygame.SRCALPHA)
        cx = cy = 16
        bfg = (14, 14, 14) if active else ((240, 240, 240) if ready else (128, 128, 128))
        draw_aa_circle(surf, (*bfg, 255), cx - 1, cy + 2, 8)
        pygame.draw.line(surf, (*bfg, 255), (cx + 4, cy - 5), (cx + 9, cy - 10), 2)
        spark = (255, 255, 255) if ready else bfg
        draw_aa_circle(surf, (*spark, 255), cx + 10, cy - 11, 2)
        surf = _finalize_alpha_surf(surf)
        self._bomb_icon_cache[key] = surf
        return surf

    def _get_bomb_badge_surf(self, ready):
        key = bool(ready)
        surf = self._bomb_badge_cache.get(key)
        if surf is not None:
            return surf
        surf = pygame.Surface((22, 22), pygame.SRCALPHA)
        draw_aa_circle(surf, (14, 14, 14, 255), 11, 11, 9)
        rim = (190, 190, 190, 255) if ready else (95, 95, 95, 255)
        draw_aa_ring(surf, rim, 11, 11, 9, 1)
        surf = _finalize_alpha_surf(surf)
        self._bomb_badge_cache[key] = surf
        return surf

    def draw(self, screen, player, ui, near_terminal=False):
        self._sync_layout()
        if not self.is_active():
            return

        # Left Move Stick
        m_active = self.move_finger is not None
        m_ring = self._get_ring_surf(self.stick_radius, m_active)
        screen.blit(m_ring, (int(self.move_base[0] - m_ring.get_width() // 2), int(self.move_base[1] - m_ring.get_height() // 2)))
        m_knob = self._get_knob_surf(self.knob_radius, m_active)
        screen.blit(m_knob, (int(self.move_pos[0] - m_knob.get_width() // 2), int(self.move_pos[1] - m_knob.get_height() // 2)))

        # Right Aim Stick
        a_active = self.aim_finger is not None
        a_ring = self._get_ring_surf(self.stick_radius, a_active)
        screen.blit(a_ring, (int(self.aim_base[0] - a_ring.get_width() // 2), int(self.aim_base[1] - a_ring.get_height() // 2)))
        if self.aim_dir != (0, 0):
            ax_d, ay_d = self.aim_dir
            ang = math.atan2(-ay_d, ax_d)
            rect = pygame.Rect(
                int(self.aim_base[0] - self.stick_radius),
                int(self.aim_base[1] - self.stick_radius),
                int(self.stick_radius * 2),
                int(self.stick_radius * 2),
            )
            pygame.draw.arc(screen, (255, 255, 255, 235), rect, ang - 0.55, ang + 0.55, 4)
        a_knob = self._get_knob_surf(self.knob_radius, a_active)
        screen.blit(a_knob, (int(self.aim_pos[0] - a_knob.get_width() // 2), int(self.aim_pos[1] - a_knob.get_height() // 2)))

        # Dash Button
        dash_ready = player.dash_cd <= 0.0
        dash_active = "dash" in self.btn_fingers.values()
        d_surf = self._get_btn_surf(self.dash_radius, dash_active, dash_ready)
        dcx, dcy = self.dash_center
        screen.blit(d_surf, (dcx - d_surf.get_width() // 2, dcy - d_surf.get_height() // 2))
        if not dash_ready and player.dash_max_cd > 0:
            prog = clamp(1.0 - player.dash_cd / player.dash_max_cd, 0.0, 1.0)
            arc_r = self.dash_radius - 3
            pygame.draw.arc(
                screen,
                (235, 235, 235, 210),
                pygame.Rect(dcx - arc_r, dcy - arc_r, arc_r * 2, arc_r * 2),
                math.pi * 0.5,
                math.pi * 0.5 + math.pi * 2.0 * prog,
                2,
            )
        fg = (14, 14, 14) if dash_active else ((242, 242, 242) if dash_ready else (140, 140, 140))
        pygame.draw.lines(screen, fg, False, [(dcx - 8, dcy - 6), (dcx - 1, dcy), (dcx - 8, dcy + 6)], 2)
        pygame.draw.lines(screen, fg, False, [(dcx + 1, dcy - 6), (dcx + 8, dcy), (dcx + 1, dcy + 6)], 2)
        tp_lbl = fit_text_surf(ui.font_tiny, "TP", (215, 215, 215) if dash_ready else (120, 120, 120), self.dash_radius * 1.45)
        screen.blit(tp_lbl, (dcx - tp_lbl.get_width() // 2, dcy + self.dash_radius - tp_lbl.get_height() - 2))

        # Jump / Slam Button
        jump_cd = getattr(player, "jump_cd", 0.0)
        jump_max = getattr(player, "jump_max_cd", 120.0)
        jump_ready = jump_cd <= 0.0 and getattr(player, "air_z", 0.0) <= 0.0
        jump_active = "jump" in self.btn_fingers.values()
        j_surf = self._get_btn_surf(self.jump_radius, jump_active, jump_ready)
        jcx, jcy = self.jump_center
        screen.blit(j_surf, (jcx - j_surf.get_width() // 2, jcy - j_surf.get_height() // 2))
        if not jump_ready and jump_max > 0:
            jprog = clamp(1.0 - jump_cd / jump_max, 0.0, 1.0)
            arc_r = self.jump_radius - 3
            pygame.draw.arc(
                screen,
                (235, 235, 235, 210),
                pygame.Rect(jcx - arc_r, jcy - arc_r, arc_r * 2, arc_r * 2),
                math.pi * 0.5,
                math.pi * 0.5 + math.pi * 2.0 * jprog,
                2,
            )
        jfg = (14, 14, 14) if jump_active else ((242, 242, 242) if jump_ready else (140, 140, 140))
        pygame.draw.lines(screen, jfg, False, [(jcx - 6, jcy + 1), (jcx, jcy - 7), (jcx + 6, jcy + 1)], 2)
        pygame.draw.line(screen, jfg, (jcx - 8, jcy + 6), (jcx + 8, jcy + 6), 2)
        jmp_lbl = fit_text_surf(ui.font_tiny, "JMP", (215, 215, 215) if jump_ready else (120, 120, 120), self.jump_radius * 1.45)
        screen.blit(jmp_lbl, (jcx - jmp_lbl.get_width() // 2, jcy + self.jump_radius - jmp_lbl.get_height() - 2))

        # Melee Cleave Button
        melee_cd = getattr(player, "melee_cd", 0.0)
        melee_max = max(1.0, getattr(player, "melee_max_cd", 26.0))
        melee_ready = melee_cd <= 0.0
        melee_active = "melee" in self.btn_fingers.values()
        m_surf = self._get_btn_surf(self.melee_radius, melee_active, melee_ready)
        mcx, mcy = self.melee_center
        screen.blit(m_surf, (mcx - m_surf.get_width() // 2, mcy - m_surf.get_height() // 2))
        if not melee_ready:
            mprog = clamp(1.0 - melee_cd / melee_max, 0.0, 1.0)
            arc_r = self.melee_radius - 3
            pygame.draw.arc(
                screen,
                (235, 235, 235, 210),
                pygame.Rect(mcx - arc_r, mcy - arc_r, arc_r * 2, arc_r * 2),
                math.pi * 0.5,
                math.pi * 0.5 + math.pi * 2.0 * mprog,
                2,
            )
        mfg = (14, 14, 14) if melee_active else ((246, 246, 246) if melee_ready else (140, 140, 140))
        pygame.draw.arc(
            screen,
            mfg,
            pygame.Rect(mcx - 10, mcy - 11, 20, 18),
            -0.3,
            2.35,
            3,
        )
        pygame.draw.line(screen, mfg, (mcx - 7, mcy + 5), (mcx + 6, mcy - 8), 2)
        atk_lbl = fit_text_surf(ui.font_tiny, "ATK", (220, 220, 220) if melee_ready else (120, 120, 120), self.melee_radius * 1.45)
        screen.blit(atk_lbl, (mcx - atk_lbl.get_width() // 2, mcy + self.melee_radius - atk_lbl.get_height() - 2))

        # Bomb Button
        bomb_cd = getattr(player, "bomb_cd", 0.0)
        bomb_max = max(1.0, getattr(player, "bomb_max_cd", 75.0))
        bomb_ready = player.bombs > 0 and bomb_cd <= 0.0
        bomb_active = "bomb" in self.btn_fingers.values()
        b_surf = self._get_btn_surf(self.bomb_radius, bomb_active, bomb_ready)
        bcx, bcy = self.bomb_center
        screen.blit(b_surf, (bcx - b_surf.get_width() // 2, bcy - b_surf.get_height() // 2))
        if player.bombs > 0 and bomb_cd > 0.0:
            bprog = clamp(1.0 - bomb_cd / bomb_max, 0.0, 1.0)
            arc_r = self.bomb_radius - 3
            pygame.draw.arc(
                screen,
                (235, 235, 235, 210),
                pygame.Rect(bcx - arc_r, bcy - arc_r, arc_r * 2, arc_r * 2),
                math.pi * 0.5,
                math.pi * 0.5 + math.pi * 2.0 * bprog,
                2,
            )
        b_icon = self._get_bomb_icon_surf(bomb_active, bomb_ready)
        screen.blit(b_icon, (bcx - 16, bcy - 16))
        badge = self._get_bomb_badge_surf(bomb_ready)
        screen.blit(badge, (bcx + 18 - 11, bcy + 16 - 11))
        cnt_lbl = fit_text_surf(ui.font_tiny, str(player.bombs), (245, 245, 245) if bomb_ready else (140, 140, 140), 18)
        screen.blit(cnt_lbl, (bcx + 18 - cnt_lbl.get_width() // 2, bcy + 16 - cnt_lbl.get_height() // 2))

        # Stealth / Invisibility Button
        inv_t = getattr(player, "invis_timer", 0.0)
        inv_cd = getattr(player, "invis_cd", 0.0)
        inv_max = max(1.0, getattr(player, "invis_max_cd", 360.0))
        inv_ready = inv_cd <= 0.0 or inv_t > 0.0
        inv_pressed = "stealth" in self.btn_fingers.values()
        s_surf = self._get_btn_surf(self.stealth_radius, inv_pressed or inv_t > 0.0, inv_ready)
        scx, scy = self.stealth_center
        screen.blit(s_surf, (scx - s_surf.get_width() // 2, scy - s_surf.get_height() // 2))
        if inv_t > 0.0:
            iprog = clamp(inv_t / 135.0, 0.0, 1.0)
            arc_r = self.stealth_radius - 3
            pygame.draw.arc(
                screen,
                (16, 16, 16, 235),
                pygame.Rect(scx - arc_r, scy - arc_r, arc_r * 2, arc_r * 2),
                math.pi * 0.5,
                math.pi * 0.5 + math.pi * 2.0 * iprog,
                3,
            )
        elif not inv_ready:
            iprog = clamp(1.0 - inv_cd / inv_max, 0.0, 1.0)
            arc_r = self.stealth_radius - 3
            pygame.draw.arc(
                screen,
                (235, 235, 235, 210),
                pygame.Rect(scx - arc_r, scy - arc_r, arc_r * 2, arc_r * 2),
                math.pi * 0.5,
                math.pi * 0.5 + math.pi * 2.0 * iprog,
                2,
            )
        sfg = (14, 14, 14) if (inv_pressed or inv_t > 0.0) else ((242, 242, 242) if inv_ready else (140, 140, 140))
        pygame.draw.ellipse(screen, sfg, pygame.Rect(scx - 10, scy - 8, 20, 11), 2)
        pygame.draw.circle(screen, sfg, (scx, scy - 2), 3)
        pygame.draw.line(screen, sfg, (scx - 9, scy + 4), (scx + 9, scy - 9), 2)
        from i18n import tr as _tr
        inv_lbl = fit_text_surf(ui.font_tiny, _tr("touch_inv"), (14, 14, 14) if inv_t > 0.0 else ((215, 215, 215) if inv_ready else (120, 120, 120)), self.stealth_radius * 1.45)
        screen.blit(inv_lbl, (scx - inv_lbl.get_width() // 2, scy + self.stealth_radius - inv_lbl.get_height() - 2))

        # Relic Button
        has_relic = player.active_item is not None
        relic_ready = has_relic and player.active_charge >= player.max_charge
        relic_active = "relic" in self.btn_fingers.values()
        r_surf = self._get_btn_surf(self.relic_radius, relic_active, relic_ready)
        rcx, rcy = self.relic_center
        screen.blit(r_surf, (rcx - r_surf.get_width() // 2, rcy - r_surf.get_height() // 2))
        if has_relic and not relic_ready and player.max_charge > 0:
            rprog = clamp(player.active_charge / float(player.max_charge), 0.0, 1.0)
            arc_r = self.relic_radius - 3
            pygame.draw.arc(
                screen,
                (220, 220, 220, 195),
                pygame.Rect(rcx - arc_r, rcy - arc_r, arc_r * 2, arc_r * 2),
                math.pi * 0.5,
                math.pi * 0.5 + math.pi * 2.0 * rprog,
                2,
            )
        rfg = (14, 14, 14) if relic_active else ((248, 248, 248) if relic_ready else (145, 145, 145))
        pygame.draw.polygon(
            screen,
            rfg,
            [(rcx, rcy - 10), (rcx + 9, rcy), (rcx, rcy + 10), (rcx - 9, rcy)],
            0 if relic_ready else 2,
        )

        # Terminal / Interact Button
        int_ready = bool(near_terminal)
        int_active = "interact" in self.btn_fingers.values()
        i_surf = self._get_btn_surf(self.interact_radius, int_active, int_ready)
        icx, icy = self.interact_center
        screen.blit(i_surf, (icx - i_surf.get_width() // 2, icy - i_surf.get_height() // 2))
        if int_ready and not int_active:
            pygame.draw.circle(screen, (246, 246, 246), (icx, icy), self.interact_radius + 3, 1)
        ifg = (14, 14, 14) if int_active else ((248, 248, 248) if int_ready else (136, 136, 136))
        pygame.draw.rect(screen, ifg, (icx - 9, icy - 10, 18, 13), 2, border_radius=2)
        pygame.draw.line(screen, ifg, (icx - 5, icy - 5), (icx - 2, icy - 3), 2)
        pygame.draw.line(screen, ifg, (icx - 5, icy - 1), (icx - 2, icy - 3), 2)
        pygame.draw.line(screen, ifg, (icx, icy - 2), (icx + 5, icy - 2), 2)
        use_lbl = fit_text_surf(ui.font_tiny, _tr("touch_use"), (236, 236, 236) if int_ready else (126, 126, 126), self.interact_radius * 1.55)
        screen.blit(use_lbl, (icx - use_lbl.get_width() // 2, icy + self.interact_radius - use_lbl.get_height() - 2))

        # Pause Button (Top-Right)
        p_active = "pause" in self.btn_fingers.values()
        p_surf = self._get_btn_surf(self.pause_radius, p_active, True)
        pcx, pcy = self.pause_center
        screen.blit(p_surf, (pcx - p_surf.get_width() // 2, pcy - p_surf.get_height() // 2))
        pfg = (14, 14, 14) if p_active else (238, 238, 238)
        pygame.draw.rect(screen, pfg, (pcx - 6, pcy - 7, 4, 14), border_radius=1)
        pygame.draw.rect(screen, pfg, (pcx + 2, pcy - 7, 4, 14), border_radius=1)
