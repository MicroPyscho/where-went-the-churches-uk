# Sacred Spaces: UK Church Conversion Dataset
## Technical Compendium & Methodology Documentation
**Version:** 1.0
**Date:** 2026-06-23
**Author:** Okereke Kelechi Collins
**Affiliation:** Independent researcher; MSc Applied Artificial Intelligence and Data Analytics (Distinction), University of Bradford
**GitHub:** https://github.com/MicroPyscho/where-went-the-churches-uk

---

## 1. Project Overview

Sacred Spaces is a systematic data research project tracking the transformation of UK religious buildings. The project assembles the first comprehensive, multi-source, nationally representative dataset of church building conversions across England, Wales, Scotland, and Northern Ireland.

The project was motivated by widespread public discourse claiming that churches are being converted to mosques at significant rates. The dataset was built to test this claim empirically against all other conversion types.

**Headline finding:** Residential conversion is 61 times more common than mosque conversion. Mosque conversions represent 0.436% of estimated UK church stock.

---

## 2. Research Questions

1. What are former UK church buildings becoming?
2. What is the true scale of church-to-mosque conversion relative to other conversion types?
3. In what kinds of areas do different conversion types occur (deprived vs affluent)?
4. Is the deprivation finding independent of Muslim population distribution?
5. How have conversion patterns changed over time?
6. What is the economic value of church conversions?

---

## 3. Repository and Links

| Resource | URL |
|----------|-----|
| GitHub | https://github.com/MicroPyscho/where-went-the-churches-uk |
| Historic England NHLE | https://historicengland.org.uk/listing/the-list/ |
| Historic Environment Scotland | https://portal.historicenvironment.scot/ |
| Cadw Wales | https://cadw.gov.wales/advice-support/cof-cymru |
| Historic Environment NI | https://www.communities-ni.gov.uk/hbni |
| OpenStreetMap Overpass | https://overpass-api.de/ |
| Land Registry Price Paid | https://www.gov.uk/government/statistical-data-sets/price-paid-data-downloads |
| Charity Commission E&W | https://register-of-charities.charitycommission.gov.uk/ |
| OSCR Scotland | https://www.oscr.org.uk/about-charities/search-the-register/ |
| CCNI Northern Ireland | https://www.charitycommissionni.org.uk/ |
| Companies House | https://find-and-update.company-information.service.gov.uk/ |
| MuslimsInBritain.org | http://www.muslimsinbritain.org/ |
| VOA Rating Lists | https://voaratinglists.blob.core.windows.net/html/rlidata.htm |
| EPC Non-Domestic | https://get-energy-performance-data.communities.gov.uk/ |
| Census 2021 Religion | https://www.nomisweb.co.uk/sources/census_2021_bulk |
| IMD 2019 England | https://www.gov.uk/government/statistics/english-indices-of-deprivation-2019 |
| Wikipedia UK Mosques | https://en.wikipedia.org/wiki/List_of_mosques_in_the_United_Kingdom |
| Guardian API | https://open-platform.theguardian.com/ |
| Postcodes.io | https://postcodes.io/ |
| planning.data.gov.uk | https://www.planning.data.gov.uk/ |

---

## 4. Dataset Files

| File | Size | Description |
|------|------|-------------|
| uk_church_conversions_20260616.csv | 29MB | Full master dataset, 54 columns |
| uk_church_conversions_20260616_PUBLIC.csv | 8.5MB | Clean public release, 23 columns |
| sacred_spaces_v1_complete.xlsx | 5.3MB | Excel workbook, 7 sheets |
| SUMMARY_REPORT.txt | 6.4KB | Headline findings |
| METHODOLOGY_UPDATE_20260622.md | 18KB | Session methodology log |
| SACRED_SPACES_COMPENDIUM.md | This file | Complete technical compendium |

---

## 5. Dataset Schema (54 columns)

