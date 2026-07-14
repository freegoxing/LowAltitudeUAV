import pytest
from uav_semantic_planner.skill_training.backends.config import BackendConfig


def test_qwen_vllm_requires_openai_compatible_base_url():
    config = BackendConfig.from_mapping(
        {
            "provider": "qwen_vllm",
            "base_url": "http://localhost:8000/v1",
            "model": "Qwen/Qwen3",
            "timeout_seconds": 120,
        }
    )

    assert config.provider == "qwen_vllm"
    assert config.base_url == "http://localhost:8000/v1"
    assert config.timeout_seconds == 120


def test_unknown_backend_is_rejected():
    with pytest.raises(ValueError, match="provider"):
        BackendConfig.from_mapping({"provider": "other", "model": "x"})
