const READING_HEADERS = [
  'event_id', 'recorded_at', 'recorded_at_th', 'device_id', 'soil_moisture_percent',
  'soil_temperature_c', 'soil_ec', 'soil_ph', 'soil_n', 'soil_p', 'soil_k',
  'air_temperature_c', 'humidity_percent', 'outdoor_temperature_c',
  'outdoor_humidity_percent', 'pressure_hpa', 'wind_avg', 'wind_gust',
  'rain_1h_mm', 'rain_24h_mm', 'rain_rate_mm_h', 'uv_index', 'dew_point_c',
  'feels_like_c', 'heat_index_c', 'light_lux'
];

function doPost(e) {
  const props = PropertiesService.getScriptProperties();
  if (!e || e.parameter.key !== props.getProperty('DEVICE_INGEST_KEY')) {
    return jsonResponse_({ ok: false, error: 'unauthorized' });
  }

  let data;
  try {
    data = JSON.parse(e.postData.contents);
  } catch (err) {
    return jsonResponse_({ ok: false, error: 'invalid_json' });
  }

  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const book = SpreadsheetApp.openById(props.getProperty('SPREADSHEET_ID'));
    appendReading_(book, data);
    upsertNdvi_(book, data);
    upsertForecast_(book, data);
    upsertHourlyForecast_(book, data);
  } finally {
    lock.releaseLock();
  }

  return jsonResponse_({ ok: true, event_id: data.event_id || '' });
}

// Run this once from the Apps Script editor to repair existing shifted rows
// immediately. New POST requests also run the same repair automatically.
function repairReadingsSheet() {
  const props = PropertiesService.getScriptProperties();
  const book = SpreadsheetApp.openById(props.getProperty('SPREADSHEET_ID'));
  const sheet = getSheet_(book, 'readings_15min', READING_HEADERS);
  ensureReadingHeaders_(sheet);
}

function appendReading_(book, data) {
  const sheet = getSheet_(book, 'readings_15min', READING_HEADERS);
  ensureReadingHeaders_(sheet);
  const eventId = data.event_id || `${data.device_id || 'unknown'}:${data.recorded_at || new Date().toISOString()}`;
  if (sheet.getLastRow() > 1 && sheet.getRange(2, 1, sheet.getLastRow() - 1, 1)
      .createTextFinder(eventId).matchEntireCell(true).findNext()) return;

  const s = data.soil || {};
  const w = data.weather || {};
  const recordedAt = data.recorded_at || new Date().toISOString();
  sheet.appendRow([
    eventId, recordedAt, bangkokTime_(recordedAt), data.device_id || '',
    value_(s.moisture_percent), value_(s.temperature_c), value_(s.ec), value_(s.ph),
    value_(s.n), value_(s.p), value_(s.k),
    value_(w.air_temperature_c), value_(w.humidity_percent),
    value_(w.outdoor_temperature_c), value_(w.outdoor_humidity_percent),
    value_(w.pressure_hpa), value_(w.wind_avg), value_(w.wind_gust),
    value_(w.rain_1h_mm), value_(w.rain_24h_mm), value_(w.rain_rate_mm_h),
    value_(w.uv_index), value_(w.dew_point_c), value_(w.feels_like_c),
    value_(w.heat_index_c), value_(w.light_lux)
  ]);
}

function upsertNdvi_(book, data) {
  const n = data.ndvi || {};
  if (!n.valid || !n.captured_epoch) return;
  const headers = ['key', 'captured_at', 'mean', 'min', 'max', 'median', 'cloud_coverage', 'source', 'received_at'];
  const sheet = getSheet_(book, 'ndvi_daily', headers);
  const key = `${data.polygon_id || 'farm-main'}:${n.captured_epoch}`;
  upsertRow_(sheet, key, [key, new Date(n.captured_epoch * 1000), value_(n.mean), value_(n.min),
    value_(n.max), value_(n.median), value_(n.cloud_coverage), n.source || '', data.recorded_at || new Date()]);
}

