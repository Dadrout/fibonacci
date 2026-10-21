import logging
import os
import subprocess
import json
from pathlib import Path

from app.core.config import settings
from app.domain.models import NarrationAudio
import requests

try:
    from google.cloud import texttospeech
except ImportError:  # pragma: no cover - dependency may be absent in tests
    texttospeech = None

try:
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request as GoogleAuthRequest
except ImportError:  # pragma: no cover - dependency may be absent in tests
    service_account = None
    GoogleAuthRequest = None

try:
    from gtts import gTTS
except ImportError:  # pragma: no cover - dependency may be absent in tests
    gTTS = None

logger = logging.getLogger(__name__)

VOICE_MAP = {
    ("en-US", "female"): settings.GOOGLE_TTS_VOICE_EN_FEMALE,
    ("en-US", "male"): settings.GOOGLE_TTS_VOICE_EN_MALE,
    ("ru-RU", "female"): settings.GOOGLE_TTS_VOICE_RU_FEMALE,
    ("ru-RU", "male"): settings.GOOGLE_TTS_VOICE_RU_MALE,
}


class GoogleCloudTTSProvider:
    provider_name = "google_cloud_tts"

    def _client(self):
        if texttospeech is None:
            raise RuntimeError("google-cloud-texttospeech is not installed.")

        credentials_path = (
            settings.GOOGLE_APPLICATION_CREDENTIALS_PATH
            or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        )
        if credentials_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
        return texttospeech.TextToSpeechClient()

    def _credentials_path(self) -> str | None:
        return (
            settings.GOOGLE_APPLICATION_CREDENTIALS_PATH
            or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        )

    def _voice_name(self, language: str, voice: str) -> str:
        normalized_voice = (voice or "female").strip().lower()
        return VOICE_MAP.get(
            (language, normalized_voice),
            VOICE_MAP.get((language, "female"), settings.GOOGLE_TTS_VOICE_EN_FEMALE),
        )

    def synthesize(
        self,
        *,
        text: str,
        language: str,
        voice: str,
        output_path: str,
    ) -> NarrationAudio:
        target_path = Path(output_path)
        voice_name = self._voice_name(language, voice)

        try:
            client = self._client()
            synthesis_input = texttospeech.SynthesisInput(text=text)
            voice_params = texttospeech.VoiceSelectionParams(
                language_code=language,
                name=voice_name,
            )
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3
            )

            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice_params,
                audio_config=audio_config,
            )
            target_path.write_bytes(response.audio_content)
            provider_name = self.provider_name
        except Exception as error:
            logger.warning(
                "Google Cloud TTS failed for language=%s voice=%s: %s. Falling back to gTTS.",
                language,
                voice_name,
                error,
            )
            provider_name = self._synthesize_with_gtts(
                text=text,
                language=language,
                target_path=target_path,
            )

        duration = self._probe_duration(target_path, text)
        logger.info(
            "TTS synthesized audio provider=%s language=%s voice=%s duration=%.2fs",
            provider_name,
            language,
            voice_name,
            duration,
        )
        return NarrationAudio(
            audio_path=str(target_path),
            duration_sec=duration,
            provider=provider_name,
            voice=voice,
            language=language,
        )

    def _synthesize_with_gtts(self, *, text: str, language: str, target_path: Path) -> str:
        if gTTS is None:
            raise RuntimeError("gTTS fallback is not installed.")

        language_code = "ru" if language.lower().startswith("ru") else "en"
        tts = gTTS(text=text, lang=language_code)
        tts.save(str(target_path))
        return "gtts_fallback"

    def _probe_duration(self, target_path: Path, text: str) -> float:
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
            return float(duration_str)
        except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
            return max(1.0, len(text.split()) / 2.5)

    def healthcheck(self) -> dict[str, str | bool]:
        credentials_path = self._credentials_path()
        status: dict[str, str | bool] = {
            "provider": self.provider_name,
            "configured": bool(texttospeech is not None and credentials_path),
            "fallback_provider": "gtts_fallback" if gTTS is not None else "unavailable",
        }
        if not credentials_path:
            status["authenticated"] = False
            status["error"] = "GOOGLE_APPLICATION_CREDENTIALS_PATH is not set."
            return status

        credential_file = Path(credentials_path)
        status["credentials_path_exists"] = credential_file.exists()
        if not credential_file.exists():
            status["authenticated"] = False
            status["error"] = "Configured credentials file does not exist."
            return status

        try:
            raw = json.loads(credential_file.read_text(encoding="utf-8"))
        except Exception as error:
            status["authenticated"] = False
            status["error"] = f"Failed to read credentials JSON: {error}"
            return status

        client_email = raw.get("client_email")
        private_key_id = raw.get("private_key_id")
        if client_email:
            status["service_account_email"] = client_email
        if private_key_id:
            status["private_key_id"] = private_key_id

        if client_email and private_key_id:
            try:
                certs_response = requests.get(
                    f"https://www.googleapis.com/robot/v1/metadata/x509/{client_email}",
                    timeout=20,
                )
                certs_response.raise_for_status()
                status["key_id_active"] = private_key_id in certs_response.text
                if not status["key_id_active"]:
                    status["authenticated"] = False
                    status["error"] = (
                        "The configured service account key is not active in Google public certs. "
                        "Create a new key for this service account."
                    )
                    return status
            except Exception as error:
                status["key_id_active"] = False
                status["authenticated"] = False
                status["error"] = f"Failed to validate key against Google certs: {error}"
                return status

        if service_account is None or GoogleAuthRequest is None:
            status["authenticated"] = False
            status["error"] = "google-auth is not installed."
            return status

        try:
            creds = service_account.Credentials.from_service_account_file(
                str(credential_file),
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
            creds.refresh(GoogleAuthRequest())
            status["authenticated"] = bool(creds.token)
        except Exception as error:
            status["authenticated"] = False
            status["error"] = str(error)
            return status

        if texttospeech is None:
            status["tts_api_enabled"] = False
            status["error"] = "google-cloud-texttospeech is not installed."
            return status

        try:
            client = self._client()
            client.list_voices(language_code="en-US")
            status["tts_api_enabled"] = True
        except Exception as error:
            status["tts_api_enabled"] = False
            status["error"] = str(error)
            return status

        return status


google_cloud_tts_provider = GoogleCloudTTSProvider()
