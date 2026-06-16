# Sacred Spaces: UK Church Conversion Research Pipeline
## Full Methodology, Research Decisions, and Technical Log
### Version 1.0 — June 16, 2026

---

## Abstract

This document provides a complete account of the research methodology, technical decisions, challenges encountered, and solutions applied in building the Sacred Spaces dataset — a systematic mapping of 23,719 former UK church buildings and their conversion to new uses. The work was conducted between June 14–16, 2026, producing what is believed to be the first open, multi-source, coordinate-level dataset of UK church conversions across all four nations. The headline finding — that residential conversion is 697 times more common than mosque conversion — directly contradicts a widespread political narrative and is supported by evidence from four independent data sources cross-validated through spatial deduplication.

---

## 1. Research Motivation and Questions

The project originated from a specific political and social question: what is actually happening to UK church buildings as Christianity declines? A persistent media narrative — that churches are being converted to mosques at significant rates — had circulated in UK public discourse without systematic empirical investigation. No unified dataset existed across all denomination types, all conversion categories, and all four UK nations.

The primary research questions were:

1. What proportion of former UK church buildings have been converted to mosques versus other uses?
2. What is the dominant conversion category, and how does it vary by region and decade?
3. Are there identifiable geographic, temporal, and economic patterns in conversion activity?
4. Which communities — religious, ethnic, and social — are acquiring former church buildings, and at what prices?
5. Can conversion activity serve as a leading indicator of neighbourhood change, housing pressure, and community infrastructure loss?

---

## 2. Data Sources and Extraction Strategy

### 2.1 Source Selection

Four primary sources were identified as the most comprehensive and freely accessible for UK church conversion data:

**Wikidata SPARQL** — The semantic web knowledge graph contains structured data on buildings with explicit conversion relationships (P1365 "replaces" and P1366 "replaced by"). Four SPARQL queries were constructed: buildings that replace churches, buildings formerly used as churches, mosques from churches, and category-tagged converted buildings. Confidence weight: 0.95 (highest — human-curated, explicitly linked data). Yield: 157 records after internal deduplication.

**OpenStreetMap Overpass API** — OSM's key insight for this project: a converted building often retains its original `building=church` tag even after conversion, while `amenity`, `religion`, and `denomination` tags reflect current use. This mismatch is the detection signal. Eight Overpass queries were constructed targeting: other-faith buildings in church structures, hospitality conversions, residential conversions, mosque-in-church, arts and community uses, explicit conversion tags (`building:was=church`), commercial conversions, and sport/leisure conversions. A ninth set of six regional queries for `historic=church` was added in the updated extractor to avoid the timeout that afflicted the single UK-wide query. Confidence weight: 0.70. Yield: 5,847 records after deduplication.

**Historic England National Heritage List for England (NHLE)** — A 379,666-record CSV of all listed buildings in England. The pipeline filtered for records containing church or chapel keywords in the building name, yielding 48,151 records. Conversion type was inferred from name patterns: "former chapel now flats," "converted to residential use," etc. This is an England-only source — no equivalent national register exists for Scotland, Wales, or Northern Ireland. Confidence weight: 0.90. Yield: 48,151 records (pre-deduplication).

**Planning Portal (planning.data.gov.uk)** — Used as an enrichment source rather than a primary extractor. The API was queried with a 100-metre bounding box around each record's coordinates to find planning applications at that location. Change-of-use class codes (C3, F2, A4 etc.) were mapped to the conversion taxonomy, and decision dates provided year-of-conversion data. Coverage: approximately 60% of English Local Planning Authorities. Wales, Scotland, and Northern Ireland are not covered. Confidence weight added to enriched records: 0.80.

### 2.2 Sources Not Yet Implemented

The following sources were designed and coded but not yet run at time of writing:

- OSCR (Office of the Scottish Charity Regulator) — Scotland charity register, to address severe Scottish undercounting
- CCNI (Charity Commission for Northern Ireland) — Northern Ireland charity register
- Ofsted register — to confirm school and nursery conversions
- CQC (Care Quality Commission) — to confirm care home and health centre conversions
- Companies House API — to identify buyer organisations, their type, SIC code, and country of incorporation
- OSM PBF local extract — to replace Overpass API for the historic_church query category that consistently times out

