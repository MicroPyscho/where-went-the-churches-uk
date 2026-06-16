"""
constants.py — Master schema, conversion taxonomy, and shared config
for the UK Church Conversion Pipeline

EXPANDED VERSION — full denomination taxonomy, 80+ subtypes
"""

# ─── MASTER SCHEMA ──────────────────────────────────────────────────────────

MASTER_COLUMNS = [
    # ── Core identity ──────────────────────────────────────────────────────
    "id",                       # Unique 12-char MD5 hash
    "church_name",              # Original name of the church
    "former_denomination",      # CoE, Methodist, Baptist etc.
    "address",                  # Street address
    "city",                     # Town or city
    "local_authority",          # Council / Local Authority District
    "region",                   # e.g. North West, Yorkshire
    "nation",                   # England / Wales / Scotland / Northern Ireland
 
    # ── Location ───────────────────────────────────────────────────────────
    "latitude",
    "longitude",
 
    # ── Conversion classification ──────────────────────────────────────────
    "conversion_type",          # Top-level: mosque, residential, hospitality etc.
    "conversion_subtype",       # Granular: rccg, sunni_deobandi, climbing_wall etc.
    "current_name",             # What the building is called now
 
    # ── Temporal ───────────────────────────────────────────────────────────
    "year_converted",           # Year of first conversion from church use
    "decade",                   # e.g. "1990s"
    "sale_date",                # Exact sale date from Land Registry (YYYY-MM-DD)
    "sale_price",               # Sale price in GBP from Land Registry
 
    # ── Use chain (sequential conversions) ─────────────────────────────────
    "use_history",              # JSON: [{use, year, price, tenure}, ...] oldest first
 
    # ── Buyer / organisation identity ─────────────────────────────────────
    "buyer_name",               # Buyer name from Land Registry
    "company_number",           # Companies House number
    "company_type",             # ltd, charity, plc, llp etc.
    "sic_code",                 # Industry code (94910 = religious orgs)
    "incorporated_country",     # Country of incorporation (reveals diaspora orgs)
 
    # ── Regulatory confirmation ────────────────────────────────────────────
    "ofsted_urn",               # Ofsted URN if school/nursery
    "cqc_id",                   # CQC location ID if care/health use
    "inspection_rating",        # Ofsted/CQC rating: Outstanding/Good/RI/Inadequate
 
    # ── Source & quality ───────────────────────────────────────────────────
    "source",                   # wikidata, osm, historic_england etc.
    "source_url",               # Direct URL to source record
    "confidence_score",         # 0.0–1.0 reliability
    "confidence_tier",          # high / medium / low (derived)
    "notes",                    # Extra context, methodology notes
]


# ─── FULL CONVERSION TAXONOMY ────────────────────────────────────────────────
# conversion_type → list of conversion_subtype values
# Every subtype must belong to exactly one type.

