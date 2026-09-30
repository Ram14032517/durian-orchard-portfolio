create table if not exists public.sensor_readings (
  id bigint generated always as identity primary key,
  event_id text not null unique,
  recorded_at timestamptz not null,
  recorded_at_th timestamp without time zone not null,
  device_id text not null,
  soil_moisture_percent real,
  soil_temperature_c real,
  soil_ec integer,
  soil_ph real,
  soil_n integer,
  soil_p integer,
  soil_k integer,
  air_temperature_c real,
  humidity_percent real,
  outdoor_temperature_c real,
  outdoor_humidity_percent real,
  pressure_hpa real,
  wind_avg real,
  wind_gust real,
  rain_1h_mm real,
  rain_24h_mm real,
  rain_rate_mm_h real,
  uv_index real,
  dew_point_c real,
  feels_like_c real,
  heat_index_c real,
  light_lux real,
  source_payload jsonb not null,
  created_at timestamptz not null default now()
);

create index if not exists sensor_readings_device_time_idx
  on public.sensor_readings (device_id, recorded_at desc);

create table if not exists public.ndvi_observations (
  polygon_id text not null,
  captured_at timestamptz not null,
  ndvi_mean real,
  ndvi_min real,
  ndvi_max real,
  ndvi_median real,
  cloud_coverage real,
  source text,
  received_at timestamptz not null default now(),
  primary key (polygon_id, captured_at)
);

create table if not exists public.weather_forecasts (
  location_id text not null,
  issued_date date not null,
  forecast_date date not null,
  temp_max_c real,
  temp_min_c real,
  humidity_percent real,
  rain_mm real,
  condition_code integer,
  received_at timestamptz not null default now(),
  primary key (location_id, issued_date, forecast_date)
);

alter table public.sensor_readings enable row level security;
alter table public.ndvi_observations enable row level security;
alter table public.weather_forecasts enable row level security;

-- The Edge Function uses the service role. Do not add an anonymous INSERT policy.
grant usage on schema public to service_role;
grant select, insert, update, delete on public.sensor_readings to service_role;
grant select, insert, update, delete on public.ndvi_observations to service_role;
grant select, insert, update, delete on public.weather_forecasts to service_role;
grant usage, select on sequence public.sensor_readings_id_seq to service_role;
