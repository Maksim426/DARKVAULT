import json
import socket
import threading
import time
from collections import deque

DEFAULT_TCP_PORT = 24680
DISCOVERY_UDP_PORT = 24681
DISCOVERY_MAGIC = "DARKVAULT_LAN_DISCOVER_V1"
PEER_TIMEOUT_SEC = 6.5
HEARTBEAT_INTERVAL_SEC = 1.2

ACTION_KEYS = (
    "jump",
    "stealth",
    "melee",
    "bomb",
    "relic",
    "cycle_relic",
    "interact",
    "confirm",
    "cancel",
)


def get_local_ips():
    """Return a deduplicated list of non-loopback IPv4 addresses on this machine."""
    ips = []
    for probe_target in (("10.255.255.255", 1), ("192.168.1.1", 1), ("8.8.8.8", 80)):
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(0.2)
            sock.connect(probe_target)
            ip = sock.getsockname()[0]
            if ip and not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
        except Exception:
            pass
        finally:
            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    return ips


def get_local_ip():
    ips = get_local_ips()
    return ips[0] if ips else "127.0.0.1"


def parse_host_port(addr_text, default_port=DEFAULT_TCP_PORT):
    raw = str(addr_text or "").strip()
    if not raw:
        return "127.0.0.1", int(default_port)
    if ":" in raw:
        h, p_str = raw.rsplit(":", 1)
        h = h.strip() or "127.0.0.1"
        try:
            p = int(p_str.strip())
            if 1 <= p <= 65535:
                return h, p
        except ValueError:
            pass
        return h, int(default_port)
    return raw, int(default_port)


def scan_lan_servers(timeout=0.35, discovery_port=DISCOVERY_UDP_PORT):
    """Broadcast a lightweight UDP discovery ping and gather responding DarkVault hosts."""
    found = {}
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(min(0.12, max(0.04, timeout * 0.35)))
        payload = json.dumps({"magic": DISCOVERY_MAGIC, "ts": time.time()}).encode("utf-8")
        targets = [("255.255.255.255", int(discovery_port)), ("127.0.0.1", int(discovery_port))]
        for local_ip in get_local_ips():
            parts = local_ip.split(".")
            if len(parts) == 4:
                bcast = (f"{parts[0]}.{parts[1]}.{parts[2]}.255", int(discovery_port))
                if bcast not in targets:
                    targets.append(bcast)
        for tgt in targets:
            try:
                sock.sendto(payload, tgt)
            except Exception:
                pass
        deadline = time.monotonic() + max(0.15, float(timeout))
        while time.monotonic() < deadline:
            try:
                data, addr = sock.recvfrom(2048)
                msg = json.loads(data.decode("utf-8", errors="ignore"))
                if not isinstance(msg, dict) or msg.get("magic") != DISCOVERY_MAGIC + "_ACK":
                    continue
                ip = str(addr[0])
                port = int(msg.get("port", DEFAULT_TCP_PORT))
                found[(ip, port)] = {
                    "ip": ip,
                    "port": port,
                    "host_name": str(msg.get("host_name", "DarkVault"))[:24],
                    "mode": str(msg.get("mode", "classic")),
                    "hero_id": str(msg.get("hero_id", "isaac")),
                    "players": int(msg.get("players", 1)),
                    "in_run": bool(msg.get("in_run", False)),
                }
            except socket.timeout:
                continue
            except Exception:
                break
    except Exception:
        pass
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass
    return list(found.values())


def _lerp_num(a, b, t):
    return a + (b - a) * t


def _interp_player(prev_p, curr_p, alpha):
    if not curr_p:
        return curr_p
    if not prev_p or prev_p.get("hero_id") != curr_p.get("hero_id"):
        return curr_p
    dx = float(curr_p["x"]) - float(prev_p["x"])
    dy = float(curr_p["y"]) - float(prev_p["y"])
    # Snap on teleports / room transitions
    if (dx * dx + dy * dy) > (180.0 * 180.0):
        return curr_p
    out = dict(curr_p)
    out["x"] = _lerp_num(float(prev_p["x"]), float(curr_p["x"]), alpha)
    out["y"] = _lerp_num(float(prev_p["y"]), float(curr_p["y"]), alpha)
    out["air_z"] = _lerp_num(float(prev_p.get("air_z", 0.0)), float(curr_p.get("air_z", 0.0)), alpha)
    return out


