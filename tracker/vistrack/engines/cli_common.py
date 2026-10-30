"""Shared helpers for engines that drive a subscription CLI (codex, claude) as a subprocess."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

QUOTA_PATTERN = re.compile(
    r"usage limit|rate limit|quota|too many requests|\b429\b|limit reached|reached your|try again (?:in|later|at)",
    re.I,
)
AUTH_PATTERN = re.compile(
    r"not logged in|log ?in required|please log ?in|failed to authenticate|oauth session expired|unauthorized|\b401\b",
    re.I,
)

# Only these variables reach a CLI agent that can read its environment (secrets from .env stay out).
ENV_ALLOWLIST = (
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "SYSTEMDRIVE",
    "WINDIR",
    "COMSPEC",
    "USERPROFILE",
    "USERNAME",
    "HOME",
    "HOMEDRIVE",
    "HOMEPATH",
    "APPDATA",
    "LOCALAPPDATA",
    "PROGRAMDATA",
    "PROGRAMFILES",
    "PROGRAMFILES(X86)",
    "TEMP",
    "TMP",
    "TMPDIR",
    "OS",
    "PROCESSOR_ARCHITECTURE",
    "NUMBER_OF_PROCESSORS",
    "LANG",
    "LC_ALL",
    "TZ",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "ALL_PROXY",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "REQUESTS_CA_BUNDLE",
    "NODE_EXTRA_CA_CERTS",
    "CODEX_HOME",
    "CLAUDE_CONFIG_DIR",  # paths, not secrets: where the CLI keeps its login
)


@dataclass
class ProcResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


Runner = Callable[[list[str], str, Path, dict[str, str], int], ProcResult]


def _kill_tree(proc: subprocess.Popen) -> None:
    """subprocess.run(timeout=) only kills the direct child; a .cmd shim leaves its node child running."""
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    else:
        proc.kill()


def run_subprocess(cmd: list[str], stdin: str, cwd: Path, env: dict[str, str], timeout: int) -> ProcResult:
    with subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=cwd,
        env=env,
    ) as proc:
        try:
            out, err = proc.communicate(stdin, timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_tree(proc)
            out, err = proc.communicate()
            return ProcResult(-1, out or "", "timeout", timed_out=True)
        return ProcResult(proc.returncode, out, err)


@contextmanager
def empty_workdir(prefix: str) -> Iterator[Path]:
    """Fresh empty directory (the CLI must not see any project files), removed afterwards."""
    path = Path(tempfile.mkdtemp(prefix=prefix))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def allowlist_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Child environment built from ENV_ALLOWLIST only, plus `extra`."""
    wanted = {n.upper() for n in ENV_ALLOWLIST}
    env = {k: v for k, v in os.environ.items() if k.upper() in wanted}
    env.update(extra or {})
    return env


def classify_failure(text: str) -> tuple[bool, str]:
    """(fatal, kind). Fatal = stop the batch (quota/auth), nothing to gain by retrying."""
    if AUTH_PATTERN.search(text):
        return True, "auth"
    if QUOTA_PATTERN.search(text):
        return True, "quota"
    return False, "other"
