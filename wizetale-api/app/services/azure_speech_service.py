import html
import logging
from pathlib import Path

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)


class SpeechGenerationError(Exception):
    pass


VOICE_MAP = {
    ("en-US", "female"): "en-US-JennyNeural",
    ("en-US", "male"): "en-US-GuyNeural",
    ("ru-RU", "female"): "ru-RU-SvetlanaNeural",
    ("ru-RU", "male"): "ru-RU-DmitryNeural",
}

LANGUAGE_ALIASES = {
    "en": "en-US",
    "en-us": "en-US",
    "ru": "ru-RU",
    "ru-ru": "ru-RU",
}


class AzureSpeechService:
    def __init__(self):
        self.subscription_key = settings.AZURE_SPEECH_KEY
        self.region = settings.AZURE_SPEECH_REGION

    def _normalize_language(self, language: str) -> str:
        normalized = (language or "en-US").strip()
        return LANGUAGE_ALIASES.get(normalized.lower(), normalized)

    def _voice_name(self, language: str, voice: str) -> str:
        normalized_language = self._normalize_language(language)
        normalized_voice = (voice or "female").strip().lower()
        return VOICE_MAP.get(
            (normalized_language, normalized_voice),
            VOICE_MAP.get((normalized_language, "female"), "en-US-JennyNeural"),
        )

    def _endpoint(self) -> str:
        region = (self.region or "").strip()
        return f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"

    def synthesize_to_file(
        self,
        *,
        text: str,
        output_path: Path,
        voice: str = "female",
        language: str = "en-US",
    ) -> Path:
        if not self.subscription_key or not self.region:
            raise SpeechGenerationError("Azure Speech configuration is incomplete.")

        normalized_language = self._normalize_language(language)
        voice_name = self._voice_name(normalized_language, voice)
        escaped_text = html.escape(text)

        ssml = f"""
<speak version="1.0" xml:lang="{normalized_language}">
    <voice name="{voice_name}">
        {escaped_text}
    </voice>
</speak>
""".strip()

        response = requests.post(
            self._endpoint(),
            headers={
                "Ocp-Apim-Subscription-Key": self.subscription_key,
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "audio-24khz-160kbitrate-mono-mp3",
                "User-Agent": "wizetale-api",
            },
            data=ssml.encode("utf-8"),
            timeout=180,
        )
        response.raise_for_status()

        output_path.write_bytes(response.content)
        logger.info(
            "Azure Speech generated audio with voice '%s' for language '%s'.",
            voice_name,
            normalized_language,
        )
        return output_path


azure_speech_service = AzureSpeechService()
