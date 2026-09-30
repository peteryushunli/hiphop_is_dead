# Hip-hop analysis hub

A home for reproducible analyses of hip-hop music, language, and culture. Each study owns its question, sample, methods, and outputs. Shared Python utilities handle source acquisition and lyric normalization.

## Explore

Open [web/index.html](web/index.html) directly—no install or network access needed—or serve the published site:

```sh
python3 -m http.server 8765 --bind 127.0.0.1 --directory web
```

Visit <http://127.0.0.1:8765/>. Only aggregate results are included in the website.

| Study | Question | Methods & results |
| --- | --- | --- |
| [The language of hip-hop](web/analyses/language-of-hip-hop/index.html) | What distinguishes hip-hop vocabulary, and which artists share it? | [Study documentation](analyses/language-of-hip-hop/README.md) · [CSV exports and audit](web/analyses/language-of-hip-hop/exports) |

The first study covers 1990 through September 30, 2026: 62,123 hip-hop songs and 15,704 comparison songs. It extends The Pudding’s original artist roster with contemporary artists; it is a new sample, not a literal superset of the original song corpus.

## Develop and reproduce

Python 3.11+:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
hiphop list
hiphop fetch historical          # ~2.4 GiB; resumes and verifies SHA-256
hiphop fetch recent              # study's bounded Genius supplement, cached locally
hiphop run language-of-hip-hop   # rebuild from local data; no network calls
python -m unittest discover -s tests -v
hiphop serve                    # serves web/ at http://127.0.0.1:8765/
```

`python -m hiphop` is equivalent to `hiphop`. Use `hiphop --root /path/to/hiphop_is_dead …` from another directory. The existing `scripts/` commands remain compatibility entry points. A fresh clone can view all results and run unit tests without downloading lyrics. Full rebuilds require local sources; live source availability may change.

## Repository layout

```text
analyses/<study>/                 Study README, cohort config, reference inputs
src/hiphop/analyses/<study>/      Study-specific pipeline and cohort builder
src/hiphop/sources/               Reusable, cached acquisition tools
src/hiphop/text.py                Shared text normalization
src/hiphop/cli.py                 Study registry and command-line entry point
data/sources/                    Committed source revisions and file hashes
data/raw/                        Local source snapshots (ignored)
data/cache/                      Local response caches (ignored)
data/processed/<study>/          Local intermediate data (ignored)
web/                             Static collection homepage
web/analyses/<study>/             Explorer, generated data.js, aggregate exports
tests/                           Offline checks and analysis fixtures
docs/                            Data conventions and guide to adding studies
```

Read [the data guide](docs/data.md) for what is downloaded locally and what belongs in Git. Follow [Adding an analysis](docs/adding-an-analysis.md) to extend the collection. CI runs offline tests and JavaScript syntax checks; large source downloads and full corpus rebuilds remain explicit local commands.
