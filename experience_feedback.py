#!/usr/bin/env python3
"""反馈循环 CLI

用法:
  python3 experience_feedback.py applied --slug "error-log/xxx" --type error-log
  python3 experience_feedback.py outcome --slug "error-log/xxx" --outcome effective
  python3 experience_feedback.py stats --slug "error-log/xxx"
  python3 experience_feedback.py ineffective
  python3 experience_feedback.py pending
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from experience import FeedbackStore, Result


def cmd_applied(args):
    store = FeedbackStore(profile=args.profile)
    result = store.record_feedback(
        page_slug=args.slug, page_type=args.type,
        action="applied", outcome_note=args.note,
    )
    if result.success:
        print(f"✅ 反馈已记录: {args.slug} 已应用")
    else:
        print(f"❌ 记录失败: {result.error}")

def cmd_outcome(args):
    store = FeedbackStore(profile=args.profile)
    result = store.record_feedback(
        page_slug=args.slug, page_type=args.type or "unknown",
        action="outcome", outcome=args.outcome, outcome_note=args.note,
    )
    if result.success:
        emoji = "✅" if args.outcome == "effective" else "⚠️" if args.outcome == "ineffective" else "❓"
        print(f"{emoji} 结果已记录: {args.slug} → {args.outcome}")
    else:
        print(f"❌ 记录失败: {result.error}")

def cmd_stats(args):
    store = FeedbackStore(profile=args.profile)
    result = store.get_stats(args.slug)
    if result.success:
        print(f"=== 反馈统计: {args.slug} ===")
        if not result.data:
            print("暂无反馈记录")
        else:
            for key, count in result.data.items():
                print(f"  {key}: {count}")
    else:
        print(f"❌ 查询失败: {result.error}")

def cmd_ineffective(args):
    store = FeedbackStore(profile=args.profile)
    try:
        with store._conn() as conn:
            cursor = conn.execute(
                """SELECT page_slug, outcome_note, created_at
                   FROM feedback
                   WHERE action='outcome' AND outcome='ineffective'
                   AND profile = ?
                   ORDER BY created_at DESC LIMIT 20""",
                (args.profile,)
            )
            rows = cursor.fetchall()
        print(f"=== 无效方案 ({len(rows)} 个) ===")
        for slug, note, created in rows:
            print(f"\n  {slug}")
            print(f"    时间: {created}")
            if note:
                print(f"    原因: {note}")
    except Exception as e:
        print(f"❌ 查询失败: {e}")

def cmd_pending(args):
    store = FeedbackStore(profile=args.profile)
    try:
        with store._conn() as conn:
            cursor = conn.execute(
                """SELECT DISTINCT f.page_slug, f.created_at
                   FROM feedback f
                   WHERE f.action = 'applied' AND f.profile = ?
                   AND NOT EXISTS (
                       SELECT 1 FROM feedback f2
                       WHERE f2.page_slug = f.page_slug
                       AND f2.action = 'outcome' AND f2.profile = f.profile
                   )
                   ORDER BY f.created_at DESC LIMIT 20""",
                (args.profile,)
            )
            rows = cursor.fetchall()
        print(f"=== 待确认方案 ({len(rows)} 个) ===")
        for slug, created in rows:
            print(f"  {slug} (应用时间: {created})")
    except Exception as e:
        print(f"❌ 查询失败: {e}")

def main():
    parser = argparse.ArgumentParser(description="反馈循环 CLI")
    parser.add_argument("--profile", default="default")
    subparsers = parser.add_subparsers(dest="command")
    
    p_applied = subparsers.add_parser("applied", help="记录方案被应用")
    p_applied.add_argument("--slug", required=True)
    p_applied.add_argument("--type", required=True)
    p_applied.add_argument("--note")
    p_applied.set_defaults(func=cmd_applied)
    
    p_outcome = subparsers.add_parser("outcome", help="记录方案结果")
    p_outcome.add_argument("--slug", required=True)
    p_outcome.add_argument("--type")
    p_outcome.add_argument("--outcome", required=True, choices=["effective", "ineffective", "unknown"])
    p_outcome.add_argument("--note")
    p_outcome.set_defaults(func=cmd_outcome)
    
    p_stats = subparsers.add_parser("stats", help="查看统计")
    p_stats.add_argument("--slug", required=True)
    p_stats.set_defaults(func=cmd_stats)
    
    p_ineffective = subparsers.add_parser("ineffective", help="查看无效方案")
    p_ineffective.set_defaults(func=cmd_ineffective)
    
    p_pending = subparsers.add_parser("pending", help="查看待确认方案")
    p_pending.set_defaults(func=cmd_pending)
    
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    args.func(args)

if __name__ == "__main__":
    main()
