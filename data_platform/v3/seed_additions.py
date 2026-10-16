"""Deterministic review fixtures; all belong to the synthetic release."""

import hashlib
import json
from datetime import timedelta
from pathlib import Path

HERE = Path(__file__).parent


def extend(add, uid, rng, dataset, asof, created, farmers, plots, cycle_ids, regions):
    for code, dim, sym, factor in [
        ("kg_ha", "mass_area", "kg/ha", 0.0001),
        ("mgkg", "mass_fraction", "mg/kg", 0.000001),
        ("ds_m", "conductivity", "dS/m", 0.1),
        ("g_cm3", "density", "g/cm³", 1000),
        ("liter", "volume", "L", 0.001),
        ("hectare", "area", "ha", 10000),
        ("acre", "area", "ac", 4046.8564224),
        ("nuts100", "count", "100 nuts", 100),
        ("vwc_pct", "volumetric_ratio", "% v/v", 0.01),
        ("cmol_kg", "exchange_capacity", "cmol(+)/kg", None),
    ]:
        add("units", code=code, dimension=dim, symbol=sym, factor_to_base=factor)
    properties = [
        ("ph", "pH", "hydrogen activity", ["ph"], 0, 14, 6.7),
        (
            "organic_carbon",
            "Organic carbon",
            "organic carbon, not organic matter",
            ["gkg", "percent"],
            0,
            1000,
            12,
        ),
        ("clay", "Clay", "particle mass fraction", ["percent"], 0, 100, 30),
        (
            "nitrogen",
            "Available nitrogen",
            "lab method; element N",
            ["kg_ha", "mgkg"],
            0,
            None,
            160,
        ),
        (
            "phosphorus",
            "Available phosphorus",
            "report basis must specify elemental P or P2O5",
            ["kg_ha", "mgkg"],
            0,
            None,
            20,
        ),
        (
            "potassium",
            "Available potassium",
            "report basis must specify elemental K or K2O",
            ["kg_ha", "mgkg"],
            0,
            None,
            180,
        ),
        (
            "sulphur",
            "Available sulphur",
            "lab extractable sulphur",
            ["mgkg"],
            0,
            None,
            15,
        ),
        ("zinc", "Zinc", "lab extractable Zn", ["mgkg"], 0, None, 1.2),
        ("iron", "Iron", "lab extractable Fe", ["mgkg"], 0, None, 8),
        ("copper", "Copper", "lab extractable Cu", ["mgkg"], 0, None, 1),
        ("manganese", "Manganese", "lab extractable Mn", ["mgkg"], 0, None, 4),
        ("boron", "Boron", "lab extractable B", ["mgkg"], 0, None, 0.8),
        (
            "ec",
            "Electrical conductivity",
            "report extraction ratio/temperature required",
            ["ds_m"],
            0,
            None,
            0.7,
        ),
    ]
    grid_definitions = [
        (
            "total_nitrogen",
            "Total nitrogen",
            "total nitrogen, not plant-available nitrogen",
            ["gkg"],
            0,
            None,
        ),
        (
            "cec",
            "Cation exchange capacity",
            "cmol of charge per kg",
            ["cmol_kg"],
            0,
            None,
        ),
        ("sand", "Sand", "particle mass fraction", ["percent"], 0, 100),
        ("silt", "Silt", "particle mass fraction", ["percent"], 0, 100),
        (
            "coarse_fragments",
            "Coarse fragments",
            "volume fraction",
            ["percent"],
            0,
            100,
        ),
        ("bulk_density", "Bulk density", "dry soil mass per volume", ["g_cm3"], 0, 3),
        (
            "field_capacity",
            "Field capacity",
            "volumetric water content, not relative sensor %",
            ["vwc_pct"],
            0,
            100,
        ),
        (
            "wilting_point",
            "Wilting point",
            "volumetric water content, not relative sensor %",
            ["vwc_pct"],
            0,
            100,
        ),
    ]
    for code, name, basis, units, minimum, maximum in grid_definitions:
        add(
            "measurement_definitions",
            code=code,
            name=name,
            basis=basis,
            allowed_units=units,
            minimum_value=minimum,
            maximum_value=maximum,
            interpretation="Preserve provider scale/offset, depth, method and uncertainty. Never substitute total nitrogen for available N or relative moisture for VWC.",
        )
    for code, name, basis, units, minimum, maximum, base in properties:
        add(
            "measurement_definitions",
            code=code,
            name=name,
            basis=basis,
            allowed_units=units,
            minimum_value=minimum,
            maximum_value=maximum,
            interpretation="Keep raw report method, extraction ratio and nutrient basis. kg/ha cannot be converted to mg/kg without sampled depth and bulk density. This catalog supplies semantics, not fertilizer dosage.",
        )
    for pid, fid, idx in plots:
        sample = uid("soil:" + pid)
        for code, name, basis, units, minimum, maximum, base in properties[3:]:
            value = round(base * (1 + rng.uniform(-0.15, 0.15)), 4)
            add(
                "soil_indicators",
                id=uid(f"soil:{pid}:{code}"),
                farmer_id=fid,
                plot_id=pid,
                sample_id=sample,
                dataset_id=dataset,
                property=code,
                depth_top_cm=0,
                depth_bottom_cm=15,
                unit_code=units[0],
                mean_value=value,
                lower_value=None,
                upper_value=None,
                evidence_type="synthetic",
            )
        add(
            "soil_calibrations",
            id=uid("soil-calibration:" + pid),
            farmer_id=fid,
            plot_id=pid,
            dataset_id=dataset,
            measured_on=asof - timedelta(days=40),
            depth_top_cm=0,
            depth_bottom_cm=30,
            field_capacity_vwc_pct=32,
            wilting_point_vwc_pct=12,
            bulk_density_g_cm3=1.3,
            method="Synthetic fixture: not a field/lab measurement",
            evidence_type="synthetic",
        )
    add(
        "source_health",
        provider_id=uid("provider:demo"),
        scope_key="demo-generation",
        checked_at=created,
        last_success_at=created,
        source_valid_through=asof,
        status="healthy",
        retry_after=None,
        safe_error=None,
    )
    add(
        "source_health",
        provider_id=uid("provider:demo"),
        scope_key="demo-outage-fixture",
        checked_at=created,
        last_success_at=f"{asof - timedelta(days=3)}T00:00:00+00:00",
        source_valid_through=asof - timedelta(days=3),
        status="outage",
        retry_after=f"{asof}T01:00:00+00:00",
        safe_error="Simulated upstream outage; no source network call made",
    )

    for code, name, lang, lat, lon, mix in regions:
        parent = uid("region:" + code)
        for level in ["district", "block", "village"]:
            rid = uid(level + ":" + code)
            add(
                "regions",
                id=rid,
                dataset_id=dataset,
                parent_id=parent,
                level=level,
                code_system="DEMO",
                code=f"DEMO-{level.upper()}-{code}",
                name=f"{name} fictional {level}",
                valid_from=asof - timedelta(days=365),
                valid_to=None,
            )
            parent = rid
    registry = json.loads((HERE / "catalog/agent-catalog.json").read_text())
    for skill in registry["skills"]:
        add(
            "skill_versions",
            id=uid("skill:" + skill["code"]),
            code=skill["code"],
            version="app-snapshot-v1",
            title=skill["title"],
            farmer_description=skill["description"],
            workflow=skill["workflow"],
            workflow_hash=skill["workflow_hash"],
            allowed_tools=skill["allowed_tools"],
            active=False,
        )
    for tool in registry["tools"]:
        add(
            "tool_versions",
            id=uid("tool:" + tool["code"]),
            code=tool["code"],
            version="app-snapshot-v1",
            title=tool["title"],
            arguments_schema=tool["arguments_schema"],
            output_schema={
                "description": "Validate using the bound runtime handler before enabling this tool"
            },
            effect=tool["effect"],
            requires_approval=tool["requires_approval"],
            active=False,
        )
    for n, fid in enumerate(farmers):
        conv = uid(f"conversation:{n}")
        run = uid(f"review-run:{n}")
        question = uid(f"question:{n}")
        attachment = uid(f"attachment:{n}")
        add(
            "attachments",
            id=attachment,
            farmer_id=fid,
            message_id=uid(f"message:{n}"),
            object_uri=f"demo://unavailable/input/{n}.jpg",
            original_name="demo-photo-placeholder.jpg",
            mime_type="image/jpeg",
            bytes=128,
            checksum=hashlib.sha256(f"demo-placeholder-{n}".encode()).hexdigest(),
            scan_status="pending",
            extracted_text=None,
            metadata={
                "synthetic": True,
                "placeholder": True,
                "actual_file_exists": False,
            },
            created_at=created,
        )
        add(
            "field_observations",
            id=uid(f"field-note:{n}"),
            farmer_id=fid,
            cycle_id=cycle_ids[fid],
            observed_at=created,
            type="crop_stage",
            observation={
                "stage": "unknown",
                "requires_farmer_confirmation": True,
                "synthetic": True,
            },
            attachment_id=None,
            origin="synthetic",
        )
        # Harvest belongs to the previous cycle, not the still-growing current crop.
        batch = uid(f"batch:{n}")
        previous = uid(f"cycle:{n}:0:0")
        add(
            "harvest_batches",
            id=batch,
            farmer_id=fid,
            cycle_id=previous,
            harvested_on=asof - timedelta(days=90),
            quantity=20,
            unit_code="quintal",
            grade="demo-unspecified",
            moisture_pct=None,
            quality_evidence={"synthetic": True, "assayed": False},
            storage_notes="Demo stock; not verified warehouse inventory",
            execution_key=f"demo-batch-{n}",
        )
        add(
            "sale_records",
            id=uid(f"sale:{n}"),
            farmer_id=fid,
            batch_id=batch,
            sold_on=asof - timedelta(days=80),
            quantity=10,
            unit_code="quintal",
            unit_price_inr=2300,
            selling_cost_inr=650,
            payment_status="demo",
            receipt_uri=None,
            execution_key=f"demo-sale-{n}",
        )
        add(
            "agent_runs",
            id=run,
            farmer_id=fid,
            conversation_id=conv,
            request_key=f"demo-run-{n}",
            status="completed" if n % 2 == 0 else "waiting_input",
            lease_expires_at=None,
            started_at=created,
            ended_at=created if n % 2 == 0 else None,
            model_name="demo-fixture-no-model-called",
        )
        add(
            "question_requests",
            id=question,
            farmer_id=fid,
            run_id=run,
            tool_call_id=None,
            prompt="Demo question: which irrigation method do you use?",
            form_schema={
                "type": "object",
                "properties": {
                    "irrigation": {
                        "type": "string",
                        "enum": ["rainfed", "drip", "sprinkler", "surface"],
                    }
                },
                "required": ["irrigation"],
                "additionalProperties": False,
            },
            status="answered" if n % 2 == 0 else "waiting",
            expires_at=f"{asof + timedelta(days=30)}T00:00:00+00:00",
            created_at=created,
        )
        events = [
            ("started", {"synthetic": True}),
            (
                "question",
                {
                    "question_id": question,
                    "status": "answered" if n % 2 == 0 else "waiting",
                },
            ),
        ]
        if n % 2 == 0:
            add(
                "question_answers",
                id=uid(f"answer:{n}"),
                farmer_id=fid,
                question_id=question,
                answer_version=1,
                answers={
                    "irrigation": ["rainfed", "drip", "sprinkler", "surface"][n % 4]
                },
                submitted_at=created,
                execution_key=f"demo-answer-{n}",
            )
            events.append(
                (
                    "completed",
                    {
                        "synthetic": True,
                        "result": "Demo answers persisted; no farm action executed",
                    },
                )
            )
        for seq, (kind, payload) in enumerate(events, 1):
            add(
                "run_events",
                id=uid(f"event:{n}:{seq}"),
                farmer_id=fid,
                run_id=run,
                sequence=seq,
                event_type=kind,
                payload=payload,
                occurred_at=created,
            )
        add(
            "context_compactions",
            id=uid(f"compaction:{n}"),
            farmer_id=fid,
            conversation_id=conv,
            first_sequence=1,
            last_sequence=1,
            summary="Synthetic onboarding fixture; no actual decisions made",
            pending_work={"question_id": question} if n % 2 else {},
            tokens_before=10,
            tokens_after=5,
            method_version="demo-checkpoint-v1",
            created_at=created,
        )
        if n < 80:
            station = uid("station:" + plots[n][0])
            owner = plots[n][1]
            add(
                "alert_events",
                id=uid(f"alert:{n}"),
                farmer_id=owner,
                dataset_id=dataset,
                station_id=station,
                source_key=f"demo-alert-{n}",
                category="demo low battery" if n % 2 else "demo stale station",
                severity="watch",
                message="Simulated warning for interface testing only",
                source_url="demo://alerts",
                issued_at=created,
                expires_at=f"{asof + timedelta(days=1)}T00:00:00+00:00",
                acknowledged_at=None,
                status="active",
            )
    # A real-memory correction fixture: original current fact expires and new fact cites same own message.
    # Existing CSV rows are not modified here; correction behavior is tested transactionally.
