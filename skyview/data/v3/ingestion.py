"""Bounded public-source adapters and durable v3 ingestion. No secret URLs in audit rows."""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import text


def uid(key):
    return str(uuid5(NAMESPACE_URL, "skyview-v3:" + key))


def execute(conn, sql, **params):
    return conn.execute(text(sql), params)


def finite(value, minimum=None, maximum=None):
    if value is None or value == -999:
        return None
    result = float(value)
    if (
        not math.isfinite(result)
        or (minimum is not None and result < minimum)
        or (maximum is not None and result > maximum)
    ):
        raise ValueError("measurement outside accepted range")
    return result


def parse_open_meteo(payload, forecast=False):
    """Require exact documented units; missing values remain missing."""
    daily, units = payload["daily"], payload["daily_units"]
    required = {
        "temperature_2m_min": "°C",
        "temperature_2m_max": "°C",
        "precipitation_sum": "mm",
    }
    for field, expected in required.items():
        if units.get(field) != expected:
            raise ValueError(f"unsupported {field} unit")
    times = daily["time"]
    for field in required:
        if len(daily[field]) != len(times):
            raise ValueError("misaligned daily arrays")
    rows = []
    for index, day in enumerate(times):
        row = {
            "day": date.fromisoformat(day),
            "temperature_min_c": finite(daily["temperature_2m_min"][index], -80, 70),
            "temperature_max_c": finite(daily["temperature_2m_max"][index], -80, 70),
            "rainfall_mm": finite(daily["precipitation_sum"][index], 0),
        }
        if (
            row["temperature_min_c"] is not None
            and row["temperature_max_c"] is not None
            and row["temperature_min_c"] > row["temperature_max_c"]
        ):
            raise ValueError("reversed temperature range")
        rows.append(row)
    return rows


def parse_power(payload):
    params = payload["properties"]["parameter"]
    unit_map = payload["parameters"]
    expected = {"T2M_MIN": "C", "T2M_MAX": "C", "PRECTOTCORR": "mm/day", "RH2M": "%"}
    if any(unit_map.get(k, {}).get("units") != unit for k, unit in expected.items()):
        raise ValueError("unsupported POWER units")
    rows = []
    for day in sorted(params["T2M_MIN"]):
        if any(day not in params[k] for k in expected):
            raise ValueError("misaligned POWER days")
        rows.append(
            {
                "day": datetime.strptime(day, "%Y%m%d").date(),
                "temperature_min_c": finite(params["T2M_MIN"][day], -80, 70),
                "temperature_max_c": finite(params["T2M_MAX"][day], -80, 70),
                "rainfall_mm": finite(params["PRECTOTCORR"][day], 0),
                "humidity_mean_pct": finite(params["RH2M"][day], 0, 100),
            }
        )
    return rows


def parse_mandi(payload, as_of):
    good, bad = [], []
    for item in payload.get("records", []):
        try:
            day = datetime.strptime(item["arrival_date"], "%d/%m/%Y").date()
            if day > as_of:
                raise ValueError("future observation")
            prices = [
                finite(item[k], 0) for k in ("min_price", "modal_price", "max_price")
            ]
            if (
                any(v is None for v in prices)
                or not prices[0] <= prices[1] <= prices[2]
            ):
                raise ValueError("invalid price band")
            # This adapter is only for the documented current-daily OGD resource (INR/quintal).
            unit = item.get("unit", "quintal").casefold()
            if unit not in ("quintal", "rs/quintal", "inr/quintal"):
                raise ValueError("unmapped price unit")
            good.append(
                {
                    "state": item["state"],
                    "district": item.get("district", ""),
                    "market": item["market"],
                    "commodity": item["commodity"],
                    "variety": item.get("variety") or "unspecified",
                    "grade": item.get("grade") or "unspecified",
                    "day": day,
                    "min_price": prices[0],
                    "modal_price": prices[1],
                    "max_price": prices[2],
                }
            )
        except (ValueError, KeyError, TypeError):
            bad.append(
                {
                    "code": "invalid_market_row",
                    "natural_key": {
                        k: item.get(k)
                        for k in ("state", "market", "commodity", "arrival_date")
                    },
                    "details": {"reason": "date, unit or price validation failed"},
                }
            )
    return good, bad


