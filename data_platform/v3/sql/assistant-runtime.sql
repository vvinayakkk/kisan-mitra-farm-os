-- Apply after schema.sql and runtime roles. Capability hashes never enter public tables.
BEGIN;
SET search_path=sv3,public;
CREATE TABLE IF NOT EXISTS assistant_sessions (
 id text PRIMARY KEY CHECK(id ~ '^[a-f0-9]{32}$'), farmer_id uuid NOT NULL REFERENCES farmers(id),
 token_hash text NOT NULL, conversation_id uuid NOT NULL, state jsonb NOT NULL DEFAULT '{"messages":[],"pending":null,"events":[]}',
 run_token text, run_expires_at timestamptz, created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(conversation_id,farmer_id) REFERENCES conversations(id,farmer_id), UNIQUE(id,farmer_id));
ALTER TABLE assistant_sessions ADD COLUMN IF NOT EXISTS legacy_imported_at timestamptz;
ALTER TABLE assistant_sessions ADD COLUMN IF NOT EXISTS expires_at timestamptz NOT NULL DEFAULT (now()+interval '30 days');
ALTER TABLE assistant_sessions ADD COLUMN IF NOT EXISTS revoked_at timestamptz;
CREATE TABLE IF NOT EXISTS assistant_records (
 id uuid PRIMARY KEY, farmer_id uuid NOT NULL REFERENCES farmers(id), session_id text NOT NULL,
 kind text NOT NULL, data jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), FOREIGN KEY(session_id,farmer_id) REFERENCES assistant_sessions(id,farmer_id));
CREATE INDEX IF NOT EXISTS assistant_records_scope ON assistant_records(farmer_id,kind,created_at DESC);
CREATE TABLE IF NOT EXISTS assistant_archives (
 id uuid PRIMARY KEY, farmer_id uuid NOT NULL REFERENCES farmers(id), session_id text NOT NULL,
 title text NOT NULL, state jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), FOREIGN KEY(session_id,farmer_id) REFERENCES assistant_sessions(id,farmer_id));
ALTER TABLE assistant_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE assistant_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE assistant_archives ENABLE ROW LEVEL SECURITY;
DO $$ DECLARE t text; BEGIN FOREACH t IN ARRAY ARRAY['assistant_sessions','assistant_records','assistant_archives'] LOOP
 IF NOT EXISTS(SELECT FROM pg_policies WHERE schemaname='sv3' AND tablename=t AND policyname='farmer_scope') THEN
 EXECUTE format('CREATE POLICY farmer_scope ON sv3.%I USING (farmer_id=nullif(current_setting(''app.farmer_id'',true),'''')::uuid) WITH CHECK (farmer_id=nullif(current_setting(''app.farmer_id'',true),'''')::uuid)',t);
 END IF; END LOOP; END $$;
-- Only the trusted backend credential is granted execution; frontend never has SQL access.
CREATE OR REPLACE FUNCTION assistant_session_identity(sid text) RETURNS TABLE(farmer_id uuid,token_hash text)
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,sv3 AS $$ SELECT farmer_id,token_hash FROM sv3.assistant_sessions WHERE id=sid AND revoked_at IS NULL AND expires_at>now() $$;
CREATE OR REPLACE FUNCTION assistant_demo_farmer(profile text) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,sv3 AS $$ DECLARE f uuid; BEGIN
 IF current_database() NOT IN ('skyview_v3_demo','skyview_v3_test') THEN RAISE EXCEPTION 'Demo bootstrap forbidden in live database'; END IF;
 SELECT id INTO f FROM sv3.farmers WHERE profile_key=profile;
 IF f IS NULL THEN RAISE EXCEPTION 'Configured demo profile missing'; END IF; RETURN f; END $$;
