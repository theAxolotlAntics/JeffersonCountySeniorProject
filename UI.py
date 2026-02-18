# Name: Gannon Kearney, Brunner Good, Isaac Wagner, Alexis Valencia
# Created: 9/3/25
# Last Updated: 2/3/26
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
from datetime import datetime

#to create new csv's
import csv

#added imporrts for image and mapping
from pathlib import Path
import webbrowser
import getpass
from MapModule import create_map, geocode_address, generate_full_map, _save_geocode_cache, _load_geocode_cache, validate


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
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# Define global paths
BASE_DIR = Path(__file__).parent
CACHE_DIR = BASE_DIR / "resources" / "cachedMaps"
# Define the cache once to speed up mapping
cache = _load_geocode_cache()

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

df = pd.read_csv(CSV_PATH)
Title = "Blight Inventory"

# columns wanted on the main page
#StreeNum and Address are seperated for ease of filtering
VisibleColumns = ["ID", "Start time", "Completion time", "Email", "First", "Last", "Date of Property Review:",
                      "Parcel ID, if known:", "Property Address Number:", "Property Address Street Name:",
                      "City:", "Zipcode:", "Municipality:", "Property Blighted?", "Commercial", "Residential", "Vacant Property:", "Submitter's Name:",
                      "Submitter's Email or Phone Number (this information will be used to collect any critical information or clear up any discrepancies)"]
                      

# columns displayed on selected property page (skip last column if image link etc)
hidden_columns = [col for col in df.columns[:-1] if col not in VisibleColumns]

# Citys and Municipalitys in Jefferson County
Citys = ["Big Run", "Brockway", "Brookville", "Corsica", "Falls Creek", "Punxsutawney",
            "Reynoldsville", "Summerville", "Sykesville", "Timblin", "Worthville"]
Municipalitys = ["Barnett", "Beaver", "Bell", "Clover", "Eldred", "Gaskill", "Heath", "Henderson",
             "Knox", "McCalmont", "Oliver", "Perry", "Pine Creek", "Polk", "Porter", "Ringgold",
             "Rose", "Snyder", "Union", "Warsaw", "Washington", "Winslow", "Young"]

Uses = ["Commercial","Residential"]

