-- Existing synthetic neighbours may be read in either deployment lane.
-- Real farmers still require active public-listing consent. Contact fields are never returned.
SET search_path TO sv3,pg_catalog;
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
 WHERE (d.lane='demo' AND d.origin='synthetic') OR
 (f.profile_attributes->>'sharing_public'='true' AND EXISTS(SELECT 1 FROM sv3.consents c WHERE c.farmer_id=f.id AND c.purpose='public_listing' AND c.revoked_at IS NULL AND (c.expires_at IS NULL OR c.expires_at>now())))
 LIMIT 500;
 $$;
REVOKE ALL ON FUNCTION public_farmer_directory() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public_farmer_directory() TO sv3_app;
