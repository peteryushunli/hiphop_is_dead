"""Compatibility entry point; prefer the hiphop CLI."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hiphop.cli import main

if __name__ == "__main__":
    main(['cohort', 'language-of-hip-hop'] + sys.argv[1:])
