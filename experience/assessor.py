"""经验沉淀引擎 — 能力评估"""

import logging
from datetime import datetime, timedelta

from .models import Result, TaskType, Outcome
from .feedback_store import FeedbackStore

logger = logging.getLogger(__name__)


class CapabilityAssessor:
    """能力评估"""

    def __init__(self, feedback_store: FeedbackStore):
        self._store = feedback_store

    def record_task_outcome(
        self,
        session_id: str,
        task_type: TaskType,
        outcome: Outcome,
        task_domain: str = None,
        duration_turns: int = None,
        error_count: int = None,
        retry_count: int = None,
        methodology_used: str = None,
        notes: str = None,
    ) -> Result:
        try:
            with self._store._conn() as conn:
                conn.execute(
                    """INSERT INTO task_outcomes
                       (session_id, task_type, task_domain, outcome, duration_turns,
                        error_count, retry_count, methodology_used, notes, profile, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (session_id, task_type.value, task_domain, outcome.value,
                     duration_turns, error_count, retry_count, methodology_used,
                     notes, self._store._profile, datetime.now().isoformat())
                )
            return Result(success=True)
        except Exception as e:
            logger.warning("record_task_outcome failed: %s", e)
            return Result(success=False, error=str(e))

    def generate_report(self, days: int = 7) -> Result:
        try:
            with self._store._conn() as conn:
                since = (datetime.now() - timedelta(days=days)).isoformat()
                cursor = conn.execute(
                    """SELECT task_type,
                              SUM(CASE WHEN outcome='effective' THEN 1 ELSE 0 END),
                              COUNT(*),
                              AVG(duration_turns),
                              AVG(error_count)
                       FROM task_outcomes
                       WHERE created_at > ? AND profile = ?
                       GROUP BY task_type""",
                    (since, self._store._profile)
                )
                by_type = {}
                for r in cursor:
                    by_type[r[0]] = {
                        "success_rate": r[1] / r[2] if r[2] > 0 else 0,
                        "total": r[2],
                        "avg_turns": round(r[3] or 0, 1),
                        "avg_errors": round(r[4] or 0, 1),
                    }
                cursor = conn.execute(
                    """SELECT page_slug, COUNT(*)
                       FROM feedback
                       WHERE action='applied' AND outcome='ineffective'
                       AND created_at > ? AND profile = ?
                       GROUP BY page_slug ORDER BY COUNT(*) DESC LIMIT 5""",
                    (since, self._store._profile)
                )
                ineffective = [{"slug": r[0], "count": r[1]} for r in cursor]
            report = {
                "period_days": days,
                "by_task_type": by_type,
                "ineffective_solutions": ineffective,
            }
            return Result(success=True, data=report)
        except Exception as e:
            logger.warning("generate_report failed: %s", e)
            return Result(success=False, error=str(e))
