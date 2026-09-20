#!/usr/bin/env python3
"""Generate the minimal static Pages payload. Never builds or publishes GIS."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'config/pages-runtime.json'

def stage(root=ROOT):
    config = json.loads((root / 'config/pages-runtime.json').read_text())
    html = (root / 'index.html').read_text()
    manifest = json.loads((root / 'data/manifest.json').read_text())
    assert manifest['assetBaseUrl'] == config['gisOrigin']
    assert manifest['datasetVersion'] == 'content-db0f839a4352ef82'
    assert len(manifest['tiles']) == 922
    allowed = set(config['files'])
    class Links(HTMLParser):
        def handle_starttag(self, tag, attrs):
            for key, value in attrs:
                if key not in ('src', 'href') or not value or value.startswith(('#', 'http:', 'https:', 'data:')):
                    continue
                assert value.split('?')[0] in allowed, 'Unstaged local HTML resource: ' + value
    Links().feed(html)
    for key in ('collectingRules', 'tileCatalog'):
        assert 'data/' + manifest[key]['url'] in allowed
    out = root / 'dist'
    # Only replace a directory bearing our marker; never erase an arbitrary path.
    if out.exists():
        assert not out.is_symlink() and (out / 'deployment.json').is_file(), 'Unrecognized dist directory'
        shutil.rmtree(out)
    out.mkdir()
    files = []
    for name in sorted(allowed):
        source = root / name
        assert source.is_file() and not source.is_symlink()
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        files.append({'path': name, 'bytes': target.stat().st_size, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
    shutil.copyfile(root / 'config/pages-headers', out / '_headers')
    (out / '404.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Page not found — Fruiting Forecast</title><h1>Page not found</h1><p><a href="/">Return to Fruiting Forecast</a></p></html>\n')
    commit = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    info = {'commit': commit, 'appVersion': re.search(r'data-deploy-version="([^"]+)"', html)[1], 'scoringModel': 'FF-1.7.0', 'datasetVersion': manifest['datasetVersion'], 'files': files}
    (out / 'deployment.json').write_text(json.dumps(info, indent=2) + '\n')
    print(json.dumps({'directory': str(out), 'commit': commit, 'runtimeFiles': len(files), 'bytes': sum(x['bytes'] for x in files)}, indent=2))
    return info

if __name__ == '__main__':
    stage()
