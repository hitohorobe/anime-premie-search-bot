"""Regenerate public/feed.xml from the full event list."""

from __future__ import annotations

from pathlib import Path

from feedgen.feed import FeedGenerator

from ..models import Event
from ..storage import EventRepository
from .base import Publisher

SITE_URL = "https://example.github.io/anime-premiere-search-bot"  # update to the real Pages URL
OUTPUT_PATH = Path("public/feed.xml")


def _describe(event: Event) -> str:
    lines = []
    for session in event.sessions:
        when = session.starts_at.isoformat() if session.starts_at else "日時未定"
        where = session.venue_name or "会場未定"
        lines.append(f"{session.location_label}: {when} @ {where}")
    if event.reservation.ticket_url:
        lines.append(f"予約: {event.reservation.ticket_url}")
    return "\n".join(lines) if lines else event.title


class RssPublisher(Publisher):
    channel_name = "rss"

    def __init__(self, output_path: Path = OUTPUT_PATH) -> None:
        self._output_path = output_path

    def publish(self, events: list[Event], repository: EventRepository) -> None:
        fg = FeedGenerator()
        fg.title("アニメ先行上映・先行配信情報")
        fg.link(href=SITE_URL, rel="alternate")
        fg.description("アニメの先行上映会・先行配信イベント情報まとめ")
        fg.language("ja")

        for event in sorted(events, key=lambda e: e.fetched_at, reverse=True):
            entry = fg.add_entry()
            entry.id(event.source_url)
            entry.title(event.title)
            entry.link(href=event.source_url)
            entry.description(_describe(event))
            entry.pubDate(event.fetched_at)

        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        fg.rss_file(str(self._output_path))

        for event in events:
            if not event.publish_status.rss:
                repository.mark_published(event.id, "rss")
