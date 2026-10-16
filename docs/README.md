# Kisan Mitra documentation

The [project README](../README.md) introduces the AI Builder Cup application and its local run path. These guides describe the current source tree and review boundaries.

| Guide | Coverage |
| --- | --- |
| [Features](features.md) | Farm OS views, classic pages, task semantics and language. |
| [Architecture](architecture.md) | Service topology, identity, data flow, worker and file boundaries. |
| [Assistant](assistant.md) | Run lifecycle, memory, approvals and the complete skill/tool registry. |
| [API overview](api/overview.md) | Identity, transport, health and caching. |
| [Endpoint inventory](api/endpoints.md) | Registered canonical and legacy HTTP routes. |
| [Channels](api/websocket-and-webhooks.md) | Streaming, voice, WhatsApp and device traffic. |
| [Data model](data-model.md) | Base tables, source catalog, provenance and SQL paths. |
| [Configuration](configuration.md) | Backend environment inventory and secret boundaries. |
| [Operations](operations.md) | Configuration, background jobs, backup, deployment and checks. |
| [Local operation](local-setup.md) | Native Python/Node development and test database setup. |
| [Mobile](mobile/README.md) | Flutter Farm OS client, identity lifecycle, permissions and release signing. |
| [Mobile parity](mobile/parity.md) | Feature and API parity between the web Farm OS and the phone app. |
| [Hardware](hardware/README.md) | HLS/RTL source, station packets and commissioning boundary. |
| [Project map](project-map.md) | Source directory responsibilities. |

The detailed data-platform contracts remain in [`data_platform/v3/`](../data_platform/v3/README.md). Contribution standards are in [CONTRIBUTING.md](../CONTRIBUTING.md).
