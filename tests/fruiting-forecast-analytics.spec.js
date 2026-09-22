const { test, expect } = require('@playwright/test');
require('./fruiting-local-manifest.cjs')(test);
const path = require('path');

const url = `file://${path.resolve(process.cwd(), 'index.html')}`;
test.use({ channel: 'chrome', viewport: { width: 1280, height: 850 } });

const EVENT_NAMES = ['forecast_run', 'species_selected', 'result_opened', 'map_interaction', 'outbound_resource'];
const ALLOWED_KEYS = ['profile', 'focus', 'depth', 'radius', 'results', 'gis', 'species', 'source', 'kind', 'rank', 'actionability', 'action', 'value', 'enabled', 'host', 'surface'];

function weatherPayload(lat = 39.1653, lon = -86.5264) {
  const now = new Date();
  const day = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const dates = [];
  for (let i = -30; i <= 7; i++) dates.push(new Date(day.getTime() + i * 86400000).toISOString().slice(0, 10));
  const hours = [];
  for (let i = -30 * 24; i <= 7 * 24; i++) hours.push(new Date(day.getTime() + i * 3600000).toISOString().slice(0, 13) + ':00');
  return {
    latitude: lat, longitude: lon, elevation: 235, timezone: 'America/Indiana/Indianapolis',
    daily: {
      time: dates, precipitation_sum: dates.map((_, i) => i > 20 && i < 29 ? 0.18 : (i === 29 ? 0.65 : 0)),
      temperature_2m_max: dates.map(() => 78), temperature_2m_min: dates.map(() => 60),
      et0_fao_evapotranspiration: dates.map(() => 0.12)
    },
    hourly: {
      time: hours, temperature_2m: hours.map(() => 69), relative_humidity_2m: hours.map(() => 78),
      dew_point_2m: hours.map(() => 62), precipitation: hours.map(() => 0),
      soil_temperature_0cm: hours.map(() => 66), soil_moisture_0_to_1cm: hours.map(() => 0.29),
      vapour_pressure_deficit: hours.map(() => 0.65), wind_speed_10m: hours.map(() => 5)
    }
  };
}

async function setup(page, { track } = {}) {
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => { if (m.type() === 'error' && !m.text().includes('ERR_FAILED') && !m.text().includes('Failed to load resource')) errors.push(m.text()); });
  await page.addInitScript(stub => {
    window.__FF_TEST_FAST__ = true;
    window.__FF_ANALYTICS__ = [];
    window.cflabAnalytics = {
      track: (name, props) => {
        window.__FF_ANALYTICS__.push({ name, props: props === undefined ? null : props });
        if (stub && stub.throwing) throw new Error('analytics unavailable');
      }
    };
  }, { throwing: !!(track && track.throwing) });
  await page.route('https://unpkg.com/**', r => r.abort());
  await page.route('https://tile.openstreetmap.org/**', r => r.abort());
  await page.route('https://api.open-meteo.com/v1/forecast**', async route => {
    const requestUrl = new URL(route.request().url());
    const lats = requestUrl.searchParams.get('latitude').split(',').map(Number);
    const lons = requestUrl.searchParams.get('longitude').split(',').map(Number);
    const body = lats.map((lat, i) => weatherPayload(lat, lons[i]));
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body.length === 1 ? body[0] : body) });
  });
  await page.route('https://api.inaturalist.org/v1/observations**', route => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ total_results: 6, results: [{ observed_on: new Date().toISOString().slice(0, 10) }] })
  }));
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => window.__FRUITING_FORECAST_TEST__);
  return errors;
}

async function runAnalysis(page) {
  await page.locator('#locationInput').fill('39.1653, -86.5264');
  await page.getByRole('button', { name: 'Run field analysis' }).click();
  await expect(page.locator('#results')).toBeVisible();
  await expect(page.locator('#status')).toContainText('Analysis ready');
}

async function events(page) {
  return page.evaluate(() => window.__FF_ANALYTICS__ || []);
}

