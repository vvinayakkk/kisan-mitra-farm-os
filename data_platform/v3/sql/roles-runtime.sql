DO $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='sv3_writer') THEN CREATE ROLE sv3_writer NOLOGIN NOSUPERUSER NOBYPASSRLS; END IF;
 IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='sv3_ingest') THEN CREATE ROLE sv3_ingest NOLOGIN NOSUPERUSER BYPASSRLS; END IF;
END $$;
GRANT USAGE ON SCHEMA sv3 TO sv3_writer,sv3_ingest;
GRANT sv3_app TO sv3_writer;

GRANT SELECT,INSERT,UPDATE,DELETE ON sv3.farmers,sv3.consents,sv3.farms,sv3.plots,sv3.crop_cycles,
 sv3.farm_operations,sv3.resources,sv3.resource_listings,sv3.resource_matches,sv3.expenses,
 sv3.tasks,sv3.task_events,sv3.soil_samples,sv3.soil_indicators,sv3.soil_calibrations,
 sv3.field_observations,sv3.harvest_batches,sv3.sale_records,sv3.conversations,sv3.messages,
 sv3.agent_runs,sv3.tool_calls,sv3.approvals,sv3.artifacts,sv3.attachments,sv3.memories,
 sv3.retrieval_citations,sv3.notifications,sv3.run_events,sv3.question_requests,
 sv3.question_answers,sv3.context_compactions,sv3.alert_events,sv3.disease_cases,
 sv3.device_commands,sv3.device_command_events TO sv3_writer;

GRANT SELECT,INSERT,UPDATE ON sv3.providers,sv3.datasets,sv3.ingest_runs,sv3.raw_objects,
 sv3.quality_issues,sv3.source_health,sv3.source_mappings,sv3.regions,sv3.locations,
 sv3.crops,sv3.crop_varieties,sv3.units,sv3.markets,sv3.market_series,
 sv3.weather_series,sv3.weather_daily,sv3.weather_forecasts,sv3.price_observations,
 sv3.msp_announcements,sv3.documents,sv3.document_chunks,sv3.crop_guides,
 sv3.diseases,sv3.scheme_versions,sv3.regional_statistics,sv3.satellite_assets,
 sv3.model_versions,sv3.forecast_runs,sv3.price_projections,
 sv3.stations,sv3.station_sensors,sv3.packet_receipts,sv3.sensor_packets,sv3.sensor_daily TO sv3_ingest;
GRANT SELECT ON sv3.farmers,sv3.farms,sv3.plots TO sv3_ingest;

ALTER FUNCTION sv3.ensure_month_partitions(text,date,date) SECURITY DEFINER;
ALTER FUNCTION sv3.ensure_month_partitions(text,date,date) SET search_path=sv3,pg_temp;
REVOKE ALL ON FUNCTION sv3.ensure_month_partitions(text,date,date) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION sv3.ensure_month_partitions(text,date,date) TO sv3_ingest;
