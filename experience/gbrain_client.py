"""经验沉淀引擎 — GBrain 交互层"""

import subprocess
import threading
import re
import json
import hashlib
import os
from pathlib import Path
from typing import Optional, Dict
import logging

from .models import Result

logger = logging.getLogger(__name__)


class GBrainClient:
    """GBrain 交互层"""

    def __init__(self, cli_path: str = None, pending_dir: Path = None,
                 profile: str = "default", feedback_store=None):
        self._cli = cli_path or os.environ.get("GBRAIN_CLI", "gbrain")
        self._pending_dir = pending_dir or (
            Path.home() / ".hermes" / "gbrain-pending" / profile
        )
        self._pending_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._available = False
        self._feedback_store = feedback_store

    def check_health(self) -> bool:
        try:
            result = subprocess.run(
                [self._cli, "doctor", "--fast"],
                capture_output=True, text=True, timeout=15
            )
            self._available = result.returncode == 0
            if not self._available:
                logger.warning("GBrain CLI health check failed: %s", result.stderr[:200])
        except Exception as e:
            self._available = False
            logger.warning("GBrain CLI not available: %s", e)
        return self._available

    @property
    def is_available(self) -> bool:
        return self._available

    def get(self, slug: str) -> Optional[Dict]:
        with self._lock:
            try:
                result = subprocess.run(
                    [self._cli, "get", slug],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0 and result.stdout.strip():
                    return {"compiled_truth": result.stdout.strip()}
            except Exception as e:
                logger.warning("gbrain get(%s) failed: %s", slug, e)
        return None

    def put(self, slug: str, content: str) -> Result:
        with self._lock:
            try:
                tmp_path = self._pending_dir / f"tmp-{slug.replace('/', '-')}.md"
                tmp_path.write_text(content)
                result = subprocess.run(
                    [self._cli, "put", slug, str(tmp_path)],
                    capture_output=True, text=True, timeout=30
                )
                tmp_path.unlink(missing_ok=True)
                if result.returncode == 0:
                    return Result(success=True, slug=slug)
                else:
                    logger.warning("gbrain put(%s) failed: %s", slug, result.stderr[:200])
            except Exception as e:
                logger.warning("gbrain put(%s) exception: %s", slug, e)

        self._save_pending(slug, content)
        self._write_wal_fallback(slug, content)
        return Result(success=False, error="GBrain unavailable, saved to pending", slug=slug)

    def search(self, query: str, limit: int = 5) -> Result:
        with self._lock:
            try:
                result = subprocess.run(
                    [self._cli, "search", query, "--limit", str(limit)],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    items = []
                    for line in result.stdout.strip().split("\n"):
                        line = line.strip()
                        if not line:
                            continue
                        match = re.match(r'\[([\d.]+)\]\s+(\S+)\s+--\s+(.*)', line)
                        if match:
                            score, slug, title = match.groups()
                            items.append({
                                "slug": slug,
                                "title": title.strip(),
                                "score": float(score),
                            })
                    return Result(success=True, data=items)
            except Exception as e:
                logger.warning("gbrain search(%s) failed: %s", query, e)
        return Result(success=False, data=[])

    def _save_pending(self, slug: str, content: str):
        slug_hash = hashlib.md5(slug.encode()).hexdigest()[:12]
        filename = f"{slug_hash}.md"
        filepath = self._pending_dir / filename
        header = f"<!-- slug: {slug} -->\n"
        filepath.write_text(header + content)
        logger.info("Saved to pending: %s (slug: %s)", filepath, slug)

    def _write_wal_fallback(self, slug: str, content: str):
        if self._feedback_store:
            self._feedback_store.record_write_log(
                operation="put_page",
                target_slug=slug,
                payload={"content": content}
            )
