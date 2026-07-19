"""Data model for collected screening/streaming events."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class Session(BaseModel):
    """A single date/venue occurrence of an event (e.g. Tokyo vs Osaka)."""

    location_label: str
    venue_name: str | None = None
    venue_address: str | None = None
    starts_at: datetime | None = None
    doors_open_at: datetime | None = None
    ends_at: datetime | None = None

    def has_ended(self, now: datetime) -> bool:
        """Whether this session is over as of ``now``.

        Falls back to ``starts_at`` when ``ends_at`` is unknown. A session
        with neither is treated as not-yet-ended (we don't have enough
        information to drop it).
        """
        reference = self.ends_at or self.starts_at
        if reference is None:
            return False
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=timezone.utc)
        return reference < now


class ReservationWindow(BaseModel):
    presale_opens_at: datetime | None = None
    presale_closes_at: datetime | None = None
    general_opens_at: datetime | None = None
    general_closes_at: datetime | None = None
    ticket_url: str | None = None
    # Populated by re-crawling ticket_url; "available" / "not_yet_open" /
    # "closed" / "sold_out", or None if never successfully checked.
    availability_status: str | None = None
    checked_at: datetime | None = None


class ExtractionMeta(BaseModel):
    model: str
    confidence_notes: str = ""
    raw_text_hash: str


class PublishStatus(BaseModel):
    rss: bool = False
    site: bool = False
    twitter: bool = False
    bluesky: bool = False
    gcal_event_ids: dict[str, str] = Field(default_factory=dict)


class Event(BaseModel):
    id: str
    title: str
    source_url: str
    source_site: str
    fetched_at: datetime
    sessions: list[Session] = Field(default_factory=list)
    reservation: ReservationWindow = Field(default_factory=ReservationWindow)
    extraction: ExtractionMeta
    publish_status: PublishStatus = Field(default_factory=PublishStatus)
    # True when the source article is a post-event report rather than a
    # pre-event announcement. Report articles often lack session dates
    # entirely, so session-based is_concluded() can't detect them on its own.
    is_report: bool = False

    def is_concluded(self, now: datetime | None = None) -> bool:
        """Whether this event is already over and no longer upcoming.

        Report articles are always treated as concluded, regardless of
        session info. Otherwise, used to drop coverage of events that have
        already happened by the time they're scraped — we only care about
        upcoming screenings. Events with no extracted sessions are kept
        (we don't have enough information to say they're over).
        """
        if self.is_report:
            return True
        now = now or datetime.now(timezone.utc)
        if not self.sessions:
            return False
        return all(session.has_ended(now) for session in self.sessions)


class EventDatabase(BaseModel):
    events: list[Event] = Field(default_factory=list)
    # 本文キーワード不一致で棄却した記事のID（例: "animatetimes-3333333333"）。
    # known_ids() に含めることで list_articles() のスキップと早期停止が正常に機能する。
    seen_article_ids: list[str] = Field(default_factory=list)
    schema_version: int = 1
