import subprocess
import sys
from pathlib import Path

def get_chromium_path():
    # When running as EXE, Chromium is inside sys._MEIPASS
    base = getattr(sys, "_MEIPASS", Path(__file__).parent)
    chromium = Path(base) / "chromium" / "chrome.exe"
    if chromium.exists():
        return str(chromium)
    raise FileNotFoundError("Bundled Chromium not found.")

def render(html_path, png_path, width, height):
    browser = get_chromium_path()

    html_path = Path(html_path).resolve()
    png_path = Path(png_path).resolve()

    cmd = [
        browser,
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu-sandbox",
        "--disable-dev-shm-usage",
        f"--window-size={width},{height}",
        f"--screenshot={png_path}",
        html_path.as_uri()
    ]

    subprocess.run(cmd, check=True)

if __name__ == "__main__":
    html_path = sys.argv[1]
    png_path = sys.argv[2]
    width = int(sys.argv[3])
    height = int(sys.argv[4])
    render(html_path, png_path, width, height)