from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from motion_instruction.models.llm_schema import LLMParsedCommand


class MotionLLMProvider(Protocol):
    @property
    def provider_name(self) -> str:
        ...

    @property
    def model_name(self) -> str:
        ...

    def parse_motion(self, instruction: str) -> LLMParsedCommand:
        ...


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    model: str = ""
    deployment: str = ""
    endpoint: str = ""
    api_key: str = ""
    api_version: str = ""
    timeout_s: float = 30.0
    max_retries: int = 2


def sanitize_provider_exception(exc: BaseException) -> str:
    text = str(exc)
    for marker in ("api-key", "api_key", "Authorization", "Bearer"):
        if marker in text:
            return f"{exc.__class__.__name__}: provider error contains sensitive fields"
    return f"{exc.__class__.__name__}: {text}"