function upsertForecast_(book, data) {
  if (!Array.isArray(data.forecast_7day)) return;
  const headers = ['key', 'issued_date', 'forecast_date', 'temp_max_c', 'temp_min_c',
    'humidity_percent', 'rain_mm', 'condition_code', 'received_at', 'source',
    'pressure_hpa', 'wind_speed_ms', 'wind_direction_deg', 'cloud_low_percent',
    'cloud_mid_percent', 'cloud_high_percent', 'shortwave'];
  const sheet = getSheet_(book, 'forecast_daily', headers);
  ensureHeaders_(sheet, headers);
  const issued = String(data.recorded_at || new Date().toISOString()).slice(0, 10);
  data.forecast_7day.forEach(day => {
    if (!day.date) return;
    const key = `${data.location_id || 'farm-main'}:${issued}:${day.date}`;
    upsertRow_(sheet, key, [key, issued, day.date, value_(day.temp_max_c),
      value_(day.temp_min_c), value_(day.humidity_percent), value_(day.rain_mm),
      value_(day.cond), data.recorded_at || new Date(), data.forecast_source || '',
      value_(day.pressure_hpa), value_(day.wind_speed_ms), value_(day.wind_direction_deg),
      value_(day.cloud_low_percent), value_(day.cloud_mid_percent),
      value_(day.cloud_high_percent), value_(day.shortwave)]);
  });
}

function upsertHourlyForecast_(book, data) {
  if (!Array.isArray(data.forecast_hourly)) return;
  const headers = ['key', 'issued_at', 'forecast_time', 'temperature_c',
    'humidity_percent', 'pressure_hpa', 'rain_mm', 'wind_speed_ms',
    'wind_direction_deg', 'cloud_low_percent', 'cloud_mid_percent',
    'cloud_high_percent', 'condition_code', 'source', 'received_at'];
  const sheet = getSheet_(book, 'forecast_hourly', headers);
  const issued = String(data.recorded_at || new Date().toISOString());
  data.forecast_hourly.forEach(hour => {
    if (!hour.time) return;
    const key = `${data.location_id || 'farm-main'}:${issued}:${hour.time}`;
    upsertRow_(sheet, key, [key, issued, hour.time, value_(hour.temperature_c),
      value_(hour.humidity_percent), value_(hour.pressure_hpa), value_(hour.rain_mm),
      value_(hour.wind_speed_ms), value_(hour.wind_direction_deg),
      value_(hour.cloud_low_percent), value_(hour.cloud_mid_percent),
      value_(hour.cloud_high_percent), value_(hour.cond),
      data.hourly_forecast_source || '', data.recorded_at || new Date()]);
  });
}

function upsertRow_(sheet, key, row) {
  let found = null;
  if (sheet.getLastRow() > 1) {
    found = sheet.getRange(2, 1, sheet.getLastRow() - 1, 1)
      .createTextFinder(key).matchEntireCell(true).findNext();
  }
  if (found) sheet.getRange(found.getRow(), 1, 1, row.length).setValues([row]);
  else sheet.appendRow(row);
}

function getSheet_(book, name, headers) {
  let sheet = book.getSheetByName(name);
  if (!sheet) sheet = book.insertSheet(name);
  if (sheet.getLastRow() === 0) sheet.appendRow(headers);
  return sheet;
}

function ensureReadingHeaders_(sheet) {
  let lastColumn = Math.max(sheet.getLastColumn(), 1);
  let headers = sheet.getRange(1, 1, 1, lastColumn).getValues()[0];

  // Migrate an existing sheet safely: delete the obsolete LoRa column so all
  // weather columns and historical values shift left together.
  const loraIndex = headers.indexOf('lora_rssi');
  if (loraIndex !== -1) {
    sheet.deleteColumn(loraIndex + 1);
    lastColumn = Math.max(sheet.getLastColumn(), 1);
    headers = sheet.getRange(1, 1, 1, lastColumn).getValues()[0];
  }

  if (headers[2] !== 'recorded_at_th') {
    sheet.insertColumnAfter(2);
    const rowCount = sheet.getLastRow() - 1;
    if (rowCount > 0) {
      const utcValues = sheet.getRange(2, 2, rowCount, 1).getValues();
      const localValues = utcValues.map(row => [row[0] ? bangkokTime_(row[0]) : '']);
      sheet.getRange(2, 3, rowCount, 1).setValues(localValues);
    }
  }

  repairLegacyLoraGap_(sheet);
  sheet.getRange(1, 1, 1, READING_HEADERS.length).setValues([READING_HEADERS]);
  sheet.setFrozenRows(1);
}

