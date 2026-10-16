-- SkyView v3: fresh databases only. Never apply to the existing farm database.
-- PostgreSQL 16+. Live and demo databases use this same schema; different credentials.
-- No DROP/TRUNCATE or import of legacy identities. Money NUMERIC, instants TIMESTAMPTZ.
BEGIN;
DO $$ BEGIN
 IF current_database() NOT IN ('skyview_v3_live','skyview_v3_demo','skyview_v3_test') THEN
  RAISE EXCEPTION 'Fresh database guard: create skyview_v3_live/demo/test first';
 END IF;
END $$;
CREATE SCHEMA sv3;
SET search_path = sv3, public;

-- ingestion: Source contract, license, access and refresh policy
CREATE TABLE providers (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), code text NOT NULL UNIQUE, name text NOT NULL, homepage text NOT NULL, access_method text NOT NULL, license_name text, attribution text NOT NULL, status text NOT NULL DEFAULT 'planned', refresh_seconds integer CHECK(refresh_seconds>0), configuration jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now()
) ;

-- ingestion: Immutable release boundary for live versus synthetic data
CREATE TABLE datasets (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), provider_id uuid NOT NULL REFERENCES providers(id), release_key text NOT NULL UNIQUE, lane text NOT NULL CHECK(lane IN ('live','demo')), origin text NOT NULL CHECK(origin IN ('observed','reanalysis','modeled','synthetic','user_reported','derived','curated')), as_of_date date NOT NULL, generator_version text, seed bigint, source_url text NOT NULL, checksum text, created_at timestamptz NOT NULL DEFAULT now(), CHECK(lane<>'live' OR origin<>'synthetic'), CHECK(origin<>'synthetic' OR generator_version IS NOT NULL)
) ;

-- ingestion: Watermark, retries, bounded jobs and source failure audit
CREATE TABLE ingest_runs (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), provider_id uuid NOT NULL REFERENCES providers(id), dataset_id uuid REFERENCES datasets(id), job_key text NOT NULL UNIQUE, state text NOT NULL CHECK(state IN ('queued','running','done','failed')), cursor jsonb, attempts integer NOT NULL DEFAULT 0, rows_received bigint NOT NULL DEFAULT 0, rows_accepted bigint NOT NULL DEFAULT 0, started_at timestamptz, finished_at timestamptz, next_attempt_at timestamptz, safe_error text, created_at timestamptz NOT NULL DEFAULT now()
) ;

-- ingestion: Original payload in object storage, hash and request identity
CREATE TABLE raw_objects (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), run_id uuid NOT NULL REFERENCES ingest_runs(id), request_key text NOT NULL, content_hash text NOT NULL, object_uri text NOT NULL, media_type text NOT NULL, bytes bigint NOT NULL CHECK(bytes>=0), fetched_at timestamptz NOT NULL, UNIQUE(run_id,request_key)
) ;

-- ingestion: Quarantine incorrect timestamps, units and conflicting duplicate values
CREATE TABLE quality_issues (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), raw_object_id uuid REFERENCES raw_objects(id), dataset_id uuid REFERENCES datasets(id), entity_type text NOT NULL, natural_key jsonb NOT NULL, code text NOT NULL, details jsonb NOT NULL, resolved_at timestamptz, created_at timestamptz NOT NULL DEFAULT now()
) ;

-- reference: Official versioned state/district/tehsil/village hierarchy; demo IDs separate
CREATE TABLE regions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), dataset_id uuid NOT NULL REFERENCES datasets(id), parent_id uuid REFERENCES regions(id), level text NOT NULL CHECK(level IN ('state','ut','district','block','village')), code_system text NOT NULL, code text NOT NULL, name text NOT NULL, valid_from date NOT NULL, valid_to date, UNIQUE(dataset_id,code_system,code), CHECK(valid_to IS NULL OR valid_to>=valid_from)
) ;

-- reference: Shared weather grid or public location anchor
CREATE TABLE locations (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), dataset_id uuid NOT NULL REFERENCES datasets(id), region_id uuid NOT NULL REFERENCES regions(id), location_key text NOT NULL, label text NOT NULL, latitude numeric(9,6) NOT NULL CHECK(latitude BETWEEN -90 AND 90), longitude numeric(9,6) NOT NULL CHECK(longitude BETWEEN -180 AND 180), resolution_m integer CHECK(resolution_m>0), UNIQUE(dataset_id,location_key)
) ;

-- reference: Canonical crops with multilingual aliases
CREATE TABLE crops (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), code text NOT NULL UNIQUE, name text NOT NULL, names jsonb NOT NULL DEFAULT '{}', category text NOT NULL, perennial boolean NOT NULL DEFAULT false
) ;

-- reference: Keep crop variety/grade distinct for market comparisons
CREATE TABLE crop_varieties (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), crop_id uuid NOT NULL REFERENCES crops(id), code text NOT NULL, name text NOT NULL, UNIQUE(crop_id,code), UNIQUE(id,crop_id)
) ;

-- reference: Explicit dimensions and conversion factors, never infer price units
CREATE TABLE units (
 code text PRIMARY KEY, dimension text NOT NULL, symbol text NOT NULL, factor_to_base numeric(16,8), CHECK(factor_to_base IS NULL OR factor_to_base>0)
) ;

-- reference: Real official markets or explicitly named demo markets
CREATE TABLE markets (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), dataset_id uuid NOT NULL REFERENCES datasets(id), region_id uuid NOT NULL REFERENCES regions(id), code_system text NOT NULL, external_code text NOT NULL, name text NOT NULL, latitude numeric(9,6), longitude numeric(9,6), UNIQUE(dataset_id,code_system,external_code)
) ;

-- market: One market/crop/variety/grade/unit series
CREATE TABLE market_series (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), market_id uuid NOT NULL REFERENCES markets(id), crop_id uuid NOT NULL REFERENCES crops(id), variety_id uuid NOT NULL, grade text NOT NULL DEFAULT 'unspecified', unit_code text NOT NULL REFERENCES units(code), currency char(3) NOT NULL DEFAULT 'INR', FOREIGN KEY(variety_id,crop_id) REFERENCES crop_varieties(id,crop_id), UNIQUE(market_id,crop_id,variety_id,grade,unit_code,currency)
) ;

-- farm: Consented account and synthetic profile; no Aadhaar or stored plaintext OTP
CREATE TABLE farmers (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), dataset_id uuid NOT NULL REFERENCES datasets(id), profile_key text NOT NULL UNIQUE, auth_subject text UNIQUE, display_name text NOT NULL, region_id uuid NOT NULL REFERENCES regions(id), preferred_language text NOT NULL, age_band text, farming_experience_years integer CHECK(farming_experience_years BETWEEN 0 AND 80), profile_attributes jsonb NOT NULL DEFAULT '{}', contact_email text, contact_phone text, contact_verified_at timestamptz, status text NOT NULL DEFAULT 'active', created_at timestamptz NOT NULL DEFAULT now()
) ;

-- farm: Purpose-scoped permissions, expiry and revocation
CREATE TABLE consents (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), purpose text NOT NULL, granted_at timestamptz NOT NULL, expires_at timestamptz, revoked_at timestamptz, evidence_hash text NOT NULL
) ;

-- farm: One farmer can own/manage several farms
CREATE TABLE farms (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), farm_key text NOT NULL UNIQUE, name text NOT NULL, region_id uuid NOT NULL REFERENCES regions(id), location_id uuid REFERENCES locations(id), ownership_type text NOT NULL, irrigation_method text NOT NULL, water_source text, UNIQUE(id,farmer_id)
) ;

-- farm: Real user-drawn field geometry or an explicitly synthetic example
CREATE TABLE plots (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), farm_id uuid NOT NULL, plot_key text NOT NULL UNIQUE, area_ha numeric(10,4) NOT NULL CHECK(area_ha>0), latitude numeric(9,6) NOT NULL CHECK(latitude BETWEEN -90 AND 90), longitude numeric(9,6) NOT NULL CHECK(longitude BETWEEN -180 AND 180), boundary_geojson jsonb, soil_texture text, UNIQUE(id,farmer_id), FOREIGN KEY(farm_id,farmer_id) REFERENCES farms(id,farmer_id), CHECK(boundary_geojson IS NULL OR jsonb_typeof(boundary_geojson)='object')
) ;

