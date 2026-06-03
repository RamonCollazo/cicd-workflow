"""Tests for ``api.storage``.

Storage isolation is provided by the autouse ``isolated_data_dir``
fixture in ``conftest.py``: each test gets its own ``tmp_path`` as
``DATA_DIR``, so writes go to a fresh CSV the test owns.

Tag normalization (``StudySessionCreate._normalize_tag``) lowercases
and strips, so tests assert against the lowercase form.
"""

from __future__ import annotations

import csv
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from api.models import StudySession, StudySessionCreate
from api.storage import (
    CSV_HEADERS,
    _sessions_file,
    get_all_sessions,
    get_sessions_by_tag,
    get_statistics,
    save_session,
)


# --------------------------------------------------------------------- #
# save_session
# --------------------------------------------------------------------- #


def test_save_session_returns_persisted_record():
    """save_session writes a row and returns the full StudySession."""
    saved = save_session(StudySessionCreate(minutes=45, tag="Terraform"))

    assert isinstance(saved, StudySession)
    assert saved.minutes == 45
    assert saved.tag == "terraform"  # normalized lowercase
    assert isinstance(saved.id, str)
    uuid.UUID(saved.id)  # round-trips as a valid UUID
    assert isinstance(saved.timestamp, datetime)
    assert saved.timestamp.tzinfo is not None  # tz-aware UTC

    # On-disk content matches the returned model
    path = _sessions_file()
    with open(path, "r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["id"] == saved.id
    assert int(rows[0]["minutes"]) == 45
    assert rows[0]["tag"] == "terraform"


def test_save_multiple_sessions_appends_in_order():
    save_session(StudySessionCreate(minutes=30, tag="Docker"))
    save_session(StudySessionCreate(minutes=60, tag="Python"))

    with open(_sessions_file(), "r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert [r["tag"] for r in rows] == ["docker", "python"]
    assert [int(r["minutes"]) for r in rows] == [30, 60]


def test_csv_headers_match_storage_constant():
    """Saving any row should write exactly the documented headers."""
    save_session(StudySessionCreate(minutes=10, tag="Linux"))
    with open(_sessions_file(), "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == CSV_HEADERS


# --------------------------------------------------------------------- #
# get_all_sessions
# --------------------------------------------------------------------- #


def test_get_all_sessions_returns_empty_when_file_missing():
    """Reading from a fresh data dir creates the CSV and returns []."""
    sessions = get_all_sessions()
    assert sessions == []
    # The reader/writer should have created the empty file with headers.
    assert _sessions_file().exists()


def test_get_all_sessions_round_trip():
    save_session(StudySessionCreate(minutes=20, tag="git"))
    save_session(StudySessionCreate(minutes=40, tag="ci-cd"))

    sessions = get_all_sessions()
    assert len(sessions) == 2
    assert all(isinstance(s, StudySession) for s in sessions)
    assert [s.tag for s in sessions] == ["git", "ci-cd"]
    assert [s.minutes for s in sessions] == [20, 40]


def test_get_all_sessions_skips_malformed_rows(isolated_data_dir: Path):
    """A row that fails to parse is logged + skipped, not raised."""
    save_session(StudySessionCreate(minutes=10, tag="ok"))

    # Append a malformed row directly to the CSV (bad minutes column).
    with open(_sessions_file(), "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writerow(
            {
                "id": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "minutes": "not-an-int",
                "tag": "broken",
            }
        )

    sessions = get_all_sessions()
    assert len(sessions) == 1
    assert sessions[0].tag == "ok"


# --------------------------------------------------------------------- #
# get_sessions_by_tag
# --------------------------------------------------------------------- #


def test_get_sessions_by_tag_filters_case_insensitive():
    save_session(StudySessionCreate(minutes=25, tag="aws"))
    save_session(StudySessionCreate(minutes=55, tag="azure"))
    save_session(StudySessionCreate(minutes=35, tag="AWS"))  # normalized -> 'aws'

    aws_sessions = get_sessions_by_tag("AWS")
    assert len(aws_sessions) == 2
    assert all(s.tag == "aws" for s in aws_sessions)

    azure_sessions = get_sessions_by_tag("azure")
    assert len(azure_sessions) == 1
    assert azure_sessions[0].tag == "azure"


def test_get_sessions_by_tag_no_match_returns_empty():
    save_session(StudySessionCreate(minutes=15, tag="rust"))
    assert get_sessions_by_tag("gcp") == []


# --------------------------------------------------------------------- #
# get_statistics
# --------------------------------------------------------------------- #


def test_get_statistics_aggregates_correctly():
    save_session(StudySessionCreate(minutes=10, tag="linux"))
    save_session(StudySessionCreate(minutes=20, tag="networking"))
    save_session(StudySessionCreate(minutes=30, tag="linux"))

    stats = get_statistics()

    assert stats.total_sessions == 3
    assert stats.total_time == 60
    assert stats.time_by_tag == {"linux": 40, "networking": 20}
    assert stats.sessions_by_tag == {"linux": 2, "networking": 1}


def test_get_statistics_empty():
    stats = get_statistics()
    assert stats.total_sessions == 0
    assert stats.total_time == 0
    assert stats.time_by_tag == {}
    assert stats.sessions_by_tag == {}


# --------------------------------------------------------------------- #
# Sanity: tests really are isolated
# --------------------------------------------------------------------- #


@pytest.mark.parametrize("run", [1, 2, 3])
def test_isolation_between_tests(run: int):
    """Each test starts with a clean data dir (no leakage across runs)."""
    assert get_all_sessions() == []
    save_session(StudySessionCreate(minutes=5, tag=f"run-{run}"))
    assert len(get_all_sessions()) == 1