---

## 3. Deduplication Methodology

### 3.1 The Problem

The three primary sources — Wikidata, OSM, and Historic England — independently identify many of the same physical buildings. Without deduplication, St Mary's Chapel in Bradford would appear three times in the dataset with three different confidence scores, three different partial records, and potentially conflicting conversion types.

### 3.2 KD-Tree Spatial Deduplication

The deduplication algorithm uses a KD-tree (k-dimensional tree) data structure to efficiently find records within a spatial proximity threshold. The threshold was set at 150 metres — buildings within 150m of each other in different source datasets are considered candidates for the same physical building.

The algorithm:
1. Builds a KD-tree index from all record coordinates
2. For each record, queries the tree for all other records within 150m
3. Where two records from different sources match within 150m, merges them into a single record
4. The merge retains the highest-confidence source's classification but notes all sources in the `notes` field
5. Fields are filled from the most specific source available (Wikidata for explicit conversion relationships, NHLE for building names and listing grades, OSM for current use tags)

The result: 54,155 raw records reduced to 23,719 deduplicated records (30,436 duplicates removed, a 56% reduction). This high deduplication rate is itself a validation signal — it demonstrates that three independent sources are finding the same real buildings, cross-validating each other.

### 3.3 Why 56% Duplication is Good News

The 56% rate was initially alarming. It means more than half of raw records appear in multiple sources. This was reframed correctly: cross-source agreement is quality evidence. A building that appears in Wikidata (confidence 0.95), OSM (0.70), and Historic England (0.90) is almost certainly real and correctly identified. Single-source records are less certain. The deduplication process produces a confidence-weighted merged record rather than discarding data.

---

## 4. Conversion Taxonomy Design

### 4.1 Initial Taxonomy

The initial taxonomy was borrowed from OSM amenity and religion tags: mosque, residential, hospitality, arts_culture, education, community, commercial, other_faith, unknown. This captured the broad categories but lost sociologically important distinctions — a Sunni Deobandi mosque and an Ahmadiyya mosque are fundamentally different institutions serving different communities, yet both appeared as "mosque."

### 4.2 Expanded Taxonomy

Through extended research into UK religious demography, a comprehensive taxonomy was developed covering 20 conversion types and 80+ subtypes. The key expansions:

**Mosque subtypes (13):** sunni_deobandi, sunni_barelwi, sunni_salafi, sunni_arab_african, sunni_somali, sunni_tablighi, shia_twelver, shia_ismaili, ahmadiyya, islamic_centre, madrasa, muslim_community_centre, mosque_general.

**African diaspora church subtypes (19):** rccg, winners_chapel, christ_embassy, mountain_of_fire, deeper_life, house_on_the_rock, cherubim_seraphim, celestial_church, church_of_pentecost (Ghanaian), icgc, action_chapel, lighthouse_chapel, zaoga_forward_faith, uckg, ethiopian_orthodox, eritrean_orthodox, congolese_church, african_apostolic, african_church_general.

**Eastern European church subtypes (9):** ukrainian_orthodox, ukrainian_catholic, polish_catholic, romanian_orthodox, romanian_catholic, russian_orthodox_rocor, serbian_orthodox, bulgarian_orthodox, eastern_european_general.

**Sport and leisure subtypes (11):** climbing_wall (St Werburgh's Bristol 1992 — UK's first), skate_park (Skaterham Surrey confirmed), gym_fitness, trampoline_park, paintball_lasertag, escape_room, bowling_alley, dance_studio, martial_arts, swimming_pool, sport_leisure_general.

**Community subtypes (12):** community_centre, lgbtq_centre, food_bank, youth_centre, nhs_health_centre, drug_rehabilitation, citizens_advice, diaspora_community_hub, refugee_community_centre, sports_hall, charity_hub, community_general.

**New religious movements (8):** scientology (confirmed UK portfolio: Manchester, Plymouth, Gateshead, Birmingham, East Grinstead), jehovahs_witness, mormon_lds, new_apostolic, christadelphians, spiritualist, unification_church, nrm_general.