-- farm: Crop, sowing date, harvest window and season per plot
CREATE TABLE crop_cycles (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), plot_id uuid NOT NULL, crop_id uuid NOT NULL REFERENCES crops(id), variety_id uuid, season text NOT NULL, sowing_date date NOT NULL, expected_harvest_date date, actual_harvest_date date, status text NOT NULL CHECK(status IN ('planned','growing','harvested','failed')), expected_yield_t_ha numeric(10,3), actual_yield_t_ha numeric(10,3), UNIQUE(id,farmer_id), FOREIGN KEY(plot_id,farmer_id) REFERENCES plots(id,farmer_id), FOREIGN KEY(variety_id,crop_id) REFERENCES crop_varieties(id,crop_id), CHECK(expected_harvest_date IS NULL OR expected_harvest_date>=sowing_date)
) ;

-- farm: Irrigation/sowing/fertilizing/scouting actual events, not inferred execution
CREATE TABLE farm_operations (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), cycle_id uuid NOT NULL, operation text NOT NULL, occurred_at timestamptz NOT NULL, quantity numeric(14,4), unit_code text REFERENCES units(code), notes text, evidence_uri text, FOREIGN KEY(cycle_id,farmer_id) REFERENCES crop_cycles(id,farmer_id)
) ;

-- sharing: Farmer inventory of equipment, produce or supplies
CREATE TABLE resources (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), category text NOT NULL, name text NOT NULL, quantity numeric(14,4) NOT NULL CHECK(quantity>=0), unit_code text NOT NULL REFERENCES units(code), UNIQUE(id,farmer_id)
) ;

-- sharing: Opt-in public/neighbor sharing availability, prices and date window
CREATE TABLE resource_listings (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), resource_id uuid NOT NULL, visibility text NOT NULL CHECK(visibility IN ('private','neighbors','public')), available_from date NOT NULL, available_to date NOT NULL, asking_price_inr numeric(14,2) CHECK(asking_price_inr>=0), status text NOT NULL, FOREIGN KEY(resource_id,farmer_id) REFERENCES resources(id,farmer_id), CHECK(available_to>=available_from)
) ;

-- sharing: Proposals between consenting participants; no invented agreements
CREATE TABLE resource_matches (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), listing_id uuid NOT NULL REFERENCES resource_listings(id), requester_id uuid NOT NULL REFERENCES farmers(id), proposed_at timestamptz NOT NULL, status text NOT NULL, terms jsonb NOT NULL DEFAULT '{}', requester_accepted_at timestamptz, owner_accepted_at timestamptz
) ;

-- farm: Exact decimal INR expenses, quantities and idempotency
CREATE TABLE expenses (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), cycle_id uuid, description text NOT NULL, spent_on date NOT NULL, amount_inr numeric(14,2) NOT NULL CHECK(amount_inr>=0), category text NOT NULL, execution_key text NOT NULL, UNIQUE(farmer_id,execution_key), FOREIGN KEY(cycle_id,farmer_id) REFERENCES crop_cycles(id,farmer_id)
) ;

-- farm: Owned calendar plan with recoverable deletion
CREATE TABLE tasks (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), cycle_id uuid, title text NOT NULL, due_at timestamptz NOT NULL, timezone text NOT NULL DEFAULT 'Asia/Kolkata', status text NOT NULL CHECK(status IN ('open','done','cancelled')), notes text, deleted_at timestamptz, execution_key text NOT NULL, UNIQUE(farmer_id,execution_key), UNIQUE(id,farmer_id), FOREIGN KEY(cycle_id,farmer_id) REFERENCES crop_cycles(id,farmer_id), row_version bigint NOT NULL DEFAULT 1 CHECK(row_version>0)
) ;

-- farm: Audit events and before/after edits for undo
CREATE TABLE task_events (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), task_id uuid NOT NULL, event_type text NOT NULL, before_state jsonb, after_state jsonb NOT NULL, actor text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), FOREIGN KEY(task_id,farmer_id) REFERENCES tasks(id,farmer_id)
) ;

-- telemetry: Real device or simulated station with explicit source identity
CREATE TABLE stations (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), plot_id uuid NOT NULL, dataset_id uuid NOT NULL REFERENCES datasets(id), station_key text NOT NULL UNIQUE, device_type text NOT NULL, calibration jsonb NOT NULL DEFAULT '{}', installed_at timestamptz NOT NULL, last_received_at timestamptz, UNIQUE(id,farmer_id), FOREIGN KEY(plot_id,farmer_id) REFERENCES plots(id,farmer_id)
) ;

-- telemetry: Metric/unit/depth/calibration per station
CREATE TABLE station_sensors (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), station_id uuid NOT NULL, metric text NOT NULL, unit_code text NOT NULL REFERENCES units(code), depth_cm numeric(6,2), enabled boolean NOT NULL DEFAULT true, FOREIGN KEY(station_id,farmer_id) REFERENCES stations(id,farmer_id), UNIQUE(station_id,metric,depth_cm), measurement_basis text NOT NULL DEFAULT 'unknown', calibration jsonb NOT NULL DEFAULT '{}'
) ;

-- telemetry: Global boot/sequence replay protection across monthly partitions
CREATE TABLE packet_receipts (
 dataset_id uuid NOT NULL REFERENCES datasets(id), farmer_id uuid NOT NULL REFERENCES farmers(id), station_id uuid NOT NULL, boot_id uuid NOT NULL, sequence bigint NOT NULL, observed_at timestamptz NOT NULL, PRIMARY KEY(dataset_id,station_id,boot_id,sequence), UNIQUE(dataset_id,station_id,boot_id,sequence,observed_at), FOREIGN KEY(station_id,farmer_id) REFERENCES stations(id,farmer_id)
) ;

-- telemetry: Idempotent packet with event/received time and valid readings
CREATE TABLE sensor_packets (
 dataset_id uuid NOT NULL REFERENCES datasets(id), farmer_id uuid NOT NULL REFERENCES farmers(id), station_id uuid NOT NULL, observed_at timestamptz NOT NULL, received_at timestamptz NOT NULL, boot_id uuid NOT NULL, sequence bigint NOT NULL CHECK(sequence>=0), temperature_c numeric(6,2) CHECK(temperature_c BETWEEN -80 AND 70), humidity_pct numeric(6,2) CHECK(humidity_pct BETWEEN 0 AND 100), pressure_hpa numeric(7,2) CHECK(pressure_hpa BETWEEN 500 AND 1200), wind_kmh numeric(7,2) CHECK(wind_kmh BETWEEN 0 AND 400), wind_direction_degrees numeric(6,2) CHECK(wind_direction_degrees>=0 AND wind_direction_degrees<360), rainfall_increment_mm numeric(8,3) CHECK(rainfall_increment_mm>=0), soil_temperature_c numeric(6,2), soil_moisture_pct numeric(6,2) CHECK(soil_moisture_pct BETWEEN 0 AND 100), pm25_ug_m3 numeric(10,3), pm10_ug_m3 numeric(10,3), uv_index numeric(6,3), lux numeric(12,2), battery_v numeric(7,3), solar_v numeric(7,3), quality_flags jsonb NOT NULL DEFAULT '[]', PRIMARY KEY(dataset_id,station_id,observed_at), FOREIGN KEY(dataset_id,station_id,boot_id,sequence,observed_at) REFERENCES packet_receipts(dataset_id,station_id,boot_id,sequence,observed_at), FOREIGN KEY(station_id,farmer_id) REFERENCES stations(id,farmer_id), CHECK(received_at>=observed_at)
) PARTITION BY RANGE(observed_at);

-- telemetry: UTC daily aggregates with counts/completeness
CREATE TABLE sensor_daily (
 dataset_id uuid NOT NULL REFERENCES datasets(id), farmer_id uuid NOT NULL REFERENCES farmers(id), station_id uuid NOT NULL, day date NOT NULL, sample_count integer NOT NULL CHECK(sample_count>=0), completeness numeric(5,4) NOT NULL CHECK(completeness BETWEEN 0 AND 1), temperature_min_c numeric(6,2), temperature_max_c numeric(6,2), rainfall_mm numeric(9,3), soil_moisture_mean_pct numeric(6,2), PRIMARY KEY(dataset_id,station_id,day), FOREIGN KEY(station_id,farmer_id) REFERENCES stations(id,farmer_id)
) ;

-- environment: Shared provider/grid/model series; never pretend to be on-farm hardware
CREATE TABLE weather_series (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), provider_id uuid NOT NULL REFERENCES providers(id), location_id uuid NOT NULL REFERENCES locations(id), model_name text NOT NULL, resolution_m integer NOT NULL CHECK(resolution_m>0), UNIQUE(provider_id,location_id,model_name), max_forecast_lead_days integer NOT NULL DEFAULT 15 CHECK(max_forecast_lead_days BETWEEN 0 AND 45)
) ;

