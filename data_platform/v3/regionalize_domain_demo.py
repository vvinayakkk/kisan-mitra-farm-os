"""One-time guarded migration of early v1 crop-only sample prices to regional v2.

A deterministic per-series factor preserves the complete temporal signal while
making same-crop comparisons across markets/states useful. Only domain sample
releases lacking the completed migration audit job are touched; all original/user/live data
and later corrected values remain untouched on reruns.
"""

import argparse
import json

from expand_domain_demo import CROP_CODES
from provision import sql


def statements():
    ordinals = json.dumps({c: i for i, c in enumerate(CROP_CODES)})
    return f"""
BEGIN;
SET LOCAL statement_timeout='900s';
SELECT pg_advisory_xact_lock(hashtext('skyview-domain-enrichment'));
DO $$ BEGIN IF current_database()<>'skyview_v3_demo' THEN RAISE EXCEPTION 'Sample regionalization is local only'; END IF; END $$;
CREATE TEMP TABLE region_fix_datasets ON COMMIT DROP AS SELECT d.id FROM sv3.datasets d JOIN sv3.providers p ON p.id=d.provider_id WHERE p.code='domain-sample-v1' AND d.origin='synthetic' AND d.lane='demo' AND d.generator_version='domain-v1' AND NOT EXISTS(SELECT 1 FROM sv3.ingest_runs i WHERE i.job_key='domain-regional-v2:'||d.id AND i.state='done');
CREATE TEMP TABLE region_fix_factors ON COMMIT DROP AS SELECT s.id,(.85+get_byte(decode(md5(s.id::text),'hex'),0)::numeric/255*.35) AS factor FROM sv3.market_series s JOIN sv3.markets m ON m.id=s.market_id JOIN sv3.regions r ON r.id=m.region_id JOIN sv3.crops c ON c.id=s.crop_id JOIN jsonb_each_text('{ordinals}'::jsonb)dc ON dc.key=c.code WHERE m.code_system='SAMPLE-DOMAIN' AND m.external_code=r.code||'-SAMPLE-'||((dc.value::integer%30)+1);
CREATE UNIQUE INDEX ON region_fix_factors(id);
ANALYZE region_fix_factors;
UPDATE sv3.price_observations p SET min_price=round(p.min_price*f.factor,2),modal_price=round(p.modal_price*f.factor,2),max_price=round(p.max_price*f.factor,2) FROM region_fix_factors f WHERE p.series_id=f.id AND p.dataset_id IN(SELECT id FROM region_fix_datasets);
UPDATE sv3.price_projections p SET lower_price=round(p.lower_price*f.factor,2),central_price=round(p.central_price*f.factor,2),upper_price=round(p.upper_price*f.factor,2) FROM region_fix_factors f WHERE p.series_id=f.id AND p.run_id IN(SELECT id FROM sv3.forecast_runs WHERE dataset_id IN(SELECT id FROM region_fix_datasets));
INSERT INTO sv3.ingest_runs(id,provider_id,dataset_id,job_key,state,attempts,rows_received,rows_accepted,started_at,finished_at) SELECT md5('domain-regional-v2:'||d.id)::uuid,d.provider_id,d.id,'domain-regional-v2:'||d.id,'done',1,0,0,now(),now() FROM sv3.datasets d WHERE d.id IN(SELECT id FROM region_fix_datasets) ON CONFLICT(job_key) DO NOTHING;
COMMIT;
ANALYZE sv3.price_observations; ANALYZE sv3.price_projections;
"""


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    a = p.parse_args()
    if a.apply:
        sql(statements(), "skyview_v3_demo")
    print("Regional v2 migration applied=" + str(a.apply))


if __name__ == "__main__":
    main()