CONVERSION_TAXONOMY = {

    # ── MOSQUE ────────────────────────────────────────────────────────────────
    "mosque": [
        "sunni_deobandi",           # South Asian Sunni — largest strand, Bradford, Leicester
        "sunni_barelwi",            # South Asian Sunni Sufi-influenced
        "sunni_salafi",             # Middle Eastern influenced, 9% of UK mosques
        "sunni_arab_african",       # Arab / West African Sunni mainstream
        "sunni_somali",             # Somali community mosques — London, Manchester, Leicester
        "sunni_tablighi",           # Tablighi Jamaat centres
        "shia_twelver",             # Iranian, Iraqi, Lebanese Shia
        "shia_ismaili",             # Aga Khan network
        "ahmadiyya",                # Ahmadiyya Muslim Community — distinct sect
        "islamic_centre",           # Multi-purpose Islamic centres
        "madrasa",                  # Islamic school / educational centre
        "muslim_community_centre",  # Community/welfare focused
        "mosque_general",           # Mosque — denomination unknown
    ],

    # ── OTHER FAITH — AFRICAN DIASPORA CHRISTIAN ─────────────────────────────
    "african_diaspora_church": [
        "rccg",                     # Redeemed Christian Church of God — Nigerian, 800+ UK parishes
        "winners_chapel",           # Living Faith / Winners Chapel — David Oyedepo
        "christ_embassy",           # Christ Embassy — Chris Oyakhilome
        "mountain_of_fire",         # Mountain of Fire & Miracles (MFM) — Nigerian
        "deeper_life",              # Deeper Life Bible Church — William Kumuyi
        "house_on_the_rock",        # House on the Rock — Islington confirmed purchase
        "cherubim_seraphim",        # Cherubim & Seraphim / Aladura — West African
        "celestial_church",         # Celestial Church of Christ — Beninese origin
        "church_of_pentecost",      # Church of Pentecost — Ghanaian, hundreds of UK branches
        "icgc",                     # International Central Gospel Church — Mensa Otabil
        "action_chapel",            # Action Chapel International — Ghanaian
        "lighthouse_chapel",        # Lighthouse Chapel International — Ghanaian
        "zaoga_forward_faith",      # ZAOGA / Forward in Faith — Zimbabwean
        "uckg",                     # Universal Church Kingdom of God — Brazilian/Black British
        "ethiopian_orthodox",       # Ethiopian Orthodox Tewahedo — buying Anglican buildings
        "eritrean_orthodox",        # Eritrean Orthodox Tewahedo
        "congolese_church",         # EJCSK, Combat Spirituel — Congolese/Central African
        "african_apostolic",        # Apostolic Church Nigeria, Christ Apostolic Church
        "african_church_general",   # African diaspora church — specific org unknown
    ],

    # ── OTHER FAITH — CARIBBEAN CHRISTIAN ────────────────────────────────────
    "caribbean_church": [
        "ntcg",                     # New Testament Church of God — Jamaican, 1950s first wave
        "church_of_god_prophecy",   # Church of God of Prophecy — Caribbean
        "seventh_day_adventist",    # Seventh-day Adventist — large Caribbean membership
        "wesleyan_holiness",        # Wesleyan Holiness Church — Caribbean
        "caribbean_church_general", # Caribbean diaspora church — specific org unknown
    ],

    # ── OTHER FAITH — EASTERN EUROPEAN CHRISTIAN ─────────────────────────────
    "eastern_european_church": [
        "ukrainian_orthodox",       # Ukrainian Orthodox — Bradford confirmed (Historic England)
        "ukrainian_catholic",       # Ukrainian Greek Catholic/Uniate — growing post-2022
        "polish_catholic",          # Polish Catholic Mission — largest Eastern European network
        "romanian_orthodox",        # Romanian Orthodox — rapid expansion 2024
        "romanian_catholic",        # Romanian Greek Catholic
        "russian_orthodox_rocor",   # Russian Orthodox Church Outside Russia
        "serbian_orthodox",         # Serbian Orthodox
        "bulgarian_orthodox",       # Bulgarian Orthodox
        "eastern_european_general", # Eastern European church — specific nation unknown
    ],

    # ── OTHER FAITH — MIDDLE EASTERN CHRISTIAN ───────────────────────────────
    "middle_eastern_church": [
        "coptic_orthodox",          # Egyptian Coptic — significant London presence
        "assyrian_chaldean",        # Assyrian / Chaldean — Iraqi Christian communities
        "maronite_catholic",        # Maronite — Lebanese community
        "syriac_orthodox",          # Syriac Orthodox
        "armenian_apostolic",       # Armenian Apostolic Church
        "middle_eastern_general",   # Middle Eastern Christian — specific tradition unknown
    ],

    # ── OTHER FAITH — EAST ASIAN CHRISTIAN ───────────────────────────────────
    "east_asian_church": [
        "korean_presbyterian",      # Korean Presbyterian — very active in London
        "chinese_christian",        # Chinese Christian churches — Cantonese/Mandarin
        "filipino_catholic",        # Filipino Catholic — El Shaddai, diaspora congregations
        "south_korean_missionary",  # Prayer Mission UK, Yoido Full Gospel branches
        "east_asian_general",       # East Asian church — specific origin unknown
    ],

    # ── OTHER FAITH — SOUTH ASIAN ─────────────────────────────────────────────
    "south_asian_faith": [
        "sikh_gurdwara",            # Sikh gurdwara — mainstream Singh Sabha
        "ravidassia",               # Ravidassia — dalit Sikh community, growing fast
        "sikh_other",               # Nihang, Namdharis, other Sikh sects
        "iskcon",                   # ISKCON / Hare Krishna — significant building portfolio
        "swaminarayan_baps",        # BAPS Swaminarayan — Gujarati, mostly purpose-built
        "hindu_mandir",             # Sanatan Hindu mandirs — mainstream
        "tamil_hindu",              # Tamil Hindu temples — distinct from North Indian
        "jain_centre",              # Jain community centres — Leicester, London
        "south_asian_general",      # South Asian faith — specific tradition unknown
    ],

    # ── OTHER FAITH — NEW RELIGIOUS MOVEMENTS ────────────────────────────────
    "new_religious_movement": [
        "scientology",              # Church of Scientology — confirmed: Manchester, Plymouth,
                                    # Gateshead, Birmingham, East Grinstead portfolio
        "jehovahs_witness",         # Jehovah's Witnesses Kingdom Halls — systematic acquirers
        "mormon_lds",               # Church of Jesus Christ of Latter-day Saints
        "new_apostolic",            # New Apostolic Church
        "christadelphians",         # Christadelphians
        "spiritualist",             # Spiritualist churches / National Spiritualist Union
        "unification_church",       # Unification Church / Moonies
        "nrm_general",              # New religious movement — specific org unknown
    ],

    # ── OTHER FAITH — COUNTER-CULTURAL / ESOTERIC ────────────────────────────
    "esoteric_occult": [
        "pagan_wiccan",             # Pagan / Wiccan temple spaces
        "druid_grove",              # Druid groves / Order of Bards, Ovates & Druids
        "satanic_temple",           # The Satanic Temple UK — non-theistic, civil rights focus
        "lavey_satanism",           # Church of Satan / LaVeyan Satanism
        "occult_lodge",             # Hermetic Order of Golden Dawn lineage, ceremonial magic
        "esoteric_general",         # Esoteric/occult — specific tradition unknown
    ],

    # ── OTHER FAITH — EASTERN PHILOSOPHY / MINDFULNESS ───────────────────────
    "eastern_philosophy": [
        "buddhist_tibetan",         # Tibetan Buddhist centres — Kagyu, Gelug, Nyingma
        "buddhist_theravada",       # Theravada Buddhist — Thai, Sri Lankan, Burmese
        "buddhist_zen",             # Zen / Soto / Rinzai
        "buddhist_general",         # Buddhist — tradition unknown
        "meditation_centre",        # Secular meditation / mindfulness centres
        "yoga_studio",              # Yoga studios with spiritual emphasis
        "transcendental_meditation", # TM centres
        "eastern_philosophy_general",
    ],

    # ── OTHER FAITH — PENTECOSTAL / EVANGELICAL (non-African specific) ────────
    "pentecostal_evangelical": [
        "pentecostal_general",      # Pentecostal — origin unknown
        "evangelical_general",      # Evangelical / charismatic
        "new_frontiers",            # Newfrontiers / Catalyst churches
        "vineyard",                 # Vineyard churches
        "elim_pentecostal",         # Elim Pentecostal Church — significant UK network
        "assemblies_of_god",        # Assemblies of God
        "hillsong",                 # Hillsong — Australian origin
        "alpha_church",             # Holy Trinity Brompton / Alpha Course associated
    ],

    # ── OTHER FAITH — OTHER CHRISTIAN ─────────────────────────────────────────
    "other_christian": [
        "methodist_reuse",          # Bought by different Methodist congregation
        "baptist_reuse",            # Bought by Baptist congregation
        "salvation_army",           # Salvation Army citadels
        "quaker_meeting_house",     # Society of Friends
        "roman_catholic_reuse",     # Bought by Roman Catholic parish
        "greek_orthodox",           # Greek Orthodox — Ecumenical Patriarchate
        "other_christian_general",  # Christian — denomination unknown
    ],

    # ── RESIDENTIAL ───────────────────────────────────────────────────────────
    "residential": [
        "luxury_apartments",        # High-end residential conversion — common in listed buildings
        "converted_flats",          # Standard residential conversion
        "single_dwelling",          # Single family home
        "student_housing",          # Purpose student accommodation
        "care_home",                # Residential care / nursing home
        "supported_housing",        # Supported housing — care leavers, mental health etc.
        "homeless_shelter",         # Night shelter / emergency accommodation
        "refugee_housing",          # Refugee / asylum seeker accommodation
        "holiday_let",              # Airbnb / holiday let — "stay in a church"
        "residential_general",      # Residential — type unknown
    ],

    # ── HOSPITALITY ───────────────────────────────────────────────────────────
    "hospitality": [
        "pub",                      # Public house
        "bar",                      # Bar / cocktail bar
        "nightclub",                # Nightclub / music venue
        "restaurant",               # Restaurant / brasserie
        "cafe",                     # Café / coffee shop
        "hotel",                    # Hotel
        "hostel",                   # Hostel / budget accommodation
        "wedding_venue",            # Wedding / events venue
        "microbrewery",             # Craft brewery / micropub
        "wine_bar",                 # Wine bar
        "hospitality_general",      # Hospitality — specific type unknown
    ],

    # ── ARTS & CULTURE ────────────────────────────────────────────────────────
    "arts_culture": [
        "theatre",                  # Theatre / playhouse
        "cinema",                   # Cinema / movie theatre
        "arts_centre",              # Arts centre / multi-use arts space
        "gallery",                  # Art gallery / exhibition space
        "museum",                   # Museum / heritage attraction
        "concert_hall",             # Concert hall / music venue
        "recording_studio",         # Recording studio — The Church Studios Crouch End (Eurythmics/Adele)
        "creative_workspace",       # Creative coworking / studios
        "bookshop",                 # Bookshop / literary venue
        "arts_culture_general",     # Arts/culture — specific type unknown
    ],

    # ── EDUCATION ─────────────────────────────────────────────────────────────
    "education": [
        "school",                   # Primary / secondary school
        "academy",                  # Academy / free school
        "university",               # University / higher education
        "college",                  # Further education college
        "library",                  # Public library
        "nursery",                  # Nursery / childcare
        "islamic_school",           # Madrasa / Islamic school
        "community_education",      # Community education / adult learning
        "education_general",        # Education — type unknown
    ],

    # ── COMMUNITY & SOCIAL ────────────────────────────────────────────────────
    "community": [
        "community_centre",         # General community centre / village hall
        "lgbtq_centre",             # LGBTQ+ community centre / Pride hub
        "food_bank",                # Food bank / food pantry
        "youth_centre",             # Youth club / youth centre
        "nhs_health_centre",        # NHS / GP surgery / health centre
        "drug_rehabilitation",      # Drug / alcohol rehabilitation centre
        "citizens_advice",          # Citizens Advice / welfare support
        "diaspora_community_hub",   # Ethnic / diaspora community hub (non-religious)
        "refugee_community_centre", # Refugee / asylum seeker community centre
        "sports_hall",              # Community sports hall
        "charity_hub",              # Charity offices / third sector hub
        "community_general",        # Community — specific use unknown
    ],

    # ── COMMERCIAL ────────────────────────────────────────────────────────────
    "commercial": [
        "office",                   # Office / professional services
        "coworking",                # Coworking / shared workspace
        "retail_shop",              # Retail shop / store
        "supermarket",              # Supermarket — Tesco Express, Co-op in former chapels
        "storage",                  # Self-storage / warehouse
        "funeral_parlour",          # Funeral home — solemn architecture fits
        "print_media_studio",       # Print works / media studio
        "data_centre",              # Data centre / server farm — thick walls, high ceilings
        "antique_centre",           # Antique centre / market
        "commercial_general",       # Commercial — specific type unknown
    ],

    # ── SPORT & LEISURE ───────────────────────────────────────────────────────
    "sport_leisure": [
        "climbing_wall",            # Indoor climbing — Bristol St Werburgh's 1992 (UK's first)
                                    # Manchester Climbing Centre; Kilmarnock Above Adventure
        "skate_park",               # Skate park — Skaterham Surrey (confirmed UK)
        "gym_fitness",              # Gym / fitness centre
        "trampoline_park",          # Trampoline park
        "paintball_lasertag",       # Paintball / laser tag
        "escape_room",              # Escape room
        "bowling_alley",            # Bowling alley
        "dance_studio",             # Dance studio / performing arts
        "martial_arts",             # Martial arts / boxing gym
        "swimming_pool",            # Swimming pool / leisure centre
        "sport_leisure_general",    # Sport/leisure — specific type unknown
    ],

    # ── TOURISM & HERITAGE ────────────────────────────────────────────────────
    "tourist": [
        "heritage_attraction",      # Heritage visitor attraction
        "heritage_centre",          # Heritage / interpretation centre
        "visitor_centre",           # Tourist / visitor centre
        "scout_guide_hut",          # Scout / guide / cadet facility
        "tourist_general",          # Tourism — specific type unknown
    ],

    # ── CIVIC & GOVERNMENT ────────────────────────────────────────────────────
    "civic": [
        "council_offices",          # Local council / government offices
        "police_station",           # Police station
        "court",                    # Court / legal facility
        "fire_station",             # Fire station
        "civic_general",            # Civic — specific type unknown
    ],

    # ── TECHNOLOGY ────────────────────────────────────────────────────────────
    "technology": [
        "data_centre_tech",         # Data centre / server infrastructure
        "tech_hub",                 # Technology hub / incubator
    ],

    # ── DEMOLISHED ────────────────────────────────────────────────────────────
    "demolished": [
        "demolished_housing",       # Cleared for housing development
        "demolished_commercial",    # Cleared for commercial development
        "demolished_cleared",       # Demolished — replacement unknown
    ],

    # ── VACANT ────────────────────────────────────────────────────────────────
    "vacant": [
        "derelict",                 # Abandoned / derelict
        "mothballed",               # Closed but maintained — awaiting use
        "churches_conservation_trust", # CCT — preserved but not in active community use
        "vacant_general",           # Vacant — status unknown
    ],

    # ── UNKNOWN ───────────────────────────────────────────────────────────────
    "unknown": [
        "unknown",
    ],
}


