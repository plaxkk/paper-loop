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
  distribute-login    检查 wechatsync 状态
  distribute-publish <file> [--dry-run]  通过 wechatsync 多平台分发
  distribute-adapt <file>  生成多平台适配版本
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


def cmd_distribute_login(args):
    """Check wechatsync setup status (replaces old Playwright login)."""
    from modules.distribution.orchestrator import check_wechatsync
    
    print("[pipeline] 检查 wechatsync 状态...")
    if check_wechatsync():
        print("✓ wechatsync CLI 已安装")
        print()
        print("请确认以下前置条件:")
        print("  1. Chrome 扩展「文章同步助手」已安装并启用")
        print("     https://chromewebstore.google.com/detail/文章同步助手/hchobocdmclopcbnibdnoafilagadion")
        print("  2. 在扩展设置中已启用「MCP 连接」")
        print("  3. 已在 Chrome 中登录知乎、掘金等目标平台")
    else:
        print("✗ wechatsync CLI 未安装")
        print("  运行: npm install -g @wechatsync/cli")


def cmd_distribute_adapt(args):
    """Generate platform-specific adapted versions of an article."""
    from modules.distribution.adapters import adapt_for_all_platforms
    result = adapt_for_all_platforms(args.file,
        output_dir=str(Path(args.file).parent.parent / "distributed"))
    print(f"[pipeline] 已生成多平台版本:")
    for platform in ["zhihu", "juejin", "csdn"]:
        length = len(result.get(platform, ""))
        print(f"  {platform}: {length} 字符")


def cmd_distribute_publish(args):
    """Publish article via wechatsync CLI (replaces old Playwright)."""
    from modules.distribution.orchestrator import publish_to_all
    
    platforms = []
    if hasattr(args, 'zhihu') and args.zhihu:
        platforms.append("zhihu")
    if hasattr(args, 'juejin') and args.juejin:
        platforms.append("juejin")
    if not platforms:
        platforms = ["zhihu", "juejin", "csdn", "weixin"]
    
    dry_run = hasattr(args, 'dry_run') and args.dry_run
    
    r = publish_to_all(
        args.file,
        dry_run=dry_run,
        platforms=platforms,
    )
    
    if not r["success"] and "超时" in r.get("error", ""):
        print("\n[pipeline] wechatsync 连接超时 — 请确认:")
        print("  1. Chrome 浏览器正在运行")
        print("  2. 「文章同步助手」扩展已安装并启用")
        print("  3. 扩展设置中「MCP 连接」已开启")


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

    # Distribution (powered by wechatsync Chrome extension)
    sub.add_parser("distribute-login", help="检查 wechatsync 状态")

    p_da = sub.add_parser("distribute-adapt", help="生成多平台适配版本")
    p_da.add_argument("file", help="文章 JSON 文件路径")

    p_dp = sub.add_parser("distribute-publish", help="通过 wechatsync 分发")
    p_dp.add_argument("file", help="文章 JSON 文件路径")
    p_dp.add_argument("--dry-run", action="store_true", help="演练模式")

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
        "distribute-login": cmd_distribute_login,
        "distribute-adapt": cmd_distribute_adapt,
        "distribute-publish": cmd_distribute_publish,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
