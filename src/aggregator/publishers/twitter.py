"""Post new events to X (Twitter) via API v2."""

from __future__ import annotations

import logging

import tweepy

from ..models import Event
from ..storage import EventRepository
from .base import Publisher
from .text import build_post_text

logger = logging.getLogger(__name__)

MAX_POST_LENGTH = 270  # leave headroom under X's 280-character limit


class TwitterPublisher(Publisher):
    channel_name = "twitter"

    def __init__(self, *, api_key: str, api_secret: str, access_token: str, access_token_secret: str) -> None:
        self._client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
        )

    def publish(self, events: list[Event], repository: EventRepository) -> None:
        for event in events:
            if event.publish_status.twitter:
                continue
            try:
                self._client.create_tweet(text=build_post_text(event, max_length=MAX_POST_LENGTH))
            except Exception:
                logger.exception("Failed to post event %s to X", event.id)
                continue
            repository.mark_published(event.id, "twitter")
