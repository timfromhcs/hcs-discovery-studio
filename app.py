"""Vercel entrypoint.

Vercel's Python runtime looks for a top-level ``app`` in ``app.py``, ``index.py``,
``main.py``, ``server.py``, ``wsgi.py`` or ``asgi.py``. The FastAPI application
itself lives in :mod:`hcs_discovery.api.app`; this module only exposes it.

Required environment for a hosted preview:

    HCS_DATA_DIR=/tmp/hcs        # only /tmp is writable on the function
    HCS_DEMO_MODE=true           # build a disposable synthetic workspace
    HCS_WEB_DIST=/var/task/apps/web/dist   # the SPA built by vercel.json

The default local configuration is unchanged: without ``HCS_DEMO_MODE`` this
serves whatever real data directory it is given, exactly like ``serve``.
"""

from __future__ import annotations

from hcs_discovery.api.app import create_app

app = create_app()
