from collections import defaultdict
import random
import re

ALPHABET = {
    'a': ['🇦', '🅰️'],
    'b': ['🇧', '🅱️'],
    'c': ['🇨', '©️'],
    'd': ['🇩'],
    'e': ['🇪', '📧'],
    'f': ['🇫'],
    'g': ['🇬'],
    'h': ['🇭', '♓'],
    'i': ['🇮'],
    'j': ['🇯'],
    'k': ['🇰'],
    'l': ['🇱'],
    'm': ['🇲', 'Ⓜ️', '♏', '♍'],
    'n': ['🇳', '♑'],
    'o': ['🇴', '⭕', '🅾️'],
    'p': ['🇵', '🅿️'],
    'q': ['🇶', '👁‍🗨'],
    'r': ['🇷', '®️'],
    's': ['🇸', '💲'],
    't': ['🇹', '✝️'],
    'u': ['🇺'],
    'v': ['🇻', '♈'],
    'w': ['🇼'],
    'x': ['🇽', '✖️'],
    'y': ['🇾'],
    'z': ['🇿'],
    'ab': ['🆎'],
    'oo': ['➿'],
    'soon': ['🔜'],
    'top': ['🔝'],
    'on': ['🔛'],
    'back': ['🔙'],
    'end': ['🔚'],
    'tm': ['™️'],
    'free': ['🆓'],
    'new': ['🆕'],
    'cool': ['🆒'],
    'up': ['🆙'],
    'ok': ['🆗'],
    'ng': ['🆖'],
    'wc': ['🚾'],
    'atm': ['🏧'],
    'zzz': ['💤'],
    'sos': ['🆘'],
    'cl': ['🆑'],
    'vs': ['🆚'],
    'off': ['📴'],
    'id': ['🆔'],
    '0': ['0️⃣'],
    '1': ['1️⃣', '🥇'],
    '2': ['2️⃣', '🥈'],
    '3': ['3️⃣', '🥉'],
    '4': ['4️⃣'],
    '5': ['5️⃣'],
    '6': ['6️⃣'],
    '7': ['7️⃣'],
    '8': ['8️⃣', '🎱'],
    '9': ['9️⃣'],
    '10': ['🔟'],
    '100': ['💯'],
    '17': ['📅'],
    '777': ['🎰'],
    '!?': ['⁉️'],
    '!!': ['‼️'],
    '?': ['❔', '❓'],
    '!': ['❕', '❗'],
    '\'': [None],
    ',': [None]
}

EXCLUDE_CHARACTERS = [' ', '\'', ',']

MAX_CHARACTERS = defaultdict(int)
for a in ALPHABET:
    for c in a:
        MAX_CHARACTERS[c] += len(ALPHABET[a])

TRIGGER_EMOJIS = ['⬆️', '⤴️', '🔼', '⏫']


def increment(vals, lens, si):
    for i in range(si, -1, -1):
        vals[i] += 1
        if vals[i] >= lens[i]:
            vals[i] = 0
        else:
            return True
    return False


def spellString(string, existing_reactions=[], max_iters=10000):
    # Check that the total character count could work
    if any(string.count(c) > n for c, n in MAX_CHARACTERS.items()):
        return None

    string = ''.join([c for c in string
                      if c not in EXCLUDE_CHARACTERS]).lower()

    vals = []
    for c in ALPHABET:
        if c == '!?':
            tmp_c = '!\?'
        elif c == '?':
            tmp_c = '\?'
        else:
            tmp_c = c
        this_pos_inds = [
            m.start() for m in re.finditer(r'(?=' + tmp_c + r')', string)
        ]
        if len(this_pos_inds) > 0:
            for e in ALPHABET[c]:
                if e not in existing_reactions:
                    vals.append((e, len(c), this_pos_inds))

    random.shuffle(vals)

    inds = [0] * len(vals)
    lens = [len(pis) for _, _, pis in vals]
    num_iters = 0
    valid_spellings = []
    loop = True
    while loop:
        if num_iters >= max_iters:
            break
        num_iters += 1

        coverage = [0] * len(string)
        this_assignment = [None] * len(vals)
        for val_ind, ((e, n, pis), i) in enumerate(zip(vals, inds)):
            if all(coverage[pis[i] + k] == 0 for k in range(n)):
                this_assignment[val_ind] = i
                for k in range(n):
                    coverage[pis[i] + k] += 1

        if all(cov == 1 for cov in coverage):
            this_spelling = [None] * len(string)
            for a, (e, _, pis) in zip(this_assignment, vals):
                if a is not None:
                    this_spelling[pis[a]] = e
            this_spelling = [e for e in this_spelling if e is not None]
            valid_spellings.append(this_spelling)

        loop = increment(inds, lens, len(inds) - 1)

    if len(valid_spellings) > 0:
        return random.choice(valid_spellings)
    return None


def getWordBoundaries(sentence):
    sentence = sentence.lower()
    si = None
    ei = None
    word_boundaries = []
    for i in range(len(sentence)):
        if sentence[i] in ALPHABET:
            if si is None:
                si = i
            ei = i
        else:
            if si is not None and ei is not None:
                word_boundaries.append((si, ei))
                si = None
                ei = None
    if si is not None and ei is not None:
        word_boundaries.append((si, ei))
        si = None
        ei = None
    return word_boundaries


def spellLongestWord(sentence, existing_reactions=[]):
    word_boundaries = getWordBoundaries(sentence)
    swi = 0
    ewi = 0

    best_spelling = None

    while True:
        this_string = sentence[
            word_boundaries[swi][0]:word_boundaries[ewi][1] + 1]
        this_spelling = spellString(this_string,
                                    existing_reactions=existing_reactions)
        if this_spelling is not None:
            ewi += 1
            if best_spelling is None or len(this_spelling) > len(
                    best_spelling) or (len(this_spelling) == len(best_spelling)
                                       and random.random() > 0.5):
                best_spelling = this_spelling
        else:
            swi += 1
            if swi > ewi:
                ewi = swi

        if ewi >= len(word_boundaries):
            break
    return best_spelling


def onReactionAdd(reaction):
    if reaction.emoji not in TRIGGER_EMOJIS:
        return None

    emoji_spelling = spellLongestWord(reaction.message.content,
                                      existing_reactions=list(
                                          map(str,
                                              reaction.message.reactions)))
    return emoji_spelling


if __name__ == '__main__':
    sentence = 'The spending limit is $25 so build your wishlist accordingly!  The deadline to sign up is this Wednesday (at PUGS).  Thursday names will be sent out for those who have signed up. The currently scheduled time for the exchange is the 23rd (which may be a PUGS night, will have to see) but if that day doesn\'t work for you send me a message with dates around the 25th that work for you and we will try and find the best day for it.'
    print(spellLongestWord(sentence))

    print(spellString('o abacb oooo'))
    print(spellString('TOO'))

    print(spellString('test', existing_reactions=['👀', '🇹', '👍']))
