import importlib.util
from pathlib import Path

import pytest

from app.domain.models import StoryDraftRequest
from app.core.config import settings


def test_story_contract_accepts_kazakh():
    assert StoryDraftRequest(subject='history', topic='Silk Road', language='kk-KZ').language == 'kk-KZ'


def test_kazakh_routes_to_elevenlabs_without_changing_other_languages(monkeypatch):
    assert importlib.util.find_spec('app.services.tts.elevenlabs_tts_service'), 'ElevenLabs provider is missing'
    from app.services.tts import provider_factory as factory
    from app.services.tts.elevenlabs_tts_service import elevenlabs_tts_provider
    provider = factory.get_tts_provider()
    calls = []
    monkeypatch.setattr(elevenlabs_tts_provider, 'synthesize', lambda **kwargs: calls.append(kwargs) or 'kazakh-audio')
    assert provider.synthesize(text='Сәлем', language='kk-KZ', voice='female', output_path='/tmp/voice.mp3') == 'kazakh-audio'
    assert calls[0]['language'] == 'kk-KZ'
    monkeypatch.setattr(factory.edge_tts_provider, 'synthesize', lambda **kwargs: 'english-audio')
    assert provider.synthesize(text='Hello', language='en-US', voice='female', output_path='/tmp/voice.mp3') == 'english-audio'


def test_missing_elevenlabs_configuration_fails_before_network(monkeypatch, tmp_path):
    assert importlib.util.find_spec('app.services.tts.elevenlabs_tts_service'), 'ElevenLabs provider is missing'
    from app.services.tts.elevenlabs_tts_service import ElevenLabsTTSProvider
    monkeypatch.setattr(settings, 'ELEVENLABS_API_KEY', None)
    with pytest.raises(RuntimeError, match='configuration'):
        ElevenLabsTTSProvider().synthesize(text='Сәлем', language='kk-KZ', voice='male', output_path=str(tmp_path/'voice.mp3'))
    assert not (tmp_path/'voice.mp3').exists()


def test_elevenlabs_mp3_and_kazakh_language_code(monkeypatch, tmp_path):
    assert importlib.util.find_spec('app.services.tts.elevenlabs_tts_service'), 'ElevenLabs provider is missing'
    from app.services.tts import elevenlabs_tts_service as speech
    monkeypatch.setattr(settings, 'ELEVENLABS_API_KEY', 'test-key')
    monkeypatch.setattr(settings, 'ELEVENLABS_KK_FEMALE_VOICE_ID', 'test-voice')
    calls = []
    class Reply:
        headers = {'Content-Type':'audio/mpeg'}
        content = b'ID3testaudio'
        def raise_for_status(self): pass
    def post(url, **kwargs):
        calls.append((url,kwargs))
        return Reply()
    monkeypatch.setattr(speech.requests, 'post', post)
    monkeypatch.setattr(speech, 'probe_duration', lambda *args: 2.0)
    path = tmp_path/'voice.mp3'
    result = speech.ElevenLabsTTSProvider().synthesize(text='Сәлем', language='kk-KZ', voice='female', output_path=str(path))
    assert path.read_bytes() == b'ID3testaudio'
    assert calls[0][1]['json']['language_code'] == 'kk'
    assert calls[0][1]['json']['model_id'] == 'eleven_v3'
    assert result.language == 'kk-KZ'
    assert result.provider == 'elevenlabs'
