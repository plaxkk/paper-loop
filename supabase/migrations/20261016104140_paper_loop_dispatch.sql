-- Durable wakeups use only a server-side secret stored in Supabase Vault.
CREATE EXTENSION IF NOT EXISTS pg_cron;
CREATE EXTENSION IF NOT EXISTS pg_net;
CREATE OR REPLACE FUNCTION paper_loop.dispatch_worker() RETURNS void
LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
DECLARE worker_key text;
BEGIN
 IF NOT (
  EXISTS(SELECT 1 FROM paper_loop.jobs WHERE status='queued' OR (status='running' AND lease<extract(epoch from now())))
  OR EXISTS(SELECT 1 FROM paper_loop.file_deletions)
  OR NOT EXISTS(SELECT 1 FROM paper_loop.maintenance WHERE name='cleanup' AND value=(floor(extract(epoch from now())/3600)::bigint)::text)
 ) THEN RETURN; END IF;
 SELECT decrypted_secret INTO worker_key FROM vault.decrypted_secrets WHERE name='paper_loop_worker_secret';
 IF worker_key IS NULL THEN RETURN; END IF;
 PERFORM net.http_post(url:='https://paper-loop-xi.vercel.app/api/internal/tick',body:='{}'::jsonb,
  headers:=jsonb_build_object('Content-Type','application/json','Authorization','Bearer '||worker_key),timeout_milliseconds:=240000);
END $$;
REVOKE ALL ON FUNCTION paper_loop.dispatch_worker() FROM PUBLIC,anon,authenticated;
CREATE OR REPLACE FUNCTION paper_loop.wake_job() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
BEGIN
 IF NEW.status='queued' THEN PERFORM paper_loop.dispatch_worker(); END IF;
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION paper_loop.wake_job() FROM PUBLIC,anon,authenticated;
CREATE TRIGGER paper_loop_job_wakeup AFTER INSERT OR UPDATE OF status ON paper_loop.jobs
FOR EACH ROW EXECUTE FUNCTION paper_loop.wake_job();
-- Minute-level fallback recovers missed notifications and expired task leases.
SELECT cron.schedule('paper-loop-worker','* * * * *','select paper_loop.dispatch_worker()');
