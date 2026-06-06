"""经验沉淀引擎 — 方法论 CRUD"""

import logging
from typing import List

from .models import Methodology, Result
from .gbrain_client import GBrainClient
from .utils import _slugify

logger = logging.getLogger(__name__)


class MethodologyRepository:
    """方法论 CRUD"""

    def __init__(self, gbrain: GBrainClient, feedback_store=None):
        self._gbrain = gbrain
        self._feedback_store = feedback_store

    def record(self, methodology: Methodology) -> Result:
        slug = f"methodology/{methodology.domain}-{_slugify(methodology.title)}"
        methodology.tags = list(set(["methodology", methodology.domain] + methodology.tags))
        content = methodology.to_gbrain_content()
        if self._feedback_store:
            self._feedback_store.record_write_log(
                operation="put_page",
                target_slug=slug,
                payload={"content": content}
            )
        result = self._gbrain.put(slug, content)
        if result.success:
            logger.info("Recorded methodology: %s", slug)
            if self._feedback_store:
                self._feedback_store.complete_write_log_by_slug(slug)
        return result

    def search(self, domain: str, limit: int = 5) -> Result:
        result = self._gbrain.search(f"methodology {domain}", limit=limit)
        if result.success:
            result.data = [r for r in result.data if "methodology" in r.get("slug", "")]
        return result
