# Farmer exchange: resource notices and private coordination

The new workspace supports a real, persisted resource-coordination workflow on this site. Farmers publish a machine, labour, transport or produce offer/need, open a private conversation, write their own terms, and record agreement and handover. PostgreSQL stores the messages and actions. The system never writes invented replies or accepts on behalf of another farmer.

## What an exchange means

A notice contains an offer/need, category, description, positive quantity, stated unit, state/district, optional availability date, and optional description of what the farmer would accept in exchange. Publication requires explicit consent to disclose that notice and the farmer's display name. Exact farm coordinates, phone numbers, documents, private ledgers and diagnoses are not included.

Starting a conversation requires the requesting farmer's consent to share their display name with the notice owner. It reconnects the existing conversation for that notice/requester pair instead of creating duplicates. A cancelled conversation is not reopened: publish a new notice for a new arrangement.

The exchange is a whole-notice arrangement, not a partial stock allocation or a rental booking engine. Acceptance reserves the notice against other agreements. A disputed arrangement retains that reservation; it does not silently make the same machine available to another farmer. Participants must put quantity, unit, quality/condition, date, meeting point, transport responsibility and any balancing payment in the reviewed written terms. The application does not calculate an agreed barter valuation, collect money or mark produce sold automatically.

The journey is:

1. **Open:** the two members can discuss availability.
2. **Negotiating:** either member writes the current proposed terms. Proposing replaces the earlier proposal before agreement. Only the other member can accept the current proposal.
3. **Agreed:** both parties have expressed agreement to the same terms. Each farmer records their own handover once.
4. **Handover:** both farmers have confirmed handover. Each then records their own completion once.
5. **Completed:** both completion confirmations are present. This is participant-reported completion, not externally verified physical delivery.

Cancellation is available before agreement. Once agreed, a described dispute records a problem rather than allowing one participant to erase the commitment. Disputes require operational resolution; this release has no automatic mediator or dispute-resolution workflow. No external mediator, WhatsApp recipient, supplier or transport operator is contacted. Messages remain a member-to-member record within the site.

## Mitra assistance

The workspace starts with a voice-enabled exchange brief. `POST /api/exchange/assist` prepares a partial notice, compares an owned notice's actual matches, drafts terms for an open participant conversation, or reviews its progress. Follow-up answers retain the farmer's brief within a 4,000-character limit. The model receives bounded records and returns structured suggestions; it has no mutation tools.

Notice and agreement drafts fill editable review forms. Publication still requires explicit sharing consent, and proposing or accepting terms remains a separate farmer action. Missing quantities, dates and amounts become questions rather than invented defaults. Numeric draft checks exclude metadata such as UUIDs and match scores. Assistance requires the configured AI provider and internet connectivity; an unavailable or malformed response leaves the exchange unchanged.

The server checks notice ownership and conversation participation before providing context and rechecks the session after the provider returns. Private participant conversation text may be processed by the configured provider to answer their request. Demo mode remains visibly simulated. Suggestions are not farmer verification, a transport booking, a payment, or a physical handover confirmation.

## API and ownership

All `/api/exchange` routes require the existing server-verified assistant capability (`Authorization` and `X-Assistant-Session`). A body-supplied farmer ID cannot select the caller. UUID route parameters, bounded inputs and PostgreSQL row security protect listing ownership and conversation participation.

| Endpoint | Purpose |
| --- | --- |
| `POST /assist` | Read-only listing, match, terms and progress assistance; returns unsaved drafts and questions. |
| `GET /listings` | Discover published notices; optional category, kind, state, district and text query. `mine=true` returns the caller's notices, including drafts/withdrawn notices. |
| `POST /listings` | Save a draft or explicitly consented publication. |
| `PATCH /listings/{id}` | Owner-only edit/withdrawal with the current `row_version`. |
| `GET /matches?listing_id=…` | Explain category, resource words, stated availability day and coarse regional fit for an owned notice. |
| `GET /conversations` | List the caller's bilateral conversations. |
| `POST /conversations` | Start/reconnect a conversation from a published notice with display-name consent. |
| `GET /conversations/{id}` | Participant-only current state, recent messages and action trail. |
| `GET /conversations/{id}/messages?after=…` | Incremental messages ordered by sequence; response carries `next_cursor`. |
| `POST /conversations/{id}/messages` | Send the caller's words with a stable UUID `client_key`. |
| `POST /conversations/{id}/actions` | Reviewed `propose`, `accept`, `handover`, `complete`, `cancel` or `dispute`, with `row_version` and UUID `client_key`. |

Action receipts bind replay keys to exact submitted payloads. Replaying identical work returns its original result; reusing a key for changed details fails. Concurrent/stale actions fail instead of overwriting another farmer's current state. Message keys likewise cannot be reused to change previously submitted words. Conversation and message records are not placed in shared offline caches.

## Storage and rollout

`sql/exchange-runtime.sql` is an additive, repeatable migration; it does not repoint the legacy database. Provisioning and test-database preparation apply it. Existing databases must apply it before serving the new routes.

It adds four tables: `exchange_listings`, `exchange_conversations`, `exchange_messages` and `exchange_events`. Listings have discovery/owner indexes; conversation indexes serve each participant's inbox; message/event sequence indexes serve a specific conversation. Messages and action receipts are append-only for the application writer. Private conversation access does not expand access to other farm tables.

The frontend uses bounded reads and visible-page polling rather than opening a new websocket infrastructure. This gives real persisted messages between two authenticated members, with a brief polling delay; it is not push notification delivery or a claim of WhatsApp-scale operation. A demonstration profile is fictional. A second authenticated test/demo account can exercise the other side of an exchange, but no synthetic farmer replies automatically.

Run exchange PostgreSQL contracts against `skyview_v3_test`, never against a production farmer account. `tests/data_v3/test_exchange_security.py` independently checks unauthenticated/foreign access, consent types, reconnect identity, replay-key collisions, proposal authorship, stale terms and premature completion. The main exchange test file covers the bilateral lifecycle and reservation behavior. TypeScript, frontend regression tests and desktop/mobile visual checks remain required.

## Mandi and routing boundaries

Market observations and historical charts retain their existing provenance and dates. A posted resource value or farmer-written balancing payment is an offer, not a current mandi observation. Synthetic market history and future scenarios remain visibly synthetic; the exchange does not turn them into verified rates.

Match scores are transparent resource/regional-fit scores, not probability of a successful deal. State/district similarity does not prove road proximity, availability or capacity. The exchange trail visualizes the agreement workflow; it does not track a vehicle or compute a road route.

A future road adapter can request road geometry and a travel-cost matrix from a hosted or self-managed routing engine after participants explicitly share meeting points. [OSRM's official API](https://project-osrm.org/docs/v5.24.0/api/) distinguishes ordered routes from pairwise fastest-route matrices; transport profiles depend on the graph prepared by the operator. A standard driving profile does not certify suitability for tractors or agricultural loads. Public basemap use must also follow the [OpenStreetMap tile policy](https://operations.osmfoundation.org/policies/tiles/). No public routing/tiles service was silently added to this release.

Before opening a large live community, configure verified live identity and add operational moderation/report resolution, per-identity abuse limits, retention/deletion procedures, cursor pagination for discovery/inboxes, delivery monitoring and load tests. Real participant feedback must verify that dates, local units, machine condition and transport terms are understandable. Current software workflow tests do not establish marketplace trust, physical delivery, insurance cover or production capacity.
