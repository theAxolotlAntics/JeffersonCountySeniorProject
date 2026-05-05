import json
import logging
from pathlib import Path
from PIL import Image, ImageDraw

import folium
import geopandas as gpd  # for creating the map
from geopy.geocoders import Nominatim  # for parsing the address into geocoded data
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable  # error handling for geopy
from shapely.geometry import Point  # for displaying the pinned location on the map
import time  # to allow the project to wait to avoid running into errors while requesting multiple geo-encodings in a row
import re

import subprocess
import sys

from branca.element import Template, MacroElement


#@author:  Brunner Good

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Directories & cache files
BASE_DIR = Path(__file__).parent
CACHE_DIR = BASE_DIR / "resources" / "cachedMaps"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
GEOCODE_CACHE_FILE = CACHE_DIR / "geocode_cache.json"
MIN_LAT = 40.90
MAX_LAT = 41.37
MIN_LON = -79.55
MAX_LON = -78.55

# List of status and their correlated colors
status_colors = {
    "Vacant Residential": "lightred",         
    "Vacant Commercial": "lightblue",          
    "Vacant Blighted": "lightgreen",       

    "Vacant Blighted Residential": "darkred", 
    "Vacant Blighted Commercial": "darkblue",   
    "Vacant Residential Commercial": "purple",     

    "Vacant Blighted Residential Commercial": "darkpurple", 

    "Residential": "red",         
    "Commercial": "blue",          
    "Blighted": "green",       

    "Blighted Residential": "darkred", 
    "Blighted Commercial": "darkblue",   
    "Residential Commercial": "purple",     

    "Blighted Residential Commercial": "darkpurple",  
}

# Maps folium icon color names -> CSS hex colors that closely match the actual marker icons
FOLIUM_CSS_COLORS = {
    "lightred":   "#FF8080",
    "lightblue":  "#80B3FF",
    "lightgreen": "#80D480",
    "darkred":    "#8B0000",
    "darkblue":   "#003DA6",
    "purple":     "#9C2BCB",
    "darkpurple": "#5B2A8A",
    "red":        "#D63E2A",
    "blue":       "#2A81CB",
    "green":      "#2AAD27",
    "black":      "#3D3D3D",
    "beige":      "#FFCB92",
}


def _build_legend_html(status_color_map: dict) -> str:
    """
    Builds the inner HTML for the legend rows.
    Deduplicates entries that share the same (label, color) pair so the
    legend stays compact when multiple statuses map to one color.
    """
    seen = set()
    rows = []
    for label, folium_color in status_color_map.items():
        css_color = FOLIUM_CSS_COLORS.get(folium_color, "#555555")
        key = (label, css_color)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            f'<div style="display:flex; align-items:center; margin-bottom:5px;">'
            f'  <span style="display:inline-block; width:14px; height:14px; border-radius:50%;'
            f'         background:{css_color}; border:1px solid rgba(0,0,0,0.3);'
            f'         flex-shrink:0; margin-right:8px;"></span>'
            f'  <span>{label}</span>'
            f'</div>'
        )
    return "\n".join(rows)

def _add_legend(folium_map: folium.Map, status_color_map: dict) -> None:
    """
    Injects a tidy legend into the bottom-left corner of a folium map.
    Uses MacroElement so it survives folium's HTML rendering pipeline.
    """
    rows_html = _build_legend_html(status_color_map)

    template_str = """
    {{% macro html(this, kwargs) %}}
    <div id="map-legend" style="
        position: fixed;
        bottom: 30px;
        left: 30px;
        z-index: 9999;
        background: rgba(255, 255, 255, 0.93);
        padding: 12px 16px;
        border-radius: 8px;
        border: 1px solid #aaa;
        box-shadow: 2px 2px 6px rgba(0,0,0,0.2);
        font-size: 13px;
        font-family: Arial, sans-serif;
        max-height: 80vh;
        overflow-y: auto;
        line-height: 1.4;
    ">
        <div style="font-weight:bold; margin-bottom:8px; border-bottom:1px solid #ccc; padding-bottom:4px;">
            Property Status
        </div>
        {rows}
    </div>
    {{% endmacro %}}
    """.format(rows=rows_html)

    macro = MacroElement()
    macro._template = Template(template_str)
    folium_map.get_root().add_child(macro)

def crop_to_bounds(png_path):

    img = Image.open(png_path)
    width, height = img.size

    left = 50
    top = 200
    right = width - 50
    bottom = height - 200

    # Safety check (prevents your crash)
    if right <= left or bottom <= top:
        raise ValueError(
            f"Invalid crop box: {(left, top, right, bottom)} for image size {(width, height)}"
        )

    cropped = img.crop((left, top, right, bottom))
    cropped.save(png_path)

# Reuse a single Nominatim instance (respect API usage)
GEOLocator = Nominatim(user_agent="Jefferson County Property Viewer/0.7.1 (https://github.com/theAxolotlAntics/JeffersonCountySeniorProject)", timeout=5)

