"""LLM provider routing for Songwriter.

Hybrid routing:
  DRAFT    → Anthropic Sonnet   (best creative quality, ~$0.008/call)
  REPAIR   → Anthropic Haiku    (targeted line fixes, ~$0.003/call)
  VALIDATE → Google Gemini Flash (~0.5s, ~$0.00007/call — fact-checks only)
  SUNO     → Google Gemini Flash (~0.5s, ~$0.00003/call)
  GENERAL  → Cerebras Qwen3     (default fast path)

Fallback chain: Anthropic API → claude --print CLI (if key absent)

Total cost per song: ~1.2-1.5 cents
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from typing import Any

from songwriter.api.settings import Settings, get_settings


log = logging.getLogger("songwriter.llm")
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")


class LLMError(RuntimeError):
    pass


# Per-task output caps
TASK_MAX_TOKENS: dict[str, int] = {
    "DRAFT":    1800,
    "REPAIR":   800,
    "VALIDATE": 400,
    "SUNO":     250,
    "GENERAL":  1000,
}

# Task → provider routing
_ANTHROPIC_TASKS = {"DRAFT", "REPAIR"}   # quality writing
_GEMINI_TASKS    = {"VALIDATE", "SUNO"}  # fast/cheap fact-checks

# Anthropic pricing per token (approximate)
_SONNET_IN  = 0.000003    # $3/MTok
_SONNET_OUT = 0.000015    # $15/MTok
_HAIKU_IN   = 0.0000008   # $0.80/MTok
_HAIKU_OUT  = 0.000004    # $4/MTok

# Cerebras: ~$0.60/MTok combined
_CEREBRAS_COST_PER_TOKEN = 0.0000006

# Gemini Flash 2.0: $0.10/MTok in, $0.40/MTok out
_GEMINI_IN  = 0.0000001   # $0.10/MTok
_GEMINI_OUT = 0.0000004   # $0.40/MTok

_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)

# System prompt injected for both providers
_SYSTEM_PROMPT = (
    "You are a skilled lyricist. "
    "Your non-negotiable rule: the genre (rap, rock, pop, etc.) sets the RHYTHM only. "
    "The song brief sets the WORLD — and every image, noun, and metaphor must come from that world. "
    "Fantasy RPG world → swords, ruins, dragons, ancient gates. "
    "House party world → red cups, bass, kitchen tiles, someone passed out on the couch. "
    "Trap/money world → wire transfers, lease documents, stacks of bills. "
    "Never substitute generic genre tropes for the specific world in the brief. "
    "Write concrete, singable lines that could only exist in THIS song."
)


def _tag(prompt: str) -> str:
    first = prompt.lstrip().splitlines()[0] if prompt.strip() else ""
    return (first[:60] + "…") if len(first) > 60 else first or "(empty)"


# ── JSON extraction ───────────────────────────────────────────────────────────

def _extract_json(raw: str) -> Any:
    raw = (raw or "").strip()

    m = _JSON_FENCE.search(raw)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Balanced-brace fallback — scan from first { or [
    starts = [i for i, c in enumerate(raw) if c in "{["]
    if not starts:
        raise LLMError(f"no JSON found in LLM output:\n{raw[:400]}")
    start = starts[0]
    for end in range(len(raw), start, -1):
        try:
            return json.loads(raw[start:end])
        except json.JSONDecodeError:
            continue

    raise LLMError(f"could not parse JSON from LLM output:\n{raw[:400]}")


# ── Anthropic Messages API ────────────────────────────────────────────────────

_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


def _anthropic_key(settings: Settings) -> str:
    path = os.path.expanduser(settings.anthropic_key_path)
    if os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    return os.environ.get("ANTHROPIC_API_KEY", "")


def _ask_anthropic(prompt: str, task: str, settings: Settings) -> str:
    key = _anthropic_key(settings)
    if not key:
        raise LLMError("no Anthropic key (checked ~/.maxrpg_api_key and ANTHROPIC_API_KEY env)")

    # DRAFT → Sonnet (quality); REPAIR → Haiku (speed + cost)
    model = settings.anthropic_sonnet_id if task == "DRAFT" else settings.anthropic_haiku_id
    in_rate  = _SONNET_IN  if task == "DRAFT" else _HAIKU_IN
    out_rate = _SONNET_OUT if task == "DRAFT" else _HAIKU_OUT

    max_tokens = TASK_MAX_TOKENS.get(task, 1000)
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": _SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": prompt}],
    }
    req = urllib.request.Request(
        _ANTHROPIC_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=settings.llm_timeout_s) as resp:
            raw = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode())
            msg = err.get("error", {}).get("message", str(e))
        except Exception:
            msg = str(e)
        raise LLMError(f"Anthropic HTTP {e.code}: {msg}")
    except Exception as e:
        raise LLMError(f"Anthropic request failed: {e}")

    elapsed = time.perf_counter() - t0
    content = raw.get("content") or []
    text = next((b["text"] for b in content if b.get("type") == "text"), "")
    usage = raw.get("usage", {})
    in_tok  = usage.get("input_tokens",  max(1, len(prompt) // 4))
    out_tok = usage.get("output_tokens", max(1, len(text) // 4))
    cost = in_tok * in_rate + out_tok * out_rate
    log.info(
        f"[llm] task={task} provider=anthropic model={model} "
        f"in={in_tok} out={out_tok} cost≈${cost:.4f} latency={elapsed:.1f}s"
    )
    return text.strip()


# ── Cerebras ──────────────────────────────────────────────────────────────────

_CEREBRAS_URL = "https://api.cerebras.ai/v1/chat/completions"


def _cerebras_key(settings: Settings) -> str:
    path = os.path.expanduser(settings.cerebras_key_path)
    if os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    return os.environ.get("CEREBRAS_API_KEY", "")


def _ask_cerebras(prompt: str, task: str, settings: Settings) -> str:
    key = _cerebras_key(settings)
    if not key:
        raise LLMError("no Cerebras key (checked ~/.cerebras_api_key and CEREBRAS_API_KEY env)")

    max_tokens = TASK_MAX_TOKENS.get(task, 1000)
    payload = {
        "model": settings.cerebras_model_id,
        "max_tokens": max_tokens,
        "temperature": 0.85,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    }
    req = urllib.request.Request(
        _CEREBRAS_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
            "User-Agent": "songwriter/1.0",
        },
        method="POST",
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=settings.llm_timeout_s) as resp:
            raw = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode()).get("error") or {}
            msg = err.get("message", str(e)) if isinstance(err, dict) else str(err)
        except Exception:
            msg = str(e)
        raise LLMError(f"Cerebras HTTP {e.code}: {msg}")
    except Exception as e:
        raise LLMError(f"Cerebras request failed: {e}")

    elapsed = time.perf_counter() - t0
    text = (raw.get("choices") or [{}])[0].get("message", {}).get("content", "")
    in_est  = max(1, len(prompt) // 4)
    out_est = max(1, len(text) // 4)
    cost_est = (in_est + out_est) * _CEREBRAS_COST_PER_TOKEN
    log.info(
        f"[llm] task={task} provider=cerebras model={settings.cerebras_model_id} "
        f"in≈{in_est} out≈{out_est} cost≈${cost_est:.4f} latency={elapsed:.1f}s"
    )
    return text.strip()


# ── Google Gemini Flash ───────────────────────────────────────────────────────

def _gemini_key(settings: Settings) -> str:
    path = os.path.expanduser(settings.gemini_key_path)
    if os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    return os.environ.get("GEMINI_API_KEY", "")


def _ask_gemini(prompt: str, task: str, settings: Settings) -> str:
    key = _gemini_key(settings)
    if not key:
        raise LLMError("no Gemini key (checked ~/.gemini_api_key and GEMINI_API_KEY env)")

    model = settings.gemini_model_id
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    max_tokens = TASK_MAX_TOKENS.get(task, 1000)
    payload = {
        "systemInstruction": {"parts": [{"text": _SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.7},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=settings.llm_timeout_s) as resp:
            raw = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode())
            msg = err.get("error", {}).get("message", str(e))
        except Exception:
            msg = str(e)
        raise LLMError(f"Gemini HTTP {e.code}: {msg}")
    except Exception as e:
        raise LLMError(f"Gemini request failed: {e}")

    elapsed = time.perf_counter() - t0
    candidates = raw.get("candidates") or []
    text = ""
    if candidates:
        parts = candidates[0].get("content", {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts)
    usage = raw.get("usageMetadata", {})
    in_tok  = usage.get("promptTokenCount",     max(1, len(prompt) // 4))
    out_tok = usage.get("candidatesTokenCount", max(1, len(text) // 4))
    cost = in_tok * _GEMINI_IN + out_tok * _GEMINI_OUT
    log.info(
        f"[llm] task={task} provider=gemini model={model} "
        f"in={in_tok} out={out_tok} cost≈${cost:.5f} latency={elapsed:.1f}s"
    )
    return text.strip()


# ── claude --print fallback ───────────────────────────────────────────────────

def _ask_cli(prompt: str, model: str | None, settings: Settings) -> str:
    cmd = [settings.claude_cli]
    if model:
        cmd += ["--model", model]
    cmd += ["--print", prompt]
    t0 = time.perf_counter()
    log.info(f"[llm] task=CLI ({model or 'default'}): {_tag(prompt)!r}")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=settings.llm_timeout_s)
    except subprocess.TimeoutExpired:
        raise LLMError(f"claude --print timed out after {time.perf_counter() - t0:.1f}s")
    elapsed = time.perf_counter() - t0
    if proc.returncode != 0:
        raise LLMError(f"claude --print failed (exit {proc.returncode}): {proc.stderr.strip()}")
    log.info(f"[llm] task=CLI ok in {elapsed:.1f}s")
    return proc.stdout.strip()


# ── Public API ────────────────────────────────────────────────────────────────

def ask_llm(prompt: str, *, task: str = "GENERAL", settings: Settings | None = None) -> str:
    """Route to the right provider based on task.

    DRAFT/REPAIR  → Anthropic (Sonnet/Haiku); falls back to CLI if no key.
    VALIDATE/SUNO → Gemini Flash; falls back to Cerebras if no key.
    GENERAL       → Cerebras.
    """
    settings = settings or get_settings()
    if task in _ANTHROPIC_TASKS:
        if _anthropic_key(settings):
            return _ask_anthropic(prompt, task, settings)
        log.warning(f"[llm] no Anthropic API key — falling back to claude CLI for {task}")
        return _ask_cli(prompt, settings.anthropic_sonnet_id, settings)
    if task in _GEMINI_TASKS:
        if _gemini_key(settings):
            return _ask_gemini(prompt, task, settings)
        log.warning(f"[llm] no Gemini key — falling back to Cerebras for {task}")
    return _ask_cerebras(prompt, task, settings)


def ask_llm_json(prompt: str, *, task: str = "GENERAL", settings: Settings | None = None) -> Any:
    raw = ask_llm(prompt, task=task, settings=settings)
    return _extract_json(raw)


# ── Backwards-compat aliases (CLI-based, kept so existing tests pass) ─────────

def ask_claude(prompt: str, *, settings: Settings | None = None, model: str | None = None) -> str:
    settings = settings or get_settings()
    return _ask_cli(prompt, model, settings)


def ask_claude_json(prompt: str, *, settings: Settings | None = None, model: str | None = None) -> Any:
    raw = ask_claude(prompt, settings=settings, model=model)
    return _extract_json(raw)
