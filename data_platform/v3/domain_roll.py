"""Small daily sample maintenance. No full reseed, user writes, or real forecasts.

Caller executes as ingestion role only in the fixed local sample database. Each
release adds at most thirty missing history points per series and only the missing
tail of the 365-day illustrative scenario horizon. Existing points always win.
Matching scenario values carry into new fixture dates; missing tails vary gently
from the last known value instead of creating a flat line.
"""

import uuid
from datetime import date

NS = uuid.UUID("139736f1-55d6-40fe-bd36-0dd104def4dd")


def uid(key):
    return str(uuid.uuid5(NS, key))


def statements(asof: date):
    d = uid("domain-release:" + str(asof))
    run = uid("scenario:" + str(asof))
    provider = uid("domain-provider")
    model = uid("scenario-model")
    return f"""
DO $$ BEGIN IF current_database()<>'skyview_v3_demo' THEN RAISE EXCEPTION 'Sample rollover is local only'; END IF; END $$;
SELECT pg_advisory_xact_lock(hashtext('skyview-domain-enrichment'));
INSERT INTO sv3.datasets(id,provider_id,release_key,lane,origin,as_of_date,generator_version,seed,source_url)
SELECT '{d}','{provider}','domain-samples-{asof}','demo','synthetic','{asof}','domain-v2-regional',17,'demo://skyview/domain-v1'
WHERE EXISTS(SELECT 1 FROM sv3.providers WHERE id='{provider}') ON CONFLICT DO NOTHING;
CREATE TEMP TABLE domain_roll_series ON COMMIT DROP AS
SELECT s.id,last.modal_price AS base_price,coalesce(p.central_price,last.modal_price) AS projection_base,
coalesce(h.latest_day,'{asof}'::date-30) AS history_day,coalesce(p.latest_day,'{asof}'::date) AS projection_day
FROM sv3.market_series s JOIN sv3.markets m ON m.id=s.market_id
JOIN LATERAL(SELECT modal_price FROM sv3.price_observations WHERE series_id=s.id ORDER BY observed_on DESC LIMIT 1)last ON true
LEFT JOIN LATERAL(SELECT max(observed_on) AS latest_day FROM sv3.price_observations WHERE series_id=s.id)h ON true
LEFT JOIN LATERAL(SELECT pp.valid_on AS latest_day,pp.central_price FROM sv3.price_projections pp
JOIN sv3.forecast_runs fr ON fr.id=pp.run_id JOIN sv3.datasets ds ON ds.id=fr.dataset_id
WHERE pp.series_id=s.id AND pp.kind='scenario' AND ds.origin='synthetic' ORDER BY pp.valid_on DESC,fr.issued_at DESC LIMIT 1)p ON true
WHERE m.code_system='SAMPLE-DOMAIN';
INSERT INTO sv3.price_observations(dataset_id,series_id,observed_on,min_price,modal_price,max_price,arrivals_quantity,arrivals_unit,fetched_at)
SELECT '{d}',s.id,day::date,round(v.price*.88,2),v.price,round(v.price*1.12,2),NULL,'tonne',now()
FROM domain_roll_series s CROSS JOIN LATERAL generate_series(greatest(s.history_day+1,'{asof}'::date-29),'{asof}'::date,'1 day')day
CROSS JOIN LATERAL(SELECT coalesce((SELECT pp.central_price FROM sv3.price_projections pp
JOIN sv3.forecast_runs fr ON fr.id=pp.run_id JOIN sv3.datasets ds ON ds.id=fr.dataset_id
WHERE pp.series_id=s.id AND pp.valid_on=day::date AND pp.kind='scenario' AND ds.origin='synthetic'
ORDER BY fr.issued_at DESC LIMIT 1),
greatest(1,round(s.base_price*(1+(get_byte(decode(md5(s.id::text||':'||day::date::text),'hex'),0)::numeric/255-.5)*.028),2))) AS price)v
WHERE NOT EXISTS(SELECT 1 FROM sv3.price_observations old WHERE old.series_id=s.id AND old.observed_on=day::date) ON CONFLICT DO NOTHING;
INSERT INTO sv3.forecast_runs(id,dataset_id,model_id,issued_at,training_cutoff,horizon_days,kind)
SELECT '{run}','{d}','{model}','{asof}T00:00:00+05:30','{asof}',365,'scenario'
WHERE EXISTS(SELECT 1 FROM sv3.datasets WHERE id='{d}') ON CONFLICT DO NOTHING;
INSERT INTO sv3.price_projections(run_id,series_id,valid_on,kind,lower_price,central_price,upper_price,interval_definition)
SELECT '{run}',s.id,day::date,'scenario',round(v.price*.7,2),v.price,round(v.price*1.3,2),'Illustrative planning envelope, not a confidence interval or validated prediction'
FROM domain_roll_series s CROSS JOIN LATERAL generate_series(greatest(s.projection_day+1,'{asof}'::date+1),'{asof}'::date+365,'1 day')day
CROSS JOIN LATERAL(SELECT greatest(1,round(s.projection_base*(1+(get_byte(decode(md5(s.id::text||':'||day::date::text),'hex'),0)::numeric/255-.5)*.028),2)) AS price)v
WHERE NOT EXISTS(SELECT 1 FROM sv3.price_projections old WHERE old.series_id=s.id AND old.valid_on=day::date AND old.kind='scenario') ON CONFLICT DO NOTHING;
"""
