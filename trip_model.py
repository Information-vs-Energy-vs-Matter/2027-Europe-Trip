"""
trip_model.py

Single source of truth for every dollar figure and every day-by-day time
assumption on the trip planner page. Run this file to regenerate
trip_data.json. Nothing in the HTML/JS layer computes numbers -- it only
reads what this script produces. Change an assumption below, rerun, and
every chart/table on the page updates from the same recomputed values.

Usage:
    python3 trip_model.py

Idempotent: same inputs always produce byte-identical output. No randomness,
no network calls, no hidden state.
"""

import json
import copy

# ============================================================
# SOURCES REGISTRY
# Every external figure used in ASSUMPTIONS below traces back to one of
# these. Cite the key (e.g. "flights_transatlantic") in a comment next to
# any number you pull from it. Update the URL/date if you re-verify.
# ============================================================

SOURCES = {
    "flights_transatlantic": [
        {"url": "https://www.expedia.com/lp/flights/rdu/fco/raleigh-to-rome", "note": "RDU-FCO one-way/RT fare ranges"},
        {"url": "https://www.kayak.com/flight-routes/Raleigh-Durham-RDU/Rome-ROM", "note": "RDU-FCO average fares, layover cities"},
        {"url": "https://www.skyscanner.com/routes/rdu/fco/raleigh-durham-to-rome-fiumicino.html", "note": "RDU-FCO lowest one-way fare"},
        {"url": "https://www.expedia.com/lp/flights/rdu/ath/raleigh-to-athens", "note": "RDU-ATH fare ranges, cheapest month"},
    ],
    "flights_intra_europe": [
        {"url": "https://www.expedia.com/lp/flights/fco/ath/rome-to-athens", "note": "FCO-ATH fare range, weekly frequency"},
        {"url": "https://www.kayak.com/flight-routes/Rome-Fiumicino-FCO/Athens-Eleftherios-V--ATH", "note": "FCO-ATH lowest fares"},
        {"url": "https://www.skyscanner.net/routes/ath/chq/athens-international-to-crete-chania.html", "note": "ATH-CHQ one-way fares by date"},
        {"url": "https://www.omio.com/flights/athens/crete", "note": "ATH-Crete airline options and frequency"},
    ],
    "airport_data": [
        {"url": "https://en.wikipedia.org/wiki/Athens_International_Airport", "note": "ATH annual passengers, terminal layout"},
        {"url": "https://www.airportsdata.net/airport-FCO/", "note": "FCO terminal count, annual traffic"},
        {"url": "https://www.chq-airport.gr/en", "note": "CHQ official site, EES processing notes"},
        {"url": "https://flightqueue.com/airport/RDU", "note": "RDU security wait time estimates"},
        {"url": "https://airportmaphq.com/rome-fiumicino-airport-security-wait-times.html", "note": "FCO peak vs off-peak security wait"},
    ],
    "rome_activities": [
        {"url": "https://mamalovesrome.com/things-to-do-in-rome-with-kids-complete-guide/", "note": "Colosseum/Domus Aurea/gladiator school pricing"},
        {"url": "https://www.adventuroustastes.com/rome-with-teenagers/", "note": "Teen-specific Rome activities and framing"},
    ],
    "peloponnese_activities": [
        {"url": "https://www.tripadvisor.com/Attractions-g189483-Activities-Peloponnese.html", "note": "Mycenae, Epidaurus, Palamidi entry costs"},
        {"url": "https://www.discovergreece.com/peloponnese", "note": "Regional overview, UNESCO sites, hiking trails"},
    ],
    "crete_activities": [
        {"url": "https://www.easyjet.com/en/cheap-flights/greece/crete", "note": "Samaria Gorge, Balos, Elafonisi overview"},
        {"url": "https://www.cretanbeaches.com/en/sea-tourism/west-crete-beaches/elafonissi-beach", "note": "Elafonisi access and cost detail"},
    ],
    "naples_amalfi_activities": [
        {"url": "https://www.earthtrekkers.com/best-things-to-do-on-the-amalfi-coast/", "note": "Path of the Gods, Ravello, Positano cost detail"},
        {"url": "https://www.earthtrekkers.com/path-of-the-gods-hike/", "note": "Path of the Gods logistics and difficulty"},
    ],
    "riviera_activities": [
        {"url": "https://www.getyourguide.com/explorer/nice-ttd314/free-things-to-do-in-nice/", "note": "Nice/Eze/Monaco free and paid activities"},
        {"url": "https://www.arbaspaa.com/info-cinque-terre-2/best-airport-to-fly-into-for-cinque-terre", "note": "Genoa/Pisa gateway options for Cinque Terre"},
        {"url": "https://shippedaway.com/vernazza-monterosso-hike-cinque-terre/", "note": "Cinque Terre trail fees and Cinque Terre Card pricing"},
    ],
    "accommodation": [
        {"url": "https://www.airbnb.com", "note": "General market-rate estimate for 2-3BR apartments in each region, no specific listing cited -- treat as rough estimate pending real search"},
    ],
    "athens_activities": [
        {"url": "https://www.discovergreece.com", "note": "Acropolis, Acropolis Museum entry pricing"},
    ],
    "switzerland_costs": [
        {"url": "https://www.jungfraujochtickets.com/", "note": "Jungfraujoch round-trip ticket pricing by origin"},
        {"url": "https://www.swissprivatetour.ch/en/switzerland-travel-cost-3/", "note": "Mountain resort hotel + food per-day cost breakdown"},
        {"url": "https://simbye.com/blogs/blog/how-much-does-trip-to-switzerland-cost-2026-budget-breakdown", "note": "Restaurant meal costs, Swiss Travel Pass pricing"},
        {"url": "https://www.swiss.com/lhg/us/en/o-d/cy-cy/raleigh-durham-zurich", "note": "RDU-ZRH direct flight pricing"},
        {"url": "https://www.expedia.com/lp/flights/rdu/zrh/raleigh-to-zurich", "note": "RDU-ZRH fare range"},
    ],
    "naples_flights": [
        {"url": "https://www.flightroutes.com/RDU-NAP", "note": "RDU-NAP routing, connections, flight time"},
        {"url": "https://www.google.com/travel/flights/flights-from-raleigh-to-naples.html", "note": "RDU-NAP fare range by month"},
        {"url": "https://www.flightconnections.com/flights-to-naples-nap", "note": "Seasonal direct summer flights from ATL/PHL/ORD/JFK"},
    ],
    "flea_markets": [
        {"url": "https://www.discovernafplio.gr/en/articles/sightseeing/flea-market", "note": "Nafplio flea market -- Wed/Sat, base of Palamidi steps"},
        {"url": "https://santorinidave.com/best-shopping-nafplio", "note": "Nafplio antique/vintage shops (Nostalgia Vintage, The Antique Shop)"},
        {"url": "https://www.rental-center-crete.com/blog/chania-markets/", "note": "Chania flea market -- vintage, antiques, retro goods"},
        {"url": "https://www.getyourguide.com/chania-l1807/chania-hidden-thrift-shops-vintage-finds-walk-t1281169/", "note": "Chania thrift/vintage shop walking tour confirms multiple real shops exist"},
        {"url": "https://www.wantedinrome.com/yellowpage/porta-portese-sunday-flea-market-in-rome.html", "note": "Porta Portese -- Rome's largest flea market, Sundays since 1945"},
        {"url": "https://www.fleamarketinsiders.com/flea-markets-rome/", "note": "Rome market closures in July/August -- Mercato Monti closes, Porta Portese and Via Sannio stay open"},
        {"url": "https://niceandbeyond.com/cours-saleya-markets-nice/", "note": "Nice: Cours Saleya Brocante (Monday, year-round) and Les Puces de Nice (Tue-Sat, Port district)"},
        {"url": "https://www.zuerich.com/en/visit/shopping/kanzlei-flea-market", "note": "Zurich Kanzlei Flohmarkt -- largest in Switzerland, 400+ vendors, year-round Saturdays"},
        {"url": "https://www.zuerich.com/en/visit/shopping/flea-market-burkliplatz", "note": "Zurich Burkliplatz flea market -- May-October, Saturdays"},
    ],
}


