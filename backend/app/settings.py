"""Application settings using Pydantic.

This module centralises configuration values that the application
depends on.  It uses Pydantic’s BaseSettings so that values can be
loaded from environment variables or a `.env` file when running
locally.  These settings include the Vertex AI model ID, region, and
any other global constants.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global configuration for the Vista AI backend.

    Attributes:
        model_id: The ID of the Gemini Live model to use
        location: The region/location of the model endpoint (e.g. europe-west4)
        system_instructions: The long constitution/system prompt for the assistant
    """

    model_id: str = "gemini-live-2.5-flash-native-audio"
    location: str = "us-central1"
    system_instructions: str = ""

    class Config:
        env_prefix = "VISTA_"


settings = Settings()  # type: ignore[call-arg]