-- environment: Historical observations, reanalysis or simulated history
CREATE TABLE weather_daily (
 dataset_id uuid NOT NULL REFERENCES datasets(id), series_id uuid NOT NULL REFERENCES weather_series(id), day date NOT NULL, kind text NOT NULL CHECK(kind IN ('observed','reanalysis','synthetic')), temperature_min_c numeric(6,2), temperature_max_c numeric(6,2), rainfall_mm numeric(9,3) CHECK(rainfall_mm>=0), humidity_mean_pct numeric(6,2) CHECK(humidity_mean_pct BETWEEN 0 AND 100), et0_mm numeric(8,3) CHECK(et0_mm>=0), PRIMARY KEY(dataset_id,series_id,day), CHECK(temperature_max_c>=temperature_min_c)
) ;

-- environment: Issued short-range forecasts or explicitly labeled long-range scenarios
CREATE TABLE weather_forecasts (
 dataset_id uuid NOT NULL REFERENCES datasets(id), series_id uuid NOT NULL REFERENCES weather_series(id), issued_at timestamptz NOT NULL, valid_on date NOT NULL, kind text NOT NULL CHECK(kind IN ('forecast','scenario')), temperature_min_c numeric(6,2), temperature_max_c numeric(6,2), rainfall_mm numeric(9,3) CHECK(rainfall_mm>=0), rainfall_probability numeric(5,4) CHECK(rainfall_probability BETWEEN 0 AND 1), method text NOT NULL, PRIMARY KEY(dataset_id,series_id,issued_at,valid_on), CHECK(valid_on>= (issued_at AT TIME ZONE 'Asia/Kolkata')::date), CHECK(temperature_max_c>=temperature_min_c)
) ;

-- environment: Consent-scoped real lab reports or demo samples
CREATE TABLE soil_samples (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), plot_id uuid NOT NULL, dataset_id uuid NOT NULL REFERENCES datasets(id), sampled_on date NOT NULL, sample_type text NOT NULL CHECK(sample_type IN ('lab','farmer_report','synthetic')), lab_name text, report_uri text, UNIQUE(id,farmer_id), FOREIGN KEY(plot_id,farmer_id) REFERENCES plots(id,farmer_id), report_metadata jsonb NOT NULL DEFAULT '{}'
) ;

-- environment: Property/unit/depth/uncertainty, with predicted values distinct from lab values
CREATE TABLE soil_indicators (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), plot_id uuid NOT NULL, sample_id uuid, dataset_id uuid NOT NULL REFERENCES datasets(id), property text NOT NULL, depth_top_cm numeric(6,2) NOT NULL CHECK(depth_top_cm>=0), depth_bottom_cm numeric(6,2) NOT NULL, unit_code text NOT NULL REFERENCES units(code), mean_value numeric(14,4) NOT NULL, lower_value numeric(14,4), upper_value numeric(14,4), evidence_type text NOT NULL CHECK(evidence_type IN ('lab','grid_prediction','synthetic','farmer_report')), FOREIGN KEY(plot_id,farmer_id) REFERENCES plots(id,farmer_id), FOREIGN KEY(sample_id,farmer_id) REFERENCES soil_samples(id,farmer_id), CHECK(depth_bottom_cm>depth_top_cm), CHECK(lower_value IS NULL OR lower_value<=mean_value), CHECK(upper_value IS NULL OR upper_value>=mean_value), reported_basis text NOT NULL DEFAULT 'unspecified'
) ;

-- environment: STAC scene metadata and immutable external asset reference
CREATE TABLE satellite_assets (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), dataset_id uuid NOT NULL REFERENCES datasets(id), provider_item_id text NOT NULL, acquired_at timestamptz NOT NULL, collection text NOT NULL, cloud_pct numeric(5,2) CHECK(cloud_pct BETWEEN 0 AND 100), asset_uri text NOT NULL, footprint_geojson jsonb, UNIQUE(dataset_id,collection,provider_item_id)
) ;

-- environment: Cloud-masked vegetation indicators with valid pixel coverage
CREATE TABLE plot_indices (
 dataset_id uuid NOT NULL REFERENCES datasets(id), farmer_id uuid NOT NULL REFERENCES farmers(id), plot_id uuid NOT NULL, asset_id uuid REFERENCES satellite_assets(id), day date NOT NULL, index_name text NOT NULL, value numeric(8,5) NOT NULL, valid_pixel_fraction numeric(5,4) NOT NULL CHECK(valid_pixel_fraction BETWEEN 0 AND 1), method_version text NOT NULL, PRIMARY KEY(dataset_id,plot_id,day,index_name), FOREIGN KEY(plot_id,farmer_id) REFERENCES plots(id,farmer_id)
) ;

-- market: Daily market observations; synthetic history only in the demo DB
CREATE TABLE price_observations (
 dataset_id uuid NOT NULL REFERENCES datasets(id), series_id uuid NOT NULL REFERENCES market_series(id), observed_on date NOT NULL, min_price numeric(14,2) NOT NULL, modal_price numeric(14,2) NOT NULL, max_price numeric(14,2) NOT NULL, arrivals_quantity numeric(14,3), arrivals_unit text REFERENCES units(code), fetched_at timestamptz NOT NULL, revision integer NOT NULL DEFAULT 1 CHECK(revision>0), PRIMARY KEY(dataset_id,series_id,observed_on), CHECK(min_price>=0 AND min_price<=modal_price AND modal_price<=max_price)
) PARTITION BY RANGE(observed_on);

-- market: Training cutoff, backtest evidence and scenario-only markers
CREATE TABLE model_versions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name text NOT NULL, version text NOT NULL, purpose text NOT NULL, trained_until date, validation jsonb NOT NULL, artifact_uri text, status text NOT NULL CHECK(status IN ('scenario_only','validated','retired')), UNIQUE(name,version)
) ;

-- market: One issuance with training cutoff and horizon
CREATE TABLE forecast_runs (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), dataset_id uuid NOT NULL REFERENCES datasets(id), model_id uuid NOT NULL REFERENCES model_versions(id), issued_at timestamptz NOT NULL, training_cutoff date NOT NULL, horizon_days integer NOT NULL CHECK(horizon_days BETWEEN 1 AND 365), kind text NOT NULL CHECK(kind IN ('forecast','scenario')), UNIQUE(id,kind), CHECK(training_cutoff<=(issued_at AT TIME ZONE 'Asia/Kolkata')::date)
) ;

-- market: Future scenarios or backtested forecasts; never observed prices
CREATE TABLE price_projections (
 run_id uuid NOT NULL, series_id uuid NOT NULL REFERENCES market_series(id), valid_on date NOT NULL, kind text NOT NULL CHECK(kind IN ('forecast','scenario')), lower_price numeric(14,2) NOT NULL, central_price numeric(14,2) NOT NULL, upper_price numeric(14,2) NOT NULL, interval_definition text NOT NULL, PRIMARY KEY(run_id,series_id,valid_on), FOREIGN KEY(run_id,kind) REFERENCES forecast_runs(id,kind), CHECK(lower_price>=0 AND lower_price<=central_price AND central_price<=upper_price)
) ;

-- market: Official policy by crop/grade/marketing season with notification URL
CREATE TABLE msp_announcements (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), dataset_id uuid NOT NULL REFERENCES datasets(id), crop_id uuid NOT NULL REFERENCES crops(id), grade text NOT NULL, marketing_season text NOT NULL, announced_on date NOT NULL, effective_from date NOT NULL, amount_inr_quintal numeric(14,2) NOT NULL CHECK(amount_inr_quintal>0), official_url text NOT NULL, UNIQUE(dataset_id,crop_id,grade,marketing_season)
) ;

-- knowledge: Versioned official source document, language, license and review date
CREATE TABLE documents (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), dataset_id uuid NOT NULL REFERENCES datasets(id), source_url text NOT NULL, title text NOT NULL, language text NOT NULL, checksum text NOT NULL, published_on date, retrieved_at timestamptz NOT NULL, review_status text NOT NULL CHECK(review_status IN ('needs_review','reviewed','retired')), object_uri text, UNIQUE(dataset_id,checksum)
) ;

