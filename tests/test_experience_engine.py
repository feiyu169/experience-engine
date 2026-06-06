"""经验沉淀引擎 — 单元测试"""

import pytest
import tempfile
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from experience.models import (
    Severity, ErrorStatus, Outcome, TaskType, Result, ErrorRecord, Methodology
)
from experience.utils import _slugify, _extract_error_keywords, _extract_domain
from experience.feedback_store import FeedbackStore
from experience.error_repo import ErrorRepository
from experience.method_repo import MethodologyRepository
from experience.recall import RecallEngine


@pytest.fixture
def tmp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        yield Path(f.name)
    os.unlink(f.name)

@pytest.fixture
def feedback_store(tmp_db):
    return FeedbackStore(db_path=tmp_db, profile="default")

@pytest.fixture
def mock_gbrain():
    class MockGBrain:
        def __init__(self):
            self.pages = {}
            self._available = True
            self._pending_dir = Path(tempfile.mkdtemp())
        def check_health(self):
            return True
        def get(self, slug):
            return self.pages.get(slug)
        def put(self, slug, content):
            self.pages[slug] = {"compiled_truth": content}
            return Result(success=True, slug=slug)
        def search(self, query, limit=5):
            return Result(success=True, data=[])
    return MockGBrain()


class TestSlugify:
    def test_normal_text(self):
        result = _slugify("TencentDB 同步错误")
        assert "tencentdb" in result
        assert "同步错误" in result
    def test_path_traversal(self):
        result = _slugify("../../../etc/passwd")
        assert ".." not in result
        assert "/" not in result
    def test_special_chars(self):
        result = _slugify("error@#$%^&*()")
        assert "@" not in result
    def test_max_length(self):
        result = _slugify("a" * 100)
        assert len(result) <= 50

class TestExtractKeywords:
    def test_english_error(self):
        keywords = _extract_error_keywords("ConnectionError: Failed to connect to localhost:8420")
        assert "connectionerror" in keywords
        assert "connect" in keywords
    def test_chinese_error(self):
        keywords = _extract_error_keywords("连接超时：无法连接到数据库")
        assert any("连接" in kw for kw in keywords)
    def test_max_keywords(self):
        keywords = _extract_error_keywords("a b c d e f g h i j k l m n")
        assert len(keywords) <= 5

class TestExtractDomain:
    def test_memory_domain(self):
        assert _extract_domain("TencentDB 同步问题") == "memory"
    def test_coding_domain(self):
        assert _extract_domain("修复代码 bug") == "coding"
    def test_unknown_domain(self):
        assert _extract_domain("今天天气怎么样") == "general"

class TestFeedbackStore:
    def test_record_feedback(self, feedback_store):
        result = feedback_store.record_feedback(
            page_slug="error-log/test", page_type="error-log",
            action="applied", outcome="effective"
        )
        assert result.success
    def test_get_stats(self, feedback_store):
        feedback_store.record_feedback(
            page_slug="error-log/test", page_type="error-log",
            action="applied", outcome="effective"
        )
        result = feedback_store.get_stats("error-log/test")
        assert result.success
        assert "applied_effective" in result.data
    def test_wal_write_log(self, feedback_store):
        result = feedback_store.record_write_log(
            operation="put_page", target_slug="error-log/test",
            payload={"content": "test"}
        )
        assert result.success
        pending = feedback_store.get_pending_writes()
        assert len(pending) == 1
    def test_wal_complete_by_slug(self, feedback_store):
        feedback_store.record_write_log(
            operation="put_page", target_slug="error-log/test",
            payload={"content": "test"}
        )
        result = feedback_store.complete_write_log_by_slug("error-log/test")
        assert result.success
        pending = feedback_store.get_pending_writes()
        assert len(pending) == 0
    def test_wal_mark_failed(self, feedback_store):
        feedback_store.record_write_log(
            operation="put_page", target_slug="error-log/test",
            payload={"content": "test"}
        )
        pending = feedback_store.get_pending_writes()
        result = feedback_store.mark_write_log_failed(pending[0]["id"])
        assert result.success
    def test_consume_pending_with_slug_header(self, feedback_store, mock_gbrain):
        test_file = mock_gbrain._pending_dir / "abc123.md"
        test_file.write_text("<!-- slug: error-log/test-error -->\n# Test Content")
        result = feedback_store.consume_pending(mock_gbrain)
        assert result.success

class TestErrorRepository:
    def test_record_error(self, mock_gbrain):
        repo = ErrorRepository(mock_gbrain)
        error = ErrorRecord(
            title="测试错误", system="test", module="test",
            severity=Severity.P1, symptoms=["症状1"],
            root_cause="根因", fix_steps=["步骤1"],
        )
        result = repo.record(error)
        assert result.success
    def test_update_occurrence(self, mock_gbrain):
        repo = ErrorRepository(mock_gbrain)
        error = ErrorRecord(
            title="重复错误", system="test", module="test",
            severity=Severity.P1, symptoms=["症状"],
            root_cause="根因", fix_steps=["步骤"],
        )
        repo.record(error)
        result = repo.record(error)
        assert result.success

class TestRecallEngine:
    def test_recall_on_unknown_error(self, mock_gbrain):
        errors = ErrorRepository(mock_gbrain)
        methods = MethodologyRepository(mock_gbrain)
        recall = RecallEngine(errors, methods)
        result = recall.on_error("完全未知的错误消息 xyz")
        assert not result.success

class TestModels:
    def test_error_record_to_content(self):
        error = ErrorRecord(
            title="测试错误", system="test", module="test",
            severity=Severity.P1, symptoms=["症状1"],
            root_cause="根因", fix_steps=["步骤1"], tags=["test"],
        )
        content = error.to_gbrain_content()
        assert "type: error-log" in content
        assert "severity: P1" in content
        assert "status: open" in content
    def test_methodology_to_content(self):
        method = Methodology(
            title="测试方法论", domain="test",
            applicable_scenarios=["场景1"], steps=["步骤1"], tags=["test"],
        )
        content = method.to_gbrain_content()
        assert "type: methodology" in content
        assert "domain: test" in content

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
