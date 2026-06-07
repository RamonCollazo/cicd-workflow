"""GET /stats: aggregation over the test's own tag slice.

Tests never assert on globals (`total_sessions`, `total_time`) because
the cluster's CSV may have leftover state from earlier runs. Using a
unique tag per test makes the per-tag aggregations deterministic.
"""

from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_stats_includes_created_session(http, api_url: str, unique_tag: str) -> None:
    create = http.post(
        f"{api_url}/sessions",
        json={"minutes": 30, "tag": unique_tag},
    )
    assert create.status_code == 200

    response = http.get(f"{api_url}/stats")
    assert response.status_code == 200
    stats = response.json()

    assert stats["time_by_tag"][unique_tag] == 30
    assert stats["sessions_by_tag"][unique_tag] == 1


@pytest.mark.e2e
def test_stats_aggregates_multiple_sessions(http, api_url: str, unique_tag: str) -> None:
    for minutes in (15, 25):
        create = http.post(
            f"{api_url}/sessions",
            json={"minutes": minutes, "tag": unique_tag},
        )
        assert create.status_code == 200

    response = http.get(f"{api_url}/stats")
    assert response.status_code == 200
    stats = response.json()

    assert stats["time_by_tag"][unique_tag] == 40
    assert stats["sessions_by_tag"][unique_tag] == 2
