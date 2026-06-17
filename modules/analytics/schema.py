#!/usr/bin/env python3
"""
微信公众号数据 Schema & 解析入库 v2
- 建表：文章、日指标、渠道来源、趋势、汇总
- 解析 WeChat MP API 响应 → 结构化入库
"""
from __future__ import annotations

import json
import hashlib
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "data" / "mp_analytics.db"
RAW_DIR = BASE_DIR / "data" / "mp_raw"
SQLITE_TIMEOUT_SECONDS = 30
SQLITE_BUSY_TIMEOUT_MS = SQLITE_TIMEOUT_SECONDS * 1000

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    msg_id TEXT NOT NULL,
    item_idx INTEGER NOT NULL DEFAULT 1,
    title TEXT NOT NULL,
    publish_date TEXT,
    first_seen TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    last_updated TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(msg_id, item_idx)
);

CREATE TABLE IF NOT EXISTS article_daily_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL,
    ref_date TEXT NOT NULL,
    total_read_uv INTEGER DEFAULT 0,
    read_uv_ratio REAL DEFAULT 0,
    share_uv INTEGER DEFAULT 0,
    captured_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    FOREIGN KEY(article_id) REFERENCES articles(id),
    UNIQUE(article_id, ref_date)
);

CREATE TABLE IF NOT EXISTS traffic_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ref_date TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_name TEXT,
    read_uv INTEGER DEFAULT 0,
    read_uv_ratio REAL DEFAULT 0,
    captured_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS trend_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL,
    snapshot_date TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL DEFAULT 0,
    captured_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    FOREIGN KEY(article_id) REFERENCES articles(id),
    UNIQUE(article_id, snapshot_date, metric_name)
);

CREATE TABLE IF NOT EXISTS summary_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ref_date TEXT NOT NULL,
    metric_id TEXT NOT NULL,
    metric_name TEXT,
    metric_value REAL DEFAULT 0,
    metric_type TEXT DEFAULT 'daily',
    captured_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(ref_date, metric_id)
);

CREATE TABLE IF NOT EXISTS collection_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_type TEXT NOT NULL,
    collected_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    api_count INTEGER DEFAULT 0,
    articles_found INTEGER DEFAULT 0,
    raw_file TEXT
);

CREATE INDEX IF NOT EXISTS idx_daily_article_date ON article_daily_metrics(article_id, ref_date);
CREATE INDEX IF NOT EXISTS idx_trends_article_date ON trend_snapshots(article_id, snapshot_date);
CREATE INDEX IF NOT EXISTS idx_traffic_date ON traffic_sources(ref_date);
CREATE INDEX IF NOT EXISTS idx_summary_date ON summary_metrics(ref_date);

-- ── User Analysis Tables ──
CREATE TABLE IF NOT EXISTS user_daily_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ref_date TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_name TEXT,
    new_user INTEGER DEFAULT 0,
    cancel_user INTEGER DEFAULT 0,
    netgain_user INTEGER DEFAULT 0,
    cumulate_user INTEGER DEFAULT 0,
    captured_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(ref_date, source_id)
);

