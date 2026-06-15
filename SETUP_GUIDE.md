# Setup & Run Guide

## UK Church Conversion Pipeline — From Zero to First Data

-----

## Before You Start

You need three things installed on your Mac:

- **Python 3.10+** (you almost certainly have this — check with `python3 --version`)
- **VS Code** (already on your M1)
- **Git** (check with `git --version` — Mac will prompt to install if missing)

You do NOT need to build anything. The CLI is already built. You just run commands.

-----

## Step 1 — Get the Project Into VS Code

### Option A: You downloaded the files from Claude

1. Unzip the folder if it’s zipped
1. Open VS Code
1. Go to **File → Open Folder**
1. Select the `church_conversion_pipeline` folder
1. Click **Open**

### Option B: You want to start fresh with Git (recommended)

```bash
# In Terminal (Command + Space → type Terminal → Enter)
mkdir ~/Projects
cd ~/Projects
mkdir church_conversion_pipeline
cd church_conversion_pipeline
git init
```

Then open VS Code:

```bash
code .
```

If `code .` doesn’t work, open VS Code manually → **File → Open Folder** → select the folder.

Now create each file by copying from Claude’s output — paste into VS Code and save with the exact filenames shown.

-----

## Step 2 — Open the Integrated Terminal in VS Code

Inside VS Code:

- Press **Control + ` ** (backtick — the key above Tab)
- Or go to **Terminal → New Terminal** from the top menu

You’ll see a terminal panel appear at the bottom. All commands from here go in there.

-----

## Step 3 — Create a Virtual Environment

A virtual environment keeps your project’s dependencies isolated from the rest of your Mac. Always use one.

```bash
# Make sure you're in the project folder (you should see church_conversion_pipeline in the path)
pwd

# Create the virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate
```

You’ll know it worked when you see `(venv)` appear at the start of your terminal line, like:

```
(venv) collins@MacBook church_conversion_pipeline %
```

**Important:** Every time you open a new terminal session, you need to re-activate:

```bash
source venv/bin/activate
```

-----

## Step 4 — Tell VS Code to Use Your Virtual Environment

1. Press **Command + Shift + P** to open the Command Palette
1. Type `Python: Select Interpreter`
1. Press Enter
1. You’ll see a list — choose the one that says `venv` in the path, something like:
   `./venv/bin/python`

This means VS Code’s IntelliSense (autocomplete, error highlighting) will use the same Python as your terminal.

-----

## Step 5 — Install Dependencies

```bash
pip install -r requirements.txt
```

This installs everything the pipeline needs. It takes 1–3 minutes. You’ll see a lot of lines scrolling — that’s normal.

When it’s done, verify the key packages are there:

```bash
python -c "import pandas, requests, rich, typer; print('All good')"
```

If you see `All good` — you’re ready. If you see an error, paste it here and I’ll fix it.

-----

## Step 6 — Set Up Your Environment File

```bash
# Copy the template
cp .env.example .env
```

Now open `.env` in VS Code (you’ll see it in the file explorer on the left sidebar).

It looks like this:

```
DATABASE_URL=postgresql://user:password@localhost:5432/church_conversions
CHARITY_COMMISSION_API_KEY=your_key_here
```

**For your first run, leave both blank.** The pipeline works without them — it just skips the database write and the Charity Commission source. You can add these later.

Change the file to:

```
DATABASE_URL=
CHARITY_COMMISSION_API_KEY=
```

Save it with **Command + S**.

-----

## Step 7 — Understand the Folder Structure

Before running anything, take 2 minutes to understand what you’re looking at:

```
church_conversion_pipeline/
│
├── main.py                  ← The entry point. This is what you run.
├── constants.py             ← Schema, taxonomy, config. Read this to understand the data model.
├── requirements.txt         ← Package list
├── .env                     ← Your private config (never commit this to GitHub)
│
├── extractors/              ← One file per data source
│   ├── wikidata_extractor.py
│   ├── osm_extractor.py
│   ├── historic_england_extractor.py
│   └── charity_commission_extractor.py
│
├── transforms/              ← Cleaning, geocoding, deduplication, output
│   ├── pipeline.py
│   └── loader.py
│
└── data/
    ├── raw/                 ← Raw data saved here after extraction
    ├── processed/           ← Intermediate stages
    └── output/              ← Your final CSVs and Excel file land here
