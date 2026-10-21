"""Kazakh narration through ElevenLabs; credentials stay on the server."""
import subprocess
from pathlib import Path
from urllib.parse import quote

import requests

from app.core.config import settings
from app.domain.models import NarrationAudio


def probe_duration(path, text):
    try:
        return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', str(path)]).decode().strip())
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return max(1.0, len(text.split()) / 2.5)


class ElevenLabsTTSProvider:
    provider_name = 'elevenlabs'

    def synthesize(self, *, text, language, voice, output_path):
        if language != 'kk-KZ':
            raise RuntimeError('ElevenLabs narration is configured for Kazakh only.')
        voice_id = settings.ELEVENLABS_KK_MALE_VOICE_ID if voice == 'male' else settings.ELEVENLABS_KK_FEMALE_VOICE_ID
        if not settings.ELEVENLABS_API_KEY or not voice_id:
            raise RuntimeError('Kazakh narration configuration is incomplete.')
        if len(text) > 5000:
            raise RuntimeError('Kazakh narration exceeds the speech model text limit.')
        response = requests.post(
            f'https://api.elevenlabs.io/v1/text-to-speech/{quote(voice_id, safe="")}',
            params={'output_format': 'mp3_44100_128'},
            headers={'xi-api-key': settings.ELEVENLABS_API_KEY, 'Content-Type': 'application/json', 'Accept': 'audio/mpeg'},
            json={'text': text, 'model_id': 'eleven_v3', 'language_code': 'kk'},
            timeout=180,
        )
        response.raise_for_status()
        if not response.content or 'audio' not in response.headers.get('Content-Type', ''):
            raise RuntimeError('Speech provider returned an invalid audio response.')
        path = Path(output_path)
        path.write_bytes(response.content)
        return NarrationAudio(audio_path=str(path), duration_sec=probe_duration(path, text), provider=self.provider_name, voice=voice, language=language)

    def healthcheck(self):
        return {'provider': self.provider_name, 'configured': bool(settings.ELEVENLABS_API_KEY and settings.ELEVENLABS_KK_FEMALE_VOICE_ID and settings.ELEVENLABS_KK_MALE_VOICE_ID)}


elevenlabs_tts_provider = ElevenLabsTTSProvider()