class Ingestor:
    """Caller supplies a restricted trusted ingestion connection, never a browser connection."""

    def __init__(self, conn, lane="demo", raw_dir=None):
        if lane not in ("demo", "live"):
            raise ValueError("invalid lane")
        self.conn, self.lane = conn, lane
        self.raw_dir = Path(
            raw_dir
            or os.getenv("V3_RAW_STORAGE_DIR")
            or os.getenv("V3_RAW_DIR", ".v3-data/raw")
        )

    def provider(self, code, url, method="documented_api"):
        identifier = uid("provider:" + code)
        execute(
            self.conn,
            """INSERT INTO sv3.providers(id,code,name,homepage,access_method,attribution,status)
          VALUES(:id,:code,:code,:url,:method,:code,'active') ON CONFLICT(code) DO UPDATE SET status='active'""",
            id=identifier,
            code=code,
            url=url,
            method=method,
        )
        return execute(
            self.conn, "SELECT id FROM sv3.providers WHERE code=:code", code=code
        ).scalar_one()

    def release(self, code, url, payload, origin, scope, now):
        if origin == "synthetic" and self.lane != "demo":
            raise ValueError("synthetic ingestion is demo-only")
        provider = self.provider(code, url)
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        digest = hashlib.sha256(encoded).hexdigest()
        self.raw_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        target = self.raw_dir / (digest + ".json")
        if not target.exists():
            temp = target.with_suffix("." + uuid4().hex + ".tmp")
            temp.write_bytes(encoded)
            temp.chmod(0o600)
            temp.replace(target)
        release_day = (
            now.astimezone(ZoneInfo("Asia/Kolkata")).date()
            if code == "ogd_agmarknet"
            else now.date()
        )
        release_key = f"{code}:{scope}:{release_day}:{digest}"
        dataset, run, raw = (
            uid(release_key),
            uid("run:" + release_key),
            uid("raw:" + release_key),
        )
        execute(
            self.conn,
            """INSERT INTO sv3.datasets(id,provider_id,release_key,lane,origin,as_of_date,generator_version,source_url,checksum)
          VALUES(:id,:p,:key,:lane,:origin,:day,:generator,:url,:hash) ON CONFLICT(release_key) DO NOTHING""",
            id=dataset,
            p=provider,
            key=release_key,
            lane=self.lane,
            origin=origin,
            day=release_day,
            generator="realtime-demo-v1" if origin == "synthetic" else None,
            url=url,
            hash=digest,
        )
        execute(
            self.conn,
            """INSERT INTO sv3.ingest_runs(id,provider_id,dataset_id,job_key,state,started_at,attempts)
          VALUES(:id,:p,:d,:key,'running',:now,1) ON CONFLICT(job_key) DO UPDATE SET state='running',attempts=sv3.ingest_runs.attempts+1""",
            id=run,
            p=provider,
            d=dataset,
            key=release_key,
            now=now,
        )
        execute(
            self.conn,
            """INSERT INTO sv3.raw_objects(id,run_id,request_key,content_hash,object_uri,media_type,bytes,fetched_at)
          VALUES(:id,:r,:scope,:hash,:uri,'application/json',:size,:now) ON CONFLICT(run_id,request_key) DO NOTHING""",
            id=raw,
            r=run,
            scope=scope,
            hash=digest,
            uri=target.resolve().as_uri(),
            size=len(encoded),
            now=now,
        )
        return provider, dataset, run, raw

    def finish(self, provider, run, scope, received, accepted, now, valid_through=None):
        execute(
            self.conn,
            "UPDATE sv3.ingest_runs SET state='done',rows_received=:received,rows_accepted=:accepted,finished_at=:now WHERE id=:id",
            id=run,
            received=received,
            accepted=accepted,
            now=now,
        )
        execute(
            self.conn,
            """INSERT INTO sv3.source_health(provider_id,scope_key,checked_at,last_success_at,source_valid_through,status)
          VALUES(:p,:scope,:now,:now,:valid,:status) ON CONFLICT(provider_id,scope_key) DO UPDATE SET checked_at=:now,last_success_at=:now,source_valid_through=:valid,status=:status,safe_error=NULL,retry_after=NULL""",
            p=provider,
            scope=scope,
            now=now,
            valid=valid_through,
            status="stale" if received and not accepted else "healthy",
        )

    def quarantine(self, raw, dataset, issues):
        for issue in issues:
            execute(
                self.conn,
                """INSERT INTO sv3.quality_issues(id,raw_object_id,dataset_id,entity_type,natural_key,code,details)
              VALUES(:id,:raw,:d,'provider_row',CAST(:key AS jsonb),:code,CAST(:details AS jsonb)) ON CONFLICT(id) DO NOTHING""",
                id=uid(str(raw) + json.dumps(issue, sort_keys=True)),
                raw=raw,
                d=dataset,
                key=json.dumps(issue["natural_key"]),
                code=issue["code"],
                details=json.dumps(issue["details"]),
            )

    def weather(self, code, location_id, payload, forecast=False, now=None):
        now = now or datetime.now(UTC)
        scope = str(location_id) + (":forecast" if forecast else ":history")
        location = (
            execute(
                self.conn,
                "SELECT latitude,longitude FROM sv3.locations WHERE id=:id",
                id=location_id,
            )
            .mappings()
            .one()
        )
        if (
            "latitude" in payload
            and "longitude" in payload
            and (
                abs(float(location["latitude"]) - float(payload["latitude"])) > 0.6
                or abs(float(location["longitude"]) - float(payload["longitude"])) > 0.6
            )
        ):
            raise ValueError(
                "weather payload does not match requested public location grid"
            )
        if code == "nasa_power" and payload.get("geometry", {}).get("coordinates"):
            coordinates = payload["geometry"]["coordinates"]
            if (
                abs(float(location["latitude"]) - float(coordinates[1])) > 0.6
                or abs(float(location["longitude"]) - float(coordinates[0])) > 0.6
            ):
                raise ValueError(
                    "POWER payload does not match requested public location grid"
                )
        rows = (
            parse_power(payload)
            if code == "nasa_power"
            else parse_open_meteo(payload, forecast)
        )
        if any(r["day"] > now.date() for r in rows) and not forecast:
            raise ValueError("future historical weather")
        origin = "modeled" if forecast else "reanalysis"
        url = (
            "https://power.larc.nasa.gov/api/temporal/daily/point"
            if code == "nasa_power"
            else (
                "https://api.open-meteo.com/v1/forecast"
                if forecast
                else "https://archive-api.open-meteo.com/v1/archive"
            )
        )
        provider, dataset, run, _raw = self.release(
            code, url, payload, origin, scope, now
        )
        model = (
            "forecast-default"
            if forecast
            else ("POWER-daily" if code == "nasa_power" else "ERA5")
        )
        series = uid(f"weather:{provider}:{location_id}:{model}")
        execute(
            self.conn,
            """INSERT INTO sv3.weather_series(id,provider_id,location_id,model_name,resolution_m,max_forecast_lead_days)
          VALUES(:id,:p,:loc,:model,:resolution,16) ON CONFLICT(provider_id,location_id,model_name) DO NOTHING""",
            id=series,
            p=provider,
            loc=location_id,
            model=model,
            resolution=50000
            if code == "nasa_power"
            else (25000 if not forecast else 9000),
        )
        series = execute(
            self.conn,
            "SELECT id FROM sv3.weather_series WHERE provider_id=:p AND location_id=:loc AND model_name=:model",
            p=provider,
            loc=location_id,
            model=model,
        ).scalar_one()
        accepted = 0
        # Stable issuance identity makes an identical snapshot retry idempotent.
        issued = execute(
            self.conn, "SELECT started_at FROM sv3.ingest_runs WHERE id=:id", id=run
        ).scalar_one()
        for row in rows:
            if forecast:
                if row["day"] < issued.astimezone(ZoneInfo("Asia/Kolkata")).date():
                    continue
                execute(
                    self.conn,
                    """INSERT INTO sv3.weather_forecasts(dataset_id,series_id,issued_at,valid_on,kind,temperature_min_c,temperature_max_c,rainfall_mm,method)
                  VALUES(:d,:s,:issued,:day,'forecast',:temperature_min_c,:temperature_max_c,:rainfall_mm,'provider numerical forecast')
                  ON CONFLICT(dataset_id,series_id,issued_at,valid_on) DO UPDATE SET temperature_min_c=EXCLUDED.temperature_min_c,temperature_max_c=EXCLUDED.temperature_max_c,rainfall_mm=EXCLUDED.rainfall_mm""",
                    d=dataset,
                    s=series,
                    issued=issued,
                    **{k: v for k, v in row.items() if k != "humidity_mean_pct"},
                )
            else:
                execute(
                    self.conn,
                    """INSERT INTO sv3.weather_daily(dataset_id,series_id,day,kind,temperature_min_c,temperature_max_c,rainfall_mm,humidity_mean_pct)
                  VALUES(:d,:s,:day,'reanalysis',:temperature_min_c,:temperature_max_c,:rainfall_mm,:humidity_mean_pct)
                  ON CONFLICT(dataset_id,series_id,day) DO NOTHING""",
                    d=dataset,
                    s=series,
                    humidity_mean_pct=row.get("humidity_mean_pct"),
                    **{k: v for k, v in row.items() if k != "humidity_mean_pct"},
                )
            accepted += 1
        self.finish(
            provider,
            run,
            scope,
            len(rows),
            accepted,
            now,
            max((r["day"] for r in rows), default=None),
        )
        return {
            "received": len(rows),
            "accepted": accepted,
            "dataset_id": str(dataset),
            "origin": origin,
        }

    def mandi(self, payload, now=None):
        now = now or datetime.now(UTC)
        rows, bad = parse_mandi(
            payload, now.astimezone(ZoneInfo("Asia/Kolkata")).date()
        )
        p, d, r, raw = self.release(
            "ogd_agmarknet",
            "https://data.gov.in/resource/current-daily-price-various-commodities-various-markets-mandi",
            payload,
            "observed",
            "daily",
            now,
        )
        accepted = 0
        for item in rows:
            region = execute(
                self.conn,
                "SELECT id FROM sv3.regions WHERE level IN ('state','ut') AND lower(name)=lower(:name) ORDER BY valid_from DESC LIMIT 1",
                name=item["state"],
            ).scalar()
            crop = execute(
                self.conn,
                "SELECT id FROM sv3.crops WHERE lower(name)=lower(:name) OR lower(code)=lower(:name)",
                name=item["commodity"],
            ).scalar()
            region_mapping = execute(
                self.conn,
                "SELECT region_id FROM sv3.source_mappings WHERE provider_id=:p AND entity_type='region' AND lower(external_key)=lower(:key) AND reviewed_at IS NOT NULL AND valid_from<=:day AND (valid_to IS NULL OR valid_to>=:day) ORDER BY reviewed_at DESC LIMIT 1",
                p=p,
                key=item["state"],
                day=item["day"],
            ).scalar()
            crop_mapping = execute(
                self.conn,
                "SELECT crop_id FROM sv3.source_mappings WHERE provider_id=:p AND entity_type='crop' AND lower(external_key)=lower(:key) AND reviewed_at IS NOT NULL AND valid_from<=:day AND (valid_to IS NULL OR valid_to>=:day) ORDER BY reviewed_at DESC LIMIT 1",
                p=p,
                key=item["commodity"],
                day=item["day"],
            ).scalar()
            region = region_mapping or region
            crop = crop_mapping or crop
            if not region or not crop:
                bad.append(
                    {
                        "code": "unmapped_market_reference",
                        "natural_key": {
                            k: item[k] for k in ("state", "commodity", "market")
                        },
                        "details": {"reason": "review canonical mapping before import"},
                    }
                )
                continue
            market = uid(
                "ogd-market:"
                + item["state"]
                + ":"
                + item["district"]
                + ":"
                + item["market"]
            )
            # Market identity must survive snapshot revisions, unlike the payload release.
            existing = execute(
                self.conn,
                "SELECT id FROM sv3.markets WHERE code_system='OGD-name' AND external_code=:code ORDER BY id LIMIT 1",
                code=market,
            ).scalar()
            if existing:
                market = existing
            else:
                execute(
                    self.conn,
                    "INSERT INTO sv3.markets(id,dataset_id,region_id,code_system,external_code,name) VALUES(:id,:d,:reg,'OGD-name',:code,:name)",
                    id=market,
                    d=d,
                    reg=region,
                    code=market,
                    name=item["market"],
                )
            variety = uid(f"variety:{crop}:{item['variety']}")
            execute(
                self.conn,
                "INSERT INTO sv3.crop_varieties(id,crop_id,code,name) VALUES(:id,:crop,:code,:name) ON CONFLICT(crop_id,code) DO NOTHING",
                id=variety,
                crop=crop,
                code=item["variety"],
                name=item["variety"],
            )
            variety = execute(
                self.conn,
                "SELECT id FROM sv3.crop_varieties WHERE crop_id=:crop AND code=:code",
                crop=crop,
                code=item["variety"],
            ).scalar_one()
            series = uid(f"market-series:{market}:{crop}:{variety}:{item['grade']}")
            execute(
                self.conn,
                """INSERT INTO sv3.market_series(id,market_id,crop_id,variety_id,grade,unit_code) VALUES(:id,:m,:c,:v,:g,'quintal')
              ON CONFLICT(market_id,crop_id,variety_id,grade,unit_code,currency) DO NOTHING""",
                id=series,
                m=market,
                c=crop,
                v=variety,
                g=item["grade"],
            )
            series = execute(
                self.conn,
                "SELECT id FROM sv3.market_series WHERE market_id=:m AND crop_id=:c AND variety_id=:v AND grade=:g AND unit_code='quintal' AND currency='INR'",
                m=market,
                c=crop,
                v=variety,
                g=item["grade"],
            ).scalar_one()
            execute(
                self.conn,
                """INSERT INTO sv3.price_observations(dataset_id,series_id,observed_on,min_price,modal_price,max_price,fetched_at)
              VALUES(:d,:s,:day,:min_price,:modal_price,:max_price,:now) ON CONFLICT(dataset_id,series_id,observed_on)
              DO UPDATE SET min_price=EXCLUDED.min_price,modal_price=EXCLUDED.modal_price,max_price=EXCLUDED.max_price,fetched_at=EXCLUDED.fetched_at""",
                d=d,
                s=series,
                now=now,
                **{
                    k: item[k] for k in ("day", "min_price", "modal_price", "max_price")
                },
            )
            accepted += 1
        self.quarantine(raw, d, bad)
        self.finish(
            p,
            r,
            "daily",
            len(payload.get("records", [])),
            accepted,
            now,
            max((x["day"] for x in rows), default=None),
        )
        return {"accepted": accepted, "quarantined": len(bad)}


