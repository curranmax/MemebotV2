from collections import defaultdict
import random
import re

ALPHABET = {
    'a': ['๐ฆ', '๐ฐ๏ธ'],
    'b': ['๐ง', '๐ฑ๏ธ'],
    'c': ['๐จ', 'ยฉ๏ธ'],
    'd': ['๐ฉ'],
    'e': ['๐ช', '๐ง'],
    'f': ['๐ซ'],
    'g': ['๐ฌ'],
    'h': ['๐ญ', 'โ'],
    'i': ['๐ฎ'],
    'j': ['๐ฏ'],
    'k': ['๐ฐ'],
    'l': ['๐ฑ'],
    'm': ['๐ฒ', 'โ๏ธ', 'โ', 'โ'],
    'n': ['๐ณ', 'โ'],
    'o': ['๐ด', 'โญ', '๐พ๏ธ'],
    'p': ['๐ต', '๐ฟ๏ธ'],
    'q': ['๐ถ', '๐โ๐จ'],
    'r': ['๐ท', 'ยฎ๏ธ'],
    's': ['๐ธ', '๐ฒ'],
    't': ['๐น', 'โ๏ธ'],
    'u': ['๐บ'],
    'v': ['๐ป', 'โ'],
    'w': ['๐ผ'],
    'x': ['๐ฝ', 'โ๏ธ'],
    'y': ['๐พ'],
    'z': ['๐ฟ'],
    'ab': ['๐'],
    'oo': ['โฟ'],
    'soon': ['๐'],
    'top': ['๐'],
    'on': ['๐'],
    'back': ['๐'],
    'end': ['๐'],
    'tm': ['โข๏ธ'],
    'free': ['๐'],
    'new': ['๐'],
    'cool': ['๐'],
    'up': ['๐'],
    'ok': ['๐'],
    'ng': ['๐'],
    'wc': ['๐พ'],
    'atm': ['๐ง'],
    'zzz': ['๐ค'],
    'sos': ['๐'],
    'cl': ['๐'],
    'vs': ['๐'],
    'off': ['๐ด'],
    'id': ['๐'],
    '0': ['0๏ธโฃ'],
    '1': ['1๏ธโฃ', '๐ฅ'],
    '2': ['2๏ธโฃ', '๐ฅ'],
    '3': ['3๏ธโฃ', '๐ฅ'],
    '4': ['4๏ธโฃ'],
    '5': ['5๏ธโฃ'],
    '6': ['6๏ธโฃ'],
    '7': ['7๏ธโฃ'],
    '8': ['8๏ธโฃ', '๐ฑ'],
    '9': ['9๏ธโฃ'],
    '10': ['๐'],
    '100': ['๐ฏ'],
    '17': ['๐'],
    '777': ['๐ฐ'],
    '!?': ['โ๏ธ'],
    '!!': ['โผ๏ธ'],
    '?': ['โ', 'โ'],
    '!': ['โ', 'โ'],
    '\'': [None],
    ',': [None]
}

EXCLUDE_CHARACTERS = [' ', '\'', ',']

MAX_CHARACTERS = defaultdict(int)
for a in ALPHABET:
    for c in a:
        MAX_CHARACTERS[c] += len(ALPHABET[a])

TRIGGER_EMOJIS = ['โฌ๏ธ', 'โคด๏ธ', '๐ผ', 'โซ']


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

    print(spellString('test', existing_reactions=['๐', '๐น', '๐']))
