import os

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .constitution import DEFAULT_SYSTEM_INSTRUCTIONS


DEPRECATED_LIVE_MODEL_ID = "gemini-live-2.5-flash-preview-native-audio-09-2025"


class Settings(BaseSettings):
    """Global configuration for the Vista AI backend."""

    model_id: str = "gemini-live-2.5-flash-native-audio"
    location: str = "us-central1"
    fallback_location: str = "us-central1"
    use_adk: bool = True
    project_id: str = Field(
        default_factory=lambda: (
            os.getenv("GOOGLE_CLOUD_PROJECT")
            or os.getenv("GCLOUD_PROJECT")
            or os.getenv("GOOGLE_CLOUD_PROJECT_ID")
            or ""
        )
    )
    system_instructions: str = DEFAULT_SYSTEM_INSTRUCTIONS

    model_config = SettingsConfigDict(env_prefix="VISTA_", extra="ignore")

    @field_validator("model_id")
    @classmethod
    def validate_model_id(cls, value: str) -> str:
        if value == DEPRECATED_LIVE_MODEL_ID:
            raise ValueError("The deprecated preview Gemini Live model is not allowed.")
        return value


settings = Settings()  # type: ignore[call-arg]
