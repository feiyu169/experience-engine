"""经验沉淀引擎 — 反馈存储 (SQLite)"""

import json
import sqlite3
import re
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager
from typing import List, Dict
import logging

from .models import Result
from .utils import _get_profile_db_path

logger = logging.getLogger(__name__)

SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_slug TEXT NOT NULL,
    page_type TEXT NOT NULL,
    action TEXT NOT NULL,
    outcome TEXT,
    outcome_note TEXT,
    session_id TEXT,
    profile TEXT DEFAULT 'default',
    created_at TEXT NOT NULL,
    updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_feedback_slug ON feedback(page_slug);
CREATE INDEX IF NOT EXISTS idx_feedback_outcome ON feedback(outcome);
CREATE INDEX IF NOT EXISTS idx_feedback_created ON feedback(created_at);

CREATE TABLE IF NOT EXISTS task_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    task_type TEXT NOT NULL,
    task_domain TEXT,
    outcome TEXT NOT NULL,
    duration_turns INTEGER,
    error_count INTEGER,
    retry_count INTEGER,
    methodology_used TEXT,
    notes TEXT,
    profile TEXT DEFAULT 'default',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_task_type ON task_outcomes(task_type);
CREATE INDEX IF NOT EXISTS idx_task_outcome ON task_outcomes(outcome);
CREATE INDEX IF NOT EXISTS idx_task_created ON task_outcomes(created_at);

CREATE TABLE IF NOT EXISTS write_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation TEXT NOT NULL,
    target_slug TEXT,
    payload_json TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_writelog_status ON write_log(status);
"""


class FeedbackStore:
    """反馈存储"""

    def __init__(self, db_path: Path = None, profile: str = "default"):
        self._db_path = db_path or _get_profile_db_path(profile)
        self._profile = profile
        self._ensure_db()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _ensure_db(self):
        with self._conn() as conn:
            conn.executescript(SCHEMA_V1)

    def record_feedback(self, page_slug: str, page_type: str, action: str,
                        outcome: str = None, outcome_note: str = None,
                        session_id: str = None) -> Result:
        try:
            with self._conn() as conn:
                conn.execute(
                    """INSERT INTO feedback
                       (page_slug, page_type, action, outcome, outcome_note,
                        session_id, profile, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (page_slug, page_type, action, outcome, outcome_note,
                     session_id, self._profile, datetime.now().isoformat())
                )
            return Result(success=True)
        except Exception as e:
            logger.warning("record_feedback failed: %s", e)
            return Result(success=False, error=str(e))

    def get_stats(self, page_slug: str) -> Result:
        try:
            with self._conn() as conn:
                cursor = conn.execute(
                    """SELECT action, outcome, COUNT(*)
                       FROM feedback WHERE page_slug = ?
                       GROUP BY action, outcome""",
                    (page_slug,)
                )
                stats = {f"{r[0]}_{r[1] or 'unknown'}": r[2] for r in cursor}
            return Result(success=True, data=stats)
        except Exception as e:
            logger.warning("get_stats failed: %s", e)
            return Result(success=False, error=str(e))

    def record_write_log(self, operation: str, target_slug: str, payload: Dict) -> Result:
        try:
            with self._conn() as conn:
                conn.execute(
                    """INSERT INTO write_log
                       (operation, target_slug, payload_json, status, created_at)
                       VALUES (?, ?, ?, 'pending', ?)""",
                    (operation, target_slug, json.dumps(payload), datetime.now().isoformat())
                )
            return Result(success=True)
        except Exception as e:
            logger.warning("record_write_log failed: %s", e)
            return Result(success=False, error=str(e))

    def complete_write_log(self, log_id: int) -> Result:
        try:
            with self._conn() as conn:
                conn.execute(
                    "UPDATE write_log SET status='completed', completed_at=? WHERE id=?",
                    (datetime.now().isoformat(), log_id)
                )
            return Result(success=True)
        except Exception as e:
            return Result(success=False, error=str(e))

    def complete_write_log_by_slug(self, slug: str) -> Result:
        try:
            with self._conn() as conn:
                conn.execute(
                    """UPDATE write_log SET status='completed', completed_at=?
                       WHERE target_slug=? AND status='pending'""",
                    (datetime.now().isoformat(), slug)
                )
            return Result(success=True)
        except Exception as e:
            return Result(success=False, error=str(e))

    def get_pending_writes(self) -> List[Dict]:
        try:
            with self._conn() as conn:
                cursor = conn.execute(
                    """SELECT id, operation, target_slug, payload_json, retry_count
                       FROM write_log WHERE status='pending' AND retry_count < 3
                       ORDER BY created_at LIMIT 50"""
                )
                return [
                    {"id": r[0], "operation": r[1], "target_slug": r[2],
                     "payload": json.loads(r[3]), "retry_count": r[4]}
                    for r in cursor
                ]
        except Exception as e:
            logger.warning("get_pending_writes failed: %s", e)
            return []

    def mark_write_log_failed(self, log_id: int) -> Result:
        try:
            with self._conn() as conn:
                conn.execute(
                    "UPDATE write_log SET status='failed', error_message=? WHERE id=?",
                    ("Retry limit exceeded", log_id)
                )
            return Result(success=True)
        except Exception as e:
            return Result(success=False, error=str(e))

    def consume_pending(self, gbrain) -> Result:
        consumed = 0
        failed = 0
        for f in gbrain._pending_dir.glob("*.md"):
            try:
                content = f.read_text()
                slug_match = re.search(r'<!--\s*slug:\s*(.+?)\s*-->', content)
                if slug_match:
                    slug = slug_match.group(1).strip()
                    content = content[content.index('-->') + 3:].lstrip()
                else:
                    slug = f.stem.replace("-", "/")
                    logger.warning("Pending file %s has no slug header", f)
                result = gbrain.put(slug, content)
                if result.success:
                    f.unlink()
                    consumed += 1
                else:
                    failed += 1
            except Exception as e:
                logger.warning("consume pending file %s failed: %s", f, e)
                failed += 1
        pending_writes = self.get_pending_writes()
        for write in pending_writes:
            try:
                if write["operation"] == "put_page":
                    result = gbrain.put(write["target_slug"], write["payload"]["content"])
                    if result.success:
                        self.complete_write_log(write["id"])
                        consumed += 1
                    else:
                        with self._conn() as conn:
                            conn.execute(
                                "UPDATE write_log SET retry_count=retry_count+1 WHERE id=?",
                                (write["id"],)
                            )
                        if write["retry_count"] + 1 >= 3:
                            self.mark_write_log_failed(write["id"])
                        failed += 1
            except Exception as e:
                logger.warning("consume WAL log %d failed: %s", write["id"], e)
                failed += 1
        logger.info("Pending consumption: consumed=%d, failed=%d", consumed, failed)
        return Result(success=True, data={"consumed": consumed, "failed": failed})
