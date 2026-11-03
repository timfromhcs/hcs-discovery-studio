"""PyInstaller launcher for the hcs-discovery CLI.

PyInstaller needs a script entry point; the console_script
``hcs-discovery = hcs_discovery.cli.main:cli`` is imported here so the frozen
executable runs the same Typer app as ``uv run hcs-discovery``.
"""

from __future__ import annotations

from hcs_discovery.cli.main import cli

if __name__ == "__main__":
    cli()
