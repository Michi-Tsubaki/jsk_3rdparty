from __future__ import annotations

import os

from motion_instruction.models.errors import ProviderError
from motion_instruction.models.llm_schema import LLMParsedCommand
from motion_instruction.providers.base import ProviderConfig, sanitize_provider_exception


class OpenAIProvider:
    def __init__(self, config: ProviderConfig, system_prompt: str) -> None:
        self.config = config
        self.system_prompt = system_prompt
        self._client = None

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self.config.model

    def parse_motion(self, instruction: str) -> LLMParsedCommand:
        client = self._get_client()
        try:
            response = client.responses.parse(
                model=self.config.model,
                input=[
                    {"type": "message", "role": "system", "content": self.system_prompt},
                    {"type": "message", "role": "user", "content": instruction},
                ],
                text_format=LLMParsedCommand,
            )
        except Exception as exc:  # pragma: no cover - optional integration path
            raise ProviderError("PROVIDER_ERROR", sanitize_provider_exception(exc)) from exc
        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            raise ProviderError("PROVIDER_ERROR", "structured output was not parsed")
        return parsed

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
        except Exception as exc:  # pragma: no cover - optional dependency
            raise ProviderError("PROVIDER_ERROR", "openai package is not installed") from exc
        api_key = self.config.api_key or os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise ProviderError("PROVIDER_ERROR", "OPENAI_API_KEY is not set")
        kwargs = {
            "api_key": api_key,
            "timeout": self.config.timeout_s,
            "max_retries": self.config.max_retries,
        }
        if self.config.endpoint:
            kwargs["base_url"] = self.config.endpoint
        self._client = OpenAI(**kwargs)
        return self._client
