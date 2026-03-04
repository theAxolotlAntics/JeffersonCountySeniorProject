# Name: Gannon Kearney, Brunner Good, Isaac Wagner, Alexis Valencia
# Created: 9/3/25
# Last Updated: 2/19/26
# Purpose: Display properties from CSV and show images using Python's Tkinter and Treeview.
#          User can create, edit, and delete properties while it saves to the csv in the folder.
#          Also displays the image (which is a hyperlink in the csv) using PIL.

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk, UnidentifiedImageError, ImageOps
import pandas as pd
import requests
import io
import re
import os
from datetime import datetime, timedelta

# to create new csv's
import csv

# added imports for image and mapping
from pathlib import Path
import webbrowser
import getpass
from MapModule import create_map, geocode_address, generate_full_map, _save_geocode_cache, _load_geocode_cache, validate

# added some imports to support exe bundling
import json
import logging
from pathlib import Path

import folium
import geopandas as gpd
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
from shapely.geometry import Point
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# Define global paths
BASE_DIR = Path(__file__).parent
CACHE_DIR = BASE_DIR / "resources" / "cachedMaps"
cache = _load_geocode_cache()


# Take an image link - preferably from Google Drive and create a list of URL's for downloading
def FindLinkFormat(url: str):
    if not isinstance(url, str) or "drive.google.com" not in url:
        return [url]

    candidates = []
    if "drive.google.com/uc?" in url:
        candidates.append(url)

    m = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    if m:
        fid = m.group(1)
        candidates += [
            f"https://drive.google.com/uc?export=view&id={fid}",
            f"https://drive.google.com/uc?export=download&id={fid}",
            f"https://drive.google.com/thumbnail?id={fid}",
        ]

    m2 = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", url)
    if m2:
        fid = m2.group(1)
        candidates += [
            f"https://drive.google.com/uc?export=view&id={fid}",
            f"https://drive.google.com/uc?export=download&id={fid}",
            f"https://drive.google.com/thumbnail?id={fid}",
        ]

    candidates.append(url)

    seen = set()
    out = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


# Download and open an image from a URL
def FindImageFromURL(url: str, timeout=10):
    candidates = FindLinkFormat(url)
    RecentError = None
    for candidate in candidates:
        try:
            resp = requests.get(candidate, stream=True, timeout=timeout)
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if ctype.startswith("image/"):
                data = resp.content
                img = Image.open(io.BytesIO(data))
                img.load()
                return img
        except Exception as e:
            RecentError = e
    raise RuntimeError(f"Unable to fetch image. Last error: {RecentError}")


# --------------------------------------------------------------------------------------------------------------------------
# csv that is being read - in the same folder as the program
CSV_PATH = "Blight Mitigation Data.csv"
# --------------------------------------------------------------------------------------------------------------------------


def choose_csv_path():
    # Prompt the user to pick a CSV file.
    root = tk.Tk()
    root.withdraw()
    path = filedialog.askopenfilename(
        title="Select CSV file",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
    )
    root.destroy()
    return path


# Let the user choose a CSV file first
user_path = choose_csv_path()
if user_path:
    CSV_PATH = user_path

if not os.path.exists(CSV_PATH):
    # create a minimal sample CSV so the app runs if file missing
    sample = pd.DataFrame(
        {
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
            "Notes": [""],
        }
    )
    sample.to_csv(CSV_PATH, index=False)

df = pd.read_csv(CSV_PATH)
Title = "Blight Inventory"

# columns wanted on the main page
VisibleColumns = [
    "ID",
    "Start time",
    "Completion time",
    "Email",
    "First",
    "Last",
    "Date of Property Review:",
    "Parcel ID, if known:",
    "Property Address Number:",
    "Property Address Street Name:",
    "City:",
    "Zipcode:",
    "Municipality:",
    "Property Blighted?",
    "Commercial",
    "Residential",
    "Vacant Property:",
    "Submitter's Name:",
    "Submitter's Email or Phone Number (this information will be used to collect any critical information or clear up any discrepancies)",
]


# Citys and Municipalitys in Jefferson County
Citys = [
    "Big Run",
    "Brockway",
    "Brookville",
    "Corsica",
    "Falls Creek",
    "Punxsutawney",
    "Reynoldsville",
    "Summerville",
    "Sykesville",
    "Timblin",
    "Worthville",
]
Municipalitys = [
    "Barnett",
    "Beaver",
    "Bell",
    "Clover",
    "Eldred",
    "Gaskill",
    "Heath",
    "Henderson",
    "Knox",
    "McCalmont",
    "Oliver",
    "Perry",
    "Pine Creek",
    "Polk",
    "Porter",
    "Ringgold",
    "Rose",
    "Snyder",
    "Union",
    "Warsaw",
    "Washington",
    "Winslow",
    "Young",
]

