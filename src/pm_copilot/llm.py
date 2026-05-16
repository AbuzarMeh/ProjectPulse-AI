"""LLM provider integration (Ollama + OpenAI-compatible APIs like Groq)."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional


_DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def _http_json(
    url: str,
    payload: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
    timeout_s: int = 120,
) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": _DEFAULT_UA,
    }
    if headers:
        req_headers.update(headers)

    req = urllib.request.Request(url=url, data=data, headers=req_headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise RuntimeError(f"HTTP {e.code} calling {url}: {body or e.reason}") from e
    except (TimeoutError, socket.timeout) as e:
        raise RuntimeError(
            f"Timeout calling {url}. Try increasing --timeout (e.g., 600) or use a smaller/faster model."
        ) from e
    except urllib.error.URLError as e:
        msg = str(e)
        if "timed out" in msg.lower():
            raise RuntimeError(
                f"Timeout calling {url}. Try increasing --timeout (e.g., 600) or use a smaller/faster model."
            ) from e
        raise RuntimeError(f"Network error calling {url}: {e}") from e


def _http_get_json(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout_s: int = 60,
) -> Dict[str, Any]:
    req_headers = {
        "Accept": "application/json",
        "User-Agent": _DEFAULT_UA,
    }
    if headers:
        req_headers.update(headers)

    req = urllib.request.Request(url=url, headers=req_headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise RuntimeError(f"HTTP {e.code} calling {url}: {body or e.reason}") from e
    except (TimeoutError, socket.timeout) as e:
        raise RuntimeError(
            f"Timeout calling {url}. Try increasing --timeout (e.g., 60) and ensure Ollama is running."
        ) from e
    except urllib.error.URLError as e:
        msg = str(e)
        if "timed out" in msg.lower():
            raise RuntimeError(
                f"Timeout calling {url}. Try increasing --timeout (e.g., 60) and ensure Ollama is running."
            ) from e
        raise RuntimeError(f"Network error calling {url}: {e}") from e


def list_ollama_models(*, base_url: str, timeout_s: int) -> List[str]:
    url = base_url.rstrip("/") + "/api/tags"
    resp = _http_get_json(url, timeout_s=timeout_s)
    models = resp.get("models", [])
    names: List[str] = []
    if isinstance(models, list):
        for m in models:
            if isinstance(m, dict) and isinstance(m.get("name"), str):
                names.append(m["name"])
    return sorted(set(names))


def resolve_ollama_model(*, base_url: str, requested: str, timeout_s: int) -> str:
    requested = requested.strip()
    if not requested:
        return requested

    try:
        available = list_ollama_models(base_url=base_url, timeout_s=timeout_s)
    except Exception:
        return requested

    if requested in available:
        return requested

    if ":" in requested:
        return requested

    candidates = [m for m in available if m == requested or m.startswith(requested + ":")]
    if not candidates:
        return requested

    for preferred in (requested + ":latest", requested + ":8b", requested + ":7b"):
        if preferred in candidates:
            return preferred

    return candidates[0]


def call_ollama_chat(
    *,
    base_url: str,
    model: str,
    messages: List[Dict[str, str]],
    timeout_s: int,
    max_tokens: int,
) -> str:
    url = base_url.rstrip("/") + "/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.2,
            "num_predict": int(max_tokens),
        },
    }
    resp = _http_json(url, payload, timeout_s=timeout_s)
    try:
        return resp["message"]["content"]
    except Exception as e:
        raise RuntimeError(f"Unexpected Ollama response shape: {resp}") from e


def call_openai_compat_chat(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: List[Dict[str, str]],
    timeout_s: int,
    max_tokens: int,
) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": int(max_tokens),
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = _http_json(url, payload, headers=headers, timeout_s=timeout_s)
    try:
        return resp["choices"][0]["message"]["content"]
    except Exception as e:
        raise RuntimeError(f"Unexpected OpenAI-compatible response shape: {resp}") from e


def list_openai_compat_models(*, base_url: str, api_key: str, timeout_s: int) -> List[str]:
    url = base_url.rstrip("/") + "/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = _http_get_json(url, headers=headers, timeout_s=timeout_s)

    data = resp.get("data", [])
    names: List[str] = []
    if isinstance(data, list):
        for m in data:
            if isinstance(m, dict) and isinstance(m.get("id"), str):
                names.append(m["id"])

    return sorted(set(names))
