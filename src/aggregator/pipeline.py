"""scrape -> extract -> persist -> publish orchestration.

Designed for a scheduled batch job: a failure isolated to one source, one
article, or one publisher must not abort the rest of the run.
"""

from __future__ import annotations

import logging

import anthropic
import httpx

from .config import Config
from .extraction import extract_event, extract_reservation_info
from .models import Event, ReservationWindow
from .publishers import (
    BlueskyPublisher,
    GoogleCalendarPublisher,
    Publisher,
    RssPublisher,
    SitePublisher,
    TwitterPublisher,
)
from .sources import AnimatetimesScraper, fetch_ticket_page_text
from .sources.animatetimes import USER_AGENT
from .sources.base import SourceScraper
from .storage import EventRepository

logger = logging.getLogger(__name__)


def _build_collect_publishers(config: Config) -> list[Publisher]:
    """RSS/site/calendar — published right alongside collection, every run."""
    publishers: list[Publisher] = [RssPublisher(), SitePublisher()]

    if config.has_gcal_credentials:
        publishers.append(
            GoogleCalendarPublisher(
                service_account_json=config.google_service_account_json,
                calendar_id=config.gcal_calendar_id,
            )
        )
    else:
        logger.info("Google Calendar credentials not configured, skipping Calendar publisher")

    return publishers


def _build_sns_publishers(config: Config) -> list[Publisher]:
    """X/Bluesky — run from the separate publish-sns pipeline (see run_publish_sns)."""
    publishers: list[Publisher] = []

    if config.has_x_credentials:
        publishers.append(
            TwitterPublisher(
                api_key=config.x_api_key,
                api_secret=config.x_api_secret,
                access_token=config.x_access_token,
                access_token_secret=config.x_access_token_secret,
            )
        )
    else:
        logger.info("X credentials not configured, skipping X publisher")

    if config.has_bluesky_credentials:
        publishers.append(
            BlueskyPublisher(handle=config.bluesky_handle, app_password=config.bluesky_app_password)
        )
    else:
        logger.info("Bluesky credentials not configured, skipping Bluesky publisher")

    return publishers


def _merge_reservation(existing: ReservationWindow, fresh: ReservationWindow) -> ReservationWindow:
    """Prefer values just read off the ticket page; keep prior values for
    anything the ticket page didn't mention (e.g. it may only show the
    general-sale window, not the presale one already known from the article).
    """
    return ReservationWindow(
        presale_opens_at=fresh.presale_opens_at or existing.presale_opens_at,
        presale_closes_at=fresh.presale_closes_at or existing.presale_closes_at,
        general_opens_at=fresh.general_opens_at or existing.general_opens_at,
        general_closes_at=fresh.general_closes_at or existing.general_closes_at,
        ticket_url=existing.ticket_url,
        availability_status=fresh.availability_status or existing.availability_status,
        checked_at=fresh.checked_at,
    )


def _refresh_ticket_reservations(
    repository: EventRepository,
    *,
    llm_client: anthropic.Anthropic,
    model: str,
    http_client: httpx.Client,
) -> None:
    candidates: list[Event] = [
        event
        for event in repository.all_events()
        if event.reservation.ticket_url and not event.is_concluded()
    ]

    for event in candidates:
        ticket_url = event.reservation.ticket_url
        try:
            text = fetch_ticket_page_text(ticket_url, client=http_client)
            if text is None:
                continue

            fresh = extract_reservation_info(
                text,
                event_title=event.title,
                ticket_url=ticket_url,
                client=llm_client,
                model=model,
            )
            if fresh is None:
                continue

            repository.update_reservation(event.id, _merge_reservation(event.reservation, fresh))
        except Exception:
            logger.exception("Failed to refresh ticket page reservation info for event %s", event.id)


def run_collect(*, config: Config | None = None, dry_run: bool = False, max_pages: int | None = None) -> EventRepository:
    config = config or Config.from_env()
    repository = EventRepository()

    effective_max_pages = max_pages if max_pages is not None else config.animatetimes_max_pages
    sources: list[SourceScraper] = [AnimatetimesScraper(max_pages=effective_max_pages)]
    llm_client = anthropic.Anthropic(api_key=config.anthropic_api_key) if config.anthropic_api_key else None

    known_ids = repository.known_ids()

    for source in sources:
        prefix = f"{source.site_name}-"
        source_known_ids = {eid[len(prefix):] for eid in known_ids if eid.startswith(prefix)}

        try:
            refs = list(source.list_articles(known_ids=source_known_ids))
        except Exception:
            logger.exception("Failed to list articles from %s", source.site_name)
            continue

        new_refs = [ref for ref in refs if ref.id not in source_known_ids]
        if not new_refs:
            logger.info("%s: no new articles", source.site_name)
            continue

        if llm_client is None:
            logger.warning("ANTHROPIC_API_KEY not set, skipping extraction for %d new articles", len(new_refs))
            continue

        for ref in new_refs:
            try:
                article = source.fetch_article(ref)
            except Exception:
                logger.exception("Failed to fetch article %s from %s", ref.id, source.site_name)
                continue

            if article is None:
                logger.debug("Article %s from %s has no body keywords, skipping", ref.id, source.site_name)
                repository.mark_seen(f"{source.site_name}-{ref.id}")
                continue

            event = extract_event(article, client=llm_client, model=config.llm_model)
            if event is None:
                continue

            if event.is_concluded():
                logger.info("Event %s has already concluded, skipping", event.id)
                continue

            repository.upsert(event)

    if llm_client is None:
        logger.warning("ANTHROPIC_API_KEY not set, skipping ticket page reservation checks")
    else:
        ticket_http_client = httpx.Client(
            headers={"User-Agent": USER_AGENT}, timeout=20.0, follow_redirects=True
        )
        try:
            _refresh_ticket_reservations(
                repository, llm_client=llm_client, model=config.llm_model, http_client=ticket_http_client
            )
        finally:
            ticket_http_client.close()

    if dry_run:
        logger.info("Dry run: skipping publish step and not saving repository")
        return repository

    repository.save()

    publishers = _build_collect_publishers(config)
    all_events = repository.all_events()
    for publisher in publishers:
        try:
            publisher.publish(all_events, repository)
        except Exception:
            logger.exception("Publisher %s failed", publisher.channel_name)

    repository.save()
    return repository


def run_publish_sns(*, config: Config | None = None, dry_run: bool = False) -> EventRepository:
    """Post pending events to X/Bluesky only.

    Reads the repository data run_collect already persisted — no scraping or
    LLM extraction here. Run as a separate pipeline/workflow so SNS posting
    (irreversible) is decoupled from collection.
    """
    config = config or Config.from_env()
    repository = EventRepository()

    publishers = _build_sns_publishers(config)
    if not publishers:
        logger.info("No SNS publishers configured, nothing to do")
        return repository

    pending_events = [event for event in repository.all_events() if not event.is_concluded()]

    for publisher in publishers:
        try:
            publisher.publish(pending_events, repository)
        except Exception:
            logger.exception("Publisher %s failed", publisher.channel_name)

    if dry_run:
        logger.info("Dry run: not saving publish_status updates")
        return repository

    repository.save()
    return repository
