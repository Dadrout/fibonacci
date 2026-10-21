from typing import Protocol

from app.domain.models import LanguageCode, NarrationAudio, VoiceCode


class TTSProvider(Protocol):
    def synthesize(
        self,
        *,
        text: str,
        language: LanguageCode,
        voice: VoiceCode,
        output_path: str,
    ) -> NarrationAudio: ...

    def healthcheck(self) -> dict[str, str | bool]: ...
