# Adding an analysis

Use a short hyphenated slug for files and URLs, such as `album-lengths`. Python module names use underscores: `album_lengths`.

1. Create `analyses/album-lengths/README.md` with the question, source provenance, sampling rules, methods, reproduction command, and interpretation limits. Put the editable study configuration in `config.json` and small reference inputs in `references/`.
2. Create `src/hiphop/analyses/album_lengths/` with `__init__.py` and a `pipeline.py` exposing `run(root, allow_partial=False)`. Add its module prefix to `STUDIES` in `src/hiphop/cli.py`. The optional `cohort.py` entry point applies only to studies that can regenerate an editorial cohort.
3. Reuse `hiphop.sources` and `hiphop.text` where their behavior suits the study. Keep study-specific cleaning decisions and statistics inside the study module. Add a source tool only when it has a reusable acquisition responsibility; pin its manifests under `data/sources/` and keep downloads under `data/raw/`.
4. Use `StudyPaths(root, 'album-lengths')` for study configuration, reference inputs, processed outputs, and site paths. Its historical/Genius helpers belong to the initial corpus; use explicit source paths for a different dataset. Write intermediates only under `data/processed/album-lengths/` and aggregate exports under `web/analyses/album-lengths/exports/`.
5. Add a standalone explorer or results page under `web/analyses/album-lengths/`. Use relative asset links so the whole `web/` directory can be served anywhere or opened locally. Link back to `../../` and add a study card to `web/index.html` and an entry to the root README.
6. Add small, synthetic offline fixtures under `tests/`. Test substantive calculations and edge cases, without fetching sources or committing lyric text. Include an audit of coverage, exclusions, source revisions, configuration, and software versions in the generated results.
7. Run `python -m unittest discover -s tests -v`, rebuild the study from its local inputs, and inspect its page and exports. For a refactor, compare semantic results before and after; timestamps may change but numbers should not.

There is no shared analysis formula or mandatory visualization framework. New studies can ask different questions without inheriting the vocabulary study’s cohort, title exclusions, or statistical assumptions.
