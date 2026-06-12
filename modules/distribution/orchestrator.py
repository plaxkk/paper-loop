#!/usr/bin/env python3
"""
Multi-platform distribution orchestrator — powered by wechatsync Chrome extension.

Replaces the old Playwright-based publishers. The wechatsync extension handles:
- Platform authentication (uses browser's existing login cookies)
- Content adaptation (images, formatting, platform-specific quirks)
- Publishing (calls each platform's official Web API)

We just need to: write markdown → call `wechatsync sync`.

Usage:
  python -m pipeline.run distribute-publish <article.json> [--dry-run] [--platforms zhihu,juejin]
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .adapters import adapt_for_all_platforms


def _load_token() -> str:
    """Load WECHATSYNC_TOKEN from env or ~/.hermes/.env (never from repo)."""
    token = os.environ.get("WECHATSYNC_TOKEN", "")
    if token:
        return token
    hermes_env = Path.home() / ".hermes" / ".env"
    if hermes_env.exists():
        for line in hermes_env.read_text().splitlines():
            if line.startswith("WECHATSYNC_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def check_wechatsync() -> bool:
    """Check if wechatsync CLI is installed and reachable."""
    try:
        r = subprocess.run(["wechatsync", "--version"], capture_output=True, text=True, timeout=5)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def publish_to_all(article_path: str, paper_id: str = None,
                   dry_run: bool = True, platforms: list = None,
                   output_dir: str = None) -> dict:
    """Publish one article to all configured platforms via wechatsync.
    
    1. Adapt WeChat HTML → Markdown
    2. Save Markdown to temp file
    3. Call `wechatsync sync` with platform list
    
    Returns: {"success": bool, "output": str, "error": str}
    """
    if platforms is None:
        platforms = ["zhihu", "juejin", "csdn", "weixin"]
    
    if not check_wechatsync():
        return {
            "success": False,
            "output": "",
            "error": "wechatsync CLI 未安装。运行: npm install -g @wechatsync/cli"
        }
    
    # 1. Adapt content
    article_path = Path(article_path)
    print(f"\n{'='*60}")
    print(f"分发文章: {article_path.name}")
    print(f"{'='*60}")
    
    result = adapt_for_all_platforms(article_path)
    title = result["title"]
    
    print(f"  标题: {title}")
    
    # 2. Write markdown to temp file
    out_dir = Path(output_dir) if output_dir else Path("/tmp/wechatsync")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    md_content = result["juejin"]  # Generic markdown (close to juejin format)
    safe_name = title.replace("/", "-").replace(":", "：")[:40]
    md_path = out_dir / f"{safe_name}.md"
    md_path.write_text(md_content, encoding="utf-8")
    print(f"  Markdown: {md_path} ({len(md_content)} 字符)")
    
    # 3. Call wechatsync
    plat_str = ",".join(platforms)
    print(f"\n--- wechatsync → {plat_str} ---")
    
    cmd = ["wechatsync", "sync", str(md_path), "-p", plat_str, "-t", title]
    if dry_run:
        cmd.append("--dry-run")
        print(f"  [DRY RUN] {' '.join(cmd)}")
    
    # Inject token from env (prefers env var, falls back to ~/.hermes/.env)
    env = os.environ.copy()
    token = _load_token()
    if token:
        env["WECHATSYNC_TOKEN"] = token
    
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env)
        output = r.stdout + r.stderr
        print(output[-500:] if len(output) > 500 else output)
        
        success = r.returncode == 0
        if not success:
            print(f"  ⚠ wechatsync 返回 exit code {r.returncode}")
        
        return {
            "success": success,
            "output": output,
            "error": "" if success else f"exit code {r.returncode}"
        }
    
    except FileNotFoundError:
        return {"success": False, "output": "", "error": "wechatsync 未安装"}
    except subprocess.TimeoutExpired:
        return {"success": False, "output": "", "error": "wechatsync 超时（检查 Chrome 扩展是否运行）"}


# ── CLI ──

def main():
    args = sys.argv[1:] if len(sys.argv) > 1 else ["help"]
    
    if args[0] == "adapt":
        if len(args) < 2:
            print("用法: orchestrator adapt <article_path>")
            return
        result = adapt_for_all_platforms(args[1])
        print(f"标题: {result['title']}")
        print(f"\n=== 知乎版 ===\n{result['zhihu'][:300]}...")
        print(f"\n=== 掘金版 ===\n{result['juejin'][:300]}...")
    
    elif args[0] == "publish":
        if len(args) < 2:
            print("用法: orchestrator publish <article_path> [--dry-run]")
            return
        
        import asyncio
        article_path = args[1]
        dry_run = "--dry-run" in args
        
        platforms = ["zhihu", "juejin", "csdn", "weixin"]
        r = publish_to_all(article_path, dry_run=dry_run, platforms=platforms)
        
        print(f"\n{'='*60}")
        status = "✓" if r["success"] else "✗"
        print(f"{status} 分发{'成功' if r['success'] else '失败'}")
        if r["error"]:
            print(f"  错误: {r['error']}")
    
    elif args[0] == "check":
        if check_wechatsync():
            print("✓ wechatsync CLI 已安装")
            # Quick health check
            try:
                r = subprocess.run(["wechatsync", "--version"], capture_output=True, text=True, timeout=5)
                print(f"  版本: {r.stdout.strip()}")
            except Exception:
                pass
        else:
            print("✗ wechatsync CLI 未安装")
            print("  运行: npm install -g @wechatsync/cli")
    
    else:
        print("Paper → WeChat 多平台分发 (基于 wechatsync)")
        print()
        print("命令:")
        print("  adapt <path>    生成各平台适配版本（预览）")
        print("  publish <path>  通过 wechatsync 分发到所有平台")
        print("  publish <path> --dry-run  演练模式")
        print("  check           检查 wechatsync 状态")
        print()
        print("前置条件:")
        print("  1. 安装 Chrome 扩展「文章同步助手」")
        print("     https://chromewebstore.google.com/detail/文章同步助手/hchobocdmclopcbnibdnoafilagadion")
        print("  2. 在扩展设置中启用「MCP 连接」")
        print("  3. 在 Chrome 中登录知乎、掘金等目标平台")
        print("  4. npm install -g @wechatsync/cli")


if __name__ == "__main__":
    main()
