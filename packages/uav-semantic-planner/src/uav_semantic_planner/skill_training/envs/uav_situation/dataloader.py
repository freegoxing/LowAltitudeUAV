"""Dataset loader for labelled UAV communication-situation examples."""

from __future__ import annotations

from typing import Any

from uav_semantic_planner.skill_training.datasets.base import SplitDataLoader


class UAVSituationDataLoader(SplitDataLoader):
    """Load the existing ``train/val/test/items.json`` UAV split."""

    def load_split_items(self, split_path: str) -> list[dict[str, Any]]:
        items = super().load_split_items(split_path)
        normalized: list[dict[str, Any]] = []
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError(f"UAV item {index} in {split_path} must be an object")
            if "input" not in item or "ground_truth" not in item:
                raise ValueError(
                    f"UAV item {index} in {split_path} requires input and ground_truth"
                )
            normalized.append(
                {
                    **item,
                    "id": str(item.get("id", index)),
                    "task_type": str(item.get("task_type", "snr_situation")),
                }
            )
        return normalized
