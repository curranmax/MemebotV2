import urllib.request
import xml.etree.ElementTree as ET
import sys

sys.stdout.reconfigure(encoding='utf-8')

rss_url = 'https://www.youtube.com/feeds/videos.xml?channel_id=UCNKUkQV2R0JKakyE1vuC1lQ'
req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as response:
        xml_data = response.read()
        root = ET.fromstring(xml_data)
        ns = {'yt': 'http://www.youtube.com/xml/schemas/2015', 'atom': 'http://www.w3.org/2005/Atom'}
        for entry in root.findall('atom:entry', ns):
            title = entry.find('atom:title', ns).text
            link = entry.find('atom:link', ns).attrib['href']
            print(f"{title}: {link}")
except Exception as e:
    print(e)
