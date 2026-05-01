import re
summary = "MIN @ BOS"
title = "PWHL: Minnesota Frost at Boston Fleet | April 25, 2026"

summary_words = set(w.lower() for w in re.findall(r'[a-zA-Z]+', summary) if len(w) >= 3)
title_words = set(w.lower() for w in re.findall(r'[a-zA-Z]+', title))

word_overlap = 0
for sw in summary_words:
    for tw in title_words:
        if sw in tw or tw in sw:
            word_overlap += 1
            break
print("Overlap:", word_overlap)