def fetch_weather(
    latitude, longitude, forecast=True, start=None, end=None, client=None
):
    owned = client is None
    client = client or httpx.Client(timeout=30, follow_redirects=False)
    try:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "timezone": "UTC",
        }
        if forecast:
            params["forecast_days"] = 16
            url = "https://api.open-meteo.com/v1/forecast"
        else:
            params.update(start_date=str(start), end_date=str(end), models="era5")
            url = "https://archive-api.open-meteo.com/v1/archive"
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.json()
    finally:
        if owned:
            client.close()


def fetch_power(latitude, longitude, start, end, client=None):
    owned = client is None
    client = client or httpx.Client(timeout=40)
    try:
        response = client.get(
            "https://power.larc.nasa.gov/api/temporal/daily/point",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "start": start.strftime("%Y%m%d"),
                "end": end.strftime("%Y%m%d"),
                "parameters": "T2M_MIN,T2M_MAX,PRECTOTCORR,RH2M",
                "community": "AG",
                "format": "JSON",
                "time-standard": "UTC",
            },
        )
        response.raise_for_status()
        return response.json()
    finally:
        if owned:
            client.close()


def fetch_mandi(api_key=None, client=None, max_pages=10, offset=0):
    api_key = (
        api_key
        or os.getenv("DATAGOV_API_KEY")
        or os.getenv("DATA_GOV_API_KEY")
        or os.getenv("OGD_API_KEY")
    )
    if not api_key:
        raise ValueError("OGD API key is required server-side")
    if not 1 <= max_pages <= 100 or offset < 0:
        raise ValueError("Invalid bounded OGD page range")
    owned = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(8, connect=5))
    rows = []
    complete = False
    try:
        for page in range(max_pages):
            response = None
            for attempt in range(3):
                try:
                    response = client.get(
                        "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070",
                        params={
                            "api-key": api_key,
                            "format": "json",
                            "limit": 1000,
                            "offset": offset + page * 1000,
                        },
                    )
                except httpx.TransportError:
                    if attempt == 2:
                        # Even transport exceptions can include the API key URL.
                        raise RuntimeError("OGD transport unavailable") from None
                    time.sleep(0.1 * 2**attempt)
                    continue
                if response.status_code == 200:
                    break
                if (
                    response.status_code not in (408, 429, 500, 502, 503, 504)
                    or attempt == 2
                ):
                    raise RuntimeError(
                        f"OGD request failed HTTP {response.status_code}"
                    )
                time.sleep(0.1 * 2**attempt)
            # Never propagate HTTPStatusError: it embeds credential query strings.
            payload = response.json()
            if not isinstance(payload, dict) or "records" not in payload:
                raise ValueError("Missing OGD records envelope")
            batch = payload["records"]
            if not isinstance(batch, list) or any(
                not isinstance(item, dict) for item in batch
            ):
                raise ValueError("Malformed OGD records")
            rows.extend(batch)
            if len(batch) < 1000:
                complete = True
                break
        return {
            "records": rows,
            "bounded_pages": max_pages,
            "complete": complete,
            "next_offset": 0 if complete else offset + len(rows),
        }
    finally:
        if owned:
            client.close()


