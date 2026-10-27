"""Release contract for the authoritative GitHub Actions Pages deployment.

These tests are intentionally dependency-light: staging, the published artifact,
SEO discovery files and the workflow gates are validated without GIS hydration or
any Cloudflare mutation.
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

from stage_pages import stage  # noqa: E402

CONFIG = json.loads((ROOT / 'config/pages-runtime.json').read_text())
WORKFLOW_PATH = ROOT / '.github/workflows/production.yml'
RUNTIME_FILES = {
    'index.html',
    'robots.txt',
    'sitemap.xml',
    'data/ecoregions.js',
    'data/states.js',
    'data/manifest.json',
    'data/public-land-rules.json',
    'data/tile-catalog.json',
}


def load_workflow():
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text())
    # PyYAML resolves the unquoted YAML 1.1 key ``on`` as a boolean.
    return workflow.get('on', workflow.get(True)), workflow


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], text=True).strip()


def test_runtime_allowlist_is_explicit_and_contains_seo_discovery_files():
    assert set(CONFIG['files']) == RUNTIME_FILES
    assert CONFIG['canonicalOrigin'] == 'https://fruitingforecast.com'
    assert CONFIG['project'] == 'fruitingforecast'
    assert CONFIG['productionBranch'] == 'main'


def test_seo_discovery_files_point_only_at_the_canonical_origin():
    robots = (ROOT / 'robots.txt').read_text()
    assert 'User-agent: *' in robots
    assert 'Allow: /' in robots
    assert 'Sitemap: https://fruitingforecast.com/sitemap.xml' in robots
    sitemap = ElementTree.fromstring((ROOT / 'sitemap.xml').read_text())
    namespace = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    locations = [node.text for node in sitemap.findall('s:url/s:loc', namespace)]
    assert locations == ['https://fruitingforecast.com/']
    assert sitemap.tag.endswith('urlset')


def test_homepage_exposes_canonical_open_graph_and_webapplication_metadata():
    html = (ROOT / 'index.html').read_text()
    assert '<link rel="canonical" href="https://fruitingforecast.com/" />' in html
    assert '<meta property="og:url" content="https://fruitingforecast.com/" />' in html
    assert '<meta property="og:title"' in html
    assert '<meta property="og:description"' in html
    assert '<meta name="description"' in html
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    applications = [json.loads(block) for block in blocks]
    applications = [item for item in applications if item.get('@type') == 'WebApplication']
    assert len(applications) == 1
    application = applications[0]
    assert application['@context'] == 'https://schema.org'
    assert application['name'] == 'Fruiting Forecast'
    assert application['url'] == 'https://fruitingforecast.com/'
    assert application['applicationCategory'] == 'LifestyleApplication'
    assert application['operatingSystem'] == 'Web'
    assert 'not a guarantee' in application['description']


def test_staged_artifact_is_minimal_seo_complete_and_commit_traceable():
    info = stage()
    dist = ROOT / 'dist'
    published = {
        str(path.relative_to(dist))
        for path in dist.rglob('*')
        if path.is_file()
    }
    assert published == RUNTIME_FILES | {'_headers', '404.html', 'deployment.json'}
    assert info['commit'] == git('rev-parse', 'HEAD')
    assert info['scoringModel'] == 'FF-1.7.0'
    assert info['datasetVersion'] == 'content-db0f839a4352ef82'
    footer = re.search(r'data-deploy-version="([^"]+)"', (ROOT / 'index.html').read_text())[1]
    assert info['appVersion'] == footer
    for entry in info['files']:
        staged = dist / entry['path']
        assert staged.stat().st_size == entry['bytes']
        assert hashlib.sha256(staged.read_bytes()).hexdigest() == entry['sha256']
    assert (dist / 'robots.txt').read_bytes() == (ROOT / 'robots.txt').read_bytes()
    assert (dist / 'sitemap.xml').read_bytes() == (ROOT / 'sitemap.xml').read_bytes()
    headers = (dist / '_headers').read_text()
    assert 'Cache-Control: public, no-transform, max-age=0, must-revalidate' in headers
    assert 'X-Content-Type-Options: nosniff' in headers


@pytest.mark.parametrize('name', [
    'tests',
    'tools',
    'docs',
    'config',
    'data/production',
    '.git',
    '.github',
    '.env',
    'node_modules',
    'deployment.json.bak',
])
def test_staged_artifact_excludes_source_only_material(name):
    dist = ROOT / 'dist'
    if not (dist / 'deployment.json').is_file():
        stage()
    assert not (dist / name).exists()
    for path in dist.rglob('*'):
        assert path.suffix not in {'.py', '.md', '.parquet', '.pbf', '.tif', '.sqlite'}
        assert path.name not in {'.env', '.gitignore'}


def test_workflow_validates_every_change_and_deploys_only_main_pushes():
    triggers, workflow = load_workflow()
    assert triggers['push']['branches'] == ['main']
    assert triggers['pull_request']['branches'] == ['main']
    jobs = workflow['jobs']
    assert 'validate' in jobs and 'deploy' in jobs
    deploy = jobs['deploy']
    assert deploy['needs'] == 'validate'
    condition = ' '.join(str(part) for part in (
        deploy['if'] if isinstance(deploy['if'], list) else [deploy['if']]
    ))
    assert "github.event_name == 'push'" in condition
    assert "github.ref == 'refs/heads/main'" in condition
    assert workflow['permissions'] == {'contents': 'read'}
    assert workflow['concurrency']['cancel-in-progress'] is False


def test_workflow_uses_pinned_actions_scoped_credentials_and_the_existing_project():
    _, workflow = load_workflow()
    uses = []

    def collect(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == 'uses':
                    uses.append(value)
                else:
                    collect(value)
        elif isinstance(node, list):
            for item in node:
                collect(item)

    collect(workflow)
    assert uses
    for reference in uses:
        assert re.fullmatch(r'[^@]+@[0-9a-f]{40}', reference), reference
    validate = workflow['jobs']['validate']['steps']
    deploy_job = workflow['jobs']['deploy']
    deploy = deploy_job['steps']
    stages = next(step for step in validate if step.get('name') == 'Stage minimal Pages artifact')
    assert 'tools/stage_pages.py' in stages['run']
    credential_step = next(step for step in deploy if step.get('name') == 'Require deployment credentials')
    assert 'secrets.CLOUDFLARE_API_TOKEN' in json.dumps(deploy_job['env'])
    assert 'secrets.CLOUDFLARE_ACCOUNT_ID' in json.dumps(deploy_job['env'])
    assert '-z "${CLOUDFLARE_API_TOKEN}"' in credential_step['run']
    assert '-z "${CLOUDFLARE_ACCOUNT_ID}"' in credential_step['run']
    assert 'exit 1' in credential_step['run']
    publish = next(step for step in deploy if step.get('name') == 'Publish to Cloudflare Pages')
    command = publish['run']
    assert 'wrangler@${WRANGLER_VERSION}' in command
    assert '--project-name fruitingforecast' in command
    assert '--branch main' in command
    assert '--commit-hash "$GITHUB_SHA"' in command
    assert '--commit-dirty=false' in command
    assert workflow['env']['WRANGLER_VERSION'] == '4.135.0'
    text = WORKFLOW_PATH.read_text().lower()
    for forbidden in ('wrangler r2', 'rclone', 'aws s3', 'build-fruiting-gis', 'fruiting_tile_publish', 'dns', 'zone'):
        assert forbidden not in text


def test_workflow_runs_application_smoke_tests_and_post_deployment_verification():
    _, workflow = load_workflow()
    validate_runs = '\n'.join(step.get('run', '') for step in workflow['jobs']['validate']['steps'])
    assert 'npm ci' in validate_runs
    assert 'tests/fruiting-forecast.spec.js' in validate_runs
    assert 'tests/fruiting-forecast-hosting.spec.js' in validate_runs
    assert 'tests/fruiting-forecast-analytics.spec.js' in validate_runs
    deploy_runs = '\n'.join(step.get('run', '') for step in workflow['jobs']['deploy']['steps'])
    assert 'tools/verify_pages_production.py' in deploy_runs
    assert '--expected-commit "$GITHUB_SHA"' in deploy_runs
    assert 'tools/fruiting_production_smoke.js' in deploy_runs
    # National GIS validation stays an explicit, separate operator action.
    assert 'fruiting_domain_qa' not in deploy_runs