Uses = ["Commercial", "Residential"]


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        # ---------- Styling (Code 1 original) ----------
        style = ttk.Style(self)
        style.theme_use("clam")

        default_font = ("Segoe UI", 10)
        style.configure("TButton", font=default_font, padding=6)
        style.configure("TLabel", font=default_font)
        style.configure("TLabelframe", padding=10)
        style.configure("TLabelframe.Label", font=("Segoe UI", 11, "bold"))
        style.configure("Treeview", font=("Segoe UI", 10), rowheight=28)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        style.configure("TCombobox", padding=4)
        style.configure("TEntry", padding=4)
        # ----------------------------------------------

        self.title(Title)
        self.geometry("1100x600")
        self.minsize(900, 520)

        self.df = df.copy()

        # --- Mode (NEW) ---
        # Blight mode: show full survey details
        # Inventory mode: hide survey questions + hide "Property Blighted?" everywhere it shows
        self.mode = tk.StringVar(value="Blight")  # "Blight" or "Inventory"

        self.all_columns = list(self.df.columns)

        # Base visible columns (only those that exist)
        self.base_visible_columns = [c for c in VisibleColumns if c in self.all_columns]
        if not self.base_visible_columns:
            self.base_visible_columns = self.all_columns.copy()

        # Actual displayed table columns depend on mode
        self.visible_columns = self._get_visible_columns_for_mode()

        self.menubar = tk.Menu(self)
        self.config(menu=self.menubar)

        self.CreateToolMenu()
        self.CreateSettingsMenu()
        self.CreateToolbar()
        self.BuildFilters()

        self.BuildTree()
        self.ShowTree(self.df)

    # ---------- Mode helpers (NEW) ----------
    def _get_visible_columns_for_mode(self):
        cols = self.base_visible_columns.copy() if self.base_visible_columns else self.all_columns.copy()

        # Inventory mode: remove Property Blighted? from table
        if self.mode.get() == "Inventory" and "Property Blighted?" in cols:
            cols.remove("Property Blighted?")
        return cols

    def _display_cols(self):
        # always use the current table columns
        return self.visible_columns

    def _sync_mode_ui(self):
        # Inventory mode: hide Blighted filter + force it off
        if hasattr(self, "BlightedCheck"):
            if self.mode.get() == "Inventory":
                self.BlightedFilter.set(False)
                self.BlightedCheck.grid_remove()
            else:
                self.BlightedCheck.grid()

    def ToggleMode(self):
        self.mode.set("Inventory" if self.mode.get() == "Blight" else "Blight")

        # update columns + UI
        self.visible_columns = self._get_visible_columns_for_mode()
        self._sync_mode_ui()

        # rebuild table so headings/columns update
        self.BuildTree()
        self.ShowTree(self.df)

        messagebox.showinfo("Mode Changed", f"Current mode: {self.mode.get()}")
    # --------------------------------------

    # --- Menu ---
    def CreateToolMenu(self):
        menubar = tk.Menu(self)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="New File", command=self.NewCSV)
        filemenu.add_command(label="Save As", command=self.SaveAsCSV)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.destroy)
        self.menubar.add_cascade(label="File", menu=filemenu)

    def CreateSettingsMenu(self):
        settingsbar = tk.Menu(self)
        settingsmenu = tk.Menu(settingsbar, tearoff=0)
        settingsmenu.add_command(label="Change Mode", command=self.ToggleMode)  # NEW
        settingsmenu.add_command(label="Themes")
        settingsmenu.add_command(label="Font Size")
        self.menubar.add_cascade(label="Settings", menu=settingsmenu)
        settingsmenu.add_command(label="Show/Hide Columns", command=self.ShowColumnSelector)

    # --- Toolbar ---
    def CreateToolbar(self):
        bar = ttk.Frame(self, padding=(8, 4))
        bar.pack(side="top", fill="x")

        self.SearchInput = tk.StringVar()

        entry = ttk.Entry(bar, textvariable=self.SearchInput, width=30)
        entry.pack(side="right", padx=4)
        entry.bind("<Return>", self.ApplyFilters)

        ttk.Button(bar, text="Search", command=self.ApplyFilters).pack(side="right", padx=4)

        ttk.Button(bar, text="New", command=self.AddProperty).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete", command=self.DelProperty).pack(side="left", padx=4)
        ttk.Button(bar, text="Show Favorites", command=self.ShowFavs).pack(side="left", padx=4)

        ttk.Button(bar, text="Toggle Mode", command=self.ToggleMode).pack(side="left", padx=4)  # NEW

    # Filters
    def BuildFilters(self):
        frm = ttk.LabelFrame(self, text="Filters & Sort", padding=8)
        frm.pack(side="top", fill="x", padx=8, pady=(0, 8))

        self.BlightedFilter = tk.BooleanVar(value=False)
        self.VacancyFilter = tk.BooleanVar(value=False)

        # store widget so we can hide it in Inventory mode
        self.BlightedCheck = ttk.Checkbutton(frm, text="Blighted", variable=self.BlightedFilter)
        self.BlightedCheck.grid(row=0, column=0, sticky="w")

        ttk.Checkbutton(frm, text="Vacant", variable=self.VacancyFilter).grid(row=0, column=1, sticky="w")

        self.use_var = tk.StringVar(value="Both")
        self.use = ttk.Combobox(frm, textvariable=self.use_var, values=["Both", "Commercial", "Residential"], state="readonly")
        self.use.grid(row=0, column=2, padx=6)

        city_list = ["All"] + (sorted(self.df["City:"].dropna().unique().tolist()) if "City:" in self.df.columns else [])
        self.city_var = tk.StringVar(value="All")
        self.City = ttk.Combobox(frm, textvariable=self.city_var, values=city_list, state="readonly")
        self.City.grid(row=0, column=3, padx=6)

        muni_list = ["All"] + (sorted(self.df["Municipality:"].dropna().unique().tolist()) if "Municipality:" in self.df.columns else [])
        self.muni_var = tk.StringVar(value="All")
        self.Municipality = ttk.Combobox(frm, textvariable=self.muni_var, values=muni_list, state="readonly")
        self.Municipality.grid(row=0, column=4, padx=6)

        ttk.Label(frm, text="From Date").grid(row=1, column=0, sticky="w")
        self.from_date = tk.StringVar()
        ttk.Entry(frm, textvariable=self.from_date, width=12).grid(row=1, column=1)

        ttk.Label(frm, text="To Date").grid(row=1, column=2, sticky="w")
        self.to_date = tk.StringVar()
        ttk.Entry(frm, textvariable=self.to_date, width=12).grid(row=1, column=3)

        ttk.Label(frm, text="ZipCode:").grid(row=1, column=4, sticky="w")
        zip_list = ["All"] + (sorted(self.df["Zipcode:"].dropna().astype(str).unique().tolist()) if "Zipcode:" in self.df.columns else [])
        self.zip_var = tk.StringVar(value="All")
        self.zip = ttk.Combobox(frm, textvariable=self.zip_var, values=zip_list, state="readonly")
        self.zip.grid(row=1, column=5, padx=6)

        self.modified_var = tk.StringVar(value="All")
        ttk.Label(frm, text="Last Modified").grid(row=2, column=0)
        ttk.Combobox(
            frm,
            textvariable=self.modified_var,
            values=["All", "Last 24 Hours", "Last 7 Days", "Last 30 Days"],
            state="readonly",
        ).grid(row=2, column=1)

        ttk.Button(frm, text="Apply", command=self.ApplyFilters).grid(row=0, column=6, padx=6)
        ttk.Button(frm, text="Reset", command=self.ResetFilters).grid(row=0, column=7, padx=6)

        self.map_regen = tk.BooleanVar(value=False)
        ttk.Button(frm, text="Full Map", command=self.CreateFullMap).grid(row=0, column=8, sticky="w")
        ttk.Checkbutton(frm, text="Regen Map", variable=self.map_regen).grid(row=0, column=9, sticky="w")

        # apply mode UI on startup
        self._sync_mode_ui()

    # Full map of all properties
    def CreateFullMap(self):
        MAP_HTML = CACHE_DIR / "full_Map.html"

        for _, row in self.df.iterrows():
            address = f"{row.get('Property Address Number:','')} {row.get('Property Address Street Name:','')}, {row.get('City:','')} PA, {row.get('Zipcode:','')}, USA"
            map_id = f"{row.get('Property Address Number:','')} {row.get('Property Address Street Name:','')}, {row.get('City:','')}"

            status_flags = []
            if validate(row.get("Vacant Property:", "")):
                status_flags.append("Vacant")
            if validate(row.get("Property Blighted?", "")):
                status_flags.append("Blighted")
            if validate(row.get("Residential", "")):
                status_flags.append("Residential")
            if validate(row.get("Commercial", "")):
                status_flags.append("Commercial")
            status = " ".join(status_flags) if status_flags else None

            coords = geocode_address(address, label=map_id, status=status, cache=cache)
            if coords:
                cache[map_id] = coords
            else:
                address = f"{row.get('Property Address Street Name:','')}, {row.get('City:','')} PA, {row.get('Zipcode:','')}, USA"
                map_id = f"Property_on_{row.get('Property Address Street Name:','')}, {row.get('City:','')}"
                coords = geocode_address(address, label=map_id, status=status, cache=cache)
                if coords:
                    cache[map_id] = coords
                else:
                    address = f"{row.get('City:','')} PA, {row.get('Zipcode:','')}, USA"
                    map_id = f"Property_in_{row.get('City:','')}"
                    coords = geocode_address(address, label=map_id, status=status, cache=cache)
                    if coords:
                        cache[map_id] = coords

        _save_geocode_cache(cache)
        png_path = generate_full_map(cache)

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

    def NewCSV(self):
        user_path = choose_csv_path()
        if user_path:
            src_csv = user_path
        else:
            src_csv = CSV_PATH

        new_csv = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            title="New CSV",
        )
        if not new_csv:
            return

        with open(src_csv, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            headers = next(reader)

        with open(new_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)

    def SaveAsCSV(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            title="Save as CSV",
        )
        if not file_path:
            return

        try:
            visible_idxs = [int(self.tree.item(iid, "tags")[0]) for iid in self.tree.get_children("")]
            self.df.loc[visible_idxs].to_csv(file_path, index=False)
            messagebox.showinfo("Saved", "Treeview exported successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save file:\n{e}")

    # --- TreeView ---
    def BuildTree(self):
        if hasattr(self, "tree_container"):
            self.tree_container.destroy()

        self.tree_container = ttk.Frame(self)
        self.tree_container.pack(side="top", fill="both", expand=True, padx=8, pady=8)

        self.tree = ttk.Treeview(
            self.tree_container,
            columns=self._display_cols(),
            show="headings",
        )

        vsb = ttk.Scrollbar(self.tree_container, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(self.tree_container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self.tree_container.grid_rowconfigure(0, weight=1)
        self.tree_container.grid_columnconfigure(0, weight=1)

        self.sort = {}

        def SortCol(col):
            self.sort[col] = not self.sort.get(col, False)
            items = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]

            def tryNum(x):
                try:
                    return float(x)
                except Exception:
                    return x

            items.sort(key=lambda t: tryNum(t[0]), reverse=self.sort[col])
            for index, (_, k) in enumerate(items):
                self.tree.move(k, "", index)

        for col in self._display_cols():
            self.tree.heading(col, text=col, command=lambda c=col: SortCol(c))
            self.tree.column(col, width=150, anchor="w", minwidth=110)

        self.tree.bind("<<TreeviewSelect>>", self.Selected)

        self._row_ids = {}
        for idx, row in self.df.iterrows():
            vals = [row.get(col, "") for col in self._display_cols()]
            iid = self.tree.insert("", "end", values=vals, tags=(str(idx),))
            self._row_ids[idx] = iid

    def ShowTree(self, data):
        visible_idx = set(data.index)
        for idx, iid in self._row_ids.items():
            if idx in visible_idx:
                self.tree.reattach(iid, "", "end")
            else:
                self.tree.detach(iid)

    # Filters processing
    def ApplyFilters(self, event=None):
        df2 = self.df.copy()

        # Blighted Filter (disabled in Inventory mode, and field hidden in Inventory mode)
        if self.mode.get() != "Inventory":
            if self.BlightedFilter.get() and "Property Blighted?" in df2.columns:
                df2 = df2[df2["Property Blighted?"]]

        if self.VacancyFilter.get() and "Vacant Property:" in df2.columns:
            df2 = df2[df2["Vacant Property:"]]

        use = self.use_var.get()
        if use == "Commercial" and "Commercial" in df2.columns:
            df2 = df2[df2["Commercial"]]
        elif use == "Residential" and "Residential" in df2.columns:
            df2 = df2[df2["Residential"]]

        city = self.city_var.get()
        if city != "All" and "City:" in df2.columns:
            df2 = df2[df2["City:"] == city]

        muni = self.muni_var.get()
        if muni != "All" and "Municipality:" in df2.columns:
            df2 = df2[df2["Municipality:"] == muni]

        if (self.from_date.get() or self.to_date.get()) and "Start time" in df2.columns:
            df2["Start time"] = pd.to_datetime(df2["Start time"], errors="coerce")

        if self.from_date.get() and "Start time" in df2.columns:
            start = pd.to_datetime(self.from_date.get(), errors="coerce")
            df2 = df2[df2["Start time"] >= start]

        if self.to_date.get() and "Start time" in df2.columns:
            end = pd.to_datetime(self.to_date.get(), errors="coerce")
            df2 = df2[df2["Start time"] <= end]

        zip_code = self.zip_var.get()
        if zip_code != "All" and "Zipcode:" in df2.columns:
            df2 = df2[df2["Zipcode:"].astype(str) == zip_code]

        modified = self.modified_var.get()
        if modified != "All" and "Completion time" in df2.columns:
            df2["Completion time"] = pd.to_datetime(df2["Completion time"], errors="coerce")
            now = datetime.now()
            if modified == "Last 24 Hours":
                cutoff = now - timedelta(days=1)
            elif modified == "Last 7 Days":
                cutoff = now - timedelta(days=7)
            else:
                cutoff = now - timedelta(days=30)
            df2 = df2[df2["Completion time"] >= cutoff]

        search = self.SearchInput.get().lower().strip()
        if search:
            df2 = df2[df2.apply(lambda row: search in " ".join(map(str, row.values)).lower(), axis=1)]

        self.ShowTree(df2)

    def ResetFilters(self):
        self.BlightedFilter.set(False)
        self.VacancyFilter.set(False)

        self.use_var.set("Both")
        self.city_var.set("All")
        self.muni_var.set("All")

        self.SearchInput.set("")

        self.from_date.set("")
        self.to_date.set("")

        # set dropdowns back to "All" (not empty string)
        self.zip_var.set("All")
        self.modified_var.set("All")

        self.ShowTree(self.df)

    # Selected row details
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

        win = tk.Toplevel(self)
        win.configure(bg="#f5f6f7")
        win.title(f"Property Address: {row.get('Property Address Number:','')} {row.get('Property Address Street Name:','')}")
        win.geometry("800x600")
        win.minsize(400, 300)
        win.columnconfigure(0, weight=1)
        win.columnconfigure(1, weight=1)
        win.rowconfigure(1, weight=1)

        # --- Top image frame ---
        ImageFrame = ttk.Frame(win, height=max(120, win.winfo_height() // 3), relief="solid")
        ImageFrame.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        ImageFrame.grid_propagate(False)

        ImageLabel = tk.Label(ImageFrame, bg="lightgray", text="Loading image...", anchor="center", justify="center")
        ImageLabel.pack(expand=True, fill="both")

        OriginalImage = None
        img_path = row.get("ImagePath", None)

        if img_path and isinstance(img_path, str) and img_path.strip():
            img_path = img_path.strip()
            try:
                if img_path.startswith("http"):
                    OriginalImage = FindImageFromURL(img_path)
                else:
                    if not os.path.exists(img_path):
                        raise FileNotFoundError(f"Local file not found: {img_path}")
                    OriginalImage = Image.open(img_path)
                    OriginalImage.load()

                try:
                    OriginalImage = ImageOps.exif_transpose(OriginalImage)
                except Exception:
                    pass

                ImageLabel.config(text="")
            except Exception as e:
                OriginalImage = None
                ImageLabel.config(text=f"Image not available\n{e}")
                print("ERROR loading image:", e)
        else:
            ImageLabel.config(text="No Image Available")

        # --- Buttons row (Edit / Note / Favorite) ---
        btn_row = ttk.Frame(win, padding=(6, 0))
        btn_row.grid(row=3, column=0, columnspan=2, sticky="ew", padx=8, pady=(6, 8))
        btn_row.columnconfigure(0, weight=1)
        btn_row.columnconfigure(1, weight=1)
        btn_row.columnconfigure(2, weight=1)

        EditBtn = ttk.Button(btn_row, text="Edit Property Values", command=lambda i=idx: self.EditProperty(i, win))
        NoteBtn = ttk.Button(btn_row, text="Add Note", command=lambda i=idx: self.AddNote(i, win))
        EditBtn.grid(row=0, column=0, sticky="ew", padx=4)
        NoteBtn.grid(row=0, column=1, sticky="ew", padx=4)

        # Favorite button only if column exists
        if "Favorited" in self.df.columns:
            try:
                cur_fav = int(self.df.at[idx, "Favorited"])
            except Exception:
                cur_fav = 0
            fav_text = "Unfavorite" if cur_fav == 1 else "Favorite"
            FavBtn = ttk.Button(btn_row, text=fav_text)
            FavBtn.config(command=lambda i=idx, b=FavBtn: self.ToggleFavorite(i, b))
            FavBtn.grid(row=0, column=2, sticky="ew", padx=4)

        # --- Resize image helpers ---
        def MaxSize():
            WinH = max(300, win.winfo_height())
            MaxH = max(120, WinH // 3)
            WinW = max(300, win.winfo_width())
            MaxW = WinW - 40
            return MaxW, MaxH

        def ResizeImage(event=None):
            nonlocal OriginalImage
            if not OriginalImage:
                ImageLabel.config(image="", text=ImageLabel.cget("text"))
                return

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

            if FrameW <= 1 or FrameH <= 1:
                win.after(80, ResizeImage)
                return

            MaxW, MaxH = MaxSize()
            ImageFrame.configure(height=MaxH)
            FrameW = min(FrameW, MaxW)
            FrameH = min(FrameH, MaxH)

            try:
                iw, ih = OriginalImage.size
            except Exception:
                return
            if iw == 0 or ih == 0:
                return

            ImageRatio = iw / ih if ih != 0 else 1
            frame_ratio = FrameW / FrameH if FrameH != 0 else 1
            if frame_ratio > ImageRatio:
                TargetH = FrameH
                TargetW = int(TargetH * ImageRatio)
            else:
                TargetW = FrameW
                TargetH = int(TargetW / ImageRatio)

            allow_upscale = False
            if not allow_upscale:
                TargetW = min(TargetW, iw)
                TargetH = min(TargetH, ih)

            TargetW = max(1, int(TargetW))
            TargetH = max(1, int(TargetH))

            cur = getattr(ImageLabel, "_last_size", (0, 0))
            if (TargetW, TargetH) == cur:
                return
            ImageLabel._last_size = (TargetW, TargetH)

            try:
                resized = OriginalImage.resize((TargetW, TargetH), Image.LANCZOS)
            except Exception:
                try:
                    resized = OriginalImage.copy()
                    resized.thumbnail((TargetW, TargetH), Image.LANCZOS)
                except Exception:
                    return

            photo = ImageTk.PhotoImage(resized)
            ImageLabel.config(image=photo, text="")
            ImageLabel.image = photo

        ImageFrame.bind("<Configure>", ResizeImage)
        win.bind("<Configure>", lambda e: ResizeImage(e))
        win.after(150, ResizeImage)

        # --- InfoFrame (left) and RightFrame (map) ---
        InfoFrame = ttk.Frame(win, relief="solid", padding=5)
        InfoFrame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        InfoFrame.grid_rowconfigure(0, weight=1)
        InfoFrame.grid_columnconfigure(0, weight=1)

        canvas = tk.Canvas(InfoFrame)
        vscroll = ttk.Scrollbar(InfoFrame, orient="vertical", command=canvas.yview)
        hscroll = ttk.Scrollbar(InfoFrame, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=vscroll.set, xscrollcommand=hscroll.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        vscroll.grid(row=0, column=1, sticky="ns")
        hscroll.grid(row=1, column=0, sticky="ew")

        ScrollFrame = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=ScrollFrame, anchor="nw")

        def ConfigureFrame(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        ScrollFrame.bind("<Configure>", ConfigureFrame)

        # Inventory mode: hide ALL survey questions/details
        if self.mode.get() == "Inventory":
            summary_fields = [
                ("Parcel ID", "Parcel ID, if known:"),
                ("Address #", "Property Address Number:"),
                ("Street", "Property Address Street Name:"),
                ("City", "City:"),
                ("Zip", "Zipcode:"),
                ("Municipality", "Municipality:"),
            ]
            r = 0
            for label, col in summary_fields:
                if col in self.df.columns:
                    val = row.get(col, "")
                    ttk.Label(ScrollFrame, text=f"{label}:", font=("Arial", 10, "bold")).grid(
                        row=r, column=0, sticky="e", padx=6, pady=4
                    )
                    ttk.Label(ScrollFrame, text=val, wraplength=300, anchor="w").grid(
                        row=r, column=1, sticky="w", padx=6, pady=4
                    )
                    r += 1
            ScrollFrame.grid_columnconfigure(1, weight=1)
        else:
            hidden_columns = [col for col in self.all_columns if col not in self._display_cols()]
            for i, col in enumerate(hidden_columns):
                val = row.get(col, "")
                ttk.Label(ScrollFrame, text=f"{col}:", font=("Arial", 10, "bold")).grid(
                    row=i, column=0, sticky="e", padx=6, pady=4
                )
                ttk.Label(ScrollFrame, text=val, wraplength=300, anchor="w").grid(
                    row=i, column=1, sticky="w", padx=6, pady=4
                )
            ScrollFrame.grid_columnconfigure(1, weight=1)

        RightFrame = ttk.Frame(win, relief="solid", padding=5)
        RightFrame.grid(row=1, column=1, rowspan=2, sticky="nsew", padx=5, pady=5)

        tk.Label(RightFrame, text="Map Viewer", font=("Arial", 12, "bold")).pack(pady=5)

        map_id = f"{row.get('Property Address Number:','')} {row.get('Property Address Street Name:','')}, {row.get('City:','')}".strip()
        map_address = f"{row.get('Property Address Number:','')} {row.get('Property Address Street Name:','')}, {row.get('City:','')} PA, {row.get('Zipcode:','')}, USA".strip()

        status_flags = []
        if validate(row.get("Vacant Property:", "")):
            status_flags.append("Vacant")
        if validate(row.get("Property Blighted?", "")):
            status_flags.append("Blighted")
        if validate(row.get("Residential", "")):
            status_flags.append("Residential")
        if validate(row.get("Commercial", "")):
            status_flags.append("Commercial")
        status = " ".join(status_flags) if status_flags else None

        test = geocode_address(map_address, label=map_id, status=status, cache=cache)
        if not test:
            map_address = f"{row.get('Property Address Street Name:','')}, {row.get('City:','')} PA, {row.get('Zipcode:','')}, USA".strip()
            map_id = f"Property_on_{row.get('Property Address Street Name:','')}, {row.get('City:','')}".strip()
            test = geocode_address(map_address, label=map_id, status=status, cache=cache)
            if not test:
                map_address = f"{row.get('City:','')} PA, {row.get('Zipcode:','')}, USA".strip()
                map_id = f"Property_in_{row.get('City:','')}".strip()

        out = create_map(map_address, ID=str(map_id), cache=cache, status=status, force_refresh=self.map_regen.get())
        MAP_HTML = out.with_suffix(".html")
        MAP_PNG = out.with_suffix(".png")

        img = Image.open(MAP_PNG)
        tk_img = ImageTk.PhotoImage(img)
        label = tk.Label(RightFrame, image=tk_img)
        label.image = tk_img
        label.pack(fill="both", expand=True)

        def open_in_browser(event=None):
            webbrowser.open(MAP_HTML.as_uri())

        label.bind("<Button-1>", open_in_browser)

        # NoteFrame for notes
        NoteFrame = ttk.Frame(win, relief="solid", padding=5)
        NoteFrame.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)

        tk.Label(
            NoteFrame,
            text=f"Notes: {row.get('Notes','')}",
            font=("Arial", 12, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=4, pady=4)

        canvas2 = tk.Canvas(NoteFrame)
        vscroll2 = ttk.Scrollbar(NoteFrame, orient="vertical", command=canvas2.yview)
        hscroll2 = ttk.Scrollbar(NoteFrame, orient="horizontal", command=canvas2.xview)
        canvas2.configure(yscrollcommand=vscroll2.set, xscrollcommand=hscroll2.set)

        canvas2.grid(row=1, column=0, sticky="nsew")
        vscroll2.grid(row=1, column=1, sticky="ns")
        hscroll2.grid(row=2, column=0, sticky="ew")

        NoteFrame.rowconfigure(1, weight=1)
        NoteFrame.columnconfigure(0, weight=1)

        AnotherScrollFrame = ttk.Frame(canvas2)
        canvas2.create_window((0, 0), window=AnotherScrollFrame, anchor="nw")

        def configure_frame2(event):
            canvas2.configure(scrollregion=canvas2.bbox("all"))

        AnotherScrollFrame.bind("<Configure>", configure_frame2)

    def ToggleFavorite(self, idx, fav_btn):
        if "Favorited" not in self.df.columns:
            return
        current = int(self.df.at[idx, "Favorited"]) if str(self.df.at[idx, "Favorited"]).strip() != "" else 0
        new_val = 0 if current == 1 else 1
        self.df.at[idx, "Favorited"] = new_val
        fav_btn.config(text="Unfavorite" if new_val == 1 else "Favorite")

    def ShowFavs(self):
        if "Favorited" not in self.df.columns:
            return
        data = self.df[self.df["Favorited"] == 1]
        self.ShowTree(data)

    def ShowColumnSelector(self):
        top = tk.Toplevel(self)
        top.title("Show / Hide Columns")
        top.geometry("300x400")
        top.grab_set()

        checkbox_vars = {}

        canvas = tk.Canvas(top)
        scrollbar = ttk.Scrollbar(top, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for col in self.all_columns:
            var = tk.BooleanVar(value=(col in self.visible_columns))
            checkbox = ttk.Checkbutton(scroll_frame, text=col, variable=var)
            checkbox.pack(anchor="w", padx=10, pady=2)
            checkbox_vars[col] = var

        def apply_changes():
            self.visible_columns = [col for col, var in checkbox_vars.items() if var.get()]

            # enforce Inventory rule: hide Property Blighted?
            if self.mode.get() == "Inventory" and "Property Blighted?" in self.visible_columns:
                self.visible_columns.remove("Property Blighted?")

            self.BuildTree()
            self.ShowTree(self.df)
            top.destroy()

        ttk.Button(top, text="Apply", command=apply_changes).pack(pady=10)

    def DelProperty(self):
        sels = self.tree.selection()
        if not sels:
            messagebox.showwarning("Delete", "No row selected to delete.")
            return

        prompt = "Delete the selected property?" if len(sels) == 1 else f"Delete the {len(sels)} selected properties?"
        if not messagebox.askyesno("Confirm delete", prompt):
            return

        idxs = []
        for iid in sels:
            tags = self.tree.item(iid, "tags") or ()
            if not tags:
                continue
            tag = tags[0]
            try:
                idx = int(tag)
            except Exception:
                idx = tag
            idxs.append(idx)

        if not idxs:
            messagebox.showwarning("Delete", "Could not determine rows to delete.")
            return

        try:
            self.df = self.df.drop(index=idxs, errors="ignore")
            self.df = self.df.reset_index(drop=True)

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

            # rebuild tree to keep indices aligned
            self.BuildTree()
            self.ShowTree(self.df)

            messagebox.showinfo("Deleted", "Selected property(ies) deleted.")
        except Exception as e:
            messagebox.showerror("Delete error", f"Failed to delete row(s): {e}")

    def AddProperty(self):
        new_values = [c for c in self.df.columns]

        new_win = tk.Toplevel(self)
        new_win.title("New Property")
        new_win.geometry("620x520")
        new_win.minsize(420, 300)

        addFrame = ttk.Frame(new_win, padding=8)
        addFrame.pack(fill="both", expand=True)

        newCanvas = tk.Canvas(addFrame)
        newVscroll = ttk.Scrollbar(addFrame, orient="vertical", command=newCanvas.yview)
        newCanvas.configure(yscrollcommand=newVscroll.set)

        newCanvas.pack(side="left", fill="both", expand=True)
        newVscroll.pack(side="right", fill="y")

        addInner = ttk.Frame(newCanvas)
        newCanvas.create_window((0, 0), window=addInner, anchor="nw")

        def _configure(e):
            newCanvas.configure(scrollregion=newCanvas.bbox("all"))

        addInner.bind("<Configure>", _configure)

        controls = {}

        for i, col in enumerate(new_values):
            lbl = ttk.Label(addInner, text=f"{col}:", font=("Arial", 10, "bold"))
            lbl.grid(row=i, column=0, sticky="e", padx=6, pady=6)

            entvar = tk.StringVar(value="")
            ent = ttk.Entry(addInner, textvariable=entvar, width=50)
            ent.grid(row=i, column=1, sticky="we", padx=6, pady=6)
            controls[col] = ("str", entvar)

        addInner.grid_columnconfigure(1, weight=1)

        btnfrm = ttk.Frame(new_win, padding=6)
        btnfrm.pack(fill="x", side="bottom")

        def OnSave():
            new_row = {}
            for col, (_k, var) in controls.items():
                v = var.get()
                new_row[col] = v if v is not None else ""

            now_iso = datetime.now().isoformat()
            if "Created" in new_row:
                new_row["Created"] = now_iso
            if "Modified" in new_row:
                new_row["Modified"] = now_iso

            if "ID" in new_row:
                try:
                    existing_ids = pd.to_numeric(self.df["ID"], errors="coerce")
                    new_row["ID"] = (int(existing_ids.max()) + 1) if existing_ids.notna().any() else (len(self.df) + 1)
                except Exception:
                    new_row["ID"] = len(self.df) + 1

            for c in self.df.columns:
                if c not in new_row:
                    new_row[c] = ""

            try:
                appended = pd.DataFrame([new_row])
                appended = appended[self.df.columns]
                self.df = pd.concat([self.df, appended], ignore_index=True)
            except Exception as e:
                messagebox.showerror("Append error", f"Failed to append new row: {e}")
                return

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

            # refresh table
            self.BuildTree()
            self.ShowTree(self.df)

            messagebox.showinfo("Saved", "New property added and saved.")
            new_win.destroy()

        def OnCancel():
            new_win.destroy()

        ttk.Button(btnfrm, text="Save", command=OnSave).pack(side="right", padx=6)
        ttk.Button(btnfrm, text="Cancel", command=OnCancel).pack(side="right", padx=6)

    def EditProperty(self, idx, parent_win=None):
        try:
            row = self.df.loc[idx].copy()
        except Exception as e:
            messagebox.showerror("Edit error", f"Unable to find row {idx}: {e}")
            return

        skip_cols = {"ImagePath", "ID", "Created", "Modified", "Notes"}
        editable_cols = [c for c in self.df.columns if c not in skip_cols]

        edit_win = tk.Toplevel(self)
        edit_win.title(f"Edit Property Address: {row.get('StreetNum','')} {row.get('Address','')}")
        edit_win.geometry("620x520")
        edit_win.minsize(420, 300)

        frame = ttk.Frame(edit_win, padding=8)
        frame.pack(fill="both", expand=True)

        canvas = tk.Canvas(frame)
        vscroll = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vscroll.set)

        canvas.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

        inner = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")

        def _configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))

        inner.bind("<Configure>", _configure)

        controls = {}

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

        for i, col in enumerate(editable_cols):
            val = row.get(col, "")
            lbl = ttk.Label(inner, text=f"{col}:", font=("Arial", 10, "bold"))
            lbl.grid(row=i, column=0, sticky="e", padx=6, pady=6)

            entvar = tk.StringVar(value="" if pd.isna(val) else str(val))
            ent = ttk.Entry(inner, textvariable=entvar, width=50)
            ent.grid(row=i, column=1, sticky="we", padx=6, pady=6)
            controls[col] = ("str", entvar)

        inner.grid_columnconfigure(1, weight=1)

        btnfrm = ttk.Frame(edit_win, padding=6)
        btnfrm.pack(fill="x", side="bottom")

        def OnSave():
            updates = {}
            for col, (_kind, ctl) in controls.items():
                try:
                    s = ctl.get().strip()
                    orig_kind = _infer_type(row.get(col, ""))

                    if s == "":
                        newv = ""
                    elif orig_kind == "int":
                        try:
                            newv = int(s)
                        except Exception:
                            newv = s
                    elif orig_kind == "float":
                        try:
                            newv = float(s)
                        except Exception:
                            newv = s
                    else:
                        newv = s

                    updates[col] = newv
                except Exception as e:
                    messagebox.showerror("Conversion error", f"Error parsing column {col}: {e}")
                    return

            try:
                for c, v in updates.items():
                    self.df.at[idx, c] = v

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

                # refresh table (columns may differ by mode)
                self.BuildTree()
                self.ShowTree(self.df)

                messagebox.showinfo("Saved", "Property values updated and saved.")
                edit_win.destroy()
            except Exception as e:
                messagebox.showerror("Update error", f"Failed to update property: {e}")

        def OnCancel():
            edit_win.destroy()

        ttk.Button(btnfrm, text="Save", command=OnSave).pack(side="right", padx=6)
        ttk.Button(btnfrm, text="Cancel", command=OnCancel).pack(side="right", padx=6)

    def AddNote(self, idx, parent_win=None):
        try:
            _ = self.df.loc[idx]
        except Exception as e:
            messagebox.showerror("Note error", f"Unable to find row {idx}: {e}")
            return

        note_win = tk.Toplevel(self)
        note_win.title("Add Note")
        note_win.geometry("420x180")
        try:
            note_win.transient(parent_win or self)
            note_win.grab_set()
        except Exception:
            pass

        ttk.Label(note_win, text="Add note:").pack(anchor="w", padx=8, pady=(8, 4))
        txt = tk.Text(note_win, height=6, width=50)
        txt.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        def OnAdd():
            s = txt.get("1.0", "end").strip()
            if not s:
                messagebox.showwarning("Empty", "Note is empty.")
                return

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            username = getpass.getuser()
            entry = f"[{username}] [{timestamp}] {s}"

            if "Notes" not in self.df.columns:
                self.df["Notes"] = ""

            CurrentRaw = self.df.at[idx, "Notes"] if "Notes" in self.df.columns else None
            current = "" if pd.isna(CurrentRaw) or CurrentRaw is None else str(CurrentRaw)

            NewInputs = f"{entry}\n\n{current}" if current else entry
            self.df.at[idx, "Notes"] = NewInputs

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

            # refresh table
            self.BuildTree()
            self.ShowTree(self.df)

            messagebox.showinfo("Note added", "Note appended and saved.")
            note_win.destroy()

        def OnCancel():
            note_win.destroy()

        btnframe = ttk.Frame(note_win)
        btnframe.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(btnframe, text="Add", command=OnAdd).pack(side="right", padx=6)
        ttk.Button(btnframe, text="Cancel", command=OnCancel).pack(side="right", padx=6)


if __name__ == "__main__":
    app = App()
    app.mainloop()
