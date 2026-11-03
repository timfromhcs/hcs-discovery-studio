"""Vercel entrypoint.

Vercel's Python runtime looks for a top-level ``app`` in ``app.py``, ``index.py``,
``main.py``, ``server.py``, ``wsgi.py`` or ``asgi.py``. The FastAPI application
itself lives in :mod:`hcs_discovery.api.app`; this module only exposes it.

Required environment for a hosted preview:

    HCS_DATA_DIR=/tmp/hcs        # only /tmp is writable on the function
    HCS_DEMO_MODE=true           # build a disposable synthetic workspace
    HCS_RUN_MODE=inline          # no worker process can outlive the response
    HCS_WEB_DIST=/var/task/apps/web/dist   # the SPA built by vercel.json

The default local configuration is unchanged: without ``HCS_DEMO_MODE`` this
serves whatever real data directory it is given, exactly like ``serve``.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Vercel installs the dependencies declared in pyproject.toml but does not install
# the project itself, and this repository uses a ``src/`` layout. Put it on the
# import path here so the entrypoint is self-contained; an installed wheel already
# resolves the package and this block is then a no-op.
_SRC = Path(__file__).resolve().parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from hcs_discovery.api.app import create_app  # noqa: E402  (path set up above)

app = create_app()
