-- Add queryable data-quality metadata without deleting historical rows.
alter table public.sensor_readings
  add column if not exists soil_valid boolean,
  add column if not exists soil_age_sec integer,
  add column if not exists weather_valid boolean,
  add column if not exists weather_age_sec integer,
  add column if not exists weather_source text;

create index if not exists sensor_readings_recorded_at_idx
  on public.sensor_readings (recorded_at desc);

create index if not exists sensor_readings_weather_quality_idx
  on public.sensor_readings (weather_valid, recorded_at desc);

create table if not exists public.weather_forecasts_hourly (
  location_id text not null,
  issued_at timestamptz not null,
  forecast_time timestamptz not null,
  temperature_c real,
  humidity_percent real,
  pressure_hpa real,
  rain_mm real,
  wind_speed_ms real,
  wind_direction_deg real,
  cloud_low_percent real,
  cloud_mid_percent real,
  cloud_high_percent real,
  condition_code integer,
  source text,
  received_at timestamptz not null default now(),
  primary key (location_id, issued_at, forecast_time)
);

create index if not exists weather_forecasts_hourly_time_idx
  on public.weather_forecasts_hourly (location_id, forecast_time desc);

alter table public.weather_forecasts_hourly enable row level security;
grant select, insert, update, delete on public.weather_forecasts_hourly to service_role;

-- Dashboard/export view. It does not remove or rewrite raw data.
create or replace view public.sensor_readings_clean as
select *
from public.sensor_readings
where coalesce(soil_valid, true)
  and coalesce(weather_valid, true);