CREATE TABLE IF NOT EXISTS account_info (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nick_name TEXT,
    fake_id TEXT,
    service_type INTEGER,
    alias TEXT,
    mass_send_left INTEGER,
    captured_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_user_daily_date ON user_daily_metrics(ref_date);

"""


def connect_db(path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path or DB_PATH), timeout=SQLITE_TIMEOUT_SECONDS)
    conn.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
    return conn


def init_db() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = connect_db()
    try:
        conn.executescript(SCHEMA_SQL)
        migrate_article_identity(conn)
        repair_article_foreign_keys(conn)
        migrate_dedupe_tables(conn)
        ensure_indexes(conn)
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_traffic_unique_date_source
            ON traffic_sources(ref_date, source_type)
        """)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def migrate_article_identity(conn: sqlite3.Connection) -> None:
    """Allow one WeChat message to contain multiple articles via item_idx."""
    if not table_exists(conn, "articles"):
        return

    if article_identity_is_composite(conn):
        recover_partial_article_migration(conn)
        return

    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("""
        CREATE TABLE articles_new (
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
    copy_article_rows_from(conn, "articles", "articles_new")
    conn.execute("DROP TABLE articles")
    conn.execute("ALTER TABLE articles_new RENAME TO articles")


def recover_partial_article_migration(conn: sqlite3.Connection) -> None:
    """Complete a previous interrupted article identity migration if needed."""
    if not table_exists(conn, "articles_old"):
        return

    new_count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    old_count = conn.execute("SELECT COUNT(*) FROM articles_old").fetchone()[0]
    if old_count == 0:
        conn.execute("DROP TABLE articles_old")
        return
    if new_count == 0:
        copy_article_rows_from(conn, "articles_old", "articles")
        conn.execute("DROP TABLE articles_old")
        return

    copy_article_rows_from(conn, "articles_old", "articles")
    missing = conn.execute("""
        SELECT COUNT(*)
        FROM articles_old old
        WHERE NOT EXISTS (
            SELECT 1 FROM articles new WHERE new.id = old.id
        )
    """).fetchone()[0]
    if missing == 0:
        conn.execute("DROP TABLE articles_old")


def copy_article_rows_from(conn: sqlite3.Connection, source_table: str, target_table: str) -> None:
    source = quote_identifier(source_table)
    target = quote_identifier(target_table)
    conn.execute(f"""
        INSERT OR IGNORE INTO {target} (id, msg_id, item_idx, title, publish_date, first_seen, last_updated)
        SELECT
            id,
            msg_id,
            COALESCE(item_idx, 1),
            title,
            publish_date,
            COALESCE(first_seen, datetime('now','localtime')),
            COALESCE(last_updated, datetime('now','localtime'))
        FROM {source}
        WHERE id IN (
            SELECT MIN(id)
            FROM {source}
            GROUP BY msg_id, COALESCE(item_idx, 1)
        )
    """)


def repair_article_foreign_keys(conn: sqlite3.Connection) -> None:
    for table_name in ("article_daily_metrics", "trend_snapshots"):
        if not table_exists(conn, table_name):
            continue
        foreign_keys = conn.execute(
            f"PRAGMA foreign_key_list({quote_identifier(table_name)})"
        ).fetchall()
        if any(row[2] == "articles_old" for row in foreign_keys):
            rebuild_table_with_article_fk(conn, table_name)


def rebuild_table_with_article_fk(conn: sqlite3.Connection, table_name: str) -> None:
    table = quote_identifier(table_name)
    temp_table_name = f"{table_name}_fk_repair_old"
    temp_table = quote_identifier(temp_table_name)
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    if not row or not row[0]:
        return

    create_sql = (
        row[0]
        .replace('REFERENCES "articles_old"', "REFERENCES articles")
        .replace("REFERENCES articles_old", "REFERENCES articles")
    )
    conn.execute("PRAGMA foreign_keys = OFF")
    if table_exists(conn, temp_table_name):
        conn.execute(f"DROP TABLE {temp_table}")
    conn.execute(f"ALTER TABLE {table} RENAME TO {temp_table}")
    conn.execute(create_sql)

    old_columns = table_columns(conn, temp_table_name)
    new_columns = table_columns(conn, table_name)
    common_columns = [column for column in old_columns if column in new_columns]
    if common_columns:
        columns_sql = ", ".join(quote_identifier(column) for column in common_columns)
        conn.execute(f"""
            INSERT INTO {table} ({columns_sql})
            SELECT {columns_sql} FROM {temp_table}
        """)
    conn.execute(f"DROP TABLE {temp_table}")


def table_columns(conn: sqlite3.Connection, table_name: str) -> list[str]:
    return [
        row[1]
        for row in conn.execute(f"PRAGMA table_info({quote_identifier(table_name)})").fetchall()
    ]


def ensure_indexes(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_daily_article_date ON article_daily_metrics(article_id, ref_date);
        CREATE INDEX IF NOT EXISTS idx_trends_article_date ON trend_snapshots(article_id, snapshot_date);
        CREATE INDEX IF NOT EXISTS idx_traffic_date ON traffic_sources(ref_date);
        CREATE INDEX IF NOT EXISTS idx_summary_date ON summary_metrics(ref_date);
        CREATE INDEX IF NOT EXISTS idx_user_daily_date ON user_daily_metrics(ref_date);
    """)


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return bool(row)


