from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite


class SQLiteDocumentStore:
    """Async SQLite document store for episodic memory items."""

    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS episodic_items (
        item_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        workflow_id TEXT,
        type TEXT NOT NULL,
        content TEXT NOT NULL,
        payload TEXT,
        modality TEXT,
        embedding TEXT,
        embedding_model TEXT,
        tags TEXT,
        importance REAL,
        confidence REAL,
        created_at TEXT,
        accessed_at TEXT,
        expires_at TEXT,
        source TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_episodic_user ON episodic_items(user_id);
    CREATE INDEX IF NOT EXISTS idx_episodic_type ON episodic_items(type);
    CREATE INDEX IF NOT EXISTS idx_episodic_workflow ON episodic_items(workflow_id);
    """

    def __init__(self, db_path: str = "data/memory.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    async def _ensure_table(self) -> None:
        if self._initialized:
            return
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(self._SCHEMA)
            await db.commit()
        self._initialized = True

    @staticmethod
    def _serialize(value: Any) -> Any:
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False)
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    @staticmethod
    def _deserialize(row: dict) -> dict:
        result = dict(row)
        for key in ("payload", "tags", "embedding"):
            if result.get(key) is not None:
                try:
                    result[key] = json.loads(result[key])
                except (json.JSONDecodeError, TypeError):
                    pass
        for key in ("created_at", "accessed_at", "expires_at"):
            if result.get(key) is not None:
                try:
                    result[key] = datetime.fromisoformat(result[key])
                except (ValueError, TypeError):
                    pass
        return result

    async def insert(self, doc: dict) -> str:
        await self._ensure_table()
        item_id = doc.get("item_id")
        if not item_id:
            raise ValueError("doc must contain 'item_id'")

        columns = [
            "item_id",
            "user_id",
            "workflow_id",
            "type",
            "content",
            "payload",
            "modality",
            "embedding",
            "embedding_model",
            "tags",
            "importance",
            "confidence",
            "created_at",
            "accessed_at",
            "expires_at",
            "source",
        ]
        values = [self._serialize(doc.get(c)) for c in columns]
        placeholders = ", ".join("?" for _ in columns)

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute(
                f"INSERT OR REPLACE INTO episodic_items ({', '.join(columns)}) VALUES ({placeholders})",
                values,
            )
            await db.commit()
        return str(item_id)

    async def get(self, item_id: str) -> dict | None:
        await self._ensure_table()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM episodic_items WHERE item_id = ?", (item_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    return None
                return self._deserialize(dict(row))

    async def query(
        self,
        where: dict | None = None,
        order_by: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        await self._ensure_table()
        where = where or {}
        clauses: list[str] = []
        params: list[Any] = []

        for key, value in where.items():
            clauses.append(f"{key} = ?")
            params.append(self._serialize(value))

        sql = "SELECT * FROM episodic_items"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        if order_by:
            # Basic sanitization: only allow column names and ASC/DESC
            ob = order_by.strip()
            ob_upper = ob.upper()
            if ob_upper.endswith(" DESC"):
                col = ob[:-5].strip()
                sql += f" ORDER BY {col} DESC"
            elif ob_upper.endswith(" ASC"):
                col = ob[:-4].strip()
                sql += f" ORDER BY {col} ASC"
            else:
                sql += f" ORDER BY {ob}"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, params) as cursor:
                rows = await cursor.fetchall()
                return [self._deserialize(dict(r)) for r in rows]

    async def delete(self, item_id: str) -> None:
        await self._ensure_table()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM episodic_items WHERE item_id = ?", (item_id,))
            await db.commit()

    async def count(self) -> int:
        await self._ensure_table()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM episodic_items") as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0
