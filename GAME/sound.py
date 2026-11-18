import array
import math
import os
import random
import time
import pygame
from settings import GAME_SETTINGS, clamp

COMPUTER_TRACKS = [
    {"id": "signal_01", "i18n": "comp_track_0", "bpm": 92.0},
    {"id": "ash_fm", "i18n": "comp_track_1", "bpm": 112.0},
    {"id": "crypt_84", "i18n": "comp_track_2", "bpm": 104.0},
    {"id": "eclipse_wav", "i18n": "comp_track_3", "bpm": 78.0},
]


class SoundBank:
    def __init__(self):
        self.sounds = {}
        self.enabled = False
        self._last_play = {}
        self._music_tracks = {}
        self._computer_tracks = {}
        self._music_channel = None
        self._computer_channel = None
        self._music_mode = "none"
        self._computer_track_idx = -1
        self._computer_playing = False
        self._sample_rate = 22050
        self._mixer_channels = 2
        try:
            if not pygame.mixer.get_init():
                try:
                    pygame.mixer.init(frequency=self._sample_rate, size=-16, channels=2, buffer=512)
                except Exception:
                    pygame.mixer.init(frequency=self._sample_rate, size=-16, channels=1, buffer=512)
            init_info = pygame.mixer.get_init()
            if init_info and len(init_info) >= 3:
                self._sample_rate = int(init_info[0]) or 22050
                self._mixer_channels = max(1, int(init_info[2]))
            try:
                if hasattr(pygame.mixer, "set_num_channels"):
                    pygame.mixer.set_num_channels(16)
                if hasattr(pygame.mixer, "set_reserved"):
                    pygame.mixer.set_reserved(2)
                if hasattr(pygame.mixer, "Channel"):
                    self._music_channel = pygame.mixer.Channel(0)
                    self._computer_channel = pygame.mixer.Channel(1)
            except Exception:
                self._music_channel = None
                self._computer_channel = None
            self.enabled = True
            self._build_all()
        except Exception:
            self.enabled = False

    def _samples_to_sound(self, mono_buf):
        if self._mixer_channels >= 2:
            st = array.array("h")
            for s in mono_buf:
                st.append(s)
                st.append(s)
            return pygame.mixer.Sound(buffer=st.tobytes())
        return pygame.mixer.Sound(buffer=mono_buf.tobytes())

    def _synth(
        self,
        duration,
        freq_start,
        freq_end,
        volume=0.22,
        wave="sine",
        noise=0.0,
        harmonics=None,
        attack=0.02,
        decay_pow=1.5,
        vib_hz=0.0,
        vib_depth=0.0,
        sub_mix=0.0,
        lp_alpha=1.0,
    ):
        sr = self._sample_rate
        n = max(1, int(sr * duration))
        buf = array.array("h")
        phase = 0.0
        sub_phase = 0.0
        two_pi = 2.0 * math.pi
        inv_sr = 1.0 / sr
        inv_n = 1.0 / n
        atk_n = max(1, int(n * attack))
        lp_state = 0.0
        rng = random.Random(int((freq_start * 13.0 + freq_end * 7.0 + duration * 1000.0)))
        harms = harmonics or ()

        for i in range(n):
            t = i * inv_n
            freq = freq_start + (freq_end - freq_start) * t
            if vib_hz > 0.0:
                freq *= 1.0 + math.sin(two_pi * vib_hz * (i * inv_sr)) * vib_depth
            if freq < 20.0:
                freq = 20.0
            phase += two_pi * freq * inv_sr
            if wave == "square":
                val = 1.0 if math.sin(phase) >= 0.0 else -1.0
            elif wave == "saw":
                val = 2.0 * ((phase / two_pi) % 1.0) - 1.0
            elif wave == "tri":
                p = (phase / two_pi) % 1.0
                val = 4.0 * p - 1.0 if p < 0.5 else 3.0 - 4.0 * p
            else:
                val = math.sin(phase)

            for mult, amp in harms:
                val += math.sin(phase * mult) * amp

            if sub_mix > 0.0:
                sub_phase += two_pi * (freq * 0.5) * inv_sr
                val = val * (1.0 - sub_mix) + math.sin(sub_phase) * sub_mix

            if noise > 0.0:
                nz = rng.uniform(-1.0, 1.0)
                val = val * (1.0 - noise) + nz * noise

            if lp_alpha < 0.999:
                lp_state += lp_alpha * (val - lp_state)
                val = lp_state

            if i < atk_n:
                env = i / float(atk_n)
            else:
                rem = max(0.0, 1.0 - (i - atk_n) / float(max(1, n - atk_n)))
                env = rem ** decay_pow

            out = math.tanh(val * 1.15) * env * volume
            sample = max(-32767, min(32767, int(out * 32767.0)))
            buf.append(sample)
        return self._samples_to_sound(buf)

    def _synth_chord(self, notes, duration, volume=0.22, wave="tri", arpeggio_step=0.0):
        sr = self._sample_rate
        n = max(1, int(sr * duration))
        buf = array.array("h")
        two_pi = 2.0 * math.pi
        inv_sr = 1.0 / sr
        phases = [0.0] * len(notes)
        starts = [int(sr * arpeggio_step * idx) for idx in range(len(notes))]
        scale = 1.0 / max(1.0, len(notes) * 0.72)

        for i in range(n):
            val = 0.0
            for idx, freq in enumerate(notes):
                st = starts[idx]
                if i < st:
                    continue
                local_t = (i - st) / float(max(1, n - st))
                phases[idx] += two_pi * freq * inv_sr
                ph = phases[idx]
                if wave == "tri":
                    p = (ph / two_pi) % 1.0
                    s = 4.0 * p - 1.0 if p < 0.5 else 3.0 - 4.0 * p
                elif wave == "saw":
                    s = 2.0 * ((ph / two_pi) % 1.0) - 1.0
                else:
                    s = math.sin(ph)
                s += 0.25 * math.sin(ph * 2.0)
                local_atk = min(1.0, (i - st) / max(1.0, sr * 0.015))
                local_env = local_atk * ((1.0 - local_t) ** 1.35)
                val += s * local_env
            out = math.tanh(val * scale * 1.1) * volume
            buf.append(max(-32767, min(32767, int(out * 32767.0))))
        return self._samples_to_sound(buf)

    def _build_music_track(self, mode):
        cached = self._music_tracks.get(mode)
        if cached is not None:
            return cached
        sr = self._sample_rate
        two_pi = 2.0 * math.pi
        inv_sr = 1.0 / sr

        if mode == "menu":
            bpm = 84.0
            steps = 16
            step_dur = 60.0 / bpm * 0.5
            dur = steps * step_dur
            bass_seq = [73.42, 73.42, 65.41, 65.41, 58.27, 58.27, 65.41, 55.00]
            arp_seq = [293.66, 349.23, 440.00, 349.23, 261.63, 329.63, 392.00, 329.63,
                       233.08, 293.66, 349.23, 293.66, 220.00, 277.18, 329.63, 277.18]
            vol = 0.14
        elif mode == "boss":
            bpm = 136.0
            steps = 16
            step_dur = 60.0 / bpm * 0.5
            dur = steps * step_dur
            bass_seq = [73.42, 73.42, 77.78, 73.42, 65.41, 65.41, 69.30, 55.00]
            arp_seq = [293.66, 311.13, 349.23, 440.00, 466.16, 440.00, 349.23, 311.13,
                       293.66, 440.00, 466.16, 523.25, 440.00, 349.23, 311.13, 277.18]
            vol = 0.15
        else:
            bpm = 108.0
            steps = 16
            step_dur = 60.0 / bpm * 0.5
            dur = steps * step_dur
            bass_seq = [65.41, 65.41, 77.78, 77.78, 58.27, 58.27, 61.74, 49.00]
            arp_seq = [261.63, 311.13, 392.00, 311.13, 261.63, 349.23, 392.00, 311.13,
                       233.08, 293.66, 349.23, 293.66, 246.94, 293.66, 392.00, 293.66]
            vol = 0.13

        n = max(1, int(sr * dur))
        step_n = max(1, n // steps)
        buf = array.array("h")
        p_bass = 0.0
        p_arp = 0.0
        p_pad = 0.0
        p_kick = 0.0
        lp = 0.0

        for i in range(n):
            s_idx = min(steps - 1, i // step_n)
            local_t = (i % step_n) / float(step_n)
            b_freq = bass_seq[(s_idx // 2) % len(bass_seq)]
            a_freq = arp_seq[s_idx % len(arp_seq)]

            p_bass += two_pi * b_freq * inv_sr
            p_arp += two_pi * a_freq * inv_sr
            p_pad += two_pi * (b_freq * 2.0) * inv_sr

            bp = (p_bass / two_pi) % 1.0
            bass_val = (4.0 * bp - 1.0 if bp < 0.5 else 3.0 - 4.0 * bp) * 0.65 + math.sin(p_bass * 0.5) * 0.35
            bass_env = 0.55 + 0.45 * ((1.0 - local_t) ** 1.2)

            arp_atk = min(1.0, local_t * 14.0)
            arp_env = arp_atk * ((1.0 - local_t) ** (1.7 if mode != "menu" else 2.1))
            arp_val = (math.sin(p_arp) * 0.72 + math.sin(p_arp * 2.0) * 0.20 + math.sin(p_arp * 3.0) * 0.08) * arp_env

            pad_val = (math.sin(p_pad) * 0.6 + math.sin(p_pad * 1.498) * 0.4) * 0.24

            kick_val = 0.0
            if (mode == "boss" and s_idx % 2 == 0) or (mode == "combat" and s_idx % 4 == 0) or (mode == "menu" and s_idx % 8 == 0):
                if local_t < 0.42:
                    kt = local_t / 0.42
                    k_freq = 95.0 - 58.0 * kt
                    p_kick += two_pi * k_freq * inv_sr
                    kick_val = math.sin(p_kick) * ((1.0 - kt) ** 2.2) * (0.42 if mode == "boss" else 0.28)
                else:
                    p_kick = 0.0

            raw = bass_val * bass_env * 0.50 + arp_val * 0.42 + pad_val + kick_val
            lp += 0.28 * (raw - lp)
            edge = 1.0
            fade_n = 132
            if i < fade_n:
                edge = i / float(fade_n)
            elif i > n - fade_n:
                edge = (n - i) / float(fade_n)

            out = math.tanh(lp * 1.1) * vol * edge
            buf.append(max(-32767, min(32767, int(out * 32767.0))))

        snd = self._samples_to_sound(buf)
        self._music_tracks[mode] = snd
        return snd

    def _build_computer_track(self, track_idx):
        idx = int(track_idx) % len(COMPUTER_TRACKS)
        cached = self._computer_tracks.get(idx)
        if cached is not None:
            return cached

        meta = COMPUTER_TRACKS[idx]
        audio_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio")
        for ext in (".ogg", ".wav", ".mp3"):
            cand = os.path.join(audio_dir, meta["id"] + ext)
            if os.path.exists(cand):
                try:
                    snd = pygame.mixer.Sound(cand)
                    self._computer_tracks[idx] = snd
                    return snd
                except Exception:
                    pass

        sr = self._sample_rate
        two_pi = 2.0 * math.pi
        inv_sr = 1.0 / sr
        rng = random.Random(9001 + idx * 173)

        if idx == 0:
            # SIGNAL-01 (Noir Tape): lo-fi moody electric synth in A minor
            bpm = 92.0
            steps = 32
            step_dur = 60.0 / bpm * 0.5
            bass_seq = [110.00, 110.00, 87.31, 87.31, 98.00, 98.00, 82.41, 98.00]
            lead_seq = [
                440.00, 523.25, 659.25, 523.25, 440.00, 0.0, 392.00, 440.00,
                349.23, 440.00, 523.25, 440.00, 392.00, 493.88, 587.33, 493.88,
                329.63, 440.00, 523.25, 659.25, 587.33, 523.25, 440.00, 392.00,
                329.63, 392.00, 493.88, 392.00, 349.23, 392.00, 440.00, 0.0,
            ]
            lead_wave = "sine"
            vol = 0.23
            lp_k = 0.24
        elif idx == 1:
            # ASH FM (Deep Pulse): driving synthwave in C# minor
            bpm = 112.0
            steps = 32
            step_dur = 60.0 / bpm * 0.5
            bass_seq = [69.30, 69.30, 82.41, 82.41, 61.74, 61.74, 73.42, 65.41]
            lead_seq = [
                277.18, 329.63, 415.30, 554.37, 415.30, 329.63, 415.30, 493.88,
                329.63, 415.30, 493.88, 659.25, 493.88, 415.30, 369.99, 329.63,
                246.94, 329.63, 369.99, 493.88, 369.99, 329.63, 293.66, 246.94,
                277.18, 369.99, 440.00, 554.37, 440.00, 369.99, 329.63, 277.18,
            ]
            lead_wave = "saw"
            vol = 0.22
            lp_k = 0.30
        elif idx == 2:
            # CRYPT-84 (Synth Arp): retro dark chiptune in E minor
            bpm = 104.0
            steps = 32
            step_dur = 60.0 / bpm * 0.5
            bass_seq = [82.41, 82.41, 98.00, 98.00, 73.42, 73.42, 65.41, 73.42]
            lead_seq = [
                329.63, 392.00, 493.88, 659.25, 587.33, 493.88, 392.00, 493.88,
                392.00, 493.88, 587.33, 783.99, 659.25, 587.33, 493.88, 392.00,
                293.66, 369.99, 440.00, 587.33, 493.88, 440.00, 369.99, 293.66,
                261.63, 329.63, 392.00, 523.25, 493.88, 392.00, 329.63, 246.94,
            ]
            lead_wave = "square"
            vol = 0.21
            lp_k = 0.34
        else:
            # ECLIPSE.WAV (Echo): haunting tape-bell ambient in F minor
            bpm = 78.0
            steps = 32
            step_dur = 60.0 / bpm * 0.5
            bass_seq = [87.31, 87.31, 77.78, 77.78, 69.30, 69.30, 65.41, 77.78]
            lead_seq = [
                349.23, 0.0, 523.25, 415.30, 349.23, 0.0, 622.25, 523.25,
                311.13, 0.0, 466.16, 392.00, 311.13, 0.0, 523.25, 466.16,
                277.18, 0.0, 415.30, 349.23, 277.18, 0.0, 466.16, 415.30,
                261.63, 349.23, 415.30, 523.25, 415.30, 349.23, 261.63, 0.0,
            ]
            lead_wave = "tri"
            vol = 0.24
            lp_k = 0.26

        dur = steps * step_dur
        n = max(1, int(sr * dur))
        step_n = max(1, n // steps)
        buf = array.array("h")
        p_bass = 0.0
        p_lead = 0.0
        p_harm = 0.0
        p_pad = 0.0
        p_kick = 0.0
        lp = 0.0
        echo_delay = int(sr * step_dur * 1.5)
        echo_buf = [0.0] * max(1, echo_delay)
        echo_pos = 0

        for i in range(n):
            s_idx = min(steps - 1, i // step_n)
            local_t = (i % step_n) / float(step_n)
            b_freq = bass_seq[(s_idx // 4) % len(bass_seq)]
            l_freq = lead_seq[s_idx % len(lead_seq)]
            wow = 1.0 + (0.0032 * math.sin(two_pi * 0.55 * (i * inv_sr)) if idx in (0, 3) else 0.0)

            p_bass += two_pi * b_freq * wow * inv_sr
            p_pad += two_pi * (b_freq * 2.0) * inv_sr

            bp = (p_bass / two_pi) % 1.0
            bass_val = (4.0 * bp - 1.0 if bp < 0.5 else 3.0 - 4.0 * bp) * 0.65 + math.sin(p_bass * 0.5) * 0.35
            bass_env = 0.45 + 0.55 * ((1.0 - local_t) ** 1.15)

            lead_val = 0.0
            if l_freq > 1.0:
                p_lead += two_pi * l_freq * wow * inv_sr
                p_harm += two_pi * (l_freq * 1.498) * wow * inv_sr
                l_atk = min(1.0, local_t * 16.0)
                l_env = l_atk * ((1.0 - local_t) ** 1.45)
                if lead_wave == "square":
                    lv = (1.0 if math.sin(p_lead) >= 0.0 else -1.0) * 0.55 + math.sin(p_lead) * 0.45
                elif lead_wave == "saw":
                    lv = (2.0 * ((p_lead / two_pi) % 1.0) - 1.0) * 0.62 + math.sin(p_lead * 0.5) * 0.38
                elif lead_wave == "tri":
                    tp = (p_lead / two_pi) % 1.0
                    lv = (4.0 * tp - 1.0 if tp < 0.5 else 3.0 - 4.0 * tp) * 0.7 + math.sin(p_lead * 2.0) * 0.25
                else:
                    lv = math.sin(p_lead) * 0.72 + math.sin(p_lead * 2.0) * 0.22 + math.sin(p_lead * 3.0) * 0.06
                lead_val = (lv + math.sin(p_harm) * 0.16) * l_env

            pad_val = (math.sin(p_pad) * 0.6 + math.sin(p_pad * 1.25) * 0.4) * 0.22

            # Soft snare / hihat & kick groove
            perc = 0.0
            if s_idx % 4 == 0 and local_t < 0.45:
                kt = local_t / 0.45
                p_kick += two_pi * (102.0 - 62.0 * kt) * inv_sr
                perc += math.sin(p_kick) * ((1.0 - kt) ** 2.2) * 0.34
            else:
                p_kick = 0.0
            if (s_idx % 4 == 2 or s_idx % 2 == 1) and local_t < 0.20:
                hat_amp = 0.12 if s_idx % 4 == 2 else 0.055
                perc += rng.uniform(-1.0, 1.0) * ((1.0 - local_t / 0.20) ** 2.6) * hat_amp

            delayed = echo_buf[echo_pos]
            dry = lead_val * 0.52 + delayed * 0.34
            echo_buf[echo_pos] = dry * 0.75
            echo_pos = (echo_pos + 1) % len(echo_buf)

            tape_hiss = rng.uniform(-1.0, 1.0) * (0.012 if idx in (0, 3) else 0.004)
            raw = bass_val * bass_env * 0.44 + dry + pad_val + perc + tape_hiss
            lp += lp_k * (raw - lp)

            edge = 1.0
            fade_n = 160
            if i < fade_n:
                edge = i / float(fade_n)
            elif i > n - fade_n:
                edge = (n - i) / float(fade_n)

            out = math.tanh(lp * 1.15) * vol * edge
            buf.append(max(-32767, min(32767, int(out * 32767.0))))

        snd = self._samples_to_sound(buf)
        self._computer_tracks[idx] = snd
        return snd

    def update_music(self, mode="none"):
        if not self.enabled:
            return
        want_on = bool(GAME_SETTINGS.get("sound_enabled", True)) and bool(GAME_SETTINGS.get("music_enabled", True))
        target = mode if (want_on and mode in ("menu", "combat", "boss")) else "none"
        m_track = int(GAME_SETTINGS.get("music_track", 0))

        def _get_track():
            if m_track > 0 and target != "none":
                return self._build_computer_track(m_track - 1)
            return self._build_music_track(target)

        if target == self._music_mode:
            if target != "none" and self._music_channel is not None:
                try:
                    if hasattr(self._music_channel, "get_busy") and not self._music_channel.get_busy():
                        trk = _get_track()
                        self._music_channel.play(trk, loops=-1)
                except Exception:
                    pass
            return
        self._music_mode = target
        if self._music_channel is None:
            return
        try:
            self._music_channel.stop()
            if target != "none":
                trk = _get_track()
                self._music_channel.play(trk, loops=-1)
                self._music_channel.set_volume(1.0, 1.0)
        except Exception:
            pass

    def stop_computer_audio(self):
        if self._computer_playing and self._computer_channel is not None:
            try:
                self._computer_channel.stop()
            except Exception:
                pass
        self._computer_playing = False
        self._computer_track_idx = -1
        if self._music_channel is not None:
            try:
                self._music_channel.set_volume(1.0, 1.0)
            except Exception:
                pass

    def compute_spatial_mix(self, comp_x, comp_y, listener_x, listener_y, max_dist=580.0):
        dx = float(comp_x) - float(listener_x)
        dy = float(comp_y) - float(listener_y)
        dist = math.hypot(dx, dy)
        if dist >= max_dist:
            return 0.0, 0.0, 0.0
        gain = clamp(((1.0 - dist / float(max_dist)) ** 1.35) * 0.94, 0.08, 0.94)
        pan = clamp(dx / 340.0, -0.85, 0.85)
        left = gain * clamp(1.0 - max(0.0, pan) * 0.80, 0.16, 1.0)
        right = gain * clamp(1.0 + min(0.0, pan) * 0.80, 0.16, 1.0)
        return gain, left, right

    def update_computer_audio(
        self,
        playing,
        track_idx,
        comp_x,
        comp_y,
        listener_x,
        listener_y,
        max_dist=580.0,
    ):
        if not self.enabled:
            return
        want_on = bool(GAME_SETTINGS.get("sound_enabled", True)) and bool(GAME_SETTINGS.get("music_enabled", True))
        if not playing or not want_on:
            self.stop_computer_audio()
            return
        gain, left, right = self.compute_spatial_mix(comp_x, comp_y, listener_x, listener_y, max_dist=max_dist)
        if gain <= 0.01:
            self.stop_computer_audio()
            return
        idx = int(track_idx) % len(COMPUTER_TRACKS)
        if self._computer_channel is None:
            return
        try:
            need_play = (not self._computer_playing) or (self._computer_track_idx != idx)
            if not need_play and hasattr(self._computer_channel, "get_busy") and not self._computer_channel.get_busy():
                need_play = True
            if need_play:
                trk = self._build_computer_track(idx)
                self._computer_channel.stop()
                self._computer_channel.play(trk, loops=-1)
                self._computer_track_idx = idx
                self._computer_playing = True
            self._computer_channel.set_volume(left, right)
            if self._music_channel is not None:
                bgm_vol = clamp(1.0 - gain * 0.68, 0.25, 1.0)
                self._music_channel.set_volume(bgm_vol, bgm_vol)
        except Exception:
            pass

    def _build_all(self):
        # Core player & world SFX (layered harmonics, warmer envelopes)
        self.sounds["shoot"] = self._synth(0.085, 580, 230, 0.16, "tri", noise=0.06, harmonics=[(2.0, 0.22)], lp_alpha=0.55)
        self.sounds["hit"] = self._synth(0.095, 240, 82, 0.22, "saw", noise=0.28, sub_mix=0.30, lp_alpha=0.45)
        self.sounds["hurt"] = self._synth(0.24, 210, 58, 0.28, "saw", noise=0.26, sub_mix=0.35, vib_hz=28.0, vib_depth=0.06, lp_alpha=0.5)
        self.sounds["pickup"] = self._synth_chord([587.33, 880.0], 0.16, 0.20, "tri", arpeggio_step=0.045)
        self.sounds["item"] = self._synth_chord([293.66, 440.0, 587.33, 880.0], 0.44, 0.24, "tri", arpeggio_step=0.065)
        self.sounds["door"] = self._synth(0.22, 130, 195, 0.23, "tri", noise=0.18, sub_mix=0.45, lp_alpha=0.38)
        self.sounds["bomb"] = self._synth(0.46, 135, 32, 0.34, "saw", noise=0.68, sub_mix=0.45, decay_pow=1.7, lp_alpha=0.35)
        self.sounds["boss"] = self._synth(0.52, 108, 46, 0.30, "saw", noise=0.22, harmonics=[(1.5, 0.35)], sub_mix=0.4, lp_alpha=0.4)
        self.sounds["teleport"] = self._synth(0.14, 520, 180, 0.19, "sine", noise=0.14, harmonics=[(2.5, 0.25)], vib_hz=22.0, vib_depth=0.08)
        self.sounds["die"] = self._synth_chord([293.66, 261.63, 220.0, 146.83], 0.62, 0.26, "saw", arpeggio_step=0.09)
        self.sounds["win"] = self._synth_chord([293.66, 369.99, 440.0, 587.33, 739.99], 0.56, 0.24, "tri", arpeggio_step=0.07)
        self.sounds["dice"] = self._synth_chord([440.0, 587.33, 783.99], 0.28, 0.22, "tri", arpeggio_step=0.05)
        self.sounds["beggar"] = self._synth_chord([523.25, 659.25], 0.17, 0.20, "sine", arpeggio_step=0.05)
        self.sounds["computer_beep"] = self._synth_chord([659.25, 987.77], 0.14, 0.20, "square", arpeggio_step=0.04)
        self.sounds["computer_switch"] = self._synth(0.11, 440, 880, 0.18, "tri", noise=0.08, harmonics=[(2.0, 0.25)])

        # Melee & destructible block SFX
        self.sounds["melee_swing"] = self._synth(0.11, 460, 140, 0.22, "tri", noise=0.48, harmonics=[(2.4, 0.18)], decay_pow=1.8, lp_alpha=0.58)
        self.sounds["melee_combo"] = self._synth(0.15, 620, 165, 0.26, "saw", noise=0.42, harmonics=[(2.0, 0.28), (3.0, 0.14)], sub_mix=0.25, lp_alpha=0.62)
        self.sounds["melee_hit"] = self._synth(0.11, 210, 62, 0.27, "square", noise=0.38, sub_mix=0.42, decay_pow=1.9, lp_alpha=0.48)
        self.sounds["melee_deflect"] = self._synth(0.14, 980, 1480, 0.22, "tri", noise=0.08, harmonics=[(2.76, 0.32)], decay_pow=2.1)
        self.sounds["block_break"] = self._synth(0.19, 175, 48, 0.25, "saw", noise=0.64, sub_mix=0.35, decay_pow=1.8, lp_alpha=0.42)

        # Custom enemy attack SFX
        self.sounds["enemy_spit"] = self._synth(0.09, 340, 170, 0.14, "sine", noise=0.22, vib_hz=18.0, vib_depth=0.06, lp_alpha=0.5)
        self.sounds["enemy_dash"] = self._synth(0.14, 240, 420, 0.16, "saw", noise=0.44, decay_pow=1.6, lp_alpha=0.52)
        self.sounds["enemy_jump"] = self._synth(0.13, 180, 390, 0.16, "tri", noise=0.14, sub_mix=0.25)
        self.sounds["enemy_mortar"] = self._synth(0.18, 165, 84, 0.19, "tri", noise=0.26, sub_mix=0.45, lp_alpha=0.36)
        self.sounds["enemy_pulse"] = self._synth(0.22, 320, 140, 0.18, "sine", harmonics=[(1.5, 0.30), (2.0, 0.18)], vib_hz=14.0, vib_depth=0.10)
        self.sounds["enemy_phantom"] = self._synth(0.20, 640, 290, 0.16, "sine", noise=0.18, harmonics=[(1.41, 0.25)], vib_hz=11.0, vib_depth=0.12)
        self.sounds["enemy_bone"] = self._synth(0.10, 720, 310, 0.16, "tri", noise=0.20, harmonics=[(2.6, 0.25)], decay_pow=2.0)
        self.sounds["enemy_split"] = self._synth(0.15, 480, 740, 0.16, "tri", noise=0.12, harmonics=[(1.5, 0.28)])
        self.sounds["enemy_fuse"] = self._synth(0.18, 520, 880, 0.15, "saw", noise=0.55, lp_alpha=0.65)

        # Custom boss attack & telegraph SFX
        self.sounds["boss_windup"] = self._synth(0.26, 130, 220, 0.22, "saw", noise=0.18, harmonics=[(1.5, 0.25)], sub_mix=0.35, attack=0.18, lp_alpha=0.42)
        self.sounds["boss_roar"] = self._synth(0.58, 128, 44, 0.32, "saw", noise=0.34, harmonics=[(1.33, 0.38), (2.0, 0.20)], sub_mix=0.45, vib_hz=9.0, vib_depth=0.08, lp_alpha=0.44)
        self.sounds["boss_beam"] = self._synth(0.32, 260, 190, 0.26, "saw", noise=0.22, harmonics=[(2.0, 0.35), (3.0, 0.22)], vib_hz=26.0, vib_depth=0.05, lp_alpha=0.58)
        self.sounds["boss_mortar"] = self._synth(0.24, 150, 56, 0.26, "tri", noise=0.35, sub_mix=0.50, lp_alpha=0.34)
        self.sounds["boss_dash"] = self._synth(0.20, 190, 92, 0.24, "saw", noise=0.48, sub_mix=0.35, lp_alpha=0.46)
        self.sounds["boss_homing"] = self._synth(0.26, 420, 620, 0.20, "sine", harmonics=[(1.5, 0.32), (2.25, 0.16)], vib_hz=16.0, vib_depth=0.11)
        self.sounds["boss_slam"] = self._synth(0.36, 125, 34, 0.32, "saw", noise=0.52, sub_mix=0.55, decay_pow=1.6, lp_alpha=0.32)

        # Progression & UI SFX
        self.sounds["hero_unlock"] = self._synth_chord([293.66, 440.0, 587.33, 739.99, 880.0], 0.65, 0.26, "tri", arpeggio_step=0.07)
        self.sounds["ui_click"] = self._synth(0.045, 520, 420, 0.12, "tri", decay_pow=2.2)
        self.sounds["ui_confirm"] = self._synth_chord([440.0, 659.25], 0.14, 0.16, "tri", arpeggio_step=0.035)

    def play(self, name, min_interval=0.045):
        if not self.enabled or not GAME_SETTINGS.get("sound_enabled", True):
            return
        snd = self.sounds.get(name)
        if snd is None:
            return
        now = time.monotonic()
        last = self._last_play.get(name, 0.0)
        if now - last < min_interval:
            return
        self._last_play[name] = now
        try:
            snd.play()
        except Exception:
            pass


_BANK = None


def get_sound_bank():
    global _BANK
    if _BANK is None:
        _BANK = SoundBank()
    return _BANK


_RECENT_SFX = []


def consume_recent_sfx():
    if not _RECENT_SFX:
        return []
    out = list(_RECENT_SFX)
    _RECENT_SFX.clear()
    return out


def play_sound(name, min_interval=0.045):
    if name and len(_RECENT_SFX) < 10 and name not in _RECENT_SFX:
        _RECENT_SFX.append(str(name))
    get_sound_bank().play(name, min_interval=min_interval)


def update_music(mode="none"):
    get_sound_bank().update_music(mode)


def update_computer_audio(playing, track_idx, comp_x, comp_y, listener_x, listener_y, max_dist=580.0):
    get_sound_bank().update_computer_audio(playing, track_idx, comp_x, comp_y, listener_x, listener_y, max_dist=max_dist)


def stop_computer_audio():
    get_sound_bank().stop_computer_audio()
