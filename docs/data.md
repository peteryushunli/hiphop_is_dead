# Data storage and provenance

The initial collection is downloaded locally in full. The historical archive is about 2.4 GiB; recent lyric snapshots and cached Genius responses bring local source storage to roughly 3 GiB. A Git clone includes source manifests, study configurations, reference rosters, and derived results, **not** those raw downloads.

| Location | Contents | In Git? |
| --- | --- | --- |
| `data/sources/genius-lyrics-cleaned/` | Pinned upstream revision and SHA-256 file manifest | Yes |
| `data/raw/genius-lyrics-cleaned/` | All ten historical Parquet shards, 3,179,588 upstream rows | No |
| `data/raw/genius/2026-09-30/` | 68 artist collection snapshots, including full recent lyrics and source URLs | No |
| `data/cache/genius/2026-09-30/` | Cached Genius JSON and HTML responses | No |
| `data/processed/language-of-hip-hop/song_index.parquet` | Retained song metadata, provenance, token counts, fingerprints | No |
| `analyses/language-of-hip-hop/references/` | Original published rosters and reviewed exclusions | Yes |
| `web/analyses/language-of-hip-hop/` | Explorer, aggregate statistics, CSV exports, collection audit | Yes |

The 3.18 million source rows are broader than the study. The study retains 77,827 songs after cohort selection, date and content filters, and deduplication. “All downloaded” means the selected archive and bounded recent supplement are local; it does not mean all hip-hop music is covered.

## Reuse and refresh

Historical sources are shared across studies, pinned by revision, and verified on acquisition. `hiphop fetch historical` also verifies already downloaded files. Study-specific intermediate products go under `data/processed/<study>/` so one pipeline cannot overwrite another’s results.

Genius snapshots and URL caches are separated by cutoff date. Updating a study’s `as_of` value uses a new snapshot and cache directory. Successful artist snapshots are skipped for the same cutoff. If collection settings change while keeping the cutoff, explicitly archive the old snapshot and cache before recollecting; the collector does not automatically detect configuration changes. An API or page may change or disappear, so preserve local snapshots when reproducibility matters. Downloads are not silently refreshed during analysis.

Keep full lyrics, downloaded source pages, credentials, and large intermediates out of commits. Review `git status` before publishing. Aggregate exports are versioned so a reader can use the site immediately. The source card’s license label does not grant this project rights to the underlying songs.

## Existing workspace migration

The hub refactor preserves the original downloaded bytes, with these path changes:

- `data/raw/train-*.parquet` → `data/raw/genius-lyrics-cleaned/`
- `data/raw/recent/` → `data/raw/genius/2026-09-30/`
- `data/cache/genius/*.{html,json}` → `data/cache/genius/2026-09-30/`
- `data/processed/song_index.parquet` → `data/processed/language-of-hip-hop/song_index.parquet`
- `reports/` → `web/analyses/language-of-hip-hop/exports/`

No source download is required again in the original workspace.
