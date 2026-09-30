"""Collect a cached, bounded supplement from public Genius pages; never bypass blocks."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
import hashlib
import json
import re
import threading
import time

from bs4 import BeautifulSoup
import requests

from hiphop.text import name_key as key


class GeniusClient:
    def __init__(self, cache):
        self.cache = cache
        cache.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.last_request = 0.0

    def fetch(self, url, html=False):
        cache = self.cache/(hashlib.sha256(url.encode()).hexdigest()+('.html' if html else '.json'))
        if cache.exists():
            content = cache.read_text()
            return content if html else json.loads(content)
        with self.lock:
            time.sleep(max(0, 0.35-(time.monotonic()-self.last_request)))
            self.last_request = time.monotonic()
        response = requests.get(url, timeout=(15,45), headers={'User-Agent': 'HipHopWordsResearch/0.1 (local analysis)'})
        response.raise_for_status()
        content = response.text
        result = content if html else response.json()
        if html and 'data-lyrics-container' not in content:
            raise ValueError('No lyrics containers; possible unavailable page')
        cache.write_text(content)
        return result



def lyrics_from_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    containers = soup.select('[data-lyrics-container="true"]')
    blocks = []
    for element in containers:
        for br in element.find_all('br'):
            br.replace_with('\n')
        for bad in element.select('script, style, button, [data-exclude-from-selection="true"]'):
            bad.decompose()
        text = element.get_text('', strip=False)
        # The lyric header may be inside the first container on newer page layouts.
        text = re.sub(r'^.*?\bLyrics\s*(?=\[)', '', text, count=1, flags=re.S)
        text = re.sub(r'\d*\s*Embed\s*$', '', text)
        if text.strip():
            blocks.append(text.strip())
    return '\n'.join(blocks)


def collect_snapshot(config, outdir, cache, workers=3, limit_artists=None):
    fetch = GeniusClient(cache).fetch
    outdir.mkdir(parents=True, exist_ok=True)
    cutoff = date.fromisoformat(config['as_of'])
    artists = [a for a in config['artists'] if a['collect_recent']][:limit_artists]

    def collect(entry):
        artist = entry['artist']
        outfile = outdir/(key(artist)+'.json')
        if outfile.exists():
            previous = json.loads(outfile.read_text())
            if previous.get('complete') and previous.get('as_of') == config['as_of']:
                print(f'Cached {artist}: {len(previous["songs"])} songs',flush=True)
                return
        result = {'artist':artist,'as_of':config['as_of'], 'genre':entry['genre'],
                  'collected_at':datetime.now(timezone.utc).isoformat(), 'songs':[],
                  'exclusions':[], 'errors':[], 'catalog_entries':0, 'complete':False}
        try:
            search = fetch('https://genius.com/api/search/multi?q='+requests.utils.quote(artist))
            candidates = []
            for section in search['response']['sections']:
                for hit in section.get('hits',[]):
                    r = hit['result']
                    candidate = r if hit.get('type') == 'artist' else r.get('primary_artist',{})
                    if key(candidate.get('name','')) == key(artist):
                        candidates.append(candidate)
            if not candidates:
                raise ValueError('No exact normalized artist match')
            artist_id = candidates[0]['id']
            result['genius_artist_id'] = artist_id
            songs = {}
            for page in range(1, config['recent_catalog_pages']+1):
                data = fetch(f'https://genius.com/api/artists/{artist_id}/songs?sort=popularity&per_page=50&page={page}')
                for song in data['response']['songs']:
                    songs[song['id']] = song
                if not data['response'].get('next_page'):
                    break
            result['catalog_entries'] = len(songs)
            for song in songs.values():
                parts = song.get('release_date_components') or {}
                year = parts.get('year')
                if not year or year < config['recent_start_year'] or year > cutoff.year:
                    continue
                # Artist song lists include features; only accept a primary artist match.
                primary = song.get('primary_artists') or [song.get('primary_artist',{})]
                if artist_id not in [a.get('id') for a in primary]:
                    continue
                if len(result['songs']) >= config['recent_max_songs_per_artist']:
                    break
                try:
                    detail = fetch(f'https://genius.com/api/songs/{song["id"]}')['response']['song']
                    release = detail.get('release_date')
                    reason = None
                    if not release or len(release) != 10:
                        reason = 'missing_full_release_date'
                    elif date.fromisoformat(release) > cutoff:
                        reason = 'after_cutoff'
                    elif detail.get('language') != 'en':
                        reason = 'not_confirmed_english'
                    elif detail.get('lyrics_state') != 'complete' or detail.get('instrumental'):
                        reason = 'incomplete_or_instrumental'
                    if reason:
                        result['exclusions'].append({'id':song['id'],'reason':reason})
                        continue
                    lyrics = lyrics_from_html(fetch(detail['url'], html=True))
                    if len(lyrics.split()) < config['min_words_per_song']:
                        result['exclusions'].append({'id':song['id'],'reason':'too_short'})
                        continue
                    result['songs'].append({'id':f'genius:{song["id"]}', 'artist':artist,
                        'title':detail['title'],'year':int(release[:4]),'release_date':release,
                        'genre':entry['genre'],'lyrics':lyrics,'source_url':detail['url'],
                        'language':detail['language'],'tags':[t['name'] for t in detail.get('tags',[])],
                        'primary_artists':[a['name'] for a in detail.get('primary_artists',[])],
                        'featured_artists':[a['name'] for a in detail.get('featured_artists',[])],
                        'source':'genius_recent','collected_at':result['collected_at']})
                except (requests.RequestException, ValueError, KeyError) as exc:
                    result['errors'].append({'id':song['id'],'error':str(exc)[:180]})
                    if isinstance(exc, requests.HTTPError) and exc.response.status_code in (401,403,429):
                        break
            result['complete'] = not result['errors']
        except (requests.RequestException, ValueError, KeyError) as exc:
            result['errors'].append({'error':str(exc)[:180]})
        outfile.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(f'{artist}: {len(result["songs"])} songs, {len(result["errors"])} errors',flush=True)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(collect,artists))
