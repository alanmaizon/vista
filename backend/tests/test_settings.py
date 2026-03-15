import os

from backend.app.settings import Settings


def test_cors_origins_parses_comma_delimited_env() -> None:
    os.environ["TUTOR_CORS_ORIGINS"] = "https://vista-ai-488623.web.app,https://vista-ai-488623.firebaseapp.com"
    try:
        settings = Settings()
    finally:
        os.environ.pop("TUTOR_CORS_ORIGINS", None)

    assert settings.cors_origins == [
        "https://vista-ai-488623.web.app",
        "https://vista-ai-488623.firebaseapp.com",
    ]


def test_cors_origins_parses_semicolon_delimited_env() -> None:
    os.environ["TUTOR_CORS_ORIGINS"] = "https://vista-ai-488623.web.app;https://vista-ai-488623.firebaseapp.com"
    try:
        settings = Settings()
    finally:
        os.environ.pop("TUTOR_CORS_ORIGINS", None)

    assert settings.cors_origins == [
        "https://vista-ai-488623.web.app",
        "https://vista-ai-488623.firebaseapp.com",
    ]


def test_cors_origins_parses_json_array_env() -> None:
    os.environ["TUTOR_CORS_ORIGINS"] = '["https://vista-ai-488623.web.app","https://vista-ai-488623.firebaseapp.com"]'
    try:
        settings = Settings()
    finally:
        os.environ.pop("TUTOR_CORS_ORIGINS", None)

    assert settings.cors_origins == [
        "https://vista-ai-488623.web.app",
        "https://vista-ai-488623.firebaseapp.com",
    ]
