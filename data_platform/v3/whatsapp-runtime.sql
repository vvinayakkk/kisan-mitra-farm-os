BEGIN;
SET search_path=sv3,pg_catalog;
CREATE TABLE IF NOT EXISTS whatsapp_connections(farmer_id uuid PRIMARY KEY REFERENCES farmers(id),sender_hash text NOT NULL UNIQUE,sender_number text NOT NULL,connected_at timestamptz NOT NULL DEFAULT now(),last_received_at timestamptz NOT NULL DEFAULT now(),disconnected_at timestamptz,session_id text);
CREATE TABLE IF NOT EXISTS whatsapp_link_codes(token_hash text PRIMARY KEY,farmer_id uuid NOT NULL REFERENCES farmers(id),expires_at timestamptz NOT NULL,used_at timestamptz);
CREATE TABLE IF NOT EXISTS whatsapp_jobs(message_sid text PRIMARY KEY,farmer_id uuid NOT NULL REFERENCES farmers(id),sender_number text NOT NULL,body text NOT NULL,media jsonb NOT NULL,state text NOT NULL DEFAULT 'queued',created_at timestamptz NOT NULL DEFAULT now(),lease_until timestamptz,finished_at timestamptz,safe_error text,attempts integer NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS whatsapp_outbound(id uuid PRIMARY KEY DEFAULT gen_random_uuid(),farmer_id uuid NOT NULL REFERENCES farmers(id),message_sid text NOT NULL REFERENCES whatsapp_jobs(message_sid),part integer NOT NULL,provider_sid text UNIQUE,status text NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now(),safe_error text,UNIQUE(message_sid,part));
CREATE TABLE IF NOT EXISTS whatsapp_media_assets(id uuid PRIMARY KEY DEFAULT gen_random_uuid(),farmer_id uuid NOT NULL REFERENCES farmers(id),file_key text NOT NULL,mime text NOT NULL,filename text NOT NULL,expires_at timestamptz NOT NULL);
CREATE INDEX IF NOT EXISTS idx_whatsapp_queue ON whatsapp_jobs(created_at) WHERE state='queued';
DO $$DECLARE t text;BEGIN FOREACH t IN ARRAY ARRAY['whatsapp_connections','whatsapp_link_codes','whatsapp_jobs','whatsapp_outbound','whatsapp_media_assets'] LOOP
 EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',t);
 EXECUTE format('DROP POLICY IF EXISTS farmer_scope ON %I',t);
 EXECUTE format('CREATE POLICY farmer_scope ON %I USING(farmer_id=nullif(current_setting(''app.farmer_id'',true),'''')::uuid) WITH CHECK(farmer_id=nullif(current_setting(''app.farmer_id'',true),'''')::uuid)',t);
 EXECUTE format('GRANT SELECT ON %I TO sv3_app',t);EXECUTE format('GRANT SELECT,INSERT,UPDATE,DELETE ON %I TO sv3_writer',t);
END LOOP;END $$;
CREATE OR REPLACE FUNCTION whatsapp_redeem_link(digest text,phone_hash text,phone text) RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=sv3,pg_catalog,pg_temp AS $$
DECLARE person uuid;BEGIN
 SELECT farmer_id INTO person FROM whatsapp_link_codes WHERE token_hash=digest AND used_at IS NULL AND expires_at>now() FOR UPDATE;
 IF person IS NULL THEN RETURN NULL;END IF;
 IF EXISTS(SELECT 1 FROM whatsapp_connections WHERE sender_hash=phone_hash AND farmer_id<>person) THEN RETURN NULL;END IF;
 INSERT INTO whatsapp_connections(farmer_id,sender_hash,sender_number) VALUES(person,phone_hash,phone)
 ON CONFLICT(farmer_id) DO UPDATE SET sender_hash=EXCLUDED.sender_hash,sender_number=EXCLUDED.sender_number,connected_at=now(),last_received_at=now(),disconnected_at=NULL,session_id=NULL;
 UPDATE whatsapp_jobs SET state='cancelled' WHERE farmer_id=person AND sender_number<>phone AND state='queued';
 UPDATE whatsapp_link_codes SET used_at=now() WHERE token_hash=digest;RETURN person;
END $$;
CREATE OR REPLACE FUNCTION whatsapp_sender(digest text) RETURNS uuid LANGUAGE sql SECURITY DEFINER SET search_path=sv3,pg_catalog,pg_temp AS $$
 SELECT farmer_id FROM whatsapp_connections WHERE sender_hash=digest AND disconnected_at IS NULL
$$;
CREATE OR REPLACE FUNCTION whatsapp_claim_job() RETURNS SETOF whatsapp_jobs LANGUAGE plpgsql SECURITY DEFINER SET search_path=sv3,pg_catalog,pg_temp AS $$
DECLARE item whatsapp_jobs;BEGIN
 UPDATE whatsapp_jobs SET state='failed',safe_error='Interrupted processing; resend your request',finished_at=now() WHERE state='processing' AND lease_until<now();
 SELECT j.* INTO item FROM whatsapp_jobs j JOIN whatsapp_connections c ON c.farmer_id=j.farmer_id AND c.disconnected_at IS NULL AND c.sender_number=j.sender_number
 WHERE j.state='queued' AND j.created_at>now()-interval '24 hours' ORDER BY j.created_at,j.message_sid FOR UPDATE OF j SKIP LOCKED LIMIT 1;
 IF item.message_sid IS NULL THEN RETURN;END IF;
 UPDATE whatsapp_jobs SET state='processing',lease_until=now()+interval '3 minutes',attempts=attempts+1 WHERE message_sid=item.message_sid RETURNING * INTO item;
 RETURN NEXT item;
END $$;
REVOKE ALL ON FUNCTION whatsapp_redeem_link(text,text,text),whatsapp_sender(text),whatsapp_claim_job() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION whatsapp_redeem_link(text,text,text),whatsapp_sender(text),whatsapp_claim_job() TO sv3_ingest;
COMMIT;
CREATE OR REPLACE FUNCTION sv3.whatsapp_delivery_owner(sid text) RETURNS uuid LANGUAGE sql SECURITY DEFINER SET search_path=sv3,pg_catalog,pg_temp AS $$ SELECT farmer_id FROM sv3.whatsapp_outbound WHERE provider_sid=sid $$;
REVOKE ALL ON FUNCTION sv3.whatsapp_delivery_owner(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION sv3.whatsapp_delivery_owner(text) TO sv3_ingest;