# Flat lookup: subtype → parent type
SUBTYPE_TO_TYPE = {
    sub: parent
    for parent, subs in CONVERSION_TAXONOMY.items()
    for sub in subs
}

ALL_CONVERSION_TYPES = list(CONVERSION_TAXONOMY.keys())


# ─── OSM DENOMINATION TAG → SUBTYPE MAP ──────────────────────────────────────
# Maps OSM denomination= tag values to our taxonomy

OSM_DENOMINATION_MAP = {
    # Islamic
    "sunni":                ("mosque", "mosque_general"),
    "shia":                 ("mosque", "shia_twelver"),
    "shi'a":                ("mosque", "shia_twelver"),
    "ahmadiyya":            ("mosque", "ahmadiyya"),
    "ismaili":              ("mosque", "shia_ismaili"),
    "deobandi":             ("mosque", "sunni_deobandi"),
    "barelwi":              ("mosque", "sunni_barelwi"),
    "salafi":               ("mosque", "sunni_salafi"),
    "tablighi":             ("mosque", "sunni_tablighi"),

    # African diaspora
    "rccg":                             ("african_diaspora_church", "rccg"),
    "redeemed":                         ("african_diaspora_church", "rccg"),
    "pentecostal":                      ("pentecostal_evangelical", "pentecostal_general"),
    "apostolic":                        ("pentecostal_evangelical", "pentecostal_general"),
    "charismatic":                      ("pentecostal_evangelical", "evangelical_general"),

    # Eastern European
    "ukrainian_orthodox":               ("eastern_european_church", "ukrainian_orthodox"),
    "ukrainian_catholic":               ("eastern_european_church", "ukrainian_catholic"),
    "greek_catholic":                   ("eastern_european_church", "ukrainian_catholic"),
    "roman_catholic":                   ("other_christian", "roman_catholic_reuse"),
    "romanian_orthodox":                ("eastern_european_church", "romanian_orthodox"),
    "russian_orthodox":                 ("eastern_european_church", "russian_orthodox_rocor"),
    "serbian_orthodox":                 ("eastern_european_church", "serbian_orthodox"),
    "coptic":                           ("middle_eastern_church", "coptic_orthodox"),
    "armenian":                         ("middle_eastern_church", "armenian_apostolic"),

    # South Asian faith
    "sikh":                             ("south_asian_faith", "sikh_gurdwara"),
    "hindu":                            ("south_asian_faith", "hindu_mandir"),
    "jain":                             ("south_asian_faith", "jain_centre"),
    "buddhist":                         ("eastern_philosophy", "buddhist_general"),
    "theravada":                        ("eastern_philosophy", "buddhist_theravada"),
    "tibetan":                          ("eastern_philosophy", "buddhist_tibetan"),
    "zen":                              ("eastern_philosophy", "buddhist_zen"),

    # New religious movements
    "jehovahs_witness":                 ("new_religious_movement", "jehovahs_witness"),
    "jehovah_witness":                  ("new_religious_movement", "jehovahs_witness"),
    "mormon":                           ("new_religious_movement", "mormon_lds"),
    "latter_day_saints":                ("new_religious_movement", "mormon_lds"),
    "christadelphian":                  ("new_religious_movement", "christadelphians"),
    "spiritualist":                     ("new_religious_movement", "spiritualist"),

    # Protestant
    "methodist":                        ("other_christian", "methodist_reuse"),
    "baptist":                          ("other_christian", "baptist_reuse"),
    "quaker":                           ("other_christian", "quaker_meeting_house"),
    "salvation_army":                   ("other_christian", "salvation_army"),
    "greek_orthodox":                   ("other_christian", "greek_orthodox"),
    "evangelical":                      ("pentecostal_evangelical", "evangelical_general"),
    "vineyard":                         ("pentecostal_evangelical", "vineyard"),
    "elim":                             ("pentecostal_evangelical", "elim_pentecostal"),
    "assemblies_of_god":                ("pentecostal_evangelical", "assemblies_of_god"),
    "hillsong":                         ("pentecostal_evangelical", "hillsong"),
    "newfrontiers":                     ("pentecostal_evangelical", "new_frontiers"),
}


