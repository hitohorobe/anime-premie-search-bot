"""Generic fetcher for ticket-vendor pages linked from articles.

Ticket URLs point to many different playguide sites (l-tike, eplus, etc.)
with no shared markup, so unlike AnimatetimesScraper this targets no
particular site — it strips obvious noise tags and returns whatever text
remains for the LLM to read. Pages that need JavaScript to render their
content will yield little or no useful text; callers treat that the same as
a fetch failure (skip, keep whatever reservation data is already known).
"""

from __future__ import annotations

import logging

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

MAX_TEXT_LENGTH = 8000  # keeps LLM input small/cheap; ticket pages rarely need more


def fetch_ticket_page_text(url: str, *, client: httpx.Client) -> str | None:
    """Fetch and clean a ticket page's body text, or None on any failure."""
    try:
        response = client.get(url)
        response.raise_for_status()
    except httpx.HTTPError:
        logger.warning("Failed to fetch ticket page %s", url, exc_info=True)
        return None

    soup = BeautifulSoup(response.text, "lxml")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()

    text = soup.get_text("\n", strip=True)
    if not text:
        return None
    return text[:MAX_TEXT_LENGTH]
