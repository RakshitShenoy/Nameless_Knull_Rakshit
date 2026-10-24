"""Download real open geographic data once, then ORBIT runs fully offline with no API keys.

    pip install -r requirements.txt
    python prepare_data.py            # all cities
    python prepare_data.py mumbai     # one city

World: Natural Earth (public domain). Cities: OpenStreetMap via the Overpass API (c) OpenStreetMap contributors, ODbL.
Needs internet and `shapely` (used only here, to build sea polygons from OSM coastlines).
"""
import json, sys, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "data" / "maps"
NE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
WORLD = {"land": "ne_50m_land", "countries": "ne_50m_admin_0_countries", "lakes": "ne_50m_lakes",
         "rivers": "ne_50m_rivers_lake_centerlines", "places": "ne_50m_populated_places_simple"}
CITIES = {"mumbai": (19.0760, 72.8777), "delhi": (28.6139, 77.2090),
          "bengaluru": (12.9716, 77.5946), "chennai": (13.0827, 80.2707)}
HALF = 0.025  # degrees each way (~2.8 km): keeps the files small. Raise for a larger area.
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]
ROAD = {"motorway": 0, "trunk": 0, "motorway_link": 0, "trunk_link": 0, "primary": 1, "primary_link": 1,
        "secondary": 2, "secondary_link": 2, "tertiary": 3, "tertiary_link": 3, "residential": 4,
        "unclassified": 4, "living_street": 4, "service": 5}


def get(url, data=None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "ORBIT-local-demo/1.0"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def world():
    (OUT / "world").mkdir(parents=True, exist_ok=True)
    for name, f in WORLD.items():
        print("world:", name)
        (OUT / "world" / f"{name}.json").write_bytes(get(NE + f + ".geojson"))
    v = ROOT / "static" / "vendor"
    v.mkdir(parents=True, exist_ok=True)
    print("d3 (rendering library, served locally)")
    (v / "d3.min.js").write_bytes(get("https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js"))


def overpass(b):
    s, w, n, e = b
    bb = f"{s},{w},{n},{e}"
    q = (f'[out:json][timeout:240];(way["highway"]({bb});way["building"]({bb});way["natural"~"^(water|coastline|bay)$"]({bb});'
         f'way["waterway"~"^(river|canal|stream|drain)$"]({bb});way["leisure"~"^(park|garden|pitch)$"]({bb});'
         f'way["landuse"~"^(grass|forest|recreation_ground|meadow)$"]({bb});way["railway"~"^(rail|subway|light_rail)$"]({bb}););out geom;')
    for url in OVERPASS * 2:
        try:
            return json.loads(get(url, urllib.parse.urlencode({"data": q}).encode()))
        except Exception as ex:
            print("  overpass retry:", ex)
            time.sleep(8)
    raise SystemExit("Overpass unavailable, try again later.")


def sea_rings(coast, b):
    """Close OSM coastlines against the bbox and keep polygons on the water side (OSM: water is on the right)."""
    from shapely.geometry import LineString, box
    from shapely.ops import unary_union, polygonize
    s, w, n, e = b
    lines = [LineString(c) for c in coast if len(c) > 1]
    if not lines:
        return []
    out = []
    for p in polygonize(unary_union(lines + [box(w, s, e, n).boundary])):
        pt = p.representative_point()
        ln = min(lines, key=lambda l: l.distance(pt))
        d = ln.project(pt)
        a, c = ln.interpolate(max(d - 1e-6, 0)), ln.interpolate(d + 1e-6)
        if (c.x - a.x) * (pt.y - a.y) - (c.y - a.y) * (pt.x - a.x) < 0:
            out.append([[round(x, 5), round(y, 5)] for x, y in p.exterior.coords])
    return out


def num(v):
    try:
        return float(str(v).split()[0].replace("m", ""))
    except Exception:
        return None


def city(name):
    lat, lng = CITIES[name]
    b = (lat - HALF, lng - HALF, lat + HALF, lng + HALF)
    print(f"{name}: downloading OSM data")
    L = dict(center=[lng, lat], bbox=[b[1], b[0], b[3], b[2]], sea=[], water=[], waterways=[], parks=[], roads=[], rail=[], buildings=[])
    coast = []
    for el in overpass(b)["elements"]:
        g = el.get("geometry")
        t = el.get("tags", {})
        if not g or len(g) < 2:
            continue
        c = [[round(p["lon"], 5), round(p["lat"], 5)] for p in g]
        closed = len(c) > 3 and c[0] == c[-1]
        if "building" in t and closed:
            h = num(t.get("height")) or ((num(t.get("building:levels")) or 0) * 3.2)
            L["buildings"].append([round(h, 1), c])
        elif "highway" in t and t["highway"] in ROAD:
            L["roads"].append([ROAD[t["highway"]], c])
        elif t.get("natural") == "coastline":
            coast.append(c)
        elif t.get("natural") in ("water", "bay") and closed:
            L["water"].append(c)
        elif "waterway" in t:
            L["waterways"].append(c)
        elif "railway" in t:
            L["rail"].append(c)
        elif closed and (t.get("leisure") or t.get("landuse")):
            L["parks"].append(c)
    try:
        L["sea"] = sea_rings(coast, b)
    except ImportError:
        print("  shapely missing: sea polygons skipped (pip install shapely)")
    d = OUT / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "city.json").write_text(json.dumps(L, separators=(",", ":")))
    print(f"  {len(L['roads'])} roads, {len(L['buildings'])} buildings, {len(L['sea'])} sea polygons")


if __name__ == "__main__":
    names = [a.lower() for a in sys.argv[1:]] or list(CITIES)
    if not (OUT / "world" / "land.json").exists():
        world()
    for n in names:
        city(n)
    print("Done. Start the app with: python server.py")