# imma be honest, this is beyond me, this and the renderer are both the horrible, disfigured brainchildren of stealing stuff from stackoverflow and the like
def get_chromium_path():
    """
    Returns the path to the bundled Chromium (Chrome for Testing).
    Works both in development and inside a PyInstaller EXE.
    """
    base = getattr(sys, "_MEIPASS", Path(__file__).parent)
    chromium = Path(base) / "chromium" / "chrome.exe"
    if chromium.exists():
        return str(chromium)
    raise FileNotFoundError("Bundled Chromium not found.")

def html_to_png(html_path, png_path, width=2400, height=2400):
    browser = get_chromium_path()

    html_path = Path(html_path).resolve()
    png_path = Path(png_path).resolve()

    cmd = [
        browser,
        "--headless=new",
        "--force-device-scale-factor=2",
        "--no-sandbox",
        "--disable-gpu-sandbox",
        "--disable-dev-shm-usage",
        f"--window-size={width},{height}",
        f"--screenshot={png_path}",
        html_path.as_uri()
    ]

    subprocess.run(cmd, check=True)



def validate(val):
    """
    A little helper function that makes sure that Yes means True
    """
    return str(val).strip().lower() in ("yes", "y", "true", "1")

def _load_geocode_cache():
    if GEOCODE_CACHE_FILE.exists():
        try:
            return json.loads(GEOCODE_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Failed to read geocode cache; starting fresh.")
    return {}


def _save_geocode_cache(cache: dict):
    try:
        GEOCODE_CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning("Failed to write geocode cache: %s", e)

def geocode_address(address, label, status, cache, retries=2, delay=1.0, silent = True):
    if not address or not isinstance(address, str):
        if not silent :logger.debug("Empty or invalid address provided.")
        return None

    key = label

    if key in cache:
        lon, lat = cache[key]["lon"], cache[key]["lat"]
        if not silent : logger.debug("Geocode cache hit for address: %s", address)
        return {"lon": lon, "lat": lat, "status" : status}  # return simple dict

    for attempt in range(retries):
        try:
            location = GEOLocator.geocode(address)
            if location:
                lon, lat = location.longitude, location.latitude
                cache[key] = {"lon": lon, "lat": lat, "status" : status}  # add new entry
                _save_geocode_cache(cache)            # save full dict
                if not silent : logger.info("Geocoded address '%s' -> (%s, %s)", address, lat, lon)
                time.sleep(1.1)
                return {"lon": lon, "lat": lat, "status": status}
            else:
                if not silent : logger.info("Address not found: %s", address)
                return None
        except (GeocoderTimedOut, GeocoderUnavailable) as e:
            if not silent : logger.warning("Geocode attempt %d/%d failed for %s: %s", attempt + 1, retries, address, e)
            time.sleep(delay * (2 ** attempt))
    if not silent : logger.error("Failed to geocode after %d attempts: %s", retries, address)
    return None

def create_map(clean_address: str, ID: str, cache, status: str, force_refresh: bool = False, silent: bool = True) -> Path:
    """
    Create (or return cached) HTML map for the given address/ID.
    - clean_address: address string to geocode
    - ID: unique identifier used to name the cached HTML file
    - force_refresh: if True, recreates the map even if a cached file exists
    - silent : if set to false, error messages will be logged
    Returns the Path to the saved HTML file.
    """
    # sanitize ID for filename
    safe_id = re.sub(r'[<>:"/\\|?*]', '_', str(ID))
    filename = f"{safe_id}_Map"
    out_path = CACHE_DIR / filename
    html_path = out_path.with_suffix(".html")
    png_path = out_path.with_suffix(".png")

    if html_path.exists() and png_path.exists() and not force_refresh:
        if not silent : logger.info("Using cached map: %s", html_path)
        return out_path

    shapefile_path = BASE_DIR / "resources" / "shapeData" / "PaMunicipalities2025_07.shp"
    if not shapefile_path.exists():
        raise FileNotFoundError(f"Shapefile not found: {shapefile_path}")

    # Read shapefile and filter to Jefferson county
    municipalities = gpd.read_file(shapefile_path, engine='pyogrio')
    municipalities = municipalities.to_crs(epsg=4326)
    if 'COUNTY_NAM' not in municipalities.columns:
        if not silent : logger.warning("Expected 'COUNTY_NAM' in shapefile; skipping county filter.")
    else:
        municipalities = municipalities[municipalities['COUNTY_NAM'].str.upper() == 'JEFFERSON']

    # geocode the address and add pin if successful
    pin = geocode_address(clean_address, label=ID, cache=cache, status=status)
    color = status_colors.get(status, "black")
    if pin is not None:
        lon, lat = pin["lon"], pin["lat"] 
        
        folium_map = folium.Map(
            location=[lat, lon],
            zoom_start=14,
            tiles=None,
            min_zoom=8,
            max_zoom=16
        )
        
        folium.TileLayer(
                    tiles="file://" + str((BASE_DIR / "resources" / "tiles" / "{z}" / "{x}" / "{y}.png").resolve()),
                    attr="© OpenStreetMap contributors",
                    name="Local Tiles",
                    overlay=False,
                    control=False
        ).add_to(folium_map)
        
        # add county polygons
        folium.GeoJson(
            municipalities,
            tooltip=folium.GeoJsonTooltip(# this one shows on hover
                fields=["MUNICIPAL1"], 
                aliases=["Municipality:"],
                localize=True,
                sticky=True
            ),
            #popup=folium.GeoJsonPopup( #this one requires clicking
            #    fields=["MUNICIPAL"],  
            #    aliases=["Municipality:"],
            #    localize=True
            #)
        ).add_to(folium_map)
        # add pin
        folium.Marker([lat, lon], icon=folium.Icon(color=color), popup=ID).add_to(folium_map)
    else:
        return None  # could not geocode address      
        
    # save the folium map to cachedMaps
    try:
        folium_map.save(str(out_path.with_suffix(".html")))
        if not silent : logger.info("Saved map to: %s", out_path)
        # Screenshot to PNG
        html_to_png(html_path = out_path.with_suffix(".html"), png_path = out_path.with_suffix(".png"))

    except Exception as e:
        if not silent : logger.exception("Failed to save map to %s: %s", out_path, e)
        raise

    return out_path

def generate_full_map(geocode_cache, silent=True, force_refresh=False):
    """
    Creates a map with all addresses in the geocode_cache dict
    """
    filename = "Full_Map"
    out_path = CACHE_DIR / filename
    html_path = out_path.with_suffix(".html")
    png_path = out_path.with_suffix(".png")
    # Skip regeneration unless forced
    if html_path.exists() and png_path.exists() and not force_refresh:
        return out_path

    shapefile_path = BASE_DIR / "resources" / "shapeData" / "PaMunicipalities2025_07.shp"
    if not shapefile_path.exists():
        raise FileNotFoundError(f"Shapefile not found: {shapefile_path}")

    # Read shapefile and filter to Jefferson county
    municipalities = gpd.read_file(shapefile_path, engine='pyogrio').to_crs(epsg=4326)
    if 'COUNTY_NAM' in municipalities.columns:
        municipalities = municipalities[municipalities['COUNTY_NAM'].str.upper() == 'JEFFERSON']

    # --- Convert dict to GeoDataFrame ---
    records = []
    for addr, coords in geocode_cache.items():

        # Skip invalid or failed geocodes
        if not coords or "lon" not in coords or "lat" not in coords:
            logger.warning("Skipping invalid geocode entry: %s %s", addr, coords)
            continue

        safe_name = re.sub(r"[^A-Za-z0-9_]", "_", addr)

        records.append({
            "name": safe_name,
            "lon": coords["lon"],
            "lat": coords["lat"],
            "status": coords.get("status"),
            "geometry": Point(coords["lon"], coords["lat"])
        })

    pins_gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")

    # use the custom-built map, so that we don't get rate limited
    folium_map = folium.Map(tiles=None, min_zoom=8, max_zoom= 16, location=[41.16, -79.06])
    # Prevent map from going outside downloaded tile area
    folium_map.fit_bounds([
        [40.90, -79.55],   # southwest corner
        [41.37, -78.55]    # northeast corner
    ])
    folium_map.options['maxBounds'] = [
        [40.90, -79.55],
        [41.37, -78.55]
    ]
    folium.TileLayer(
                tiles="file://" + str((BASE_DIR / "resources" / "tiles" / "{z}" / "{x}" / "{y}.png").resolve()),
                attr="© OpenStreetMap contributors",
                name="Local Tiles",
                overlay=False,
                control=False
    ).add_to(folium_map)

    # Add county polygons
    folium.GeoJson(
        municipalities,
        tooltip=folium.GeoJsonTooltip(
            fields=["MUNICIPAL1"],
            aliases=["Municipality:"],
            localize=True,
            sticky=True
        )
    ).add_to(folium_map)
    
    # --- Add pins from GeoDataFrame ---

    for _, row in pins_gdf.iterrows():
        color = status_colors.get(row["status"], "black")
        marker = folium.Marker(
            [row["lat"], row["lon"]],
            icon=folium.Icon(color=color),
            popup=f"{row['name']}\n{row['status']}"
        )
        marker.add_to(folium_map)

    # --- Add legend ---
    _add_legend(folium_map, status_colors)
    # Force a fixed zoom level AFTER all layers are added
    folium_map.zoom_start = 12
    folium_map.location = [41.16, -79.06]

    # Save HTML
    folium_map.save(str(html_path))
    if not silent : logger.info("Saved map to: %s", html_path)

    # --- Generate PNG screenshot using  ---
    html_to_png(html_path = out_path.with_suffix(".html"), png_path = out_path.with_suffix(".png"), width=1600, height=1200)
    crop_to_bounds(png_path)
    return out_path