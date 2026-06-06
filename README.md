# Experience Engine v1.0

经验沉淀引擎 — 为 Hermes Agent 提供错误自动召回、方法论积累、反馈循环和能力评估。

## 架构

```
ExperienceEngine (协调者，只做路由)
├── ErrorRepository ──────→ 错误库 CRUD (GBrain)
├── MethodologyRepository → 方法论 CRUD (GBrain)
├── FeedbackStore ────────→ 反馈存储 (SQLite)
├── CapabilityAssessor ───→ 能力评估 (SQLite)
└── RecallEngine ─────────→ 自动召回 (组合上述组件)
```

## 安装

```bash
git clone https://github.com/feiyu169/experience-engine.git
cd experience-engine
pip install pytest
python -m pytest tests/ -v
```

## 使用

### CLI

```bash
python experience_recall.py lookup "错误消息"
python experience_recall.py record --title "标题" --system tencentdb --module sync --severity P0
python experience_recall.py task --session-id "xxx" --type coding --outcome success
python experience_recall.py report --days 7
python experience_feedback.py applied --slug "error-log/xxx" --type error-log
python experience_feedback.py outcome --slug "error-log/xxx" --outcome effective
```

### Python API

```python
from experience import ExperienceEngine, Severity, TaskType, Outcome

engine = ExperienceEngine(profile="default")
result = engine.auto_recall_on_error("ConnectionError: session_key missing")
```

## License

MIT
