"""Read/write data/events.json — the event database and dedup/publish-state store."""

from __future__ import annotations

from pathlib import Path

from ..models import Event, EventDatabase, ReservationWindow

DEFAULT_PATH = Path("data/events.json")


class EventRepository:
    def __init__(self, path: Path = DEFAULT_PATH) -> None:
        self._path = path
        self._db = self._load()

    def _load(self) -> EventDatabase:
        if not self._path.exists():
            return EventDatabase()
        return EventDatabase.model_validate_json(self._path.read_text(encoding="utf-8"))

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            self._db.model_dump_json(indent=2, exclude_none=False) + "\n", encoding="utf-8"
        )

    def known_ids(self) -> set[str]:
        return {event.id for event in self._db.events} | set(self._db.seen_article_ids)

    def mark_seen(self, article_id: str) -> None:
        """本文キーワード不一致で棄却した記事IDを記録する。

        毎回の実行で同じ記事を再取得しないようにする。
        save() の呼び出しは呼び出し元の責務。
        """
        if article_id not in self._db.seen_article_ids:
            self._db.seen_article_ids.append(article_id)

    def get(self, event_id: str) -> Event | None:
        return next((e for e in self._db.events if e.id == event_id), None)

    def all_events(self) -> list[Event]:
        return list(self._db.events)

    def upsert(self, new_event: Event) -> Event:
        """Insert a new event, or merge into an existing one with the same id.

        On merge: if the source text changed (different raw_text_hash),
        sessions/reservation/extraction are replaced with the freshly
        extracted values, but publish_status is preserved so already-posted
        channels are not re-posted.
        """
        existing = self.get(new_event.id)
        if existing is None:
            self._db.events.append(new_event)
            return new_event

        if existing.extraction.raw_text_hash == new_event.extraction.raw_text_hash:
            return existing

        existing.title = new_event.title
        existing.sessions = new_event.sessions
        existing.reservation = new_event.reservation
        existing.extraction = new_event.extraction
        return existing

    def update_reservation(self, event_id: str, reservation: ReservationWindow) -> None:
        """Overwrite an event's reservation info unconditionally.

        Unlike upsert(), this isn't gated on raw_text_hash: reservation
        availability changes on the ticket vendor's page independently of
        whether the source article's text ever changes.
        """
        event = self.get(event_id)
        if event is None:
            return
        event.reservation = reservation

    def mark_published(self, event_id: str, channel: str) -> None:
        event = self.get(event_id)
        if event is None:
            return
        setattr(event.publish_status, channel, True)

    def set_gcal_event_id(self, event_id: str, location_label: str, gcal_id: str) -> None:
        event = self.get(event_id)
        if event is None:
            return
        event.publish_status.gcal_event_ids[location_label] = gcal_id