| Column | Type | Description | Coverage |
|--------|------|-------------|----------|
| id | string | Unique 12-char record ID | 100% |
| church_name | string | Original building name | 82% |
| former_denomination | string | e.g. methodist, baptist, church_of_england | 71.5% |
| address | string | Street address | 78% |
| city | string | Town or city | 71% |
| local_authority | string | Council district | 89% |
| region | string | UK region | 89% |
| nation | string | England/Wales/Scotland/NI | 100% |
| latitude | float | WGS84 decimal degrees | 100% |
| longitude | float | WGS84 decimal degrees | 100% |
| postcode | string | UK postcode | 98.6% |
| lsoa | string | LSOA name (2021 boundaries) | 98.6% |
| msoa | string | MSOA name | 87% |
| ward | string | Electoral ward | 87% |
| parliamentary_constituency | string | Westminster constituency | 87% |
| conversion_type | string | Top-level category | 98.5% |
| conversion_subtype | string | Granular sub-classification | 45% |
| current_name | string | Current building name | 38% |
| year_converted | integer | Year of conversion | 63.1% |
| decade | string | e.g. 1990s, 2000s | 63.1% |
| source | string | Primary data source | 100% |
| confidence_score | float | 0.0-1.0 reliability rating | 76% |
| confidence_tier | string | high/medium/low | 76% |
| sale_price | integer | Land Registry sale price nominal | 61.9% |
| sale_price_2024 | float | Inflation-adjusted to 2024 | 42.5% |
| sale_date | date | Land Registry transaction date | 61.9% |
| imd_decile | integer | IMD 2019 decile (1=most deprived) | 63.7% |
| imd_rank | integer | IMD 2019 rank | 63.7% |
| muslim_pct | float | Percent Muslim in LSOA (Census 2021) | 76.4% |
| is_non_building_artifact | boolean | True if non-building structure | 15% |
| notes | string | Full enrichment audit trail | 100% |

---

## 6. Tools and Libraries

### Runtime
| Tool | Version |
|------|---------|
| Python | 3.13.13 |
| Operating System | macOS Sequoia (Apple Silicon) |

### Python Libraries
| Library | Version | Purpose |
|---------|---------|---------|
| pandas | 2.3.3 | Data manipulation |
| numpy | 2.4.4 | Numerical operations |
| scipy | 1.17.1 | Statistical tests |
| scikit-learn | 1.8.0 | Machine learning / clustering |
| statsmodels | 0.14.6 | Regression, confidence intervals |
| requests | 2.33.1 | HTTP API queries |
| openpyxl | 3.1.5 | Excel workbook generation |
| libpysal | latest | Spatial weights matrix |
| esda | latest | Moran's I spatial autocorrelation |
| tenacity | latest | API retry logic |

---

## 7. Raw Data Downloads

All files stored in data/raw/:

| File | Size | Source | Date |
|------|------|--------|------|
| muslimsinbritain_mosques.csv | ~2MB | muslimsinbritain.org | 2026-06-22 |
| voa_2026_listentries.zip | 87MB | VOA blob storage | 2026-06-22 |
| voa_2023_listentries.zip | 100MB | VOA blob storage | 2026-06-22 |
| voa_2017_listentries.zip | 132MB | VOA blob storage | 2026-06-22 |
| voa_2010_listentries.zip | 148MB | VOA blob storage | 2026-06-22 |
| epc_nondomestic.zip | ~500MB | MHCLG EPC portal | 2026-06-22 |
| census2021_religion_lsoa.zip | 3.4MB | Nomis/ONS | 2026-06-23 |
| imd_2019_lsoa.csv | ~5MB | MHCLG | 2026-06-16 |
| cadw_listedbuildings.json | 25.3MB | Cadw public API | 2026-06-16 |
| lsoa_name_to_code.csv | ~1MB | Derived from Census 2021 | 2026-06-23 |
| voa_2026_places_of_worship.csv | ~50MB | Extracted from VOA 2026 | 2026-06-22 |
| epc_places_of_worship.csv | ~15MB | Extracted from EPC zip | 2026-06-22 |

---

## 8. Pipeline Architecture

