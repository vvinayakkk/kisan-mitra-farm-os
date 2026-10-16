"""Generate a complete PostgreSQL schema and readable table catalog."""

import json
from pathlib import Path

from schema_additions import INDEXES, SQL, extend

HERE = Path(__file__).parent
TABLES = []


def table(name, group, purpose, columns, private=False, tail=""):
    TABLES.append(
        {
            "name": name,
            "group": group,
            "purpose": purpose,
            "columns": columns,
            "private": private,
            "tail": tail,
        }
    )


U = "uuid PRIMARY KEY DEFAULT gen_random_uuid()"
D = "dataset_id uuid NOT NULL REFERENCES datasets(id)"
F = "farmer_id uuid NOT NULL REFERENCES farmers(id)"
T = "created_at timestamptz NOT NULL DEFAULT now()"

# Lineage and controlled ingestion.
table(
    "providers",
    "ingestion",
    "Source contract, license, access and refresh policy",
    f"id {U}, code text NOT NULL UNIQUE, name text NOT NULL, homepage text NOT NULL, access_method text NOT NULL, license_name text, attribution text NOT NULL, status text NOT NULL DEFAULT 'planned', refresh_seconds integer CHECK(refresh_seconds>0), configuration jsonb NOT NULL DEFAULT '{{}}', {T}",
)
table(
    "datasets",
    "ingestion",
    "Immutable release boundary for live versus synthetic data",
    f"id {U}, provider_id uuid NOT NULL REFERENCES providers(id), release_key text NOT NULL UNIQUE, lane text NOT NULL CHECK(lane IN ('live','demo')), origin text NOT NULL CHECK(origin IN ('observed','reanalysis','modeled','synthetic','user_reported','derived','curated')), as_of_date date NOT NULL, generator_version text, seed bigint, source_url text NOT NULL, checksum text, {T}, CHECK(lane<>'live' OR origin<>'synthetic'), CHECK(origin<>'synthetic' OR generator_version IS NOT NULL)",
)
table(
    "ingest_runs",
    "ingestion",
    "Watermark, retries, bounded jobs and source failure audit",
    f"id {U}, provider_id uuid NOT NULL REFERENCES providers(id), dataset_id uuid REFERENCES datasets(id), job_key text NOT NULL UNIQUE, state text NOT NULL CHECK(state IN ('queued','running','done','failed')), cursor jsonb, attempts integer NOT NULL DEFAULT 0, rows_received bigint NOT NULL DEFAULT 0, rows_accepted bigint NOT NULL DEFAULT 0, started_at timestamptz, finished_at timestamptz, next_attempt_at timestamptz, safe_error text, {T}",
)
table(
    "raw_objects",
    "ingestion",
    "Original payload in object storage, hash and request identity",
    f"id {U}, run_id uuid NOT NULL REFERENCES ingest_runs(id), request_key text NOT NULL, content_hash text NOT NULL, object_uri text NOT NULL, media_type text NOT NULL, bytes bigint NOT NULL CHECK(bytes>=0), fetched_at timestamptz NOT NULL, UNIQUE(run_id,request_key)",
)
table(
    "quality_issues",
    "ingestion",
    "Quarantine incorrect timestamps, units and conflicting duplicate values",
    f"id {U}, raw_object_id uuid REFERENCES raw_objects(id), dataset_id uuid REFERENCES datasets(id), entity_type text NOT NULL, natural_key jsonb NOT NULL, code text NOT NULL, details jsonb NOT NULL, resolved_at timestamptz, {T}",
)
# Canonical dimensions.
table(
    "regions",
    "reference",
    "Official versioned state/district/tehsil/village hierarchy; demo IDs separate",
    f"id {U}, {D}, parent_id uuid REFERENCES regions(id), level text NOT NULL CHECK(level IN ('state','ut','district','block','village')), code_system text NOT NULL, code text NOT NULL, name text NOT NULL, valid_from date NOT NULL, valid_to date, UNIQUE(dataset_id,code_system,code), CHECK(valid_to IS NULL OR valid_to>=valid_from)",
)
table(
    "locations",
    "reference",
    "Shared weather grid or public location anchor",
    f"id {U}, {D}, region_id uuid NOT NULL REFERENCES regions(id), location_key text NOT NULL, label text NOT NULL, latitude numeric(9,6) NOT NULL CHECK(latitude BETWEEN -90 AND 90), longitude numeric(9,6) NOT NULL CHECK(longitude BETWEEN -180 AND 180), resolution_m integer CHECK(resolution_m>0), UNIQUE(dataset_id,location_key)",
)
table(
    "crops",
    "reference",
    "Canonical crops with multilingual aliases",
    f"id {U}, code text NOT NULL UNIQUE, name text NOT NULL, names jsonb NOT NULL DEFAULT '{{}}', category text NOT NULL, perennial boolean NOT NULL DEFAULT false",
)
table(
    "crop_varieties",
    "reference",
    "Keep crop variety/grade distinct for market comparisons",
    f"id {U}, crop_id uuid NOT NULL REFERENCES crops(id), code text NOT NULL, name text NOT NULL, UNIQUE(crop_id,code), UNIQUE(id,crop_id)",
)
table(
    "units",
    "reference",
    "Explicit dimensions and conversion factors, never infer price units",
    "code text PRIMARY KEY, dimension text NOT NULL, symbol text NOT NULL, factor_to_base numeric(16,8), CHECK(factor_to_base IS NULL OR factor_to_base>0)",
)
table(
    "markets",
    "reference",
    "Real official markets or explicitly named demo markets",
    f"id {U}, {D}, region_id uuid NOT NULL REFERENCES regions(id), code_system text NOT NULL, external_code text NOT NULL, name text NOT NULL, latitude numeric(9,6), longitude numeric(9,6), UNIQUE(dataset_id,code_system,external_code)",
)
table(
    "market_series",
    "market",
    "One market/crop/variety/grade/unit series",
    f"id {U}, market_id uuid NOT NULL REFERENCES markets(id), crop_id uuid NOT NULL REFERENCES crops(id), variety_id uuid NOT NULL, grade text NOT NULL DEFAULT 'unspecified', unit_code text NOT NULL REFERENCES units(code), currency char(3) NOT NULL DEFAULT 'INR', FOREIGN KEY(variety_id,crop_id) REFERENCES crop_varieties(id,crop_id), UNIQUE(market_id,crop_id,variety_id,grade,unit_code,currency)",
)
# Farmer-owned data, composite keys bind private parent and child to same owner.
table(
    "farmers",
    "farm",
    "Consented account and synthetic profile; no Aadhaar or stored plaintext OTP",
    f"id {U}, {D}, profile_key text NOT NULL UNIQUE, auth_subject text UNIQUE, display_name text NOT NULL, region_id uuid NOT NULL REFERENCES regions(id), preferred_language text NOT NULL, age_band text, farming_experience_years integer CHECK(farming_experience_years BETWEEN 0 AND 80), profile_attributes jsonb NOT NULL DEFAULT '{{}}', contact_email text, contact_phone text, contact_verified_at timestamptz, status text NOT NULL DEFAULT 'active', {T}",
    True,
)
table(
    "consents",
    "farm",
    "Purpose-scoped permissions, expiry and revocation",
    f"id {U}, {F}, purpose text NOT NULL, granted_at timestamptz NOT NULL, expires_at timestamptz, revoked_at timestamptz, evidence_hash text NOT NULL",
    True,
)
table(
    "farms",
    "farm",
    "One farmer can own/manage several farms",
    f"id {U}, {F}, farm_key text NOT NULL UNIQUE, name text NOT NULL, region_id uuid NOT NULL REFERENCES regions(id), location_id uuid REFERENCES locations(id), ownership_type text NOT NULL, irrigation_method text NOT NULL, water_source text, UNIQUE(id,farmer_id)",
    True,
)
table(
    "plots",
    "farm",
    "Real user-drawn field geometry or an explicitly synthetic example",
    f"id {U}, {F}, farm_id uuid NOT NULL, plot_key text NOT NULL UNIQUE, area_ha numeric(10,4) NOT NULL CHECK(area_ha>0), latitude numeric(9,6) NOT NULL CHECK(latitude BETWEEN -90 AND 90), longitude numeric(9,6) NOT NULL CHECK(longitude BETWEEN -180 AND 180), boundary_geojson jsonb, soil_texture text, UNIQUE(id,farmer_id), FOREIGN KEY(farm_id,farmer_id) REFERENCES farms(id,farmer_id), CHECK(boundary_geojson IS NULL OR jsonb_typeof(boundary_geojson)='object')",
    True,
)
table(
    "crop_cycles",
    "farm",
    "Crop, sowing date, harvest window and season per plot",
    f"id {U}, {F}, plot_id uuid NOT NULL, crop_id uuid NOT NULL REFERENCES crops(id), variety_id uuid, season text NOT NULL, sowing_date date NOT NULL, expected_harvest_date date, actual_harvest_date date, status text NOT NULL CHECK(status IN ('planned','growing','harvested','failed')), expected_yield_t_ha numeric(10,3), actual_yield_t_ha numeric(10,3), UNIQUE(id,farmer_id), FOREIGN KEY(plot_id,farmer_id) REFERENCES plots(id,farmer_id), FOREIGN KEY(variety_id,crop_id) REFERENCES crop_varieties(id,crop_id), CHECK(expected_harvest_date IS NULL OR expected_harvest_date>=sowing_date)",
    True,
)
table(
    "farm_operations",
    "farm",
    "Irrigation/sowing/fertilizing/scouting actual events, not inferred execution",
    f"id {U}, {F}, cycle_id uuid NOT NULL, operation text NOT NULL, occurred_at timestamptz NOT NULL, quantity numeric(14,4), unit_code text REFERENCES units(code), notes text, evidence_uri text, FOREIGN KEY(cycle_id,farmer_id) REFERENCES crop_cycles(id,farmer_id)",
    True,
)
table(
    "resources",
    "sharing",
    "Farmer inventory of equipment, produce or supplies",
    f"id {U}, {F}, category text NOT NULL, name text NOT NULL, quantity numeric(14,4) NOT NULL CHECK(quantity>=0), unit_code text NOT NULL REFERENCES units(code), UNIQUE(id,farmer_id)",
    True,
)
table(
    "resource_listings",
    "sharing",
    "Opt-in public/neighbor sharing availability, prices and date window",
    f"id {U}, {F}, resource_id uuid NOT NULL, visibility text NOT NULL CHECK(visibility IN ('private','neighbors','public')), available_from date NOT NULL, available_to date NOT NULL, asking_price_inr numeric(14,2) CHECK(asking_price_inr>=0), status text NOT NULL, FOREIGN KEY(resource_id,farmer_id) REFERENCES resources(id,farmer_id), CHECK(available_to>=available_from)",
    True,
)
table(
    "resource_matches",
    "sharing",
    "Proposals between consenting participants; no invented agreements",
    f"id {U}, listing_id uuid NOT NULL REFERENCES resource_listings(id), requester_id uuid NOT NULL REFERENCES farmers(id), proposed_at timestamptz NOT NULL, status text NOT NULL, terms jsonb NOT NULL DEFAULT '{{}}', requester_accepted_at timestamptz, owner_accepted_at timestamptz",
)
table(
    "expenses",
    "farm",
    "Exact decimal INR expenses, quantities and idempotency",
    f"id {U}, {F}, cycle_id uuid, description text NOT NULL, spent_on date NOT NULL, amount_inr numeric(14,2) NOT NULL CHECK(amount_inr>=0), category text NOT NULL, execution_key text NOT NULL, UNIQUE(farmer_id,execution_key), FOREIGN KEY(cycle_id,farmer_id) REFERENCES crop_cycles(id,farmer_id)",
    True,
)
table(
    "tasks",
    "farm",
    "Owned calendar plan with recoverable deletion",
    f"id {U}, {F}, cycle_id uuid, title text NOT NULL, due_at timestamptz NOT NULL, timezone text NOT NULL DEFAULT 'Asia/Kolkata', status text NOT NULL CHECK(status IN ('open','done','cancelled')), notes text, deleted_at timestamptz, execution_key text NOT NULL, UNIQUE(farmer_id,execution_key), UNIQUE(id,farmer_id), FOREIGN KEY(cycle_id,farmer_id) REFERENCES crop_cycles(id,farmer_id)",
    True,
)
table(
    "task_events",
    "farm",
    "Audit events and before/after edits for undo",
    f"id {U}, {F}, task_id uuid NOT NULL, event_type text NOT NULL, before_state jsonb, after_state jsonb NOT NULL, actor text NOT NULL, {T}, FOREIGN KEY(task_id,farmer_id) REFERENCES tasks(id,farmer_id)",
    True,
)
# Sensor and external environmental data.
table(
    "stations",
    "telemetry",
    "Real device or simulated station with explicit source identity",
    f"id {U}, {F}, plot_id uuid NOT NULL, {D}, station_key text NOT NULL UNIQUE, device_type text NOT NULL, calibration jsonb NOT NULL DEFAULT '{{}}', installed_at timestamptz NOT NULL, last_received_at timestamptz, UNIQUE(id,farmer_id), FOREIGN KEY(plot_id,farmer_id) REFERENCES plots(id,farmer_id)",
    True,
)
table(
    "station_sensors",
    "telemetry",
    "Metric/unit/depth/calibration per station",
    f"id {U}, {F}, station_id uuid NOT NULL, metric text NOT NULL, unit_code text NOT NULL REFERENCES units(code), depth_cm numeric(6,2), enabled boolean NOT NULL DEFAULT true, FOREIGN KEY(station_id,farmer_id) REFERENCES stations(id,farmer_id), UNIQUE(station_id,metric,depth_cm)",
    True,
)
table(
    "packet_receipts",
    "telemetry",
    "Global boot/sequence replay protection across monthly partitions",
    f"{D}, {F}, station_id uuid NOT NULL, boot_id uuid NOT NULL, sequence bigint NOT NULL, observed_at timestamptz NOT NULL, PRIMARY KEY(dataset_id,station_id,boot_id,sequence), UNIQUE(dataset_id,station_id,boot_id,sequence,observed_at), FOREIGN KEY(station_id,farmer_id) REFERENCES stations(id,farmer_id)",
    True,
)
table(
    "sensor_packets",
    "telemetry",
    "Idempotent packet with event/received time and valid readings",
    f"{D}, {F}, station_id uuid NOT NULL, observed_at timestamptz NOT NULL, received_at timestamptz NOT NULL, boot_id uuid NOT NULL, sequence bigint NOT NULL CHECK(sequence>=0), temperature_c numeric(6,2) CHECK(temperature_c BETWEEN -80 AND 70), humidity_pct numeric(6,2) CHECK(humidity_pct BETWEEN 0 AND 100), pressure_hpa numeric(7,2) CHECK(pressure_hpa BETWEEN 500 AND 1200), wind_kmh numeric(7,2) CHECK(wind_kmh BETWEEN 0 AND 400), wind_direction_degrees numeric(6,2) CHECK(wind_direction_degrees>=0 AND wind_direction_degrees<360), rainfall_increment_mm numeric(8,3) CHECK(rainfall_increment_mm>=0), soil_temperature_c numeric(6,2), soil_moisture_pct numeric(6,2) CHECK(soil_moisture_pct BETWEEN 0 AND 100), pm25_ug_m3 numeric(10,3), pm10_ug_m3 numeric(10,3), uv_index numeric(6,3), lux numeric(12,2), battery_v numeric(7,3), solar_v numeric(7,3), quality_flags jsonb NOT NULL DEFAULT '[]', PRIMARY KEY(dataset_id,station_id,observed_at), FOREIGN KEY(dataset_id,station_id,boot_id,sequence,observed_at) REFERENCES packet_receipts(dataset_id,station_id,boot_id,sequence,observed_at), FOREIGN KEY(station_id,farmer_id) REFERENCES stations(id,farmer_id), CHECK(received_at>=observed_at)",
    True,
    "PARTITION BY RANGE(observed_at)",
)
table(
    "sensor_daily",
    "telemetry",
    "UTC daily aggregates with counts/completeness",
    f"{D}, {F}, station_id uuid NOT NULL, day date NOT NULL, sample_count integer NOT NULL CHECK(sample_count>=0), completeness numeric(5,4) NOT NULL CHECK(completeness BETWEEN 0 AND 1), temperature_min_c numeric(6,2), temperature_max_c numeric(6,2), rainfall_mm numeric(9,3), soil_moisture_mean_pct numeric(6,2), PRIMARY KEY(dataset_id,station_id,day), FOREIGN KEY(station_id,farmer_id) REFERENCES stations(id,farmer_id)",
    True,
)
table(
    "weather_series",
    "environment",
    "Shared provider/grid/model series; never pretend to be on-farm hardware",
    f"id {U}, provider_id uuid NOT NULL REFERENCES providers(id), location_id uuid NOT NULL REFERENCES locations(id), model_name text NOT NULL, resolution_m integer NOT NULL CHECK(resolution_m>0), UNIQUE(provider_id,location_id,model_name)",
)
table(
    "weather_daily",
    "environment",
    "Historical observations, reanalysis or simulated history",
    f"{D}, series_id uuid NOT NULL REFERENCES weather_series(id), day date NOT NULL, kind text NOT NULL CHECK(kind IN ('observed','reanalysis','synthetic')), temperature_min_c numeric(6,2), temperature_max_c numeric(6,2), rainfall_mm numeric(9,3) CHECK(rainfall_mm>=0), humidity_mean_pct numeric(6,2) CHECK(humidity_mean_pct BETWEEN 0 AND 100), et0_mm numeric(8,3) CHECK(et0_mm>=0), PRIMARY KEY(dataset_id,series_id,day), CHECK(temperature_max_c>=temperature_min_c)",
)
table(
    "weather_forecasts",
    "environment",
    "Issued short-range forecasts or explicitly labeled long-range scenarios",
    f"{D}, series_id uuid NOT NULL REFERENCES weather_series(id), issued_at timestamptz NOT NULL, valid_on date NOT NULL, kind text NOT NULL CHECK(kind IN ('forecast','scenario')), temperature_min_c numeric(6,2), temperature_max_c numeric(6,2), rainfall_mm numeric(9,3) CHECK(rainfall_mm>=0), rainfall_probability numeric(5,4) CHECK(rainfall_probability BETWEEN 0 AND 1), method text NOT NULL, PRIMARY KEY(dataset_id,series_id,issued_at,valid_on), CHECK(valid_on>= (issued_at AT TIME ZONE 'Asia/Kolkata')::date), CHECK(temperature_max_c>=temperature_min_c)",
)
table(
    "soil_samples",
    "environment",
    "Consent-scoped real lab reports or demo samples",
    f"id {U}, {F}, plot_id uuid NOT NULL, {D}, sampled_on date NOT NULL, sample_type text NOT NULL CHECK(sample_type IN ('lab','farmer_report','synthetic')), lab_name text, report_uri text, UNIQUE(id,farmer_id), FOREIGN KEY(plot_id,farmer_id) REFERENCES plots(id,farmer_id)",
    True,
)
table(
    "soil_indicators",
    "environment",
    "Property/unit/depth/uncertainty, with predicted values distinct from lab values",
    f"id {U}, {F}, plot_id uuid NOT NULL, sample_id uuid, {D}, property text NOT NULL, depth_top_cm numeric(6,2) NOT NULL CHECK(depth_top_cm>=0), depth_bottom_cm numeric(6,2) NOT NULL, unit_code text NOT NULL REFERENCES units(code), mean_value numeric(14,4) NOT NULL, lower_value numeric(14,4), upper_value numeric(14,4), evidence_type text NOT NULL CHECK(evidence_type IN ('lab','grid_prediction','synthetic','farmer_report')), FOREIGN KEY(plot_id,farmer_id) REFERENCES plots(id,farmer_id), FOREIGN KEY(sample_id,farmer_id) REFERENCES soil_samples(id,farmer_id), CHECK(depth_bottom_cm>depth_top_cm), CHECK(lower_value IS NULL OR lower_value<=mean_value), CHECK(upper_value IS NULL OR upper_value>=mean_value)",
    True,
)
table(
    "satellite_assets",
    "environment",
    "STAC scene metadata and immutable external asset reference",
    f"id {U}, {D}, provider_item_id text NOT NULL, acquired_at timestamptz NOT NULL, collection text NOT NULL, cloud_pct numeric(5,2) CHECK(cloud_pct BETWEEN 0 AND 100), asset_uri text NOT NULL, footprint_geojson jsonb, UNIQUE(dataset_id,collection,provider_item_id)",
)
table(
    "plot_indices",
    "environment",
    "Cloud-masked vegetation indicators with valid pixel coverage",
    f"{D}, {F}, plot_id uuid NOT NULL, asset_id uuid REFERENCES satellite_assets(id), day date NOT NULL, index_name text NOT NULL, value numeric(8,5) NOT NULL, valid_pixel_fraction numeric(5,4) NOT NULL CHECK(valid_pixel_fraction BETWEEN 0 AND 1), method_version text NOT NULL, PRIMARY KEY(dataset_id,plot_id,day,index_name), FOREIGN KEY(plot_id,farmer_id) REFERENCES plots(id,farmer_id)",
    True,
)
# Prices: future values physically separate.
table(
    "price_observations",
    "market",
    "Daily market observations; synthetic history only in the demo DB",
    f"{D}, series_id uuid NOT NULL REFERENCES market_series(id), observed_on date NOT NULL, min_price numeric(14,2) NOT NULL, modal_price numeric(14,2) NOT NULL, max_price numeric(14,2) NOT NULL, arrivals_quantity numeric(14,3), arrivals_unit text REFERENCES units(code), fetched_at timestamptz NOT NULL, revision integer NOT NULL DEFAULT 1 CHECK(revision>0), PRIMARY KEY(dataset_id,series_id,observed_on), CHECK(min_price>=0 AND min_price<=modal_price AND modal_price<=max_price)",
    False,
    "PARTITION BY RANGE(observed_on)",
)
table(
    "model_versions",
    "market",
    "Training cutoff, backtest evidence and scenario-only markers",
    f"id {U}, name text NOT NULL, version text NOT NULL, purpose text NOT NULL, trained_until date, validation jsonb NOT NULL, artifact_uri text, status text NOT NULL CHECK(status IN ('scenario_only','validated','retired')), UNIQUE(name,version)",
)
table(
    "forecast_runs",
    "market",
    "One issuance with training cutoff and horizon",
    f"id {U}, {D}, model_id uuid NOT NULL REFERENCES model_versions(id), issued_at timestamptz NOT NULL, training_cutoff date NOT NULL, horizon_days integer NOT NULL CHECK(horizon_days BETWEEN 1 AND 365), kind text NOT NULL CHECK(kind IN ('forecast','scenario')), UNIQUE(id,kind), CHECK(training_cutoff<=(issued_at AT TIME ZONE 'Asia/Kolkata')::date)",
)
table(
    "price_projections",
    "market",
    "Future scenarios or backtested forecasts; never observed prices",
    "run_id uuid NOT NULL, series_id uuid NOT NULL REFERENCES market_series(id), valid_on date NOT NULL, kind text NOT NULL CHECK(kind IN ('forecast','scenario')), lower_price numeric(14,2) NOT NULL, central_price numeric(14,2) NOT NULL, upper_price numeric(14,2) NOT NULL, interval_definition text NOT NULL, PRIMARY KEY(run_id,series_id,valid_on), FOREIGN KEY(run_id,kind) REFERENCES forecast_runs(id,kind), CHECK(lower_price>=0 AND lower_price<=central_price AND central_price<=upper_price)",
)
table(
    "msp_announcements",
    "market",
    "Official policy by crop/grade/marketing season with notification URL",
    f"id {U}, {D}, crop_id uuid NOT NULL REFERENCES crops(id), grade text NOT NULL, marketing_season text NOT NULL, announced_on date NOT NULL, effective_from date NOT NULL, amount_inr_quintal numeric(14,2) NOT NULL CHECK(amount_inr_quintal>0), official_url text NOT NULL, UNIQUE(dataset_id,crop_id,grade,marketing_season)",
)
# Evidence-backed agricultural knowledge.
table(
    "documents",
    "knowledge",
    "Versioned official source document, language, license and review date",
    f"id {U}, {D}, source_url text NOT NULL, title text NOT NULL, language text NOT NULL, checksum text NOT NULL, published_on date, retrieved_at timestamptz NOT NULL, review_status text NOT NULL CHECK(review_status IN ('needs_review','reviewed','retired')), object_uri text, UNIQUE(dataset_id,checksum)",
)
table(
    "document_chunks",
    "knowledge",
    "Citable document sections; PostgreSQL text search before optional embeddings",
    f"id {U}, document_id uuid NOT NULL REFERENCES documents(id), ordinal integer NOT NULL, page_number integer, section_title text, content text NOT NULL, search_vector tsvector GENERATED ALWAYS AS (to_tsvector('simple',coalesce(section_title,'')||' '||content)) STORED, UNIQUE(document_id,ordinal)",
)
table(
    "crop_guides",
    "knowledge",
    "Region/season/crop stage guidance and validated assumptions",
    f"id {U}, document_id uuid NOT NULL REFERENCES documents(id), crop_id uuid NOT NULL REFERENCES crops(id), region_id uuid REFERENCES regions(id), season text NOT NULL, growth_stage text NOT NULL, guidance jsonb NOT NULL, verified_at timestamptz",
)
table(
    "diseases",
    "knowledge",
    "Reference symptoms and expert-reviewed support, not fabricated dosage",
    f"id {U}, code text NOT NULL UNIQUE, name text NOT NULL, crop_id uuid NOT NULL REFERENCES crops(id), reference_document_id uuid REFERENCES documents(id), symptoms jsonb NOT NULL, expert_reviewed_at timestamptz",
)
table(
    "disease_cases",
    "knowledge",
    "Real submitted image and uncertain model assessment; no invented ground truth",
    f"id {U}, {F}, cycle_id uuid NOT NULL, image_uri text NOT NULL, image_hash text NOT NULL, captured_at timestamptz, assessment jsonb, model_version text, clinician_label text, reviewed_by text, status text NOT NULL, {T}, FOREIGN KEY(cycle_id,farmer_id) REFERENCES crop_cycles(id,farmer_id)",
    True,
)
table(
    "scheme_versions",
    "knowledge",
    "Versioned real scheme requirements and official application link",
    f"id {U}, document_id uuid NOT NULL REFERENCES documents(id), scheme_code text NOT NULL, version text NOT NULL, name text NOT NULL, region_id uuid REFERENCES regions(id), requirements jsonb NOT NULL, benefits jsonb NOT NULL, application_url text NOT NULL, verified_at timestamptz, valid_from date, valid_to date, UNIQUE(scheme_code,version)",
)
table(
    "scheme_checks",
    "knowledge",
    "Explained recommendation, missing answers and reviewed application checklist",
    f"id {U}, {F}, scheme_version_id uuid NOT NULL REFERENCES scheme_versions(id), result text NOT NULL CHECK(result IN ('potential_match','missing_information','not_matched')), reasons jsonb NOT NULL, checked_at timestamptz NOT NULL, official_decision_reference text",
    True,
)
table(
    "regional_statistics",
    "knowledge",
    "Published aggregate crop area, production and yield; no farm-level inference",
    f"{D}, region_id uuid NOT NULL REFERENCES regions(id), crop_id uuid NOT NULL REFERENCES crops(id), year integer NOT NULL, season text NOT NULL, area_ha numeric(16,3), production_t numeric(16,3), yield_t_ha numeric(12,4), estimate_stage text NOT NULL, PRIMARY KEY(dataset_id,region_id,crop_id,year,season,estimate_stage)",
)
# Agent state, execution and evidence.
table(
    "conversations",
    "agent",
    "Owned conversation header and resumable summary cursor",
    f"id {U}, {F}, title text NOT NULL, summary text, summarized_through bigint NOT NULL DEFAULT 0, archived_at timestamptz, UNIQUE(id,farmer_id), {T}",
    True,
)
table(
    "messages",
    "agent",
    "Append-only complete public transcript, sequence and token accounting",
    f"id {U}, {F}, conversation_id uuid NOT NULL, sequence bigint NOT NULL, role text NOT NULL CHECK(role IN ('user','assistant','tool')), content jsonb NOT NULL, token_count integer CHECK(token_count>=0), {T}, UNIQUE(conversation_id,sequence), UNIQUE(id,farmer_id), FOREIGN KEY(conversation_id,farmer_id) REFERENCES conversations(id,farmer_id)",
    True,
)
table(
    "agent_runs",
    "agent",
    "Bounded run, lease owner, cancellation and terminal state",
    f"id {U}, {F}, conversation_id uuid NOT NULL, request_key text NOT NULL, status text NOT NULL, lease_expires_at timestamptz, started_at timestamptz, ended_at timestamptz, model_name text, UNIQUE(farmer_id,request_key), UNIQUE(id,farmer_id), FOREIGN KEY(conversation_id,farmer_id) REFERENCES conversations(id,farmer_id)",
    True,
)
table(
    "tool_calls",
    "agent",
    "Validated arguments, result and idempotent execution identity",
    f"id {U}, {F}, run_id uuid NOT NULL, call_key text NOT NULL, tool_name text NOT NULL, arguments jsonb NOT NULL, result jsonb, status text NOT NULL, started_at timestamptz, ended_at timestamptz, UNIQUE(run_id,call_key), UNIQUE(id,farmer_id), FOREIGN KEY(run_id,farmer_id) REFERENCES agent_runs(id,farmer_id)",
    True,
)
table(
    "approvals",
    "agent",
    "Exact argument hash and explicit decision before a write",
    f"id {U}, {F}, tool_call_id uuid NOT NULL, arguments_hash text NOT NULL, decision text CHECK(decision IN ('approved','rejected')), decided_at timestamptz, expires_at timestamptz NOT NULL, UNIQUE(tool_call_id), FOREIGN KEY(tool_call_id,farmer_id) REFERENCES tool_calls(id,farmer_id)",
    True,
)
table(
    "artifacts",
    "agent",
    "Owned file metadata, safe excerpt, hash and object storage reference",
    f"id {U}, {F}, run_id uuid, title text NOT NULL, format text NOT NULL CHECK(format IN ('docx','pdf','xlsx','csv','pptx')), object_uri text NOT NULL, bytes bigint NOT NULL CHECK(bytes>=0), checksum text NOT NULL, preview jsonb NOT NULL, {T}, FOREIGN KEY(run_id,farmer_id) REFERENCES agent_runs(id,farmer_id)",
    True,
)
table(
    "memories",
    "agent",
    "Correction-aware durable farmer facts with evidence, expiry and text search",
    f"id {U}, {F}, fact_key text NOT NULL, value jsonb NOT NULL, evidence_message_id uuid, confidence numeric(5,4) CHECK(confidence BETWEEN 0 AND 1), valid_from timestamptz NOT NULL, valid_to timestamptz, supersedes_id uuid, search_text text NOT NULL, search_vector tsvector GENERATED ALWAYS AS (to_tsvector('simple',search_text)) STORED, UNIQUE(id,farmer_id), FOREIGN KEY(evidence_message_id,farmer_id) REFERENCES messages(id,farmer_id), FOREIGN KEY(supersedes_id,farmer_id) REFERENCES memories(id,farmer_id), CHECK(valid_to IS NULL OR valid_to>valid_from)",
    True,
)
table(
    "retrieval_citations",
    "agent",
    "Answer evidence references with exact excerpts and source versions",
    f"id {U}, {F}, run_id uuid NOT NULL, chunk_id uuid REFERENCES document_chunks(id), dataset_id uuid REFERENCES datasets(id), source_record_key jsonb, excerpt text NOT NULL, FOREIGN KEY(run_id,farmer_id) REFERENCES agent_runs(id,farmer_id)",
    True,
)
table(
    "notifications",
    "agent",
    "Transactional outbox; demo delivery disabled, never imply an actual send",
    f"id {U}, {F}, task_id uuid, channel text NOT NULL CHECK(channel IN ('in_app','sms','whatsapp','email')), delivery_allowed boolean NOT NULL DEFAULT false, scheduled_at timestamptz NOT NULL, status text NOT NULL, payload jsonb NOT NULL, dedupe_key text NOT NULL, attempts integer NOT NULL DEFAULT 0, UNIQUE(farmer_id,dedupe_key), FOREIGN KEY(task_id,farmer_id) REFERENCES tasks(id,farmer_id)",
    True,
)

