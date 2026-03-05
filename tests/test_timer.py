"""Tests for timecard.timer."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from timecard.db import get_active_session, get_connection, get_entry
from timecard.timer import get_timer_status, start_timer, stop_timer


@pytest.fixture
def conn(tmp_path):
    return get_connection(tmp_path / "test.db")


class TestStartTimer:
    def test_start_creates_session(self, conn):
        started_at = start_timer(conn)
        assert started_at is not None
        session = get_active_session(conn)
        assert session is not None
        assert session.started_at == started_at

    def test_start_twice_raises(self, conn):
        start_timer(conn)
        with pytest.raises(ValueError, match="already running"):
            start_timer(conn)


class TestStopTimer:
    def test_stop_creates_entry(self, conn):
        start_timer(conn)
        entry = stop_timer(conn)
        assert entry.id is not None
        assert entry.started_at is not None
        assert entry.ended_at is not None
        assert entry.duration_minutes >= 0

        # Verify session is cleared
        assert get_active_session(conn) is None

        # Verify entry is in DB
        db_entry = get_entry(conn, entry.id)
        assert db_entry is not None
        assert db_entry.duration_minutes == entry.duration_minutes

    def test_stop_without_start_raises(self, conn):
        with pytest.raises(ValueError, match="No timer session"):
            stop_timer(conn)

    def test_stop_calculates_duration(self, conn):
        ten_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        conn.execute(
            "INSERT INTO active_session (id, started_at) VALUES (:id, :started_at)",
            {"id": 1, "started_at": ten_min_ago},
        )
        conn.commit()

        entry = stop_timer(conn)
        # Should be approximately 10 minutes (allow some tolerance)
        assert 9.5 < entry.duration_minutes < 10.5


class TestGetTimerStatus:
    def test_no_timer_running(self, conn):
        status = get_timer_status(conn)
        assert status["running"] is False

    def test_timer_running(self, conn):
        start_timer(conn)
        status = get_timer_status(conn)
        assert status["running"] is True
        assert "started_at" in status
        assert "elapsed_minutes" in status
        assert status["elapsed_minutes"] >= 0
