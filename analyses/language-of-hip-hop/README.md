# The language of hip-hop, 1990–now

A reproducible, local recreation and extension of [The Pudding’s 2017 analysis](https://pudding.cool/2017/09/hip-hop-words/): genre-distinctive words, artist signature vocabulary, cosine similarity, and a t-SNE map. Adds decade comparisons, annual word histories, release-year matching, and a repeated-line sensitivity check.

The main release window is **1990-01-01 through 2026-09-30**. This is a new editorial sample, not a literal superset of the original study’s songs. Original source files also contain pre-1990 records, but those are excluded from this analysis.

## View the results

Open [the explorer](../../web/analyses/language-of-hip-hop/index.html) directly in a browser, or run:

```sh
python3 -m http.server 8765 --bind 127.0.0.1 --directory web
```

Then visit `http://127.0.0.1:8765/analyses/language-of-hip-hop/`. No JavaScript dependencies or external services are needed by the explorer. `web/analyses/language-of-hip-hop/data.js` contains derived aggregates, not lyric text.

## Reproduce

Run these commands from the repository root after installing the package as described in the [hub README](../../README.md). Python 3.11+ is required.

```sh
hiphop fetch historical --workers 3
hiphop fetch recent --workers 3
hiphop run language-of-hip-hop
python3 -m unittest discover -s tests -v
```

Historical downloads resume and verify SHA-256 hashes against the recorded upstream manifest. Collection caches are local. The recent collector skips successful artist snapshots for the same cutoff; change the cutoff and rerun to collect a new snapshot. Snapshots and URL caches are separated by cutoff date; a new cutoff uses a fresh cache directory. It does not bypass unavailable pages or access challenges.

`--allow-partial` on the analyzer creates an explicitly provisional preview before historical collection finishes. The standard command requires all ten historical files. The audit separately identifies any pending or failed recent artist collection.

## Sources and sampling

1. **Historical:** [theelderemo/genius-lyrics-cleaned](https://huggingface.co/datasets/theelderemo/genius-lyrics-cleaned), revision recorded in `data/sources/genius-lyrics-cleaned/source-info.json`, ten immutable Parquet files with expected hashes in `data/sources/genius-lyrics-cleaned/source-files.json`. Derived from the [Genius Song Lyrics dataset on Kaggle](https://www.kaggle.com/datasets/carlosgdcj/genius-song-lyrics-with-language-information). Its upload date is not its coverage date. We accept historical release years through 2022; later entries in this old collection are unverified and excluded. There is a substantial coverage drop during 2022.
2. **Recent supplement:** public Genius artist search, catalog metadata, individual song metadata, and lyric pages. Collect up to two pages of 50 popularity-sorted entries for each of 68 contemporary artists, retaining at most 40 eligible songs from 2023 onward. Require a matching primary artist, confirmed English language, completed lyrics, full release date, and date no later than the cutoff. No account or API key was used.

`analyses/language-of-hip-hop/config.json` defines **429 artists** across rap, pop, R&B, rock, and country. It combines the 307 names in [The Pudding’s published artist roster](https://pudding.cool/2017/09/hip-hop-words/data/artist_song_counts_full.csv) with editorial additions, including newer artists and the comparison genres. The article describes 308 mapped artists, while the currently available roster file has 307 rows and its map file has 306; those source artifacts are preserved as downloaded. This is not representative sampling. `hiphop cohort language-of-hip-hop` reproduces the configuration; edit `analyses/language-of-hip-hop/config.json` directly for subsequent cohort changes.

The historical corpus matches normalized artist names exactly, with a small documented alias map. Joint artist strings in the historical dataset are excluded unless they match a cohort entry; feature verses within accepted songs remain. Genre is assigned at the artist level, including crossover artists. Comparisons therefore concern these collected catalogs, not a claim about all tracks assigned to a genre.

### Local data and exports

- `data/raw/`: shared historical Parquet files and dated per-artist recent collections; ignored by Git.
- `data/cache/`: fetched JSON and HTML; ignored by Git.
- `data/processed/language-of-hip-hop/song_index.parquet`: per-song metadata, source locator, token count, and lyric fingerprint; no raw lyric text.
- `web/analyses/language-of-hip-hop/exports/audit.json`: source completion, exclusions, observed artists, raw-year counts, and coverage.
- `web/analyses/language-of-hip-hop/exports/coverage.csv`: counts by release year, genre, and source.
- `web/analyses/language-of-hip-hop/exports/artists.csv`: retained songs and date ranges per artist.
- `web/analyses/language-of-hip-hop/exports/pudding-roster-coverage.csv`: matching and map eligibility for every artist in the original published roster.
- `analyses/language-of-hip-hop/references/exclusions.json`: individually reviewed non-song exclusions and reasons.
- `web/analyses/language-of-hip-hop/exports/words-*.csv`: period-specific rankings and sensitivity measures.
- `web/analyses/language-of-hip-hop/exports/trends.csv`: annual word counts, normalized rates, and song prevalence.
- `web/analyses/language-of-hip-hop/`: self-contained interactive explorer and derived data.

Full lyrics and source-page caches are not committed or published by this project. The upstream card’s license label should not be interpreted as this project granting rights to the underlying songs.

## Methods

### Cleaning and unit of analysis

Lowercase; normalize Unicode apostrophes; fold accents for tokenization; remove bracketed section/performer labels, common website boilerplate, and trailing embed counters. Preserve slang and contractions. No stemming, lemmatization, stop-word removal, profanity filtering, or speculative slang merging is applied.

Require 50 tokens per song. Exclude titles indicating remixes, remasters, live-at/from/in recordings, instrumentals, demos, snippets, translations, and selected non-song content. This conservative title filter can omit legitimate recordings. Deduplicate by tokenized full-text hash across the corpus and by normalized artist/title. Keep the earliest listed release; when tied, use deterministic artist/title/source ordering. This is exact/content-title deduplication, not a full near-duplicate audio or text match.

Lyrics remain attached to the credited catalog, not individual vocalists. Features, interpolations, sampled vocals, and transcriptions can affect signatures. The original study’s light lemmatization is not reproduced; the cleaning and sampling differences prevent direct numerical equivalence with its rankings.

### Distinctive words

For each period, pool hip-hop tokens and comparison tokens separately. Display observed word frequency per 10,000 tokens. Rank using the frequency ratio:

```text
((rap_count + 0.5) / (rap_total + 1)) /
((other_count + 0.5) / (other_total + 1))
```

These are **frequency ratios, not odds ratios or probabilities of genre membership**. Smoothing avoids an infinite result when the comparison count is zero; very large ratios still need caution. Support requirements: at least 10 rap songs, five rap artists, and `max(30, round(rap_total × 1000 / 26,000,000))` rap occurrences. The last rule scales the original study’s 1,000-of-26-million threshold.

Two sensitivity measures accompany the pooled result:

- **Release-year matching:** restrict to years with both groups; weight each comparison-year word rate by that year’s share of hip-hop tokens. This adjusts year mix, not artist composition or comparison-genre mix.
- **Repeated-line check:** count each identical cleaned line once within a song, then recalculate the pooled frequency ratio. It does not identify all musical chorus repetitions or expand shorthand such as “chorus ×2.”

The UI shows the top 15 words; CSV exports include all words meeting the support floor. Annual trends are restricted to the union of the top 40 pooled words per period plus a small fixed exploration list, and display both token rate and song prevalence.

### Artist signatures and map

Use artists with at least 20 retained rap songs. Build one count vector per artist. Retain words used by at least `ceil(0.10 × eligible_artists)` artists. Apply term frequency `1 + log(count)`, smoothed IDF `log((1 + N)/(1 + document_frequency)) + 1`, then L2 normalize.

The ten largest eligible weights are the signature words. Each artist’s own name components, punctuation/stylized variants (such as JAY-Z/jayz and A$AP/asap), and possessive forms are excluded from their displayed signature list; the next highest-scoring words fill the gaps. This name filter applies to signature selection only. Neighbors use cosine similarity on the complete TF-IDF vectors. The map reduces them with Truncated SVD (up to 50 components) and t-SNE (seed 42, PCA initialization, automatic learning rate, 1,500 iterations, perplexity `min(40, (N - 1)/3)`). Map axes have no semantic units. Global distances and islands must not be read as a precise ranking.

## Interpretation limits

All results describe the sample. The recent supplement is popularity-capped and artist-selected; the historical dataset has different selection and metadata. Missingness is not random. Years after 2022 must not be used to claim an industry-wide trend without a consistent sampling frame. 2026 is a partial year. We have not produced confidence intervals or established statistical significance.

A larger next edition should replace editorial selection with a reproducible chart/scene sampling frame, gather complete album tracklists for equal windows, audit original release dates against reissues, separate guest verses, and quantify sensitivity to artist and genre weighting. The current project retains the data and code needed to make those improvements without rebuilding the interface.
