"""Turn a scraped article's body text into a structured Event candidate."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone

import anthropic
from pydantic import BaseModel, ValidationError

from ..models import Event, ExtractionMeta, ReservationWindow, Session
from ..sources.base import RawArticle
from .prompts import (
    EVENT_JSON_SCHEMA,
    RESERVATION_JSON_SCHEMA,
    RESERVATION_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    build_reservation_user_prompt,
    build_user_prompt,
)

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-haiku-4-5"


class _ExtractedSession(BaseModel):
    location_label: str
    venue_name: str | None = None
    venue_address: str | None = None
    starts_at: datetime | None = None
    doors_open_at: datetime | None = None
    ends_at: datetime | None = None


class _ExtractedReservation(BaseModel):
    presale_opens_at: datetime | None = None
    presale_closes_at: datetime | None = None
    general_opens_at: datetime | None = None
    general_closes_at: datetime | None = None
    ticket_url: str | None = None


class _ExtractedEvent(BaseModel):
    title: str
    is_screening_event: bool
    is_report: bool
    sessions: list[_ExtractedSession]
    reservation: _ExtractedReservation
    confidence_notes: str


class _ExtractedReservationInfo(BaseModel):
    presale_opens_at: datetime | None = None
    presale_closes_at: datetime | None = None
    general_opens_at: datetime | None = None
    general_closes_at: datetime | None = None
    availability_status: str | None = None
    confidence_notes: str


def _raw_text_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_event(
    article: RawArticle,
    *,
    client: anthropic.Anthropic,
    model: str = DEFAULT_MODEL,
) -> Event | None:
    """Call the LLM to extract structured fields from one article.

    Returns None (and logs) on any extraction failure — callers should skip
    the article and let it be retried on a future pipeline run, rather than
    crashing the whole batch.
    """
    try:
        response = client.messages.create(
            model=model,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": build_user_prompt(title=article.title, url=article.url, text=article.text),
                }
            ],
            output_config={"format": {"type": "json_schema", "schema": EVENT_JSON_SCHEMA}},
        )
    except anthropic.APIError:
        logger.exception("LLM request failed for article %s", article.id)
        return None

    if response.stop_reason == "refusal":
        logger.warning("LLM refused to extract article %s", article.id)
        return None

    text_block = next((b for b in response.content if b.type == "text"), None)
    if text_block is None:
        logger.warning("LLM response had no text block for article %s", article.id)
        return None

    try:
        raw = json.loads(text_block.text)
        extracted = _ExtractedEvent.model_validate(raw)
    except (json.JSONDecodeError, ValidationError):
        logger.exception("Failed to parse/validate LLM output for article %s", article.id)
        return None

    if not extracted.is_screening_event:
        logger.info("Article %s is not a screening/streaming event, skipping", article.id)
        return None

    sessions = [
        Session(
            location_label=s.location_label,
            venue_name=s.venue_name,
            venue_address=s.venue_address,
            starts_at=s.starts_at,
            doors_open_at=s.doors_open_at,
            ends_at=s.ends_at,
        )
        for s in extracted.sessions
    ]

    return Event(
        id=f"{article.source_site}-{article.id}",
        title=extracted.title,
        source_url=article.url,
        source_site=article.source_site,
        fetched_at=datetime.now(timezone.utc),
        sessions=sessions,
        reservation=ReservationWindow(**extracted.reservation.model_dump()),
        is_report=extracted.is_report,
        extraction=ExtractionMeta(
            model=model,
            confidence_notes=extracted.confidence_notes,
            raw_text_hash=_raw_text_hash(article.text),
        ),
    )


def extract_reservation_info(
    text: str,
    *,
    event_title: str,
    ticket_url: str,
    client: anthropic.Anthropic,
    model: str = DEFAULT_MODEL,
) -> ReservationWindow | None:
    """Call the LLM to read reservation timing/availability off a ticket page.

    Returns None (and logs) on any failure — callers should keep whatever
    reservation data they already have rather than erasing it.
    """
    try:
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=RESERVATION_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": build_reservation_user_prompt(event_title=event_title, ticket_url=ticket_url, text=text),
                }
            ],
            output_config={"format": {"type": "json_schema", "schema": RESERVATION_JSON_SCHEMA}},
        )
    except anthropic.APIError:
        logger.exception("LLM request failed for ticket page %s", ticket_url)
        return None

    if response.stop_reason == "refusal":
        logger.warning("LLM refused to extract ticket page %s", ticket_url)
        return None

    text_block = next((b for b in response.content if b.type == "text"), None)
    if text_block is None:
        logger.warning("LLM response had no text block for ticket page %s", ticket_url)
        return None

    try:
        raw = json.loads(text_block.text)
        extracted = _ExtractedReservationInfo.model_validate(raw)
    except (json.JSONDecodeError, ValidationError):
        logger.exception("Failed to parse/validate LLM output for ticket page %s", ticket_url)
        return None

    return ReservationWindow(
        presale_opens_at=extracted.presale_opens_at,
        presale_closes_at=extracted.presale_closes_at,
        general_opens_at=extracted.general_opens_at,
        general_closes_at=extracted.general_closes_at,
        ticket_url=ticket_url,
        availability_status=extracted.availability_status,
        checked_at=datetime.now(timezone.utc),
    )
