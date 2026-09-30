"""Repository layout, with study outputs isolated from reusable source snapshots."""
from dataclasses import dataclass
from pathlib import Path


def repository_root():
    for candidate in [Path.cwd(), *Path.cwd().parents, Path(__file__).resolve().parents[2]]:
        if (candidate / 'pyproject.toml').exists() and (candidate / 'analyses').is_dir():
            return candidate
    raise ValueError('Run inside the repository or pass --root /path/to/hiphop_is_dead.')


@dataclass(frozen=True)
class StudyPaths:
    root: Path
    slug: str

    @property
    def study(self):
        return self.root / 'analyses' / self.slug

    @property
    def config(self):
        return self.study / 'config.json'

    @property
    def references(self):
        return self.study / 'references'

    @property
    def web(self):
        return self.root / 'web/analyses' / self.slug

    @property
    def exports(self):
        return self.web / 'exports'

    @property
    def processed(self):
        return self.root / 'data/processed' / self.slug

    @property
    def source(self):
        return self.root / 'data/sources/genius-lyrics-cleaned'

    @property
    def historical(self):
        return self.root / 'data/raw/genius-lyrics-cleaned'

    def recent(self, cutoff):
        return self.root / 'data/raw/genius' / cutoff

    def genius_cache(self, cutoff):
        return self.root / 'data/cache/genius' / cutoff
