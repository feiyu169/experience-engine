"""经验沉淀引擎 — 错误库 CRUD"""

import re
import logging
from datetime import datetime
from typing import Dict

from .models import ErrorRecord, Result, ErrorStatus
from .gbrain_client import GBrainClient
from .utils import _slugify, _extract_error_keywords

logger = logging.getLogger(__name__)


class ErrorRepository:
    """错误库 CRUD"""

    def __init__(self, gbrain: GBrainClient):
        self._gbrain = gbrain

    def record(self, error: ErrorRecord) -> Result:
        slug = f"error-log/{error.system}-{error.module}-{_slugify(error.title)}"
        existing = self._gbrain.get(slug)
        if existing:
            return self._update_occurrence(slug, existing)
        error.tags = list(set(["error-log", error.system, error.module] + error.tags))
        content = error.to_gbrain_content()
        result = self._gbrain.put(slug, content)
        if result.success:
            logger.info("Recorded error: %s", slug)
        return result

    def search(self, query: str, limit: int = 5) -> Result:
        result = self._gbrain.search(f"error-log {query}", limit=limit)
        if result.success:
            result.data = [r for r in result.data if "error-log" in r.get("slug", "")]
        return result

    def get_fix(self, error_msg: str) -> Result:
        keywords = _extract_error_keywords(error_msg)
        if not keywords:
            return Result(success=False, error="No keywords extracted")
        query = " OR ".join(keywords[:3])
        result = self.search(query, limit=3)
        if result.success and result.data:
            first_match = result.data[0]
            slug = first_match.get("slug", "")
            page = self._gbrain.get(slug)
            if page and "compiled_truth" in page:
                return Result(success=True, data=page["compiled_truth"])
            return Result(success=True, data=first_match.get("title", ""))
        return Result(success=False)

    def _update_occurrence(self, slug: str, existing: Dict) -> Result:
        content = existing.get("compiled_truth", "")
        now = datetime.now().isoformat()
        content = re.sub(r'last_seen:\s*\S+', f'last_seen: {now}', content)
        content = re.sub(
            r'occurrence_count:\s*(\d+)',
            lambda m: f'occurrence_count: {int(m.group(1)) + 1}',
            content
        )
        result = self._gbrain.put(slug, content)
        return Result(success=result.success, slug=slug)
