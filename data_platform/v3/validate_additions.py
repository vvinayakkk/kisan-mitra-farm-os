"""Focused integrity regressions for the in-depth review."""


def extend(query, assertq, rejects, rls_count, farmer, other):
    assertq("Demo hierarchy populated", "SELECT count(*) FROM sv3.regions;", 144)
    assertq(
        "Farms linked to fictional village hierarchy",
        "SELECT count(*) FROM sv3.farms f JOIN sv3.regions r ON r.id=f.region_id WHERE r.level='village' AND r.code_system='DEMO';",
        400,
    )
    assertq(
        "Every plot has all 12 SHC properties",
        "SELECT count(*) FROM (SELECT plot_id FROM sv3.soil_indicators WHERE property IN ('ph','ec','organic_carbon','nitrogen','phosphorus','potassium','sulphur','zinc','iron','copper','manganese','boron') GROUP BY plot_id HAVING count(distinct property)=12) p;",
        800,
    )
    assertq(
        "All soil moisture sensors labeled relative uncalibrated",
        "SELECT count(*) FROM sv3.station_sensors WHERE metric='soil_moisture' AND measurement_basis='relative_demo_percent' AND calibration->>'calibrated_for_vwc'='false';",
        80,
    )
    assertq(
        "Registry contains current 11 skills and 19 tools",
        "SELECT (SELECT count(*) FROM sv3.skill_versions)||','||(SELECT count(*) FROM sv3.tool_versions);",
        "11,19",
    )
    assertq(
        "Tool registry is not implicitly enabled",
        "SELECT count(*) FROM sv3.tool_versions WHERE active;",
        0,
    )
    assertq(
        "Sales net arithmetic is decimal and correct",
        "SELECT count(*) FROM sv3.sale_records WHERE gross_inr=23000 AND net_inr=22350;",
        400,
    )
    rls_count("question_requests", "", 1)
    rls_count("sale_records", "", 1)
    rls_count("attachments", "", 1)
    rejects(
        "Direct partition access denied",
        "SET LOCAL ROLE sv3_app; SELECT * FROM sv3.sensor_packets_2026_10 LIMIT 1",
        "permission denied",
    )
    rejects(
        "Raw ingest log access denied",
        "SET LOCAL ROLE sv3_app; SELECT * FROM sv3.raw_objects",
        "permission denied",
    )
    rejects(
        "Soil pH cannot be recorded as a percentage",
        "UPDATE soil_indicators SET unit_code='percent' WHERE property='ph'",
        "Incompatible soil property unit",
    )
    rejects(
        "pH outside physical bounds rejected",
        "UPDATE soil_indicators SET mean_value=15 WHERE property='ph'",
        "outside property bounds",
    )
    rejects(
        "Negative particle measurement rejected",
        "UPDATE sensor_packets SET pm25_ug_m3=-1 WHERE observed_at=(SELECT min(observed_at) FROM sensor_packets)",
        "check constraint",
    )
    rejects(
        "Sale cannot exceed recorded stock",
        "UPDATE sale_records SET quantity=21",
        "exceeds recorded harvest stock",
    )
    rejects(
        "Sale unit mismatch rejected",
        "UPDATE sale_records SET unit_code='kg'",
        "units differ",
    )
    rejects(
        "Sale before harvest rejected",
        "UPDATE sale_records SET sold_on='2025-01-01'",
        "Sale precedes harvest",
    )
    rejects(
        "Cross-owner question answer rejected",
        f"UPDATE question_answers SET farmer_id='{other}' WHERE farmer_id='{farmer}'",
        "foreign key constraint",
    )
    rejects(
        "Duplicate public progress event rejected",
        "INSERT INTO run_events SELECT gen_random_uuid(),farmer_id,run_id,sequence,event_type,payload,occurred_at FROM run_events LIMIT 1",
        "duplicate key",
    )
    rejects(
        "Synthetic data cannot become a validated real forecast",
        "UPDATE model_versions SET status='validated'; INSERT INTO forecast_runs(id,dataset_id,model_id,issued_at,training_cutoff,horizon_days,kind) SELECT '00000000-0000-0000-0000-000000000222',dataset_id,model_id,issued_at,training_cutoff,horizon_days,'forecast' FROM forecast_runs LIMIT 1; INSERT INTO price_projections SELECT '00000000-0000-0000-0000-000000000222',series_id,valid_on,'forecast',lower_price,central_price,upper_price,interval_definition FROM price_projections LIMIT 1",
        "Synthetic data cannot produce real forecasts",
    )
    rejects(
        "Demo cannot send external notifications",
        f"INSERT INTO notifications(farmer_id,channel,delivery_allowed,scheduled_at,status,payload,dedupe_key) VALUES('{farmer}','email',true,now(),'queued','{{}}','test-external')",
        "Demo cannot deliver external messages",
    )
    assertq(
        "Task version increments once on edit",
        f"BEGIN; UPDATE sv3.tasks SET title=title WHERE farmer_id='{farmer}'; SELECT min(row_version) FROM sv3.tasks WHERE farmer_id='{farmer}'; ROLLBACK;",
        "BEGIN\nUPDATE 6\n2\nROLLBACK",
    )

    assertq(
        "Correction preserves history and one current memory",
        f"BEGIN; SET search_path=sv3,public; UPDATE memories SET valid_to=valid_from+interval '1 minute' WHERE farmer_id='{farmer}'; INSERT INTO memories(farmer_id,fact_key,value,evidence_message_id,confidence,valid_from,supersedes_id,search_text) SELECT farmer_id,fact_key,'{{\"synthetic\":true,\"corrected\":true}}',evidence_message_id,1,valid_to,id,'Corrected synthetic fixture' FROM memories WHERE farmer_id='{farmer}'; SELECT count(*) FROM current_memories WHERE farmer_id='{farmer}'; ROLLBACK;",
        "BEGIN\nSET\nUPDATE 1\nINSERT 0 1\n1\nROLLBACK",
    )

    setup = f"""INSERT INTO tool_calls(id,farmer_id,run_id,call_key,tool_name,arguments,status) SELECT '00000000-0000-0000-0000-000000000333','{farmer}',id,'test-pump','demo-pump','{{}}','waiting_approval' FROM agent_runs WHERE farmer_id='{farmer}' LIMIT 1;
    INSERT INTO approvals(id,farmer_id,tool_call_id,arguments_hash,decision,decided_at,expires_at) VALUES('00000000-0000-0000-0000-000000000444','{farmer}','00000000-0000-0000-0000-000000000333','test-hash','approved',now(),now()+interval '1 hour');
    """
    insert = f"""INSERT INTO device_commands(farmer_id,station_id,tool_call_id,approval_id,command,arguments_hash,payload,mode,status,expires_at,execution_key) SELECT '{farmer}',id,'00000000-0000-0000-0000-000000000333','00000000-0000-0000-0000-000000000444','demo-pump','test-hash','{{}}','live','queued',now()+interval '10 minutes','test-command' FROM stations WHERE farmer_id='{farmer}' LIMIT 1"""
    rejects(
        "Mock station cannot receive live commands",
        setup + insert,
        "Command mode must match station data lane",
    )
    rejects(
        "Hardware intent requires matching approval hash",
        setup
        + insert.replace("'live'", "'demo'").replace(
            "'demo-pump','test-hash'", "'demo-pump','wrong-hash'"
        ),
        "matching unexpired approval",
    )

    rls_count("sensor_packets", f"WHERE farmer_id='{other}'", 0)

    rejects(
        "Mandi unit cannot be temperature",
        "UPDATE market_series SET unit_code='celsius'",
        "Market price requires mass or count unit",
    )
    rejects(
        "Harvest reduction cannot invalidate sales",
        "UPDATE harvest_batches SET quantity=5",
        "Harvest edit conflicts with recorded sales",
    )
    own_station = query(
        f"SELECT id FROM sv3.stations WHERE farmer_id='{farmer}' LIMIT 1;"
    ).stdout.strip()
    signed_setup = setup.replace(
        "'test-hash','approved'",
        f"sv3.command_argument_hash('{own_station}','demo-pump','demo','{{}}'),'approved'",
    )
    signed_insert = insert.replace("'live'", "'demo'").replace(
        "'demo-pump','test-hash'",
        f"'demo-pump',sv3.command_argument_hash('{own_station}','demo-pump','demo','{{}}')",
    )
    assertq(
        "Approved demo command intent accepted without executing hardware",
        "BEGIN; SET search_path=sv3,public; "
        + signed_setup
        + signed_insert
        + "; SELECT count(*) FROM device_commands; ROLLBACK;",
        "BEGIN\nSET\nINSERT 0 1\nINSERT 0 1\nINSERT 0 1\n1\nROLLBACK",
    )
    rejects(
        "Changed payload cannot reuse old approval",
        signed_setup
        + signed_insert
        + "; UPDATE device_commands SET payload='{\"duration_seconds\":999}'",
        "Command payload does not match approved intent",
    )

    rejects(
        "Real-labeled weather cannot exceed supported daily horizon",
        "INSERT INTO datasets(id,provider_id,release_key,lane,origin,as_of_date,source_url) SELECT '00000000-0000-0000-0000-000000000777',provider_id,'test-weather-horizon','demo','modeled',as_of_date,'demo://test-only' FROM datasets LIMIT 1; INSERT INTO weather_forecasts(dataset_id,series_id,issued_at,valid_on,kind,method) SELECT '00000000-0000-0000-0000-000000000777',id,'2026-10-14','2027-10-14','forecast','test fixture only' FROM weather_series LIMIT 1",
        "Daily weather forecast exceeds configured model lead",
    )