def article_identity_is_composite(conn: sqlite3.Connection) -> bool:
    for index in conn.execute("PRAGMA index_list(articles)").fetchall():
        is_unique = int(index[2]) == 1
        if not is_unique:
            continue
        columns = [
            row[2]
            for row in conn.execute(f"PRAGMA index_info({quote_identifier(index[1])})").fetchall()
        ]
        if columns == ["msg_id", "item_idx"]:
            return True
    return False


def quote_identifier(value: str) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def migrate_dedupe_tables(conn: sqlite3.Connection) -> None:
    """Clean historical duplicates before unique indexes are enforced."""
    conn.execute("""
        DELETE FROM traffic_sources
        WHERE COALESCE(ref_date, '') = ''
          AND COALESCE(source_type, '') = ''
    """)
    conn.execute("""
        DELETE FROM traffic_sources
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM traffic_sources
            GROUP BY ref_date, source_type
        )
    """)


def norm_date(s: str) -> str:
    """Normalize date strings to YYYY-MM-DD."""
    s = str(s).strip()
    # "2026/05/12" → "2026-05-12"
    s = s.replace("/", "-")
    return s


def normalize_item_idx(value: Any) -> int:
    try:
        item_idx = int(str(value).strip() or "1")
    except (TypeError, ValueError):
        return 1
    return item_idx if item_idx > 0 else 1


def parse_tendency_list(raw: str) -> list[dict]:
    """
    Parse tendency_list compressed format.
    Example: "20260610_2,102,52,38,..." 
    First part is the start date, rest are daily values over ~30 days.
    Returns list of {snapshot_date, metric_value}
    """
    if not raw or not isinstance(raw, str):
        return []
    m = re.match(r"(\d{8})_(.+)", raw)
    if not m:
        return []
    try:
        start_date = datetime.strptime(m.group(1), "%Y%m%d")
        values = [int(v) for v in m.group(2).split(",")]
    except (ValueError, OverflowError):
        return []
    
    result = []
    for i, val in enumerate(values):
        d = datetime(start_date.year, start_date.month, start_date.day)
        # Each value is one day, going backwards from start_date
        # Subtract i days
        from datetime import timedelta
        d = start_date - timedelta(days=i)
        result.append({
            "snapshot_date": d.strftime("%Y-%m-%d"),
            "metric_value": val,
        })
    return result


