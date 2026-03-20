# Name: Gannon Kearney, Brunner Good, Isaac Wagner, Alexis Valencia
# Created: 9/3/25
# Last Updated: 2/19/26
# Purpose: Display properties from CSV and show images using Python's Tkinter and Treeview.  User is able to create, edit, and delete properties while it saves to the csv in the folder.
    #Also displays the image (which is a hyperlink in the csv) using PIL.

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk, UnidentifiedImageError, ImageOps
import pandas as pd
import requests
import io
import re
import os
from datetime import datetime, timedelta

#to create new csv's
import csv

#added imporrts for image and mapping
from pathlib import Path
import webbrowser
import getpass
from MapModule import generate_full_map, _load_geocode_cache, validate, geocode_address, _save_geocode_cache, generate_property_preview



#added some imports to support exe bundling
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



#Take an image link - preferably from Google Drive and create a list of URL's for downloading
def FindLinkFormat(url: str):
    # if url is not a valid string or not a google drive link, return
    if not isinstance(url, str) or "drive.google.com" not in url:
        return [url]

    candidates = []
    # keep if the url is already in the uc? format
    if "drive.google.com/uc?" in url:
        candidates.append(url)

    #url may contain the phrase /d/
    m = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    if m:
        fid = m.group(1)
        #take the fileid if it ends in any of these examples
        candidates += [
            f"https://drive.google.com/uc?export=view&id={fid}",
            f"https://drive.google.com/uc?export=download&id={fid}",
            f"https://drive.google.com/thumbnail?id={fid}"
        ]

    #the url might end in ?id= or &id=
    m2 = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", url)
    if m2:
        #if the url has this build, grab the file id
        fid = m2.group(1)
        candidates += [
            f"https://drive.google.com/uc?export=view&id={fid}",
            f"https://drive.google.com/uc?export=download&id={fid}",
            f"https://drive.google.com/thumbnail?id={fid}"
        ]

    candidates.append(url)
    #make sure there are no duplicate url's
    seen = set()
    out = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out

#Download and open an image from a URL
def FindImageFromURL(url: str, timeout=10):
    candidates = FindLinkFormat(url)
    RecentError = None
    #try each url until one returns an image
    for candidate in candidates:
        try:
            resp = requests.get(candidate, stream=True, timeout=timeout)
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if ctype.startswith("image/"):
                data = resp.content
                img = Image.open(io.BytesIO(data))
                img.load()
                return img #return PIL image if successful
        except Exception as e:
            RecentError = e #raise runtime error if no url's work
    raise RuntimeError(f"Unable to fetch image. Last error: {RecentError}")

# ---- Data ----



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


def normalize(series):
    return series.astype(str).str.strip().str.lower()


