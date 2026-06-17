"""Smoke tests for the Paper-to-WeChat Pipeline."""

from __future__ import annotations

import importlib
import json
import tempfile
import os
import sys
from pathlib import Path
from unittest import mock

import pytest

import pipeline


class TestPackage:
    def test_version_is_string(self) -> None:
        assert isinstance(pipeline.__version__, str)
        assert len(pipeline.__version__) > 0

    def test_version_parseable(self) -> None:
        parts = pipeline.__version__.split(".")
        assert len(parts) == 3
        for p in parts:
            int(p)


class TestConfig:
    def test_singleton_same_instance(self) -> None:
        from pipeline.config import Config
        c1 = Config.get()
        c2 = Config.get()
        assert c1 is c2

    def test_default_values(self) -> None:
        from pipeline.config import Config
        with mock.patch.object(Config, "_default_config_path") as mock_path:
            mock_path.return_value = Path("/nonexistent/config.json")
            cfg = Config.reload()
        assert cfg.collector_port == 8899

    def test_env_var_fallback(self) -> None:
        from pipeline.config import Config
        with mock.patch.dict("os.environ", {"PAPER_TO_WECHAT_COLLECTOR_PORT": "9999"}):
            with mock.patch.object(Config, "_default_config_path") as mock_path:
                mock_path.return_value = Path("/nonexistent/config.json")
                cfg = Config.reload()
            assert cfg.collector_port == 9999

    def test_config_file_overrides_env(self) -> None:
        from pipeline.config import Config
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tf:
            tf.write('{"collector_port": 7777}')
            config_path = tf.name
        try:
            with mock.patch.dict("os.environ", {"PAPER_TO_WECHAT_COLLECTOR_PORT": "9999"}):
                with mock.patch.object(Config, "_default_config_path") as mock_path:
                    mock_path.return_value = Path(config_path)
                    cfg = Config.reload()
                assert cfg.collector_port == 7777
        finally:
            Path(config_path).unlink()


