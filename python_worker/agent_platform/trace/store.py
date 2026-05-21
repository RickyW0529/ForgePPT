"""SQLite-backed trace store."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from agent_platform.orchestration.plans import AgentTrace


class TraceStore:
    """Async SQLite store for AgentTrace records."""

    def __init__(self, db_path: str = "data/traces.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    async def _ensure_table(self) -> None:
        if self._initialized:
            return
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS traces (
                    trace_id TEXT PRIMARY KEY,
                    workflow_id TEXT,
                    node_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    plan TEXT,
                    plan_failures TEXT,
                    step_results TEXT,
                    tokens TEXT,
                    latency_ms INTEGER,
                    created_at TEXT NOT NULL
                )
                """
            )
            await db.commit()
        self._initialized = True

    @staticmethod
    def _serialize(value: Any) -> str | None:
        if value is None:
            return None
        return json.dumps(value, default=str, ensure_ascii=False)

    async def save(self, trace: AgentTrace, workflow_id: str = "") -> None:
        """Persist an AgentTrace."""
        await self._ensure_table()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO traces (trace_id, workflow_id, node_id, status, plan,
                    plan_failures, step_results, tokens, latency_ms, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace.trace_id or str(trace.node_id) + "-" + datetime.now(timezone.utc).isoformat(),
                    workflow_id,
                    trace.node_id,
                    trace.status,
                    self._serialize(trace.plan.model_dump(mode="json") if trace.plan else None),
                    self._serialize([f.model_dump(mode="json") for f in trace.plan_failures]) if trace.plan_failures else None,
                    self._serialize([s.model_dump(mode="json") for s in trace.step_results]) if trace.step_results else None,
                    self._serialize(trace.tokens.model_dump(mode="json") if trace.tokens else None),
                    trace.latency_ms,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            await db.commit()

    async def list_traces(
        self,
        workflow_id: str | None = None,
        node_id: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """List traces with optional filtering."""
        await self._ensure_table()
        clauses = []
        params: list[Any] = []
        if workflow_id:
            clauses.append("workflow_id = ?")
            params.append(workflow_id)
        if node_id:
            clauses.append("node_id = ?")
            params.append(node_id)
        sql = "SELECT * FROM traces"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]
