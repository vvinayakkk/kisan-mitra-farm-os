-- Consented public resource notices; private bilateral coordination.
BEGIN;
SET search_path=sv3,pg_catalog;
CREATE TABLE IF NOT EXISTS exchange_listings(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),farmer_id uuid NOT NULL REFERENCES farmers(id),display_name text NOT NULL,
 title text NOT NULL,category text NOT NULL CHECK(category IN ('equipment','labour','transport','produce')),kind text NOT NULL CHECK(kind IN ('offer','request')),
 description text NOT NULL DEFAULT '',quantity numeric NOT NULL CHECK(quantity>0),unit text NOT NULL,state text NOT NULL,district text NOT NULL,
 available_on date,exchange_for text NOT NULL DEFAULT '',status text NOT NULL CHECK(status IN ('draft','published','withdrawn')),
 row_version bigint NOT NULL DEFAULT 1,created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS exchange_conversations(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),listing_id uuid NOT NULL REFERENCES exchange_listings(id),listing_title text NOT NULL,
 owner_id uuid NOT NULL REFERENCES farmers(id),requester_id uuid NOT NULL REFERENCES farmers(id),owner_name text NOT NULL,requester_name text NOT NULL,
 status text NOT NULL DEFAULT 'open' CHECK(status IN ('open','negotiating','agreed','handover','completed','cancelled','disputed')),
 proposal jsonb,handovers jsonb NOT NULL DEFAULT '[]',completions jsonb NOT NULL DEFAULT '[]',row_version bigint NOT NULL DEFAULT 1,
 created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now(),CHECK(owner_id<>requester_id),UNIQUE(listing_id,requester_id));
CREATE TABLE IF NOT EXISTS exchange_messages(
 sequence bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,conversation_id uuid NOT NULL REFERENCES exchange_conversations(id),sender_id uuid NOT NULL REFERENCES farmers(id),text text NOT NULL,
 client_key uuid NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),UNIQUE(conversation_id,sender_id,client_key));
CREATE TABLE IF NOT EXISTS exchange_events(
 sequence bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,conversation_id uuid NOT NULL REFERENCES exchange_conversations(id),actor_id uuid NOT NULL REFERENCES farmers(id),action text NOT NULL,
 client_key uuid NOT NULL,request_hash text NOT NULL,result jsonb NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),UNIQUE(conversation_id,actor_id,client_key));
CREATE OR REPLACE FUNCTION exchange_participant(identifier uuid) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,sv3 AS $$
 SELECT EXISTS(SELECT 1 FROM exchange_conversations WHERE id=identifier AND nullif(current_setting('app.farmer_id',true),'')::uuid IN(owner_id,requester_id))
$$;
REVOKE ALL ON FUNCTION exchange_participant(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION exchange_participant(uuid) TO sv3_app,sv3_writer;
CREATE OR REPLACE FUNCTION exchange_listing_open(identifier uuid) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,sv3 AS $$
 SELECT EXISTS(SELECT 1 FROM sv3.exchange_listings WHERE id=identifier AND status='published')
 AND NOT EXISTS(SELECT 1 FROM sv3.exchange_conversations WHERE listing_id=identifier AND status IN ('agreed','handover','completed','disputed'))
$$;
REVOKE ALL ON FUNCTION exchange_listing_open(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION exchange_listing_open(uuid) TO sv3_app,sv3_writer;
-- Serialize acceptance per notice without exposing another farmer's private threads.
CREATE OR REPLACE FUNCTION exchange_available(identifier uuid) RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,sv3 AS $$
BEGIN
 PERFORM pg_advisory_xact_lock(hashtextextended(identifier::text,0));
 RETURN EXISTS(SELECT 1 FROM sv3.exchange_listings WHERE id=identifier AND status='published')
 AND NOT EXISTS(SELECT 1 FROM sv3.exchange_conversations WHERE listing_id=identifier AND status IN ('agreed','handover','completed','disputed'));
END $$;
REVOKE ALL ON FUNCTION exchange_available(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION exchange_available(uuid) TO sv3_writer;
ALTER TABLE exchange_listings ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS exchange_read ON exchange_listings;
CREATE POLICY exchange_read ON exchange_listings FOR SELECT USING(farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid OR status='published');
DROP POLICY IF EXISTS exchange_create ON exchange_listings;
CREATE POLICY exchange_create ON exchange_listings FOR INSERT WITH CHECK(farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
DROP POLICY IF EXISTS exchange_edit ON exchange_listings;
CREATE POLICY exchange_edit ON exchange_listings FOR UPDATE USING(farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid) WITH CHECK(farmer_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE exchange_conversations ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS conversation_scope ON exchange_conversations;
CREATE POLICY conversation_scope ON exchange_conversations USING(nullif(current_setting('app.farmer_id',true),'')::uuid IN(owner_id,requester_id)) WITH CHECK(nullif(current_setting('app.farmer_id',true),'')::uuid IN(owner_id,requester_id));
ALTER TABLE exchange_messages ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS message_read ON exchange_messages;
CREATE POLICY message_read ON exchange_messages FOR SELECT USING(exchange_participant(conversation_id));
DROP POLICY IF EXISTS message_send ON exchange_messages;
CREATE POLICY message_send ON exchange_messages FOR INSERT WITH CHECK(exchange_participant(conversation_id) AND sender_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
ALTER TABLE exchange_events ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS event_read ON exchange_events;
CREATE POLICY event_read ON exchange_events FOR SELECT USING(exchange_participant(conversation_id));
DROP POLICY IF EXISTS event_create ON exchange_events;
CREATE POLICY event_create ON exchange_events FOR INSERT WITH CHECK(exchange_participant(conversation_id) AND actor_id=nullif(current_setting('app.farmer_id',true),'')::uuid);
GRANT SELECT ON exchange_listings,exchange_conversations,exchange_messages,exchange_events TO sv3_app;
GRANT SELECT,INSERT,UPDATE ON exchange_listings,exchange_conversations TO sv3_writer;
GRANT SELECT,INSERT ON exchange_messages,exchange_events TO sv3_writer;
GRANT USAGE,SELECT ON SEQUENCE exchange_messages_sequence_seq,exchange_events_sequence_seq TO sv3_writer;
CREATE INDEX IF NOT EXISTS exchange_discovery ON exchange_listings(state,district,category,updated_at DESC) WHERE status='published';
CREATE INDEX IF NOT EXISTS exchange_owner ON exchange_listings(farmer_id,updated_at DESC);
CREATE INDEX IF NOT EXISTS exchange_thread_owner ON exchange_conversations(owner_id,updated_at DESC);
CREATE INDEX IF NOT EXISTS exchange_thread_requester ON exchange_conversations(requester_id,updated_at DESC);
CREATE INDEX IF NOT EXISTS exchange_message_cursor ON exchange_messages(conversation_id,sequence);
CREATE INDEX IF NOT EXISTS exchange_event_cursor ON exchange_events(conversation_id,sequence);
COMMIT;
