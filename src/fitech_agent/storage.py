from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from .models import DailyMarketBrief, ForecastOutcome, MarketImpactAssessment
from .utils import ensure_directory, to_json, utc_now_iso


class SQLiteStorage:
    def __init__(self, database_path: str) -> None:
        self.database_path = Path(database_path)
        ensure_directory(self.database_path.parent)

    def connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scheduled_for TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    degraded INTEGER NOT NULL DEFAULT 0,
                    degraded_reasons TEXT,
                    config_json TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS stage_payloads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    stage TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reports (
                    run_id INTEGER PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    markdown_path TEXT NOT NULL,
                    pdf_path TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS outcomes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    assessment_id TEXT NOT NULL,
                    asset TEXT NOT NULL,
                    evaluation_window TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def create_run(self, scheduled_for: str, config_json: str) -> int:
        started_at = utc_now_iso()
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO runs (scheduled_for, status, started_at, config_json)
                VALUES (?, ?, ?, ?)
                """,
                (scheduled_for, "running", started_at, config_json),
            )
            return int(cursor.lastrowid)

    def finalize_run(
        self, run_id: int, status: str, degraded: bool, degraded_reasons: list[str]
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE runs
                SET status = ?, finished_at = ?, degraded = ?, degraded_reasons = ?
                WHERE id = ?
                """,
                (status, utc_now_iso(), int(degraded), to_json(degraded_reasons), run_id),
            )

    def record_stage(
        self,
        run_id: int,
        stage: str,
        entity_type: str,
        payloads: Iterable[object],
        *,
        entity_ids: Iterable[str] | None = None,
    ) -> None:
        ids = list(entity_ids or [])
        rows = []
        created_at = utc_now_iso()
        for index, payload in enumerate(payloads):
            entity_id = ids[index] if index < len(ids) else None
            rows.append((run_id, stage, entity_type, entity_id, to_json(payload), created_at))
        if not rows:
            return
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO stage_payloads (
                    run_id, stage, entity_type, entity_id, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def save_report(
        self,
        run_id: int,
        report: DailyMarketBrief,
        markdown_path: str,
        pdf_path: str | None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO reports (
                    run_id, payload_json, markdown_path, pdf_path, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, to_json(report), markdown_path, pdf_path, utc_now_iso()),
            )

    def load_assessments(self, run_id: int) -> list[MarketImpactAssessment]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT stage, payload_json
                FROM stage_payloads
                WHERE run_id = ? AND entity_type = 'market_impact_assessment'
                ORDER BY id ASC
                """,
                (run_id,),
            ).fetchall()
        import json

        if not rows:
            return []

        preferred_stage = 'audit_evidence'
        stages = [row[0] for row in rows]
        selected_stage = preferred_stage if preferred_stage in stages else stages[-1]
        return [
            MarketImpactAssessment.from_dict(json.loads(payload_json))
            for stage, payload_json in rows
            if stage == selected_stage
        ]

    def record_outcomes(self, run_id: int, outcomes: list[ForecastOutcome]) -> None:
        if not outcomes:
            return
        created_at = utc_now_iso()
        rows = [
            (
                run_id,
                item.assessment_id,
                item.asset,
                item.evaluation_window,
                to_json(item),
                created_at,
            )
            for item in outcomes
        ]
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO outcomes (
                    run_id, assessment_id, asset, evaluation_window, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
