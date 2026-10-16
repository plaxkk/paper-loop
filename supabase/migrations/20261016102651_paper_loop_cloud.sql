-- Private application data. No browser or Data API table access is granted.
CREATE SCHEMA IF NOT EXISTS paper_loop;
REVOKE ALL ON SCHEMA paper_loop FROM PUBLIC, anon, authenticated;
CREATE TABLE paper_loop.sessions(id TEXT PRIMARY KEY, created DOUBLE PRECISION NOT NULL);
CREATE TABLE paper_loop.workspaces(
 id TEXT PRIMARY KEY, owner TEXT NOT NULL REFERENCES paper_loop.sessions(id),
 title TEXT NOT NULL, source_key TEXT NOT NULL, source TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'queued', error TEXT, filename TEXT,
 created DOUBLE PRECISION NOT NULL, page INTEGER NOT NULL DEFAULT 1,
 pages TEXT NOT NULL DEFAULT '[]', blocks TEXT NOT NULL DEFAULT '[]',
 overview TEXT, analysis_error TEXT, UNIQUE(owner,source_key));
CREATE INDEX workspaces_owner ON paper_loop.workspaces(owner,created);
CREATE TABLE paper_loop.jobs(
 id TEXT PRIMARY KEY, workspace TEXT NOT NULL REFERENCES paper_loop.workspaces(id) ON DELETE CASCADE,
 kind TEXT NOT NULL, payload TEXT NOT NULL, cache_key TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'queued', result TEXT, error TEXT,
 created DOUBLE PRECISION NOT NULL, lease DOUBLE PRECISION, claim TEXT,
 checkpoint TEXT NOT NULL DEFAULT '{}', UNIQUE(workspace,cache_key));
CREATE INDEX jobs_queue ON paper_loop.jobs(status,created);
CREATE TABLE paper_loop.messages(
 id TEXT PRIMARY KEY, workspace TEXT NOT NULL REFERENCES paper_loop.workspaces(id) ON DELETE CASCADE,
 role TEXT NOT NULL, content TEXT NOT NULL, citations TEXT NOT NULL DEFAULT '[]',
 created DOUBLE PRECISION NOT NULL, job TEXT REFERENCES paper_loop.jobs(id) ON DELETE CASCADE);
CREATE TABLE paper_loop.events(
 id TEXT PRIMARY KEY, owner TEXT NOT NULL, workspace TEXT REFERENCES paper_loop.workspaces(id) ON DELETE CASCADE,
 kind TEXT NOT NULL, category TEXT NOT NULL, value DOUBLE PRECISION NOT NULL DEFAULT 1,
 created DOUBLE PRECISION NOT NULL);
CREATE TABLE paper_loop.quota(
 owner TEXT NOT NULL, day TEXT NOT NULL, kind TEXT NOT NULL, amount INTEGER NOT NULL,
 PRIMARY KEY(owner,day,kind));
CREATE TABLE paper_loop.aggregates(
 day TEXT NOT NULL, kind TEXT NOT NULL, category TEXT NOT NULL, value DOUBLE PRECISION NOT NULL,
 PRIMARY KEY(day,kind,category));
CREATE TABLE paper_loop.maintenance(name TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE paper_loop.file_deletions(id TEXT PRIMARY KEY, created DOUBLE PRECISION NOT NULL);
DO $$ DECLARE item record; BEGIN
 FOR item IN SELECT tablename FROM pg_tables WHERE schemaname='paper_loop' LOOP
  EXECUTE format('ALTER TABLE paper_loop.%I ENABLE ROW LEVEL SECURITY',item.tablename);
 END LOOP;
END $$;
REVOKE ALL ON ALL TABLES IN SCHEMA paper_loop FROM PUBLIC, anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA paper_loop REVOKE ALL ON TABLES FROM PUBLIC, anon, authenticated;
INSERT INTO storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
VALUES('paper-pdfs','paper-pdfs',false,31457280,ARRAY['application/pdf'])
ON CONFLICT(id) DO UPDATE SET public=false,file_size_limit=31457280,allowed_mime_types=ARRAY['application/pdf'];