def _interp_entity_list(prev_list, curr_list, alpha, max_jump=140.0):
    if not curr_list or not prev_list:
        return curr_list
    max_jump_sq = max_jump * max_jump
    if isinstance(curr_list[0], dict):
        prev_by_id = {pe.get("id"): pe for pe in prev_list if isinstance(pe, dict) and pe.get("id") is not None}
        out = []
        for idx, ce in enumerate(curr_list):
            if not isinstance(ce, dict):
                out.append(ce)
                continue
            eid = ce.get("id")
            pe = prev_by_id.get(eid) if eid is not None else (prev_list[idx] if idx < len(prev_list) and len(prev_list) == len(curr_list) else None)
            if isinstance(pe, dict) and "x" in pe and "y" in pe and "x" in ce and "y" in ce:
                dx = float(ce["x"]) - float(pe["x"])
                dy = float(ce["y"]) - float(pe["y"])
                if (dx * dx + dy * dy) <= max_jump_sq:
                    row = dict(ce)
                    row["x"] = _lerp_num(float(pe["x"]), float(ce["x"]), alpha)
                    row["y"] = _lerp_num(float(pe["y"]), float(ce["y"]), alpha)
                    if "air_z" in pe and "air_z" in ce:
                        row["air_z"] = _lerp_num(float(pe["air_z"]), float(ce["air_z"]), alpha)
                    out.append(row)
                    continue
            out.append(ce)
        return out
    if len(prev_list) != len(curr_list):
        return curr_list
    out = []
    for pe, ce in zip(prev_list, curr_list):
        if isinstance(pe, (list, tuple)) and isinstance(ce, (list, tuple)) and len(pe) >= 2 and len(ce) >= 2:
            dx = float(ce[0]) - float(pe[0])
            dy = float(ce[1]) - float(pe[1])
            if (dx * dx + dy * dy) <= max_jump_sq:
                row = list(ce)
                row[0] = _lerp_num(float(pe[0]), float(ce[0]), alpha)
                row[1] = _lerp_num(float(pe[1]), float(ce[1]), alpha)
                out.append(row)
                continue
        out.append(ce)
    return out


def interpolate_lan_snapshot(prev_st, curr_st, alpha):
    """Smoothly interpolate entity positions between two host snapshots for 60 FPS client visuals."""
    if not curr_st:
        return curr_st
    if not prev_st or alpha >= 0.999 or alpha <= 0.0:
        return curr_st
    if prev_st.get("floor") != curr_st.get("floor") or prev_st.get("coord") != curr_st.get("coord"):
        return curr_st
    t = max(0.0, min(1.0, float(alpha)))
    out = dict(curr_st)
    out["p1"] = _interp_player(prev_st.get("p1"), curr_st.get("p1"), t)
    out["p2"] = _interp_player(prev_st.get("p2"), curr_st.get("p2"), t)
    out["enemies"] = _interp_entity_list(prev_st.get("enemies"), curr_st.get("enemies"), t, max_jump=150.0)
    out["bosses"] = _interp_entity_list(prev_st.get("bosses"), curr_st.get("bosses"), t, max_jump=190.0)
    out["tears"] = _interp_entity_list(prev_st.get("tears"), curr_st.get("tears"), t, max_jump=110.0)
    out["eproj"] = _interp_entity_list(prev_st.get("eproj"), curr_st.get("eproj"), t, max_jump=110.0)
    return out


