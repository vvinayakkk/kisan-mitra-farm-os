-- Station reads execute as the caller, so owner RLS still applies.
CREATE OR REPLACE FUNCTION sv3.pick_station(_key text, _first_station boolean)
RETURNS TABLE(id uuid, station_key text)
LANGUAGE sql STABLE SECURITY INVOKER SET search_path = pg_catalog, sv3 AS $$
  SELECT s.id,s.station_key::text FROM sv3.stations s
  WHERE _first_station OR s.station_key=_key OR s.id::text=_key
  ORDER BY (s.station_key=_key) DESC,(s.device_type<>'mock-v3') DESC,s.station_key
  LIMIT 1;
$$;

CREATE OR REPLACE FUNCTION sv3.latest_station_packet(_station uuid)
RETURNS jsonb
LANGUAGE sql STABLE SECURITY INVOKER SET search_path = pg_catalog, sv3 AS $$
  SELECT to_jsonb(result) FROM (
    SELECT p.*,d.origin,d.lane,d.as_of_date,d.source_url,v.name AS provider_name
    FROM sv3.sensor_packets p
    JOIN sv3.datasets d ON d.id=p.dataset_id
    JOIN sv3.providers v ON v.id=d.provider_id
    WHERE p.station_id=_station AND p.observed_at<=now()+interval '2 minutes'
    ORDER BY p.observed_at DESC LIMIT 1
  ) result;
$$;

CREATE OR REPLACE FUNCTION sv3.station_packet_history(
  _station uuid, _hours integer, _limit integer
) RETURNS SETOF jsonb
LANGUAGE sql STABLE SECURITY INVOKER SET search_path = pg_catalog, sv3 AS $$
  SELECT to_jsonb(result) FROM (
    SELECT p.observed_at AS timestamp,p.temperature_c AS temperature,p.humidity_pct AS humidity,p.pressure_hpa AS pressure,
      p.wind_kmh AS "windSpeed",p.wind_direction_degrees AS "windDirection",p.rainfall_increment_mm AS rainfall,
      p.soil_temperature_c AS "soilTemperature",p.soil_moisture_pct AS "soilMoisture",
      p.pm25_ug_m3 AS "airQualityPM25",p.pm10_ug_m3 AS "airQualityPM10",p.uv_index AS "uvIndex",
      p.lux AS "lightIntensity",p.battery_v AS "batteryVoltage",p.solar_v AS "solarVoltage",d.origin AS data_origin
    FROM sv3.sensor_packets p JOIN sv3.datasets d ON d.id=p.dataset_id
    WHERE p.station_id=_station AND p.observed_at<=now()
      AND p.observed_at>=now()-make_interval(hours=>least(8760,greatest(1,_hours)))
    ORDER BY p.observed_at DESC LIMIT least(2000,greatest(1,_limit))
  ) result;
$$;

REVOKE ALL ON FUNCTION sv3.pick_station(text,boolean) FROM PUBLIC;
REVOKE ALL ON FUNCTION sv3.latest_station_packet(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION sv3.station_packet_history(uuid,integer,integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION sv3.pick_station(text,boolean) TO sv3_app;
GRANT EXECUTE ON FUNCTION sv3.latest_station_packet(uuid) TO sv3_app;
GRANT EXECUTE ON FUNCTION sv3.station_packet_history(uuid,integer,integer) TO sv3_app;
