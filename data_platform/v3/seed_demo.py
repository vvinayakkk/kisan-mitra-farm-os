"""Deterministic, fictional India-wide demo. Standard library only; no network/PII."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import uuid
from datetime import date, timedelta
from pathlib import Path

from seed_additions import extend

VERSION = "3.1.0"
NS = uuid.UUID("2077ed5e-7964-47c3-a6dc-6232cebf4971")


def uid(key):
    return str(uuid.uuid5(NS, key))


# Public approximate anchors, not field boundaries, official codes, or survey weights.
REGIONS = [
    ("AP", "Andhra Pradesh", "te", 16.51, 80.64, "rice,maize,groundnut"),
    ("AR", "Arunachal Pradesh", "en", 27.10, 93.62, "rice,maize,ginger"),
    ("AS", "Assam", "as", 26.14, 91.74, "rice,tea,mustard"),
    ("BR", "Bihar", "hi", 25.61, 85.14, "rice,wheat,maize"),
    ("CG", "Chhattisgarh", "hi", 21.25, 81.63, "rice,maize,chickpea"),
    ("GA", "Goa", "kok", 15.49, 73.83, "rice,coconut,cashew"),
    ("GJ", "Gujarat", "gu", 23.02, 72.57, "cotton,groundnut,castor"),
    ("HR", "Haryana", "hi", 29.39, 76.97, "wheat,rice,mustard"),
    ("HP", "Himachal Pradesh", "hi", 31.10, 77.17, "apple,maize,wheat"),
    ("JH", "Jharkhand", "hi", 23.34, 85.31, "rice,maize,potato"),
    ("KA", "Karnataka", "kn", 15.36, 75.12, "ragi,maize,coffee"),
    ("KL", "Kerala", "ml", 10.53, 76.21, "coconut,rice,pepper"),
    ("MP", "Madhya Pradesh", "hi", 23.26, 77.41, "soybean,wheat,chickpea"),
    ("MH", "Maharashtra", "mr", 19.99, 73.79, "cotton,soybean,onion"),
    ("MN", "Manipur", "mni", 24.82, 93.94, "rice,maize,ginger"),
    ("ML", "Meghalaya", "en", 25.57, 91.88, "rice,ginger,potato"),
    ("MZ", "Mizoram", "en", 23.73, 92.72, "rice,maize,ginger"),
    ("NL", "Nagaland", "en", 25.68, 94.11, "rice,maize,ginger"),
    ("OD", "Odisha", "or", 20.30, 85.82, "rice,groundnut,mustard"),
    ("PB", "Punjab", "pa", 30.90, 75.86, "wheat,rice,cotton"),
    ("RJ", "Rajasthan", "hi", 26.91, 75.79, "bajra,mustard,chickpea"),
    ("SK", "Sikkim", "en", 27.33, 88.61, "maize,ginger,cardamom"),
    ("TN", "Tamil Nadu", "ta", 11.02, 76.96, "rice,coconut,banana"),
    ("TS", "Telangana", "te", 17.38, 78.49, "rice,cotton,maize"),
    ("TR", "Tripura", "bn", 23.83, 91.28, "rice,maize,banana"),
    ("UP", "Uttar Pradesh", "hi", 26.85, 80.95, "wheat,rice,sugarcane"),
    ("UK", "Uttarakhand", "hi", 30.32, 78.03, "wheat,rice,apple"),
    ("WB", "West Bengal", "bn", 22.57, 88.36, "rice,potato,jute"),
    ("AN", "Andaman and Nicobar Islands", "hi", 11.67, 92.74, "coconut,rice,banana"),
    ("CH", "Chandigarh", "hi", 30.73, 76.78, "wheat,maize,potato"),
    (
        "DN",
        "Dadra and Nagar Haveli and Daman and Diu",
        "gu",
        20.27,
        73.01,
        "rice,maize,banana",
    ),
    ("DL", "Delhi", "hi", 28.61, 77.21, "wheat,mustard,potato"),
    ("JK", "Jammu and Kashmir", "ur", 34.08, 74.80, "apple,rice,maize"),
    ("LA", "Ladakh", "hi", 34.15, 77.58, "barley,potato,apple"),
    ("LD", "Lakshadweep", "ml", 10.57, 72.64, "coconut,banana,pepper"),
    ("PY", "Puducherry", "ta", 11.94, 79.81, "rice,groundnut,banana"),
]
BASE = {
    "rice": 2300,
    "wheat": 2500,
    "maize": 2100,
    "ginger": 6500,
    "tea": 12000,
    "mustard": 5500,
    "groundnut": 5900,
    "chickpea": 5700,
    "coconut": 3000,
    "cashew": 11500,
    "cotton": 6800,
    "castor": 6200,
    "apple": 7500,
    "potato": 1600,
    "ragi": 4200,
    "coffee": 16000,
    "pepper": 45000,
    "soybean": 4500,
    "onion": 2200,
    "bajra": 2400,
    "cardamom": 100000,
    "banana": 2300,
    "sugarcane": 350,
    "jute": 5200,
    "barley": 2100,
}
PERENNIAL = {
    "tea",
    "coconut",
    "cashew",
    "apple",
    "coffee",
    "pepper",
    "cardamom",
    "banana",
    "sugarcane",
}


def generate(out: Path, asof: date, seed: int):
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    counts = {}
    writers = {}
    files = {}
    cols = {}
    created = f"{asof.isoformat()}T00:00:00+00:00"
    dataset = uid(f"dataset:{seed}:{asof}")

    def add(table, **row):
        if table not in writers:
            cols[table] = list(row)
            f = (out / f"{table}.csv").open("w", newline="")
            files[table] = f
            writers[table] = csv.writer(f)
            counts[table] = 0
        if list(row) != cols[table]:
            raise ValueError(f"Inconsistent columns: {table}")
        writers[table].writerow(
            [
                "\\N"
                if v is None
                else json.dumps(v, ensure_ascii=False, separators=(",", ":"))
                if isinstance(v, (dict, list))
                else v
                for v in row.values()
            ]
        )
        counts[table] += 1

    add(
        "providers",
        id=uid("provider:demo"),
        code="demo-generator",
        name="SkyView synthetic generator",
        homepage="https://example.invalid/skyview-demo",
        access_method="local deterministic generator",
        license_name="Project demo fixtures",
        attribution="Entirely fictional; no real farmer records or observed prices",
        status="demo",
        refresh_seconds=86400,
        configuration={"version": VERSION},
        created_at=created,
    )
    add(
        "datasets",
        id=dataset,
        provider_id=uid("provider:demo"),
        release_key=f"demo-{VERSION}-{seed}-{asof}",
        lane="demo",
        origin="synthetic",
        as_of_date=asof,
        generator_version=VERSION,
        seed=seed,
        source_url="demo://skyview/v3",
        checksum=None,
        created_at=created,
    )
    for code, dim, sym, factor in [
        ("quintal", "mass", "q", 100),
        ("tonne", "mass", "t", 1000),
        ("kg", "mass", "kg", 1),
        ("count", "count", "items", 1),
        ("celsius", "temperature", "°C", None),
        ("percent", "ratio", "%", 0.01),
        ("mm", "length", "mm", 0.001),
        ("hpa", "pressure", "hPa", 100),
        ("kmh", "velocity", "km/h", None),
        ("degrees", "angle", "°", None),
        ("ugm3", "concentration", "µg/m³", None),
        ("index", "dimensionless", "index", None),
        ("lux", "illuminance", "lx", None),
        ("volt", "voltage", "V", 1),
        ("ph", "acidity", "pH", None),
        ("gkg", "mass_fraction", "g/kg", 0.001),
    ]:
        add("units", code=code, dimension=dim, symbol=sym, factor_to_base=factor)
    for crop in BASE:
        add(
            "crops",
            id=uid("crop:" + crop),
            code=crop,
            name=crop.title(),
            names={},
            category="perennial" if crop in PERENNIAL else "seasonal",
            perennial=crop in PERENNIAL,
        )
        add(
            "crop_varieties",
            id=uid("variety:" + crop),
            crop_id=uid("crop:" + crop),
            code="demo-standard",
            name="Demo standard — not an actual cultivar",
        )
    market_series = []
    weather_series = []
    for idx, (code, name, lang, lat, lon, cropmix) in enumerate(REGIONS):
        rid = uid("region:" + code)
        lid = uid("location:" + code)
        add(
            "regions",
            id=rid,
            dataset_id=dataset,
            parent_id=None,
            level="state" if idx < 28 else "ut",
            code_system="DEMO",
            code="DEMO-IN-" + code,
            name=name,
            valid_from=asof - timedelta(days=365),
            valid_to=None,
        )
        add(
            "locations",
            id=lid,
            dataset_id=dataset,
            region_id=rid,
            location_key="demo-anchor-" + code,
            label=name + " demo anchor",
            latitude=lat,
            longitude=lon,
            resolution_m=25000,
        )
        wid = uid("weather:" + code)
        weather_series.append(wid)
        add(
            "weather_series",
            id=wid,
            provider_id=uid("provider:demo"),
            location_id=lid,
            model_name="synthetic-seasonal-v3",
            resolution_m=25000,
        )
        for m in range(3):
            mid = uid(f"market:{code}:{m}")
            add(
                "markets",
                id=mid,
                dataset_id=dataset,
                region_id=rid,
                code_system="DEMO",
                external_code=f"{code}-{m}",
                name=f"{name} demo market {m + 1}",
                latitude=lat + (m - 1) * 0.08,
                longitude=lon,
            )
            for crop in cropmix.split(","):
                sid = uid(f"series:{code}:{m}:{crop}")
                market_series.append((sid, crop, idx, m))
                add(
                    "market_series",
                    id=sid,
                    market_id=mid,
                    crop_id=uid("crop:" + crop),
                    variety_id=uid("variety:" + crop),
                    grade="demo-standard",
                    unit_code="quintal",
                    currency="INR",
                )
    plots = []
    cycle_ids = {}
    farmers = []
    # 11 in every region + one extra in first four: balanced test coverage, not population weights.
    for n in range(400):
        idx = n % 36
        code, name, lang, lat, lon, mix = REGIONS[idx]
        crops = mix.split(",")
        fid = uid(f"farmer:{n}")
        farm = uid(f"farm:{n}")
        farmers.append(fid)
        size = round(rng.uniform(0.3, 1.9) if n % 10 < 7 else rng.uniform(2, 6), 4)
        add(
            "farmers",
            id=fid,
            dataset_id=dataset,
            profile_key=f"DEMO-F{n + 1:04}",
            auth_subject=None,
            display_name=f"Demo farmer {n + 1:04}",
            region_id=uid("region:" + code),
            preferred_language=lang,
            age_band=["25–34", "35–44", "45–54", "55–64"][n % 4],
            farming_experience_years=5 + n % 30,
            profile_attributes={
                "synthetic": True,
                "coverage_group": code,
                "connectivity": ["intermittent", "mobile", "broadband"][n % 3],
                "advisory_style": "plain-language",
                "training_eligible": False,
            },
            contact_email=f"farmer-{n + 1:04}@example.invalid",
            contact_phone=None,
            contact_verified_at=None,
            status="demo",
            created_at=created,
        )
        add(
            "farms",
            id=farm,
            farmer_id=fid,
            farm_key=f"DEMO-FARM-{n + 1:04}",
            name=f"Demo farm {n + 1:04}",
            region_id=uid("village:" + code),
            location_id=uid("location:" + code),
            ownership_type=["owned", "leased", "managed"][n % 3],
            irrigation_method=["rainfed", "drip", "sprinkler", "surface"][n % 4],
            water_source="rain"
            if n % 4 == 0
            else ["well", "canal", "stored water"][n % 3],
        )
        for p in range(2):
            pid = uid(f"plot:{n}:{p}")
            plat = lat + rng.uniform(-0.02, 0.02)
            plon = lon + rng.uniform(-0.02, 0.02)
            area = round(size * (0.55 if p == 0 else 0.45), 4)
            # Synthetic square calculated in local metres; no cadastral boundary assertion.
            edge = math.sqrt(area * 10000) / 2
            dy = edge / 111320
            dx = edge / (111320 * math.cos(math.radians(plat)))
            poly = {
                "type": "Polygon",
                "coordinates": [
                    [
                        [plon - dx, plat - dy],
                        [plon + dx, plat - dy],
                        [plon + dx, plat + dy],
                        [plon - dx, plat + dy],
                        [plon - dx, plat - dy],
                    ]
                ],
            }
            add(
                "plots",
                id=pid,
                farmer_id=fid,
                farm_id=farm,
                plot_key=f"DEMO-P{n:04}-{p}",
                area_ha=area,
                latitude=round(plat, 6),
                longitude=round(plon, 6),
                boundary_geojson=poly,
                soil_texture=["loam", "clay", "sandy loam"][n % 3],
            )
            plots.append((pid, fid, idx))
            for phase in range(2):
                cid = uid(f"cycle:{n}:{p}:{phase}")
                crop = crops[(n + p + phase) % 3]
                sow = asof - timedelta(days=210 if phase == 0 else 60)
                add(
                    "crop_cycles",
                    id=cid,
                    farmer_id=fid,
                    plot_id=pid,
                    crop_id=uid("crop:" + crop),
                    variety_id=uid("variety:" + crop),
                    season="demo previous" if phase == 0 else "demo current",
                    sowing_date=sow,
                    expected_harvest_date=sow + timedelta(days=120),
                    actual_harvest_date=sow + timedelta(days=120)
                    if phase == 0
                    else None,
                    status="harvested" if phase == 0 else "growing",
                    expected_yield_t_ha=None,
                    actual_yield_t_ha=None,
                )
                if phase == 1 and p == 0:
                    cycle_ids[fid] = cid
                add(
                    "farm_operations",
                    id=uid(f"op:{cid}"),
                    farmer_id=fid,
                    cycle_id=cid,
                    operation="demo sowing",
                    occurred_at=f"{sow}T06:00:00+00:00",
                    quantity=None,
                    unit_code=None,
                    notes="Synthetic event for testing",
                    evidence_uri=None,
                )
            sample = uid("soil:" + pid)
            add(
                "soil_samples",
                id=sample,
                farmer_id=fid,
                plot_id=pid,
                dataset_id=dataset,
                sampled_on=asof - timedelta(days=40),
                sample_type="synthetic",
                lab_name=None,
                report_uri=None,
            )
            for prop, unit, base in [
                ("ph", "ph", 6.7),
                ("organic_carbon", "gkg", 12),
                ("clay", "percent", 30),
            ]:
                value = round(base + rng.uniform(-0.6, 0.6), 3)
                add(
                    "soil_indicators",
                    id=uid(f"soil:{pid}:{prop}"),
                    farmer_id=fid,
                    plot_id=pid,
                    sample_id=sample,
                    dataset_id=dataset,
                    property=prop,
                    depth_top_cm=0,
                    depth_bottom_cm=15,
                    unit_code=unit,
                    mean_value=value,
                    lower_value=None,
                    upper_value=None,
                    evidence_type="synthetic",
                )
    for n, fid in enumerate(farmers):
        for r in range(3):
            rid = uid(f"resource:{n}:{r}")
            add(
                "resources",
                id=rid,
                farmer_id=fid,
                category=["equipment", "produce", "supplies"][r],
                name=["Demo sprayer", "Demo produce", "Demo seed stock"][r],
                quantity=1 if r == 0 else 100,
                unit_code="count" if r == 0 else "kg",
            )
            if r == 0 and n < 300:
                add(
                    "resource_listings",
                    id=uid(f"listing:{n}"),
                    farmer_id=fid,
                    resource_id=rid,
                    visibility="private",
                    available_from=asof,
                    available_to=asof + timedelta(days=30),
                    asking_price_inr=200,
                    status="demo draft",
                )
        for m in range(12):
            add(
                "expenses",
                id=uid(f"expense:{n}:{m}"),
                farmer_id=fid,
                cycle_id=None,
                description="Demo farm expense",
                spent_on=asof - timedelta(days=m * 30),
                amount_inr=round(rng.uniform(250, 3500), 2),
                category=["seed", "labor", "water"][m % 3],
                execution_key=f"demo-expense-{n}-{m}",
            )
        for t in range(6):
            task = uid(f"task:{n}:{t}")
            add(
                "tasks",
                id=task,
                farmer_id=fid,
                cycle_id=cycle_ids[fid],
                title=[
                    "Scout crop",
                    "Check moisture",
                    "Review weather",
                    "Compare mandi prices",
                    "Record expenses",
                    "Review next season",
                ][t],
                due_at=f"{asof + timedelta(days=t * 3)}T04:30:00+00:00",
                timezone="Asia/Kolkata",
                status="open",
                notes="Demo plan: no real work has been executed",
                deleted_at=None,
                execution_key=f"demo-task-{n}-{t}",
            )
        conv = uid(f"conversation:{n}")
        msg = uid(f"message:{n}")
        add(
            "conversations",
            id=conv,
            farmer_id=fid,
            title="Demo farm context",
            summary="Synthetic onboarding fixture",
            summarized_through=1,
            archived_at=None,
            created_at=created,
        )
        add(
            "messages",
            id=msg,
            farmer_id=fid,
            conversation_id=conv,
            sequence=1,
            role="user",
            content={"text": "This is a synthetic demo farm."},
            token_count=10,
            created_at=created,
        )
        add(
            "memories",
            id=uid(f"memory:{n}"),
            farmer_id=fid,
            fact_key="profile.synthetic",
            value={"synthetic": True},
            evidence_message_id=msg,
            confidence=1,
            valid_from=created,
            valid_to=None,
            supersedes_id=None,
            search_text="Synthetic demo farm context",
        )
    history_start = asof - timedelta(days=364)
    for sid, crop, region_idx, m in market_series:
        level = BASE[crop] * (1 + region_idx * 0.002 + m * 0.012)
        for offset in range(365):
            day = history_start + timedelta(days=offset)
            price = round(
                level
                * (
                    1
                    + 0.12 * math.sin(2 * math.pi * day.timetuple().tm_yday / 365)
                    + rng.uniform(-0.035, 0.035)
                ),
                2,
            )
            add(
                "price_observations",
                dataset_id=dataset,
                series_id=sid,
                observed_on=day,
                min_price=round(price * 0.92, 2),
                modal_price=price,
                max_price=round(price * 1.09, 2),
                arrivals_quantity=round(rng.uniform(5, 130), 3),
                arrivals_unit="tonne",
                fetched_at=created,
                revision=1,
            )
    model = uid("model:scenario")
    run = uid("run:" + str(asof) + ":" + str(seed))
    add(
        "model_versions",
        id=model,
        name="demo-seasonality",
        version=VERSION,
        purpose="UI and stress testing only; not a trained prediction model",
        trained_until=None,
        validation={"status": "not validated", "training_eligible": False},
        artifact_uri=None,
        status="scenario_only",
    )
    add(
        "forecast_runs",
        id=run,
        dataset_id=dataset,
        model_id=model,
        issued_at=created,
        training_cutoff=asof,
        horizon_days=365,
        kind="scenario",
    )
    for sid, crop, region_idx, m in market_series:
        level = BASE[crop] * (1 + region_idx * 0.002 + m * 0.012)
        for lead in range(1, 366):
            day = asof + timedelta(days=lead)
            price = round(
                level
                * (1 + 0.12 * math.sin(2 * math.pi * day.timetuple().tm_yday / 365)),
                2,
            )
            width = 0.15 + 0.2 * lead / 365
            add(
                "price_projections",
                run_id=run,
                series_id=sid,
                valid_on=day,
                kind="scenario",
                lower_price=round(price * (1 - width), 2),
                central_price=price,
                upper_price=round(price * (1 + width), 2),
                interval_definition="Synthetic planning envelope; NOT a calibrated confidence interval",
            )
    for idx, wid in enumerate(weather_series):
        for offset in range(365):
            day = history_start + timedelta(days=offset)
            temp = (
                24
                + 7 * math.sin(2 * math.pi * (day.timetuple().tm_yday - 95) / 365)
                - (idx % 6)
            )
            rain = (
                round(rng.uniform(1, 30), 3)
                if rng.random()
                < (0.45 if 150 < day.timetuple().tm_yday < 270 else 0.09)
                else 0
            )
            add(
                "weather_daily",
                dataset_id=dataset,
                series_id=wid,
                day=day,
                kind="synthetic",
                temperature_min_c=round(temp - 5, 2),
                temperature_max_c=round(temp + 7, 2),
                rainfall_mm=rain,
                humidity_mean_pct=round(min(95, 50 + rain), 2),
                et0_mm=round(max(1, (temp + 5) / 9), 3),
            )
        for lead in range(1, 366):
            day = asof + timedelta(days=lead)
            temp = (
                24
                + 7 * math.sin(2 * math.pi * (day.timetuple().tm_yday - 95) / 365)
                - (idx % 6)
            )
            add(
                "weather_forecasts",
                dataset_id=dataset,
                series_id=wid,
                issued_at=created,
                valid_on=day,
                kind="scenario",
                temperature_min_c=round(temp - 5, 2),
                temperature_max_c=round(temp + 7, 2),
                rainfall_mm=4 if 150 < day.timetuple().tm_yday < 270 else 0.5,
                rainfall_probability=None,
                method="Synthetic seasonal scenario; not a daily weather forecast",
            )
    metrics = [
        ("temperature", "celsius"),
        ("humidity", "percent"),
        ("pressure", "hpa"),
        ("wind", "kmh"),
        ("wind_direction", "degrees"),
        ("rainfall_increment", "mm"),
        ("soil_temperature", "celsius"),
        ("soil_moisture", "percent"),
        ("pm25", "ugm3"),
        ("pm10", "ugm3"),
        ("uv", "index"),
        ("lux", "lux"),
        ("battery", "volt"),
        ("solar", "volt"),
    ]
    sensor_start = asof - timedelta(days=30)
    for n, (pid, fid, idx) in enumerate(plots[:80]):
        station = uid("station:" + pid)
        boot = uid("boot:" + pid)
        seq = 0
        add(
            "stations",
            id=station,
            farmer_id=fid,
            plot_id=pid,
            dataset_id=dataset,
            station_key=f"DEMO-STATION-{n:03}",
            device_type="mock-v3",
            calibration={"synthetic": True, "interval_seconds": 3600},
            installed_at=f"{sensor_start}T00:00:00+00:00",
            last_received_at=f"{asof-timedelta(days=1)}T23:03:00+00:00",
        )
        for metric, unit in metrics:
            add(
                "station_sensors",
                id=uid(f"sensor:{station}:{metric}"),
                farmer_id=fid,
                station_id=station,
                metric=metric,
                unit_code=unit,
                depth_cm=15 if metric.startswith("soil") else None,
                enabled=True,
                measurement_basis="relative_demo_percent"
                if metric == "soil_moisture"
                else "canonical_typed_metric",
                calibration={"synthetic": True, "calibrated_for_vwc": False},
            )
        for offset in range(30):
            day = sensor_start + timedelta(days=offset)
            temps = []
            moisture = []
            rain_sum = 0
            for hour in range(24):
                # Deterministic outage windows: missing packets remain missing.
                if n % 10 == 0 and offset in (10, 11) and 8 <= hour < 16:
                    continue
                seq += 1
                instant = f"{day}T{hour:02}:00:00+00:00"
                received = f"{day}T{hour:02}:03:00+00:00"
                temp = round(
                    24
                    + 5 * math.sin(2 * math.pi * (hour - 6) / 24)
                    + rng.uniform(-0.7, 0.7),
                    2,
                )
                moist = round(max(8, 35 - offset * 0.4 + n % 6), 2)
                rain = round(rng.uniform(0, 5), 3) if n % 7 == 0 and offset == 20 else 0
                flags = ["low_battery"] if n % 13 == 0 and offset > 24 else []
                add(
                    "packet_receipts",
                    dataset_id=dataset,
                    farmer_id=fid,
                    station_id=station,
                    boot_id=boot,
                    sequence=seq,
                    observed_at=instant,
                )
                add(
                    "sensor_packets",
                    dataset_id=dataset,
                    farmer_id=fid,
                    station_id=station,
                    observed_at=instant,
                    received_at=received,
                    boot_id=boot,
                    sequence=seq,
                    temperature_c=temp,
                    humidity_pct=65,
                    pressure_hpa=1007,
                    wind_kmh=6,
                    wind_direction_degrees=120,
                    rainfall_increment_mm=rain,
                    soil_temperature_c=round(temp - 2, 2),
                    soil_moisture_pct=moist,
                    pm25_ug_m3=15,
                    pm10_ug_m3=25,
                    uv_index=max(0, round(5 * math.sin(math.pi * hour / 24), 3)),
                    lux=10000 if 6 <= hour <= 18 else 0,
                    battery_v=3.2 if flags else 4.1,
                    solar_v=5 if 6 <= hour <= 18 else 0,
                    quality_flags=flags,
                )
                temps.append(temp)
                moisture.append(moist)
                rain_sum += rain
            add(
                "sensor_daily",
                dataset_id=dataset,
                farmer_id=fid,
                station_id=station,
                day=day,
                sample_count=len(temps),
                completeness=round(len(temps) / 24, 4),
                temperature_min_c=min(temps),
                temperature_max_c=max(temps),
                rainfall_mm=round(rain_sum, 3),
                soil_moisture_mean_pct=round(sum(moisture) / len(moisture), 2),
            )
    extend(add, uid, rng, dataset, asof, created, farmers, plots, cycle_ids, REGIONS)
    for f in files.values():
        f.close()
    catalog = json.loads((Path(__file__).parent / "catalog/schema-catalog.json").read_text())
    for t in catalog["tables"]:
        counts.setdefault(t["name"], 0)
    sql = out / "seed.sql"
    with sql.open("w") as f:
        f.write(
            "BEGIN;\nSET search_path=sv3,public;\nDO $$ BEGIN IF current_database() NOT IN ('skyview_v3_demo','skyview_v3_test') THEN RAISE EXCEPTION 'Seed permitted only in fresh demo/test database'; END IF; IF EXISTS(SELECT 1 FROM sv3.farmers) THEN RAISE EXCEPTION 'Seed requires empty database'; END IF; END $$;\n"
        )
        for parent, start in [
            ("price_observations", history_start),
            ("sensor_packets", sensor_start),
        ]:
            f.write(f"SELECT ensure_month_partitions('{parent}','{start}','{asof}');\n")
        # Actual creation order above is topologically valid; grouped files keep dependencies.
        copy_order = list(writers)
        copy_order.remove("measurement_definitions")
        copy_order.insert(copy_order.index("units") + 1, "measurement_definitions")
        for table in copy_order:
            f.write(
                f"COPY {table} ({','.join(cols[table])}) FROM STDIN WITH (FORMAT csv, NULL '\\N');\n"
            )
            with (out / f"{table}.csv").open() as raw:
                for line in raw:
                    f.write(line)
            f.write("\\.\n")
        f.write("COMMIT;\n")
    manifest = {
        "generator_version": VERSION,
        "seed": seed,
        "as_of_date": str(asof),
        "lane": "demo",
        "origin": "synthetic",
        "farmers": 400,
        "regions": 36,
        "history": {"from": str(history_start), "through": str(asof), "days": 365},
        "future_scenarios": {
            "from": str(asof + timedelta(days=1)),
            "through": str(asof + timedelta(days=365)),
            "days": 365,
            "not_forecasts": True,
        },
        "base_tables": len(counts),
        "rows": counts,
        "total_rows": sum(counts.values()),
        "empty_tables": [k for k, v in counts.items() if not v],
        "files": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(out.glob("*.csv"))
        },
        "limitations": [
            "Balanced regional test coverage, not representative demographic sampling",
            "No real contacts, government identity, diagnosis labels, lab evidence or external delivery",
            "Geography anchors are approximate; plots are fictional, not cadastral data",
            "All prices use explicit INR/quintal and arbitrary scenario baselines; not MSP",
            "No official reference documents were ingested; curated source links are in source-catalog.json",
        ],
    }
    manifest["seed_sql_sha256"] = hashlib.sha256(sql.read_bytes()).hexdigest()
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False)
    )
    print(
        json.dumps(
            {
                k: manifest[k]
                for k in [
                    "farmers",
                    "regions",
                    "base_tables",
                    "total_rows",
                    "history",
                    "future_scenarios",
                ]
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date(2026, 10, 14))
    parser.add_argument("--seed", type=int, default=20261014)
    args = parser.parse_args()
    generate(args.output, args.as_of, args.seed)