-- knowledge: Citable document sections; PostgreSQL text search before optional embeddings
CREATE TABLE document_chunks (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), document_id uuid NOT NULL REFERENCES documents(id), ordinal integer NOT NULL, page_number integer, section_title text, content text NOT NULL, search_vector tsvector GENERATED ALWAYS AS (to_tsvector('simple',coalesce(section_title,'')||' '||content)) STORED, UNIQUE(document_id,ordinal)
) ;

-- knowledge: Region/season/crop stage guidance and validated assumptions
CREATE TABLE crop_guides (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), document_id uuid NOT NULL REFERENCES documents(id), crop_id uuid NOT NULL REFERENCES crops(id), region_id uuid REFERENCES regions(id), season text NOT NULL, growth_stage text NOT NULL, guidance jsonb NOT NULL, verified_at timestamptz
) ;

-- knowledge: Reference symptoms and expert-reviewed support, not fabricated dosage
CREATE TABLE diseases (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), code text NOT NULL UNIQUE, name text NOT NULL, crop_id uuid NOT NULL REFERENCES crops(id), reference_document_id uuid REFERENCES documents(id), symptoms jsonb NOT NULL, expert_reviewed_at timestamptz
) ;

-- knowledge: Real submitted image and uncertain model assessment; no invented ground truth
CREATE TABLE disease_cases (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), cycle_id uuid NOT NULL, image_uri text NOT NULL, image_hash text NOT NULL, captured_at timestamptz, assessment jsonb, model_version text, clinician_label text, reviewed_by text, status text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), FOREIGN KEY(cycle_id,farmer_id) REFERENCES crop_cycles(id,farmer_id)
) ;

-- knowledge: Versioned real scheme requirements and official application link
CREATE TABLE scheme_versions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), document_id uuid NOT NULL REFERENCES documents(id), scheme_code text NOT NULL, version text NOT NULL, name text NOT NULL, region_id uuid REFERENCES regions(id), requirements jsonb NOT NULL, benefits jsonb NOT NULL, application_url text NOT NULL, verified_at timestamptz, valid_from date, valid_to date, UNIQUE(scheme_code,version)
) ;

-- knowledge: Explained recommendation, missing answers and reviewed application checklist
CREATE TABLE scheme_checks (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), scheme_version_id uuid NOT NULL REFERENCES scheme_versions(id), result text NOT NULL CHECK(result IN ('potential_match','missing_information','not_matched')), reasons jsonb NOT NULL, checked_at timestamptz NOT NULL, official_decision_reference text
) ;

-- knowledge: Published aggregate crop area, production and yield; no farm-level inference
CREATE TABLE regional_statistics (
 dataset_id uuid NOT NULL REFERENCES datasets(id), region_id uuid NOT NULL REFERENCES regions(id), crop_id uuid NOT NULL REFERENCES crops(id), year integer NOT NULL, season text NOT NULL, area_ha numeric(16,3), production_t numeric(16,3), yield_t_ha numeric(12,4), estimate_stage text NOT NULL, PRIMARY KEY(dataset_id,region_id,crop_id,year,season,estimate_stage)
) ;

-- agent: Owned conversation header and resumable summary cursor
CREATE TABLE conversations (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), title text NOT NULL, summary text, summarized_through bigint NOT NULL DEFAULT 0, archived_at timestamptz, UNIQUE(id,farmer_id), created_at timestamptz NOT NULL DEFAULT now()
) ;

-- agent: Append-only complete public transcript, sequence and token accounting
CREATE TABLE messages (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), conversation_id uuid NOT NULL, sequence bigint NOT NULL, role text NOT NULL CHECK(role IN ('user','assistant','tool')), content jsonb NOT NULL, token_count integer CHECK(token_count>=0), created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(conversation_id,sequence), UNIQUE(id,farmer_id), FOREIGN KEY(conversation_id,farmer_id) REFERENCES conversations(id,farmer_id)
) ;

-- agent: Bounded run, lease owner, cancellation and terminal state
CREATE TABLE agent_runs (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), conversation_id uuid NOT NULL, request_key text NOT NULL, status text NOT NULL, lease_expires_at timestamptz, started_at timestamptz, ended_at timestamptz, model_name text, UNIQUE(farmer_id,request_key), UNIQUE(id,farmer_id), FOREIGN KEY(conversation_id,farmer_id) REFERENCES conversations(id,farmer_id)
) ;

-- agent: Validated arguments, result and idempotent execution identity
CREATE TABLE tool_calls (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), run_id uuid NOT NULL, call_key text NOT NULL, tool_name text NOT NULL, arguments jsonb NOT NULL, result jsonb, status text NOT NULL, started_at timestamptz, ended_at timestamptz, UNIQUE(run_id,call_key), UNIQUE(id,farmer_id), FOREIGN KEY(run_id,farmer_id) REFERENCES agent_runs(id,farmer_id), tool_version_id uuid
) ;

-- agent: Exact argument hash and explicit decision before a write
CREATE TABLE approvals (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), tool_call_id uuid NOT NULL, arguments_hash text NOT NULL, decision text CHECK(decision IN ('approved','rejected')), decided_at timestamptz, expires_at timestamptz NOT NULL, UNIQUE(tool_call_id), FOREIGN KEY(tool_call_id,farmer_id) REFERENCES tool_calls(id,farmer_id)
) ;

-- agent: Owned file metadata, safe excerpt, hash and object storage reference
CREATE TABLE artifacts (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), run_id uuid, title text NOT NULL, format text NOT NULL CHECK(format IN ('docx','pdf','xlsx','csv','pptx')), object_uri text NOT NULL, bytes bigint NOT NULL CHECK(bytes>=0), checksum text NOT NULL, preview jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), FOREIGN KEY(run_id,farmer_id) REFERENCES agent_runs(id,farmer_id)
) ;

-- agent: Correction-aware durable farmer facts with evidence, expiry and text search
CREATE TABLE memories (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), fact_key text NOT NULL, value jsonb NOT NULL, evidence_message_id uuid, confidence numeric(5,4) CHECK(confidence BETWEEN 0 AND 1), valid_from timestamptz NOT NULL, valid_to timestamptz, supersedes_id uuid, search_text text NOT NULL, search_vector tsvector GENERATED ALWAYS AS (to_tsvector('simple',search_text)) STORED, UNIQUE(id,farmer_id), FOREIGN KEY(evidence_message_id,farmer_id) REFERENCES messages(id,farmer_id), FOREIGN KEY(supersedes_id,farmer_id) REFERENCES memories(id,farmer_id), CHECK(valid_to IS NULL OR valid_to>valid_from)
) ;

-- agent: Answer evidence references with exact excerpts and source versions
CREATE TABLE retrieval_citations (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), run_id uuid NOT NULL, chunk_id uuid REFERENCES document_chunks(id), dataset_id uuid REFERENCES datasets(id), source_record_key jsonb, excerpt text NOT NULL, FOREIGN KEY(run_id,farmer_id) REFERENCES agent_runs(id,farmer_id)
) ;

-- agent: Transactional outbox; demo delivery disabled, never imply an actual send
CREATE TABLE notifications (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), task_id uuid, channel text NOT NULL CHECK(channel IN ('in_app','sms','whatsapp','email')), delivery_allowed boolean NOT NULL DEFAULT false, scheduled_at timestamptz NOT NULL, status text NOT NULL, payload jsonb NOT NULL, dedupe_key text NOT NULL, attempts integer NOT NULL DEFAULT 0, UNIQUE(farmer_id,dedupe_key), FOREIGN KEY(task_id,farmer_id) REFERENCES tasks(id,farmer_id)
) ;

-- reference: Reviewed external crop/variety/market/region identifiers, never fuzzy-merge silently
CREATE TABLE source_mappings (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), provider_id uuid NOT NULL REFERENCES providers(id), entity_type text NOT NULL CHECK(entity_type IN ('crop','variety','market','region')), external_key text NOT NULL, crop_id uuid REFERENCES crops(id), variety_id uuid REFERENCES crop_varieties(id), market_id uuid REFERENCES markets(id), region_id uuid REFERENCES regions(id), valid_from date NOT NULL, valid_to date, reviewed_at timestamptz, CHECK(valid_to IS NULL OR valid_to>=valid_from), CHECK(num_nonnulls(crop_id,variety_id,market_id,region_id)=1), CHECK((entity_type='crop')=(crop_id IS NOT NULL)), CHECK((entity_type='variety')=(variety_id IS NOT NULL)), CHECK((entity_type='market')=(market_id IS NOT NULL)), CHECK((entity_type='region')=(region_id IS NOT NULL))
) ;

