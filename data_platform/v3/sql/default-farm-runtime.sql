-- A real, editable empty farm workspace for every signed-in account.
-- Location, acreage, crops and equipment remain unknown until supplied.
BEGIN;
ALTER TABLE sv3.farms ALTER COLUMN region_id DROP NOT NULL;
INSERT INTO sv3.farms(farmer_id,farm_key,name,region_id,ownership_type,irrigation_method)
SELECT f.id,'HOME-'||f.id::text,'My farm',f.region_id,'unspecified','unspecified'
FROM sv3.farmers f WHERE NOT EXISTS (SELECT 1 FROM sv3.farms x WHERE x.farmer_id=f.id)
ON CONFLICT(farm_key) DO NOTHING;
COMMIT;
