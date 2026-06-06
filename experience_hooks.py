#!/usr/bin/env python3
"""经验沉淀集成钩子

用法:
    from experience_hooks import (
        lookup_error, record_error, record_task_end,
        record_solution_applied, record_solution_outcome,
    )
    
    result = lookup_error("ConnectionError: session_key missing")
    record_task_end("session-xxx", "coding", "success", turns=15, errors=2)
    record_solution_applied("error-log/tencentdb-session-key", "修改了 __init__.py")
    record_solution_outcome("error-log/tencentdb-session-key", "effective", "问题已解决")
"""

import sys
from pathlib import Path
from typing import Optional, Dict

sys.path.insert(0, str(Path(__file__).parent))

from experience import ExperienceEngine, TaskType, Outcome

_engine: Optional[ExperienceEngine] = None


def _get_engine(profile: str = "default") -> ExperienceEngine:
    global _engine
    if _engine is None:
        _engine = ExperienceEngine(profile=profile)
    return _engine


def lookup_error(error_msg: str, profile: str = "default") -> Optional[Dict]:
    """遇到错误时自动查询错误库"""
    engine = _get_engine(profile)
    result = engine.auto_recall_on_error(error_msg)
    if result.success:
        return result.data
    return None


def record_error(title: str, system: str, module: str, severity: str,
                 symptoms: list, root_cause: str, fix_steps: list,
                 prevention: str = "", profile: str = "default") -> Optional[str]:
    """记录新错误到 GBrain"""
    from experience.models import Severity
    engine = _get_engine(profile)
    result = engine.record_error(
        title=title, system=system, module=module,
        severity=Severity(severity), symptoms=symptoms,
        root_cause=root_cause, fix_steps=fix_steps, prevention=prevention,
    )
    if result.success:
        return result.slug
    return None


def record_task_end(session_id: str, task_type: str, outcome: str,
                    domain: str = None, turns: int = None, errors: int = None,
                    retries: int = None, methodology: str = None,
                    notes: str = None, profile: str = "default") -> bool:
    """任务结束时记录结果"""
    engine = _get_engine(profile)
    result = engine.record_task_outcome(
        session_id=session_id, task_type=TaskType(task_type),
        outcome=Outcome(outcome) if outcome in ["success", "failure"] else Outcome.UNKNOWN,
        task_domain=domain, duration_turns=turns, error_count=errors,
        retry_count=retries, methodology_used=methodology, notes=notes,
    )
    return result.success


def record_solution_applied(slug: str, note: str = None,
                            profile: str = "default") -> bool:
    """应用方案时记录"""
    engine = _get_engine(profile)
    result = engine.record_feedback(
        page_slug=slug,
        page_type="error-log" if slug.startswith("error-log/") else "methodology",
        action="applied", outcome_note=note,
    )
    return result.success


def record_solution_outcome(slug: str, outcome: str, note: str = None,
                            profile: str = "default") -> bool:
    """方案结果确认"""
    engine = _get_engine(profile)
    result = engine.record_feedback(
        page_slug=slug,
        page_type="error-log" if slug.startswith("error-log/") else "methodology",
        action="outcome", outcome=outcome, outcome_note=note,
    )
    return result.success


def get_capability_report(days: int = 7, profile: str = "default") -> Optional[Dict]:
    """获取能力评估报告"""
    engine = _get_engine(profile)
    result = engine.get_capability_report(days=days)
    if result.success:
        return result.data
    return None


def consume_pending(profile: str = "default") -> Optional[Dict]:
    """消费 pending 文件和 WAL 日志"""
    engine = _get_engine(profile)
    result = engine.consume_pending()
    if result.success:
        return result.data
    return None
