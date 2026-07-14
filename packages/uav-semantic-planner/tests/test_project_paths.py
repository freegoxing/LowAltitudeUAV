import pytest
from uav_semantic_planner.project_paths import find_project_root


def test_find_project_root_walks_up_from_nested_directory(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.uv.workspace]\n")
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)

    assert find_project_root(nested) == tmp_path


def test_find_project_root_fails_when_workspace_marker_is_missing(tmp_path):
    with pytest.raises(RuntimeError, match="workspace root"):
        find_project_root(tmp_path)
