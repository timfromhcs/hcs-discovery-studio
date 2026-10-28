"""Remove RDKit's bundled type stubs before running mypy.

RDKit 2026.9.1 ships ``rdkit-stubs`` generated from Boost bindings, and at least
one file contains invalid Python syntax
(``rdkit.rdBase._vectunsigned int``). Mypy parses the package before applying
the project's ``ignore_missing_imports`` override for ``rdkit``, so the syntax
error aborts the whole check. This project treats RDKit as an untyped
dependency; removing the incompatible stub package restores the intended
behaviour without weakening checks for FastAPI, Pydantic or SQLAlchemy.

Run this once in a fresh environment before ``uv run mypy``. It is idempotent
and only touches the current virtual environment's ``rdkit-stubs`` directory.
"""

from __future__ import annotations

import shutil
import sysconfig
from pathlib import Path


def main() -> int:
    site_packages = Path(sysconfig.get_paths()["purelib"])
    target = site_packages / "rdkit-stubs"
    if target.is_dir():
        shutil.rmtree(target)
        print(f"Removed incompatible RDKit stubs: {target}")
    else:
        print("No RDKit stub package installed; nothing to remove.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
