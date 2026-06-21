from datetime import datetime, timezone
from pathlib import Path

from aggregator.models import Event, ExtractionMeta, ReservationWindow, Session
from aggregator.publishers.rss import RssPublisher
from aggregator.storage import EventRepository


def _event() -> Event:
    return Event(
        id="animatetimes-1111111111",
        title="テストアニメ 第13話先行上映会",
        source_url="https://www.animatetimes.com/news/details.php?id=1111111111",
        source_site="animatetimes",
        fetched_at=datetime(2026, 6, 16, tzinfo=timezone.utc),
        sessions=[
            Session(
                location_label="東京",
                venue_name="テストホール",
                starts_at=datetime(2026, 7, 19, 18, 30, tzinfo=timezone.utc),
            )
        ],
        reservation=ReservationWindow(ticket_url="https://example-ticket.test/test-anime/"),
        extraction=ExtractionMeta(model="claude-haiku-4-5", raw_text_hash="sha256:a"),
    )


def test_rss_publish_writes_feed_with_event_fields(tmp_path: Path):
    repo = EventRepository(tmp_path / "events.json")
    event = repo.upsert(_event())
    output_path = tmp_path / "feed.xml"

    RssPublisher(output_path=output_path).publish([event], repo)

    assert output_path.exists()
    xml = output_path.read_text(encoding="utf-8")
    assert "テストアニメ" in xml
    assert "https://www.animatetimes.com/news/details.php?id=1111111111" in xml
    assert "example-ticket.test" in xml


def test_rss_publish_marks_events_as_published(tmp_path: Path):
    repo = EventRepository(tmp_path / "events.json")
    event = repo.upsert(_event())
    output_path = tmp_path / "feed.xml"

    RssPublisher(output_path=output_path).publish([event], repo)

    assert repo.get(event.id).publish_status.rss is True
