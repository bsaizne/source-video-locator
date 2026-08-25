"""Low-level subprocess helpers for the FFmpegIO module.

Cross-platform (Windows / macOS). On Windows a GUI app must never flash a
console window per spawned subprocess, so we pass ``CREATE_NO_WINDOW`` to every
``subprocess`` call. Every failure surfaces as :class:`MediaError` carrying the
tail of the subprocess stderr, so the UI can show a meaningful reason instead of
a silent ``returncode != 0``.

The module also owns binary resolution (ffmpeg / ffprobe) so the rest of the
product never hard-codes a path to a machine-specific binary.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from infrastructure.errors import LocatorError

# Windows: prevent a console window flashing for each spawned process. 0 on
# non-Windows so the flag is harmless.
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

# Applied to every ffmpeg/ffprobe invocation: no banner, errors only, never read
# stdin (so a GUI process that owns a console cannot hang by accident).
BASE_ARGS = ["-hide_banner", "-loglevel", "error", "-nostdin"]


class MediaError(LocatorError):
    """A video / FFmpeg / ffprobe operation failed.

    Subclasses :class:`infrastructure.errors.LocatorError` so the UI can catch any
    product-runtime failure at the base type. Raised for: unreadable file,
    unsupported codec, bad seek, invalid clip range, timeout, missing binary.
    Carries the tail of the subprocess stderr.
    """


def _brief(args: list[str], *, n: int = 8) -> str:
    return " ".join(f"{a!r}" if " " in a else a for a in args[:n])


def _error_tail(stderr: bytes | str | None, *, n: int = 1500) -> str:
    text = stderr.decode(errors="replace") if isinstance(stderr, bytes) else (stderr or "")
    return text.strip()[-n:].strip()


def check_run(args: list[str], *, timeout: float = 600.0) -> str:
    """Run a command to completion and return its stdout as text.

    ``args`` is the FULL command (starting with the ffmpeg/ffprobe binary).
    Raises :class:`MediaError` on non-zero exit or timeout.
    """
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            timeout=timeout,
            check=False,
            creationflags=CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired as exc:
        raise MediaError(
            f"command timed out after {timeout:.0f}s: {_brief(args)}"
        ) from exc
    if proc.returncode != 0:
        raise MediaError(
            f"command failed (rc={proc.returncode}): {_brief(args)}\n"
            f"{_error_tail(proc.stderr)}"
        )
    return proc.stdout.decode("utf-8", errors="replace")


def popen(args: list[str]) -> subprocess.Popen:
    """Start a long-running command with piped stdout/stderr (streaming use).

    Used by :meth:`FFmpegIO.iter_frames` which reads raw frame bytes from stdout
    incrementally instead of buffering the whole output.
    """
    return subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW,
    )


# --------------------------------------------------------------------------- #
# Binary resolution
# --------------------------------------------------------------------------- #

def _exe_name(base: str) -> str:
    return f"{base}.exe" if os.name == "nt" else base


def _repo_tools(name: str) -> Path | None:
    """Look for ``tools/<name>`` walking up from this package (dev repo layout)."""
    for parent in Path(__file__).resolve().parents:
        cand = parent / "tools" / _exe_name(name)
        if cand.exists():
            return cand
    return None


def _from_env(key: str) -> Path | None:
    val = os.environ.get(key)
    return Path(val) if val else None


def _locate(name: str) -> Path | None:
    """Resolve a binary (ffmpeg / ffprobe): env -> repo tools -> PATH."""
    hint = _from_env(f"MEDIA_{name.upper()}")
    if hint and hint.exists():
        return hint
    repo = _repo_tools(name)
    if repo:
        return repo
    on_path = shutil.which(name)
    return Path(on_path) if on_path else None


def resolve_binaries(ffmpeg: str | Path | None = None,
                     ffprobe: str | Path | None = None) -> tuple[Path, Path]:
    """Return (ffmpeg, ffprobe) as Paths, resolving each in order.

    Order per binary: explicit ``ffmpeg``/``ffprobe`` argument -> env var
    ``MEDIA_FFMPEG`` / ``MEDIA_FFPROBE`` -> a ``tools/`` dir next to this package
    (dev repo layout) -> ``PATH`` via shutil.which. Raises :class:`MediaError` if
    either is unresolvable.
    """
    def _one(name: str, explicit: str | Path | None) -> Path | None:
        if explicit:
            p = Path(explicit)
            if p.exists():
                return p
            raise MediaError(f"given {name} binary does not exist: {explicit}")
        return _locate(name)

    ffmpeg_p = _one("ffmpeg", ffmpeg)
    ffprobe_p = _one("ffprobe", ffprobe)
    if ffmpeg_p is None:
        raise MediaError(
            "ffmpeg binary not found; set MEDIA_FFMPEG or pass ffmpeg= to FFmpegIO"
        )
    if ffprobe_p is None:
        raise MediaError(
            "ffprobe binary not found; set MEDIA_FFPROBE or pass ffprobe= to FFmpegIO"
        )
    return ffmpeg_p, ffprobe_p
