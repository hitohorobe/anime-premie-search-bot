from aggregator.config import Config


def test_animatetimes_max_pages_defaults_to_thirty(monkeypatch):
    monkeypatch.delenv("ANIMATETIMES_MAX_PAGES", raising=False)
    assert Config.from_env().animatetimes_max_pages == 30


def test_animatetimes_max_pages_reads_from_env(monkeypatch):
    monkeypatch.setenv("ANIMATETIMES_MAX_PAGES", "3")
    assert Config.from_env().animatetimes_max_pages == 3
