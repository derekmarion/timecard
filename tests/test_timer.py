"""Tests for timecard.timer."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from timecard.db import get_active_session, get_connection, get_entry
from timecard.timer import (
    get_timer_status,
    pause_timer,
    resume_timer,
    start_timer,
    stop_timer,
)


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

    def test_stop_while_paused_accounts_for_pause(self, conn):
        """Stopping a paused timer should exclude paused time from duration."""
        twenty_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
        five_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        conn.execute(
            "INSERT INTO active_session (id, started_at, paused_at, paused_duration_minutes) "
            "VALUES (1, :started, :paused, :dur)",
            {"started": twenty_min_ago, "paused": five_min_ago, "dur": 5.0},
        )
        conn.commit()

        entry = stop_timer(conn)
        # 20 min total - 5 min previous pause - 5 min current pause = ~10 min
        assert 9.0 < entry.duration_minutes < 11.0


class TestPauseTimer:
    def test_pause_running_timer(self, conn):
        start_timer(conn)
        paused_at = pause_timer(conn)
        assert paused_at is not None

        session = get_active_session(conn)
        assert session.is_paused
        assert session.paused_at == paused_at

    def test_pause_without_session_raises(self, conn):
        with pytest.raises(ValueError, match="No timer session"):
            pause_timer(conn)

    def test_pause_already_paused_raises(self, conn):
        start_timer(conn)
        pause_timer(conn)
        with pytest.raises(ValueError, match="already paused"):
            pause_timer(conn)


class TestResumeTimer:
    def test_resume_paused_timer(self, conn):
        start_timer(conn)
        pause_timer(conn)
        resumed_at = resume_timer(conn)
        assert resumed_at is not None

        session = get_active_session(conn)
        assert not session.is_paused
        assert session.paused_duration_minutes > 0

    def test_resume_without_session_raises(self, conn):
        with pytest.raises(ValueError, match="No timer session"):
            resume_timer(conn)

    def test_resume_not_paused_raises(self, conn):
        start_timer(conn)
        with pytest.raises(ValueError, match="not paused"):
            resume_timer(conn)

    def test_resume_accumulates_paused_time(self, conn):
        """Multiple pause/resume cycles should accumulate paused_duration_minutes."""
        ten_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        five_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()

        # Simulate: started 10 min ago, paused 5 min ago, already accumulated 2 min
        conn.execute(
            "INSERT INTO active_session (id, started_at, paused_at, paused_duration_minutes) "
            "VALUES (1, :started, :paused, :dur)",
            {"started": ten_min_ago, "paused": five_min_ago, "dur": 2.0},
        )
        conn.commit()

        resume_timer(conn)
        session = get_active_session(conn)
        # Should have ~2 + ~5 = ~7 minutes of paused time
        assert 6.5 < session.paused_duration_minutes < 7.5


class TestGetTimerStatus:
    def test_no_timer_running(self, conn):
        status = get_timer_status(conn)
        assert status["running"] is False

    def test_timer_running(self, conn):
        start_timer(conn)
        status = get_timer_status(conn)
        assert status["running"] is True
        assert status["paused"] is False
        assert "started_at" in status
        assert "elapsed_minutes" in status
        assert status["elapsed_minutes"] >= 0

    def test_timer_paused(self, conn):
        start_timer(conn)
        pause_timer(conn)
        status = get_timer_status(conn)
        assert status["running"] is True
        assert status["paused"] is True
