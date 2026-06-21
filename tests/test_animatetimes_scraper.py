from pathlib import Path

from aggregator.sources.animatetimes import AnimatetimesScraper

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


def test_list_articles_only_returns_event_like_titles():
    scraper = _scraper_with_fixtures()
    refs = list(scraper.list_articles())

    ids = {ref.id for ref in refs}
    assert ids == {"1111111111", "2222222222"}  # the goods-roundup article is excluded


def test_list_articles_deduplicates_by_id():
    scraper = _scraper_with_fixtures()
    refs = list(scraper.list_articles())
    assert len(refs) == len(set(ref.id for ref in refs))


def test_list_articles_stops_once_page_is_empty():
    scraper = _scraper_with_fixtures(max_pages=10)
    # page 2 onward is the empty fixture, so list_articles must not loop
    # max_pages times — it should stop right after page 1.
    refs = list(scraper.list_articles())
    assert {ref.id for ref in refs} == {"1111111111", "2222222222"}


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

    assert {ref.id for ref in refs} == {"1111111111", "2222222222", "4444444444", "5555555555"}


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

    # Every id on page 1 (including the non-event one) is already known, so
    # the scraper should stop before ever requesting page 2.
    refs = list(scraper.list_articles(known_ids={"1111111111", "2222222222", "3333333333"}))

    assert {ref.id for ref in refs} == {"1111111111", "2222222222"}


def test_fetch_article_extracts_title_and_body_text():
    scraper = _scraper_with_fixtures()
    ref = next(r for r in scraper.list_articles() if r.id == "1111111111")

    article = scraper.fetch_article(ref)

    assert article.id == "1111111111"
    assert article.source_site == "animatetimes"
    assert "第13話先行上映会" in article.title
    assert "テストホール" in article.text
    assert "予約サイト" in article.text
    assert "header noise" not in article.text
    assert "footer noise" not in article.text
