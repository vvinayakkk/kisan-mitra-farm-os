BEGIN;
SET search_path=sv3,pg_catalog;
CREATE TABLE IF NOT EXISTS companion_jobs (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id),
 area text NOT NULL CHECK(area IN ('today','markets','schemes','records','crops','exchange')),
 state text NOT NULL DEFAULT 'queued' CHECK(state IN ('queued','running','done','failed')),
 research boolean NOT NULL DEFAULT false, attempts integer NOT NULL DEFAULT 0,
 lease_token uuid, lease_until timestamptz, next_attempt_at timestamptz NOT NULL DEFAULT now(),
 safe_error text, created_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz
);
CREATE UNIQUE INDEX IF NOT EXISTS companion_job_active ON companion_jobs(farmer_id,area) WHERE state IN ('queued','running');
CREATE INDEX IF NOT EXISTS companion_job_due ON companion_jobs(next_attempt_at) WHERE state IN ('queued','running');
CREATE TABLE IF NOT EXISTS companion_proposals (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),farmer_id uuid NOT NULL REFERENCES farmers(id),
 area text NOT NULL, dedupe_key text NOT NULL, title text NOT NULL, summary text NOT NULL,
 steps jsonb NOT NULL CHECK(jsonb_typeof(steps)='array'), evidence jsonb NOT NULL DEFAULT '[]',
 research jsonb, status text NOT NULL DEFAULT 'ready' CHECK(status IN ('ready','approved','dismissed')),
 mission_id uuid, row_version bigint NOT NULL DEFAULT 1,
 created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(farmer_id,dedupe_key), FOREIGN KEY(mission_id,farmer_id) REFERENCES farm_missions(id,farmer_id)
);
CREATE INDEX IF NOT EXISTS companion_proposal_area ON companion_proposals(farmer_id,area,created_at DESC);
DO $$ DECLARE tab text; BEGIN
 FOREACH tab IN ARRAY ARRAY['companion_jobs','companion_proposals'] LOOP
  EXECUTE format('ALTER TABLE sv3.%I ENABLE ROW LEVEL SECURITY',tab);
  EXECUTE format('DROP POLICY IF EXISTS farmer_scope ON sv3.%I',tab);
  EXECUTE format('CREATE POLICY farmer_scope ON sv3.%I USING(farmer_id=nullif(current_setting(''app.farmer_id'',true),'''')::uuid) WITH CHECK(farmer_id=nullif(current_setting(''app.farmer_id'',true),'''')::uuid)',tab);
  EXECUTE format('GRANT SELECT ON sv3.%I TO sv3_app',tab);
  EXECUTE format('GRANT SELECT,INSERT,UPDATE ON sv3.%I TO sv3_writer',tab);
 END LOOP;
END $$;
CREATE OR REPLACE FUNCTION companion_schedule_plans() RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path=sv3,pg_catalog,pg_temp AS $$
DECLARE added integer;
BEGIN
 INSERT INTO companion_jobs(farmer_id,area)
 SELECT p.farmer_id,areas.area FROM companion_preferences p
 CROSS JOIN (VALUES('today'),('markets'),('schemes'),('records'),('crops'),('exchange')) areas(area)
 WHERE p.enabled AND p.last_checked_at>now()-interval '2 minutes'
 AND NOT EXISTS(SELECT 1 FROM companion_jobs j WHERE j.farmer_id=p.farmer_id AND j.area=areas.area AND j.created_at>now()-make_interval(hours=>p.frequency_hours))
 LIMIT 60 ON CONFLICT DO NOTHING;
 GET DIAGNOSTICS added=ROW_COUNT; RETURN added;
END $$;
CREATE OR REPLACE FUNCTION companion_claim_plan() RETURNS SETOF companion_jobs
LANGUAGE plpgsql SECURITY DEFINER SET search_path=sv3,pg_catalog,pg_temp AS $$
BEGIN
 UPDATE companion_jobs SET state='failed',safe_error='Preparation interrupted. Please try again.',finished_at=now()
 WHERE state='running' AND lease_until<now() AND attempts>=3;
 RETURN QUERY WITH picked AS (
  SELECT id FROM companion_jobs WHERE attempts<3 AND next_attempt_at<=now()
  AND (state='queued' OR (state='running' AND lease_until<now()))
  ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1
 ) UPDATE companion_jobs j SET state='running',attempts=j.attempts+1,lease_token=gen_random_uuid(),lease_until=now()+interval '3 minutes'
 FROM picked WHERE j.id=picked.id RETURNING j.*;
END $$;
REVOKE ALL ON FUNCTION companion_schedule_plans(),companion_claim_plan() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION companion_schedule_plans(),companion_claim_plan() TO sv3_ingest;
COMMIT;
