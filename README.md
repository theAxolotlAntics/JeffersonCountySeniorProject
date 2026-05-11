# **Jefferson County Property Viewer**  
*A Senior Project for PennWest Clarion — Fall 2025 / Spring 2026*

The **Jefferson County Property Viewer** is a Python‑based desktop application designed to help Jefferson County staff manage, review, and visualize property information. Built for secure, offline use, the system interprets CSV datasets, displays property details, generates interactive maps, and provides tools for note‑taking, filtering, and data review. The application is fully packaged as a standalone executable for ease of deployment on county machines.

---

## **Features**
- **CSV Interpretation & Editing**  
  Load, review, filter, and update property datasets with a clean, structured interface.

- **Integrated Mapping System**  
  Generate interactive Folium maps, view static previews in‑app, and open full maps in a browser.

- **Offline Map Tiles**  
  Uses locally stored tiles for fast, reliable rendering without external dependencies.

- **Geocoding with Caching**  
  New addresses are geocoded once and stored for future use, improving performance over time.

- **Image & Document Display**  
  View property images and related files directly within the interface.

- **Notes & Comments**  
  Add and save property‑specific notes for internal tracking.

- **Safe Exporting**  
  Updated CSVs are exported as new files to preserve original datasets.

- **Local‑Only Operation**  
  No internet connection required; ideal for secure government environments.

---

## **Technology Stack**
- **Python 3.x**
- **Tkinter** — GUI framework  
- **Pandas** — CSV handling  
- **Folium** — Map generation  
- **Selenium** — Map preview capture  
- **Offline Tile System** — Local map rendering  
- **PyInstaller** — Executable packaging  

---

## **Development Timeline (High‑Level Summary)**

### **Weeks 1–3 — Planning**
Team formation, client meetings, technology research, and early design decisions.

### **Weeks 4–5 — Early Testing**
Prototype mapping, geocoding tests, and initial CSV handling.

### **Weeks 6–10 — Foundation Building**
Dummy data creation, modular code structure, and early UI experiments.

### **Weeks 11–16 — Major Growth**
GitHub migration, mapping module stabilization, and first full UI integration.

### **Week 17 — Reflection**
Repository cleanup, documentation restructuring, and planning for semester two.

### **Weeks 18–23 — Feature Sprint**
Color‑coding, caching, UI improvements, bug fixes, and performance enhancements.

### **Weeks 24–28 — Polishing**
Offline tile migration, UI refinement, documentation expansion, and stability testing.

### **Weeks 29–32 — Finalization**
Packaging fixes, final documentation, advisor feedback integration, and delivery preparation.

---

## **Major Milestones**
- First working map rendering  
- CSV interpreter + filtering system  
- Full mapping module integration  
- GitHub workflow adoption  
- Color‑coded property markers  
- Offline tile system implementation  
- Packaged executable builds  
- Completed documentation suite (User Manual, System Documentation, Implementation Manual)

---

## **Known Challenges & Solutions**
- **Geocoding rate limits** → Implemented caching  
- **Shapefile inconsistencies** → Switched to municipality‑level datasets  
- **Tkinter map embedding issues** → Adopted Selenium screenshot workflow  
- **OSM throttling** → Migrated to offline tiles  
- **Client device restrictions** → Adjusted packaging and file paths  

---

## **Future Improvements**
- Enhanced error handling  
- Additional map layers (zoning, parcels, flood zones)  
- Multi‑user support  
- Cloud‑based data storage  
- Automated reporting tools  
- Improved UI theming (dark mode, accessibility options)

---

## **Project Team**
**Team 1 — PennWest Clarion Senior Project (Fall 2025 / Spring 2026)**  
- Brunner Good — Backend Developer
- Gannon — Frontend Developer & Communications  
- Alexis — Frontend Developer 
- Issac — Documentation & Backend Support  