-- ingestion: Per-provider/scope freshness, outage, rate limiting and last-good state
CREATE TABLE source_health (
 provider_id uuid NOT NULL REFERENCES providers(id), scope_key text NOT NULL, checked_at timestamptz NOT NULL, last_success_at timestamptz, source_valid_through date, status text NOT NULL CHECK(status IN ('healthy','stale','outage','rate_limited','unknown')), retry_after timestamptz, safe_error text, PRIMARY KEY(provider_id,scope_key)
) ;

-- reference: Soil property basis, accepted units, bounds and non-convertible nutrient forms
CREATE TABLE measurement_definitions (
 code text PRIMARY KEY, name text NOT NULL, basis text NOT NULL, allowed_units jsonb NOT NULL CHECK(jsonb_typeof(allowed_units)='array'), minimum_value numeric, maximum_value numeric, interpretation text NOT NULL, CHECK(maximum_value IS NULL OR minimum_value IS NULL OR maximum_value>=minimum_value)
) ;

-- environment: Plot/depth field capacity and wilting point for explicit volumetric water balance
CREATE TABLE soil_calibrations (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), plot_id uuid NOT NULL, dataset_id uuid NOT NULL REFERENCES datasets(id), measured_on date NOT NULL, depth_top_cm numeric NOT NULL CHECK(depth_top_cm>=0), depth_bottom_cm numeric NOT NULL, field_capacity_vwc_pct numeric NOT NULL CHECK(field_capacity_vwc_pct BETWEEN 0 AND 100), wilting_point_vwc_pct numeric NOT NULL CHECK(wilting_point_vwc_pct BETWEEN 0 AND 100), bulk_density_g_cm3 numeric CHECK(bulk_density_g_cm3>0 AND bulk_density_g_cm3<3), method text NOT NULL, evidence_type text NOT NULL CHECK(evidence_type IN ('lab','derived','synthetic')), FOREIGN KEY(plot_id,farmer_id) REFERENCES plots(id,farmer_id), CHECK(depth_bottom_cm>depth_top_cm), CHECK(field_capacity_vwc_pct>wilting_point_vwc_pct)
) ;

-- agent: Owned input image/report/audio metadata with quarantine and extraction status
CREATE TABLE attachments (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), message_id uuid, object_uri text NOT NULL, original_name text NOT NULL, mime_type text NOT NULL, bytes bigint NOT NULL CHECK(bytes>0), checksum text NOT NULL, scan_status text NOT NULL CHECK(scan_status IN ('pending','clean','rejected')), extracted_text text, metadata jsonb NOT NULL DEFAULT '{}', UNIQUE(id,farmer_id), FOREIGN KEY(message_id,farmer_id) REFERENCES messages(id,farmer_id), created_at timestamptz NOT NULL DEFAULT now()
) ;

-- farm: Farmer reports of stage, symptoms, pests, moisture and uncertainty with optional photo
CREATE TABLE field_observations (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), cycle_id uuid NOT NULL, observed_at timestamptz NOT NULL, type text NOT NULL, observation jsonb NOT NULL CHECK(jsonb_typeof(observation)='object'), attachment_id uuid, origin text NOT NULL CHECK(origin IN ('user_reported','synthetic')), FOREIGN KEY(cycle_id,farmer_id) REFERENCES crop_cycles(id,farmer_id), FOREIGN KEY(attachment_id,farmer_id) REFERENCES attachments(id,farmer_id)
) ;

-- farm: Actual harvest stock, moisture/grade evidence and storage; units never inferred
CREATE TABLE harvest_batches (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), cycle_id uuid NOT NULL, harvested_on date NOT NULL, quantity numeric(14,3) NOT NULL CHECK(quantity>0), unit_code text NOT NULL REFERENCES units(code), grade text NOT NULL, moisture_pct numeric CHECK(moisture_pct BETWEEN 0 AND 100), quality_evidence jsonb NOT NULL DEFAULT '{}', storage_notes text, execution_key text NOT NULL, UNIQUE(farmer_id,execution_key), UNIQUE(id,farmer_id), FOREIGN KEY(cycle_id,farmer_id) REFERENCES crop_cycles(id,farmer_id)
) ;

-- farm: Recorded sale proceeds and selling costs, distinct from mandi quotes and payment claims
CREATE TABLE sale_records (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), batch_id uuid NOT NULL, sold_on date NOT NULL, quantity numeric(14,3) NOT NULL CHECK(quantity>0), unit_code text NOT NULL REFERENCES units(code), unit_price_inr numeric(14,2) NOT NULL CHECK(unit_price_inr>=0), selling_cost_inr numeric(14,2) NOT NULL CHECK(selling_cost_inr>=0), gross_inr numeric(18,2) GENERATED ALWAYS AS (round(quantity*unit_price_inr,2)) STORED, net_inr numeric(18,2) GENERATED ALWAYS AS (round(quantity*unit_price_inr-selling_cost_inr,2)) STORED, payment_status text NOT NULL CHECK(payment_status IN ('reported_paid','pending','unknown','demo')), receipt_uri text, execution_key text NOT NULL, UNIQUE(farmer_id,execution_key), FOREIGN KEY(batch_id,farmer_id) REFERENCES harvest_batches(id,farmer_id)
) ;

-- agent: Versioned skill descriptions, farmer purpose, workflow hash and allowed tools
CREATE TABLE skill_versions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), code text NOT NULL, version text NOT NULL, title text NOT NULL, farmer_description text NOT NULL, workflow text NOT NULL, workflow_hash text NOT NULL, allowed_tools jsonb NOT NULL, active boolean NOT NULL DEFAULT false, UNIQUE(code,version)
) ;

-- agent: Versioned tool argument/output schemas and side-effect policy
CREATE TABLE tool_versions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), code text NOT NULL, version text NOT NULL, title text NOT NULL, arguments_schema jsonb NOT NULL, output_schema jsonb NOT NULL, effect text NOT NULL CHECK(effect IN ('read','artifact','write','external','hardware')), requires_approval boolean NOT NULL, active boolean NOT NULL DEFAULT false, UNIQUE(code,version), CHECK(effect NOT IN ('write','external','hardware') OR requires_approval)
) ;

-- agent: Resumable public progress/tool/artifact/question timeline; no hidden chain-of-thought
CREATE TABLE run_events (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), run_id uuid NOT NULL, sequence bigint NOT NULL CHECK(sequence>0), event_type text NOT NULL CHECK(event_type IN ('started','skill','tool_started','tool_result','question','approval','text_delta','artifact','completed','failed','cancelled')), payload jsonb NOT NULL, occurred_at timestamptz NOT NULL, UNIQUE(run_id,sequence), FOREIGN KEY(run_id,farmer_id) REFERENCES agent_runs(id,farmer_id)
) ;

-- agent: Persisted structured farmer question and waiting state across reconnect/restart
CREATE TABLE question_requests (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), run_id uuid NOT NULL, tool_call_id uuid, prompt text NOT NULL, form_schema jsonb NOT NULL, status text NOT NULL CHECK(status IN ('waiting','answered','cancelled','expired')), expires_at timestamptz NOT NULL, UNIQUE(id,farmer_id), FOREIGN KEY(run_id,farmer_id) REFERENCES agent_runs(id,farmer_id), FOREIGN KEY(tool_call_id,farmer_id) REFERENCES tool_calls(id,farmer_id), created_at timestamptz NOT NULL DEFAULT now()
) ;

-- agent: Typed answer payload and revision identity; server validates against request form schema
CREATE TABLE question_answers (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), question_id uuid NOT NULL, answer_version integer NOT NULL CHECK(answer_version>0), answers jsonb NOT NULL CHECK(jsonb_typeof(answers)='object'), submitted_at timestamptz NOT NULL, execution_key text NOT NULL, UNIQUE(question_id,answer_version), UNIQUE(farmer_id,execution_key), FOREIGN KEY(question_id,farmer_id) REFERENCES question_requests(id,farmer_id)
) ;

-- agent: Versioned summary checkpoints, covered sequences, open questions and token budget audit
CREATE TABLE context_compactions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), conversation_id uuid NOT NULL, first_sequence bigint NOT NULL CHECK(first_sequence>0), last_sequence bigint NOT NULL, summary text NOT NULL, pending_work jsonb NOT NULL, tokens_before integer NOT NULL CHECK(tokens_before>=0), tokens_after integer NOT NULL CHECK(tokens_after>=0), method_version text NOT NULL, UNIQUE(conversation_id,last_sequence,method_version), FOREIGN KEY(conversation_id,farmer_id) REFERENCES conversations(id,farmer_id), CHECK(last_sequence>=first_sequence), created_at timestamptz NOT NULL DEFAULT now()
) ;

