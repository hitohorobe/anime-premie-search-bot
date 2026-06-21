from datetime import datetime, timezone
from pathlib import Path

from aggregator.models import Event, ExtractionMeta, ReservationWindow, Session
from aggregator.publishers.site import SitePublisher, _order_events
from aggregator.storage import EventRepository

NOW = datetime(2026, 6, 22, 12, 0, tzinfo=timezone.utc)
TEMPLATES_DIR = Path("templates/site")


def _event(*, event_id: str, starts_at: datetime | None, title: str = "Test Event") -> Event:
    return Event(
        id=event_id,
        title=title,
        source_url=f"https://www.animatetimes.com/news/details.php?id={event_id}",
        source_site="animatetimes",
        fetched_at=NOW,
        sessions=[Session(location_label="東京", starts_at=starts_at)] if starts_at is not None else [],
        reservation=ReservationWindow(),
        extraction=ExtractionMeta(model="claude-haiku-4-5", raw_text_hash=f"sha256:{event_id}"),
    )


def test_order_events_puts_upcoming_before_concluded():
    soon = _event(event_id="1", starts_at=datetime(2026, 7, 1, tzinfo=timezone.utc))
    later = _event(event_id="2", starts_at=datetime(2026, 8, 1, tzinfo=timezone.utc))
    past = _event(event_id="3", starts_at=datetime(2026, 1, 1, tzinfo=timezone.utc))

    ordered = _order_events([later, past, soon], now=NOW)

    assert [e.id for e in ordered] == ["1", "2", "3"]


def test_order_events_sorts_concluded_most_recent_first():
    older_past = _event(event_id="1", starts_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    newer_past = _event(event_id="2", starts_at=datetime(2026, 5, 1, tzinfo=timezone.utc))

    ordered = _order_events([older_past, newer_past], now=NOW)

    assert [e.id for e in ordered] == ["2", "1"]


def test_order_events_keeps_dateless_events_without_dropping_them():
    dateless = _event(event_id="1", starts_at=None)
    soon = _event(event_id="2", starts_at=datetime(2026, 7, 1, tzinfo=timezone.utc))

    ordered = _order_events([dateless, soon], now=NOW)

    assert {e.id for e in ordered} == {"1", "2"}
    assert ordered[0].id == "2"  # known upcoming date sorts before the dateless one


def test_publish_embeds_all_events_and_copies_site_js(tmp_path: Path):
    repo = EventRepository(tmp_path / "events.json")
    events = [
        repo.upsert(_event(event_id="1", starts_at=datetime(2026, 7, 1, tzinfo=timezone.utc), title="Event One")),
        repo.upsert(_event(event_id="2", starts_at=datetime(2026, 1, 1, tzinfo=timezone.utc), title="Event Two")),
    ]

    SitePublisher(templates_dir=TEMPLATES_DIR, output_dir=tmp_path).publish(events, repo)

    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "Event One" in html
    assert "Event Two" in html  # concluded events are kept, not pruned

    site_js = (tmp_path / "site.js").read_text(encoding="utf-8")
    assert site_js == (TEMPLATES_DIR / "site.js").read_text(encoding="utf-8")


def test_publish_marks_events_as_published(tmp_path: Path):
    repo = EventRepository(tmp_path / "events.json")
    event = repo.upsert(_event(event_id="1", starts_at=datetime(2026, 7, 1, tzinfo=timezone.utc)))

    SitePublisher(templates_dir=TEMPLATES_DIR, output_dir=tmp_path).publish([event], repo)

    assert repo.get(event.id).publish_status.site is True
