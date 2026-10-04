"""Deterministic dictionary phones and an explicitly provisional rhyme metric.

The 8-point consonant edit cost fits several observed RhymeZone examples.
Vowel costs and acceptance gates are our choices, not a recovered formula.
"""
from dataclasses import dataclass
from functools import lru_cache
import re
import unicodedata

import cmudict

TOKEN = re.compile(r"[a-z]+(?:'[a-z]+)*|\d+")
VOWELS = set('AA AE AH AO AW AY EH ER EY IH IY OW OY UH UW'.split())
# Conservative neighboring vowel pairs. No dialect or performed delivery inference.
NEAR_VOWELS = {frozenset(p.split()) for p in ['IH IY', 'EH AE', 'AH UH', 'AA AO', 'UH UW']}
ALIASES = {"'em": 'them', 'em': 'them', "'cause": 'cause', 'cuz': 'cause',
           'tryna': 'trying', 'wanna': 'want', 'gonna': 'going', 'imma': 'ima'}
# Multiword expansions preserve nuclei rather than pretending "wanna" is "want".
EXPANSIONS = {'tryna': ['trying', 'to'], 'wanna': ['want', 'to'],
              'gonna': ['going', 'to'], 'imma': ['i', 'am', 'going', 'to']}
NUMBER_WORDS = ('zero one two three four five six seven eight nine ten eleven twelve '
                'thirteen fourteen fifteen sixteen seventeen eighteen nineteen').split()
TENS = 'zero ten twenty thirty forty fifty sixty seventy eighty ninety'.split()


def words(text):
    text = unicodedata.normalize('NFKD', text.lower().replace('’', "'").replace('‘', "'"))
    text = ''.join(c for c in text if not unicodedata.combining(c) and unicodedata.category(c) != 'Cf')
    # Public lyric transcriptions occasionally substitute visually identical
    # Cyrillic letters. Normalize only these known Latin lookalikes.
    text = text.translate(str.maketrans({'а': 'a', 'е': 'e', 'о': 'o', 'р': 'p',
                                        'с': 'c', 'х': 'x', 'у': 'y', 'і': 'i'}))
    return TOKEN.findall(text)


def base(phone):
    return phone.rstrip('012')


def vowel(phone):
    return base(phone) in VOWELS


@lru_cache(maxsize=1)
def dictionary():
    return cmudict.dict()


