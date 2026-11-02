# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for a one-file ``hcs-discovery`` executable.

Bundles the Typer CLI + FastAPI app, RDKit (compiled extensions and data), the
built single-page application and the Alembic migration scripts so the frozen
executable behaves like the installed wheel: ``doctor``, ``db upgrade``,
``serve`` and workflow execution all work without a Python installation.
"""

from __future__ import annotations

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

# SPECPATH is the directory containing this spec (scripts/release/).
ROOT = Path(SPECPATH).parents[1]  # noqa: F821 - provided by PyInstaller

datas = []
binaries = []
hiddenimports = []

# RDKit: collect every submodule plus data/binaries. There is no upstream
# hook for rdkit, so be explicit; a missing module here means a runtime ImportError.
for package in ("rdkit",):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h

# The compiled SPA is resolved at runtime relative to the package; ship it.
web_dist = ROOT / "apps" / "web" / "dist"
if web_dist.is_dir():
    datas += [(str(web_dist), "hcs_discovery/web")]

# Alembic migration scripts (same layout the wheel uses via force-include).
migrations = ROOT / "migrations"
if migrations.is_dir():
    datas += [(str(migrations), "hcs_discovery/_alembic")]

# Example datasets, so the shipped demo workflow is runnable from the exe.
examples = ROOT / "examples"
if examples.is_dir():
    datas += [(str(examples), "examples")]

a = Analysis(
    [str(ROOT / "scripts" / "release" / "cli_launcher.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest", "mypy", "ruff"],
    noarchive=False,
)

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="hcs-discovery",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)
