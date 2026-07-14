"""Filesystem contract for skill-training artifacts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .types import RunRecord

SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def _validate_identifier(value: str) -> None:
    if not SAFE_IDENTIFIER.fullmatch(value) or value in {".", ".."}:
        raise ValueError(f"unsafe artifact identifier: {value!r}")


@dataclass(frozen=True, slots=True)
class RunArtifacts:
    run_dir: Path

    @classmethod
    def create(cls, root: Path, agent: str, run_id: str) -> RunArtifacts:
        _validate_identifier(agent)
        _validate_identifier(run_id)
        run_dir = root / "skill-training" / agent / run_id
        (run_dir / "skills").mkdir(parents=True, exist_ok=True)
        (run_dir / "artifacts").mkdir(exist_ok=True)
        return cls(run_dir)

    def write_run(self, record: RunRecord) -> None:
        destination = self.run_dir / "run.json"
        temporary = destination.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(record.to_dict(), ensure_ascii=False, indent=2) + "\n"
        )
        temporary.replace(destination)

    def append_metric(self, metric: dict[str, object]) -> None:
        with (self.run_dir / "metrics.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(metric, ensure_ascii=False) + "\n")

    def write_skill(self, name: str, content: str) -> Path:
        _validate_identifier(name)
        destination = self.run_dir / "skills" / f"{name}.md"
        destination.write_text(content)
        return destination
