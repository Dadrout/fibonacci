from typing import Optional
from urllib.parse import urlsplit
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """
    Application Settings using Pydantic BaseSettings.
    Loads variables from .env file and environment.
    """

    # Environment and API settings
    ENVIRONMENT: str = "development"
    API_PORT: int = 8000
    API_HOST: str = "0.0.0.0"
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False
    API_ALLOWED_ORIGINS: str = "https://wizetale.com,https://www.wizetale.com"
    SUPABASE_URL: Optional[str] = None
    SUPABASE_PUBLISHABLE_KEY: Optional[str] = None
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None
    SUPABASE_VIDEO_BUCKET: str = "story-videos"
    MEDIA_STORAGE_PROVIDER: str = "r2"
    R2_ENDPOINT_URL: Optional[str] = None
    R2_ACCESS_KEY_ID: Optional[str] = None
    R2_SECRET_ACCESS_KEY: Optional[str] = None
    R2_BUCKET_NAME: Optional[str] = None
    MEDIA_SIGNED_URL_TTL_SECONDS: int = Field(default=900, ge=60, le=86400)

    # Stability AI API for image generation
    STABILITY_API_KEY: Optional[str] = None

    # Gemini API (for story text generation)
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_BILLING_TIER: str = "unknown"
    GEMINI_TEXT_MODEL: str = "gemini-3.1-flash-lite"
    GEMINI_FALLBACK_TEXT_MODEL: str = "gemini-3-flash-preview"
    GEMINI_IMAGE_MODEL: str = "gemini-3.1-flash-lite-image"
    GEMINI_TEXT_INPUT_USD_PER_MILLION_TOKENS: float = 0.25
    GEMINI_TEXT_OUTPUT_USD_PER_MILLION_TOKENS: float = 1.50
    GEMINI_FALLBACK_TEXT_INPUT_USD_PER_MILLION_TOKENS: float = 0.50
    GEMINI_FALLBACK_TEXT_OUTPUT_USD_PER_MILLION_TOKENS: float = 3.00
    GEMINI_IMAGE_USD_PER_IMAGE: float = 0.034
    AI_PROVIDER: str = "gemini"
    IMAGE_PROVIDER: str = "gemini"
    FAL_KEY: Optional[str] = None
    FAL_IMAGE_MODEL: str = "fal-ai/flux-2/turbo"
    FAL_IMAGE_TIMEOUT_SECONDS: int = Field(default=180, ge=10, le=600)
    FAL_IMAGE_CONCURRENCY: int = Field(default=3, ge=1, le=10)
    CLOUDFLARE_ACCOUNT_ID: Optional[str] = None
    CLOUDFLARE_API_TOKEN: Optional[str] = None
    CLOUDFLARE_IMAGE_MODEL: str = "@cf/black-forest-labs/flux-1-schnell"
    CLOUDFLARE_IMAGE_TIMEOUT_SECONDS: int = Field(default=180, ge=10, le=600)
    IMAGE_GENERATION_CONCURRENCY: int = Field(default=3, ge=1, le=10)
    TTS_PROVIDER: str = "edge"
    ELEVENLABS_API_KEY: Optional[str] = None
    ELEVENLABS_KK_FEMALE_VOICE_ID: Optional[str] = None
    ELEVENLABS_KK_MALE_VOICE_ID: Optional[str] = None
    ENABLE_GEMINI_IMAGE: bool = True
    GENERATION_MAX_SCENES: int = Field(default=10, ge=5, le=10)
    GENERATION_MAX_IMAGES_PER_STORY: int = Field(default=10, ge=0, le=10)
    GENERATION_TARGET_DURATION_SEC: int = 300
    WORKDIR_ROOT: str = "/tmp"
    GOOGLE_TTS_VOICE_EN_FEMALE: str = "en-US-Neural2-F"
    GOOGLE_TTS_VOICE_EN_MALE: str = "en-US-Neural2-J"
    GOOGLE_TTS_VOICE_RU_FEMALE: str = "ru-RU-Wavenet-E"
    GOOGLE_TTS_VOICE_RU_MALE: str = "ru-RU-Wavenet-D"
    EDGE_TTS_VOICE_EN_FEMALE: str = "en-US-AriaNeural"
    EDGE_TTS_VOICE_EN_MALE: str = "en-US-GuyNeural"
    EDGE_TTS_VOICE_RU_FEMALE: str = "ru-RU-SvetlanaNeural"
    EDGE_TTS_VOICE_RU_MALE: str = "ru-RU-DmitryNeural"
    EDGE_TTS_PRESENTATION_VOICE_EN_FEMALE: str = "en-US-JennyNeural"
    EDGE_TTS_PRESENTATION_VOICE_RU_FEMALE: str = "ru-RU-SvetlanaNeural"

    # Azure OpenAI (deprecated)
    AZURE_OPENAI_ENDPOINT: Optional[str] = None
    AZURE_OPENAI_API_KEY: Optional[str] = None
    AZURE_OPENAI_API_VERSION: Optional[str] = None
    AZURE_OPENAI_DEPLOYMENT_NAME: Optional[str] = None

    # Azure Speech (for audio generation)
    AZURE_SPEECH_KEY: Optional[str] = None
    AZURE_SPEECH_REGION: Optional[str] = None

    # Redis URL for Celery broker and cache
    # Use different DB numbers for broker and results backend, e.g., /0 and /1
    REDIS_URL: str = "redis://redis:6379/0"

    GOOGLE_APPLICATION_CREDENTIALS_PATH: Optional[str] = None

    # Default values
    DEFAULT_PERSONA: str = "narrator"
    DEFAULT_LANGUAGE: str = "en"
    TARGET_LANGUAGE: str = "en"
    RUNWARE_API_KEY: str = ""

    # Celery settings
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/1"

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug_flag(cls, value):
        if isinstance(value, bool):
            return value
        if value is None:
            return False

        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "on", "debug"}:
            return True
        if normalized in {"0", "false", "no", "off", "release", "prod", "production"}:
            return False
        return False

    def production_configuration_errors(self) -> list[str]:
        """Return missing or unsafe settings required by the selected production providers."""
        if self.ENVIRONMENT.strip().lower() != "production":
            return []

        def is_configured(value: str | None) -> bool:
            normalized = (value or "").strip().lower()
            return bool(normalized) and not any(
                marker in normalized
                for marker in ("your_", "replace_me", "change_me", "example")
            )

        errors: list[str] = []
        if self.AI_PROVIDER.strip().lower() != "gemini":
            errors.append("AI_PROVIDER must be gemini")
        if self.IMAGE_PROVIDER.strip().lower() not in {"gemini", "fal", "cloudflare"}:
            errors.append("IMAGE_PROVIDER must be gemini, fal, or cloudflare")
        if self.IMAGE_PROVIDER.strip().lower() == "fal" and not is_configured(
            self.FAL_KEY
        ):
            errors.append("FAL_KEY")
        if self.IMAGE_PROVIDER.strip().lower() == "cloudflare":
            for name in ("CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"):
                if not is_configured(getattr(self, name)):
                    errors.append(name)
        if self.TTS_PROVIDER.strip().lower() not in {"edge", "google", "azure"}:
            errors.append("TTS_PROVIDER must be edge, google, or azure")
        if self.MEDIA_STORAGE_PROVIDER.strip().lower() not in {"r2", "supabase"}:
            errors.append("MEDIA_STORAGE_PROVIDER must be r2 or supabase")

        required = [
            "SUPABASE_URL",
            "SUPABASE_PUBLISHABLE_KEY",
            "SUPABASE_SERVICE_ROLE_KEY",
            "REDIS_URL",
        ]
        for name in required:
            if not is_configured(getattr(self, name)):
                errors.append(name)

        if (
            self.AI_PROVIDER.strip().lower() == "gemini"
            or self.IMAGE_PROVIDER.strip().lower() == "gemini"
        ):
            if not is_configured(self.GEMINI_API_KEY):
                errors.append("GEMINI_API_KEY")
            if self.GEMINI_BILLING_TIER.strip().lower() != "paid":
                errors.append("GEMINI_BILLING_TIER must be paid")

        if self.MEDIA_STORAGE_PROVIDER.strip().lower() == "r2":
            for name in (
                "R2_ENDPOINT_URL",
                "R2_ACCESS_KEY_ID",
                "R2_SECRET_ACCESS_KEY",
                "R2_BUCKET_NAME",
            ):
                if not is_configured(getattr(self, name)):
                    errors.append(name)

        if self.TTS_PROVIDER.strip().lower() == "azure":
            for name in ("AZURE_SPEECH_KEY", "AZURE_SPEECH_REGION"):
                if not is_configured(getattr(self, name)):
                    errors.append(name)
        elif self.TTS_PROVIDER.strip().lower() == "google" and not is_configured(
            self.GOOGLE_APPLICATION_CREDENTIALS_PATH
        ):
            errors.append("GOOGLE_APPLICATION_CREDENTIALS_PATH")

        if self.DEBUG:
            errors.append("DEBUG must be false")

        origins = [
            origin.strip()
            for origin in self.API_ALLOWED_ORIGINS.split(",")
            if origin.strip()
        ]
        if not origins or "*" in origins:
            errors.append("API_ALLOWED_ORIGINS must list explicit HTTPS origins")
        elif any(
            urlsplit(origin).scheme != "https"
            or not urlsplit(origin).netloc
            or urlsplit(origin).path not in {"", "/"}
            for origin in origins
        ):
            errors.append("API_ALLOWED_ORIGINS must list explicit HTTPS origins")

        for name in ("SUPABASE_URL", "R2_ENDPOINT_URL"):
            value = getattr(self, name)
            if is_configured(value):
                parsed = urlsplit(value)
                if (
                    parsed.scheme != "https"
                    or not parsed.netloc
                    or parsed.path not in {"", "/"}
                ):
                    errors.append(f"{name} must be a valid HTTPS origin")

        return errors


# Create a single instance of the settings
settings = Settings()
