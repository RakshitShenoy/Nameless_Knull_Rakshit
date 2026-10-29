"""ORBIT server: serves the frontend, local map data (data/maps) and events (events.json). No API keys."""
import json, os, threading, uuid
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory

ROOT = Path(__file__).parent
DB = ROOT / "events.json"
LOCK = threading.Lock()
CITIES = {"Mumbai", "Delhi", "Bengaluru", "Chennai"}
CATEGORIES = {"Tech", "Music", "Art", "Food", "Sports", "Business"}


def load_env():
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


load_env()
app = Flask(__name__, static_folder=str(ROOT / "static"), static_url_path="/static")


def seed():
    def e(city, title, cat, venue, lat, lng, when, desc):
        return dict(id=uuid.uuid4().hex[:8], city=city, title=title, category=cat, mode="in-person",
                    venue=venue, address=venue + ", " + city, lat=lat, lng=lng, when=when, description=desc)
    return [
        e("Mumbai", "AI Hackathon", "Tech", "Jio World Centre", 19.0646, 72.8686, "2026-11-14T10:00", "24-hour build sprint."),
        e("Mumbai", "Harbour Sunset Sessions", "Music", "Gateway of India", 18.9220, 72.8347, "2026-11-08T17:30", "Live acoustic sets by the water."),
        e("Mumbai", "Founders Breakfast", "Business", "NSCI Dome", 19.0176, 72.8179, "2026-11-20T08:30", "Early-stage founder meetup."),
        e("Delhi", "Data Science Summit", "Tech", "Bharat Mandapam", 28.6180, 77.2437, "2026-11-18T09:30", "Talks on applied analytics."),
        e("Delhi", "Habitat Art Walk", "Art", "India Habitat Centre", 28.5931, 77.2250, "2026-11-10T16:00", "Gallery walk with artists."),
        e("Delhi", "Night Run 10K", "Sports", "Jawaharlal Nehru Stadium", 28.5826, 77.2338, "2026-11-22T20:00", "Community run under lights."),
        e("Bengaluru", "Cubbon Park Startup Picnic", "Business", "Cubbon Park", 12.9763, 77.5929, "2026-11-09T11:00", "Casual founder and student mixer."),
        e("Bengaluru", "Lalbagh Flower Food Fest", "Food", "Lalbagh Botanical Garden", 12.9507, 77.5848, "2026-11-15T12:00", "Street food among the gardens."),
        e("Bengaluru", "Indie Gig Night", "Music", "Phoenix Marketcity Whitefield", 12.9959, 77.6962, "2026-11-21T19:00", "Three indie bands, one stage."),
        e("Chennai", "Marina Beach Cleanup Run", "Sports", "Marina Beach", 13.0500, 80.2824, "2026-11-08T06:00", "Run and clean the shoreline."),
        e("Chennai", "Carnatic Fusion Evening", "Music", "Nehru Indoor Stadium", 13.0873, 80.2699, "2026-11-16T18:30", "Classical meets electronic."),
        e("Chennai", "Product Design Jam", "Tech", "Phoenix MarketCity Chennai", 12.9910, 80.2181, "2026-11-19T10:00", "Design sprint for students."),
    ]


def read():
    with LOCK:
        if not DB.exists():
            DB.write_text(json.dumps(seed(), indent=2))
        return json.loads(DB.read_text())


def write(events):
    with LOCK:
        DB.write_text(json.dumps(events, indent=2))


@app.get("/")
def index():
    return send_from_directory(ROOT, "index.html")


@app.get("/api/status")
def status():
    maps = ROOT / "data" / "maps"
    return jsonify(world=(maps / "world" / "land.json").exists() and (ROOT / "static" / "vendor" / "d3.min.js").exists(),
                   cities=[c for c in ("mumbai", "delhi", "bengaluru", "chennai") if (maps / c / "city.json").exists()])


@app.get("/data/<path:p>")
def data(p):
    return send_from_directory(ROOT / "data", p)


@app.get("/api/events")
def list_events():
    return jsonify(read())


@app.post("/api/events")
def create_event():
    d = request.get_json(silent=True) or {}
    err = None
    title = str(d.get("title", "")).strip()
    mode = d.get("mode")
    if not title: err = "Title is required."
    elif d.get("city") not in CITIES: err = "Choose a supported city."
    elif d.get("category") not in CATEGORIES: err = "Choose a category."
    elif mode not in ("in-person", "online", "hybrid"): err = "Choose an event type."
    lat = lng = None
    if not err and mode != "online":
        try:
            lat, lng = float(d.get("lat")), float(d.get("lng"))
            if not (-90 <= lat <= 90 and -180 <= lng <= 180): raise ValueError
        except (TypeError, ValueError):
            err = "In-person and hybrid events need a venue with valid coordinates."
    if err:
        return jsonify(error=err), 400
    ev = dict(id=uuid.uuid4().hex[:8], city=d["city"], title=title[:120], category=d["category"], mode=mode,
              venue=str(d.get("venue", ""))[:120], address=str(d.get("address", ""))[:200], lat=lat, lng=lng,
              when=str(d.get("when", ""))[:25], description=str(d.get("description", ""))[:600])
    events = read()
    events.append(ev)
    write(events)
    return jsonify(ev), 201


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
