from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

from motion_instruction.models.errors import ProviderError
from motion_instruction.providers.azure_openai_provider import AzureOpenAIProvider
from motion_instruction.providers.base import MotionLLMProvider, ProviderConfig
from motion_instruction.providers.openai_provider import OpenAIProvider


_ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def build_provider(
    provider_name: str,
    api_config_path: str,
    system_prompt: str,
) -> MotionLLMProvider:
    config = load_provider_config(provider_name, api_config_path)
    if config.provider == "azure_openai":
        return AzureOpenAIProvider(config, system_prompt)
    if config.provider == "openai":
        return OpenAIProvider(config, system_prompt)
    raise ProviderError("PROVIDER_ERROR", f"unsupported provider: {config.provider}")


def load_provider_config(provider_name: str, api_config_path: str) -> ProviderConfig:
    path = _resolve_config_path(provider_name, api_config_path)
    data = _load_yaml(path) if path is not None else {}
    provider = str(provider_name or data.get("provider") or "azure_openai")
    endpoint = _resolve_config_value(data, "endpoint", "endpoint_env")
    if not endpoint:
        endpoint = _resolve_config_value(data, "base_url", "base_url_env")
    config = ProviderConfig(
        provider=provider,
        model=str(data.get("model") or ""),
        deployment=str(data.get("deployment") or ""),
        endpoint=endpoint,
        api_key=_resolve_config_value(data, "api_key", "api_key_env"),
        api_version=str(data.get("api_version") or ""),
        timeout_s=float(data.get("timeout_s", 30.0)),
        max_retries=int(data.get("max_retries", 2)),
    )
    if config.provider in ("azure_openai", "openai") and not (config.deployment or config.model):
        raise ProviderError(
            "PROVIDER_ERROR",
            f"{config.provider} config must set deployment or model",
        )
    return config


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream) or {}
    if not isinstance(data, dict):
        raise ProviderError("PROVIDER_ERROR", f"provider config is not a mapping: {path}")
    return data


def _resolve_config_value(data: dict[str, Any], value_key: str, env_key: str) -> str:
    direct_value = str(data.get(value_key) or "")
    if direct_value:
        return direct_value

    env_name_or_value = str(data.get(env_key) or "")
    if not env_name_or_value:
        return ""

    env_value = os.environ.get(env_name_or_value)
    if env_value:
        return env_value

    if value_key in ("endpoint", "base_url") and env_name_or_value.startswith(("http://", "https://")):
        return env_name_or_value
    if value_key == "api_key" and not _ENV_NAME_RE.match(env_name_or_value):
        return env_name_or_value
    return ""


def _resolve_config_path(provider_name: str, api_config_path: str) -> Path | None:
    for path in _config_path_candidates(provider_name, api_config_path):
        if path.is_file():
            return path
    if api_config_path:
        raise ProviderError("PROVIDER_ERROR", f"provider config file was not found: {api_config_path}")
    return None


def _config_path_candidates(provider_name: str, api_config_path: str) -> list[Path]:
    if api_config_path:
        requested = Path(api_config_path).expanduser()
        if requested.is_absolute():
            return [requested]
        return [Path.cwd() / requested, _package_root() / requested, *_share_path_candidates(requested)]

    candidates: list[Path] = []
    env_path = os.environ.get("MOTION_INSTRUCTION_API_CONFIG", "")
    if env_path:
        candidates.append(Path(env_path).expanduser())

    provider = provider_name or "azure_openai"
    names = (
        f"{provider}.yaml",
        f"{provider}.yaml.example",
    )
    for root in _default_config_roots():
        candidates.extend(root / name for name in names)
    return candidates


def _default_config_roots() -> list[Path]:
    relative = Path("cfg/api")
    return [
        _package_root() / relative,
        Path.cwd() / "motion_instruction" / relative,
        *_share_path_candidates(relative),
    ]


def _share_path_candidates(relative: Path) -> list[Path]:
    try:
        from ament_index_python.packages import get_package_share_directory
    except Exception:
        return []
    try:
        return [Path(get_package_share_directory("motion_instruction")) / relative]
    except Exception:
        return []


def _package_root() -> Path:
    return Path(__file__).resolve().parents[2]
