from contextlib import contextmanager
import hashlib
import json
import sqlite3
import time
import uuid


def uid():
    return uuid.uuid4().hex


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def encode(value):
    return json.dumps(value, ensure_ascii=False)


@contextmanager
def connection(settings, write=False):
    if settings.database_url:
        from .postgres import connect
        with connect(settings, write) as db:
            yield db
        return
    db = sqlite3.connect(settings.database, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        if write:
            db.execute("BEGIN IMMEDIATE")
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def initialize(settings):
    settings.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    (settings.data_dir / "files").mkdir(exist_ok=True, mode=0o700)
    if settings.serverless and (not settings.database_url or not settings.supabase_url or not settings.storage_key):
        raise RuntimeError("Cloud database and private storage must be configured before enabling the service.")
    if settings.database_url:
        with connection(settings) as db:
            if not db.execute("SELECT to_regclass('paper_loop.workspaces')").fetchone()[0]:
                raise RuntimeError("Apply the Paper Loop database migration before starting the API.")
        return
    with connection(settings) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript("""
        CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS workspaces(
          id TEXT PRIMARY KEY, owner TEXT NOT NULL REFERENCES sessions(id),
          title TEXT NOT NULL, source_key TEXT NOT NULL, source TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'queued', error TEXT, filename TEXT,
          created REAL NOT NULL, page INTEGER NOT NULL DEFAULT 1,
          pages TEXT NOT NULL DEFAULT '[]', blocks TEXT NOT NULL DEFAULT '[]',
          overview TEXT, analysis_error TEXT, UNIQUE(owner,source_key));
        CREATE TABLE IF NOT EXISTS jobs(
          id TEXT PRIMARY KEY, workspace TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
          kind TEXT NOT NULL, payload TEXT NOT NULL, cache_key TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'queued', result TEXT, error TEXT,
          created REAL NOT NULL, lease REAL, claim TEXT,
          checkpoint TEXT NOT NULL DEFAULT '{}', UNIQUE(workspace,cache_key));
        CREATE INDEX IF NOT EXISTS jobs_queue ON jobs(status,created);
        CREATE TABLE IF NOT EXISTS messages(
          id TEXT PRIMARY KEY, workspace TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
          role TEXT NOT NULL, content TEXT NOT NULL, citations TEXT NOT NULL DEFAULT '[]',
          created REAL NOT NULL, job TEXT REFERENCES jobs(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS events(
          id TEXT PRIMARY KEY, owner TEXT NOT NULL, workspace TEXT REFERENCES workspaces(id) ON DELETE CASCADE,
          kind TEXT NOT NULL, category TEXT NOT NULL, value REAL NOT NULL DEFAULT 1,
          created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS quota(
          owner TEXT NOT NULL, day TEXT NOT NULL, kind TEXT NOT NULL, amount INTEGER NOT NULL,
          PRIMARY KEY(owner,day,kind));
        CREATE TABLE IF NOT EXISTS maintenance(name TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS file_deletions(id TEXT PRIMARY KEY, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS aggregates(
          day TEXT NOT NULL, kind TEXT NOT NULL, category TEXT NOT NULL, value REAL NOT NULL,
          PRIMARY KEY(day,kind,category));
        """)
        if "checkpoint" not in {r[1] for r in db.execute("PRAGMA table_info(jobs)")}:
            db.execute("ALTER TABLE jobs ADD COLUMN checkpoint TEXT NOT NULL DEFAULT '{}'")


def event(db, owner, workspace, kind, category="", value=1):
    db.execute("INSERT INTO events VALUES(?,?,?,?,?,?,?)", (uid(), owner, workspace, kind, category, value, time.time()))


def enqueue(db, workspace, kind, payload, cache_key):
    existing = db.execute("SELECT * FROM jobs WHERE workspace=? AND cache_key=?", (workspace, cache_key)).fetchone()
    if existing:
        if existing["status"] == "failed":
            db.execute("UPDATE jobs SET status='queued', error=NULL, lease=NULL, claim=NULL WHERE id=?", (existing["id"],))
        return existing["id"]
    job = uid()
    db.execute("INSERT INTO jobs(id,workspace,kind,payload,cache_key,created) VALUES(?,?,?,?,?,?)", (job, workspace, kind, encode(payload), cache_key, time.time()))
    return job
