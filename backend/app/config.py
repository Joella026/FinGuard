from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

DATA_DIR = Path(os.getenv("FINGUARD_DATA_DIR", ROOT_DIR / "data")).resolve()
RUNS_DIR = Path(os.getenv("FINGUARD_RUNS_DIR", ROOT_DIR / "runs")).resolve()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.5")


def ensure_directories() -> None:
    for directory in (
        DATA_DIR / "raw_reports",
        DATA_DIR / "parsed_reports",
        DATA_DIR / "manifests",
        DATA_DIR / "extractions",
        DATA_DIR / "benchmark",
        RUNS_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)