Stage 1 - Data Collection: NHLE + HES + Cadw + HENI + OSM + Wikidata
Stage 2 - Geocoding: postcodes.io coordinates, LSOA, ward, constituency
Stage 3 - Classification: OSM tags, Charity Commission, heritage CurrentUse, LR buyer type
Stage 4 - Mosque Verification: MiB cross-reference, Wikipedia, Guardian, Ahmadiyya
Stage 5 - Year Enrichment: Land Registry (9912), EPC (125), VOA epochs (51), Coflein (7)
Stage 6 - Unknown Resolution: HENI CurrentUse (37), Cadw (6), name patterns (442+)
Stage 7 - Statistical Analysis: IMD join, deprivation analysis, ITS, Kruskal-Wallis
Stage 8 - Outputs: Master CSV, Public CSV, Excel, Summary Report, Compendium

---

## 9. Complete Methodology

### 9.1 Building Identification

Six sources were used to identify former church buildings:

NHLE (Historic England): ~21,000 records. Listed buildings with Place of Worship primary use. Downloaded via bulk API. Grades I, II*, II included.

HES (Scotland): ~5,100 records. Categories A, B, C. Scottish listed buildings with cultural classification.

Cadw (Wales): ~3,000 records. BroadClass Religious, Ritual and Funerary. Downloaded as GeoJSON.

HENI (Northern Ireland): ~1,900 records. FormerUse and CurrentUse fields included — used directly for classification.

OpenStreetMap: ~5,847 records. amenity=place_of_worship OR building=church/chapel. Overpass API queries.

Wikidata: 157 records. Entities with replaces relationships involving churches. SPARQL endpoint.

### 9.2 Classification System

Conversion type assigned via hierarchical evidence system:

Tier 1 (confidence 0.90-0.99): OSM amenity tag, Charity Commission Islamic activities, NHLE/HENI CurrentUse, Wikipedia conversion statement.

Tier 2 (confidence 0.80-0.89): Land Registry buyer type, Companies House SIC code, Charity Commission general activities.

Tier 3 (confidence 0.65-0.79): OSM within 50m radius, postcode-level Land Registry flag.

### 9.3 Mosque Verification

All 240 mosque records verified through at least one independent source:
- MuslimsInBritain.org: 2,191 entries cross-referenced, 17 new mosques found
- Charity Commission: Islamic charity at same postcode
- Wikipedia: Building article states former church use
- Guardian API: 63 search queries, 1 new mosque (Clitheroe BB7 1AG)
- Ahmadiyya directory: 2 new mosques (Wolverhampton WV1 2HT, Plaistow E13 8BP)
- Historic searches: Shacklewell Lane E8 2DA, Madina Horsham RH12 1HL

### 9.4 Year Converted Enrichment

Route 1: Land Registry sale_date year extraction: +9,912 records
Route 2: EPC inspection_date by postcode match: +125 records
Route 3: VOA epoch estimate (last seen as church): +51 records
Route 4: Coflein/HENI report text extraction: +7 records
Route 5: Notes field text extraction: +2 records
Total: 20,470 records (63.1% coverage)

### 9.5 Denomination Enrichment

Regex pattern matching against 18 denomination keywords applied to church_name field. Rules applied in specificity order. Critical bug identified and corrected: keyword urc matched as substring of church, wrongly classifying 6,735 records as United Reformed Church. Fixed with word boundary matching.

Final coverage: 71.5% (23,193 records).

### 9.6 Unknown Resolution

Records with insufficient evidence for classification were resolved through:
- Reclassified-from-residential defaults (lr_prop_type_S): 1,129 resolved
- CoE parish company (02590933): 40 resolved
- Scotland/Wales/NI name patterns (20 rules): 442 resolved
- HENI CurrentUse field extraction: 37 resolved
- Coflein full report API: 6 resolved
- Cadw BroadClass mapping: 12 resolved
- Including rule (church is primary structure): 66 resolved
- OSM active church signal: 6 resolved
Remaining unknowns: 483 (472 Scotland, 7 Wales/NI/England, 4 OSM)

---

## 10. Statistical Methods

Kruskal-Wallis H-test: Non-parametric test of sale price differences across conversion types. Result: H=87.06, p<0.001 (significant).

Wilson Confidence Intervals: 95% CIs for mosque proportion (0.0074, CI: 0.0065-0.0084) and residential proportion (0.4536, CI: 0.4482-0.4590).

Interrupted Time Series: OLS regression testing 2012 PDR change (p=0.723, not significant) and 2008 financial crisis (p=0.004, significant decrease in residential volumes).