# ============================================================
# OBJECTIVES & CONSTRAINTS
# Structured so the "Objectives & constraints" tab and the copy-paste
# Signal text block are BOTH generated from this one Python structure --
# never hand-typed twice. Edit here, rerun, both outputs update.
# ============================================================

GROUP_INFO = {
    "group": "3 adults + 3 teens (13-15), able-bodied, good travel problem-solvers",
    "window": "Mid-June to late July",
    "budget": "$10-15K per family of 4 (2 adults + 2 teens)",
}

OBJECTIVES = [
    {
        "num": 1, "name": "Exploration index",
        "desc": "Places none of us have been. Greece = high (first time) for everyone. Rome, French Riviera, and Italian Riviera are all lower here since 2 of the 6 travelers have already been to all three.",
    },
    {
        "num": 2, "name": "History & culture index",
        "desc": "Real ruins, castles, archaeological sites -- walk through the story, not just photos. Note: teens ranked ancient ruins LOWEST of 5 priorities when asked what they'd miss most if cut -- adults may value this more than teens do.",
    },
    {
        "num": 3, "name": "Outdoor / active index",
        "desc": "Hiking, swimming, physical challenge. Teens want to move.",
    },
    {
        "num": 4, "name": "Mediterranean coast index",
        "desc": "Refined: dramatic topology -- steep mountains/cliffs meeting the sea (Amalfi-style) -- is worth far more than flat resort beaches, which are easy to satisfy anywhere on this trip. A significant goal overall, but not a requirement at every single stop.",
    },
    {
        "num": 5, "name": "Food index",
        "desc": "Eat like locals -- markets, tavernas, street food. No tourist traps.",
    },
    {
        "num": 6, "name": "Cost efficiency index",
        "desc": "Max experience per dollar. Rural Greece beats Rome badly here.",
    },
    {
        "num": 7, "name": "Travel simplicity index",
        "desc": "Minimize painful transit -- long waits and rushed city-to-city moves drain the trip.",
    },
    {
        "num": 8, "name": "Group harmony index",
        "desc": "Teens engaged + adults not bored. Mix of challenge and depth. Teens specifically ranked exploring a big city on their own as MORE exciting than swimming, glaciers, or hiking -- build in unstructured/independent time in Athens and Naples.",
    },
    {
        "num": 9, "name": "Variety index",
        "desc": "Not every stop should feel like the same Mediterranean postcard. Snow, mountains, and a modern city (like Switzerland offers) count as real trip value, distinct from coast/history/food.",
    },
]

TEEN_FEEDBACK = {
    "date_collected": "in-person, mid-planning",
    "cut_priority_ranking": [
        "Beach/swim day (would be missed MOST if cut)",
        "Big modern city exploration (Athens/Naples)",
        "Samaria Gorge hike",
        "Switzerland snow/glaciers",
        "Ancient ruins -- Pompeii/Acropolis/Mycenae (would be missed LEAST if cut)",
    ],
    "switzerland_verdict": "Conditional yes -- only if kept to 2-3 nights max, not extended",
    "most_exciting_anticipated": "Clarified after follow-up: 'exploring a big city' specifically meant flea markets / junk shops / thrift shopping, not generic city wandering.",
    "market_preferences": {
        "what_theyre_looking_for": ["Weird old antiques/knick-knacks", "Vintage clothes", "Random one-of-a-kind junk, don't care what"],
        "buy_or_browse": "Buy stuff -- worth the luggage space",
        "time_wanted_per_city": "Half a day",
        "naples_vs_athens": "Both equally -- try to hit whichever lines up with actual travel dates",
    },
    "implications": [
        "Ancient ruins ranked LAST despite adults prioritizing history heavily (objective 2) -- worth checking whether ruin-heavy days need trimming or reframing for teen engagement.",
        "The #2 priority is specifically flea markets and junk shops, not generic city time -- Naples now has a real flea market attraction added (Mercatino dell'Antiquariato), and Athens' Monastiraki is exactly this kind of stop.",
        "They want to BUY, not just browse -- pack an empty duffel or expect to buy a cheap bag abroad; factor this into Ryanair/budget-airline baggage fee math on the intra-Europe legs.",
        "Half a day is a real time block -- this should show up as scheduled time in Naples and/or Athens, not squeezed into leftover hours.",
        "Naples' market is only open specific weekends of the month -- MUST check actual travel dates against this before counting on it. If dates don't line up, Athens' daily Monastiraki becomes the reliable fallback.",
        "Every destination now has a flea market / junk shop attraction added to its detail page. Amalfi Coast and the Italian Riviera are honestly the weakest options here (no real dedicated flea market at either) -- worth knowing if this is a real priority when comparing alternatives.",
        "Many Italian outdoor flea markets close for July/August (e.g. Rome's Mercato Monti) -- Porta Portese (Rome) and Via Sannio stay open through summer, so check specific market calendars against actual travel dates once locked in.",
        "Switzerland's 3-night length is already at the edge of teen tolerance -- do not extend it if it's added.",
    ],
}


OPEN_QUESTIONS = [
    "Naples is now the baseline Italy stop (Rome lost group support) -- any objections?",
    "Worth swapping in Switzerland (mountains/glaciers) despite it being ~2x the cost of every other option?",
    "Comfortable with narrow mountain driving in the Peloponnese?",
    "Everyone in for the Samaria Gorge hike (16km, ~6hrs)?",
    "Ryanair (cheaper, bag fees) vs full-service airlines for intra-Europe legs?",
    "Exact dates -- mid-June (cooler, cheaper) vs July (hotter, pricier)?",
]


def build_crew_text():
    """Assembles the copy-paste-to-Signal text block from the structured
    data above. This is the ONLY place this text is generated -- the HTML
    just displays whatever this function (via trip_data.json) produces."""
    lines = []
    lines.append("OUR TRIP OBJECTIVES -- REACT / ADD BELOW")
    lines.append("")
    lines.append(f"GROUP: {GROUP_INFO['group']}")
    lines.append(f"WINDOW: {GROUP_INFO['window']}")
    lines.append(f"BUDGET: {GROUP_INFO['budget']}")
    lines.append("")
    for o in OBJECTIVES:
        lines.append(f"{o['num']}. {o['name'].upper()}")
        lines.append(o['desc'])
        lines.append("")
    lines.append("OPEN QUESTIONS FOR THE GROUP:")
    for q in OPEN_QUESTIONS:
        lines.append(f"- {q}")
    lines.append("")
    lines.append("Reply with your top 3 priorities from the list above, or add anything missing.")
    return "\n".join(lines)


