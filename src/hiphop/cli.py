"""Small, explicit registry of studies and their reproducible entry points."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from importlib import import_module
import json
from pathlib import Path

from hiphop.paths import StudyPaths, repository_root

STUDIES = {'language-of-hip-hop': 'hiphop.analyses.language_of_hiphop'}


def main(argv=None):
    parser = argparse.ArgumentParser(prog='hiphop', description='Hip-hop analysis hub')
    parser.add_argument('--root', type=Path, help='Repository root (auto-detected by default)')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('list', help='List available studies')
    run = commands.add_parser('run', help='Rebuild a study from local sources')
    run.add_argument('study', choices=STUDIES)
    run.add_argument('--allow-partial', action='store_true')
    fetch = commands.add_parser('fetch', help='Acquire or verify local source snapshots')
    fetch.add_argument('source', choices=['historical', 'recent'])
    fetch.add_argument('--study', choices=STUDIES, default='language-of-hip-hop')
    fetch.add_argument('--workers', type=int, default=3)
    fetch.add_argument('--start', type=int, default=0, help='Historical shard offset')
    fetch.add_argument('--limit-artists', type=int, help='Recent collection preview limit')
    cohort = commands.add_parser('cohort', help='Reset a study config to its original editorial cohort')
    cohort.add_argument('study', choices=STUDIES)
    serve = commands.add_parser('serve', help='Serve the hub and aggregate exports only')
    serve.add_argument('--port', type=int, default=8765)
    args = parser.parse_args(argv)
    root = args.root.resolve() if args.root else repository_root()
    if args.command == 'list':
        for slug in STUDIES:
            print(f'{slug}\tanalyses/{slug}/README.md')
    elif args.command == 'run':
        import_module(STUDIES[args.study] + '.pipeline').run(root, args.allow_partial)
    elif args.command == 'cohort':
        import_module(STUDIES[args.study] + '.cohort').build_config(root)
    elif args.command == 'fetch':
        if args.workers < 1 or args.start < 0 or (args.limit_artists is not None and args.limit_artists < 1):
            parser.error('workers and limit-artists must be positive; start must be nonnegative')
        paths = StudyPaths(root, args.study)
        if args.source == 'historical':
            from hiphop.sources.huggingface import download_snapshot
            download_snapshot(paths.source, paths.historical, args.workers, args.start)
        else:
            from hiphop.sources.genius import collect_snapshot
            config = json.loads(paths.config.read_text())
            cutoff = config['as_of']
            collect_snapshot(config, paths.recent(cutoff), paths.genius_cache(cutoff),
                             args.workers, args.limit_artists)
    elif args.command == 'serve':
        handler = partial(SimpleHTTPRequestHandler, directory=str(root / 'web'))
        with ThreadingHTTPServer(('127.0.0.1', args.port), handler) as server:
            print(f'Hip-hop analysis hub: http://127.0.0.1:{args.port}/', flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
