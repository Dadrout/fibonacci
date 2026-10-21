import asyncio
import logging
import subprocess
from pathlib import Path

from app.core.config import settings
from app.domain.models import NarrationAudio

try:
    import edge_tts
    from aiohttp import ClientConnectionError
except ImportError:  # pragma: no cover - dependency may be absent in tests
    edge_tts = None
    ClientConnectionError = ConnectionError

logger = logging.getLogger(__name__)

LANGUAGE_ALIASES = {
    "en": "en-US",
    "en-us": "en-US",
    "ru": "ru-RU",
    "ru-ru": "ru-RU",
}

VOICE_MAP = {
    ("en-US", "female"): settings.EDGE_TTS_VOICE_EN_FEMALE,
    ("en-US", "male"): settings.EDGE_TTS_VOICE_EN_MALE,
    ("ru-RU", "female"): settings.EDGE_TTS_VOICE_RU_FEMALE,
    ("ru-RU", "male"): settings.EDGE_TTS_VOICE_RU_MALE,
}


class EdgeTTSProvider:
    provider_name = "edge_tts"

    def _normalize_language(self, language: str) -> str:
        normalized = (language or "en-US").strip()
        return LANGUAGE_ALIASES.get(normalized.lower(), normalized)

    def _voice_name(
        self, language: str, voice: str, *, presentation: bool = False
    ) -> str:
        normalized_language = self._normalize_language(language)
        normalized_voice = (voice or "female").strip().lower()
        if presentation and normalized_voice == "female":
            presentation_voices = {
                "en-US": settings.EDGE_TTS_PRESENTATION_VOICE_EN_FEMALE,
                "ru-RU": settings.EDGE_TTS_PRESENTATION_VOICE_RU_FEMALE,
            }
            if normalized_language in presentation_voices:
                return presentation_voices[normalized_language]
        return VOICE_MAP.get(
            (normalized_language, normalized_voice),
            VOICE_MAP.get(
                (normalized_language, "female"), settings.EDGE_TTS_VOICE_EN_FEMALE
            ),
        )

    async def _save_audio(
        self,
        *,
        text: str,
        voice_name: str,
        output_path: Path,
        rate: str | None = None,
    ) -> None:
        if edge_tts is None:
            raise RuntimeError("edge-tts is not installed.")

        for attempt in range(3):
            try:
                options = {"text": text, "voice": voice_name}
                if rate is not None:
                    options["rate"] = rate
                communicator = edge_tts.Communicate(**options)
                await asyncio.wait_for(communicator.save(str(output_path)), timeout=90)
                return
            except (
                edge_tts.exceptions.NoAudioReceived,
                ClientConnectionError,
                TimeoutError,
            ):
                output_path.unlink(missing_ok=True)
                if attempt == 2:
                    raise
                logger.warning(
                    "Speech provider interrupted; retrying attempt=%s", attempt + 2
                )
                await asyncio.sleep(0.5 * (attempt + 1))

    def synthesize(
        self,
        *,
        text: str,
        language: str,
        voice: str,
        output_path: str,
        rate: str | None = None,
        presentation: bool = False,
    ) -> NarrationAudio:
        normalized_language = self._normalize_language(language)
        voice_name = self._voice_name(
            normalized_language, voice, presentation=presentation
        )
        target_path = Path(output_path)

        asyncio.run(
            self._save_audio(
                text=text,
                voice_name=voice_name,
                output_path=target_path,
                rate=rate,
            )
        )

        duration = self._probe_duration(target_path, text)
        logger.info(
            "TTS synthesized audio provider=%s language=%s voice=%s duration=%.2fs",
            self.provider_name,
            normalized_language,
            voice_name,
            duration,
        )
        return NarrationAudio(
            audio_path=str(target_path),
            duration_sec=duration,
            provider=self.provider_name,
            voice=voice,
            language=normalized_language,
        )

    def _probe_duration(self, target_path: Path, text: str) -> float:
        try:
            duration_str = (
                subprocess.check_output(
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
                )
                .decode("utf-8")
                .strip()
            )
            return float(duration_str)
        except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
            return max(1.0, len(text.split()) / 2.5)

    def healthcheck(self) -> dict[str, str | bool]:
        return {
            "provider": self.provider_name,
            "configured": edge_tts is not None,
            "default_en_female_voice": settings.EDGE_TTS_VOICE_EN_FEMALE,
            "default_en_male_voice": settings.EDGE_TTS_VOICE_EN_MALE,
            "default_ru_female_voice": settings.EDGE_TTS_VOICE_RU_FEMALE,
            "default_ru_male_voice": settings.EDGE_TTS_VOICE_RU_MALE,
        }


edge_tts_provider = EdgeTTSProvider()
