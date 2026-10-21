import logging
import subprocess
from pathlib import Path

from app.domain.models import NarrationAudio
from app.services.azure_speech_service import (
    SpeechGenerationError,
    azure_speech_service,
)

logger = logging.getLogger(__name__)


class AzureTTSProvider:
    provider_name = "azure_speech"

    def synthesize(
        self,
        *,
        text: str,
        language: str,
        voice: str,
        output_path: str,
    ) -> NarrationAudio:
        target_path = Path(output_path)
        try:
            azure_speech_service.synthesize_to_file(
                text=text,
                output_path=target_path,
                voice=voice,
                language=language,
            )
        except SpeechGenerationError:
            raise

        try:
            duration_str = subprocess.check_output(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(target_path),
                ]
            ).decode("utf-8").strip()
            duration = float(duration_str)
        except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
            duration = max(1.0, len(text.split()) / 2.5)

        logger.info(
            "TTS synthesized audio provider=%s language=%s voice=%s duration=%.2fs",
            self.provider_name,
            language,
            voice,
            duration,
        )
        return NarrationAudio(
            audio_path=str(target_path),
            duration_sec=duration,
            provider=self.provider_name,
            voice=voice,
            language=language,
        )

    def healthcheck(self) -> dict[str, str | bool]:
        return {
            "provider": self.provider_name,
            "configured": bool(
                azure_speech_service.subscription_key and azure_speech_service.region
            ),
        }


azure_tts_provider = AzureTTSProvider()
