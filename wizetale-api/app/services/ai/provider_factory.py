from app.core.config import settings
from app.services.ai.cloudflare_image_service import cloudflare_image_service
from app.services.ai.fal_image_service import fal_image_service
from app.services.ai.gemini_image_service import gemini_image_service
from app.services.ai.gemini_text_service import gemini_text_service


def get_text_provider():
    provider = settings.AI_PROVIDER.lower()
    if provider == "gemini":
        return gemini_text_service
    raise RuntimeError(f"Unsupported text AI provider: {provider}")


def get_image_provider():
    provider = settings.IMAGE_PROVIDER.lower()
    if provider == "gemini":
        return gemini_image_service
    if provider == "fal":
        return fal_image_service
    if provider == "cloudflare":
        return cloudflare_image_service
    raise RuntimeError(f"Unsupported image AI provider: {provider}")