# ============================================================
# PRIOR VISITS
# Who in the group has already been where -- drives the Exploration index
# score below. Edit this when someone's travel history changes.
# ============================================================

PRIOR_VISITS = {
    "rome": "2 of 6 travelers (both adults in one family) have been before",
    "fr": "2 of 6 travelers (both adults in one family) have been before",
    "it": "2 of 6 travelers (both adults in one family) have been before",
}


# ============================================================
# DESTINATION SCORES
# 1-5 per objective, per destination/alternative. This is the single
# source of truth for the Scores tab -- edit a number here, rerun, and
# the bar chart + verdict table both update. "naples"/"amalfi" are Italy
# alternatives; "fr"/"it" are French Riviera / Italian Riviera alternatives.
# ============================================================

DESTINATION_SCORES = {
    # dest_key: {objective_num: score}  -- objective 9 = Variety index (new)
    "rome":    {1: 3, 2: 5, 3: 2, 4: 2, 5: 5, 6: 2, 7: 3, 8: 3, 9: 4},
    "pelo":    {1: 5, 2: 5, 3: 4, 4: 3, 5: 4, 6: 5, 7: 3, 8: 5, 9: 3},  # coast lowered: Nafplio is a harbor town, not sheer cliffs; Mani's drama is a day-trip mention, not core itinerary
    "crete":   {1: 5, 2: 4, 3: 5, 4: 5, 5: 5, 6: 5, 7: 4, 8: 5, 9: 3},
    "naples":  {1: 5, 2: 5, 3: 3, 4: 3, 5: 5, 6: 4, 7: 3, 8: 4, 9: 3},
    "amalfi":  {1: 5, 2: 3, 3: 5, 4: 5, 5: 4, 6: 2, 7: 2, 8: 4, 9: 2},
    "fr":      {1: 3, 2: 3, 3: 3, 4: 4, 5: 4, 6: 1, 7: 2, 8: 3, 9: 3},  # exploration lowered: 2 of 6 have been; coast lowered slightly: glamorous coastal drives, but less sheer-cliff-dramatic than Amalfi/Cinque Terre/Crete\'s south coast
    "it":      {1: 3, 2: 2, 3: 5, 4: 5, 5: 4, 6: 3, 7: 2, 8: 4, 9: 2},  # exploration lowered: 2 of 6 have been
    "switzerland": {1: 5, 2: 3, 3: 5, 4: 1, 5: 4, 6: 1, 7: 3, 8: 4, 9: 5},  # no coast (landlocked), cost efficiency lowest, but HIGHEST variety: snow + modern city
}

DESTINATION_LABELS = {
    "rome": "Rome", "pelo": "Peloponnese", "crete": "Crete",
    "naples": "Naples", "amalfi": "Amalfi Coast",
    "fr": "French Riviera", "it": "Italian Riviera",
    "switzerland": "Switzerland (Jungfrau Region)",
}

DESTINATION_EMOJI = {
    "rome": "🏟️", "pelo": "🗺️", "crete": "🏖️",
    "naples": "🍕", "amalfi": "🌊", "fr": "🇫🇷", "it": "🇮🇹",
    "switzerland": "🏔️",
}

DESTINATION_VERDICTS = {
    "crete": "Best overall match",
    "pelo": "Excellent across the board",
    "naples": "Current baseline plan -- primary Italy stop",
    "amalfi": "Strong coastal/hiking alt",
    "it": "Good hiking alt, less novel now",
    "rome": "Losing group support -- crowds, cost, repeat visits",
    "fr": "Priciest reroute, and less novel now",
    "switzerland": "Stunning mountains/glaciers, by far the most expensive option",
}


def compute_destination_totals():
    """Sums each destination's per-objective scores and attaches a verdict.
    Sorted descending by total so the highest-scoring option leads."""
    results = []
    for dest, scores in DESTINATION_SCORES.items():
        total = sum(scores.values())
        results.append({
            "dest": dest,
            "label": DESTINATION_LABELS[dest],
            "emoji": DESTINATION_EMOJI[dest],
            "scores": scores,
            "total": total,
            "prior_visit_note": PRIOR_VISITS.get(dest),
            "verdict": DESTINATION_VERDICTS.get(dest, ""),
        })
    results.sort(key=lambda r: -r["total"])
    return results


# ============================================================
# DESTINATION COST ATOMS
# The verifiable ground truth. Every dollar shown on a destination's detail
# page comes from here, AND every dollar in the Costs tab's accommodation
# and activities lines is a SUM of these same atoms -- never a separately
# guessed lump number. If a destination page and the Costs tab ever
# disagree, one of them has a bug; they can't both be "roughly right"
# independently anymore.
#
# accommodation_per_night: (low, high) USD for the whole group's rental
# activities: list of {name, per_person_low, per_person_high, source,
#             in_budget} -- in_budget=True means its cost is counted in
#             the trip's pre-booked activities total; False means it's
#             an optional extra shown for planning but not pre-costed
#             (usually because it's cheap/paid cash on the day, or truly
#             optional and not everyone will do it).
# ============================================================

