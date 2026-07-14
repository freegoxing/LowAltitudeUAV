"""Serializable types shared by skill-training runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class TrainingStage(StrEnum):
    IDLE = "idle"
    ROLLOUT = "rollout"
    REFLECT = "reflect"
    AGGREGATE = "aggregate"
    SELECT = "select"
    UPDATE = "update"
    GATE = "gate"


@dataclass(slots=True)
class RunRecord:
    run_id: str
    agent: str
    backend: str
    status: RunStatus
    stage: TrainingStage
    started_at: str
    finished_at: str | None = None
    error: str | None = None

    @classmethod
    def new(cls, run_id: str, agent: str, backend: str) -> RunRecord:
        return cls(
            run_id=run_id,
            agent=agent,
            backend=backend,
            status=RunStatus.PENDING,
            stage=TrainingStage.IDLE,
            started_at=datetime.now(UTC).isoformat(),
        )

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["status"] = self.status.value
        data["stage"] = self.stage.value
        return data
