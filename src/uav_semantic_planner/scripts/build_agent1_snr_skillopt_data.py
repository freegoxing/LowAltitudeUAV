"""Build reproducible train/val/test labels from the SNR-only mock UAV graph."""

import argparse
import json
import random
import sys
import tempfile
from pathlib import Path

PROJECT_SRC = Path(__file__).resolve().parents[2]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from uav_semantic_planner.scripts.generate_mock_uav_data import (  # noqa: E402
    generate_mock_uav_data,
)


def graph_stats(graph: dict) -> dict[str, float | int]:
    edges = graph["edges"]
    if not edges:
        raise ValueError("mock graph contains no edges")
    # The graph stores each physical link twice; report physical disconnected links.
    disconn_edges = sum(edge["relation"] == "DISCONN" for edge in edges)
    return {
        "avg_snr": round(sum(edge["snr"] for edge in edges) / len(edges), 1),
        "disconn_count": disconn_edges // 2,
    }


def label(stats: dict[str, float | int]) -> str:
    if stats["disconn_count"] >= 5 or stats["avg_snr"] < 10:
        return "Level_1"
    if stats["disconn_count"] >= 2 or stats["avg_snr"] < 18:
        return "Level_2"
    return "Level_3"


def build_items(samples: int, seed: int) -> list[dict]:
    items: list[dict] = []
    with tempfile.TemporaryDirectory() as temporary_directory:
        temporary_path = Path(temporary_directory)
        for index in range(samples):
            random.seed(seed + index)
            graph_path = temporary_path / f"graph_{index:04d}.json"
            profile = index % 3
            if profile == 0:
                generation_kwargs = {"snr_offset": 8.0, "num_disconn_range": (0, 1)}
            elif profile == 1:
                generation_kwargs = {"snr_offset": 0.0, "num_disconn_range": (2, 4)}
            else:
                generation_kwargs = {"snr_offset": -8.0, "num_disconn_range": (5, 6)}
            generate_mock_uav_data(str(graph_path), **generation_kwargs)
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
            stats = graph_stats(graph)
            items.append(
                {
                    "id": f"snr_scenario_{index:04d}",
                    "input": {"graph_stats": stats},
                    "ground_truth": {"level": label(stats)},
                }
            )
    return items


def write_splits(items: list[dict], output_dir: Path, seed: int) -> None:
    if len(items) < 20:
        raise ValueError("at least 20 samples are required for train/val/test splits")
    shuffled = list(items)
    random.Random(seed).shuffle(shuffled)
    train_end = int(len(shuffled) * 0.7)
    val_end = train_end + int(len(shuffled) * 0.15)
    splits = {
        "train": shuffled[:train_end],
        "val": shuffled[train_end:val_end],
        "test": shuffled[val_end:],
    }
    for name, split_items in splits.items():
        path = output_dir / name / "items.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(split_items, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"{name}: {len(split_items)} items -> {path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_SRC.parent / "data" / "agent1_snr_split",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    write_splits(build_items(args.samples, args.seed), args.output_dir, args.seed)
