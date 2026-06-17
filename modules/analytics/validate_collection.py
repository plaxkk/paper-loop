#!/usr/bin/env python3
"""Validation checks for the WeChat MP collection pipeline."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from . import schema


@dataclass
class Check:
    name: str
    passed: bool
    detail: str
    level: str = "pass"


def latest_raw_for(page_type: str, raw_dir: Path | None = None) -> Path | None:
    raw_dir = raw_dir or schema.RAW_DIR
    files = sorted(raw_dir.glob(f"*{page_type}.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def raw_files_for(page_type: str, raw_dir: Path | None = None) -> list[Path]:
    raw_dir = raw_dir or schema.RAW_DIR
    return sorted(raw_dir.glob(f"*{page_type}.json"), key=lambda p: p.stat().st_mtime, reverse=True)


def latest_published_raw(raw_dir: Path | None = None) -> Path | None:
    return latest_raw_for("published_records", raw_dir)


def latest_preview_raw(raw_dir: Path | None = None) -> Path | None:
    return latest_raw_for("published_records_preview", raw_dir)


def latest_diagnostic_raw(raw_dir: Path | None = None) -> Path | None:
    return latest_raw_for("diagnostic", raw_dir)


def latest_diagnostic_raw_for_kinds(kinds: list[str] | None, raw_dir: Path | None = None) -> Path | None:
    allowed = {kind for kind in (kinds or []) if kind}
    if not allowed:
        return latest_diagnostic_raw(raw_dir)
    for path in raw_files_for("diagnostic", raw_dir):
        try:
            payload = load_json(path)
        except Exception:
            continue
        page_data = payload.get("page_data", {}) or {}
        if str(page_data.get("kind") or "") in allowed:
            return path
    return None


def latest_diagnostic_raws_by_kind(kinds: list[str], raw_dir: Path | None = None) -> dict[str, Path | None]:
    wanted = [kind for kind in kinds if kind]
    result: dict[str, Path | None] = {kind: None for kind in wanted}
    if not wanted:
        return result
    remaining = set(wanted)
    for path in raw_files_for("diagnostic", raw_dir):
        try:
            payload = load_json(path)
        except Exception:
            continue
        kind = str(payload_page_data(payload).get("kind") or "")
        if kind in remaining:
            result[kind] = path
            remaining.remove(kind)
            if not remaining:
                break
    return result


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def published_articles(payload: dict[str, Any]) -> list[dict[str, Any]]:
    articles: list[dict[str, Any]] = []
    for resp in payload.get("api_responses", []) or []:
        body = resp.get("body", {}) if isinstance(resp, dict) else {}
        if isinstance(body, dict):
            for item in body.get("article_list", []) or []:
                if isinstance(item, dict):
                    articles.append(item)
    return articles


def payload_page_data(payload: dict[str, Any]) -> dict[str, Any]:
    page_data = payload.get("page_data", {}) or {}
    return page_data if isinstance(page_data, dict) else {}


def payload_page_session_id(payload: dict[str, Any]) -> str:
    page_data = payload_page_data(payload)
    diagnostics = page_data.get("diagnostics", {}) or {}
    return str(page_data.get("page_session_id") or diagnostics.get("page_session_id") or "")


def payload_scan_session_id(payload: dict[str, Any]) -> str:
    page_data = payload_page_data(payload)
    diagnostics = page_data.get("diagnostics", {}) or {}
    return str(page_data.get("scan_session_id") or diagnostics.get("scan_session_id") or "")


def article_key(article: dict[str, Any]) -> str:
    msg_id = str(article.get("msg_id", "") or "").strip()
    item_idx = str(schema.normalize_item_idx(article.get("item_idx", 1)))
    title = str(article.get("title", "") or "").strip()
    publish_date = schema.norm_date(article.get("publish_date", "") or "")
    if msg_id:
        return f"id:{msg_id}:{item_idx}"
    if title and publish_date:
        return f"title_date:{title}:{publish_date}:{item_idx}"
    if title:
        return f"title:{title}:{item_idx}"
    return ""


def duplicate_keys(articles: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for article in articles:
        key = article_key(article)
        if not key:
            continue
        if key in seen:
            duplicates.append(key)
        seen.add(key)
    return duplicates


def normalized_title(value: Any) -> str:
    return " ".join(str(value or "").split())


def article_titles(articles: list[dict[str, Any]]) -> list[str]:
    return [normalized_title(article.get("title", "")) for article in articles]


def title_fingerprint(titles: list[str]) -> str:
    payload = "\n".join(normalized_title(title) for title in titles)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_expected_titles(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8")
    stripped = raw.strip()
    if not stripped:
        return []
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return [normalized_title(line) for line in raw.splitlines() if normalized_title(line)]

    if isinstance(parsed, dict):
        parsed = parsed.get("titles") or parsed.get("articles") or []
    if isinstance(parsed, list):
        titles: list[str] = []
        for item in parsed:
            if isinstance(item, dict):
                titles.append(normalized_title(item.get("title", "")))
            else:
                titles.append(normalized_title(item))
        return [title for title in titles if title]
    return []


def expected_titles_check(articles: list[dict[str, Any]], expected_titles_path: Path) -> Check:
    actual = article_titles(articles)
    try:
        expected = load_expected_titles(expected_titles_path)
    except OSError as exc:
        return Check("latest_expected_titles", False, f"error={exc}")
    missing = [title for title in expected if title not in actual]
    extra = [title for title in actual if title not in expected]
    first_mismatch = ""
    for idx, expected_title in enumerate(expected):
        actual_title = actual[idx] if idx < len(actual) else ""
        if actual_title != expected_title:
            first_mismatch = f"index={idx + 1}, actual={actual_title or '<missing>'}, expected={expected_title}"
            break
    passed = actual == expected
    detail = (
        f"actual={len(actual)}, expected={len(expected)}, "
        f"actual_sha256={title_fingerprint(actual)}, expected_sha256={title_fingerprint(expected)}"
    )
    if not passed:
        detail += (
            f", missing={missing[:3]}, extra={extra[:3]}, "
            f"first_mismatch={first_mismatch or 'none'}"
        )
    return Check("latest_expected_titles", passed, detail)


def expected_title_sha256_check(articles: list[dict[str, Any]], expected_sha256: str) -> Check:
    actual = article_titles(articles)
    actual_sha256 = title_fingerprint(actual)
    expected = str(expected_sha256 or "").strip().lower()
    passed = bool(expected) and actual_sha256 == expected
    return Check(
        "latest_expected_title_sha256",
        passed,
        f"rows={len(actual)}, actual_sha256={actual_sha256}, expected_sha256={expected or '<missing>'}",
    )


def parse_count_list(value: str | None) -> list[int] | None:
    if not value:
        return None
    counts: list[int] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        counts.append(int(part))
    return counts


def parse_string_list(value: str | None) -> list[str] | None:
    if not value:
        return None
    values = [part.strip() for part in value.split(",") if part.strip()]
    return values or None


def safe_int(value: Any, default: int = -1) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def raw_summary(path: Path, article_limit: int = 30) -> dict[str, Any]:
    payload = load_json(path)
    page_data = payload_page_data(payload)
    diagnostics = page_data.get("diagnostics", {}) or {}
    articles = published_articles(payload)
    page_sources = page_data.get("page_sources") or []
    titles = article_titles(articles)
    return {
        "file": path.name,
        "page_type": payload.get("page_type", "unknown"),
        "script_version": diagnostics.get("script_version") or "",
        "article_count": page_data.get("article_count"),
        "rows": len(articles),
        "source": page_data.get("source") or "",
        "kind": page_data.get("kind") or "",
        "stop_reason": page_data.get("stop_reason") or "",
        "scan_mode": page_data.get("scan_mode") or "",
        "started_from_current_page": page_data.get("started_from_current_page"),
        "page_session_id": payload_page_session_id(payload),
        "scan_session_id": payload_scan_session_id(payload),
        "page_sources": page_sources,
        "duplicates": duplicate_keys(articles),
        "title_fingerprint": title_fingerprint(titles),
        "articles": articles[:article_limit],
    }


def format_raw_summary(summary: dict[str, Any]) -> str:
    lines = [
        f"file: {summary['file']}",
        f"page_type: {summary['page_type']}",
        f"script_version: {summary['script_version'] or 'unknown'}",
        f"article_count: {summary['article_count']} rows: {summary['rows']}",
        f"title_sha256: {summary['title_fingerprint']}",
    ]
    if summary.get("source"):
        lines.append(f"source: {summary['source']}")
    if summary.get("kind"):
        lines.append(f"kind: {summary['kind']}")
    if summary.get("stop_reason"):
        lines.append(f"stop_reason: {summary['stop_reason']}")
    if summary.get("scan_mode") or summary.get("started_from_current_page") is not None:
        lines.append(
            f"scan_mode: {summary.get('scan_mode') or 'missing'} "
            f"started_from_current_page={summary.get('started_from_current_page')}"
        )
    if summary.get("page_session_id"):
        lines.append(f"page_session_id: {summary['page_session_id']}")
    if summary.get("scan_session_id"):
        lines.append(f"scan_session_id: {summary['scan_session_id']}")

    page_sources = summary.get("page_sources") or []
    if page_sources:
        lines.append("page_sources:")
        for idx, item in enumerate(page_sources, 1):
            lines.append(
                f"  {idx}. label={item.get('label', '')} source={item.get('source', '')} "
                f"candidates={item.get('candidates')} added={item.get('added')} total={item.get('total')}"
            )

    duplicates = summary.get("duplicates") or []
    lines.append("duplicates: " + (", ".join(duplicates[:5]) if duplicates else "0"))
    articles = summary.get("articles") or []
    if articles:
        lines.append("articles:")
        for idx, article in enumerate(articles, 1):
            lines.append(
                f"  {idx}. {article.get('title', '')} | "
                f"date={article.get('publish_date', '')} msg_id={article.get('msg_id', '')} "
                f"reads={article.get('total_reads', '')}"
            )
    return "\n".join(lines)


def raw_freshness_check(name: str, path: Path, max_age_seconds: float | None, strict: bool) -> Check | None:
    if max_age_seconds is None:
        return None
    age_seconds = max(time.time() - path.stat().st_mtime, 0)
    fresh = age_seconds <= max_age_seconds
    return Check(
        name,
        fresh or not strict,
        f"age={age_seconds:.1f}s, max={max_age_seconds:.1f}s",
        "pass" if fresh else "fail" if strict else "warn",
    )


def page_sources_consistency_check(page_sources: list[Any], row_count: int, strict: bool) -> Check:
    if not page_sources:
        return Check(
            "latest_page_sources_consistent",
            not strict,
            "page_sources=0",
            "fail" if strict else "warn",
        )

    cumulative = 0
    added_counts: list[int] = []
    candidate_counts: list[int] = []
    totals: list[int] = []
    issues: list[str] = []

    for idx, item in enumerate(page_sources, 1):
        if not isinstance(item, dict):
            issues.append(f"page={idx}:not_object")
            continue
        added = safe_int(item.get("added"))
        candidates = safe_int(item.get("candidates"))
        total = safe_int(item.get("total"))
        added_counts.append(added)
        candidate_counts.append(candidates)
        totals.append(total)
        if added < 0 or candidates < 0 or total < 0:
            issues.append(f"page={idx}:missing_or_negative")
            continue
        if candidates < added:
            issues.append(f"page={idx}:candidates_lt_added")
        cumulative += added
        if total != cumulative:
            issues.append(f"page={idx}:total={total},expected={cumulative}")

    final_total = totals[-1] if totals else 0
    if final_total != row_count:
        issues.append(f"final_total={final_total},rows={row_count}")

    passed = not issues
    return Check(
        "latest_page_sources_consistent",
        passed or not strict,
        (
            f"added={added_counts}, candidates={candidate_counts}, totals={totals}, "
            f"rows={row_count}, issues={issues or 'none'}"
        ),
        "fail" if strict and not passed else "warn" if not passed else "pass",
    )


def validate_latest_raw(
    expected_count: int | None = None,
    expected_page_counts: list[int] | None = None,
    expected_titles_path: Path | None = None,
    expected_title_sha256: str | None = None,
    expected_version: str = "5.0",
    strict: bool = False,
    max_age_seconds: float | None = None,
) -> list[Check]:
    path = latest_published_raw()
    if not path:
        return [Check(
            "latest_raw_present",
            not strict,
            "no published_records raw file found",
            "fail" if strict else "warn",
        )]

    payload = load_json(path)
    page_data = payload.get("page_data", {}) or {}
    diagnostics = page_data.get("diagnostics", {}) or {}
    articles = published_articles(payload)
    version = str(diagnostics.get("script_version") or "")
    page_sources = page_data.get("page_sources") or []
    duplicates = duplicate_keys(articles)
    article_count = page_data.get("article_count")
    scan_mode = str(page_data.get("scan_mode") or "")
    started_from_current_page = page_data.get("started_from_current_page")
    scan_mode_ok = scan_mode == "from_first_page" and started_from_current_page is False

    checks = [
        Check("latest_raw_file", True, path.name),
        Check(
            "latest_script_version",
            version == expected_version or not strict,
            f"version={version or 'unknown'}, expected={expected_version}",
            "fail" if strict and version != expected_version else "warn" if version != expected_version else "pass",
        ),
        Check(
            "latest_article_count_matches_rows",
            article_count == len(articles),
            f"page_data.article_count={article_count}, rows={len(articles)}",
        ),
        Check(
            "latest_has_no_duplicate_articles",
            not duplicates,
            "duplicates=" + (", ".join(duplicates[:5]) if duplicates else "0"),
        ),
        Check(
            "latest_page_sources_present",
            bool(page_sources) or not strict,
            f"page_sources={len(page_sources)}",
            "fail" if strict and not page_sources else "warn" if not page_sources else "pass",
        ),
        page_sources_consistency_check(page_sources, len(articles), strict),
        Check(
            "latest_scan_mode_from_first_page",
            scan_mode_ok or not strict,
            f"scan_mode={scan_mode or 'missing'}, started_from_current_page={started_from_current_page}",
            "fail" if strict and not scan_mode_ok else "warn" if not scan_mode_ok else "pass",
        ),
    ]
    freshness = raw_freshness_check("latest_raw_fresh", path, max_age_seconds, strict)
    if freshness:
        checks.insert(1, freshness)
    if expected_count is not None:
        checks.append(Check(
            "latest_expected_article_count",
            len(articles) == expected_count,
            f"rows={len(articles)}, expected={expected_count}",
        ))
    if expected_page_counts is not None:
        added_counts = [safe_int(item.get("added")) for item in page_sources if isinstance(item, dict)]
        candidate_counts = [item.get("candidates") for item in page_sources if isinstance(item, dict)]
        labels = [str(item.get("label") or "") for item in page_sources if isinstance(item, dict)]
        expected_labels = ["page_1"] + [f"page_turn_{idx}" for idx in range(1, len(expected_page_counts))]
        checks.append(Check(
            "latest_expected_page_counts",
            added_counts == expected_page_counts and labels == expected_labels,
            (
                f"added={added_counts}, candidates={candidate_counts}, labels={labels}, "
                f"expected={expected_page_counts}, expected_labels={expected_labels}"
            ),
        ))
    if expected_titles_path is not None:
        checks.append(expected_titles_check(articles, expected_titles_path))
    if expected_title_sha256 is not None:
        checks.append(expected_title_sha256_check(articles, expected_title_sha256))
    return checks


def validate_latest_preview(
    expected_count: int | None = None,
    expected_version: str = "5.0",
    strict: bool = False,
    max_age_seconds: float | None = None,
) -> list[Check]:
    path = latest_preview_raw()
    if not path:
        return [Check(
            "preview_raw_present",
            not strict,
            "no published_records_preview raw file found",
            "fail" if strict else "warn",
        )]

    payload = load_json(path)
    page_data = payload.get("page_data", {}) or {}
    diagnostics = page_data.get("diagnostics", {}) or {}
    articles = published_articles(payload)
    version = str(diagnostics.get("script_version") or "")
    source = str(page_data.get("source") or "")
    article_count = page_data.get("article_count")
    duplicates = duplicate_keys(articles)

    checks = [
        Check("preview_raw_file", True, path.name),
        Check(
            "preview_script_version",
            version == expected_version or not strict,
            f"version={version or 'unknown'}, expected={expected_version}",
            "fail" if strict and version != expected_version else "warn" if version != expected_version else "pass",
        ),
        Check(
            "preview_article_count_matches_rows",
            article_count == len(articles),
            f"page_data.article_count={article_count}, rows={len(articles)}",
        ),
        Check(
            "preview_has_no_duplicate_articles",
            not duplicates,
            "duplicates=" + (", ".join(duplicates[:5]) if duplicates else "0"),
        ),
        Check(
            "preview_source_present",
            bool(source) and source != "none" or not strict,
            f"source={source or 'missing'}",
            "fail" if strict and (not source or source == "none") else "warn" if (not source or source == "none") else "pass",
        ),
    ]
    freshness = raw_freshness_check("preview_raw_fresh", path, max_age_seconds, strict)
    if freshness:
        checks.insert(1, freshness)
    if expected_count is not None:
        checks.append(Check(
            "preview_expected_article_count",
            len(articles) == expected_count,
            f"rows={len(articles)}, expected={expected_count}",
        ))
    return checks


def validate_latest_diagnostic(
    expected_version: str = "5.0",
    strict: bool = False,
    max_age_seconds: float | None = None,
    expected_kinds: list[str] | None = None,
) -> list[Check]:
    expected_kinds = expected_kinds or []
    kind_paths = latest_diagnostic_raws_by_kind(expected_kinds) if expected_kinds else {}
    path = latest_diagnostic_raw_for_kinds(expected_kinds)
    if not path:
        detail = "no diagnostic raw file found"
        if expected_kinds:
            detail = "no diagnostic raw file found for kinds=" + ",".join(expected_kinds)
        checks = [Check(
            "diagnostic_raw_present",
            not strict,
            detail,
            "fail" if strict else "warn",
        )]
        if expected_kinds:
            checks.append(diagnostic_expected_kinds_present_check(kind_paths, strict))
        return checks

    payload = load_json(path)
    page_data = payload.get("page_data", {}) or {}
    diagnostics = page_data.get("diagnostics", {}) or {}
    version = str(diagnostics.get("script_version") or "")
    kind = str(page_data.get("kind") or "")

    checks = [
        Check("diagnostic_raw_file", True, path.name),
        Check(
            "diagnostic_script_version",
            version == expected_version or not strict,
            f"version={version or 'unknown'}, expected={expected_version}, kind={kind or 'missing'}",
            "fail" if strict and version != expected_version else "warn" if version != expected_version else "pass",
        ),
    ]
    if expected_kinds:
        checks.append(Check(
            "diagnostic_expected_kind",
            kind in expected_kinds,
            f"kind={kind or 'missing'}, expected={expected_kinds}",
        ))
        checks.append(diagnostic_expected_kinds_present_check(kind_paths, strict))
        checks.append(diagnostic_expected_kinds_version_check(kind_paths, expected_version, strict))
        freshness = diagnostic_expected_kinds_freshness_check(kind_paths, max_age_seconds, strict)
        if freshness:
            checks.append(freshness)
    freshness = raw_freshness_check("diagnostic_raw_fresh", path, max_age_seconds, strict)
    if freshness:
        checks.insert(1, freshness)
    return checks


def diagnostic_expected_kinds_present_check(kind_paths: dict[str, Path | None], strict: bool) -> Check:
    found = {kind: path.name for kind, path in kind_paths.items() if path}
    missing = [kind for kind, path in kind_paths.items() if not path]
    passed = not missing
    return Check(
        "diagnostic_expected_kinds_present",
        passed or not strict,
        f"found={found}, missing={missing}",
        "fail" if strict and not passed else "warn" if not passed else "pass",
    )


def diagnostic_expected_kinds_version_check(
    kind_paths: dict[str, Path | None],
    expected_version: str,
    strict: bool,
) -> Check:
    versions: dict[str, str] = {}
    wrong: dict[str, str] = {}
    for kind, path in kind_paths.items():
        if not path:
            continue
        try:
            payload = load_json(path)
            diagnostics = payload_page_data(payload).get("diagnostics", {}) or {}
            version = str(diagnostics.get("script_version") or "")
        except Exception:
            version = ""
        versions[kind] = version or "unknown"
        if version != expected_version:
            wrong[kind] = version or "unknown"
    passed = not wrong
    return Check(
        "diagnostic_expected_kinds_versions",
        passed or not strict,
        f"versions={versions}, expected={expected_version}",
        "fail" if strict and not passed else "warn" if not passed else "pass",
    )


def diagnostic_expected_kinds_freshness_check(
    kind_paths: dict[str, Path | None],
    max_age_seconds: float | None,
    strict: bool,
) -> Check | None:
    if max_age_seconds is None:
        return None
    ages: dict[str, float | None] = {}
    stale: dict[str, float | None] = {}
    now = time.time()
    for kind, path in kind_paths.items():
        if not path:
            ages[kind] = None
            stale[kind] = None
            continue
        age = max(0.0, now - path.stat().st_mtime)
        ages[kind] = round(age, 1)
        if age > max_age_seconds:
            stale[kind] = round(age, 1)
    passed = not stale
    return Check(
        "diagnostic_expected_kinds_fresh",
        passed or not strict,
        f"ages={ages}, max={max_age_seconds:.1f}, stale={stale}",
        "fail" if strict and not passed else "warn" if not passed else "pass",
    )


def session_consistency_checks(
    strict: bool = False,
    expected_diagnostic_kinds: list[str] | None = None,
) -> list[Check]:
    checks: list[Check] = []
    sources: list[tuple[str, Path | None]] = [
        ("published", latest_published_raw()),
        ("preview", latest_preview_raw()),
        ("diagnostic", latest_diagnostic_raw_for_kinds(expected_diagnostic_kinds)),
    ]
    sessions: dict[str, str] = {}
    missing_files: list[str] = []
    missing_sessions: list[str] = []
    for label, path in sources:
        if not path:
            missing_files.append(label)
            continue
        try:
            session_id = payload_page_session_id(load_json(path))
        except Exception:
            session_id = ""
        if session_id:
            sessions[label] = session_id
        else:
            missing_sessions.append(label)

    unique_sessions = sorted(set(sessions.values()))
    passed = not missing_files and not missing_sessions and len(unique_sessions) == 1
    checks.append(Check(
        "latest_page_session_consistent",
        passed or not strict,
        f"sessions={sessions}, missing_files={missing_files}, missing_sessions={missing_sessions}",
        "fail" if strict and not passed else "warn" if not passed else "pass",
    ))

    published_path = latest_published_raw()
    scan_started_path = latest_diagnostic_raw_for_kinds(["published_records_scan_started"])
    scan_sessions: dict[str, str] = {}
    scan_missing_files: list[str] = []
    scan_missing_sessions: list[str] = []
    for label, path in [("published", published_path), ("scan_started", scan_started_path)]:
        if not path:
            scan_missing_files.append(label)
            continue
        try:
            scan_session_id = payload_scan_session_id(load_json(path))
        except Exception:
            scan_session_id = ""
        if scan_session_id:
            scan_sessions[label] = scan_session_id
        else:
            scan_missing_sessions.append(label)
    unique_scan_sessions = sorted(set(scan_sessions.values()))
    scan_passed = not scan_missing_files and not scan_missing_sessions and len(unique_scan_sessions) == 1
    checks.append(Check(
        "latest_scan_session_consistent",
        scan_passed or not strict,
        f"sessions={scan_sessions}, missing_files={scan_missing_files}, missing_sessions={scan_missing_sessions}",
        "fail" if strict and not scan_passed else "warn" if not scan_passed else "pass",
    ))
    return checks


def database_checks(db_path: Path | None = None) -> list[Check]:
    db_path = db_path or schema.DB_PATH
    if not db_path.exists():
        return [Check("database_present", False, f"{db_path} missing")]

    conn = sqlite3.connect(str(db_path))
    try:
        queries = [
            ("duplicate_article_identity_groups", "SELECT COUNT(*) FROM (SELECT msg_id, item_idx FROM articles GROUP BY msg_id, item_idx HAVING COUNT(*) > 1)"),
            ("duplicate_title_date_groups", "SELECT COUNT(*) FROM (SELECT title, publish_date FROM articles GROUP BY title, publish_date HAVING COUNT(*) > 1)"),
            ("duplicate_metric_groups", "SELECT COUNT(*) FROM (SELECT article_id, ref_date FROM article_daily_metrics GROUP BY article_id, ref_date HAVING COUNT(*) > 1)"),
            ("duplicate_traffic_groups", "SELECT COUNT(*) FROM (SELECT ref_date, source_type FROM traffic_sources GROUP BY ref_date, source_type HAVING COUNT(*) > 1)"),
            ("blank_traffic_rows", "SELECT COUNT(*) FROM traffic_sources WHERE COALESCE(ref_date, '') = '' AND COALESCE(source_type, '') = ''"),
        ]
        checks = [Check("database_present", True, str(db_path))]
        for name, sql in queries:
            count = conn.execute(sql).fetchone()[0]
            checks.append(Check(name, count == 0, f"count={count}"))
        return checks
    finally:
        conn.close()


def find_article_id(conn: sqlite3.Connection, article: dict[str, Any]) -> int | None:
    msg_id = str(article.get("msg_id", "") or "").strip()
    item_idx = schema.normalize_item_idx(article.get("item_idx", 1))
    title = str(article.get("title", "") or "").strip()
    publish_date = schema.norm_date(article.get("publish_date", "") or "")

    if msg_id:
        row = conn.execute(
            "SELECT id FROM articles WHERE msg_id=? AND item_idx=?",
            (msg_id, item_idx),
        ).fetchone()
        if row:
            return int(row[0])
    if title and publish_date:
        row = conn.execute(
            "SELECT id FROM articles WHERE title=? AND publish_date=? AND item_idx=?",
            (title, publish_date, item_idx),
        ).fetchone()
        if row:
            return int(row[0])
    if title:
        row = conn.execute("SELECT id FROM articles WHERE title=?", (title,)).fetchone()
        if row:
            return int(row[0])
    return None


def latest_raw_database_alignment_checks(db_path: Path | None = None, strict: bool = False) -> list[Check]:
    path = latest_published_raw()
    if not path:
        return [Check(
            "latest_raw_db_raw_present",
            not strict,
            "no published_records raw file found",
            "fail" if strict else "warn",
        )]

    db_path = db_path or schema.DB_PATH
    if not db_path.exists():
        return [Check("latest_raw_db_present", False, f"{db_path} missing")]

    payload = load_json(path)
    articles = schema.dedupe_published_articles(published_articles(payload))
    missing_articles: list[str] = []
    missing_metrics: list[str] = []
    metric_expected = 0

    conn = sqlite3.connect(str(db_path))
    try:
        for article in articles:
            key = schema.published_article_key(article)
            article_id = find_article_id(conn, article)
            if not article_id:
                missing_articles.append(key)
                continue
            total_reads = schema.parse_total_reads(article.get("total_reads", 0) or 0)
            if total_reads > 0:
                metric_expected += 1
                row = conn.execute(
                    "SELECT COUNT(*) FROM article_daily_metrics WHERE article_id=? AND total_read_uv=?",
                    (article_id, total_reads),
                ).fetchone()
                if not row or int(row[0]) == 0:
                    missing_metrics.append(key)
    finally:
        conn.close()

    return [
        Check(
            "latest_raw_db_articles_present",
            not missing_articles,
            f"raw_unique={len(articles)}, missing={len(missing_articles)}"
            + (f", examples={missing_articles[:5]}" if missing_articles else ""),
        ),
        Check(
            "latest_raw_db_metrics_present",
            not missing_metrics,
            f"expected_metrics={metric_expected}, missing={len(missing_metrics)}"
            + (f", examples={missing_metrics[:5]}" if missing_metrics else ""),
        ),
    ]


def synthetic_published_payload() -> dict[str, Any]:
    articles: list[dict[str, Any]] = []
    for i in range(1, 23):
        articles.append({
            "msg_id": str(2247485000 + i),
            "item_idx": 1,
            "title": f"验收文章 {i:02d}",
            "publish_date": "2026-06-16" if i <= 10 else "2026-06-15" if i <= 20 else "2026-06-14",
            "total_reads": str(100 + i),
        })
    return {
        "page_type": "published_records",
        "api_responses": [{
            "url": "published_records_scan",
            "body": {"article_list": articles + [dict(articles[0]), dict(articles[10])]},
        }],
    }


def synthetic_import_checks() -> list[Check]:
    return import_idempotency_checks(
        synthetic_published_payload(),
        "synthetic",
        expected_unique_count=22,
        expected_metric_count=22,
    )


def latest_raw_import_checks(strict: bool = False) -> list[Check]:
    path = latest_published_raw()
    if not path:
        return [Check(
            "latest_import_raw_present",
            not strict,
            "no published_records raw file found",
            "fail" if strict else "warn",
        )]
    payload = load_json(path)
    articles = published_articles(payload)
    expected_unique_count = len(schema.dedupe_published_articles(articles))
    return [
        Check("latest_import_raw_file", True, path.name),
        *import_idempotency_checks(
            payload,
            "latest_import",
            expected_unique_count=expected_unique_count,
            expected_metric_count=None,
        ),
    ]


def import_idempotency_checks(
    payload: dict[str, Any],
    prefix: str,
    expected_unique_count: int | None = None,
    expected_metric_count: int | None = None,
) -> list[Check]:
    old_db, old_raw = schema.DB_PATH, schema.RAW_DIR
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            schema.DB_PATH = root / "mp_analytics.db"
            schema.RAW_DIR = root / "mp_raw"
            schema.init_db()
            first = schema.import_published_records(payload)
            second = schema.import_published_records(payload)
            conn = sqlite3.connect(str(schema.DB_PATH))
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
    except Exception as exc:
        return [Check(f"{prefix}_import_idempotency", False, f"error={exc}")]
    finally:
        schema.DB_PATH, schema.RAW_DIR = old_db, old_raw

    expected_unique_count = expected_unique_count if expected_unique_count is not None else first[0]
    expected_metric_count = expected_metric_count if expected_metric_count is not None else metric_count
    return [
        Check(f"{prefix}_first_import", first == (expected_unique_count, 0), f"result={first}, expected=({expected_unique_count}, 0)"),
        Check(f"{prefix}_second_import", second == (0, expected_unique_count), f"result={second}, expected=(0, {expected_unique_count})"),
        Check(f"{prefix}_article_count", article_count == expected_unique_count, f"count={article_count}, expected={expected_unique_count}"),
        Check(f"{prefix}_metric_count", metric_count == expected_metric_count, f"count={metric_count}, expected={expected_metric_count}"),
        Check(f"{prefix}_duplicate_articles", duplicate_articles == 0, f"count={duplicate_articles}"),
        Check(f"{prefix}_duplicate_metrics", duplicate_metrics == 0, f"count={duplicate_metrics}"),
    ]


def run_checks(args: argparse.Namespace) -> list[Check]:
    checks: list[Check] = []
    checks.extend(validate_latest_raw(
        args.expected_published_count,
        parse_count_list(args.expected_page_counts),
        Path(args.expected_titles_file) if args.expected_titles_file else None,
        args.expected_title_sha256,
        args.expected_script_version,
        args.strict_latest,
        args.max_raw_age_seconds,
    ))
    checks.extend(validate_latest_preview(
        args.expected_preview_count,
        args.expected_script_version,
        args.strict_preview,
        args.max_raw_age_seconds,
    ))
    checks.extend(validate_latest_diagnostic(
        args.expected_script_version,
        args.strict_diagnostic,
        args.max_raw_age_seconds,
        parse_string_list(args.expected_diagnostic_kinds),
    ))
    checks.extend(session_consistency_checks(
        args.strict_session,
        parse_string_list(args.expected_diagnostic_kinds),
    ))
    checks.extend(database_checks())
    checks.extend(latest_raw_database_alignment_checks(strict=args.strict_latest))
    checks.extend(synthetic_import_checks())
    checks.extend(latest_raw_import_checks(args.strict_latest))
    return checks


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate WeChat MP collection accuracy and idempotency.")
    parser.add_argument("--expected-published-count", type=int, default=None)
    parser.add_argument("--expected-page-counts", default=None, help="Comma-separated expected full-scan page counts, e.g. 10,10,2.")
    parser.add_argument("--expected-titles-file", default=None, help="Text or JSON file with expected published titles in order.")
    parser.add_argument("--expected-title-sha256", default=None, help="Expected SHA-256 of normalized published titles in order.")
    parser.add_argument("--expected-preview-count", type=int, default=None)
    parser.add_argument("--expected-diagnostic-kinds", default=None, help="Comma-separated accepted diagnostic kinds.")
    parser.add_argument("--expected-script-version", default="5.0")
    parser.add_argument("--strict-latest", action="store_true", help="Fail if the latest published raw is missing/stale.")
    parser.add_argument("--strict-preview", action="store_true", help="Fail if the latest current-page preview raw is missing/stale.")
    parser.add_argument("--strict-diagnostic", action="store_true", help="Fail if the latest diagnostic raw is missing/stale.")
    parser.add_argument("--strict-session", action="store_true", help="Fail if latest published/preview/diagnostic raw files do not share one page session.")
    parser.add_argument("--max-raw-age-seconds", type=float, default=None, help="Fail if latest raw files are older than this age.")
    parser.add_argument("--watch-seconds", type=float, default=0, help="Wait until checks pass or timeout.")
    parser.add_argument("--poll-interval", type=float, default=2, help="Polling interval for --watch-seconds.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    checks = wait_for_checks(args) if args.watch_seconds else run_checks(args)
    failed = [check for check in checks if not check.passed]

    if args.json:
        print(json.dumps([check.__dict__ for check in checks], ensure_ascii=False, indent=2))
    else:
        for check in checks:
            status = "FAIL" if not check.passed else "WARN" if check.level == "warn" else "PASS"
            print(f"{status} {check.name}: {check.detail}")

    return 1 if failed else 0


def wait_for_checks(args: argparse.Namespace) -> list[Check]:
    deadline = time.time() + max(args.watch_seconds, 0)
    last_checks: list[Check] = []
    while True:
        last_checks = run_checks(args)
        if all(check.passed for check in last_checks):
            return last_checks
        if time.time() >= deadline:
            return last_checks
        time.sleep(max(args.poll_interval, 0.1))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
