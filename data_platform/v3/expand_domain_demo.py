"""Add broad, reproducible domain examples to the fixed local sample database.

Never targets live storage. Market directory references have a separate curated
release; synthetic quotes are attached ONLY to explicitly sample market names.
Reruns fill gaps, preserve edits, and never erase existing history or user records.
"""

import argparse
import json
import uuid
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from provision import sql
from seed_demo import BASE

DATABASE = "skyview_v3_demo"
NS = uuid.UUID("139736f1-55d6-40fe-bd36-0dd104def4dd")
EXTRA = [
    "tomato",
    "brinjal",
    "cabbage",
    "cauliflower",
    "okra",
    "cucumber",
    "pumpkin",
    "bottle-gourd",
    "bitter-gourd",
    "ridge-gourd",
    "ash-gourd",
    "snake-gourd",
    "pointed-gourd",
    "ivy-gourd",
    "sponge-gourd",
    "capsicum",
    "chilli",
    "green-chilli",
    "carrot",
    "radish",
    "beetroot",
    "turnip",
    "sweet-potato",
    "tapioca",
    "yam",
    "taro",
    "drumstick",
    "amaranth",
    "spinach",
    "fenugreek",
    "coriander",
    "mint",
    "lettuce",
    "broccoli",
    "peas",
    "french-bean",
    "cluster-bean",
    "cowpea",
    "broad-bean",
    "pigeon-pea",
    "green-gram",
    "black-gram",
    "lentil",
    "moth-bean",
    "horse-gram",
    "field-pea",
    "rajma",
    "sorghum",
    "foxtail-millet",
    "little-millet",
    "kodo-millet",
    "barnyard-millet",
    "proso-millet",
    "pearl-millet",
    "sesame",
    "sunflower",
    "safflower",
    "linseed",
    "niger",
    "rapeseed",
    "oil-palm",
    "mango",
    "guava",
    "papaya",
    "pomegranate",
    "grape",
    "orange",
    "kinnow",
    "sweet-orange",
    "lemon",
    "lime",
    "sapota",
    "jackfruit",
    "pineapple",
    "litchi",
    "pear",
    "peach",
    "plum",
    "apricot",
    "strawberry",
    "watermelon",
    "muskmelon",
    "fig",
    "custard-apple",
    "dragon-fruit",
    "aonla",
    "ber",
    "tamarind",
    "turmeric",
    "garlic",
    "cumin",
    "fennel",
    "ajwain",
    "dill",
    "clove",
    "nutmeg",
    "cinnamon",
    "bay-leaf",
    "saffron",
    "cocoa",
    "rubber",
    "arecanut",
    "betel-leaf",
    "stevia",
    "aloe-vera",
    "marigold",
    "rose",
    "jasmine",
    "chrysanthemum",
    "tuberose",
    "gladiolus",
    "lotus",
    "makhana",
    "buckwheat",
    "quinoa",
    "oats",
    "fodder-maize",
    "lucerne",
    "berseem",
    "napier-grass",
    "sweet-corn",
    "baby-corn",
    "mushroom",
    "button-mushroom",
    "oyster-mushroom",
]
CROP_CODES = sorted(set(BASE) | set(EXTRA))


def uid(key):
    return str(uuid.uuid5(NS, key))


def lit(value):
    return "'" + str(value).replace("'", "''") + "'"


COMPARISON_CROPS = (
    "tomato",
    "brinjal",
    "okra",
    "cabbage",
    "cauliflower",
    "chilli",
    "peas",
    "mango",
    "guava",
    "papaya",
)