extend(table, U, D, F, T)
for definition in TABLES:
    if definition["name"] == "station_sensors":
        definition["columns"] += (
            ", measurement_basis text NOT NULL DEFAULT 'unknown', calibration jsonb NOT NULL DEFAULT '{}'"
        )
    if definition["name"] == "tasks":
        definition["columns"] += (
            ", row_version bigint NOT NULL DEFAULT 1 CHECK(row_version>0)"
        )
    if definition["name"] == "weather_series":
        definition["columns"] += (
            ", max_forecast_lead_days integer NOT NULL DEFAULT 15 CHECK(max_forecast_lead_days BETWEEN 0 AND 45)"
        )
    if definition["name"] == "soil_samples":
        definition["columns"] += ", report_metadata jsonb NOT NULL DEFAULT '{}'"
    if definition["name"] == "soil_indicators":
        definition["columns"] += ", reported_basis text NOT NULL DEFAULT 'unspecified'"
    if definition["name"] == "tool_calls":
        definition["columns"] += ", tool_version_id uuid"


header = """-- SkyView v3: fresh databases only. Never apply to the existing farm database.
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
"""
sql = header + "".join(
    f"\n-- {t['group']}: {t['purpose']}\nCREATE TABLE {t['name']} (\n {t['columns']}\n) {t['tail']};\n"
    for t in TABLES
)
# Read-heavy composite indexes reflect actual endpoints; avoid indexing every numeric metric.
indexes = [
    (
        "idx_jobs_due",
        "ingest_runs",
        "(next_attempt_at) WHERE state IN ('queued','failed')",
    ),
    (
        "idx_quality_dataset",
        "quality_issues",
        "(dataset_id,created_at DESC) WHERE resolved_at IS NULL",
    ),
    ("idx_regions_parent", "regions", "(parent_id,level)"),
    ("idx_locations_region", "locations", "(region_id)"),
    ("idx_markets_region", "markets", "(region_id)"),
    ("idx_series_crop", "market_series", "(crop_id,market_id,unit_code)"),
    (
        "idx_tasks_open",
        "tasks",
        "(farmer_id,due_at) WHERE status='open' AND deleted_at IS NULL",
    ),
    (
        "idx_expenses_date",
        "expenses",
        "(farmer_id,spent_on DESC) INCLUDE(amount_inr,category)",
    ),
    ("idx_packets_latest", "sensor_packets", "(farmer_id,station_id,observed_at DESC)"),
    ("idx_packets_time_brin", "sensor_packets", "USING brin(observed_at)"),
    (
        "idx_prices_latest",
        "price_observations",
        "(series_id,observed_on DESC) INCLUDE(modal_price,min_price,max_price)",
    ),
    ("idx_prices_time_brin", "price_observations", "USING brin(observed_on)"),
    ("idx_projection_series", "price_projections", "(series_id,valid_on,run_id)"),
    ("idx_projection_scenario_latest", "price_projections", "(series_id,valid_on DESC) WHERE kind='scenario'"),
    ("idx_weather_latest", "weather_daily", "(series_id,day DESC)"),
    (
        "idx_weather_forecast",
        "weather_forecasts",
        "(series_id,issued_at DESC,valid_on)",
    ),
    ("idx_indices_plot", "plot_indices", "(farmer_id,plot_id,day DESC)"),
    ("idx_chunks_search", "document_chunks", "USING gin(search_vector)"),
    ("idx_memory_search", "memories", "USING gin(search_vector)"),
    ("idx_memory_current", "memories", "(farmer_id,fact_key) WHERE valid_to IS NULL"),
    ("idx_artifacts_owner", "artifacts", "(farmer_id,created_at DESC)"),
    ("idx_messages_owner", "messages", "(farmer_id,conversation_id,sequence)"),
    ("idx_scheme_documents", "scheme_versions", "(region_id,scheme_code)"),
    (
        "idx_notification_due",
        "notifications",
        "(scheduled_at) WHERE status='queued' AND delivery_allowed",
    ),
]
indexes.extend(INDEXES)
for name, t, expression in indexes:
    uniqueness = (
        "UNIQUE " if name in ("idx_memory_current", "idx_mapping_current") else ""
    )
    sql += f"CREATE {uniqueness}INDEX {name} ON {t} {expression};\n"
