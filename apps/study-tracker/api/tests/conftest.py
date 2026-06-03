"""Pytest fixtures shared across the api test suite.

The ``isolated_data_dir`` fixture runs for every test (``autouse=True``),
points ``DATA_DIR`` at a fresh ``tmp_path``, and clears the ``get_settings``
``lru_cache`` so storage code reads the per-test path. Production data
(``apps/study-tracker/api/data/sessions.csv``) is never touched by the
test suite.
"""

from __future__ import annotations

import pytest

from api.config import get_settings


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Redirect storage to a per-test directory.

    ``Settings`` reads env vars on instantiation, and ``get_settings`` is
    ``lru_cache``'d, so we set ``DATA_DIR`` and clear the cache both
    before yielding (so the test sees the override) and after (so the
    next test starts clean).
    """
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        yield tmp_path
    finally:
        get_settings.cache_clear()
