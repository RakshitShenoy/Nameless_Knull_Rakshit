# ORBIT — local event discovery and community platform

ORBIT is a Flask application with a CesiumJS globe and OpenStreetMap imagery. It does **not** require a Google Maps API key, Google Cloud billing, a payment gateway, or a Cesium ion token for the configured basic globe.

## Windows setup

1. Install Python 3.10 or newer.
2. Extract this project into a folder.
3. **If you have an existing `events.json` from your older ORBIT folder, copy it into this new folder before the first launch.** The app imports its event records into SQLite on startup. Keep your old project and data as a backup until you've checked the migration.
4. Open the extracted folder in File Explorer, click the address bar, type `cmd`, and press Enter.
5. Run:

   ```bat
   python -m pip install -r requirements.txt
   python server.py
   ```

6. Open <http://127.0.0.1:5000> in Chrome.
7. Register an account. The first account in a local migrated installation becomes the owner of legacy events because the old app did not have user accounts.

The app creates `orbit.db`, `.orbit_secret`, and `uploads/` automatically. Keep these files/folders together with `server.py`; they contain your local database, session-signing secret, and uploaded media.

## Current features

- Interactive CesiumJS globe with OpenStreetMap tiles and attribution.
- Event markers at saved latitude/longitude and camera flight to the selected event.
- Event search and category filters for Mumbai, Delhi, Bengaluru, and Chennai.
- Account registration and sign-in for local use.
- Event creation and editing, including timing, venue, requirements, fee/capacity fields, and publication status.
- Event banner upload and organizer contact management with per-field public visibility.
- Event channels with organizer-only, participant, restricted, and announcements-only settings.
- Persistent channel messages with five-second refresh polling.
- Participant join records and manual payment status verification.
- Restricted channel membership grants/revocation with server-side access checks; paid-event access requires verified status.
- Event document uploads and permission-checked downloads.
- SQLite persistence and import of the previous `events.json` format.

## Important limitations

- This is a **local-development version**, not ready to expose directly to the public internet. Before public deployment, configure a strong persistent `ORBIT_SECRET_KEY`, HTTPS, production-grade session/CSRF protections, rate limiting, backups, and a production server.
- User registration is open. The first account claims legacy events only to support migration from the previous local version. Do not deploy this first-run migration behavior as-is in a public multi-user service.
- Chat is persistent with periodic refresh, not WebSocket push. Message history is limited to the most recent 100 messages per request.
- Event payment is recorded manually; no financial transaction is processed or automatically verified.
- Organizer contacts are contact entries, not separate authenticated co-organizer accounts. Only the event owner has administrative access in this version.
- The current geocoding flow uses manually entered coordinates. Copy coordinates from OpenStreetMap or use a map coordinate picker in a future iteration; no Google Places API is used.
- OpenStreetMap public tile servers have usage policies and are not an unlimited commercial tile service. Respect <https://operations.osmfoundation.org/policies/tiles/> and attribution requirements.
- Uploaded files are limited to 12 MB each and a conservative allowlist of formats.

## Data and backup

Back up `orbit.db` and `uploads/` together. If you are migrating from an older version, retain the original `events.json` until you have verified the imported events. The original JSON is not overwritten or deleted by the importer.

## Troubleshooting

- If Python says Flask is missing, run `python -m pip install -r requirements.txt` from the project folder.
- If port 5000 is already in use, stop the other ORBIT server before starting this one.
- If map imagery is blank, check internet connectivity and the browser Developer Tools Network/Console tabs for failed CesiumJS or `tile.openstreetmap.org` requests.
- Never put API keys or passwords into frontend HTML or commit `.orbit_secret`, `orbit.db`, or uploaded private documents to a public repository.
