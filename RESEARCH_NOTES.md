# Sacred Spaces — Research Notes & Todo

## Status (June 15 2026)
- Pipeline: 23,690 records from Wikidata + OSM + Historic England
- Planning portal enrichment: ~14,000 records queried, running overnight
- Denomination taxonomy: constants.py expanded to 80+ subtypes
- Files updated: constants.py, osm_extractor.py, enrich_denomination.py

## Next steps (in order)
1. Let planning portal enrichment finish overnight
2. Run denomination enrichment: python enrich_denomination.py
3. Rerun pipeline: python main.py --sources wikidata --sources osm --sources historic_england --skip-geocode
4. Add Land Registry extractor (sale price, sale date, buyer name)
5. Add Companies House cross-reference (buyer type, SIC code, director origin)
6. Add OSCR (Scotland) and CCNI (Northern Ireland) charity registers
7. Add Ofsted register (schools in former churches)
8. Add CQC register (care homes, GP surgeries)
9. Ground truth validation — verify 200 records manually
10. Calculate denominator — total UK church stock by denomination

## Critical methodology gaps to document
- Informal conversions undercounted (no planning application, no OSM tag)
- Planning portal covers only ~60% of English LPAs
- Scotland severely undercounted (60 records vs hundreds actual)
- Northern Ireland essentially missing (8 records)
- OSM quality degrades in rural areas
- No denominator for conversion rates
- Confidence scores need empirical validation
- Deregistration ≠ confirmed conversion

## Key statistics for paper
- 32 mosque conversions = 1.5% of UK's 2,191 mosques
- Pubs outnumber mosques 2.2x
- Residential is largest category by far
- Community halls outnumber mosques 9:1
- Scientology confirmed portfolio: Manchester, Plymouth, Gateshead, Birmingham
- African diaspora churches likely most undercounted category

## Sources still to add
- Land Registry: https://landregistry.data.gov.uk/
- Companies House: https://developer.company-information.service.gov.uk/
- OSCR (Scotland): https://www.oscr.org.uk/
- CCNI (Northern Ireland): https://www.charitycommissionni.org.uk/
- Ofsted: https://api.ofsted.gov.uk/
- CQC: https://api.cqc.org.uk/
- OS Open UPRN: https://osdatahub.os.uk/
- MuslimsInBritain.org — 2,191 UK mosques directory
