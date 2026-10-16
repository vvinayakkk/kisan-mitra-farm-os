"""Owned onboarding, actual farm records and physical-device enrollment.

State names are curated public references, not LGD village IDs. No coordinates,
varieties, contact verification, telemetry or physical execution are fabricated.
"""

import hashlib
import json
import secrets
import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from skyview.api.v3_routes import Owner
from skyview.data.v3 import db, repository
from skyview.languages import LANGUAGE_NAMES, normalize_language

router = APIRouter(tags=["Farmer onboarding and owned farm records"])

LANGUAGES = tuple(LANGUAGE_NAMES)


class Inputs(BaseModel):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, allow_inf_nan=False
    )


class Onboarding(Inputs):
    display_name: str = Field(min_length=2, max_length=100)
    region_id: uuid.UUID
    preferred_language: str = Field(min_length=2, max_length=12)
    consent_to_store_profile: Literal[True]

    @field_validator("preferred_language")
    @classmethod
    def language(cls, value):
        return normalize_language(value)


class FarmInput(Inputs):
    name: str = Field(min_length=2, max_length=120)
    region_id: uuid.UUID
    ownership_type: Literal["owned", "leased", "shared"]
    irrigation_method: Literal[
        "rainfed", "drip", "sprinkler", "flood", "manual", "other"
    ]
    water_source: str | None = Field(default=None, max_length=160)


class PlotInput(Inputs):
    name: str = Field(default="", max_length=120)
    farm_id: uuid.UUID
    area_ha: Decimal = Field(gt=0, le=100000, max_digits=10, decimal_places=4)
    latitude: Decimal = Field(ge=-90, le=90, max_digits=9, decimal_places=6)
    longitude: Decimal = Field(ge=-180, le=180, max_digits=9, decimal_places=6)
    boundary_geojson: dict | None = None
    soil_texture: str | None = Field(default=None, max_length=60)

    @model_validator(mode="after")
    def geometry(self):
        value = self.boundary_geojson
        if value is None:
            return self
        if len(json.dumps(value, allow_nan=False)) > 64000 or value.get("type") not in (
            "Polygon",
            "MultiPolygon",
        ):
            raise ValueError(
                "Boundary must be a bounded Polygon or MultiPolygon geometry"
            )
        try:
            from shapely.geometry import shape

            geometry = shape(value)
        except ImportError as exc:
            raise ValueError(
                "Boundary validation unavailable; supply coordinates without a polygon"
            ) from exc
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError("Unreadable plot boundary") from exc
        if geometry.is_empty or not geometry.is_valid or geometry.area <= 0:
            raise ValueError("Plot boundary must be nonempty and valid")
        west, south, east, north = geometry.bounds
        if not (-180 <= west <= east <= 180 and -90 <= south <= north <= 90):
            raise ValueError("Boundary coordinates must use WGS84 longitude, latitude")
        if not (
            west <= float(self.longitude) <= east
            and south <= float(self.latitude) <= north
        ):
            raise ValueError("Plot coordinates must fall within boundary bounds")
        return self


class CycleInput(Inputs):
    plot_id: uuid.UUID
    crop_id: uuid.UUID
    variety_id: uuid.UUID | None = None
    season: str = Field(min_length=2, max_length=40)
    sowing_date: date
    expected_harvest_date: date | None = None
    actual_harvest_date: date | None = None
    status: Literal["planned", "growing", "harvested", "failed"]

    @model_validator(mode="after")
    def dates(self):
        if any(
            day is not None and day < self.sowing_date
            for day in (self.expected_harvest_date, self.actual_harvest_date)
        ):
            raise ValueError("Harvest must follow sowing")
        if self.status == "harvested" and self.actual_harvest_date is None:
            raise ValueError("Record the actual harvest date")
        if self.actual_harvest_date and self.actual_harvest_date > date.today():
            raise ValueError("Actual harvest cannot be in the future")
        return self


class Enrollment(Inputs):
    plot_id: uuid.UUID
    physical_device: Literal[True]
    device_label: str = Field(min_length=2, max_length=120)


class WeatherLink(Inputs):
    plot_id: uuid.UUID
    consent_to_share_coarse_grid: Literal[True]


