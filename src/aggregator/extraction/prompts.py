"""Prompt and output schema for the LLM extraction step."""

SYSTEM_PROMPT = (
    "あなたはアニメニュース記事から先行上映会・先行配信イベントの情報を抽出するアシスタントです。"
    "記事本文に含まれる事実のみを抽出し、本文に書かれていない情報を推測で補わないでください。"
    "日時は記事に明記された西暦・月日・時刻からISO 8601形式（タイムゾーンは日本時間 +09:00）に変換してください。"
    "年が明記されていない場合は記事の文脈から妥当な年を推測し、どうしても判断できない場合はnullにしてください。"
    "複数の会場・複数の回がある場合はsessionsに複数要素を入れてください。"
    "情報が存在しない項目はnullにしてください。"
)

EVENT_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "イベント名・対象アニメ作品名を含む短い名称"},
        "is_screening_event": {
            "type": "boolean",
            "description": "この記事が先行上映会・先行配信・舞台挨拶付き上映会などのイベント告知/レポートであるか",
        },
        "sessions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "location_label": {"type": "string", "description": "例: 東京, 大阪"},
                    "venue_name": {"type": ["string", "null"]},
                    "venue_address": {"type": ["string", "null"]},
                    "starts_at": {"type": ["string", "null"], "description": "ISO 8601"},
                    "doors_open_at": {"type": ["string", "null"], "description": "ISO 8601"},
                    "ends_at": {"type": ["string", "null"], "description": "ISO 8601"},
                },
                "required": ["location_label", "venue_name", "venue_address", "starts_at", "doors_open_at", "ends_at"],
                "additionalProperties": False,
            },
        },
        "reservation": {
            "type": "object",
            "properties": {
                "presale_opens_at": {"type": ["string", "null"], "description": "ISO 8601"},
                "presale_closes_at": {"type": ["string", "null"], "description": "ISO 8601"},
                "general_opens_at": {"type": ["string", "null"], "description": "ISO 8601"},
                "general_closes_at": {"type": ["string", "null"], "description": "ISO 8601"},
                "ticket_url": {"type": ["string", "null"]},
            },
            "required": [
                "presale_opens_at",
                "presale_closes_at",
                "general_opens_at",
                "general_closes_at",
                "ticket_url",
            ],
            "additionalProperties": False,
        },
        "confidence_notes": {
            "type": "string",
            "description": "抽出時に不確実だった点があれば短く記載。なければ空文字",
        },
    },
    "required": ["title", "is_screening_event", "sessions", "reservation", "confidence_notes"],
    "additionalProperties": False,
}


def build_user_prompt(*, title: str, url: str, text: str) -> str:
    return (
        f"以下はアニメ情報サイトの記事です。\n\n"
        f"記事タイトル: {title}\n"
        f"記事URL: {url}\n\n"
        f"--- 本文 ---\n{text}\n--- 本文ここまで ---\n\n"
        "この記事から先行上映会・先行配信イベントの情報を抽出してください。"
    )


RESERVATION_SYSTEM_PROMPT = (
    "あなたはチケット予約サイトのページから、あるイベントの予約受付状況を読み取るアシスタントです。"
    "ページ本文に含まれる事実のみを抽出し、書かれていない情報を推測で補わないでください。"
    "日時は西暦・月日・時刻からISO 8601形式（タイムゾーンは日本時間 +09:00）に変換してください。"
    "年が明記されていない場合はページの文脈から妥当な年を推測し、どうしても判断できない場合はnullにしてください。"
    "現在の受付状況（availability_status）は次のいずれかから最も当てはまるものを選んでください: "
    "'available'（受付中・購入可能）、'not_yet_open'（受付開始前）、'closed'（受付終了）、'sold_out'（完売）。"
    "判断できない場合はnullにしてください。"
    "情報が存在しない項目はnullにしてください。"
)

RESERVATION_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "presale_opens_at": {"type": ["string", "null"], "description": "ISO 8601"},
        "presale_closes_at": {"type": ["string", "null"], "description": "ISO 8601"},
        "general_opens_at": {"type": ["string", "null"], "description": "ISO 8601"},
        "general_closes_at": {"type": ["string", "null"], "description": "ISO 8601"},
        "availability_status": {
            "type": ["string", "null"],
            "enum": ["available", "not_yet_open", "closed", "sold_out", None],
            "description": "現在の予約受付状況",
        },
        "confidence_notes": {
            "type": "string",
            "description": "抽出時に不確実だった点があれば短く記載。なければ空文字",
        },
    },
    "required": [
        "presale_opens_at",
        "presale_closes_at",
        "general_opens_at",
        "general_closes_at",
        "availability_status",
        "confidence_notes",
    ],
    "additionalProperties": False,
}


def build_reservation_user_prompt(*, event_title: str, ticket_url: str, text: str) -> str:
    return (
        f"以下は「{event_title}」の予約/チケット販売ページです。\n\n"
        f"ページURL: {ticket_url}\n\n"
        f"--- 本文 ---\n{text}\n--- 本文ここまで ---\n\n"
        "このページから予約開始/終了日時と現在の受付状況を抽出してください。"
    )
