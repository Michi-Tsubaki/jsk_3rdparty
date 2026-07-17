from __future__ import annotations

import os

from motion_instruction.models.errors import ProviderError
from motion_instruction.models.llm_schema import LLMParsedCommand
from motion_instruction.providers.base import ProviderConfig, sanitize_provider_exception


class AzureOpenAIProvider:
    def __init__(self, config: ProviderConfig, system_prompt: str) -> None:
        self.config = config
        self.system_prompt = system_prompt
        self._client = None

    @property
    def provider_name(self) -> str:
        return "azure_openai"

    @property
    def model_name(self) -> str:
        return self.config.deployment or self.config.model

    def parse_motion(self, instruction: str) -> LLMParsedCommand:
        client = self._get_client()
        try:
            response = client.responses.parse(
                model=self.model_name,
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
            from openai import AzureOpenAI, OpenAI
        except Exception as exc:  # pragma: no cover - optional dependency
            raise ProviderError("PROVIDER_ERROR", "openai package is not installed") from exc
        endpoint = self.config.endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT", "")
        api_key = self.config.api_key or os.environ.get("AZURE_OPENAI_API_KEY", "")
        if not endpoint:
            raise ProviderError("PROVIDER_ERROR", "AZURE_OPENAI_ENDPOINT is not set")
        if not api_key:
            raise ProviderError("PROVIDER_ERROR", "AZURE_OPENAI_API_KEY is not set")
        if self.config.api_version:
            self._client = AzureOpenAI(
                azure_endpoint=endpoint,
                api_key=api_key,
                api_version=self.config.api_version,
                timeout=self.config.timeout_s,
                max_retries=self.config.max_retries,
            )
            return self._client

        self._client = OpenAI(
            base_url=_normalize_azure_v1_base_url(endpoint),
            api_key=api_key,
            timeout=self.config.timeout_s,
            max_retries=self.config.max_retries,
        )
        return self._client


def _normalize_azure_v1_base_url(endpoint: str) -> str:
    endpoint = endpoint.rstrip("/")
    if endpoint.endswith("/openai/v1"):
        return f"{endpoint}/"
    return f"{endpoint}/openai/v1/"