Deprivation Analysis: Median IMD decile by conversion type. Mosque=3.0, Residential=6.0 (3-decile difference).

Confounding Analysis: Census 2021 Muslim% by LSOA joined by LSOA name. Quartile-stratified comparison. Within Q4 (>1.83% Muslim, 82% of mosques): mosque IMD=2.0, residential IMD=4.0 (2-decile gap persists). Finding is partially confounded but holds within high-Muslim areas.

---

## 11. Known Limitations

1. Informal conversions undercounted: no planning/OSM/charity record means invisible to all methods.
2. Scotland SAA data costs 50 GBP per dataset: 472 Scottish unknowns unresolvable without payment.
3. Planning Portal incomplete: 100,627 records covering fraction of UK LPAs.
4. Land Registry proxy: year_converted is transaction date not physical conversion date for most residential records.
5. CE/CS charity numbers incompatible with Companies House API.
6. OSM tag staleness: converted buildings often retain church tags for months or years.
7. Confidence scores not empirically calibrated against independent ground truth.
8. Mosque undercount: buildings without any formal registration invisible to all methods.
9. Residential postcode duplicates: 352 records share postcodes but are separate listed structures.
10. year_converted gap concentrated in Scotland/Wales/NI and demolished/active-church records.

---

## 12. Criticism-Proofing Audit

| Criticism | Status | Finding |
|-----------|--------|---------|
| Mosque undercount - no planning search | Documented limitation | planning.data.gov.uk has only 100,627 records, patchy coverage |
| Residential overcount - flat counting | Not a significant issue | 352 records on 163 postcodes are separate listed structures |
| Deprivation confounded by Muslim population | Partially confounded | Finding holds within Q4 - 2 decile gap persists |
| Inter-rater reliability not tested | Manual verification recommended | OSM auto-validation invalid due to tag staleness |
| MCB/MINAB not cross-referenced | Not actionable | No public list; MiB already supersedes both |
| Welsh unknowns unresolved | 6 resolved, 67 irreducible | Coflein API queried for all 73 Cadw records |
| NI unknowns unresolved | 37 of 38 resolved | HENI CurrentUse fields extracted |
| Scotland unknowns | Documented limitation | HES portal is JS-rendered, no API access |
| Denomination URC bug | Fixed | 6,735 false positives corrected |

---

## 13. Changelog

### v1.0 (2026-06-23) - Current

Mosques: 32 to 240 (+208)
Residential:Mosque ratio: 701:1 to 61:1
Unknowns: 8,714 to 483 (94.5% resolution rate)
year_converted: 31.8% to 63.1%
former_denomination: 0% to 71.5%
IMD decile coverage: 0% to 63.7%
Muslim percent LSOA: 0% to 76.4%
Columns: 53 to 54
Records: 32,439 to 32,451

New mosque sources: MuslimsInBritain.org, Wikipedia, Guardian API, Ahmadiyya UK directory
Criticism-proofing: deprivation confounding analysis, residential duplicate audit, planning portal limitation, HENI CurrentUse extraction, Coflein API queries, denomination bug fix

### v0.1 (2026-06-16) - Initial pipeline run

First complete pipeline. 32 mosques. 8,714 unknowns. 32% year coverage.

---

## 14. Citation and Licence

Licence: Creative Commons Attribution 4.0 International (CC BY 4.0)

Suggested citation:
Okereke, K.C. (2026). Sacred Spaces: UK Church Conversion Dataset v1.0. [Dataset]. Zenodo. DOI: pending. GitHub: https://github.com/MicroPyscho/where-went-the-churches-uk

Attribution required. This dataset contains data from:
- Historic England NHLE, Open Government Licence v3.0
- OpenStreetMap contributors, ODbL
- HM Land Registry Price Paid Data, Open Government Licence v3.0
- Historic Environment Scotland, Open Government Licence
- Cadw Welsh Historic Monuments, Open Government Licence
- Historic Environment NI, Open Government Licence
- ONS Census 2021, Open Government Licence v3.0
- MHCLG IMD 2019, Open Government Licence v3.0
- Valuation Office Agency Rating Lists, Open Government Licence v3.0
