"""Synthetic offline checks of the pilot's substantive scoring rules."""
import json
from pathlib import Path
import unittest

from hiphop.analyses.rhyme_quality.phonetics import tail, match_tails, word_rating, words
from hiphop.analyses.rhyme_quality.model import analyze_song, lyric_lines, summarize_links
from hiphop.analyses.rhyme_quality.pipeline import inspection_records
from hiphop.analyses.rhyme_quality.connections import connect

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / 'analyses/rhyme-quality/config.json').read_text())


class RhymeTests(unittest.TestCase):
    def compare(self, a, b, **kwargs):
        return match_tails(tail(a), tail(b), **kwargs)

    def song(self, lyrics, **kwargs):
        return analyze_song({'title': 'Synthetic', 'track': 1, 'lyrics': lyrics}, CONFIG, **kwargs)

    def test_exact_and_near_word_ratings(self):
        self.assertEqual(word_rating('history', 'mystery'), 100)
        self.assertEqual(word_rating('history', 'victory'), 92)
        self.assertEqual(word_rating('history', 'mysteries'), 92)

    def test_phrase_extension_and_cutoff(self):
        self.assertEqual(self.compare('mystery', 'history').syllables, 3)
        extended = self.compare('red mystery', 'dead history')
        self.assertEqual((extended.syllables, extended.rating), (4, 92))
        self.assertEqual(self.compare('blue mystery', 'dead history').syllables, 3)
        self.assertEqual(self.compare('bright red mystery', 'white dead history').syllables, 5)
        self.assertIsNone(self.compare('cat', 'shoe'))
        self.assertIsNone(self.compare('doggy', 'silly'))  # just an unstressed y
        self.assertEqual(self.compare('red mystery', 'dead history', max_syllables=3).syllables, 3)

    def test_unknowns_never_bridge_or_become_zeros(self):
        self.assertIsNone(self.compare('a qzxxyzz', 'a mystery'))
        self.assertEqual(self.compare('qzxxyzz mystery', 'red history').syllables, 3)
        a = self.song('[Verse]\nqzxxyzz\ncat\nhat')
        self.assertEqual(a['metrics']['unknown_endings'], 1)
        self.assertEqual(a['metrics']['rhyme_links'], 1)
        self.assertEqual(a['metrics']['mean_rating'], 100)

    def test_abab_and_section_reset(self):
        a = self.song('[Verse 1]\ncat\nblue\nhat\nshoe\n[Verse 2]\ncat')
        self.assertEqual([(l['from_index'], l['to_index']) for l in a['links']], [(0, 2), (1, 3)])
        self.assertEqual(a['metrics']['schemes'], 2)
        adjacent = self.song('[Verse]\ncat\nblue\nhat\nshoe', lookback_lines=1)
        self.assertEqual(adjacent['metrics']['rhyme_links'], 0)

    def test_expiration_and_repeated_words(self):
        a = self.song('[Verse]\ncat\nblue\nred\ngreen\nmoon\nhat')
        self.assertFalse(any(l['from_index'] == 0 and l['to_index'] == 5 for l in a['links']))
        self.assertIsNone(self.compare('I like the cat', 'I see the cat'))

    def test_one_link_per_current_line_and_pooled_statistics(self):
        a = self.song('[Verse]\ncat\nhat\nbat\nmat')
        self.assertEqual(len({l['to_index'] for l in a['links']}), len(a['links']))
        self.assertEqual(a['metrics']['total_rhymed_syllables'], 3)
        self.assertEqual(a['metrics']['weighted_syllables_per_100_lines'], 75)
        pooled = summarize_links(a['links'] + [{'rating': 84, 'syllables': 2}], 8, 7)
        self.assertEqual(pooled['mean_rating'], 96)
        self.assertEqual(pooled['median_rating'], 100)
        self.assertEqual(pooled['total_rhymed_syllables'], 5)

    def test_labels_and_adlibs_preserve_source_locations(self):
        lines = list(lyric_lines('[Verse: AZ]\ncat (yeah)\n\n[Chorus]\nshoe\n[Verse: Nas]\nhat'))
        self.assertEqual([l['source_line'] for l in lines], [2, 5, 7])
        self.assertEqual(lines[0]['text'], 'cat')
        self.assertEqual(len(self.song('[Verse]\ncat\n[Chorus]\nhat')['lines']), 1)
        self.assertEqual(len(self.song('[Verse]\ncat\n[Chorus]\nhat', scope='lyric_sections')['lines']), 2)
        self.assertEqual(words('gеnius mist\u200bery'), ['genius', 'mistery'])

    def test_exports_are_consistent_and_do_not_publish_lyrics(self):
        result = json.loads((ROOT / 'web/analyses/rhyme-quality/exports/results.json').read_text())
        for album in result['albums']:
            self.assertTrue(album['complete'])
            for key in ['eligible_lines', 'rhyme_links', 'total_rhymed_syllables', 'total_rating_points']:
                self.assertEqual(sum(s['metrics'][key] for s in album['songs']), album['metrics'][key])
        for line in result['line_records']:
            self.assertFalse({'text', 'raw', 'ending_word', 'phones'} & line.keys())

    def test_inspector_keeps_adjacent_match_when_best_link_skips_a_line(self):
        song = self.song('[Verse]\nred mystery\nblue mystery\ndead history')
        display = inspection_records(song, CONFIG)
        self.assertEqual(display[2]['predecessor'], 0)
        self.assertEqual(display[2]['syllables'], 4)
        self.assertEqual((display[2]['adjacent_syllables'], display[2]['adjacent_rating']), (3, 100))
        self.assertEqual(display[0]['anchor_partner'], 2)
        self.assertEqual(display[0]['anchor_syllables'], 4)
        self.assertEqual(display[0]['text'][display[0]['ending_start']:], 'red mystery')
        self.assertEqual(display[2]['line_syllables'], 4)
        self.assertEqual(song['metrics']['total_rhymed_syllables'], 4)


    def test_repeated_suffix_connects_without_credit(self):
        m = connect('blow money', 'show money', CONFIG)
        self.assertEqual((m['full_syllables'], m['repeated_syllables'], m['syllables'], m['rating']), (3, 2, 1, 100))
        m = connect('blow old money', 'show old money', CONFIG)
        self.assertEqual((m['full_syllables'], m['repeated_syllables'], m['syllables']), (4, 3, 1))
        a = self.song('[Verse]\ncat money\nblue money')
        self.assertEqual(a['lines'][0]['scheme'], a['lines'][1]['scheme'])
        self.assertEqual(a['metrics']['repeat_only_links'], 1)
        self.assertEqual(a['metrics']['total_rhymed_syllables'], 0)
        self.assertIsNone(a['metrics']['mean_rating'])
        a = self.song('[Verse]\nblow money\nshow money\ngrow money')
        self.assertEqual(a['metrics']['total_rhymed_syllables'], 2)
        self.assertEqual(a['metrics']['repeated_syllables_uncredited'], 4)

    def test_repeated_unknown_suffix_remains_a_barrier(self):
        m = connect('blow qzxxyzz', 'show qzxxyzz', CONFIG)
        self.assertEqual(m['kind'], 'repetition')
        self.assertEqual(m['syllables'], 0)
        self.assertFalse(m['repetition_known'])

    def test_unmarked_adlib_requires_two_native_witnesses(self):
        a = self.song('[Verse]\nhigh-riser, yeah\nriser\nadvisor')
        self.assertEqual(a['lines'][0]['analysis_text'], 'high-riser')
        self.assertEqual(a['lines'][0]['adlib_support'], [3, 4])
        a = self.song('[Verse]\ncat, yeah\nhat')
        self.assertEqual(a['lines'][0]['analysis_text'], 'cat, yeah')
        a = self.song('[Verse]\ncat, yeah\nhat, yeah\nbat, yeah')
        self.assertFalse(any(l['ignored_adlib'] for l in a['lines']))  # no circular support
        a = self.song('[Verse 1]\ncat, yeah\n[Verse 2]\nhat\nbat')
        self.assertFalse(a['lines'][0]['ignored_adlib'])
        a = self.song('[Verse]\nshow, money\nblow\ngrow')
        self.assertFalse(a['lines'][0]['adlib_candidate'])  # substantive suffix not allowlisted

    def test_marked_adlibs_are_short_or_echoes_not_arbitrary_text(self):
        lines = list(lyric_lines('[Verse]\ncat (yeah)\nhat (hat)\nbat (the history of the world)'))
        self.assertEqual(lines[0]['text'], 'cat')
        self.assertEqual(lines[1]['text'], 'hat')
        self.assertIn('(the history of the world)', lines[2]['text'])
        self.assertEqual(lines[0]['raw'], 'cat (yeah)')
        self.assertEqual(lines[0]['removed_parentheticals'], ['(yeah)'])

    def test_phrase_slant_retains_stressed_anchor_and_is_separate(self):
        m = connect('riser', 'guys up', CONFIG)
        self.assertEqual((m['kind'], m['syllables'], m['rating']), ('slant', 2, 80))
        for a, b in [('riser', 'blue cup'), ('riser', 'line up'), ('riser', 'guys cat')]:
            self.assertIsNone(connect(a, b, CONFIG))
        a = self.song('[Verse]\nriser\nguys up')
        self.assertEqual(a['metrics']['rhyme_links'], 0)
        self.assertEqual(a['metrics']['tentative_slant_links'], 1)
        self.assertEqual(a['metrics']['total_rhymed_syllables'], 0)
        self.assertIsNone(a['metrics']['mean_rating'])
        expanded = summarize_links(a['links'], 2, 2, include_slants=True)
        self.assertEqual(expanded['total_rhymed_syllables'], 2)
        self.assertEqual(expanded['weighted_rhyme_syllables'], 1.6)
        self.assertEqual(a['lines'][0]['expanded_scheme'], a['lines'][1]['expanded_scheme'])

    def test_dust_style_chain_adlibs_slants_repetition(self):
        a = self.song('[Verse]\nhigh-riser, yeah\nmy guys up, yeah\non a riser\nmy eyes up\ntrusted advisor\nlined up')
        self.assertTrue(a['lines'][0]['ignored_adlib'])
        self.assertTrue(a['lines'][1]['ignored_adlib'])
        self.assertEqual(len({l['expanded_scheme'] for l in a['lines']}), 1)
        display = inspection_records(a, CONFIG)
        self.assertEqual(display[1]['adjacent_kind'], 'slant')
        self.assertEqual(display[2]['repeated_syllables'], 2)
        self.assertEqual(display[2]['syllables'], 0)