-- farm: Farmer-facing sourced/derived warning lifecycle with expiry and acknowledgment
CREATE TABLE alert_events (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), dataset_id uuid NOT NULL REFERENCES datasets(id), station_id uuid, source_key text NOT NULL, category text NOT NULL, severity text NOT NULL CHECK(severity IN ('info','watch','warning','critical')), message text NOT NULL, source_url text NOT NULL, issued_at timestamptz NOT NULL, expires_at timestamptz NOT NULL, acknowledged_at timestamptz, status text NOT NULL CHECK(status IN ('active','resolved','expired')), UNIQUE(farmer_id,dataset_id,source_key), FOREIGN KEY(station_id,farmer_id) REFERENCES stations(id,farmer_id), CHECK(expires_at>issued_at)
) ;

-- telemetry: Approved bounded command intent: mock/live, exact approval link, expiry and execution identity
CREATE TABLE device_commands (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), station_id uuid NOT NULL, tool_call_id uuid NOT NULL, approval_id uuid NOT NULL REFERENCES approvals(id), command text NOT NULL, arguments_hash text NOT NULL, payload jsonb NOT NULL, mode text NOT NULL CHECK(mode IN ('demo','live')), status text NOT NULL CHECK(status IN ('queued','sent','acknowledged','failed','expired','cancelled')), expires_at timestamptz NOT NULL, execution_key text NOT NULL, UNIQUE(farmer_id,execution_key), UNIQUE(id,farmer_id), FOREIGN KEY(station_id,farmer_id) REFERENCES stations(id,farmer_id), FOREIGN KEY(tool_call_id,farmer_id) REFERENCES tool_calls(id,farmer_id), created_at timestamptz NOT NULL DEFAULT now()
) ;

-- telemetry: Device acknowledgment/rejection/timeout audit; broker delivery is not execution proof
CREATE TABLE device_command_events (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id), command_id uuid NOT NULL, event_key text NOT NULL, event_type text NOT NULL CHECK(event_type IN ('sent','acknowledged','rejected','timeout','cancelled')), occurred_at timestamptz NOT NULL, device_response jsonb NOT NULL, UNIQUE(command_id,event_key), FOREIGN KEY(command_id,farmer_id) REFERENCES device_commands(id,farmer_id)
) ;
CREATE INDEX idx_jobs_due ON ingest_runs (next_attempt_at) WHERE state IN ('queued','failed');
CREATE INDEX idx_quality_dataset ON quality_issues (dataset_id,created_at DESC) WHERE resolved_at IS NULL;
CREATE INDEX idx_regions_parent ON regions (parent_id,level);
CREATE INDEX idx_locations_region ON locations (region_id);
CREATE INDEX idx_markets_region ON markets (region_id);
CREATE INDEX idx_series_crop ON market_series (crop_id,market_id,unit_code);
CREATE INDEX idx_tasks_open ON tasks (farmer_id,due_at) WHERE status='open' AND deleted_at IS NULL;
CREATE INDEX idx_expenses_date ON expenses (farmer_id,spent_on DESC) INCLUDE(amount_inr,category);
CREATE INDEX idx_packets_latest ON sensor_packets (farmer_id,station_id,observed_at DESC);
CREATE INDEX idx_packets_time_brin ON sensor_packets USING brin(observed_at);
CREATE INDEX idx_prices_latest ON price_observations (series_id,observed_on DESC) INCLUDE(modal_price,min_price,max_price);
CREATE INDEX idx_prices_time_brin ON price_observations USING brin(observed_on);
CREATE INDEX idx_projection_series ON price_projections (series_id,valid_on,run_id);
CREATE INDEX idx_projection_scenario_latest ON price_projections (series_id,valid_on DESC) WHERE kind='scenario';
CREATE INDEX idx_weather_latest ON weather_daily (series_id,day DESC);
CREATE INDEX idx_weather_forecast ON weather_forecasts (series_id,issued_at DESC,valid_on);
CREATE INDEX idx_indices_plot ON plot_indices (farmer_id,plot_id,day DESC);
CREATE INDEX idx_chunks_search ON document_chunks USING gin(search_vector);
CREATE INDEX idx_memory_search ON memories USING gin(search_vector);
CREATE UNIQUE INDEX idx_memory_current ON memories (farmer_id,fact_key) WHERE valid_to IS NULL;
CREATE INDEX idx_artifacts_owner ON artifacts (farmer_id,created_at DESC);
CREATE INDEX idx_messages_owner ON messages (farmer_id,conversation_id,sequence);
CREATE INDEX idx_scheme_documents ON scheme_versions (region_id,scheme_code);
CREATE INDEX idx_notification_due ON notifications (scheduled_at) WHERE status='queued' AND delivery_allowed;
CREATE UNIQUE INDEX idx_mapping_current ON source_mappings (provider_id,entity_type,external_key) WHERE valid_to IS NULL;
CREATE INDEX idx_alert_active ON alert_events (farmer_id,expires_at) WHERE status='active';
CREATE INDEX idx_events_resume ON run_events (farmer_id,run_id,sequence);
CREATE INDEX idx_question_waiting ON question_requests (farmer_id,expires_at) WHERE status='waiting';
CREATE INDEX idx_sales_day ON sale_records (farmer_id,sold_on DESC);
CREATE INDEX idx_commands_due ON device_commands (expires_at) WHERE status IN ('queued','sent');
CREATE INDEX idx_consents_farmer ON consents(farmer_id);
CREATE INDEX idx_farms_farmer ON farms(farmer_id);
CREATE INDEX idx_plots_farmer ON plots(farmer_id);
CREATE INDEX idx_crop_cycles_farmer ON crop_cycles(farmer_id);
CREATE INDEX idx_farm_operations_farmer ON farm_operations(farmer_id);
CREATE INDEX idx_resources_farmer ON resources(farmer_id);
CREATE INDEX idx_resource_listings_farmer ON resource_listings(farmer_id);
CREATE INDEX idx_expenses_farmer ON expenses(farmer_id);
CREATE INDEX idx_tasks_farmer ON tasks(farmer_id);
CREATE INDEX idx_task_events_farmer ON task_events(farmer_id);
CREATE INDEX idx_stations_farmer ON stations(farmer_id);
CREATE INDEX idx_station_sensors_farmer ON station_sensors(farmer_id);
CREATE INDEX idx_packet_receipts_farmer ON packet_receipts(farmer_id);
CREATE INDEX idx_sensor_packets_farmer ON sensor_packets(farmer_id);
CREATE INDEX idx_sensor_daily_farmer ON sensor_daily(farmer_id);
CREATE INDEX idx_soil_samples_farmer ON soil_samples(farmer_id);
CREATE INDEX idx_soil_indicators_farmer ON soil_indicators(farmer_id);
CREATE INDEX idx_plot_indices_farmer ON plot_indices(farmer_id);
CREATE INDEX idx_disease_cases_farmer ON disease_cases(farmer_id);
CREATE INDEX idx_scheme_checks_farmer ON scheme_checks(farmer_id);
CREATE INDEX idx_conversations_farmer ON conversations(farmer_id);
CREATE INDEX idx_messages_farmer ON messages(farmer_id);
CREATE INDEX idx_agent_runs_farmer ON agent_runs(farmer_id);
CREATE INDEX idx_tool_calls_farmer ON tool_calls(farmer_id);
CREATE INDEX idx_approvals_farmer ON approvals(farmer_id);
CREATE INDEX idx_artifacts_farmer ON artifacts(farmer_id);
CREATE INDEX idx_memories_farmer ON memories(farmer_id);
CREATE INDEX idx_retrieval_citations_farmer ON retrieval_citations(farmer_id);
CREATE INDEX idx_notifications_farmer ON notifications(farmer_id);
CREATE INDEX idx_soil_calibrations_farmer ON soil_calibrations(farmer_id);
CREATE INDEX idx_attachments_farmer ON attachments(farmer_id);
CREATE INDEX idx_field_observations_farmer ON field_observations(farmer_id);
CREATE INDEX idx_harvest_batches_farmer ON harvest_batches(farmer_id);
CREATE INDEX idx_sale_records_farmer ON sale_records(farmer_id);
CREATE INDEX idx_run_events_farmer ON run_events(farmer_id);
CREATE INDEX idx_question_requests_farmer ON question_requests(farmer_id);
CREATE INDEX idx_question_answers_farmer ON question_answers(farmer_id);
CREATE INDEX idx_context_compactions_farmer ON context_compactions(farmer_id);
CREATE INDEX idx_alert_events_farmer ON alert_events(farmer_id);
CREATE INDEX idx_device_commands_farmer ON device_commands(farmer_id);
CREATE INDEX idx_device_command_events_farmer ON device_command_events(farmer_id);

