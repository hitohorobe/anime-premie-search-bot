"""Shared helper for building short SNS post text from an Event."""

from __future__ import annotations

from ..models import Event

_AVAILABILITY_LABELS = {
    "available": "受付中",
    "not_yet_open": "受付前",
    "closed": "受付終了",
    "sold_out": "完売",
}


def build_post_text(event: Event, *, max_length: int) -> str:
    parts = [event.title]

    first_session = event.sessions[0] if event.sessions else None
    if first_session and first_session.starts_at:
        parts.append(first_session.starts_at.strftime("%Y/%m/%d %H:%M"))
    if first_session and first_session.venue_name:
        parts.append(first_session.venue_name)
    availability_label = _AVAILABILITY_LABELS.get(event.reservation.availability_status)
    if availability_label:
        parts.append(availability_label)
    if event.reservation.ticket_url:
        parts.append(event.reservation.ticket_url)
    parts.append(event.source_url)

    text = " / ".join(parts)
    if len(text) <= max_length:
        return text

    # Trim from the longest non-essential part (title) first; URLs stay intact.
    overflow = len(text) - max_length
    title = parts[0]
    parts[0] = title[: max(0, len(title) - overflow - 1)] + "…"
    return " / ".join(parts)
