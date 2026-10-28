"""Vulkan capability probing.

We report what the host actually exposes. A Vulkan device does **not** imply that
any scientific model can use it; per-model backends must be proven separately.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from typing import Any


def probe_vulkan(*, timeout: float = 20.0) -> dict[str, Any]:
    executable = shutil.which("vulkaninfo")
    if executable is None:
        return {
            "available": False,
            "status": "unavailable",
            "detail": "vulkaninfo was not found on PATH.",
            "remediation": "Install the Vulkan SDK/runtime if you want optional Vulkan-backed inference.",
            "devices": [],
            "model_support": "unknown",
        }
    try:
        completed = subprocess.run(
            [executable, "--summary"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "available": False,
            "status": "error",
            "detail": f"vulkaninfo failed: {type(exc).__name__}",
            "devices": [],
            "model_support": "unknown",
        }
    output = f"{completed.stdout}\n{completed.stderr}"
    devices: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in output.splitlines():
        if re.match(r"^GPU\d+:", line.strip()):
            current = {}
            devices.append(current)
            continue
        if current is not None and "=" in line:
            key, _, value = line.partition("=")
            current[key.strip()] = value.strip()
    instance_match = re.search(r"Vulkan Instance Version:\s*([\w.\-]+)", output)
    return {
        "available": bool(devices),
        "status": "detected" if devices else "no_device",
        "detail": f"{len(devices)} Vulkan device(s) reported by vulkaninfo.",
        "instance_version": instance_match.group(1) if instance_match else None,
        "devices": devices,
        "model_support": "unknown",
        "note": (
            "Vulkan presence is not a model capability. Each model adapter must prove its backend "
            "support before the UI advertises it."
        ),
    }
