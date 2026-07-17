from __future__ import annotations

import textwrap

import pytest

from motion_instruction.models.errors import ProviderError
from motion_instruction.providers.factory import load_provider_config


def test_loads_azure_openai_config_from_direct_values(tmp_path):
    config_path = tmp_path / "azure_openai.yaml"
    config_path.write_text(
        textwrap.dedent(
            """
            provider: azure_openai
            deployment: motion-parser-gpt-5-3
            endpoint: https://example.services.ai.azure.com/api/projects/robot-inference
            api_key: test-key
            timeout_s: 12.5
            max_retries: 3
            """
        ),
        encoding="utf-8",
    )

    config = load_provider_config("azure_openai", str(config_path))

    assert config.provider == "azure_openai"
    assert config.deployment == "motion-parser-gpt-5-3"
    assert config.endpoint == "https://example.services.ai.azure.com/api/projects/robot-inference"
    assert config.api_key == "test-key"
    assert config.timeout_s == 12.5
    assert config.max_retries == 3


def test_loads_azure_openai_config_from_env_names(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_AZURE_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("TEST_AZURE_API_KEY", "from-env")
    config_path = tmp_path / "azure_openai.yaml"
    config_path.write_text(
        textwrap.dedent(
            """
            provider: azure_openai
            deployment: motion-parser
            endpoint_env: TEST_AZURE_ENDPOINT
            api_key_env: TEST_AZURE_API_KEY
            """
        ),
        encoding="utf-8",
    )

    config = load_provider_config("azure_openai", str(config_path))

    assert config.endpoint == "https://example.openai.azure.com"
    assert config.api_key == "from-env"


def test_accepts_literal_values_in_env_fields_for_local_configs(tmp_path):
    config_path = tmp_path / "azure_openai.yaml"
    config_path.write_text(
        textwrap.dedent(
            """
            provider: azure_openai
            deployment: motion-parser
            endpoint_env: https://example.services.ai.azure.com/api/projects/robot-inference
            api_key_env: 1-local-test-key
            """
        ),
        encoding="utf-8",
    )

    config = load_provider_config("azure_openai", str(config_path))

    assert config.endpoint == "https://example.services.ai.azure.com/api/projects/robot-inference"
    assert config.api_key == "1-local-test-key"


def test_rejects_missing_deployment_or_model(tmp_path):
    config_path = tmp_path / "azure_openai.yaml"
    config_path.write_text("provider: azure_openai\n", encoding="utf-8")

    with pytest.raises(ProviderError, match="deployment or model"):
        load_provider_config("azure_openai", str(config_path))