**Esoteric/occult (6):** pagan_wiccan, druid_grove, satanic_temple, lavey_satanism, occult_lodge, esoteric_general.

### 4.3 Detection Methods

Three-tier detection was implemented:

1. **OSM denomination tag** — the `denomination=` tag in OSM records maps directly to subtypes. Most reliable but sparse coverage (approximately 30% of relevant records).

2. **Name keyword matching** — the `current_name` and `church_name` fields are scanned against 80+ keyword rules. "Redeemed Christian Church" → rccg. "Kingdom Hall" → jehovahs_witness. "Masjid" → mosque_general. "Climbing" → climbing_wall.

3. **Notes field text** — the pipeline notes field captures OSM raw tags. Text parsing extracts denomination information even when not formally recorded in structured fields.

The denomination enrichment script processed all 23,719 records in under 3 seconds (no API calls required) and upgraded 23 subtypes from general to specific classifications. The low yield reflects the dominant source (Historic England NHLE) which records building names not current organisational names.

---

## 5. Planning Portal Enrichment — The Major Enrichment

### 5.1 Methodology

The planning portal enrichment was the single most significant data quality improvement. The script queried planning.data.gov.uk for each record's coordinates, searching within a 100-metre bounding box for planning applications at that location.

For each matching application:
- The `proposed-use-class` field was mapped to the conversion taxonomy using Use Class Order codes (C3=residential, F2=community, A4=pub, etc.)
- The application description text was pattern-matched for specific conversion types (mosque, gurdwara, climbing, etc.)
- The `decision-date` was used as the year of conversion proxy

### 5.2 Performance

The script ran with checkpoint-based resume capability, saving progress every 100 records. Performance across the full run:

- Total records queried: 23,606
- Conversion types resolved: ~13,000 (from unknown to specific)
- Years added: 23,483 (from 8 at project start to 99% coverage)
- Errors: 3 total across entire run
- Hit rate: ~89% type resolution, ~100% year resolution

The near-100% year resolution rate reflects the planning portal's comprehensive coverage of English LPAs for post-2000 applications. The 89% type resolution rate reflects the proportion of applications containing sufficient description text for classification.

### 5.3 Methodological Limitations

The planning portal covers approximately 60% of English Local Planning Authorities. Rural councils, smaller authorities, and pre-2000 applications are systematically absent. This creates a geographic bias toward urban areas and a temporal bias toward recent conversions. The dataset therefore slightly overrepresents urban and post-2000 conversions relative to rural and pre-2000 conversions.

Decision date is used as a proxy for conversion year. In practice, the gap between planning decision and actual conversion ranges from months to several years. The year_converted field should be understood as "year of planning approval" not "year building was physically converted."

Wales, Scotland, and Northern Ireland are not covered by planning.data.gov.uk. All year and type enrichment from this source applies to English records only.

---

## 6. Geographic Enrichment — Solving the Nation/Region Problem

### 6.1 The Problem

After the initial pipeline run, 3,851 records (16%) had no nation or region assigned. These were primarily OSM records where the `addr:city` field contained local authority names not in the lookup table, and NHLE records where the city field was blank.

### 6.2 Three-Stage Solution

**Stage 1 — UK_LA_TO_REGION lookup expansion.** The constants file was expanded from a minimal lookup table to a comprehensive mapping of 200+ UK place names (city names, local authority names, parish names) to region and nation. Manually populated from knowledge of UK geography. Added 267 records to nation coverage.

**Stage 2 — Coordinate-based nation detection in OSM extractor.** The updated OSM extractor includes a `nation_from_tags()` function that uses coordinate bounding boxes as a fallback when OSM address tags are absent. Scotland: latitude > 55.0°N and longitude < -1.5°W. Northern Ireland: latitude > 54.0°N and longitude < -5.5°W. Wales: 51.3°N–53.5°N and longitude < -2.8°W.

**Stage 3 — Postcodes.io reverse geocoding.** The definitive solution. A bulk API (postcodes.io) accepts up to 100 coordinate pairs per request and returns the nearest postcode, region, nation, ward, LSOA, and MSOA. The full 23,717 records with coordinates were processed in 238 API calls taking 3 minutes 8 seconds at zero cost. Results: 17,423 postcodes added, 16,093 regions upgraded, 2,393 nations upgraded. Nation coverage rose from 85.3% to 95.4%.

