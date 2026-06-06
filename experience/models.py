"""经验沉淀引擎 — 数据模型"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Any
from datetime import datetime


class Severity(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


class ErrorStatus(str, Enum):
    OPEN = "open"
    FIXED = "fixed"
    WORKAROUND = "workaround"
    WONTFIX = "wontfix"


class Outcome(str, Enum):
    EFFECTIVE = "effective"
    INEFFECTIVE = "ineffective"
    UNKNOWN = "unknown"


class TaskType(str, Enum):
    CODING = "coding"
    DEBUGGING = "debugging"
    DEPLOYMENT = "deployment"
    REVIEW = "review"
    RESEARCH = "research"
    CONFIGURATION = "configuration"
    OTHER = "other"


@dataclass
class Result:
    """统一返回类型"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    slug: Optional[str] = None


@dataclass
class ErrorRecord:
    """错误记录"""
    title: str
    system: str
    module: str
    severity: Severity
    symptoms: List[str]
    root_cause: str
    fix_steps: List[str]
    prevention: str = ""
    status: ErrorStatus = ErrorStatus.OPEN
    fix_verified: bool = False
    occurrence_count: int = 1
    related_pages: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    first_seen: str = ""
    last_seen: str = ""

    def to_gbrain_content(self) -> str:
        tags_str = ", ".join(self.tags)
        symptoms_str = "\n".join(f"- {s}" for s in self.symptoms)
        fix_str = "\n".join(f"{i+1}. {s}" for i, s in enumerate(self.fix_steps))
        related_str = "\n".join(f"- [[{s}]]" for s in self.related_pages)
        now = datetime.now().isoformat()
        return f"""---
type: error-log
tags: [{tags_str}]
severity: {self.severity.value}
status: {self.status.value}
fix_verified: {str(self.fix_verified).lower()}
first_seen: {self.first_seen or now}
last_seen: {self.last_seen or now}
occurrence_count: {self.occurrence_count}
---

# {self.title}

## 症状
{symptoms_str}

## 根因
{self.root_cause}

## 修复
{fix_str}

## 预防
{self.prevention}

## 相关页面
{related_str}
"""


@dataclass
class Methodology:
    """方法论"""
    title: str
    domain: str
    applicable_scenarios: List[str]
    steps: List[str]
    anti_patterns: List[str] = field(default_factory=list)
    success_cases: List[str] = field(default_factory=list)
    effectiveness: Outcome = Outcome.UNKNOWN
    usage_count: int = 0
    tags: List[str] = field(default_factory=list)

    def to_gbrain_content(self) -> str:
        tags_str = ", ".join(self.tags)
        scenarios_str = "\n".join(f"- {s}" for s in self.applicable_scenarios)
        steps_str = "\n".join(f"{i+1}. {s}" for i, s in enumerate(self.steps))
        anti_str = "\n".join(f"- ❌ {s}" for s in self.anti_patterns)
        cases_str = "\n".join(f"- [[{s}]]" for s in self.success_cases)
        now = datetime.now().isoformat()
        return f"""---
type: methodology
tags: [{tags_str}]
domain: {self.domain}
effectiveness: {self.effectiveness.value}
usage_count: {self.usage_count}
created: {now}
---

# {self.title}

## 适用场景
{scenarios_str}

## 步骤
{steps_str}

## 反模式
{anti_str}

## 成功案例
{cases_str}
"""
