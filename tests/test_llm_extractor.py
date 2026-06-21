import json
from dataclasses import dataclass
from unittest.mock import MagicMock

from aggregator.extraction.llm_extractor import extract_event, extract_reservation_info
from aggregator.sources.base import RawArticle


@dataclass
class _FakeTextBlock:
    text: str
    type: str = "text"


@dataclass
class _FakeResponse:
    content: list
    stop_reason: str = "end_turn"


def _article() -> RawArticle:
    return RawArticle(
        id="1111111111",
        url="https://www.animatetimes.com/news/details.php?id=1111111111",
        title="『テストアニメ』第13話先行上映会が開催決定",
        text="名称: テストアニメ第13話先行上映会\n日程: 2026年7月19日18:30開演\n会場: テストホール",
        source_site="animatetimes",
    )


def _extraction_payload(**overrides) -> dict:
    payload = {
        "title": "テストアニメ 第13話先行上映会",
        "is_screening_event": True,
        "sessions": [
            {
                "location_label": "東京",
                "venue_name": "テストホール",
                "venue_address": None,
                "starts_at": "2026-07-19T18:30:00+09:00",
                "doors_open_at": "2026-07-19T17:30:00+09:00",
                "ends_at": "2026-07-19T20:00:00+09:00",
            }
        ],
        "reservation": {
            "presale_opens_at": "2026-06-11T18:00:00+09:00",
            "presale_closes_at": "2026-07-07T23:00:00+09:00",
            "general_opens_at": None,
            "general_closes_at": None,
            "ticket_url": "https://example-ticket.test/test-anime/",
        },
        "confidence_notes": "",
    }
    payload.update(overrides)
    return payload


def _client_returning(payload: dict, *, stop_reason: str = "end_turn") -> MagicMock:
    client = MagicMock()
    client.messages.create.return_value = _FakeResponse(
        content=[_FakeTextBlock(text=json.dumps(payload))],
        stop_reason=stop_reason,
    )
    return client


def test_extract_event_builds_event_from_valid_llm_output():
    client = _client_returning(_extraction_payload())

    event = extract_event(_article(), client=client, model="claude-haiku-4-5")

    assert event is not None
    assert event.id == "animatetimes-1111111111"
    assert event.sessions[0].location_label == "東京"
    assert event.sessions[0].venue_name == "テストホール"
    assert event.reservation.ticket_url == "https://example-ticket.test/test-anime/"
    assert event.extraction.raw_text_hash.startswith("sha256:")


def test_extract_event_returns_none_when_not_a_screening_event():
    client = _client_returning(_extraction_payload(is_screening_event=False, sessions=[]))

    event = extract_event(_article(), client=client, model="claude-haiku-4-5")

    assert event is None


def test_extract_event_returns_none_on_refusal():
    client = _client_returning(_extraction_payload(), stop_reason="refusal")

    event = extract_event(_article(), client=client, model="claude-haiku-4-5")

    assert event is None


def test_extract_event_returns_none_on_invalid_json():
    client = MagicMock()
    client.messages.create.return_value = _FakeResponse(
        content=[_FakeTextBlock(text="not json")],
        stop_reason="end_turn",
    )

    event = extract_event(_article(), client=client, model="claude-haiku-4-5")

    assert event is None


def _reservation_payload(**overrides) -> dict:
    payload = {
        "presale_opens_at": None,
        "presale_closes_at": None,
        "general_opens_at": "2026-07-01T10:00:00+09:00",
        "general_closes_at": None,
        "availability_status": "available",
        "confidence_notes": "",
    }
    payload.update(overrides)
    return payload


def test_extract_reservation_info_builds_reservation_window():
    client = _client_returning(_reservation_payload())

    reservation = extract_reservation_info(
        "受付中です。一般発売: 2026年7月1日10:00〜",
        event_title="テストアニメ 第13話先行上映会",
        ticket_url="https://example-ticket.test/test-anime/",
        client=client,
        model="claude-haiku-4-5",
    )

    assert reservation is not None
    assert reservation.availability_status == "available"
    assert reservation.general_opens_at is not None
    assert reservation.ticket_url == "https://example-ticket.test/test-anime/"
    assert reservation.checked_at is not None


def test_extract_reservation_info_returns_none_on_refusal():
    client = _client_returning(_reservation_payload(), stop_reason="refusal")

    reservation = extract_reservation_info(
        "text",
        event_title="テストアニメ",
        ticket_url="https://example-ticket.test/test-anime/",
        client=client,
        model="claude-haiku-4-5",
    )

    assert reservation is None


def test_extract_reservation_info_returns_none_on_invalid_json():
    client = MagicMock()
    client.messages.create.return_value = _FakeResponse(
        content=[_FakeTextBlock(text="not json")],
        stop_reason="end_turn",
    )

    reservation = extract_reservation_info(
        "text",
        event_title="テストアニメ",
        ticket_url="https://example-ticket.test/test-anime/",
        client=client,
        model="claude-haiku-4-5",
    )

    assert reservation is None