def parse_content_analysis(raw_file: Path) -> dict:
    """Parse a raw content_analysis JSON into structured records."""
    data = json.loads(raw_file.read_text(encoding="utf-8"))
    api_responses = data.get("api_responses", [])
    
    result = {
        "articles": [],
        "daily_metrics": [],
        "traffic_sources": [],
        "trends": [],
        "summary_metrics": [],
    }

    for resp in api_responses:
        body = resp.get("body", {})
        if not isinstance(body, dict):
            continue
        url = resp.get("url", "")

        # --- Summary KPI cards ---
        for item in body.get("mgr_list", []):
            if isinstance(item, dict):
                result["summary_metrics"].append({
                    "ref_date": datetime.now().strftime("%Y-%m-%d"),
                    "metric_id": str(item.get("id", "")),
                    "metric_name": item.get("name", ""),
                    "metric_value": float(item.get("value", 0) or 0),
                    "metric_type": "daily_summary",
                })

        # --- Per-article data ---
        collect_date = datetime.now().strftime("%Y-%m-%d")  # 采集日期，用于差分追踪
        for article in body.get("article_list", []):
            if not isinstance(article, dict):
                continue
            msg_id = str(article.get("msg_id", ""))
            title = article.get("title", "")
            publish_date = norm_date(article.get("ref_date", ""))  # 发布日期
            item_idx = normalize_item_idx(article.get("item_idx", 1))

            if not msg_id:
                continue

            # Article record (use publish_date for article metadata)
            result["articles"].append({
                "msg_id": msg_id,
                "item_idx": item_idx,
                "title": title,
                "publish_date": publish_date,
            })

            # Daily metrics — use COLLECTION date so each snapshot creates a new row
            result["daily_metrics"].append({
                "msg_id": msg_id,
                "item_idx": item_idx,
                "ref_date": collect_date,
                "total_read_uv": int(article.get("total_read_uv", 0) or 0),
                "read_uv_ratio": float(article.get("read_uv_ratio", 0) or 0),
                "share_uv": int(article.get("share_uv", 0) or 0),
            })

            # Trend data from tendency_list
            tl = article.get("tendency_list", "")
            if tl:
                for point in parse_tendency_list(tl):
                    result["trends"].append({
                        "msg_id": msg_id,
                        "item_idx": item_idx,
                        **point,
                    })

        # --- Traffic source data ---
        source_data = body.get("all_article_stat_source", {})
        for entry in source_data.get("list", []):
            if isinstance(entry, dict):
                result["traffic_sources"].append({
                    "ref_date": norm_date(entry.get("ref_date", "")),
                    "source_type": str(entry.get("user_source", "")),
                    "source_name": entry.get("source_name", ""),
                    "read_uv": int(entry.get("read_uv", 0) or 0),
                    "read_uv_ratio": float(entry.get("read_uv_ratio", 0) or 0),
                })

    return result


import re
from datetime import datetime, timedelta


def parse_user_analysis(raw_file: Path) -> dict:
    """Parse a raw user_analysis JSON into structured records."""
    data = json.loads(raw_file.read_text(encoding="utf-8"))
    api_responses = data.get("api_responses", [])

    SOURCE_NAMES = {
        "99999999": "全部来源汇总",
        "0": "全部来源",
        "1": "公众号搜索",
        "17": "名片分享",
        "30": "扫描二维码",
        "57": "文章内账号名称",
        "100": "微信广告",
        "149": "视频号",
        "161": "小程序",
        "200": "其他合计",
        "201": "其他",
    }

    result = {"account_info": {}, "user_daily": []}

    for resp in api_responses:
        body = resp.get("body", {})
        if not isinstance(body, dict):
            continue
        ui = body.get("user_info", {})
        if ui and not result["account_info"]:
            result["account_info"] = {
                "nick_name": ui.get("nick_name", ""),
                "fake_id": ui.get("fake_id", ""),
                "service_type": ui.get("service_type", 0),
                "alias": ui.get("alias", ""),
                "mass_send_left": ui.get("mass_send_left", 0),
            }
        for cat in body.get("category_list", []):
            if not isinstance(cat, dict):
                continue
            source_id = str(cat.get("user_source", ""))
            for item in cat.get("list", []):
                if not isinstance(item, dict):
                    continue
                result["user_daily"].append({
                    "ref_date": item.get("date", ""),
                    "source_id": source_id,
                    "source_name": SOURCE_NAMES.get(source_id, f"来源{source_id}"),
                    "new_user": int(item.get("new_user", 0) or 0),
                    "cancel_user": int(item.get("cancel_user", 0) or 0),
                    "netgain_user": int(item.get("netgain_user", 0) or 0),
                    "cumulate_user": int(item.get("cumulate_user", 0) or 0),
                })
    return result


