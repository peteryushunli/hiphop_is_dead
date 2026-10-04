"""Conservative transcription-based ad-lib candidates, with visible decisions."""
import re
from .phonetics import words
from .connections import connect

ADLIBS = {'yeah', 'yea', 'yah', 'ayy', 'ay', 'aye', 'hey', 'uh', 'huh', 'ah', 'oh', 'ooh', 'woo', 'wooh', 'whoo', 'woah', 'wow', 'yuh', 'brr', 'brrr', 'brrt', 'skrr', 'skrrt', 'skrt', 'grr', 'grrt'}


def marked_lead(raw):
    ignored = []
    def replace(match):
        tokens = words(match.group(1))
        before = words(raw[:match.start()])
        short = 0 < len(tokens) <= 4
        echo = short and len(before) >= len(tokens) and before[-len(tokens):] == tokens
        if short and (all(w in ADLIBS for w in tokens) or echo):
            ignored.append(match.group(0))
            return ''
        return match.group(0)
    lead = re.sub(r'\(([^()]*)\)', replace, raw).strip()
    return lead, ignored


def trailing_candidate(text):
    # Require punctuation plus a one/two-token allowlisted suffix. A substantive
    # word such as "money" never becomes an ad-lib just because removing it fits.
    match = re.search(r'[,;:!—–]\s*([^,;:!—–]+?)\s*$', text)
    if match:
        tokens = words(match.group(1))
        if 0 < len(tokens) <= 2 and all(w in ADLIBS for w in tokens):
            candidate = text[:match.start()].rstrip()
            if words(candidate):
                return candidate, text[match.start():]
    return None


def choose_endpoints(lines, config):
    # Support comes only from unchanged native endpoints, never another proposed
    # deletion. Two independent local witnesses prevent circular ad-lib removal.
    for line in lines:
        line.update(analysis_text=line['text'], ignored_adlib='', adlib_support=[], adlib_candidate=False)
    if not config.get('conservative_adlibs', True):
        return
    lookback = config['lookback_lines']
    for i, line in enumerate(lines):
        proposal = trailing_candidate(line['text'])
        if proposal is None:
            continue
        shortened, suffix = proposal
        line['adlib_candidate'] = True
        supports, native_supports = [], []
        for j in range(max(0, i - lookback), min(len(lines), i + lookback + 1)):
            other = lines[j]
            if i == j or line['section'] != other['section']:
                continue
            # Other unresolved trailing candidates cannot validate this deletion.
            if trailing_candidate(other['text']):
                continue
            match = connect(shortened, other['text'], config, allow_slant=False)
            if match and (match['syllables'] > 0 or match['repeated_syllables'] >= 2):
                supports.append(other['source_line'])
            native = connect(line['text'], other['text'], config, allow_slant=False)
            if native and (native['syllables'] > 0 or native['repeated_syllables'] >= 2):
                native_supports.append(other['source_line'])
        line['adlib_support'] = supports
        if len(supports) >= config.get('adlib_minimum_support', 2) and len(supports) > len(native_supports):
            line['analysis_text'], line['ignored_adlib'] = shortened, suffix
