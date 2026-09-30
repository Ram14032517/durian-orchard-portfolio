-- Align an existing sensor_readings table with the Wi-Fi-only gateway.
alter table public.sensor_readings
  add column if not exists recorded_at_th timestamp without time zone;

update public.sensor_readings
set recorded_at_th = recorded_at at time zone 'Asia/Bangkok'
where recorded_at_th is null;

alter table public.sensor_readings
  alter column recorded_at_th set not null;

alter table public.sensor_readings
  drop column if exists lora_rssi;
