from pathlib import Path

from aggregator.sources.animatetimes import BODY_KEYWORDS, AnimatetimesScraper
from aggregator.sources.base import ArticleRef

FIXTURES = Path(__file__).parent / "fixtures"

EMPTY_LISTING_HTML = "<html><body><p>no more articles</p></body></html>"


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        pass


class _FakeClient:
    """Maps URL substrings to canned HTML. Unmatched listing pages (anime/?p=N)
    return an empty page so pagination terminates naturally; unmatched article
    URLs raise, to catch unintended fetches."""

    def __init__(self, pages: dict[str, str]) -> None:
        self._pages = pages

    def get(self, url: str) -> _FakeResponse:
        for key, text in self._pages.items():
            if key in url:
                return _FakeResponse(text)
        if "anime/?p=" in url:
            return _FakeResponse(EMPTY_LISTING_HTML)
        raise AssertionError(f"unexpected url requested: {url}")


def _scraper_with_fixtures(*, max_pages: int = 10) -> AnimatetimesScraper:
    listing_html = (FIXTURES / "animatetimes_listing.html").read_text(encoding="utf-8")
    article_html = (FIXTURES / "animatetimes_article.html").read_text(encoding="utf-8")
    client = _FakeClient(
        {
            "anime/?p=1": listing_html,
            "details.php?id=1111111111": article_html,
        }
    )
    return AnimatetimesScraper(client=client, max_pages=max_pages)  # type: ignore[arg-type]


def test_list_articles_returns_all_article_ids():
    """list_articles() yields all articles regardless of title keywords."""
    scraper = _scraper_with_fixtures()
    refs = list(scraper.list_articles())

    ids = {ref.id for ref in refs}
    assert ids == {"1111111111", "2222222222", "3333333333"}


def test_list_articles_deduplicates_by_id():
    scraper = _scraper_with_fixtures()
    refs = list(scraper.list_articles())
    assert len(refs) == len(set(ref.id for ref in refs))


def test_list_articles_stops_once_page_is_empty():
    scraper = _scraper_with_fixtures(max_pages=10)
    refs = list(scraper.list_articles())
    assert {ref.id for ref in refs} == {"1111111111", "2222222222", "3333333333"}


def test_list_articles_continues_to_next_page_when_new_articles_remain():
    listing_html = (FIXTURES / "animatetimes_listing.html").read_text(encoding="utf-8")
    listing_page2_html = (FIXTURES / "animatetimes_listing_page2.html").read_text(encoding="utf-8")
    article_html = (FIXTURES / "animatetimes_article.html").read_text(encoding="utf-8")
    client = _FakeClient(
        {
            "anime/?p=1": listing_html,
            "anime/?p=2": listing_page2_html,
            "details.php?id=1111111111": article_html,
        }
    )
    scraper = AnimatetimesScraper(client=client)  # type: ignore[arg-type]

    refs = list(scraper.list_articles())

    assert {ref.id for ref in refs} == {"1111111111", "2222222222", "3333333333", "4444444444", "5555555555"}


def test_list_articles_stops_pagination_once_page_is_fully_known():
    listing_html = (FIXTURES / "animatetimes_listing.html").read_text(encoding="utf-8")
    listing_page2_html = (FIXTURES / "animatetimes_listing_page2.html").read_text(encoding="utf-8")
    client = _FakeClient(
        {
            "anime/?p=1": listing_html,
            "anime/?p=2": listing_page2_html,
        }
    )
    scraper = AnimatetimesScraper(client=client)  # type: ignore[arg-type]

    # All ids on page 1 are already known — page 2 must not be requested.
    refs = list(scraper.list_articles(known_ids={"1111111111", "2222222222", "3333333333"}))

    assert refs == []


def test_list_articles_skips_known_ids():
    """Known IDs are excluded from yielded refs but still count for early-stop."""
    listing_html = (FIXTURES / "animatetimes_listing.html").read_text(encoding="utf-8")
    client = _FakeClient({"anime/?p=1": listing_html})
    scraper = AnimatetimesScraper(client=client, max_pages=1)  # type: ignore[arg-type]

    refs = list(scraper.list_articles(known_ids={"1111111111"}))

    ids = {ref.id for ref in refs}
    assert "1111111111" not in ids
    assert ids == {"2222222222", "3333333333"}


def test_body_keywords_contains_expected_terms():
    for term in ("先行上映", "舞台挨拶", "試写会", "イベント", "ファンミーティング", "復活上映", "トークショー"):
        assert term in BODY_KEYWORDS


def test_fetch_article_extracts_title_and_body_text():
    scraper = _scraper_with_fixtures()
    ref = next(r for r in scraper.list_articles() if r.id == "1111111111")

    article = scraper.fetch_article(ref)

    assert article is not None
    assert article.id == "1111111111"
    assert article.source_site == "animatetimes"
    assert "第13話先行上映会" in article.title
    assert "テストホール" in article.text
    assert "予約サイト" in article.text
    assert "header noise" not in article.text
    assert "footer noise" not in article.text


def test_fetch_article_returns_none_when_body_has_no_keywords():
    no_keyword_html = """
    <html><body>
      <nav>nav noise</nav>
      <article>グッズ情報: Tシャツ・マグカップ・ポスター等の発売が決定しました。</article>
      <footer>footer noise</footer>
    </body></html>
    """
    client = _FakeClient({"details.php?id=9999999999": no_keyword_html})
    scraper = AnimatetimesScraper(client=client, max_pages=1)  # type: ignore[arg-type]

    ref = ArticleRef(
        id="9999999999",
        url="https://www.animatetimes.com/news/details.php?id=9999999999",
        title="グッズ情報まとめ",
    )
    assert scraper.fetch_article(ref) is None
