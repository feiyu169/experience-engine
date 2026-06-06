"""经验沉淀引擎 — 自动召回"""

import logging

from .models import Result
from .error_repo import ErrorRepository
from .method_repo import MethodologyRepository
from .utils import _extract_error_keywords, _extract_domain

logger = logging.getLogger(__name__)


class RecallEngine:
    """自动召回"""

    def __init__(self, error_repo: ErrorRepository, method_repo: MethodologyRepository):
        self._errors = error_repo
        self._methods = method_repo

    def on_error(self, error_msg: str) -> Result:
        fix_result = self._errors.get_fix(error_msg)
        if fix_result.success:
            return Result(success=True, data={
                "type": "error_fix",
                "content": fix_result.data,
                "source": "error-log"
            })
        keywords = _extract_error_keywords(error_msg)
        for kw in keywords:
            search_result = self._errors._gbrain.search(f"experience {kw}", limit=3)
            if search_result.success and search_result.data:
                return Result(success=True, data={
                    "type": "experience",
                    "content": search_result.data[0],
                    "source": "experience"
                })
        return Result(success=False, error="No matching experience found")

    def on_task_start(self, task_desc: str) -> Result:
        domain = _extract_domain(task_desc)
        result = self._methods.search(domain, limit=3)
        if result.success and result.data:
            return Result(success=True, data={
                "type": "methodology",
                "content": result.data[0],
                "source": "methodology"
            })
        return Result(success=False, error="No matching methodology found")
