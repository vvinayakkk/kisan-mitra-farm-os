-- Owned farmer workspace records. Repeatable, additive; no automatic hardware execution.
BEGIN;
SET search_path=sv3,pg_catalog;
CREATE TABLE IF NOT EXISTS ledger_entries (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id),
 cycle_id uuid, description text NOT NULL, category text NOT NULL,
 kind text NOT NULL CHECK(kind IN ('income','expense')),
 basis text NOT NULL CHECK(basis IN ('actual','estimated','receivable')),
 amount_inr numeric(14,2) NOT NULL CHECK(amount_inr>=0), occurred_on date NOT NULL,
 notes text NOT NULL DEFAULT '', row_version bigint NOT NULL DEFAULT 1 CHECK(row_version>0),
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(), deleted_at timestamptz,
 FOREIGN KEY(cycle_id,farmer_id) REFERENCES crop_cycles(id,farmer_id),
 CHECK(basis<>'receivable' OR kind='income'));
ALTER TABLE ledger_entries ADD COLUMN IF NOT EXISTS origin text NOT NULL DEFAULT 'user_reported' CHECK(origin IN ('user_reported','synthetic'));
UPDATE ledger_entries l SET origin='synthetic' FROM expenses e WHERE e.id=l.id AND e.execution_key LIKE 'demo-expense-%' AND l.origin='user_reported';
-- Preserve original expense IDs and idempotent assistant expense writes.
INSERT INTO ledger_entries(id,farmer_id,cycle_id,description,category,kind,basis,amount_inr,occurred_on,origin)
SELECT id,farmer_id,cycle_id,description,category,'expense','actual',amount_inr,spent_on,CASE WHEN execution_key LIKE 'demo-expense-%' THEN 'synthetic' ELSE 'user_reported' END FROM expenses ON CONFLICT(id) DO NOTHING;
CREATE OR REPLACE FUNCTION mirror_expense_ledger() RETURNS trigger LANGUAGE plpgsql SET search_path=sv3,pg_catalog AS $$
BEGIN
 INSERT INTO ledger_entries(id,farmer_id,cycle_id,description,category,kind,basis,amount_inr,occurred_on)
 VALUES(NEW.id,NEW.farmer_id,NEW.cycle_id,NEW.description,NEW.category,'expense','actual',NEW.amount_inr,NEW.spent_on)
 ON CONFLICT(id) DO NOTHING;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS expense_to_ledger ON expenses;
CREATE TRIGGER expense_to_ledger AFTER INSERT ON expenses FOR EACH ROW EXECUTE FUNCTION mirror_expense_ledger();
CREATE TABLE IF NOT EXISTS farm_missions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id),
 title text NOT NULL, objective text NOT NULL DEFAULT '', status text NOT NULL DEFAULT 'draft'
 CHECK(status IN ('draft','active','paused','completed','cancelled')),
 steps jsonb NOT NULL DEFAULT '[]' CHECK(jsonb_typeof(steps)='array'),
 row_version bigint NOT NULL DEFAULT 1 CHECK(row_version>0),
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(id,farmer_id));
CREATE TABLE IF NOT EXISTS mission_receipts (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id),
 mission_id uuid NOT NULL, action text NOT NULL, detail text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(mission_id,farmer_id) REFERENCES farm_missions(id,farmer_id));
ALTER TABLE disease_cases ADD COLUMN IF NOT EXISTS title text NOT NULL DEFAULT 'Crop photo assessment';
ALTER TABLE disease_cases ADD COLUMN IF NOT EXISTS row_version bigint NOT NULL DEFAULT 1;
ALTER TABLE disease_cases ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();
-- Existing assessments retain their original chronology on first migration.
UPDATE disease_cases SET updated_at=created_at WHERE row_version=1 AND updated_at>created_at;
CREATE UNIQUE INDEX IF NOT EXISTS disease_case_owner_key ON disease_cases(id,farmer_id);
CREATE TABLE IF NOT EXISTS crop_case_notes (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id),
 case_id uuid NOT NULL, note text NOT NULL, observed_on date NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), FOREIGN KEY(case_id,farmer_id) REFERENCES disease_cases(id,farmer_id));
CREATE TABLE IF NOT EXISTS workflow_tool_executions (
 id uuid PRIMARY KEY, farmer_id uuid NOT NULL REFERENCES farmers(id), tool_name text NOT NULL,
 argument_hash text NOT NULL, result jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
DO $$ DECLARE tab text; BEGIN
 FOREACH tab IN ARRAY ARRAY['ledger_entries','farm_missions','mission_receipts','crop_case_notes','workflow_tool_executions'] LOOP
  EXECUTE format('ALTER TABLE sv3.%I ENABLE ROW LEVEL SECURITY',tab);
  EXECUTE format('DROP POLICY IF EXISTS farmer_scope ON sv3.%I',tab);
  EXECUTE format('CREATE POLICY farmer_scope ON sv3.%I USING(farmer_id=nullif(current_setting(''app.farmer_id'',true),'''')::uuid) WITH CHECK(farmer_id=nullif(current_setting(''app.farmer_id'',true),'''')::uuid)',tab);
  EXECUTE format('GRANT SELECT ON sv3.%I TO sv3_app',tab);
  EXECUTE format('GRANT SELECT,INSERT,UPDATE ON sv3.%I TO sv3_writer',tab);
 END LOOP;
END $$;
-- Audit/replay receipts are append-only for the application role.
REVOKE UPDATE ON mission_receipts,workflow_tool_executions FROM sv3_writer;
CREATE INDEX IF NOT EXISTS ledger_owner_date ON ledger_entries(farmer_id,occurred_on DESC) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS mission_owner_state ON farm_missions(farmer_id,status,updated_at DESC);
CREATE INDEX IF NOT EXISTS case_note_owner ON crop_case_notes(farmer_id,case_id,created_at DESC);
CREATE INDEX IF NOT EXISTS receipt_owner ON mission_receipts(farmer_id,mission_id,created_at DESC);
COMMIT;
