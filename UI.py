# Name: Gannon Kearney, Brunner Good, Isaac Wagner, Alexis Valencia
# Created: 9/3/25
# Last Updated: 4/6/26
# Purpose: Tkinter-based property management system that:
        #loads property data from a CSV
        #Displays it in a Treeview
        #Allows create/edit/delete of properties
        #displays images from Google Dive links using PIL
        #Supports mapping/geocoding and calendar input


#GUI Libraries
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter import font

#Image Handling
from PIL import Image, ImageTk, UnidentifiedImageError, ImageOps

#Data Holding
import pandas as pd
import csv
import json

#network/requests
import requests
from  io import BytesIO

#system/file handling
import re
import os
from pathlib import Path
import webbrowser
import getpass
import logging

#date/time
from datetime import datetime, timedelta
import time

#calendar UI
from tkcalendar import Calendar

#custome module
from MapModule import create_map, geocode_address, generate_full_map, _save_geocode_cache, _load_geocode_cache, validate



#mapping
import folium
import geopandas as gpd  # for creating the map
from geopy.geocoders import Nominatim  # for parsing the address into geocoded data
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable  # error handling for geopy
from shapely.geometry import Point  # for displaying the pinned location on the map

#map rendering/export automation
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# Define global paths
BASE_DIR = Path(__file__).parent
CACHE_DIR = BASE_DIR / "resources" / "cachedMaps"
# Define the cache once to speed up mapping
cache = _load_geocode_cache()

#favorited options
favorited_options = ["0","1"]

#submitter names
sub_names= ["Elise Grovanz", "Jess Seary", "Other"]

#submitter emails
sub_emails = ["egrovanz@jeffersoncountypa.gov", "jseary@jeffersoncountypa.gov", "Other"]

JEFFERSON_ZIPS = {
    "15767",	#Punxsutawney	
    "15825",	#Brookville	
    "15851",	#Reynoldsville	
    "15824",	#Brockway	
    "15840",	#Falls Creek	
    "15864",	#Summerville	
    "16240",	#Mayport	
    "15829",	#Corsica	
    "15860",	#Sigel	
    "15865",	#Sykesville	
    "15715",	#Big Run	
    "15778",	#Timblin	
    "15711",	#Anita	
    "15770",	#Ringgold	
    "15764",	#Oliveburg	
    "15863",	#Stump Creek	
    "15730",	#Coolspring	
    "15780",	#Valier	
    "15781",	#Walston	
    "15733",	#De Lancey	
    "15847",	#Knox Dale  
    "15784",	#Worthville	
    "15744",	#Hamilton	
    "15776",	#Sprankle Mills	
}

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


#google drive image downloader
def download_drive_image(file_id):
    #Download image from Google Drive, handling confirmation tokens.
    URL = "https://drive.google.com/uc?export=download"
    session = requests.Session()

    #initial request
    response = session.get(URL, params={'id': file_id}, stream=True, headers=headers)
    
    # Check for confirmation token
    for key, value in response.cookies.items():
        if key.startswith('download_warning'):
            token = value
            response = session.get(URL, params={'id': file_id, 'confirm': token}, stream=True, headers=headers)
            break
    #convert response to PIL Image
    file_bytes = BytesIO(response.content)
    img = Image.open(file_bytes)
    
    #Fix image orientaition based on EXIF data
    img = ImageOps.exif_transpose(img)
    return img
        
def extract_drive_id(url):
    #Extracts Google Drive file ID from multiple possible URL formats.
    #Returns the file ID string or None if not found.


    # Handles /file/d/<id>/view
    match = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)

    # Handles open?id=<id>
    match = re.search(r"id=([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)

    # Handles uc?id=<id>
    match = re.search(r"uc\?id=([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)

    return None


#hover help text for widgets
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, event=None):
        #display tooltip near widget
        if self.tip:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + 20
        self.tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, background="lightyellow",
                         relief="solid", borderwidth=1)
        label.pack()

    def hide(self, event=None):
        #hide tooltip
        if self.tip:
            self.tip.destroy()
            self.tip = None

#calendar pop up function
def open_calendar(parent,var):
    #opens a calendar widget in a popup window and writes a selected ate into Tkinter StringVar
    top = tk.Toplevel(parent)

    # Create the calendar widget
    cal = Calendar(top, selectmode="day")
    cal.pack(pady=10)
    
    # when date selected
    def select_date():
        selected_date = cal.get_date()
        var.set(selected_date)
        top.destroy()

            

    ttk.Button(top, text="Select", command=select_date).pack(pady=5)

#--------------------------------------------------------------------------------------------------------------------------

# csv that is being read - in the same folder as the program
CSV_PATH = "Blight Mitigation Data.csv"

#----------------------------------------------------------------------------------------------------------------------------

def choose_csv_path():
    #Prompt the user to pick a CSV file. If they cancel, fall back to DummyData.csv.
    root = tk.Tk()
    root.withdraw()
    path = filedialog.askopenfilename(
        title="Select CSV file",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
    )
    root.destroy()
    return path

# Let the user choose a CSV file first
user_path = choose_csv_path()
if user_path:
    CSV_PATH = user_path

if not os.path.exists(CSV_PATH):
    # create a minimal sample CSV so the app runs if file missing
    sample = pd.DataFrame({
        "ID": [1],
        "Created": [datetime.now().isoformat()],
        "Modified": [datetime.now().isoformat()],
        "ParcelID": ["0001"],
        "StreetNum": ["123"],
        "Address": ["Main St"],
        "City": ["Brookville"],
        "First": ["John"],
        "Last": ["Doe"],
        "ImagePath": [""],
        "Notes": [""]
    })
    sample.to_csv(CSV_PATH, index=False)

Originaldf = pd.read_csv(CSV_PATH)
date_cols = ["Start time", "Completion time", "Date of Property Review"]

for col in date_cols:
    if col in Originaldf.columns:
        Originaldf[col] = pd.to_datetime(Originaldf[col], errors="coerce")
#----------------------------------------------------------------------------------------------------------------------------
#APPLICATION
#-----------------------------------------------------------------------------------------------------------------

Title = "Blight Inventory"

# columns wanted on the main page
#StreeNum and Address are seperated for ease of filtering
VisibleColumns = ["ID", "Start time", "Completion time", "Email", "First", "Last", "Date of Property Review:",
                      "Parcel ID, if known:", "Property Address Number:", "Property Address Street Name:",
                      "City:", "Zipcode:", "Municipality:", "Property Blighted?", "Commercial", "Residential", "Vacant Property:", "Submitter's Name:",
                      "Submitter's Email or Phone Number (this information will be used to collect any critical information or clear up any discrepancies)"]
                      

# columns displayed on selected property page (skip last column if image link etc)
hidden_columns = [col for col in Originaldf.columns[:-1] if col not in VisibleColumns]

# Citys and Municipalitys in Jefferson County
Citys = ["Big Run", "Brockway", "Brookville", "Corsica", "Falls Creek", "Punxsutawney",
            "Reynoldsville", "Summerville", "Sykesville", "Timblin", "Worthville"]
Municipalitys = ["Barnett", "Beaver", "Bell", "Clover", "Eldred", "Gaskill", "Heath", "Henderson",
             "Knox", "McCalmont", "Oliver", "Perry", "Pine Creek", "Polk", "Porter", "Ringgold",
             "Rose", "Snyder", "Union", "Warsaw", "Washington", "Winslow", "Young"]

Uses = ["Commercial","Residential"]

#normalize data by converting values to string and stripping whitespace.  also lowercases all values
def normalize(series):
    return series.astype(str).str.strip().str.lower()


def get_backup_path(csv_path):
    """Return one consistent backup filename for the current date."""
    base, ext = os.path.splitext(csv_path)
    date_str = datetime.now().strftime("%Y%m%d")
    return f"{base}_backup_{date_str}{ext}"


# ---- App ----

#- Load and display CSV data in a Treeview
    #- Manage property records (add/edit/delete)
   # - Handle filtering and search
  #  - Provide UI menus, toolbar, and settings
 #   - Support theme switching (dark/light mode)
