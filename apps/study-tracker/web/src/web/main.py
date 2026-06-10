"""Study Tracker Web — Flask application module.

The WSGI app is exposed as ``web.main:app`` for WSGI servers.
``create_app()`` is the factory that owns app construction so importing
this module remains free of network and logging side effects.
"""

# Module entrypoint: defines the Flask WSGI app for the Study Tracker web UI.
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict

from flask import (
    Flask,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from .api_client import ApiClient, ApiError
from .config import DEV_INSECURE_SECRET_KEY, Settings, get_settings

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------- #


def format_session(session: Dict[str, Any]) -> Dict[str, Any]:
    """Format a session's timestamp for display."""
    timestamp = datetime.fromisoformat(session["timestamp"].replace("Z", "+00:00"))
    session["formatted_date"] = timestamp.strftime("%Y-%m-%d %H:%M")
    session["timestamp_obj"] = timestamp
    return session


def _get_client() -> ApiClient:
    """Return the per-app ApiClient instance."""
    return current_app.extensions["api_client"]


# --------------------------------------------------------------------- #
# Route handlers (registered by create_app)
# --------------------------------------------------------------------- #


def index():
    """Homepage displaying study session form and list."""
    try:
        raw = _get_client().get_sessions()
    except ApiError as e:
        logger.exception("Error fetching sessions: %s", e)
        flash("API is unavailable — showing no sessions.", "error")
        raw = []

    sessions = [format_session(s) for s in raw]
    sessions.sort(key=lambda x: x["timestamp_obj"], reverse=True)
    return render_template("index.html", sessions=sessions)


def add_session():
    """Add a new study session."""
    try:
        minutes = int(request.form.get("minutes", 0))
    except ValueError:
        logger.error("Invalid input for minutes")
        flash("Invalid minutes value.", "warning")
        return redirect(url_for("index"))

    tag = request.form.get("tag", "").strip()

    if minutes <= 0:
        logger.warning("Attempted to add session with minutes <= 0")
        flash("Minutes must be greater than zero.", "warning")
        return redirect(url_for("index"))

    if not tag:
        logger.warning("Attempted to add session with empty tag")
        flash("Tag is required.", "warning")
        return redirect(url_for("index"))

    try:
        _get_client().create_session(minutes, tag)
        logger.info("Successfully added session: %d mins, tag=%r", minutes, tag)
        flash("Session saved.", "info")
    except ApiError as e:
        logger.exception("Failed to add session %d mins, tag=%r: %s", minutes, tag, e)
        flash("Could not save session — API unavailable.", "error")

    return redirect(url_for("index"))


def health():
    """Health check endpoint for monitoring."""
    api_status = _get_client().health()
    status = "healthy" if api_status else "unhealthy"
    status_code = 200 if api_status else 503
    return jsonify({"status": status, "api_connectivity": api_status}), status_code


def handle_unhandled(e: Exception):
    """Log unhandled exceptions and render a generic error page.

    Internal error details are not exposed to the client. This handler
    is bypassed when ``FLASK_DEBUG=true`` so the Werkzeug debugger can
    take over in development.
    """
    logger.exception("Unhandled error on %s %s", request.method, request.path)
    return render_template("error.html"), 500


# Marker for CI pipeline
# This comment is used to trigger the CI pipeline when changes are made to this file.


# --------------------------------------------------------------------- #
# App factory
# --------------------------------------------------------------------- #


def create_app(settings: Settings | None = None) -> Flask:
    """Build and configure a Flask application instance."""
    settings = settings or get_settings()

    app = Flask(__name__)

    # Flask config sourced from validated settings.
    app.config["SETTINGS"] = settings
    app.config["API_URL"] = settings.api_url
    app.config["API_TIMEOUT"] = settings.api_timeout
    app.config["PORT"] = settings.frontend_port
    app.config["DEBUG"] = settings.debug
    app.config["HOST"] = settings.frontend_host

    # Session signing key for `flash` and any future session use.
    app.secret_key = settings.secret_key
    if settings.secret_key == DEV_INSECURE_SECRET_KEY:
        logger.warning(
            "SECRET_KEY is unset; using insecure dev default. "
            "Set SECRET_KEY env var for production."
        )

    # Per-app HTTP client. Stored on app.extensions so routes can pull
    # it via current_app without reaching for module-level globals.
    app.extensions["api_client"] = ApiClient(
        base_url=settings.api_url,
        timeout=settings.api_timeout,
        retries=settings.api_retries,
        backoff=settings.api_retry_backoff,
    )

    # Routes
    app.add_url_rule("/", "index", index, methods=["GET"])
    app.add_url_rule("/add_session", "add_session", add_session, methods=["POST"])
    app.add_url_rule("/health", "health", health, methods=["GET"])

    # Global error handler. Bypassed when DEBUG=True so the Werkzeug
    # debugger remains usable during local development.
    app.register_error_handler(Exception, handle_unhandled)

    return app


# --------------------------------------------------------------------- #
# Entrypoints
# --------------------------------------------------------------------- #


def setup_logging(level: str = "INFO") -> None:
    """Configure root logging. Called from ``main()`` only."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def main() -> None:
    """Entry point for running the Flask dev server."""
    setup_logging()
    logger.info("Starting Study Tracker Web")
    settings = get_settings()
    app.run(
        host=settings.frontend_host,
        port=settings.frontend_port,
        debug=settings.debug,
    )


# Module-level WSGI app for ``flask --app web.main`` and gunicorn.
app = create_app()


if __name__ == "__main__":
    main()