# Ensure all farmer-owned access paths and FK filters have an ownership index.
for t in TABLES:
    if t["private"] and t["name"] != "farmers":
        sql += f"CREATE INDEX idx_{t['name']}_farmer ON {t['name']}(farmer_id);\n"

sql += """
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
"""
sql += """
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
"""

sql += SQL
# RLS: app must set trusted farmer ID inside its transaction, never from request query args.
for t in TABLES:
    if t["private"]:
        column = "id" if t["name"] == "farmers" else "farmer_id"
        sql += f"ALTER TABLE {t['name']} ENABLE ROW LEVEL SECURITY;\nCREATE POLICY farmer_scope ON {t['name']} USING ({column}=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK ({column}=nullif(current_setting('app.farmer_id',true),'')::uuid);\n"
sql += """ALTER TABLE resource_matches ENABLE ROW LEVEL SECURITY;
CREATE POLICY participant_scope ON resource_matches USING (
 requester_id=nullif(current_setting('app.farmer_id',true),'')::uuid OR
 EXISTS(SELECT 1 FROM sv3.resource_listings l WHERE l.id=listing_id AND l.farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid)
) WITH CHECK(requester_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
CREATE VIEW latest_prices WITH (security_invoker=true) AS
 SELECT DISTINCT ON (series_id) * FROM price_observations ORDER BY series_id,observed_on DESC,fetched_at DESC;
CREATE VIEW current_memories WITH (security_invoker=true) AS SELECT * FROM memories WHERE valid_to IS NULL;
COMMIT;
"""
(HERE / "sql/schema.sql").write_text(sql)
(HERE / "catalog/schema-catalog.json").write_text(
    json.dumps(
        {"base_tables": len(TABLES), "tables": TABLES, "explicit_indexes": indexes},
        indent=2,
    )
)
roles = """-- Run as database administrator once, after schema.sql. No LOGIN, passwords or PUBLIC grants.
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
"""
(HERE / "sql/roles.sql").write_text(roles)
print(
    f"Generated {len(TABLES)} base tables and {len(indexes)} explicit access-path indexes plus ownership indexes."
)