function repairLegacyLoraGap_(sheet) {
  const rowCount = sheet.getLastRow() - 1;
  const legacyLastColumn = READING_HEADERS.length + 1; // AA: old light_lux
  if (rowCount < 1 || sheet.getLastColumn() < legacyLastColumn) return;

  // Old deployed code still wrote a blank lora_rssi at L, putting weather in
  // M:AA. Only repair rows that have the blank gap and a value in AA.
  const firstWeatherColumn = 12; // L
  const width = legacyLastColumn - firstWeatherColumn + 1; // L:AA
  const range = sheet.getRange(2, firstWeatherColumn, rowCount, width);
  const rows = range.getValues();
  let changed = false;

  rows.forEach(row => {
    if (row[0] === '' && row[width - 1] !== '') {
      for (let column = 0; column < width - 1; column++) {
        row[column] = row[column + 1];
      }
      row[width - 1] = '';
      changed = true;
    }
  });

  if (changed) range.setValues(rows);
}

function ensureTrailingHeader_(sheet, header) {
  const lastColumn = Math.max(sheet.getLastColumn(), 1);
  const headers = sheet.getRange(1, 1, 1, lastColumn).getValues()[0];
  if (headers.indexOf(header) !== -1) return;
  sheet.getRange(1, lastColumn + 1).setValue(header);
}

function ensureHeaders_(sheet, headers) {
  const current = sheet.getRange(1, 1, 1, Math.max(sheet.getLastColumn(), 1)).getValues()[0];
  headers.forEach(header => {
    if (current.indexOf(header) === -1) {
      current.push(header);
      sheet.getRange(1, current.length).setValue(header);
    }
  });
}

function bangkokTime_(value) {
  const date = value instanceof Date ? value : new Date(value);
  if (isNaN(date.getTime())) return '';
  return Utilities.formatDate(date, 'Asia/Bangkok', 'yyyy-MM-dd HH:mm:ss');
}

function value_(v) {
  return typeof v === 'number' && isFinite(v) ? v : '';
}

function jsonResponse_(value) {
  return ContentService.createTextOutput(JSON.stringify(value))
    .setMimeType(ContentService.MimeType.JSON);
}

// Preview retention without changing the spreadsheet. Run this first and
// inspect Executions > Logs before calling applySheetRetention().
function previewSheetRetention() {
  const book = SpreadsheetApp.openById(
    PropertiesService.getScriptProperties().getProperty('SPREADSHEET_ID')
  );
  const plan = retentionPlan_(book, new Date());
  console.log(JSON.stringify(plan, null, 2));
  return plan;
}

// Destructive: delete old rows only after a verified local backup exists.
// Keep NDVI history because it is small and valuable for model evaluation.
function applySheetRetention() {
  const book = SpreadsheetApp.openById(
    PropertiesService.getScriptProperties().getProperty('SPREADSHEET_ID')
  );
  // Preserve lightweight daily statistics before raw rows are removed.
  rebuildEnvironmentRiskDaily_(book);
  const now = new Date();
  const rules = [
    { sheet: 'readings_15min', dateColumn: 2, days: 30 },
    { sheet: 'forecast_hourly', dateColumn: 2, days: 7 },
    { sheet: 'forecast_daily', dateColumn: 2, days: 30 }
  ];
  const result = rules.map(rule => {
    const cutoff = new Date(now.getTime() - rule.days * 24 * 60 * 60 * 1000);
    return deleteRowsOlderThan_(book.getSheetByName(rule.sheet), rule.dateColumn, cutoff, rule.days);
  });
  console.log(JSON.stringify(result, null, 2));
  return result;
}

// Run daily (or manually) to build a compact long-term summary from readings.
// This is an environmental screening score, not NDVI or a disease diagnosis.
function rebuildEnvironmentRiskDaily() {
  const book = SpreadsheetApp.openById(
    PropertiesService.getScriptProperties().getProperty('SPREADSHEET_ID')
  );
  return rebuildEnvironmentRiskDaily_(book);
}