def store_parsed(parsed: dict, raw_file: Path) -> dict:
    """Store parsed records. Returns counts per table."""
    conn = connect_db()
    cur = conn.cursor()
    counts = {"articles": 0, "daily": 0, "traffic": 0, "trends": 0, "summary": 0, "user_daily": 0, "account": 0}

    try:
        # Articles (content_analysis only)
        for a in parsed.get("articles", []):
            item_idx = normalize_item_idx(a.get("item_idx", 1))
            cur.execute("""
                INSERT INTO articles (msg_id, item_idx, title, publish_date, last_updated)
                VALUES (?,?,?,?,datetime('now','localtime'))
                ON CONFLICT(msg_id, item_idx) DO UPDATE SET
                    title=excluded.title,
                    publish_date=COALESCE(excluded.publish_date, articles.publish_date),
                    last_updated=datetime('now','localtime')
            """, (a["msg_id"], item_idx, a["title"], a["publish_date"]))
            counts["articles"] += 1

        # Build article_id map
        cur.execute("SELECT msg_id, item_idx, id FROM articles")
        article_to_id = {(r[0], normalize_item_idx(r[1])): r[2] for r in cur.fetchall()}

        # Daily metrics
        for dm in parsed.get("daily_metrics", []):
            aid = article_to_id.get((dm["msg_id"], normalize_item_idx(dm.get("item_idx", 1))))
            if not aid:
                continue
            try:
                cur.execute("""
                    INSERT OR REPLACE INTO article_daily_metrics
                    (article_id, ref_date, total_read_uv, read_uv_ratio, share_uv, captured_at)
                    VALUES (?,?,?,?,?,datetime('now','localtime'))
                """, (aid, dm["ref_date"], dm["total_read_uv"], dm["read_uv_ratio"], dm["share_uv"]))
                counts["daily"] += 1
            except Exception as e:
                print(f"  [warn] daily insert failed for {dm['msg_id']}: {e}")

        # Traffic sources
        for ts in parsed.get("traffic_sources", []):
            if not ts.get("ref_date") or not ts.get("source_type"):
                continue
            try:
                cur.execute("""
                    INSERT INTO traffic_sources
                    (ref_date, source_type, source_name, read_uv, read_uv_ratio, captured_at)
                    VALUES (?,?,?,?,?,datetime('now','localtime'))
                    ON CONFLICT(ref_date, source_type) DO UPDATE SET
                        source_name=excluded.source_name,
                        read_uv=excluded.read_uv,
                        read_uv_ratio=excluded.read_uv_ratio,
                        captured_at=datetime('now','localtime')
                """, (ts["ref_date"], ts["source_type"], ts["source_name"], ts["read_uv"], ts["read_uv_ratio"]))
                counts["traffic"] += 1
            except Exception as e:
                print(f"  [warn] traffic insert failed: {e}")

        # Trends
        for td in parsed.get("trends", []):
            aid = article_to_id.get((td["msg_id"], normalize_item_idx(td.get("item_idx", 1))))
            if not aid:
                continue
            try:
                cur.execute("""
                    INSERT OR REPLACE INTO trend_snapshots
                    (article_id, snapshot_date, metric_name, metric_value, captured_at)
                    VALUES (?,?,?,?,datetime('now','localtime'))
                """, (aid, td["snapshot_date"], "read_uv_trend", td["metric_value"]))
                counts["trends"] += 1
            except Exception as e:
                pass  # ignore duplicate key errors silently

        # User daily metrics
        for ud in parsed.get("user_daily", []):
            try:
                cur.execute("""
                    INSERT OR REPLACE INTO user_daily_metrics
                    (ref_date, source_id, source_name, new_user, cancel_user, netgain_user, cumulate_user, captured_at)
                    VALUES (?,?,?,?,?,?,?,datetime('now','localtime'))
                """, (ud["ref_date"], ud["source_id"], ud["source_name"],
                      ud["new_user"], ud["cancel_user"], ud["netgain_user"], ud["cumulate_user"]))
                counts["user_daily"] += 1
            except Exception:
                pass

        # Account info (keep latest only)
        ai = parsed.get("account_info", {})
        if ai:
            try:
                cur.execute("DELETE FROM account_info")
                cur.execute("""
                    INSERT INTO account_info (nick_name, fake_id, service_type, alias, mass_send_left)
                    VALUES (?,?,?,?,?)
                """, (ai.get("nick_name"), ai.get("fake_id"), ai.get("service_type"),
                      ai.get("alias"), ai.get("mass_send_left")))
                counts["account"] += 1
            except Exception:
                pass

        # Summary metrics
        for sm in parsed.get("summary_metrics", []):
            try:
                cur.execute("""
                    INSERT OR REPLACE INTO summary_metrics
                    (ref_date, metric_id, metric_name, metric_value, metric_type, captured_at)
                    VALUES (?,?,?,?,?,datetime('now','localtime'))
                """, (sm["ref_date"], sm["metric_id"], sm["metric_name"], sm["metric_value"], sm["metric_type"]))
                counts["summary"] += 1
            except Exception as e:
                print(f"  [warn] summary insert failed: {e}")

        # Collection log — detect page type
        page_type = "content_analysis" if parsed.get("articles") else "user_analysis" if parsed.get("user_daily") else "unknown"
        article_count = counts.get("articles", 0)
        api_count = len(parsed.get("daily_metrics", [])) or len(parsed.get("user_daily", []))
        cur.execute("""
            INSERT INTO collection_log (page_type, api_count, articles_found, raw_file)
            VALUES (?, ?, ?, ?)
        """, (page_type, api_count, article_count, str(raw_file)))

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return counts


