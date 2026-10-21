import asyncio
from types import SimpleNamespace
from pathlib import Path
import pytest
from app.services.tts import edge_tts_service as speech

@pytest.mark.parametrize('failures', [1, 2, 3])
def test_edge_speech_retries_transient_empty_audio_with_a_fresh_request(monkeypatch, tmp_path, failures):
    class TemporaryNoAudio(Exception): pass
    calls=[]
    class Communicate:
        def __init__(self, **kwargs): calls.append(kwargs)
        async def save(self, target):
            if len(calls) <= failures:
                Path(target).write_bytes(b'partial')
                raise TemporaryNoAudio('empty audio')
            Path(target).write_bytes(b'complete audio')
    async def no_wait(*_args): pass
    monkeypatch.setattr(speech, 'edge_tts', SimpleNamespace(Communicate=Communicate, exceptions=SimpleNamespace(NoAudioReceived=TemporaryNoAudio)))
    monkeypatch.setattr(speech.asyncio, 'sleep', no_wait)
    target=tmp_path/'speech.mp3'
    if failures==3:
        with pytest.raises(TemporaryNoAudio):asyncio.run(speech.EdgeTTSProvider()._save_audio(text='Reference',voice_name='voice',output_path=target))
        assert len(calls)==3
        assert not target.exists()
    else:
        asyncio.run(speech.EdgeTTSProvider()._save_audio(text='Reference',voice_name='voice',output_path=target))
        assert len(calls)==failures+1
        assert target.read_bytes()==b'complete audio'