# ─── NAME KEYWORD → DENOMINATION DETECTION ───────────────────────────────────
# Each entry: (list_of_keywords, conversion_type, conversion_subtype)
# Keywords are matched case-insensitively against the building name.
# More specific entries should come BEFORE more general ones.

NAME_DENOMINATION_RULES = [

    # ── SPECIFIC ORGANISATIONS (highest confidence) ───────────────────────────
    # Nigerian churches
    (["redeemed christian church", "rccg"],         "african_diaspora_church", "rccg"),
    (["winners chapel", "living faith"],            "african_diaspora_church", "winners_chapel"),
    (["christ embassy", "believers loveworld"],     "african_diaspora_church", "christ_embassy"),
    (["mountain of fire", "mfm"],                   "african_diaspora_church", "mountain_of_fire"),
    (["deeper life"],                               "african_diaspora_church", "deeper_life"),
    (["house on the rock"],                         "african_diaspora_church", "house_on_the_rock"),
    (["cherubim", "seraphim"],                      "african_diaspora_church", "cherubim_seraphim"),
    (["celestial church of christ"],                "african_diaspora_church", "celestial_church"),

    # Ghanaian churches
    (["church of pentecost"],                       "african_diaspora_church", "church_of_pentecost"),
    (["international central gospel", "icgc"],      "african_diaspora_church", "icgc"),
    (["action chapel"],                             "african_diaspora_church", "action_chapel"),
    (["lighthouse chapel"],                         "african_diaspora_church", "lighthouse_chapel"),

    # Zimbabwean/Southern African
    (["zaoga", "forward in faith"],                 "african_diaspora_church", "zaoga_forward_faith"),

    # Brazilian/Pan-African
    (["universal church of the kingdom", "uckg"],   "african_diaspora_church", "uckg"),

    # Ethiopian/Eritrean
    (["ethiopian orthodox", "tewahedo"],            "african_diaspora_church", "ethiopian_orthodox"),
    (["eritrean orthodox"],                         "african_diaspora_church", "eritrean_orthodox"),

    # Caribbean
    (["new testament church of god", "ntcg"],       "caribbean_church", "ntcg"),
    (["church of god of prophecy"],                 "caribbean_church", "church_of_god_prophecy"),
    (["seventh.day adventist", "seventh day adventist", "sda"],
                                                    "caribbean_church", "seventh_day_adventist"),
    (["wesleyan holiness"],                         "caribbean_church", "wesleyan_holiness"),

    # Eastern European
    (["ukrainian orthodox", "ukrainian autocephalous"],
                                                    "eastern_european_church", "ukrainian_orthodox"),
    (["ukrainian catholic", "greek catholic"],      "eastern_european_church", "ukrainian_catholic"),
    (["polish catholic", "polska misja katolicka", "polish mission"],
                                                    "eastern_european_church", "polish_catholic"),
    (["romanian orthodox", "biserica ortodoxa"],    "eastern_european_church", "romanian_orthodox"),
    (["russian orthodox", "rocor"],                 "eastern_european_church", "russian_orthodox_rocor"),
    (["serbian orthodox"],                          "eastern_european_church", "serbian_orthodox"),
    (["bulgarian orthodox"],                        "eastern_european_church", "bulgarian_orthodox"),

    # Middle Eastern Christian
    (["coptic orthodox", "coptic church"],          "middle_eastern_church", "coptic_orthodox"),
    (["assyrian", "chaldean"],                      "middle_eastern_church", "assyrian_chaldean"),
    (["maronite"],                                  "middle_eastern_church", "maronite_catholic"),
    (["syriac orthodox", "syrian orthodox"],        "middle_eastern_church", "syriac_orthodox"),
    (["armenian apostolic", "armenian church"],     "middle_eastern_church", "armenian_apostolic"),

    # East Asian
    (["korean"],                                    "east_asian_church", "korean_presbyterian"),
    (["chinese christian", "chinese church"],       "east_asian_church", "chinese_christian"),
    (["filipino", "fil-"],                          "east_asian_church", "filipino_catholic"),

    # South Asian Faith
    (["gurdwara", "sikh temple", "sri guru"],       "south_asian_faith", "sikh_gurdwara"),
    (["ravidassia", "ravidass"],                    "south_asian_faith", "ravidassia"),
    (["iskcon", "hare krishna", "krishna"],         "south_asian_faith", "iskcon"),
    (["swaminarayan", "baps"],                      "south_asian_faith", "swaminarayan_baps"),
    (["mandir", "hindu temple", "shree"],           "south_asian_faith", "hindu_mandir"),
    (["tamil"],                                     "south_asian_faith", "tamil_hindu"),
    (["jain"],                                      "south_asian_faith", "jain_centre"),

    # Islamic
    (["masjid", "mosque"],                          "mosque", "mosque_general"),
    (["islamic centre", "islamic center"],          "mosque", "islamic_centre"),
    (["madrasa", "madrasah", "maktab"],             "mosque", "madrasa"),
    (["muslim school", "islamic school"],           "mosque", "madrasa"),
    (["muslim community"],                          "mosque", "muslim_community_centre"),
    (["jamia", "jami"],                             "mosque", "sunni_deobandi"),
    (["barelwi", "ahl-e-sunnat"],                   "mosque", "sunni_barelwi"),
    (["salafi", "ahle hadith", "ahl-al-hadith"],    "mosque", "sunni_salafi"),
    (["ahmadiyya", "ahmadi"],                       "mosque", "ahmadiyya"),
    (["shia", "shi'a", "hussainiya", "imambara"],   "mosque", "shia_twelver"),
    (["ismaili", "jamatkhana"],                     "mosque", "shia_ismaili"),
    (["somali"],                                    "mosque", "sunni_somali"),

    # New Religious Movements
    (["scientology", "dianetics", "hubbard"],       "new_religious_movement", "scientology"),
    (["kingdom hall", "jehovah"],                   "new_religious_movement", "jehovahs_witness"),
    (["latter-day saints", "latter day saints", "mormon"],
                                                    "new_religious_movement", "mormon_lds"),
    (["new apostolic"],                             "new_religious_movement", "new_apostolic"),
    (["christadelphian"],                           "new_religious_movement", "christadelphians"),
    (["spiritualist", "spiritualism"],              "new_religious_movement", "spiritualist"),

    # Esoteric/Occult
    (["pagan", "wicca", "wiccan", "witch"],         "esoteric_occult", "pagan_wiccan"),
    (["druid", "druidry"],                          "esoteric_occult", "druid_grove"),
    (["satanic temple"],                            "esoteric_occult", "satanic_temple"),
    (["church of satan"],                           "esoteric_occult", "lavey_satanism"),
    (["golden dawn", "thelema", "aleister"],        "esoteric_occult", "occult_lodge"),

    # Eastern Philosophy
    (["buddhist", "buddha", "dhamma", "sangha"],    "eastern_philosophy", "buddhist_general"),
    (["tibetan", "kagyu", "gelug", "nyingma", "rigpa"],
                                                    "eastern_philosophy", "buddhist_tibetan"),
    (["theravada", "thai temple", "thai monastery"],
                                                    "eastern_philosophy", "buddhist_theravada"),
    (["zen", "soto", "rinzai"],                     "eastern_philosophy", "buddhist_zen"),
    (["meditation centre", "meditation center"],    "eastern_philosophy", "meditation_centre"),
    (["yoga", "ashram"],                            "eastern_philosophy", "yoga_studio"),

    # Pentecostal/Evangelical
    (["elim"],                                      "pentecostal_evangelical", "elim_pentecostal"),
    (["hillsong"],                                  "pentecostal_evangelical", "hillsong"),
    (["vineyard"],                                  "pentecostal_evangelical", "vineyard"),
    (["newfrontiers", "new frontiers", "catalyst church"],
                                                    "pentecostal_evangelical", "new_frontiers"),
    (["assemblies of god"],                         "pentecostal_evangelical", "assemblies_of_god"),
    (["holy trinity brompton", "htb", "alpha"],     "pentecostal_evangelical", "alpha_church"),

    # Other Christian
    (["salvation army", "citadel"],                 "other_christian", "salvation_army"),
    (["quaker", "friends meeting", "society of friends"],
                                                    "other_christian", "quaker_meeting_house"),
    (["greek orthodox"],                            "other_christian", "greek_orthodox"),

    # ── HOSPITALITY ───────────────────────────────────────────────────────────
    (["wetherspoon", "spoons"],                     "hospitality", "pub"),
    (["micropub", "microbrewery", "craft brewery", "taproom"],
                                                    "hospitality", "microbrewery"),
    (["wedding venue", "events venue", "event space"],
                                                    "hospitality", "wedding_venue"),

    # ── ARTS & CULTURE ────────────────────────────────────────────────────────
    (["recording studio", "music studio"],          "arts_culture", "recording_studio"),
    (["bookshop", "book shop", "bookseller"],       "arts_culture", "bookshop"),

    # ── SPORT & LEISURE ───────────────────────────────────────────────────────
    (["climbing", "bouldering", "climbing wall"],   "sport_leisure", "climbing_wall"),
    (["skate", "skateboard", "skatepark"],          "sport_leisure", "skate_park"),
    (["trampoline"],                                "sport_leisure", "trampoline_park"),
    (["paintball", "laser tag", "lasertag"],        "sport_leisure", "paintball_lasertag"),
    (["escape room"],                               "sport_leisure", "escape_room"),

    # ── COMMUNITY & SOCIAL ────────────────────────────────────────────────────
    (["lgbtq", "lgbt", "pride hub", "gay community"],
                                                    "community", "lgbtq_centre"),
    (["food bank", "foodbank", "food pantry"],      "community", "food_bank"),
    (["homeless", "night shelter", "rough sleeper"],
                                                    "residential", "homeless_shelter"),
    (["refugee", "asylum"],                         "community", "refugee_community_centre"),
    (["drug rehab", "rehabilitation", "recovery"],  "community", "drug_rehabilitation"),
    (["citizens advice", "citizens' advice"],       "community", "citizens_advice"),

    # ── COMMERCIAL ────────────────────────────────────────────────────────────
    (["funeral", "undertaker", "crematorium"],      "commercial", "funeral_parlour"),
    (["self storage", "self-storage"],              "commercial", "storage"),
    (["data centre", "data center", "server"],      "technology", "data_centre_tech"),

    # ── CIVIC ─────────────────────────────────────────────────────────────────
    (["council office", "town hall", "civic centre"],
                                                    "civic", "council_offices"),
]


