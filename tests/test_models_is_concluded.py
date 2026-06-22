from datetime import datetime, timedelta, timezone

from aggregator.models import Event, ExtractionMeta, Session

NOW = datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc)


def _event(sessions: list[Session], *, is_report: bool = False) -> Event:
    return Event(
        id="animatetimes-1",
        title="Test",
        source_url="https://example.test/1",
        source_site="animatetimes",
        fetched_at=NOW,
        sessions=sessions,
        is_report=is_report,
        extraction=ExtractionMeta(model="claude-haiku-4-5", raw_text_hash="sha256:a"),
    )


def test_event_with_no_sessions_is_not_concluded():
    assert _event([]).is_concluded(NOW) is False


def test_event_with_future_session_is_not_concluded():
    session = Session(location_label="東京", starts_at=NOW + timedelta(days=1))
    assert _event([session]).is_concluded(NOW) is False


def test_event_with_only_past_sessions_is_concluded():
    session = Session(location_label="東京", starts_at=NOW - timedelta(days=2), ends_at=NOW - timedelta(days=2, hours=-2))
    assert _event([session]).is_concluded(NOW) is True


def test_event_is_not_concluded_if_any_session_is_still_upcoming():
    past = Session(location_label="東京", starts_at=NOW - timedelta(days=2))
    future = Session(location_label="大阪", starts_at=NOW + timedelta(days=2))
    assert _event([past, future]).is_concluded(NOW) is False


def test_report_event_is_concluded_even_without_sessions():
    assert _event([], is_report=True).is_concluded(NOW) is True


def test_report_event_is_concluded_even_with_future_session():
    session = Session(location_label="東京", starts_at=NOW + timedelta(days=1))
    assert _event([session], is_report=True).is_concluded(NOW) is True


def test_session_uses_starts_at_when_ends_at_missing():
    past_no_end = Session(location_label="東京", starts_at=NOW - timedelta(hours=1))
    assert past_no_end.has_ended(NOW) is True
