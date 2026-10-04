"""Rebuild album pilot, local line audit, and publishable aggregate explorer."""
import csv
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import re
import statistics

from hiphop.analyses.rhyme_quality.connections import connect
from hiphop.paths import StudyPaths
from hiphop.analyses.rhyme_quality.model import analyze_song, summarize_links
from hiphop.analyses.rhyme_quality.phonetics import word_rating, words, pronunciation, vowel
from hiphop.analyses.rhyme_quality.sources import write_json


def rounded(value):
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, dict):
        return {k: rounded(v) for k, v in value.items()}
    if isinstance(value, list):
        return [rounded(v) for v in value]
    return value


def inspection_records(song, config):
    """Enrich display with credited/repeated spans and independently adjacent pairs."""
    records = []
    previous = None
    first_successor = {}
    for line in song['lines']:
        if line['predecessor'] is not None:
            existing = first_successor.get(line['predecessor'])
            def priority(item):
                return 2 if item['syllables'] and item['connection_kind'] != 'slant' else (1 if item['connection_kind'] == 'repetition' else 0)
            if existing is None or priority(line) > priority(existing):
                first_successor[line['predecessor']] = line
    for line in song['lines']:
        adjacent = None
        if previous is not None and previous['section'] == line['section']:
            adjacent = connect(previous['analysis_text'], line['analysis_text'], config)
        phones = [pronunciation(w)[0] for w in words(line['analysis_text'])]
        known_syllables = sum(vowel(p) for part in phones if part for p in part)
        successor = first_successor.get(line['index']) if line['predecessor'] is None else None
        display = successor or line
        spans = list(re.finditer(r"[A-Za-z]+(?:'[A-Za-z]+)*|\d+", line['analysis_text']))
        remaining = display['full_syllables']
        ending_start = len(line['analysis_text'])
        if remaining:
            for span in reversed(spans):
                part = pronunciation(words(span.group())[0])[0]
                remaining -= sum(vowel(p) for p in part) if part else 0
                ending_start = span.start()
                if remaining <= 0:
                    break
        repeated_words = display['repeated_words']
        repeat_start = spans[-repeated_words].start() if repeated_words and repeated_words <= len(spans) else len(line['analysis_text'])
        records.append(dict(line, adjacent_syllables=adjacent['syllables'] if adjacent else 0,
                            adjacent_rating=adjacent['rating'] if adjacent else None,
                            adjacent_kind=adjacent['kind'] if adjacent else None,
                            adjacent_repeated=adjacent['repeated_syllables'] if adjacent else 0,
                            adjacent_full=adjacent['full_syllables'] if adjacent else 0,
                            line_syllables=known_syllables,
                            unknown_word_count=sum(p is None for p in phones),
                            anchor_partner=successor['index'] if successor else None,
                            anchor_syllables=successor['syllables'] if successor else 0,
                            anchor_rating=successor['rating'] if successor else None,
                            anchor_kind=successor['connection_kind'] if successor else None,
                            anchor_repeated=successor['repeated_syllables'] if successor else 0,
                            ending_start=ending_start, repeat_start=repeat_start,
                            endpoint_end=len(line['analysis_text']),
                            marked_adlib_count=len(line['removed_parentheticals']),
                            adlib_adjusted=bool(line['ignored_adlib'])))
        previous = line
    return records