```

-----

## Step 8 — Run the Test Script First

Before running the full pipeline, run this to check each extractor individually:

```bash
python test_extractors.py
```

(See the test script section below — create this file first.)

-----

## Step 9 — Your First Real Run

Start small. Wikidata only, no geocoding, no file output:

```bash
python main.py --sources wikidata --skip-geocode --dry-run
```

What each flag means:

- `--sources wikidata` — only run the Wikidata extractor (fastest, most reliable)
- `--skip-geocode` — skip the step that fills in missing coordinates (saves time)
- `--dry-run` — extract and transform but don’t write any files

You’ll see Rich terminal output showing records flowing in. If you see church conversion records printing — it’s working.

-----

## Step 10 — Run With Output Files

Once the dry run works, run for real:

```bash
python main.py --sources wikidata osm --skip-geocode
```

This runs Wikidata + OpenStreetMap and writes your output files.

Check the `data/output/` folder in VS Code’s sidebar — you should see:

- `uk_church_conversions_YYYYMMDD.csv`
- `uk_church_conversions_PUBLIC_YYYYMMDD.csv`
- `uk_church_conversions_summary_YYYYMMDD.xlsx`

Open the Excel file to see the pivot sheets.

-----

## Step 11 — Full Pipeline Run

When you’re confident, run everything:

```bash
python main.py
```

This runs all 4 sources with geocoding. It will take **15–45 minutes** depending on how much data comes back from OSM and how many records need geocoding. The geocoder is rate-limited to 1 request/second by law (Nominatim’s terms of use) — that’s not something to bypass.

Watch the log file in real time in a second terminal:

```bash
tail -f pipeline.log
```

-----

## Step 12 — Run Options Reference

```bash
# Run all sources (default)
python main.py

# Run specific sources only
python main.py --sources wikidata
python main.py --sources wikidata osm
python main.py --sources historic_england charity_commission

# Skip geocoding (much faster, good for testing)
python main.py --skip-geocode

# Dry run — no files written
python main.py --dry-run

# Verbose logging (shows DEBUG messages)
python main.py --verbose

# Combine flags freely
python main.py --sources wikidata --skip-geocode --dry-run --verbose

# See all options
python main.py --help
```

-----

## Common Errors and Fixes

### `ModuleNotFoundError: No module named 'X'`

You’re not in the virtual environment, or didn’t install dependencies.

```bash
source venv/bin/activate
pip install -r requirements.txt
```

### `(venv)` disappeared from my terminal prompt

The venv deactivated. Just re-activate:

```bash
source venv/bin/activate
```

### OSM query takes forever / times out

Normal on first run. The UK bounding box is large. Wait it out or reduce scope:

```bash
# Run OSM alone to watch it
python main.py --sources osm --skip-geocode --verbose
```

### `connection refused` or `psycopg2` error

PostgreSQL isn’t running or DATABASE_URL is wrong. Leave `.env` blank for now — the pipeline skips the DB write gracefully.

### Rate limit error from Nominatim

The geocoder is hitting Nominatim too fast. The pipeline already respects the 1 req/sec limit, but if you get errors, add `--skip-geocode` and geocode in a separate later run.

-----

## VS Code Extensions Worth Installing

Open the Extensions panel (**Command + Shift + X**) and install:

- **Python** (by Microsoft) — essential. Linting, IntelliSense, debugger
- **Pylance** — better Python autocomplete
- **Rainbow CSV** — makes your output CSV files readable in VS Code
- **GitLens** — shows git blame inline, very useful
- **Thunder Client** — lightweight API tester (useful for testing SPARQL queries)

-----

## About the CLI — You Don’t Need to Build It

The CLI is already built. `main.py` uses a library called **Typer** which turns your Python functions into a proper command-line interface automatically. When you run `python main.py --help`, Typer generates the help text. When you pass `--sources wikidata`, Typer parses and validates it. You get all of this for free — no extra work needed.

-----

## Next Steps After Your First Successful Run

1. **Check data quality** — open the Excel file, look at the pivot sheets. How many records per type? Which sources gave the most data?
1. **Register for Charity Commission API** — free, takes 5 minutes, unlocks another source: <https://register-of-charities.charitycommission.gov.uk/api>
1. **Set up PostgreSQL locally** — use Postgres.app (free Mac app): <https://postgresapp.com> — then add your DATABASE_URL to `.env`
1. **Push to GitHub** — make the dataset public so others can use it
1. **Build the dashboard** — send me 2–3 reference designs you like and your logo/fonts

-----

## Quick Command Summary (Bookmark This)

```bash
# Navigate to project
cd ~/Projects/church_conversion_pipeline

# Activate environment (every new terminal session)
source venv/bin/activate

# Quick test (Wikidata only, no files written)
python main.py --sources wikidata --skip-geocode --dry-run

# Medium run (two sources, no geocoding)
python main.py --sources wikidata osm --skip-geocode

# Full run
python main.py

# Watch the log
tail -f pipeline.log

# See all options
python main.py --help
```