DESTINATION_COST_ATOMS = {
    "rome": {
        "nights": 3,
        "accommodation_per_night": (250, 400),
        "accommodation_source": "accommodation",
        "activities": [
            {"name": "Colosseum + Arena Floor", "per_person_low": 25, "per_person_high": 35, "source": "rome_activities", "in_budget": True},
            {"name": "Roman Forum + Palatine Hill", "per_person_low": 0, "per_person_high": 0, "source": "rome_activities", "in_budget": False, "note": "included on Colosseum ticket"},
            {"name": "Vatican Museums + Sistine Chapel", "per_person_low": 30, "per_person_high": 35, "source": "rome_activities", "in_budget": False},
            {"name": "Domus Aurea", "per_person_low": 16, "per_person_high": 20, "source": "rome_activities", "in_budget": False},
            {"name": "Gladiator school", "per_person_low": 60, "per_person_high": 100, "source": "rome_activities", "in_budget": False},
            {"name": "Pizza or pasta making class in Trastevere", "per_person_low": 50, "per_person_high": 75, "source": "rome_activities", "in_budget": False},
            {"name": "Catacombs of San Callisto", "per_person_low": 12, "per_person_high": 15, "source": "rome_activities", "in_budget": False},
            {"name": "Capuchin Crypt", "per_person_low": 10, "per_person_high": 10, "source": "rome_activities", "in_budget": False},
            {"name": "Janiculum Hill sunset walk", "per_person_low": 0, "per_person_high": 0, "source": "rome_activities", "in_budget": False, "note": "free"},
            {"name": "Porta Portese flea market", "per_person_low": 0, "per_person_high": 0, "source": "flea_markets", "in_budget": False, "note": "free to browse; Rome's largest flea market since 1945 -- stays open through summer, unlike Mercato Monti which closes July/August"},
        ],
    },
    "pelo": {
        "nights": 4,
        "accommodation_per_night": (100, 180),
        "accommodation_source": "accommodation",
        "activities": [
            {"name": "Palamidi Fortress", "per_person_low": 5, "per_person_high": 8, "source": "peloponnese_activities", "in_budget": False},
            {"name": "Ancient Mycenae", "per_person_low": 8, "per_person_high": 12, "source": "peloponnese_activities", "in_budget": False},
            {"name": "Epidaurus theater", "per_person_low": 8, "per_person_high": 12, "source": "peloponnese_activities", "in_budget": False},
            {"name": "Ancient Corinth + Canal", "per_person_low": 8, "per_person_high": 10, "source": "peloponnese_activities", "in_budget": False},
            {"name": "Lousios Gorge hike", "per_person_low": 0, "per_person_high": 0, "source": "peloponnese_activities", "in_budget": False, "note": "free"},
            {"name": "Mani Peninsula", "per_person_low": 0, "per_person_high": 0, "source": "peloponnese_activities", "in_budget": False, "note": "free to explore"},
            {"name": "Diros Caves", "per_person_low": 15, "per_person_high": 18, "source": "peloponnese_activities", "in_budget": False},
            {"name": "Voidokilia Beach", "per_person_low": 0, "per_person_high": 0, "source": "peloponnese_activities", "in_budget": False, "note": "free"},
            {"name": "Mystras Byzantine ruins", "per_person_low": 8, "per_person_high": 8, "source": "peloponnese_activities", "in_budget": False},
            {"name": "Nafplio flea market (Wed/Sat, base of Palamidi steps)", "per_person_low": 0, "per_person_high": 0, "source": "flea_markets", "in_budget": False, "note": "free to browse; plus antique/vintage shops in Old Town"},
        ],
    },
    "crete": {
        "nights": 5,
        "accommodation_per_night": (120, 200),
        "accommodation_source": "accommodation",
        "activities": [
            {"name": "Samaria Gorge hike", "per_person_low": 6, "per_person_high": 6, "source": "crete_activities", "in_budget": False, "note": "cash on trail, not pre-booked"},
            {"name": "Imbros Gorge", "per_person_low": 4, "per_person_high": 4, "source": "crete_activities", "in_budget": False},
            {"name": "Balos Lagoon", "per_person_low": 20, "per_person_high": 20, "source": "crete_activities", "in_budget": False, "note": "boat from Kissamos"},
            {"name": "Elafonisi Beach", "per_person_low": 0, "per_person_high": 0, "source": "crete_activities", "in_budget": False, "note": "free"},
            {"name": "Chania Old Town", "per_person_low": 0, "per_person_high": 0, "source": "crete_activities", "in_budget": False, "note": "free"},
            {"name": "Knossos Minoan palace", "per_person_low": 18, "per_person_high": 20, "source": "crete_activities", "in_budget": False},
            {"name": "Aptera ruins", "per_person_low": 6, "per_person_high": 6, "source": "crete_activities", "in_budget": False},
            {"name": "Seitan Limania cove", "per_person_low": 0, "per_person_high": 0, "source": "crete_activities", "in_budget": False, "note": "free"},
            {"name": "Chania flea market", "per_person_low": 0, "per_person_high": 0, "source": "flea_markets", "in_budget": False, "note": "free to browse; vintage/retro goods, guided thrift walks available"},
            {"name": "Sfakia + Loutro day trip", "per_person_low": 10, "per_person_high": 20, "source": "crete_activities", "in_budget": False, "note": "1.5-2hr drive from Chania + ferry; this IS the Amalfi-style dramatic cliffs-meet-sea terrain, just wilder and car-free at Loutro"},
        ],
    },
    "athens": {
        "nights": 2,
        "accommodation_per_night": (150, 250),
        "accommodation_source": "accommodation",
        "activities": [
            {"name": "Acropolis + Parthenon", "per_person_low": 22, "per_person_high": 25, "source": "athens_activities", "in_budget": True},
            {"name": "Acropolis Museum", "per_person_low": 10, "per_person_high": 13, "source": "athens_activities", "in_budget": True},
            {"name": "Plaka neighborhood", "per_person_low": 0, "per_person_high": 0, "source": "athens_activities", "in_budget": False, "note": "free"},
            {"name": "Monastiraki flea market", "per_person_low": 0, "per_person_high": 0, "source": "athens_activities", "in_budget": False, "note": "free to browse"},
            {"name": "Changing of the Guard", "per_person_low": 0, "per_person_high": 0, "source": "athens_activities", "in_budget": False, "note": "free"},
        ],
    },
    # Alternatives -- not part of the 16-day itinerary, so these do NOT
    # roll into the main Costs tab total. Shown on their own detail pages
    # as an "if you swapped Rome for this" illustrative estimate, using
    # the same 3-night duration Rome would have occupied.
    "naples": {
        "nights": 3,
        "accommodation_per_night": (150, 250),
        "accommodation_source": "accommodation",
        "activities": [
            {"name": "Pompeii ruins", "per_person_low": 20, "per_person_high": 22, "source": "naples_amalfi_activities", "in_budget": True},
            {"name": "Herculaneum", "per_person_low": 15, "per_person_high": 15, "source": "naples_amalfi_activities", "in_budget": False},
            {"name": "Naples historic center (UNESCO)", "per_person_low": 12, "per_person_high": 15, "source": "naples_amalfi_activities", "in_budget": False},
            {"name": "Mount Vesuvius hike", "per_person_low": 12, "per_person_high": 12, "source": "naples_amalfi_activities", "in_budget": False, "note": "+ transport"},
            {"name": "National Archaeological Museum", "per_person_low": 16, "per_person_high": 16, "source": "naples_amalfi_activities", "in_budget": False},
            {"name": "Pizza in the Spanish Quarter", "per_person_low": 6, "per_person_high": 10, "source": "naples_amalfi_activities", "in_budget": False, "note": "per pizza, not per person"},
            {"name": "Mercatino dell'Antiquariato flea market", "per_person_low": 0, "per_person_high": 0, "source": "naples_amalfi_activities", "in_budget": False, "note": "free to browse; Villa Comunale, 3rd/4th weekend of month -- furniture, prints, antiques, real junk-shop treasure hunting"},
        ],
    },
    "amalfi": {
        "nights": 3,
        "accommodation_per_night": (180, 320),
        "accommodation_source": "accommodation",
        "activities": [
            {"name": "Path of the Gods guided hike", "per_person_low": 40, "per_person_high": 60, "source": "naples_amalfi_activities", "in_budget": True},
            {"name": "Villa Cimbrone gardens (Ravello)", "per_person_low": 11, "per_person_high": 11, "source": "naples_amalfi_activities", "in_budget": False},
            {"name": "Boat tour of the coast", "per_person_low": 60, "per_person_high": 90, "source": "naples_amalfi_activities", "in_budget": False},
            {"name": "Positano/Amalfi antique & boutique shops (no dedicated flea market)", "per_person_low": 0, "per_person_high": 0, "source": "flea_markets", "in_budget": False, "note": "weakest stop for junk-shop hunting -- scattered antique shops only, no real flea market like the other destinations"},
        ],
    },
    "fr": {
        "nights": 3,
        "accommodation_per_night": (200, 350),
        "accommodation_source": "accommodation",
        "activities": [
            {"name": "Eze botanical garden entry", "per_person_low": 7, "per_person_high": 7, "source": "riviera_activities", "in_budget": True},
            {"name": "Monaco Oceanographic Museum", "per_person_low": 18, "per_person_high": 20, "source": "riviera_activities", "in_budget": False},
            {"name": "Gorges du Loup guided aquatic hike", "per_person_low": 30, "per_person_high": 50, "source": "riviera_activities", "in_budget": False},
            {"name": "Cours Saleya Brocante", "per_person_low": 0, "per_person_high": 0, "source": "flea_markets", "in_budget": False, "note": "free to browse; year-round, reliable even in summer -- antiques, vintage, bric-a-brac"},
        ],
    },
    "it": {
        "nights": 3,
        "accommodation_per_night": (150, 260),
        "accommodation_source": "accommodation",
        "activities": [
            {"name": "Cinque Terre Card (trails + trains, per day)", "per_person_low": 21, "per_person_high": 24, "source": "riviera_activities", "in_budget": True},
            {"name": "Boat tour between villages", "per_person_low": 25, "per_person_high": 35, "source": "riviera_activities", "in_budget": False},
            {"name": "No dedicated flea market in Cinque Terre villages", "per_person_low": 0, "per_person_high": 0, "source": "flea_markets", "in_budget": False, "note": "honest gap -- these are tiny fishing villages, no real flea market; closest options are in La Spezia or Genoa, outside the planned itinerary"},
        ],
    },
    "switzerland": {
        "nights": 3,
        "accommodation_per_night": (350, 550),
        "accommodation_source": "switzerland_costs",
        "activities": [
            {"name": "Jungfraujoch 'Top of Europe'", "per_person_low": 250, "per_person_high": 295, "source": "switzerland_costs", "in_budget": True},
            {"name": "Swiss Travel Pass (multi-day)", "per_person_low": 150, "per_person_high": 220, "source": "switzerland_costs", "in_budget": False},
            {"name": "Grindelwald First + cliff walk", "per_person_low": 90, "per_person_high": 90, "source": "switzerland_costs", "in_budget": False},
            {"name": "Trummelbach Falls", "per_person_low": 14, "per_person_high": 14, "source": "switzerland_costs", "in_budget": False},
            {"name": "Lauterbrunnen valley walk", "per_person_low": 0, "per_person_high": 0, "source": "switzerland_costs", "in_budget": False, "note": "free"},
            {"name": "Harder Kulm viewpoint (Interlaken)", "per_person_low": 24, "per_person_high": 24, "source": "switzerland_costs", "in_budget": False},
            {"name": "Zurich Kanzlei Flohmarkt", "per_person_low": 0, "per_person_high": 0, "source": "flea_markets", "in_budget": False, "note": "free to browse; Switzerland's largest flea market, 400+ vendors -- only if routing through Zurich (Interlaken itself has no real flea market, it's a small mountain town)"},
        ],
    },
}


