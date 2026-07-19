"""Scraper for animatetimes.com.

There is no RSS feed (confirmed: /feed returns 404, no <link rel=alternate>
on the homepage), so this scrapes the news listing page
(https://www.animatetimes.com/anime/?p=N) for article links and the article
detail page for body text. The listing is paginated and sorted newest-first;
list_articles() pages through it and stops as soon as a page contains no
article IDs we haven't already seen, since everything beyond that point is
older than what's already in data/events.json.
"""

from __future__ import annotations

import re
from typing import Iterable

import httpx
from bs4 import BeautifulSoup

from .base import ArticleRef, RawArticle, SourceScraper

LISTING_URL_TEMPLATE = "https://www.animatetimes.com/anime/?p={page}"
ARTICLE_URL_RE = re.compile(r"/news/details\.php\?id=(\d+)")
USER_AGENT = "Mozilla/5.0 (compatible; anime-premiere-aggregator/0.1; +https://github.com/)"
DEFAULT_MAX_PAGES = 30

# 記事本文に対してマッチするキーワード（一覧ページのタイトルではない）。
# 本文はすでに記事コンテンツ要素に絞り込まれているため、「イベント」のような広義の語も
# タイトルマッチでは誤検知が多すぎるが、本文マッチであれば許容できる。
BODY_KEYWORDS = (
    "先行上映",
    "先行配信",
    "舞台挨拶",
    "試写会",
    "上映会",
    "完成披露",
    "先行視聴",
    "講演会",
    "トークショー",
    "イベント",
    "復活上映",
    "ファンミーティング",
)


class AnimatetimesScraper(SourceScraper):
    site_name = "animatetimes"

    def __init__(self, client: httpx.Client | None = None, max_pages: int = DEFAULT_MAX_PAGES) -> None:
        self._client = client or httpx.Client(
            headers={"User-Agent": USER_AGENT}, timeout=20.0, follow_redirects=True
        )
        self._max_pages = max_pages

    def list_articles(self, known_ids: set[str] | None = None) -> Iterable[ArticleRef]:
        known_ids = known_ids or set()
        seen: set[str] = set()

        for page in range(1, self._max_pages + 1):
            response = self._client.get(LISTING_URL_TEMPLATE.format(page=page))
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")

            page_article_ids: set[str] = set()
            page_refs: list[ArticleRef] = []
            for anchor in soup.find_all("a", href=True):
                match = ARTICLE_URL_RE.search(anchor["href"])
                if not match:
                    continue
                article_id = match.group(1)
                page_article_ids.add(article_id)
                if article_id in seen or article_id in known_ids:
                    continue
                title = anchor.get_text(strip=True)
                if not title:
                    continue
                seen.add(article_id)
                page_refs.append(
                    ArticleRef(
                        id=article_id,
                        url=f"https://www.animatetimes.com/news/details.php?id={article_id}",
                        title=title,
                    )
                )

            if not page_article_ids:
                break  # 最終ページを超えた

            yield from page_refs

            if page_article_ids <= known_ids:
                # このページの記事がすべて既知 — それより古いページも不要なので停止。
                break

    def fetch_article(self, ref: ArticleRef) -> RawArticle | None:
        response = self._client.get(ref.url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()

        container = (
            soup.find("article")
            or soup.find(class_=re.compile(r"(article|news)[-_]?(body|detail|content)", re.I))
            or soup.find("main")
            or soup.body
        )
        text = container.get_text("\n", strip=True) if container else soup.get_text("\n", strip=True)

        if not any(keyword in text for keyword in BODY_KEYWORDS):
            return None

        title_tag = soup.find("h1")
        title = title_tag.get_text(strip=True) if title_tag else ref.title

        return RawArticle(
            id=ref.id,
            url=ref.url,
            title=title,
            text=text,
            source_site=self.site_name,
        )
