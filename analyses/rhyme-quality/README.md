# End-rhyme quality: ICEMAN × Illmatic × Culture

A text-only scoring pilot with three separate connection types: novel phonetic rhyme, shared terminal words, and tentative phrase slants. Model version `phonetic-suffix-v2`. The exact RhymeZone algorithm remains unknown; these ratings are our explicit approximation.

## What we learned about RhymeZone

[RhymeZone’s help](https://www.rhymezone.com/help/) identifies CMU-derived pronunciation data, supplemented by user submissions. It also describes using poetry and lyrics in near-rhyme discovery. [Datamuse](https://www.datamuse.com/api/) exposes exact rhymes (`rel_rhy`), approximate rhymes (`rel_nry`), syllables (`md=s`), and ARPAbet pronunciations (`md=r`). Its documented `score` is a search ranking with no interpretable percentage meaning. A live `rel_rhy=history&md=rs` response returned mystery with score 15043, not 100. The public documented API does not expose a general pairwise 0–100 rating endpoint.

The screenshot gives a useful behavioral clue. After discarding the opening consonant(s), history and mystery both have `IH1 S T ER0 IY0`. Victory has `IH1 K T ER0 IY0`: one consonant substitution. Mysteries adds a final `Z`; glittery removes an `S`. All these one-edit cases receive 92, consistent with an eight-point consonant penalty. This is an inference, not recovered server code.

We recorded all 17 screenshot rows plus five additional pairs from RhymeZone’s [rate](https://www.rhymezone.com/r/rhyme.cgi?Word=rate&org1=syl&org2=l&org3=y&typeofrhyme=nry) and [credible](https://www.rhymezone.com/r/rhyme.cgi?Word=credible&org1=syl&org2=l&org3=y&typeofrhyme=nry) tables. The local model agrees with all 17 dictionary-covered pairs. Five rare screenshot terms have no local pronunciation and remain unscored. This small, consonant-heavy sample does **not** identify vowel penalties or validate the model independently; the eight-point cost was chosen from these observations.

Direct page and JavaScript downloads returned CloudFront 403. A normal browser loaded the RhymeZone shell but no advanced results. No bypass was attempted. The proprietary distance function, pronunciation selection, and precise score mapping remain unknown. `references/rhymezone-observations.json` records the evidence, unknown examples, hypothesis, and access limitation.

## Sources and scope

ICEMAN: all 18 original tracks from the pinned Genius album ID 1395699. Illmatic: all ten original tracks from the existing hashed `genius-lyrics-cleaned` archive, with “The Genesis” excluded as a spoken/sample collage. Culture: all 13 original tracks from the same archive, matched to exact artist Migos and reviewed titles. Culture was released **January 27, 2017**, verified against [Apple Music](https://music.apple.com/us/album/culture/1615488284). Track order and edition follow [Amazon Music](https://music.amazon.com/albums/B09W4S8L4K), cross-checked with [Spotify](https://open.spotify.com/embed/album/4JTOxuvM2jcSqAvEZtZsOO). Features are included. “Bad and Boujee” is dated 2016 in the archive; “Halftime” is dated 1992. Album membership follows the pinned manifest, rather than filtering by release year.

A fresh public Genius metadata request was unavailable in this run. All Culture lyrics were already in the pinned local archive; no access block was bypassed. Archive provenance records exact shard, zero-based row and lyric hash, because the archive has no original Genius IDs. Source identity, complete track count, title order, artist and lyric hashes are checked before scoring.

Main results use explicit verse sections and all vocalists, including guests. Hooks, bridges, intros, outros and interludes are outside the main pass. Lyric-section sensitivity adds hooks and bridges. Source line breaks are bar proxies. No audio or performed pronunciation is inferred.

## Code walkthrough

### Sounds and strict suffixes — `phonetics.py`

Use the first CMU dictionary pronunciation consistently (`cmudict==1.1.3`), with deterministic written-elision normalization, numbers and possessives. Unknown words stop the backward scan; known suffixes after them can still be analyzed. Concatenate phones across word boundaries and inspect at most six vowel nuclei. Ignore the initial onset of the included tail, but retain consonants between nuclei and after the final nucleus.

Strict weighted Levenshtein costs are: consonant edit 8, selected neighboring vowel substitution 16, other vowel edit 40, vowel/consonant substitution 48, stressed/unstressed disagreement 4. Neighboring pairs are IH/IY, EH/AE, AH/UH, AA/AO and UH/UW. Extend a tail backward only while the next vowel agrees or is a neighbor, incremental cost is at most 16, and total rating is at least 84. Require a stressed nucleus on both sides. Scores are additive: long tails cannot dilute an incompatible preceding syllable through averaging.

Only the consonant penalty is motivated directly by the observed RhymeZone sample. The other costs and gates are modeling choices. `word_rating()` compares traditional last-stressed-vowel tails for calibration; song scoring searches the longest accepted phrase tail.

### Repeated suffixes — `connections.py:connect`

Find the longest identical terminal **word sequence**, not just the final word. Separate it, count its dictionary syllables, and compare the prefixes with the strict suffix matcher. The entire display span, repeated plus novel, is capped at six syllables. Unknown shared words remain barriers: repetition can be shown, but no rhyme is invented across them.

```python
shared = longest_common_word_suffix(words_a, words_b)
prefix_a, prefix_b = remove_shared_suffix(words_a, words_b, shared)
novel = strict_suffix_match(prefix_a, prefix_b, max_syllables=6 - shared_syllables)
credited_mass = novel.syllables * novel.rating / 100
# Shared syllables earn no credit. No novel match -> rating=None, mass=0.
```

| Pair | Full span | Repeated, no credit | Credited | Rating |
| --- | ---: | ---: | ---: | ---: |
| blow money / show money | 3 | 2 | 1 | 100 |
| coal money / Cole money | 3 | 2 | 1 | 100 |
| blow old money / show old money | 4 | 3 | 1 | 100 |
| cat money / blue money | 2 | 2 | 0 | — |

Thus J. Cole-style repeated “money” endings remain connected, while the changing rhyme before “money” supplies the score. Homophones with different words, such as coal/Cole, are still phonetic rhymes. This is an end-rhyme pass; multiple internal “money” phrases inside one bar are not separately counted.

### Conservative ad-libs — `endpoints.py`

Keep `raw`, the original source line, separate from lead text and the adopted `analysis_text` endpoint. Short parentheticals (at most four tokens) are separated only if all their words are in the explicit vocalization allowlist or they exactly echo the immediately preceding lead words. Other parenthetical content stays. This replaces the old blanket removal of all parentheticals. Parenthetical-only allowlisted lines are excluded; unmarked standalone ad-libs are conservatively retained.

For an unmarked trailing suffix:

1. Require punctuation and one or two allowlisted tokens, such as “, yeah” or “, ayy”. Substantive “money” cannot enter this rule.
2. Propose the shortened endpoint without committing it.
3. Check the previous and next four eligible lines in the same section. Only unchanged native endpoints are witnesses; another proposed deletion cannot supply evidence. This prevents circular removal.
4. Require **two** supporting lines and more supporting lines than the original endpoint has. Support means a positive strict novel match, or at least two identical repeated syllables. Repetition can help locate an endpoint without earning rhyme credit. Tentative slants cannot validate a deletion.
5. Keep the original endpoint when evidence is insufficient. Export the candidate, adopted decision and supporting source line numbers for inspection.

In the Dust example, the endpoint before the first “yeah” is supported by native “riser” and “advisor”; the second is supported by native “eyes up” and “lined up”. Both decisions are made from unchanged witnesses, independently. A passage consisting only of proposed “cat, yeah” / “hat, yeah” / “bat, yeah” endpoints stays unresolved, even though a human can hear the likely scheme.

This rule is intentionally incomplete. Short unfamiliar vocalizations, meaningful backing words such as “Cash”, long repeated ad-lib runs, standalone ad-libs and phrases needing delivery may remain. The inspector shows those source lines and unresolved allowlisted candidates. Increased rhyme coverage is not a correctness benchmark.

### Phrase slants — `connections.py:phrase_slant`

The strict final-vowel-first algorithm cannot get past ER versus AH at the end of “riser” / “guys up”. The new tentative branch aligns a multi-syllable phrase around its stressed anchor instead:

```text
riser:    [AY1] Z [ER0]
guys up:  [AY1] Z [AH1] P
```

AY is the “eye” diphthong. Both spellings map to the same vowel; letters are irrelevant after dictionary conversion. This does not equate ER with AH or silently delete the final P.

Require at least two aligned nuclei, an identical stressed first nucleus on both sides, no incompatible earlier vowel, a shared consonant between the last two nuclei, and at most one consonant edit there. The final vowel may differ only within ER/AH, ER/UH or AH/UH, and at least one of the final vowels must be dictionary-unstressed. Earlier phones retain strict costs. A central final-vowel mismatch costs 12; final consonant edits cost half the normal 8; stress disagreement still costs 4. Accept tentative scores of at least 76.

For riser/guys up: anchor/intervening sounds cost 0, ER/AH costs 12, added P costs 4, and dictionary stress disagreement costs 4, giving **80**. This is a deliberately provisional two-syllable slant estimate, not an official RhymeZone score. The narrow rule rejects riser/blue cup, riser/line up and riser/guys cat. It does not cover every rap slant rhyme or syllable compression.

### Local scheme and aggregation — `model.py`, `pipeline.py`

Compare each current line to the previous four eligible lines in its section. Section labels reset the window. Select at most one incoming connection: positive strict rhyme first, repetition-only next, tentative slant last. Within a category select greatest novel weighted syllables, then rating, then proximity. This prevents a longer uncertain slant from displacing a scored strict rhyme, and prevents all pair combinations from inflating totals.

Strict family IDs use selected non-slant connections. Expanded family IDs additionally join all locally detected tentative slant pairs. The inspector checkbox switches between these views. This is a transitive graph heuristic; a weak bridge can join families, and it is not proof of artist intent. Adjacent comparisons are displayed independently even when the strongest selected predecessor skips a line.

Primary means, medians and totals include positive strict links only. Repetition-only connections have no rating and contribute zero. Tentative slants contribute zero to primary totals; the separate “include tentative slants” scenario includes selected tentative links. It does not add every possible pair or displace already selected strict/repeated links.

```python
scored = [l for l in selected_links if l.syllables > 0 and l.kind != 'slant']
weighted_syllables = sum(l.syllables * l.rating / 100 for l in scored)
weighted_per_100_lines = 100 * weighted_syllables / eligible_verse_lines
```

The denominator includes anchors, unknown endings and unlinked eligible lines. Null mean means no scored links, not zero quality. Album means/medians pool links; totals sum songs. An equal-song mean is also exported. Full spans in the inspector can include repeated syllables, but primary syllable metrics always mean **credited novel syllables**.

## Updated results

| Metric | ICEMAN | Illmatic | Culture |
| --- | ---: | ---: | ---: |
| Scored tracks | 18 | 9 | 13 |
| Verse lines | 794 | 499 | 701 |
| Scored links | 433 | 182 | 241 |
| Mean rating | 91.10 | 93.03 | 91.72 |
| Median rating | 92 | 92.00 | 92 |
| Sum rating points | 39448 | 16932 | 22104 |
| Mean credited syllables | 1.56 | 1.25 | 1.31 |
| Credited syllables | 674 | 228 | 315 |
| Weighted / 100 lines | 76.25 | 42.31 | 40.78 |
| Repetition-only connections | 35 | 2 | 34 |
| Rhymes before shared suffix | 28 | 4 | 21 |
| Selected tentative slants | 5 | 3 | 2 |
| Marked ad-lib lines separated | 17 | 0 | 194 |
| Unmarked endpoints moved | 17 | 0 | 5 |
| Unresolved candidates retained | 18 | 1 | 25 |
| Unknown analyzed endings | 38 | 18 | 60 |

Culture's credited syllables rise from 259 with raw endpoints, to 310 with short marked parentheticals separated, to 315 with the additional conservative unmarked rule. Weighted volume rises from 33.33 to 40.17 to 40.78 per 100 verse lines. The unmarked rule moves five lines, with a net two additional scored links and five additional syllables; it leaves 25 candidates untouched. Those are implementation effects, not evidence that all intended rhymes were found.

Both known Drake “yeah” endings now move to the supported lead endpoint. With tentative slants shown, high-riser / guys up / riser / eyes up / advisor / lined up connect in the expanded family. The shared riser/up words remain uncredited. With tentative slants hidden, the AY-ER and AY-AH-P families split.

These measurements remain narrower than rhyme quality: no internal rhyme, delivery, actual bar alignment, voice isolation or wordplay. The conditional mean is high partly because weak matches are excluded. Culture's retained backing words and unknown vocabulary can reduce coverage. Compare settings and inspect specific decisions before drawing artistic conclusions.

## Track results

### ICEMAN

| Song | Mean rating | Median | Credited syllables | Ad-lib endpoints moved |
| --- | ---: | ---: | ---: | ---: |
| Make Them Cry | 89.8 | 92 | 90 | 2 |
| Dust | 91.5 | 92 | 24 | 3 |
| Whisper My Name | 92.4 | 92 | 30 | 0 |
| Janice STFU | 91.7 | 92 | 33 | 3 |
| Ran To Atlanta | 89.9 | 92 | 24 | 1 |
| Shabang | 91.3 | 92 | 11 | 0 |
| Make Them Pay | 90.3 | 92 | 76 | 2 |
| Burning Bridges | 88.7 | 88 | 20 | 2 |
| National Treasures | 90.6 | 92 | 47 | 0 |
| B’s On The Table | 95.3 | 92 | 21 | 2 |
| What Did I Miss? | 91.3 | 92 | 19 | 0 |
| Plot Twist | 90.9 | 92 | 11 | 0 |
| 2 Hard 4 The Radio | 92.4 | 92 | 29 | 0 |
| Make Them Remember | 90.4 | 92 | 110 | 1 |
| Little Birdie | 88.0 | 88 | 13 | 0 |
| Don’t Worry | 100.0 | 100 | 6 | 0 |
| Firm Friends | 91.4 | 92 | 54 | 1 |
| Make Them Know | 91.4 | 92 | 56 | 0 |

### Illmatic

| Song | Mean rating | Median | Credited syllables | Ad-lib endpoints moved |
| --- | ---: | ---: | ---: | ---: |
| N.Y. State of Mind | 92.0 | 92 | 33 | 0 |
| Life’s a Bitch | 93.6 | 96 | 15 | 0 |
| The World Is Yours | 94.3 | 92 | 27 | 0 |
| Halftime | 93.3 | 92 | 37 | 0 |
| Memory Lane (Sittin’ in da Park) | 93.8 | 92 | 24 | 0 |
| One Love | 94.1 | 92 | 37 | 0 |
| One Time 4 Your Mind | 92.0 | 92 | 17 | 0 |
| Represent | 90.7 | 92 | 22 | 0 |
| It Ain’t Hard to Tell | 92.7 | 92 | 16 | 0 |

### Culture

| Song | Mean rating | Median | Credited syllables | Ad-lib endpoints moved |
| --- | ---: | ---: | ---: | ---: |
| Culture | 92.0 | 92 | 26 | 0 |
| T-Shirt | 92.8 | 92 | 16 | 1 |
| Call Casting | 93.1 | 92 | 40 | 0 |
| Bad and Boujee | 91.9 | 92 | 33 | 2 |
| Get Right Witcha | 88.0 | 88 | 21 | 1 |
| Slippery | 90.9 | 92 | 26 | 0 |
| Big on Big | 90.3 | 92 | 30 | 0 |
| What the Price | 87.2 | 84 | 14 | 0 |
| Brown Paper Bag | 91.5 | 92 | 19 | 1 |
| Deadz | 92.9 | 92 | 14 | 0 |
| All Ass | 92.5 | 92 | 23 | 0 |
| Kelly Price | 92.4 | 92 | 24 | 0 |
| Out Yo Way | 93.8 | 92 | 29 | 0 |

## Sensitivity and verification

Change one setting at a time: strict threshold 80/84/92, adjacent-only, lyric sections, no unmarked removal, raw endpoints, old identical-end-word rejection, and inclusion of tentative slants. The strict threshold never changes the separate slant cutoff. The old-end-word scenario changes only repeated-suffix handling, not every other v1 behavior.

| Scenario | ICEMAN weighted / 100 | Illmatic weighted / 100 | Culture weighted / 100 |
| --- | ---: | ---: | ---: |
| threshold-80 | 78.32 | 43.27 | 42.43 |
| threshold-84 | 76.25 | 42.31 | 40.78 |
| threshold-92 | 55.69 | 34.47 | 31.74 |
| adjacent-only | 48.24 | 38.16 | 21.90 |
| lyric-sections | 72.11 | 37.50 | 34.20 |
| no-unmarked-adlib-removal | 72.39 | 42.31 | 40.17 |
| raw-endpoints | 71.09 | 42.31 | 33.33 |
| no-repeated-suffix-credit | 70.58 | 41.89 | 37.34 |
| include-tentative-slants | 77.26 | 43.33 | 41.23 |

Synthetic checks cover repeated multiword suffixes, no-credit repetition-only means, homophones, unknown barriers, independent ad-lib witnesses, rejection of circular removal, section boundaries, substantive suffix preservation, short marked echoes, phrase-slant positive/negative pairs, separate slant totals, the Dust-style chain, strict multisyllable extension, ABAB and one incoming link per line. Repository checks also reconcile album/song sums and ensure aggregate line exports contain no full lyrics. This validates implementation, not precision/recall against human labels.

The next empirical test is a human-labeled sample of accepted/rejected pairs and adopted/retained ad-lib candidates. More coverage alone does not establish better accuracy.

## Reproduce and inspect

```sh
hiphop fetch historical                   # only if archive not already available
hiphop fetch albums --study rhyme-quality # Genius ICEMAN; archive Illmatic/Culture
hiphop run rhyme-quality                  # cached sources; no network
python -m unittest discover -s tests -v
hiphop serve
```

Config pins albums, pronunciation policy, six-syllable cap, four-line window, strict and slant cutoffs, repetition handling and ad-lib support count. Full lyric snapshots and `data/processed/rhyme-quality/line-audit.json` remain ignored local files. Public exports include source hashes, software versions, complete track manifests, song/album aggregates, sensitivity scenarios and numeric line decisions.

The local inspector shows credited endings with a solid underline, shared words with a dotted underline, trailing ad-libs in muted type, and badges explaining marked/unmarked decisions. Original-source and tentative-slant checkboxes expose the alternatives. Pair buttons identify whether a connection is scored, repetition-only or tentative. Anchor rows prefer the first later scored connection, otherwise a repetition or tentative connection, without adding a second score. Whole-word highlights can include extra syllables in their first word; numeric counts govern the credit.

`lyrics.local.js` is explicitly ignored and loaded only on localhost/direct-file previews. Public copies without it show numeric patterns and an availability message. Source lines refer to cached transcription, not recording timestamps.
