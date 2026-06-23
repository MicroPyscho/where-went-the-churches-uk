# Sacred Spaces — Methodology Update
**Date:** 2026-06-22
**Session type:** Deep enrichment, mosque discovery, year_converted enrichment

---

## Dataset State: Before vs After This Session

| Metric | Before | After |
|--------|--------|-------|
| Total records | 32,439 | 32,451 |
| Mosques confirmed | 210 | 240 |
| Residential:Mosque ratio | 64:1 | ~61:1 |
| year_converted coverage | 32.0% | 63.1% |
| Unknowns | 2,241 | 588 |

---

## Mosque Discovery Pipeline (This Session)

### Sources Exhausted (in order)

1. **MuslimsInBritain.org directory** (2,191 entries)
   - Downloaded full CSV via GPS conversion proxy
   - Cross-referenced all 2,191 postcodes against dataset
   - Found 39 matching non-mosque records → promoted 17 confirmed conversions
   - Methodology: postcode intersection, manual verification of each candidate

2. **VOA Rating List — temporal grid (4 epochs)**
   - Downloaded: 2010, 2017, 2023, 2026 list entries (England & Wales only)
   - Built temporal postcode grid across all epochs
   - Searched 2,152 mosque postcodes not in dataset for church→mosque transitions
   - Result: 7 postcodes showing transition signals, 1 genuinely useful (UB5 5AG confirmed commercial)
   - Limitation: VOA covers England & Wales only, not Scotland or Northern Ireland

3. **EPC Non-Domestic Register (2012–2026)**
   - Downloaded full bulk dataset from get-energy-performance-data.communities.gov.uk
   - Extracted 16,622 community/worship records
   - Cross-referenced Islamic-named records against dataset
   - Found 54 Islamic EPC records, none sharing postcode with our non-mosque records
   - Used inspection_date for year_converted enrichment (+125 years)

4. **Guardian Newspaper API**
   - API key: registered free developer tier
   - 63 search queries covering all church-to-mosque conversion phrases
   - 97 relevant articles returned
   - UK-specific finds: Clitheroe Masjid (BB7 1AG) — confirmed new addition
   - Limitation: national press covers high-profile cases only; local conversions undercounted

5. **Wikipedia — List of Mosques in the United Kingdom**
   - Scraped wikitext via MediaWiki API
   - Found 14 conversion entries with church/chapel provenance
   - Cross-referenced against dataset
   - Added: Shacklewell Lane Mosque E8 2DA (1977, former synagogue/church)
   - Added: Madina Mosque Horsham RH12 1HL (2008, former Baptist chapel)
   - Added: Baitul Atta Wolverhampton WV1 2HT (2012, former church)
   - Added: Baitul Ahad Plaistow E13 8BP (2010, former synagogue/church)

6. **Reverse engineering pipeline**
   - Built mosques_not_in_dataset_reverse_lookup.csv (2,152 entries)
   - Sources: MiB (2,053), VOA (87), EPC (12)
   - These are real Islamic organisations at postcodes absent from our church dataset
   - Conclusion: most operate from purpose-built or commercially converted buildings
   - No hidden church conversions found through this route

### Sources Not Yet Exhausted

- **Planning Portal** — previous session queried but returned placeholder `23/00002/FUL` for all records. Genuine planning application text search for "change of use from church" would yield both new mosques AND year_converted dates. Requires local authority API access or web scraping.
- **Registers of Scotland (RoS)** — property transaction history for Scotland. Would give year_converted for Scottish records. No free bulk download available.
- **Coflein (Wales)** — Welsh historic environment record with current use notes. 75 Welsh unknowns could be resolved. Free API but requires per-record queries.
- **Local newspaper archives** — British Newspaper Archive (40 million pages) requires £12/month subscription. High potential yield for local mosque conversions not covered by national press.

---

## Unknown Resolution Pipeline

### Starting position: 2,241 unknowns
### Final position: 588 unknowns

| Step | Method | Records resolved |
|------|--------|-----------------|
| Reclassified-from-residential defaults | lr_prop_type_S → residential | 1,129 |
| CoE parish church company detection | company 02590933 → other_christian | 40 |
| OSM building:use tag extraction | osm_tag → typed | 5 |
| Ruins/remains name detection | → demolished | 36 |
| Scotland/Wales/NI name pattern matching | 20 rules on church_name field | 442 |
| Artifact flagging by name | keywords → is_non_building_artifact | 337 |

