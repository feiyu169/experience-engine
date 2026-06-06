"""经验沉淀引擎 — 协调者"""

import re
import json
import logging
from datetime import datetime

from .models import (
    ErrorRecord, Methodology, Result, Severity, ErrorStatus, Outcome, TaskType
)
from .gbrain_client import GBrainClient
from .error_repo import ErrorRepository
from .method_repo import MethodologyRepository
from .feedback_store import FeedbackStore
from .assessor import CapabilityAssessor
from .recall import RecallEngine
from .utils import _slugify, _extract_error_keywords, _extract_domain

logger = logging.getLogger(__name__)


class ExperienceEngine:
    """经验沉淀引擎 — 协调者"""

    def __init__(self, profile: str = "default"):
        self._feedback = FeedbackStore(profile=profile)
        self._gbrain = GBrainClient(
            profile=profile,
            feedback_store=self._feedback
        )
        self._errors = ErrorRepository(self._gbrain)
        self._methods = MethodologyRepository(
            self._gbrain,
            feedback_store=self._feedback
        )
        self._assessor = CapabilityAssessor(self._feedback)
        self._recall = RecallEngine(self._errors, self._methods)
        self._gbrain.check_health()

    def record_error(self, **kwargs) -> Result:
        error = ErrorRecord(**kwargs)
        return self._errors.record(error)

    def search_errors(self, query: str, limit: int = 5) -> Result:
        return self._errors.search(query, limit)

    def record_methodology(self, **kwargs) -> Result:
        method = Methodology(**kwargs)
        return self._methods.record(method)

    def search_methodologies(self, domain: str, limit: int = 5) -> Result:
        return self._methods.search(domain, limit)

    def record_feedback(self, **kwargs) -> Result:
        return self._feedback.record_feedback(**kwargs)

    def record_task_outcome(self, **kwargs) -> Result:
        return self._assessor.record_task_outcome(**kwargs)

    def get_capability_report(self, days: int = 7) -> Result:
        return self._assessor.generate_report(days)

    def auto_recall_on_error(self, error_msg: str) -> Result:
        return self._recall.on_error(error_msg)

    def auto_recall_on_task_start(self, task_desc: str) -> Result:
        return self._recall.on_task_start(task_desc)

    def consume_pending(self) -> Result:
        return self._feedback.consume_pending(self._gbrain)

    def generate_weekly_report(self) -> str:
        report_result = self._assessor.generate_report(days=7)
        if not report_result.success:
            return f"# 周度报告生成失败: {report_result.error}"
        report = report_result.data
        lines = ["# 周度经验报告", ""]
        lines.append(f"## 统计周期: 过去 {report['period_days']} 天")
        lines.append("")
        if not report["by_task_type"]:
            lines.append("暂无任务数据。")
            return "\n".join(lines)
        lines.append("## 任务能力评估")
        lines.append("")
        lines.append("| 任务类型 | 成功率 | 总数 | 平均轮次 | 平均错误 |")
        lines.append("|---------|--------|------|----------|----------|")
        for ttype, stats in report["by_task_type"].items():
            lines.append(
                f"| {ttype} | {stats['success_rate']:.0%} | {stats['total']} | "
                f"{stats['avg_turns']} | {stats['avg_errors']} |"
            )
        lines.append("")
        if report["ineffective_solutions"]:
            lines.append("## 无效方案 (需要重新审视)")
            for item in report["ineffective_solutions"]:
                lines.append(f"- {item['slug']}: 失败 {item['count']} 次")
        return "\n".join(lines)
