"""Preserve source lines; separate scored rhyme from pattern-only connections."""
from collections import Counter
import re
import statistics

from .phonetics import tail
from .connections import connect
from .endpoints import marked_lead, choose_endpoints


def lyric_lines(text, marked_adlibs=True):
    """Source lines are bar proxies. Bracket labels reset the search window."""
    section, heading = 0, 'Unlabeled'
    text = text.replace('’', "'").replace('‘', "'")
    text = re.sub(r'^.{0,500}?\bLyrics\s*(?=\[)', '', text, count=1, flags=re.S)
    text = re.sub(r'(?i)\d*\s*embed\s*$', '', text)
    for source_line, raw in enumerate(text.splitlines(), 1):
        raw = raw.strip()
        if not raw:
            continue
        labels = re.findall(r'\[([^\]]+)\]', raw)
        if labels:
            section += 1
            heading = labels[-1]
            raw = re.sub(r'\[[^\]]*\]', '', raw).strip()
        if not raw or re.search(r'(?i)you might also like|see .+ live|get tickets|contributors?\b.*lyrics|^translations\b', raw):
            continue
        lead, removed = marked_lead(raw) if marked_adlibs else (raw, [])
        if not lead or not re.search('[A-Za-z]', lead):
            continue
        yield {'source_line': source_line, 'section': section, 'heading': heading,
               'text': lead, 'raw': raw, 'removed_parentheticals': removed,
               'is_verse': bool(re.match(r'(?i)^verse\b', heading)),
               'is_lyric': bool(re.match(r'(?i)^(verse|chorus|hook|refrain|post.chorus|bridge)\b', heading))}


def analyze_song(song, config, scope='verses', minimum_rating=None, lookback_lines=None):
    threshold = config['minimum_rating'] if minimum_rating is None else minimum_rating
    lookback = config['lookback_lines'] if lookback_lines is None else lookback_lines
    source_lines = list(lyric_lines(song['lyrics'], config.get('marked_adlibs', True)))
    lines = [dict(l, index=i, match=None, predecessor=None) for i, l in enumerate(
        l for l in source_lines if l['is_verse'] or (scope == 'lyric_sections' and l['is_lyric']))]
    choose_endpoints(lines, config | {'lookback_lines': lookback})
    for line in lines:
        line['tail'] = tail(line['analysis_text'], config['max_syllables'])
    links, slant_pairs = [], []
    parent = list(range(len(lines)))
    expanded_parent = parent.copy()
    def find(x, parents=parent):
        while parents[x] != x:
            parents[x] = parents[parents[x]]
            x = parents[x]
        return x
    for i, line in enumerate(lines):
        candidates = []
        for j in range(i - 1, max(-1, i - lookback - 1), -1):
            previous = lines[j]
            if previous['section'] != line['section']:
                break
            match = connect(previous['analysis_text'], line['analysis_text'], config, threshold)
            if match:
                # Prefer a scored connection. Tentative slants do not displace
                # an accepted strict rhyme, even when they are longer.
                priority = 2 if match['kind'] != 'slant' and match['syllables'] > 0 else (1 if match['kind'] == 'repetition' else 0)
                candidates.append((priority,
                                   match['mass'], match['rating'] or 0, -(i - j), j, match))
                if match['kind'] == 'slant':
                    slant_pairs.append({'from_index': j, 'to_index': i, **match})
                    expanded_parent[find(i, expanded_parent)] = find(j, expanded_parent)
        if candidates:
            *_, j, match = max(candidates, key=lambda item: item[:4])
            line['match'], line['predecessor'] = match, j
            if match['kind'] != 'slant':
                parent[find(i)] = find(j)
            expanded_parent[find(i, expanded_parent)] = find(j, expanded_parent)
            links.append({'from_index': j, 'to_index': i, 'from_line': lines[j]['source_line'],
                          'to_line': line['source_line'], 'gap': i - j, **match})
    def labels(parents):
        counts = Counter(find(i, parents) for i in range(len(lines)))
        mapping = {key: i + 1 for i, key in enumerate(k for k, n in counts.items() if n > 1)}
        return [mapping.get(find(i, parents)) for i in range(len(lines))], len(mapping)
    schemes, scheme_count = labels(parent)
    expanded, _ = labels(expanded_parent)
    details = []
    for i, line in enumerate(lines):
        match = line['match']
        details.append({k: line[k] for k in ['source_line', 'section', 'heading', 'text', 'raw',
                         'analysis_text', 'removed_parentheticals', 'ignored_adlib', 'adlib_support', 'adlib_candidate']} | {
            'index': i, 'scheme': schemes[i], 'expanded_scheme': expanded[i], 'predecessor': line['predecessor'],
            'ending_word': line['tail'].tokens[-1] if line['tail'].tokens else None,
            'ending_known': bool(line['tail'].nuclei), 'available_tail_syllables': min(config['max_syllables'], len(line['tail'].nuclei)),
            'tail_blocked_at': line['tail'].blocked_at,
            'unknown_words': line['tail'].unknown_words, 'normalized_words': line['tail'].normalized_words,
            'rating': match['rating'] if match else None, 'syllables': match['syllables'] if match else 0,
            'full_syllables': match['full_syllables'] if match else 0,
            'repeated_syllables': match['repeated_syllables'] if match else 0,
            'repeated_words': match['repeated_words'] if match else 0,
            'connection_kind': match['kind'] if match else None,
            'mass': match['mass'] if match and match['kind'] != 'slant' else 0})
    metrics = summarize_links(links, len(lines), sum(bool(l['tail'].nuclei) for l in lines))
    metrics.update({'source_lyric_lines': len(source_lines), 'sections': len({l['section'] for l in lines}),
                    'schemes': scheme_count, 'possible_slant_pairs': len(slant_pairs),
                    'marked_adlib_lines': sum(bool(l['removed_parentheticals']) for l in lines),
                    'adlib_candidates': sum(l['adlib_candidate'] for l in lines),
                    'adlib_adjusted_lines': sum(bool(l['ignored_adlib']) for l in lines),
                    'adlib_unresolved_lines': sum(l['adlib_candidate'] and not l['ignored_adlib'] for l in lines),
                    'unknown_token_occurrences': sum(len(l['tail'].unknown_words) for l in lines),
                    'tail_blocked_lines': sum(l['tail'].blocked_at is not None for l in lines),
                    'normalized_token_occurrences': sum(len(l['tail'].normalized_words) for l in lines)})
    return {'title': song['title'], 'track': song['track'], 'scope': scope, 'threshold': threshold,
            'lookback_lines': lookback, 'metrics': metrics, 'links': links, 'slant_pairs': slant_pairs, 'lines': details}


