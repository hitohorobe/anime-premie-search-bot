"""Post new events to Bluesky."""

from __future__ import annotations

import logging

from atproto import Client

from ..models import Event
from ..storage import EventRepository
from .base import Publisher
from .text import build_post_text

logger = logging.getLogger(__name__)

MAX_POST_LENGTH = 290  # leave headroom under Bluesky's 300-character limit


class BlueskyPublisher(Publisher):
    channel_name = "bluesky"

    def __init__(self, *, handle: str, app_password: str) -> None:
        self._client = Client()
        self._client.login(handle, app_password)

    def publish(self, events: list[Event], repository: EventRepository) -> None:
        for event in events:
            if event.publish_status.bluesky:
                continue
            try:
                self._client.send_post(text=build_post_text(event, max_length=MAX_POST_LENGTH))
            except Exception:
                logger.exception("Failed to post event %s to Bluesky", event.id)
                continue
            repository.mark_published(event.id, "bluesky")