def stats() -> dict:
    conn = connect_db()
    conn.row_factory = sqlite3.Row
    try:
        return {
            "articles": conn.execute("SELECT COUNT(*) n FROM articles").fetchone()["n"],
            "daily_metrics": conn.execute("SELECT COUNT(*) n FROM article_daily_metrics").fetchone()["n"],
            "traffic_sources": conn.execute("SELECT COUNT(*) n FROM traffic_sources").fetchone()["n"],
            "trends": conn.execute("SELECT COUNT(*) n FROM trend_snapshots").fetchone()["n"],
            "summary_metrics": conn.execute("SELECT COUNT(*) n FROM summary_metrics").fetchone()["n"],
            "user_daily": conn.execute("SELECT COUNT(*) n FROM user_daily_metrics").fetchone()["n"],
            "collections": conn.execute("SELECT COUNT(*) n FROM collection_log").fetchone()["n"],
        }
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    
    # Wipe and reparse from existing raw files
    conn = connect_db()
    conn.execute("DELETE FROM trend_snapshots")
    conn.execute("DELETE FROM traffic_sources")
    conn.execute("DELETE FROM article_daily_metrics")
    conn.execute("DELETE FROM summary_metrics")
    conn.execute("DELETE FROM collection_log")
    conn.execute("DELETE FROM articles")
    conn.execute("DELETE FROM sqlite_sequence")
    conn.commit()
    conn.close()
    
    raw_files = sorted(RAW_DIR.glob("*content_analysis*.json"))
    for rf in raw_files:
        print(f"Parsing: {rf.name}")
        parsed = parse_content_analysis(rf)
        counts = store_parsed(parsed, rf)
        print(f"  → articles:{counts['articles']} daily:{counts['daily']} "
              f"traffic:{counts['traffic']} trends:{counts['trends']} summary:{counts['summary']}")

    s = stats()
    print(f"\nDB stats: {s}")


