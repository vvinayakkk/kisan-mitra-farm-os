"""Review additions for farmer workflows and auditable, resumable execution."""


def extend(table, U, D, F, T):
    table(
        "source_mappings",
        "reference",
        "Reviewed external crop/variety/market/region identifiers, never fuzzy-merge silently",
        f"id {U}, provider_id uuid NOT NULL REFERENCES providers(id), entity_type text NOT NULL CHECK(entity_type IN ('crop','variety','market','region')), external_key text NOT NULL, crop_id uuid REFERENCES crops(id), variety_id uuid REFERENCES crop_varieties(id), market_id uuid REFERENCES markets(id), region_id uuid REFERENCES regions(id), valid_from date NOT NULL, valid_to date, reviewed_at timestamptz, CHECK(valid_to IS NULL OR valid_to>=valid_from), CHECK(num_nonnulls(crop_id,variety_id,market_id,region_id)=1), CHECK((entity_type='crop')=(crop_id IS NOT NULL)), CHECK((entity_type='variety')=(variety_id IS NOT NULL)), CHECK((entity_type='market')=(market_id IS NOT NULL)), CHECK((entity_type='region')=(region_id IS NOT NULL))",
    )
    table(
        "source_health",
        "ingestion",
        "Per-provider/scope freshness, outage, rate limiting and last-good state",
        "provider_id uuid NOT NULL REFERENCES providers(id), scope_key text NOT NULL, checked_at timestamptz NOT NULL, last_success_at timestamptz, source_valid_through date, status text NOT NULL CHECK(status IN ('healthy','stale','outage','rate_limited','unknown')), retry_after timestamptz, safe_error text, PRIMARY KEY(provider_id,scope_key)",
    )
    table(
        "measurement_definitions",
        "reference",
        "Soil property basis, accepted units, bounds and non-convertible nutrient forms",
        "code text PRIMARY KEY, name text NOT NULL, basis text NOT NULL, allowed_units jsonb NOT NULL CHECK(jsonb_typeof(allowed_units)='array'), minimum_value numeric, maximum_value numeric, interpretation text NOT NULL, CHECK(maximum_value IS NULL OR minimum_value IS NULL OR maximum_value>=minimum_value)",
    )
    table(
        "soil_calibrations",
        "environment",
        "Plot/depth field capacity and wilting point for explicit volumetric water balance",
        f"id {U}, {F}, plot_id uuid NOT NULL, {D}, measured_on date NOT NULL, depth_top_cm numeric NOT NULL CHECK(depth_top_cm>=0), depth_bottom_cm numeric NOT NULL, field_capacity_vwc_pct numeric NOT NULL CHECK(field_capacity_vwc_pct BETWEEN 0 AND 100), wilting_point_vwc_pct numeric NOT NULL CHECK(wilting_point_vwc_pct BETWEEN 0 AND 100), bulk_density_g_cm3 numeric CHECK(bulk_density_g_cm3>0 AND bulk_density_g_cm3<3), method text NOT NULL, evidence_type text NOT NULL CHECK(evidence_type IN ('lab','derived','synthetic')), FOREIGN KEY(plot_id,farmer_id) REFERENCES plots(id,farmer_id), CHECK(depth_bottom_cm>depth_top_cm), CHECK(field_capacity_vwc_pct>wilting_point_vwc_pct)",
        True,
    )
    table(
        "attachments",
        "agent",
        "Owned input image/report/audio metadata with quarantine and extraction status",
        f"id {U}, {F}, message_id uuid, object_uri text NOT NULL, original_name text NOT NULL, mime_type text NOT NULL, bytes bigint NOT NULL CHECK(bytes>0), checksum text NOT NULL, scan_status text NOT NULL CHECK(scan_status IN ('pending','clean','rejected')), extracted_text text, metadata jsonb NOT NULL DEFAULT '{{}}', UNIQUE(id,farmer_id), FOREIGN KEY(message_id,farmer_id) REFERENCES messages(id,farmer_id), {T}",
        True,
    )
    table(
        "field_observations",
        "farm",
        "Farmer reports of stage, symptoms, pests, moisture and uncertainty with optional photo",
        f"id {U}, {F}, cycle_id uuid NOT NULL, observed_at timestamptz NOT NULL, type text NOT NULL, observation jsonb NOT NULL CHECK(jsonb_typeof(observation)='object'), attachment_id uuid, origin text NOT NULL CHECK(origin IN ('user_reported','synthetic')), FOREIGN KEY(cycle_id,farmer_id) REFERENCES crop_cycles(id,farmer_id), FOREIGN KEY(attachment_id,farmer_id) REFERENCES attachments(id,farmer_id)",
        True,
    )
    table(
        "harvest_batches",
        "farm",
        "Actual harvest stock, moisture/grade evidence and storage; units never inferred",
        f"id {U}, {F}, cycle_id uuid NOT NULL, harvested_on date NOT NULL, quantity numeric(14,3) NOT NULL CHECK(quantity>0), unit_code text NOT NULL REFERENCES units(code), grade text NOT NULL, moisture_pct numeric CHECK(moisture_pct BETWEEN 0 AND 100), quality_evidence jsonb NOT NULL DEFAULT '{{}}', storage_notes text, execution_key text NOT NULL, UNIQUE(farmer_id,execution_key), UNIQUE(id,farmer_id), FOREIGN KEY(cycle_id,farmer_id) REFERENCES crop_cycles(id,farmer_id)",
        True,
    )
    table(
        "sale_records",
        "farm",
        "Recorded sale proceeds and selling costs, distinct from mandi quotes and payment claims",
        f"id {U}, {F}, batch_id uuid NOT NULL, sold_on date NOT NULL, quantity numeric(14,3) NOT NULL CHECK(quantity>0), unit_code text NOT NULL REFERENCES units(code), unit_price_inr numeric(14,2) NOT NULL CHECK(unit_price_inr>=0), selling_cost_inr numeric(14,2) NOT NULL CHECK(selling_cost_inr>=0), gross_inr numeric(18,2) GENERATED ALWAYS AS (round(quantity*unit_price_inr,2)) STORED, net_inr numeric(18,2) GENERATED ALWAYS AS (round(quantity*unit_price_inr-selling_cost_inr,2)) STORED, payment_status text NOT NULL CHECK(payment_status IN ('reported_paid','pending','unknown','demo')), receipt_uri text, execution_key text NOT NULL, UNIQUE(farmer_id,execution_key), FOREIGN KEY(batch_id,farmer_id) REFERENCES harvest_batches(id,farmer_id)",
        True,
    )
    table(
        "skill_versions",
        "agent",
        "Versioned skill descriptions, farmer purpose, workflow hash and allowed tools",
        f"id {U}, code text NOT NULL, version text NOT NULL, title text NOT NULL, farmer_description text NOT NULL, workflow text NOT NULL, workflow_hash text NOT NULL, allowed_tools jsonb NOT NULL, active boolean NOT NULL DEFAULT false, UNIQUE(code,version)",
    )
    table(
        "tool_versions",
        "agent",
        "Versioned tool argument/output schemas and side-effect policy",
        f"id {U}, code text NOT NULL, version text NOT NULL, title text NOT NULL, arguments_schema jsonb NOT NULL, output_schema jsonb NOT NULL, effect text NOT NULL CHECK(effect IN ('read','artifact','write','external','hardware')), requires_approval boolean NOT NULL, active boolean NOT NULL DEFAULT false, UNIQUE(code,version), CHECK(effect NOT IN ('write','external','hardware') OR requires_approval)",
    )
    table(
        "run_events",
        "agent",
        "Resumable public progress/tool/artifact/question timeline; no hidden chain-of-thought",
        f"id {U}, {F}, run_id uuid NOT NULL, sequence bigint NOT NULL CHECK(sequence>0), event_type text NOT NULL CHECK(event_type IN ('started','skill','tool_started','tool_result','question','approval','text_delta','artifact','completed','failed','cancelled')), payload jsonb NOT NULL, occurred_at timestamptz NOT NULL, UNIQUE(run_id,sequence), FOREIGN KEY(run_id,farmer_id) REFERENCES agent_runs(id,farmer_id)",
        True,
    )
    table(
        "question_requests",
        "agent",
        "Persisted structured farmer question and waiting state across reconnect/restart",
        f"id {U}, {F}, run_id uuid NOT NULL, tool_call_id uuid, prompt text NOT NULL, form_schema jsonb NOT NULL, status text NOT NULL CHECK(status IN ('waiting','answered','cancelled','expired')), expires_at timestamptz NOT NULL, UNIQUE(id,farmer_id), FOREIGN KEY(run_id,farmer_id) REFERENCES agent_runs(id,farmer_id), FOREIGN KEY(tool_call_id,farmer_id) REFERENCES tool_calls(id,farmer_id), {T}",
        True,
    )
    table(
        "question_answers",
        "agent",
        "Typed answer payload and revision identity; server validates against request form schema",
        f"id {U}, {F}, question_id uuid NOT NULL, answer_version integer NOT NULL CHECK(answer_version>0), answers jsonb NOT NULL CHECK(jsonb_typeof(answers)='object'), submitted_at timestamptz NOT NULL, execution_key text NOT NULL, UNIQUE(question_id,answer_version), UNIQUE(farmer_id,execution_key), FOREIGN KEY(question_id,farmer_id) REFERENCES question_requests(id,farmer_id)",
        True,
    )
    table(
        "context_compactions",
        "agent",
        "Versioned summary checkpoints, covered sequences, open questions and token budget audit",
        f"id {U}, {F}, conversation_id uuid NOT NULL, first_sequence bigint NOT NULL CHECK(first_sequence>0), last_sequence bigint NOT NULL, summary text NOT NULL, pending_work jsonb NOT NULL, tokens_before integer NOT NULL CHECK(tokens_before>=0), tokens_after integer NOT NULL CHECK(tokens_after>=0), method_version text NOT NULL, UNIQUE(conversation_id,last_sequence,method_version), FOREIGN KEY(conversation_id,farmer_id) REFERENCES conversations(id,farmer_id), CHECK(last_sequence>=first_sequence), {T}",
        True,
    )
    table(
        "alert_events",
        "farm",
        "Farmer-facing sourced/derived warning lifecycle with expiry and acknowledgment",
        f"id {U}, {F}, {D}, station_id uuid, source_key text NOT NULL, category text NOT NULL, severity text NOT NULL CHECK(severity IN ('info','watch','warning','critical')), message text NOT NULL, source_url text NOT NULL, issued_at timestamptz NOT NULL, expires_at timestamptz NOT NULL, acknowledged_at timestamptz, status text NOT NULL CHECK(status IN ('active','resolved','expired')), UNIQUE(farmer_id,dataset_id,source_key), FOREIGN KEY(station_id,farmer_id) REFERENCES stations(id,farmer_id), CHECK(expires_at>issued_at)",
        True,
    )
    table(
        "device_commands",
        "telemetry",
        "Approved bounded command intent: mock/live, exact approval link, expiry and execution identity",
        f"id {U}, {F}, station_id uuid NOT NULL, tool_call_id uuid NOT NULL, approval_id uuid NOT NULL REFERENCES approvals(id), command text NOT NULL, arguments_hash text NOT NULL, payload jsonb NOT NULL, mode text NOT NULL CHECK(mode IN ('demo','live')), status text NOT NULL CHECK(status IN ('queued','sent','acknowledged','failed','expired','cancelled')), expires_at timestamptz NOT NULL, execution_key text NOT NULL, UNIQUE(farmer_id,execution_key), UNIQUE(id,farmer_id), FOREIGN KEY(station_id,farmer_id) REFERENCES stations(id,farmer_id), FOREIGN KEY(tool_call_id,farmer_id) REFERENCES tool_calls(id,farmer_id), {T}",
        True,
    )
    table(
        "device_command_events",
        "telemetry",
        "Device acknowledgment/rejection/timeout audit; broker delivery is not execution proof",
        f"id {U}, {F}, command_id uuid NOT NULL, event_key text NOT NULL, event_type text NOT NULL CHECK(event_type IN ('sent','acknowledged','rejected','timeout','cancelled')), occurred_at timestamptz NOT NULL, device_response jsonb NOT NULL, UNIQUE(command_id,event_key), FOREIGN KEY(command_id,farmer_id) REFERENCES device_commands(id,farmer_id)",
        True,
    )


INDEXES = [
    (
        "idx_mapping_current",
        "source_mappings",
        "(provider_id,entity_type,external_key) WHERE valid_to IS NULL",
    ),
    (
        "idx_alert_active",
        "alert_events",
        "(farmer_id,expires_at) WHERE status='active'",
    ),
    ("idx_events_resume", "run_events", "(farmer_id,run_id,sequence)"),
    (
        "idx_question_waiting",
        "question_requests",
        "(farmer_id,expires_at) WHERE status='waiting'",
    ),
    ("idx_sales_day", "sale_records", "(farmer_id,sold_on DESC)"),
    (
        "idx_commands_due",
        "device_commands",
        "(expires_at) WHERE status IN ('queued','sent')",
    ),
]
SQL = r"""
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
"""
