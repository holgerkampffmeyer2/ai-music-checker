"""Vendored HTTP utilities from wav-to-aac-converter."""
from __future__ import annotations

import os
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_TIMEOUT = 10
USER_AGENT = "ai-music-checker/0.1.0 (+https://github.com/holgerkampffmeyer2/ai-music-checker)"


class NetworkError(Exception):
    """Network-related error."""


def load_env() -> None:
    """Load .env file if present."""
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ.setdefault(key.strip(), val.strip())


def fetch_url(url: str, timeout: int = DEFAULT_TIMEOUT, retries: int = 2) -> str | None:
    """Fetch URL with retries and error handling."""
    load_env()
    req = Request(url, headers={"User-Agent": USER_AGENT})
    last_exc = None
    for attempt in range(retries + 1):
        try:
            with urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except HTTPError as e:
            if e.code == 304:
                return None
            if (500 <= e.code < 600 or e.code == 429) and attempt < retries:
                time.sleep(1 * (2 ** attempt))
                last_exc = NetworkError(f"HTTP {e.code}: {e.reason} (retry {attempt+1})")
                continue
            raise NetworkError(f"HTTP {e.code}: {e.reason}")
        except URLError as e:
            last_exc = NetworkError(f"URL error: {e.reason}")
            if attempt < retries:
                time.sleep(1 * (2 ** attempt))
                continue
            raise last_exc
        except TimeoutError:
            last_exc = NetworkError("Request timeout")
            if attempt < retries:
                time.sleep(1 * (2 ** attempt))
                continue
            raise last_exc
    raise last_exc


def retry(func, attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Retry function with exponential backoff."""
    last_exc = None
    for i in range(attempts):
        try:
            return func()
        except (OSError, ValueError) as e:
            last_exc = e
            if i < attempts - 1:
                time.sleep(delay * (backoff ** i))
    raise last_exc