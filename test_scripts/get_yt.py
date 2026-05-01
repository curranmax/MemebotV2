import urllib.request
import re

html = urllib.request.urlopen('https://www.youtube.com/@thepwhlofficial').read().decode('utf-8')
match = re.search(r'"externalId":"(UC[a-zA-Z0-9_-]+)"', html)
if match:
    print(match.group(1))