def compute_destination_cost_breakdown(party_size, food_rates):
    """The single place accommodation + food + activities dollars get
    computed PER DESTINATION -- itinerary stops and alternatives alike.
    Every destination gets a total_cost_low/high (accommodation + food +
    only the "in_budget" must-do activities) so any two destinations,
    including alternatives like Switzerland, can be directly compared
    on the same basis. Returns the per-destination breakdown AND the
    itinerary-wide totals that feed the pretrip cash timeline / Costs tab."""
    breakdown = {}
    itin_accom_low = itin_accom_high = 0.0
    itin_activities_low = itin_activities_high = 0.0
    itinerary_keys = ["naples", "pelo", "crete", "athens"]

    for dest, info in DESTINATION_COST_ATOMS.items():
        nights = info["nights"]
        accom_low = info["accommodation_per_night"][0] * nights
        accom_high = info["accommodation_per_night"][1] * nights

        act_in_budget_low = sum(a["per_person_low"] for a in info["activities"] if a["in_budget"]) * party_size
        act_in_budget_high = sum(a["per_person_high"] for a in info["activities"] if a["in_budget"]) * party_size
        act_all_low = sum(a["per_person_low"] for a in info["activities"]) * party_size
        act_all_high = sum(a["per_person_high"] for a in info["activities"]) * party_size

        food_rate_low, food_rate_high = food_rates[dest]
        food_low = food_rate_low * party_size * nights
        food_high = food_rate_high * party_size * nights

        total_low = accom_low + food_low + act_in_budget_low
        total_high = accom_high + food_high + act_in_budget_high

        breakdown[dest] = {
            "nights": nights,
            "accommodation_per_night_low": info["accommodation_per_night"][0],
            "accommodation_per_night_high": info["accommodation_per_night"][1],
            "accommodation_total_low": round(accom_low, 2),
            "accommodation_total_high": round(accom_high, 2),
            "accommodation_source": info["accommodation_source"],
            "food_per_person_per_day_low": food_rate_low,
            "food_per_person_per_day_high": food_rate_high,
            "food_total_low": round(food_low, 2),
            "food_total_high": round(food_high, 2),
            "activities": info["activities"],
            "activities_in_budget_low": round(act_in_budget_low, 2),
            "activities_in_budget_high": round(act_in_budget_high, 2),
            "activities_all_low": round(act_all_low, 2),
            "activities_all_high": round(act_all_high, 2),
            "total_cost_low": round(total_low, 2),
            "total_cost_high": round(total_high, 2),
        }

        if dest in itinerary_keys:
            itin_accom_low += accom_low
            itin_accom_high += accom_high
            itin_activities_low += act_in_budget_low
            itin_activities_high += act_in_budget_high

    return breakdown, (round(itin_accom_low, 2), round(itin_accom_high, 2)), (round(itin_activities_low, 2), round(itin_activities_high, 2))


# ============================================================
# ASSUMPTIONS
# Every number below is editable. Ranges are (low, high) in USD unless noted.
# Change these, rerun the script, and every downstream chart updates.
# ============================================================

