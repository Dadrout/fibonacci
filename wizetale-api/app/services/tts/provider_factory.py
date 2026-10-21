from app.core.config import settings
from app.services.tts.azure_tts_service import azure_tts_provider
from app.services.tts.edge_tts_service import edge_tts_provider
from app.services.tts.google_tts_service import google_cloud_tts_provider


def _default_tts_provider():
    if settings.TTS_PROVIDER == "edge":
        return edge_tts_provider
    if settings.TTS_PROVIDER == "google":
        return google_cloud_tts_provider
    if settings.TTS_PROVIDER == "azure":
        return azure_tts_provider
    return edge_tts_provider


from app.services.tts.elevenlabs_tts_service import elevenlabs_tts_provider


class LanguageRoutingTTSProvider:
    def __init__(self, default_provider):
        self.default_provider = default_provider

    def synthesize(self, **kwargs):
        provider = (
            elevenlabs_tts_provider
            if kwargs.get("language") == "kk-KZ"
            else self.default_provider
        )
        if getattr(provider, "provider_name", None) != "edge_tts":
            # Presentation pacing and voice selection are Edge-specific options.
            kwargs.pop("rate", None)
            kwargs.pop("presentation", None)
        return provider.synthesize(**kwargs)

    def healthcheck(self):
        return {
            **self.default_provider.healthcheck(),
            "kazakh_configured": elevenlabs_tts_provider.healthcheck()["configured"],
        }


def get_tts_provider():
    return LanguageRoutingTTSProvider(_default_tts_provider())
