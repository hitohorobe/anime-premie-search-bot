"""Common interface for everything that republishes events to a channel."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Event
from ..storage import EventRepository


class Publisher(ABC):
    #: matches the PublishStatus field name this publisher is responsible for
    channel_name: str

    @abstractmethod
    def publish(self, events: list[Event], repository: EventRepository) -> None:
        """Publish whatever is pending for this channel.

        Implementations are responsible for checking publish_status
        themselves (per-event for SNS/calendar, or "regenerate everything"
        for RSS/site) and for calling repository.save()-triggering mutations
        (e.g. mark_published) as soon as a side effect succeeds, so a
        mid-run crash can't cause a duplicate post on retry.
        """
