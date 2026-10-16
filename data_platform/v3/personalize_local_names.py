"""Give the owner's local fixtures readable names without changing source metadata.

Idempotent and restricted to skyview_v3_demo. The first run backs up changed
name fields in ignored .v3-data/local-name-backup.json. Never edits user names.
"""

import argparse
import json
from pathlib import Path

from provision import sql

TOWNS = {
    "AP": "Vijayawada Guntur Tirupati",
    "AR": "Itanagar Pasighat Ziro",
    "AS": "Guwahati Jorhat Dibrugarh",
    "BR": "Patna Gaya Muzaffarpur",
    "CG": "Raipur Bilaspur Durg",
    "GA": "Panaji Mapusa Margao",
    "GJ": "Ahmedabad Rajkot Surat",
    "HR": "Karnal Hisar Panipat",
    "HP": "Shimla Solan Mandi",
    "JH": "Ranchi Hazaribagh Deoghar",
    "KA": "Bengaluru Mysuru Hubballi",
    "KL": "Thrissur Palakkad Kozhikode",
    "MP": "Bhopal Indore Ujjain",
    "MH": "Nashik Pune Nagpur",
    "MN": "Imphal Thoubal Bishnupur",
    "ML": "Shillong Tura Jowai",
    "MZ": "Aizawl Lunglei Champhai",
    "NL": "Kohima Dimapur Mokokchung",
    "OD": "Bhubaneswar Cuttack Sambalpur",
    "PB": "Ludhiana Amritsar Patiala",
    "RJ": "Jaipur Kota Jodhpur",
    "SK": "Gangtok Namchi Gyalshing",
    "TN": "Coimbatore Madurai Thanjavur",
    "TS": "Hyderabad Warangal Nizamabad",
    "TR": "Agartala Udaipur Dharmanagar",
    "UP": "Lucknow Kanpur Varanasi",
    "UK": "Dehradun Haldwani Haridwar",
    "WB": "Kolkata Siliguri Bardhaman",
    "AN": "Sri-Vijaya-Puram Diglipur Rangat",
    "CH": "Chandigarh Manimajra Dhanas",
    "DN": "Silvassa Daman Diu",
    "DL": "Azadpur Narela Najafgarh",
    "JK": "Srinagar Jammu Sopore",
    "LA": "Leh Kargil Diskit",
    "LD": "Kavaratti Agatti Minicoy",
    "PY": "Puducherry Karaikal Yanam",
}
SURNAMES = dict(
    zip(
        TOWNS,
        [
            "Reddy",
            "Dorjee",
            "Saikia",
            "Prasad",
            "Sahu",
            "Naik",
            "Patel",
            "Dahiya",
            "Thakur",
            "Mahato",
            "Gowda",
            "Nair",
            "Verma",
            "Patil",
            "Singh",
            "Sangma",
            "Ralte",
            "Sema",
            "Pradhan",
            "Sandhu",
            "Rathore",
            "Lepcha",
            "Subramanian",
            "Rao",
            "Deb",
            "Yadav",
            "Rawat",
            "Chatterjee",
            "Kumar",
            "Sharma",
            "Desai",
            "Malik",
            "Dar",
            "Namgyal",
            "Koya",
            "Pillai",
        ],
    )
)
GIVEN = [
    "Arun",
    "Kiran",
    "Lakshmi",
    "Vijay",
    "Anita",
    "Ravi",
    "Meena",
    "Suresh",
    "Kavita",
    "Deepak",
    "Sunita",
    "Mohan",
]
MARKETS = [
    "Central Krishi Mandi",
    "Grain Market",
    "Vegetable Market",
    "Farmers Market",
    "Harvest Market",
    "Fruit Market",
    "Cooperative Mandi",
    "Wholesale Market",
    "Produce Market",
    "Agricultural Market",
    "Rural Market",
]
FIELDS = ["North field", "Orchard plot", "Well-side field", "South field"]


def quote(value):
    return "'" + value.replace("'", "''") + "'"


