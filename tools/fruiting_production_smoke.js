// Live production startup and GIS manifest compatibility smoke test.
// National GIS validation remains a separate, explicit operator task.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('fs');

const APP = (process.env.FF_PROD_URL || 'https://fruitingforecast.com').replace(/\/+$/, '');
const EXPECTED_COMMIT = process.env.FF_EXPECTED_COMMIT || '';
const GIS = 'https://data.hanksjunkdrawer.com/';
const report = { app: APP, generatedAt: new Date().toISOString(), checks: {} };

(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const page = await context.newPage();
    const pageErrors = [];
    const consoleErrors = [];
    page.on('pageerror', error => pageErrors.push(String(error)));
    page.on('console', message => {
      if (message.type() === 'error' && !message.text().includes('Failed to load resource')) consoleErrors.push(message.text());
    });
    // Production analytics must never receive CI or operator smoke traffic.
    await page.route('https://analytics.aismallbizguru.com/**', route =>
      route.fulfill({ status: 200, contentType: 'application/javascript', body: '' }));

    const deploymentResponse = await context.request.get(APP + '/deployment.json');
    assert.equal(deploymentResponse.status(), 200);
    const deployment = await deploymentResponse.json();
    if (EXPECTED_COMMIT) assert.equal(deployment.commit, EXPECTED_COMMIT);
    report.checks.release = {
      commit: deployment.commit, appVersion: deployment.appVersion, datasetVersion: deployment.datasetVersion
    };

    const response = await page.goto(APP + '/', { waitUntil: 'domcontentloaded', timeout: 90000 });
    assert.equal(response.status(), 200);
    await page.waitForFunction(() => window.__FRUITING_FORECAST_TEST__, null, { timeout: 90000 });
    await page.waitForFunction(() => document.querySelector('[data-deploy-version]'), null, { timeout: 30000 });

    const seo = await page.evaluate(() => ({
      title: document.title,
      canonical: (document.querySelector('link[rel="canonical"]') || {}).href,
      ogUrl: (document.querySelector('meta[property="og:url"]') || {}).content,
      version: document.querySelector('[data-deploy-version]').dataset.deployVersion,
      jsonLd: Array.from(document.querySelectorAll('script[type="application/ld+json"]')).map(node => JSON.parse(node.textContent))
    }));
    assert.equal(seo.canonical, APP + '/');
    assert.equal(seo.ogUrl, APP + '/');
    assert.equal(seo.version, deployment.appVersion);
    assert.match(seo.title, /Fruiting Forecast/);
    assert.ok(seo.jsonLd.some(item => item['@type'] === 'WebApplication' && item.url === APP + '/'));
    report.checks.homepage = { title: seo.title, canonical: seo.canonical, version: seo.version };

    const manifest = await page.evaluate(() => __FRUITING_FORECAST_TEST__.gisManifest(false));
    assert.equal(manifest.datasetVersion, deployment.datasetVersion);
    assert.equal(manifest.assetBaseUrl, GIS);
    assert.ok(Array.isArray(manifest.tiles));
    assert.equal(manifest.tiles.length, 922);
    await page.evaluate(value => { window.__FRUITING_FORECAST_TEST__.getState().gis.manifest = value; }, manifest);

    const habitats = manifest.tiles.map(tile => tile.habitat).filter(Boolean).sort((a, b) => a.bytes - b.bytes);
    assert.ok(habitats.length);
    const asset = habitats[0];
    const bytes = await page.evaluate(async item => {
      const payload = await window.__FRUITING_FORECAST_CACHE_TEST__.gisAssetBytes('production-smoke', item, false);
      return new Uint8Array(payload).length;
    }, asset);
    assert.equal(bytes, asset.bytes);
    report.checks.gis = {
      datasetVersion: manifest.datasetVersion, tiles: manifest.tiles.length, asset: asset.url, bytes
    };

    const startup = await page.evaluate(() => ({
      model: document.getElementById('modelVersion').textContent,
      analyze: typeof window.__FRUITING_FORECAST_TEST__.analyze
    }));
    assert.match(startup.model, /FF-1\.7\.0/);
    assert.equal(startup.analyze, 'function');
    assert.deepEqual(pageErrors, []);
    assert.deepEqual(consoleErrors, []);
    report.checks.startup = { model: startup.model, consoleErrors: consoleErrors.length, pageErrors: pageErrors.length };
    report.verdict = 'PASS';
  } finally {
    await browser.close();
    fs.writeFileSync(process.argv[2] || '/tmp/ff-production-smoke.json', JSON.stringify(report, null, 2) + '\n');
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
