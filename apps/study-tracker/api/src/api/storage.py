"""CSV-backed storage for study sessions.

Concurrency safety is single-process only (uses a module-level
`threading.Lock`). Multi-worker deployments will need file locking
(e.g., `fcntl.flock`) or a real database.
"""

import csv
import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from .config import get_settings
from .models import Stats, StudySession, StudySessionCreate

logger = logging.getLogger(__name__)

# CSV headers (order matters — written/read in this order)
CSV_HEADERS = ["id", "timestamp", "minutes", "tag"]

# Serializes append-writes within a single process.
_write_lock = threading.Lock()


def _sessions_file() -> Path:
    """Return the path to the sessions CSV, sourced from current settings."""
    return get_settings().data_dir / "sessions.csv"


def _create_csv_if_not_exists(path: Path) -> None:
    """Create the data dir and CSV file with headers if either is missing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        logger.info("Creating new sessions CSV file at %s", path)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            writer.writeheader()


def _parse_row(row: Dict[str, str]) -> StudySession:
    """Parse a CSV row into a StudySession. Raises on malformed data."""
    return StudySession(
        id=row["id"],
        timestamp=datetime.fromisoformat(row["timestamp"]),
        minutes=int(row["minutes"]),
        tag=row["tag"],
    )


def save_session(session: StudySessionCreate) -> StudySession:
    """Save a new study session to the CSV file."""
    path = _sessions_file()

    new_session = StudySession(
        id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc),
        minutes=session.minutes,
        tag=session.tag,
    )

    with _write_lock:
        _create_csv_if_not_exists(path)
        with open(path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            writer.writerow(
                {
                    "id": new_session.id,
                    "timestamp": new_session.timestamp.isoformat(),
                    "minutes": new_session.minutes,
                    "tag": new_session.tag,
                }
            )

    logger.info("Saved new session with ID %s", new_session.id)
    return new_session


def get_all_sessions() -> List[StudySession]:
    """Retrieve all study sessions from the CSV file.

    Malformed rows are logged at WARNING level and skipped.
    """
    path = _sessions_file()
    _create_csv_if_not_exists(path)

    sessions: List[StudySession] = []
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for line_no, row in enumerate(reader, start=2):  # header is line 1
            try:
                sessions.append(_parse_row(row))
            except Exception as e:
                logger.warning(
                    "Skipping malformed row at line %d: %s", line_no, e
                )
                continue

    logger.info("Retrieved %d sessions", len(sessions))
    return sessions


def get_sessions_by_tag(tag: str) -> List[StudySession]:
    """Retrieve study sessions filtered by tag (case-insensitive)."""
    needle = tag.strip().lower()
    all_sessions = get_all_sessions()
    filtered_sessions = [s for s in all_sessions if s.tag == needle]
    logger.info(
        "Retrieved %d sessions with tag %r", len(filtered_sessions), needle
    )
    return filtered_sessions


def get_statistics() -> Stats:
    """Calculate aggregated statistics from all sessions."""
    sessions = get_all_sessions()

    total_minutes = sum(s.minutes for s in sessions)

    time_by_tag: Dict[str, int] = {}
    sessions_by_tag: Dict[str, int] = {}
    for s in sessions:
        time_by_tag[s.tag] = time_by_tag.get(s.tag, 0) + s.minutes
        sessions_by_tag[s.tag] = sessions_by_tag.get(s.tag, 0) + 1

    stats = Stats(
        total_time=total_minutes,
        time_by_tag=time_by_tag,
        total_sessions=len(sessions),
        sessions_by_tag=sessions_by_tag,
    )

    logger.info(
        "Calculated statistics: %d minutes across %d sessions",
        total_minutes,
        len(sessions),
    )
    return stats
