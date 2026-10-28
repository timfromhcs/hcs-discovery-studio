"""Hatch build hook.

``uv sync`` installs this project in editable mode, and the wheel target
force-includes the compiled single-page application. On a fresh checkout that
directory does not exist until ``npm run build`` has run, which made Python-only
setup fail. Creating the empty directory keeps editable installs working; the
server reports that no UI is available until the SPA is built, and release
builds still compile the frontend before building the wheel.
"""

from __future__ import annotations

from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict) -> None:
        (Path(self.root) / "apps" / "web" / "dist").mkdir(parents=True, exist_ok=True)
