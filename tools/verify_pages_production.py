#!/usr/bin/env python3
"""Read-only verification of the published Fruiting Forecast Pages release.

Checks release traceability, canonical routing, SEO metadata, discovery files,
response headers, and GIS manifest/object compatibility. It never mutates
Cloudflare, R2, DNS or application data.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from http.client import HTTPSConnection
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / 'config/pages-runtime.json').read_text())
MANIFEST = json.loads((ROOT / 'data/manifest.json').read_text())
APP_VERSION = re.search(r'data-deploy-version="([^"]+)"', (ROOT / 'index.html').read_text())[1]
USER_AGENT = 'FruitingForecast-DeployVerifier/1.0 (+https://fruitingforecast.com/)'


class VerificationError(RuntimeError):
    pass


def expect(condition, message):
    if not condition:
        raise VerificationError(message)


def fetch(url, headers=None):
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return response.status, {key.lower(): value for key, value in response.headers.items()}, response.read()
    except urllib.error.HTTPError as error:
        return error.code, {key.lower(): value for key, value in error.headers.items()}, error.read()


def attributes(tag):
    return {key: value for key, value in re.findall(r'([\w:-]+)="([^"]*)"', tag)}


def verify(base, expected_commit, www_url):
    base = base.rstrip('/')
    checks = {}
    failures = []

    def check(name, function):
        try:
            checks[name] = {'passed': True, **(function() or {})}
        except Exception as error:  # noqa: BLE001 - report every verification failure
            checks[name] = {'passed': False, 'error': str(error)}
            failures.append('%s: %s' % (name, error))

    def release_identity():
        status, headers, body = fetch(base + '/deployment.json')
        expect(status == 200, 'deployment.json returned HTTP %s' % status)
        deployment = json.loads(body)
        expect(deployment['commit'] == expected_commit,
               'deployed commit %s != expected %s' % (deployment['commit'], expected_commit))
        expect(deployment['appVersion'] == APP_VERSION,
               'appVersion %s != source %s' % (deployment['appVersion'], APP_VERSION))
        expect(deployment['scoringModel'] == 'FF-1.7.0', 'unexpected scoring model')
        expect(deployment['datasetVersion'] == MANIFEST['datasetVersion'], 'dataset version drift')
        published = {entry['path'] for entry in deployment['files']}
        expect(published == set(CONFIG['files']),
               'artifact allowlist drift: %s' % sorted(published.symmetric_difference(CONFIG['files'])))
        return {'commit': deployment['commit'], 'appVersion': deployment['appVersion'],
                'datasetVersion': deployment['datasetVersion'], 'files': len(published)}

    def homepage():
        status, headers, body = fetch(base + '/')
        expect(status == 200, 'homepage returned HTTP %s' % status)
        html = body.decode('utf-8')
        links = [attributes(tag) for tag in re.findall(r'<link\b[^>]*>', html)]
        metas = [attributes(tag) for tag in re.findall(r'<meta\b[^>]*>', html)]
        canonical = [link.get('href') for link in links if link.get('rel') == 'canonical']
        expect(canonical == [base + '/'], 'canonical link is %s' % canonical)
        by_property = {meta.get('property'): meta.get('content') for meta in metas if meta.get('property')}
        by_name = {meta.get('name'): meta.get('content') for meta in metas if meta.get('name')}
        expect(by_property.get('og:url') == base + '/', 'og:url mismatch')
        expect(by_property.get('og:title'), 'missing og:title')
        expect(by_property.get('og:description'), 'missing og:description')
        expect(by_property.get('og:site_name') == 'Fruiting Forecast', 'og:site_name mismatch')
        expect(by_name.get('description'), 'missing meta description')
        expect(by_name.get('viewport'), 'missing viewport meta')
        version = re.search(r'data-deploy-version="([^"]+)"', html)
        expect(version and version[1] == APP_VERSION, 'homepage footer version mismatch')
        blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
        applications = [json.loads(block) for block in blocks]
        applications = [item for item in applications if item.get('@type') == 'WebApplication']
        expect(len(applications) == 1, 'expected one WebApplication JSON-LD block')
        application = applications[0]
        expect(application.get('name') == 'Fruiting Forecast', 'JSON-LD name mismatch')
        expect(application.get('url') == base + '/', 'JSON-LD url mismatch')
        expect(application.get('applicationCategory') == 'LifestyleApplication', 'JSON-LD category mismatch')
        expect(application.get('operatingSystem') == 'Web', 'JSON-LD operating system mismatch')
        expect('not a guarantee' in application.get('description', ''), 'JSON-LD disclaimer mismatch')
        expect('no-transform' in headers.get('cache-control', ''), 'cache-control lacks no-transform')
        expect(headers.get('x-content-type-options') == 'nosniff', 'missing nosniff header')
        expect(headers.get('referrer-policy') == 'strict-origin-when-cross-origin', 'referrer policy mismatch')
        return {'canonical': canonical[0], 'appVersion': version[1], 'jsonLd': 'WebApplication'}

    def discovery_files():
        status, headers, body = fetch(base + '/robots.txt')
        expect(status == 200, 'robots.txt returned HTTP %s' % status)
        expect(headers.get('content-type', '').startswith('text/plain'), 'robots.txt content type')
        robots = body.decode('utf-8')
        expect('User-agent:' in robots, 'robots.txt missing User-agent')
        sitemap_lines = [line.strip() for line in robots.splitlines() if line.strip().lower().startswith('sitemap:')]
        expect('Sitemap: %s/sitemap.xml' % base in sitemap_lines,
               'robots.txt Sitemap lines are %s' % sitemap_lines)
        status, headers, sitemap_body = fetch(base + '/sitemap.xml')
        expect(status == 200, 'sitemap.xml returned HTTP %s' % status)
        expect('xml' in headers.get('content-type', ''), 'sitemap.xml content type')
        sitemap = ElementTree.fromstring(sitemap_body)
        namespace = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        locations = [node.text for node in sitemap.findall('s:url/s:loc', namespace)]
        expect(locations == [base + '/'], 'sitemap locations are %s' % locations)
        digest = hashlib.sha256(sitemap_body).hexdigest()
        expect(digest == hashlib.sha256((ROOT / 'sitemap.xml').read_bytes()).hexdigest(),
               'served sitemap.xml differs from the committed artifact')
        return {'robots': 'canonical sitemap', 'sitemapLocations': locations, 'sitemapSha256': digest}

    def canonical_redirect():
        host = www_url.split('//', 1)[1].split('/', 1)[0]
        path = '/release-check?probe=1'
        connection = HTTPSConnection(host, timeout=30)
        try:
            connection.request('GET', path, headers={'User-Agent': USER_AGENT})
            response = connection.getresponse()
            status = response.status
            location = response.getheader('location')
            response.read()
        finally:
            connection.close()
        expect(status == 301, 'www redirect returned HTTP %s' % status)
        expect(location == base + path, 'www redirect location is %s' % location)
        return {'status': status, 'location': location}

    def gis_compatibility():
        status, headers, body = fetch(base + '/data/manifest.json')
        expect(status == 200, 'manifest returned HTTP %s' % status)
        deployed = json.loads(body)
        expect(deployed.get('schemaVersion') in (1, 2, 3, 4), 'unsupported manifest schema')
        expect(deployed.get('assetBaseUrl') == CONFIG['gisOrigin'],
               'manifest assetBaseUrl is %s' % deployed.get('assetBaseUrl'))
        expect(deployed.get('datasetVersion') == MANIFEST['datasetVersion'], 'manifest dataset version drift')
        expect(len(deployed.get('tiles', [])) == len(MANIFEST['tiles']) == 922,
               'manifest tile count is %s' % len(deployed.get('tiles', [])))
        for key in ('tileCatalog', 'collectingRules'):
            url = 'data/' + deployed[key]['url']
            status, headers, body = fetch(base + '/' + url)
            expect(status == 200, '%s returned HTTP %s' % (url, status))
            expect(isinstance(json.loads(body), dict), '%s is not a JSON object' % url)
        habitat = [tile['habitat'] for tile in deployed['tiles'] if tile.get('habitat')]
        expect(habitat, 'manifest has no habitat assets')
        asset = min(habitat, key=lambda item: item['bytes'])
        object_url = CONFIG['gisOrigin'].rstrip('/') + '/' + asset['url']
        status, headers, body = fetch(object_url, {'Origin': base})
        expect(status == 200, 'GIS object returned HTTP %s' % status)
        expect(len(body) == asset['bytes'], 'GIS object length %s != %s' % (len(body), asset['bytes']))
        expect(hashlib.sha256(body).hexdigest() == asset['sha256'], 'GIS object checksum mismatch')
        allowed = headers.get('access-control-allow-origin')
        expect(allowed in ('*', base), 'GIS CORS origin is %s' % allowed)
        expect('bytes' in headers.get('accept-ranges', ''), 'GIS object missing Accept-Ranges')
        return {'datasetVersion': deployed['datasetVersion'], 'tiles': len(deployed['tiles']),
                'object': asset['url'], 'bytes': len(body), 'cors': allowed}

    check('release_identity', release_identity)
    check('homepage_metadata', homepage)
    check('discovery_files', discovery_files)
    check('www_redirect', canonical_redirect)
    check('gis_compatibility', gis_compatibility)
    return {'app': base, 'expectedCommit': expected_commit, 'checks': checks, 'failures': failures,
            'verdict': 'PASS' if not failures else 'FAIL'}


def default_commit():
    if os.environ.get('GITHUB_SHA'):
        return os.environ['GITHUB_SHA']
    return subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()


def main():
    host = CONFIG['canonicalOrigin'].split('//', 1)[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default=CONFIG['canonicalOrigin'])
    parser.add_argument('--www-url', default='https://www.' + host)
    parser.add_argument('--expected-commit', default=default_commit())
    parser.add_argument('--report')
    args = parser.parse_args()
    report = verify(args.base_url, args.expected_commit, args.www_url)
    output = json.dumps(report, indent=2) + '\n'
    if args.report:
        Path(args.report).write_text(output)
    print(output)
    return 0 if report['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