-- Monthly partition manager: identifier/value quoting, fixed allowlist and UTC bounds.
CREATE FUNCTION ensure_month_partitions(parent_name text, first_month date, last_month date)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE month_start date; next_month date; suffix text;
BEGIN
 IF parent_name NOT IN ('sensor_packets','price_observations') THEN RAISE EXCEPTION 'Unknown partition parent'; END IF;
 IF last_month<first_month OR last_month-first_month>3660 THEN RAISE EXCEPTION 'Invalid partition window'; END IF;
 month_start:=date_trunc('month',first_month)::date;
 WHILE month_start<=last_month LOOP
  next_month:=(month_start+interval '1 month')::date; suffix:=to_char(month_start,'YYYY_MM');
  EXECUTE format('CREATE TABLE IF NOT EXISTS sv3.%I PARTITION OF sv3.%I FOR VALUES FROM (%L) TO (%L)', parent_name||'_'||suffix,parent_name,month_start::text||' 00:00:00+00',next_month::text||' 00:00:00+00');
  month_start:=next_month;
 END LOOP;
END $$;

-- Dataset provenance enforcement, including synthetic-to-live leakage prevention.
CREATE FUNCTION guard_dataset() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='UPDATE' AND (NEW.provider_id,NEW.release_key,NEW.lane,NEW.origin,NEW.as_of_date,NEW.generator_version,NEW.seed,NEW.source_url) IS DISTINCT FROM (OLD.provider_id,OLD.release_key,OLD.lane,OLD.origin,OLD.as_of_date,OLD.generator_version,OLD.seed,OLD.source_url) THEN RAISE EXCEPTION 'Dataset lineage is immutable; create a new release'; END IF;
 IF current_database()='skyview_v3_live' AND NEW.lane<>'live' THEN RAISE EXCEPTION 'Demo datasets cannot enter live database'; END IF;
 IF NEW.origin='synthetic' AND NEW.lane<>'demo' THEN RAISE EXCEPTION 'Synthetic data must be in demo lane'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER dataset_guard BEFORE INSERT OR UPDATE ON datasets FOR EACH ROW EXECUTE FUNCTION guard_dataset();
CREATE FUNCTION guard_historical_day() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE cut date; day_value date;
BEGIN
 SELECT as_of_date INTO cut FROM sv3.datasets WHERE id=NEW.dataset_id;
 day_value:=CASE WHEN TG_TABLE_NAME LIKE 'price_observations%' THEN (to_jsonb(NEW)->>'observed_on')::date ELSE (to_jsonb(NEW)->>'day')::date END;
 IF day_value>cut THEN RAISE EXCEPTION 'Future value cannot be inserted into historical observations'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER price_history_guard BEFORE INSERT OR UPDATE ON price_observations FOR EACH ROW EXECUTE FUNCTION guard_historical_day();
CREATE TRIGGER weather_history_guard BEFORE INSERT OR UPDATE ON weather_daily FOR EACH ROW EXECUTE FUNCTION guard_historical_day();
CREATE FUNCTION guard_projection() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE issued date; horizon integer; trained date; model_state text; model_cutoff date; origin text;
BEGIN
 SELECT (r.issued_at AT TIME ZONE 'Asia/Kolkata')::date,r.horizon_days,r.training_cutoff,m.status,m.trained_until,d.origin INTO issued,horizon,trained,model_state,model_cutoff,origin
 FROM sv3.forecast_runs r JOIN sv3.model_versions m ON m.id=r.model_id JOIN sv3.datasets d ON d.id=r.dataset_id WHERE r.id=NEW.run_id;
 IF NEW.valid_on<=issued OR NEW.valid_on>issued+horizon THEN RAISE EXCEPTION 'Projection is outside issued horizon'; END IF;
 IF model_cutoff>trained THEN RAISE EXCEPTION 'Training leakage: model includes data beyond run cutoff'; END IF;
 IF NEW.kind='forecast' AND model_state<>'validated' THEN RAISE EXCEPTION 'Unvalidated model can only create scenarios'; END IF;
 IF NEW.kind='forecast' AND origin='synthetic' THEN RAISE EXCEPTION 'Synthetic data cannot produce real forecasts'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER projection_guard BEFORE INSERT OR UPDATE ON price_projections FOR EACH ROW EXECUTE FUNCTION guard_projection();

CREATE FUNCTION guard_evidence_kind() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE source_origin text; label text;
BEGIN
 SELECT origin INTO source_origin FROM sv3.datasets WHERE id=NEW.dataset_id;
 label:=coalesce(to_jsonb(NEW)->>'kind',to_jsonb(NEW)->>'sample_type',to_jsonb(NEW)->>'evidence_type');
 IF source_origin='synthetic' AND label NOT IN ('synthetic','scenario') THEN RAISE EXCEPTION 'Synthetic evidence cannot be labeled real'; END IF;
 IF source_origin<>'synthetic' AND label='synthetic' THEN RAISE EXCEPTION 'Synthetic label requires synthetic release'; END IF;
 IF label IN ('observed','reanalysis') AND source_origin<>label THEN RAISE EXCEPTION 'Historical evidence label disagrees with release origin'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER weather_kind_guard BEFORE INSERT OR UPDATE ON weather_daily FOR EACH ROW EXECUTE FUNCTION guard_evidence_kind();
CREATE TRIGGER weather_forecast_kind_guard BEFORE INSERT OR UPDATE ON weather_forecasts FOR EACH ROW EXECUTE FUNCTION guard_evidence_kind();
CREATE TRIGGER soil_sample_kind_guard BEFORE INSERT OR UPDATE ON soil_samples FOR EACH ROW EXECUTE FUNCTION guard_evidence_kind();
CREATE TRIGGER soil_indicator_kind_guard BEFORE INSERT OR UPDATE ON soil_indicators FOR EACH ROW EXECUTE FUNCTION guard_evidence_kind();
-- Uniqueness on nullable sensor depth must also cover surface sensors (PostgreSQL 15+).
CREATE UNIQUE INDEX idx_sensor_metric_depth ON station_sensors(station_id,metric,depth_cm) NULLS NOT DISTINCT;

ALTER TABLE sensor_packets ADD CONSTRAINT sensor_nonnegative CHECK((pm25_ug_m3 IS NULL OR pm25_ug_m3>=0) AND (pm10_ug_m3 IS NULL OR pm10_ug_m3>=0) AND (uv_index IS NULL OR uv_index>=0) AND (lux IS NULL OR lux>=0) AND (battery_v IS NULL OR battery_v>=0) AND (solar_v IS NULL OR solar_v>=0));
CREATE FUNCTION guard_weather_lead() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE max_lead integer; issue_day date;
BEGIN
 SELECT max_forecast_lead_days INTO max_lead FROM sv3.weather_series WHERE id=NEW.series_id;
 issue_day:=(NEW.issued_at AT TIME ZONE 'Asia/Kolkata')::date;
 IF NEW.kind='forecast' AND NEW.valid_on>issue_day+max_lead THEN RAISE EXCEPTION 'Daily weather forecast exceeds configured model lead'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER weather_lead_guard BEFORE INSERT OR UPDATE ON weather_forecasts FOR EACH ROW EXECUTE FUNCTION guard_weather_lead();
CREATE FUNCTION guard_packet_date() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE cut date;
BEGIN
 SELECT as_of_date INTO cut FROM sv3.datasets WHERE id=NEW.dataset_id;
 IF (NEW.observed_at AT TIME ZONE 'UTC')::date>cut THEN RAISE EXCEPTION 'Packet observation exceeds release cutoff'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER packet_date_guard BEFORE INSERT OR UPDATE ON sensor_packets FOR EACH ROW EXECUTE FUNCTION guard_packet_date();

