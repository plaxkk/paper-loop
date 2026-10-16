"""Internal-only analytics: python -m services.paper_api.analytics [--cleanup]."""
import argparse
import json
import time
from .config import Settings
from .db import connection, initialize


def delete_workspaces(db, settings, owner=None, workspace=None, before=None):
    clause, values = [], []
    if owner:
        clause.append("owner=?")
        values.append(owner)
    if workspace:
        clause.append("id=?")
        values.append(workspace)
    if before is not None:
        clause.append("created<?")
        values.append(before)
    where = " AND ".join(clause) or "1"
    ids = [r[0] for r in db.execute("SELECT id FROM workspaces WHERE " + where, values)]
    # FK cascades also remove jobs, blocking any late worker completion from writing back.
    db.execute("DELETE FROM workspaces WHERE " + where, values)
    for identifier in ids:
        (settings.data_dir / "files" / f"{identifier}.pdf").unlink(missing_ok=True)
    return len(ids)


def cleanup(settings):
    now = time.time()
    cutoff = now - settings.retention_days * 86400
    with connection(settings, True) as db:
        # Aggregate once by removing the source events in this same transaction.
        db.execute("""INSERT INTO aggregates(day,kind,category,value)
          SELECT date(created,'unixepoch'),kind,category,sum(value) FROM events
          WHERE created<? GROUP BY 1,2,3
          ON CONFLICT(day,kind,category) DO UPDATE SET value=value+excluded.value""", (cutoff,))
        db.execute("DELETE FROM events WHERE created<?", (cutoff,))
        # Child records expire by their own creation time even in an active workspace.
        db.execute("DELETE FROM jobs WHERE created<?", (cutoff,))
        db.execute("DELETE FROM messages WHERE created<?", (cutoff,))
        deleted = delete_workspaces(db, settings, before=cutoff)
        db.execute("DELETE FROM events WHERE created<?", (cutoff,))
        db.execute("DELETE FROM quota WHERE kind!='rate' AND day<date(?,'unixepoch')", (cutoff,))
        db.execute("DELETE FROM quota WHERE kind='rate' AND CAST(day AS INTEGER)<?", (int(now // 60) - 60,))
        db.execute("DELETE FROM aggregates WHERE day<date(?,'unixepoch')", (now - settings.aggregate_days * 86400,))
        db.execute("DELETE FROM sessions WHERE created<? AND id NOT IN(SELECT owner FROM workspaces) AND id NOT IN(SELECT owner FROM events) AND id NOT IN(SELECT owner FROM quota)", (cutoff,))
        files = {f"{r[0]}.pdf" for r in db.execute("SELECT id FROM workspaces")}
    for path in (settings.data_dir / "files").glob("*"):
        if path.name not in files and path.stat().st_mtime < now - settings.lease_seconds:
            path.unlink(missing_ok=True)
    return deleted


def report(settings):
    with connection(settings) as db:
        counts = db.execute("""SELECT day,kind,category,sum(value) AS value FROM (
          SELECT date(created,'unixepoch') day,kind,category,value FROM events
          UNION ALL SELECT day,kind,category,value FROM aggregates
          ) GROUP BY day,kind,category ORDER BY day DESC,kind""").fetchall()
        summary = {}
        for row in counts:
            summary[row["kind"]] = summary.get(row["kind"], 0) + row["value"]
        def ratio(numerator, denominator):
            return round(numerator / denominator, 4) if denominator else None
        imports = summary.get("import_started", 0)
        completed = summary.get("import_success", 0)
        engaged = db.execute("SELECT count(DISTINCT workspace) FROM events WHERE kind IN ('claim_view','hint_view','translate_requested','chat_requested','explain_requested')").fetchone()[0]
        recent_ready = db.execute("SELECT count(*) FROM workspaces WHERE status='ready'").fetchone()[0]
        visitors = db.execute("SELECT count(DISTINCT owner) FROM events WHERE kind='visit' AND created<?", (time.time() - 7 * 86400,)).fetchone()[0]
        returned = db.execute("""SELECT count(DISTINCT first.owner) FROM events first JOIN events later
          ON first.owner=later.owner AND later.kind='visit' AND later.created>first.created+86400
          AND later.created<=first.created+7*86400 WHERE first.kind='visit' AND first.created<?""", (time.time() - 7 * 86400,)).fetchone()[0]
        metrics = {
            "classic_continuation_proxy": ratio(summary.get("classic_next", 0), summary.get("classic_open", 0)),
            "import_success_rate": ratio(completed, imports),
            "engaged_workspace_rate_30d": ratio(engaged, recent_ready),
            "return_within_7d_eligible_visitors_30d": visitors,
            "return_within_7d_rate_30d": ratio(returned, visitors),
            "note": "无样本时返回 null；经典连续阅读为点击率代理；清除 Cookie 会影响匿名回访统计。聚合事件不包含原始提问。",
        }
        return {"generated_at": int(time.time()), "summary": summary, "metrics": metrics, "daily": [dict(r) for r in counts]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    initialize(settings)
    if args.cleanup:
        print(json.dumps({"deleted_workspaces": cleanup(settings)}))
    else:
        print(json.dumps(report(settings), ensure_ascii=False, indent=2))