def mock_values(station_id, observed_at):
    """Smooth deterministic values. Never a lab measurement or real device command."""
    phase = (
        int(hashlib.sha256(str(station_id).encode()).hexdigest()[:8], 16)
        / 0xFFFFFFFF
        * math.tau
    )
    t = observed_at.timestamp()
    daylight = max(0, math.sin(math.tau * (t / 86400 - 0.25)))
    wave = math.sin(t / 3600 + phase)
    return {
        "temperature_c": round(25 + 7 * daylight + wave, 2),
        "humidity_pct": round(65 - 15 * daylight + 5 * wave, 2),
        "pressure_hpa": round(1008 + 3 * math.sin(t / 18000 + phase), 2),
        "wind_kmh": round(5 + 3 * (1 + wave), 2),
        "wind_direction_degrees": round((t / 90 + phase * 60) % 360, 2),
        "rainfall_increment_mm": 0,
        "soil_temperature_c": round(24 + 3 * daylight, 2),
        "soil_moisture_pct": round(32 + 3 * math.sin(t / 80000 + phase), 2),
        "battery_v": round(3.8 + 0.2 * daylight, 3),
        "solar_v": round(6 * daylight, 3),
        "lux": round(42000 * daylight, 2),
        "uv_index": round(5 * daylight, 3),
        "pm25_ug_m3": round(15 + 5 * (1 + wave), 3),
        "pm10_ug_m3": round(25 + 8 * (1 + wave), 3),
    }


