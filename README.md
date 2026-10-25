# ORBIT

ORBIT is a local event-discovery and community platform. It combines an
interactive CesiumJS globe with an event directory, user accounts, organizer
tools, participant management, event channels, and permission-controlled
documents.

The application is designed for local development and demonstrations. It
currently supports events in **Mumbai, Delhi, Bengaluru, and Chennai**. The
map uses CesiumJS with OpenStreetMap imagery and does not require a Google Maps
API key, Google Cloud billing account, payment gateway, or Cesium ion token.

> **Important:** ORBIT is not configured for direct public-internet deployment.
> Review [Security and limitations](#security-and-limitations) before exposing
> it beyond your local machine.

## Contents

- [Features](#features)
- [Technology](#technology)
- [Project layout](#project-layout)
- [Requirements](#requirements)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Using ORBIT](#using-orbit)
  - [Explore events](#explore-events)
  - [Create an event](#create-an-event)
  - [Manage an event](#manage-an-event)
  - [Join an event](#join-an-event)
- [Data, migration, and backups](#data-migration-and-backups)
- [HTTP API](#http-api)
- [Troubleshooting](#troubleshooting)
- [Security and limitations](#security-and-limitations)
- [Development notes](#development-notes)
- [License and attribution](#license-and-attribution)

## Features

### Discover events

- Start on an interactive 3D Earth and enter a supported city.
- Browse published and cancelled events by city.
- Search event titles and venues.
- Filter events by Tech, Music, Art, Food, Sports, or Business.
- Select an event marker or list item to fly the camera to its location.
- Display event timing, venue, address, description, requirements, entry type,
  capacity, registration deadline, organizer contacts, and documents.
- Support in-person, online, and hybrid events.

### Accounts and participation

- Register with a username, email address, and password.
- Sign in with either username or email.
- Join events and enforce optional capacity limits.
- Record paid-event participation as pending until an organizer verifies payment.
- Keep participant and organizer actions behind server-side authorization checks.

### Organizer tools

- Create, edit, publish, cancel, archive, or save event drafts.
- Add or replace an event banner.
- Manage organizer contacts with per-field public visibility controls.
- Create public, organizer-only, or restricted event channels.
- Mark channels as announcements-only.
- Grant or revoke restricted-channel membership.
- Review participants and manually update payment status.
- Upload public, participant-only, or restricted event documents.
- View an audit trail of organizer actions in the SQLite database.

### Community channels

Event channels persist messages in SQLite and refresh periodically in the
browser. Access is enforced on the server:

- **Event participants:** available to joined participants and the organizer.
- **Organizers only:** available only to the event owner.
- **Restricted:** available only to participants explicitly granted access.
- **Announcements-only:** organizers can post; participants can read.

## Technology

| Layer | Implementation |
| --- | --- |
| Backend | Python 3.10+ and Flask |
| Frontend | Plain HTML, CSS, and JavaScript |
| Globe and map | CesiumJS 1.127 |
| Map imagery | OpenStreetMap tiles |
| Persistence | SQLite (`orbit.db`) |
| Authentication | Flask sessions and Werkzeug password hashes |
| Uploads | Local `uploads/` directory with extension, size, and signature checks |
| Dependencies | Flask only; browser assets load from configured CDNs |

## Project layout

```text
.
├── ORBIT_Community_Upgrade (1)/
│   ├── index.html          Browser UI and client-side application logic
│   ├── server.py           Flask application, routes, database setup, and auth
│   ├── requirements.txt    Python dependencies
│   ├── orbit.db            Local SQLite database (created/updated at runtime)
│   └── uploads/            Event banners and documents (created at runtime)
├── LICENSE
├── .gitignore
└── README.md
```

The application files are inside the `ORBIT_Community_Upgrade (1)` directory.
Run all Python commands from that directory.

## Requirements

- Python 3.10 or newer
- Internet access when loading CesiumJS, OpenStreetMap tiles, and the Google
  Fonts stylesheet used by the interface
- A modern browser such as Chrome, Edge, or Firefox

No Node.js, frontend build step, map API key, or separate database server is
required.

## Quick start

### Windows PowerShell

```powershell
Set-Location ".\ORBIT_Community_Upgrade (1)"
python -m pip install -r requirements.txt
python server.py
```

If the `python` command is unavailable, use the Python launcher:

```powershell
py -m pip install -r requirements.txt
py .\server.py
```

### Windows Command Prompt

```bat
cd "ORBIT_Community_Upgrade (1)"
python -m pip install -r requirements.txt
python server.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) after the server starts.
Stop the development server with `Ctrl+C`.

On first launch, ORBIT automatically:

1. Creates the SQLite schema in `orbit.db`.
2. Creates `uploads/` for uploaded media.
3. Generates `.orbit_secret` when `ORBIT_SECRET_KEY` is not configured.
4. Seeds a small set of demonstration events when the database is empty.

## Configuration

ORBIT reads a `.env` file from the application directory when present. The
most important setting is:

```dotenv
ORBIT_SECRET_KEY=replace-with-a-long-random-value
```

For local development, omitting the setting causes a random key to be saved in
`.orbit_secret`. Set a persistent `ORBIT_SECRET_KEY` for any environment where
sessions must survive restarts. Never commit `.env`, `.orbit_secret`, uploaded
private files, or a production database containing personal data.

## Using ORBIT

### Explore events

1. Open the local URL.
2. Select **Mumbai**, **Delhi**, **Bengaluru**, or **Chennai** at the bottom of
   the globe.
3. Search by event or venue, or select a category chip.
4. Select an event from the list or its map marker.
5. Use **Earth** to return to the global view.

Online events appear in the event list but do not have a physical map marker.
Physical and hybrid events require valid latitude and longitude values.

### Create an event

1. Select **Sign in** and register or log in.
2. Enter a city view and select **Host an event**.
3. Provide the title, category, event type, start time, and optional end time.
4. For an in-person or hybrid event, provide the venue coordinates. You can
   copy coordinates from OpenStreetMap.
5. Add the description, requirements, entry type, capacity, and optional
   banner.
6. Select **Create event**.

Passwords must be at least 10 characters. Event titles are limited to 120
characters, descriptions and requirements to 4,000 characters, and uploaded
files to 12 MB.

### Manage an event

Open an event you own and select the organizer controls to access the dashboard.
From there you can:

- Update event details and status.
- Upload or remove a banner.
- Create and edit channels.
- Add organizer contacts and choose which contact fields are public.
- Review participants and update payment status.
- Upload documents with public, participant, or restricted access.

Payment is recorded manually. ORBIT does not process money or verify payments
with a payment provider.

### Join an event

Sign in, open a published event, and select the join action. Free events are
immediately marked as joined. Paid events receive a pending payment status
until the organizer verifies them. Joining an event is required before a user
can access participant channels or participant documents.

## Data, migration, and backups

The current application stores data in SQLite:

- `orbit.db` contains users, events, memberships, channels, messages, contacts,
  documents, and audit records.
- `uploads/` contains event banners and uploaded documents.
- `.orbit_secret` contains the automatically generated session-signing secret
  when no environment variable is configured.

Back up `orbit.db`, `uploads/`, and `.orbit_secret` together. Restoring only the
database without the uploads directory can leave banner and document records
pointing to missing files.

Older ORBIT versions may have an `events.json` file. To migrate it, copy the
file into the application directory **before the first launch**. The startup
migration imports valid records into SQLite and preserves the original JSON.
The first account created on a migrated local installation becomes the owner
of legacy events that do not already have an owner. Demo events are not claimed
by that account.

## HTTP API

The Flask server exposes JSON endpoints used by the frontend. The API is
available at the same host and port as the web interface.

| Method | Endpoint | Purpose | Auth |
| --- | --- | --- | --- |
| `GET` | `/api/health` | Report storage and map configuration | No |
| `GET` | `/api/me` | Return the current user, if signed in | No |
| `POST` | `/api/register` | Create an account and sign in | No |
| `POST` | `/api/login` | Start a session | No |
| `POST` | `/api/logout` | End the current session | No |
| `GET` | `/api/events` | List published/cancelled events; optional `?city=` filter | No |
| `GET` | `/api/events/<event_id>` | Read one event | No |
| `POST` | `/api/events` | Create an event | User |
| `PATCH` | `/api/events/<event_id>` | Update an owned event | Owner |
| `POST` | `/api/events/<event_id>/join` | Join an event | User |
| `GET` | `/api/my-events` | List events owned by the current user | User |
| `GET` | `/api/events/<event_id>/participants` | List participants | Owner |
| `PATCH` | `/api/events/<event_id>/participants/<user_id>` | Update payment status | Owner |
| `POST` | `/api/events/<event_id>/channels` | Create a channel | Owner |
| `PATCH` | `/api/channels/<channel_id>` | Update a channel | Owner |
| `DELETE` | `/api/channels/<channel_id>` | Delete a channel | Owner |
| `GET` | `/api/channels/<channel_id>/messages` | Read accessible messages | Member |
| `POST` | `/api/channels/<channel_id>/messages` | Post an accessible message | Member |
| `POST` | `/api/events/<event_id>/banner` | Upload a banner | Owner |
| `POST` | `/api/events/<event_id>/documents` | Upload an event document | Owner |
| `GET` | `/api/documents/<document_id>/download` | Download an authorized document | Eligible user |
| `GET` | `/media/<filename>` | Serve a referenced event banner | No |

Unauthorized requests return JSON errors with an appropriate HTTP status. The
frontend sends session cookies with API requests.

## Troubleshooting

### Flask is missing

Run the dependency installation from the application directory:

```powershell
python -m pip install -r requirements.txt
```

### Port 5000 is already in use

Stop the other local ORBIT process, or change the `port=5000` value in
`server.py` and open the matching URL. The built-in server binds to
`127.0.0.1` by default.

### The globe or imagery is blank

Check internet access and the browser Developer Tools **Console** and
**Network** tabs. CesiumJS and OpenStreetMap tiles are loaded remotely, so
content blockers, offline mode, or tile-service availability can affect the
map.

### An upload is rejected

Files must use an allowed image or document extension, must not exceed 12 MB,
and must not match common executable/script signatures. Rename the file only
after confirming it is a supported, non-executable document.

### Events or uploads disappear

Confirm that the server is running from the application directory and that the
process can write to `orbit.db` and `uploads/`. Restore those files together
from a backup if the local data was moved.

## Security and limitations

- Use a strong, persistent `ORBIT_SECRET_KEY` outside local development.
- The application uses Flask's built-in development server and is not hardened
  for public deployment.
- Registration is open and there is no email verification, password reset, or
  administrator provisioning workflow.
- The current version does not provide production CSRF protection, rate
  limiting, HTTPS termination, centralized logging, or automated backups.
- Paid-event status is manually verified; no payment is processed.
- Chat uses periodic polling rather than WebSockets and returns a bounded recent
  message history.
- Organizer contacts are profile entries, not separate co-organizer accounts.
- OpenStreetMap public tile servers have usage policies. Follow the
  [OpenStreetMap tile usage policy](https://operations.osmfoundation.org/policies/tiles/)
  and retain required attribution.
- Uploaded files are stored locally. Use a dedicated object store, malware
  scanning, access logging, and a retention policy before production use.

## Development notes

There is no frontend build pipeline. `index.html` contains the interface,
styles, and browser logic, while `server.py` contains the Flask routes and
database initialization. A basic health check is available at
[`/api/health`](http://127.0.0.1:5000/api/health).

For a more implementation-focused guide located beside the app files, see the
[application README](<ORBIT_Community_Upgrade (1)/README.md>).

## License and attribution

See [LICENSE](LICENSE) for the repository license. Map imagery is provided by
OpenStreetMap contributors. CesiumJS, Flask, Werkzeug, and the other referenced
libraries remain under their respective licenses.