def run(root, allow_partial=False):
    paths = StudyPaths(root, 'rhyme-quality')
    config = json.loads(paths.config.read_text())
    albums, local_details, sensitivity, source_audit = [], [], [], []
    for spec in config['albums']:
        source_path = root / 'data/raw/rhyme-quality' / (spec['slug'] + '.json')
        if not source_path.exists():
            raise FileNotFoundError('Acquire album sources first: hiphop fetch albums --study rhyme-quality')
        source = json.loads(source_path.read_text())
        actual = len(source['songs'])
        if (actual != spec['expected_tracks'] or source.get('errors')) and not allow_partial:
            raise ValueError(f"Incomplete {spec['album']}: {actual}/{spec['expected_tracks']}; use --allow-partial explicitly")
        refs = json.loads((paths.references / (spec['slug'] + '-tracklist.json')).read_text())
        expected = {t['track']: t['title'] for t in refs['tracks']}
        seen = set()
        included, excluded, songs = [], [], []
        for song in sorted(source['songs'], key=lambda x: x['track']):
            if song['track'] in seen or expected.get(song['track']) != song['title'] or song['artist'] != spec['artist']:
                raise ValueError('Source album identity, track order, or title does not match pinned manifest')
            seen.add(song['track'])
            if hashlib.sha256(song['lyrics'].encode()).hexdigest() != song['lyrics_sha256']:
                raise ValueError('Lyric hash mismatch')
            if song['title'] in spec.get('exclude_tracks', []):
                excluded.append({'track': song['track'], 'title': song['title'], 'reason': 'Spoken/sample collage; not comparable verse text'})
                continue
            analysis = analyze_song(song, config, scope=config['scope'])
            if not analysis['metrics']['eligible_lines']:
                excluded.append({'track': song['track'], 'title': song['title'], 'reason': 'No explicit verse labels'})
                continue
            included.append(song)
            songs.append({k: analysis[k] for k in ['title', 'track', 'metrics']} | {'source_url': song['source_url']})
            local_details.append({'album': spec['album'], 'artist': spec['artist'], **analysis})
        links = [l for a in local_details if a['album'] == spec['album'] for l in a['links']]
        metrics = summarize_links(links, sum(s['metrics']['eligible_lines'] for s in songs), sum(s['metrics']['known_endings'] for s in songs))
        song_means = [s['metrics']['mean_rating'] for s in songs if s['metrics']['mean_rating'] is not None]
        for key in ['marked_adlib_lines', 'adlib_candidates', 'adlib_adjusted_lines', 'adlib_unresolved_lines', 'possible_slant_pairs']:
            metrics[key] = sum(s['metrics'][key] for s in songs)
        metrics['equal_song_mean_rating'] = statistics.mean(song_means) if song_means else None
        albums.append({'slug': spec['slug'], 'artist': spec['artist'], 'album': spec['album'],
                       'source_tracks': actual, 'expected_tracks': spec['expected_tracks'],
                       'scored_tracks': len(songs), 'complete': actual == spec['expected_tracks'] and not source.get('errors'),
                       'metrics': metrics, 'songs': songs, 'excluded_tracks': excluded})
        # Settings vary one factor at a time to expose sensitivity, not optimize a winner.
        scenarios = [('threshold-' + str(t), 'verses', t, config['lookback_lines']) for t in config['thresholds']]
        scenarios += [('adjacent-only', 'verses', config['minimum_rating'], 1),
                      ('lyric-sections', 'lyric_sections', config['minimum_rating'], config['lookback_lines'])]
        scenarios += [('no-unmarked-adlib-removal', 'verses', config['minimum_rating'], config['lookback_lines']),
                      ('raw-endpoints', 'verses', config['minimum_rating'], config['lookback_lines']),
                      ('no-repeated-suffix-credit', 'verses', config['minimum_rating'], config['lookback_lines']),
                      ('include-tentative-slants', 'verses', config['minimum_rating'], config['lookback_lines'])]
        for label, scope, threshold, lookback in scenarios:
            scenario_config = dict(config)
            if label in ['no-unmarked-adlib-removal', 'raw-endpoints']:
                scenario_config['conservative_adlibs'] = False
            if label == 'raw-endpoints':
                scenario_config['marked_adlibs'] = False
            if label == 'no-repeated-suffix-credit':
                scenario_config['repeated_suffixes'] = False
            results = [analyze_song(s, scenario_config, scope, threshold, lookback) for s in included]
            summary = summarize_links([l for r in results for l in r['links']],
                                      sum(r['metrics']['eligible_lines'] for r in results),
                                      sum(r['metrics']['known_endings'] for r in results),
                                      include_slants=label == 'include-tentative-slants')
            sensitivity.append({'album': spec['album'], 'scenario': label, 'scope': scope,
                                'threshold': threshold, 'lookback': lookback, **summary})
        source_audit.append({'album': spec['album'], 'snapshot': str(source_path.relative_to(root)),
                             'snapshot_sha256': hashlib.sha256(source_path.read_bytes()).hexdigest(),
                             'collected_at': source['collected_at'], 'errors': source.get('errors', []),
                             'tracks': [{k: s.get(k) for k in ['track', 'title', 'id', 'source', 'source_url',
                                                              'source_file', 'source_row', 'lyrics_sha256']} for s in source['songs']]})
    calibration = json.loads((paths.references / 'rhymezone-observations.json').read_text())
    calibration['predictions'] = [dict(o, model_rating=word_rating(o['a'], o['b'])) for o in calibration['observations']]
    comparable = [p for p in calibration['predictions'] if p['model_rating'] is not None]
    calibration['scored_examples'] = len(comparable)
    calibration['unknown_examples'] = len(calibration['predictions']) - len(comparable)
    calibration['exact_agreements'] = sum(p['model_rating'] == p['rating'] for p in comparable)
    calibration['mean_absolute_error'] = statistics.mean(abs(p['model_rating'] - p['rating']) for p in comparable)
    calibration['warning'] = 'Small selected examples; consonant cost chosen from these. This is in-sample agreement, not independent validation or proof of equivalence.'
    examples = []
    for a, b in [('mystery', 'history'), ('red mystery', 'dead history'), ('history', 'victory'), ('blow money', 'show money'), ('coal money', 'Cole money'), ('cat money', 'blue money'), ('riser', 'guys up')]:
        m = connect(a, b, config)
        examples.append({'a': a, 'b': b, 'syllables': m['syllables'] if m else 0, 'rating': m['rating'] if m else None,
                         'repeated_syllables': m['repeated_syllables'] if m else 0, 'kind': m['kind'] if m else None,
                         'a_phones': ' '.join(m['a_phones']) if m else '', 'b_phones': ' '.join(m['b_phones']) if m else ''})
    data = rounded({'config': config, 'albums': albums, 'sensitivity': sensitivity,
                    'calibration': calibration, 'examples': examples})
    write_json(paths.processed / 'line-audit.json', rounded(local_details))
    # Public line records carry numbers, no words, phrases, phones, or full lyrics.
    line_records, lyric_records = [], []
    for song in local_details:
        display_lines = inspection_records(song, config)
        lyric_records.append({'album': song['album'], 'track': song['track'], 'lines': [
            {k: line[k] for k in ['index', 'text', 'raw', 'analysis_text', 'heading', 'ending_start', 'repeat_start', 'endpoint_end', 'removed_parentheticals', 'ignored_adlib', 'adlib_support']} for line in display_lines]})
        for line in display_lines:
            line_records.append({'album': song['album'], 'title': song['title'], 'track': song['track'],
                                 **{k: line[k] for k in ['source_line', 'section', 'index', 'scheme', 'predecessor',
                                                        'ending_known', 'available_tail_syllables', 'rating', 'syllables', 'mass',
                                                        'adjacent_syllables', 'adjacent_rating', 'line_syllables', 'unknown_word_count',
                                                        'anchor_partner', 'anchor_syllables', 'anchor_rating', 'anchor_kind', 'anchor_repeated',
                                                        'expanded_scheme', 'full_syllables', 'repeated_syllables', 'repeated_words', 'connection_kind',
                                                        'adjacent_kind', 'adjacent_repeated', 'adjacent_full', 'marked_adlib_count',
                                                        'adlib_candidate', 'adlib_adjusted']}})
    data['line_records'] = rounded(line_records)
    paths.exports.mkdir(parents=True, exist_ok=True)
    write_json(paths.exports / 'results.json', data)
    (paths.web / 'data.js').write_text('window.RHYME_DATA = ' + json.dumps(data, ensure_ascii=False) + ';\n')
    # The requested lyric view is local-only; this file is explicitly ignored
    # so the committed public site and exports still contain no full lyrics.
    (paths.web / 'lyrics.local.js').write_text('window.RHYME_LYRICS = ' + json.dumps(lyric_records, ensure_ascii=False) + ';\n')
    for name, records in [('songs', [{'album': a['album'], 'artist': a['artist'], 'track': s['track'], 'title': s['title'],
                                     **{k: v for k, v in s['metrics'].items() if not isinstance(v, dict)}} for a in albums for s in a['songs']]),
                          ('albums', [{'album': a['album'], 'artist': a['artist'], 'scored_tracks': a['scored_tracks'],
                                       **{k: v for k, v in a['metrics'].items() if not isinstance(v, dict)}} for a in albums]),
                          ('sensitivity', [{k: v for k, v in s.items() if not isinstance(v, dict)} for s in sensitivity]),
                          ('lines', line_records)]:
        with (paths.exports / (name + '.csv')).open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(records[0]) if records else [], lineterminator='\n')
            writer.writeheader()
            writer.writerows(rounded(records))
    unknown = sorted({w for a in local_details for l in a['lines'] for w in l['unknown_words']})
    audit = {'generated_at': datetime.now(timezone.utc).isoformat(), 'as_of': config['as_of'],
             'model_version': config['model_version'], 'config_sha256': hashlib.sha256(paths.config.read_bytes()).hexdigest(),
             'software': {p: version(p) for p in ['cmudict', 'pyarrow']},
             'source_audit': source_audit, 'unrecognized_vocabulary': unknown,
             'scope': 'Explicit verses, all vocalists; excludes intro/outro/interlude and The Genesis',
             'pronunciation_policy': config['pronunciation'], 'rhymezone_equivalent': False,
             'local_line_audit': str((paths.processed / 'line-audit.json').relative_to(root))}
    write_json(paths.exports / 'audit.json', audit)
    print(json.dumps(rounded(albums), ensure_ascii=False, indent=2))