def ingest_mock_packet(conn, station, observed_at=None):
    now = observed_at or datetime.now(UTC)
    now = now.replace(microsecond=0)
    ingest = Ingestor(conn, "demo")
    p, d, r, _raw = ingest.release(
        "demo_hardware",
        "urn:skyview:synthetic-realtime",
        {"generator": "realtime-demo-v1", "day": now.date().isoformat()},
        "synthetic",
        str(station["id"]),
        now,
    )
    boot = uid("demo-boot:" + str(station["id"]) + ":" + str(now.date()))
    sequence = int(now.timestamp())
    receipt = execute(
        conn,
        """INSERT INTO sv3.packet_receipts(dataset_id,farmer_id,station_id,boot_id,sequence,observed_at)
      VALUES(:d,:f,:s,:b,:seq,:now) ON CONFLICT(dataset_id,station_id,boot_id,sequence) DO NOTHING RETURNING sequence""",
        d=d,
        f=station["farmer_id"],
        s=station["id"],
        b=boot,
        seq=sequence,
        now=now,
    ).scalar()
    if receipt is None:
        return False
    values = mock_values(station["id"], now)
    names = ",".join(values)
    binds = ",".join(":" + key for key in values)
    execute(
        conn,
        f"""INSERT INTO sv3.sensor_packets(dataset_id,farmer_id,station_id,observed_at,received_at,boot_id,sequence,{names},quality_flags)
      VALUES(:d,:f,:s,:now,:now,:b,:seq,{binds},'["synthetic","uncalibrated"]'::jsonb)""",
        d=d,
        f=station["farmer_id"],
        s=station["id"],
        now=now,
        b=boot,
        seq=sequence,
        **values,
    )
    execute(
        conn,
        "UPDATE sv3.stations SET last_received_at=:now WHERE id=:id",
        now=now,
        id=station["id"],
    )
    ingest.finish(p, r, str(station["id"]), 1, 1, now, now.date())
    return True


