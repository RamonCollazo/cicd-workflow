"""Study Tracker Web package.

A Flask web frontend for the Study Tracker API. The WSGI app lives in
``web.main`` and is exposed as ``web.main:app`` for WSGI servers.

This package intentionally does **not** re-export anything from
``web.main``, so ``import web`` has no logging or network side effects.
For the application factory, import explicitly:

    from web.main import create_app
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
