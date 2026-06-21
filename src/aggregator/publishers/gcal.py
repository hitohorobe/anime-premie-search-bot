"""Insert/update events on the dedicated public Google Calendar.

Setup (one-time, outside this pipeline — see README): create a Google Cloud
service account, create a new Google Calendar, share that calendar with the
service account email (Editor), make the calendar public, and store the
service account JSON + calendar ID as GitHub Actions secrets.
"""

from __future__ import annotations

import json
import logging

from google.oauth2 import service_account
from googleapiclient.discovery import build

from ..models import Event, Session
from ..storage import EventRepository
from .base import Publisher

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _session_to_gcal_body(event: Event, session: Session) -> dict | None:
    if session.starts_at is None:
        return None
    end = session.ends_at or session.starts_at
    description_lines = [f"出典: {event.source_url}"]
    if event.reservation.ticket_url:
        description_lines.append(f"予約サイト: {event.reservation.ticket_url}")
    if event.reservation.presale_opens_at:
        description_lines.append(f"予約開始: {event.reservation.presale_opens_at.isoformat()}")
    if event.reservation.presale_closes_at:
        description_lines.append(f"予約終了: {event.reservation.presale_closes_at.isoformat()}")

    return {
        "summary": f"{event.title}（{session.location_label}）",
        "location": session.venue_name or "",
        "description": "\n".join(description_lines),
        "start": {"dateTime": session.starts_at.isoformat()},
        "end": {"dateTime": end.isoformat()},
    }


class GoogleCalendarPublisher(Publisher):
    channel_name = "gcal"

    def __init__(self, *, service_account_json: str, calendar_id: str) -> None:
        credentials = service_account.Credentials.from_service_account_info(
            json.loads(service_account_json), scopes=SCOPES
        )
        self._service = build("calendar", "v3", credentials=credentials)
        self._calendar_id = calendar_id

    def publish(self, events: list[Event], repository: EventRepository) -> None:
        for event in events:
            for session in event.sessions:
                body = _session_to_gcal_body(event, session)
                if body is None:
                    continue

                existing_id = event.publish_status.gcal_event_ids.get(session.location_label)
                try:
                    if existing_id:
                        self._service.events().update(
                            calendarId=self._calendar_id, eventId=existing_id, body=body
                        ).execute()
                    else:
                        created = (
                            self._service.events()
                            .insert(calendarId=self._calendar_id, body=body)
                            .execute()
                        )
                        repository.set_gcal_event_id(event.id, session.location_label, created["id"])
                except Exception:
                    logger.exception(
                        "Failed to sync event %s session %s to Google Calendar",
                        event.id,
                        session.location_label,
                    )
