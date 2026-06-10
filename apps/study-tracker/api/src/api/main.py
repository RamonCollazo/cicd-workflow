"""Study Tracker API — FastAPI application module.

The ASGI app is exposed as ``api.main:app``.
"""

# Module entrypoint: defines the FastAPI ASGI app for the Study Tracker API.
import logging
from typing import List, Optional

import uvicorn
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import __version__
from .config import get_settings
from .models import Stats, StudySession, StudySessionCreate
from .storage import (
    get_all_sessions,
    get_sessions_by_tag,
    get_statistics,
    save_session,
)

logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description="API for tracking study time",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log unhandled exceptions and return a generic 500 response.

    Internal error details are kept out of the response body.
    """
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/")
async def root() -> dict:
    """Root endpoint returning API information."""
    return {"message": f"{settings.app_name} API", "version": __version__}


@app.get("/health")
async def health() -> dict:
    """Health endpoint for kubernetes probes."""
    return {"status": "healthy"}


@app.post("/sessions", response_model=StudySession)
async def create_session(session: StudySessionCreate) -> StudySession:
    """Create a new study session."""
    logger.info(
        "Creating new session: %d minutes with tag %r",
        session.minutes,
        session.tag,
    )
    return save_session(session)


@app.get("/sessions", response_model=List[StudySession])
async def read_sessions(
    tag: Optional[str] = Query(None, description="Filter sessions by tag"),
) -> List[StudySession]:
    """Get all study sessions, optionally filtered by tag."""
    if tag:
        logger.info("Fetching sessions with tag %r", tag)
        return get_sessions_by_tag(tag)
    logger.info("Fetching all sessions")
    return get_all_sessions()


@app.get("/stats", response_model=Stats)
async def read_stats() -> Stats:
    """Get aggregated statistics about study sessions."""
    logger.info("Fetching statistics")
    return get_statistics()


# Marker for CI pipeline
# This comment is used to trigger the CI pipeline when changes are made to this file.
# This comment is used to trigger the CI pipeline when changes are made to this file.
# This comment is used to trigger the CI pipeline when changes are made to this file.
# This comment is used to trigger the CI pipeline when changes are made to this file.


def setup_logging(level: str = "INFO") -> None:
    """Configure root logging. Called from ``main()`` only."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def main() -> None:
    """Entry point for running the API server."""
    setup_logging()
    logger.info("Starting %s API v%s", settings.app_name, __version__)
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.reload,
    )


if __name__ == "__main__":
    main()