# ---- App ----
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(Title)
        self.geometry("1100x600")
        self.minsize(900, 520) #min size of the main window
        
        self.df = Originaldf.copy()
        

        self.mode = tk.StringVar(value="Blight")  # NEW: "Blight" or "Inventory"
        
        self.all_columns = list(self.df.columns)
        self.visible_columns= [col for col in VisibleColumns if col in self.all_columns]

        if not self.visible_columns:
            self.visible_columns=self.all_columns.copy()

        self.menubar = tk.Menu(self)
        self.config(menu=self.menubar)

        self.CreateToolMenu()
        self.CreateSettingsMenu()
        self.CreateToolbar()
        self.BuildFilters()

        self.BuildTree()
        self.ShowTree(self.df)

        #Generate a fresh map
        self.CreateFullMap(False)

    def ToggleMode(self):  # NEW
        self.mode.set("Inventory" if self.mode.get() == "Blight" else "Blight")
        messagebox.showinfo("Mode Changed", f"Current mode: {self.mode.get()}")

    # --- Menu ---
    def CreateToolMenu(self): #creates a tool bar with navigation buttons
        menubar = tk.Menu(self)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="New File", command=self.NewCSV)
        filemenu.add_command(label="Save As", command=self.SaveAsCSV)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.destroy) #exit option closes program
        self.menubar.add_cascade(label="File", menu=filemenu)

    def CreateSettingsMenu(self): #create a settings menubar.  This can change font size, themes, and toggle the mode (blight or inventory)
        settingsbar = tk.Menu(self)
        settingsmenu = tk.Menu(settingsbar, tearoff=0)
        settingsmenu.add_command(label="Change Mode", command=self.ToggleMode)  # NEW
        settingsmenu.add_command(label="Themes")
        settingsmenu.add_command(label="Font Size")
        self.menubar.add_cascade(label="Settings", menu=settingsmenu)
        settingsmenu.add_command(label = "Show/Hide Columns", command=self.ShowColumnSelector)

      # --- Toolbar ---
    def CreateToolbar(self): #creates a tool bar with navigation buttons
        bar = ttk.Frame(self, padding=(8, 4))
        bar.pack(side="top", fill="x")
        self.SearchInput = tk.StringVar()
        #if an entry is place in Entry, it will call SearchInput
        entry = ttk.Entry(bar, textvariable=self.SearchInput, width=30)
        entry.pack(side="right", padx=4)

        #bind search bar to the apply filter command
        entry.bind("<Return>", self.ApplyFilters)
        #The Apply filters take into account, the filters selected and the search bar contents
        ttk.Button(bar, text="Search", command=self.ApplyFilters).pack(side="right", padx=4)
        
        ttk.Button(bar, text="New", command=self.AddProperty).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete", command=self.DelProperty).pack(side="left", padx=4)
        ttk.Button(bar, text="Show Favorites", command=self.ShowFavs).pack(side="left", padx=4)

        ttk.Button(bar, text="Toggle Mode", command=self.ToggleMode).pack(side="left", padx=4)  # NEW

   #Filters
    #Different filters based on customer needs
    def BuildFilters(self):
        frm = ttk.LabelFrame(self, text="Filters & Sort", padding=8)
        frm.pack(side="top", fill="x", padx=8, pady=(0, 8))

        self.BlightedFilter = tk.BooleanVar(value=False)
        self.VacancyFilter = tk.BooleanVar(value=False)

        ttk.Checkbutton(frm, text="Blighted", variable=self.BlightedFilter)\
            .grid(row=0, column=0, sticky="w")

        ttk.Checkbutton(frm, text="Vacant", variable=self.VacancyFilter)\
            .grid(row=0, column=1, sticky="w")

        #Use Dropdown
        uses = ["Both"] + sorted(self.df["Commercial"].dropna().unique().tolist() +
                                 self.df["Residential"].dropna().unique().tolist())

        self.use_var = tk.StringVar(value="Both")
        self.use = ttk.Combobox(frm, textvariable=self.use_var, values=["Both", "Commercial", "Residential"], state="readonly")
        self.use.grid(row=0, column=2, padx=6)

        #City Dropdown
        city_list = ["All"] + sorted(self.df["City:"].dropna().astype(str).str.strip().unique().tolist())

        self.city_var = tk.StringVar(value="All")
        self.City = ttk.Combobox(frm, textvariable=self.city_var, values=city_list, state="readonly")
        self.City.grid(row=0, column=3, padx=6)

        # Municipality Dropdown
        muni_list = ["All"] + sorted(self.df["Municipality:"].dropna().astype(str).str.strip().unique().tolist())

        self.muni_var = tk.StringVar(value="All")
        self.Municipality = ttk.Combobox(frm, textvariable=self.muni_var, values=muni_list, state="readonly")
        self.Municipality.grid(row=0, column=4, padx=6)

        #Date Range
        ttk.Label(frm, text="From Date").grid(row=1,column=0,sticky="w")
        self.from_date = tk.StringVar()
        ttk.Entry(frm, textvariable=self.from_date,width=12).grid(row=1,column=1)

        ttk.Label(frm, text="To Date").grid(row=1,column=2,sticky="w")
        self.to_date = tk.StringVar()
        ttk.Entry(frm, textvariable=self.to_date,width=12).grid(row=1,column=3)

        #ZipCode Filter
        ttk.Label(frm,text="ZipCode:").grid(row=1,column=4,sticky="w")
        zip_list = ["All"] + sorted(self.df["Zipcode:"].dropna().astype(str).unique().tolist())

        self.zip_var = tk.StringVar(value="All")
        self.zip = ttk.Combobox(frm, textvariable=self.zip_var,values=zip_list,state="readonly")
        self.zip.grid(row=1,column=5,padx=6)

        #LastModified Filter
        self.modified_var = tk.StringVar(value="All")
        ttk.Label(frm,text="Last Modified").grid(row=2, column=0)

        ttk.Combobox(frm, textvariable=self.modified_var, values=["All", "Last 24 Hours", "Last 7 Days", "Last 30 Days"], state="readonly").grid(row=2,column=1)

        # Buttons
        ttk.Button(frm, text="Apply", command=self.ApplyFilters).grid(row=0, column=5, padx=6)

        ttk.Button(frm, text="Reset", command=self.ResetFilters).grid(row=0, column=6, padx=6)

        #apply and reset filters call respective commands
        self.map_regen = tk.BooleanVar(value=False)
        ttk.Button(frm, text="Full Map", command=self.CreateFullMap).grid(row=0, column=7, sticky="w")

    def CreateFullMap(self, openMap=True):
        # --- 1. Build a set of valid map_ids from the dataframe ---
        valid_ids = set()

        for _, row in self.df.iterrows():
            primary_id = f"{row.get('Property Address Number:','')} {row.get('Property Address Street Name:','')}, {row.get('City:','')}"
            valid_ids.add(primary_id)

            fallback1 = f"Property on {row.get('Property Address Street Name:','')}, {row.get('City:','')}"
            valid_ids.add(fallback1)

            fallback2 = f"Property in {row.get('City:','')}"
            valid_ids.add(fallback2)

        # --- 2. Remove stale entries from cache ---
        stale_keys = [k for k in cache.keys() if k not in valid_ids]
        for k in stale_keys:
            del cache[k]

        # --- 3. Process each row and geocode only missing entries ---
        for _, row in self.df.iterrows():
            # Build primary address + ID
            address_full = f"{row.get('Property Address Number:','')} {row.get('Property Address Street Name:','')}, {row.get('City:','')} PA, {row.get('Zipcode:','')}, USA"
            map_id = f"{row.get('Property Address Number:','')} {row.get('Property Address Street Name:','')}, {row.get('City:','')}"

            # Build status string
            flags = []
            if validate(row.get("Vacant Property:", "")): flags.append("Vacant")
            if validate(row.get("Property Blighted?", "")): flags.append("Blighted")
            if validate(row.get("Residential", "")): flags.append("Residential")
            if validate(row.get("Commercial", "")): flags.append("Commercial")
            status = " ".join(flags) if flags else None

            # --- Primary geocode ---
            if map_id not in cache:
                coords = geocode_address(address_full, label=map_id, status=status, cache=cache)
            else:
                coords = cache[map_id]

            # --- Fallback 1 ---
            if not coords:
                fallback_addr = f"{row.get('Property Address Street Name:','')}, {row.get('City:','')} PA, {row.get('Zipcode:','')}, USA"
                fallback_id = f"Property on {row.get('Property Address Street Name:','')}, {row.get('City:','')}"
                coords = geocode_address(fallback_addr, label=fallback_id, status=status, cache=cache)

            # --- Fallback 2 ---
            if not coords:
                fallback_addr = f"{row.get('City:','')} PA, {row.get('Zipcode:','')}, USA"
                fallback_id = f"Property in {row.get('City:','')}"
                coords = geocode_address(fallback_addr, label=fallback_id, status=status, cache=cache)

            # Save if valid
            if coords:
                cache[fallback_id if 'fallback_id' in locals() else map_id] = coords

        # --- 4. Save cache once ---
        _save_geocode_cache(cache)

        # --- 5. Generate and show full map ---
        if openMap:
            full_map_path = generate_full_map(cache)
            html_path = full_map_path.with_suffix(".html")
            png_path = full_map_path.with_suffix(".png")

            if not png_path.exists():
                messagebox.showerror("Error", "Failed to generate map image.")
                return

            new_win = tk.Toplevel(self)
            new_win.title("Full Map of All Properties")

            img = Image.open(png_path)
            photo = ImageTk.PhotoImage(img)

            label = tk.Label(new_win, image=photo, cursor="hand2")
            label.image = photo
            label.pack(padx=20, pady=20)

            def open_in_browser(event=None):
                webbrowser.open(html_path.as_uri())

            label.bind("<Button-1>", open_in_browser)

    #create a new csv with the 
    def NewCSV(self):
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
        
    #This function takes the contents of the csv and displays them in an easy-to-read table
    # TreeView
    def BuildTree(self):
        # Destroy previous tree frame completely (prevents stacking)
        if hasattr(self, "tree_container"):
            self.tree_container.destroy()

        # Create container frame once per rebuild
        self.tree_container = ttk.Frame(self)
        self.tree_container.pack(side="top", fill="both", expand=True, padx=8, pady=8)

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
            self.tree.column(col, width=150, anchor="w", minwidth=110)

        # Selection binding
        self.tree.bind("<<TreeviewSelect>>", self.Selected)

        # Insert data
        self._row_ids = {}

        for idx, row in self.df.iterrows():
            vals = [row.get(col, "") for col in self.visible_columns]
            iid = self.tree.insert("", "end", values=vals, tags=(str(idx),))
            self._row_ids[idx] = iid

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
        self.BlightedFilter.set(False)
        self.VacancyFilter.set(False)

        self.use_var.set("Both")
        self.city_var.set("All")
        self.muni_var.set("All")

        self.SearchInput.set("")

        self.from_date.set("")
        self.to_date.set("")
        self.zip_var.set("All")
        self.modified_var.set("All")
        self.SearchInput.set("")
        
        self.df = Originaldf.copy()
        self.ShowTree(self.df)

    

    # This function displays what happens when a row is selected on
        #It displays property details, an image from the csv, and the ability to edit all values or notes
    def Selected(self, event):
        selected = self.tree.selection()
        if not selected:
            return

        # get dataframe index for selected row
        tag = self.tree.item(selected[0], "tags")[0]
        try:
            idx = int(tag)
        except Exception:
            idx = tag
        row = self.df.loc[idx]

        win = tk.Toplevel(self)
        #the title of the window is the address of the property (as requested)
        win.title(f"Property Address: {row.get('Property Address Number:','')} {row.get('Property Address Street Name:','')}")
        win.geometry("800x600") #minimum size of the window
        win.minsize(400, 300)
        win.columnconfigure(0, weight=1)
        win.columnconfigure(1, weight=1)
        win.rowconfigure(1, weight=1)



        #  Top image frame (where the image is presented)
        ImageFrame = ttk.Frame(win, height=max(120, win.winfo_height() // 3), relief="solid")
        ImageFrame.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        ImageFrame.grid_propagate(False)
        #label shown while image loads
        ImageLabel = tk.Label(ImageFrame, bg="lightgray", text="Loading image...", anchor="center", justify="center")
        ImageLabel.pack(expand=True, fill="both")

        #load the image
        OriginalImage = None
        img_path = row.get("ImagePath", None) #get the image from the ImagePath row
        
        if img_path and isinstance(img_path, str) and img_path.strip():
            img_path = img_path.strip()
            try:
                if img_path.startswith("http"): #grab url from the web
                    OriginalImage = FindImageFromURL(img_path)
                else:
                    #if it is a local file path, verify that it exists
                    if not os.path.exists(img_path):
                        raise FileNotFoundError(f"Local file not found: {img_path}")
                    OriginalImage = Image.open(img_path)
                    OriginalImage.load()

                #the image might be rotation, so correct that    
                try:
                    OriginalImage = ImageOps.exif_transpose(OriginalImage)
                except Exception:
                    pass
                
                ImageLabel.config(text="") #clear the label after it has loaded
            except Exception as e:
                #if there is a problem, show error message
                OriginalImage = None
                ImageLabel.config(text=f"Image not available\n{e}")
                print("ERROR loading image:", e)
        else:
            #if no image path exists
            ImageLabel.config(text="No Image Available")

        #Buttons outside frames
        #these are displayed to be able to edit property values and add notes specific to the property
        EditBtn = ttk.Button(win, text="Edit Property Values", command=lambda i=idx: self.EditProperty(i, win))
        NoteBtn = ttk.Button(win, text="Add Note", command=lambda i=idx: self.AddNote(i, win))
        
        EditBtn.grid(row=3, column=0, sticky="ew", padx=8, pady=(6, 8))
        NoteBtn.grid(row=3, column=1, sticky="ew", padx=8, pady=(6, 8))

        # determine initial button text
        fav_text = "Unfavorite" if self.df.at[idx, "Favorited"] == 1 else "Favorite"

        FavBtn = ttk.Button(win,text=fav_text,command=lambda i=idx, b=None: self.ToggleFavorite(i, b))

        # hack to pass the button instance to itself
        FavBtn.config(command=lambda i=idx, b=FavBtn: self.ToggleFavorite(i, b))

        FavBtn.grid(row=2, column=1, sticky="ew", padx=8, pady=(6, 8))


        # finds out how big the image should be based on the window size
        def MaxSize():
            WinH = max(300, win.winfo_height())
            MaxH = max(120, WinH // 3) #height is always 1/3 of the window
            WinW = max(300, win.winfo_width())
            MaxW = WinW - 40 #subtract padding
            return MaxW, MaxH
        #function resizes the image, essentially bootstrapping
        def ResizeImage(event=None):
            nonlocal OriginalImage
            if not OriginalImage:
                #show place holder tet if there is no image available
                ImageLabel.config(image="", text=ImageLabel.cget("text"))
                return

            #get new frame size
            try:
                if event is not None and getattr(event, "widget", None) is ImageFrame:
                    FrameW = max(1, getattr(event, "width", ImageFrame.winfo_width()))
                    FrameH = max(1, getattr(event, "height", ImageFrame.winfo_height()))
                else:
                    FrameW = ImageFrame.winfo_width()
                    FrameH = ImageFrame.winfo_height()
            except Exception:
                FrameW = ImageFrame.winfo_width()
                FrameH = ImageFrame.winfo_height()

            #if the frame is not visible, try again soon
            if FrameW <= 1 or FrameH <= 1:
                win.after(80, ResizeImage)
                return
            
            #apply maximum size limits
            MaxW, MaxH = MaxSize()
            ImageFrame.configure(height=MaxH)
            FrameW = min(FrameW, MaxW)
            FrameH = min(FrameH, MaxH)

            #get image dimensions
            try:
                iw, ih = OriginalImage.size
            except Exception:
                return
            if iw == 0 or ih == 0:
                return

            #get ratio of image
            ImageRatio = iw / ih if ih != 0 else 1
            frame_ratio = FrameW / FrameH if FrameH != 0 else 1
            if frame_ratio > ImageRatio:
                TargetH = FrameH
                TargetW = int(TargetH * ImageRatio)
            else:
                TargetW = FrameW
                TargetH = int(TargetW / ImageRatio)

            #upscale is false so the image can maintain sharp
            allow_upscale = False
            if not allow_upscale:
                TargetW = min(TargetW, iw)
                TargetH = min(TargetH, ih)
                
            TargetW = max(1, int(TargetW))
            TargetH = max(1, int(TargetH))

            #if the size has not change, do not change the values
            cur = getattr(ImageLabel, "_last_size", (0, 0))
            if (TargetW, TargetH) == cur:
                return
            ImageLabel._last_size = (TargetW, TargetH)

            try:
                resized = OriginalImage.resize((TargetW, TargetH), Image.LANCZOS)
            except Exception:
                # fallback to thumbnail (in-place) if resize fails
                try:
                    resized = OriginalImage.copy()
                    resized.thumbnail((TargetW, TargetH), Image.LANCZOS)
                except Exception:
                    return

            #display new image in label once resized
            photo = ImageTk.PhotoImage(resized)
            ImageLabel.config(image=photo, text="")
            ImageLabel.image = photo

        #update image dynamically
        ImageFrame.bind("<Configure>", ResizeImage)
        win.bind("<Configure>", lambda e: ResizeImage(e))
        win.after(150, ResizeImage)

        
        # InfoFrame and RightFrame 
        InfoFrame=ttk.Frame(win,relief="solid",padding=5)
        InfoFrame.grid(row=1,column=0,sticky="nsew", padx=5,pady=5)

        InfoFrame.grid_rowconfigure(0,weight=1)
        InfoFrame.grid_columnconfigure(0,weight=1)

        canvas = tk.Canvas(InfoFrame)
        vscroll = ttk.Scrollbar(InfoFrame, orient="vertical", command=canvas.yview)
        hscroll = ttk.Scrollbar(InfoFrame, orient="horizontal", command=canvas.xview)

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


        hidden_columns=[col for col in self.all_columns if col not in self.visible_columns]


        if self.mode.get() == "Inventory":
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
                    ttk.Label(ScrollFrame, text=f"{label}:", font=("Arial", 10, "bold"))\
                        .grid(row=r, column=0, sticky="ne", padx=6, pady=4)

                    ttk.Label(ScrollFrame, text=val, wraplength=300, anchor="w")\
                        .grid(row=r, column=1, sticky="nw", padx=6, pady=4)
        else:
            for i, col in enumerate(hidden_columns):
                val = row.get(col, "")
                ttk.Label(ScrollFrame, text=f"{col}:", font=("Arial", 10, "bold"))\
                    .grid(row=i, column=0, sticky="ne", padx=6, pady=4)

                ttk.Label(ScrollFrame, text=val, wraplength=300, anchor="w")\
                    .grid(row=i, column=1, sticky="nw", padx=6, pady=4)

        ScrollFrame.grid_columnconfigure(1, weight=1)

        #right frame that will hold html page of image 
        #Newly implemented right frame should get the mapping functionality working??
        RightFrame = ttk.Frame(win, relief="solid", padding=5)
        RightFrame.grid(row=1, column=1, rowspan=2, sticky="nsew", padx=5, pady=5)

        # Title label inside RightFrame
        tk.Label(RightFrame, text="Map Viewer", font=("Arial", 12, "bold")).pack(pady=5)
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
                    
        # Build sanitized name
        safe_name = re.sub(r"[^A-Za-z0-9_]", "_", map_id)

        full_map_html = CACHE_DIR / "Full_Map.html"
        preview_path = CACHE_DIR / f"{safe_name}_preview.png"

        preview = generate_property_preview(full_map_html, safe_name, preview_path)

        if preview and preview.exists():
            img = Image.open(preview)
            img = img.resize((350, 350))
            tk_img = ImageTk.PhotoImage(img)

            map_label = tk.Label(win, image=tk_img, cursor="hand2")
            map_label.image = tk_img
            map_label.grid(row=1, column=1, sticky="nsew", padx=10, pady=10)

            # Clicking opens full map
            map_label.bind("<Button-1>", lambda e: webbrowser.open(full_map_html.as_uri()))
        else:
            tk.Label(win, text="Map preview unavailable").grid(row=1, column=1)
                
        #place holder right frame that will hold html page of image 
        # NoteFrame for notes 
        NoteFrame = ttk.Frame(win, relief="solid", padding=5)
        NoteFrame.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)

        NoteFrame.rowconfigure(1, weight=1)
        NoteFrame.columnconfigure(0, weight=1)

        # Header label
        tk.Label(
            NoteFrame,
            text=f"Notes: {row.get('Notes','')}",
            font=("Arial", 12, "bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=4, pady=4)

        # Canvas + scrollbars
        note_canvas = tk.Canvas(NoteFrame)
        note_vscroll = ttk.Scrollbar(NoteFrame, orient="vertical", command=note_canvas.yview)
        note_hscroll = ttk.Scrollbar(NoteFrame, orient="horizontal", command=note_canvas.xview)

        note_canvas.configure(
            yscrollcommand=note_vscroll.set,
            xscrollcommand=note_hscroll.set
        )

        note_canvas.grid(row=1, column=0, sticky="nsew")
        note_vscroll.grid(row=1, column=1, sticky="ns")
        note_hscroll.grid(row=2, column=0, sticky="ew")

        # Scrollable frame
        NoteScrollFrame = ttk.Frame(note_canvas)
        note_window = note_canvas.create_window((0, 0), window=NoteScrollFrame, anchor="nw")

        # Update scroll region when content changes
        def note_configure_frame(event):
            note_canvas.configure(scrollregion=note_canvas.bbox("all"))

        NoteScrollFrame.bind("<Configure>", note_configure_frame)

        # Resize inner frame with canvas
        def note_configure_canvas(event):
            note_canvas.itemconfig(note_window, width=event.width)

        note_canvas.bind("<Configure>", note_configure_canvas)


        # Example: display notes text inside scrollable area
        notes_text = row.get("Notes", "")

        ttk.Label(
            NoteScrollFrame,
            text=notes_text,
            wraplength=350,
            anchor="nw",
            justify="left"
        ).grid(row=0, column=0, sticky="nw", padx=5, pady=5)



         # Helper to guess the original column type for smarter conversion on save
        def _infer_type(val):
            if pd.isna(val):
                return "str"
            if isinstance(val, bool):
                return "bool"
            # note: bool is subclass of int, so check bool above
            if isinstance(val, int) and not isinstance(val, bool):
                return "int"
            if isinstance(val, float):
                return "float"
            return "str"
        
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

            def apply_changes():
                self.visible_columns = [
                    col for col, var in checkbox_vars.items() if var.get()
                ]
                self.BuildTree()
                self.ShowTree(self.df)  # repopulate tree
                top.destroy()
                
            ttk.Button(top, text="Apply", command=apply_changes).pack(pady=10)


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

            # Backup CSV before writing
            csv_path = CSV_PATH
            try:
                if os.path.exists(csv_path):
                    bak_name = f"{os.path.splitext(csv_path)[0]}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                    os.replace(csv_path, bak_name)
            except Exception as e:
                messagebox.showwarning("Backup warning", f"Failed to create backup: {e}")

            # Save updated CSV
            try:
                self.df.to_csv(csv_path, index=False)
            except Exception as e:
                messagebox.showwarning("Save warning", f"Failed to write CSV ({csv_path}): {e}")

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
    
    #function that adds appends a new property to csv
    def AddProperty(self):
        new_values = [c for c in self.df.columns]

        new_win = tk.Toplevel(self)
        new_win.title("New Property")
        new_win.geometry("620x520") #new window opens with these dimensions
        new_win.minsize(420,300) #minimum size of window

        #scrollable area

        addFrame = ttk.Frame(new_win,padding=8)
        addFrame.pack(fill="both",expand=True)

        addFrame.rowconfigure(0,weight=1)
        addFrame.columnconfigure(0,weight=1)

        #enables scrollable window
        newCanvas = tk.Canvas(addFrame)
        newVscroll = ttk.Scrollbar(addFrame, orient="vertical", command=newCanvas.yview)
        newHscroll = ttk.Scrollbar(addFrame, orient="horizontal", command=newCanvas.xview)
        newCanvas.configure(yscrollcommand=newVscroll.set)

        
        newCanvas.configure(
            yscrollcommand=newVscroll.set,
            xscrollcommand=newHscroll.set
        )

        newCanvas.grid(row=0, column=0, sticky="nsew")
        newVscroll.grid(row=0, column=1, sticky="ns")
        newHscroll.grid(row=1, column=0, sticky="ew")

        # Scrollable frame
        ScrollFrame = ttk.Frame(newCanvas)
        canvas_window = newCanvas.create_window((0, 0), window=ScrollFrame, anchor="nw")

        #keep the scroll space up-to-date whenever size changes
        def configure_frame(event):
            newCanvas.configure(scrollregion=newCanvas.bbox("all"))

        ScrollFrame.bind("<Configure>", configure_frame)

        # Resize inner frame with canvas
        def configure_canvas(event):
            newCanvas.itemconfig(canvas_window, width=event.width)

        newCanvas.bind("<Configure>", configure_canvas)


        #stores input controls to be read
        controls = {}
        
        #each row will hold a new column detail
        for i, col in enumerate(new_values):
            #label for the column name is the column name from the csv
            lbl = ttk.Label(ScrollFrame, text=f"{col}:", font=("Arial", 10, "bold"))
            lbl.grid(row=i, column=0, sticky="e", padx=6, pady=6)

            if col == "City:":
                var=tk.StringVar()
                widget=ttk.Combobox(ScrollFrame, textvariable=var, values=Citys, state="readonly")

            elif col == "Municipality:":
                var=tk.StringVar()
                widget=ttk.Combobox(ScrollFrame, textvariable=var, values=Municipalitys, state="readonly")

            #dropdown cases
            elif col == "Favorited":
                var=tk.StringVar(value=favorited_options[0])
                widget=ttk.Combobox(ScrollFrame, textvariable=var, values=favorited_options, state="readonly")

            elif col == "Submitter's Name:":
                var=tk.StringVar()
                widget=ttk.Combobox(ScrollFrame, textvariable=var, values=sub_names, state="readonly")

            elif col ==  "Submitter's Email or Phone Number (this information will be used to collect any critical information or clear up any discrepancies)":
                var=tk.StringVar()
                widget=ttk.Combobox(ScrollFrame, textvariable=var, values=sub_emails, state="readonly")

            elif col in ["Commercial", "Residential", "Vacant Property:", "Property Blighted?"]:
                var = tk.StringVar(value="False")
                widget = ttk.Combobox(ScrollFrame, textvariable=var,values=["True", "False"], state="readonly")
            else:
                #use entry widget to change values
                var = tk.StringVar(value="")
                widget = ttk.Entry(ScrollFrame, textvariable=var, width=50)
                
            widget.grid(row=i, column=1, sticky="we", padx=6, pady=6)
            controls[col] = var
            
        #right column should expand with window
        ScrollFrame.grid_columnconfigure(1, weight=1)

        # Buttons at bottom
        btnfrm = ttk.Frame(new_win, padding=6)
        btnfrm.pack(fill="x", side="bottom")

        # When user clicks Save: gather controls, create new row, append, save, update tree
        def OnSave():
            # read controls
            new_row = {}
            for col, var in controls.items():
                # leave empty string for blanks (consistent with other code)
                new_row[col] = var.get()

            # Generate Created and Modified timestamps
            now_iso = datetime.now().isoformat()
            if "Created" in new_row:
                new_row["Created"] = now_iso
            if "Modified" in new_row:
                new_row["Modified"] = now_iso

            # Generate ID if present and numeric
            if "ID" in new_row:
                try:
                    # attempt to create a numeric ID: max existing numeric ID + 1
                    existing_ids = pd.to_numeric(self.df["ID"], errors="coerce")
                    if existing_ids.notna().any():
                        max_id = int(existing_ids.max())
                        new_id = max_id + 1
                    else:
                        new_id = len(self.df) + 1
                    new_row["ID"] = new_id
                except Exception:
                    # fallback: use length+1 as ID (string)
                    new_row["ID"] = len(self.df) + 1

            # Ensure all dataframe columns exist in the row (fill missing with "")
            for c in self.df.columns:
                if c not in new_row:
                    new_row[c] = ""

            # Append to dataframe
            try:
                appended = pd.DataFrame([new_row])
                # keep original columns order
                appended = appended[self.df.columns]
                self.df = pd.concat([self.df, appended], ignore_index=True)
            except Exception as e:
                messagebox.showerror("Append error", f"Failed to append new row: {e}")
                return

            # Save CSV with backup
            csv_path = CSV_PATH
            try:
                if os.path.exists(csv_path):
                    bak_name = f"{os.path.splitext(csv_path)[0]}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                    os.replace(csv_path, bak_name)
            except Exception as e:
                messagebox.showwarning("Backup warning", f"Failed to create backup: {e}")

            try:
                self.df.to_csv(csv_path, index=False)
            except Exception as e:
                messagebox.showwarning("Save warning", f"Failed to write CSV ({csv_path}): {e}")

            # Update Treeview: insert new row at end and record its iid
            try:
                idx = self.df.index[-1]
                vals = [self.df.at[idx, col] if col in self.df.columns else "" for col in VisibleColumns]
                vals = [("" if pd.isna(v) else str(v)) for v in vals]
                iid = self.tree.insert("", "end", values=vals, tags=(str(idx),))
                self._row_ids[idx] = iid
            except Exception:
                # if tree update fails, ignore but continue
                pass

            messagebox.showinfo("Saved", "New property added and saved.")
            try:
                new_win.grab_release()
            except Exception:
                pass
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
        edit_win.geometry("620x520")
        edit_win.minsize(420, 300)

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

        # Build form
        for i, col in enumerate(editable_cols):
            val = row.get(col, "")
            typ = _infer_type(val)

            lbl = ttk.Label(inner, text=f"{col}:", font=("Arial", 10, "bold"))
            lbl.grid(row=i, column=0, sticky="e", padx=6, pady=6)

            #Widget selection

            if col == "City:":
                var=tk.StringVar(value=str(val))
                widget=ttk.Combobox(inner, textvariable=var, values=Citys, state="readonly")

            elif col == "Municipality:":
                var=tk.StringVar(value=str(val))
                widget=ttk.Combobox(inner, textvariable=var, values=Municipalitys, state="readonly")

            elif typ == "bool" or col in ["Commercial", "Residential", "Vacant Property:", "Property Blighted?"]:
                var = tk.StringVar(value=str(val))
                widget = ttk.Combobox(inner, textvariable=var, values=["True", "False"], state="readonly")

            elif col == "Favorited":
                var = tk.StringVar(value=str(val))
                widget = ttk.Combobox(inner, textvariable=var, values=["0", "1"], state="readonly")

            elif col == "Submitter's Name:":
                var = tk.StringVar(value=str(val))
                widget = ttk.Combobox(inner, textvariable=var, values=sub_names, state="readonly")

            elif col.startswith("Submitter's Email"):
                var = tk.StringVar(value=str(val))
                widget = ttk.Combobox(inner, textvariable=var, values=sub_emails, state="readonly")

            else:
                var = tk.StringVar(value="" if pd.isna(val) else str(val))
                widget = ttk.Entry(inner, textvariable=var, width=50)

            widget.grid(row=i, column=1, sticky="we", padx=6, pady=6)
            controls[col] = (typ, var)

        inner.grid_columnconfigure(1, weight=1)

        # Buttons
        btnfrm = ttk.Frame(edit_win, padding=6)
        btnfrm.pack(fill="x", side="bottom")

        def OnSave():
            updates = {}

            # Convert values
            for col, (typ, var) in controls.items():
                val = var.get()
                try:
                    if typ == "int":
                        updates[col] = int(val) if val else None
                    elif typ == "float":
                        updates[col] = float(val) if val else None
                    elif typ == "bool":
                        updates[col] = val == "True"
                    else:
                        updates[col] = val
                except:
                    updates[col] = val

            # Notes handling
            if "Notes" in updates:
                raw = updates["Notes"]
                new_input = (raw or "").strip()

                old_raw = self.df.at[idx, "Notes"] if "Notes" in self.df.columns else ""
                previous_notes = "" if pd.isna(old_raw) else str(old_raw)

                if new_input == "":
                    updates.pop("Notes", None)
                else:
                    ts = datetime.now().strftime("[%Y-%m-%d %H:%M:%S] ")
                    formatted = f"[{username}]{ts}{new_input}"

                    if previous_notes and previous_notes in new_input:
                        combined = new_input
                    else:
                        combined = formatted if not previous_notes else f"{formatted}\n\n{previous_notes}"

                    updates["Notes"] = combined

            try:
                # Apply updates
                for c, v in updates.items():
                    self.df.at[idx, c] = v

                # Backup
                if os.path.exists(CSV_PATH):
                    bak = f"{os.path.splitext(CSV_PATH)[0]}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                    os.replace(CSV_PATH, bak)

                # Save
                self.df.to_csv(CSV_PATH, index=False)

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
        note_win.geometry("420x180")
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

            # save CSV (with backup)
            csv_path = CSV_PATH
            try:
                if os.path.exists(csv_path):
                    bak_name = f"{os.path.splitext(csv_path)[0]}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                    os.replace(csv_path, bak_name)
            except Exception as e:
                #if csv is already open
                messagebox.showwarning("Backup warning", f"Failed to create backup: {e}")
            try:
                self.df.to_csv(csv_path, index=False)
            except Exception as e:
                messagebox.showwarning("Save warning", f"Failed to write CSV ({csv_path}): {e}")

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