def read(table, fields, where):
    return json.loads(
        sql(
            f"SELECT coalesce(json_agg(x),'[]') FROM (SELECT {fields} FROM sv3.{table} WHERE {where}) x",
            "skyview_v3_demo",
        )
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    changes = []
    farmers = read(
        "farmers f JOIN sv3.regions r ON r.id=f.region_id",
        "f.id,f.display_name,r.code",
        "f.profile_key LIKE 'DEMO-F%' AND f.display_name ~* '^(demo )?farmer [0-9]+$'",
    )
    counts = {}
    for farmer in farmers:
        code = farmer["code"].split("-")[-1]
        n = counts.get(code, 0)
        counts[code] = n + 1
        name = f"{GIVEN[n % len(GIVEN)]} {SURNAMES.get(code, 'Kumar')}"
        changes.append(
            ("farmers", farmer["id"], "display_name", farmer["display_name"], name)
        )
    markets = read(
        "markets m JOIN sv3.regions r ON r.id=m.region_id",
        "m.id,m.name,r.code",
        "m.code_system IN('DEMO','SAMPLE-DOMAIN') AND m.name ~* '(sample|demo) market'",
    )
    counts = {}
    for market in sorted(markets, key=lambda x: (x["code"], x["name"], x["id"])):
        code = market["code"].split("-")[-1]
        n = counts.get(code, 0)
        counts[code] = n + 1
        towns = TOWNS.get(code, code).split()
        name = f"{towns[n % len(towns)].replace('-', ' ')} {MARKETS[(n // len(towns)) % len(MARKETS)]}"
        changes.append(("markets", market["id"], "name", market["name"], name))
    farms = read(
        "farms f JOIN sv3.farmers p ON p.id=f.farmer_id",
        "f.id,f.name,p.id AS owner,p.display_name",
        "f.name ~* '^(demo|sample) farm'",
    )
    names = {c[1]: c[4] for c in changes if c[0] == "farmers"}
    for farm in farms:
        name = names.get(farm["owner"], farm["display_name"])
        changes.append(("farms", farm["id"], "name", farm["name"], f"{name}'s Farm"))
    for i, plot in enumerate(
        read(
            "plots",
            "id,name,soil_texture",
            "plot_key LIKE 'DEMO-%' OR plot_key LIKE 'SAMPLE-DOMAIN-%'",
        )
    ):
        if (
            not plot["name"]
            or "sample" in plot["name"].lower()
            or "demo" in plot["name"].lower()
        ):
            changes.append(
                ("plots", plot["id"], "name", plot["name"], FIELDS[i % len(FIELDS)])
            )
        if plot["soil_texture"] and plot["soil_texture"].startswith("sample "):
            changes.append(
                (
                    "plots",
                    plot["id"],
                    "soil_texture",
                    plot["soil_texture"],
                    plot["soil_texture"].removeprefix("sample "),
                )
            )
    for row in read(
        "ledger_entries",
        "id,description,category",
        "origin='synthetic' AND description ~* '(demo|sample)'",
    ):
        label = (row["category"] or "Farm expense").replace("_", " ").capitalize()
        changes.append(
            ("ledger_entries", row["id"], "description", row["description"], label)
        )
    for row in read(
        "crop_varieties",
        "id,name",
        "code='sample-unspecified' AND name <> 'Standard variety'",
    ):
        changes.append(
            ("crop_varieties", row["id"], "name", row["name"], "Standard variety")
        )
    for listing in read(
        "exchange_listings l JOIN sv3.farmers f ON f.id=l.farmer_id",
        "l.id,l.display_name,l.description,f.display_name AS farmer_name",
        "f.profile_key LIKE 'DEMO-F%' AND (l.display_name ~* '^Farmer [0-9]+$' OR l.description LIKE 'Sample resource listing.%')",
    ):
        if listing["display_name"] != listing["farmer_name"]:
            changes.append(
                (
                    "exchange_listings",
                    listing["id"],
                    "display_name",
                    listing["display_name"],
                    listing["farmer_name"],
                )
            )
        if listing["description"].startswith("Sample resource listing."):
            changes.append(
                (
                    "exchange_listings",
                    listing["id"],
                    "description",
                    listing["description"],
                    "Available for a local exchange. Discuss timing, condition and collection with the farmer.",
                )
            )
    if args.apply and changes:
        backup = Path(__file__).resolve().parents[2] / ".v3-data/local-name-backup.json"
        original = json.loads(backup.read_text()) if backup.exists() else []
        saved = {(row[0], row[1], row[2]) for row in original}
        original.extend(row for row in changes if (row[0], row[1], row[2]) not in saved)
        backup.write_text(json.dumps(original, indent=2))
        backup.chmod(0o600)
        statements = [
            "BEGIN; SELECT pg_advisory_xact_lock(hashtext('skyview-local-names')); DO $$ BEGIN IF current_database()<>'skyview_v3_demo' THEN RAISE EXCEPTION 'Local database only'; END IF; END $$;"
        ]
        for table, key, column, old, new in changes:
            old_sql = "NULL" if old is None else quote(old)
            statements.append(
                f"UPDATE sv3.{table} SET {column}={quote(new)} WHERE id={quote(key)}::uuid AND {column} IS NOT DISTINCT FROM {old_sql};"
            )
        statements.append("COMMIT;")
        sql("\n".join(statements), "skyview_v3_demo")
    print(
        json.dumps(
            {
                "applied": args.apply,
                "renamed_fields": len(changes),
                "farmers": len(farmers),
                "markets": len(markets),
            }
        )
    )


if __name__ == "__main__":
    main()
