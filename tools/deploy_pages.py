#!/usr/bin/env python3
"""Deploy a clean main checkout through Wrangler Direct Upload; no app build."""
import json
import subprocess
from pathlib import Path
from stage_pages import stage
ROOT = Path(__file__).resolve().parents[1]
def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], text=True).strip()
if __name__ == '__main__':
    config = json.loads((ROOT / 'config/pages-runtime.json').read_text())
    if git('branch', '--show-current') != config['productionBranch'] or git('status', '--porcelain'):
        raise SystemExit('Production deployment requires a clean main checkout. Commit and review changes first.')
    info = stage()
    subprocess.run(['npx', 'wrangler@4.135.0', 'pages', 'deploy', str(ROOT / 'dist'), '--project-name', config['project'], '--branch', config['productionBranch'], '--commit-hash', info['commit'], '--commit-dirty=false'], cwd=ROOT, check=True)
