#!/usr/bin/env python3
"""
Paper → WeChat Pipeline CLI
用法: python -m pipeline.run [command]

Commands:
  collector-start   启动数据采集服务
  collector-stop    停止数据采集服务
  profile           生成用户画像报告
  strategy          生成周策略复盘
  publish <file>    发布文章到公众号草稿箱
  review <file>     审稿（对比论文原文）
  review-all        审稿所有文章
  render-formula    渲染文章公式
  extract-figures   提取论文图片
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def cmd_collector_start(args):
    from modules.analytics.collector import start_collector
    print("[pipeline] 启动数据采集服务...")
    start_collector()


def cmd_collector_stop(args):
    subprocess.run(["pkill", "-f", "analytics/collector"], capture_output=True)
    print("[pipeline] 采集服务已停止")


def cmd_profile(args):
    from modules.analytics.profile import generate_profile
    report = generate_profile()
    print(report)


def cmd_strategy(args):
    from modules.analytics.strategy import generate_strategy
    s = generate_strategy()
    print(f"# 周策略复盘: {s.get('period', 'unknown')}")
    for i in s.get("insights", []):
        if isinstance(i, dict):
            print(f"  {i.get('title','?')}: {i.get('action','')}")
        else:
            print(f"  {i}")
    print(f"\n策略已保存到 data/weekly_strategy.json")


def cmd_publish(args):
    from modules.publish.publisher import publish_article
    filepath = args.file
    if not Path(filepath).exists():
        print(f"[pipeline] 文件不存在: {filepath}")
        sys.exit(1)
    result = publish_article(filepath)
    print(f"[pipeline] 发布结果: {result}")


def cmd_review(args):
    from modules.review.reviewer import review_article
    filepath = args.file
    if not Path(filepath).exists():
        print(f"[pipeline] 文件不存在: {filepath}")
        sys.exit(1)
    result = review_article(filepath)
    print(f"[pipeline] 审稿结果: {result}")


def cmd_review_all(args):
    from modules.review.reviewer import review_all
    review_all()


def cmd_render_formula(args):
    from modules.write.formula_render import render_formulas_in_article
    filepath = args.file
    if Path(filepath).exists():
        render_formulas_in_article(filepath)
        print(f"[pipeline] 公式渲染完成: {filepath}")
    else:
        print(f"[pipeline] 文件不存在: {filepath}")


def cmd_extract_figures(args):
    from modules.write.extract_figures import process_paper
    paper_id = args.paper
    process_paper(paper_id)
    print(f"[pipeline] 图片提取完成: {paper_id}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="论文→公众号 全自动流水线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m pipeline.run collector-start
  python -m pipeline.run profile
  python -m pipeline.run strategy
  python -m pipeline.run publish data/articles/P11_InstructGPT.json
  python -m pipeline.run review data/articles/P11_InstructGPT.json
  python -m pipeline.run extract-figures P14
        """
    )
    sub = parser.add_subparsers(dest="command", help="可用命令")

    # Collector
    sub.add_parser("collector-start", help="启动数据采集服务")
    sub.add_parser("collector-stop", help="停止数据采集服务")

    # Reports
    sub.add_parser("profile", help="生成用户画像报告")
    sub.add_parser("strategy", help="生成周策略复盘")

    # Publish
    p_pub = sub.add_parser("publish", help="发布文章到草稿箱")
    p_pub.add_argument("file", help="文章 JSON 文件路径")

    # Review
    p_rev = sub.add_parser("review", help="审稿单篇文章")
    p_rev.add_argument("file", help="文章 JSON 文件路径")
    sub.add_parser("review-all", help="审稿所有文章")

    # Write tools
    p_fml = sub.add_parser("render-formula", help="渲染文章公式")
    p_fml.add_argument("file", help="文章 JSON 文件路径")

    p_fig = sub.add_parser("extract-figures", help="提取论文图片")
    p_fig.add_argument("paper", help="论文ID (如 P14)")

    args = parser.parse_args(argv)

    commands = {
        "collector-start": cmd_collector_start,
        "collector-stop": cmd_collector_stop,
        "profile": cmd_profile,
        "strategy": cmd_strategy,
        "publish": cmd_publish,
        "review": cmd_review,
        "review-all": cmd_review_all,
        "render-formula": cmd_render_formula,
        "extract-figures": cmd_extract_figures,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
