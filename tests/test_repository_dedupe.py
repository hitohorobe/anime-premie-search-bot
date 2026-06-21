from datetime import datetime, timezone
from pathlib import Path

from aggregator.models import Event, ExtractionMeta, ReservationWindow
from aggregator.storage import EventRepository


def _event(*, hash_suffix: str = "a", title: str = "Test Event") -> Event:
    return Event(
        id="animatetimes-1111111111",
        title=title,
        source_url="https://www.animatetimes.com/news/details.php?id=1111111111",
        source_site="animatetimes",
        fetched_at=datetime.now(timezone.utc),
        sessions=[],
        extraction=ExtractionMeta(model="claude-haiku-4-5", raw_text_hash=f"sha256:{hash_suffix}"),
    )


def test_upsert_inserts_new_event(tmp_path: Path):
    repo = EventRepository(tmp_path / "events.json")

    repo.upsert(_event())

    assert len(repo.all_events()) == 1
    assert "animatetimes-1111111111" in repo.known_ids()


def test_upsert_is_idempotent_for_unchanged_text(tmp_path: Path):
    repo = EventRepository(tmp_path / "events.json")
    repo.upsert(_event(hash_suffix="a", title="Original Title"))

    repo.upsert(_event(hash_suffix="a", title="Should Not Apply"))

    assert len(repo.all_events()) == 1
    assert repo.all_events()[0].title == "Original Title"


def test_upsert_updates_fields_when_text_hash_changes(tmp_path: Path):
    repo = EventRepository(tmp_path / "events.json")
    repo.upsert(_event(hash_suffix="a", title="Original Title"))

    repo.upsert(_event(hash_suffix="b", title="Updated Title"))

    assert len(repo.all_events()) == 1
    assert repo.all_events()[0].title == "Updated Title"


def test_mark_published_preserved_across_text_update(tmp_path: Path):
    repo = EventRepository(tmp_path / "events.json")
    repo.upsert(_event(hash_suffix="a"))
    repo.mark_published("animatetimes-1111111111", "rss")

    repo.upsert(_event(hash_suffix="b", title="Updated Title"))

    assert repo.get("animatetimes-1111111111").publish_status.rss is True


def test_update_reservation_overwrites_regardless_of_hash(tmp_path: Path):
    repo = EventRepository(tmp_path / "events.json")
    repo.upsert(_event(hash_suffix="a"))

    repo.update_reservation(
        "animatetimes-1111111111",
        ReservationWindow(availability_status="available", ticket_url="https://example-ticket.test/x"),
    )

    updated = repo.get("animatetimes-1111111111")
    assert updated.reservation.availability_status == "available"
    assert updated.reservation.ticket_url == "https://example-ticket.test/x"


def test_update_reservation_preserves_publish_status(tmp_path: Path):
    repo = EventRepository(tmp_path / "events.json")
    repo.upsert(_event())
    repo.mark_published("animatetimes-1111111111", "rss")

    repo.update_reservation("animatetimes-1111111111", ReservationWindow(availability_status="sold_out"))

    event = repo.get("animatetimes-1111111111")
    assert event.publish_status.rss is True
    assert event.reservation.availability_status == "sold_out"


def test_update_reservation_is_noop_for_unknown_event(tmp_path: Path):
    repo = EventRepository(tmp_path / "events.json")

    repo.update_reservation("does-not-exist", ReservationWindow(availability_status="available"))

    assert repo.all_events() == []


def test_save_and_reload_roundtrip(tmp_path: Path):
    path = tmp_path / "events.json"
    repo = EventRepository(path)
    repo.upsert(_event())
    repo.save()

    reloaded = EventRepository(path)

    assert reloaded.known_ids() == {"animatetimes-1111111111"}
