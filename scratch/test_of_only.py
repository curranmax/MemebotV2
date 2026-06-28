import urllib.request
import re
import os
import json
from datetime import datetime, timedelta
import pytz

GROUND_TO_VENUE = {
    "Los Angeles (Inglewood)": "SoFi Stadium, Inglewood",
    "Los Angeles": "SoFi Stadium, Inglewood",
    "Inglewood": "SoFi Stadium, Inglewood",
    "Boston (Foxborough)": "Gillette Stadium, Boston",
    "Boston": "Gillette Stadium, Boston",
    "Foxborough": "Gillette Stadium, Boston",
    "Monterrey (Guadalupe)": "Estadio BBVA, Monterrey",
    "Monterrey": "Estadio BBVA, Monterrey",
    "Houston": "NRG Stadium, Houston",
    "New York/New Jersey (East Rutherford)": "MetLife Stadium, East Rutherford",
    "New York/New Jersey": "MetLife Stadium, East Rutherford",
    "East Rutherford": "MetLife Stadium, East Rutherford",
    "Dallas (Arlington)": "AT&T Stadium, Arlington",
    "Dallas": "AT&T Stadium, Arlington",
    "Arlington": "AT&T Stadium, Arlington",
    "Mexico City": "Estadio Banorte, Mexico City",
    "Atlanta": "Mercedes-Benz Stadium, Atlanta",
    "San Francisco Bay Area (Santa Clara)": "Levi's Stadium, Santa Clara",
    "San Francisco": "Levi's Stadium, Santa Clara",
    "Santa Clara": "Levi's Stadium, Santa Clara",
    "Seattle": "Lumen Field, Seattle",
    "Toronto": "BMO Field, Toronto",
    "Vancouver": "BC Place, Vancouver",
    "Miami (Miami Gardens)": "Hard Rock Stadium, Miami Gardens",
    "Miami": "Hard Rock Stadium, Miami Gardens",
    "Miami Gardens": "Hard Rock Stadium, Miami Gardens",
    "Kansas City": "Arrowhead Stadium, Kansas City",
    "Philadelphia": "Lincoln Financial Field, Philadelphia",
    "Guadalajara (Zapopan)": "Estadio Akron, Zapopan",
    "Guadalajara": "Estadio Akron, Zapopan",
    "Zapopan": "Estadio Akron, Zapopan"
}

def parse_openfootball_time(date_str, time_str):
    match = re.match(r'^(\d{2}):(\d{2})\s+UTC(?:([+-]\d+))?$', time_str)
    if not match:
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except Exception:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.replace(tzinfo=pytz.utc)
    
    hour = int(match.group(1))
    minute = int(match.group(2))
    offset_str = match.group(3)
    offset = int(offset_str) if offset_str else 0
    
    dt = datetime.strptime(f"{date_str} {hour:02d}:{minute:02d}", "%Y-%m-%d %H:%M")
    utc_dt = dt - timedelta(hours=offset)
    return utc_dt.replace(tzinfo=pytz.utc)

def test():
    openfootball_url = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"
    print(f"Downloading openfootball schedule from {openfootball_url}...")
    req_of = urllib.request.Request(openfootball_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req_of) as response:
        of_data = json.loads(response.read().decode('utf-8'))

    parsed_matches = []
    for of_match in of_data["matches"]:
        of_date = of_match["date"]
        of_time = of_match["time"]
        utc_dt = parse_openfootball_time(of_date, of_time)

        # Decide team names
        team1 = of_match["team1"].strip()
        team2 = of_match["team2"].strip()

        # Determine Group
        round_name = of_match.get("round", "")
        knockout_keywords = ["Round of 32", "Round of 16", "Quarter-finals", "Semi-finals", "3rd Place Final", "Final"]
        if round_name in knockout_keywords:
            group = round_name
        else:
            group = of_match.get("group", "Group Stage")

        # Determine Venue
        ground = of_match.get("ground", "")
        if ground in GROUND_TO_VENUE:
            venue = GROUND_TO_VENUE[ground]
        else:
            venue = ground

        # Time/date Pacific
        pacific_tz = pytz.timezone('US/Pacific')
        pacific_dt = utc_dt.astimezone(pacific_tz)
        time_pacific = pacific_dt.strftime('%I:%M %p')
        date_pacific = pacific_dt.strftime('%Y-%m-%d')

        parsed_matches.append({
            "team1": team1,
            "team2": team2,
            "group": group,
            "venue": venue,
            "time_pacific": time_pacific,
            "date_pacific": date_pacific,
            "num": of_match.get("num", 0)
        })

    print(f"Total matches: {len(parsed_matches)}")
    r32 = [m for m in parsed_matches if m["group"] == "Round of 32"]
    for m in r32:
        print(f"#{m['num'] - 72}: {m['team1']} vs {m['team2']} at {m['venue']} on {m['date_pacific']} {m['time_pacific']}")

if __name__ == "__main__":
    test()