# ─── OSM TAG MAPS (unchanged from original) ──────────────────────────────────

OSM_RELIGION_MAP = {
    "muslim":       ("mosque", "mosque_general"),
    "sikh":         ("south_asian_faith", "sikh_gurdwara"),
    "hindu":        ("south_asian_faith", "hindu_mandir"),
    "buddhist":     ("eastern_philosophy", "buddhist_general"),
    "jewish":       ("other_christian", "other_christian_general"),
    "christian":    ("other_christian", "other_christian_general"),
    "scientology":  ("new_religious_movement", "scientology"),
    "pagan":        ("esoteric_occult", "pagan_wiccan"),
    "unitarian":    ("other_christian", "other_christian_general"),
    "taoist":       ("eastern_philosophy", "eastern_philosophy_general"),
    "shinto":       ("eastern_philosophy", "eastern_philosophy_general"),
    "jain":         ("south_asian_faith", "jain_centre"),
}

OSM_AMENITY_MAP = {
    "bar":                  ("hospitality", "bar"),
    "pub":                  ("hospitality", "pub"),
    "nightclub":            ("hospitality", "nightclub"),
    "restaurant":           ("hospitality", "restaurant"),
    "cafe":                 ("hospitality", "cafe"),
    "fast_food":            ("hospitality", "cafe"),
    "arts_centre":          ("arts_culture", "arts_centre"),
    "theatre":              ("arts_culture", "theatre"),
    "cinema":               ("arts_culture", "cinema"),
    "library":              ("education", "library"),
    "school":               ("education", "school"),
    "college":              ("education", "college"),
    "university":           ("education", "university"),
    "community_centre":     ("community", "community_centre"),
    "social_centre":        ("community", "community_centre"),
    "gym":                  ("sport_leisure", "gym_fitness"),
    "fitness_centre":       ("sport_leisure", "gym_fitness"),
    "climbing":             ("sport_leisure", "climbing_wall"),
    "office":               ("commercial", "office"),
    "doctors":              ("community", "nhs_health_centre"),
    "dentist":              ("community", "nhs_health_centre"),
    "pharmacy":             ("community", "nhs_health_centre"),
    "food_bank":            ("community", "food_bank"),
    "shelter":              ("residential", "homeless_shelter"),
    "funeral_hall":         ("commercial", "funeral_parlour"),
    "place_of_worship":     ("other_christian", "other_christian_general"),
}

