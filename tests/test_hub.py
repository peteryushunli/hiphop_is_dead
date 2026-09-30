"""Offline contracts: published pages are portable and source caches are reusable."""
import csv
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup
from hiphop.paths import StudyPaths
from hiphop.sources.genius import GeniusClient

ROOT = Path(__file__).resolve().parents[1]


class HubTests(unittest.TestCase):
    def test_local_site_links_stay_inside_publishable_directory(self):
        web = ROOT / 'web'
        for page in web.rglob('*.html'):
            soup = BeautifulSoup(page.read_text(), 'html.parser')
            for tag in soup.select('[href], [src]'):
                ref = urlsplit(tag.get('href') or tag.get('src'))
                if ref.scheme or ref.netloc or not ref.path:
                    continue
                target = (page.parent / unquote(ref.path)).resolve()
                with self.subTest(page=page.name, link=ref.path):
                    self.assertTrue(target.is_relative_to(web))
                    self.assertTrue(target.exists(), target)
                    if target.is_dir():
                        self.assertTrue((target / 'index.html').exists())

    def test_published_coverage_matches_audit(self):
        paths = StudyPaths(ROOT, 'language-of-hip-hop')
        audit = json.loads((paths.exports / 'audit.json').read_text())
        with (paths.exports / 'coverage.csv').open() as file:
            rows = list(csv.DictReader(file))
        self.assertEqual(sum(int(r['songs']) for r in rows if r['genre'] == 'rap'), audit['rap_songs'])
        self.assertEqual(sum(int(r['songs']) for r in rows if r['genre'] != 'rap'), audit['other_songs'])
        self.assertEqual(sum(int(r['tokens']) for r in rows), audit['total_tokens'])
        self.assertEqual(hashlib.sha256(paths.config.read_bytes()).hexdigest(), audit['config_sha256'])

    def test_studies_share_sources_but_not_outputs(self):
        a, b = (StudyPaths(ROOT, slug) for slug in ['language-of-hip-hop', 'another-study'])
        self.assertEqual(a.historical, b.historical)
        self.assertNotEqual(a.processed, b.processed)
        self.assertNotEqual(a.exports, b.exports)
        self.assertNotEqual(a.genius_cache('2026-09-30'), a.genius_cache('2027-01-01'))

    def test_cached_source_reads_without_network(self):
        with TemporaryDirectory() as directory:
            cache = Path(directory)
            url = 'https://example.invalid/api/song'
            (cache / (hashlib.sha256(url.encode()).hexdigest() + '.json')).write_text('{"cached": true}')
            with patch('hiphop.sources.genius.requests.get', side_effect=AssertionError('Network called')):
                self.assertEqual(GeniusClient(cache).fetch(url), {'cached': True})