function rebuildEnvironmentRiskDaily_(book) {
  const input = book.getSheetByName('readings_15min');
  if (!input || input.getLastRow() <= 1) return [];

  const headers = input.getRange(1, 1, 1, input.getLastColumn()).getValues()[0];
  const index = {};
  headers.forEach((header, column) => index[header] = column);
  const required = [
    'recorded_at_th', 'soil_moisture_percent', 'humidity_percent',
    'rain_1h_mm', 'air_temperature_c', 'outdoor_temperature_c',
    'outdoor_humidity_percent', 'pressure_hpa', 'light_lux', 'uv_index'
  ];
  required.forEach(header => {
    if (index[header] === undefined) throw new Error(`Missing readings header: ${header}`);
  });

  const rows = input.getRange(2, 1, input.getLastRow() - 1, input.getLastColumn()).getValues();
  const daily = {};
  let previousWeather = null;
  let unchangedSince = null;

  rows.forEach(row => {
    const observed = row[index.recorded_at_th] instanceof Date
      ? row[index.recorded_at_th]
      : new Date(row[index.recorded_at_th]);
    if (isNaN(observed.getTime())) return;
    const day = Utilities.formatDate(observed, 'Asia/Bangkok', 'yyyy-MM-dd');
    if (!daily[day]) {
      daily[day] = {
        date: day, rows: 0, usableWeather: 0, staleWeather: 0,
        soilMoistureSum: 0, soilMoistureCount: 0,
        humiditySum: 0, humidityCount: 0, rainSum: 0, wetAlerts: 0,
        lightSum: 0, lightCount: 0, lightMax: 0, lightExposureKluxHours: 0,
        uvSum: 0, uvCount: 0, uvMax: 0
      };
    }
    const item = daily[day];
    item.rows++;

    const soilMoisture = Number(row[index.soil_moisture_percent]);
    const humidity = Number(row[index.outdoor_humidity_percent]);
    const rain = Number(row[index.rain_1h_mm]);
    const light = Number(row[index.light_lux]);
    const uv = Number(row[index.uv_index]);
    if (Number.isFinite(soilMoisture)) {
      item.soilMoistureSum += soilMoisture;
      item.soilMoistureCount++;
    }
    const weather = [
      row[index.outdoor_temperature_c], row[index.outdoor_humidity_percent],
      row[index.pressure_hpa]
    ];
    const weatherValid = weather.every(value => value !== '' && Number.isFinite(Number(value)));

    const weatherKey = weatherValid ? weather.join('|') : null;
    let weatherStale = false;
    if (weatherKey && weatherKey === previousWeather) {
      if (unchangedSince === null) unchangedSince = observed.getTime() - 15 * 60 * 1000;
      weatherStale = observed.getTime() - unchangedSince >= 60 * 60 * 1000;
      if (weatherStale) item.staleWeather++;
    } else {
      unchangedSince = observed.getTime();
    }
    previousWeather = weatherKey;

    const weatherUsable = weatherValid && !weatherStale;
    if (weatherUsable) {
      item.usableWeather++;
      if (Number.isFinite(humidity)) {
        item.humiditySum += humidity;
        item.humidityCount++;
      }
      if (Number.isFinite(rain)) item.rainSum += Math.max(0, rain);
      if (Number.isFinite(light)) {
        item.lightSum += light;
        item.lightCount++;
        item.lightMax = Math.max(item.lightMax, light);
        // Sampling interval is 15 minutes. This is a lux exposure proxy,
        // not PAR/DLI because the sensor does not measure photon spectrum.
        item.lightExposureKluxHours += light * 0.25 / 1000;
      }
      if (Number.isFinite(uv)) {
        item.uvSum += uv;
        item.uvCount++;
        item.uvMax = Math.max(item.uvMax, uv);
      }
    }

    // Thresholds come from the current dataset's Q3 values, not disease labels.
    const wetPoints = (soilMoisture >= 43.5 ? 1 : 0)
      + (humidity >= 75 ? 1 : 0)
      + (rain > 0 ? 1 : 0);
    if (weatherUsable && wetPoints >= 2) item.wetAlerts++;
  });

  const outputHeaders = [
    'date', 'reading_count', 'usable_weather_count', 'stale_weather_count',
    'avg_soil_moisture_percent', 'avg_humidity_percent', 'rain_1h_sum_mm',
    'avg_light_lux', 'max_light_lux', 'light_exposure_klux_hours',
    'avg_uv_index', 'max_uv_index',
    'wet_environment_alert_count', 'wet_environment_alert_rate', 'risk_level',
    'method'
  ];
  const outputRows = Object.keys(daily).sort().map(day => {
    const item = daily[day];
    const alertRate = item.usableWeather ? item.wetAlerts / item.usableWeather : 0;
    const riskLevel = alertRate >= 0.5 ? 'high' : alertRate >= 0.2 ? 'medium' : 'low';
    return [
      item.date, item.rows, item.usableWeather, item.staleWeather,
      item.soilMoistureCount ? item.soilMoistureSum / item.soilMoistureCount : '',
      item.humidityCount ? item.humiditySum / item.humidityCount : '',
      item.rainSum,
      item.lightCount ? item.lightSum / item.lightCount : '',
      item.lightMax, item.lightExposureKluxHours,
      item.uvCount ? item.uvSum / item.uvCount : '', item.uvMax,
      item.wetAlerts, alertRate, riskLevel,
      'environment proxy; not NDVI or disease diagnosis'
    ];
  });

  const output = getSheet_(book, 'environment_risk_daily', outputHeaders);
  output.clearContents();
  output.getRange(1, 1, 1, outputHeaders.length).setValues([outputHeaders]);
  if (outputRows.length) {
    output.getRange(2, 1, outputRows.length, outputHeaders.length).setValues(outputRows);
    output.getRange(2, 14, outputRows.length, 1).setNumberFormat('0.0%');
  }
  output.setFrozenRows(1);
  return outputRows;
}

