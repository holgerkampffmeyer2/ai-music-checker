"""Optional LLM second-opinion judge."""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

CACHE_DIR = Path.home() / ".cache" / "ai-music-checker" / "llm"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class LLMResult:
    probability: float
    confidence: float
    reasoning: str
    agrees_with_deterministic: bool
    key_disagreements: list[str]


class LLMBackend(Protocol):
    def analyze(self, prompt: str, model: str) -> dict[str, Any]: ...


class BaseCurlBackend:
    def __init__(self, api_key: str, endpoint: str):
        self.api_key = api_key
        self.endpoint = endpoint

    def analyze(self, prompt: str, model: str) -> dict[str, Any]:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are an expert audio forensics analyst. Respond with JSON only."},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        import shlex
        import subprocess as sp
        cmd = f"curl -s -X POST {shlex.quote(self.endpoint)} -H 'Authorization: Bearer {self.api_key}' -H 'Content-Type: application/json' -d {shlex.quote(json.dumps(payload))}"
        proc = sp.run(cmd, shell=True, capture_output=True, text=True, timeout=60, check=False)
        if proc.returncode != 0:
            raise RuntimeError(f"Request failed: {proc.stderr}")
        return json.loads(proc.stdout)


class OpenRouterBackend(BaseCurlBackend):
    def __init__(self, api_key: str):
        super().__init__(api_key, "https://openrouter.ai/api/v1/chat/completions")


class OllamaBackend:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url.rstrip("/")

    def analyze(self, prompt: str, model: str) -> dict[str, Any]:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are an expert audio forensics analyst. Respond with JSON only."},
                {"role": "user", "content": prompt},
            ],
            "format": "json",
        }
        import shlex
        import subprocess as sp
        url = f"{self.base_url}/api/chat"
        cmd = f"curl -s -X POST {shlex.quote(url)} -H 'Content-Type: application/json' -d {shlex.quote(json.dumps(payload))}"
        proc = sp.run(cmd, shell=True, capture_output=True, text=True, timeout=60, check=False)
        if proc.returncode != 0:
            raise RuntimeError(f"Ollama request failed: {proc.stderr}")
        data = json.loads(proc.stdout)
        content = data.get("message", {}).get("content", "{}")
        return {"choices": [{"message": {"content": content}}]}


def build_prompt_v1(aggregate: Any, probe: Any, signals: list[Any] | None = None, press_text: str | None = None) -> str:
    signals_summary = []
    sigs = signals or []
    for s in sigs:
        signals_summary.append(f"{getattr(s, 'id', '?')}: subscore={getattr(s, 'subscore', '?')} note={getattr(s, 'note', '')}")
    prompt = (
        "Analyze the following audio forensic signals and give an AI-generation probability.\n"
        f"File: {getattr(probe.path, 'name', '?')}, duration {getattr(probe, 'duration', '?')} s, sample_rate {getattr(probe, 'sample_rate', '?')}\n"
        f"Aggregate AI probability: {getattr(aggregate, 'ai_probability', '?')}\n"
        "Signals:\n" + "\n".join(signals_summary)
    )
    if press_text:
        prompt += f"\nPress text:\n{press_text}"
    prompt += "\nRespond with JSON: {\"probability\": float 0-1, \"confidence\": float 0-1, \"reasoning\": str, \"agrees_with_deterministic\": bool, \"key_disagreements\": []}"
    return prompt


def _cache_key(prompt: str, model: str) -> str:
    h = hashlib.sha256((prompt + model).encode()).hexdigest()
    return h


def judge(aggregate: Any, signals: list[Any], probe: Any, config: Any) -> dict[str, Any] | None:
    llm_cfg = getattr(config, "llm_judge", {}) or {}
    backend_name = llm_cfg.get("backend", "openrouter")
    model = llm_cfg.get("model", "openai/gpt-4o-mini")
    prompt = build_prompt_v1(aggregate, probe, signals)
    key = _cache_key(prompt, model)
    cache_file = CACHE_DIR / f"{key}.json"
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text())
            return data
        except (OSError, json.JSONDecodeError):
            pass
    if backend_name == "llm-agent":
        result = {
            "mode": "llm-agent",
            "backend": "llm-agent",
            "model": "agent",
            "prompt": prompt,
            "context": {
                "aggregate_ai_probability": getattr(aggregate, "ai_probability", None),
                "aggregate_verdict": getattr(aggregate, "verdict", None),
                "probe_name": getattr(getattr(probe, "path", None), "name", None),
                "signals": [
                    {
                        "id": getattr(s, "id", None),
                        "subscore": getattr(s, "subscore", None),
                        "note": getattr(s, "note", None),
                    }
                    for s in signals
                ],
            },
        }
        try:
            cache_file.write_text(json.dumps(result))
        except OSError:
            pass
        return result
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return None
    if backend_name == "openrouter":
        backend: LLMBackend = OpenRouterBackend(api_key)
    elif backend_name == "ollama":
        backend = OllamaBackend()
    else:
        backend = OpenRouterBackend(api_key)
    try:
        resp = backend.analyze(prompt, model)
        content = resp.get("choices", [{}])[0].get("message", {}).get("content", "{}")
        result = json.loads(content)
        result.setdefault("backend", backend_name)
        result.setdefault("model", model)
        cache_file.write_text(json.dumps(result))
        return result
    except (RuntimeError, OSError, json.JSONDecodeError):
        return None