def summarize_links(links, eligible_lines, known_endings, include_slants=False):
    scored = [l for l in links if l['syllables'] > 0 and l['rating'] is not None
              and (include_slants or l.get('kind') != 'slant')]
    ratings = [l['rating'] for l in scored]
    lengths = [l['syllables'] for l in scored]
    mass = sum(l['syllables'] * l['rating'] / 100 for l in scored)
    return {'eligible_lines': eligible_lines, 'known_endings': known_endings,
            'unknown_endings': eligible_lines - known_endings, 'rhyme_links': len(scored),
            'pattern_links': len(links), 'repeat_only_links': sum(l.get('kind') == 'repetition' for l in links),
            'rhyme_before_repeat_links': sum(l.get('kind') == 'rhyme-before-repeat' for l in links),
            'tentative_slant_links': sum(l.get('kind') == 'slant' for l in links),
            'repeated_syllables_uncredited': sum(l.get('repeated_syllables', 0) for l in links),
            'mean_rating': statistics.mean(ratings) if ratings else None,
            'median_rating': statistics.median(ratings) if ratings else None,
            'total_rating_points': sum(ratings),
            'mean_syllables': statistics.mean(lengths) if lengths else None,
            'median_syllables': statistics.median(lengths) if lengths else None,
            'total_rhymed_syllables': sum(lengths), 'weighted_rhyme_syllables': mass,
            'weighted_syllables_per_100_lines': mass / eligible_lines * 100 if eligible_lines else None,
            'linked_line_percent': len(scored) / eligible_lines * 100 if eligible_lines else None,
            'syllable_histogram': dict(sorted(Counter(lengths).items())),
            'perfect_links': sum(r == 100 for r in ratings), 'max_syllables': max(lengths, default=0)}
