"""Validated backend configuration without resolved secrets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class BackendConfig:
    provider: str
    model: str
    base_url: str | None = None
    api_key_env: str | None = None
    timeout_seconds: float = 120.0

    @classmethod
    def from_mapping(cls, values: dict[str, Any]) -> BackendConfig:
        provider = str(values.get("provider", ""))
        if provider not in {"openai", "azure_openai", "qwen_vllm"}:
            raise ValueError(f"unsupported backend provider: {provider!r}")
        model = str(values.get("model", ""))
        if not model:
            raise ValueError("backend model is required")
        base_url = values.get("base_url")
        if provider == "qwen_vllm" and not base_url:
            raise ValueError("qwen_vllm backend base_url is required")
        return cls(
            provider=provider,
            model=model,
            base_url=str(base_url) if base_url else None,
            api_key_env=(
                str(values["api_key_env"]) if values.get("api_key_env") else None
            ),
            timeout_seconds=float(values.get("timeout_seconds", 120)),
        )
