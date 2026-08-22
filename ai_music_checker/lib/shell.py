"""Vendored shell utilities from wav-to-aac-converter."""
from __future__ import annotations

import shlex
import subprocess


class NetworkError(Exception):
    pass


def shq(s: str) -> str:
    """Shell-quote a string safely."""
    return shlex.quote(s)


def run_cmd(cmd: str, timeout: int = 60) -> tuple[bool, str, str]:
    """Run shell command, return (success, stdout, stderr)."""
    try:
        proc = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout, check=False
        )
        return proc.returncode == 0, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except (OSError, ValueError) as e:
        return False, "", str(e)


def retry(func, attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Retry function with exponential backoff."""
    import time
    last_exc = None
    for i in range(attempts):
        try:
            return func()
        except (OSError, ValueError) as e:
            last_exc = e
            if i < attempts - 1:
                time.sleep(delay * (backoff ** i))
    raise last_exc