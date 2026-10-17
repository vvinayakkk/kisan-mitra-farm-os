# Shared app and web setup

Both phone clients use Firebase phone identity. The backend maps the verified issuer and Firebase UID to one farmer, so signing in on a laptop with the same Firebase account reads the profile, farms, fields and plans saved from Android. A session is a device capability, not a separate farmer account. Integration coverage checks two capabilities for one identity, edits visible in both directions, starter-plan idempotency, and isolation from another farmer.

The web login now opens `/workspace`. Classic remains accessible from the workspace header and retains its link back to the new interface. Signup goes through the same phone-verification entry point; setup loads the database profile before asking for details and never overwrites an existing profile with an empty signup form. Hardware enrollment is optional, not the mandatory destination after registering.

The web setup reminder offers missing profile details and the same reviewed starter routines used by Android. The server exposes the routine catalog and each routine's saved state. Saving uses the existing owner-scoped, idempotent starter-plan endpoint. Existing farm/plot records are not duplicated. Plans remain editable drafts in the notebook, rather than fabricated dated tasks.

Web custom question answers and consented nearby weather match the new Android capabilities. Device coordinates are rounded to two decimal places and used only for the regional forecast; they do not overwrite farm coordinates. Profile refresh preserves visible saved content, and background warming includes starter state and saved plans. Returning to the tab triggers the existing cache-refresh lifecycle. This is refresh-based consistency, not an instantaneous cross-device push channel.

Unfinished web edits are scoped to the local session/browser and resume after reload; unsaved app drafts remain on the app. Only successfully saved database details are shared between devices. Signing out clears local drafts. Fresh-device live SMS sign-in and production-data acceptance remain rollout checks.

## Coordinated rollout

1. Deploy the backend revision containing the v1.1.0 changes and this shared-state/catalog update. It uses existing tables; no new migration is required.
2. Verify authenticated profile and starter-plan reads, reviewed plan creation and the nearby-weather route.
3. Deploy the web build with the existing production Firebase project and API configuration.
4. Check the installed v1.1.0 APK and web with the same test account, then verify Classic navigation.

The existing v1.1.0 APK is compatible with these additive APIs; this web update does not require replacing it. Publishing source does not deploy either hosted service.

Validation: 228 frontend tests, TypeScript checking, production web build, and 460 backend tests passed. Browser checks with controlled API responses verified workspace login routing, Classic round-trip, prefilled setup, local draft resumption and desktop/390px layouts. They are not a production Firebase SMS test.
