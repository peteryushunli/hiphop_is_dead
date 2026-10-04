"""Separate repeated text, credited suffix rhymes, and tentative phrase slants."""
from dataclasses import asdict

from .phonetics import tail, words, pronunciation, vowel, base, vowel_cost, edit_cost, match_tails


def phrase_slant(a, b, maximum=6, minimum=76):
    """A stressed anchor plus a similar central trailing vowel, across word boundaries.

    This is deliberately narrower than general assonance: the intervening
    consonants must share a phone and differ by at most one consonant edit.
    At least one final vowel must be unstressed in the dictionary. We retain
    the stress disagreement as a penalty, rather than inventing delivery.
    """
    best = None
    central = {frozenset(p.split()) for p in ['ER AH', 'ER UH', 'AH UH']}
    for n in range(2, min(maximum, len(a.nuclei), len(b.nuclei)) + 1):
        av = [a.phones[i] for i in a.nuclei[-n:]]
        bv = [b.phones[i] for i in b.nuclei[-n:]]
        if base(av[0]) != base(bv[0]) or not a.stresses[-n] or not b.stresses[-n]:
            continue
        if frozenset((base(av[-1]), base(bv[-1]))) not in central or (a.stresses[-1] and b.stresses[-1]):
            continue
        if any(vowel_cost(x, y) > 16 for x, y in zip(av[:-1], bv[:-1])):
            continue
        am = a.phones[a.nuclei[-2] + 1:a.nuclei[-1]]
        bm = b.phones[b.nuclei[-2] + 1:b.nuclei[-1]]
        if not set(am) & set(bm) or edit_cost(am, bm) > 8:
            continue
        stress = sum((x > 0) != (y > 0) for x, y in zip(a.stresses[-n:], b.stresses[-n:]))
        # Earlier sounds retain the strict phone costs. The differing central
        # tail costs 12; final consonants receive half the usual edit weight.
        cost = edit_cost(a.suffix(n)[:a.nuclei[-1] - a.nuclei[-n]],
                         b.suffix(n)[:b.nuclei[-1] - b.nuclei[-n]])
        cost += 12 + edit_cost(a.phones[a.nuclei[-1] + 1:], b.phones[b.nuclei[-1] + 1:]) / 2 + 4 * stress
        rating = max(0, 100 - cost)
        if rating >= minimum:
            candidate = {'syllables': n, 'rating': rating, 'cost': cost, 'stress_mismatches': stress,
                         'a_phones': a.suffix(n), 'b_phones': b.suffix(n)}
            if best is None or n * rating > best['syllables'] * best['rating']:
                best = candidate
    return best


def connect(a_text, b_text, config, minimum_rating=None, allow_slant=True):
    threshold = config['minimum_rating'] if minimum_rating is None else minimum_rating
    maximum = config['max_syllables']
    aw, bw = words(a_text), words(b_text)
    shared = 0
    if config.get('repeated_suffixes', True):
        for x, y in zip(reversed(aw), reversed(bw)):
            if x != y:
                break
            shared += 1
    elif aw and bw and aw[-1] == bw[-1]:
        return None
    repeated = 0
    repeated_known = True
    for w in aw[len(aw) - shared:] if shared else []:
        phones = pronunciation(w)[0]
        if phones is None:
            repeated_known = False
        else:
            repeated += sum(vowel(p) for p in phones)
    repeated = min(maximum, repeated)
    # Remove the entire common word suffix before measuring novel rhyme.
    # An unknown repeated suffix is a barrier, just as in the strict model.
    a = tail(' '.join(aw[:-shared] if shared else aw), maximum)
    b = tail(' '.join(bw[:-shared] if shared else bw), maximum)
    budget = maximum - repeated
    match = match_tails(a, b, threshold, budget, config['maximum_incremental_cost'], True) if repeated_known and budget > 0 else None
    value = asdict(match) if match else None
    kind = 'rhyme'
    if value is None and allow_slant and config.get('phrase_slants', True) and repeated_known and budget > 0:
        value = phrase_slant(a, b, budget, config.get('slant_minimum_rating', 76))
        if value:
            kind = 'slant'
    if value is None and not shared:
        return None
    if value is None:
        value = {'syllables': 0, 'rating': None, 'cost': 0, 'stress_mismatches': 0, 'a_phones': (), 'b_phones': ()}
        kind = 'repetition'
    elif shared and kind == 'rhyme':
        kind = 'rhyme-before-repeat'
    return value | {'kind': kind, 'repeated_words': shared, 'repeated_syllables': repeated,
                    'full_syllables': repeated + value['syllables'], 'repetition_known': repeated_known,
                    'mass': value['syllables'] * (value['rating'] or 0) / 100}
