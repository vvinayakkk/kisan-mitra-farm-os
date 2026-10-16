# Streaming and webhook channels

The assistant run endpoint streams ordered activity and answer events over an HTTP response. The client can resume its owned conversation using persisted session events; it does not need a separate WebSocket server. Live voice captures a turn, transcribes it, sends it through the assistant task path and synthesizes a spoken answer when speech providers are configured. Microphone access remains a browser/device permission.

`skyview/api/v3_voice_routes.py` serves speech capabilities, transcription and synthesis in canonical mode. `skyview/api/v3_whatsapp_routes.py` handles linked WhatsApp identity, signed Twilio callbacks, bounded media retrieval and delivery state. The webhook validates provider signatures and replay identity before associating content with a farmer. Outbound delivery is a distinct channel action; an assistant draft is not a sent message. The retained legacy webhook and voice routers are registered only in legacy mode.

The exchange UI uses bounded HTTP polling for participant messages and events. It does not claim real-time push delivery or vehicle tracking. Device packets use authenticated station enrollment and receipt checks through the canonical sensor routes; a UI animation is not hardware evidence.
