import math
import os
import requests
from pathlib import Path
from time import sleep

# Jefferson County bounding box + buffer
MIN_LAT = 40.97
MAX_LAT = 41.37
MIN_LON = -79.55
MAX_LON = -78.55

# Zoom levels needed for full map + property previews
ZOOMS = [8, 9, 10, 11, 12, 13, 14, 15, 16]

# Output folder
TILE_DIR = Path("resources/tiles")

# Required by OSM policy
HEADERS = {
    "User-Agent": "JeffersonCountyPropertyViewer/1.0 (https://github.com/theAxolotlAntics/JeffersonCountySeniorProject)"
}

def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2.0 * n)
    return xtile, ytile

def download_tile(z, x, y):
    url = f"https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    out_path = TILE_DIR / str(z) / str(x)
    out_path.mkdir(parents=True, exist_ok=True)
    file_path = out_path / f"{y}.png"

    if file_path.exists():
        return

    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            file_path.write_bytes(r.content)
            print(f"Downloaded z{z}/{x}/{y}")
        else:
            print(f"Failed {url}: {r.status_code}")
    except Exception as e:
        print(f"Error downloading {url}: {e}")

    sleep(0.15)

def main():
    for z in ZOOMS:
        print(f"=== Zoom {z} ===")

        # Convert bounding box to tile numbers
        x_min, y_max = deg2num(MIN_LAT, MIN_LON, z)
        x_max, y_min = deg2num(MAX_LAT, MAX_LON, z)

        # Add 1-tile buffer around edges
        x_min -= 1
        x_max += 1
        y_min -= 1
        y_max += 1

        for x in range(x_min, x_max + 1):
            for y in range(y_min, y_max + 1):
                download_tile(z, x, y)

if __name__ == "__main__":
    main()