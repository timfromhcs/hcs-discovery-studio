"""Safe filesystem path handling for untrusted names and relative artifact paths."""

from __future__ import annotations

import os
import re
from pathlib import Path

from .errors import ValidationError

_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED_WINDOWS = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def safe_filename(name: str, *, fallback: str = "file", max_length: int = 120) -> str:
    """Return a single path component that is safe on Windows and POSIX."""
    candidate = Path(name.replace("\\", "/")).name
    candidate = _UNSAFE.sub("_", candidate).strip(" .")
    if not candidate:
        candidate = fallback
    stem, dot, suffix = candidate.rpartition(".")
    if dot and stem and len(suffix) <= 10:
        candidate = f"{stem[: max_length - len(suffix) - 1]}.{suffix}"
    else:
        candidate = candidate[:max_length]
    if candidate.split(".")[0].upper() in _RESERVED_WINDOWS:
        candidate = f"_{candidate}"
    return candidate


def safe_join(base: Path, *parts: str) -> Path:
    """Join ``parts`` under ``base``, rejecting traversal and absolute segments."""
    for part in parts:
        piece = Path(part)
        if piece.is_absolute() or piece.drive:
            raise ValidationError("Absolute paths are not allowed here.", details={"part": part})
    # realpath + prefix check (rather than Path.parents) is the containment idiom
    # that static analysers such as CodeQL recognise as a path-injection guard.
    base_resolved = os.path.realpath(base)
    target = os.path.realpath(os.path.join(base_resolved, *parts))
    prefix = base_resolved.rstrip(os.sep) + os.sep
    if target != base_resolved and not target.startswith(prefix):
        raise ValidationError("Path escapes the allowed directory.", details={"part": target})
    return Path(target)


def relative_artifact_path(run_dir: Path, file_path: Path) -> str:
    """Validate that ``file_path`` lives inside ``run_dir`` and return a POSIX relative path."""
    run_resolved = run_dir.resolve()
    file_resolved = file_path.resolve()
    if file_resolved != run_resolved and run_resolved not in file_resolved.parents:
        raise ValidationError("Artifact path is outside the run directory.", details={"path": str(file_path)})
    return file_resolved.relative_to(run_resolved).as_posix()
