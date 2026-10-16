-- Personal preparation only: these flags never represent official eligibility or approval.
BEGIN;
SET search_path=sv3,pg_catalog;
CREATE TABLE IF NOT EXISTS support_folder_preparation(
 farmer_id uuid NOT NULL REFERENCES farmers(id),
 scheme_version_id uuid NOT NULL REFERENCES scheme_versions(id),
 eligibility_reviewed boolean NOT NULL DEFAULT false,
 documents_reviewed boolean NOT NULL DEFAULT false,
 application_reviewed boolean NOT NULL DEFAULT false,
 row_version bigint NOT NULL DEFAULT 1 CHECK(row_version>0),
 updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(farmer_id,scheme_version_id)
);
ALTER TABLE support_folder_preparation ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS farmer_scope ON support_folder_preparation;
CREATE POLICY farmer_scope ON support_folder_preparation
 USING(farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid)
 WITH CHECK(farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
GRANT SELECT ON support_folder_preparation TO sv3_app;
GRANT SELECT,INSERT,UPDATE ON support_folder_preparation TO sv3_writer;
COMMIT;
