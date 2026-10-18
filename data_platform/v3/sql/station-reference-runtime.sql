-- Public, read-only reference telemetry, restricted to the existing synthetic
-- dataset. Never returns another farmer's identifiers or observed sensor data.
CREATE OR REPLACE FUNCTION sv3.station_reference_packets(_limit integer DEFAULT 1)
RETURNS SETOF jsonb LANGUAGE sql STABLE SECURITY DEFINER
SET search_path=pg_catalog,sv3 AS $$
SELECT jsonb_build_object(
 'observed_at',p.observed_at,'received_at',p.received_at,'quality_flags',p.quality_flags,
 'temperature_c',p.temperature_c,'humidity_pct',p.humidity_pct,'pressure_hpa',p.pressure_hpa,
 'wind_kmh',p.wind_kmh,'wind_direction_degrees',p.wind_direction_degrees,
 'rainfall_increment_mm',p.rainfall_increment_mm,'soil_temperature_c',p.soil_temperature_c,
 'soil_moisture_pct',p.soil_moisture_pct,'pm25_ug_m3',p.pm25_ug_m3,'pm10_ug_m3',p.pm10_ug_m3,
 'uv_index',p.uv_index,'lux',p.lux,'battery_v',p.battery_v,'solar_v',p.solar_v,
 'origin','synthetic','lane',d.lane,'provider_name','Stored station reference',
 'source_url',d.source_url,'reference',true)
FROM sv3.sensor_packets p JOIN sv3.datasets d ON d.id=p.dataset_id
WHERE d.origin='synthetic' AND p.observed_at<=now()
 AND p.station_id=(SELECT s.id FROM sv3.stations s WHERE s.device_type='mock-v3' ORDER BY s.station_key LIMIT 1)
ORDER BY p.observed_at DESC LIMIT least(2000,greatest(1,_limit));
$$;
REVOKE ALL ON FUNCTION sv3.station_reference_packets(integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION sv3.station_reference_packets(integer) TO sv3_app;