def mock_once(now=None, limit=400):
    from skyview.data.v3.db import connection, mode

    if mode() != "v3_demo":
        raise RuntimeError("Mock telemetry is disabled outside v3_demo")
    now = now or datetime.now(UTC)
    # Partition administration is an allowlisted function, not arbitrary SQL DDL.
    with connection(write=True, ingest=True) as conn:
        execute(
            conn,
            "SELECT sv3.ensure_month_partitions('sensor_packets',:first,:last)",
            first=now.date().replace(day=1),
            last=now.date().replace(day=1),
        )
        stations = (
            execute(
                conn,
                """SELECT s.id,s.farmer_id FROM sv3.stations s JOIN sv3.datasets d ON d.id=s.dataset_id
          WHERE d.origin='synthetic' AND d.lane='demo' ORDER BY s.id LIMIT :limit""",
                limit=max(1, min(limit, 400)),
            )
            .mappings()
            .all()
        )
    count = 0
    for station in stations:
        # Each station is independent; a failure does not hold every station's locks.
        with connection(station["farmer_id"], write=True, ingest=True) as conn:
            count += int(ingest_mock_packet(conn, station, now))
    return {
        "stations": len(stations),
        "inserted": count,
        "origin": "synthetic",
        "actuator_dispatch": False,
    }


