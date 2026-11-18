# DarkVault AI Mod Assistant & Code Editor Agent
import ast
import json
import os
import ssl
import threading
import time
import urllib.error
import urllib.request

import settings

PROVIDER_CHOICES = ("gemini", "openai", "claude", "deepseek", "custom")

DEFAULT_MODELS = {
    "gemini": "gemini-2.5-flash",
    "openai": "gpt-4o-mini",
    "claude": "claude-3-5-sonnet-latest",
    "deepseek": "deepseek-chat",
    "custom": "gpt-4o-mini",
}

GEMINI_FALLBACK_MODELS = ("gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash")


def _build_ssl_context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        try:
            return ssl.create_default_context()
        except Exception:
            return None


def detect_provider_from_key(api_key, current_provider="gemini"):
    k = str(api_key or "").strip()
    if not k:
        return current_provider if current_provider in PROVIDER_CHOICES else "gemini"
    if k.startswith("AIza"):
        return "gemini"
    if k.startswith("sk-ant-"):
        return "claude"
    if k.startswith("sk-"):
        if current_provider in ("openai", "deepseek", "custom"):
            return current_provider
        return "openai"
    return current_provider if current_provider in PROVIDER_CHOICES else "gemini"


def _extract_http_error_message(raw_body, reason=""):
    txt = (raw_body or "").strip()
    if txt:
        try:
            parsed = json.loads(txt)
            if isinstance(parsed, dict):
                err = parsed.get("error")
                if isinstance(err, dict):
                    msg = str(err.get("message", "")).strip()
                    if msg:
                        return msg[:260]
                msg = str(parsed.get("message", "")).strip()
                if msg:
                    return msg[:260]
        except Exception:
            pass
        return txt[:260]
    return str(reason or "HTTP Error")[:260]


def validate_python_syntax(code_text):
    try:
        ast.parse(code_text or "")
        return True, "", 0
    except SyntaxError as exc:
        line_no = int(getattr(exc, "lineno", 1) or 1)
        msg = str(getattr(exc, "msg", exc) or "SyntaxError")
        return False, f"Line {line_no}: {msg}", line_no
    except Exception as exc:
        return False, str(exc), 1


