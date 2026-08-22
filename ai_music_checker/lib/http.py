"""Vendored HTTP utilities from wav-to-aac-converter."""
from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


DEFAULT_TIMEOUT = 10
USER_AGENT = "ai-music-checker/0.1.0 (+https://github.com/holgerkampffmeyer2/ai-music-checker)"


class NetworkError(Exception):
    """Network-related error."""
    pass


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


def fetch_url(url: str, timeout: int = DEFAULT_TIMEOUT) -> Optional[str]:
    """Fetch URL with retries and error handling."""
    load_env()
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        if e.code == 304:
            return None  # Not modified
        raise NetworkError(f"HTTP {e.code}: {e.reason}")
    except URLError as e:
        raise NetworkError(f"URL error: {e.reason}")
    except TimeoutError:
        raise NetworkError("Request timeout")


def retry(func, attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Retry function with exponential backoff."""
    last_exc = None
    for i in range(attempts):
        try:
            return func()
        except Exception as e:
            last_exc = e
            if i < attempts - 1:
                time.sleep(delay * (backoff ** i))
    raise last_exc