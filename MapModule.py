import json
import logging
from pathlib import Path
import math
from PIL import Image, ImageDraw

import folium
import geopandas as gpd  # for creating the map
from geopy.geocoders import Nominatim  # for parsing the address into geocoded data
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable  # error handling for geopy
from shapely.geometry import Point  # for displaying the pinned location on the map
import time  # to allow the project to wait to avoid running into errors while requesting multiple geo-encodings in a row
import re

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import base64

#@author:  Brunner Good

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Directories & cache files
BASE_DIR = Path(__file__).parent
CACHE_DIR = BASE_DIR / "resources" / "cachedMaps"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
GEOCODE_CACHE_FILE = CACHE_DIR / "geocode_cache.json"

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

# Reuse a single Nominatim instance (respect API usage)
GEOLocator = Nominatim(user_agent="Jefferson County Property Viwer/0.7.1 (https://github.com/theAxolotlAntics/JeffersonCountySeniorProject", timeout=5)


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

def geocode_address(address, label, status, cache, retries=2, delay=1.0):
    if not address or not isinstance(address, str):
        logger.debug("Empty or invalid address provided.")
        return None

    key = label

    if key in cache:
        lon, lat = cache[key]["lon"], cache[key]["lat"]
        logger.debug("Geocode cache hit for address: %s", address)
        return {"lon": lon, "lat": lat, "status" : status}  # return simple dict

    for attempt in range(retries):
        try:
            location = GEOLocator.geocode(address)
            if location:
                lon, lat = location.longitude, location.latitude
                cache[key] = {"lon": lon, "lat": lat, "status" : status}  # add new entry
                _save_geocode_cache(cache)            # save full dict
                logger.info("Geocoded address '%s' -> (%s, %s)", address, lat, lon)
                time.sleep(1.1)
                return {"lon": lon, "lat": lat, "status": status}
            else:
                logger.info("Address not found: %s", address)
                return None
        except (GeocoderTimedOut, GeocoderUnavailable) as e:
            logger.warning("Geocode attempt %d/%d failed for %s: %s", attempt + 1, retries, address, e)
            time.sleep(delay * (2 ** attempt))
    logger.error("Failed to geocode after %d attempts: %s", retries, address)
    return None

def generate_full_map(geocode_cache):
    """
    Creates a map with all addresses in the geocode_cache dict
    """
    filename = "Full_Map"
    out_path = CACHE_DIR / filename
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
            print("Skipping invalid geocode entry:", addr, coords)
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
    folium_map = folium.Map(
                location=[41.16, -79.06],
                zoom_start=12,
                tiles=None
    )
    # Add JS for zooming to markers
    folium_map.get_root().html.add_child(folium.Element("""
<script>

var markerIndex = {};

function registerMarker(name, marker) {
    markerIndex[name] = marker;
}

function zoomToMarker(name) {
    var m = markerIndex[name];
    if (m) {
        map.setView(m.getLatLng(), 17);
        m.openPopup();
    }
}

window.onload = function() {
    const params = new URLSearchParams(window.location.search);
    const target = params.get("target");
    if (target) {
        zoomToMarker(target);
    }
};

</script>
    """))
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

        # Register marker in JS
        folium_map.get_root().html.add_child(folium.Element(
            f"<script>registerMarker('{row['name']}', {marker.get_name()});</script>"
        ))
    # Save HTML
    html_path = out_path.with_suffix(".html")
    folium_map.save(str(html_path))
    logger.info("Saved map to: %s", html_path)

    # --- Generate PNG screenshot using Selenium ---
    png_path = out_path.with_suffix(".png")

    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--window-size=1200,900")

        driver = webdriver.Chrome(options=chrome_options)
        driver.get(html_path.as_uri())

        # wait for tiles to load
        time.sleep(2.5)

        screenshot = driver.get_screenshot_as_png()
        with open(png_path, "wb") as f:
            f.write(screenshot)

        driver.quit()
        logger.info("Saved PNG screenshot to: %s", png_path)

    except Exception as e:
        logger.error("Failed to generate PNG screenshot: %s", e)
        png_path = None

    return png_path

def generate_property_preview(full_map_html, safe_name, out_path):
    """
    Loads the full map in Selenium, zooms to the specific marker,
    and screenshots the viewport as a PNG preview.
    """

    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--window-size=600,600")

        driver = webdriver.Chrome(options=chrome_options)
        driver.get(full_map_html.as_uri())

        # Wait for map JS to load
        time.sleep(1.2)

        # Run your built-in JS zoom function
        driver.execute_script(f"zoomToMarker('{safe_name}')")

        # Wait for tiles to load at the new zoom
        time.sleep(1.2)

        # Screenshot
        screenshot = driver.get_screenshot_as_png()
        with open(out_path, "wb") as f:
            f.write(screenshot)

        driver.quit()
        return out_path

    except Exception as e:
        logger.error("Failed to generate property preview: %s", e)
        return None
