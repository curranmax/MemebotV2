import re

DEFAULT_AUTO_REACTS_FNAME = 'data/auto_reacts.txt'


class AutoReactManager:

    def __init__(self, auto_reacts_fname=DEFAULT_AUTO_REACTS_FNAME):
        self.auto_reacts = getAutoReactsFromFile(auto_reacts_fname)

    def getEmotes(self, msg):
        return [ar.emote for ar in self.auto_reacts if ar.searchRegex(msg)]


def getAutoReactsFromFile(auto_reacts_fname=DEFAULT_AUTO_REACTS_FNAME):
    f = open(auto_reacts_fname, 'r')
    auto_reacts = []
    for line in f:
        regex_expr, emote = line.strip().split('\t')
        auto_reacts.append(AutoReact(regex_expr, emote))
    return auto_reacts


class AutoReact:

    def __init__(self, regex_expr, emote):
        self.regex = re.compile(regex_expr)
        self.emote = emote

    def searchRegex(self, msg):
        return self.regex.search(msg) is not None


if __name__ == "__main__":
    getAutoReactsFromFile()
