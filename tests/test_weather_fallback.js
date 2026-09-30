// Run: node --test tests/test_weather_fallback.js
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const pages = [
  'tools/unified_orchard_map.html',
  'research_data/five_province_history/UNIFIED_MAP.html',
];
const province = { province_code: '86', province_name: 'ชุมพร', weather_latitude: 10.31859, weather_longitude: 99.03505 };

function weatherFunction(page, fetch) {
  const html = fs.readFileSync(path.join(root, page), 'utf8');
  const start = html.indexOf('async function weatherAtPoint(');
  const end = html.indexOf('async function loadWeather(', start);
  assert.ok(start >= 0 && end > start, `weatherAtPoint not found in ${page}`);
  return new Function('DATA', 'fetch', html.slice(start, end) + '; return weatherAtPoint;')(
    { provinces: [province] }, fetch);
}

for (const page of pages) {
  test(`${page}: HTTP 403 uses clearly labelled province proxy for a district point`, async () => {
    const urls = [];
    const fetch = async (url) => {
      urls.push(url);
      if (url.startsWith('/api/weather?')) return { status: 403, headers: { get: () => 'text/html' } };
      assert.equal(url, 'daily_86.json');
      return { ok: true, json: async () => [{ date: '2025-07-01', T2M: 27 }] };
    };
    const result = await weatherFunction(page, fetch)(
      { code: '86', lat: 10.64172, lon: 99.22074 }, '2025-07-01', '2025-07-01');
    assert.equal(result.rows.length, 1);
    assert.match(result.source, /ไม่ใช่พิกัด A\/B/);
    assert.match(result.warning, /ไม่ใช่ค่ารายอำเภอหรือหน่วยดิน/);
    assert.match(result.warning, /10\.31859/);
    assert.equal(urls.length, 2);
  });

  test(`${page}: incomplete backup is rejected`, async () => {
    const fetch = async (url) => url.startsWith('/api/weather?')
      ? { status: 403, headers: { get: () => 'text/html' } }
      : { ok: true, json: async () => [{ date: '2025-07-01', T2M: 27 }] };
    await assert.rejects(weatherFunction(page, fetch)(
      { code: '86', lat: 10.64172, lon: 99.22074 }, '2025-07-01', '2025-07-02'),
    /ไม่ครอบคลุมทุกวันที่เลือก/);
  });

  test(`${page}: verified stale point cache stays distinguished from live API`, async () => {
    const fetch = async () => ({
      ok: true, status: 200, headers: { get: () => 'application/json' },
      json: async () => ({ rows: [{ date: '2025-07-01', T2M: 27 }], stale_cache: true,
        provenance: { retrieved_utc: '2026-09-01T00:00:00+00:00' } }),
    });
    const result = await weatherFunction(page, fetch)(
      { code: '86', lat: 10.64172, lon: 99.22074 }, '2025-07-01', '2025-07-01');
    assert.match(result.source, /cache จุดที่เลือก/);
    assert.match(result.warning, /ไม่ได้อัปเดต|ข้อมูลล่าสุด/);
  });
}
