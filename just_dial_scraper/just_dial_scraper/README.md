# Justdial Parallel Scraper (Production Edition)

A high-speed, parallel, multi-city/service scraper with direct integration to local MySQL & SQLite fallback databases and dynamic gzip caching.

## 📁 Project Directory Structure
```
just_dial_scraper/
├── config.json           # MySQL & Scraper settings
├── requirements.txt      # Python dependencies
├── README.md             # Running & configuration guides
├── run.py                # Main project entrypoint CLI
└── justdial/             # Scraper core module
    ├── __init__.py       # Package marker
    ├── scraper.py        # Intercept stabilization & pagination loops
    ├── parser.py         # Playwright suggestion selecting & browser wrapper
    └── db.py             # Schema creation & SQL transaction pipelines
```

---

## ⚙️ Configuration (`config.json`)
Open [`config.json`](file:///c:/Users/meetv/OneDrive/Desktop/just_dial_scraper/config.json) to customize scraper targets or database settings:
* **`database`**: Local MySQL server host, port, root user, password, and target database name.
* **`scraper`**: 
  - `cities`: Array of cities to scrape (e.g. `["Ahmedabad", "Surat", "Rajkot"]`).
  - `services`: Array of target services/categories (e.g. `["Pest Control Services", "Plumbers"]`).
  - `page_chunk_size`: Number of pages to scrape concurrently in parallel (default: `5`).
  - `pagesave_directory`: Local directory to save raw page JSON responses as compressed gzip files.

---

## 🚀 Execution CLI Commands
All tasks are triggered using the master CLI entrypoint [`run.py`](file:///c:/Users/meetv/OneDrive/Desktop/just_dial_scraper/run.py):

### 1. Run Scraper
Fetches targets, refreshes sessions automatically, and inserts records into dynamic daily tables `justdial_leads_YYYY_MM_DD`:
```bash
python run.py
```

### 2. Export Database to Excel
Reads dynamic date-based table and exports to Excel spreadsheet `justdial_leads_YYYY_MM_DD.xlsx`:
* **Today's Table**:
  ```bash
  python run.py --export
  ```
* **Specific Historical Date Table**:
  ```bash
  python run.py --export 2026_08_18
  ```

### 3. Test Database Connection
Validates MySQL root username and password credentials:
```bash
python run.py --test-db
```
