import { createClient } from "npm:@supabase/supabase-js@2";

const jsonHeaders = { "content-type": "application/json; charset=utf-8" };

function numberOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function bangkokTimestamp(value: string): string {
  const parsed = new Date(value);
  const utcMs = Number.isNaN(parsed.getTime()) ? Date.now() : parsed.getTime();
  return new Date(utcMs + 7 * 60 * 60 * 1000).toISOString().slice(0, 19);
}

Deno.serve(async (req) => {
  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "method_not_allowed" }), { status: 405, headers: jsonHeaders });
  }

  const expectedKey = Deno.env.get("DEVICE_INGEST_KEY");
  if (!expectedKey || req.headers.get("x-device-key") !== expectedKey) {
    return new Response(JSON.stringify({ error: "unauthorized" }), { status: 401, headers: jsonHeaders });
  }

  let body: Record<string, any>;
  try {
    body = await req.json();
  } catch {
    return new Response(JSON.stringify({ error: "invalid_json" }), { status: 400, headers: jsonHeaders });
  }

  const recordedAt = typeof body.recorded_at === "string" ? body.recorded_at : new Date().toISOString();
  const deviceId = typeof body.device_id === "string" ? body.device_id : "unknown";
  const eventId = typeof body.event_id === "string" ? body.event_id : `${deviceId}:${recordedAt}`;
  const soil = body.soil ?? {};
  const weather = body.weather ?? {};

  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    { auth: { persistSession: false } },
  );

  const reading = {
    event_id: eventId,
    recorded_at: recordedAt,
    recorded_at_th: bangkokTimestamp(recordedAt),
    device_id: deviceId,
    soil_moisture_percent: numberOrNull(soil.moisture_percent),
    soil_temperature_c: numberOrNull(soil.temperature_c),
    soil_ec: numberOrNull(soil.ec),
    soil_ph: numberOrNull(soil.ph),
    soil_n: numberOrNull(soil.n),
    soil_p: numberOrNull(soil.p),
    soil_k: numberOrNull(soil.k),
    soil_valid: typeof soil.valid === "boolean" ? soil.valid : null,
    soil_age_sec: numberOrNull(soil.age_sec),
    air_temperature_c: numberOrNull(weather.air_temperature_c),
    humidity_percent: numberOrNull(weather.humidity_percent),
    outdoor_temperature_c: numberOrNull(weather.outdoor_temperature_c),
    outdoor_humidity_percent: numberOrNull(weather.outdoor_humidity_percent),
    pressure_hpa: numberOrNull(weather.pressure_hpa),
    wind_avg: numberOrNull(weather.wind_avg),
    wind_gust: numberOrNull(weather.wind_gust),
    rain_1h_mm: numberOrNull(weather.rain_1h_mm),
    rain_24h_mm: numberOrNull(weather.rain_24h_mm),
    rain_rate_mm_h: numberOrNull(weather.rain_rate_mm_h),
    uv_index: numberOrNull(weather.uv_index),
    dew_point_c: numberOrNull(weather.dew_point_c),
    feels_like_c: numberOrNull(weather.feels_like_c),
    heat_index_c: numberOrNull(weather.heat_index_c),
    light_lux: numberOrNull(weather.light_lux),
    weather_valid: typeof weather.valid === "boolean" ? weather.valid : null,
    weather_age_sec: numberOrNull(weather.age_sec),
    weather_source: typeof weather.source === "string" ? weather.source : null,
    source_payload: body,
  };

  const { error: readingError } = await supabase
    .from("sensor_readings")
    .upsert(reading, { onConflict: "event_id" });
  if (readingError) {
    return new Response(JSON.stringify({ error: "reading_insert_failed", detail: readingError.message }), { status: 500, headers: jsonHeaders });
  }

  const ndvi = body.ndvi;
  if (ndvi?.valid && Number.isFinite(ndvi.captured_epoch)) {
    const capturedAt = new Date(ndvi.captured_epoch * 1000).toISOString();
    const { error } = await supabase.from("ndvi_observations").upsert({
      polygon_id: body.polygon_id ?? "farm-main",
      captured_at: capturedAt,
      ndvi_mean: numberOrNull(ndvi.mean),
      ndvi_min: numberOrNull(ndvi.min),
      ndvi_max: numberOrNull(ndvi.max),
      ndvi_median: numberOrNull(ndvi.median),
      cloud_coverage: numberOrNull(ndvi.cloud_coverage),
      source: ndvi.source ?? null,
      received_at: recordedAt,
    }, { onConflict: "polygon_id,captured_at" });
    if (error) console.error("NDVI upsert failed", error);
  }

  if (Array.isArray(body.forecast_7day)) {
    const issuedDate = recordedAt.slice(0, 10);
    const rows = body.forecast_7day
      .filter((day: any) => typeof day?.date === "string")
      .map((day: any) => ({
        location_id: body.location_id ?? "farm-main",
        issued_date: issuedDate,
        forecast_date: day.date,
        temp_max_c: numberOrNull(day.temp_max_c),
        temp_min_c: numberOrNull(day.temp_min_c),
        humidity_percent: numberOrNull(day.humidity_percent),
        rain_mm: numberOrNull(day.rain_mm),
        condition_code: numberOrNull(day.cond),
        received_at: recordedAt,
      }));
    if (rows.length) {
      const { error } = await supabase.from("weather_forecasts").upsert(rows, {
        onConflict: "location_id,issued_date,forecast_date",
      });
      if (error) console.error("Forecast upsert failed", error);
    }
  }

  if (Array.isArray(body.forecast_hourly)) {
    const rows = body.forecast_hourly
      .filter((hour: any) => typeof hour?.time === "string")
      .map((hour: any) => ({
        location_id: body.location_id ?? "farm-main",
        issued_at: recordedAt,
        forecast_time: hour.time,
        temperature_c: numberOrNull(hour.temperature_c),
        humidity_percent: numberOrNull(hour.humidity_percent),
        pressure_hpa: numberOrNull(hour.pressure_hpa),
        rain_mm: numberOrNull(hour.rain_mm),
        wind_speed_ms: numberOrNull(hour.wind_speed_ms),
        wind_direction_deg: numberOrNull(hour.wind_direction_deg),
        cloud_low_percent: numberOrNull(hour.cloud_low_percent),
        cloud_mid_percent: numberOrNull(hour.cloud_mid_percent),
        cloud_high_percent: numberOrNull(hour.cloud_high_percent),
        condition_code: numberOrNull(hour.cond),
        source: body.hourly_forecast_source ?? null,
        received_at: recordedAt,
      }));
    if (rows.length) {
      const { error } = await supabase.from("weather_forecasts_hourly").upsert(rows, {
        onConflict: "location_id,issued_at,forecast_time",
      });
      if (error) console.error("Hourly forecast upsert failed", error);
    }
  }

  return new Response(JSON.stringify({ ok: true, event_id: eventId }), { status: 200, headers: jsonHeaders });
});
