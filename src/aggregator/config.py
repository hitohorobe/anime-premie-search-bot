"""Environment-variable-backed configuration for the pipeline and publishers."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    anthropic_api_key: str | None = None
    llm_model: str = "claude-haiku-4-5"

    x_api_key: str | None = None
    x_api_secret: str | None = None
    x_access_token: str | None = None
    x_access_token_secret: str | None = None

    bluesky_handle: str | None = None
    bluesky_app_password: str | None = None

    google_service_account_json: str | None = None
    gcal_calendar_id: str | None = None

    animatetimes_max_pages: int = 30

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
            llm_model=os.environ.get("LLM_MODEL", "claude-haiku-4-5"),
            x_api_key=os.environ.get("X_API_KEY"),
            x_api_secret=os.environ.get("X_API_SECRET"),
            x_access_token=os.environ.get("X_ACCESS_TOKEN"),
            x_access_token_secret=os.environ.get("X_ACCESS_TOKEN_SECRET"),
            bluesky_handle=os.environ.get("BLUESKY_HANDLE"),
            bluesky_app_password=os.environ.get("BLUESKY_APP_PASSWORD"),
            google_service_account_json=os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"),
            gcal_calendar_id=os.environ.get("GCAL_CALENDAR_ID"),
            animatetimes_max_pages=int(os.environ.get("ANIMATETIMES_MAX_PAGES", "30")),
        )

    @property
    def has_x_credentials(self) -> bool:
        return all([self.x_api_key, self.x_api_secret, self.x_access_token, self.x_access_token_secret])

    @property
    def has_bluesky_credentials(self) -> bool:
        return bool(self.bluesky_handle and self.bluesky_app_password)

    @property
    def has_gcal_credentials(self) -> bool:
        return bool(self.google_service_account_json and self.gcal_calendar_id)