SOIL_PROPERTIES = (
    "ph",
    "organic_carbon",
    "nitrogen",
    "phosphorus",
    "potassium",
    "sulphur",
    "zinc",
    "iron",
    "copper",
    "manganese",
    "boron",
    "ec",
)


class SoilValue(Inputs):
    property: str
    unit_code: str = Field(min_length=1, max_length=20)
    value: Decimal = Field(ge=0, max_digits=14, decimal_places=4)
    reported_basis: str = Field(min_length=3, max_length=160)
    depth_top_cm: Decimal = Field(ge=0, lt=200, max_digits=6, decimal_places=2)
    depth_bottom_cm: Decimal = Field(gt=0, le=200, max_digits=6, decimal_places=2)

    @model_validator(mode="after")
    def explicit_basis(self):
        if self.property not in SOIL_PROPERTIES:
            raise ValueError("Choose a supported soil report parameter")
        if self.depth_bottom_cm <= self.depth_top_cm:
            raise ValueError("Sample bottom depth must exceed top depth")
        bases = {
            "nitrogen": {"available N"},
            "phosphorus": {"elemental P", "P2O5"},
            "potassium": {"elemental K", "K2O"},
        }
        if self.property in bases and self.reported_basis not in bases[self.property]:
            raise ValueError(
                "Select the explicit nutrient basis shown on the source report"
            )
        return self


class SoilReport(Inputs):
    request_key: uuid.UUID
    plot_id: uuid.UUID
    attachment_id: uuid.UUID
    sampled_on: date
    values: list[SoilValue] = Field(min_length=1, max_length=36)
    values_confirmed_by_farmer: Literal[True]
    reported_lab_name: str | None = Field(default=None, max_length=160)

    @model_validator(mode="after")
    def dates_and_unique(self):
        if self.sampled_on > date.today():
            raise ValueError("Sample date cannot be in the future")
        keys = {(v.property, v.depth_top_cm, v.depth_bottom_cm) for v in self.values}
        if len(keys) != len(self.values):
            raise ValueError("Duplicate property and sample depth")
        return self


def sql(conn, statement, **params):
    return conn.execute(text(statement), params)


