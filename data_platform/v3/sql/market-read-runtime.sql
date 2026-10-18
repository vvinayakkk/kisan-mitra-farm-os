-- History filters by dataset origin and date, whereas the existing index starts
-- with series_id. Avoid sorting every historical packet for a small chart.
CREATE INDEX IF NOT EXISTS idx_prices_dataset_date
ON sv3.price_observations (dataset_id, observed_on DESC, fetched_at DESC, series_id);

CREATE OR REPLACE FUNCTION sv3.market_price_history(
  _crop text, _aliases text[], _state text, _market text,
  _year integer, _month integer, _week integer,
  _observed_only boolean, _limit integer
) RETURNS SETOF jsonb
LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path = pg_catalog, sv3 AS $$
BEGIN
  -- Plan for the current filters; SQL-function generic plans scan all partitions.
  RETURN QUERY EXECUTE $history$
WITH RECURSIVE market_regions AS (
  SELECT id, name AS state, NULL::text AS district FROM sv3.regions WHERE level IN ('state','ut')
  UNION ALL
  SELECT r.id, p.state, CASE WHEN r.level='district' THEN r.name ELSE p.district END
  FROM sv3.regions r JOIN market_regions p ON r.parent_id=p.id
)
SELECT to_jsonb(result) FROM (
 SELECT candidate.* FROM sv3.datasets d
 JOIN sv3.providers v ON v.id=d.provider_id
 JOIN LATERAL (
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
  WHERE p.dataset_id=d.id
    AND p.observed_on <= (now() AT TIME ZONE 'Asia/Kolkata')::date
    AND ($1='' OR lower(c.name)=ANY($2) OR lower(c.code)=ANY($2)
      OR EXISTS (SELECT 1 FROM jsonb_each_text(c.names) a WHERE lower(a.value)=lower($1)))
    AND ($3='' OR lower(coalesce(mr.state,r.name))=lower($3))
    AND ($4='' OR lower(m.name)=lower($4) OR m.id::text=$4)
    AND ($5 IS NULL OR extract(year from p.observed_on)=$5)
    AND ($6 IS NULL OR extract(month from p.observed_on)=$6)
    AND ($7 IS NULL OR extract(week from p.observed_on)=$7)
  ORDER BY p.observed_on DESC,p.fetched_at DESC,p.series_id
  LIMIT least(3000,greatest(1,$9))
) candidate ON true
 WHERE (NOT $8 OR d.origin='observed')
 ORDER BY candidate.arrival_date DESC,(candidate.origin<>'synthetic') DESC,candidate.fetched_at DESC,candidate.series_id
 LIMIT least(3000,greatest(1,$9))
) result
  $history$ USING _crop,_aliases,_state,_market,_year,_month,_week,_observed_only,_limit;
END;
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