OSM_BUILDING_MAP = {
    "apartments":       ("residential", "converted_flats"),
    "residential":      ("residential", "residential_general"),
    "house":            ("residential", "single_dwelling"),
    "detached":         ("residential", "single_dwelling"),
    "terrace":          ("residential", "single_dwelling"),
    "retail":           ("commercial", "retail_shop"),
    "office":           ("commercial", "office"),
    "hotel":            ("hospitality", "hotel"),
    "warehouse":        ("commercial", "storage"),
    "supermarket":      ("commercial", "supermarket"),
    "mosque":           ("mosque", "mosque_general"),
    "temple":           ("south_asian_faith", "hindu_mandir"),
    "synagogue":        ("other_christian", "other_christian_general"),
    "gurdwara":         ("south_asian_faith", "sikh_gurdwara"),
    "monastery":        ("other_christian", "other_christian_general"),
    "school":           ("education", "school"),
    "university":       ("education", "university"),
    "hospital":         ("community", "nhs_health_centre"),
    "gym":              ("sport_leisure", "gym_fitness"),
    "stadium":          ("sport_leisure", "sport_leisure_general"),
    "sports_hall":      ("sport_leisure", "sport_leisure_general"),
    "cinema":           ("arts_culture", "cinema"),
    "theatre":          ("arts_culture", "theatre"),
    "pub":              ("hospitality", "pub"),
    "bar":              ("hospitality", "bar"),
}


