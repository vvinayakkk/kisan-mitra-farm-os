"""Populate fictional sharing resources in the existing demo database, never live.

Default is a dry run. --apply adds stable UUID resources/notices for 400 existing
synthetic demo farmers. Existing edited notices/resources and profiles survive reruns.
No contacts, chats, agreements or completed exchanges are fabricated.
"""

import argparse
import json
import re
import uuid
from collections import Counter

from provision import sql

NAMESPACE = uuid.UUID("d8446e37-e9e7-408d-a382-bcbe3c42b6b8")
DATABASE = "skyview_v3_demo"
CATALOG = [
    ("Tractor", "equipment", 1, "machine"),
    ("Sprayer", "equipment", 1, "machine"),
    ("Harvesting labour", "labour", 2, "days"),
    ("Farm transport", "transport", 1, "trip"),
]


def identifier(key):
    return str(uuid.uuid5(NAMESPACE, key))


def literal(value):
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def statements(farmers):
    per_state = Counter()
    result = [
        "BEGIN; SET LOCAL statement_timeout='30s'; DO $$ BEGIN IF current_database()<>'skyview_v3_demo' THEN RAISE EXCEPTION 'Demo only'; END IF; END $$;"
    ]
    for farmer in farmers:
        fid, state = farmer["id"], farmer["state"]
        display_name = re.sub(
            r"^Demo farmer (?=\d+$)", "Farmer ", farmer["display_name"]
        )
        result.append(
            f"UPDATE sv3.farmers SET display_name={literal(display_name)} WHERE id={literal(fid)} AND display_name={literal(farmer['display_name'])} AND display_name ~ '^Demo farmer [0-9]+$';"
        )
        slot = per_state[state] % len(CATALOG)
        per_state[state] += 1
        offer, need = CATALOG[slot], CATALOG[(slot + 1) % len(CATALOG)]
        extra_need = CATALOG[(slot + 2) % len(CATALOG)]
        district = farmer.get("district") or "Regional sharing area"
        if district.startswith("Demo "):
            district = "Regional sharing area"
        result.append(
            f"UPDATE sv3.farmers SET profile_attributes=jsonb_set(profile_attributes,'{{district}}','\"Regional sharing area\"'::jsonb) WHERE id={literal(fid)} AND profile_attributes->>'resource_catalog_origin'='synthetic' AND profile_attributes->>'district' LIKE 'Demo %';"
        )
        attrs = {
            "excess_resources": [offer[0]],
            "required_resources": [need[0], extra_need[0]],
            "district": district,
            "resource_catalog_version": "demo-sharing-v2",
            "resource_catalog_origin": "synthetic",
        }
        # Do not overwrite explicit existing farmer-edited sharing preferences.
        result.append(
            f"UPDATE sv3.farmers SET profile_attributes=profile_attributes||{literal(json.dumps(attrs))}::jsonb WHERE id={literal(fid)} AND ((NOT(profile_attributes ? 'resource_catalog_version') AND coalesce(profile_attributes->'required_resources','[]'::jsonb)='[]'::jsonb) OR (profile_attributes->>'resource_catalog_version'='demo-sharing-v1' AND profile_attributes->'required_resources'={literal(json.dumps([need[0]]))}::jsonb));"
        )
        rid = identifier(f"resource:{fid}")
        result.append(
            f"INSERT INTO sv3.resources(id,farmer_id,category,name,quantity,unit_code) VALUES({literal(rid)},{literal(fid)},{literal(offer[1])},{literal(offer[0])},1,'count') ON CONFLICT(id) DO NOTHING;"
        )
        result.append(
            f"INSERT INTO sv3.resource_listings(id,farmer_id,resource_id,visibility,available_from,available_to,asking_price_inr,status) VALUES({literal(identifier('inventory-listing:' + fid))},{literal(fid)},{literal(rid)},'public',CURRENT_DATE,CURRENT_DATE+30,NULL,'synthetic demo availability') ON CONFLICT(id) DO NOTHING;"
        )
        for key, kind, resource, exchange in [
            ("offer", "offer", offer, (need[0] + "; " + extra_need[0],)),
            ("request", "request", need, offer),
            ("request-extra", "request", extra_need, offer),
        ]:
            lid = identifier(f"notice:{fid}:{key}")
            title = f"{resource[0]} · {'available to share' if kind == 'offer' else 'needed for farm work'}"
            description = "Sample resource listing. Confirm availability, condition and handover with the member."
            values = [
                lid,
                fid,
                display_name,
                title,
                resource[1],
                kind,
                description,
                resource[2],
                resource[3],
                state,
                district,
                exchange[0],
                "published",
            ]
            result.append(
                f"UPDATE sv3.exchange_listings SET description={literal(description)},district={literal(district)} WHERE id={literal(lid)} AND row_version=1 AND description LIKE 'Fictional demo notice.%';"
            )
            result.append(
                "INSERT INTO sv3.exchange_listings(id,farmer_id,display_name,title,category,kind,description,quantity,unit,state,district,exchange_for,status) VALUES("
                + ",".join(literal(value) for value in values)
                + ") ON CONFLICT(id) DO NOTHING;"
            )
        result.append(
            f"UPDATE sv3.exchange_listings SET exchange_for={literal(need[0] + '; ' + extra_need[0])} WHERE id={literal(identifier('notice:' + fid + ':offer'))} AND row_version=1 AND exchange_for={literal(need[0])} AND (description LIKE 'Fictional demo notice.%' OR description LIKE 'Sample resource listing.%');"
        )
        result.append(
            f"UPDATE sv3.exchange_listings SET display_name={literal(display_name)} WHERE farmer_id={literal(fid)} AND row_version=1 AND display_name ~ '^Demo farmer [0-9]+$' AND (description LIKE 'Fictional demo notice.%' OR description LIKE 'Sample resource listing.%');"
        )
    result.append("COMMIT;")
    return "\n".join(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    # The database target is a constant; only existing synthetic demo records qualify.
    query = "SELECT coalesce(json_agg(t),'[]'::json) FROM (SELECT f.id,f.display_name,r.name AS state,f.profile_attributes->>'district' AS district FROM sv3.farmers f JOIN sv3.datasets d ON d.id=f.dataset_id JOIN sv3.regions r ON r.id=f.region_id WHERE f.profile_key LIKE 'DEMO-F%' AND f.status='demo' AND d.origin='synthetic' AND d.lane='demo' ORDER BY f.profile_key LIMIT 400) t"
    farmers = json.loads(sql(query, DATABASE))
    if len(farmers) != 400:
        raise SystemExit(
            "Expected at least 400 existing synthetic demo farmers; no writes made."
        )
    summary = {
        "database": DATABASE,
        "origin": "synthetic",
        "farmers": len(farmers),
        "states_uts": len({f["state"] for f in farmers}),
        "new_catalog_resources_max": len(farmers),
        "stable_notices_max": len(farmers) * 3,
        "messages_created": 0,
        "agreements_created": 0,
        "apply": args.apply,
    }
    print(json.dumps(summary))
    if args.apply:
        sql(statements(farmers), DATABASE)
        print(
            sql(
                "SELECT json_build_object('catalog_farmers',(SELECT count(*) FROM sv3.farmers WHERE profile_attributes->>'resource_catalog_version'='demo-sharing-v2'),'fictional_exchange_notices',(SELECT count(*) FROM sv3.exchange_listings WHERE description LIKE 'Fictional demo notice.%' OR description LIKE 'Sample resource listing.%'),'published_notices',(SELECT count(*) FROM sv3.exchange_listings WHERE status='published'),'nonempty_needs',(SELECT count(*) FROM sv3.farmers WHERE jsonb_array_length(coalesce(profile_attributes->'required_resources','[]'))>0))",
                DATABASE,
            )
        )


if __name__ == "__main__":
    main()
