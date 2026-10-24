# ORBIT

Event discovery on a real Earth: space, then Earth, then city (Mumbai, Delhi, Bengaluru, Chennai).
Python (Flask) server + plain HTML/CSS/JS. **No API keys, no map services, no Node.js.**

## Run
```bash
pip install -r requirements.txt
python prepare_data.py     # one-time download of open map data (needs internet)
python server.py
```
Open http://127.0.0.1:5000. After `prepare_data.py` ORBIT works fully offline. Without the data it shows a setup screen.

## Where the geographic data lives
```
data/maps/world/{land,countries,lakes,rivers,places}.json   Natural Earth 1:50m (public domain)
data/maps/<city>/city.json                                   OpenStreetMap extract (ODbL): roads, building footprints,
                                                             water, sea (built from coastlines), parks, rail
static/vendor/d3.min.js                                      rendering library, downloaded by prepare_data.py
events.json                                                  ORBIT events (created on first run)
```
Each city covers about 5.5 km x 5.5 km around its centre (`HALF` in `prepare_data.py`). Re-run `python prepare_data.py mumbai` to refresh one city.

## Architecture
`static/index.html` defines independent map classes, each with its own canvas, camera and markers:
- `EarthMap`: orthographic globe with real coastlines, borders, lakes, rivers, day/night from the current UTC time, and city lights on the night side.
- `CityMap`: renders the OSM data (road hierarchy, water, parks, footprints; buildings extrude at high zoom using real height or levels where tagged).
- `LocationPickerMap`: a separate `CityMap` in the Create Event dialog; click to place the pin, drag to move it, coordinates are saved with the event.
- Earth to city: the globe flies to the city, then cross-fades into the `CityMap` at the matching scale. Leaving the city reverses it.

## Known limits
- No terrain relief, clouds or place/road labels yet (the extract keeps no names).
- Water bodies mapped as OSM relations (large multipolygons) are not included; coastline sea fill and closed water ways are.
- Buildings without a height tag use a default of 8 m.
- Geographic search is not implemented; ORBIT search only searches events.
