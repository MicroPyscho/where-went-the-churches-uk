# UK Church Conversion Research Pipeline

**What are former UK church buildings becoming?**

A data research project tracking the transformation of the UK religious landscape —
mosques, pubs, flats, arts venues, and everything in between.

This pipeline is the data foundation for the **Sacred Spaces** property intelligence platform.

-----

## What This Produces

|Output                                       |Description                       |
|---------------------------------------------|----------------------------------|
|`uk_church_conversions_YYYYMMDD.csv`         |Full master dataset (all fields)  |
|`uk_church_conversions_PUBLIC_YYYYMMDD.csv`  |Clean public release version      |
|`uk_church_conversions_summary_YYYYMMDD.xlsx`|Excel with 7 pivot analysis sheets|
|PostgreSQL table `church_conversions`        |Powers the web app                |

### Dataset Schema

|Column                  |Description                                        |
|------------------------|---------------------------------------------------|
|`id`                    |Unique record ID (12-char MD5 hash)                |
|`church_name`           |Original name of the church building               |
|`former_denomination`   |e.g. Church of England, Methodist, Baptist         |
|`address`               |Street address                                     |
|`city`                  |Town or city                                       |
|`local_authority`       |Council district                                   |
|`region`                |UK region (e.g. North West, Yorkshire)             |
|`nation`                |England / Wales / Scotland / Northern Ireland      |
|`latitude` / `longitude`|WGS84 coordinates                                  |
|`conversion_type`       |Top-level category (see taxonomy below)            |
|`conversion_subtype`    |Granular sub-classification                        |
|`current_name`          |What the building is now called                    |
|`year_converted`        |Year of conversion (where known)                   |
|`decade`                |e.g. “1990s”, “2000s”                              |
|`source`                |Data source (wikidata, osm, historic_england, etc.)|
|`confidence_score`      |0.0–1.0 reliability rating                         |
|`confidence_tier`       |high / medium / low                                |

### Conversion Taxonomy

```
mosque          → mosque_general, sunni_mosque, shia_mosque, islamic_centre, madrasa
other_faith     → sikh_gurdwara, hindu_temple, buddhist_temple, jewish_synagogue,
                  pentecostal, evangelical, other_christian, jehovahs_witness
residential     → converted_flats, single_dwelling, care_home, student_housing,
                  luxury_apartments
hospitality     → pub, bar, nightclub, restaurant, cafe, hotel, event_venue
arts_culture    → theatre, concert_hall, arts_centre, gallery, cinema, museum
education       → school, university, library, nursery
community       → community_centre, sports_hall, food_bank, charity_hub
commercial      → office, shop, supermarket, gym, climbing_wall, storage
demolished      → demolished_cleared, demolished_replaced
vacant          → derelict, mothballed
tourist         → heritage_attraction, visitor_centre
unknown         → unknown
```

-----

## Data Sources

|Source                |Coverage       |Confidence|API Key?         |
|----------------------|---------------|----------|-----------------|
|Wikidata SPARQL       |All UK         |0.95      |No               |
|OpenStreetMap Overpass|All UK         |0.70      |No               |
|Historic England NHLE |England only   |0.90      |No               |
|Charity Commission    |England & Wales|0.75      |Free registration|

-----

## Setup

```bash
# 1. Clone and install
git clone <your-repo>
cd church_conversion_pipeline
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env — only DATABASE_URL and CHARITY_COMMISSION_API_KEY are optional

# 3. Run the pipeline
python main.py

# Options
python main.py --sources wikidata osm          # Run specific sources
python main.py --skip-geocode                  # Skip geocoding (faster)
python main.py --dry-run                       # Extract only, no file output
python main.py --verbose                       # Debug logging
```

-----

## Architecture

```
church_conversion_pipeline/
├── main.py                          # CLI runner (Rich + Typer)
├── constants.py                     # Master schema, taxonomy, config
├── requirements.txt
├── .env.example
│
├── extractors/
│   ├── wikidata_extractor.py        # 4 SPARQL queries → verified conversions
│   ├── osm_extractor.py             # 8 Overpass queries → crowd-sourced data
│   ├── historic_england_extractor.py # NHLE API → listed buildings
│   └── charity_commission_extractor.py # Deregistered church charities
│
├── transforms/
│   ├── pipeline.py                  # Clean → Geocode → Enrich → Dedup → Validate
│   └── loader.py                    # CSV + PostgreSQL + Excel pivot output
│
└── data/
    ├── raw/                         # Raw extractor outputs (one CSV per source)
    ├── processed/                   # Intermediate pipeline stages
    └── output/                      # Final deliverables
```

### Pipeline Flow

```
[Wikidata]  [OSM]  [Historic England]  [Charity Commission]
     ↓         ↓            ↓                   ↓
  Extract   Extract       Extract             Extract
     └─────────┴────────────┴───────────────────┘
                           ↓
                       Combine
                           ↓
                        Clean
                    (normalise types, fix coords, validate)
                           ↓
                  Geocode missing coords
                    (Nominatim — free)
                           ↓
                  Reverse geocode enrichment
                    (fill region, nation, LA)
                           ↓
                   Cross-source dedup
                    (150m proximity + fuzzy name)
                           ↓
                  Add derived fields
                    (decade, ID, confidence_tier)
                           ↓
                       Validate
                    (report coverage metrics)
                           ↓
              ┌────────────┴────────────┐
           CSV/Public              PostgreSQL
           Excel pivots
```

-----

## Caveats & Honest Limitations

1. **No single authoritative registry exists** for UK church conversions. This pipeline
   is the closest approximation from five complementary sources.
1. **OSM data is crowd-sourced** — quality varies by area. Urban areas (esp. London,
   Birmingham, Manchester) are well-mapped; rural areas less so.
1. **Charity Commission matching is indirect** — deregistration of a church charity
   doesn’t always mean physical conversion; the congregation may have merged elsewhere.
1. **The “mosque” claim context**: Many viral claims about “500 churches becoming mosques”
   conflate different outcomes. This dataset shows the full picture — residential
   conversion is typically the most common outcome, not religious conversion.
1. **Year data is sparse** — most records won’t have a conversion year. This improves
   over time as more records are cross-referenced.

-----

## Extending the Pipeline

To add a new source extractor:

1. Create `extractors/your_source_extractor.py`
1. Implement `extract() → pd.DataFrame` returning MASTER_COLUMNS
1. Add it to `main.py` under the extraction stage
1. Add its confidence weight to `SOURCE_CONFIDENCE` in `constants.py`

-----

## Data Release

The public CSV is released under **Creative Commons CC BY 4.0**.
If you use it, please cite: *UK Church Conversion Dataset, [Your Name], [Year].*

For academic citation or collaboration enquiries, see [your contact].

-----

## Related Projects

- **Sacred Spaces** — church property marketplace using this data as its foundation
- **SafeMap UK** — ward-level urban intelligence platform (same author)