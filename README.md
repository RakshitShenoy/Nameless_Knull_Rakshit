# ORBIT

ORBIT is an interactive event-discovery application that lets people explore events
from a global Earth view down to real city streets. It starts in space, moves to
Earth, and then transitions into a detailed local map for **Mumbai, Delhi,
Bengaluru, or Chennai**.

The app is intentionally lightweight:

- **Backend:** Python and Flask
- **Frontend:** Plain HTML, CSS, and JavaScript
- **Rendering:** Canvas and D3 geo utilities
- **Data:** Natural Earth and OpenStreetMap extracts
- **Storage:** A local `events.json` file
- **External services:** No API keys, hosted map services, database, or Node.js required

## Contents

- [Quick start](#quick-start)
- [Prepare map data](#prepare-map-data)
- [Start the application](#start-the-application)
- [Use ORBIT](#use-orbit)
- [Create an event](#create-an-event)
- [Project structure](#project-structure)
- [How the application works](#how-the-application-works)
- [Data sources and licensing](#data-sources-and-licensing)
- [API endpoints](#api-endpoints)
- [Refresh map data](#refresh-map-data)
- [Troubleshooting](#troubleshooting)
- [Known limitations](#known-limitations)

## Quick start

From the project directory, run:

```bash
pip install -r requirements.txt
python prepare_data.py
python server.py
```

Then open [http://127.0.0.1:5000](http://127.0.0.1:5000) in a browser.

The first two commands install dependencies and download the map data. The
download requires an internet connection, but ORBIT runs from the prepared local
files afterward.

### Windows

The Python launcher can be used if `python` is not on `PATH`:

```powershell
py -m pip install -r requirements.txt
py .\prepare_data.py
py .\server.py
```

Open [http://localhost:5000](http://localhost:5000).

## Prepare map data

`prepare_data.py` downloads and converts the geographic data used by the frontend.
Run it once before starting ORBIT:

```bash
python prepare_data.py
```

It downloads:

1. World land, country borders, lakes, rivers, and populated places from Natural
   Earth.
2. Roads, buildings, waterways, coastline, parks, and rail data for each
   supported city from OpenStreetMap through Overpass.
3. The local D3 browser library used for geographic projections.

The script creates the `data/maps` directory and `static/vendor/d3.min.js`.
If the data is missing, the application displays a setup message instead of the
interactive maps.

## Start the application

Start the Flask server from the project directory:

```bash
python server.py
```

The server listens on `127.0.0.1:5000` by default. Visit:

- [ORBIT frontend](http://127.0.0.1:5000/)
- [API status](http://127.0.0.1:5000/api/status)
- [Event API](http://127.0.0.1:5000/api/events)

Stop the server with `Ctrl+C`.

## Use ORBIT

### 1. Explore the Earth

The opening view is an orthographic globe. You can:

- Drag to rotate the globe.
- Scroll or use a trackpad to zoom.
- Select a highlighted city to travel into its local map.
- See day/night shading based on the current UTC time.
- See city lights on the night side.

### 2. Explore a city

After selecting a city, ORBIT flies from the globe into the matching city map.
The city view includes:

- Roads drawn by road hierarchy.
- Water and coastline.
- Parks and other green spaces.
- Rail lines.
- Building footprints.
- Building extrusion at high zoom when height data is available.
- Event markers for in-person and hybrid events.

Use **Back to Earth** to return to the globe.

### 3. Find events

The city panel provides:

- Text search across event title, venue, description, and category.
- Category filters for Tech, Music, Art, Food, Sports, and Business.
- A scrollable event list sorted by date and time.
- Clickable event markers on the map.
- A detail card for the selected event.

Online events appear in the event list but do not have a map marker because they
do not require a physical location.

## Create an event

1. Enter a city and open its city map.
2. Select **Create event**.
3. Enter a title, category, event type, date, and time.
4. For an **in-person** or **hybrid** event, click the location map to place the
   pin. Drag the pin to adjust it.
5. Add the venue, address, and description.
6. Select **Publish event**.

The event is validated by Flask and appended to `events.json`. In-person and
hybrid events must have valid latitude and longitude values. Online events do
not require a map location.

## Project structure

```text
.
├── index.html             Frontend UI, styles, map classes, and application logic
├── server.py              Flask server and event API
├── prepare_data.py        Geographic data downloader and converter
├── requirements.txt       Python dependencies
├── events.json            Local event store, created or updated by the server
├── data/
│   └── maps/
│       ├── world/         Natural Earth world GeoJSON files
│       └── <city>/        OpenStreetMap city extracts
└── static/
    └── vendor/
        └── d3.min.js      Local D3 library downloaded during preparation
```

## How the application works

### Frontend

`index.html` contains the complete browser application. It uses independent
canvas map instances so the Earth view, city view, and event-location picker
each maintain their own camera, markers, and interactions.

The main map components are:

- **EarthMap:** Renders the globe, borders, water, rivers, populated places,
  day/night shading, and city entry points.
- **CityMap:** Renders the selected city's OSM-derived roads, buildings, water,
  parks, rail, and event markers.
- **LocationPickerMap:** Provides the map embedded in the Create event dialog.
- **Transitions:** Animates the flight from Earth to a city and fades between
  map views.

### Backend

`server.py` serves the frontend and local geographic files and exposes the
event API. It uses a lock when reading or writing `events.json` so concurrent
requests do not overwrite each other.

## Data sources and licensing

- **Natural Earth:** World geographic data; public domain.
- **OpenStreetMap:** City map data; © OpenStreetMap contributors and available
  under the Open Database License (ODbL).
- **D3:** Distributed locally from the D3 project during data preparation.

The application displays an attribution notice for Natural Earth and
OpenStreetMap in the frontend.

## API endpoints

### `GET /api/status`

Reports whether the world assets are ready and which city datasets exist:

```json
{
  "world": true,
  "cities": ["mumbai", "delhi", "bengaluru", "chennai"]
}
```

### `GET /api/events`

Returns all events stored in `events.json`.

### `POST /api/events`

Creates an event from a JSON request. Required values include:

- `title`
- `city`
- `category`
- `mode`: `in-person`, `online`, or `hybrid`

In-person and hybrid events also require numeric `lat` and `lng` values.

## Refresh map data

Refresh all world and city data:

```bash
python prepare_data.py
```

Refresh only one city:

```bash
python prepare_data.py mumbai
python prepare_data.py delhi
python prepare_data.py bengaluru
python prepare_data.py chennai
```

The city extracts cover approximately 5.5 km by 5.5 km around each city centre.
This area is controlled by `HALF` in `prepare_data.py`.

## Troubleshooting

### The browser shows “Map data not found”

Run the dependency installation and preparation steps, then restart Flask:

```bash
python -m pip install -r requirements.txt
python prepare_data.py
python server.py
```

### Port 5000 is already in use

Stop the process using port 5000, or run the Flask app with a different port by
changing the `port` value in the `app.run(...)` call in `server.py`. Then open
the matching URL, for example `http://127.0.0.1:5001`.

### Map preparation fails

The preparation step needs internet access because it downloads Natural Earth,
D3, and OpenStreetMap data. Retry later if an Overpass server is unavailable.
The script tries more than one Overpass endpoint.

### Changes to events do not appear

Reload the page after publishing an event. Confirm that `events.json` is
writable and that the Flask process is running from the project directory.

## Known limitations

- No terrain relief, clouds, or place and road labels are rendered.
- Large water bodies represented only as OSM relations are not included;
  coastline sea fill and closed water ways are supported.
- Buildings without a height tag use a default height of 8 metres.
- Geographic search is not implemented; search only filters loaded events.
- Event storage is a local JSON file and is not intended for multi-user
  production deployment.
