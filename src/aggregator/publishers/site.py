"""Regenerate the public/ static site from the full event list.

All collected events are kept (nothing is pruned from data/events.json), so
the page embeds the full list as JSON and lets a small client-side script
(site.js) handle pagination and date-range filtering — see templates/site/.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..models import Event, Session
from ..storage import EventRepository
from .base import Publisher

TEMPLATES_DIR = Path("templates/site")
OUTPUT_DIR = Path("public")

_FAR_FUTURE = datetime.max.replace(tzinfo=timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _session_reference(session: Session) -> datetime | None:
    return session.starts_at or session.ends_at


def _earliest_reference(event: Event) -> datetime | None:
    refs = [_aware(r) for r in (_session_reference(s) for s in event.sessions) if r is not None]
    return min(refs) if refs else None


def _latest_reference(event: Event) -> datetime | None:
    refs = [_aware(r) for r in (_session_reference(s) for s in event.sessions) if r is not None]
    return max(refs) if refs else None


def _order_events(events: list[Event], now: datetime | None = None) -> list[Event]:
    """Upcoming events soonest-first, then concluded events most-recent-first.

    Nothing is dropped — this only controls display order, since the site
    is meant to keep every event ever collected (see SitePublisher docstring).
    """
    now = now or datetime.now(timezone.utc)
    upcoming = [e for e in events if not e.is_concluded(now)]
    concluded = [e for e in events if e.is_concluded(now)]

    upcoming.sort(key=lambda e: _earliest_reference(e) or _FAR_FUTURE)
    concluded.sort(key=lambda e: _latest_reference(e) or _aware(e.fetched_at), reverse=True)

    return upcoming + concluded


class SitePublisher(Publisher):
    channel_name = "site"

    def __init__(self, templates_dir: Path = TEMPLATES_DIR, output_dir: Path = OUTPUT_DIR) -> None:
        self._templates_dir = templates_dir
        self._env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(["html"]),
        )
        self._output_dir = output_dir

    def publish(self, events: list[Event], repository: EventRepository) -> None:
        ordered = _order_events(events)
        events_json = [event.model_dump(mode="json") for event in ordered]
        html = self._env.get_template("index.html").render(events_json=events_json)

        self._output_dir.mkdir(parents=True, exist_ok=True)
        (self._output_dir / "index.html").write_text(html, encoding="utf-8")
        (self._output_dir / ".nojekyll").touch()
        shutil.copyfile(self._templates_dir / "site.js", self._output_dir / "site.js")

        for event in events:
            if not event.publish_status.site:
                repository.mark_published(event.id, "site")
