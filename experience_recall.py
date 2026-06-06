#!/usr/bin/env python3
"""经验沉淀引擎 — CLI

用法:
  python3 experience_recall.py lookup "错误消息"
  python3 experience_recall.py record --title "标题" --system tencentdb --module sync --severity P0
  python3 experience_recall.py task --session-id "xxx" --type coding --outcome success
  python3 experience_recall.py report --days 7
  python3 experience_recall.py consume-pending
"""

import sys
import argparse
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from experience import (
    ExperienceEngine, Severity, ErrorStatus, Outcome, TaskType
)


def cmd_lookup(args):
    engine = ExperienceEngine(profile=args.profile)
    result = engine.auto_recall_on_error(args.message)
    if result.success:
        data = result.data
        print(f"=== 找到匹配 [{data['type']}] ===")
        print(f"来源: {data['source']}")
        if isinstance(data['content'], str):
            print(data['content'][:2000])
        else:
            print(json.dumps(data['content'], ensure_ascii=False, indent=2)[:2000])
    else:
        print(f"未找到匹配的错误记录: {args.message}")
        print("提示: 修复后请用 'record' 命令记录到错误库")


def cmd_record(args):
    engine = ExperienceEngine(profile=args.profile)
    symptoms = args.symptoms.split("|") if args.symptoms else ["待补充"]
    fix_steps = args.fix.split("|") if args.fix else ["待补充"]
    result = engine.record_error(
        title=args.title, system=args.system, module=args.module,
        severity=Severity(args.severity), symptoms=symptoms,
        root_cause=args.root_cause or "待补充", fix_steps=fix_steps,
        prevention=args.prevention or "",
    )
    if result.success:
        print(f"✅ 错误已记录: {result.slug}")
    else:
        print(f"❌ 记录失败: {result.error}")


def cmd_task(args):
    engine = ExperienceEngine(profile=args.profile)
    outcome_map = {
        "success": Outcome.EFFECTIVE,
        "failure": Outcome.INEFFECTIVE,
        "partial": Outcome.UNKNOWN,
    }
    result = engine.record_task_outcome(
        session_id=args.session_id, task_type=TaskType(args.type),
        outcome=outcome_map.get(args.outcome, Outcome.UNKNOWN),
        task_domain=args.domain, duration_turns=args.turns,
        error_count=args.errors, retry_count=args.retries,
        methodology_used=args.methodology, notes=args.notes,
    )
    if result.success:
        print(f"✅ 任务结果已记录")
    else:
        print(f"❌ 记录失败: {result.error}")


def cmd_report(args):
    engine = ExperienceEngine(profile=args.profile)
    if args.format == "text":
        report = engine.generate_weekly_report()
        print(report)
    else:
        result = engine.get_capability_report(days=args.days)
        if result.success:
            print(json.dumps(result.data, ensure_ascii=False, indent=2))
        else:
            print(f"❌ 报告生成失败: {result.error}")


def cmd_consume_pending(args):
    engine = ExperienceEngine(profile=args.profile)
    result = engine.consume_pending()
    if result.success:
        data = result.data
        print(f"✅ Pending 消费完成")
        print(f"  消费: {data['consumed']} 个")
        print(f"  失败: {data['failed']} 个")
    else:
        print(f"❌ 消费失败: {result.error}")


def main():
    parser = argparse.ArgumentParser(description="经验沉淀引擎 CLI")
    parser.add_argument("--profile", default="default", help="Hermes profile")
    subparsers = parser.add_subparsers(dest="command")
    
    p_lookup = subparsers.add_parser("lookup", help="查询错误库")
    p_lookup.add_argument("message", help="错误消息")
    p_lookup.set_defaults(func=cmd_lookup)
    
    p_record = subparsers.add_parser("record", help="记录新错误")
    p_record.add_argument("--title", required=True)
    p_record.add_argument("--system", required=True)
    p_record.add_argument("--module", required=True)
    p_record.add_argument("--severity", required=True, choices=["P0", "P1", "P2"])
    p_record.add_argument("--symptoms", help="症状 (用 | 分隔)")
    p_record.add_argument("--root-cause")
    p_record.add_argument("--fix", help="修复步骤 (用 | 分隔)")
    p_record.add_argument("--prevention")
    p_record.set_defaults(func=cmd_record)
    
    p_task = subparsers.add_parser("task", help="记录任务结果")
    p_task.add_argument("--session-id", required=True)
    p_task.add_argument("--type", required=True, choices=[t.value for t in TaskType])
    p_task.add_argument("--outcome", required=True, choices=["success", "failure", "partial"])
    p_task.add_argument("--domain")
    p_task.add_argument("--turns", type=int)
    p_task.add_argument("--errors", type=int)
    p_task.add_argument("--retries", type=int)
    p_task.add_argument("--methodology")
    p_task.add_argument("--notes")
    p_task.set_defaults(func=cmd_task)
    
    p_report = subparsers.add_parser("report", help="生成报告")
    p_report.add_argument("--days", type=int, default=7)
    p_report.add_argument("--format", choices=["text", "json"], default="text")
    p_report.set_defaults(func=cmd_report)
    
    p_consume = subparsers.add_parser("consume-pending", help="消费 pending")
    p_consume.set_defaults(func=cmd_consume_pending)
    
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    args.func(args)

if __name__ == "__main__":
    main()
