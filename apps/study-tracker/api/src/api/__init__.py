"""Study Tracker API package.

A FastAPI application for tracking study time. The ASGI app lives in
``api.main`` and is exposed as ``api.main:app`` for ASGI servers.
"""

from .models import Stats, StudySession, StudySessionCreate
from .storage import (
    get_all_sessions,
    get_sessions_by_tag,
    get_statistics,
    save_session,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "StudySession",
    "StudySessionCreate",
    "Stats",
    "save_session",
    "get_all_sessions",
    "get_sessions_by_tag",
    "get_statistics",
]