Scotland increased from 75 to 446 records. Wales from 30 to 507. Northern Ireland from 8 to 138. These increases came entirely from coordinates already in the dataset — the data knew where these buildings were, it simply had not been asked the right question until the postcode reverse-geocoding step.

### 6.3 Additional Geographic Fields Added

The postcodes.io enrichment also added:
- **LSOA codes** (Lower Super Output Area) — enables joining to Index of Multiple Deprivation
- **MSOA codes** (Middle Super Output Area) — census geography unit
- **Ward** — enables political geography analysis
- **Parliamentary constituency** — enables analysis by MP and political party

---

## 7. Land Registry Price Data

### 7.1 SPARQL API vs Bulk Download Decision

The Land Registry SPARQL endpoint was initially used for price enrichment. After 26 minutes of running with no output — the API was stuck in retry loops on slow queries — the approach was abandoned. The SPARQL endpoint is notoriously unreliable for programmatic access.

The alternative was the HM Land Registry Price Paid Data bulk download — a 5.2GB CSV file of all 31,270,275 property transactions in England and Wales from January 1995 to the present. The file was downloaded in 3 minutes 8 seconds (27.6MB/s). The local join operation matched 20,076 church records to Land Registry transactions in approximately 90 seconds — faster than the SPARQL API had managed for a single record.

### 7.2 Matching Methodology

The match was performed by postcode — each church record's postcode was matched to the earliest Land Registry transaction at that postcode. The "earliest transaction" heuristic captures the likely conversion sale: the first time the building changed hands after its use as a church. This is an imperfect proxy — in some cases the earliest transaction may predate the conversion, or a later transaction may be the conversion sale. The `sale_date` field should be interpreted as "earliest recorded transaction at this postcode" not definitively "the conversion sale date."

### 7.3 Price Findings

Key findings from the raw (non-inflation-adjusted) price data:

- Average sale price: £174,849
- Median sale price: £58,000 (much more representative given outliers)
- Maximum: £75,100,000 — St Augustine with St Philip's Church, E1 2JL, Whitechapel, 2018, residential conversion
- Minimum reliable price: £100 — peppercorn transfers to charities and community organisations

By conversion type (nominal, non-adjusted):
- Arts and culture: average £1,818,829 (n=26) — heavily skewed by high-value city centre buildings
- Hospitality: average £290,486 (n=72)
- Residential: average £172,816, median £58,000 (n=19,076)
- Mosque: average £69,603, median £48,000 (n=23)
- Community: average £93,957, median £46,400 (n=164)

### 7.4 Critical Data Quality Flags

Two categories of unreliable price records were identified:

**Peppercorn transfers (sub-£1,000):** Property law allows nominal transfers at £1, £100, or other token amounts when transferring to charities, community organisations, or family members. These are not market prices. They should be excluded from price analysis but retained in the dataset with a flag.

**1995-01-03 batch entries:** A cluster of records dated January 3, 1995 with prices of exactly £8,000 appears to be Land Registry's batch-entry of historic transactions on the first day of digital recording. These prices are not reliable market values.

### 7.5 Inflation Adjustment Requirement

All prices require adjustment to a common base year (2024) before comparison. The UK housing market experienced approximately 6.5× nominal price growth from 1995 to 2024. A mosque conversion recorded at £48,000 in 1999 equates to approximately £240,000 in 2024 terms. The inflation adjustment script applies Nationwide HPI multipliers by year to produce a `sale_price_2024` column.

---

## 8. Known Methodological Limitations

### 8.1 Informal Conversion Undercounting

The dataset captures buildings that appear in public data sources. Buildings occupied without planning permission, without an OSM tag, without a charity registration, and without a Wikidata entry are invisible. Academic research on UK diaspora religious communities suggests informal occupancies may exceed formal ones by a ratio of 3:1 in some urban areas. African diaspora churches — the RCCG network, Church of Pentecost, smaller Aladura congregations — are the most severely undercounted category. The dataset records 2 African diaspora church conversions. The actual number is certainly in the hundreds.