@lru_cache(maxsize=50000)
def pronunciation(word):
    """Use one consistent dictionary reading for a word throughout the corpus."""
    d = dictionary()
    if word in d:
        return tuple(d[word][0]), 'dictionary'
    if word.isdigit() and int(word) < 100:
        n = int(word)
        parts = [NUMBER_WORDS[n]] if n < 20 else [TENS[n // 10]] + ([NUMBER_WORDS[n % 10]] if n % 10 else [])
        return tuple(p for w in parts for p in d[w][0]), 'number'
    if word in EXPANSIONS:
        return tuple(p for w in EXPANSIONS[word] for p in d[w][0]), 'written_expansion'
    lookup = ALIASES.get(word, word)
    if lookup in d:
        return tuple(d[lookup][0]), 'written_alias'
    if word.endswith('in') and word + 'g' in d:
        phones = list(d[word + 'g'][0])
        if phones[-1] == 'NG':
            phones[-1] = 'N'
            return tuple(phones), 'written_elision'
    if word.endswith("'s") and word[:-2] in d:
        phones = tuple(d[word[:-2]][0])
        end = base(phones[-1])
        suffix = ('IH0', 'Z') if end in {'S', 'Z', 'SH', 'ZH', 'CH', 'JH'} else (('S',) if end in {'P', 'T', 'K', 'F', 'TH'} else ('Z',))
        return phones + suffix, 'possessive'
    return None, 'unknown'


@dataclass(frozen=True)
class Tail:
    tokens: tuple
    phones: tuple
    nuclei: tuple
    stresses: tuple
    unknown_words: tuple
    normalized_words: tuple
    blocked_at: str | None

    def suffix(self, syllables):
        return self.phones[self.nuclei[-syllables]:]


def tail(text, max_syllables=6):
    tokens = words(text)
    parts, unknown, normalized = [], [], []
    for word in tokens:
        phones, source = pronunciation(word)
        parts.append(phones)
        if phones is None:
            unknown.append(word)
        elif source != 'dictionary':
            normalized.append(word)
    # Never bridge over an unknown word. Known line endings can still be scored.
    suffix = []
    blocked_at = None
    for word, phones in reversed(list(zip(tokens, parts))):
        if phones is None:
            blocked_at = word
            break
        suffix[0:0] = phones
        if sum(vowel(p) for p in suffix) >= max_syllables:
            break
    nuclei = tuple(i for i, p in enumerate(suffix) if vowel(p))
    stresses = tuple(int(suffix[i][-1]) if suffix[i][-1].isdigit() else 0 for i in nuclei)
    return Tail(tuple(tokens), tuple(suffix), nuclei, stresses,
                tuple(unknown), tuple(normalized), blocked_at)


def vowel_cost(a, b):
    a, b = base(a), base(b)
    if a == b:
        return 0
    return 16 if frozenset((a, b)) in NEAR_VOWELS else 40


def substitution(a, b):
    if base(a) == base(b):
        return 0
    if vowel(a) and vowel(b):
        return vowel_cost(a, b)
    if vowel(a) != vowel(b):
        return 48
    return 8


def gap(phone):
    return 40 if vowel(phone) else 8


@lru_cache(maxsize=100000)
def edit_cost(a, b):
    """Weighted Levenshtein distance over vowel-to-end phonetic tails."""
    row = [0]
    for phone in b:
        row.append(row[-1] + gap(phone))
    for x in a:
        nxt = [row[0] + gap(x)]
        for j, y in enumerate(b, 1):
            nxt.append(min(nxt[-1] + gap(y), row[j] + gap(x),
                           row[j - 1] + substitution(x, y)))
        row = nxt
    return row[-1]


@dataclass(frozen=True)
class Match:
    syllables: int
    rating: float
    cost: float
    stress_mismatches: int
    a_phones: tuple
    b_phones: tuple

    @property
    def mass(self):
        return self.syllables * self.rating / 100


def match_tails(a, b, minimum_rating=84, max_syllables=6,
                maximum_incremental_cost=16, exclude_identical_end_words=True):
    if not a.tokens or not b.tokens or not a.nuclei or not b.nuclei:
        return None
    if exclude_identical_end_words and a.tokens[-1] == b.tokens[-1]:
        return None
    limit = min(max_syllables, len(a.nuclei), len(b.nuclei))
    best, previous_cost = None, 0
    for n in range(1, limit + 1):
        # An unmatched preceding vowel terminates the extension. Long tails
        # cannot wash out bad earlier syllables through averaging.
        av, bv = a.phones[a.nuclei[-n]], b.phones[b.nuclei[-n]]
        if vowel_cost(av, bv) > 16:
            break
        ap, bp = a.suffix(n), b.suffix(n)
        stress_mismatches = sum((x > 0) != (y > 0) for x, y in zip(a.stresses[-n:], b.stresses[-n:]))
        cost = edit_cost(ap, bp) + 4 * stress_mismatches
        rating = max(0, 100 - cost)
        if cost - previous_cost > maximum_incremental_cost or rating < minimum_rating:
            break
        # A shared unstressed '-y' or '-er' alone is too weak a rhyme anchor.
        if any(a.stresses[-n:]) and any(b.stresses[-n:]):
            best = Match(n, rating, cost, stress_mismatches, ap, bp)
        previous_cost = cost
    return best


def word_rating(a, b):
    """Standalone traditional last-stressed-vowel comparison for calibration."""
    def phrase(text):
        parts = [pronunciation(w)[0] for w in words(text)]
        if not parts or any(p is None for p in parts):
            return None
        return tuple(phone for part in parts for phone in part)
    pa, pb = phrase(a), phrase(b)
    if pa is None or pb is None:
        return None
    def part(phones):
        indexes = [i for i, p in enumerate(phones) if vowel(p) and p.endswith(('1', '2'))]
        return phones[indexes[-1]:] if indexes else phones
    return max(0, 100 - edit_cost(part(pa), part(pb)))
