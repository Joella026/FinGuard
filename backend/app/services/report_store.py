from __future__ import annotations

import json
from pathlib import Path

from app.config import DATA_DIR
from app.models.contracts import Report


def manifest_path(report_id: str) -> Path:
    return DATA_DIR / "manifests" / f"{report_id}.json"


def save_report(report: Report) -> None:
    manifest_path(report.report_id).write_text(report.model_dump_json(indent=2), encoding="utf-8")


def load_report(report_id: str) -> Report:
    path = manifest_path(report_id)
    if not path.exists():
        raise FileNotFoundError(f"未找到报告 {report_id}")
    return Report.model_validate(json.loads(path.read_text(encoding="utf-8")))


def list_reports() -> list[Report]:
    return [Report.model_validate(json.loads(path.read_text(encoding="utf-8"))) for path in sorted((DATA_DIR / "manifests").glob("*.json"))]

