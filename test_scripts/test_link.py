import re
from datetime import datetime

def test_link_logic(summary, game_date):
    import urllib.request
    import xml.etree.ElementTree as ET
    
    rss_url = 'https://www.youtube.com/feeds/videos.xml?channel_id=UCNKUkQV2R0JKakyE1vuC1lQ'
    req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            ns = {'yt': 'http://www.youtube.com/xml/schemas/2015', 'atom': 'http://www.w3.org/2005/Atom'}
            
            date_str1 = game_date.strftime('%B %d, %Y').replace(' 0', ' ')
            date_str2 = game_date.strftime('%b %d, %Y').replace(' 0', ' ')
            
            summary_words = set(w.lower() for w in re.findall(r'[a-zA-Z]+', summary) if len(w) >= 3)
            
            best_match = None
            best_score = -1
            
            for entry in root.findall('atom:entry', ns):
                title_elem = entry.find('atom:title', ns)
                if title_elem is None:
                    continue
                title = title_elem.text
                link = entry.find('atom:link', ns).attrib['href']
                
                title_words = set(w.lower() for w in re.findall(r'[a-zA-Z]+', title))
                word_overlap = 0
                for sw in summary_words:
                    for tw in title_words:
                        if sw in tw or tw in sw:
                            word_overlap += 1
                            break
                            
                score = word_overlap
                
                if date_str1.lower() in title.lower() or date_str2.lower() in title.lower():
                    score += 5
                    
                is_pwhl = 'pwhl' in title.lower()
                
                if (score > 0 or is_pwhl) and score > best_score:
                    # We only want to match if it has some overlap or if it's the only PWHL video of the day
                    # Actually, we need some overlap to ensure it's the right game, 
                    # OR we need the date to match.
                    if word_overlap > 0 or score >= 5:
                        best_score = score
                        best_match = link
                        
            return best_match
    except Exception as e:
        print(f'Error fetching YouTube link: {e}')
        return None

print(test_link_logic("NY @ BOS", datetime(2026, 4, 25)))