def ingest_sensor_envelope(
    conn, farmer_id, station_id, envelope, lane="live", now=None
):
    """Owner/device binding must come from server authentication; not envelope claims.

    This function validates and stores measurements only. It never dispatches actuators.
    """
    from uuid import UUID

    now = now or datetime.now(UTC)
    station = (
        execute(
            conn,
            "SELECT id,farmer_id FROM sv3.stations WHERE id=:id AND farmer_id=:owner",
            id=str(UUID(str(station_id))),
            owner=str(UUID(str(farmer_id))),
        )
        .mappings()
        .first()
    )
    if station is None:
        raise ValueError("station is not bound to authenticated owner")
    if set(envelope) - {"observed_at", "boot_id", "sequence", "measurements"}:
        raise ValueError(
            "unsupported envelope fields; credentials belong in authenticated headers"
        )
    observed = datetime.fromisoformat(envelope["observed_at"])
    if observed.tzinfo is None:
        raise ValueError("observed_at requires timezone")
    observed = observed.astimezone(UTC)
    if observed > now + timedelta(seconds=30) or observed < now - timedelta(days=31):
        raise ValueError("packet outside accepted clock window")
    # Future clock skew is quarantined by rejection; observed time is never silently changed.
    if observed > now:
        raise ValueError("packet timestamp is in the future")
    boot = str(UUID(envelope["boot_id"]))
    sequence = envelope["sequence"]
    if type(sequence) is not int or not 0 <= sequence <= 9223372036854775807:
        raise ValueError("invalid sequence")
    allowed = {
        "temperature_c": (-80, 70),
        "humidity_pct": (0, 100),
        "pressure_hpa": (500, 1200),
        "wind_kmh": (0, 400),
        "wind_direction_degrees": (0, 359.99),
        "rainfall_increment_mm": (0, None),
        "soil_temperature_c": (-80, 70),
        "soil_moisture_pct": (0, 100),
        "battery_v": (0, 100),
        "solar_v": (0, 100),
        "lux": (0, None),
        "uv_index": (0, None),
        "pm25_ug_m3": (0, None),
        "pm10_ug_m3": (0, None),
    }
    measurements = envelope.get("measurements", {})
    if not measurements or set(measurements) - set(allowed):
        raise ValueError("unsupported or empty metric envelope")
    values = {key: finite(value, *allowed[key]) for key, value in measurements.items()}
    if all(value is None for value in values.values()):
        raise ValueError("packet has no usable measurement")
    # One stable device release per UTC receipt day, replay protection spans packets/partitions.
    ingest = Ingestor(conn, lane)
    provider, dataset, run, _raw = ingest.release(
        "authenticated_hardware",
        "urn:skyview:authenticated-device",
        {"station_id": str(station_id), "receipt_day": str(now.date())},
        "observed",
        str(station_id),
        now,
    )
    # Global device replay check is across release days (PK alone is release-scoped).
    execute(
        conn,
        "SELECT pg_advisory_xact_lock(hashtextextended(:station,0))",
        station=str(station_id),
    )
    previous = execute(
        conn,
        "SELECT observed_at FROM sv3.packet_receipts WHERE station_id=:s AND boot_id=:b AND sequence=:seq LIMIT 1",
        s=station_id,
        b=boot,
        seq=sequence,
    ).scalar()
    if previous is not None:
        if previous != observed:
            raise ValueError("conflicting packet replay")
        return {"accepted": False, "duplicate": True}
    execute(
        conn,
        "SELECT sv3.ensure_month_partitions('sensor_packets',:first,:last)",
        first=observed.date().replace(day=1),
        last=observed.date().replace(day=1),
    )
    execute(
        conn,
        """INSERT INTO sv3.packet_receipts(dataset_id,farmer_id,station_id,boot_id,sequence,observed_at)
      VALUES(:d,:f,:s,:b,:seq,:at)""",
        d=dataset,
        f=farmer_id,
        s=station_id,
        b=boot,
        seq=sequence,
        at=observed,
    )
    encoded = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    path = ingest.raw_dir / (digest + ".json")
    if not path.exists():
        path.write_bytes(encoded)
        path.chmod(0o600)
    execute(
        conn,
        """INSERT INTO sv3.raw_objects(id,run_id,request_key,content_hash,object_uri,media_type,bytes,fetched_at)
      VALUES(:id,:run,:key,:hash,:uri,'application/json',:size,:now) ON CONFLICT(run_id,request_key) DO NOTHING""",
        id=uid("packet-raw:" + digest),
        run=run,
        key=boot + ":" + str(sequence),
        hash=digest,
        uri=path.resolve().as_uri(),
        size=len(encoded),
        now=now,
    )
    keys = ",".join(values)
    placeholders = ",".join(":" + key for key in values)
    execute(
        conn,
        f"INSERT INTO sv3.sensor_packets(dataset_id,farmer_id,station_id,observed_at,received_at,boot_id,sequence,{keys}) VALUES(:d,:f,:s,:at,:now,:b,:seq,{placeholders})",
        d=dataset,
        f=farmer_id,
        s=station_id,
        at=observed,
        now=now,
        b=boot,
        seq=sequence,
        **values,
    )
    execute(
        conn,
        "UPDATE sv3.stations SET last_received_at=:now WHERE id=:s",
        now=now,
        s=station_id,
    )
    ingest.finish(provider, run, str(station_id), 1, 1, now, observed.date())
    return {"accepted": True, "duplicate": False, "origin": "observed"}


