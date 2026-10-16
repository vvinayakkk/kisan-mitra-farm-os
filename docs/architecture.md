# Application architecture

## Two views, one farm

Classic SkyView screens and the Kisan Mitra workspace are routes in the same React application. The workspace keeps chat, calendar, notebook, exchange, crop doctor, markets, weather and station within one navigation shell. The user can return to classic views without losing owned farm context.

## Reviewed assistant actions

The agent reads through typed tools. It may prepare a task, record, file or plan, but farm-changing writes pause at a review boundary. Approval binds the exact action arguments and execution identity; retries cannot silently duplicate a committed write. External messages and hardware actions require their own verified connectors.

## Source freshness and cache boundaries

Provider fetch time, source observation time and forecast issuance are distinct. Background workers lease bounded jobs and retain source health on failures. Public regional weather may use short-lived shared cache entries; owner-scoped records are invalidated when the farmer or data changes. Last-good data carries its age instead of masquerading as live.