def build(asof, crop_codes=None, market_offsets=(0, 0)):
    """Generate bounded set-based SQL; date is explicit for reproducible release IDs."""
    dataset = uid("domain-release:" + str(asof))
    provider = uid("domain-provider")
    run = uid("scenario:" + str(asof))
    q = [
        "BEGIN;",
        "SET LOCAL statement_timeout='600s';",
        "SELECT pg_advisory_xact_lock(hashtext('skyview-domain-enrichment'));",
        "DO $$ BEGIN IF current_database()<>'skyview_v3_demo' THEN RAISE EXCEPTION 'Local sample database only'; END IF; END $$;",
    ]
    q += [
        f"INSERT INTO sv3.providers(id,code,name,homepage,access_method,attribution,status) VALUES ('{provider}','domain-sample-v1','SkyView sample domain catalogue','https://example.invalid/skyview-samples','deterministic local generator','Illustrative fictional prices, weather and field examples. No observed mandi rates or medical ground truth.','demo') ON CONFLICT DO NOTHING;",
        f"INSERT INTO sv3.datasets(id,provider_id,release_key,lane,origin,as_of_date,generator_version,seed,source_url) VALUES('{dataset}','{provider}','domain-samples-{asof}','demo','synthetic','{asof}','domain-v2-regional',17,'demo://skyview/domain-v1') ON CONFLICT DO NOTHING;",
        "CREATE TEMP TABLE domain_crops(code text PRIMARY KEY,base_price numeric,ordinal integer) ON COMMIT DROP;",
    ]
    for crop in CROP_CODES if crop_codes is None else crop_codes:
        i = CROP_CODES.index(crop)
        base = BASE.get(crop, 1800 + (i % 12) * 350)
        q += [
            f"INSERT INTO sv3.crops(id,code,name,category,names) VALUES('{uid('crop:' + crop)}',{lit(crop)},{lit(crop.replace('-', ' ').title())},'crop','{{}}') ON CONFLICT(code) DO NOTHING;",
            f"INSERT INTO domain_crops VALUES({lit(crop)},{base},{i});",
        ]
    q += [
        "INSERT INTO sv3.crop_varieties(id,crop_id,code,name) SELECT md5('domain-variety:'||c.id)::uuid,c.id,'sample-unspecified','Unspecified variety — sample series' FROM sv3.crops c JOIN domain_crops dc USING(code) ON CONFLICT DO NOTHING;",
        "CREATE TEMP TABLE domain_states ON COMMIT DROP AS SELECT r.*,row_number() OVER(ORDER BY r.code)::integer AS ordinal FROM sv3.regions r WHERE code_system='DEMO' AND level IN ('state','ut') AND code LIKE 'DEMO-IN-%';",
        f"INSERT INTO sv3.markets(id,dataset_id,region_id,code_system,external_code,name,latitude,longitude) SELECT md5('domain-market:'||r.id||':'||n)::uuid,'{dataset}',r.id,'SAMPLE-DOMAIN',r.code||'-SAMPLE-'||n,r.name||' sample market '||lpad(n::text,2,'0'),NULL,NULL FROM domain_states r CROSS JOIN generate_series(1,30)n ON CONFLICT DO NOTHING;",
        f"INSERT INTO sv3.market_series(id,market_id,crop_id,variety_id,grade,unit_code,currency) SELECT md5('domain-series:'||m.id||':'||c.id)::uuid,m.id,c.id,v.id,'unspecified','quintal','INR' FROM domain_states r CROSS JOIN domain_crops dc CROSS JOIN generate_series({market_offsets[0]},{market_offsets[1]})off JOIN sv3.crops c ON c.code=dc.code JOIN sv3.crop_varieties v ON v.crop_id=c.id AND v.code='sample-unspecified' JOIN sv3.markets m ON m.region_id=r.id AND m.code_system='SAMPLE-DOMAIN' AND m.external_code=r.code||'-SAMPLE-'||(((dc.ordinal+off)%30)+1) ON CONFLICT DO NOTHING;",
        "CREATE TEMP TABLE domain_series ON COMMIT DROP AS SELECT s.id,dc.base_price,dc.ordinal FROM sv3.market_series s JOIN sv3.markets m ON m.id=s.market_id JOIN sv3.crops c ON c.id=s.crop_id JOIN domain_crops dc ON dc.code=c.code WHERE m.code_system='SAMPLE-DOMAIN';",
        # Reuse original ownership release per series on reruns, avoiding daily duplication.
        f"INSERT INTO sv3.price_observations(dataset_id,series_id,observed_on,min_price,modal_price,max_price,arrivals_quantity,arrivals_unit,fetched_at) SELECT '{dataset}',s.id,d::date,round(p*.88,2),round(p,2),round(p*1.12,2),round(((20+s.ordinal%80)*(1+.15*sin(extract(doy FROM d))))::numeric,3),'tonne','{asof}T00:00:00+05:30' FROM domain_series s CROSS JOIN generate_series('{asof}'::date-730,'{asof}'::date,'1 day')d CROSS JOIN LATERAL (SELECT s.base_price*(.85+get_byte(decode(md5(s.id::text),'hex'),0)::numeric/255*.35)*(1+.12*sin(extract(doy FROM d)*6.283185/365+s.ordinal)+.03*cos(extract(epoch FROM d)/86400*.37+s.ordinal))::numeric AS p)x WHERE NOT EXISTS(SELECT 1 FROM sv3.price_observations old WHERE old.series_id=s.id AND old.observed_on=d::date) ON CONFLICT DO NOTHING;",
        f"INSERT INTO sv3.model_versions(id,name,version,purpose,trained_until,validation,status) VALUES('{uid('scenario-model')}','sample-seasonal-envelope','1','Illustrative scenarios only; not predictive or observed rates',NULL,'{{\"backtested\":false,\"accuracy_claim\":false}}','scenario_only') ON CONFLICT DO NOTHING;",
        f"INSERT INTO sv3.forecast_runs(id,dataset_id,model_id,issued_at,training_cutoff,horizon_days,kind) VALUES('{run}','{dataset}','{uid('scenario-model')}','{asof}T00:00:00+05:30','{asof}',365,'scenario') ON CONFLICT DO NOTHING;",
        f"INSERT INTO sv3.price_projections(run_id,series_id,valid_on,kind,lower_price,central_price,upper_price,interval_definition) SELECT '{run}',s.id,'{asof}'::date+n,'scenario',round(p*.7,2),round(p,2),round(p*1.3,2),'Illustrative ±30% envelope, not a confidence interval or trading forecast' FROM domain_series s CROSS JOIN generate_series(1,365)n CROSS JOIN LATERAL(SELECT (s.base_price*(.85+get_byte(decode(md5(s.id::text),'hex'),0)::numeric/255*.35)*(1+.12*sin(extract(doy FROM ('{asof}'::date+n))*6.283185/365+s.ordinal)))::numeric p)x WHERE NOT EXISTS(SELECT 1 FROM sv3.price_projections old WHERE old.series_id=s.id AND old.valid_on='{asof}'::date+n AND old.kind='scenario') ON CONFLICT DO NOTHING;",
    ]
    q.append(
        "UPDATE sv3.markets SET name=replace(name,' demo market ',' sample market ') WHERE code_system='DEMO' AND name LIKE '% demo market %';"
    )
    q.extend(field_sql(dataset, asof))
    q += [
        "COMMIT;",
        "ANALYZE sv3.price_observations; ANALYZE sv3.price_projections; ANALYZE sv3.market_series; ANALYZE sv3.markets;",
    ]
    return "\n".join(q)