function retentionPlan_(book, now) {
  const rules = [
    { sheet: 'readings_15min', dateColumn: 2, days: 30 },
    { sheet: 'forecast_hourly', dateColumn: 2, days: 7 },
    { sheet: 'forecast_daily', dateColumn: 2, days: 30 }
  ];
  return rules.map(rule => {
    const cutoff = new Date(now.getTime() - rule.days * 24 * 60 * 60 * 1000);
    const sheet = book.getSheetByName(rule.sheet);
    const count = countRowsOlderThan_(sheet, rule.dateColumn, cutoff);
    return {
      sheet: rule.sheet,
      retention_days: rule.days,
      cutoff: cutoff.toISOString(),
      rows_to_delete: count,
      rows_to_keep: Math.max(0, sheet.getLastRow() - 1 - count)
    };
  });
}

function countRowsOlderThan_(sheet, dateColumn, cutoff) {
  if (!sheet || sheet.getLastRow() <= 1) return 0;
  const values = sheet.getRange(2, dateColumn, sheet.getLastRow() - 1, 1).getValues();
  return values.reduce((count, row) => {
    const date = row[0] instanceof Date ? row[0] : new Date(row[0]);
    return count + (!isNaN(date.getTime()) && date < cutoff ? 1 : 0);
  }, 0);
}

function deleteRowsOlderThan_(sheet, dateColumn, cutoff, retentionDays) {
  if (!sheet || sheet.getLastRow() <= 1) {
    return { sheet: sheet ? sheet.getName() : '', deleted: 0 };
  }

  const values = sheet.getRange(2, dateColumn, sheet.getLastRow() - 1, 1).getValues();
  const rows = [];
  values.forEach((row, index) => {
    const date = row[0] instanceof Date ? row[0] : new Date(row[0]);
    if (!isNaN(date.getTime()) && date < cutoff) rows.push(index + 2);
  });

  // Delete bottom-up in contiguous blocks to reduce Spreadsheet API calls.
  let blockEnd = null;
  let blockStart = null;
  let deleted = 0;
  for (let index = rows.length - 1; index >= 0; index--) {
    const rowNumber = rows[index];
    if (blockEnd === null) {
      blockStart = rowNumber;
      blockEnd = rowNumber;
    } else if (rowNumber === blockStart - 1) {
      blockStart = rowNumber;
    } else {
      sheet.deleteRows(blockStart, blockEnd - blockStart + 1);
      deleted += blockEnd - blockStart + 1;
      blockStart = rowNumber;
      blockEnd = rowNumber;
    }
  }
  if (blockEnd !== null) {
    sheet.deleteRows(blockStart, blockEnd - blockStart + 1);
    deleted += blockEnd - blockStart + 1;
  }

  return {
    sheet: sheet.getName(),
    retention_days: retentionDays,
    cutoff: cutoff.toISOString(),
    deleted: deleted,
    remaining: Math.max(0, sheet.getLastRow() - 1)
  };
}