#    - Toggle between Blight and Inventory modes
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        #configure window
        self.title(Title)
        self.geometry("1100x600")
        self.minsize(900, 520) #min size of the main window

        #dataset
        self.df = Originaldf.copy()
        

        self.mode = tk.StringVar(value="Blight")  # mode toggle "Blight" or "Inventory"
        
        self.all_columns = list(self.df.columns) #all available columns in dataset
        self.visible_columns= [col for col in VisibleColumns if col in self.all_columns]

        if not self.visible_columns: #fallback if no visible columns match
            self.visible_columns=self.all_columns.copy()

        #menubar
        self.menubar = tk.Menu(self)
        self.config(menu=self.menubar)
        self.dark_mode = tk.BooleanVar(value=False) #current theme
        self.font_size = tk.IntVar(value=10)
        self.base_font_size = 10
        self.base_window_width = 1100
        self.base_window_height = 600
        self.base_min_width = 900
        self.base_min_height = 520
        self.style = ttk.Style()

        #UI components
        self.CreateToolMenu()
        self.CreateSettingsMenu()
        self.CreateToolbar()
        self.BuildFilters()

        self.BuildTree()
        self.ApplyTheme()

        #populate treeview
        self.ShowTree(self.df)
        self.protocol("WM_DELETE_WINDOW", self.OnClose)

    def ToggleMode(self):
        self.mode.set("Inventory" if self.mode.get() == "Blight" else "Blight")
        self.RebuildLayout()
        self.ApplyFilters()

    #  creates a faile menu with new, save, and exit app
    def CreateToolMenu(self): #creates a tool bar with navigation buttons
        menubar = tk.Menu(self)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="New File", command=self.NewCSV)
        filemenu.add_command(label="Save As", command=self.SaveAsCSV)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.OnClose) #exit option closes program
        self.menubar.add_cascade(label="File", menu=filemenu)

    def CreateSettingsMenu(self): #create a settings menubar.  This can change font size, themes, and toggle the mode (blight or inventory)
        settingsmenu = tk.Menu(self.menubar, tearoff=0)
        settingsmenu.add_command(label="Change Mode", command=self.ToggleMode)
        settingsmenu.add_command(label="Themes", command=self.ShowThemesMenu)
        settingsmenu.add_command(label="Font Size", command=self.ShowFontSizeMenu)
        settingsmenu.add_command(label="Show/Hide Columns", command=self.ShowColumnSelector)
        self.menubar.add_cascade(label="Settings", menu=settingsmenu)

    def ScaleValue(self, value, minimum=1):
        scale = self.font_size.get() / self.base_font_size
        return max(minimum, int(round(value * scale)))

    def CurrentFonts(self):
        size = self.font_size.get()
        return {
            "normal": ("Arial", size),
            "bold": ("Arial", size, "bold"),
            "small": ("Arial", max(8, size - 1)),
            "title": ("Arial", size + 2, "bold"),
        }

    def ApplyFontSize(self, *_):
        self.ApplyTheme()
        self.UpdateWindowSizing()
        self.RebuildLayout()
        self.ApplyFilters()

    def UpdateWindowSizing(self):
        scale = self.font_size.get() / self.base_font_size
        min_w = int(self.base_min_width * scale)
        min_h = int(self.base_min_height * scale)
        self.minsize(min_w, min_h)

    def RebuildLayout(self):
        if hasattr(self, "toolbar_frame") and self.toolbar_frame.winfo_exists():
            self.toolbar_frame.destroy()
        if hasattr(self, "filter_frame") and self.filter_frame.winfo_exists():
            self.filter_frame.destroy()
        if hasattr(self, "tree_container") and self.tree_container.winfo_exists():
            self.tree_container.destroy()

        self.CreateToolbar()
        self.BuildFilters()
        self.BuildTree()
        self.ShowTree(self.df)

    def ShowFontSizeMenu(self):
        top = tk.Toplevel(self)
        top.title("Font Size")
        top.geometry("340x180")
        top.minsize(300, 160)
        top.grab_set()
        top.configure(bg="#2b2b2b" if self.dark_mode.get() else "#f0f0f0")

        fonts = self.CurrentFonts()

        ttk.Label(top, text="Adjust Text Size", font=fonts["title"]).pack(pady=(12, 8))

        value_label = ttk.Label(top, text=f"{self.font_size.get()} pt", font=fonts["normal"])
        value_label.pack(pady=(0, 8))

        def on_slide(val):
            value_label.config(text=f"{int(float(val))} pt")

        slider = tk.Scale(
            top,
            from_=8,
            to=18,
            orient="horizontal",
            variable=self.font_size,
            command=on_slide,
            length=220
        )
        slider.pack(pady=4)

        btns = ttk.Frame(top)
        btns.pack(pady=10)

        ttk.Button(btns, text="Apply", command=lambda: [self.ApplyFontSize(), top.destroy()]).pack(side="left", padx=5)
        ttk.Button(btns, text="Reset", command=lambda: [self.font_size.set(self.base_font_size), on_slide(self.base_font_size)]).pack(side="left", padx=5)
        ttk.Button(btns, text="Close", command=top.destroy).pack(side="left", padx=5)

    #theme handling
    def ShowThemesMenu(self):

        top = tk.Toplevel(self)
        top.title("Themes")
        top.geometry("280x180")
        top.minsize(260, 160)
        top.grab_set()
        top.configure(bg="#2b2b2b" if self.dark_mode.get() else "#f0f0f0")

        fonts = self.CurrentFonts()

        ttk.Label(top, text="Appearance", font=fonts["title"]).pack(pady=10)

        dark_check = ttk.Checkbutton(
            top,
            text="Dark Mode",
            variable=self.dark_mode,
            command=self.ApplyTheme
        )
        dark_check.pack(pady=5)

        ttk.Button(top, text="Font Size...", command=self.ShowFontSizeMenu).pack(pady=8)

    def ApplyTheme(self):
        style = self.style
        fonts = self.CurrentFonts()
        row_h = self.ScaleValue(25, minimum=22)
        pad_small = self.ScaleValue(4, minimum=2)
        pad_med = self.ScaleValue(8, minimum=4)

        default_bg = "#f0f0f0"
        default_fg = "#000000"

        if self.dark_mode.get():
            style.theme_use("clam")

            bg = "#2b2b2b"
            fg = "#ffffff"
            field_bg = "#3c3f41"
            accent = "#4a90e2"

            self.configure(bg=bg)

            style.configure(".", background=bg, foreground=fg, font=fonts["normal"])
            style.configure("TFrame", background=bg)
            style.configure("TLabel", background=bg, foreground=fg, font=fonts["normal"])
            style.configure("TLabelframe", background=bg, foreground=fg)
            style.configure("TLabelframe.Label", background=bg, foreground=fg, font=fonts["bold"])

            style.configure(
                "TButton",
                background=field_bg,
                foreground=fg,
                borderwidth=1,
                padding=(pad_med, pad_small),
                font=fonts["normal"]
            )
            style.map("TButton", background=[("active", accent)])

            style.configure("TCheckbutton", background=bg, foreground=fg, font=fonts["normal"])
            style.configure("TCombobox", fieldbackground=field_bg, background=field_bg, foreground=fg, arrowcolor=fg, padding=pad_small, font=fonts["normal"])
            style.configure("TEntry", fieldbackground=field_bg, foreground=fg, padding=pad_small, font=fonts["normal"])

            style.map(
                "TCombobox",
                fieldbackground=[("readonly", field_bg)],
                selectbackground=[("readonly", accent)],
                selectforeground=[("readonly", "white")]
            )

            style.configure("Treeview", background=bg, foreground=fg, fieldbackground=bg, rowheight=row_h, font=fonts["normal"])
            style.map("Treeview", background=[("selected", accent)], foreground=[("selected", "white")])
            style.configure("Treeview.Heading", background=field_bg, foreground=fg, font=fonts["bold"], padding=(pad_small, pad_small))

            self.option_add("*TCombobox*Listbox.background", field_bg)
            self.option_add("*TCombobox*Listbox.foreground", fg)
            self.option_add("*TCombobox*Listbox.selectBackground", accent)
            self.option_add("*TCombobox*Listbox.selectForeground", "white")
            self.option_add("*Background", bg)
            self.option_add("*Foreground", fg)
            self.option_add("*Font", fonts["normal"])
            self.option_add("*Entry.Background", field_bg)
            self.option_add("*Entry.Foreground", fg)
            self.option_add("*Entry.insertBackground", fg)

        else:
            style.theme_use("default")
            self.configure(bg=default_bg)

            style.configure(".", font=fonts["normal"])
            style.configure("TFrame", background=default_bg)
            style.configure("TLabel", background=default_bg, foreground=default_fg, font=fonts["normal"])
            style.configure("TLabelframe", background=default_bg, foreground=default_fg)
            style.configure("TLabelframe.Label", background=default_bg, foreground=default_fg, font=fonts["bold"])
            style.configure("TButton", padding=(pad_med, pad_small), font=fonts["normal"])
            style.configure("TCheckbutton", font=fonts["normal"])
            style.configure("TCombobox", padding=pad_small, font=fonts["normal"])
            style.configure("TEntry", padding=pad_small, font=fonts["normal"])
            style.configure("Treeview", rowheight=row_h, font=fonts["normal"])
            style.configure("Treeview.Heading", font=fonts["bold"], padding=(pad_small, pad_small))

            self.option_add("*Background", default_bg)
            self.option_add("*Foreground", default_fg)
            self.option_add("*Font", fonts["normal"])

        if hasattr(self, "tree"):
            self.FitColumns()


      # Toolbar
    def CreateToolbar(self): #creates a tool bar with navigation buttons
        self.toolbar_frame = ttk.Frame(self, padding=(self.ScaleValue(8, 4), self.ScaleValue(6, 4)))
        self.toolbar_frame.pack(side="top", fill="x")

        left = ttk.Frame(self.toolbar_frame)
        left.pack(side="left", fill="x", expand=True)

        right = ttk.Frame(self.toolbar_frame)
        right.pack(side="right")

        self.SearchInput = tk.StringVar()

        ttk.Button(left, text="New", command=self.AddProperty).pack(side="left", padx=4, pady=2)
        ttk.Button(left, text="Delete", command=self.DelProperty).pack(side="left", padx=4, pady=2)
        ttk.Button(left, text="Show Favorites", command=self.ShowFavs).pack(side="left", padx=4, pady=2)
        ttk.Button(left, text="Toggle Mode", command=self.ToggleMode).pack(side="left", padx=4, pady=2)

        entry = ttk.Entry(right, textvariable=self.SearchInput, width=max(20, self.ScaleValue(30, 20)))
        entry.pack(side="left", padx=4, pady=2)
        entry.bind("<Return>", self.ApplyFilters)

        ttk.Button(right, text="Search", command=self.ApplyFilters).pack(side="left", padx=4, pady=2)

   #Filters
    #Different filters based on customer needs
    def BuildFilters(self):
        pad_x = self.ScaleValue(6, 4)
        pad_y = self.ScaleValue(6, 3)
        entry_w = max(12, self.ScaleValue(14, 12))
        combo_w = max(14, self.ScaleValue(16, 14))

        self.filter_frame = ttk.LabelFrame(self, text="Filters & Sort", padding=self.ScaleValue(8, 6))
        self.filter_frame.pack(side="top", fill="x", padx=self.ScaleValue(8, 4), pady=(0, self.ScaleValue(8, 4)))

        for c in range(9):
            self.filter_frame.grid_columnconfigure(c, weight=1)

        self.BlightedFilter = tk.BooleanVar(value=False)
        self.VacancyFilter = tk.BooleanVar(value=False)

        ttk.Checkbutton(self.filter_frame, text="Blighted", variable=self.BlightedFilter).grid(row=0, column=0, sticky="w", padx=pad_x, pady=pad_y)
        ttk.Checkbutton(self.filter_frame, text="Vacant", variable=self.VacancyFilter).grid(row=0, column=1, sticky="w", padx=pad_x, pady=pad_y)

        self.use_var = tk.StringVar(value="Both")
        self.use = ttk.Combobox(self.filter_frame, textvariable=self.use_var, values=["Both", "Commercial", "Residential"], state="readonly", width=combo_w)
        self.use.grid(row=0, column=2, sticky="ew", padx=pad_x, pady=pad_y)

        city_list = ["All"] + sorted(self.df["City:"].dropna().astype(str).str.strip().unique().tolist())
        self.city_var = tk.StringVar(value="All")
        self.City = ttk.Combobox(self.filter_frame, textvariable=self.city_var, values=city_list, state="readonly", width=combo_w)
        self.City.grid(row=0, column=3, sticky="ew", padx=pad_x, pady=pad_y)

        muni_list = ["All"] + sorted(self.df["Municipality:"].dropna().astype(str).str.strip().unique().tolist())
        self.muni_var = tk.StringVar(value="All")
        self.Municipality = ttk.Combobox(self.filter_frame, textvariable=self.muni_var, values=muni_list, state="readonly", width=combo_w)
        self.Municipality.grid(row=0, column=4, sticky="ew", padx=pad_x, pady=pad_y)

        ttk.Button(self.filter_frame, text="Apply", command=self.ApplyFilters).grid(row=0, column=5, sticky="ew", padx=pad_x, pady=pad_y)
        ttk.Button(self.filter_frame, text="Reset", command=self.ResetFilters).grid(row=0, column=6, sticky="ew", padx=pad_x, pady=pad_y)

        self.map_regen = tk.BooleanVar(value=False)
        ttk.Button(self.filter_frame, text="Full Map", command=self.CreateFullMap).grid(row=0, column=7, sticky="ew", padx=pad_x, pady=pad_y)
        ttk.Checkbutton(self.filter_frame, text="Refresh Map", variable=self.map_regen).grid(row=0, column=8, sticky="w", padx=pad_x, pady=pad_y)

        ttk.Label(self.filter_frame, text="From Date").grid(row=1, column=0, sticky="w", padx=pad_x, pady=pad_y)
        self.from_date = tk.StringVar()
        ttk.Entry(self.filter_frame, textvariable=self.from_date, width=entry_w).grid(row=1, column=1, sticky="ew", padx=pad_x, pady=pad_y)
        self.calbtn = ttk.Button(self.filter_frame, text="📅", width=3, command=lambda: open_calendar(self.filter_frame, self.from_date))
        self.calbtn.grid(row=1, column=2, padx=pad_x, pady=pad_y)

        ttk.Label(self.filter_frame, text="To Date").grid(row=1, column=3, sticky="w", padx=pad_x, pady=pad_y)
        self.to_date = tk.StringVar()
        ttk.Entry(self.filter_frame, textvariable=self.to_date, width=entry_w).grid(row=1, column=4, sticky="ew", padx=pad_x, pady=pad_y)
        self.tobtn = ttk.Button(self.filter_frame, text="📅", width=3, command=lambda: open_calendar(self.filter_frame, self.to_date))
        self.tobtn.grid(row=1, column=5, padx=pad_x, pady=pad_y)

        ttk.Label(self.filter_frame, text="ZipCode").grid(row=1, column=6, sticky="w", padx=pad_x, pady=pad_y)
        zip_list = ["All"] + sorted(self.df["Zipcode:"].dropna().astype(str).unique().tolist())
        self.zip_var = tk.StringVar(value="All")
        self.zip = ttk.Combobox(self.filter_frame, textvariable=self.zip_var, values=zip_list, state="readonly", width=combo_w)
        self.zip.grid(row=1, column=7, sticky="ew", padx=pad_x, pady=pad_y)

        ttk.Label(self.filter_frame, text="Modified Date").grid(row=2, column=0, sticky="w", padx=pad_x, pady=pad_y)
        self.modified_var = tk.StringVar(value="All")
        self.mod_date = tk.StringVar()
        ttk.Entry(self.filter_frame, textvariable=self.mod_date, width=entry_w).grid(row=2, column=1, sticky="ew", padx=pad_x, pady=pad_y)
        self.modbtn = ttk.Button(self.filter_frame, text="📅", width=3, command=lambda: open_calendar(self.filter_frame, self.mod_date))
        self.modbtn.grid(row=2, column=2, padx=pad_x, pady=pad_y)


    # This fuction will create a map with all the adresses in the dataframe
    def CreateFullMap(self):
        MAP_HTML = CACHE_DIR / "full_Map.html"

        # Load cache
        cache = _load_geocode_cache()

        for index, row in self.df.iterrows():

            # primary address + map_id
            address_full = f"{row.get('Property Address Number:','')} {row.get('Property Address Street Name:','')}, {row.get('City:','')} PA, {row.get('Zipcode:','')}, USA"
            map_id_full = f"{row.get('Property Address Number:','')} {row.get('Property Address Street Name:','')}, {row.get('City:','')}"

            # fallback addresses
            address_street = f"{row.get('Property Address Street Name:','')}, {row.get('City:','')} PA, {row.get('Zipcode:','')}, USA"
            map_id_street = f"Property on {row.get('Property Address Street Name:','')}, {row.get('City:','')}"

            address_city = f"{row.get('City:','')} PA, {row.get('Zipcode:','')}, USA"
            map_id_city = f"Property in {row.get('City:','')}"

            # status flags
            status_flags = []
            if validate(row.get("Vacant Property:", "")): status_flags.append("Vacant")
            if validate(row.get("Property Blighted?", "")): status_flags.append("Blighted")
            if validate(row.get("Residential", "")): status_flags.append("Residential")
            if validate(row.get("Commercial", "")): status_flags.append("Commercial")
            status = " ".join(status_flags) if status_flags else None

            # --- CACHE CHECKS ---
            if map_id_full in cache:
                coords = cache[map_id_full]
            elif map_id_street in cache:
                coords = cache[map_id_street]
            elif map_id_city in cache:
                coords = cache[map_id_city]
            else:
                # --- GEOCODE ONLY IF NOT IN CACHE ---
                coords = (
                    geocode_address(address_full, label=map_id_full, status=status, cache=cache)
                    or geocode_address(address_street, label=map_id_street, status=status, cache=cache)
                    or geocode_address(address_city, label=map_id_city, status=status, cache=cache)
                )

                # Save whichever succeeded
                if coords:
                    cache[coords["label"]] = coords

        # Save updated cache
        _save_geocode_cache(cache)

        # Generate map
        out_path = generate_full_map(cache)
        png_path = out_path.with_suffix(".png")

        # Show in Tkinter window
        new_win = tk.Toplevel(self)
        new_win.title("Full Map of All Properties")

        img = Image.open(png_path)
        photo = ImageTk.PhotoImage(img)
        label = tk.Label(new_win, image=photo)
        label.image = photo
        label.pack(padx=20, pady=20)

        def open_in_browser(event=None):
            webbrowser.open(MAP_HTML.as_uri())

        label.bind("<Button-1>", open_in_browser)


    #create a new csv with the 
    def NewCSV(self):
        global CSV_PATH
        # Let the user choose a CSV file first
        user_path = choose_csv_path()
        if user_path:
            CSV_PATH = user_path
        
        # Ask user where to save the new file
        new_csv = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            title="New CSV"
        )

        if not new_csv:  # user cancelled
            return

        # Read headers from source file
        with open(CSV_PATH, newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)

        # Create a new file with only those headers
        with open(new_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)

    def SaveAsCSV(self):
        # Ask user where to save
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            title="Save as CSV"
        )

        if not file_path:
            return  # user cancelled

        try:
             # get visible row indices from treeview tags
            visible_idxs = [int(self.tree.item(iid, "tags")[0])
                for iid in self.tree.get_children("")]

        # export ALL columns for visible rows
            self.df.loc[visible_idxs].to_csv(file_path, index=False)

            messagebox.showinfo("Saved", "Treeview exported successfully.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save file:\n{e}")

    #fit all columns to one window
    def FitColumns(self, event=None):
        if not hasattr(self, "tree"):
            return

        total_width = self.tree.winfo_width()
        columns = self.tree["columns"]

        if not columns or total_width <= 1:
            return

        scrollbar_space = self.ScaleValue(20, 16)
        usable_width = max(200, total_width - scrollbar_space)
        col_width = max(int(usable_width / len(columns)), self.ScaleValue(110, 80))

        for col in columns:
            self.tree.column(col, width=col_width, stretch=True)

    def show(self, text, x, y):
        if self.tip:
            self.tip.destroy()
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self.tip, text=text, background="lightyellow", relief="solid", borderwidth=1)
        label.pack()

    def hide(self):
        if self.tip:
            self.tip.destroy()
            self.tip = None
        
    #This function takes the contents of the csv and displays them in an easy-to-read table
    # TreeView
    def BuildTree(self):
        # Destroy previous tree frame completely (prevents stacking)
        if hasattr(self, "tree_container"):
            self.tree_container.destroy()

        # Create container frame once per rebuild
        self.tree_container = ttk.Frame(self)
        self.tree_container.pack(side="top", fill="both", expand=True, padx=self.ScaleValue(8, 4), pady=self.ScaleValue(8, 4))

        # Create Treeview
        self.tree = ttk.Treeview(
            self.tree_container,
            columns=self.visible_columns,
            show="headings"
        )

        # Scrollbars
        vsb = ttk.Scrollbar(self.tree_container, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(self.tree_container, orient="horizontal", command=self.tree.xview)

        self.tree.configure(
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set
        )

        # Grid layout
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self.tree_container.grid_rowconfigure(0, weight=1)
        self.tree_container.grid_columnconfigure(0, weight=1)

        # Sorting dictionary
        self.sort = {}
        
        # Sorting function
        def SortCol(col):
            self.sort[col] = not self.sort.get(col, False)

            items = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]

            def tryNum(x):
                try:
                    return float(x)
                except:
                    return x

            items.sort(key=lambda t: tryNum(t[0]), reverse=self.sort[col])

            for index, (_, k) in enumerate(items):
                self.tree.move(k, "", index)

        # Configure headings + columns
        for col in self.visible_columns:
            self.tree.heading(col, text=col, command=lambda c=col: SortCol(c))
            self.tree.column(col, width=self.ScaleValue(110, 80), anchor="w", minwidth=self.ScaleValue(110, 80), stretch=True)

        # Selection binding
        self.tree.bind("<<TreeviewSelect>>", self.Selected)
        self.tree.bind("<Configure>", self.FitColumns)

        # Insert data
        self._row_ids = {}

        for idx, row in self.df.iterrows():
            vals = [row.get(col, "") for col in self.visible_columns]
            iid = self.tree.insert("", "end", values=vals, tags=(str(idx),))
            self._row_ids[idx] = iid

        self.after(50, self.FitColumns)

    #update the rows that are visible depending on filtering results
    def ShowTree(self, data):
        visible_idx = set(data.index)
        for idx, iid in self._row_ids.items():
            if idx in visible_idx:
                self.tree.reattach(iid, "", "end")
            else:
                self.tree.detach(iid) #hides rows not filtered results

   # Filters processing
    def ApplyFilters(self, event=None):
        df = Originaldf.copy()

        #Blighted Filter
        if self.BlightedFilter.get():
            df = df[normalize(df["Property Blighted?"]) == "true"]

        #Vacancy Filter
        if self.VacancyFilter.get():
            df = df[normalize(df["Vacant Property:"]) == "true"]

        #Use Filter
        use = self.use_var.get()
        if use == "Commercial":
            df = df[normalize(df["Commercial"]) == "true"]
        elif use == "Residential":
            df = df[normalize(df["Residential"]) =="true"]

        #City Filter
        city = self.city_var.get()
        if city != "All":
            df = df[normalize(df["City:"]) == city.strip().lower()]

        #Municipality Filter
        muni = self.muni_var.get()
        if muni != "All":
            df = df[normalize(df["Municipality:"]) == muni.strip().lower()]

        #Date Range
        if self.from_date.get() or self.to_date.get():
            df["Start time"] = pd.to_datetime(df["Start time"], errors="coerce")

        if self.from_date.get():
            start = pd.to_datetime(self.from_date.get(), errors="coerce")
            df = df[df["Start time"] >= start]

        if self.to_date.get():
            end = pd.to_datetime(self.to_date.get(), errors="coerce")
            df = df[df["Start time"] <= end]

        #Zip Code
        zip_code = self.zip_var.get()
        if zip_code != "All":
            df = df[normalize(df["Zipcode:"]) == zip_code.strip().lower()]

        #Last Modified Filter
        modified = self.modified_var.get()
        if modified != "All":
            df["Completion time"] = pd.to_datetime(df["Completion time"], errors="coerce")
            now = datetime.now()
            cutoff = datetime.now()

            if modified == "Last 24 Hours":
                cutoff = now - timedelta(days=1)
            elif modified == "Last 7 Days":
                cutoff = now - timedelta(days=7)
            elif modified == "Last 30 Days":
                cutoff = now - timedelta(days=30)

            df = df[df["Completion time"] >= cutoff]

        #Search Filter
        search = self.SearchInput.get().lower().strip()
        if search:
            df = df[df.apply(
                lambda row: search in " ".join(map(str, row.values)).lower(),
                axis=1
            )]

        # Refresh tree
        self.ShowTree(df)
        

    def ResetFilters(self):
        #reset filters to default state
        self.BlightedFilter.set(False)
        self.VacancyFilter.set(False)

        self.use_var.set("Both")
        self.city_var.set("All")
        self.muni_var.set("All")

        self.SearchInput.set("")

        self.from_date.set("")
        self.to_date.set("")
        self.mod_date.set("")
        self.zip_var.set("All")
        self.modified_var.set("All")
        self.SearchInput.set("")
        
        self.df = Originaldf.copy()
        self.ShowTree(self.df)

    def SaveMainCSV(self):
        global Originaldf
        try:
            self.df.to_csv(CSV_PATH, index=False)
            Originaldf = self.df.copy()
            return True
        except Exception as e:
            messagebox.showerror("Save error", f"Failed to save file:\n{e}")
            return False

    def SaveBackup(self):
        try:
            backup_path = get_backup_path(CSV_PATH)
            self.df.to_csv(backup_path, index=False)
            return True
        except Exception as e:
            messagebox.showerror("Backup error", f"Failed to create backup:\n{e}")
            return False

    def OnClose(self):
        try:
            if not self.SaveMainCSV():
                return
            if not self.SaveBackup():
                return
            self.destroy()
        except Exception as e:
            messagebox.showerror("Close error", f"Failed while closing:\n{e}")

    def ShowImage(self):
        #displays current image from ImageList in the UI
        #maintains aspect ratio
        if not self.ImageList:
            return
        self.OriginalImage = self.ImageList[self.ImageIndex]
        img = self.OriginalImage.copy()
        # Resize to fit label
        frame_width = self.ImageLabel.winfo_width() or 400
        frame_height = self.ImageLabel.winfo_height() or 400
        img.thumbnail((frame_width, frame_height), Image.LANCZOS)
        self.tkimage = ImageTk.PhotoImage(img)
        self.ImageLabel.config(image=self.tkimage)
        self.ImageLabel.image = self.tkimage  # keep reference

    #navigate to next image in carousel
    def NextImage(self):
        if not self.ImageList:
            return
        self.ImageIndex = (self.ImageIndex + 1) % len(self.ImageList)
        self.ShowImage()

    #navigate to previous image in carousel
    def PrevImage(self):
        if not self.ImageList:
            return
        self.ImageIndex = (self.ImageIndex - 1) % len(self.ImageList)
        self.ShowImage()
    
        
    # This function displays what happens when a row is selected on
        #It displays property details, an image from the csv, and the ability to edit all values or notes
    def Selected(self, event):
        selected = self.tree.selection()
        if not selected:
            return

        tag = self.tree.item(selected[0], "tags")[0]
        try:
            idx = int(tag)
        except Exception:
            idx = tag
        row = self.df.loc[idx]

        #window header of property address
        win = tk.Toplevel(self)
        win.title(f"Property Address: {row.get('Property Address Number:', '')} {row.get('Property Address Street Name:', '')}")
        fonts = self.CurrentFonts()
        win.geometry(f"{self.ScaleValue(800, 640)}x{self.ScaleValue(600, 480)}")
        win.minsize(self.ScaleValue(400, 340), self.ScaleValue(300, 260))
        win.columnconfigure(0, weight=1,uniform="half")
        win.columnconfigure(1, weight=1,uniform="half")
        win.rowconfigure(0, weight=0)
        win.rowconfigure(1, weight=1)
        win.rowconfigure(2, weight=1)

                # --- UI ---
        ImageFrame = ttk.Frame(win)
        ImageFrame.grid(row=0,column=0,columnspan=2,sticky="nsew", padx=5,pady=5)
        ImageFrame.rowconfigure(0,weight=1)
        ImageFrame.columnconfigure(0,weight=1)
        ImageFrame.columnconfigure(0, weight=1)
        ImageFrame.columnconfigure(2, weight=1)
        
        ImageLabel = tk.Label(ImageFrame, text="No Images Available", bg="lightgray")
        ImageLabel.grid(row=0,column=1,sticky="nsew")

        OriginalImages = []
        image_index = 0

         #function resizes the image, essentially bootstrapping
        def ResizeImage(event=None):
                    if not OriginalImages:
                        ImageLabel.config(image="", text=ImageLabel.cget("text"))
                        return

                    try:
                        FrameW = ImageFrame.winfo_width()
                        FrameH = ImageFrame.winfo_height()
                    except Exception:
                        return

                    if FrameW <= 1 or FrameH <= 1:
                        win.after(80, ResizeImage)
                        return

                    MaxW, MaxH = MaxSize()
                    FrameW = min(FrameW, MaxW)
                    FrameH = min(FrameH, MaxH)

                    try:
                        iw, ih = OriginalImages[image_index].size
                    except Exception:
                        return

                    ImageRatio = iw / ih if ih != 0 else 1
                    frame_ratio = FrameW / FrameH if FrameH != 0 else 1

                    if frame_ratio > ImageRatio:
                        TargetH = FrameH
                        TargetW = int(TargetH * ImageRatio)
                    else:
                        TargetW = FrameW
                        TargetH = int(TargetW / ImageRatio)

                    TargetW = min(TargetW, iw)
                    TargetH = min(TargetH, ih)

                    TargetW = max(1, int(TargetW))
                    TargetH = max(1, int(TargetH))

                    cur = getattr(ImageLabel, "_last_size", (0, 0))
                    if (TargetW, TargetH) == cur:
                        return

                    ImageLabel._last_size = (TargetW, TargetH)

                    try:
                        resized = OriginalImages[image_index].resize((TargetW, TargetH), Image.LANCZOS)
                    except Exception:
                        resized = OriginalImages[image_index].copy()
                        resized.thumbnail((TargetW, TargetH), Image.LANCZOS)

                    photo = ImageTk.PhotoImage(resized)
                    ImageLabel.config(image=photo, text="")
                    ImageLabel.image = photo
        #update image dynamically
        ImageLabel.bind("<Configure>", ResizeImage)
        win.bind("<Configure>", lambda e: ResizeImage(e))
        win.after(150, ResizeImage)

        def show_image(idx):
            #disp;ays image at a given index from OriginalImages

            #wraps index using mod for safe navigation
            #triggers ResizeImage after updating Index
            nonlocal image_index
            if not OriginalImages:
                ImageLabel.config(text="No Images Available")
                return
            image_index = idx % len(OriginalImages)
            win.after(1,ResizeImage)

        def next_image():
            #advances to next image in list
            show_image(image_index + 1)

        def prev_image():
            #advances to previous image in list
            show_image(image_index - 1)

        #previous and next image buttons
        btnPrev = tk.Button(ImageFrame, text="◀", command=prev_image)
        btnPrev.grid(row=0,column=0, sticky="w", padx=5, pady=5)
        btnNext = tk.Button(ImageFrame, text="▶", command=next_image)
        btnNext.grid(row=0,column=2, sticky="e", padx=5, pady=5)

        #stores loaded PIL images
        OriginalImages = []

        #raw image paths from dataframe row
        image_paths = row.get("ImagePath:", "")

        if image_paths:
            #split multiple paths, seperate by comma
            paths = [p.strip() for p in str(image_paths).split(",")]

            for p in paths:
                try:
                    # Google Drive link
                    if "drive.google.com" in p:
                        file_id = extract_drive_id(p)
                        if file_id:
                            img = download_drive_image(file_id)
                            OriginalImages.append(img)

                    # URL
                    elif p.startswith("http"):
                        response = requests.get(p)
                        img = Image.open(BytesIO(response.content))
                        img = ImageOps.exif_transpose(img)
                        OriginalImages.append(img)

                    # Local file
                    elif os.path.exists(p):
                        img = Image.open(p)
                        img = ImageOps.exif_transpose(img)
                        OriginalImages.append(img)

                except Exception as e:
                    print("Error loading image:", e)
        #show first image
        show_image(0)
        # Buttons for editing and notes
        EditBtn = ttk.Button(win, text="Edit Property Values", command=lambda i=idx: self.EditProperty(i, win))
        NoteBtn = ttk.Button(win, text="Add Note", command=lambda i=idx: self.AddNote(i, win))
        EditBtn.grid(row=3, column=0, sticky="ew", padx=8, pady=(6, 8))
        NoteBtn.grid(row=3, column=1, sticky="ew", padx=8, pady=(6, 8))

        # finds out how big the image should be based on the window size
        def MaxSize():
            WinH = max(300, win.winfo_height())
            MaxH = max(120, WinH // 3) #height is always 1/3 of the window
            WinW = max(300, win.winfo_width())
            MaxW = WinW - 40 #subtract padding
            return MaxW, MaxH
       

        
        InfoFrame = ttk.Frame(win, relief="solid", padding=5)
        InfoFrame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        InfoFrame.rowconfigure(0, weight=1)
        InfoFrame.columnconfigure(0, weight=1)

        infcanvas = tk.Canvas(InfoFrame) #add scrollbars
        infvscroll = ttk.Scrollbar(InfoFrame, orient="vertical", command=infcanvas.yview)
        infhscroll = ttk.Scrollbar(InfoFrame, orient="horizontal", command=infcanvas.xview)

            #set scrollbars
        infcanvas.configure(
            yscrollcommand=infvscroll.set,
            xscrollcommand=infhscroll.set
        )

        infcanvas.grid(row=0, column=0, sticky="nsew")
        infvscroll.grid(row=0, column=1, sticky="ns")
        infhscroll.grid(row=1, column=0, sticky="ew")

        infScrollFrame = ttk.Frame(infcanvas)
        infScrollFrame.bind("<Configure>", lambda e: infcanvas.configure(scrollregion=canvas.bbox("all")))
        infScrollFrame.grid_columnconfigure(0, weight=1)
        infScrollFrame.grid_rowconfigure(0, weight=1)

        infcanvas_window = infcanvas.create_window((0,0), window=infScrollFrame, anchor="nw")

        def resize_canvas(event):
            infcanvas.itemconfig(infcanvas_window, width=event.width)

        infcanvas.bind("<Configure>", resize_canvas)

        def ConfigureFrame(event):
            infcanvas.configure(scrollregion=infcanvas.bbox("all"))

        infScrollFrame.bind("<Configure>", ConfigureFrame)
        
        hidden_columns=[col for col in self.all_columns if col not in self.visible_columns]



        if self.mode.get() == "Inventory": #display information necessary for inventory mode
            summary_fields = [
                ("Parcel ID", "Parcel ID, if known:"),
                ("Address #", "Property Address Number:"),
                ("Street", "Property Address Street Name:"),
                ("City", "City:"),
                ("Zip", "Zipcode:"),
                ("Municipality", "Municipality:"),
            ]

            for r, (label, col) in enumerate(summary_fields):
                if col in self.df.columns:
                    val = row.get(col, "")
                    ttk.Label(infScrollFrame, text=f"{label}:", font=("Arial", 10, "bold"))\
                        .grid(row=r, column=0, sticky="ne", padx=6, pady=4)

                    ttk.Label(infScrollFrame, text=val, anchor="w")\
                        .grid(row=r, column=1, sticky="nw", padx=6, pady=4)
        
        else: #display information in hidden columns - more information
            for i, col in enumerate(hidden_columns):
                val = row.get(col, "")
                ttk.Label(infScrollFrame, text=f"{col}:", font=("Arial", 10, "bold"))\
                    .grid(row=i, column=0, sticky="ne", padx=6, pady=4)

                ttk.Label(infScrollFrame, text=val, wraplength=300, anchor="w")\
                    .grid(row=i, column=1, sticky="nw", padx=6, pady=4)

        #ScrollFrame.grid_columnconfigure(1, weight=1)
 
       # NoteFrame for notes 
        NoteFrame = ttk.Frame(win, relief="solid", padding=5)
        NoteFrame.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)

        NoteFrame.rowconfigure(0, weight=1)
        NoteFrame.columnconfigure(0, weight=1)

        canvas = tk.Canvas(NoteFrame) #add scrollbars
        vscroll = ttk.Scrollbar(NoteFrame, orient="vertical", command=canvas.yview)
        hscroll = ttk.Scrollbar(NoteFrame, orient="horizontal", command=canvas.xview)

            #set scrollbars
        canvas.configure(
            yscrollcommand=vscroll.set,
            xscrollcommand=hscroll.set
        )

        canvas.grid(row=0, column=0, sticky="nsew")
        vscroll.grid(row=0, column=1, sticky="ns")
        hscroll.grid(row=1, column=0, sticky="ew")

        ScrollFrame = ttk.Frame(canvas)
        canvas.create_window((0,0), window=ScrollFrame, anchor="nw")

        def ConfigureFrame(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        ScrollFrame.bind("<Configure>", ConfigureFrame)

        # Add text
        tk.Label(
            ScrollFrame,
            text=f"Notes: {row.get('Notes','')}",
            font=fonts["title"]
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=4, pady=4)

        ScrollFrame.grid_columnconfigure(1, weight=1)



         # Helper to guess the original column type for smarter conversion on save
        def _infer_type(val):
            if pd.isna(val):
                return "str"
            if isinstance(val, bool):
                return "bool"
            if isinstance(val, int) and not isinstance(val, bool):
                return "int"
            if isinstance(val, float):
                return "float"
            return "str"
         #right frame that will hold html page of image 
        #Newly implemented right frame should get the mapping functionality working??
        RightFrame = ttk.Frame(win, relief="solid", padding=5)
        RightFrame.grid(row=1, column=1, rowspan =2, sticky="nsew", padx=5, pady=5)
        RightFrame.rowconfigure(1,weight=1)
        RightFrame.columnconfigure(0,weight=1)

        # Title label inside RightFrame
        tk.Label(RightFrame, text="Map Viewer", font=fonts["title"]).pack(pady=5)
        # generate map html and png paths if none exist

        # use the address to build an ID that makes sense
        map_id = f"{row.get('Property Address Number:','')} {row.get('Property Address Street Name:','')}, {row.get('City:','')}".strip()
        # generate a valid address for the property
        map_address = f"{row.get('Property Address Number:','')} {row.get('Property Address Street Name:','')}, {row.get('City:','')} PA, {row.get('Zipcode:','')}, USA".strip()
        # create list of status flags for possible status and combination support
        status_flags = []

        if validate(row.get("Vacant Property:", "")):
                status_flags.append("Vacant")

        if validate(row.get("Property Blighted?", "")):
                status_flags.append("Blighted")

        if validate(row.get("Residential", "")):
                status_flags.append("Residential")

        if validate(row.get("Commercial", "")):
                status_flags.append("Commercial")
            
        # combine flags into a string
        status = " ".join(status_flags) if status_flags else None
        # create the map, so that the status effects the pin color
        test = geocode_address(map_address, label=map_id, status=status, cache=cache) 
        if not test:
                map_address = f"{row.get('Property Address Street Name:','')}, {row.get('City:','')} PA, {row.get('Zipcode:','')}, USA".strip()
                map_id = f"Property on {row.get('Property Address Street Name:','')}, {row.get('City:','')}".strip()
                test = geocode_address(map_address, label=map_id, status=status, cache=cache)

                if not test:
                    map_address = f"{row.get('City:','')} PA, {row.get('Zipcode:','')}, USA".strip()
                    map_id = f"Property in {row.get('City:','')}".strip()
                    
        out = create_map(map_address, ID=str(map_id), cache=cache, status=status, force_refresh= self.map_regen.get()) 
        MAP_HTML = out.with_suffix(".html")
        MAP_PNG = out.with_suffix(".png")
        
        # Load PNG into Tkinter inside RightFrame

        img = Image.open(MAP_PNG)
        tk_img = ImageTk.PhotoImage(img)

        label = tk.Label(RightFrame, image=tk_img)
        label.image = tk_img
        label.pack(fill="both", expand=True)

        # Button to open full interactive map in browser
        def open_in_browser(event=None):
            webbrowser.open(MAP_HTML.as_uri())

        # Bind left mouse click on the label to open_in_browser
        label.bind("<Button-1>", open_in_browser)
        
    def ToggleFavorite(self, idx, fav_btn):
        # safety check
        if "Favorited" not in self.df.columns:
            return

        # toggle value
        current = int(self.df.at[idx, "Favorited"])
        new_val = 0 if current == 1 else 1
        self.df.at[idx, "Favorited"] = new_val

        # update button text
        fav_btn.config(text="Unfavorite" if new_val == 1 else "Favorite")

#function that only shows that favorite properties as marked by user.  This displats a new tree with all properties with 1 in Favorited Column
    def ShowFavs(self):
        if "Favorited" not in self.df.columns:
            return  # safety check

        data = self.df[self.df["Favorited"] == 1]
        self.ShowTree(data)

    def ShowColumnSelector(self):
        #user is able to modify shown columns.

            top = tk.Toplevel(self)
            top.title("Show / Hide Columns")
            top.geometry("300x400")
            top.grab_set()  # modal window

            checkbox_vars = {}

            # Scrollable frame (in case many columns)
            canvas = tk.Canvas(top)
            scrollbar = ttk.Scrollbar(top, orient="vertical", command=canvas.yview)
            scroll_frame = ttk.Frame(canvas)

            scroll_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            # Create checkboxes
            for col in self.all_columns:
                var = tk.BooleanVar(value=(col in self.visible_columns))
                checkbox = ttk.Checkbutton(scroll_frame, text=col, variable=var)
                checkbox.pack(anchor="w", padx=10, pady=2)
                checkbox_vars[col] = var
            def select_all():
                for var in checkbox_vars.values():
                    var.set(True)
            def select_normal():
                for col,var in checkbox_vars.items():
                        if col in self.visible_columns:
                                var.set(True)
                        else:
                                var.set(False)

            def deselect_all():
                for var in checkbox_vars.values():
                    var.set(False)   

            def apply_changes():
                self.visible_columns = [
                    col for col, var in checkbox_vars.items() if var.get()
                ]
                self.BuildTree()
                self.ShowTree(self.df)  # repopulate tree
                top.destroy()
            btn_frame = ttk.Frame(top)
            btn_frame.pack(pady=10)

            ttk.Button(btn_frame, text="Select All", command=select_all).pack(side="left", padx=5)
            ttk.Button(btn_frame, text="Deselect All", command=deselect_all).pack(side="left", padx=5)
            ttk.Button(btn_frame, text="Default", command=select_normal).pack(side="left", padx=5)
            ttk.Button(btn_frame, text="Apply", command=apply_changes).pack(side="left", padx=5)  


 #function that deletes a row from the csv, thus deleting from treeview
    def DelProperty(self):
        # get selected items
        sels = self.tree.selection()
        if not sels:
            messagebox.showwarning("Delete", "No row selected to delete.")
            return

        # ask for confirmation
        if len(sels) == 1:
            prompt = "Delete the selected property?"
        else:
            prompt = f"Delete the {len(sels)} selected properties?"
        if not messagebox.askyesno("Confirm delete", prompt):
            return

        # collect indices (tags) corresponding to DataFrame indices
        idxs = []
        for iid in sels:
            tags = self.tree.item(iid, "tags") or ()
            if not tags:
                continue
            tag = tags[0]
            try:
                idx = int(tag)
            except Exception:
                # fallback: string index (if your df index is strings)
                idx = tag
            idxs.append(idx)

        if not idxs:
            messagebox.showwarning("Delete", "Could not determine rows to delete.")
            return

        try:
            # Drop the rows from the DataFrame (ignore missing)
            self.df = self.df.drop(index=idxs, errors="ignore")

            # Reset index so everything "pushes up" and indices are contiguous
            self.df = self.df.reset_index(drop=True)

            if not self.SaveMainCSV():
                return

            # Rebuild Treeview contents and _row_ids mapping
            # remove all existing items
            for iid in self.tree.get_children():
                self.tree.delete(iid)
            self._row_ids = {}
            for idx, row in self.df.iterrows():
                vals = [row.get(col, "") for col in VisibleColumns]
                # ensure strings for display (avoid NaN)
                vals = [("" if pd.isna(v) else str(v)) for v in vals]
                iid = self.tree.insert("", "end", values=vals, tags=(str(idx),))
                self._row_ids[idx] = iid

            messagebox.showinfo("Deleted", "Selected property(ies) deleted.")
        except Exception as e:
            messagebox.showerror("Delete error", f"Failed to delete row(s): {e}")
    
    def AddProperty(self):
        #user is able to add new property, with some required fields
        new_values = list(self.df.columns)

        new_win = tk.Toplevel(self)
        new_win.title("New Property")
        fonts = self.CurrentFonts()
        new_win.geometry(f"{self.ScaleValue(620, 500)}x{self.ScaleValue(520, 420)}")
        new_win.minsize(self.ScaleValue(420, 340), self.ScaleValue(300, 260))

        # Scrollable area
        addFrame = ttk.Frame(new_win, padding=8)
        addFrame.pack(fill="both", expand=True)

        addFrame.rowconfigure(0, weight=1)
        addFrame.columnconfigure(0, weight=1)

        newCanvas = tk.Canvas(addFrame)
        #add srollbars
        newVscroll = ttk.Scrollbar(addFrame, orient="vertical", command=newCanvas.yview)
        newHscroll = ttk.Scrollbar(addFrame, orient="horizontal", command=newCanvas.xview)

        newCanvas.configure(yscrollcommand=newVscroll.set, xscrollcommand=newHscroll.set)
        newCanvas.grid(row=0, column=0, sticky="nsew")
        newVscroll.grid(row=0, column=1, sticky="ns")
        newHscroll.grid(row=1, column=0, sticky="ew")

        ScrollFrame = ttk.Frame(newCanvas)
        canvas_window = newCanvas.create_window((0, 0), window=ScrollFrame, anchor="nw")

        ScrollFrame.bind("<Configure>", lambda e: newCanvas.configure(scrollregion=newCanvas.bbox("all")))
        newCanvas.bind("<Configure>", lambda e: newCanvas.itemconfig(canvas_window, width=e.width))

        # Store controls as (typ, var)
        controls = {}

        # Build form
        for i, col in enumerate(new_values):

            lbl = ttk.Label(ScrollFrame, text=f"{col}:", font=fonts["bold"])
            lbl.grid(row=i, column=0, sticky="e", padx=6, pady=6)

            var = tk.StringVar()
            typ = "str"  # default type
            validation = None

            #import values with dropdowns
            # ID
            if col == "ID":
                widget = ttk.Entry(ScrollFrame, textvariable=var, width=50)
                typ = "str"

            # City
            elif col == "City:":
                widget = ttk.Combobox(ScrollFrame, textvariable=var, values=Citys, state="readonly")

            # Municipality
            elif col == "Municipality:":
                widget = ttk.Combobox(ScrollFrame, textvariable=var, values=Municipalitys, state="readonly")

            # Favorited
            elif col == "Favorited":
                widget = ttk.Combobox(ScrollFrame, textvariable=var, values=["0", "1"], state="readonly")

            # Submitter Name
            elif col == "Submitter's Name:":
                widget = ttk.Combobox(ScrollFrame, textvariable=var, values=sub_names, state="readonly")

            # Submitter Email/Phone
            elif col.startswith("Submitter's Email"):
                widget = ttk.Entry(ScrollFrame, textvariable=var, width=50)

            # Boolean fields
            elif col in ["Commercial", "Residential", "Vacant Property:", "Property Blighted?"]:
                widget = ttk.Combobox(ScrollFrame, textvariable=var, values=["True", "False"], state="readonly")
                typ = "bool"

            # Start time
            elif col.startswith("Start time"):
                widget = ttk.Entry(ScrollFrame, textvariable=var, width=50)
                ttk.Button(
                    ScrollFrame, text="📅", width=3,
                    command=lambda v=var: open_calendar(new_win, v)
                ).grid(row=i, column=2, padx=4)
                typ = "date"

            # Completion time
            elif col.startswith("Completion time"):
                widget = ttk.Entry(ScrollFrame, textvariable=var, width=50)
                ttk.Button(
                    ScrollFrame, text="📅", width=3,
                    command=lambda v=var: open_calendar(new_win, v)
                ).grid(row=i, column=2, padx=4)
                typ = "date"

            # Zipcode
            elif col == "Zipcode:":
                widget = ttk.Entry(ScrollFrame, textvariable=var, width=50)

            # Address number
            elif col == "Property Address Number:":
                widget = ttk.Entry(ScrollFrame, textvariable=var, width=50)
                typ = "int"

            # Street name
            elif col == "Property Address Street Name:":
                widget = ttk.Entry(ScrollFrame, textvariable=var, width=50)

            # Generic date fields
            elif "time" in col.lower() or "date" in col.lower():
                widget = ttk.Entry(ScrollFrame, textvariable=var, width=50)
                typ = "date"

            # Default text
            else:
                widget = ttk.Entry(ScrollFrame, textvariable=var, width=50)

            widget.grid(row=i, column=1, sticky="we", padx=6, pady=6)

            # Store (typ, var)
            controls[col] = (typ, var)

        ScrollFrame.grid_columnconfigure(1, weight=1)

        # Buttons
        btnfrm = ttk.Frame(new_win, padding=6)
        btnfrm.pack(fill="x", side="bottom")

        def OnSave():
            #user can save property to df, must have some fields required, then makes a new row
            new_row = {}

            for col, (typ, var) in controls.items():
                val = var.get().strip()

                if typ == "int":
                    new_row[col] = int(val) if val else None
                elif typ == "float":
                    new_row[col] = float(val) if val else None
                elif typ == "bool":
                    new_row[col] = (val == "True")
                elif typ == "date":
                    new_row[col] = pd.to_datetime(val, errors="coerce")
                else:
                    new_row[col] = val
                    
            # Required fields
            required_fields = ["City:","Municipality:","Property Address Number:","Property Address Street Name:"]

            missing = []

            for field in required_fields:
                val = controls[field][1].get().strip()
                if not val:
                    missing.append(field)

            if missing:
                messagebox.showerror("Missing Required Fields","Please fill in the following required fields:\n\n" + "\n".join(missing))
                return

            zip_field = "Zipcode:"
            zip_value = controls[zip_field][1].get().strip()

            if not zip_value:
                messagebox.showerror("Missing ZIP Code", "ZIP Code is required.")
                return

            if zip_value not in JEFFERSON_ZIPS:
                messagebox.showerror(
                    "Invalid ZIP Code",
                    "ZIP Code must be in Jefferson County, PA.\n\n"
                    f"Invalid value: {zip_value}"
                )
                return    

            # Append new row
            self.df.loc[len(self.df)] = new_row

            if not self.SaveMainCSV():
                return

            # Update Treeview
            idx = len(self.df) - 1
            vals = []
            for col in VisibleColumns:
                v = self.df.at[idx, col]
                if isinstance(v, pd.Timestamp):
                    v = v.strftime("%Y-%m-%d")
                vals.append("" if pd.isna(v) else str(v))

            iid = self.tree.insert("", "end", values=vals, tags=(str(idx),))
            self._row_ids[idx] = iid

            messagebox.showinfo("Saved", "New property added.")
            new_win.destroy()

            #function to close without saving
        def OnCancel():
            try:
                new_win.grab_release()
            except Exception:
                pass
            new_win.destroy()

        #button has designated commands 
        save_btn = ttk.Button(btnfrm, text="Save", command = OnSave)
        cancel_btn = ttk.Button(btnfrm, text="Cancel", command = OnCancel)
        save_btn.pack(side="right", padx=6)
        cancel_btn.pack(side="right", padx=6)
            
            

    # allow user to edit fields of property 
    def EditProperty(self, idx, parent_win=None):
        try:
            row = self.df.loc[idx].copy()
        except Exception as e:
            messagebox.showerror("Edit error", f"Unable to find row {idx}: {e}")
            return

        skip_cols = {"ImagePath", "ID", "Created", "Modified"}
        editable_cols = [c for c in self.df.columns if c not in skip_cols]

        edit_win = tk.Toplevel(self)
        edit_win.title("Edit Property")
        fonts = self.CurrentFonts()
        edit_win.geometry(f"{self.ScaleValue(620, 500)}x{self.ScaleValue(520, 420)}")
        edit_win.minsize(self.ScaleValue(420, 340), self.ScaleValue(300, 260))

        # Scrollable area 
        frame = ttk.Frame(edit_win, padding=8)
        frame.pack(fill="both", expand=True)

        canvas = tk.Canvas(frame)
        vscroll = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)

        canvas.configure(yscrollcommand=vscroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

        inner = ttk.Frame(canvas)
        canvas_window = canvas.create_window((0, 0), window=inner, anchor="nw")

        def configure_frame(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        inner.bind("<Configure>", configure_frame)

        def configure_canvas(event):
            canvas.itemconfig(canvas_window, width=event.width)

        canvas.bind("<Configure>", configure_canvas)

        # Controls storage 
        controls = {}

        # Type inference 
        def _infer_type(val):
            if pd.isna(val):
                return "str"
            if isinstance(val, bool):
                return "bool"
            if isinstance(val, int) and not isinstance(val, bool):
                return "int"
            if isinstance(val, float):
                return "float"
            return "str"

        for i, col in enumerate(editable_cols): #some columns are not editable
            val = row.get(col, "")
            val = "" if pd.isna(val) else str(val)
            typ = _infer_type(row.get(col))

            lbl = ttk.Label(inner, text=f"{col}:", font=fonts["bold"])
            lbl.grid(row=i, column=0, sticky="e", padx=6, pady=6)

            # Default var
            var = tk.StringVar(value=val)

            # CITY
            if col == "City:":
                widget = ttk.Combobox(inner, textvariable=var, values=Citys, state="readonly")

            # MUNICIPALITY
            elif col == "Municipality:":
                widget = ttk.Combobox(inner, textvariable=var, values=Municipalitys, state="readonly")

            # BOOLEAN
            elif typ == "bool" or col in ["Commercial", "Residential", "Vacant Property:", "Property Blighted?"]:
                widget = ttk.Combobox(inner, textvariable=var, values=["True", "False"], state="readonly")

            # FAVORITED
            elif col == "Favorited":
                widget = ttk.Combobox(inner, textvariable=var, values=["0", "1"], state="readonly")

            # SUBMITTER NAME
            elif col == "Submitter's Name:":
                widget = ttk.Combobox(inner, textvariable=var, values=sub_names, state="readonly")

            # SUBMITTER EMAIL
            elif col.startswith("Submitter's Email"):
                widget = ttk.Combobox(inner, textvariable=var, values=sub_emails, state="readonly")

            # START TIME
            elif col.startswith("Start time"):
                widget = ttk.Entry(inner, textvariable=var)
                ttk.Button(inner, text="📅", width=3,
                           command=lambda v=var: open_calendar(inner.winfo_toplevel(), v)
                ).grid(row=i, column=4, padx=4)

            # COMPLETION TIME
            elif col.startswith("Completion time"):
                widget = ttk.Entry(inner, textvariable=var)
                ttk.Button(inner, text="📅", width=3,
                           command=lambda v=var: open_calendar(inner, v)
                ).grid(row=i, column=4, padx=4)

            # DEFAULT ENTRY
            else:
                widget = ttk.Entry(inner, textvariable=var, width=50)

            widget.grid(row=i, column=1, sticky="we", padx=6, pady=6)

            # Store correct variable
            controls[col] = (typ, var)


        inner.grid_columnconfigure(1, weight=1)

        # Buttons
        btnfrm = ttk.Frame(edit_win, padding=6)
        btnfrm.pack(fill="x", side="bottom")

        

        def OnSave():
            updates = {}

            # Convert values from UI
            for col, (typ, var) in controls.items():
                val = var.get()

                # Handle numeric + bool types
                try:
                    if typ == "int":
                        updates[col] = int(val) if val else None
                    elif typ == "float":
                        updates[col] = float(val) if val else None
                    elif typ == "bool":
                        updates[col] = (val == "True")
                    else:
                        updates[col] = val
                except:
                    updates[col] = val

            # Required fields - can not be left empty
            required_fields = [ "City:", "Municipality:","Property Address Number:","Property Address Street Name:"]

            missing = []

            for field in required_fields:
                val = controls[field][1].get().strip()
                if not val:
                    missing.append(field)

            if missing:
                messagebox.showerror(
                    "Missing Required Fields",
                    "Please fill in the following required fields:\n\n" + "\n".join(missing)
                )
                return

            zip_field = "Zipcode:"
            zip_value = controls[zip_field][1].get().strip()

            if not zip_value:
                messagebox.showerror("Missing ZIP Code", "ZIP Code is required.")
                return

            if zip_value not in JEFFERSON_ZIPS:
                messagebox.showerror(
                    "Invalid ZIP Code",
                    "ZIP Code must be in Jefferson County, PA.\n\n"
                    f"Invalid value: {zip_value}"
                )
                return

            new_row = {}

            # Notes handling
            if "Notes" in updates:
                raw = updates["Notes"]
                new_input = (raw or "").strip()

                old_raw = self.df.at[idx, "Notes"] if "Notes" in self.df.columns else ""
                previous_notes = "" if pd.isna(old_raw) else str(old_raw)

                if new_input == "":
                    updates.pop("Notes", None)
                else: #strips username of user and timestamp
                    ts = datetime.now().strftime("[%Y-%m-%d %H:%M:%S] ")
                    username = getpass.getuser()
                    formatted = f"[{username}]{ts}{new_input}"

                    if previous_notes and previous_notes in new_input:
                        combined = new_input
                    else:
                        combined = formatted if not previous_notes else f"{formatted}\n\n{previous_notes}"

                    updates["Notes"] = combined

            try:
                # Apply updates safely
                for c, v in updates.items():

                    # Detect date/time fields
                    if "time" in c.lower() or "date" in c.lower():

                        # Convert incoming string datetime
                        v = pd.to_datetime(v, errors="coerce")

                    # Assign to DataFrame
                    self.df.at[idx, c] = v

                if not self.SaveMainCSV():
                    return

                # Update Treeview
                if hasattr(self, "_row_ids") and idx in self._row_ids:
                    iid = self._row_ids[idx]
                    vals = [self.df.at[idx, col] if col in self.df.columns else "" for col in VisibleColumns]
                    vals = [("" if pd.isna(v) else str(v)) for v in vals]
                    self.tree.item(iid, values=vals)

                messagebox.showinfo("Saved", "Property updated.")
                edit_win.destroy()

            except Exception as e:
                messagebox.showerror("Update error", f"Failed: {e}")


        def OnCancel():
            edit_win.destroy()

        ttk.Button(btnfrm, text="Save", command=OnSave).pack(side="right", padx=6)
        ttk.Button(btnfrm, text="Cancel", command=OnCancel).pack(side="right", padx=6)
    #  Add note helper 
    def AddNote(self, idx, parent_win=None):
        #open dialog box to append note
        try:
            row = self.df.loc[idx]
        except Exception as e:
            #if can't find row, abore and tell user
            messagebox.showerror("Note error", f"Unable to find row {idx}: {e}")
            return

        #build small window for user to type note in
        note_win = tk.Toplevel(self)
        note_win.title("Add Note")
        note_win.geometry(f"{self.ScaleValue(420, 340)}x{self.ScaleValue(220, 190)}")
        try:
            note_win.transient(parent_win or self)
            note_win.grab_set()
        except Exception:
            pass

        
        #label for note box
        ttk.Label(note_win, text="Add note:").pack(anchor="w", padx=8, pady=(8, 4))
        txt = tk.Text(note_win, height=6, width=50)
        txt.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        #handler to add note
        def OnAdd():
            s = txt.get("1.0", "end").strip()
            if not s:
                messagebox.showwarning("Empty", "Note is empty.")
                return

            #add timestamp before contents of note
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            username = getpass.getuser()
            entry = f"[{username}] [{timestamp}] {s}"

            #initialize note column to be empty on csv
            if "Notes" not in self.df.columns:
                self.df["Notes"] = ""
            CurrentRaw = self.df.at[idx, "Notes"] if "Notes" in self.df.columns else None
            current = "" if pd.isna(CurrentRaw) or CurrentRaw is None else str(CurrentRaw)

            # Prepend new entry so newest appears first
            if current:
                NewInputs = f"{entry}\n\n{current}"
            else:
                NewInputs = entry

            self.df.at[idx, "Notes"] = NewInputs

            if not self.SaveMainCSV():
                return

            # update tree if needed
            if hasattr(self, "_row_ids") and idx in self._row_ids:
                try:
                    iid = self._row_ids[idx]
                    vals = [self.df.at[idx, col] if col in self.df.columns else "" for col in VisibleColumns]
                    vals = [("" if pd.isna(v) else str(v)) for v in vals]
                    self.tree.item(iid, values=vals)
                except Exception:
                    pass

            #notify user and close dialog
            messagebox.showinfo("Note added", "Note appended and saved.")
            try:
                note_win.grab_release()
            except Exception:
                pass
            note_win.destroy()

        #close not window if pressing cancel
        def OnCancel():
            try:
                note_win.grab_release()
            except Exception:
                pass
            note_win.destroy()

        #buttons for add/cancel in note window
        btnframe = ttk.Frame(note_win)
        btnframe.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(btnframe, text="Add", command=OnAdd).pack(side="right", padx=6)
        ttk.Button(btnframe, text="Cancel", command=OnCancel).pack(side="right", padx=6)
        
#  Run App 
if __name__ == "__main__":
    app = App()
    app.mainloop()