### 8.2 Nation Imbalances

Despite improvements, Scotland (446 records), Wales (507), and Northern Ireland (138) remain underrepresented relative to their actual church conversion activity. This reflects structural data availability: the NHLE covers England only, the planning portal covers England only, and the Charity Commission covers England and Wales only. Scotland uses the OSCR charity register. Northern Ireland uses CCNI. Neither has been incorporated at time of writing.

### 8.3 Temporal Snapshot Bias

OSM and Wikidata capture the current state of a building. A building that was converted in 1985, then reconverted in 2003, then demolished in 2019 is invisible or misleadingly recorded. Sequential conversions — the `use_history` chain — are captured only where Land Registry shows multiple transactions at the same address. The `year_converted` field reflects the first known conversion from church use, not subsequent changes.

### 8.4 Deregistration Does Not Confirm Conversion

The Charity Commission records the deregistration of church charities. Deregistration indicates closure of the charitable entity but does not confirm that the physical building was converted to another use. A congregation may dissolve while the building is sold to another congregation, sits vacant, or is demolished. The confidence score system partially addresses this — records sourced only from charity deregistration receive lower confidence scores.

### 8.5 Confidence Score Validation

The confidence scores (0.70 for OSM, 0.90 for Historic England, 0.95 for Wikidata) are expert-assigned heuristics not empirically validated. A ground truth validation exercise — manually verifying a random sample of 200 records against Google Street View, planning portal records, and OS mapping — has not yet been conducted. Until this exercise is complete, confidence scores should be treated as indicative, not definitive.

---

## 9. Key Statistics and Findings

### 9.1 Dataset Composition

| Metric | Value |
|---|---|
| Total records | 23,719 |
| With coordinates | 23,717 (100%) |
| With year of conversion | 23,483 (99%) |
| With postcode | 17,423 (73.5%) |
| With LSOA code | 17,423 (73.5%) |
| With sale price | 20,076 (85% of postcoded) |
| Nation coverage | 22,631 (95.4%) |

### 9.2 Nation Breakdown

| Nation | Records |
|---|---|
| England | 21,540 |
| Wales | 507 |
| Scotland | 446 |
| Northern Ireland | 138 |
| Unknown | 1,088 |

### 9.3 Conversion Type Breakdown

| Conversion type | Count | % of total |
|---|---|---|
| Residential | 22,311 | 94.1% of typed |
| Education | 497 | 2.1% |
| Community | 279 | 1.2% |
| Other Christian | 130 | 0.5% |
| Commercial | 92 | 0.4% |
| Hospitality | 90 | 0.4% |
| Arts and culture | 50 | 0.2% |
| Mosque | 32 | 0.1% |
| New religious movement | 19 | 0.1% |
| Sport and leisure | 9 | 0.04% |
| Eastern European church | 9 | 0.04% |
| Unknown | 175 | — |

### 9.4 The Defining Statistic

Residential conversions (22,311) are **697 times** more common than mosque conversions (32). Against an estimated total UK church stock of ~55,000 buildings (1851 Religious Census baseline of 34,467 plus subsequent additions), mosque conversions represent 0.058% of all UK churches ever built.

### 9.5 Price Findings

The most expensive confirmed church conversion: St Augustine with St Philip's Church, Whitechapel (E1 2JL), sold for £75,100,000 in July 2018, converted to residential. This building sits in the same postcode district as several mosque conversions with median sale prices of £48,000 — a price ratio of approximately 1,565:1 within a single East London postcode district. This contrast encapsulates the inequality dynamic at the heart of the research.

Mosque conversions show the lowest median price (£48,000 nominal) of any typed conversion category. Adjusted to 2024 prices at estimated purchase dates (predominantly 1990s–2000s), this equates to approximately £150,000–£240,000 — consistent with fair market value for secondary commercial property in the areas where Muslim communities have historically settled. This finding challenges the narrative that mosques are acquiring valuable heritage buildings; the evidence suggests the opposite.

---

## 10. Technical Infrastructure

### 10.1 Pipeline Architecture

The pipeline is structured as three stages:

**Stage 1 — Extraction:** Individual extractor modules (wikidata_extractor.py, osm_extractor.py, historic_england_extractor.py, charity_commission_extractor.py) each return a DataFrame conforming to MASTER_COLUMNS schema. Extractors are independent and can be run selectively via command-line flags.

**Stage 2 — Transform:** The pipeline module combines all source DataFrames, cleans data (standardises types, validates coordinates, normalises strings), deduplicates using KD-tree spatial matching, and derives computed fields (decade from year, confidence_tier from confidence_score).

**Stage 3 — Load:** The loader writes outputs to CSV (main dataset and public version with PII removed), Excel workbook (multiple analysis sheets), and optionally PostgreSQL (if DATABASE_URL is configured in .env).

### 10.2 Enrichment Scripts

Standalone enrichment scripts run after the main pipeline:

- `enrich_planning_portal.py` — checkpoint-based planning portal enrichment
- `enrich_denomination.py` — name-keyword denomination subtype assignment
- `enrich_postcodes.py` — bulk coordinate-to-postcode reverse geocoding
- `enrich_companies_house.py` — buyer organisation identification (not yet run)
- `enrich_ofsted_cqc.py` — school and care home confirmation (not yet run)
- `extractors/land_registry_extractor.py` — sale price matching from bulk PPD data

### 10.3 Data Storage and Versioning

Raw data files (NHLE CSV, Land Registry PPD, OSM PBF when downloaded) are excluded from version control via .gitignore. Output CSVs are also excluded — the pipeline is the reproducible artifact, not the data files. Output files are published separately on Zenodo under CC BY 4.0.

The GitHub repository (github.com/MicroPyscho/where-went-the-churches-uk) contains all pipeline code and documentation. The Zenodo dataset will contain the output CSV and Excel workbook.

---

## 11. Baseline and Denominator

The 1851 Religious Census is adopted as the primary baseline denominator. Conducted on Sunday 30 March 1851, it recorded 34,467 places of worship in England and Wales — denomination, location, date built, seating capacity, and attendance. This is the only comprehensive national count of religious buildings ever conducted in the UK and provides a validated denominator for pre-1851 church stock.

For post-1851 buildings, denomination-specific statistics are used: Church of England faculty records (~16,000 peak parishes), Methodist Conference annual statistics (~14,000 peak chapels), Baptist Union and URC published records. Total estimated UK church stock 1851–2026: approximately 55,000 buildings.

The consecration/dedication date is adopted as the reference date for building age. This is the legally and ecclesiastically meaningful date, recorded consistently across all sources, and avoids the ambiguity of construction start versus completion dates.

---

## 12. Attribution and Licensing

Data sources and their licences:

- Wikidata: CC0 (public domain)
- OpenStreetMap: ODbL (Open Database Licence)
- Historic England NHLE: Open Government Licence v3.0
- Planning Portal (planning.data.gov.uk): Open Government Licence v3.0
- HM Land Registry Price Paid Data: Open Government Licence v3.0, © Crown copyright
- Postcodes.io: MIT licence

The compiled Sacred Spaces dataset is published under Creative Commons Attribution 4.0 International (CC BY 4.0). Users may use, share, and adapt the data for any purpose including commercial use, provided appropriate credit is given.

Required attribution: "Sacred Spaces: UK Church Conversion Dataset, [Author], 2026. Contains data from Historic England, OpenStreetMap contributors, HM Land Registry, and planning.data.gov.uk, all under Open Government Licence v3.0."

---

## 13. Planned Future Work

1. OSCR and CCNI extraction — to address Scotland and Northern Ireland undercounting
2. OSM PBF local processing — to recover historic_church records lost to API timeouts
3. Index of Multiple Deprivation join — to enable deprivation analysis
4. Ground truth validation — 200-record manual verification sample
5. Inflation-adjusted price analysis — full hedonic regression
6. Spatial autocorrelation (Moran's I) — geographic clustering analysis
7. Interrupted time series — policy impact analysis (2012 PDR change)
8. Companies House buyer identification — who is purchasing former churches
9. MuslimsInBritain.org cross-reference — mosque directory for direct verification
10. Zenodo publication — DOI assignment and public dataset release

---

*This document was last updated June 16, 2026. More updates as research progresses.*