-- Private service records and explicitly shared group checklists; no external dispatch.
BEGIN;
SET search_path=sv3,pg_catalog;
CREATE TABLE IF NOT EXISTS service_requests (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farmer_id uuid NOT NULL REFERENCES farmers(id),
 title text NOT NULL, service_type text NOT NULL CHECK(service_type IN ('labour','machinery','transport','expert','other')),
 supplier text NOT NULL DEFAULT '',quote_inr numeric(14,2) CHECK(quote_inr>=0),scheduled_on date,
 status text NOT NULL DEFAULT 'planned' CHECK(status IN ('planned','requested','quote_recorded','farmer_confirmed','farmer_completed','cancelled')),
 notes text NOT NULL DEFAULT '',row_version bigint NOT NULL DEFAULT 1,created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS farm_groups(id uuid PRIMARY KEY DEFAULT gen_random_uuid(),owner_farmer_id uuid NOT NULL REFERENCES farmers(id),name text NOT NULL,created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS group_members(group_id uuid NOT NULL REFERENCES farm_groups(id),farmer_id uuid NOT NULL REFERENCES farmers(id),display_name text NOT NULL,role text NOT NULL CHECK(role IN ('reader','contributor')),created_at timestamptz NOT NULL DEFAULT now(),PRIMARY KEY(group_id,farmer_id));
CREATE TABLE IF NOT EXISTS group_invites(id uuid PRIMARY KEY DEFAULT gen_random_uuid(),group_id uuid NOT NULL REFERENCES farm_groups(id),token_hash text NOT NULL UNIQUE,role text NOT NULL CHECK(role IN ('reader','contributor')),expires_at timestamptz NOT NULL,used_by uuid REFERENCES farmers(id),revoked_at timestamptz,created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS group_tasks(id uuid PRIMARY KEY DEFAULT gen_random_uuid(),group_id uuid NOT NULL REFERENCES farm_groups(id),creator_id uuid NOT NULL REFERENCES farmers(id),title text NOT NULL,notes text NOT NULL DEFAULT '',due_on date,completed boolean NOT NULL DEFAULT false,row_version bigint NOT NULL DEFAULT 1,created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now());
-- Definer queries only these isolated collaboration tables; no permission is granted on private farm records.
CREATE OR REPLACE FUNCTION group_role(identifier uuid) RETURNS text LANGUAGE sql STABLE SECURITY DEFINER SET search_path=sv3,pg_catalog AS $$
 SELECT CASE WHEN g.owner_farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid THEN 'owner' ELSE m.role END
 FROM farm_groups g LEFT JOIN group_members m ON m.group_id=g.id AND m.farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid WHERE g.id=identifier
$$;
REVOKE ALL ON FUNCTION group_role(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION group_role(uuid) TO sv3_app,sv3_writer;
CREATE OR REPLACE FUNCTION accept_group_invite(digest text) RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=sv3,pg_catalog AS $$
DECLARE invite sv3.group_invites; person uuid; person_name text;
BEGIN
 person:=nullif(current_setting('app.farmer_id',true),'')::uuid;
 IF person IS NULL THEN RAISE EXCEPTION 'Invite unavailable' USING ERRCODE='22023'; END IF;
 SELECT * INTO invite FROM group_invites WHERE token_hash=digest AND revoked_at IS NULL AND used_by IS NULL AND expires_at>now() FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Invite unavailable' USING ERRCODE='22023'; END IF;
 IF EXISTS(SELECT 1 FROM farm_groups WHERE id=invite.group_id AND owner_farmer_id=person) OR EXISTS(SELECT 1 FROM group_members WHERE group_id=invite.group_id AND farmer_id=person) THEN RAISE EXCEPTION 'Already a member' USING ERRCODE='22023'; END IF;
 SELECT display_name INTO person_name FROM farmers WHERE id=person AND status IN ('active','demo');
 IF NOT FOUND THEN RAISE EXCEPTION 'Invite unavailable' USING ERRCODE='22023'; END IF;
 INSERT INTO group_members(group_id,farmer_id,display_name,role) VALUES(invite.group_id,person,person_name,invite.role);
 UPDATE group_invites SET used_by=person WHERE id=invite.id;
 RETURN invite.group_id;
END $$;
REVOKE ALL ON FUNCTION accept_group_invite(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION accept_group_invite(text) TO sv3_writer;
ALTER TABLE service_requests ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS farmer_scope ON service_requests;
CREATE POLICY farmer_scope ON service_requests USING(farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK(farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE farm_groups ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS group_scope ON farm_groups;
CREATE POLICY group_scope ON farm_groups FOR SELECT USING(owner_farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid OR group_role(id) IS NOT NULL);
DROP POLICY IF EXISTS group_create ON farm_groups;
CREATE POLICY group_create ON farm_groups FOR INSERT WITH CHECK(owner_farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE group_members ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS member_read ON group_members;
CREATE POLICY member_read ON group_members FOR SELECT USING(group_role(group_id) IS NOT NULL);
DROP POLICY IF EXISTS member_revoke ON group_members;
CREATE POLICY member_revoke ON group_members FOR DELETE USING(group_role(group_id)='owner');
ALTER TABLE group_invites ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS invite_owner ON group_invites;
CREATE POLICY invite_owner ON group_invites USING(group_role(group_id)='owner') WITH CHECK(group_role(group_id)='owner');
ALTER TABLE group_tasks ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS task_read ON group_tasks;
CREATE POLICY task_read ON group_tasks FOR SELECT USING(group_role(group_id) IS NOT NULL);
DROP POLICY IF EXISTS task_create ON group_tasks;
CREATE POLICY task_create ON group_tasks FOR INSERT WITH CHECK(group_role(group_id) IN ('owner','contributor') AND creator_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
DROP POLICY IF EXISTS task_update ON group_tasks;
CREATE POLICY task_update ON group_tasks FOR UPDATE USING(group_role(group_id) IN ('owner','contributor')) WITH CHECK(group_role(group_id) IN ('owner','contributor'));
GRANT SELECT ON service_requests,farm_groups,group_members,group_invites,group_tasks TO sv3_app;
GRANT SELECT,INSERT,UPDATE ON service_requests,farm_groups,group_invites,group_tasks TO sv3_writer;
GRANT SELECT,DELETE ON group_members TO sv3_writer;
CREATE INDEX IF NOT EXISTS service_owner_updated ON service_requests(farmer_id,updated_at DESC);
CREATE INDEX IF NOT EXISTS group_member_person ON group_members(farmer_id,group_id);
CREATE INDEX IF NOT EXISTS group_task_date ON group_tasks(group_id,due_on);
COMMIT;
