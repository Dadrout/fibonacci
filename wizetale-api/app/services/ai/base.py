from typing import Protocol, TypeVar

from pydantic import BaseModel

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class TextGenerationProvider(Protocol):
    def generate_text(
        self,
        *,
        prompt: str,
        operation_name: str,
        temperature: float = 0.7,
        max_output_tokens: int = 1024,
        system_prompt: str | None = None,
    ) -> str: ...

    def generate_structured(
        self,
        *,
        prompt: str,
        operation_name: str,
        schema: type[SchemaT],
        temperature: float = 0.3,
        max_output_tokens: int = 2048,
        system_prompt: str | None = None,
    ) -> SchemaT: ...

    def healthcheck(self) -> dict[str, str | bool]: ...


class ImageGenerationProvider(Protocol):
    def generate_image(
        self,
        *,
        prompt: str,
        output_path: str,
        aspect_ratio: str = "16:9",
        style: str | None = None,
    ) -> str | None: ...

    def healthcheck(self) -> dict[str, str | bool]: ...
