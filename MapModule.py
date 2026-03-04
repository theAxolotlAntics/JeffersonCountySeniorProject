import json
import logging
from pathlib import Path

import folium
import geopandas as gpd  # for creating the map
from geopy.geocoders import Nominatim  # for parsing the address into geocoded data
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable  # error handling for geopy
from shapely.geometry import Point  # for displaying the pinned location on the map
import time  # to allow the project to wait to avoid running into errors while requesting multiple geo-encodings in a row
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


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
GEOLocator = Nominatim(user_agent="Jefferson County Economic Development", timeout=5)

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

def geocode_address(address, label, status, cache, retries=3, delay=1.0):
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
                return {"lon": lon, "lat": lat, "status": status}
            else:
                logger.info("Address not found: %s", address)
                return None
        except (GeocoderTimedOut, GeocoderUnavailable) as e:
            logger.warning("Geocode attempt %d/%d failed for %s: %s", attempt + 1, retries, address, e)
            time.sleep(delay * (2 ** attempt))
    logger.error("Failed to geocode after %d attempts: %s", retries, address)
    return None

def create_map(address: str, ID: str, cache, status: str, force_refresh: bool = False) -> Path:
    """
    Create (or return cached) HTML map for the given address/ID.
    - address: address string to geocode
    - ID: unique identifier used to name the cached HTML file
    - force_refresh: if True, recreates the map even if a cached file exists
    Returns the Path to the saved HTML file.
    """
    # sanitize ID for filename
    
    filename = f"{ID}_Map"
    out_path = CACHE_DIR / filename
    html_path = out_path.with_suffix(".html")
    png_path = out_path.with_suffix(".png")

    if html_path.exists() and png_path.exists() and not force_refresh:
        logger.info("Using cached map: %s", html_path)
        return out_path

    shapefile_path = BASE_DIR / "resources" / "shapeData" / "PaMunicipalities2025_07.shp"
    if not shapefile_path.exists():
        raise FileNotFoundError(f"Shapefile not found: {shapefile_path}")

    # Read shapefile and filter to Jefferson county
    municipalities = gpd.read_file(shapefile_path, engine='pyogrio')
    municipalities = municipalities.to_crs(epsg=4326)
    if 'COUNTY_NAM' not in municipalities.columns:
        logger.warning("Expected 'COUNTY_NAM' in shapefile; skipping county filter.")
    else:
        municipalities = municipalities[municipalities['COUNTY_NAM'].str.upper() == 'JEFFERSON']

    # geocode the address and add pin if successful
    pin = geocode_address(address, label=ID, cache=cache, status=status)
    color = status_colors.get(status, "black")  # default if status is None
    if pin is not None:
        lon, lat = pin["lon"], pin["lat"] 
        folium_map = folium.Map(location=[lat, lon], zoom_start=15)
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
        folium.Marker([lat, lon], icon=folium.Icon(color=color), popup=f"{ID}\n{status}").add_to(folium_map)
    else:
        return None  # could not geocode address      
        
    # save the folium map to cachedMaps
    try:
        folium_map.save(str(out_path.with_suffix(".html")))
        logger.info("Saved map to: %s", out_path)
        # Screenshot to PNG
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--window-size=800,600")

        driver = webdriver.Chrome(options=options)
        driver.get(out_path.with_suffix(".html").as_uri())
        time.sleep(1)  # wait for tiles to load
        driver.save_screenshot(str(out_path.with_suffix(".png")))
        driver.quit()

    except Exception as e:
        logger.exception("Failed to save map to %s: %s", out_path, e)
        raise

    return out_path

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

    # --- Convert dict → GeoDataFrame ---
    records = []
    for addr, coords in geocode_cache.items():
        records.append({
            "name": addr,
            "lon": coords["lon"],
            "lat": coords["lat"],
            "status": coords.get("status"),
            "geometry": Point(coords["lon"], coords["lat"])
        })
    pins_gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")

    # Base map centered on county
    folium_map = folium.Map(location=[41.16, -79.06], zoom_start=10)

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
        color = status_colors.get(row["status"], "black")  # default if status is None
        folium.Marker([row["lat"], row["lon"]], icon=folium.Icon(color=color), popup=f"{row['name']}\n{row['status']}", ).add_to(folium_map)

    # Save HTML
    html_path = out_path.with_suffix(".html")
    folium_map.save(str(html_path))

    # Screenshot to PNG
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--window-size=800,600")
    driver = webdriver.Chrome(options=options)
    driver.get(html_path.as_uri())
    time.sleep(2)
    driver.save_screenshot(str(out_path.with_suffix(".png")))
    driver.quit()

    return out_path.with_suffix(".png")
