"""Download an immutable corpus snapshot, verifying upstream SHA-256 hashes."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import time

import requests


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def download_snapshot(source, target, workers=3, start=0):
    info = json.loads((source / 'source-info.json').read_text())
    files = json.loads((source / 'source-files.json').read_text())
    target.mkdir(parents=True, exist_ok=True)

    def download(item):
        path = target / Path(item['path']).name
        expected = item['lfs']['oid']
        if path.exists() and path.stat().st_size == item['size'] and digest(path) == expected:
            print(f'Verified {path.name}', flush=True)
            return
        url = f"https://huggingface.co/datasets/{info['id']}/resolve/{info['sha']}/{item['path']}"
        part = path.with_suffix('.part')
        for attempt in range(4):
            try:
                offset = part.stat().st_size if part.exists() else 0
                with requests.get(url, headers={'Range': f'bytes={offset}-'} if offset else {},
                                  stream=True, timeout=(30, 120)) as response:
                    response.raise_for_status()
                    mode = 'ab' if offset and response.status_code == 206 else 'wb'
                    with part.open(mode) as out:
                        for chunk in response.iter_content(1024 * 1024):
                            out.write(chunk)
                if part.stat().st_size != item['size'] or digest(part) != expected:
                    part.unlink(missing_ok=True)
                    raise ValueError(f'Integrity check failed: {path.name}')
                part.replace(path)
                print(f'Downloaded and verified {path.name}', flush=True)
                return
            except (requests.RequestException, ValueError) as exc:
                if attempt == 3:
                    raise
                print(f'Retrying {path.name}: {type(exc).__name__}', flush=True)
                time.sleep(2 ** attempt)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(download, files[start:]))
