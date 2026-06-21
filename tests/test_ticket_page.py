import httpx

from aggregator.sources.ticket_page import fetch_ticket_page_text


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        pass


class _FakeClient:
    def __init__(self, html: str | None = None, raise_error: bool = False) -> None:
        self._html = html
        self._raise_error = raise_error

    def get(self, url: str) -> _FakeResponse:
        if self._raise_error:
            raise httpx.ConnectError("boom")
        return _FakeResponse(self._html)


def test_fetch_ticket_page_text_extracts_cleaned_text():
    html = """
    <html><body>
    <nav>nav text</nav>
    <main>
      <h1>受付中</h1>
      <p>一般発売: 2026年7月1日10:00〜</p>
    </main>
    <footer>footer text</footer>
    </body></html>
    """
    client = _FakeClient(html=html)

    text = fetch_ticket_page_text("https://example-ticket.test/x", client=client)

    assert text is not None
    assert "受付中" in text
    assert "nav text" not in text
    assert "footer text" not in text


def test_fetch_ticket_page_text_returns_none_on_http_error():
    client = _FakeClient(raise_error=True)

    text = fetch_ticket_page_text("https://example-ticket.test/x", client=client)

    assert text is None


def test_fetch_ticket_page_text_truncates_long_text():
    html = "<html><body>" + "あ" * 20000 + "</body></html>"
    client = _FakeClient(html=html)

    text = fetch_ticket_page_text("https://example-ticket.test/x", client=client)

    assert text is not None
    assert len(text) <= 8000
