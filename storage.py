from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_processed_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def is_activity_processed(path: Path, activity_id: int | str) -> bool:
    activity_id_str = str(activity_id).strip()
    return activity_id_str in load_processed_ids(path)


def mark_activity_processed(path: Path, activity_id: int | str) -> None:
    activity_id_str = str(activity_id).strip()
    if is_activity_processed(path, activity_id_str):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{activity_id_str}\n")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(path)


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
