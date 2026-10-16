-- Run as database administrator once, after schema.sql. No LOGIN, passwords or PUBLIC grants.
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='sv3_app') THEN CREATE ROLE sv3_app NOLOGIN NOSUPERUSER NOBYPASSRLS; END IF; END $$;
GRANT USAGE ON SCHEMA sv3 TO sv3_app;
REVOKE ALL ON ALL TABLES IN SCHEMA sv3 FROM sv3_app;
DO $$ DECLARE relation record; BEGIN
 FOR relation IN SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='sv3' AND c.relkind IN ('r','p','v') AND NOT c.relispartition
 AND c.relname NOT IN ('ingest_runs','raw_objects','quality_issues') LOOP
  EXECUTE format('GRANT SELECT ON sv3.%I TO sv3_app',relation.relname);
 END LOOP;
END $$;
-- Direct partition reads bypass parent RLS; do not grant child-table access.
-- Raw ingest/quality details are admin-only and may contain untrusted sensitive payloads.
REVOKE ALL ON FUNCTION sv3.ensure_month_partitions(text,date,date) FROM PUBLIC;
-- API-authenticated application sets SET LOCAL app.farmer_id using a bound validated UUID.
-- Grant mutation privileges only to selected application services, not browser SQL clients.