ALTER TABLE soil_indicators ADD CONSTRAINT soil_property_known FOREIGN KEY(property) REFERENCES measurement_definitions(code);
ALTER TABLE tool_calls ADD CONSTRAINT call_tool_version FOREIGN KEY(tool_version_id) REFERENCES tool_versions(id);
CREATE UNIQUE INDEX idx_skill_active ON skill_versions(code) WHERE active;
CREATE UNIQUE INDEX idx_tool_active ON tool_versions(code) WHERE active;
CREATE FUNCTION guard_soil_units() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE def sv3.measurement_definitions;
BEGIN
 SELECT * INTO def FROM sv3.measurement_definitions WHERE code=NEW.property;
 IF NOT def.allowed_units ? NEW.unit_code THEN RAISE EXCEPTION 'Incompatible soil property unit'; END IF;
 IF NEW.unit_code='percent' AND NEW.mean_value>100 THEN RAISE EXCEPTION 'Percent soil value exceeds 100'; END IF;
 IF NEW.mean_value<def.minimum_value OR NEW.mean_value>def.maximum_value THEN RAISE EXCEPTION 'Soil value outside property bounds'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER soil_units_guard BEFORE INSERT OR UPDATE ON soil_indicators FOR EACH ROW EXECUTE FUNCTION guard_soil_units();
CREATE TRIGGER soil_calibration_kind_guard BEFORE INSERT OR UPDATE ON soil_calibrations FOR EACH ROW EXECUTE FUNCTION guard_evidence_kind();
CREATE FUNCTION guard_demo_delivery() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE farmer_lane text;
BEGIN
 SELECT d.lane INTO farmer_lane FROM sv3.farmers f JOIN sv3.datasets d ON d.id=f.dataset_id WHERE f.id=NEW.farmer_id;
 IF farmer_lane='demo' AND NEW.delivery_allowed AND NEW.channel<>'in_app' THEN RAISE EXCEPTION 'Demo cannot deliver external messages'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER demo_delivery_guard BEFORE INSERT OR UPDATE ON notifications FOR EACH ROW EXECUTE FUNCTION guard_demo_delivery();
CREATE FUNCTION command_argument_hash(station uuid, action text, lane text, arguments jsonb) RETURNS text LANGUAGE sql IMMUTABLE STRICT AS $$
 SELECT encode(sha256(convert_to(jsonb_build_object('station_id',station,'command',action,'mode',lane,'payload',arguments)::text,'UTF8')),'hex');
$$;
CREATE FUNCTION guard_device_command() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE approved sv3.approvals; station_lane text;
BEGIN
 SELECT * INTO approved FROM sv3.approvals WHERE id=NEW.approval_id;
 IF approved.farmer_id IS DISTINCT FROM NEW.farmer_id OR approved.tool_call_id IS DISTINCT FROM NEW.tool_call_id OR approved.arguments_hash IS DISTINCT FROM NEW.arguments_hash OR approved.decision IS DISTINCT FROM 'approved' OR approved.expires_at<=now() THEN RAISE EXCEPTION 'Command requires matching unexpired approval'; END IF;
 SELECT d.lane INTO station_lane FROM sv3.stations s JOIN sv3.datasets d ON d.id=s.dataset_id WHERE s.id=NEW.station_id;
 IF NEW.mode<>station_lane THEN RAISE EXCEPTION 'Command mode must match station data lane'; END IF;
 IF NEW.arguments_hash<>sv3.command_argument_hash(NEW.station_id,NEW.command,NEW.mode,NEW.payload) THEN RAISE EXCEPTION 'Command payload does not match approved intent'; END IF;
 IF NEW.expires_at<=now() OR NEW.expires_at>approved.expires_at THEN RAISE EXCEPTION 'Invalid command expiry'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER command_guard BEFORE INSERT OR UPDATE OF farmer_id,station_id,tool_call_id,approval_id,arguments_hash,command,payload,mode,expires_at ON device_commands FOR EACH ROW EXECUTE FUNCTION guard_device_command();
CREATE FUNCTION bump_task_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN NEW.row_version:=OLD.row_version+1; RETURN NEW; END $$;
CREATE TRIGGER task_version_guard BEFORE UPDATE ON tasks FOR EACH ROW EXECUTE FUNCTION bump_task_version();
CREATE FUNCTION guard_market_unit() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE dim text;
BEGIN SELECT dimension INTO dim FROM sv3.units WHERE code=NEW.unit_code;
 IF dim NOT IN ('mass','count') THEN RAISE EXCEPTION 'Market price requires mass or count unit'; END IF;
 RETURN NEW; END $$;
CREATE TRIGGER market_unit_guard BEFORE INSERT OR UPDATE ON market_series FOR EACH ROW EXECUTE FUNCTION guard_market_unit();
CREATE FUNCTION guard_harvest_edit() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE sold numeric;
BEGIN
 SELECT coalesce(sum(quantity),0) INTO sold FROM sv3.sale_records WHERE batch_id=OLD.id;
 IF NEW.quantity<sold OR (sold>0 AND NEW.unit_code<>OLD.unit_code) THEN RAISE EXCEPTION 'Harvest edit conflicts with recorded sales'; END IF;
 RETURN NEW; END $$;
CREATE TRIGGER harvest_edit_guard BEFORE UPDATE ON harvest_batches FOR EACH ROW EXECUTE FUNCTION guard_harvest_edit();
CREATE FUNCTION guard_sale() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE batch sv3.harvest_batches; sold numeric;
BEGIN
 SELECT * INTO batch FROM sv3.harvest_batches WHERE id=NEW.batch_id FOR UPDATE;
 IF NEW.unit_code<>batch.unit_code THEN RAISE EXCEPTION 'Sale and harvest units differ; normalize explicitly before recording'; END IF;
 IF NEW.sold_on<batch.harvested_on THEN RAISE EXCEPTION 'Sale precedes harvest'; END IF;
 SELECT coalesce(sum(quantity),0) INTO sold FROM sv3.sale_records WHERE batch_id=NEW.batch_id AND id<>NEW.id;
 IF sold+NEW.quantity>batch.quantity THEN RAISE EXCEPTION 'Sale exceeds recorded harvest stock'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER sale_stock_guard BEFORE INSERT OR UPDATE ON sale_records FOR EACH ROW EXECUTE FUNCTION guard_sale();
ALTER TABLE farmers ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON farmers USING (id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE consents ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON consents USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE farms ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON farms USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE plots ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON plots USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE crop_cycles ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON crop_cycles USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE farm_operations ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON farm_operations USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE resources ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON resources USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE resource_listings ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON resource_listings USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE expenses ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON expenses USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON tasks USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE task_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON task_events USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE stations ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON stations USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE station_sensors ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON station_sensors USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE packet_receipts ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON packet_receipts USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE sensor_packets ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON sensor_packets USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE sensor_daily ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON sensor_daily USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE soil_samples ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON soil_samples USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE soil_indicators ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON soil_indicators USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE plot_indices ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON plot_indices USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE disease_cases ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON disease_cases USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE scheme_checks ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON scheme_checks USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON conversations USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON messages USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE agent_runs ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON agent_runs USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE tool_calls ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON tool_calls USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE approvals ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON approvals USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE artifacts ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON artifacts USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE memories ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON memories USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE retrieval_citations ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON retrieval_citations USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON notifications USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE soil_calibrations ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON soil_calibrations USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE attachments ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON attachments USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE field_observations ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON field_observations USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE harvest_batches ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON harvest_batches USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE sale_records ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON sale_records USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE run_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON run_events USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE question_requests ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON question_requests USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE question_answers ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON question_answers USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE context_compactions ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON context_compactions USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE alert_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON alert_events USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE device_commands ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON device_commands USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE device_command_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_scope ON device_command_events USING (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK (farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE resource_matches ENABLE ROW LEVEL SECURITY;
CREATE POLICY participant_scope ON resource_matches USING (
 requester_id=nullif(current_setting('app.farmer_id',true),'')::uuid OR
 EXISTS(SELECT 1 FROM sv3.resource_listings l WHERE l.id=listing_id AND l.farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid)
) WITH CHECK(requester_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
CREATE VIEW latest_prices WITH (security_invoker=true) AS
 SELECT DISTINCT ON (series_id) * FROM price_observations ORDER BY series_id,observed_on DESC,fetched_at DESC;
CREATE VIEW current_memories WITH (security_invoker=true) AS SELECT * FROM memories WHERE valid_to IS NULL;
COMMIT;