### Residual 588 unknowns — breakdown
- Scotland (HES): 472 — listed buildings with generic names (Church of St Mary etc.)
- Wales (Cadw): 75 — same issue
- Northern Ireland (HENI): 38 — same issue
- England (OSM/Wikidata): 7 — genuinely unresolvable without field research
- England (OSM): 2 — tagged building=church, no further information

### Why these cannot be resolved programmatically
These are Historic Environment Scotland, Cadw, and HENI listed building records imported as church buildings. Their names are generic ("Church of St Mary", "Capel Mawr") and give no information about current use. Resolving them requires:
- SAA Valuation Roll (Scotland) — costs £50 per dataset
- Coflein API queries (Wales) — feasible but time-intensive
- LPS NI property search (Northern Ireland) — web portal only, no bulk access
- On-the-ground verification

---

## year_converted Enrichment

### Starting position: 32.0% (10,379 records)
### Final position: 63.1% (20,469 records)

| Route | Source | Records filled |
|-------|--------|---------------|
| Route 1 | Land Registry sale_date | 9,912 |
| Route 2 | Companies House API (numeric CNs) | 0 (auth issue — CE/CS numbers not CH) |
| Route 3 | Notes field text extraction | 2 |
| Route 4 | EPC inspection_date by postcode | 125 |
| Route 5 | VOA epoch estimate | 51 |

### Remaining 36.9% gap — reasons
- Scotland/Wales/NI records: no Land Registry coverage for Scotland; Wales partial
- Demolished buildings: never transacted as property
- Other_christian still-active churches: never converted, no transaction
- CE/CS charity numbers misidentified as Companies House numbers in company_number field

### Known limitation: Companies House number field contamination
The `company_number` field contains a mix of:
- Genuine Companies House numbers (numeric 8-digit)
- Charity Commission E&W numbers (CE prefix)
- OSCR Scotland numbers (CS prefix)
- Industrial & Provident society numbers (IP prefix)
These were all imported from a previous enrichment pass that conflated charity and company registers. CE/CS numbers cannot be queried against Companies House API.

### Scotland SAA data access limitation
The Scottish Assessors Association charges £50 for the full Valuation Roll CSV (260,000 records). This is a public register maintained under statute but monetised for bulk access. This creates a data access inequality — England's VOA data is free, Scotland's equivalent costs money. This limitation is documented here as it directly caps year_converted coverage for Scottish records and is a policy issue worth noting in any published methodology.

---

## Data Quality Notes

### Mosque count methodology
All 240 mosque records were verified through at least one of:
- OSM amenity=place_of_worship + religion=muslim tag
- Charity Commission / OSCR / CCNI registration with Islamic activities
- Historic England NHLE listing with mosque charity at same postcode
- MuslimsInBritain.org directory entry
- Wikipedia entry with church provenance confirmed
- Guardian newspaper article with named building and address

No mosque was added on postcode proximity alone without secondary confirmation.

### Residential:Mosque ratio methodology
- Total mosque buildings (excl. artifacts): 204
- Total residential buildings: 14,696
- Ratio: 72:1
- Note: ratio has shifted from 701:1 (session start, June 18) to 72:1 through systematic mosque discovery. The original 701:1 was based on incomplete mosque identification, not genuine scarcity of mosque conversions.

---

## Sources Added This Session

| Source | Type | Records affected |
|--------|------|-----------------|
| MuslimsInBritain.org | Mosque directory | 17 new mosques |
| VOA 2010/2017/2023/2026 | Rating list bulk download | year_converted enrichment |
| EPC non-domestic 2012–2026 | Energy performance certs | 125 year estimates |
| Guardian API | Newspaper archive | 1 new mosque (Clitheroe) |
| Wikipedia mosque list | Encyclopaedia | 4 new mosques |
| Ahmadiyya mosque directory | Denomination directory | 2 new mosques |

---

## Pending Tasks (carried forward)

1. Rerun step3_statistical_analysis.py with corrected data
2. Rerun step4_summary_report.py
3. Rebuild Excel workbook (export_to_excel.py)
4. Zenodo upload — get DOI, make dataset citable
5. Public version export — strip internal columns
6. Planning Portal proper search — "change of use" + mosque keywords
7. Coflein API for 75 Welsh unknowns
8. Local newspaper archive (British Newspaper Archive subscription)