def owned(conn, table, identifier):

    if table not in {"farmers", "farms", "plots", "crop_cycles", "stations"}:
        raise ValueError("Unsupported owned entity")
    row = (
        sql(conn, f"SELECT * FROM sv3.{table} WHERE id=:id", id=identifier)
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(404, "This record is not in your farm account.")
    return row


def onboarded(conn, owner):
    row = owned(conn, "farmers", owner)
    if row["status"] == "onboarding" or row["region_id"] is None:
        raise HTTPException(409, "Finish your name, state and language profile first.")
    return row


def curated_region(conn, identifier):
    row = (
        sql(
            conn,
            "SELECT id,name FROM sv3.regions WHERE id=:id AND code_system='skyview-curated-state-name' AND valid_to IS NULL",
            id=identifier,
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(
            422, "Choose a state or union territory from onboarding options."
        )
    return row


@router.get("/api/onboarding/options")
def options():
    with db.connection() as conn:
        regions = repository.rows(
            conn,
            "SELECT r.id,r.name,r.level,r.code_system,d.source_url FROM sv3.regions r JOIN sv3.datasets d ON d.id=r.dataset_id WHERE r.code_system='skyview-curated-state-name' AND r.valid_to IS NULL ORDER BY r.name",
        )
        crops = repository.rows(
            conn, "SELECT id,code,name FROM sv3.crops ORDER BY name"
        )
    return {
        "regions": regions,
        "languages": LANGUAGES,
        "crops": crops,
        "geography_note": "State names only; these IDs are internal reference keys, not official LGD or cadastral codes.",
    }


@router.post("/api/onboarding")
def onboarding(payload: Onboarding, owner: Owner):
    with db.connection(owner, write=True) as conn:
        current = owned(conn, "farmers", owner)
        curated_region(conn, payload.region_id)
        if db.mode() == "v3_live" and not (current["auth_subject"] or "").startswith(
            "oidc:"
        ):
            raise HTTPException(403, "A verified sign-in account is required.")
        status = "demo" if current["status"] == "demo" else "active"
        sql(
            conn,
            "UPDATE sv3.farmers SET display_name=:name,region_id=:region,preferred_language=:language,status=:status,profile_attributes=profile_attributes||jsonb_build_object('onboarding_required',false) WHERE id=:owner",
            name=payload.display_name,
            region=payload.region_id,
            language=payload.preferred_language,
            status=status,
            owner=owner,
        )
        sql(
            conn,
            "INSERT INTO sv3.consents(farmer_id,purpose,granted_at,evidence_hash) VALUES(:owner,'profile_storage',now(),:hash)",
            owner=owner,
            hash=hashlib.sha256(payload.model_dump_json().encode()).hexdigest(),
        )
    return {
        "saved": True,
        "status": status,
        "profile": repository.profile(owner)["profile"],
        "contact_verified": bool(current["contact_verified_at"]),
    }


@router.get("/api/farms")
def farms(owner: Owner):
    with db.connection(owner) as conn:
        items = repository.rows(
            conn,
            "SELECT id,farm_key,name,region_id,ownership_type,irrigation_method,water_source FROM sv3.farms ORDER BY name",
        )
    return {"farms": items}


@router.post("/api/farms")
def create_farm(payload: FarmInput, owner: Owner):
    identifier = uuid.uuid4()
    with db.connection(owner, write=True) as conn:
        onboarded(conn, owner)
        curated_region(conn, payload.region_id)
        sql(
            conn,
            "INSERT INTO sv3.farms(id,farmer_id,farm_key,name,region_id,ownership_type,irrigation_method,water_source) VALUES(:id,:owner,:key,:name,:region,:ownership,:irrigation,:water)",
            id=identifier,
            owner=owner,
            key="USER-FARM-" + identifier.hex,
            name=payload.name,
            region=payload.region_id,
            ownership=payload.ownership_type,
            irrigation=payload.irrigation_method,
            water=payload.water_source,
        )
    return {"saved": True, "id": str(identifier)}


@router.put("/api/farms/{identifier}")
def update_farm(identifier: uuid.UUID, payload: FarmInput, owner: Owner):
    with db.connection(owner, write=True) as conn:
        owned(conn, "farms", identifier)
        curated_region(conn, payload.region_id)
        sql(
            conn,
            "UPDATE sv3.farms SET name=:name,region_id=:region,ownership_type=:ownership,irrigation_method=:irrigation,water_source=:water WHERE id=:id",
            id=identifier,
            name=payload.name,
            region=payload.region_id,
            ownership=payload.ownership_type,
            irrigation=payload.irrigation_method,
            water=payload.water_source,
        )
    return {"saved": True, "id": str(identifier)}


def delete_owned(table, identifier, owner):
    try:
        with db.connection(owner, write=True) as conn:
            owned(conn, table, identifier)
            sql(conn, f"DELETE FROM sv3.{table} WHERE id=:id", id=identifier)
    except IntegrityError as exc:
        raise HTTPException(
            409,
            "This record has associated history. Keep it or remove its empty child records first.",
        ) from exc
    return {"deleted": True, "id": str(identifier)}


@router.delete("/api/farms/{identifier}")
def delete_farm(identifier: uuid.UUID, owner: Owner):
    return delete_owned("farms", identifier, owner)


@router.get("/api/plots")
def plots(owner: Owner):
    with db.connection(owner) as conn:
        items = repository.rows(
            conn,
            "SELECT id,farm_id,name,plot_key,area_ha,latitude,longitude,boundary_geojson,soil_texture FROM sv3.plots ORDER BY plot_key",
        )
    return {"plots": items}


def write_plot(conn, owner, identifier, payload, create):
    owned(conn, "farms", payload.farm_id)
    params = {
        "id": identifier,
        "owner": owner,
        "key": "USER-PLOT-" + identifier.hex,
        "farm": payload.farm_id,
        "area": payload.area_ha,
        "lat": payload.latitude,
        "lon": payload.longitude,
        "boundary": json.dumps(payload.boundary_geojson)
        if payload.boundary_geojson
        else None,
        "soil": payload.soil_texture,
        "name": payload.name if "name" in payload.model_fields_set else None,
    }
    if create:
        sql(
            conn,
            "INSERT INTO sv3.plots(id,farmer_id,farm_id,plot_key,area_ha,latitude,longitude,boundary_geojson,soil_texture,name) VALUES(:id,:owner,:farm,:key,:area,:lat,:lon,CAST(:boundary AS jsonb),:soil,COALESCE(:name,''))",
            **params,
        )
    else:
        sql(
            conn,
            "UPDATE sv3.plots SET farm_id=:farm,area_ha=:area,latitude=:lat,longitude=:lon,boundary_geojson=CAST(:boundary AS jsonb),soil_texture=:soil,name=COALESCE(:name,name) WHERE id=:id",
            **params,
        )


@router.post("/api/plots")
def create_plot(payload: PlotInput, owner: Owner):
    identifier = uuid.uuid4()
    with db.connection(owner, write=True) as conn:
        onboarded(conn, owner)
        write_plot(conn, owner, identifier, payload, True)
    return {"saved": True, "id": str(identifier)}


@router.put("/api/plots/{identifier}")
def update_plot(identifier: uuid.UUID, payload: PlotInput, owner: Owner):
    with db.connection(owner, write=True) as conn:
        owned(conn, "plots", identifier)
        write_plot(conn, owner, identifier, payload, False)
    return {"saved": True, "id": str(identifier)}


@router.delete("/api/plots/{identifier}")
def delete_plot(identifier: uuid.UUID, owner: Owner):
    return delete_owned("plots", identifier, owner)


@router.get("/api/crop-cycles")
def cycles(owner: Owner):
    with db.connection(owner) as conn:
        items = repository.rows(
            conn,
            "SELECT cc.*,c.name AS crop_name FROM sv3.crop_cycles cc JOIN sv3.crops c ON c.id=cc.crop_id ORDER BY cc.sowing_date DESC",
        )
    return {"crop_cycles": items}


def write_cycle(conn, owner, identifier, payload, create):
    owned(conn, "plots", payload.plot_id)
    if not sql(
        conn, "SELECT id FROM sv3.crops WHERE id=:id", id=payload.crop_id
    ).scalar_one_or_none():
        raise HTTPException(422, "Select a known crop reference.")
    if (
        payload.variety_id
        and not sql(
            conn,
            "SELECT id FROM sv3.crop_varieties WHERE id=:id AND crop_id=:crop",
            id=payload.variety_id,
            crop=payload.crop_id,
        ).scalar_one_or_none()
    ):
        raise HTTPException(422, "The selected variety does not belong to this crop.")
    params = {
        "id": identifier,
        "owner": owner,
        "plot": payload.plot_id,
        "crop": payload.crop_id,
        "variety": payload.variety_id,
        "season": payload.season,
        "sow": payload.sowing_date,
        "expected": payload.expected_harvest_date,
        "actual": payload.actual_harvest_date,
        "status": payload.status,
    }
    if create:
        sql(
            conn,
            "INSERT INTO sv3.crop_cycles(id,farmer_id,plot_id,crop_id,variety_id,season,sowing_date,expected_harvest_date,actual_harvest_date,status) VALUES(:id,:owner,:plot,:crop,:variety,:season,:sow,:expected,:actual,:status)",
            **params,
        )
    else:
        sql(
            conn,
            "UPDATE sv3.crop_cycles SET plot_id=:plot,crop_id=:crop,variety_id=:variety,season=:season,sowing_date=:sow,expected_harvest_date=:expected,actual_harvest_date=:actual,status=:status WHERE id=:id",
            **params,
        )


@router.post("/api/crop-cycles")
def create_cycle(payload: CycleInput, owner: Owner):
    identifier = uuid.uuid4()
    with db.connection(owner, write=True) as conn:
        onboarded(conn, owner)
        write_cycle(conn, owner, identifier, payload, True)
    return {"saved": True, "id": str(identifier)}


@router.put("/api/crop-cycles/{identifier}")
def update_cycle(identifier: uuid.UUID, payload: CycleInput, owner: Owner):
    with db.connection(owner, write=True) as conn:
        owned(conn, "crop_cycles", identifier)
        write_cycle(conn, owner, identifier, payload, False)
    return {"saved": True, "id": str(identifier)}


@router.delete("/api/crop-cycles/{identifier}")
def delete_cycle(identifier: uuid.UUID, owner: Owner):
    return delete_owned("crop_cycles", identifier, owner)


@router.post("/api/stations/enroll")
def enroll(payload: Enrollment, owner: Owner):
    with db.connection(owner) as conn:
        onboarded(conn, owner)
        owned(conn, "plots", payload.plot_id)
    identifier = uuid.uuid4()
    key = secrets.token_urlsafe(32)
    station_key = "DEVICE-" + identifier.hex

    with db.connection(owner, write=True, ingest=True) as conn:
        if not sql(
            conn,
            "SELECT id FROM sv3.plots WHERE id=:plot AND farmer_id=:owner",
            plot=payload.plot_id,
            owner=owner,
        ).scalar_one_or_none():
            raise HTTPException(404, "Owned plot no longer exists.")
        provider = sql(
            conn,
            "INSERT INTO sv3.providers(code,name,homepage,access_method,attribution,status) VALUES('physical-device-enrollment','Farmer-enrolled physical devices','urn:skyview:physical-device','owned_device_enrollment','Farmer enrollment; measurements require authenticated device packets','active') ON CONFLICT(code) DO UPDATE SET status='active' RETURNING id",
        ).scalar_one()
        release = "physical-device-enrollment:" + str(date.today())
        lane = db.mode().removeprefix("v3_")

        sql(
            conn,
            "INSERT INTO sv3.datasets(provider_id,release_key,lane,origin,as_of_date,source_url) VALUES(:provider,:release,:lane,'user_reported',CURRENT_DATE,'urn:skyview:physical-device-enrollment') ON CONFLICT(release_key) DO NOTHING",
            provider=provider,
            release=release,
            lane=lane,
        )
        dataset = sql(
            conn,
            "SELECT id FROM sv3.datasets WHERE release_key=:release AND provider_id=:provider AND lane=:lane AND origin='user_reported' AND source_url='urn:skyview:physical-device-enrollment'",
            release=release,
            provider=provider,
            lane=lane,
        ).scalar_one_or_none()
        if dataset is None:
            raise HTTPException(
                409, "Device enrollment source does not match this workspace."
            )
        sql(
            conn,
            "INSERT INTO sv3.stations(id,farmer_id,plot_id,dataset_id,station_key,device_type,calibration,installed_at) VALUES(:id,:owner,:plot,:dataset,:key,'physical-pending',CAST(:metadata AS jsonb),now())",
            id=identifier,
            owner=owner,
            plot=payload.plot_id,
            dataset=dataset,
            key=station_key,
            metadata=json.dumps(
                {
                    "label": payload.device_label,
                    "physical_device_declared": True,
                    "calibration_status": "uncalibrated",
                    "connection_verified": False,
                }
            ),
        )
        sql(
            conn,
            "INSERT INTO sv3.device_credentials(station_id,farmer_id,key_hash) VALUES(:station,:owner,:hash)",
            station=identifier,
            owner=owner,
            hash=hashlib.sha256(key.encode()).hexdigest(),
        )
    return {
        "enrolled": True,
        "station_id": station_key,
        "id": str(identifier),
        "device_key": key,
        "connection_verified": False,
        "calibration_status": "uncalibrated",
        "device_key_shown_once": True,
        "protocol": {
            "endpoint": "/api/sensors/ingest",
            "authorization": "Device <device_key>",
            "station_id": station_key,
            "envelope": {
                "observed_at": "ISO8601 UTC actual sample time",
                "boot_id": "UUID generated once per device boot",
                "sequence": "monotonically increasing integer for each boot",
                "measurements": {
                    "temperature_c": "actual sensor measurement; omit absent metrics"
                },
            },
        },
        "note": "Enrollment does not establish a connection. Only accepted device packets create readings; calibrate before agronomic decisions. No watering action is performed.",
    }


@router.post("/api/stations/{identifier}/revoke")
def revoke(identifier: uuid.UUID, owner: Owner):
    with db.connection(owner, write=True) as conn:
        owned(conn, "stations", identifier)
        sql(
            conn,
            "UPDATE sv3.device_credentials SET revoked_at=now() WHERE station_id=:id",
            id=identifier,
        )
    return {"revoked": True}


@router.get("/api/soil-report/options")
def soil_options():
    with db.connection() as conn:
        definitions = repository.rows(
            conn,
            "SELECT * FROM sv3.measurement_definitions WHERE code=ANY(:codes) ORDER BY code",
            {"codes": list(SOIL_PROPERTIES)},
        )
    return {
        "parameters": definitions,
        "nutrient_basis_choices": {
            "nitrogen": ["available N"],
            "phosphorus": ["elemental P", "P2O5"],
            "potassium": ["elemental K", "K2O"],
        },
        "note": "Uploaded-report transcription remains farmer-reported until reviewed. Preserve units, depth and nutrient basis; no fertilizer dose is inferred.",
    }


@router.post("/api/soil-reports")
def soil_report(payload: SoilReport, owner: Owner):
    sample = uuid.uuid5(uuid.UUID(owner), "soil-report:" + str(payload.request_key))
    digest = hashlib.sha256(payload.model_dump_json().encode()).hexdigest()
    with db.connection(owner) as conn:
        onboarded(conn, owner)
        owned(conn, "plots", payload.plot_id)
        attachment = (
            sql(
                conn,
                "SELECT id,object_uri,scan_status,metadata FROM sv3.attachments WHERE id=:id",
                id=payload.attachment_id,
            )
            .mappings()
            .first()
        )
        if not attachment or attachment["scan_status"] != "clean":
            raise HTTPException(
                422,
                "Attach a readable owned soil report before confirming its numbers.",
            )
        existing = sql(
            conn, "SELECT report_metadata FROM sv3.soil_samples WHERE id=:id", id=sample
        ).scalar_one_or_none()
        if existing:
            if existing.get("request_hash") != digest:
                raise HTTPException(
                    409, "This request was already saved with different values."
                )
            return {
                "saved": True,
                "id": str(sample),
                "duplicate": True,
                "evidence_type": "farmer_report",
                "lab_verified": False,
            }
        for value in payload.values:
            definition = (
                sql(
                    conn,
                    "SELECT * FROM sv3.measurement_definitions WHERE code=:code",
                    code=value.property,
                )
                .mappings()
                .first()
            )
            if not definition or value.unit_code not in definition["allowed_units"]:
                raise HTTPException(
                    422, "Soil property and unit do not match the report catalog."
                )
            if (
                (
                    definition["minimum_value"] is not None
                    and value.value < definition["minimum_value"]
                )
                or (
                    definition["maximum_value"] is not None
                    and value.value > definition["maximum_value"]
                )
                or (value.unit_code == "percent" and value.value > 100)
            ):
                raise HTTPException(
                    422, "Soil value falls outside the accepted property range."
                )
    with db.connection(owner, write=True, ingest=True) as conn:
        provider = sql(
            conn,
            "INSERT INTO sv3.providers(code,name,homepage,access_method,attribution,status) VALUES('farmer-confirmed-soil-reports','Farmer-confirmed soil report transcriptions','urn:skyview:owned-soil-reports','farmer_upload','Owned user upload; not independent lab verification','active') ON CONFLICT(code) DO UPDATE SET status='active' RETURNING id",
        ).scalar_one()
        dataset = sql(
            conn,
            "INSERT INTO sv3.datasets(provider_id,release_key,lane,origin,as_of_date,source_url) VALUES(:provider,:release,:lane,'user_reported',CURRENT_DATE,'urn:skyview:owned-soil-reports') ON CONFLICT(release_key) DO NOTHING RETURNING id",
            provider=provider,
            release="soil-report:" + str(sample),
            lane=db.mode().removeprefix("v3_"),
        ).scalar_one_or_none()
        if dataset is None:
            dataset = sql(
                conn,
                "SELECT id FROM sv3.datasets WHERE release_key=:release",
                release="soil-report:" + str(sample),
            ).scalar_one()
    metadata = {
        "request_key": str(payload.request_key),
        "request_hash": digest,
        "attachment_id": str(payload.attachment_id),
        "values_confirmation": "farmer",
        "lab_verified": False,
        "original_bytes_unavailable": bool(
            attachment["metadata"].get("legacy_original_bytes_unavailable")
        ),
    }
    with db.connection(owner, write=True) as conn:
        sql(
            conn,
            "SELECT pg_advisory_xact_lock(hashtextextended(:key,0))",
            key=str(sample),
        )
        if not sql(
            conn,
            "SELECT id FROM sv3.attachments WHERE id=:id",
            id=payload.attachment_id,
        ).scalar_one_or_none():
            raise HTTPException(422, "The source report is no longer available.")
        existing = sql(
            conn, "SELECT report_metadata FROM sv3.soil_samples WHERE id=:id", id=sample
        ).scalar_one_or_none()
        if existing:
            if existing.get("request_hash") != digest:
                raise HTTPException(
                    409, "This request was already saved with different values."
                )
            return {
                "saved": True,
                "id": str(sample),
                "duplicate": True,
                "evidence_type": "farmer_report",
                "lab_verified": False,
            }
        sql(
            conn,
            "INSERT INTO sv3.soil_samples(id,farmer_id,plot_id,dataset_id,sampled_on,sample_type,lab_name,report_uri,report_metadata) VALUES(:id,:owner,:plot,:dataset,:day,'farmer_report',:lab,:uri,CAST(:metadata AS jsonb))",
            id=sample,
            owner=owner,
            plot=payload.plot_id,
            dataset=dataset,
            day=payload.sampled_on,
            lab=payload.reported_lab_name,
            uri=attachment["object_uri"],
            metadata=json.dumps(metadata),
        )
        for value in payload.values:
            sql(
                conn,
                "INSERT INTO sv3.soil_indicators(id,farmer_id,plot_id,sample_id,dataset_id,property,depth_top_cm,depth_bottom_cm,unit_code,mean_value,evidence_type,reported_basis) VALUES(:id,:owner,:plot,:sample,:dataset,:property,:top,:bottom,:unit,:value,'farmer_report',:basis)",
                id=uuid.uuid5(
                    sample,
                    f"{value.property}:{value.depth_top_cm}:{value.depth_bottom_cm}",
                ),
                owner=owner,
                plot=payload.plot_id,
                sample=sample,
                dataset=dataset,
                property=value.property,
                top=value.depth_top_cm,
                bottom=value.depth_bottom_cm,
                unit=value.unit_code,
                value=value.value,
                basis=value.reported_basis,
            )
    return {
        "saved": True,
        "id": str(sample),
        "duplicate": False,
        "evidence_type": "farmer_report",
        "lab_verified": False,
        "parameter_count": len(payload.values),
    }


@router.get("/api/soil-reports")
def soil_reports(owner: Owner):
    with db.connection(owner) as conn:
        samples = repository.rows(
            conn,
            "SELECT id,plot_id,sampled_on,sample_type,lab_name,report_metadata FROM sv3.soil_samples ORDER BY sampled_on DESC LIMIT 100",
        )
        values = repository.rows(
            conn,
            "SELECT id,plot_id,sample_id,property,depth_top_cm,depth_bottom_cm,unit_code,mean_value,evidence_type,reported_basis FROM sv3.soil_indicators WHERE sample_id IN (SELECT id FROM sv3.soil_samples ORDER BY sampled_on DESC LIMIT 100) ORDER BY property",
        )
    return {"samples": samples, "values": values}


@router.post("/api/farms/{identifier}/weather-link")
def link_weather(identifier: uuid.UUID, payload: WeatherLink, owner: Owner):
    with db.connection(owner) as conn:
        onboarded(conn, owner)
        farm = owned(conn, "farms", identifier)
        plot = owned(conn, "plots", payload.plot_id)
        if plot["farm_id"] != identifier:
            raise HTTPException(422, "Select a plot from this farm.")
        step = Decimal("0.25")
        lat = (Decimal(plot["latitude"]) / step).quantize(
            Decimal(1), rounding=ROUND_HALF_UP
        ) * step
        lon = (Decimal(plot["longitude"]) / step).quantize(
            Decimal(1), rounding=ROUND_HALF_UP
        ) * step
    key = f"weather-grid:0.25:{lat:.2f}:{lon:.2f}"
    lane = db.mode().removeprefix("v3_")
    with db.connection(owner, write=True, ingest=True) as conn:
        provider = sql(
            conn,
            "INSERT INTO sv3.providers(code,name,homepage,access_method,attribution,status) VALUES('farmer-selected-coarse-weather-grid','Farmer-selected coarse weather grid','urn:skyview:consented-weather-grid','explicit_farmer_consent','User-selected grid snapped to 0.25 degrees; not exact farm coordinates or official geography','active') ON CONFLICT(code) DO UPDATE SET status='active' RETURNING id",
        ).scalar_one()
        dataset = sql(
            conn,
            "INSERT INTO sv3.datasets(provider_id,release_key,lane,origin,as_of_date,source_url) VALUES(:provider,:release,:lane,'user_reported',CURRENT_DATE,'urn:skyview:consented-weather-grid') ON CONFLICT(release_key) DO NOTHING RETURNING id",
            provider=provider,
            release="consented-weather-grid:v1:" + lane,
            lane=lane,
        ).scalar_one_or_none()
        if dataset is None:
            dataset = sql(
                conn,
                "SELECT id FROM sv3.datasets WHERE release_key=:release",
                release="consented-weather-grid:v1:" + lane,
            ).scalar_one()
        location = sql(
            conn,
            "INSERT INTO sv3.locations(dataset_id,region_id,location_key,label,latitude,longitude,resolution_m) VALUES(:dataset,:region,:key,'Coarse weather grid (0.25 degrees)',:lat,:lon,25000) ON CONFLICT(dataset_id,location_key) DO UPDATE SET resolution_m=25000 RETURNING id",
            dataset=dataset,
            region=farm["region_id"],
            key=key,
            lat=lat,
            lon=lon,
        ).scalar_one()
    with db.connection(owner, write=True) as conn:
        owned(conn, "farms", identifier)
        current_plot = owned(conn, "plots", payload.plot_id)
        if (
            current_plot["farm_id"] != identifier
            or current_plot["latitude"] != plot["latitude"]
            or current_plot["longitude"] != plot["longitude"]
        ):
            raise HTTPException(
                409, "The plot changed during linking. Refresh and try again."
            )
        sql(
            conn,
            "UPDATE sv3.farms SET location_id=:location WHERE id=:id",
            location=location,
            id=identifier,
        )
        evidence = json.dumps(
            {
                "farm_id": str(identifier),
                "plot_id": str(payload.plot_id),
                "grid_key": key,
                "purpose": "weather_grid_lookup",
            },
            sort_keys=True,
        )
        sql(
            conn,
            "INSERT INTO sv3.consents(farmer_id,purpose,granted_at,evidence_hash) VALUES(:owner,'weather_grid_lookup',now(),:hash)",
            owner=owner,
            hash=hashlib.sha256(evidence.encode()).hexdigest(),
        )
    from skyview.data.v3.worker import notify_weather_link

    notify_weather_link()
    return {
        "linked": True,
        "farm_id": str(identifier),
        "location_id": str(location),
        "coarse_grid": {
            "latitude": float(lat),
            "longitude": float(lon),
            "step_degrees": 0.25,
            "resolution_m": 25000,
        },
        "lookup_requested": True,
        "sharing_scope": "Account weather-grid lookup; no exact plot coordinates are sent",
        "note": "The worker may request weather for this coarse grid. Linking itself does not create weather readings or a forecast.",
    }


@router.delete("/api/farms/{identifier}/weather-link")
def unlink_weather(identifier: uuid.UUID, owner: Owner):
    with db.connection(owner, write=True) as conn:
        owned(conn, "farms", identifier)
        sql(conn, "UPDATE sv3.farms SET location_id=NULL WHERE id=:id", id=identifier)
        sql(
            conn,
            "UPDATE sv3.consents SET revoked_at=now() WHERE purpose='weather_grid_lookup' AND revoked_at IS NULL",
        )
    return {
        "unlinked": True,
        "future_account_grid_lookups_disabled": True,
        "history_preserved": True,
        "note": "Weather-sharing consent was revoked for this account. Other linked farms need new consent before additional grid lookups.",
    }
