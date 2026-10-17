-- Source migration only: review before applying with a database owner.
-- Never grant this role to the ordinary app database login.
BEGIN;
DO $$ BEGIN
 IF current_database() NOT IN ('skyview_v3_live','skyview_v3_demo','skyview_v3_test') THEN RAISE EXCEPTION 'Wrong database'; END IF;
 IF EXISTS(SELECT FROM pg_roles WHERE rolname='sv3_admin' AND (rolsuper OR rolbypassrls OR rolcanlogin)) THEN RAISE EXCEPTION 'Existing admin role has unexpected privileges'; END IF;
 IF NOT EXISTS(SELECT FROM pg_roles WHERE rolname='sv3_admin') THEN CREATE ROLE sv3_admin NOLOGIN NOSUPERUSER NOBYPASSRLS; END IF;
END $$;
CREATE TABLE IF NOT EXISTS sv3.admin_previews (
 id uuid PRIMARY KEY, actor text NOT NULL, resource text NOT NULL, payload jsonb NOT NULL,
 expires_at timestamptz NOT NULL, committed_at timestamptz, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS admin_preview_expiry ON sv3.admin_previews(expires_at);
CREATE TABLE IF NOT EXISTS sv3.admin_audit (
 id uuid PRIMARY KEY, actor text NOT NULL, role text NOT NULL, resource text NOT NULL,
 reason text NOT NULL, changes jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
-- Remain private even if a later generic runtime migration grants SELECT.
ALTER TABLE sv3.admin_previews ENABLE ROW LEVEL SECURITY;
ALTER TABLE sv3.admin_previews FORCE ROW LEVEL SECURITY;
ALTER TABLE sv3.admin_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE sv3.admin_audit FORCE ROW LEVEL SECURITY;
DO $$ DECLARE n text; BEGIN FOREACH n IN ARRAY ARRAY['admin_previews','admin_audit'] LOOP
 IF NOT EXISTS(SELECT FROM pg_policies WHERE schemaname='sv3' AND tablename=n AND policyname='administrator_only') THEN
  EXECUTE format('CREATE POLICY administrator_only ON sv3.%I TO sv3_admin USING(true) WITH CHECK(true)',n);
 END IF;
END LOOP; END $$;
REVOKE UPDATE,DELETE,TRUNCATE ON sv3.admin_audit FROM sv3_admin;
REVOKE ALL ON sv3.admin_previews,sv3.admin_audit FROM PUBLIC,sv3_app,sv3_writer;
GRANT USAGE ON SCHEMA sv3 TO sv3_admin;
-- No BYPASSRLS, no all-table grants, no implicit access to future tables.
DO $$ DECLARE n text; BEGIN FOREACH n IN ARRAY ARRAY['farmers','farms','plots','crop_cycles','resources','expenses','tasks','field_observations','harvest_batches','sale_records','crops','crop_varieties','units','regions','locations','markets','market_series','price_observations','msp_announcements','crop_guides','diseases','scheme_versions','stations','station_sensors','weather_series','weather_daily','weather_forecasts','soil_samples','soil_indicators','exchange_listings','resource_listings','farm_missions','companion_proposals','service_requests','ledger_entries','crop_case_notes','conversations','agent_runs','task_events','exchange_events','source_health','ingest_runs','datasets'] LOOP
 IF to_regclass('sv3.'||n) IS NOT NULL THEN
  EXECUTE format('GRANT SELECT ON sv3.%I TO sv3_admin',n);
  IF NOT EXISTS(SELECT FROM pg_policies WHERE schemaname='sv3' AND tablename=n AND policyname='admin_scope') THEN
   EXECUTE format('CREATE POLICY admin_scope ON sv3.%I TO sv3_admin USING (true) WITH CHECK (true)',n);
  END IF;
 END IF;
END LOOP; END $$;
GRANT SELECT,INSERT ON sv3.admin_audit TO sv3_admin;
GRANT SELECT,INSERT,UPDATE,DELETE ON sv3.admin_previews TO sv3_admin;
GRANT SELECT(farmer_id),UPDATE(revoked_at,run_token,run_expires_at) ON sv3.assistant_sessions TO sv3_admin;
DO $$ BEGIN
 IF NOT EXISTS(SELECT FROM pg_policies WHERE schemaname='sv3' AND tablename='assistant_sessions' AND policyname='admin_revoke') THEN
  CREATE POLICY admin_revoke ON sv3.assistant_sessions TO sv3_admin USING(true) WITH CHECK(true);
 END IF;
END $$;
DO $$ DECLARE n text; BEGIN FOREACH n IN ARRAY ARRAY['farmers','farms','plots','crop_cycles','resources','expenses','tasks','field_observations','harvest_batches','sale_records','crops','crop_varieties','units','regions','locations','markets','market_series','price_observations','msp_announcements','crop_guides','diseases','scheme_versions','stations','station_sensors','weather_series','weather_daily','weather_forecasts','soil_samples','soil_indicators','exchange_listings','resource_listings','service_requests','ledger_entries','crop_case_notes'] LOOP
 IF to_regclass('sv3.'||n) IS NOT NULL THEN EXECUTE format('GRANT INSERT,UPDATE,DELETE ON sv3.%I TO sv3_admin',n); END IF;
END LOOP; END $$;
ALTER TABLE sv3.farmers DROP CONSTRAINT IF EXISTS farmer_region_or_onboarding;
ALTER TABLE sv3.farmers ADD CONSTRAINT farmer_region_or_onboarding CHECK(region_id IS NOT NULL OR status IN ('onboarding','suspended'));
COMMIT;
