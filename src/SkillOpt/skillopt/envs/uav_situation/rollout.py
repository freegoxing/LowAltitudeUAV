"""Rollouts and deterministic scoring for UAV communication situations."""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from skillopt.model import chat_target

_LEVELS = ("Level_1", "Level_2", "Level_3")


def _user_prompt(item: dict[str, Any]) -> str:
    raw_input = item["input"]
    graph_stats = raw_input.get("graph_stats", raw_input)
    return json.dumps({"graph_stats": graph_stats}, ensure_ascii=False, indent=2)


def _parse_prediction(response: str) -> dict[str, Any]:
    match = re.search(r"```json\s*(\{.*?\})\s*```", response, re.DOTALL)
    payload = match.group(1) if match else response
    prediction = json.loads(payload)
    if not isinstance(prediction, dict) or prediction.get("level") not in _LEVELS:
        raise ValueError("response must contain level: Level_1, Level_2, or Level_3")
    return prediction


def _score(prediction: dict[str, Any], item: dict[str, Any]) -> tuple[int, float]:
    expected = item["ground_truth"]["level"]
    actual = prediction["level"]
    hard = int(actual == expected)
    distance = abs(_LEVELS.index(actual) - _LEVELS.index(expected))
    return hard, 1.0 - distance / (len(_LEVELS) - 1)


def _rollout_one(item: dict[str, Any], skill_content: str, max_completion_tokens: int) -> dict[str, Any]:
    response, usage = chat_target(
        system=skill_content,
        user=_user_prompt(item),
        max_completion_tokens=max_completion_tokens,
    )
    result: dict[str, Any] = {
        "id": str(item["id"]),
        "task_type": item["task_type"],
        "input": item["input"],
        "ground_truth": item["ground_truth"],
        "response": response or "",
        "prediction": {},
        "hard": 0,
        "soft": 0.0,
        "error": "",
        "usage": usage,
    }
    try:
        prediction = _parse_prediction(response or "")
        hard, soft = _score(prediction, item)
        result.update(prediction=prediction, hard=hard, soft=soft)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def run_batch(
    *,
    items: list[dict[str, Any]],
    skill_content: str,
    out_root: str,
    workers: int = 4,
    max_completion_tokens: int = 4096,
) -> list[dict[str, Any]]:
    """Execute and persist one SkillOpt rollout batch."""
    Path(out_root).mkdir(parents=True, exist_ok=True)
    worker_count = max(1, min(int(workers), len(items))) if items else 1
    if worker_count == 1:
        results = [_rollout_one(item, skill_content, max_completion_tokens) for item in items]
    else:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            results = list(
                executor.map(
                    lambda item: _rollout_one(item, skill_content, max_completion_tokens),
                    items,
                )
            )
    Path(out_root, "rollouts.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return results