def field_sql(dataset, asof):
    # Only add to pre-existing fictional profiles. No synthetic records on real farmers.
    return [
        "CREATE TEMP TABLE domain_farmers ON COMMIT DROP AS SELECT f.id,f.region_id,fa.id AS farm_id,p.latitude,p.longitude FROM sv3.farmers f JOIN sv3.datasets d ON d.id=f.dataset_id JOIN LATERAL(SELECT id FROM sv3.farms WHERE farmer_id=f.id ORDER BY farm_key LIMIT 1)fa ON true JOIN LATERAL(SELECT latitude,longitude FROM sv3.plots WHERE farmer_id=f.id ORDER BY plot_key LIMIT 1)p ON true WHERE d.origin='synthetic' AND f.profile_key LIKE 'DEMO-F%';",
        "INSERT INTO sv3.plots(id,farmer_id,farm_id,plot_key,area_ha,latitude,longitude,soil_texture) SELECT md5('domain-plot:'||f.id||':'||n)::uuid,f.id,f.farm_id,'SAMPLE-DOMAIN-'||f.id||'-'||n,1+(n*.25),f.latitude,f.longitude,'sample loam' FROM domain_farmers f CROSS JOIN generate_series(1,2)n ON CONFLICT DO NOTHING;",
        f"INSERT INTO sv3.crop_cycles(id,farmer_id,plot_id,crop_id,season,sowing_date,expected_harvest_date,status) SELECT md5('domain-cycle:'||p.id)::uuid,p.farmer_id,p.id,c.id,'illustrative','{asof}'::date-45,'{asof}'::date+75,'growing' FROM sv3.plots p JOIN domain_farmers f ON f.id=p.farmer_id JOIN LATERAL(SELECT id FROM sv3.crops WHERE code IN('rice','wheat','maize','groundnut') ORDER BY md5(p.id::text||code) LIMIT 1)c ON true WHERE p.plot_key LIKE 'SAMPLE-DOMAIN-%' ON CONFLICT DO NOTHING;",
        f"INSERT INTO sv3.soil_samples(id,farmer_id,plot_id,dataset_id,sampled_on,sample_type,report_metadata) SELECT md5('domain-soil:'||p.id)::uuid,p.farmer_id,p.id,'{dataset}','{asof}'::date-30,'synthetic','{{\"origin\":\"synthetic\",\"lab_tested\":false,\"purpose\":\"illustrative field example\"}}' FROM sv3.plots p JOIN domain_farmers f ON f.id=p.farmer_id WHERE p.plot_key LIKE 'SAMPLE-DOMAIN-%' ON CONFLICT DO NOTHING;",
        f"INSERT INTO sv3.soil_indicators(id,farmer_id,plot_id,sample_id,dataset_id,property,depth_top_cm,depth_bottom_cm,unit_code,mean_value,evidence_type) SELECT md5('domain-soil-ph:'||p.id)::uuid,p.farmer_id,p.id,md5('domain-soil:'||p.id)::uuid,'{dataset}','ph',0,15,'ph',6.2+(get_byte(decode(md5(p.id::text),'hex'),0)%15)*.1,'synthetic' FROM sv3.plots p JOIN domain_farmers f ON f.id=p.farmer_id WHERE p.plot_key LIKE 'SAMPLE-DOMAIN-%' ON CONFLICT DO NOTHING;",
        f"INSERT INTO sv3.field_observations(id,farmer_id,cycle_id,observed_at,type,observation,origin) SELECT md5('domain-scout:'||cy.id||':'||n)::uuid,cy.farmer_id,cy.id,'{asof}'::date-(n*7),'crop_scouting',jsonb_build_object('origin','synthetic','symptom',CASE n%3 WHEN 0 THEN 'yellowing leaves' WHEN 1 THEN 'leaf spots' ELSE 'wilting' END,'severity','unconfirmed','notes','Illustrative scouting record; inspect actual field before acting'),'synthetic' FROM sv3.crop_cycles cy JOIN sv3.plots p ON p.id=cy.plot_id CROSS JOIN generate_series(1,3)n WHERE p.plot_key LIKE 'SAMPLE-DOMAIN-%' ON CONFLICT DO NOTHING;",
        f"INSERT INTO sv3.disease_cases(id,farmer_id,cycle_id,image_uri,image_hash,captured_at,assessment,model_version,status,created_at) SELECT md5('domain-case:'||cy.id||':'||n)::uuid,cy.farmer_id,cy.id,'demo://no-image/synthetic-case','synthetic-no-image-'||cy.id||'-'||n,'{asof}'::date-(n*7),jsonb_build_object('origin','synthetic','image_available',false,'diagnosis_confirmed',false,'possible_issue',CASE n%3 WHEN 0 THEN 'Leaf yellowing: nutrition, water stress or disease require differentiation' WHEN 1 THEN 'Leaf spotting: examine distribution and obtain clear images' ELSE 'Wilting: check roots, water and stem before diagnosis' END,'next_step','Upload actual crop image and confirm location, growth stage and symptom progression','confidence',NULL),'sample-no-inference','synthetic_example','{asof}'::date-(n*7) FROM sv3.crop_cycles cy JOIN sv3.plots p ON p.id=cy.plot_id CROSS JOIN generate_series(1,3)n WHERE p.plot_key LIKE 'SAMPLE-DOMAIN-%' ON CONFLICT DO NOTHING;",
    ]


