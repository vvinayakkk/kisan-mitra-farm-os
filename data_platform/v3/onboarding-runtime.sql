-- Public state-name references, not official LGD codes or fabricated cadastral data.
BEGIN;
SET search_path=sv3,pg_catalog;
ALTER TABLE plots ADD COLUMN IF NOT EXISTS name text NOT NULL DEFAULT '';
INSERT INTO providers(code,name,homepage,access_method,license_name,attribution,status)
VALUES('curated-india-state-names','India state and union territory names','https://knowindia.india.gov.in/states-uts/','curated_reference','Source portal terms; names as reference metadata','Know India state/UT directory; LGD https://lgdirectory.gov.in/','curated') ON CONFLICT(code) DO NOTHING;
INSERT INTO datasets(provider_id,release_key,lane,origin,as_of_date,source_url)
SELECT id,'curated-india-state-names:v1','live','curated',current_date,'https://knowindia.india.gov.in/states-uts/' FROM providers WHERE code='curated-india-state-names' ON CONFLICT(release_key) DO NOTHING;
WITH state_names(name,kind) AS (VALUES
('Andhra Pradesh','state'),('Arunachal Pradesh','state'),('Assam','state'),('Bihar','state'),('Chhattisgarh','state'),('Goa','state'),('Gujarat','state'),('Haryana','state'),('Himachal Pradesh','state'),('Jharkhand','state'),('Karnataka','state'),('Kerala','state'),('Madhya Pradesh','state'),('Maharashtra','state'),('Manipur','state'),('Meghalaya','state'),('Mizoram','state'),('Nagaland','state'),('Odisha','state'),('Punjab','state'),('Rajasthan','state'),('Sikkim','state'),('Tamil Nadu','state'),('Telangana','state'),('Tripura','state'),('Uttar Pradesh','state'),('Uttarakhand','state'),('West Bengal','state'),
('Andaman and Nicobar Islands','ut'),('Chandigarh','ut'),('Dadra and Nagar Haveli and Daman and Diu','ut'),('Delhi','ut'),('Jammu and Kashmir','ut'),('Ladakh','ut'),('Lakshadweep','ut'),('Puducherry','ut'))
INSERT INTO regions(dataset_id,level,code_system,code,name,valid_from)
SELECT d.id,s.kind,'skyview-curated-state-name',lower(replace(s.name,' ','-')),s.name,current_date FROM state_names s CROSS JOIN datasets d WHERE d.release_key='curated-india-state-names:v1'
ON CONFLICT(dataset_id,code_system,code) DO NOTHING;
-- Canonical common-name vocabulary only. No official variety, seed certificate,
-- crop suitability, yield or treatment claim is implied by these names.
INSERT INTO crops(code,name,category,perennial,names) VALUES
('rice','Rice','cereal',false,'{"en":"Rice"}'),('wheat','Wheat','cereal',false,'{"en":"Wheat"}'),('maize','Maize','cereal',false,'{"en":"Maize"}'),
('ragi','Ragi','cereal',false,'{"en":"Ragi"}'),('bajra','Bajra','cereal',false,'{"en":"Bajra"}'),('jowar','Jowar','cereal',false,'{"en":"Jowar"}'),
('chickpea','Chickpea','pulse',false,'{"en":"Chickpea"}'),('pigeon_pea','Pigeon pea','pulse',false,'{"en":"Pigeon pea"}'),('lentil','Lentil','pulse',false,'{"en":"Lentil"}'),
('soybean','Soybean','oilseed',false,'{"en":"Soybean"}'),('groundnut','Groundnut','oilseed',false,'{"en":"Groundnut"}'),('mustard','Mustard','oilseed',false,'{"en":"Mustard"}'),('castor','Castor','oilseed',false,'{"en":"Castor"}'),
('cotton','Cotton','fiber',false,'{"en":"Cotton"}'),('jute','Jute','fiber',false,'{"en":"Jute"}'),('sugarcane','Sugarcane','industrial',false,'{"en":"Sugarcane"}'),
('potato','Potato','vegetable',false,'{"en":"Potato"}'),('onion','Onion','vegetable',false,'{"en":"Onion"}'),('tomato','Tomato','vegetable',false,'{"en":"Tomato"}'),
('banana','Banana','fruit',true,'{"en":"Banana"}'),('apple','Apple','fruit',true,'{"en":"Apple"}'),('mango','Mango','fruit',true,'{"en":"Mango"}'),
('coconut','Coconut','plantation',true,'{"en":"Coconut"}'),('cashew','Cashew','plantation',true,'{"en":"Cashew"}'),('tea','Tea','plantation',true,'{"en":"Tea"}'),('coffee','Coffee','plantation',true,'{"en":"Coffee"}'),
('ginger','Ginger','spice',false,'{"en":"Ginger"}'),('pepper','Pepper','spice',true,'{"en":"Pepper"}'),('cardamom','Cardamom','spice',true,'{"en":"Cardamom"}')
ON CONFLICT(code) DO NOTHING;
-- Lab-report semantics only; this adds no sample values or fabricated reports.
INSERT INTO units(code,dimension,symbol) VALUES('ph','acidity','pH'),('percent','fraction','%'),('gkg','mass_fraction','g/kg'),('kg_ha','areal_mass','kg/ha'),('mgkg','mass_fraction','mg/kg'),('ds_m','conductivity','dS/m') ON CONFLICT(code) DO NOTHING;
INSERT INTO measurement_definitions(code,name,basis,allowed_units,minimum_value,maximum_value,interpretation) VALUES
('ph','pH','hydrogen activity','["ph"]',0,14,'Record laboratory method; no fertilizer dose is inferred.'),
('organic_carbon','Organic carbon','organic carbon, not organic matter','["gkg","percent"]',0,1000,'Preserve carbon versus organic matter and units; no unapproved conversion.'),
('nitrogen','Available nitrogen','lab method; element N','["kg_ha","mgkg"]',0,NULL,'Available N is not total nitrogen; preserve reported method and basis.'),
('phosphorus','Available phosphorus','report basis must specify elemental P or P2O5','["kg_ha","mgkg"]',0,NULL,'Record elemental P versus P2O5; never silently convert.'),
('potassium','Available potassium','report basis must specify elemental K or K2O','["kg_ha","mgkg"]',0,NULL,'Record elemental K versus K2O; never silently convert.'),
('sulphur','Available sulphur','lab extractable sulphur','["mgkg"]',0,NULL,'Preserve laboratory method and units.'),
('zinc','Zinc','lab extractable Zn','["mgkg"]',0,NULL,'Preserve laboratory method and units.'),
('iron','Iron','lab extractable Fe','["mgkg"]',0,NULL,'Preserve laboratory method and units.'),
('copper','Copper','lab extractable Cu','["mgkg"]',0,NULL,'Preserve laboratory method and units.'),
('manganese','Manganese','lab extractable Mn','["mgkg"]',0,NULL,'Preserve laboratory method and units.'),
('boron','Boron','lab extractable B','["mgkg"]',0,NULL,'Preserve laboratory method and units.'),
('ec','Electrical conductivity','report extraction ratio/temperature required','["ds_m"]',0,NULL,'Record extraction ratio and temperature; no salinity guarantee.')
ON CONFLICT(code) DO NOTHING;
GRANT SELECT,INSERT,UPDATE ON stations,station_sensors TO sv3_writer;
-- Enrollment worker validates a scoped owned plot before selecting this trusted role.
GRANT SELECT,INSERT,UPDATE ON device_credentials TO sv3_ingest;
COMMIT;

-- Workers get only currently consented coarse weather anchors, never private
-- farmer IDs, exact plot geometry, contact fields or a broad consent-table grant.
BEGIN;
CREATE OR REPLACE FUNCTION sv3.consented_weather_locations() RETURNS TABLE(id uuid,latitude numeric,longitude numeric)
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,sv3 AS $$
 SELECT DISTINCT l.id,l.latitude,l.longitude FROM sv3.locations l
 JOIN sv3.farms f ON f.location_id=l.id JOIN sv3.datasets d ON d.id=l.dataset_id
 WHERE l.location_key LIKE 'weather-grid:0.25:%' AND l.resolution_m>=25000 AND d.origin='user_reported'
 AND EXISTS(SELECT 1 FROM sv3.consents c WHERE c.farmer_id=f.farmer_id AND c.purpose='weather_grid_lookup' AND c.revoked_at IS NULL AND (c.expires_at IS NULL OR c.expires_at>now()))
 LIMIT 500;
$$;
REVOKE ALL ON FUNCTION sv3.consented_weather_locations() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION sv3.consented_weather_locations() TO sv3_ingest;
COMMIT;