# ---- App ----
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(Title)
        self.geometry("1100x600")
        self.minsize(900, 520) #min size of the main window
        self.df = df.copy()
        self.CreateMenu() #call constructors
        self.CreateToolbar()
        self.BuildFilters()
        self.BuildTree()
        self.ShowTree(self.df)

    # --- Menu ---
    def CreateMenu(self): #create the menubar.  This appears in the top left with an exit option
        menubar = tk.Menu(self)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Save As", command=self.SaveAsCSV)
        filemenu.add_command(label="Exit", command=self.destroy) #exit option closes program
        menubar.add_cascade(label="File", menu=filemenu)
        self.config(menu=menubar)

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

    # --- Filters ---
    #Different filters based on customer needs
    def BuildFilters(self):
        frm = ttk.LabelFrame(self, text="Filters & Sort", padding=8)
        frm.pack(side="top", fill="x", padx=8, pady=(0, 8))
        self.BlightedFilter = tk.BooleanVar(value=False) #blighted property is false by default
        self.VacancyFilter = tk.BooleanVar(value=False) #vacancy (true or false) is false by default

        ttk.Checkbutton(frm, text="Blighted", variable=self.BlightedFilter).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(frm, text="Vacancy", variable=self.VacancyFilter).grid(row=0, column=1, sticky="w")
        self.use = ttk.Combobox(frm,values=["Both"] + Uses, state="readonly")
        self.use.set("Both")
        self.use.grid(row=0,column=2, sticky="w", padx=6)

        #using all of the Citys, display them in a drop down list, with all appearing first
        self.City = ttk.Combobox(frm, values=["City"] + Citys, state="readonly")
        self.City.set("City") #all is default
        self.City.grid(row=0, column=3, sticky="w", padx=6)

        #using all of the Municipalitys, display in a dropdown with all defaulted
        self.Municipality = ttk.Combobox(frm, values=["Municipality"] + Municipalitys, state="readonly")
        self.Municipality.set("Municipality")
        self.Municipality.grid(row=0, column=4, sticky="w", padx=6)

        #apply and reset filters call respective commands
        self.map_regen = tk.BooleanVar(value=False)
        ttk.Button(frm, text="Apply", command=self.ApplyFilters).grid(row=0, column=5, padx=6)
        ttk.Button(frm, text="Reset", command=self.ResetFilters).grid(row=0, column=6, padx=6)
        ttk.Button(frm, text="Full Map", command=self.CreateFullMap).grid(row=0, column=7, sticky="w")
        ttk.Checkbutton(frm, text="Regen Map", variable=self.map_regen).grid(row=0, column=8, sticky="w")


    #This fuction will create a map with all the adresses in the dataframe
    def CreateFullMap(self):
        MAP_HTML = CACHE_DIR / "full_Map.html"
        

        for index, row in self.df.iterrows():
            address = f"{row.get('Property Address Number:','')} {row.get('Property Address Street Name:','')}, {row.get('City:','')} PA, {row.get('Zipcode:','')}, USA"
            map_id = f"{row.get('Property Address Number:','')} {row.get('Property Address Street Name:','')}, {row.get('City:','')}"
             # assign the boolean values to possible statuses
            status_flags = [ ("blight", validate(row.get("Property Blighted?", ""))), ("com", validate(row.get("Commercial", ""))), ("res", validate(row.get("Residential", ""))),]
            # assign the status to the first valid flag
            status = next((name for name, flag in status_flags if flag), None)
            coords = geocode_address(address, label=map_id, status=status, cache=cache)
            if coords:
                cache[map_id] = coords  
            else:
                address = f"{row.get('Property Address Street Name:','')}, {row.get('City:','')} PA, {row.get('Zipcode:','')}, USA"
                map_id = f"{row.get('Property Address Street Name:','')}, {row.get('City:','')}"
                coords = geocode_address(address, label=map_id, status=status, cache=cache)
                if coords:
                    cache[map_id] = coords  
                else:
                    address = f"{row.get('City:','')} PA, {row.get('Zipcode:','')}, USA"
                    map_id = f"{row.get('City:','')}"
                    coords = geocode_address(address, label=map_id, status=status, cache=cache)
                    if coords:
                        cache[map_id] = coords  

        # Save merged cache 
        _save_geocode_cache(cache)

        # Generate map with all pins
        png_path = generate_full_map(cache)

        # Show in Tkinter window
        new_win = tk.Toplevel(self)
        new_win.title("Full Map of All Properties")

        img = Image.open(png_path)
        photo = ImageTk.PhotoImage(img)
        label = tk.Label(new_win, image=photo)
        label.image = photo
        label.pack(padx=20, pady=20)
                # Button to open full interactive map in browser
        def open_in_browser(event=None):
            webbrowser.open(MAP_HTML.as_uri())

        # Bind left mouse click on the label to open_in_browser
        label.bind("<Button-1>", open_in_browser)

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
    # --- TreeView ---
    def BuildTree(self):
        container = ttk.Frame(self)
        container.pack(side="top", fill="both", expand=True, padx=8, pady=8)
            #take the values of the headings in visible columns and display them
        self.tree = ttk.Treeview(container, columns=VisibleColumns, show="headings")
        
            #have a vertical scroll bar and horizontal scroll bar for navigation
        vsb = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscroll=vsb.set, xscroll=hsb.set)

        self.sort = {}
        
        def SortCol(col):
            self.sort[col] = not self.sort.get(col,False) #toggle sort
            items = [(self.tree.set(k,col),k)for k in self.tree.get_children("")]

            def tryNum(x):
                try:
                    return float(x)
                except Exception: #incase the contents are not able to be caste
                    return x
            items.sort(key=lambda t:tryNum(t[0]), reverse=self.sort[col])

            for index,(_,k) in enumerate(items):
                self.tree.move(k,"",index)
                
        #for each column in visible columns, display it as a heading in the tree
        for col in VisibleColumns:
            self.tree.heading(col, text=col, command= lambda c=col: SortCol(c))
            self.tree.column(col, width=150, anchor="w", minwidth =110)

        #place the grid and scrollbars
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        #if a row is selected, run the selected function
        self.tree.bind("<<TreeviewSelect>>", self.Selected)

        #for each row in the table, display its respective value for each column
        self._row_ids = {}
        for idx, row in self.df.iterrows():
            vals = [row.get(col, "") for col in VisibleColumns]
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

    # --- Filters processing ---
    def ApplyFilters(self, event=None):
        #copy original df
        data = self.df.copy()
        if self.City.get() != "City" and "City:" in data.columns:
            #grab the City filter if it is not all
            data = data[data["City:"] == self.City.get()]
        if self.Municipality.get() != "Municipality" and "Municipality:" in data.columns:
            #grab the Municipality if it is not all
            data = data[data["Municipality:"] == self.Municipality.get()]
        if self.BlightedFilter.get() and "Property Blighted?" in data.columns:
            #See if the blighted filter is selected
            data = data[data["Property Blighted?"] == True]
        if self.use.get() != "Both" and ("Commercial" and "Residential") in data.columns:
            #grab the use if it is not all
            if self.use.get() == "Commercial":
                data = data[data["Commercial"] == True]
            elif self.use.get() == "Residential":
               data = data[data["Residential"] == True]
        if self.VacancyFilter.get() and "Vacant Property:" in data.columns:
            #see if the vacanct filter is selected
            data = data[data["Vacant Property:"] == True]

        # grab the contents of the search bar, strip whitespace, and lowercase
        query = self.SearchInput.get().strip().lower()
        if query:
            # start with all False
            mask = pd.Series(False, index=data.index)

            # search across ALL columns, converting to string and ignoring case
            for col in data.columns:
                try:
                    col_str = data[col].astype(str).str.lower()
                    mask |= col_str.str.contains(query, na=False)
                except Exception:
                    # if a column somehow fails conversion, just skip it
                    pass

            data = data[mask]

        #show everything that accounts for all filters
        self.ShowTree(data)

    def ResetFilters(self):
        #reset all filters and earch bars to default values
        self.City.set("City")
        self.Municipality.set("Municipality")
        self.BlightedFilter.set(False)
        self.use.set("Use")
        self.VacancyFilter.set(False)
        self.SearchInput.set("")
        self.ShowTree(self.df) #show original df

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


        # --- Top image frame --- (where the image is presented)
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

        # --- Buttons outside frames  ---
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

        FavBtn.grid(row=3, column=2, sticky="ew", padx=8, pady=(6, 8))


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


        
        # --- InfoFrame and RightFrame ---
        InfoFrame = ttk.Frame(win, relief="solid", padding=5)
        InfoFrame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        InfoFrame.grid_rowconfigure(0, weight=1)
        InfoFrame.grid_columnconfigure(0, weight=1)

        canvas = tk.Canvas(InfoFrame) #set the info frame on the bottom left of the window
        vscroll = ttk.Scrollbar(InfoFrame, orient="vertical", command=canvas.yview)
        hscroll = ttk.Scrollbar(InfoFrame, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=vscroll.set, xscrollcommand=hscroll.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        vscroll.grid(row=0, column=1, sticky="ns")
        hscroll.grid(row=1, column=0, sticky="ew") #scrollbar will stick if necessary
        ScrollFrame = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=ScrollFrame, anchor="nw")

        #adjusts scroll region when content changes
        def ConfigureFrame(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        ScrollFrame.bind("<Configure>", ConfigureFrame)

        #display all values for hidden columns' cells
        for i, col in enumerate(hidden_columns):
            val = row.get(col, "")
            ttk.Label(ScrollFrame, text=f"{col}:", font=("Arial", 10, "bold")).grid(row=i, column=0, sticky="e", padx=6, pady=4)
            ttk.Label(ScrollFrame, text=val, wraplength=300, anchor="w").grid(row=i, column=1, sticky="w", padx=6, pady=4)
        ScrollFrame.grid_columnconfigure(1, weight=1)

        #right frame that will hold html page of image 
        #Newly implemented right frame should get the mapping functionality working??
        RightFrame = ttk.Frame(win, relief="solid", padding=5)
        RightFrame.grid(row=1, column=1, rowspan=2, sticky="nsew", padx=5, pady=5)

        # Title label inside RightFrame
        tk.Label(RightFrame, text="Map Viewer", font=("Arial", 12, "bold")).pack(pady=5)
        # generate map html and png paths if none exist

        # use the ID to assign a unique ID
        map_id = row.get("ID") 
        # generate a valid address for the property
        map_address = f"{row.get('StreetNum','')} {row.get('Address','')}, {row.get('City','')}, PA, {row.get('Zipcode', '')}, USA"
        # assign the boolean values to possible statuses
        status_flags = [ ("blight", validate(row.get("Property Blighted?", ""))), ("com", validate(row.get("Commercial", ""))), ("res", validate(row.get("Residential", ""))),]
        # assign the status to the first valid flag
        status = next((name for name, flag in status_flags if flag), None)
        # create the map, so that the status effects the pin color
        out = create_map(map_address, ID=str(map_id), cache=cache, status=status)
        MAP_HTML = CACHE_DIR / f"{map_id}_Map.html"
        MAP_PNG = CACHE_DIR / f"{map_id}_Map.png"
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



        #place holder right frame that will hold html page of image 
       # NoteFrame for notes
        NoteFrame = ttk.Frame(win, relief="solid", padding=5)
        NoteFrame.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        

        # Header label -> use grid, not pack
        tk.Label(NoteFrame, text=f"Notes: {row.get('Notes','')}", font=("Arial", 12, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=4, pady=4)

        # canvas + scrollbars inside NoteFrame (all grid)
        canvas = tk.Canvas(NoteFrame)
        vscroll = ttk.Scrollbar(NoteFrame, orient="vertical", command=canvas.yview)
        hscroll = ttk.Scrollbar(NoteFrame, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=vscroll.set, xscrollcommand=hscroll.set)

        # Layout: canvas at (1,0), vscroll at (1,1), hscroll at (2,0)
        canvas.grid(row=1, column=0, sticky="nsew")
        vscroll.grid(row=1, column=1, sticky="ns")
        hscroll.grid(row=2, column=0, sticky="ew")

        # Make canvas expand
        NoteFrame.rowconfigure(1, weight=1)
        NoteFrame.columnconfigure(0, weight=1)

        # scrollable frame inside the canvas
        AnotherScrollFrame = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=AnotherScrollFrame, anchor="nw")

        def configure_frame(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        AnotherScrollFrame.bind("<Configure>", configure_frame)



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
        addFrame = ttk.Frame(new_win, padding = 8)
        addFrame.pack(fill="both", expand=True)

        #enables scrollable window
        newCanvas = tk.Canvas(addFrame)
        newVscroll = ttk.Scrollbar(addFrame, orient="vertical", command=newCanvas.yview)
        newCanvas.configure(yscrollcommand=newVscroll.set)

        #layout canvas and scrollbar
        newCanvas.pack(side="left",fill="both", expand=True)
        newVscroll.pack(side="right", fill="y")

        #space for the contents - inner frame
        addInner = ttk.Frame(newCanvas)
        newCanvas.create_window((0, 0), window=addInner, anchor="nw")

        #keep the scroll space up-to-date whenever size changes
        def _configure(e):
            newCanvas.configure(scrollregion=newCanvas.bbox("all"))
        addInner.bind("<Configure>", _configure)

        #stores input controls to be read
        controls = {}
        
        #each row will hold a new column detail
        for i, col in enumerate(new_values):
            #val = row.get(col, "")
            #typ = _infer_type(val)

            #label for the column name is the column name from the csv
            lbl = ttk.Label(addInner, text=f"{col}:", font=("Arial", 10, "bold"))
            lbl.grid(row=i, column=0, sticky="e", padx=6, pady=6)

            #use entry widget to change values
            entvar = tk.StringVar(value="")
            ent = ttk.Entry(addInner, textvariable=entvar, width=50)
            ent.grid(row=i, column=1, sticky="we", padx=6, pady=6)
            controls[col] = ("str", entvar)
            
        #right column should expand with window
        addInner.grid_columnconfigure(1, weight=1)

        # Buttons at bottom
        btnfrm = ttk.Frame(new_win, padding=6)
        btnfrm.pack(fill="x", side="bottom")

        # When user clicks Save: gather controls, create new row, append, save, update tree
        def OnSave():
            # read controls
            new_row = {}
            for col, (_k, var) in controls.items():
                v = var.get()
                # leave empty string for blanks (consistent with other code)
                new_row[col] = v if v is not None else ""

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
        try: #grab the contents of the row that was selected
            row = self.df.loc[idx].copy()
        except Exception as e:
            messagebox.showerror("Edit error", f"Unable to find row {idx}: {e}")
            return

        #cannot change imagepath, id, created date, modified date directly
        skip_cols = {"ImagePath", "ID", "Created", "Modified", "Notes"}
        #all other values can be changed
        editable_cols = [c for c in self.df.columns if c not in skip_cols]


        edit_win = tk.Toplevel(self)
            #open a new window with details about the property
        edit_win.title(f"Edit Property Address: {row.get('StreetNum','')} {row.get('Address','')}")
        edit_win.geometry("620x520") #new window opens 
        edit_win.minsize(420, 300) #minimum size of window

        # Scrollable area
        frame = ttk.Frame(edit_win, padding=8)
        frame.pack(fill="both", expand=True)
        
        #enables scrollable window
        canvas = tk.Canvas(frame)
        vscroll = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vscroll.set)

        #layout canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

        #space for the contents - inner frame
        inner = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")

        #keep the scroll space up-to-date whenever size changes
        def _configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        inner.bind("<Configure>", _configure)

        #stores input controls to be read
        controls = {}

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
        
        #each row will hold a new column detail
        for i, col in enumerate(editable_cols):
            val = row.get(col, "")
            typ = _infer_type(val)

            #label for the column name is the column name from the csv
            lbl = ttk.Label(inner, text=f"{col}:", font=("Arial", 10, "bold"))
            lbl.grid(row=i, column=0, sticky="e", padx=6, pady=6)

            #use entry widget to change values
            entvar = tk.StringVar(value="" if pd.isna(val) else str(val))
            ent = ttk.Entry(inner, textvariable=entvar, width=50)
            ent.grid(row=i, column=1, sticky="we", padx=6, pady=6)
            controls[col] = ("str", entvar)
        #right column should expand with window
        inner.grid_columnconfigure(1, weight=1)

        # Buttons at bottom
        btnfrm = ttk.Frame(edit_win, padding=6)
        btnfrm.pack(fill="x", side="bottom")

        #when saving the data, it needs to be updated and backed up, treeview should also be updated
        def OnSave():
            updates = {}
            #read each control and convert to inferred datatype
            for col, (kind, ctl) in controls.items():
                try:
                    s = ctl.get().strip()
                    orig_val = row.get(col, "")
                    orig_kind = _infer_type(orig_val)
                    if s == "":
                        #store empty string if value is ""
                        newv = ""
                    elif orig_kind == "int":
                        #try int conversion
                        try:
                            newv = int(s)
                        except Exception:
                            newv = s
                    elif orig_kind == "float":
                        #try float conversion
                        try:
                            newv = float(s)
                        except Exception:
                            newv = s
                    else:
                        newv = s
                    updates[col] = newv
                except Exception as e:
                    #show conversion error and do not save
                    messagebox.showerror("Conversion error", f"Error parsing column {col}: {e}")
                    return
                
            if "Notes" in updates:
                raw = updates["Notes"]
                NewInput = (raw or "").strip()

                # read current notes robustly (handle NaN/None)
                old_raw = None
                if "Notes" in self.df.columns:
                    old_raw = self.df.at[idx, "Notes"]
                if pd.isna(old_raw) or old_raw is None:
                    previousNotes = ""
                else:
                    previousNotes = str(old_raw)

                # if user left the edit blank, do not overwrite existing notes
                if NewInput == "":
                    updates.pop("Notes", None)
                else:
                    # optional timestamp - set to False to disable
                    ADD_TIMESTAMP = True
                    if ADD_TIMESTAMP:
                        ts = datetime.now().strftime("[%Y-%m-%d %H:%M:%S] ")
                        FormatNew = f"[{username}{ts}]{NewInput}"
                    else:
                        FormatNew = NewInput

                    # if the user pasted/edited full history (their input contains previousNotes),
                    # trust their input exactly (do not prepend).
                    if previousNotes and previousNotes.strip() and previousNotes in NewInput:
                        combined = NewInput
                    else:
                        # avoid duplicate top entries
                        if previousNotes.strip().startswith(FormatNew):
                            combined = previousNotes
                        else:
                            combined = FormatNew if previousNotes.strip() == "" else f"{FormatNew}\n\n{previousNotes}"

                    updates["Notes"] = combined

            try:
                #apply updates to df
                for c, v in updates.items():
                    self.df.at[idx, c] = v

                # backup original CSV
                csv_path = CSV_PATH
                try:
                    if os.path.exists(csv_path):
                        bak_name = f"{os.path.splitext(csv_path)[0]}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                        #rename original to backup
                        os.replace(csv_path, bak_name)
                except Exception as e:
                    #warn if backup did not save
                    messagebox.showwarning("Backup warning", f"Failed to create backup: {e}")

                # save DataFrame
                try:
                    self.df.to_csv(csv_path, index=False)
                except Exception as e:
                    messagebox.showwarning("Save warning", f"Failed to write CSV ({csv_path}): {e}")

                # refresh Treeview row
                if hasattr(self, "_row_ids") and idx in self._row_ids:
                    iid = self._row_ids[idx]
                    #build displayed values for Visible columns
                    vals = [self.df.at[idx, col] if col in self.df.columns else "" for col in VisibleColumns]
                    vals = [("" if pd.isna(v) else str(v)) for v in vals]
                    try:
                        self.tree.item(iid, values=vals)
                    except Exception:
                        #ignore if treeview update fails
                        pass

                #inform user of save
                messagebox.showinfo("Saved", "Property values updated and saved.")
                try:
                    edit_win.grab_release()
                except Exception:
                    pass
                edit_win.destroy()
            except Exception as e:
                #catch unexpected update failures
                messagebox.showerror("Update error", f"Failed to update property: {e}")

        #function to close without saving
        def OnCancel():
            try:
                edit_win.grab_release()
            except Exception:
                pass
            edit_win.destroy()

        #button has designated commands 
        save_btn = ttk.Button(btnfrm, text="Save", command=OnSave)
        cancel_btn = ttk.Button(btnfrm, text="Cancel", command=OnCancel)
        save_btn.pack(side="right", padx=6)
        cancel_btn.pack(side="right", padx=6)

    # --- Add note helper ---
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
        
# --- Run App ---
if __name__ == "__main__":
    app = App()
    app.mainloop()

