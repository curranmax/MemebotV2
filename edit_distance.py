import logging

_CHAR_KEYBOARD_POSITION = {
    'q': (1.5, 3.0),
    'w': (2.5, 3.0),
    'e': (3.5, 3.0),
    'r': (4.5, 3.0),
    't': (5.5, 3.0),
    'y': (6.5, 3.0),
    'u': (7.5, 3.0),
    'i': (8.5, 3.0),
    'o': (9.5, 3.0),
    'p': (10.5, 3.0),

    'a': (2.0, 2.0),
    's': (3.0, 2.0),
    'd': (4.0, 2.0),
    'f': (5.0, 2.0),
    'g': (6.0, 2.0),
    'h': (7.0, 2.0),
    'j': (8.0, 2.0),
    'k': (9.0, 2.0),
    'l': (10.0, 2.0),

    'z': (2.5, 1.0),
    'x': (3.5, 1.0),
    'c': (4.5, 1.0),
    'v': (5.5, 1.0),
    'b': (6.5, 1.0),
    'n': (7.5, 1.0),
    'm': (8.5, 1.0),

    '1': (1.0, 4.0),
    '2': (2.0, 4.0),
    '3': (3.0, 4.0),
    '4': (4.0, 4.0),
    '5': (5.0, 4.0),
    '6': (6.0, 4.0),
    '7': (7.0, 4.0),
    '8': (8.0, 4.0),
    '9': (9.0, 4.0),
    '0': (10.0, 4.0),

    '\'': (12.0, 2.0),
    '"': (12.0, 2.0),
    ',': (9.5, 1.0),
    '.': (10.5, 1.0),
    '?': (11.5, 1.0),
    '!': (1.0, 4.0),
    ':': (11.0, 2.0),
    '&': (7.0, 4.0),
    '-': (11.0, 4.0),
    '(': (9.0, 4.0),
    ')': (10.0, 4.0),
}

# This is the value to use if the character isn't in the above map. This will always be needed since we will compare to "None".
_CHAR_KEYBOARD_UNKNOWN_DIST = 10.0

class Options:
    # Algo type
    SIMPLE = '_simple'
    WORD = '_word'
    # TODO Add a hybrid methodd that is _simple but applies different weights if the words align vs. not
    # TODO Add a earth mover distance that can allow up to k gaps in between the words.

    # Character distance type
    CHAR_EQUALITY = '_char_equality'
    CHAR_KEYBORAD_DISTANCE = '_char_keyboard_distance'

    def __init__(self, edit_distance_type: str = SIMPLE, char_distance_type: str = CHAR_EQUALITY, ignore_case: bool = True):
        self.edit_distance_type = edit_distance_type
        self.char_distance_type = char_distance_type

        self.ignore_case = ignore_case
        # TODO Add a bool to handle special characters (i.e. treat ones with accents the same as the ones without accents)

    def preprocess(self, v: str) -> str:
        if self.ignore_case:
            v = v.lower()
        return v

    def characterDistance(self, c1: str, c2: str) -> float:
        if self.char_distance_type == Options.CHAR_EQUALITY:
            if c1 == c2:
                return 0
            return 1
        elif self.char_distance_type == Options.CHAR_KEYBORAD_DISTANCE:
            c1 = c1.lower()
            c2 = c2.lower()
            if c1 not in _CHAR_KEYBOARD_POSITION or c2 not in _CHAR_KEYBOARD_POSITION:
                if c1 is not None:
                    logging.warning(f'Unknown character: {c1}')
                if c2 is not None:
                    logging.warning(f'Unknown character: {c2}')
                return _CHAR_KEYBOARD_UNKNOWN_DIST
            x1, y2 = _CHAR_KEYBOARD_POSITION[c1]
            x2, y2 = _CHAR_KEYBOARD_POSITION[c2]
            # TODO Cache these values? Return dist squared for efficiency?
            return ((x1-x2)**2 + (y1-y2)**2)**0.5


def compute(v1: str, v2: str, options: Options|None = None) -> float:
    if options is None:
        options = Options()
    v1 = options.preprocess(v1)
    v2 = options.preprocess(v2)
    if options.edit_distance_type == Options.SIMPLE:
        return _simple(v1, v2, options)
    elif options.edit_distance_type == Options.WORD:
        return _word(v1, v2, options)
    raise Exception(f'Unknown edit distance type: {options.edit_distance_type}')


def _getChar(v: str, i: int) -> str|None:
    if i < 0 or i >= len(v):
        return None
    return v[i]


def _simple(v1: str, v2: str, options: Options) -> float:
    best_score = None
    for i in range(1-len(v2), len(v1), 1):
        this_score = 0
        for j in range(len(v2)):
            c1 = _getChar(v1, i+j)
            c2 = _getChar(v2, j)
            this_score += options.characterDistance(c1, c2)
        if best_score is None or this_score < best_score:
            best_score = this_score
        if best_score == 0:
            return best_score
    return best_score


def _getWordIndexes(v: str) -> list[int]:
    indexes = []
    for i, c in enumerate(v):
        if i == 0:
            indexes.append(i)
        # TODO Handle other whitespace characters.
        elif v[i-1] == ' ' and c != ' ':
            indexes.append(i)
    return indexes


def _word(v1: str, v2: str, options: Options) -> float:
    print('AA')
    best_score = None
    v1_inds = _getWordIndexes(v1)
    v2_inds = _getWordIndexes(v2)
    for i in v1_inds:
        print(f'i: {i}')
        this_score = 0
        for v2_align in v2_inds:
            print(f'v2_align: {v2_align}')
            # Compare with aligning v1[i] with v2[v2_align]
            for j in range(len(v2)):
                print(f'j: {j}')
                c1 = _getChar(v1, i+j-v2_align)
                print(f'c1: {c1}')
                c2 = _getChar(v2, j)
                print(f'c2: {c2}')
                this_score += options.characterDistance(c1, c2)
                print(f'this_score: {this_score}')
        if best_score is None or this_score < best_score:
            best_score = this_score
        if best_score == 0:
            return best_score
    print('BB')
    return best_score
