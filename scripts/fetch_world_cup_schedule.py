import urllib.request
import re
import os
import json
from datetime import datetime
import pytz

# Mappings of the 48 teams to their group stage groups.
TEAMS_TO_GROUP = {
    # Group A
    "Mexico": "Group A", "South Africa": "Group A", "South Korea": "Group A", "Czech Republic": "Group A",
    # Group B
    "Canada": "Group B", "Bosnia & Herzegovina": "Group B", "Qatar": "Group B", "Switzerland": "Group B",
    # Group C
    "Brazil": "Group C", "Morocco": "Group C", "Haiti": "Group C", "Scotland": "Group C",
    # Group D
    "United States": "Group D", "USA": "Group D", "Paraguay": "Group D", "Australia": "Group D", "Türkiye": "Group D", "Turkey": "Group D",
    # Group E
    "Germany": "Group E", "Curaçao": "Group E", "Ivory Coast": "Group E", "Ecuador": "Group E",
    # Group F
    "Netherlands": "Group F", "Japan": "Group F", "Sweden": "Group F", "Tunisia": "Group F",
    # Group G
    "Belgium": "Group G", "Egypt": "Group G", "Iran": "Group G", "New Zealand": "Group G",
    # Group H
    "Spain": "Group H", "Cape Verde": "Group H", "Saudi Arabia": "Group H", "Uruguay": "Group H",
    # Group I
    "France": "Group I", "Senegal": "Group I", "Iraq": "Group I", "Norway": "Group I",
    # Group J
    "Argentina": "Group J", "Algeria": "Group J", "Austria": "Group J", "Jordan": "Group J",
    # Group K
    "Portugal": "Group K", "DR Congo": "Group K", "Uzbekistan": "Group K", "Colombia": "Group K",
    # Group L
    "England": "Group L", "Croatia": "Group L", "Ghana": "Group L", "Panama": "Group L"
}

def fetch_and_parse_schedule():
    url = "https://www.matchesio.com/competition/world-cup/export/ics/"
    print(f"Downloading schedule from {url}...")
    
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        ics_data = response.read().decode('utf-8')

    print("Unfolding lines...")
    # Unfold lines according to ICS RFC 5545 (remove CRLF + space/tab)
    unfolded_lines = []
    for line in ics_data.splitlines():
        if line.startswith(' ') or line.startswith('\t'):
            if unfolded_lines:
                unfolded_lines[-1] += line[1:]
        else:
            unfolded_lines.append(line)

    print("Parsing events...")
    matches = []
    current_event = None

    for line in unfolded_lines:
        line = line.strip()
        if line == "BEGIN:VEVENT":
            current_event = {}
        elif line == "END:VEVENT":
            if current_event:
                parsed_match = process_event(current_event)
                if parsed_match:
                    matches.append(parsed_match)
            current_event = None
        elif current_event is not None:
            if ":" in line:
                key, val = line.split(":", 1)
                # Keep keys clean (e.g. ignore params like DTSTART;VALUE=DATE)
                key = key.split(";")[0]
                current_event[key] = val

    print(f"Successfully parsed {len(matches)} matches.")
    
    # Sort matches by kickoff time
    matches.sort(key=lambda m: m["datetime_utc"])

    # Remove the temporary UTC datetime objects before saving to JSON
    for m in matches:
        del m["datetime_utc"]

    # Write output to file
    out_dir = "data"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "world_cup_2026_schedule.json")
    
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(matches, f, indent=2, ensure_ascii=False)
        
    print(f"Schedule saved to {out_path}")

def process_event(event):
    summary = event.get("SUMMARY", "").strip()
    if not summary or " - " not in summary:
        return None

    team1, team2 = [t.strip() for t in summary.split(" - ", 1)]
    
    location = event.get("LOCATION", "").strip()
    city = event.get("X-MATCHESIO-CITY", "").strip()
    venue = f"{location}, {city}" if city else location

    dtstart = event.get("DTSTART", "").strip()
    if not dtstart:
        return None

    # Parse DTSTART as UTC
    # MatchesIO uses Zulu time: e.g. 20260611T190000Z
    try:
        utc_dt = datetime.strptime(dtstart, '%Y%m%dT%H%M%SZ').replace(tzinfo=pytz.utc)
    except Exception as e:
        print(f"Error parsing date {dtstart}: {e}")
        return None

    # Convert to US/Pacific timezone
    pacific_tz = pytz.timezone('US/Pacific')
    pacific_dt = utc_dt.astimezone(pacific_tz)

    time_pacific = pacific_dt.strftime('%I:%M %p')
    date_pacific = pacific_dt.strftime('%Y-%m-%d')

    # Determine Group
    group = None
    if team1 in TEAMS_TO_GROUP:
        group = TEAMS_TO_GROUP[team1]
    elif team2 in TEAMS_TO_GROUP:
        group = TEAMS_TO_GROUP[team2]
    else:
        # Fallback to stage in description
        description = event.get("DESCRIPTION", "").strip()
        desc_parts = [p.strip() for p in description.split('·')]
        
        # Look for knockout stage names
        knockout_keywords = ["Round of 32", "Round of 16", "Quarter-finals", "Semi-finals", "3rd Place Final", "Final"]
        for part in desc_parts:
            if any(kw in part for kw in knockout_keywords):
                group = part
                break
        
        if not group:
            group = "Knockout Stage"

    return {
        "team1": team1,
        "team2": team2,
        "group": group,
        "venue": venue,
        "time_pacific": time_pacific,
        "date_pacific": date_pacific,
        "datetime_utc": utc_dt.isoformat()
    }

if __name__ == "__main__":
    fetch_and_parse_schedule()
