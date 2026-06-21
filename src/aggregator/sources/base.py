"""Common interface every news-source scraper implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ArticleRef:
    """A lightweight pointer to an article found on a listing page."""

    id: str
    url: str
    title: str


@dataclass(frozen=True)
class RawArticle:
    """An article's body, ready to hand to the LLM extractor."""

    id: str
    url: str
    title: str
    text: str
    source_site: str


class SourceScraper(ABC):
    """Base class for a site-specific scraper.

    Implementations only need to know how to (1) list candidate articles and
    (2) fetch+clean one article's body text. Dedup against already-known IDs
    and the extraction step itself live outside this class.
    """

    #: short, stable identifier used as part of Event.id and Event.source_site
    site_name: str

    @abstractmethod
    def list_articles(self, known_ids: set[str] | None = None) -> Iterable[ArticleRef]:
        """Return candidate articles from the source's listing page(s).

        ``known_ids`` (already-persisted Event.id values) lets a paginated
        scraper stop early once it reaches articles it has already seen,
        instead of always walking every page.
        """

    @abstractmethod
    def fetch_article(self, ref: ArticleRef) -> RawArticle:
        """Fetch and clean one article's body text."""