ASSUMPTIONS = {

    # ---- Pre-trip cash outlay, in weeks before departure ----
    # "weeks_before" = how many weeks before Day 1 of the trip this needs to be paid.
    "pretrip_milestones": [
        {
            "weeks_before": 10,
            "item": "Transatlantic flights (RDU <-> Rome / Athens)",
            "amount_low": 3500, "amount_high": 5500,
            "source": "flights_transatlantic",
        },
        {
            "weeks_before": 8,
            "item": "Intra-Europe flights (Rome-Athens, Athens<->Crete)",
            "amount_low": 520, "amount_high": 920,
            "source": "flights_intra_europe",
        },
        {
            "weeks_before": 6,
            "item": "Accommodation (4 Airbnb bookings, full or majority prepaid)",
            "amount_low": None, "amount_high": None,  # computed from DESTINATION_COST_ATOMS, see compute_pretrip_timeline
            "source": "accommodation",
            "computed": "accommodation",
        },
        {
            "weeks_before": 3,
            "item": "Pre-bookable activities & entry tickets (Colosseum, Acropolis)",
            "amount_low": None, "amount_high": None,  # computed from DESTINATION_COST_ATOMS, see compute_pretrip_timeline
            "source": "rome_activities",
            "computed": "activities",
        },
    ],

    # ---- In-trip daily costs ----
    # Per-person-per-day food range by destination "zone". Multiply by
    # party size at render time -- kept per-person here so party size is a
    # single editable knob, not baked into every number.
    "food_per_person_per_day": {
        "naples":   (18, 27),    # lower cost than Rome, source: naples_amalfi_activities
        "rome":     (20, 30),    # kept for Rome's alternative detail page
        "pelo":     (12.5, 20),
        "crete":    (12.5, 20),
        "athens":   (15, 22.5),
        "transit":  (7.5, 10),   # airport/in-flight food on travel days
        "amalfi":   (22, 32),    # source: naples_amalfi_activities -- pricier than Naples
        "fr":       (25, 38),    # source: riviera_activities -- French Riviera dining
        "it":       (18, 26),    # source: riviera_activities -- cheaper than Rome, pricier than rural Greece
        "switzerland": (50, 85), # source: switzerland_costs -- lunch special $20-35, dinner $35-50; ~2x every other option
    },

    "party_size": 4,  # family of 4; family-of-2 figures are derived, not re-typed

    # One-time in-trip costs, tagged to the specific day they land on
    # (day numbers match the 16-day itinerary in the Gantt/Time-budget tabs)
    "intrip_lump_costs": [
        {"day": 5,  "item": "Car rental (full charge at Peloponnese pickup)", "amount_low": 300, "amount_high": 500, "source": "peloponnese_activities"},
        {"day": 5,  "item": "Gas + tolls (Peloponnese driving)", "amount_low": 75, "amount_high": 100, "source": "peloponnese_activities"},
        {"day": 10, "item": "Gas + tolls (Crete driving)", "amount_low": 75, "amount_high": 100, "source": "crete_activities"},
        {"day": 1,  "item": "Airport transfer (arrival Naples)", "amount_low": 40, "amount_high": 70, "source": "naples_flights"},
        {"day": 5,  "item": "Airport transfer (Peloponnese leg)", "amount_low": 60, "amount_high": 90, "source": "airport_data"},
        {"day": 9,  "item": "Airport transfer (Crete leg)", "amount_low": 60, "amount_high": 90, "source": "airport_data"},
        {"day": 14, "item": "Airport transfer (Athens leg)", "amount_low": 60, "amount_high": 90, "source": "airport_data"},
        {"day": 10, "item": "Samaria Gorge entry fee (cash, on trail)", "amount_low": 20, "amount_high": 24, "source": "crete_activities"},
        # NOTE: Colosseum/Vatican/Acropolis tickets are NOT listed here --
        # they're bought online in advance and already counted in the
        # pretrip "Pre-bookable activities & entry tickets" milestone.
        # Listing them again here would double-count the same dollars.
    ],

    # ---- Itemized sub-components of every travel-heavy day ----
    # This is the ground truth behind the Time Budget tab's "Travel" hours.
    # Nothing here is a single guessed lump -- each line is either sourced
    # (airport arrival-early recommendations, immigration wait averages,
    # known transit times) or flagged as a judgment call (packing time,
    # baggage claim, hotel check-in buffer -- things no website publishes
    # a number for). Summing these per day REPLACES the old single
    # "travel hours" guess; sleep/eat/visit for that day are recomputed
    # to still fit in 24 hours once the real travel total is known.
    "travel_itemized": {
        1: [  # RDU departure + majority of the overnight flight
            {"label": "Pack and get ready", "hours": 1.0, "source": None},
            {"label": "Wait for ride to airport (own car/rideshare)", "hours": 0.15, "source": None},
            {"label": "Drive to RDU airport + park", "hours": 0.6, "source": "airport_data"},
            {"label": "Airport arrival buffer (check-in, security, gate wait)", "hours": 3.0, "source": "airport_data", "note": "RDU recommends 3 hrs before international departure"},
            {"label": "Flight RDU -> Naples via connection (boarding + bulk of flight)", "hours": 8.25, "source": "naples_flights", "note": "No direct RDU-NAP route; connects via CDG/PHL/ATL, ~11-13 hrs total"},
        ],
        2: [  # Remainder of flight + arrival into Naples
            {"label": "Remaining flight time + connection + descent", "hours": 4.0, "source": "naples_flights"},
            {"label": "Deplane + immigration/passport control (non-EU)", "hours": 0.75, "source": "airport_data", "note": "similar to other Italian airports, ~30-40 min average"},
            {"label": "Baggage claim", "hours": 0.5, "source": None},
            {"label": "Wait for taxi/shuttle at NAP arrivals", "hours": 0.1, "source": None},
            {"label": "Taxi/shuttle NAP airport -> Naples hotel", "hours": 0.3, "source": "naples_flights"},
            {"label": "Hotel check-in", "hours": 0.5, "source": None},
        ],
        5: [  # Rome -> Peloponnese (flight + drive)
            {"label": "Hotel check-out, pack up", "hours": 0.5, "source": None},
            {"label": "Wait for taxi to airport", "hours": 0.15, "source": None},
            {"label": "Taxi to FCO airport", "hours": 0.6, "source": "airport_data"},
            {"label": "Airport arrival buffer (intra-Europe)", "hours": 2.0, "source": "airport_data"},
            {"label": "Flight FCO -> ATH", "hours": 2.0, "source": "flights_intra_europe"},
            {"label": "Deplane + baggage claim", "hours": 0.5, "source": None},
            {"label": "Rental car pickup", "hours": 0.5, "source": None},
            {"label": "Drive ATH airport -> Nafplio", "hours": 2.0, "source": "peloponnese_activities"},
            {"label": "Check-in Nafplio accommodation", "hours": 0.5, "source": None},
        ],
        9: [  # Peloponnese -> Crete (drive + flight)
            {"label": "Check-out, pack up", "hours": 0.5, "source": None},
            {"label": "Drive Nafplio -> ATH airport", "hours": 2.0, "source": "peloponnese_activities"},
            {"label": "Return rental car", "hours": 0.3, "source": None},
            {"label": "Airport arrival buffer (domestic)", "hours": 1.5, "source": "airport_data"},
            {"label": "Flight ATH -> CHQ", "hours": 0.92, "source": "flights_intra_europe"},
            {"label": "Deplane + baggage claim", "hours": 0.4, "source": None},
            {"label": "Local car rental pickup (Chania)", "hours": 0.4, "source": None},
            {"label": "Check-in Chania accommodation", "hours": 0.5, "source": None},
        ],
        14: [  # Crete -> Athens (flight)
            {"label": "Check-out, return rental car", "hours": 0.75, "source": None},
            {"label": "Wait for taxi to CHQ airport", "hours": 0.1, "source": None},
            {"label": "Taxi to CHQ airport", "hours": 0.2, "source": "airport_data"},
            {"label": "Airport arrival buffer (CHQ gets very busy in July)", "hours": 2.0, "source": "airport_data", "note": "CHQ peak security waits 60-90 min in July"},
            {"label": "Flight CHQ -> ATH", "hours": 0.92, "source": "flights_intra_europe"},
            {"label": "Deplane + baggage claim", "hours": 0.4, "source": None},
            {"label": "Wait for metro/taxi at ATH arrivals", "hours": 0.1, "source": None},
            {"label": "Metro/taxi ATH airport -> Athens hotel", "hours": 0.57, "source": "airport_data"},
            {"label": "Hotel check-in", "hours": 0.5, "source": None},
        ],
        16: [  # Athens -> depart RDU
            {"label": "Check-out, get ready", "hours": 0.5, "source": None},
            {"label": "Wait for metro/taxi to ATH airport", "hours": 0.1, "source": None},
            {"label": "Metro/taxi to ATH airport", "hours": 0.57, "source": "airport_data"},
            {"label": "Airport arrival buffer (international)", "hours": 3.0, "source": "airport_data"},
            {"label": "Flight ATH -> RDU (with connection)", "hours": 15.0, "source": "flights_transatlantic"},
            {"label": "Deplane + immigration/customs at RDU", "hours": 0.5, "source": "airport_data"},
            {"label": "Baggage claim", "hours": 0.4, "source": None},
            {"label": "Drive home from RDU", "hours": 0.4, "source": "airport_data"},
        ],
        10: [  # Samaria Gorge day -- lighter itemization, same principle
            {"label": "Drive Chania -> Samaria trailhead", "hours": 0.75, "source": "crete_activities"},
            {"label": "Drive/ferry return from Agia Roumeli", "hours": 0.75, "source": "crete_activities"},
        ],
    },

    # ---- The 16-day itinerary skeleton, shared with the Time Budget / Gantt tabs ----
    # dest values: rome, pelo, crete, athens, transfer_pelo, transfer_crete, transfer_athens, travel_out, travel_back
    "day_model": [
        {"day": 1,  "label": "Depart RDU (overnight flight)",              "dest": "travel_out"},
        {"day": 2,  "label": "Arrive Naples, settle in",                   "dest": "naples"},
        {"day": 3,  "label": "Naples full day",                            "dest": "naples"},
        {"day": 4,  "label": "Naples full day (last night)",               "dest": "naples"},
        {"day": 5,  "label": "Naples -> Peloponnese (flight + drive)",     "dest": "transfer_pelo"},
        {"day": 6,  "label": "Peloponnese full day",                       "dest": "pelo"},
        {"day": 7,  "label": "Peloponnese full day",                       "dest": "pelo"},
        {"day": 8,  "label": "Peloponnese full day (last night)",          "dest": "pelo"},
        {"day": 9,  "label": "Peloponnese -> Crete (drive + flight)",      "dest": "transfer_crete"},
        {"day": 10, "label": "Crete - Samaria Gorge (5am start)",          "dest": "crete"},
        {"day": 11, "label": "Crete full day",                            "dest": "crete"},
        {"day": 12, "label": "Crete full day",                            "dest": "crete"},
        {"day": 13, "label": "Crete full day (last night)",               "dest": "crete"},
        {"day": 14, "label": "Crete -> Athens (flight)",                  "dest": "transfer_athens"},
        {"day": 15, "label": "Athens full day (last night)",              "dest": "athens"},
        {"day": 16, "label": "Athens -> depart RDU (overnight flight)",   "dest": "travel_back"},
    ],
}

