import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


def test_settings_load_from_env_file() -> None:
    get_settings.cache_clear()
    settings = get_settings()

    assert settings.openai_base_url == "https://api.minimaxi.com/v1"
    assert settings.minimax_model == "MiniMax-M2.5"
    assert settings.openai_api_key
    assert settings.minimax_timeout_seconds == 30.0
    assert settings.minimax_max_retries == 2
    assert settings.delilegal_timeout_seconds == 20.0
    assert settings.app_log_level == "INFO"


def test_settings_require_env_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("MINIMAX_MODEL", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