REVOKE ALL ON FUNCTION assistant_session_identity(text),assistant_demo_farmer(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION assistant_session_identity(text),assistant_demo_farmer(text) TO sv3_app,sv3_writer;
GRANT SELECT ON assistant_sessions,assistant_records,assistant_archives TO sv3_app;
GRANT SELECT,INSERT,UPDATE,DELETE ON assistant_sessions,assistant_records,assistant_archives TO sv3_writer;
GRANT SELECT,INSERT,UPDATE ON conversations,messages,agent_runs,tool_calls,approvals,artifacts,attachments,memories,context_compactions,run_events,question_requests,question_answers,tasks,task_events,expenses TO sv3_writer;
COMMIT;

-- Verified OIDC accounts can chat before completing location onboarding.
BEGIN;
ALTER TABLE sv3.farmers ALTER COLUMN region_id DROP NOT NULL;
DO $$ BEGIN
 IF NOT EXISTS(SELECT FROM pg_constraint WHERE conname='farmer_region_or_onboarding' AND conrelid='sv3.farmers'::regclass) THEN
 ALTER TABLE sv3.farmers ADD CONSTRAINT farmer_region_or_onboarding CHECK(region_id IS NOT NULL OR status='onboarding');
 END IF;
END $$;
CREATE OR REPLACE FUNCTION sv3.assistant_oidc_farmer(subject text, issuer text) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,sv3 AS $$
DECLARE f uuid; p uuid; d uuid; provider_code text;
BEGIN
 IF current_database() NOT IN ('skyview_v3_live','skyview_v3_test') THEN RAISE EXCEPTION 'Verified live bootstrap forbidden outside live/test'; END IF;
 IF subject !~ '^oidc:[a-f0-9]{64}$' OR issuer !~ '^https://' THEN RAISE EXCEPTION 'Invalid verified identity'; END IF;
 SELECT id INTO f FROM sv3.farmers WHERE auth_subject=subject;
 IF f IS NOT NULL THEN RETURN f; END IF;
 provider_code := 'oidc-'||md5(issuer);
 INSERT INTO sv3.providers(code,name,homepage,access_method,attribution,status) VALUES(provider_code,'Verified account onboarding',issuer,'verified_oidc','Farmer-provided onboarding','active') ON CONFLICT(code) DO NOTHING;
 SELECT id INTO p FROM sv3.providers WHERE providers.code=provider_code;
 INSERT INTO sv3.datasets(provider_id,release_key,lane,origin,as_of_date,source_url) VALUES(p,provider_code||'-accounts','live','user_reported',current_date,issuer) ON CONFLICT(release_key) DO NOTHING;
 SELECT id INTO d FROM sv3.datasets WHERE release_key=provider_code||'-accounts';
 INSERT INTO sv3.farmers(dataset_id,profile_key,auth_subject,display_name,region_id,preferred_language,status,profile_attributes)
 VALUES(d,'ACCOUNT-'||substr(subject,6),subject,'New farmer',NULL,'en','onboarding','{"onboarding_required":true}')
 ON CONFLICT(auth_subject) DO UPDATE SET auth_subject=excluded.auth_subject RETURNING id INTO f;
 RETURN f;
END $$;
REVOKE ALL ON FUNCTION sv3.assistant_oidc_farmer(text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION sv3.assistant_oidc_farmer(text,text) TO sv3_writer;
COMMIT;

-- Versioned actual runtime catalog and exact skill-file linkage for audits.
BEGIN;
ALTER TABLE sv3.tool_calls ADD COLUMN IF NOT EXISTS skill_version_id uuid REFERENCES sv3.skill_versions(id);
GRANT SELECT,INSERT,UPDATE ON sv3.skill_versions,sv3.tool_versions TO sv3_ingest;
COMMIT;

-- Capability lifetime and explicit logout revocation retain farmer-owned history.
BEGIN;
ALTER TABLE sv3.assistant_sessions ADD COLUMN IF NOT EXISTS expires_at timestamptz NOT NULL DEFAULT (now()+interval '30 days');
ALTER TABLE sv3.assistant_sessions ADD COLUMN IF NOT EXISTS revoked_at timestamptz;
CREATE INDEX IF NOT EXISTS assistant_session_expiry ON sv3.assistant_sessions(expires_at) WHERE revoked_at IS NULL;
CREATE OR REPLACE FUNCTION sv3.assistant_session_identity(sid text) RETURNS TABLE(farmer_id uuid,token_hash text)
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,sv3 AS $$ SELECT farmer_id,token_hash FROM sv3.assistant_sessions WHERE id=sid AND revoked_at IS NULL AND expires_at>now() $$;
REVOKE ALL ON FUNCTION sv3.assistant_session_identity(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION sv3.assistant_session_identity(text) TO sv3_app,sv3_writer;
COMMIT;
