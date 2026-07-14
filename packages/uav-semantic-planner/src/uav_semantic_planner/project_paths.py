"""Repository path discovery for commands launched from any working directory."""

from __future__ import annotations

from pathlib import Path


def find_project_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        marker = candidate / "pyproject.toml"
        if marker.is_file() and "[tool.uv.workspace]" in marker.read_text():
            return candidate
    raise RuntimeError(f"could not find uv workspace root from {current}")
