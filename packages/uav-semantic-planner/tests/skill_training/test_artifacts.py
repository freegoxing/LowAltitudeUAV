import json

import pytest
from uav_semantic_planner.skill_training.artifacts import RunArtifacts
from uav_semantic_planner.skill_training.types import RunRecord, RunStatus


def test_run_artifacts_write_readable_run_metrics_and_skills(tmp_path):
    artifacts = RunArtifacts.create(tmp_path, "agent1", "run-001")
    record = RunRecord.new("run-001", "agent1", "qwen_vllm")

    artifacts.write_run(record)
    artifacts.append_metric({"step": 1, "score": 0.75})
    artifacts.write_skill("best", "# best skill\n")

    payload = json.loads((artifacts.run_dir / "run.json").read_text())
    metric = json.loads((artifacts.run_dir / "metrics.jsonl").read_text())
    assert payload["status"] == RunStatus.PENDING.value
    assert metric == {"step": 1, "score": 0.75}
    assert (artifacts.run_dir / "skills/best.md").read_text() == "# best skill\n"


@pytest.mark.parametrize("value", ["../agent", "agent/name", "", "."])
def test_run_artifacts_reject_unsafe_identifiers(tmp_path, value):
    with pytest.raises(ValueError, match="identifier"):
        RunArtifacts.create(tmp_path, value, "run-001")