def reference_sql(asof):
    payload = json.loads(
        (Path(__file__).parent / "catalog/enam_market_reference.json").read_text()
    )
    provider = uid("enam-reference-provider")
    dataset = uid("enam-reference-2026-10-15")
    q = [
        "BEGIN;",
        "DO $$ BEGIN IF current_database()<>'skyview_v3_demo' THEN RAISE EXCEPTION 'Local sample database only'; END IF; END $$;",
        f"INSERT INTO sv3.providers(id,code,name,homepage,access_method,attribution,status) VALUES('{provider}','enam-directory-reference','eNAM published market directory','https://enam.gov.in/aspirational-districts','reviewed public directory snapshot','Government of India eNAM aspirational-district mapping; names only, no rate or current operation assertion','reference') ON CONFLICT DO NOTHING;",
        f"INSERT INTO sv3.datasets(id,provider_id,release_key,lane,origin,as_of_date,source_url) VALUES('{dataset}','{provider}','enam-aspirational-2026-10-15','demo','curated','2026-10-15','https://enam.gov.in/aspirational-districts') ON CONFLICT DO NOTHING;",
    ]
    for m in payload["markets"]:
        state = m["state"]
        district = m["district"]
        name = m["name"]
        key = state + ":" + district + ":" + name
        q += [
            f"INSERT INTO sv3.regions(id,dataset_id,parent_id,level,code_system,code,name,valid_from) SELECT '{uid('enam-district:' + state + district)}','{dataset}',r.id,'district','ENAM-REFERENCE',{lit(state + ':' + district)},{lit(district)},'2026-10-15' FROM sv3.regions r WHERE lower(r.name)={lit(state.lower())} AND r.code_system='DEMO' AND r.level IN('state','ut') ON CONFLICT DO NOTHING;",
            f"INSERT INTO sv3.markets(id,dataset_id,region_id,code_system,external_code,name) SELECT '{uid('enam-market:' + key)}','{dataset}',r.id,'ENAM-REFERENCE',{lit('snapshot:' + key)},{lit(name)} FROM sv3.regions r WHERE r.id='{uid('enam-district:' + state + district)}' ON CONFLICT DO NOTHING;",
        ]
    return "\n".join(q + ["COMMIT;"])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apply", action="store_true")
    p.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=datetime.now(ZoneInfo("Asia/Kolkata")).date(),
    )
    a = p.parse_args()
    if a.as_of > datetime.now(ZoneInfo("Asia/Kolkata")).date():
        p.error("Historical release cannot be dated in the future")
    if not a.apply:
        print(
            json.dumps(
                {
                    "database": DATABASE,
                    "crop_codes": len(CROP_CODES),
                    "states": 36,
                    "sample_markets": 1080,
                    "history_days": 731,
                    "scenario_days": 365,
                    "official_directory_names": 158,
                    "apply": False,
                }
            )
        )
        return
    sql(reference_sql(a.as_of), DATABASE)
    sql(
        f"DO $$ BEGIN IF current_database()<>'skyview_v3_demo' THEN RAISE EXCEPTION 'Local sample database only'; END IF; END $$; SELECT sv3.ensure_month_partitions('price_observations','{a.as_of}'::date-730,'{a.as_of}'::date);",
        DATABASE,
    )
    from regionalize_domain_demo import statements as regionalize

    sql(regionalize(), DATABASE)
    sql(build(a.as_of), DATABASE)
    sql(build(a.as_of, COMPARISON_CROPS, (1, 2)), DATABASE)
    print(
        sql(
            "SELECT json_build_object('crops',(SELECT count(*) FROM sv3.crops),'markets',(SELECT count(*) FROM sv3.markets),'price_history',(SELECT count(*) FROM sv3.price_observations),'price_scenarios',(SELECT count(*) FROM sv3.price_projections),'plots',(SELECT count(*) FROM sv3.plots),'soil_samples',(SELECT count(*) FROM sv3.soil_samples),'field_observations',(SELECT count(*) FROM sv3.field_observations),'disease_cases',(SELECT count(*) FROM sv3.disease_cases));",
            DATABASE,
        )
    )


if __name__ == "__main__":
    main()
