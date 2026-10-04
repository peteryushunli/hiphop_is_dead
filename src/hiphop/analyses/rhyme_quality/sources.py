"""Explicit acquisition; analysis runs never make network calls."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from hiphop.sources.genius import GeniusClient, lyrics_from_html


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def collect_albums(root):
    config = json.loads((root / 'analyses/rhyme-quality/config.json').read_text())
    out = root / 'data/raw/rhyme-quality'
    refs = root / 'analyses/rhyme-quality/references'
    fetch = GeniusClient(root / 'data/cache/genius' / config['as_of'] / 'rhyme-quality').fetch
    for album in config['albums']:
        dest = out / (album['slug'] + '.json')
        if dest.exists():
            prior = json.loads(dest.read_text())
            if len(prior['songs']) == album['expected_tracks'] and not prior.get('errors'):
                print(f"Cached {album['album']}: {len(prior['songs'])} tracks", flush=True)
                continue
        if album['slug'] == 'illmatic' or album.get('source') == 'archive':
            manifest = json.loads((refs / (album['slug'] + '-tracklist.json')).read_text())
            needed = {t['archive_title']: t for t in manifest['tracks']}
            songs = []
            for path in sorted((root / 'data/raw/genius-lyrics-cleaned').glob('*.parquet')):
                table = pq.read_table(path, columns=['artist', 'title', 'year'])
                mask = pc.and_(pc.equal(pc.utf8_lower(table['artist']), album['artist'].lower()),
                               pc.is_in(table['title'], value_set=pa.array(list(needed))))
                indexes = pc.indices_nonzero(mask).to_pylist()
                if not indexes:
                    continue
                rows = pq.read_table(path).take(indexes).to_pylist()
                for index, row in zip(indexes, rows):
                    spec = needed[row['title']]
                    songs.append({'track': spec['track'], 'title': spec['title'], 'artist': album['artist'],
                                  'year': row['year'], 'lyrics': row['lyrics'],
                                  'id': f'archive:{path.name}:{index}', 'archive_title': row['title'],
                                  'source': 'genius_lyrics_cleaned',
                                  'source_url': 'https://huggingface.co/datasets/sebastiandizon/genius-lyrics-cleaned',
                                  'source_file': path.name, 'source_row': index,
                                  'lyrics_sha256': hashlib.sha256(row['lyrics'].encode()).hexdigest()})
            if len(songs) != len(needed) or len({s['track'] for s in songs}) != len(needed):
                raise ValueError('Album archive track selection is missing or ambiguous; review before scoring')
            result = {'album': album['album'], 'artist': album['artist'], 'expected_tracks': album['expected_tracks'], 'songs': sorted(songs, key=lambda s: s['track']),
                      'source_manifest_sha256': hashlib.sha256((root / 'data/sources/genius-lyrics-cleaned/source-files.json').read_bytes()).hexdigest(),
                      'errors': []}
        else:
            album_id = album['genius_album_id']
            meta = fetch(f'https://genius.com/api/albums/{album_id}')['response']['album']
            if meta['name'].casefold() != album['album'].casefold() or meta['artist']['name'] != album['artist']:
                raise ValueError('Unexpected album identity')
            tracks, page = [], 1
            while page:
                response = fetch(f'https://genius.com/api/albums/{album_id}/tracks?per_page=50&page={page}')['response']
                tracks.extend(response['tracks'])
                page = response.get('next_page')
            if len(tracks) != album['expected_tracks']:
                raise ValueError('Album edition changed: review tracklist before scoring')
            songs, errors = [], []
            for track in tracks:
                song = track['song']
                try:
                    if song['lyrics_state'] != 'complete':
                        raise ValueError('Incomplete lyrics')
                    lyrics = lyrics_from_html(fetch(song['url'], html=True))
                    if len(lyrics.splitlines()) < 8:
                        raise ValueError('Too few source lines')
                    songs.append({'track': track['number'], 'title': song['title'], 'artist': album['artist'],
                                  'id': f"genius:{song['id']}", 'lyrics': lyrics,
                                  'source_url': song['url'], 'source': 'genius_album',
                                  'lyrics_sha256': hashlib.sha256(lyrics.encode()).hexdigest()})
                    print(song['title'], len(lyrics.splitlines()), flush=True)
                except Exception as exc:
                    errors.append({'title': song['title'], 'error': str(exc)[:250]})
                    if getattr(getattr(exc, 'response', None), 'status_code', None) in (401, 403, 429):
                        break
            write_json(refs / (album['slug'] + '-tracklist.json'), {
                'album': album['album'], 'artist': album['artist'], 'source_url': meta['url'],
                'tracks': [{'track': t['number'], 'title': t['song']['title'], 'id': t['song']['id'],
                            'source_url': t['song']['url']} for t in tracks]})
            result = {'album': album['album'], 'artist': album['artist'], 'album_id': album_id,
                      'source_url': meta['url'], 'expected_tracks': len(tracks), 'songs': songs, 'errors': errors}
        result['collected_at'] = datetime.now(timezone.utc).isoformat()
        write_json(dest, result)
        print(f"{album['album']}: {len(result['songs'])} tracks, {len(result['errors'])} errors", flush=True)
