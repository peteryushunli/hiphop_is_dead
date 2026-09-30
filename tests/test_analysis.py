import unittest
from collections import Counter
import numpy as np

from hiphop.text import clean_lyrics, tokens, name_key
from hiphop.analyses.language_of_hiphop.pipeline import word_comparison, VARIANT, signature_word_indices
from hiphop.sources.genius import lyrics_from_html


class AnalysisTests(unittest.TestCase):
    def test_headers_and_apostrophes(self):
        lines=clean_lyrics("[Verse 1: Artist]\nWe’re here\n[Chorus]\nWe’re here\n123Embed")
        self.assertEqual(tokens(' '.join(lines)),["we're",'here',"we're",'here'])
        self.assertEqual(len(dict.fromkeys(lines)),1)

    def test_html_preserves_word_boundaries_and_lines(self):
        html='<div data-lyrics-container="true">[Verse]<br/>orange <a>sun</a><br/>blue moon</div>'
        self.assertEqual(tokens(' '.join(clean_lyrics(lyrics_from_html(html)))),['orange','sun','blue','moon'])

    def test_same_year_mix_removes_temporal_confound(self):
        # Rap is mostly in year A, other music mostly in B; within each year the word rates agree.
        rows=[]
        for year,rap_n,other_n,signal in [(2000,90,10,20),(2020,10,90,2)]:
            for group,n in [('rap',rap_n),('pop',other_n)]:
                for i in range(n):
                    c=Counter({'signal':signal,'background':100-signal})
                    rows.append({'artist':f'{group}{i%5}','genre':group,'year':year,'counts':c,
                                 'unique_line_counts':c,'n_tokens':100})
        result=next(r for r in word_comparison(rows)['words'] if r['word']=='signal')
        self.assertGreater(result['ratio'],4)
        self.assertAlmostEqual(result['year_matched_ratio'],1,places=2)

    def test_small_corpus_and_absent_reference_word_are_finite(self):
        rows=[]
        for i in range(10):
            for g,w in [('rap','signal'),('pop','background')]:
                c=Counter({w:100})
                rows.append({'artist':str(i),'genre':g,'year':2020,'counts':c,
                             'unique_line_counts':c,'n_tokens':100})
        r=word_comparison(rows)['words'][0]
        self.assertGreater(r['ratio'],0)
        self.assertEqual(r['other_per_10k'],0)

    def test_accents_and_punctuation(self):
        self.assertEqual(name_key('Beyoncé'),name_key('Beyonce'))
        self.assertEqual(name_key('JAY-Z'),name_key('Jay Z'))
        self.assertEqual(tokens('patrón déjà'), ['patron','deja'])

    def test_publishing_credit_pages_are_not_songs(self):
        self.assertTrue(VARIANT.search('Gods Son Credits'))
        self.assertFalse(VARIANT.search('Meet Joe Black'))

    def test_signature_excludes_own_name_and_backfills(self):
        terms=np.array(['kendrick','lamar',"kendrick's",'compton','lucy','drake','love'])
        scores=np.array([.9,.8,.7,.6,.5,.4,0])
        selected=signature_word_indices('Kendrick Lamar',terms,scores,limit=3)
        self.assertEqual(terms[selected].tolist(),['compton','lucy','drake'])

    def test_signature_matches_stylized_names(self):
        cases=[('A$AP Rocky',['asap','rocky',"rocky's",'a','ap','harlem']),
               ('JAY-Z',['jay','z','jayz',"jay-z's",'brooklyn']),
               ('Nicki Minaj',['nicki','minaj','nickiminaj','barbie']),
               ('N.W.A',['n','w','a','nwa','compton']),
               ('Lil’ Kim',['lil','kim',"kim's",'queen'])]
        for artist,words in cases:
            with self.subTest(artist=artist):
                terms=np.array(words)
                selected=signature_word_indices(artist,terms,np.ones(len(words)))
                self.assertEqual(terms[selected].tolist(),[words[-1]])


if __name__=='__main__':
    unittest.main()
