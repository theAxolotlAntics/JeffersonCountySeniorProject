from pathlib import Path
import tkinter as tk
from PIL import Image, ImageTk
import webbrowser

# Paths
BASE_DIR = Path(__file__).parent
CACHE_DIR = BASE_DIR / "resources" / "cachedMaps"
MAP_HTML = CACHE_DIR / "549_Route_28_Map.html"
MAP_PNG = CACHE_DIR / "549_Route_28_Map.png"

# Requires: pip install selenium pillow
# And a webdriver (e.g. ChromeDriver or GeckoDriver) installed on your system.
def generate_map_png():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--window-size=800,600")

    driver = webdriver.Chrome(options=options)
    driver.get(MAP_HTML.as_uri())
    driver.save_screenshot(str(MAP_PNG))
    driver.quit()

# Generate PNG if not already cached
if not MAP_PNG.exists():
    generate_map_png()


root = tk.Tk()
root.title("Map Viewer")
root.geometry("800x600")

# Load PNG into Tkinter
img = Image.open(MAP_PNG)
tk_img = ImageTk.PhotoImage(img)

label = tk.Label(root, image=tk_img)
label.pack(fill="both", expand=True)

# Button to open full interactive map in browser
def open_in_browser():
    webbrowser.open(MAP_HTML.as_uri())

btn = tk.Button(root, text="Open Interactive Map in Browser", command=open_in_browser)
btn.pack(pady=10)

root.mainloop()