def import_published_records(data: dict) -> tuple[int, int]:
    """
    Import articles from the published records page scan.
    Called when collector receives page_type='published_records'.
    Extracts msg_id, title, publish_date, total_reads from the scan data.
    Returns (new_count, updated_count).
    """
    init_db()
    conn = connect_db()
    cur = conn.cursor()

    article_list = []
    for resp in data.get("api_responses", []):
        body = resp.get("body", {})
        items = body.get("article_list", [])
        for item in items:
            if isinstance(item, dict):
                article_list.append(item)

    try:
        new_count, updated_count = 0, 0
        for a in dedupe_published_articles(article_list):
            msg_id = str(a.get("msg_id", "") or "").strip()
            item_idx = normalize_item_idx(a.get("item_idx", 1))
            title = str(a.get("title", ""))
            publish_date = a.get("publish_date", "")
            total_reads = parse_total_reads(a.get("total_reads", 0) or 0)

            if not msg_id and not title:
                continue

            # Normalize publish_date
            if publish_date:
                publish_date = norm_date(publish_date)

            # Try to find by msg_id first, then by title+publish_date
            existing_id = None
            if msg_id:
                cur.execute(
                    "SELECT id FROM articles WHERE msg_id=? AND item_idx=?",
                    (msg_id, item_idx),
                )
                row = cur.fetchone()
                if row:
                    existing_id = row[0]

            if not existing_id and not msg_id and title and publish_date:
                cur.execute(
                    "SELECT id FROM articles WHERE title=? AND publish_date=? AND item_idx=?",
                    (title, publish_date, item_idx),
                )
                row = cur.fetchone()
                if row:
                    existing_id = row[0]

            stable_msg_id = msg_id or fallback_msg_id(title, publish_date, item_idx)
            if not existing_id and stable_msg_id:
                cur.execute(
                    "SELECT id FROM articles WHERE msg_id=? AND item_idx=?",
                    (stable_msg_id, item_idx),
                )
                row = cur.fetchone()
                if row:
                    existing_id = row[0]

            if existing_id:
                if msg_id:
                    cur.execute(
                        "SELECT id FROM articles WHERE msg_id=? AND item_idx=? AND id<>?",
                        (msg_id, item_idx, existing_id),
                    )
                    target = cur.fetchone()
                    if target:
                        existing_id = target[0]
                # Update existing
                cur.execute("""
                    UPDATE articles SET 
                        msg_id=CASE
                            WHEN ? != '' AND msg_id LIKE 'dom_%' THEN ?
                            ELSE msg_id
                        END,
                        item_idx=?,
                        title=COALESCE(?, title),
                        publish_date=COALESCE(?, publish_date),
                        last_updated=datetime('now','localtime')
                    WHERE id=?
                """, (msg_id, msg_id, item_idx, title or None, publish_date or None, existing_id))
                updated_count += 1
            else:
                # Insert new
                cur.execute("""
                    INSERT INTO articles (msg_id, item_idx, title, publish_date)
                    VALUES (?, ?, ?, ?)
                """, (stable_msg_id, item_idx, title, publish_date))
                new_count += 1

            aid = existing_id or cur.lastrowid
            if aid and total_reads > 0:
                import_date = datetime.now().strftime("%Y-%m-%d")
                cur.execute("""
                    INSERT OR REPLACE INTO article_daily_metrics
                    (article_id, ref_date, total_read_uv, read_uv_ratio, share_uv, captured_at)
                    VALUES (?, ?, ?, 0, 0, datetime('now','localtime'))
                """, (aid, import_date, total_reads))

        conn.commit()
        return new_count, updated_count
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def dedupe_published_articles(article_list: list[dict]) -> list[dict]:
    """Keep one record per article before importing a published-record scan."""
    deduped: list[dict] = []
    seen: set[str] = set()
    for article in article_list:
        key = published_article_key(article)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(article)
    return deduped


def published_article_key(article: dict) -> str:
    msg_id = str(article.get("msg_id", "") or "").strip()
    item_idx = str(normalize_item_idx(article.get("item_idx", 1)))
    title = str(article.get("title", "") or "").strip()
    publish_date = norm_date(article.get("publish_date", "") or "")
    if msg_id:
        return f"id:{msg_id}:{item_idx}"
    if title and publish_date:
        return f"title_date:{title}:{publish_date}:{item_idx}"
    if title:
        return f"title:{title}:{item_idx}"
    return ""


def parse_total_reads(value: Any) -> int:
    if isinstance(value, str) and "万" in value:
        try:
            return round(float(value.replace(",", "").replace("万", "").strip()) * 10000)
        except ValueError:
            return 0
    try:
        return int(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return 0


def fallback_msg_id(title: str, publish_date: str, item_idx: Any = 1) -> str:
    raw = f"{title}|{publish_date}|{normalize_item_idx(item_idx)}".encode("utf-8")
    return "dom_" + hashlib.sha1(raw).hexdigest()[:16]