# ---- Baseline sleep and eating hours per day (judgment calls) ----
# Assumes 10 hrs sleep/night unless the schedule genuinely doesn't allow
# it. Eat hours are TIME spent eating (breakfast/lunch/dinner), separate
# from the food dollar-cost model above. Travel hours are NOT listed here
# -- they're computed from ASSUMPTIONS["travel_itemized"] where a day has
# an entry, or default to 1.0h (local transit) otherwise.
BASE_SLEEP_HOURS = {1:5, 2:10, 3:10, 4:10, 5:10, 6:10, 7:10, 8:10, 9:10, 10:7, 11:10, 12:10, 13:10, 14:10, 15:10, 16:1}
BASE_EAT_HOURS =   {1:2,  2:3,  3:3,  4:3,  5:2.5,6:3,  7:3,  8:3,  9:2.5,10:2, 11:3,  12:3,  13:3,  14:2.5,15:3,  16:1.5}
DEFAULT_LOCAL_TRAVEL_HOURS = 1.0


def compute_time_budget(a):
    """Travel hours per day = sum of ASSUMPTIONS['travel_itemized'][day] if
    present, else a flat local-transit default. Visit hours = whatever's
    left of the 24-hour day after sleep + travel + eat -- never a
    separately guessed number, so an itemization correction here (e.g.
    airport waits taking longer than expected) automatically eats into
    visit time instead of silently breaking the day's total."""
    itemized = a.get("travel_itemized", {})
    out = []
    for d in a["day_model"]:
        day = d["day"]
        sleep_h = BASE_SLEEP_HOURS[day]
        eat_h = BASE_EAT_HOURS[day]
        items = itemized.get(day)
        if items:
            travel_h = round(sum(i["hours"] for i in items), 2)
        else:
            travel_h = DEFAULT_LOCAL_TRAVEL_HOURS
        visit_h = round(24 - sleep_h - travel_h - eat_h, 2)
        out.append({
            "day": day,
            "label": d["label"],
            "dest": d["dest"],
            "sleep": sleep_h,
            "travel": travel_h,
            "eat": eat_h,
            "visit": visit_h,
            "travel_itemized": items,  # None if this day has no itemization
        })
    return out


# Maps a day's "dest" tag to which food-cost zone applies that day
DEST_TO_FOOD_ZONE = {
    "naples": "naples",
    "pelo": "pelo",
    "crete": "crete",
    "athens": "athens",
    "transfer_pelo": "pelo",       # arriving that evening, eating in Peloponnese
    "transfer_crete": "crete",     # arriving that evening, eating in Crete
    "transfer_athens": "athens",   # arriving that evening, eating in Athens
    "travel_out": "transit",
    "travel_back": "transit",
}


def compute_pretrip_timeline(a, party_size):
    """Returns milestones sorted furthest-out first, with running cumulative
    low/high totals. weeks_before is converted to a negative day-offset
    (day 0 = trip start) so it can share an axis with the in-trip burn.
    Milestones marked "computed" pull their amount from
    compute_destination_cost_breakdown() -- the same atoms shown on each
    destination's detail page -- instead of a separately hand-typed number."""
    _, itin_accom, itin_activities = compute_destination_cost_breakdown(party_size, a["food_per_person_per_day"])
    computed_amounts = {
        "accommodation": itin_accom,
        "activities": itin_activities,
    }

    milestones = sorted(a["pretrip_milestones"], key=lambda m: -m["weeks_before"])
    out = []
    cum_low, cum_high = 0.0, 0.0
    for m in milestones:
        if m.get("computed"):
            amount_low, amount_high = computed_amounts[m["computed"]]
        else:
            amount_low, amount_high = m["amount_low"], m["amount_high"]

        cum_low += amount_low
        cum_high += amount_high
        out.append({
            "day_offset": -m["weeks_before"] * 7,
            "weeks_before": m["weeks_before"],
            "item": m["item"],
            "amount_low": amount_low,
            "amount_high": amount_high,
            "cumulative_low": round(cum_low, 2),
            "cumulative_high": round(cum_high, 2),
            "source": m["source"],
        })
    return out, cum_low, cum_high


def compute_intrip_burn(a, pretrip_cum_low, pretrip_cum_high):
    """Returns one entry per trip day with that day's spend (food + any
    lump costs landing on that day) and a cumulative total that continues
    on from the pre-trip cumulative, so the two charts share one number line."""
    party = a["party_size"]
    food_zone = a["food_per_person_per_day"]
    lumps_by_day = {}
    for lump in a["intrip_lump_costs"]:
        lumps_by_day.setdefault(lump["day"], []).append(lump)

    out = []
    cum_low, cum_high = pretrip_cum_low, pretrip_cum_high
    for d in a["day_model"]:
        zone = DEST_TO_FOOD_ZONE[d["dest"]]
        f_low, f_high = food_zone[zone]
        day_food_low = f_low * party
        day_food_high = f_high * party

        day_lump_low = sum(l["amount_low"] for l in lumps_by_day.get(d["day"], []))
        day_lump_high = sum(l["amount_high"] for l in lumps_by_day.get(d["day"], []))

        day_total_low = day_food_low + day_lump_low
        day_total_high = day_food_high + day_lump_high

        cum_low += day_total_low
        cum_high += day_total_high

        out.append({
            "day": d["day"],
            "label": d["label"],
            "dest": d["dest"],
            "food_low": round(day_food_low, 2),
            "food_high": round(day_food_high, 2),
            "lump_low": round(day_lump_low, 2),
            "lump_high": round(day_lump_high, 2),
            "lump_items": [l["item"] for l in lumps_by_day.get(d["day"], [])],
            "day_total_low": round(day_total_low, 2),
            "day_total_high": round(day_total_high, 2),
            "cumulative_low": round(cum_low, 2),
            "cumulative_high": round(cum_high, 2),
        })
    return out, cum_low, cum_high


