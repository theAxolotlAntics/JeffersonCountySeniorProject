import json
import logging
from pathlib import Path
from typing import Optional

import geopandas as gpd  # for creating the map
from geopy.geocoders import Nominatim  # for parsing the address into geocoded data
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable  # error handling for geopy
from shapely.geometry import Point  # for displaying the pinned location on the map
import time  # to allow the project to wait to avoid running into errors while requesting multiple geo-encodings in a row
import re

#@author:  Brunner Good

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Directories & cache files
BASE_DIR = Path(__file__).parent
CACHE_DIR = BASE_DIR / "cachedMaps"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
GEOCODE_CACHE_FILE = CACHE_DIR / "geocode_cache.json"


# Reuse a single Nominatim instance (respect API usage)
GEOLocator = Nominatim(user_agent="Jefferson County Economic Development", timeout=5)


def _load_geocode_cache() -> dict:
    if GEOCODE_CACHE_FILE.exists():
        try:
            return json.loads(GEOCODE_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Failed to read geocode cache; starting fresh.")
    return {}


def _save_geocode_cache(cache: dict) -> None:
    try:
        GEOCODE_CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning("Failed to write geocode cache: %s", e)


def geocode_address(address: str, label: str = "Location", retries: int = 3, delay: float = 1.0) -> Optional[gpd.GeoDataFrame]:
    """
    Geocode an address to a GeoDataFrame point with a 'name' column.
    Will use a persistent JSON cache in cachedMaps/geocode_cache.json to avoid repeated queries.
    Returns None if geocoding fails.
    """
    if not address or not isinstance(address, str):
        logger.debug("Empty or invalid address provided.")
        return None

    key = address.strip().lower()
    cache = _load_geocode_cache()

    if key in cache:
        lon, lat = cache[key]["lon"], cache[key]["lat"]
        logger.debug("Geocode cache hit for address: %s", address)
        return gpd.GeoDataFrame([{"geometry": Point(lon, lat), "name": label}], crs="EPSG:4326")

    # Attempt geocoding with retries + exponential backoff
    for attempt in range(retries):
        try:
            location = GEOLocator.geocode(address)
            if location:
                lon, lat = location.longitude, location.latitude
                cache[key] = {"lon": lon, "lat": lat}
                _save_geocode_cache(cache)
                logger.info("Geocoded address '%s' -> (%s, %s)", address, lat, lon)
                return gpd.GeoDataFrame([{"geometry": Point(lon, lat), "name": label}], crs="EPSG:4326")
            else:
                logger.info("Address not found: %s", address)
                return None
        except (GeocoderTimedOut, GeocoderUnavailable) as e:
            logger.warning("Geocode attempt %d/%d failed for %s: %s", attempt + 1, retries, address, e)
            time.sleep(delay * (2 ** attempt))  # exponential backoff
    logger.error("Failed to geocode after %d attempts: %s", retries, address)
    return None


def create_map(clean_address: str, ID: str, force_refresh: bool = False) -> Path:
    """
    Create (or return cached) HTML map for the given address/ID.
    - clean_address: address string to geocode
    - ID: unique identifier used to name the cached HTML file
    - force_refresh: if True, recreates the map even if a cached file exists
    Returns the Path to the saved HTML file.
    """
    # sanitize ID for filename
    safe_id = re.sub(r'[<>:"/\\|?*]', '_', str(ID))
    filename = f"{safe_id}_Map.html"
    out_path = CACHE_DIR / filename

    if out_path.exists() and not force_refresh:
        logger.info("Using cached map: %s", out_path)
        return out_path

    shapefile_path = BASE_DIR / "resources" / "shapeData" / "PaMunicipalities2025_07.shp"
    if not shapefile_path.exists():
        raise FileNotFoundError(f"Shapefile not found: {shapefile_path}")

    # Read shapefile and filter to Jefferson county
    municipalities = gpd.read_file(shapefile_path)
    municipalities = municipalities.to_crs(epsg=4326)
    if 'COUNTY_NAM' not in municipalities.columns:
        logger.warning("Expected 'COUNTY_NAM' in shapefile; skipping county filter.")
    else:
        municipalities = municipalities[municipalities['COUNTY_NAM'].str.upper() == 'JEFFERSON']

    # create the folium map object from the GeoDataFrame
    try:
        folium_map = municipalities.explore()
    except Exception as e:
        logger.exception("Failed to create base map: %s", e)
        raise

    # geocode the address and add pin if successful
    pin = geocode_address(clean_address, label=ID)
    if pin is not None:
        try:
            pin.explore(m=folium_map, color="red", marker_kwds={'popup': pin['name'].iat[0]})
        except Exception as e:
            logger.warning("Failed to add pin to map: %s", e)

    # save the folium map to cachedMaps
    try:
        folium_map.save(str(out_path))
        logger.info("Saved map to: %s", out_path)
    except Exception as e:
        logger.exception("Failed to save map to %s: %s", out_path, e)
        raise

    return out_path