class LanHost:
    def __init__(self):
        self._lock = threading.Lock()
        self._stop_ev = threading.Event()
        self._srv_sock = None
        self._udp_sock = None
        self._client_sock = None
        self._ctrl_queue = deque(maxlen=24)
        self._latest_snapshot_raw = None
        self._send_ev = threading.Event()
        self._snapshot_seq = 0
        self._last_client_rx = 0.0

        self.running = False
        self.port = DEFAULT_TCP_PORT
        self.discovery_port = DISCOVERY_UDP_PORT
        self.local_ip = "127.0.0.1"
        self.last_error = ""

        self.host_name = "Host"
        self.host_hero_id = "isaac"
        self.game_mode = "classic"
        self.in_run = False

        self.client_connected = False
        self.client_name = "P2"
        self.client_hero_id = "magdalene"
        self.ping_ms = 0
        self._p2_input = {
            "mx": 0.0,
            "my": 0.0,
            "ax": 0.0,
            "ay": 0.0,
            "dash": False,
            "ts": 0.0,
        }
        self._p2_actions = {ak: False for ak in ACTION_KEYS}
        self._p2_inv_slots = deque(maxlen=16)
        self._p2_inv_pages = deque(maxlen=16)

    def start(
        self,
        host_name="Host",
        hero_id="isaac",
        game_mode="classic",
        port=DEFAULT_TCP_PORT,
        discovery_port=DISCOVERY_UDP_PORT,
    ):
        self.stop()
        self._stop_ev.clear()
        self.last_error = ""
        self.host_name = str(host_name or "Host")[:24]
        self.host_hero_id = str(hero_id or "isaac")
        self.game_mode = str(game_mode or "classic")
        self.discovery_port = int(discovery_port)
        self.local_ip = get_local_ip()
        self.ping_ms = 0
        self._snapshot_seq = 0

        bound = False
        for cand_port in range(int(port), int(port) + 8):
            srv = None
            try:
                srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                srv.bind(("0.0.0.0", cand_port))
                srv.listen(2)
                srv.settimeout(0.4)
                self._srv_sock = srv
                self.port = cand_port
                bound = True
                break
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
                if srv is not None:
                    try:
                        srv.close()
                    except Exception:
                        pass
                self._srv_sock = None

        if not bound:
            self.running = False
            return False, self.last_error or "bind_failed"

        try:
            udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            udp.bind(("0.0.0.0", self.discovery_port))
            udp.settimeout(0.4)
            self._udp_sock = udp
        except Exception:
            self._udp_sock = None

        self.running = True
        threading.Thread(target=self._accept_loop, daemon=True, name="DarkVaultLanAccept").start()
        threading.Thread(target=self._send_loop, daemon=True, name="DarkVaultLanSend").start()
        if self._udp_sock is not None:
            threading.Thread(target=self._udp_loop, daemon=True, name="DarkVaultLanBeacon").start()
        return True, f"{self.local_ip}:{self.port}"

    def update_lobby_meta(self, host_hero_id=None, game_mode=None, in_run=None):
        changed = False
        with self._lock:
            if host_hero_id is not None and str(host_hero_id) != self.host_hero_id:
                self.host_hero_id = str(host_hero_id)
                changed = True
            if game_mode is not None and str(game_mode) != self.game_mode:
                self.game_mode = str(game_mode)
                changed = True
            if in_run is not None and bool(in_run) != self.in_run:
                self.in_run = bool(in_run)
                changed = True
            should_push = changed and self.client_connected
            meta_pkt = {
                "type": "welcome",
                "host_name": self.host_name,
                "hero_id": self.host_hero_id,
                "mode": self.game_mode,
                "in_run": self.in_run,
            }
        if should_push:
            self._queue_packet(meta_pkt, is_snapshot=False)

    def _udp_loop(self):
        while not self._stop_ev.is_set() and self._udp_sock is not None:
            try:
                data, addr = self._udp_sock.recvfrom(1024)
                msg = json.loads(data.decode("utf-8", errors="ignore"))
                if isinstance(msg, dict) and msg.get("magic") == DISCOVERY_MAGIC:
                    with self._lock:
                        ack = {
                            "magic": DISCOVERY_MAGIC + "_ACK",
                            "port": self.port,
                            "host_name": self.host_name,
                            "mode": self.game_mode,
                            "hero_id": self.host_hero_id,
                            "players": 2 if self.client_connected else 1,
                            "in_run": self.in_run,
                        }
                    self._udp_sock.sendto(json.dumps(ack, ensure_ascii=False).encode("utf-8"), addr)
            except socket.timeout:
                continue
            except Exception:
                if self._stop_ev.is_set():
                    break

    def _accept_loop(self):
        while not self._stop_ev.is_set() and self._srv_sock is not None:
            try:
                conn, _ = self._srv_sock.accept()
            except socket.timeout:
                continue
            except Exception:
                break
            try:
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                conn.settimeout(0.5)
            except Exception:
                pass
            with self._lock:
                old = self._client_sock
                self._client_sock = conn
                self.client_connected = True
                self.ping_ms = 0
                self._last_client_rx = time.monotonic()
                self._ctrl_queue.clear()
                self._latest_snapshot_raw = None
                self._p2_input = {"mx": 0.0, "my": 0.0, "ax": 0.0, "ay": 0.0, "dash": False, "ts": 0.0}
                self._p2_actions = {ak: False for ak in ACTION_KEYS}
                self._p2_inv_slots.clear()
                self._p2_inv_pages.clear()
            if old is not None:
                try:
                    old.close()
                except Exception:
                    pass
            self._queue_packet({
                "type": "welcome",
                "host_name": self.host_name,
                "hero_id": self.host_hero_id,
                "mode": self.game_mode,
                "in_run": self.in_run,
            })
            self._recv_client_loop(conn)

    def _recv_client_loop(self, conn):
        buf = b""
        try:
            while not self._stop_ev.is_set():
                try:
                    chunk = conn.recv(4096)
                except socket.timeout:
                    with self._lock:
                        if self._client_sock is conn and (time.monotonic() - self._last_client_rx) > PEER_TIMEOUT_SEC:
                            break
                    continue
                if not chunk:
                    break
                with self._lock:
                    self._last_client_rx = time.monotonic()
                buf += chunk
                if len(buf) > 131072:
                    buf = buf[-65536:]
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    try:
                        msg = json.loads(line.decode("utf-8", errors="ignore"))
                    except Exception:
                        continue
                    if not isinstance(msg, dict):
                        continue
                    mtype = msg.get("type")
                    if mtype == "hello":
                        with self._lock:
                            self.client_name = str(msg.get("name", "P2"))[:24]
                            if msg.get("hero_id"):
                                self.client_hero_id = str(msg["hero_id"])
                    elif mtype == "hero":
                        with self._lock:
                            if msg.get("hero_id"):
                                self.client_hero_id = str(msg["hero_id"])
                    elif mtype == "ping":
                        c_ts = msg.get("ts", 0.0)
                        c_rtt = msg.get("rtt_ms")
                        with self._lock:
                            if isinstance(c_rtt, (int, float)) and c_rtt >= 0:
                                self.ping_ms = int(round(c_rtt))
                            pong_pkt = {
                                "type": "pong",
                                "ts": c_ts,
                                "host_name": self.host_name,
                                "hero_id": self.host_hero_id,
                                "mode": self.game_mode,
                                "in_run": self.in_run,
                            }
                        self._queue_packet(pong_pkt, is_snapshot=False)
                    elif mtype == "action":
                        with self._lock:
                            for ak in ACTION_KEYS:
                                if msg.get(ak):
                                    self._p2_actions[ak] = True
                            if "inv_slot" in msg and isinstance(msg.get("inv_slot"), int):
                                self._p2_inv_slots.append(int(msg["inv_slot"]))
                            if "inv_page" in msg and isinstance(msg.get("inv_page"), int):
                                self._p2_inv_pages.append(int(msg["inv_page"]))
                    elif mtype == "input":
                        with self._lock:
                            self._p2_input["mx"] = max(-1.0, min(1.0, float(msg.get("mx", 0.0))))
                            self._p2_input["my"] = max(-1.0, min(1.0, float(msg.get("my", 0.0))))
                            self._p2_input["ax"] = max(-1.0, min(1.0, float(msg.get("ax", 0.0))))
                            self._p2_input["ay"] = max(-1.0, min(1.0, float(msg.get("ay", 0.0))))
                            self._p2_input["dash"] = bool(msg.get("dash", False))
                            self._p2_input["ts"] = time.monotonic()
                            for ak in ACTION_KEYS:
                                if msg.get(ak):
                                    self._p2_actions[ak] = True
        except Exception:
            pass
        finally:
            with self._lock:
                if self._client_sock is conn:
                    self._client_sock = None
                    self.client_connected = False
                    self.ping_ms = 0
                    self._ctrl_queue.clear()
                    self._latest_snapshot_raw = None
            try:
                conn.close()
            except Exception:
                pass

    def _queue_packet(self, payload_dict, is_snapshot=False):
        if not self.running:
            return
        try:
            raw = (json.dumps(payload_dict, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        except Exception:
            return
        with self._lock:
            if self._client_sock is None:
                return
            if is_snapshot:
                self._latest_snapshot_raw = raw
            else:
                self._ctrl_queue.append(raw)
        self._send_ev.set()

    def send_snapshot(self, snapshot):
        if not isinstance(snapshot, dict):
            return
        with self._lock:
            self._snapshot_seq += 1
            seq = self._snapshot_seq
        payload = dict(snapshot)
        payload["seq"] = seq
        self._queue_packet(payload, is_snapshot=True)

    def _send_loop(self):
        while not self._stop_ev.is_set():
            self._send_ev.wait(0.08)
            self._send_ev.clear()
            while not self._stop_ev.is_set():
                with self._lock:
                    if self._client_sock is None:
                        break
                    if self._ctrl_queue:
                        raw = self._ctrl_queue.popleft()
                    elif self._latest_snapshot_raw is not None:
                        raw = self._latest_snapshot_raw
                        self._latest_snapshot_raw = None
                    else:
                        break
                    conn = self._client_sock
                try:
                    conn.sendall(raw)
                except Exception:
                    with self._lock:
                        if self._client_sock is conn:
                            self._client_sock = None
                            self.client_connected = False
                            self.ping_ms = 0
                            self._ctrl_queue.clear()
                            self._latest_snapshot_raw = None
                    try:
                        conn.close()
                    except Exception:
                        pass
                    break

    def consume_client_input(self):
        with self._lock:
            if not self.client_connected:
                return None
            # Decay stale continuous input if network quiet > 0.35s
            stale = (time.monotonic() - self._p2_input["ts"]) > 0.35
            out = {
                "mx": 0.0 if stale else self._p2_input["mx"],
                "my": 0.0 if stale else self._p2_input["my"],
                "ax": 0.0 if stale else self._p2_input["ax"],
                "ay": 0.0 if stale else self._p2_input["ay"],
                "dash": False if stale else self._p2_input["dash"],
            }
            for ak in ACTION_KEYS:
                out[ak] = self._p2_actions[ak]
                self._p2_actions[ak] = False
            out["inv_slots"] = list(self._p2_inv_slots)
            self._p2_inv_slots.clear()
            out["inv_pages"] = list(self._p2_inv_pages)
            self._p2_inv_pages.clear()
            return out

    def stop(self):
        self._stop_ev.set()
        self.running = False
        self.client_connected = False
        self.ping_ms = 0
        self._send_ev.set()
        for attr in ("_client_sock", "_srv_sock", "_udp_sock"):
            s = getattr(self, attr, None)
            if s is not None:
                setattr(self, attr, None)
                try:
                    s.close()
                except Exception:
                    pass


class LanClient:
    def __init__(self):
        self._lock = threading.Lock()
        self._stop_ev = threading.Event()
        self._sock = None
        self._ctrl_queue = deque(maxlen=24)
        self._latest_input_raw = None
        self._send_ev = threading.Event()
        self._last_host_rx = 0.0
        self._last_ping_sent = 0.0

        self.connected = False
        self.host_addr = ""
        self.host_name = ""
        self.host_hero_id = "isaac"
        self.game_mode = "classic"
        self.host_in_run = False
        self.last_error = ""
        self.ping_ms = 0

        self._prev_state = None
        self._latest_state = None
        self._state_rx_ts = 0.0
        self._state_interval = 1.0 / 30.0
        self._pending_actions = {ak: False for ak in ACTION_KEYS}

    def connect(self, ip, port=DEFAULT_TCP_PORT, name="P2", hero_id="magdalene"):
        self.stop()
        self._stop_ev.clear()
        self.last_error = ""
        self._prev_state = None
        self._latest_state = None
        self._state_rx_ts = 0.0
        self._state_interval = 1.0 / 30.0
        self.host_in_run = False
        self.ping_ms = 0
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.5)
            sock.connect((str(ip).strip(), int(port)))
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.settimeout(0.5)
            now = time.monotonic()
            with self._lock:
                self._sock = sock
                self.connected = True
                self.host_addr = f"{ip}:{port}"
                self._last_host_rx = now
                self._last_ping_sent = 0.0
                self._ctrl_queue.clear()
                self._latest_input_raw = None
                self._pending_actions = {ak: False for ak in ACTION_KEYS}
            self._queue_packet({"type": "hello", "name": str(name)[:24], "hero_id": str(hero_id)}, reliable=True)
            self._send_ping_now()
            threading.Thread(target=self._recv_loop, daemon=True, name="DarkVaultLanClientRecv").start()
            threading.Thread(target=self._send_loop, daemon=True, name="DarkVaultLanClientSend").start()
            return True, self.host_addr
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass
            self._sock = None
            self.connected = False
            return False, self.last_error

    def _queue_packet(self, payload, reliable=True):
        if not self.connected or self._sock is None:
            return
        try:
            raw = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        except Exception:
            return
        with self._lock:
            if reliable:
                self._ctrl_queue.append(raw)
            else:
                self._latest_input_raw = raw
        self._send_ev.set()

    def _send_ping_now(self):
        now = time.monotonic()
        with self._lock:
            self._last_ping_sent = now
            rtt = self.ping_ms
        self._queue_packet({"type": "ping", "ts": now, "rtt_ms": rtt}, reliable=True)

    def send_hero(self, hero_id):
        self._queue_packet({"type": "hero", "hero_id": str(hero_id)}, reliable=True)

    def send_action(self, action_name, **extra):
        payload = {"type": "action"}
        has_any = False
        if action_name in ACTION_KEYS:
            payload[action_name] = True
            has_any = True
        for k, v in extra.items():
            if k in ("inv_slot", "inv_page") and isinstance(v, int):
                payload[k] = int(v)
                has_any = True
        if has_any:
            self._queue_packet(payload, reliable=True)

    def send_input(
        self,
        mx,
        my,
        ax,
        ay,
        dash=False,
        jump=False,
        stealth=False,
        bomb=False,
        relic=False,
        melee=False,
        cycle_relic=False,
        interact=False,
        confirm=False,
        cancel=False,
    ):
        one_shots = {}
        with self._lock:
            flags = {
                "jump": jump,
                "stealth": stealth,
                "melee": melee,
                "bomb": bomb,
                "relic": relic,
                "cycle_relic": cycle_relic,
                "interact": interact,
                "confirm": confirm,
                "cancel": cancel,
            }
            for k, v in flags.items():
                if v:
                    self._pending_actions[k] = True
            for k in ACTION_KEYS:
                if self._pending_actions[k]:
                    one_shots[k] = True
                    self._pending_actions[k] = False

        # Send one-shot button presses reliably so continuous movement never drops them
        if one_shots:
            self._queue_packet({"type": "action", **one_shots}, reliable=True)

        self._queue_packet(
            {
                "type": "input",
                "mx": round(float(mx), 3),
                "my": round(float(my), 3),
                "ax": round(float(ax), 3),
                "ay": round(float(ay), 3),
                "dash": bool(dash),
            },
            reliable=False,
        )

    def _send_loop(self):
        while not self._stop_ev.is_set() and self.connected:
            self._send_ev.wait(0.08)
            self._send_ev.clear()
            now = time.monotonic()
            if (now - self._last_ping_sent) >= HEARTBEAT_INTERVAL_SEC:
                self._send_ping_now()
            while not self._stop_ev.is_set() and self.connected:
                with self._lock:
                    if self._sock is None:
                        break
                    if self._ctrl_queue:
                        raw = self._ctrl_queue.popleft()
                    elif self._latest_input_raw is not None:
                        raw = self._latest_input_raw
                        self._latest_input_raw = None
                    else:
                        break
                    sock = self._sock
                try:
                    sock.sendall(raw)
                except Exception:
                    self.connected = False
                    break

    def _recv_loop(self):
        buf = b""
        sock = self._sock
        try:
            while not self._stop_ev.is_set() and sock is not None:
                try:
                    chunk = sock.recv(16384)
                except socket.timeout:
                    if (time.monotonic() - self._last_host_rx) > PEER_TIMEOUT_SEC:
                        self.last_error = "Connection timed out"
                        break
                    continue
                if not chunk:
                    break
                now = time.monotonic()
                with self._lock:
                    self._last_host_rx = now
                buf += chunk
                if len(buf) > 524288:
                    buf = buf[-262144:]
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    try:
                        msg = json.loads(line.decode("utf-8", errors="ignore"))
                    except Exception:
                        continue
                    if not isinstance(msg, dict):
                        continue
                    mtype = msg.get("type")
                    if mtype == "welcome":
                        with self._lock:
                            self.host_name = str(msg.get("host_name", "Host"))[:24]
                            self.host_hero_id = str(msg.get("hero_id", "isaac"))
                            self.game_mode = str(msg.get("mode", "classic"))
                            self.host_in_run = bool(msg.get("in_run", False))
                    elif mtype == "pong":
                        sent_ts = msg.get("ts")
                        with self._lock:
                            if isinstance(sent_ts, (int, float)) and sent_ts > 0:
                                rtt = max(0.0, (time.monotonic() - float(sent_ts)) * 1000.0)
                                self.ping_ms = int(round(rtt if self.ping_ms <= 0 else (self.ping_ms * 0.6 + rtt * 0.4)))
                            if msg.get("host_name"):
                                self.host_name = str(msg.get("host_name", self.host_name))[:24]
                            if msg.get("hero_id"):
                                self.host_hero_id = str(msg.get("hero_id", self.host_hero_id))
                            if msg.get("mode"):
                                self.game_mode = str(msg.get("mode", self.game_mode))
                            if "in_run" in msg:
                                self.host_in_run = bool(msg.get("in_run", self.host_in_run))
                    elif mtype == "state":
                        rx_now = time.monotonic()
                        with self._lock:
                            if self._latest_state is not None and self._state_rx_ts > 0.0:
                                dt_snap = max(0.012, min(0.15, rx_now - self._state_rx_ts))
                                self._state_interval = self._state_interval * 0.7 + dt_snap * 0.3
                            self._prev_state = self._latest_state
                            self._latest_state = msg
                            self._state_rx_ts = rx_now
                            self.host_in_run = bool(msg.get("in_run", self.host_in_run))
        except Exception:
            pass
        finally:
            self.connected = False
            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass

    def get_latest_state(self):
        with self._lock:
            return self._latest_state

    def get_interpolated_state(self):
        with self._lock:
            curr = self._latest_state
            prev = self._prev_state
            rx_ts = self._state_rx_ts
            interval = self._state_interval
        if curr is None:
            return None
        if prev is None or rx_ts <= 0.0:
            return curr
        alpha = max(0.0, min(1.0, (time.monotonic() - rx_ts) / max(0.016, interval)))
        return interpolate_lan_snapshot(prev, curr, alpha)

    def stop(self):
        self._stop_ev.set()
        self.connected = False
        self.ping_ms = 0
        self._send_ev.set()
        s = self._sock
        self._sock = None
        if s is not None:
            try:
                s.close()
            except Exception:
                pass
