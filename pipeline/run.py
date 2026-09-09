#!/usr/bin/env python3
"""
Paper → WeChat Pipeline CLI
用法: python -m pipeline.run [command]

Commands:
  collector-start   启动数据采集服务
  collector-stop    停止数据采集服务
  collector-status  查看数据采集服务状态
  collector-acceptance-report 一键输出采集验收报告
  collector-validate 验证采集数据准确性与去重
  collector-inspect 查看最新采集 raw 摘要
  collector-script-info 查看 Tampermonkey 脚本版本与哈希
  collector-self-test 浏览器外的采集后端自检
  collector-title-fingerprint <file> 计算后台标题清单指纹
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
import hashlib
import json
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
from http.server import HTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib import request

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
DATA_DIR = REPO_ROOT / "data"
COLLECTOR_PID_FILE = DATA_DIR / "mp_collector.pid"
COLLECTOR_STDOUT_LOG = DATA_DIR / "mp_collector.stdout.log"
COLLECTOR_PORT = 9876
USERSCRIPT_PATH = REPO_ROOT / "modules" / "browser" / "mp_analytics_injector.user.js"
USERSCRIPT_INSTALL_URL = f"http://127.0.0.1:{COLLECTOR_PORT}/mp_analytics_injector.user.js"


def _collector_port_open() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", COLLECTOR_PORT), timeout=0.2):
            return True
    except OSError:
        return False


def _collector_process_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _read_collector_pid() -> int | None:
    try:
        return int(COLLECTOR_PID_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _collector_process_status() -> tuple[str, bool]:
    pid = _read_collector_pid()
    if pid and _collector_process_running(pid):
        return f"PID {pid} running", True
    if pid:
        return f"PID {pid} not running", False
    return "no pid file", False


def cmd_collector_start(args):
    if getattr(args, "daemon", False):
        if _collector_port_open():
            print(f"[pipeline] 采集服务已在运行: http://127.0.0.1:{COLLECTOR_PORT}")
            return

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(COLLECTOR_STDOUT_LOG, "a", encoding="utf-8", buffering=1) as log_file:
            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-u",
                    "-c",
                    "from modules.analytics.collector import start_collector; start_collector()",
                ],
                cwd=str(REPO_ROOT),
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                close_fds=True,
            )

        COLLECTOR_PID_FILE.write_text(str(proc.pid), encoding="utf-8")
        deadline = time.time() + 3
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            if _collector_port_open():
                print(f"[pipeline] 采集服务已后台启动: PID {proc.pid}, http://127.0.0.1:{COLLECTOR_PORT}")
                print(f"[pipeline] 日志: {COLLECTOR_STDOUT_LOG}")
                return
            time.sleep(0.1)

        print(f"[pipeline] 采集服务启动失败，查看日志: {COLLECTOR_STDOUT_LOG}")
        sys.exit(1)

    from modules.analytics.collector import start_collector
    print("[pipeline] 启动数据采集服务...")
    start_collector()


def cmd_collector_stop(args):
    pid = _read_collector_pid()
    if pid and _collector_process_running(pid):
        os.kill(pid, signal.SIGTERM)
        deadline = time.time() + 3
        while time.time() < deadline:
            if not _collector_process_running(pid):
                break
            time.sleep(0.1)
        if _collector_process_running(pid):
            os.kill(pid, signal.SIGKILL)
        COLLECTOR_PID_FILE.unlink(missing_ok=True)
        print(f"[pipeline] 采集服务已停止: PID {pid}")
        return

    subprocess.run(["pkill", "-f", "modules.analytics.collector"], capture_output=True)
    subprocess.run(["pkill", "-f", "analytics/collector"], capture_output=True)
    COLLECTOR_PID_FILE.unlink(missing_ok=True)
    print("[pipeline] 采集服务已停止")


def cmd_collector_status(args):
    port_open = _collector_port_open()
    proc_status, process_running = _collector_process_status()
    if port_open and not process_running:
        proc_status += " (port open; pid check may be stale or sandboxed)"

    print(f"[pipeline] collector process: {proc_status}")
    print(f"[pipeline] collector port: {'open' if port_open else 'closed'} http://127.0.0.1:{COLLECTOR_PORT}")
    print(f"[pipeline] stdout log: {COLLECTOR_STDOUT_LOG}")
    print(f"[pipeline] userscript install/update URL: {USERSCRIPT_INSTALL_URL}")

    try:
        from modules.analytics.validate_collection import latest_diagnostic_raw, latest_published_raw, latest_preview_raw

        latest_published = latest_published_raw()
        latest_preview = latest_preview_raw()
        latest_diagnostic = latest_diagnostic_raw()
        print(f"[pipeline] latest published raw: {latest_published.name if latest_published else 'none'}")
        print(f"[pipeline] latest preview raw: {latest_preview.name if latest_preview else 'none'}")
        print(f"[pipeline] latest diagnostic raw: {latest_diagnostic.name if latest_diagnostic else 'none'}")
    except Exception as exc:
        print(f"[pipeline] raw status unavailable: {exc}")


def cmd_collector_validate(args):
    from modules.analytics.validate_collection import main as validate_main

    argv = []
    if args.expected_published_count is not None:
        argv.extend(["--expected-published-count", str(args.expected_published_count)])
    if args.expected_page_counts:
        argv.extend(["--expected-page-counts", args.expected_page_counts])
    if args.expected_titles_file:
        argv.extend(["--expected-titles-file", args.expected_titles_file])
    if args.expected_title_sha256:
        argv.extend(["--expected-title-sha256", args.expected_title_sha256])
    if args.expected_preview_count is not None:
        argv.extend(["--expected-preview-count", str(args.expected_preview_count)])
    if args.expected_diagnostic_kinds:
        argv.extend(["--expected-diagnostic-kinds", args.expected_diagnostic_kinds])
    if args.expected_script_version:
        argv.extend(["--expected-script-version", args.expected_script_version])
    if args.strict_latest:
        argv.append("--strict-latest")
    if args.strict_preview:
        argv.append("--strict-preview")
    if args.strict_diagnostic:
        argv.append("--strict-diagnostic")
    if args.strict_session:
        argv.append("--strict-session")
    if args.max_raw_age_seconds is not None:
        argv.extend(["--max-raw-age-seconds", str(args.max_raw_age_seconds)])
    if args.watch_seconds:
        argv.extend(["--watch-seconds", str(args.watch_seconds)])
    if args.poll_interval:
        argv.extend(["--poll-interval", str(args.poll_interval)])
    if args.json:
        argv.append("--json")

    rc = validate_main(argv)
    if rc:
        sys.exit(rc)


def cmd_collector_inspect(args):
    from modules.analytics.validate_collection import (
        format_raw_summary,
        latest_diagnostic_raw,
        latest_published_raw,
        latest_preview_raw,
        raw_summary,
    )

    latest_by_type = {
        "published": latest_published_raw,
        "preview": latest_preview_raw,
        "diagnostic": latest_diagnostic_raw,
    }
    page_types = latest_by_type.keys() if args.page_type == "all" else [args.page_type]
    printed = False
    for page_type in page_types:
        path = latest_by_type[page_type]()
        if not path:
            print(f"[{page_type}] no raw file")
            continue
        if printed:
            print()
        print(f"[{page_type}]")
        print(format_raw_summary(raw_summary(path, args.limit)))
        printed = True


def _userscript_versions(script: str) -> tuple[str, str]:
    header_match = re.search(r"^//\s*@version\s+(.+?)\s*$", script, re.MULTILINE)
    const_match = re.search(r"const\s+SCRIPT_VERSION\s*=\s*['\"]([^'\"]+)['\"]", script)
    return (
        header_match.group(1).strip() if header_match else "",
        const_match.group(1).strip() if const_match else "",
    )


def cmd_collector_script_info(args):
    script = USERSCRIPT_PATH.read_text(encoding="utf-8")
    header_version, runtime_version = _userscript_versions(script)
    digest = hashlib.sha256(script.encode("utf-8")).hexdigest()
    expected = args.expected_version or header_version
    ok = bool(header_version and runtime_version and header_version == runtime_version and header_version == expected)

    print(f"[pipeline] userscript: {USERSCRIPT_PATH}")
    print(f"[pipeline] @version: {header_version or 'missing'}")
    print(f"[pipeline] SCRIPT_VERSION: {runtime_version or 'missing'}")
    print(f"[pipeline] expected: {expected or 'missing'}")
    print(f"[pipeline] sha256: {digest}")
    print("[pipeline] Tampermonkey 右上按钮应显示: v" + (runtime_version or "?"))
    print(f"[pipeline] install/update URL: {USERSCRIPT_INSTALL_URL}")
    if not ok:
        sys.exit(1)


def cmd_collector_acceptance_report(args):
    from modules.analytics import validate_collection

    script = USERSCRIPT_PATH.read_text(encoding="utf-8")
    header_version, runtime_version = _userscript_versions(script)
    digest = hashlib.sha256(script.encode("utf-8")).hexdigest()
    expected_version = args.expected_script_version
    script_ok = bool(
        header_version
        and runtime_version
        and header_version == runtime_version
        and header_version == expected_version
    )

    port_open = _collector_port_open()
    proc_status, process_running = _collector_process_status()
    if port_open and not process_running:
        proc_status += " (port open; pid check may be stale or sandboxed)"
        process_running = True
    validation_args = argparse.Namespace(
        expected_published_count=args.expected_published_count,
        expected_page_counts=args.expected_page_counts,
        expected_titles_file=args.expected_titles_file,
        expected_title_sha256=args.expected_title_sha256,
        expected_preview_count=args.expected_preview_count,
        expected_diagnostic_kinds=args.expected_diagnostic_kinds,
        expected_script_version=args.expected_script_version,
        strict_latest=True,
        strict_preview=True,
        strict_diagnostic=True,
        strict_session=True,
        max_raw_age_seconds=args.max_raw_age_seconds,
        watch_seconds=args.watch_seconds,
        poll_interval=args.poll_interval,
        json=False,
    )
    checks = (
        validate_collection.wait_for_checks(validation_args)
        if args.watch_seconds
        else validate_collection.run_checks(validation_args)
    )
    failed = [check for check in checks if not check.passed]
    warnings = [check for check in checks if check.passed and check.level == "warn"]
    passed = [check for check in checks if check.passed and check.level != "warn"]
    report_ok = script_ok and process_running and port_open and not failed

    print("[acceptance] 微信公众号已发表采集验收报告")
    print(f"[acceptance] verdict: {'PASS' if report_ok else 'FAIL'}")
    print()
    print("[script]")
    print(f"path: {USERSCRIPT_PATH}")
    print(f"@version: {header_version or 'missing'}")
    print(f"SCRIPT_VERSION: {runtime_version or 'missing'}")
    print(f"expected: {expected_version}")
    print(f"sha256: {digest}")
    print(f"button: v{runtime_version or '?'} 从第一页全量扫描已发表记录")
    print(f"install_url: {USERSCRIPT_INSTALL_URL}")
    print(f"status: {'PASS' if script_ok else 'FAIL'}")
    print()
    print("[collector]")
    print(f"process: {proc_status}")
    print(f"port: {'open' if port_open else 'closed'} http://127.0.0.1:{COLLECTOR_PORT}")
    print(f"stdout_log: {COLLECTOR_STDOUT_LOG}")
    print()
    print("[latest_raw]")
    latest_by_type = [
        ("published", validate_collection.latest_published_raw()),
        ("preview", validate_collection.latest_preview_raw()),
        (
            "diagnostic",
            validate_collection.latest_diagnostic_raw_for_kinds(
                validate_collection.parse_string_list(args.expected_diagnostic_kinds)
            ),
        ),
    ]
    latest_summaries = {}
    for label, path in latest_by_type:
        if not path:
            print(f"{label}: none")
            continue
        print(f"{label}:")
        summary = validate_collection.raw_summary(path, args.limit)
        latest_summaries[label] = summary
        for line in validate_collection.format_raw_summary(summary).splitlines():
            print(f"  {line}")
    print()
    print("[checks]")
    print(f"passed: {len(passed)}  warnings: {len(warnings)}  failed: {len(failed)}")
    if failed:
        print("failures:")
        for check in failed:
            print(f"  FAIL {check.name}: {check.detail}")
    else:
        print("failures: none")
    if warnings:
        print("warnings:")
        for check in warnings:
            print(f"  WARN {check.name}: {check.detail}")

    if not report_ok:
        print()
        print("[next]")
        for action in _collector_next_actions(
            expected_version,
            script_ok,
            process_running,
            port_open,
            latest_summaries,
            failed,
        ):
            print(f"- {action}")
        sys.exit(1)


def _collector_next_actions(
    expected_version: str,
    script_ok: bool,
    process_running: bool,
    port_open: bool,
    latest_summaries: dict,
    failed: list,
) -> list[str]:
    actions: list[str] = []
    if not script_ok:
        actions.append(f"Tampermonkey 需要安装并运行 v{expected_version}；右上角按钮应显示 v{expected_version}。")
    if not process_running or not port_open:
        actions.append("先运行 `make collector-start` 启动本地采集服务。")
    else:
        actions.append(f"如需更新脚本，浏览器打开 `{USERSCRIPT_INSTALL_URL}`，让 Tampermonkey 安装/更新。")

    summaries = [summary for summary in latest_summaries.values() if summary]
    latest_versions = {
        str(summary.get("script_version") or "")
        for summary in summaries
        if summary.get("script_version")
    }
    if latest_versions and expected_version not in latest_versions:
        versions = ", ".join(sorted(latest_versions))
        actions.append(
            f"最近收到的浏览器数据仍是 v{versions}，不是 v{expected_version}；请更新 Tampermonkey 脚本并刷新微信公众号后台页面。"
        )

    published = latest_summaries.get("published") or {}
    preview = latest_summaries.get("preview") or {}
    if published.get("script_version") != expected_version:
        actions.append(
            f"还没有收到 v{expected_version} 的全量扫描 raw；在已发表页点击 `v{expected_version} 从第一页全量扫描已发表记录`。"
        )
    elif published.get("rows") != 22:
        actions.append(
            f"已收到 v{expected_version} 全量 raw，但条数是 {published.get('rows')}；检查 page_sources、标题清单和后台实际页数是否一致。"
        )

    if preview.get("script_version") == expected_version and preview.get("rows") not in (None, 10):
        actions.append(
            f"v{expected_version} 当前页预检条数是 {preview.get('rows')}，不是 10；用报告里的 dom_debug 定位是否仍有 DOM 误采。"
        )
    elif preview.get("script_version") != expected_version:
        actions.append(f"更新脚本后先点 `当前页预检 v{expected_version}`，确认当前页是 10 篇且不含金额/状态文本。")

    failed_names = {check.name for check in failed}
    if "latest_page_session_consistent" in failed_names or "latest_scan_session_consistent" in failed_names:
        actions.append("预检、页面加载诊断、全量扫描需要来自同一次页面会话；更新脚本后刷新后台页面再连续点击预检和全量扫描。")

    if not actions:
        actions.append(f"重新运行 `python -m pipeline.run collector-acceptance-report` 复验 v{expected_version} 采集结果。")
    return list(dict.fromkeys(actions))


def cmd_collector_title_fingerprint(args):
    from modules.analytics.validate_collection import load_expected_titles, title_fingerprint

    path = Path(args.file)
    if not path.exists():
        print(f"[pipeline] 标题文件不存在: {path}")
        sys.exit(1)

    titles = load_expected_titles(path)
    digest = title_fingerprint(titles)
    print(f"[pipeline] titles file: {path}")
    print(f"[pipeline] title_count: {len(titles)}")
    print(f"[pipeline] title_sha256: {digest}")
    print(
        "[pipeline] acceptance command: "
        f"python -m pipeline.run collector-acceptance-report --expected-title-sha256 {digest}"
    )


def cmd_collector_self_test(args):
    from modules.analytics import collector, schema, validate_collection

    old_collector_paths = collector.DATA_DIR, collector.LATEST_FILE, collector.LOG_FILE
    old_schema_paths = schema.DB_PATH, schema.RAW_DIR
    server = None
    thread = None

    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_dir = root / "mp_raw"
            raw_dir.mkdir(parents=True, exist_ok=True)

            collector.DATA_DIR = raw_dir
            collector.LATEST_FILE = root / "mp_analytics_latest.json"
            collector.LOG_FILE = root / "mp_collector.log"
            schema.DB_PATH = root / "mp_analytics.db"
            schema.RAW_DIR = raw_dir

            server = HTTPServer(("127.0.0.1", 0), collector.CollectorHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

            payload = validate_collection.synthetic_published_payload()
            url = f"http://127.0.0.1:{server.server_port}/mp-data"
            install_url = f"http://127.0.0.1:{server.server_port}/mp_analytics_injector.user.js"
            served_script = _get_collector_text(install_url)
            responses = [
                _post_collector_payload(url, payload),
                _post_collector_payload(url, payload),
            ]

            raw_files = sorted(raw_dir.glob("*_published_records.json"))
            conn = schema.connect_db()
            try:
                article_count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
                metric_count = conn.execute("SELECT COUNT(*) FROM article_daily_metrics").fetchone()[0]
                duplicate_articles = conn.execute("""
                    SELECT COUNT(*) FROM (
                        SELECT msg_id, item_idx FROM articles
                        GROUP BY msg_id, item_idx HAVING COUNT(*) > 1
                    )
                """).fetchone()[0]
                duplicate_metrics = conn.execute("""
                    SELECT COUNT(*) FROM (
                        SELECT article_id, ref_date FROM article_daily_metrics
                        GROUP BY article_id, ref_date HAVING COUNT(*) > 1
                    )
                """).fetchone()[0]
            finally:
                conn.close()

            checks = {
                "userscript_served": "@version" in served_script and "SCRIPT_VERSION" in served_script,
                "http_accepts_two_posts": all(resp.get("status") == "ok" for resp in responses),
                "raw_files_unique": len(raw_files) == 2 and len({path.name for path in raw_files}) == 2,
                "latest_file_written": collector.LATEST_FILE.exists(),
                "article_count_22": article_count == 22,
                "metric_count_22": metric_count == 22,
                "duplicate_articles_0": duplicate_articles == 0,
                "duplicate_metrics_0": duplicate_metrics == 0,
            }

            print("[pipeline] collector backend self-test")
            print(f"[pipeline] temp root: {root}")
            print(f"[pipeline] userscript bytes: {len(served_script.encode('utf-8'))}")
            print(f"[pipeline] http responses: {[resp.get('status') for resp in responses]}")
            print(f"[pipeline] raw files: {len(raw_files)}")
            print(f"[pipeline] articles: {article_count}")
            print(f"[pipeline] daily metrics: {metric_count}")
            print(f"[pipeline] duplicate article identities: {duplicate_articles}")
            print(f"[pipeline] duplicate metric groups: {duplicate_metrics}")
            for name, passed in checks.items():
                print(f"[pipeline] {'PASS' if passed else 'FAIL'} {name}")

            if not all(checks.values()):
                sys.exit(1)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=2)
        collector.DATA_DIR, collector.LATEST_FILE, collector.LOG_FILE = old_collector_paths
        schema.DB_PATH, schema.RAW_DIR = old_schema_paths


def _post_collector_payload(url: str, payload: dict) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_collector_text(url: str) -> str:
    with request.urlopen(url, timeout=5) as resp:
        return resp.read().decode("utf-8")


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
  python -m pipeline.run collector-start --daemon
  python -m pipeline.run profile
  python -m pipeline.run strategy
  python -m pipeline.run publish data/articles/P11_InstructGPT.json
  python -m pipeline.run review data/articles/P11_InstructGPT.json
  python -m pipeline.run extract-figures P14
        """
    )
    sub = parser.add_subparsers(dest="command", help="可用命令")

    # Collector
    p_collect = sub.add_parser("collector-start", help="启动数据采集服务")
    p_collect.add_argument("--daemon", action="store_true", help="后台启动采集服务")
    sub.add_parser("collector-stop", help="停止数据采集服务")
    sub.add_parser("collector-status", help="查看数据采集服务状态")

    p_car = sub.add_parser("collector-acceptance-report", help="输出微信公众号已发表采集验收报告")
    p_car.add_argument("--expected-published-count", type=int, default=22, help="期望全量已发表文章数")
    p_car.add_argument("--expected-page-counts", default="10,10,2", help="期望每页新增数量，例如 10,10,2")
    p_car.add_argument("--expected-titles-file", default=None, help="期望标题文件，一行一个标题或 JSON")
    p_car.add_argument("--expected-title-sha256", default=None, help="期望标题顺序 SHA-256 指纹")
    p_car.add_argument("--expected-preview-count", type=int, default=10, help="期望当前页预检文章数")
    p_car.add_argument("--expected-diagnostic-kinds", default="published_records_page_loaded,published_records_scan_started", help="期望诊断事件类型，逗号分隔")
    p_car.add_argument("--expected-script-version", default="5.0", help="期望 Tampermonkey 脚本版本")
    p_car.add_argument("--max-raw-age-seconds", type=float, default=600, help="最新 raw 的最大允许年龄秒数")
    p_car.add_argument("--watch-seconds", type=float, default=0, help="等待 raw 到达并自动验收")
    p_car.add_argument("--poll-interval", type=float, default=2, help="等待模式轮询间隔")
    p_car.add_argument("--limit", type=int, default=30, help="报告中最多展示文章条数")

    p_cv = sub.add_parser("collector-validate", help="验证采集数据准确性与去重")
    p_cv.add_argument("--expected-published-count", type=int, default=None, help="期望全量已发表文章数")
    p_cv.add_argument("--expected-page-counts", default=None, help="期望每页新增数量，例如 10,10,2")
    p_cv.add_argument("--expected-titles-file", default=None, help="期望标题文件，一行一个标题或 JSON")
    p_cv.add_argument("--expected-title-sha256", default=None, help="期望标题顺序 SHA-256 指纹")
    p_cv.add_argument("--expected-preview-count", type=int, default=None, help="期望当前页预检文章数")
    p_cv.add_argument("--expected-diagnostic-kinds", default=None, help="期望诊断事件类型，逗号分隔")
    p_cv.add_argument("--expected-script-version", default="5.0", help="期望 Tampermonkey 脚本版本")
    p_cv.add_argument("--strict-latest", action="store_true", help="严格检查最新全量 raw")
    p_cv.add_argument("--strict-preview", action="store_true", help="严格检查最新预检 raw")
    p_cv.add_argument("--strict-diagnostic", action="store_true", help="严格检查最新诊断 raw")
    p_cv.add_argument("--strict-session", action="store_true", help="严格检查最新 raw 是否来自同一页面会话")
    p_cv.add_argument("--max-raw-age-seconds", type=float, default=None, help="最新 raw 的最大允许年龄秒数")
    p_cv.add_argument("--watch-seconds", type=float, default=0, help="等待 raw 到达并自动验收")
    p_cv.add_argument("--poll-interval", type=float, default=2, help="等待模式轮询间隔")
    p_cv.add_argument("--json", action="store_true", help="JSON 输出")

    p_ci = sub.add_parser("collector-inspect", help="查看最新采集 raw 摘要")
    p_ci.add_argument("--page-type", choices=["published", "preview", "diagnostic", "all"], default="all")
    p_ci.add_argument("--limit", type=int, default=30, help="最多展示文章条数")

    p_csi = sub.add_parser("collector-script-info", help="查看 Tampermonkey 脚本版本与哈希")
    p_csi.add_argument("--expected-version", default="5.0", help="期望脚本版本")

    sub.add_parser("collector-self-test", help="浏览器外的采集后端自检")

    p_ctf = sub.add_parser("collector-title-fingerprint", help="计算后台标题清单 SHA-256 指纹")
    p_ctf.add_argument("file", help="标题清单文件，一行一个标题或 JSON")

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
        "collector-status": cmd_collector_status,
        "collector-acceptance-report": cmd_collector_acceptance_report,
        "collector-validate": cmd_collector_validate,
        "collector-inspect": cmd_collector_inspect,
        "collector-script-info": cmd_collector_script_info,
        "collector-self-test": cmd_collector_self_test,
        "collector-title-fingerprint": cmd_collector_title_fingerprint,
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