def import_reviewed(conn, payload, lane="demo", now=None):
    """Human-reviewed local evidence bundle. No web content is interpreted as instructions."""
    from urllib.parse import urlparse

    now = now or datetime.now(UTC)
    source = payload["source_url"]
    host = (urlparse(source).hostname or "").lower()
    if urlparse(source).scheme != "https" or not (
        host.endswith(".gov.in")
        or host in ("icar.org.in", "icar.gov.in", "www.icar.gov.in")
        or host
        in {
            "www.fao.org",
            "www.farmers.gov",
            "agriculture.ec.europa.eu",
            "www.gov.uk",
            "agriculture.canada.ca",
            "www.agriculture.gov.au",
            "agritech.tnau.ac.in",
            "www.agritech.tnau.ac.in",
        }
    ):
        raise ValueError("reviewed evidence requires official HTTPS source")
    if (
        payload.get("review_status") != "reviewed"
        or not payload.get("reviewed_by")
        or not payload.get("evidence_text")
    ):
        raise ValueError("reviewed_by and evidence_text are required")
    ingest = Ingestor(conn, lane)
    p, d, r, _raw = ingest.release(
        "reviewed_official_import", source, payload, "curated", source, now
    )
    doc = uid("reviewed-document:" + str(d))
    content = payload["evidence_text"]
    execute(
        conn,
        """INSERT INTO sv3.documents(id,dataset_id,source_url,title,language,checksum,published_on,retrieved_at,review_status)
      VALUES(:id,:d,:url,:title,:lang,:hash,:published,:now,'reviewed') ON CONFLICT(id) DO NOTHING""",
        id=doc,
        d=d,
        url=source,
        title=payload["title"],
        lang=payload.get("language", "en"),
        hash=hashlib.sha256(content.encode()).hexdigest(),
        published=payload.get("published_on"),
        now=now,
    )
    execute(
        conn,
        "INSERT INTO sv3.document_chunks(id,document_id,ordinal,content) VALUES(:id,:doc,0,:content) ON CONFLICT(document_id,ordinal) DO NOTHING",
        id=uid("chunk:" + doc),
        doc=doc,
        content=content,
    )
    count = 0
    for item in payload.get("msp", []):
        execute(
            conn,
            """INSERT INTO sv3.msp_announcements(id,dataset_id,crop_id,grade,marketing_season,announced_on,effective_from,amount_inr_quintal,official_url)
          VALUES(:id,:d,:crop,:grade,:season,:announced,:effective,:amount,:url) ON CONFLICT(dataset_id,crop_id,grade,marketing_season) DO NOTHING""",
            id=uid("msp:" + str(d) + json.dumps(item, sort_keys=True)),
            d=d,
            crop=item["crop_id"],
            grade=item["grade"],
            season=item["marketing_season"],
            announced=item["announced_on"],
            effective=item["effective_from"],
            amount=finite(item["amount_inr_quintal"], 0),
            url=source,
        )
        count += 1
    for item in payload.get("crop_guides", []):
        execute(
            conn,
            """INSERT INTO sv3.crop_guides(id,document_id,crop_id,region_id,season,growth_stage,guidance,verified_at)
          VALUES(:id,:doc,:crop,:region,:season,:stage,CAST(:guidance AS jsonb),:now) ON CONFLICT(id) DO NOTHING""",
            id=uid("guide:" + str(d) + json.dumps(item, sort_keys=True)),
            doc=doc,
            crop=item["crop_id"],
            region=item.get("region_id"),
            season=item["season"],
            stage=item["growth_stage"],
            guidance=json.dumps(item["guidance"]),
            now=now,
        )
        count += 1
    for item in payload.get("schemes", []):
        app_host = (urlparse(item["application_url"]).hostname or "").lower()
        if urlparse(item["application_url"]).scheme != "https" or not app_host.endswith(
            ".gov.in"
        ):
            raise ValueError("scheme application URL must be official HTTPS")
        execute(
            conn,
            """INSERT INTO sv3.scheme_versions(id,document_id,scheme_code,version,name,region_id,requirements,benefits,application_url,verified_at,valid_from,valid_to)
          VALUES(:id,:doc,:code,:version,:name,:region,CAST(:req AS jsonb),CAST(:benefits AS jsonb),:url,:now,:start,:end)
          ON CONFLICT(scheme_code,version) DO NOTHING""",
            id=uid("scheme:" + item["scheme_code"] + ":" + item["version"]),
            doc=doc,
            code=item["scheme_code"],
            version=item["version"],
            name=item["name"],
            region=item.get("region_id"),
            req=json.dumps(item["requirements"]),
            benefits=json.dumps(item["benefits"]),
            url=item["application_url"],
            now=now,
            start=item.get("valid_from"),
            end=item.get("valid_to"),
        )
        count += 1
    ingest.finish(p, r, source, count, count, now)
    return {
        "document_id": doc,
        "imported": count,
        "reviewed_by": payload["reviewed_by"],
    }
