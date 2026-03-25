#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path


def _is_framework_root(path: Path) -> bool:
    return (
        (path / "base" / "sample_player.py").is_file()
        and (path / "base" / "sample_coach.py").is_file()
        and (path / "lib" / "player" / "player_agent.py").is_file()
    )


def find_pyrus2d_root(project_root: Path | None = None) -> Path:
    project_root = (project_root or Path(__file__).resolve().parent).resolve()
    candidates = []

    env_home = os.environ.get("PYRUS2D_HOME")
    if env_home:
        candidates.append(Path(env_home).expanduser())

    candidates.extend(
        [
            project_root / ".vendor" / "Pyrus2D",
            project_root / "Pyrus2D",
            project_root.parent / "Pyrus2D",
        ]
    )

    for candidate in candidates:
        candidate = candidate.resolve()
        if _is_framework_root(candidate):
            return candidate

    raise RuntimeError(
        "Pyrus2D framework not found. Set PYRUS2D_HOME or place the framework under "
        f"{project_root / '.vendor' / 'Pyrus2D'}."
    )


def bootstrap_pyrus2d(project_root: Path | None = None) -> Path:
    project_root = (project_root or Path(__file__).resolve().parent).resolve()
    framework_root = find_pyrus2d_root(project_root)

    if str(framework_root) not in sys.path:
        sys.path.insert(0, str(framework_root))
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    return framework_root