class TestCLI:
    def test_parser_help(self) -> None:
        from pipeline.run import main
        with pytest.raises(SystemExit) as e:
            main(["-h"])
        assert e.value.code == 0

    def test_collector_start(self) -> None:
        from pipeline.run import main
        # collector-start opens a server, so we just verify parser accepts it
        with pytest.raises(SystemExit) as e:
            main(["collector-start", "--help"])
        assert e.value.code == 0

    def test_collector_status(self, monkeypatch, capsys) -> None:
        import pipeline.run as run

        monkeypatch.setattr(run, "_read_collector_pid", lambda: 12345)
        monkeypatch.setattr(run, "_collector_process_running", lambda pid: True)
        monkeypatch.setattr(run, "_collector_port_open", lambda: True)

        run.main(["collector-status"])
        out = capsys.readouterr().out
        assert "PID 12345 running" in out
        assert "collector port: open" in out
        assert "userscript install/update URL: http://127.0.0.1:9876/mp_analytics_injector.user.js" in out

    def test_collector_status_reports_open_port_when_pid_check_is_stale(self, monkeypatch, capsys) -> None:
        import pipeline.run as run

        monkeypatch.setattr(run, "_read_collector_pid", lambda: 12345)
        monkeypatch.setattr(run, "_collector_process_running", lambda pid: False)
        monkeypatch.setattr(run, "_collector_port_open", lambda: True)

        run.main(["collector-status"])
        out = capsys.readouterr().out
        assert "PID 12345 not running (port open; pid check may be stale or sandboxed)" in out
        assert "collector port: open" in out

    def test_collector_validate_forwards_args(self, monkeypatch) -> None:
        import pipeline.run as run
        from modules.analytics import validate_collection

        seen = {}

        def fake_validate(argv):
            seen["argv"] = argv
            return 0

        monkeypatch.setattr(validate_collection, "main", fake_validate)
        run.main([
            "collector-validate",
            "--strict-preview",
            "--expected-preview-count", "10",
            "--strict-latest",
            "--strict-diagnostic",
            "--strict-session",
            "--expected-published-count", "22",
            "--expected-page-counts", "10,10,2",
            "--expected-titles-file", "expected_titles.txt",
            "--expected-title-sha256", "abc123",
            "--expected-diagnostic-kinds", "published_records_page_loaded,published_records_scan_started",
            "--max-raw-age-seconds", "600",
            "--watch-seconds", "5",
            "--poll-interval", "0.5",
        ])

        assert seen["argv"] == [
            "--expected-published-count", "22",
            "--expected-page-counts", "10,10,2",
            "--expected-titles-file", "expected_titles.txt",
            "--expected-title-sha256", "abc123",
            "--expected-preview-count", "10",
            "--expected-diagnostic-kinds", "published_records_page_loaded,published_records_scan_started",
            "--expected-script-version", "5.0",
            "--strict-latest",
            "--strict-preview",
            "--strict-diagnostic",
            "--strict-session",
            "--max-raw-age-seconds", "600.0",
            "--watch-seconds", "5.0",
            "--poll-interval", "0.5",
        ]

    def test_collector_inspect_prints_latest_published_summary(self, tmp_path, monkeypatch, capsys) -> None:
        import pipeline.run as run
        from modules.analytics import schema, validate_collection

        monkeypatch.setattr(schema, "RAW_DIR", tmp_path)
        raw = {
            "page_type": "published_records",
            "page_data": {
                "article_count": 1,
                "scan_mode": "from_first_page",
                "started_from_current_page": False,
                "page_sources": [{"label": "page_1", "source": "dom_fallback", "candidates": 1, "added": 1, "total": 1}],
                "diagnostics": {"script_version": "5.0"},
            },
            "api_responses": [{
                "body": {"article_list": [{
                    "msg_id": "2247487001",
                    "item_idx": 1,
                    "title": "inspect 文章",
                    "publish_date": "2026-06-16",
                    "total_reads": 123,
                }]}
            }],
        }
        (tmp_path / "20260616_180000_published_records.json").write_text(
            validate_collection.json.dumps(raw, ensure_ascii=False),
            encoding="utf-8",
        )

        run.main(["collector-inspect", "--page-type", "published"])
        out = capsys.readouterr().out
        assert "[published]" in out
        assert "script_version: 5.0" in out
        assert "article_count: 1 rows: 1" in out
        assert "title_sha256:" in out
        assert "inspect 文章" in out

    def test_collector_script_info_reports_version_and_hash(self, tmp_path, monkeypatch, capsys) -> None:
        import pipeline.run as run

        script_path = tmp_path / "mp_analytics_injector.user.js"
        script_path.write_text(
            "\n".join([
                "// ==UserScript==",
                "// @version      5.0",
                "// ==/UserScript==",
                "const SCRIPT_VERSION = '5.0';",
            ]),
            encoding="utf-8",
        )
        monkeypatch.setattr(run, "USERSCRIPT_PATH", script_path)

        run.main(["collector-script-info"])
        out = capsys.readouterr().out
        assert "@version: 5.0" in out
        assert "SCRIPT_VERSION: 5.0" in out
        assert "sha256:" in out
        assert "Tampermonkey 右上按钮应显示: v5.0" in out
        assert "install/update URL: http://127.0.0.1:9876/mp_analytics_injector.user.js" in out

    def test_collector_script_info_fails_on_version_mismatch(self, tmp_path, monkeypatch) -> None:
        import pipeline.run as run

        script_path = tmp_path / "mp_analytics_injector.user.js"
        script_path.write_text(
            "\n".join([
                "// ==UserScript==",
                "// @version      5.0",
                "// ==/UserScript==",
                "const SCRIPT_VERSION = '4.3';",
            ]),
            encoding="utf-8",
        )
        monkeypatch.setattr(run, "USERSCRIPT_PATH", script_path)

        with pytest.raises(SystemExit) as exc:
            run.main(["collector-script-info"])
        assert exc.value.code == 1

    def test_collector_self_test_exercises_http_import_and_dedupes(self, capsys) -> None:
        import pipeline.run as run

        run.main(["collector-self-test"])
        out = capsys.readouterr().out

        assert "collector backend self-test" in out
        assert "PASS userscript_served" in out
        assert "http responses: ['ok', 'ok']" in out
        assert "raw files: 2" in out
        assert "articles: 22" in out
        assert "daily metrics: 22" in out
        assert "PASS raw_files_unique" in out
        assert "PASS duplicate_articles_0" in out
        assert "PASS duplicate_metrics_0" in out

    def test_collector_title_fingerprint_prints_hash(self, tmp_path, capsys) -> None:
        from pipeline.run import main
        from modules.analytics.validate_collection import title_fingerprint

        titles_file = tmp_path / "expected_titles.txt"
        titles_file.write_text(" 后台标题 A \n后台标题 B\n", encoding="utf-8")
        expected = title_fingerprint(["后台标题 A", "后台标题 B"])

        main(["collector-title-fingerprint", str(titles_file)])
        out = capsys.readouterr().out
        assert "title_count: 2" in out
        assert f"title_sha256: {expected}" in out
        assert f"--expected-title-sha256 {expected}" in out

    def test_collector_title_fingerprint_requires_existing_file(self) -> None:
        from pipeline.run import main

        with pytest.raises(SystemExit) as exc:
            main(["collector-title-fingerprint", "/tmp/definitely_missing_titles.txt"])
        assert exc.value.code == 1

    def test_collector_acceptance_report_passes_when_all_gates_pass(self, tmp_path, monkeypatch, capsys) -> None:
        import pipeline.run as run
        from modules.analytics import validate_collection

        script_path = tmp_path / "mp_analytics_injector.user.js"
        script_path.write_text(
            "\n".join([
                "// ==UserScript==",
                "// @version      5.0",
                "// ==/UserScript==",
                "const SCRIPT_VERSION = '5.0';",
            ]),
            encoding="utf-8",
        )
        monkeypatch.setattr(run, "USERSCRIPT_PATH", script_path)
        monkeypatch.setattr(run, "_collector_process_status", lambda: ("PID 123 running", True))
        monkeypatch.setattr(run, "_collector_port_open", lambda: True)
        monkeypatch.setattr(validate_collection, "latest_published_raw", lambda: None)
        monkeypatch.setattr(validate_collection, "latest_preview_raw", lambda: None)
        monkeypatch.setattr(validate_collection, "latest_diagnostic_raw_for_kinds", lambda kinds: None)
        monkeypatch.setattr(validate_collection, "run_checks", lambda args: [
            validate_collection.Check("latest_expected_article_count", True, "rows=22, expected=22"),
        ])

        run.main(["collector-acceptance-report"])
        out = capsys.readouterr().out
        assert "verdict: PASS" in out
        assert "status: PASS" in out
        assert "install_url: http://127.0.0.1:9876/mp_analytics_injector.user.js" in out
        assert "passed: 1" in out
        assert "failures: none" in out

    def test_collector_acceptance_report_allows_open_port_with_stale_pid(self, tmp_path, monkeypatch, capsys) -> None:
        import pipeline.run as run
        from modules.analytics import validate_collection

        script_path = tmp_path / "mp_analytics_injector.user.js"
        script_path.write_text(
            "\n".join([
                "// ==UserScript==",
                "// @version      5.0",
                "// ==/UserScript==",
                "const SCRIPT_VERSION = '5.0';",
            ]),
            encoding="utf-8",
        )
        monkeypatch.setattr(run, "USERSCRIPT_PATH", script_path)
        monkeypatch.setattr(run, "_collector_process_status", lambda: ("PID 123 not running", False))
        monkeypatch.setattr(run, "_collector_port_open", lambda: True)
        monkeypatch.setattr(validate_collection, "latest_published_raw", lambda: None)
        monkeypatch.setattr(validate_collection, "latest_preview_raw", lambda: None)
        monkeypatch.setattr(validate_collection, "latest_diagnostic_raw_for_kinds", lambda kinds: None)
        monkeypatch.setattr(validate_collection, "run_checks", lambda args: [
            validate_collection.Check("latest_expected_article_count", True, "rows=22, expected=22"),
        ])

        run.main(["collector-acceptance-report"])
        out = capsys.readouterr().out
        assert "verdict: PASS" in out
        assert "PID 123 not running (port open; pid check may be stale or sandboxed)" in out

    def test_collector_acceptance_report_fails_with_actionable_output(self, tmp_path, monkeypatch, capsys) -> None:
        import pipeline.run as run
        from modules.analytics import validate_collection

        script_path = tmp_path / "mp_analytics_injector.user.js"
        script_path.write_text(
            "\n".join([
                "// ==UserScript==",
                "// @version      4.4",
                "// ==/UserScript==",
                "const SCRIPT_VERSION = '4.4';",
            ]),
            encoding="utf-8",
        )
        monkeypatch.setattr(run, "USERSCRIPT_PATH", script_path)
        monkeypatch.setattr(run, "_collector_process_status", lambda: ("PID 123 running", True))
        monkeypatch.setattr(run, "_collector_port_open", lambda: True)
        monkeypatch.setattr(validate_collection, "latest_published_raw", lambda: None)
        monkeypatch.setattr(validate_collection, "latest_preview_raw", lambda: None)
        monkeypatch.setattr(validate_collection, "latest_diagnostic_raw_for_kinds", lambda kinds: None)
        monkeypatch.setattr(validate_collection, "run_checks", lambda args: [
            validate_collection.Check("latest_expected_article_count", False, "rows=2, expected=22"),
        ])

        with pytest.raises(SystemExit) as exc:
            run.main(["collector-acceptance-report"])
        assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "verdict: FAIL" in out
        assert "status: FAIL" in out
        assert "FAIL latest_expected_article_count: rows=2, expected=22" in out
        assert "Tampermonkey 需要安装并运行 v5.0" in out

    def test_collector_acceptance_report_explains_stale_browser_script(self, tmp_path, monkeypatch, capsys) -> None:
        import pipeline.run as run
        from modules.analytics import validate_collection

        script_path = tmp_path / "mp_analytics_injector.user.js"
        script_path.write_text(
            "\n".join([
                "// ==UserScript==",
                "// @version      5.0",
                "// ==/UserScript==",
                "const SCRIPT_VERSION = '5.0';",
            ]),
            encoding="utf-8",
        )
        preview_raw = tmp_path / "20260616_200000_published_records_preview.json"
        preview_raw.write_text(
            validate_collection.json.dumps({
                "page_type": "published_records_preview",
                "page_data": {
                    "article_count": 12,
                    "diagnostics": {"script_version": "4.6"},
                },
                "api_responses": [{"body": {"article_list": [
                    {"title": "旧版误采", "publish_date": "2026-06-16"}
                ]}}],
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        diagnostic_raw = tmp_path / "20260616_200001_diagnostic.json"
        diagnostic_raw.write_text(
            validate_collection.json.dumps({
                "page_type": "diagnostic",
                "page_data": {
                    "kind": "published_records_page_loaded",
                    "diagnostics": {"script_version": "4.6"},
                },
                "api_responses": [],
            }, ensure_ascii=False),
            encoding="utf-8",
        )

        monkeypatch.setattr(run, "USERSCRIPT_PATH", script_path)
        monkeypatch.setattr(run, "_collector_process_status", lambda: ("PID 123 running", True))
        monkeypatch.setattr(run, "_collector_port_open", lambda: True)
        monkeypatch.setattr(validate_collection, "latest_published_raw", lambda: None)
        monkeypatch.setattr(validate_collection, "latest_preview_raw", lambda: preview_raw)
        monkeypatch.setattr(validate_collection, "latest_diagnostic_raw_for_kinds", lambda kinds: diagnostic_raw)
        monkeypatch.setattr(validate_collection, "run_checks", lambda args: [
            validate_collection.Check("preview_script_version", False, "version=4.6, expected=5.0"),
            validate_collection.Check("latest_expected_article_count", False, "rows=0, expected=22"),
            validate_collection.Check("latest_page_session_consistent", False, "sessions={}"),
        ])

        with pytest.raises(SystemExit) as exc:
            run.main(["collector-acceptance-report"])
        assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "最近收到的浏览器数据仍是 v4.6，不是 v5.0" in out
        assert "还没有收到 v5.0 的全量扫描 raw" in out
        assert "当前页预检 v5.0" in out
        assert "刷新后台页面再连续点击预检和全量扫描" in out

    def test_collector_start_daemon_detaches(self, tmp_path, monkeypatch) -> None:
        import pipeline.run as run

        fake_proc = mock.Mock()
        fake_proc.pid = 12345
        fake_proc.poll.return_value = None

        monkeypatch.setattr(run, "COLLECTOR_PID_FILE", tmp_path / "mp_collector.pid")
        monkeypatch.setattr(run, "COLLECTOR_STDOUT_LOG", tmp_path / "mp_collector.stdout.log")

        with (
            mock.patch.object(run, "_collector_port_open", side_effect=[False, True]),
            mock.patch.object(run.subprocess, "Popen", return_value=fake_proc) as popen,
        ):
            run.main(["collector-start", "--daemon"])

        assert (tmp_path / "mp_collector.pid").read_text(encoding="utf-8") == "12345"
        kwargs = popen.call_args.kwargs
        assert kwargs["start_new_session"] is True
        assert kwargs["stdin"] == run.subprocess.DEVNULL
        assert popen.call_args.args[0] == [
            sys.executable,
            "-u",
            "-c",
            "from modules.analytics.collector import start_collector; start_collector()",
        ]

    def test_profile_command(self) -> None:
        from pipeline.run import main
        import sys
        # Mock to avoid actual DB query
        rc = main(["profile"])
        assert rc is None  # prints to stdout, returns None

    def test_strategy_command(self) -> None:
        from pipeline.run import main
        rc = main(["strategy"])
        assert rc is None

    def test_publish_command_requires_file(self) -> None:
        from pipeline.run import main
        with pytest.raises(SystemExit):
            main(["publish"])

    def test_publish_command_with_file(self) -> None:
        from pipeline.run import main
        with pytest.raises(SystemExit) as e:
            main(["publish", "/nonexistent/article.json"])
        assert e.value.code == 1  # file not found

    def test_review_command_requires_file(self) -> None:
        from pipeline.run import main
        with pytest.raises(SystemExit):
            main(["review"])

    def test_review_command_with_file(self) -> None:
        from pipeline.run import main
        with pytest.raises(SystemExit) as e:
            main(["review", "/nonexistent/article.json"])
        assert e.value.code == 1

    def test_unknown_command_exits(self) -> None:
        from pipeline.run import main
        with pytest.raises(SystemExit):
            main(["nonexistent"])


class TestModulesImportable:
    def test_modules_package(self) -> None:
        import modules
        assert modules

    @pytest.mark.parametrize("module_name", ["write", "review", "publish", "analytics", "browser"])
    def test_submodule_importable(self, module_name: str) -> None:
        mod = importlib.import_module(f"modules.{module_name}")
        assert mod is not None


class TestBrowserUserscript:
    def test_userscript_version_is_visible_and_current(self) -> None:
        script = (Path(__file__).parent.parent / "modules/browser/mp_analytics_injector.user.js").read_text(
            encoding="utf-8"
        )

        assert "// @version      5.0" in script
        assert "// @updateURL    http://127.0.0.1:9876/mp_analytics_injector.user.js" in script
        assert "// @downloadURL  http://127.0.0.1:9876/mp_analytics_injector.user.js" in script
        assert "const SCRIPT_VERSION = '5.0';" in script
        assert "'📊 v' + SCRIPT_VERSION" in script
        assert "'🔎 当前页预检 v' + SCRIPT_VERSION" in script

    def test_full_scan_returns_to_first_page_without_adding_stale_cached_api(self) -> None:
        script = (Path(__file__).parent.parent / "modules/browser/mp_analytics_injector.user.js").read_text(
            encoding="utf-8"
        )

        assert "await returnToFirstPage(btn, MAX_PAGE_TURNS, SCAN_PAGE_DELAY_MS);" in script
        assert "const initialAdded = await seedScanFromCurrentPage('page_1');" in script
        assert "started_from_current_page: false" in script
        assert "scan_mode: 'from_first_page'" in script
        assert "const SCAN_STATE_KEY = 'mp_collector_full_scan_state_v1';" in script
        assert "persistScanState({" in script
        assert "resumeScanIfNeeded(btn);" in script
        assert "seedScanFromCollectedResponses() + seedScanFromDOM()" not in script
        assert "function seedScanFromCurrentPage(label)" in script
        assert "seeded from cached current-page API" in script
        assert "seeded from visible DOM fallback" in script

    def test_scan_api_responses_are_queued_as_page_fallback(self) -> None:
        script = (Path(__file__).parent.parent / "modules/browser/mp_analytics_injector.user.js").read_text(
            encoding="utf-8"
        )

        assert "queueScanApiArticles(articles, url);" in script
        assert "seeded from live page API" in script
        assert "scanPageApiArticles = [];" in script
        assert "page_sources" in script
        assert "function cachedResponse(url, status, body)" in script
        assert "captured_href: canonicalPageHref(window.location.href)" in script
        assert "current_page_cached_responses" in script

    def test_published_page_sends_diagnostics_for_load_and_scan_start(self) -> None:
        script = (Path(__file__).parent.parent / "modules/browser/mp_analytics_injector.user.js").read_text(
            encoding="utf-8"
        )

        assert "function sendDiagnostic(kind, extra)" in script
        assert "sendDiagnostic('published_records_page_loaded')" in script
        assert "sendDiagnostic('published_records_scan_started'" in script
        assert "page_type: 'diagnostic'" in script

    def test_current_page_preview_reports_without_importing(self) -> None:
        script = (Path(__file__).parent.parent / "modules/browser/mp_analytics_injector.user.js").read_text(
            encoding="utf-8"
        )

        assert "function addCurrentPagePreviewButton()" in script
        assert "page_type: 'published_records_preview'" in script
        assert "published_records_current_page_preview" in script
        assert "current_page_preview" in script

    def test_scan_dom_candidates_are_grouped_by_record_container(self) -> None:
        script = (Path(__file__).parent.parent / "modules/browser/mp_analytics_injector.user.js").read_text(
            encoding="utf-8"
        )

        assert "function selectDomArticleCandidates(groups)" in script
        assert "function articleRecordContainerForElement(el)" in script
        assert "domRecordKey(record, article, recordIds" in script
        assert "group_size" in script
        assert "dom_merged" in script
        assert "currentPageSizeLimit" not in script


class TestAnalyticsImport:
    def test_schema_connect_db_sets_busy_timeout(self, tmp_path, monkeypatch) -> None:
        from modules.analytics import schema

        monkeypatch.setattr(schema, "DB_PATH", tmp_path / "mp_analytics.db")
        conn = schema.connect_db()
        try:
            timeout_ms = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        finally:
            conn.close()

        assert timeout_ms == schema.SQLITE_BUSY_TIMEOUT_MS

    def test_strategy_skips_articles_without_publish_date(self, tmp_path, monkeypatch) -> None:
        from modules.analytics import schema
        from modules.analytics import strategy as strategy_mod

        db_path = tmp_path / "mp_analytics.db"
        monkeypatch.setattr(schema, "DB_PATH", db_path)
        monkeypatch.setattr(strategy_mod, "DB_PATH", db_path)
        schema.init_db()

        conn = schema.connect_db()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO articles (msg_id, item_idx, title, publish_date) VALUES (?, ?, ?, ?)",
                ("dom_blank_date", 1, "无发布日期文章", ""),
            )
            article_id = cur.lastrowid
            cur.execute(
                """
                INSERT INTO article_daily_metrics (article_id, ref_date, total_read_uv, read_uv_ratio, share_uv)
                VALUES (?, ?, ?, 0, 0)
                """,
                (article_id, "2026-06-17", 7),
            )
            conn.commit()
        finally:
            conn.close()

        result = strategy_mod.generate_strategy()

        assert result["insights"] == ["已采集文章缺少发布日期，暂时无法生成日均阅读策略。"]

    def test_published_records_without_msg_id_uses_stable_fallback(self, tmp_path, monkeypatch) -> None:
        from modules.analytics import schema

        monkeypatch.setattr(schema, "DB_PATH", tmp_path / "mp_analytics.db")
        monkeypatch.setattr(schema, "RAW_DIR", tmp_path / "mp_raw")
        schema.init_db()

        payload = {
            "api_responses": [{
                "body": {
                    "article_list": [{
                        "title": "DOM 兜底文章",
                        "publish_date": "2026/06/16",
                        "total_reads": "1.2万",
                    }]
                }
            }]
        }

        assert schema.import_published_records(payload) == (1, 0)
        assert schema.import_published_records(payload) == (0, 1)

        conn = schema.sqlite3.connect(str(schema.DB_PATH))
        conn.row_factory = schema.sqlite3.Row
        try:
            row = conn.execute("""
                SELECT a.msg_id, a.publish_date, d.total_read_uv
                FROM articles a
                JOIN article_daily_metrics d ON d.article_id = a.id
            """).fetchone()
        finally:
            conn.close()

        assert row["msg_id"].startswith("dom_")
        assert row["publish_date"] == "2026-06-16"
        assert row["total_read_uv"] == 12000

    def test_published_records_without_msg_id_or_date_reimports_idempotently(self, tmp_path, monkeypatch) -> None:
        from modules.analytics import schema

        monkeypatch.setattr(schema, "DB_PATH", tmp_path / "mp_analytics.db")
        monkeypatch.setattr(schema, "RAW_DIR", tmp_path / "mp_raw")
        schema.init_db()

        payload = {
            "api_responses": [{
                "body": {
                    "article_list": [{
                        "title": "DOM 无日期兜底文章",
                        "publish_date": "",
                        "total_reads": "7",
                    }]
                }
            }]
        }

        assert schema.import_published_records(payload) == (1, 0)
        assert schema.import_published_records(payload) == (0, 1)

        conn = schema.sqlite3.connect(str(schema.DB_PATH))
        conn.row_factory = schema.sqlite3.Row
        try:
            rows = conn.execute("SELECT msg_id, title, publish_date FROM articles").fetchall()
        finally:
            conn.close()

        assert len(rows) == 1
        assert rows[0]["msg_id"].startswith("dom_")
        assert rows[0]["title"] == "DOM 无日期兜底文章"
        assert rows[0]["publish_date"] == ""

    def test_published_records_dedupes_within_payload_and_reimport(self, tmp_path, monkeypatch) -> None:
        from modules.analytics import schema

        monkeypatch.setattr(schema, "DB_PATH", tmp_path / "mp_analytics.db")
        monkeypatch.setattr(schema, "RAW_DIR", tmp_path / "mp_raw")
        schema.init_db()

        article = {
            "msg_id": "2247484999",
            "item_idx": 1,
            "title": "重复导入文章",
            "publish_date": "2026/06/16",
            "total_reads": "1.5万",
        }
        payload = {
            "api_responses": [{
                "body": {
                    "article_list": [article, dict(article)]
                }
            }]
        }

        assert schema.import_published_records(payload) == (1, 0)
        assert schema.import_published_records(payload) == (0, 1)

        conn = schema.sqlite3.connect(str(schema.DB_PATH))
        conn.row_factory = schema.sqlite3.Row
        try:
            article_count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
            metric_count = conn.execute("SELECT COUNT(*) FROM article_daily_metrics").fetchone()[0]
            row = conn.execute("""
                SELECT a.msg_id, a.title, a.publish_date, d.total_read_uv
                FROM articles a
                JOIN article_daily_metrics d ON d.article_id = a.id
            """).fetchone()
        finally:
            conn.close()

        assert article_count == 1
        assert metric_count == 1
        assert row["msg_id"] == "2247484999"
        assert row["publish_date"] == "2026-06-16"
        assert row["total_read_uv"] == 15000

    def test_published_records_preserves_same_msg_id_different_item_idx(self, tmp_path, monkeypatch) -> None:
        from modules.analytics import schema

        monkeypatch.setattr(schema, "DB_PATH", tmp_path / "mp_analytics.db")
        monkeypatch.setattr(schema, "RAW_DIR", tmp_path / "mp_raw")
        schema.init_db()

        articles = [
            {
                "msg_id": "2247485000",
                "item_idx": 1,
                "title": "同群发主图文",
                "publish_date": "2026/06/16",
                "total_reads": "101",
            },
            {
                "msg_id": "2247485000",
                "item_idx": 2,
                "title": "同群发次图文",
                "publish_date": "2026/06/16",
                "total_reads": "202",
            },
        ]
        payload = {"api_responses": [{"body": {"article_list": articles}}]}

        assert schema.import_published_records(payload) == (2, 0)
        assert schema.import_published_records(payload) == (0, 2)

        conn = schema.sqlite3.connect(str(schema.DB_PATH))
        conn.row_factory = schema.sqlite3.Row
        try:
            rows = conn.execute("""
                SELECT a.msg_id, a.item_idx, a.title, d.total_read_uv
                FROM articles a
                JOIN article_daily_metrics d ON d.article_id = a.id
                ORDER BY a.item_idx
            """).fetchall()
        finally:
            conn.close()

        assert [dict(row) for row in rows] == [
            {"msg_id": "2247485000", "item_idx": 1, "title": "同群发主图文", "total_read_uv": 101},
            {"msg_id": "2247485000", "item_idx": 2, "title": "同群发次图文", "total_read_uv": 202},
        ]

    def test_published_records_preserves_same_title_date_with_different_msg_ids(self, tmp_path, monkeypatch) -> None:
        from modules.analytics import schema

        monkeypatch.setattr(schema, "DB_PATH", tmp_path / "mp_analytics.db")
        monkeypatch.setattr(schema, "RAW_DIR", tmp_path / "mp_raw")
        schema.init_db()

        articles = [
            {
                "msg_id": "2247483698",
                "item_idx": 1,
                "title": "什么是广告超播？",
                "publish_date": "2021-10-03",
                "total_reads": 0,
            },
            {
                "msg_id": "2247483667",
                "item_idx": 1,
                "title": "什么是广告超播？",
                "publish_date": "2021-10-03",
                "total_reads": 0,
            },
        ]
        payload = {"api_responses": [{"body": {"article_list": articles}}]}

        assert schema.import_published_records(payload) == (2, 0)
        assert schema.import_published_records(payload) == (0, 2)

        conn = schema.sqlite3.connect(str(schema.DB_PATH))
        conn.row_factory = schema.sqlite3.Row
        try:
            rows = conn.execute("""
                SELECT msg_id, item_idx, title, publish_date
                FROM articles
                ORDER BY msg_id
            """).fetchall()
        finally:
            conn.close()

        assert [dict(row) for row in rows] == [
            {
                "msg_id": "2247483667",
                "item_idx": 1,
                "title": "什么是广告超播？",
                "publish_date": "2021-10-03",
            },
            {
                "msg_id": "2247483698",
                "item_idx": 1,
                "title": "什么是广告超播？",
                "publish_date": "2021-10-03",
            },
        ]

    def test_content_analysis_preserves_same_msg_id_different_item_idx(self, tmp_path, monkeypatch) -> None:
        from modules.analytics import schema

        monkeypatch.setattr(schema, "DB_PATH", tmp_path / "mp_analytics.db")
        monkeypatch.setattr(schema, "RAW_DIR", tmp_path / "mp_raw")
        schema.init_db()

        parsed = {
            "articles": [
                {"msg_id": "2247485001", "item_idx": 1, "title": "内容主图文", "publish_date": "2026-06-16"},
                {"msg_id": "2247485001", "item_idx": 2, "title": "内容次图文", "publish_date": "2026-06-16"},
            ],
            "daily_metrics": [
                {"msg_id": "2247485001", "item_idx": 1, "ref_date": "2026-06-17", "total_read_uv": 11, "read_uv_ratio": 0, "share_uv": 0},
                {"msg_id": "2247485001", "item_idx": 2, "ref_date": "2026-06-17", "total_read_uv": 22, "read_uv_ratio": 0, "share_uv": 0},
            ],
        }

        schema.store_parsed(parsed, tmp_path / "raw.json")
        schema.store_parsed(parsed, tmp_path / "raw.json")

        conn = schema.sqlite3.connect(str(schema.DB_PATH))
        conn.row_factory = schema.sqlite3.Row
        try:
            rows = conn.execute("""
                SELECT a.item_idx, a.title, d.total_read_uv
                FROM articles a
                JOIN article_daily_metrics d ON d.article_id = a.id
                ORDER BY a.item_idx
            """).fetchall()
        finally:
            conn.close()

        assert [dict(row) for row in rows] == [
            {"item_idx": 1, "title": "内容主图文", "total_read_uv": 11},
            {"item_idx": 2, "title": "内容次图文", "total_read_uv": 22},
        ]

    def test_init_db_migrates_articles_from_msg_id_unique_to_msg_item_unique(self, tmp_path, monkeypatch) -> None:
        from modules.analytics import schema

        monkeypatch.setattr(schema, "DB_PATH", tmp_path / "mp_analytics.db")
        monkeypatch.setattr(schema, "RAW_DIR", tmp_path / "mp_raw")

        conn = schema.sqlite3.connect(str(schema.DB_PATH))
        try:
            conn.execute("""
                CREATE TABLE articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    msg_id TEXT NOT NULL UNIQUE,
                    item_idx INTEGER DEFAULT 1,
                    title TEXT NOT NULL,
                    publish_date TEXT,
                    first_seen TEXT,
                    last_updated TEXT
                )
            """)
            conn.execute("""
                INSERT INTO articles (msg_id, item_idx, title, publish_date)
                VALUES ('2247485002', 1, '迁移前文章', '2026-06-16')
            """)
            conn.execute("""
                CREATE TABLE trend_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article_id INTEGER NOT NULL,
                    snapshot_date TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value REAL DEFAULT 0,
                    captured_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                    FOREIGN KEY(article_id) REFERENCES articles(id),
                    UNIQUE(article_id, snapshot_date, metric_name)
                )
            """)
            conn.execute("""
                INSERT INTO trend_snapshots (article_id, snapshot_date, metric_name, metric_value)
                VALUES (1, '2026-06-16', 'read_uv_trend', 10)
            """)
            conn.commit()
        finally:
            conn.close()

        schema.init_db()
        payload = {"api_responses": [{"body": {"article_list": [
            {
                "msg_id": "2247485002",
                "item_idx": 2,
                "title": "迁移后同群发次图文",
                "publish_date": "2026-06-16",
                "total_reads": 20,
            }
        ]}}]}

        assert schema.import_published_records(payload) == (1, 0)

        conn = schema.sqlite3.connect(str(schema.DB_PATH))
        try:
            count = conn.execute("SELECT COUNT(*) FROM articles WHERE msg_id='2247485002'").fetchone()[0]
            trend_fk = conn.execute("PRAGMA foreign_key_list(trend_snapshots)").fetchone()
            trend_count = conn.execute("SELECT COUNT(*) FROM trend_snapshots WHERE article_id=1").fetchone()[0]
        finally:
            conn.close()

        assert count == 2
        assert trend_fk[2] == "articles"
        assert trend_count == 1

    def test_init_db_recovers_interrupted_article_identity_migration(self, tmp_path, monkeypatch) -> None:
        from modules.analytics import schema

        monkeypatch.setattr(schema, "DB_PATH", tmp_path / "mp_analytics.db")
        monkeypatch.setattr(schema, "RAW_DIR", tmp_path / "mp_raw")

        conn = schema.sqlite3.connect(str(schema.DB_PATH))
        try:
            conn.execute("""
                CREATE TABLE articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    msg_id TEXT NOT NULL,
                    item_idx INTEGER NOT NULL DEFAULT 1,
                    title TEXT NOT NULL,
                    publish_date TEXT,
                    first_seen TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                    last_updated TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                    UNIQUE(msg_id, item_idx)
                )
            """)
            conn.execute("""
                CREATE TABLE articles_old (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    msg_id TEXT NOT NULL UNIQUE,
                    item_idx INTEGER DEFAULT 1,
                    title TEXT NOT NULL,
                    publish_date TEXT,
                    first_seen TEXT,
                    last_updated TEXT
                )
            """)
            conn.execute("""
                INSERT INTO articles_old (id, msg_id, item_idx, title, publish_date)
                VALUES (7, '2247485003', 1, '中断迁移文章', '2026-06-16')
            """)
            conn.execute("""
                CREATE TABLE trend_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article_id INTEGER NOT NULL,
                    snapshot_date TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value REAL DEFAULT 0,
                    captured_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                    FOREIGN KEY(article_id) REFERENCES "articles_old"(id),
                    UNIQUE(article_id, snapshot_date, metric_name)
                )
            """)
            conn.execute("""
                INSERT INTO trend_snapshots (article_id, snapshot_date, metric_name, metric_value)
                VALUES (7, '2026-06-16', 'read_uv_trend', 70)
            """)
            conn.commit()
        finally:
            conn.close()

        schema.init_db()

        conn = schema.sqlite3.connect(str(schema.DB_PATH))
        conn.row_factory = schema.sqlite3.Row
        try:
            old_table = conn.execute("""
                SELECT 1 FROM sqlite_master WHERE type='table' AND name='articles_old'
            """).fetchone()
            row = conn.execute("SELECT id, msg_id, item_idx, title FROM articles").fetchone()
            trend_fk = conn.execute("PRAGMA foreign_key_list(trend_snapshots)").fetchone()
            trend = conn.execute("SELECT article_id, metric_value FROM trend_snapshots").fetchone()
        finally:
            conn.close()

        assert old_table is None
        assert dict(row) == {
            "id": 7,
            "msg_id": "2247485003",
            "item_idx": 1,
            "title": "中断迁移文章",
        }
        assert trend_fk[2] == "articles"
        assert tuple(trend) == (7, 70)

    def test_traffic_sources_are_deduped_and_blank_rows_skipped(self, tmp_path, monkeypatch) -> None:
        from modules.analytics import schema

        monkeypatch.setattr(schema, "DB_PATH", tmp_path / "mp_analytics.db")
        monkeypatch.setattr(schema, "RAW_DIR", tmp_path / "mp_raw")
        schema.init_db()

        parsed = {
            "traffic_sources": [
                {"ref_date": "", "source_type": "", "source_name": "", "read_uv": 999, "read_uv_ratio": 0},
                {"ref_date": "2026-06-16", "source_type": "17", "source_name": "名片分享", "read_uv": 10, "read_uv_ratio": 0.1},
                {"ref_date": "2026-06-16", "source_type": "17", "source_name": "名片分享", "read_uv": 12, "read_uv_ratio": 0.2},
            ]
        }

        schema.store_parsed(parsed, tmp_path / "raw.json")
        schema.store_parsed(parsed, tmp_path / "raw.json")

        conn = schema.sqlite3.connect(str(schema.DB_PATH))
        conn.row_factory = schema.sqlite3.Row
        try:
            rows = conn.execute("SELECT ref_date, source_type, read_uv FROM traffic_sources").fetchall()
        finally:
            conn.close()

        assert len(rows) == 1
        assert rows[0]["ref_date"] == "2026-06-16"
        assert rows[0]["source_type"] == "17"
        assert rows[0]["read_uv"] == 12

    def test_collection_validator_synthetic_checks_pass(self) -> None:
        from modules.analytics import validate_collection

        checks = validate_collection.synthetic_import_checks()
        assert all(check.passed for check in checks)

    def test_collection_validator_detects_duplicate_raw_articles(self) -> None:
        from modules.analytics import validate_collection

        article = {
            "msg_id": "2247485001",
            "item_idx": 1,
            "title": "重复 raw",
            "publish_date": "2026-06-16",
        }

        duplicates = validate_collection.duplicate_keys([article, dict(article)])
        assert duplicates == ["id:2247485001:1"]

    def test_collection_validator_accepts_preview_raw(self, tmp_path, monkeypatch) -> None:
        from modules.analytics import schema, validate_collection

        monkeypatch.setattr(schema, "RAW_DIR", tmp_path)
        articles = [{
            "msg_id": str(2247486000 + i),
            "item_idx": 1,
            "title": f"预检文章 {i}",
            "publish_date": "2026-06-16",
        } for i in range(10)]
        raw = {
            "page_type": "published_records_preview",
            "page_data": {
                "source": "cached_api",
                "article_count": 10,
                "diagnostics": {"script_version": "5.0"},
            },
            "api_responses": [{
                "body": {"article_list": articles}
            }],
        }
        (tmp_path / "20260616_170000_published_records_preview.json").write_text(
            validate_collection.json.dumps(raw, ensure_ascii=False),
            encoding="utf-8",
        )

        checks = validate_collection.validate_latest_preview(
            expected_count=10,
            expected_version="5.0",
            strict=True,
        )
        assert all(check.passed for check in checks)

    def test_collection_validator_checks_expected_page_counts(self, tmp_path, monkeypatch) -> None:
        from modules.analytics import schema, validate_collection

        monkeypatch.setattr(schema, "RAW_DIR", tmp_path)
        articles = [{
            "msg_id": str(2247487000 + i),
            "item_idx": 1,
            "title": f"全量文章 {i:02d}",
            "publish_date": "2026-06-16",
        } for i in range(1, 23)]
        raw = {
            "page_type": "published_records",
            "page_data": {
                "article_count": 22,
                "scan_mode": "from_first_page",
                "started_from_current_page": False,
                "page_sources": [
                    {"label": "page_1", "source": "cached_api", "candidates": 10, "added": 10, "total": 10},
                    {"label": "page_turn_1", "source": "cached_api", "candidates": 10, "added": 10, "total": 20},
                    {"label": "page_turn_2", "source": "cached_api", "candidates": 2, "added": 2, "total": 22},
                ],
                "diagnostics": {"script_version": "5.0"},
            },
            "api_responses": [{"body": {"article_list": articles}}],
        }
        (tmp_path / "20260616_180000_published_records.json").write_text(
            validate_collection.json.dumps(raw, ensure_ascii=False),
            encoding="utf-8",
        )

        checks = validate_collection.validate_latest_raw(
            expected_count=22,
            expected_page_counts=[10, 10, 2],
            expected_version="5.0",
            strict=True,
        )
        assert all(check.passed for check in checks)

        wrong_checks = validate_collection.validate_latest_raw(
            expected_count=22,
            expected_page_counts=[10, 10, 3],
            expected_version="5.0",
            strict=True,
        )
        page_count_check = next(check for check in wrong_checks if check.name == "latest_expected_page_counts")
        assert page_count_check.passed is False

    def test_collection_validator_rejects_old_page_source_labels(self, tmp_path, monkeypatch) -> None:
        from modules.analytics import schema, validate_collection

        monkeypatch.setattr(schema, "RAW_DIR", tmp_path)
        articles = [{
            "msg_id": str(2247487700 + i),
            "item_idx": 1,
            "title": f"标签文章 {i:02d}",
            "publish_date": "2026-06-16",
        } for i in range(1, 23)]
        raw = {
            "page_type": "published_records",
            "page_data": {
                "article_count": 22,
                "scan_mode": "from_first_page",
                "started_from_current_page": False,
                "page_sources": [
                    {"label": "current", "source": "cached_api", "candidates": 10, "added": 10, "total": 10},
                    {"label": "page_turn_1", "source": "cached_api", "candidates": 10, "added": 10, "total": 20},
                    {"label": "page_turn_2", "source": "cached_api", "candidates": 2, "added": 2, "total": 22},
                ],
                "diagnostics": {"script_version": "5.0"},
            },
            "api_responses": [{"body": {"article_list": articles}}],
        }
        (tmp_path / "20260616_180000_published_records.json").write_text(
            validate_collection.json.dumps(raw, ensure_ascii=False),
            encoding="utf-8",
        )

        checks = validate_collection.validate_latest_raw(
            expected_count=22,
            expected_page_counts=[10, 10, 2],
            expected_version="5.0",
            strict=True,
        )
        page_count_check = next(check for check in checks if check.name == "latest_expected_page_counts")
        assert page_count_check.passed is False
        assert "labels=['current', 'page_turn_1', 'page_turn_2']" in page_count_check.detail

    def test_collection_validator_rejects_inconsistent_page_source_totals(self, tmp_path, monkeypatch) -> None:
        from modules.analytics import schema, validate_collection

        monkeypatch.setattr(schema, "RAW_DIR", tmp_path)
        articles = [{
            "msg_id": str(2247487800 + i),
            "item_idx": 1,
            "title": f"累计文章 {i:02d}",
            "publish_date": "2026-06-16",
        } for i in range(1, 23)]
        raw = {
            "page_type": "published_records",
            "page_data": {
                "article_count": 22,
                "scan_mode": "from_first_page",
                "started_from_current_page": False,
                "page_sources": [
                    {"label": "page_1", "source": "cached_api", "candidates": 10, "added": 10, "total": 10},
                    {"label": "page_turn_1", "source": "cached_api", "candidates": 10, "added": 10, "total": 21},
                    {"label": "page_turn_2", "source": "cached_api", "candidates": 2, "added": 2, "total": 22},
                ],
                "diagnostics": {"script_version": "5.0"},
            },
            "api_responses": [{"body": {"article_list": articles}}],
        }
        (tmp_path / "20260616_180000_published_records.json").write_text(
            validate_collection.json.dumps(raw, ensure_ascii=False),
            encoding="utf-8",
        )

        checks = validate_collection.validate_latest_raw(
            expected_count=22,
            expected_page_counts=[10, 10, 2],
            expected_version="5.0",
            strict=True,
        )
        consistency = next(check for check in checks if check.name == "latest_page_sources_consistent")
        assert consistency.passed is False
        assert "page=2:total=21,expected=20" in consistency.detail

    def test_collection_validator_rejects_current_page_scan_mode_in_strict_raw(self, tmp_path, monkeypatch) -> None:
        from modules.analytics import schema, validate_collection

        monkeypatch.setattr(schema, "RAW_DIR", tmp_path)
        articles = [{
            "msg_id": str(2247487600 + i),
            "item_idx": 1,
            "title": f"旧扫描文章 {i:02d}",
            "publish_date": "2026-06-16",
        } for i in range(1, 23)]
        raw = {
            "page_type": "published_records",
            "page_data": {
                "article_count": 22,
                "scan_mode": "from_current_page",
                "started_from_current_page": True,
                "page_sources": [
                    {"label": "current", "source": "cached_api", "candidates": 10, "added": 10, "total": 10},
                    {"label": "page_turn_1", "source": "cached_api", "candidates": 10, "added": 10, "total": 20},
                    {"label": "page_turn_2", "source": "cached_api", "candidates": 2, "added": 2, "total": 22},
                ],
                "diagnostics": {"script_version": "5.0"},
            },
            "api_responses": [{"body": {"article_list": articles}}],
        }
        (tmp_path / "20260616_180000_published_records.json").write_text(
            validate_collection.json.dumps(raw, ensure_ascii=False),
            encoding="utf-8",
        )

        checks = validate_collection.validate_latest_raw(
            expected_count=22,
            expected_page_counts=[10, 10, 2],
            expected_version="5.0",
            strict=True,
        )
        scan_mode_check = next(check for check in checks if check.name == "latest_scan_mode_from_first_page")
        assert scan_mode_check.passed is False
        assert "from_current_page" in scan_mode_check.detail

    def test_collection_validator_checks_expected_titles_file(self, tmp_path, monkeypatch) -> None:
        from modules.analytics import schema, validate_collection

        monkeypatch.setattr(schema, "RAW_DIR", tmp_path)
        articles = [
            {
                "msg_id": "2247487201",
                "item_idx": 1,
                "title": "后台标题 A",
                "publish_date": "2026-06-16",
            },
            {
                "msg_id": "2247487202",
                "item_idx": 1,
                "title": "后台标题 B",
                "publish_date": "2026-06-16",
            },
        ]
        raw = {
            "page_type": "published_records",
            "page_data": {
                "article_count": 2,
                "scan_mode": "from_first_page",
                "started_from_current_page": False,
                "page_sources": [{"label": "page_1", "source": "cached_api", "candidates": 2, "added": 2, "total": 2}],
                "diagnostics": {"script_version": "5.0"},
            },
            "api_responses": [{"body": {"article_list": articles}}],
        }
        (tmp_path / "20260616_180000_published_records.json").write_text(
            validate_collection.json.dumps(raw, ensure_ascii=False),
            encoding="utf-8",
        )
        expected_titles = tmp_path / "expected_titles.txt"
        expected_titles.write_text("后台标题 A\n后台标题 B\n", encoding="utf-8")
        wrong_titles = tmp_path / "wrong_titles.json"
        wrong_titles.write_text(
            validate_collection.json.dumps(["后台标题 B", "后台标题 A"], ensure_ascii=False),
            encoding="utf-8",
        )

        checks = validate_collection.validate_latest_raw(
            expected_count=2,
            expected_titles_path=expected_titles,
            expected_version="5.0",
            strict=True,
        )
        assert all(check.passed for check in checks)

        title_sha256 = validate_collection.title_fingerprint(["后台标题 A", "后台标题 B"])
        hash_checks = validate_collection.validate_latest_raw(
            expected_count=2,
            expected_title_sha256=title_sha256,
            expected_version="5.0",
            strict=True,
        )
        assert all(check.passed for check in hash_checks)

        wrong_hash_checks = validate_collection.validate_latest_raw(
            expected_count=2,
            expected_title_sha256=validate_collection.title_fingerprint(["后台标题 B", "后台标题 A"]),
            expected_version="5.0",
            strict=True,
        )
        hash_check = next(check for check in wrong_hash_checks if check.name == "latest_expected_title_sha256")
        assert hash_check.passed is False
        assert f"actual_sha256={title_sha256}" in hash_check.detail

        wrong_checks = validate_collection.validate_latest_raw(
            expected_count=2,
            expected_titles_path=wrong_titles,
            expected_version="5.0",
            strict=True,
        )
        title_check = next(check for check in wrong_checks if check.name == "latest_expected_titles")
        assert title_check.passed is False
        assert "first_mismatch=index=1" in title_check.detail

    def test_collection_validator_reports_missing_expected_titles_file(self) -> None:
        from modules.analytics import validate_collection

        check = validate_collection.expected_titles_check([], Path("/tmp/definitely_missing_expected_titles.txt"))
        assert check.name == "latest_expected_titles"
        assert check.passed is False
        assert "error=" in check.detail

    def test_collection_validator_reimports_latest_raw_idempotently(self, tmp_path, monkeypatch) -> None:
        from modules.analytics import schema, validate_collection

        monkeypatch.setattr(schema, "RAW_DIR", tmp_path)
        articles = [
            {
                "msg_id": "2247487101",
                "item_idx": 1,
                "title": "真实 raw 幂等文章 1",
                "publish_date": "2026-06-16",
                "total_reads": 11,
            },
            {
                "msg_id": "2247487102",
                "item_idx": 1,
                "title": "真实 raw 幂等文章 2",
                "publish_date": "2026-06-16",
                "total_reads": 12,
            },
        ]
        raw = {
            "page_type": "published_records",
            "page_data": {
                "article_count": 3,
                "diagnostics": {"script_version": "5.0"},
            },
            "api_responses": [{"body": {"article_list": articles + [dict(articles[0])]}}],
        }
        (tmp_path / "20260616_180000_published_records.json").write_text(
            validate_collection.json.dumps(raw, ensure_ascii=False),
            encoding="utf-8",
        )

        checks = validate_collection.latest_raw_import_checks(strict=True)
        by_name = {check.name: check for check in checks}
        assert by_name["latest_import_raw_file"].detail == "20260616_180000_published_records.json"
        assert by_name["latest_import_first_import"].detail.startswith("result=(2, 0)")
        assert by_name["latest_import_second_import"].detail.startswith("result=(0, 2)")
        assert by_name["latest_import_article_count"].detail.startswith("count=2")
        assert by_name["latest_import_duplicate_articles"].passed is True
        assert by_name["latest_import_duplicate_metrics"].passed is True

    def test_collection_validator_checks_latest_raw_database_alignment(self, tmp_path, monkeypatch) -> None:
        from modules.analytics import schema, validate_collection

        monkeypatch.setattr(schema, "RAW_DIR", tmp_path / "mp_raw")
        monkeypatch.setattr(schema, "DB_PATH", tmp_path / "mp_analytics.db")
        schema.RAW_DIR.mkdir(parents=True)
        article = {
            "msg_id": "2247487151",
            "item_idx": 1,
            "title": "生产库对齐文章",
            "publish_date": "2026-06-16",
            "total_reads": 15,
        }
        raw = {
            "page_type": "published_records",
            "page_data": {
                "article_count": 1,
                "diagnostics": {"script_version": "5.0"},
            },
            "api_responses": [{"body": {"article_list": [article]}}],
        }
        (schema.RAW_DIR / "20260616_180000_published_records.json").write_text(
            validate_collection.json.dumps(raw, ensure_ascii=False),
            encoding="utf-8",
        )
        schema.init_db()

        missing_checks = validate_collection.latest_raw_database_alignment_checks(strict=True)
        missing_by_name = {check.name: check for check in missing_checks}
        assert missing_by_name["latest_raw_db_articles_present"].passed is False
        assert "missing=1" in missing_by_name["latest_raw_db_articles_present"].detail

        assert schema.import_published_records(raw) == (1, 0)
        checks = validate_collection.latest_raw_database_alignment_checks(strict=True)
        by_name = {check.name: check for check in checks}
        assert by_name["latest_raw_db_articles_present"].passed is True
        assert by_name["latest_raw_db_metrics_present"].passed is True

    def test_collection_validator_rejects_stale_preview_raw(self, tmp_path, monkeypatch) -> None:
        from modules.analytics import schema, validate_collection

        monkeypatch.setattr(schema, "RAW_DIR", tmp_path)
        raw = {
            "page_type": "published_records_preview",
            "page_data": {
                "source": "cached_api",
                "article_count": 1,
                "diagnostics": {"script_version": "5.0"},
            },
            "api_responses": [{
                "body": {"article_list": [{
                    "msg_id": "2247486001",
                    "item_idx": 1,
                    "title": "过期预检文章",
                    "publish_date": "2026-06-16",
                }]}
            }],
        }
        path = tmp_path / "20260616_170000_published_records_preview.json"
        path.write_text(validate_collection.json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        stale_time = validate_collection.time.time() - 120
        os.utime(path, (stale_time, stale_time))

        checks = validate_collection.validate_latest_preview(
            expected_count=1,
            expected_version="5.0",
            strict=True,
            max_age_seconds=60,
        )
        freshness = next(check for check in checks if check.name == "preview_raw_fresh")
        assert freshness.passed is False

    def test_collection_validator_accepts_fresh_diagnostic_raw(self, tmp_path, monkeypatch) -> None:
        from modules.analytics import schema, validate_collection

        monkeypatch.setattr(schema, "RAW_DIR", tmp_path)
        page_loaded = {
            "page_type": "diagnostic",
            "page_data": {
                "kind": "published_records_page_loaded",
                "diagnostics": {"script_version": "5.0"},
            },
            "api_responses": [],
        }
        scan_started = {
            "page_type": "diagnostic",
            "page_data": {
                "kind": "published_records_scan_started",
                "diagnostics": {"script_version": "5.0"},
            },
            "api_responses": [],
        }
        (tmp_path / "20260616_170000_diagnostic.json").write_text(
            validate_collection.json.dumps(page_loaded, ensure_ascii=False),
            encoding="utf-8",
        )
        (tmp_path / "20260616_170001_diagnostic.json").write_text(
            validate_collection.json.dumps(scan_started, ensure_ascii=False),
            encoding="utf-8",
        )

        checks = validate_collection.validate_latest_diagnostic(
            expected_version="5.0",
            strict=True,
            max_age_seconds=60,
            expected_kinds=["published_records_page_loaded", "published_records_scan_started"],
        )
        assert all(check.passed for check in checks)

    def test_collection_validator_requires_all_expected_diagnostic_kinds(self, tmp_path, monkeypatch) -> None:
        from modules.analytics import schema, validate_collection

        monkeypatch.setattr(schema, "RAW_DIR", tmp_path)
        page_loaded = {
            "page_type": "diagnostic",
            "page_data": {
                "kind": "published_records_page_loaded",
                "diagnostics": {"script_version": "5.0"},
            },
            "api_responses": [],
        }
        (tmp_path / "20260616_170000_diagnostic.json").write_text(
            validate_collection.json.dumps(page_loaded, ensure_ascii=False),
            encoding="utf-8",
        )

        checks = validate_collection.validate_latest_diagnostic(
            expected_version="5.0",
            strict=True,
            expected_kinds=["published_records_page_loaded", "published_records_scan_started"],
        )
        kinds_check = next(check for check in checks if check.name == "diagnostic_expected_kinds_present")
        assert kinds_check.passed is False
        assert "published_records_scan_started" in kinds_check.detail

    def test_collection_validator_selects_latest_matching_diagnostic_kind(self, tmp_path, monkeypatch) -> None:
        from modules.analytics import schema, validate_collection

        monkeypatch.setattr(schema, "RAW_DIR", tmp_path)
        page_loaded = {
            "page_type": "diagnostic",
            "page_data": {
                "kind": "published_records_page_loaded",
                "diagnostics": {"script_version": "5.0"},
            },
            "api_responses": [],
        }
        manual_test = {
            "page_type": "diagnostic",
            "page_data": {
                "kind": "manual_connectivity_test",
                "diagnostics": {"script_version": "5.0"},
            },
            "api_responses": [],
        }
        page_path = tmp_path / "20260616_170000_diagnostic.json"
        manual_path = tmp_path / "20260616_170100_diagnostic.json"
        page_path.write_text(validate_collection.json.dumps(page_loaded, ensure_ascii=False), encoding="utf-8")
        manual_path.write_text(validate_collection.json.dumps(manual_test, ensure_ascii=False), encoding="utf-8")
        now = validate_collection.time.time()
        os.utime(page_path, (now - 10, now - 10))
        os.utime(manual_path, (now, now))

        checks = validate_collection.validate_latest_diagnostic(
            expected_version="5.0",
            strict=True,
            max_age_seconds=60,
            expected_kinds=["published_records_page_loaded"],
        )
        raw_file = next(check for check in checks if check.name == "diagnostic_raw_file")
        kind_check = next(check for check in checks if check.name == "diagnostic_expected_kind")
        assert raw_file.detail == page_path.name
        assert kind_check.passed is True

    def test_collection_validator_checks_page_session_consistency(self, tmp_path, monkeypatch) -> None:
        from modules.analytics import schema, validate_collection

        monkeypatch.setattr(schema, "RAW_DIR", tmp_path)
        base_page_data = {
            "page_session_id": "page_same",
            "diagnostics": {"script_version": "5.0", "page_session_id": "page_same"},
        }
        published = {
            "page_type": "published_records",
            "page_data": {**base_page_data, "article_count": 1},
            "api_responses": [{"body": {"article_list": [{
                "msg_id": "2247487301",
                "item_idx": 1,
                "title": "会话文章",
                "publish_date": "2026-06-16",
            }]}}],
        }
        preview = {
            "page_type": "published_records_preview",
            "page_data": {**base_page_data, "source": "cached_api", "article_count": 1},
            "api_responses": [{"body": {"article_list": published["api_responses"][0]["body"]["article_list"]}}],
        }
        diagnostic = {
            "page_type": "diagnostic",
            "page_data": {**base_page_data, "kind": "published_records_page_loaded"},
            "api_responses": [],
        }
        (tmp_path / "20260616_180000_published_records.json").write_text(
            validate_collection.json.dumps(published, ensure_ascii=False), encoding="utf-8"
        )
        (tmp_path / "20260616_180001_published_records_preview.json").write_text(
            validate_collection.json.dumps(preview, ensure_ascii=False), encoding="utf-8"
        )
        diagnostic_path = tmp_path / "20260616_180002_diagnostic.json"
        diagnostic_path.write_text(validate_collection.json.dumps(diagnostic, ensure_ascii=False), encoding="utf-8")

        checks = validate_collection.session_consistency_checks(
            strict=True,
            expected_diagnostic_kinds=["published_records_page_loaded"],
        )
        assert checks[0].passed is True

        diagnostic["page_data"]["page_session_id"] = "page_other"
        diagnostic_path.write_text(validate_collection.json.dumps(diagnostic, ensure_ascii=False), encoding="utf-8")
        wrong_checks = validate_collection.session_consistency_checks(
            strict=True,
            expected_diagnostic_kinds=["published_records_page_loaded"],
        )
        assert wrong_checks[0].passed is False

    def test_collection_validator_checks_scan_session_consistency(self, tmp_path, monkeypatch) -> None:
        from modules.analytics import schema, validate_collection

        monkeypatch.setattr(schema, "RAW_DIR", tmp_path)
        article_list = [{
            "msg_id": "2247487302",
            "item_idx": 1,
            "title": "扫描会话文章",
            "publish_date": "2026-06-16",
        }]
        base_page_data = {
            "page_session_id": "page_same",
            "diagnostics": {"script_version": "5.0", "page_session_id": "page_same"},
        }
        published = {
            "page_type": "published_records",
            "page_data": {**base_page_data, "scan_session_id": "scan_same", "article_count": 1},
            "api_responses": [{"body": {"article_list": article_list}}],
        }
        preview = {
            "page_type": "published_records_preview",
            "page_data": {**base_page_data, "source": "cached_api", "article_count": 1},
            "api_responses": [{"body": {"article_list": article_list}}],
        }
        page_loaded = {
            "page_type": "diagnostic",
            "page_data": {**base_page_data, "kind": "published_records_page_loaded"},
            "api_responses": [],
        }
        scan_started = {
            "page_type": "diagnostic",
            "page_data": {**base_page_data, "kind": "published_records_scan_started", "scan_session_id": "scan_same"},
            "api_responses": [],
        }
        (tmp_path / "20260616_180000_published_records.json").write_text(
            validate_collection.json.dumps(published, ensure_ascii=False), encoding="utf-8"
        )
        (tmp_path / "20260616_180001_published_records_preview.json").write_text(
            validate_collection.json.dumps(preview, ensure_ascii=False), encoding="utf-8"
        )
        (tmp_path / "20260616_180002_diagnostic.json").write_text(
            validate_collection.json.dumps(page_loaded, ensure_ascii=False), encoding="utf-8"
        )
        scan_started_path = tmp_path / "20260616_180003_diagnostic.json"
        scan_started_path.write_text(validate_collection.json.dumps(scan_started, ensure_ascii=False), encoding="utf-8")

        checks = validate_collection.session_consistency_checks(
            strict=True,
            expected_diagnostic_kinds=["published_records_page_loaded"],
        )
        scan_check = next(check for check in checks if check.name == "latest_scan_session_consistent")
        assert scan_check.passed is True

        scan_started["page_data"]["scan_session_id"] = "scan_other"
        scan_started_path.write_text(validate_collection.json.dumps(scan_started, ensure_ascii=False), encoding="utf-8")
        wrong_checks = validate_collection.session_consistency_checks(
            strict=True,
            expected_diagnostic_kinds=["published_records_page_loaded"],
        )
        wrong_scan_check = next(check for check in wrong_checks if check.name == "latest_scan_session_consistent")
        assert wrong_scan_check.passed is False

    def test_collection_validator_watch_returns_when_checks_pass(self, monkeypatch) -> None:
        from types import SimpleNamespace
        from modules.analytics import validate_collection

        calls = {"n": 0}

        def fake_run_checks(args):
            calls["n"] += 1
            return [validate_collection.Check("ready", calls["n"] >= 2, f"call={calls['n']}")]

        monkeypatch.setattr(validate_collection, "run_checks", fake_run_checks)
        monkeypatch.setattr(validate_collection.time, "sleep", lambda seconds: None)

        checks = validate_collection.wait_for_checks(SimpleNamespace(
            watch_seconds=5,
            poll_interval=0.1,
        ))

        assert calls["n"] == 2
        assert checks[0].passed is True

    def test_userscript_collects_ten_visible_published_records_without_extra_dom_candidates(self) -> None:
        from playwright.sync_api import sync_playwright

        script = (Path(__file__).parent.parent / "modules/browser/mp_analytics_injector.user.js").read_text(
            encoding="utf-8"
        )
        records = "\n".join(
            f"""
            <li class="publish-item">
              <a class="publish-title" href="https://mp.weixin.qq.com/s?__biz=test&mid=2247486{i:03d}&idx=1">验收文章 {i:02d}</a>
              <div class="appmsg"><span class="title">验收文章 {i:02d}</span></div>
              <span class="publish-date">2026-06-{i:02d}</span>
              <span class="read-count">阅读 {100 + i}</span>
            </li>
            """
            for i in range(1, 11)
        )
        html = f"""
        <!doctype html>
        <html>
          <head><title>发表记录</title></head>
          <body>
            <h1>发表记录</h1>
            <ul class="publish-list">{records}</ul>
            <button class="weui-desktop-btn weui-desktop-btn_disabled">下一页</button>
          </body>
        </html>
        """

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.route(
                "https://mp.weixin.qq.com/cgi-bin/appmsgpublish**",
                lambda route: route.fulfill(status=200, content_type="text/html; charset=utf-8", body=html),
            )
            page.goto("https://mp.weixin.qq.com/cgi-bin/appmsgpublish?action=list&begin=0")
            page.evaluate(
                """
                () => {
                window.__collectorPayloads = [];
                window.GM_xmlhttpRequest = function(options) {
                  window.__collectorPayloads.push(JSON.parse(options.data));
                  options.onload({
                    status: 200,
                    response: {status: 'ok'},
                    responseText: '{"status":"ok"}'
                  });
                };
                }
                """
            )
            page.add_script_tag(content=script)
            page.locator("#mp-preview-current-btn").wait_for(state="visible", timeout=5000)
            page.click("#mp-preview-current-btn")
            page.wait_for_function(
                "() => window.__collectorPayloads.some(p => p.page_type === 'published_records_preview')"
            )
            page.click("#mp-scan-all-btn")
            page.wait_for_function(
                "() => window.__collectorPayloads.some(p => p.page_type === 'published_records')"
            )
            payloads = page.evaluate("window.__collectorPayloads")
            browser.close()

        diagnostics = [p for p in payloads if p["page_type"] == "diagnostic"]
        preview = next(p for p in payloads if p["page_type"] == "published_records_preview")
        full_scan = next(p for p in payloads if p["page_type"] == "published_records")

        assert any(p["page_data"]["kind"] == "published_records_page_loaded" for p in diagnostics)
        assert any(p["page_data"]["kind"] == "published_records_scan_started" for p in diagnostics)
        page_sessions = {
            p["page_data"]["page_session_id"]
            for p in [*diagnostics, preview, full_scan]
            if p["page_data"].get("page_session_id")
        }
        assert len(page_sessions) == 1
        assert full_scan["page_data"]["scan_session_id"]
        assert any(
            p["page_data"].get("scan_session_id") == full_scan["page_data"]["scan_session_id"]
            for p in diagnostics
            if p["page_data"]["kind"] == "published_records_scan_started"
        )
        assert preview["page_data"]["source"] == "dom_fallback"
        assert preview["page_data"]["candidates"] == 10
        assert preview["page_data"]["article_count"] == 10
        assert len(preview["api_responses"][0]["body"]["article_list"]) == 10
        assert full_scan["page_data"]["page_sources"][0]["candidates"] == 10
        assert full_scan["page_data"]["article_count"] == 10
        assert len(full_scan["api_responses"][0]["body"]["article_list"]) == 10

    def test_userscript_dom_fallback_ignores_price_and_status_candidates(self) -> None:
        from playwright.sync_api import sync_playwright

        script = (Path(__file__).parent.parent / "modules/browser/mp_analytics_injector.user.js").read_text(
            encoding="utf-8"
        )
        records = "\n".join(
            f"""
            <li class="publish-item" data-msgid="2247489{i:03d}">
              <div class="appmsg-title">¥{i}.00</div>
              <div class="appmsg-title">已修改</div>
              <div class="publish-title">
                噪声验收文章 {i:02d} 原创 已修改 第1次修改 2026年05月11日 09时23分 KingWang
              </div>
              <span class="publish-date">2026年05月11日 09时23分</span>
              <span class="read-count">阅读 {100 + i}</span>
            </li>
            """
            for i in range(1, 11)
        )
        html = f"""
        <!doctype html>
        <html>
          <head><title>发表记录</title></head>
          <body>
            <h1>发表记录</h1>
            <ul class="publish-list">{records}</ul>
          </body>
        </html>
        """

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.route(
                "https://mp.weixin.qq.com/cgi-bin/appmsgpublish**",
                lambda route: route.fulfill(status=200, content_type="text/html; charset=utf-8", body=html),
            )
            page.goto("https://mp.weixin.qq.com/cgi-bin/appmsgpublish?action=list&begin=0")
            page.evaluate(
                """
                () => {
                window.__collectorPayloads = [];
                window.GM_xmlhttpRequest = function(options) {
                  window.__collectorPayloads.push(JSON.parse(options.data));
                  options.onload({
                    status: 200,
                    response: {status: 'ok'},
                    responseText: '{"status":"ok"}'
                  });
                };
                }
                """
            )
            page.add_script_tag(content=script)
            page.locator("#mp-preview-current-btn").wait_for(state="visible", timeout=5000)
            page.click("#mp-preview-current-btn")
            page.wait_for_function(
                "() => window.__collectorPayloads.some(p => p.page_type === 'published_records_preview')"
            )
            payloads = page.evaluate("window.__collectorPayloads")
            browser.close()

        preview = next(p for p in payloads if p["page_type"] == "published_records_preview")
        articles = preview["api_responses"][0]["body"]["article_list"]
        titles = [article["title"] for article in articles]

        assert preview["page_data"]["source"] == "dom_fallback"
        assert preview["page_data"]["candidates"] == 10
        assert preview["page_data"]["article_count"] == 10
        assert all(title.startswith("噪声验收文章") for title in titles)
        assert all("¥" not in title and "已修改" not in title and "2026年" not in title for title in titles)
        assert preview["page_data"]["diagnostics"]["dom_articles"] == 10
        assert "dom_debug" in preview["page_data"]["diagnostics"]

    def test_userscript_dom_fallback_rejects_future_container_dates(self) -> None:
        from playwright.sync_api import sync_playwright

        script = (Path(__file__).parent.parent / "modules/browser/mp_analytics_injector.user.js").read_text(
            encoding="utf-8"
        )
        records = "\n".join(
            f"""
            <div class="publish-card">
              <div class="publish-title">未来日期保护文章 {i}</div>
              <span class="read-count">阅读 {20 + i}</span>
            </div>
            """
            for i in range(1, 3)
        )
        html = f"""
        <!doctype html>
        <html>
          <head><title>发表记录</title></head>
          <body>
            <section class="publish-list">
              <div class="publish-date">2099年09月11日</div>
              {records}
            </section>
          </body>
        </html>
        """

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.route(
                "https://mp.weixin.qq.com/cgi-bin/appmsgpublish**",
                lambda route: route.fulfill(status=200, content_type="text/html; charset=utf-8", body=html),
            )
            page.goto("https://mp.weixin.qq.com/cgi-bin/appmsgpublish?action=list&begin=0")
            page.evaluate(
                """
                () => {
                window.__collectorPayloads = [];
                window.GM_xmlhttpRequest = function(options) {
                  window.__collectorPayloads.push(JSON.parse(options.data));
                  options.onload({
                    status: 200,
                    response: {status: 'ok'},
                    responseText: '{"status":"ok"}'
                  });
                };
                }
                """
            )
            page.add_script_tag(content=script)
            page.locator("#mp-preview-current-btn").wait_for(state="visible", timeout=5000)
            page.click("#mp-preview-current-btn")
            page.wait_for_function(
                "() => window.__collectorPayloads.some(p => p.page_type === 'published_records_preview')"
            )
            payloads = page.evaluate("window.__collectorPayloads")
            browser.close()

        preview = next(p for p in payloads if p["page_type"] == "published_records_preview")
        articles = preview["api_responses"][0]["body"]["article_list"]

        assert preview["page_data"]["article_count"] == 2
        assert [article["title"] for article in articles] == ["未来日期保护文章 1", "未来日期保护文章 2"]
        assert [article["publish_date"] for article in articles] == ["", ""]

    def test_userscript_dom_fallback_keeps_same_title_on_different_dates(self) -> None:
        from playwright.sync_api import sync_playwright

        script = (Path(__file__).parent.parent / "modules/browser/mp_analytics_injector.user.js").read_text(
            encoding="utf-8"
        )
        html = """
        <!doctype html>
        <html>
          <head><title>发表记录</title></head>
          <body>
            <ul class="publish-list">
              <li class="publish-item">
                <a class="publish-title" href="#">什么是广告超播？</a>
                <span class="publish-date">2021-10-04</span>
                <span class="read-count">阅读 4</span>
              </li>
              <li class="publish-item">
                <a class="publish-title" href="#">什么是广告超播？</a>
                <span class="publish-date">2022-01-02</span>
                <span class="read-count">阅读 0</span>
              </li>
            </ul>
          </body>
        </html>
        """

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.route(
                "https://mp.weixin.qq.com/cgi-bin/appmsgpublish**",
                lambda route: route.fulfill(status=200, content_type="text/html; charset=utf-8", body=html),
            )
            page.goto("https://mp.weixin.qq.com/cgi-bin/appmsgpublish?action=list&begin=0")
            page.evaluate(
                """
                () => {
                window.__collectorPayloads = [];
                window.GM_xmlhttpRequest = function(options) {
                  window.__collectorPayloads.push(JSON.parse(options.data));
                  options.onload({
                    status: 200,
                    response: {status: 'ok'},
                    responseText: '{"status":"ok"}'
                  });
                };
                }
                """
            )
            page.add_script_tag(content=script)
            page.locator("#mp-preview-current-btn").wait_for(state="visible", timeout=5000)
            page.click("#mp-preview-current-btn")
            page.wait_for_function(
                "() => window.__collectorPayloads.some(p => p.page_type === 'published_records_preview')"
            )
            payloads = page.evaluate("window.__collectorPayloads")
            browser.close()

        preview = next(p for p in payloads if p["page_type"] == "published_records_preview")
        articles = preview["api_responses"][0]["body"]["article_list"]

        assert preview["page_data"]["source"] == "dom_fallback"
        assert preview["page_data"]["candidates"] == 2
        assert preview["page_data"]["article_count"] == 2
        assert [article["title"] for article in articles] == ["什么是广告超播？", "什么是广告超播？"]
        assert [article["publish_date"] for article in articles] == ["2021-10-04", "2022-01-02"]

    def test_userscript_full_scan_starts_from_first_page_when_clicked_on_third_page(self) -> None:
        from playwright.sync_api import sync_playwright

        script = (Path(__file__).parent.parent / "modules/browser/mp_analytics_injector.user.js").read_text(
            encoding="utf-8"
        )

        def articles(start: int, count: int) -> list[dict]:
            return [{
                "msg_id": str(2247488000 + i),
                "item_idx": 1,
                "title": f"分页文章 {i:02d}",
                "publish_date": "2026-06-16",
                "total_reads": 100 + i,
            } for i in range(start, start + count)]

        def record_html(article: dict) -> str:
            return f"""
            <li class="publish-item">
              <a class="publish-title" href="https://mp.weixin.qq.com/s?__biz=test&mid={article['msg_id']}&idx=1">{article['title']}</a>
              <span class="publish-date">{article['publish_date']}</span>
              <span class="read-count">阅读 {article['total_reads']}</span>
            </li>
            """

        first_page = articles(1, 10)
        second_page = articles(11, 10)
        third_page = articles(21, 2)

        def publish_page_body(page_articles: list[dict]) -> dict:
            publish_list = []
            for article in page_articles:
                appmsgex = [{
                    "appmsgid": article["msg_id"],
                    "itemidx": article["item_idx"],
                    "title": article["title"],
                    "link": f"https://mp.weixin.qq.com/s?__biz=test&mid={article['msg_id']}&idx={article['item_idx']}",
                    "create_time": article["publish_date"],
                    "read_num": article["total_reads"],
                }]
                publish_list.append({
                    "publish_info": json.dumps({"appmsgex": json.dumps(appmsgex, ensure_ascii=False)}, ensure_ascii=False)
                })
            return {
                "publish_page": json.dumps({
                    "total_count": 22,
                    "publish_list": publish_list,
                }, ensure_ascii=False)
            }

        html = f"""
        <!doctype html>
        <html>
          <head><title>发表记录</title></head>
          <body>
            <ul id="publish-list" class="publish-list">{''.join(record_html(article) for article in third_page)}</ul>
            <div class="weui-desktop-pagination__nav">
              <button id="prev-page" class="weui-desktop-btn">上一页</button>
              <button id="next-page" class="weui-desktop-btn">下一页</button>
            </div>
            <script>
              let currentPage = 3;
              const apiPages = {{
                1: {json.dumps(first_page, ensure_ascii=False)},
                2: {json.dumps(second_page, ensure_ascii=False)},
                3: {json.dumps(third_page, ensure_ascii=False)}
              }};
              function render(list) {{
                document.getElementById('publish-list').innerHTML = list.map(article => `
                  <li class="publish-item">
                    <a class="publish-title" href="https://mp.weixin.qq.com/s?__biz=test&mid=${{article.msg_id}}&idx=1">${{article.title}}</a>
                    <span class="publish-date">${{article.publish_date}}</span>
                    <span class="read-count">阅读 ${{article.total_reads}}</span>
                  </li>
                `).join('');
              }}

              function updatePagination() {{
                document.getElementById('prev-page').classList.toggle('weui-desktop-btn_disabled', currentPage <= 1);
                document.getElementById('next-page').classList.toggle('weui-desktop-btn_disabled', currentPage >= 3);
              }}

              async function loadPage(pageNum) {{
                currentPage = pageNum;
                const begin = (currentPage - 1) * 10;
                const response = await fetch('/cgi-bin/appmsgpublish?action=list&begin=' + begin);
                const data = await response.json();
                history.pushState(null, '', '/cgi-bin/appmsgpublish?action=list&begin=' + begin);
                render(data.article_list);
                updatePagination();
              }}

              document.getElementById('prev-page').addEventListener('click', async () => {{
                if (currentPage <= 1) return;
                await loadPage(currentPage - 1);
              }});

              document.getElementById('next-page').addEventListener('click', async () => {{
                if (currentPage >= 3) return;
                await loadPage(currentPage + 1);
              }});
              updatePagination();
            </script>
          </body>
        </html>
        """

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            def fulfill_page_or_api(route):
                url = route.request.url
                if route.request.resource_type == "document":
                    route.fulfill(status=200, content_type="text/html; charset=utf-8", body=html)
                    return

                if "begin=0" in url:
                    page_articles = first_page
                elif "begin=10" in url:
                    page_articles = second_page
                else:
                    page_articles = third_page
                body = publish_page_body(page_articles) if "f=json" in url else {"article_list": page_articles}
                route.fulfill(
                    status=200,
                    content_type="application/json; charset=utf-8",
                    body=json.dumps(body, ensure_ascii=False),
                )

            page.route("**/cgi-bin/appmsgpublish**", fulfill_page_or_api)
            page.goto("https://mp.weixin.qq.com/cgi-bin/appmsgpublish?action=list&begin=20")
            page.evaluate(
                """
                () => {
                window.__collectorPayloads = [];
                window.GM_xmlhttpRequest = function(options) {
                  window.__collectorPayloads.push(JSON.parse(options.data));
                  options.onload({
                    status: 200,
                    response: {status: 'ok'},
                    responseText: '{"status":"ok"}'
                  });
                };
                }
                """
            )
            page.add_script_tag(content=script)
            page.locator("#mp-scan-all-btn").wait_for(state="visible", timeout=5000)
            page.click("#mp-scan-all-btn")
            page.wait_for_function(
                "() => window.__collectorPayloads.some(p => p.page_type === 'published_records')",
                timeout=15000,
            )
            payloads = page.evaluate("window.__collectorPayloads")
            browser.close()

        full_scan = next(p for p in payloads if p["page_type"] == "published_records")
        sources = full_scan["page_data"]["page_sources"]
        assert full_scan["page_data"]["scan_mode"] == "from_first_page"
        assert full_scan["page_data"]["started_from_current_page"] is False
        assert full_scan["page_data"]["pre_scan_page_turns"] == 2
        assert "begin=20" in full_scan["page_data"]["start_href"]
        assert "begin=0" in full_scan["page_data"]["first_page_href"]
        assert [source["label"] for source in sources] == ["page_1", "page_turn_1", "page_turn_2"]
        assert [source["source"] for source in sources] == ["api_fetch", "api_fetch", "api_fetch"]
        assert [source["begin"] for source in sources] == [0, 10, 20]
        assert [source["total_count"] for source in sources] == [22, 22, 22]
        assert [source["added"] for source in sources] == [10, 10, 2]
        assert [source["candidates"] for source in sources] == [10, 10, 2]
        assert full_scan["page_data"]["article_count"] == 22
        assert len(full_scan["api_responses"][0]["body"]["article_list"]) == 22

    def test_userscript_full_scan_survives_document_reload_between_pages(self) -> None:
        from playwright.sync_api import sync_playwright

        script = (Path(__file__).parent.parent / "modules/browser/mp_analytics_injector.user.js").read_text(
            encoding="utf-8"
        )
        inline_script = script.replace("</script>", "<\\/script>")

        def articles(start: int, count: int) -> list[dict]:
            return [{
                "msg_id": str(2247489000 + i),
                "item_idx": 1,
                "title": f"重载分页文章 {i:02d}",
                "publish_date": "2026-06-16",
                "total_reads": 200 + i,
            } for i in range(start, start + count)]

        pages = {
            0: articles(1, 10),
            10: articles(11, 10),
            20: articles(21, 2),
        }

        def record_html(article: dict) -> str:
            return f"""
            <li class="publish-item">
              <a class="publish-title" href="https://mp.weixin.qq.com/s?__biz=test&mid={article['msg_id']}&idx=1">{article['title']}</a>
              <span class="publish-date">{article['publish_date']}</span>
              <span class="read-count">阅读 {article['total_reads']}</span>
            </li>
            """

        def page_html(begin: int) -> str:
            prev_begin = max(begin - 10, 0)
            next_begin = begin + 10
            prev_disabled = "weui-desktop-btn_disabled" if begin <= 0 else ""
            next_disabled = "weui-desktop-btn_disabled" if begin >= 20 else ""
            can_prev = "true" if begin > 0 else "false"
            can_next = "true" if begin < 20 else "false"
            return f"""
            <!doctype html>
            <html>
              <head><title>发表记录</title></head>
              <body>
                <ul id="publish-list" class="publish-list">{''.join(record_html(article) for article in pages[begin])}</ul>
                <div class="weui-desktop-pagination__nav">
                  <button id="prev-page" class="weui-desktop-btn {prev_disabled}"
                    onclick="if ({can_prev}) window.location.href='/cgi-bin/appmsgpublish?action=list&begin={prev_begin}'">上一页</button>
                  <button id="next-page" class="weui-desktop-btn {next_disabled}"
                    onclick="if ({can_next}) window.location.href='/cgi-bin/appmsgpublish?action=list&begin={next_begin}'">下一页</button>
                </div>
                <script>
                  window.__collectorPayloads = JSON.parse(sessionStorage.getItem('__collectorPayloads') || '[]');
                  window.GM_xmlhttpRequest = function(options) {{
                    const payloads = JSON.parse(sessionStorage.getItem('__collectorPayloads') || '[]');
                    payloads.push(JSON.parse(options.data));
                    sessionStorage.setItem('__collectorPayloads', JSON.stringify(payloads));
                    window.__collectorPayloads = payloads;
                    options.onload({{
                      status: 200,
                      response: {{status: 'ok'}},
                      responseText: '{{"status":"ok"}}'
                    }});
                  }};
                </script>
                <script>{inline_script}</script>
              </body>
            </html>
            """

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            def fulfill_document(route):
                url = route.request.url
                if "begin=20" in url:
                    begin = 20
                elif "begin=10" in url:
                    begin = 10
                else:
                    begin = 0
                route.fulfill(status=200, content_type="text/html; charset=utf-8", body=page_html(begin))

            page.route("https://mp.weixin.qq.com/cgi-bin/appmsgpublish**", fulfill_document)
            page.goto("https://mp.weixin.qq.com/cgi-bin/appmsgpublish?action=list&begin=0")
            page.locator("#mp-scan-all-btn").wait_for(state="visible", timeout=5000)
            page.click("#mp-scan-all-btn")
            page.wait_for_function(
                """
                () => JSON.parse(sessionStorage.getItem('__collectorPayloads') || '[]')
                  .some(p => p.page_type === 'published_records')
                """,
                timeout=20000,
            )
            payloads = page.evaluate("JSON.parse(sessionStorage.getItem('__collectorPayloads') || '[]')")
            persisted_state = page.evaluate("sessionStorage.getItem('mp_collector_full_scan_state_v1')")
            browser.close()

        full_scan = next(p for p in payloads if p["page_type"] == "published_records")
        diagnostics = [p for p in payloads if p["page_type"] == "diagnostic"]
        sources = full_scan["page_data"]["page_sources"]
        page_sessions = {
            p["page_data"].get("page_session_id")
            for p in [*diagnostics, full_scan]
            if p["page_data"].get("page_session_id")
        }

        assert persisted_state is None
        assert len(page_sessions) == 1
        assert full_scan["page_data"]["scan_mode"] == "from_first_page"
        assert full_scan["page_data"]["started_from_current_page"] is False
        assert full_scan["page_data"]["page_turns"] == 2
        assert [source["label"] for source in sources] == ["page_1", "page_turn_1", "page_turn_2"]
        assert [source["source"] for source in sources] == ["dom_fallback", "dom_fallback", "dom_fallback"]
        assert [source["added"] for source in sources] == [10, 10, 2]
        assert [source["candidates"] for source in sources] == [10, 10, 2]
        assert full_scan["page_data"]["article_count"] == 22
        assert len(full_scan["api_responses"][0]["body"]["article_list"]) == 22
