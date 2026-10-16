-- Stable public-data read contract shared by the market UI and assistant.
-- Invoker privileges preserve the caller's role; future private sources retain RLS.
CREATE OR REPLACE FUNCTION sv3.market_price_history(
  _crop text, _aliases text[], _state text, _market text,
  _year integer, _month integer, _week integer,
  _observed_only boolean, _limit integer
) RETURNS SETOF jsonb
LANGUAGE sql STABLE SECURITY INVOKER SET search_path = pg_catalog, sv3 AS $$
WITH RECURSIVE market_regions AS (
  SELECT id, name AS state, NULL::text AS district FROM sv3.regions WHERE level IN ('state','ut')
  UNION ALL
  SELECT r.id, p.state, CASE WHEN r.level='district' THEN r.name ELSE p.district END
  FROM sv3.regions r JOIN market_regions p ON r.parent_id=p.id
)
SELECT to_jsonb(result) FROM (
  SELECT p.series_id,p.observed_on AS arrival_date,p.min_price,p.max_price,p.modal_price,p.arrivals_quantity,
    s.unit_code AS unit,c.name AS commodity,cv.name AS variety,s.grade,m.name AS market,
    coalesce(mr.state,r.name) AS state,mr.district,
    extract(year from p.observed_on)::int AS year,extract(month from p.observed_on)::int AS month,
    extract(week from p.observed_on)::int AS week,p.fetched_at,d.origin,d.origin AS data_origin,
    d.lane,d.source_url,v.name AS provider_name,d.as_of_date
  FROM sv3.price_observations p
  JOIN sv3.market_series s ON s.id=p.series_id
  JOIN sv3.markets m ON m.id=s.market_id JOIN sv3.crops c ON c.id=s.crop_id
  JOIN sv3.crop_varieties cv ON cv.id=s.variety_id JOIN sv3.regions r ON r.id=m.region_id
  LEFT JOIN market_regions mr ON mr.id=r.id
  JOIN sv3.datasets d ON d.id=p.dataset_id JOIN sv3.providers v ON v.id=d.provider_id
  WHERE (NOT _observed_only OR d.origin='observed')
    AND p.observed_on <= (now() AT TIME ZONE 'Asia/Kolkata')::date
    AND (_crop='' OR lower(c.name)=ANY(_aliases) OR lower(c.code)=ANY(_aliases)
      OR EXISTS (SELECT 1 FROM jsonb_each_text(c.names) a WHERE lower(a.value)=lower(_crop)))
    AND (_state='' OR lower(coalesce(mr.state,r.name))=lower(_state))
    AND (_market='' OR lower(m.name)=lower(_market) OR m.id::text=_market)
    AND (_year IS NULL OR extract(year from p.observed_on)=_year)
    AND (_month IS NULL OR extract(month from p.observed_on)=_month)
    AND (_week IS NULL OR extract(week from p.observed_on)=_week)
  ORDER BY p.observed_on DESC,(d.origin<>'synthetic') DESC,p.fetched_at DESC,p.series_id
  LIMIT least(3000,greatest(1,_limit))
) result;
$$;

CREATE OR REPLACE FUNCTION sv3.market_latest_prices(
  _crop text, _aliases text[], _state text, _market text,
  _observed_only boolean, _limit integer
) RETURNS SETOF jsonb
LANGUAGE sql STABLE SECURITY INVOKER SET search_path = pg_catalog, sv3 AS $$
WITH RECURSIVE market_regions AS (
  SELECT id, name AS state, NULL::text AS district FROM sv3.regions WHERE level IN ('state','ut')
  UNION ALL
  SELECT r.id, p.state, CASE WHEN r.level='district' THEN r.name ELSE p.district END
  FROM sv3.regions r JOIN market_regions p ON r.parent_id=p.id
)
SELECT to_jsonb(result) FROM (
  SELECT p.series_id,p.observed_on AS arrival_date,p.min_price,p.max_price,p.modal_price,p.arrivals_quantity,
    s.unit_code AS unit,c.name AS commodity,cv.name AS variety,s.grade,m.name AS market,
    coalesce(mr.state,r.name) AS state,mr.district,
    extract(year from p.observed_on)::int AS year,extract(month from p.observed_on)::int AS month,
    extract(week from p.observed_on)::int AS week,p.fetched_at,d.origin,d.origin AS data_origin,
    d.lane,d.source_url,v.name AS provider_name,d.as_of_date
  FROM sv3.market_series s
  JOIN sv3.markets m ON m.id=s.market_id JOIN sv3.crops c ON c.id=s.crop_id
  JOIN sv3.crop_varieties cv ON cv.id=s.variety_id JOIN sv3.regions r ON r.id=m.region_id
  LEFT JOIN market_regions mr ON mr.id=r.id
  JOIN LATERAL (
    SELECT x.* FROM sv3.price_observations x JOIN sv3.datasets dx ON dx.id=x.dataset_id
    WHERE x.series_id=s.id AND (NOT _observed_only OR dx.origin='observed')
      AND x.observed_on <= (now() AT TIME ZONE 'Asia/Kolkata')::date
    ORDER BY x.observed_on DESC,(dx.origin<>'synthetic') DESC,x.fetched_at DESC LIMIT 1
  ) p ON true
  JOIN sv3.datasets d ON d.id=p.dataset_id JOIN sv3.providers v ON v.id=d.provider_id
  WHERE (NOT _observed_only OR m.dataset_id IN (SELECT id FROM sv3.datasets WHERE origin IN ('observed','curated')))
    AND (_crop='' OR lower(c.name)=ANY(_aliases) OR lower(c.code)=ANY(_aliases)
      OR EXISTS (SELECT 1 FROM jsonb_each_text(c.names) a WHERE lower(a.value)=lower(_crop)))
    AND (_state='' OR lower(coalesce(mr.state,r.name))=lower(_state))
    AND (_market='' OR lower(m.name)=lower(_market) OR m.id::text=_market)
  ORDER BY p.observed_on DESC,(d.origin<>'synthetic') DESC,m.name,c.name,s.id
  LIMIT least(200,greatest(1,_limit))
) result;
$$;

REVOKE ALL ON FUNCTION sv3.market_price_history(text,text[],text,text,integer,integer,integer,boolean,integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION sv3.market_latest_prices(text,text[],text,text,boolean,integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION sv3.market_price_history(text,text[],text,text,integer,integer,integer,boolean,integer) TO sv3_app,sv3_ingest;
GRANT EXECUTE ON FUNCTION sv3.market_latest_prices(text,text[],text,text,boolean,integer) TO sv3_app,sv3_ingest;