class AIModAgentClient:
    def __init__(self):
        self.config_path = os.path.join(settings.get_user_data_dir(), "ai_agent_config.json")
        self.provider = "gemini"
        self.model = DEFAULT_MODELS["gemini"]
        self.api_key = ""
        self.endpoint = ""
        self._lock = threading.Lock()
        self.busy = False
        self.status_text = ""
        self.error_text = ""
        self.last_response = ""
        self.last_action = "generate"
        self._request_seq = 0
        self._active_seq = 0
        self._request_started_at = None
        self.REQUEST_TIMEOUT = 25
        self._load()

    def _load(self):
        data = settings.safe_read_json(
            self.config_path,
            default=None,
            expected_type=dict,
            try_backups=True,
            self_heal=True,
        )
        if isinstance(data, dict):
            prov = str(data.get("provider", self.provider)).strip().lower()
            if prov in PROVIDER_CHOICES:
                self.provider = prov
            self.model = str(data.get("model", DEFAULT_MODELS.get(self.provider, self.model))).strip()
            self.api_key = str(data.get("api_key", self.api_key)).strip()
            self.endpoint = str(data.get("endpoint", self.endpoint)).strip()
            # Env fallback if config has no key stored
            if not self.api_key:
                self.api_key = str(os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY") or "").strip()
            if self.api_key:
                detected = detect_provider_from_key(self.api_key, self.provider)
                if detected != self.provider and self.api_key.startswith(("AIza", "sk-ant-")):
                    self.provider = detected
                    if self.model in DEFAULT_MODELS.values():
                        self.model = DEFAULT_MODELS[detected]

    def save(self, provider, model, api_key, endpoint=""):
        raw_key = str(api_key or "").strip()
        prov = str(provider or "gemini").strip().lower()
        if prov not in PROVIDER_CHOICES:
            prov = "gemini"
        detected = detect_provider_from_key(raw_key, prov)
        if raw_key.startswith(("AIza", "sk-ant-")) and detected != prov:
            prov = detected
        self.provider = prov
        self.model = str(model or DEFAULT_MODELS.get(prov, "gemini-2.5-flash")).strip() or DEFAULT_MODELS.get(prov, "gemini-2.5-flash")
        self.api_key = raw_key
        self.endpoint = str(endpoint or "").strip()
        settings.atomic_write_json(
            self.config_path,
            {
                "provider": self.provider,
                "model": self.model,
                "api_key": self.api_key,
                "endpoint": self.endpoint,
            },
            indent=2,
            ensure_ascii=False,
            backup=True,
            verify=True,
        )

    def set_api_key(self, api_key, provider=None, model=None, endpoint=None, persist=True):
        raw_key = str(api_key or "").strip()
        prov = str(provider or self.provider or "gemini").strip().lower()
        prov = detect_provider_from_key(raw_key, prov)
        mdl = str(model if model is not None else self.model or "").strip()
        if not mdl or (prov != self.provider and mdl in DEFAULT_MODELS.values()):
            mdl = DEFAULT_MODELS.get(prov, "gemini-2.5-flash")
        ep = str(endpoint if endpoint is not None else self.endpoint or "").strip()
        if persist:
            self.save(prov, mdl, raw_key, ep)
        else:
            self.provider = prov
            self.model = mdl
            self.api_key = raw_key
            self.endpoint = ep
        return self.provider, self.model

    def build_system_prompt(self, action="generate", lang="ru"):
        api_doc = (
            "You are an expert Python & DarkVault modding assistant.\n"
            "DarkVault is a noir Pygame rogue-lite game with monochrome aesthetics.\n"
            "Available Mod Hooks & API:\n"
            "  MOD_NAME = '...'\n"
            "  MOD_DESC = '...'\n"
            "  MOD_AUTHOR = '...'\n"
            "  def on_register(api):\n"
            "      api.add_item({'id': 'my_id', 'name': '...', 'name_en': '...', 'desc': '...', 'desc_en': '...',\n"
            "                    'type': 'passive'|'active', 'max_charge': 4, 'dmg_add': 0.5, 'speed_add': 0.25, ...})\n"
            "      api.add_hero({'id': '...', 'name': '...', 'name_en': '...', 'hp': 6, 'soul_hp': 2, 'damage': 4.0,\n"
            "                    'speed': 4.1, 'fire_delay': 12.0, 'color_body': (220,220,220), 'color_cloak': (80,80,80), 'color_accent': (245,245,245)})\n"
            "  def on_run_start(api, game, player): ...\n"
            "  def on_room_enter(api, game, room, player): ...\n"
            "  def on_update(api, game, dt): ...\n"
            "Rules:\n"
            "- Only use standard Python + pygame + DarkVault api methods.\n"
            "- Write defensive, crash-proof code checking getattr/None.\n"
        )
        if action == "explain":
            lang_hint = "Explain concisely in Russian." if lang == "ru" else "Explain concisely in English."
            return (
                api_doc
                + f"\nExplain what the provided Python code does, list any bugs or edge cases, and how to improve it. {lang_hint}"
            )
        if action == "fix":
            return (
                api_doc
                + "\nFix all syntax errors, runtime bugs, missing imports, or crash risks in the user's code. "
                "Return ONLY the complete fixed Python file without prose or markdown fences."
            )
        if action == "edit":
            return (
                api_doc
                + "\nModify and enhance the provided Python code according to the user's instruction while preserving existing features. "
                "Return ONLY the complete updated Python file without prose or markdown fences."
            )
        return (
            api_doc
            + "\nGenerate a complete, ready-to-run DarkVault Python mod satisfying the user's request. "
            "Return ONLY valid Python code without prose or markdown fences."
        )

    def _build_user_message(self, prompt_text, current_code="", filename="", diagnostics="", action="generate"):
        parts = []
        if filename:
            parts.append(f"Target file: {filename}")
        if diagnostics:
            parts.append(f"Current syntax/runtime diagnostic:\n{diagnostics}")
        if current_code and action in ("edit", "fix", "explain"):
            snippet = current_code if len(current_code) <= 14000 else current_code[:14000] + "\n# ... truncated ..."
            parts.append(f"Current code:\n```python\n{snippet}\n```")
        if prompt_text:
            parts.append(f"Instruction:\n{prompt_text}")
        return "\n\n".join(parts)

    def _urlopen_json(self, req, timeout=25):
        ctx = _build_ssl_context()
        try:
            if ctx is not None:
                resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
            else:
                resp = urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.URLError as exc:
            if isinstance(getattr(exc, "reason", None), ssl.SSLCertVerificationError):
                unverified = ssl._create_unverified_context()
                resp = urllib.request.urlopen(req, timeout=timeout, context=unverified)
            else:
                raise
        except ssl.SSLCertVerificationError:
            unverified = ssl._create_unverified_context()
            resp = urllib.request.urlopen(req, timeout=timeout, context=unverified)
        with resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def _perform_gemini(self, system_prompt, user_message):
        primary_model = (self.model or DEFAULT_MODELS["gemini"]).strip()
        models_to_try = [primary_model]
        for fb in GEMINI_FALLBACK_MODELS:
            if fb not in models_to_try:
                models_to_try.append(fb)

        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_message or "Create a DarkVault mod."}]}],
            "generationConfig": {"temperature": 0.35},
        }
        body_bytes = json.dumps(payload).encode("utf-8")
        last_err = None
        for idx, model_name in enumerate(models_to_try):
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
            req = urllib.request.Request(
                url,
                data=body_bytes,
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": self.api_key,
                },
            )
            try:
                res_data = self._urlopen_json(req, timeout=self.REQUEST_TIMEOUT)
                candidates = res_data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    text = "".join(str(p.get("text", "")) for p in parts if isinstance(p, dict))
                    if text.strip():
                        if idx > 0 and model_name != self.model:
                            self.model = model_name
                        return text
                fb_info = res_data.get("promptFeedback") or {}
                block_reason = fb_info.get("blockReason") if isinstance(fb_info, dict) else ""
                if block_reason:
                    raise RuntimeError(f"Gemini blocked request: {block_reason}")
                raise RuntimeError("Empty response from Gemini API.")
            except urllib.error.HTTPError as exc:
                raw_body = ""
                try:
                    raw_body = exc.read().decode("utf-8", errors="replace")
                except Exception:
                    pass
                msg = _extract_http_error_message(raw_body, exc.reason)
                last_err = RuntimeError(f"Gemini HTTP {exc.code}: {msg}")
                if exc.code == 404 and idx + 1 < len(models_to_try):
                    continue
                raise last_err
            except RuntimeError:
                raise
            except Exception as exc:
                raise RuntimeError(f"Gemini API Error: {exc}")
        if last_err is not None:
            raise last_err
        raise RuntimeError("Gemini request failed.")

    def _perform_http(self, system_prompt, user_message):
        key = str(self.api_key or "").strip()
        if not key and self.provider != "custom":
            raise ValueError("API Key is not configured. Open API Settings in the Agent panel.")

        if self.provider == "gemini":
            return self._perform_gemini(system_prompt, user_message)

        url = self.endpoint.strip() if self.endpoint.strip() else (
            "https://api.openai.com/v1/chat/completions"
            if self.provider in ("openai", "custom")
            else "https://api.anthropic.com/v1/messages"
            if self.provider == "claude"
            else "https://api.deepseek.com/v1/chat/completions"
        )
        headers = {"Content-Type": "application/json"}
        if self.provider == "claude":
            headers["x-api-key"] = key
            headers["anthropic-version"] = "2023-06-01"
            payload = {
                "model": self.model or DEFAULT_MODELS["claude"],
                "max_tokens": 4096,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_message}],
            }
        else:
            if key:
                headers["Authorization"] = f"Bearer {key}"
            payload = {
                "model": self.model or DEFAULT_MODELS.get(self.provider, "gpt-4o-mini"),
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            }
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        try:
            res_data = self._urlopen_json(req, timeout=self.REQUEST_TIMEOUT)
            if self.provider == "claude":
                blocks = res_data.get("content", [])
                return "".join(str(b.get("text", "")) for b in blocks if isinstance(b, dict))
            return str(res_data.get("choices", [{}])[0].get("message", {}).get("content", ""))
        except urllib.error.HTTPError as exc:
            raw_body = ""
            try:
                raw_body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            msg = _extract_http_error_message(raw_body, exc.reason)
            raise RuntimeError(f"{self.provider.upper()} HTTP {exc.code}: {msg}")
        except Exception as exc:
            raise RuntimeError(f"API Error ({self.provider}): {exc}")

    def run_action(self, prompt_text, action="generate", current_code="", filename="", diagnostics="", lang="ru"):
        sys_p = self.build_system_prompt(action=action, lang=lang)
        user_m = self._build_user_message(
            prompt_text,
            current_code=current_code,
            filename=filename,
            diagnostics=diagnostics,
            action=action,
        )
        raw = self._perform_http(sys_p, user_m)
        if action == "explain":
            return raw.strip()
        return self._clean_code_response(raw)

    def generate_mod_code(self, prompt_text):
        return self.run_action(prompt_text, action="generate")

    def start_request(
        self,
        prompt_text,
        action="generate",
        current_code="",
        filename="",
        diagnostics="",
        lang="ru",
        api_key=None,
        provider=None,
        model=None,
        endpoint=None,
    ):
        if api_key is not None or provider is not None or model is not None or endpoint is not None:
            effective_key = api_key if api_key is not None else self.api_key
            self.set_api_key(
                effective_key,
                provider=provider if provider is not None else self.provider,
                model=model if model is not None else self.model,
                endpoint=endpoint if endpoint is not None else self.endpoint,
                persist=bool(str(effective_key or "").strip()),
            )
        with self._lock:
            self._request_seq += 1
            seq = self._request_seq
            self._active_seq = seq
            self.busy = True
            self._request_started_at = time.monotonic()
            self.error_text = ""
            self.last_action = action
            self.status_text = "Thinking..." if lang == "en" else "Запрос к ИИ..."

        def _worker():
            try:
                result = self.run_action(
                    prompt_text,
                    action=action,
                    current_code=current_code,
                    filename=filename,
                    diagnostics=diagnostics,
                    lang=lang,
                )
                with self._lock:
                    if seq == self._active_seq:
                        self.last_response = result
                        self.busy = False
                        self._request_started_at = None
                        ok, err, _ = validate_python_syntax(result) if action != "explain" else (True, "", 0)
                        if action == "explain":
                            self.status_text = "Explanation ready" if lang == "en" else "Объяснение готово"
                        elif ok:
                            self.status_text = "Valid Python ready" if lang == "en" else "Код готов (синтаксис OK)"
                        else:
                            self.status_text = f"Warning: {err}"
            except Exception as exc:
                with self._lock:
                    if seq == self._active_seq:
                        self.busy = False
                        self._request_started_at = None
                        self.error_text = str(exc)
                        self.status_text = str(exc)

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        return seq

    def check_watchdog(self, max_sec=32.0, lang="ru"):
        with self._lock:
            if not self.busy or self._request_started_at is None:
                return False
            if (time.monotonic() - self._request_started_at) >= float(max_sec):
                self._active_seq += 1
                self.busy = False
                self._request_started_at = None
                msg = (
                    f"Request timed out ({int(max_sec)}s). Check internet or API key."
                    if lang == "en"
                    else f"Тайм-аут запроса ({int(max_sec)}с). Проверьте сеть или API ключ."
                )
                self.error_text = msg
                self.status_text = msg
                return True
        return False

    def cancel(self, lang="ru"):
        with self._lock:
            self._active_seq += 1
            self.busy = False
            self._request_started_at = None
            self.status_text = "Cancelled" if lang == "en" else "Отменено"

    def _clean_code_response(self, text):
        t = (text or "").strip()
        if t.startswith("```python"):
            t = t[9:]
        elif t.startswith("```py"):
            t = t[5:]
        elif t.startswith("```"):
            t = t[3:]
        if t.endswith("```"):
            t = t[:-3]
        return t.strip()


ai_agent_client = AIModAgentClient()
