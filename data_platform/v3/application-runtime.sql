-- App-specific migration, additive and repeatable; do not touch legacy schema.
SET search_path=sv3,pg_catalog;
CREATE TABLE IF NOT EXISTS device_credentials (
 station_id uuid PRIMARY KEY REFERENCES stations(id), farmer_id uuid NOT NULL REFERENCES farmers(id),
 key_hash text NOT NULL, revoked_at timestamptz, created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(station_id,farmer_id) REFERENCES stations(id,farmer_id));
ALTER TABLE device_credentials ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS farmer_scope ON device_credentials;
CREATE POLICY farmer_scope ON device_credentials USING(farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
CREATE OR REPLACE FUNCTION verify_device(station_key text) RETURNS TABLE(station_id uuid,farmer_id uuid,key_hash text)
 LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,sv3 AS $$
 SELECT s.id,d.farmer_id,d.key_hash FROM sv3.stations s JOIN sv3.device_credentials d ON d.station_id=s.id
 WHERE s.station_key=$1 AND d.revoked_at IS NULL AND s.device_type<>'mock-v3'
 $$;
REVOKE ALL ON FUNCTION verify_device(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION verify_device(text) TO sv3_app;
GRANT SELECT,INSERT,UPDATE ON device_credentials TO sv3_writer;
-- Opt-in contacts never appear in this sanitized directory. Synthetic fixture neighbors
-- are public demo examples; live entries require explicit current sharing consent.
CREATE OR REPLACE FUNCTION public_farmer_directory() RETURNS TABLE(
 id uuid,name text,land_size_acres numeric,location text,state text,district text,
 latitude numeric,longitude numeric,crops jsonb,excess_resources jsonb,required_resources jsonb,origin text)
 LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,sv3 AS $$
 SELECT f.id,f.display_name,(SELECT sum(p.area_ha)*2.47105381 FROM sv3.plots p WHERE p.farmer_id=f.id),
 coalesce(f.profile_attributes->>'location',r.name),r.name,coalesce(f.profile_attributes->>'district',r.name),
 (SELECT round(avg(p.latitude),2) FROM sv3.plots p WHERE p.farmer_id=f.id),
 (SELECT round(avg(p.longitude),2) FROM sv3.plots p WHERE p.farmer_id=f.id),
 coalesce((SELECT jsonb_agg(DISTINCT c.name) FROM sv3.crop_cycles cc JOIN sv3.crops c ON c.id=cc.crop_id WHERE cc.farmer_id=f.id),'[]'),
 coalesce(f.profile_attributes->'excess_resources',(SELECT jsonb_agg(DISTINCT rs.name) FROM sv3.resources rs WHERE rs.farmer_id=f.id AND rs.category IN ('equipment','produce','labour','transport','supplies')),'[]'),
 coalesce(f.profile_attributes->'required_resources','[]'),d.origin
 FROM sv3.farmers f JOIN sv3.datasets d ON d.id=f.dataset_id JOIN sv3.regions r ON r.id=f.region_id
 WHERE (current_database()='skyview_v3_demo' AND d.lane='demo' AND d.origin='synthetic') OR
 (f.profile_attributes->>'sharing_public'='true' AND EXISTS(SELECT 1 FROM sv3.consents c WHERE c.farmer_id=f.id AND c.purpose='public_listing' AND c.revoked_at IS NULL AND (c.expires_at IS NULL OR c.expires_at>now())))
 LIMIT 500;
 $$;
REVOKE ALL ON FUNCTION public_farmer_directory() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public_farmer_directory() TO sv3_app;
ALTER TABLE sv3.disease_cases ALTER COLUMN cycle_id DROP NOT NULL;
ALTER TABLE sv3.disease_cases ADD COLUMN IF NOT EXISTS attachment_id uuid;
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='disease_attachment_owner' AND conrelid='sv3.disease_cases'::regclass) THEN
 ALTER TABLE sv3.disease_cases ADD CONSTRAINT disease_attachment_owner FOREIGN KEY(attachment_id,farmer_id) REFERENCES sv3.attachments(id,farmer_id);
END IF; END $$;
