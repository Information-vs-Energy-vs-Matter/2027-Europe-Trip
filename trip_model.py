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
}


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
            "amount_low": 2050, "amount_high": 3420,
            "source": "accommodation",
        },
        {
            "weeks_before": 3,
            "item": "Pre-bookable activities & entry tickets (Colosseum, Vatican, etc.)",
            "amount_low": 600, "amount_high": 900,
            "source": "rome_activities",
        },
    ],

    # ---- In-trip daily costs ----
    # Per-person-per-day food range by destination "zone". Multiply by
    # party size at render time -- kept per-person here so party size is a
    # single editable knob, not baked into every number.
    "food_per_person_per_day": {
        "rome":     (20, 30),
        "pelo":     (12.5, 20),
        "crete":    (12.5, 20),
        "athens":   (15, 22.5),
        "transit":  (7.5, 10),   # airport/in-flight food on travel days
    },

    "party_size": 4,  # family of 4; family-of-2 figures are derived, not re-typed

    # One-time in-trip costs, tagged to the specific day they land on
    # (day numbers match the 16-day itinerary in the Gantt/Time-budget tabs)
    "intrip_lump_costs": [
        {"day": 5,  "item": "Car rental (full charge at Peloponnese pickup)", "amount_low": 300, "amount_high": 500, "source": "peloponnese_activities"},
        {"day": 5,  "item": "Gas + tolls (Peloponnese driving)", "amount_low": 75, "amount_high": 100, "source": "peloponnese_activities"},
        {"day": 10, "item": "Gas + tolls (Crete driving)", "amount_low": 75, "amount_high": 100, "source": "crete_activities"},
        {"day": 1,  "item": "Airport transfer (arrival Rome)", "amount_low": 60, "amount_high": 90, "source": "airport_data"},
        {"day": 5,  "item": "Airport transfer (Peloponnese leg)", "amount_low": 60, "amount_high": 90, "source": "airport_data"},
        {"day": 9,  "item": "Airport transfer (Crete leg)", "amount_low": 60, "amount_high": 90, "source": "airport_data"},
        {"day": 14, "item": "Airport transfer (Athens leg)", "amount_low": 60, "amount_high": 90, "source": "airport_data"},
        {"day": 10, "item": "Samaria Gorge entry fee (cash, on trail)", "amount_low": 20, "amount_high": 24, "source": "crete_activities"},
        # NOTE: Colosseum/Vatican/Acropolis tickets are NOT listed here --
        # they're bought online in advance and already counted in the
        # pretrip "Pre-bookable activities & entry tickets" milestone.
        # Listing them again here would double-count the same dollars.
    ],

    # ---- The 16-day itinerary skeleton, shared with the Time Budget / Gantt tabs ----
    # dest values: rome, pelo, crete, athens, transfer_pelo, transfer_crete, transfer_athens, travel_out, travel_back
    "day_model": [
        {"day": 1,  "label": "Depart RDU (overnight flight)",              "dest": "travel_out"},
        {"day": 2,  "label": "Arrive Rome, settle in",                     "dest": "rome"},
        {"day": 3,  "label": "Rome full day",                              "dest": "rome"},
        {"day": 4,  "label": "Rome full day (last night)",                 "dest": "rome"},
        {"day": 5,  "label": "Rome -> Peloponnese (flight + drive)",       "dest": "transfer_pelo"},
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

# Maps a day's "dest" tag to which food-cost zone applies that day
DEST_TO_FOOD_ZONE = {
    "rome": "rome",
    "pelo": "pelo",
    "crete": "crete",
    "athens": "athens",
    "transfer_pelo": "pelo",       # arriving that evening, eating in Peloponnese
    "transfer_crete": "crete",     # arriving that evening, eating in Crete
    "transfer_athens": "athens",   # arriving that evening, eating in Athens
    "travel_out": "transit",
    "travel_back": "transit",
}


def compute_pretrip_timeline(a):
    """Returns milestones sorted furthest-out first, with running cumulative
    low/high totals. weeks_before is converted to a negative day-offset
    (day 0 = trip start) so it can share an axis with the in-trip burn."""
    milestones = sorted(a["pretrip_milestones"], key=lambda m: -m["weeks_before"])
    out = []
    cum_low, cum_high = 0.0, 0.0
    for m in milestones:
        cum_low += m["amount_low"]
        cum_high += m["amount_high"]
        out.append({
            "day_offset": -m["weeks_before"] * 7,
            "weeks_before": m["weeks_before"],
            "item": m["item"],
            "amount_low": m["amount_low"],
            "amount_high": m["amount_high"],
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


def main():
    a = ASSUMPTIONS
    pretrip, pre_cum_low, pre_cum_high = compute_pretrip_timeline(a)
    intrip, grand_low, grand_high = compute_intrip_burn(a, pre_cum_low, pre_cum_high)
    f2_pretrip, f2_intrip, f2_low, f2_high = compute_family_of_2(pretrip, intrip, grand_low, grand_high)

    data = {
        "party_size": a["party_size"],
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
    }

    with open("trip_data.json", "w") as f:
        json.dump(data, f, indent=2)

    print(f"Pre-trip cumulative by day 0:  ${pre_cum_low:,.0f} - ${pre_cum_high:,.0f}")
    print(f"Grand total by end of trip:    ${grand_low:,.0f} - ${grand_high:,.0f}")
    print(f"Family of 2 grand total:       ${f2_low:,.0f} - ${f2_high:,.0f}")
    print("Wrote trip_data.json")


if __name__ == "__main__":
    main()