def compute_family_of_2(pretrip, intrip, grand_low, grand_high):
    """Scales the family-of-4 model to 2 adults. Flights/food/activities
    scale 1:1 per person (halve). Accommodation and car rental don't
    (assume 65% and 70% of the 4-person cost respectively -- a couple
    doesn't get a half-price apartment)."""
    ACCOM_SCALE = 0.65
    CAR_SCALE = 0.70
    PERPERSON_SCALE = 0.50

    f2_pretrip = []
    cum_low, cum_high = 0.0, 0.0
    for m in pretrip:
        if "Accommodation" in m["item"]:
            scale = ACCOM_SCALE
        else:
            scale = PERPERSON_SCALE
        low = m["amount_low"] * scale
        high = m["amount_high"] * scale
        cum_low += low
        cum_high += high
        f2_pretrip.append({**m, "amount_low": round(low, 2), "amount_high": round(high, 2),
                            "cumulative_low": round(cum_low, 2), "cumulative_high": round(cum_high, 2)})

    f2_intrip = []
    for d in intrip:
        # food scales 1:1 per person (already per-person in the model -> just party_size change,
        # here approximated by halving the 4-person total)
        food_low = d["food_low"] * PERPERSON_SCALE
        food_high = d["food_high"] * PERPERSON_SCALE
        # car rental scaled at CAR_SCALE, everything else per-person at 0.5
        lump_low = 0.0
        lump_high = 0.0
        for item_name in d["lump_items"]:
            pass  # detail not re-derived here; approximate below
        lump_low = d["lump_low"] * (CAR_SCALE if "Car rental" in " ".join(d["lump_items"]) else PERPERSON_SCALE)
        lump_high = d["lump_high"] * (CAR_SCALE if "Car rental" in " ".join(d["lump_items"]) else PERPERSON_SCALE)

        day_total_low = food_low + lump_low
        day_total_high = food_high + lump_high
        cum_low += day_total_low
        cum_high += day_total_high
        f2_intrip.append({**d, "food_low": round(food_low, 2), "food_high": round(food_high, 2),
                           "lump_low": round(lump_low, 2), "lump_high": round(lump_high, 2),
                           "day_total_low": round(day_total_low, 2), "day_total_high": round(day_total_high, 2),
                           "cumulative_low": round(cum_low, 2), "cumulative_high": round(cum_high, 2)})

    return f2_pretrip, f2_intrip, round(cum_low, 2), round(cum_high, 2)


def add_cost_per_point(destination_totals, dest_cost_breakdown):
    """Value-for-money metric: $ spent per objective point earned. Lower
    is better -- it directly answers "which option gives the most trip
    value per dollar" instead of leaving cost and score as two separate
    numbers the reader has to mentally combine themselves."""
    for d in destination_totals:
        cb = dest_cost_breakdown.get(d["dest"])
        if cb and d["total"] > 0:
            d["cost_per_point_low"] = round(cb["total_cost_low"] / d["total"], 2)
            d["cost_per_point_high"] = round(cb["total_cost_high"] / d["total"], 2)
        else:
            d["cost_per_point_low"] = None
            d["cost_per_point_high"] = None
    return destination_totals


def main():
    a = ASSUMPTIONS
    party_size = a["party_size"]
    dest_cost_breakdown, itin_accom, itin_activities = compute_destination_cost_breakdown(party_size, ASSUMPTIONS["food_per_person_per_day"])
    pretrip, pre_cum_low, pre_cum_high = compute_pretrip_timeline(a, party_size)
    intrip, grand_low, grand_high = compute_intrip_burn(a, pre_cum_low, pre_cum_high)
    f2_pretrip, f2_intrip, f2_low, f2_high = compute_family_of_2(pretrip, intrip, grand_low, grand_high)
    time_budget = compute_time_budget(a)

    # sanity check: every day must sum to exactly 24 hours
    for row in time_budget:
        total = row["sleep"] + row["travel"] + row["eat"] + row["visit"]
        assert abs(total - 24) < 0.01, f"Day {row['day']} sums to {total}, not 24!"

    total_days = len(time_budget)
    total_hours = total_days * 24
    tb_sleep = sum(r["sleep"] for r in time_budget)
    tb_travel = sum(r["travel"] for r in time_budget)
    tb_eat = sum(r["eat"] for r in time_budget)
    tb_visit = sum(r["visit"] for r in time_budget)
    tb_awake = total_hours - tb_sleep
    time_budget_summary = {
        "total_hours": total_hours,
        "sleep_hours": round(tb_sleep, 1), "sleep_pct": round(tb_sleep / total_hours * 100, 1),
        "travel_hours": round(tb_travel, 1), "travel_pct": round(tb_travel / total_hours * 100, 1),
        "eat_hours": round(tb_eat, 1), "eat_pct": round(tb_eat / total_hours * 100, 1),
        "visit_hours": round(tb_visit, 1), "visit_pct": round(tb_visit / total_hours * 100, 1),
        "awake_hours": round(tb_awake, 1),
        "travel_pct_of_awake": round(tb_travel / tb_awake * 100, 1),
        "eat_pct_of_awake": round(tb_eat / tb_awake * 100, 1),
        "visit_pct_of_awake": round(tb_visit / tb_awake * 100, 1),
    }

    data = {
        "party_size": party_size,
        "pretrip_timeline": pretrip,
        "intrip_burn": intrip,
        "grand_total_low": round(grand_low, 2),
        "grand_total_high": round(grand_high, 2),
        "family_of_2": {
            "pretrip_timeline": f2_pretrip,
            "intrip_burn": f2_intrip,
            "grand_total_low": f2_low,
            "grand_total_high": f2_high,
        },
        "sources": SOURCES,
        "group_info": GROUP_INFO,
        "objectives": OBJECTIVES,
        "open_questions": OPEN_QUESTIONS,
        "crew_text": build_crew_text(),
        "destination_totals": add_cost_per_point(compute_destination_totals(), dest_cost_breakdown),
        "prior_visits": PRIOR_VISITS,
        "teen_feedback": TEEN_FEEDBACK,
        "destination_cost_breakdown": dest_cost_breakdown,
        "itinerary_accommodation_total": {"low": itin_accom[0], "high": itin_accom[1]},
        "itinerary_activities_total": {"low": itin_activities[0], "high": itin_activities[1]},
        "time_budget": time_budget,
        "time_budget_summary": time_budget_summary,
    }

    with open("trip_data.json", "w") as f:
        json.dump(data, f, indent=2)

    print(f"Pre-trip cumulative by day 0:  ${pre_cum_low:,.0f} - ${pre_cum_high:,.0f}")
    print(f"Grand total by end of trip:    ${grand_low:,.0f} - ${grand_high:,.0f}")
    print(f"Family of 2 grand total:       ${f2_low:,.0f} - ${f2_high:,.0f}")
    print("Wrote trip_data.json")


if __name__ == "__main__":
    main()