# ─── WIKIDATA PROPERTY IDs ───────────────────────────────────────────────────
WD_INSTANCE_OF         = "P31"
WD_COORDINATE_LOCATION = "P625"
WD_INCEPTION           = "P571"
WD_DISSOLVED           = "P576"
WD_COUNTRY             = "P17"
WD_ADMIN_REGION        = "P131"
WD_REPLACES            = "P1365"
WD_REPLACED_BY         = "P1366"
WD_HERITAGE_DESIG      = "P1435"
WD_STREET_ADDRESS      = "P6375"

WD_CHURCH    = "Q16970"
WD_CHAPEL    = "Q108325"
WD_MOSQUE    = "Q32815"
WD_GURDWARA  = "Q193727"
WD_TEMPLE    = "Q44539"
WD_PUB       = "Q212198"
WD_NIGHTCLUB = "Q622425"


# ─── UK REGION MAPPING ───────────────────────────────────────────────────────
UK_LA_TO_REGION = {
    # England — North East
    "county durham":            ("North East", "England"),
    "gateshead":                ("North East", "England"),
    "newcastle upon tyne":      ("North East", "England"),
    "newcastle":                ("North East", "England"),
    "north tyneside":           ("North East", "England"),
    "northumberland":           ("North East", "England"),
    "south tyneside":           ("North East", "England"),
    "sunderland":               ("North East", "England"),
    "middlesbrough":            ("North East", "England"),
    "redcar and cleveland":     ("North East", "England"),
    "stockton-on-tees":         ("North East", "England"),
    "hartlepool":               ("North East", "England"),
    "darlington":               ("North East", "England"),
    "hutton henry and station town": ("North East", "England"),
    "longtown":                 ("North East", "England"),

    # England — North West
    "manchester":               ("North West", "England"),
    "salford":                  ("North West", "England"),
    "liverpool":                ("North West", "England"),
    "lancashire":               ("North West", "England"),
    "cumbria":                  ("North West", "England"),
    "cheshire":                 ("North West", "England"),
    "blackburn with darwen":    ("North West", "England"),
    "blackpool":                ("North West", "England"),
    "chorley":                  ("North West", "England"),
    "preston":                  ("North West", "England"),
    "delamere":                 ("North West", "England"),
    "downham":                  ("North West", "England"),
    "barrowford":               ("North West", "England"),
    "trafford":                 ("North West", "England"),

    # England — Yorkshire
    "leeds":                    ("Yorkshire and The Humber", "England"),
    "sheffield":                ("Yorkshire and The Humber", "England"),
    "bradford":                 ("Yorkshire and The Humber", "England"),
    "hull":                     ("Yorkshire and The Humber", "England"),
    "york":                     ("Yorkshire and The Humber", "England"),
    "north yorkshire":          ("Yorkshire and The Humber", "England"),
    "east riding of yorkshire": ("Yorkshire and The Humber", "England"),
    "barnsley":                 ("Yorkshire and The Humber", "England"),
    "hebden royd":              ("Yorkshire and The Humber", "England"),
    "wadsworth":                ("Yorkshire and The Humber", "England"),
    "hawes":                    ("Yorkshire and The Humber", "England"),
    "hellifield":               ("Yorkshire and The Humber", "England"),
    "sinnington":               ("Yorkshire and The Humber", "England"),
    "grimsby":                  ("Yorkshire and The Humber", "England"),
    "huddersfield":             ("Yorkshire and The Humber", "England"),

    # England — East Midlands
    "nottingham":               ("East Midlands", "England"),
    "leicester":                ("East Midlands", "England"),
    "derby":                    ("East Midlands", "England"),
    "northamptonshire":         ("East Midlands", "England"),
    "lincolnshire":             ("East Midlands", "England"),
    "high peak":                ("East Midlands", "England"),
    "ilkeston":                 ("East Midlands", "England"),
    "erewash":                  ("East Midlands", "England"),
    "oundle":                   ("East Midlands", "England"),
    "city of nottingham":       ("East Midlands", "England"),
    "caistor":                  ("East Midlands", "England"),
    "cold hanworth":            ("East Midlands", "England"),
    "middleton and smerrill":   ("East Midlands", "England"),
    "staveley":                 ("East Midlands", "England"),

    # England — West Midlands
    "birmingham":               ("West Midlands", "England"),
    "coventry":                 ("West Midlands", "England"),
    "wolverhampton":            ("West Midlands", "England"),
    "walsall":                  ("West Midlands", "England"),
    "tamworth":                 ("West Midlands", "England"),
    "rugby":                    ("West Midlands", "England"),
    "wythall":                  ("West Midlands", "England"),
    "princethorpe":             ("West Midlands", "England"),

    # England — East of England
    "norfolk":                  ("East of England", "England"),
    "suffolk":                  ("East of England", "England"),
    "essex":                    ("East of England", "England"),
    "cambridge":                ("East of England", "England"),
    "hertfordshire":            ("East of England", "England"),
    "wymondham":                ("East of England", "England"),
    "hawkwell":                 ("East of England", "England"),
    "new leake":                ("East of England", "England"),
    "sibton":                   ("East of England", "England"),
    "chignall":                 ("East of England", "England"),
    "foxhall":                  ("East of England", "England"),
    "dacorum":                  ("East of England", "England"),
    "southend-on-sea":          ("East of England", "England"),
    "hormead":                  ("East of England", "England"),
    "nayland-with-wissington":  ("East of England", "England"),

    # England — London
    "london":                   ("London", "England"),
    "city of london":           ("London", "England"),
    "westminster":              ("London", "England"),
    "city of westminster":      ("London", "England"),
    "tower hamlets":            ("London", "England"),
    "hackney":                  ("London", "England"),
    "southwark":                ("London", "England"),
    "lambeth":                  ("London", "England"),
    "newham":                   ("London", "England"),
    "brent":                    ("London", "England"),
    "london borough of lambeth":("London", "England"),
    "london borough of southwark": ("London", "England"),
    "london borough of ealing": ("London", "England"),
    "london borough of croydon":("London", "England"),
    "london borough of sutton": ("London", "England"),

    # England — South East
    "kent":                     ("South East", "England"),
    "surrey":                   ("South East", "England"),
    "sussex":                   ("South East", "England"),
    "hampshire":                ("South East", "England"),
    "oxfordshire":              ("South East", "England"),
    "berkshire":                ("South East", "England"),
    "buckinghamshire":          ("South East", "England"),
    "oxford":                   ("South East", "England"),
    "reading":                  ("South East", "England"),
    "brighton":                 ("South East", "England"),
    "brighton and hove":        ("South East", "England"),
    "tunbridge wells":          ("South East", "England"),
    "rushmoor":                 ("South East", "England"),
    "reigate and banstead":     ("South East", "England"),
    "tonbridge and malling":    ("South East", "England"),
    "city of portsmouth":       ("South East", "England"),
    "folkestone":               ("South East", "England"),
    "pembury":                  ("South East", "England"),
    "ramsgate":                 ("South East", "England"),
    "over norton":              ("South East", "England"),
    "didcot":                   ("South East", "England"),
    "thatcham":                 ("South East", "England"),
    "slaugham":                 ("South East", "England"),
    "oxted":                    ("South East", "England"),
    "bembridge":                ("South East", "England"),
    "netley marsh":             ("South East", "England"),
    "sandleheath":              ("South East", "England"),
    "romsey extra":             ("South East", "England"),
    "foscott":                  ("South East", "England"),
    "haversham-cum-little linford": ("South East", "England"),
    "eastbourne":               ("South East", "England"),
    "worthing":                 ("South East", "England"),
    "southampton":              ("South East", "England"),

    # England — South West
    "bristol":                  ("South West", "England"),
    "devon":                    ("South West", "England"),
    "cornwall":                 ("South West", "England"),
    "somerset":                 ("South West", "England"),
    "dorset":                   ("South West", "England"),
    "wiltshire":                ("South West", "England"),
    "christchurch":             ("South West", "England"),
    "wareham":                  ("South West", "England"),
    "dunster":                  ("South West", "England"),
    "bodmin":                   ("South West", "England"),
    "painswick":                ("South West", "England"),
    "trowbridge":               ("South West", "England"),
    "city of plymouth":         ("South West", "England"),
    "portland":                 ("South West", "England"),
    "treverbyn":                ("South West", "England"),
    "cotford st luke":          ("South West", "England"),
    "burton bradstock":         ("South West", "England"),
    "broad clyst":              ("South West", "England"),
    "iwerne minster":           ("South West", "England"),

    # Wales
    "cardiff":                  ("Wales", "Wales"),
    "swansea":                  ("Wales", "Wales"),
    "newport":                  ("Wales", "Wales"),
    "rhondda cynon taf":        ("Wales", "Wales"),
    "carmarthenshire":          ("Wales", "Wales"),
    "pembrokeshire":            ("Wales", "Wales"),
    "gwynedd":                  ("Wales", "Wales"),
    "ceredigion":               ("Wales", "Wales"),
    "tredegar":                 ("Wales", "Wales"),
    "manorbier":                ("Wales", "Wales"),
    "machynlleth":              ("Wales", "Wales"),
    "abersychan":               ("Wales", "Wales"),
    "fishguard and goodwick":   ("Wales", "Wales"),
    "pontypridd":               ("Wales", "Wales"),
    "pentre":                   ("Wales", "Wales"),

    # Scotland
    "glasgow":                  ("Scotland", "Scotland"),
    "edinburgh":                ("Scotland", "Scotland"),
    "aberdeen":                 ("Scotland", "Scotland"),
    "dundee":                   ("Scotland", "Scotland"),
    "highland":                 ("Scotland", "Scotland"),
    "fife":                     ("Scotland", "Scotland"),
    "city of edinburgh":        ("Scotland", "Scotland"),
    "argyll and bute":          ("Scotland", "Scotland"),
    "ceredigion":               ("Wales", "Wales"),
    "blairgowrie and rattray":  ("Scotland", "Scotland"),
    "east dunbartonshire":      ("Scotland", "Scotland"),
    "north lanarkshire":        ("Scotland", "Scotland"),
    "moray":                    ("Scotland", "Scotland"),
    "shetland islands":         ("Scotland", "Scotland"),
    "shetland":                 ("Scotland", "Scotland"),
    "angus":                    ("Scotland", "Scotland"),
    "stirling":                 ("Scotland", "Scotland"),
    "inverness":                ("Scotland", "Scotland"),
    "perth":                    ("Scotland", "Scotland"),

    # Northern Ireland
    "belfast":                  ("Northern Ireland", "Northern Ireland"),
    "derry":                    ("Northern Ireland", "Northern Ireland"),
    "antrim":                   ("Northern Ireland", "Northern Ireland"),
    "armagh":                   ("Northern Ireland", "Northern Ireland"),
    "down":                     ("Northern Ireland", "Northern Ireland"),
}


# ─── SOURCE CONFIDENCE WEIGHTS ────────────────────────────────────────────────
SOURCE_CONFIDENCE = {
    "wikidata":             0.95,
    "historic_england":     0.90,
    "osm":                  0.70,
    "osm_pbf":              0.70,
    "charity_commission":   0.75,
    "planning_portal":      0.80,
    "denomination_enriched": 0.65,
    "manual":               1.00,
}