test('product events carry only coarse allowlisted properties and never coordinates', async ({ page }) => {
  const errors = await setup(page);
  await runAnalysis(page);

  await page.selectOption('#focusSelect', 'specific');
  await page.selectOption('#speciesSelect', 'maitake');
  await page.locator('[data-select]').nth(1).click();
  await expect(page.locator('[data-zone-fallback]').first()).toBeVisible();
  await page.locator('[data-zone-fallback]').first().click();
  await page.selectOption('#mapLayer', 'forest');
  await page.uncheck('#showPublicLands');
  await page.evaluate(() => document.querySelector('.source-links a[href="https://open-meteo.com/"]').click());

  const captured = await events(page);
  const names = captured.map(e => e.name);
  expect(names).toContain('forecast_run');
  expect(names).toContain('species_selected');
  expect(names).toContain('result_opened');
  expect(names).toContain('map_interaction');
  expect(names).toContain('outbound_resource');
  expect(names.every(name => EVENT_NAMES.includes(name))).toBe(true);

  const forecast = captured.find(e => e.name === 'forecast_run');
  expect(forecast.props).toMatchObject({ profile: 'appalachians', focus: 'best', depth: 'standard', radius: 25, results: '4-7', gis: 'basic' });
  expect(captured.find(e => e.name === 'species_selected' && e.props.source === 'selector').props).toEqual({ species: 'maitake', source: 'selector' });
  expect(captured.find(e => e.name === 'species_selected' && e.props.source === 'ranking')).toBeTruthy();
  const opened = captured.find(e => e.name === 'result_opened');
  expect(opened.props).toMatchObject({ kind: 'sector', rank: 1 });
  expect(captured.find(e => e.name === 'map_interaction' && e.props.action === 'layer').props).toEqual({ action: 'layer', value: 'forest' });
  expect(captured.find(e => e.name === 'map_interaction' && e.props.action === 'overlay').props).toEqual({ action: 'overlay', value: 'public_lands', enabled: false });
  expect(captured.find(e => e.name === 'outbound_resource').props).toEqual({ host: 'open-meteo.com', surface: 'sources' });

  const serialized = JSON.stringify(captured);
  expect(serialized).not.toContain('39.1653');
  expect(serialized).not.toContain('86.5264');
  expect(serialized).not.toMatch(/-?\d{1,3}\.\d{3,}/);
  for (const entry of captured) {
    expect(Object.keys(entry.props || {}).every(key => ALLOWED_KEYS.includes(key))).toBe(true);
    expect(Object.keys(entry.props || {}).length).toBeLessThanOrEqual(10);
    for (const value of Object.values(entry.props || {})) expect(['string', 'number', 'boolean']).toContain(typeof value);
  }
  expect(errors).toEqual([]);
});

test('analytics helpers drop unknown and location-shaped properties', async ({ page }) => {
  await setup(page);
  const clean = await page.evaluate(() => window.__FRUITING_FORECAST_TEST__.analyticsCleanProps({
    species: 'morel', radius: 25, rank: 3, enabled: true, host: 'www.openstreetmap.org',
    lat: 39.1653, lon: -86.5264, latitude: 39.1653, longitude: -86.5264, location: '39.1653, -86.5264',
    query: 'morels near Bloomington', prompt: 'interpret this', apiKey: 'secret', geometry: { type: 'Point' },
    results: 'not-a-bucket', surface: 'elsewhere'
  }));
  expect(clean).toEqual({ species: 'morel', radius: 25, rank: 3, enabled: true, host: 'www.openstreetmap.org' });
  const dropped = await page.evaluate(() => window.__FRUITING_FORECAST_TEST__.analyticsCleanProps({ lat: 39.1653, lon: -86.5264 }));
  expect(dropped).toBeNull();
});

test('analytics failure never blocks the forecast workflow', async ({ page }) => {
  const errors = await setup(page, { track: { throwing: true } });
  await runAnalysis(page);
  await expect(page.locator('.rank-card').first()).toBeVisible();
  await page.selectOption('#focusSelect', 'specific');
  await expect(page.locator('#status')).toContainText('Analysis ready');
  expect(errors).toEqual([]);
});