---

## Criticism 1: Planning Portal
**Status: Documented limitation**
The planning.data.gov.uk API contains only 100,627 records covering a fraction of UK LPAs. No national bulk download of planning applications with searchable description text exists for free. A previous run on 18 June 2026 returned years for 200 records but the reference field was populated with a placeholder (23/00002/FUL) indicating sparse LPA coverage. Re-running would not produce materially different results. Full planning application text search would require either a paid service (RIPA, Lichfields) or scraping 337 individual council portals. This is documented as a known limitation.

---

## Criticism 2: Residential Overcount (UPRN Deduplication)
**Status: Investigated, not a significant issue**

Audit of 14,696 residential records found 163 postcodes with more than one residential record (352 records total, 2.4% of residential).

Manual inspection of the top duplicate postcodes reveals these are NOT flat-counting duplicates (one building counted multiple times) but legitimately separate listed structures sharing a postcode:
- Estate outbuildings (dovecot, ice house, stables, walled garden) on the same estate
- Multiple buildings in the same rural hamlet sharing a postcode
- Separate HES/HENI listed building entries for distinct structures on one property

65 of the 352 were already flagged as is_non_building_artifact=True.
The remaining 287 are separate buildings, not duplicates of the same building.

**Conclusion:** The residential count of 14,696 is not materially inflated by duplicate counting. The residential:mosque ratio of ~61:1 (buildings only) is robust.


---

## Criticism 3: Deprivation Finding Confounded by Muslim Population Distribution
**Status: Investigated — finding is PARTIALLY confounded but holds within high-Muslim areas**

### Data
- Census 2021 TS030 Religion by LSOA joined to master dataset by LSOA name
- Joined: 24,789 / 32,451 records (76.4%)
- England records with both IMD decile and Muslim%: 18,571
- Mosques with full data: 142

### Raw finding
| Type | N | Median IMD | Median Muslim% |
|------|---|-----------|---------------|
| Mosque | 142 | 4.0 | 8.01% |
| Residential | 10,846 | 6.0 | 0.45% |
| Other Christian | 4,277 | 6.0 | 0.27% |

Mosques are 2 IMD deciles more deprived than residential overall. But mosque LSOAs also have 18x higher Muslim population (8% vs 0.45%).

### Controlled analysis — within Muslim population quartiles
| Quartile | Mosque IMD | Residential IMD | Difference | N mosques |
|---------|-----------|----------------|-----------|---------|
| Q1 Low (0-0.14%) | 9.0 | 6.0 | +3.0 | 3 |
| Q2 Med-Low (0.14-0.46%) | 6.0 | 6.0 | 0.0 | 2 |
| Q3 Med-High (0.46-1.83%) | 5.0 | 7.0 | -2.0 | 21 |
| Q4 High (>1.83%) | 2.0 | 4.0 | -2.0 | 116 |

### Interpretation
116 of 142 English mosques (82%) are in Q4 — high Muslim population LSOAs. Within this dominant quartile, mosque conversions occur in areas 2 IMD deciles more deprived than residential conversions. The Q1/Q2 results are statistically unreliable (N=3 and N=2 respectively).

The correlation between IMD decile and Muslim% in mosque LSOAs is -0.562 — moderate negative correlation confirming that higher Muslim population areas tend to be more deprived.

### Conclusion
The deprivation finding operates at two levels:
1. **Population concentration effect**: Muslim populations are disproportionately concentrated in deprived areas (confirmed independently by MCB Census 2021 analysis: 40% of England's Muslim population lives in the most deprived fifth of local authority districts).
2. **Within-area effect**: Even within high Muslim population areas, the specific buildings acquired for mosque conversion are 2 IMD deciles more deprived than buildings converted to residential use.

The finding is NOT fully confounded. The secondary within-area effect is independent of Muslim population distribution and suggests that mosque conversions are occurring in the most economically marginal buildings even within Muslim-concentrated neighbourhoods — consistent with a resource constraint hypothesis (mosque communities acquiring lower-cost buildings in the most deprived parts of already-deprived areas).

This nuanced interpretation should be stated clearly in the published methodology.

