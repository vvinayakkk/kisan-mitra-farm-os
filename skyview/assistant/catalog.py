"""Version actual runtime skill files and validated tool schemas, not demo catalogs."""

import hashlib
import json
import threading

from sqlalchemy import text

from skyview.data.v3 import db

_lock = threading.Lock()
_registered = set()


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def definitions():
    from pathlib import Path

    from .tools import SKILLS, SKILLS_DIR, TOOLS

    root = Path(__file__).resolve().parents[2]
    dependencies = (
        "skyview/assistant/tools.py",
        "skyview/assistant/mission_execution.py",
        "skyview/assistant/document_vision.py",
        "skyview/api/v3_farm_workflow_routes.py",
        "skyview/api/v3_shared_work_routes.py",
        "skyview/api/v3_exchange_routes.py",
        "skyview/assistant/weather_tools.py",
        "skyview/assistant/reference_tools.py",
        "skyview/assistant/planning_tools.py",
        "skyview/assistant/models.py",
        "skyview/assistant/data_sources.py",
        "skyview/assistant/artifacts.py",
        "skyview/assistant/attachments.py",
        "skyview/assistant/memory.py",
        "skyview/assistant/memory_facts.py",
        "skyview/assistant/provider.py",
        "skyview/assistant/v3_store.py",
        "skyview/assistant/catalog.py",
        "skyview/agents/disease_service.py",
        "skyview/data/v3/repository.py",
    )
    implementation_hash = hashlib.sha256(
        _json(
            {
                path: hashlib.sha256((root / path).read_bytes()).hexdigest()
                for path in dependencies
                if (root / path).is_file()
            }
        ).encode()
    ).hexdigest()

    skills = []
    for code, description in SKILLS.items():
        workflow = (SKILLS_DIR / f"{code}.md").read_text()
        digest = hashlib.sha256(workflow.encode()).hexdigest()
        skills.append(
            {
                "code": code,
                "version": "runtime-" + digest[:20],
                "title": description[0],
                "description": description[1],
                "workflow": workflow,
                "hash": digest,
            }
        )
    tools = []
    for code, tool in TOOLS.items():
        arguments = tool.arguments.model_json_schema()
        effect = (
            "artifact"
            if code in {"create_file", "revise_file", "diagnose_crop"}
            else "write"
            if tool.approval
            else "read"
        )
        material = {
            "arguments": arguments,
            "description": tool.description,
            "effect": effect,
            "requires_approval": tool.approval,
            "implementation_sha256": implementation_hash,
        }
        digest = hashlib.sha256(_json(material).encode()).hexdigest()
        tools.append(
            {
                "code": code,
                "version": "runtime-" + digest[:20],
                "title": tool.label,
                "arguments": arguments,
                "effect": effect,
                "approval": tool.approval,
            }
        )
    fingerprint = hashlib.sha256(
        _json({"skills": skills, "tools": tools}).encode()
    ).hexdigest()
    return skills, tools, fingerprint


def sync_runtime_catalog():
    if not db.enabled():
        return {"skills": 0, "tools": 0, "mode": "legacy"}
    skills, tools, fingerprint = definitions()

    engine_url = db.engine().url
    database_key = (
        engine_url.host,
        engine_url.port,
        engine_url.database,
        db.mode(),
        fingerprint,
    )
    with _lock:
        if database_key in _registered:
            return {"skills": len(skills), "tools": len(tools), "changed": False}
        with db.connection(write=True, ingest=True) as conn:
            conn.execute(
                text(
                    "SELECT pg_advisory_xact_lock(hashtextextended('skyview-runtime-catalog',0))"
                )
            )
            conn.execute(
                text(
                    "UPDATE sv3.skill_versions SET active=false WHERE active AND code<>ALL(:codes)"
                ),
                {"codes": [s["code"] for s in skills]},
            )
            conn.execute(
                text(
                    "UPDATE sv3.tool_versions SET active=false WHERE active AND code<>ALL(:codes)"
                ),
                {"codes": [t["code"] for t in tools]},
            )
            for item in tools:
                conn.execute(
                    text(
                        "UPDATE sv3.tool_versions SET active=false WHERE code=:code AND version<>:version"
                    ),
                    item,
                )
                conn.execute(
                    text(
                        "INSERT INTO sv3.tool_versions(code,version,title,arguments_schema,output_schema,effect,requires_approval,active) VALUES(:code,:version,:title,CAST(:arguments AS jsonb),CAST(:output AS jsonb),:effect,:approval,true) ON CONFLICT(code,version) DO UPDATE SET active=true"
                    ),
                    {
                        **item,
                        "arguments": _json(item["arguments"]),
                        "output": _json(
                            {
                                "type": "object",
                                "additionalProperties": True,
                                "description": "Source-specific result envelope; integrations validate their own fields.",
                            }
                        ),
                    },
                )
            for item in skills:
                conn.execute(
                    text(
                        "UPDATE sv3.skill_versions SET active=false WHERE code=:code AND version<>:version"
                    ),
                    item,
                )
                conn.execute(
                    text(
                        "INSERT INTO sv3.skill_versions(code,version,title,farmer_description,workflow,workflow_hash,allowed_tools,active) VALUES(:code,:version,:title,:description,:workflow,:hash,CAST(:allowed AS jsonb),true) ON CONFLICT(code,version) DO UPDATE SET active=true"
                    ),
                    {**item, "allowed": _json([t["code"] for t in tools])},
                )
        _registered.add(database_key)
    return {"skills": len(skills), "tools": len(tools), "changed": True}


def runtime_version_bindings():
    """Pin this worker's exact definitions even when another deployment becomes active."""
    skills, tools, _fingerprint = definitions()
    return {
        "tools": {t["code"]: t["version"] for t in tools},
        "skills": {s["code"]: s["version"] for s in skills},
    }
