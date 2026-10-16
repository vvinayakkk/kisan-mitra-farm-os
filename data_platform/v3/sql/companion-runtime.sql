BEGIN;
SET search_path=sv3,pg_catalog;
CREATE TABLE IF NOT EXISTS companion_preferences(
 farmer_id uuid PRIMARY KEY REFERENCES farmers(id),name text NOT NULL DEFAULT 'Saathi' CHECK(length(name) BETWEEN 1 AND 40),
 enabled boolean NOT NULL DEFAULT false,frequency_hours integer NOT NULL DEFAULT 6 CHECK(frequency_hours BETWEEN 1 AND 168),
 quiet_start integer NOT NULL DEFAULT 22 CHECK(quiet_start BETWEEN 0 AND 23),quiet_end integer NOT NULL DEFAULT 6 CHECK(quiet_end BETWEEN 0 AND 23),
 timezone text NOT NULL DEFAULT 'Asia/Kolkata',row_version bigint NOT NULL DEFAULT 1 CHECK(row_version>0),
 last_checked_at timestamptz,next_check_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS idx_companion_due ON companion_preferences(next_check_at) WHERE enabled;
ALTER TABLE companion_preferences ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS farmer_scope ON companion_preferences;
CREATE POLICY farmer_scope ON companion_preferences USING(farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK(farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
GRANT SELECT ON companion_preferences TO sv3_app;
GRANT SELECT,INSERT,UPDATE ON companion_preferences TO sv3_writer;
CREATE TABLE IF NOT EXISTS companion_worker_state(singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),last_sweep_at timestamptz);
GRANT SELECT ON companion_worker_state TO sv3_app;

CREATE OR REPLACE FUNCTION companion_sweep(batch_limit integer DEFAULT 100) RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path=sv3,pg_catalog,pg_temp AS $$
DECLARE prefs companion_preferences; item record; hour_local integer; created integer:=0; changed integer; stamp timestamptz:=clock_timestamp(); day_local date;
BEGIN
 FOR prefs IN SELECT * FROM companion_preferences WHERE enabled AND next_check_at<=stamp
  ORDER BY next_check_at,farmer_id FOR UPDATE SKIP LOCKED LIMIT least(100,greatest(1,batch_limit)) LOOP
  hour_local:=extract(hour FROM stamp AT TIME ZONE prefs.timezone);day_local:=(stamp AT TIME ZONE prefs.timezone)::date;
  IF (prefs.quiet_start<prefs.quiet_end AND hour_local>=prefs.quiet_start AND hour_local<prefs.quiet_end)
   OR (prefs.quiet_start>prefs.quiet_end AND (hour_local>=prefs.quiet_start OR hour_local<prefs.quiet_end)) THEN
   UPDATE companion_preferences SET next_check_at=stamp+interval '30 minutes' WHERE farmer_id=prefs.farmer_id;
   CONTINUE;
  END IF;
  FOR item IN SELECT id,title,due_at,status FROM tasks WHERE farmer_id=prefs.farmer_id AND status='open' AND deleted_at IS NULL
    AND due_at BETWEEN stamp-interval '7 days' AND stamp+interval '24 hours' ORDER BY due_at,id LIMIT 8 LOOP
   INSERT INTO notifications(farmer_id,task_id,channel,delivery_allowed,scheduled_at,status,payload,dedupe_key)
   VALUES(prefs.farmer_id,item.id,'in_app',true,stamp,'ready',jsonb_build_object('source','companion','kind','task_due',
    'title',CASE WHEN item.due_at<stamp THEN 'A farm task needs attention' ELSE 'Coming up on your farm' END,
    'detail',item.title,'href','/workspace?view=calendar','evidence',jsonb_build_object('task_id',item.id,'due_at',item.due_at,'status',item.status),
    'created_at',stamp), 'companion:task:'||item.id||':'||day_local) ON CONFLICT(farmer_id,dedupe_key) DO NOTHING;
   GET DIAGNOSTICS changed=ROW_COUNT;created:=created+changed;
  END LOOP;
  FOR item IN SELECT id,title,updated_at,status FROM disease_cases WHERE farmer_id=prefs.farmer_id
   AND status NOT IN ('resolved','closed','archived') AND updated_at BETWEEN stamp-interval '30 days' AND stamp-interval '48 hours'
   ORDER BY updated_at,id LIMIT 3 LOOP
   INSERT INTO notifications(farmer_id,channel,delivery_allowed,scheduled_at,status,payload,dedupe_key)
   VALUES(prefs.farmer_id,'in_app',true,stamp,'ready',jsonb_build_object('source','companion','kind','crop_followup',
    'title','How is your crop doing?','detail',item.title,'href','/workspace?view=crops',
    'evidence',jsonb_build_object('case_id',item.id,'last_updated_at',item.updated_at,'status',item.status),'created_at',stamp),
    'companion:case:'||item.id||':'||day_local) ON CONFLICT(farmer_id,dedupe_key) DO NOTHING;
   GET DIAGNOSTICS changed=ROW_COUNT;created:=created+changed;
  END LOOP;
  UPDATE companion_preferences SET last_checked_at=stamp,next_check_at=stamp+make_interval(hours=>prefs.frequency_hours) WHERE farmer_id=prefs.farmer_id;
 END LOOP;
 INSERT INTO companion_worker_state(singleton,last_sweep_at) VALUES(true,stamp) ON CONFLICT(singleton) DO UPDATE SET last_sweep_at=EXCLUDED.last_sweep_at;
 RETURN created;
END $$;
REVOKE ALL ON FUNCTION companion_sweep(integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION companion_sweep(integer) TO sv3_ingest;
COMMIT;
