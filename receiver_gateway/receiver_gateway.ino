#include <WiFi.h>
#include "farm_secret.h"
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <mbedtls/md.h>
#include "TuyaLocal34.h"
#include "tuya_local_secret.h"
#include "tuya_cloud_secret.h"

// =====================
// WIFI CONFIG
// =====================

// =====================
// TUYA LOCAL CONFIG
// =====================
const char* TUYA_LOCAL_IP = "192.168.1.2";
const bool ENABLE_TUYA_LOCAL = true;
const char* TUYA_CODES =
  "temp_current,humidity_value,temp_current_external,humidity_outdoor,"
  "atmospheric_pressture,windspeed_avg,windspeed_gust,rain_1h,rain_24h,"
  "rain_rate,uv_index,dew_point_temp,feellike_temp,heat_index,Light_intensity";

// =====================
// TMD 7-DAY FORECAST
// =====================
const char* TMD_ENDPOINT = "https://data.tmd.go.th/nwpapi/v1/forecast/location/daily/at";
const int TMD_FORECAST_DAYS = 7;
const int TMD_FORECAST_HOURS = 48;
const char* TMD_FIELDS = "tc_max,tc_min,rh,slp,rain,ws10m,wd10m,cloudlow,cloudmed,cloudhigh,swdown,cond";
const char* TMD_HOURLY_ENDPOINT = "https://data.tmd.go.th/nwpapi/v1/forecast/location/hourly/at";
const char* TMD_HOURLY_FIELDS = "tc,rh,slp,rain,ws10m,wd10m,cloudlow,cloudmed,cloudhigh,cond";

// =====================
// AGROMONITORING NDVI
// =====================
const char* AGRO_ENDPOINT = "https://api.agromonitoring.com/agro/1.0/ndvi/history";
const unsigned long AGRO_LOOKBACK_SEC = 30UL * 24UL * 60UL * 60UL;

// =====================
// CLOUD STORAGE
// =====================
// Fill these after deploying the Supabase Edge Function and Google Apps Script.
// DEVICE_INGEST_KEY must be a new random value used only for this gateway.
const bool ENABLE_SUPABASE = true;
const bool ENABLE_GOOGLE_SHEETS = true;

// =====================
// SOIL SENSOR RS485 / MODBUS RTU
// =====================
#define SOIL_TX_PIN 17
#define SOIL_RX_PIN 18
const uint32_t SOIL_BAUD = 4800;
const uint8_t SOIL_ADDRESS = 0x01;
// Match the proven soil sender: use ESP32 UART2.
HardwareSerial soilSerial(2);

// =====================
// DATA STRUCT
// =====================
struct SoilData {
  bool valid = false;
  float moisture = 0;
  float temp = 0;
  int ec = 0;
  float ph = 0;
  int n = 0;
  int p = 0;
  int k = 0;
  unsigned long updatedMs = 0;
};

struct WeatherData {
  bool valid = false;

  bool hasAirTemp = false;
  bool hasHumidity = false;
  bool hasOutdoorTemp = false;
  bool hasOutdoorHumidity = false;
  bool hasPressure = false;
  bool hasWindAvg = false;
  bool hasWindGust = false;
  bool hasRain1h = false;
  bool hasRain24h = false;
  bool hasRainRate = false;
  bool hasUv = false;
  bool hasDewPoint = false;
  bool hasFeelsLike = false;
  bool hasHeatIndex = false;
  bool hasLight = false;

  float airTemp = 0;
  float humidity = 0;
  float outdoorTemp = 0;
  float outdoorHumidity = 0;
  float pressure = 0;
  float windAvg = 0;
  float windGust = 0;
  float rain1h = 0;
  float rain24h = 0;
  float rainRate = 0;
  float uv = 0;
  float dewPoint = 0;
  float feelsLike = 0;
  float heatIndex = 0;
  float light = 0;
  String source;

  unsigned long updatedMs = 0;
};

struct ForecastDay {
  bool valid = false;
  String date;
  float tempMax = 0;
  float tempMin = 0;
  float humidity = 0;
  float rain = 0;
  float pressure = 0;
  float windSpeed = 0;
  float windDirection = 0;
  float cloudLow = 0;
  float cloudMid = 0;
  float cloudHigh = 0;
  float shortwave = 0;
  int cond = -1;
};

struct ForecastHour {
  bool valid = false;
  String time;
  float temperature = 0;
  float humidity = 0;
  float pressure = 0;
  float rain = 0;
  float windSpeed = 0;
  float windDirection = 0;
  float cloudLow = 0;
  float cloudMid = 0;
  float cloudHigh = 0;
  int cond = -1;
};

struct NdviData {
  bool valid = false;
  float mean = 0;
  float minVal = 0;
  float maxVal = 0;
  float median = 0;
  float cloudCoverage = 0;
  unsigned long captureDt = 0;
  String source;
};

SoilData soil;
WeatherData weather;
ForecastDay forecast[7];
bool forecastValid = false;
unsigned long forecastUpdatedMs = 0;
String forecastSource;
ForecastHour hourlyForecast[48];
bool hourlyForecastValid = false;
unsigned long hourlyForecastUpdatedMs = 0;
String hourlyForecastSource;
bool forecastsPendingUpload = true;
NdviData ndvi;
unsigned long ndviUpdatedMs = 0;

TuyaLocal34 tuyaLocal(TUYA_LOCAL_IP, TUYA_LOCAL_KEY);
String tuyaAccessToken;
unsigned long tuyaTokenExpireMs = 0;
long long lastUploadSlot = -1;
int lastForecastDateKey = -1;
int lastNdviDateKey = -1;
time_t scheduledRecordedAt = 0;

// =====================
// HELPERS
// =====================
int ageSec(bool valid, unsigned long updatedMs) {
  if (!valid || updatedMs == 0) return -1;
  return (int)((millis() - updatedMs) / 1000UL);
}

String sha256Hex(const String& data) {
  uint8_t hash[32];
  mbedtls_md_context_t context;
  const mbedtls_md_info_t* info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  mbedtls_md_init(&context);
  mbedtls_md_setup(&context, info, 0);
  mbedtls_md_starts(&context);
  mbedtls_md_update(&context, (const uint8_t*)data.c_str(), data.length());
  mbedtls_md_finish(&context, hash);
  mbedtls_md_free(&context);
  char output[65];
  for (int i = 0; i < 32; ++i) sprintf(output + i * 2, "%02x", hash[i]);
  output[64] = 0;
  return String(output);
}

String hmacSha256Upper(const String& key, const String& data) {
  uint8_t hash[32];
  mbedtls_md_context_t context;
  const mbedtls_md_info_t* info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  mbedtls_md_init(&context);
  mbedtls_md_setup(&context, info, 1);
  mbedtls_md_hmac_starts(&context, (const uint8_t*)key.c_str(), key.length());
  mbedtls_md_hmac_update(&context, (const uint8_t*)data.c_str(), data.length());
  mbedtls_md_hmac_finish(&context, hash);
  mbedtls_md_free(&context);
  char output[65];
  for (int i = 0; i < 32; ++i) sprintf(output + i * 2, "%02X", hash[i]);
  output[64] = 0;
  return String(output);
}

String tuyaTimestampMs() {
  return String((uint64_t)time(nullptr) * 1000ULL);
}

String tuyaSign(const String& path, const String& timestamp,
                const String& accessToken = "") {
  String stringToSign = "GET\n" + sha256Hex("") + "\n\n" + path;
  return hmacSha256Upper(String(TUYA_CLIENT_SECRET),
      String(TUYA_CLIENT_ID) + accessToken + timestamp + stringToSign);
}

// =====================
// WIFI / TIME
// =====================
bool ensureWiFi() {
  if (WiFi.status() == WL_CONNECTED) return true;

  Serial.print("WiFi connecting");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
    Serial.print(".");
    delay(500);
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("WiFi OK IP: ");
    Serial.println(WiFi.localIP());
    return true;
  }

  Serial.println("WiFi failed");
  return false;
}

bool waitForTime() {
  Serial.print("Waiting NTP time");

  configTime(7 * 3600, 0, "pool.ntp.org", "time.google.com", "time.nist.gov");

  unsigned long start = millis();
  time_t now = time(nullptr);

  while (now < 1700000000 && millis() - start < 30000) {
    Serial.print(".");
    delay(500);
    now = time(nullptr);
  }

  Serial.println();

  if (now < 1700000000) {
    Serial.println("NTP time failed. Cloud timestamps may be unavailable.");
    return false;
  }

  Serial.print("Time OK: ");
  Serial.println((unsigned long)now);
  return true;
}

// =====================
// TUYA LOCAL PROTOCOL 3.4
// =====================
bool fetchTuyaWeatherLocal() {
  if (!ensureWiFi()) {
    weather = WeatherData();
    return false;
  }

  String res;
  bool localOk = false;
  for (int attempt = 1; attempt <= 2 && !localOk; ++attempt) {
    localOk = tuyaLocal.getStatus(res);
    if (!localOk && attempt < 2) delay(2000);
  }
  if (!localOk) {
    Serial.print("Tuya Local failed: ");
    Serial.println(tuyaLocal.lastError());
    weather = WeatherData();
    return false;
  }

  DynamicJsonDocument doc(4096);
  DeserializationError err = deserializeJson(doc, res);
  if (err) {
    Serial.print("Tuya Local JSON error: ");
    Serial.println(err.c_str());
    weather = WeatherData();
    return false;
  }

  JsonObject dps = doc["dps"].as<JsonObject>();
  if (dps.isNull()) dps = doc["data"]["dps"].as<JsonObject>();
  if (dps.isNull()) {
    Serial.println("Tuya Local response has no DPS");
    weather = WeatherData();
    return false;
  }

  WeatherData nextWeather;
  if (dps.containsKey("1")) { nextWeather.airTemp = dps["1"].as<float>() / 10.0; nextWeather.hasAirTemp = true; }
  if (dps.containsKey("2")) { nextWeather.humidity = dps["2"].as<float>(); nextWeather.hasHumidity = true; }
  if (dps.containsKey("38")) { nextWeather.outdoorTemp = dps["38"].as<float>() / 10.0; nextWeather.hasOutdoorTemp = true; }
  if (dps.containsKey("39")) { nextWeather.outdoorHumidity = dps["39"].as<float>(); nextWeather.hasOutdoorHumidity = true; }
  if (dps.containsKey("54")) { nextWeather.pressure = dps["54"].as<float>(); nextWeather.hasPressure = true; }
  if (dps.containsKey("56")) { nextWeather.windAvg = dps["56"].as<float>() / 10.0; nextWeather.hasWindAvg = true; }
  if (dps.containsKey("57")) { nextWeather.windGust = dps["57"].as<float>() / 10.0; nextWeather.hasWindGust = true; }
  if (dps.containsKey("59")) { nextWeather.rain1h = dps["59"].as<float>() / 10.0; nextWeather.hasRain1h = true; }
  if (dps.containsKey("60")) { nextWeather.rain24h = dps["60"].as<float>() / 10.0; nextWeather.hasRain24h = true; }
  if (dps.containsKey("61")) { nextWeather.rainRate = dps["61"].as<float>() / 10.0; nextWeather.hasRainRate = true; }
  if (dps.containsKey("62")) { nextWeather.uv = dps["62"].as<float>(); nextWeather.hasUv = true; }
  if (dps.containsKey("64")) { nextWeather.dewPoint = dps["64"].as<float>() / 10.0; nextWeather.hasDewPoint = true; }
  if (dps.containsKey("65")) { nextWeather.feelsLike = dps["65"].as<float>() / 10.0; nextWeather.hasFeelsLike = true; }
  if (dps.containsKey("66")) { nextWeather.heatIndex = dps["66"].as<float>() / 10.0; nextWeather.hasHeatIndex = true; }
  // DP 135 is 0.01 klux. Convert to lux: raw * 0.01 * 1000 = raw * 10.
  if (dps.containsKey("135")) { nextWeather.light = dps["135"].as<float>() * 10.0; nextWeather.hasLight = true; }

  nextWeather.valid = nextWeather.hasOutdoorTemp && nextWeather.hasOutdoorHumidity;
  nextWeather.source = "tuya_local_3.4";
  nextWeather.updatedMs = millis();
  weather = nextWeather;

  if (weather.valid) {
    Serial.print("Tuya Local OK air_temp=");
    Serial.print(weather.airTemp);
    Serial.print(" hum=");
    Serial.print(weather.humidity);
    Serial.print(" pressure=");
    Serial.print(weather.pressure);
    Serial.print(" rain24h=");
    Serial.print(weather.rain24h);
    Serial.print(" uv=");
    Serial.println(weather.uv);
  } else {
    Serial.println("Tuya Local DPS missing outdoor temperature or humidity.");
  }

  return weather.valid;
}

bool fetchTuyaTokenCloud() {
  if (!ensureWiFi()) return false;
  if (time(nullptr) < 1700000000 && !waitForTime()) return false;

  const String path = "/v1.0/token?grant_type=1";
  const String timestamp = tuyaTimestampMs();
  WiFiClientSecure client;
  client.setInsecure();
  HTTPClient http;
  http.begin(client, String(TUYA_ENDPOINT) + path);
  http.addHeader("client_id", TUYA_CLIENT_ID);
  http.addHeader("sign", tuyaSign(path, timestamp));
  http.addHeader("t", timestamp);
  http.addHeader("sign_method", "HMAC-SHA256");
  int code = http.GET();
  String response = http.getString();
  http.end();

  DynamicJsonDocument doc(4096);
  DeserializationError jsonError = deserializeJson(doc, response);
  if (code != 200 || jsonError || doc["success"] != true) {
    Serial.print("Tuya Cloud token failed HTTP: ");
    Serial.println(code);
    return false;
  }
  tuyaAccessToken = doc["result"]["access_token"].as<String>();
  unsigned long expires = doc["result"]["expire_time"] | 7200UL;
  tuyaTokenExpireMs = millis() + (expires > 300 ? expires - 300 : expires) * 1000UL;
  return tuyaAccessToken.length() > 0;
}

bool fetchTuyaWeatherCloud() {
  if (tuyaAccessToken.length() == 0 || (long)(millis() - tuyaTokenExpireMs) >= 0) {
    if (!fetchTuyaTokenCloud()) return false;
  }

  String path = "/v2.0/cloud/thing/" + String(TUYA_DEVICE_ID) +
                "/shadow/properties?codes=" + String(TUYA_CODES);
  String timestamp = tuyaTimestampMs();
  WiFiClientSecure client;
  client.setInsecure();
  HTTPClient http;
  http.begin(client, String(TUYA_ENDPOINT) + path);
  http.addHeader("client_id", TUYA_CLIENT_ID);
  http.addHeader("access_token", tuyaAccessToken);
  http.addHeader("sign", tuyaSign(path, timestamp, tuyaAccessToken));
  http.addHeader("t", timestamp);
  http.addHeader("sign_method", "HMAC-SHA256");
  int code = http.GET();
  String response = http.getString();
  http.end();

  DynamicJsonDocument doc(8192);
  DeserializationError jsonError = deserializeJson(doc, response);
  if (code != 200 || jsonError || doc["success"] != true) {
    Serial.print("Tuya Cloud weather failed HTTP: ");
    Serial.println(code);
    if (code == 401 || code == 1106) tuyaAccessToken = "";
    return false;
  }

  WeatherData nextWeather;
  for (JsonObject item : doc["result"]["properties"].as<JsonArray>()) {
    String dp = item["code"].as<String>();
    float value = item["value"].as<float>();
    if (dp == "temp_current") { nextWeather.airTemp = value / 10.0; nextWeather.hasAirTemp = true; }
    else if (dp == "humidity_value") { nextWeather.humidity = value; nextWeather.hasHumidity = true; }
    else if (dp == "temp_current_external") { nextWeather.outdoorTemp = value / 10.0; nextWeather.hasOutdoorTemp = true; }
    else if (dp == "humidity_outdoor") { nextWeather.outdoorHumidity = value; nextWeather.hasOutdoorHumidity = true; }
    else if (dp == "atmospheric_pressture") { nextWeather.pressure = value; nextWeather.hasPressure = true; }
    else if (dp == "windspeed_avg") { nextWeather.windAvg = value / 10.0; nextWeather.hasWindAvg = true; }
    else if (dp == "windspeed_gust") { nextWeather.windGust = value / 10.0; nextWeather.hasWindGust = true; }
    else if (dp == "rain_1h") { nextWeather.rain1h = value / 10.0; nextWeather.hasRain1h = true; }
    else if (dp == "rain_24h") { nextWeather.rain24h = value / 10.0; nextWeather.hasRain24h = true; }
    else if (dp == "rain_rate") { nextWeather.rainRate = value / 10.0; nextWeather.hasRainRate = true; }
    else if (dp == "uv_index") { nextWeather.uv = value; nextWeather.hasUv = true; }
    else if (dp == "dew_point_temp") { nextWeather.dewPoint = value / 10.0; nextWeather.hasDewPoint = true; }
    else if (dp == "feellike_temp") { nextWeather.feelsLike = value / 10.0; nextWeather.hasFeelsLike = true; }
    else if (dp == "heat_index") { nextWeather.heatIndex = value / 10.0; nextWeather.hasHeatIndex = true; }
    else if (dp == "Light_intensity") { nextWeather.light = value * 10.0; nextWeather.hasLight = true; }
  }
  nextWeather.valid = nextWeather.hasOutdoorTemp && nextWeather.hasOutdoorHumidity;
  nextWeather.source = "tuya_cloud_fallback";
  nextWeather.updatedMs = millis();
  weather = nextWeather;
  if (weather.valid) {
    Serial.print("Tuya Cloud fallback OK outdoor_temp=");
    Serial.print(weather.outdoorTemp);
    Serial.print(" humidity=");
    Serial.println(weather.outdoorHumidity);
  }
  return weather.valid;
}

bool fetchTuyaWeather() {
  if (ENABLE_TUYA_LOCAL && fetchTuyaWeatherLocal()) return true;
  Serial.println("Using Tuya Cloud fallback");
  if (fetchTuyaWeatherCloud()) return true;
  weather = WeatherData();
  return false;
}

// =====================
// TMD FORECAST
// =====================
bool fetchTmdForecastPrimary() {
  if (!ensureWiFi()) return false;

  time_t now = time(nullptr);
  if (now < 1700000000 && !waitForTime()) return false;

  // Omitting date avoids the TMD API's contradictory date boundary validation.
  String url = String(TMD_ENDPOINT) +
               "?lat=" + String(FARM_LAT, 6) +
               "&lon=" + String(FARM_LON, 6) +
               "&fields=" + String(TMD_FIELDS) +
               "&duration=" + String(TMD_FORECAST_DAYS);

  WiFiClientSecure client;
  client.setInsecure();
  HTTPClient http;
  http.begin(client, url);
  http.addHeader("accept", "application/json");
  http.addHeader("authorization", "Bearer " + String(TMD_API_TOKEN_CURRENT));

  int code = http.GET();
  String res = http.getString();
  http.end();

  Serial.print("TMD forecast HTTP: ");
  Serial.println(code);
  if (code != 200) {
    Serial.println(res);
    return false;
  }

  DynamicJsonDocument doc(8192);
  DeserializationError err = deserializeJson(doc, res);
  if (err) {
    Serial.print("TMD JSON error: ");
    Serial.println(err.c_str());
    return false;
  }

  JsonArray days = doc["WeatherForecasts"][0]["forecasts"].as<JsonArray>();
  if (days.isNull()) {
    days = doc["weather_forecast"]["locations"][0]["forecasts"].as<JsonArray>();
  }
  int i = 0;
  bool gotAny = false;
  for (JsonObject item : days) {
    if (i >= 7) break;
    String timeValue = item["time"].as<String>();
    forecast[i].date = timeValue.substring(0, 10);
    forecast[i].tempMax = item["data"]["tc_max"] | 0.0;
    forecast[i].tempMin = item["data"]["tc_min"] | 0.0;
    forecast[i].humidity = item["data"]["rh"] | 0.0;
    forecast[i].rain = item["data"]["rain"] | 0.0;
    forecast[i].pressure = item["data"]["slp"] | 0.0;
    forecast[i].windSpeed = item["data"]["ws10m"] | 0.0;
    forecast[i].windDirection = item["data"]["wd10m"] | 0.0;
    forecast[i].cloudLow = item["data"]["cloudlow"] | 0.0;
    forecast[i].cloudMid = item["data"]["cloudmed"] | 0.0;
    forecast[i].cloudHigh = item["data"]["cloudhigh"] | 0.0;
    forecast[i].shortwave = item["data"]["swdown"] | 0.0;
    forecast[i].cond = item["data"]["cond"] | -1;
    forecast[i].valid = true;
    gotAny = true;
    i++;
  }

  for (; i < 7; i++) forecast[i].valid = false;
  forecastValid = gotAny;
  forecastUpdatedMs = millis();
  if (gotAny) forecastSource = "tmd";
  Serial.println(gotAny ? "TMD forecast OK" : "TMD forecast empty");
  return gotAny;
}

bool fetchOpenMeteoForecast() {
  if (!ensureWiFi()) return false;

  String url = String("https://api.open-meteo.com/v1/forecast") +
               "?latitude=" + String(FARM_LAT, 6) +
               "&longitude=" + String(FARM_LON, 6) +
               "&daily=weather_code,temperature_2m_max,temperature_2m_min," +
               "precipitation_sum,relative_humidity_2m_mean,wind_speed_10m_max," +
               "wind_direction_10m_dominant,shortwave_radiation_sum" +
               "&wind_speed_unit=ms&timezone=Asia%2FBangkok&forecast_days=7";

  WiFiClientSecure client;
  client.setInsecure();
  HTTPClient http;
  http.begin(client, url);
  http.addHeader("accept", "application/json");

  int code = http.GET();
  String res = http.getString();
  http.end();

  Serial.print("Open-Meteo forecast HTTP: ");
  Serial.println(code);
  if (code != 200) return false;

  DynamicJsonDocument doc(8192);
  DeserializationError err = deserializeJson(doc, res);
  if (err) {
    Serial.print("Open-Meteo JSON error: ");
    Serial.println(err.c_str());
    return false;
  }

  JsonArray dates = doc["daily"]["time"].as<JsonArray>();
  JsonArray maxTemps = doc["daily"]["temperature_2m_max"].as<JsonArray>();
  JsonArray minTemps = doc["daily"]["temperature_2m_min"].as<JsonArray>();
  JsonArray humidity = doc["daily"]["relative_humidity_2m_mean"].as<JsonArray>();
  JsonArray rain = doc["daily"]["precipitation_sum"].as<JsonArray>();
  JsonArray conditions = doc["daily"]["weather_code"].as<JsonArray>();
  JsonArray windSpeed = doc["daily"]["wind_speed_10m_max"].as<JsonArray>();
  JsonArray windDirection = doc["daily"]["wind_direction_10m_dominant"].as<JsonArray>();
  JsonArray shortwave = doc["daily"]["shortwave_radiation_sum"].as<JsonArray>();

  int count = min(7, (int)dates.size());
  for (int i = 0; i < count; i++) {
    forecast[i].date = dates[i].as<String>();
    forecast[i].tempMax = maxTemps[i] | 0.0;
    forecast[i].tempMin = minTemps[i] | 0.0;
    forecast[i].humidity = humidity[i] | 0.0;
    forecast[i].rain = rain[i] | 0.0;
    forecast[i].windSpeed = windSpeed[i] | 0.0;
    forecast[i].windDirection = windDirection[i] | 0.0;
    forecast[i].shortwave = shortwave[i] | 0.0;
    forecast[i].cond = conditions[i] | -1;
    forecast[i].valid = true;
  }
  for (int i = count; i < 7; i++) forecast[i].valid = false;

  forecastValid = count > 0;
  forecastUpdatedMs = millis();
  if (forecastValid) forecastSource = "open_meteo";
  Serial.println(forecastValid ? "Open-Meteo forecast OK" : "Open-Meteo forecast empty");
  return forecastValid;
}

bool fetchTmdForecast() {
  if (fetchTmdForecastPrimary()) return true;
  Serial.println("TMD unavailable; using Open-Meteo fallback");
  return fetchOpenMeteoForecast();
}

bool fetchTmdHourlyPrimary() {
  if (!ensureWiFi()) return false;

  String url = String(TMD_HOURLY_ENDPOINT) +
               "?lat=" + String(FARM_LAT, 6) +
               "&lon=" + String(FARM_LON, 6) +
               "&fields=" + String(TMD_HOURLY_FIELDS) +
               "&duration=" + String(TMD_FORECAST_HOURS);

  WiFiClientSecure client;
  client.setInsecure();
  HTTPClient http;
  http.begin(client, url);
  http.addHeader("accept", "application/json");
  http.addHeader("authorization", "Bearer " + String(TMD_API_TOKEN_CURRENT));

  int code = http.GET();
  String res = http.getString();
  http.end();
  Serial.print("TMD hourly HTTP: ");
  Serial.println(code);
  if (code != 200) return false;

  DynamicJsonDocument doc(24576);
  if (deserializeJson(doc, res)) return false;

  JsonArray hours = doc["WeatherForcasts"][0]["forecasts"].as<JsonArray>();
  if (hours.isNull()) hours = doc["WeatherForecasts"][0]["forecasts"].as<JsonArray>();
  if (hours.isNull()) hours = doc["weather_forecast"]["locations"][0]["forecasts"].as<JsonArray>();

  int i = 0;
  for (JsonObject item : hours) {
    if (i >= 48) break;
    hourlyForecast[i].time = item["time"].as<String>();
    hourlyForecast[i].temperature = item["data"]["tc"] | 0.0;
    hourlyForecast[i].humidity = item["data"]["rh"] | 0.0;
    hourlyForecast[i].pressure = item["data"]["slp"] | 0.0;
    hourlyForecast[i].rain = item["data"]["rain"] | 0.0;
    hourlyForecast[i].windSpeed = item["data"]["ws10m"] | 0.0;
    hourlyForecast[i].windDirection = item["data"]["wd10m"] | 0.0;
    hourlyForecast[i].cloudLow = item["data"]["cloudlow"] | 0.0;
    hourlyForecast[i].cloudMid = item["data"]["cloudmed"] | 0.0;
    hourlyForecast[i].cloudHigh = item["data"]["cloudhigh"] | 0.0;
    hourlyForecast[i].cond = item["data"]["cond"] | -1;
    hourlyForecast[i].valid = true;
    i++;
  }
  for (int j = i; j < 48; j++) hourlyForecast[j].valid = false;
  hourlyForecastValid = i > 0;
  hourlyForecastUpdatedMs = millis();
  if (hourlyForecastValid) hourlyForecastSource = "tmd";
  Serial.println(hourlyForecastValid ? "TMD hourly OK" : "TMD hourly empty");
  return hourlyForecastValid;
}

bool fetchOpenMeteoHourly() {
  if (!ensureWiFi()) return false;
  String url = String("https://api.open-meteo.com/v1/forecast") +
               "?latitude=" + String(FARM_LAT, 6) +
               "&longitude=" + String(FARM_LON, 6) +
               "&hourly=temperature_2m,relative_humidity_2m,pressure_msl,precipitation," +
               "wind_speed_10m,wind_direction_10m,cloud_cover_low,cloud_cover_mid," +
               "cloud_cover_high,weather_code&wind_speed_unit=ms" +
               "&timezone=Asia%2FBangkok&forecast_hours=48";

  WiFiClientSecure client;
  client.setInsecure();
  HTTPClient http;
  http.begin(client, url);
  int code = http.GET();
  String res = http.getString();
  http.end();
  Serial.print("Open-Meteo hourly HTTP: ");
  Serial.println(code);
  if (code != 200) return false;

  DynamicJsonDocument doc(24576);
  if (deserializeJson(doc, res)) return false;
  JsonObject h = doc["hourly"];
  JsonArray times = h["time"].as<JsonArray>();
  int count = min(48, (int)times.size());
  for (int i = 0; i < count; i++) {
    hourlyForecast[i].time = times[i].as<String>();
    hourlyForecast[i].temperature = h["temperature_2m"][i] | 0.0;
    hourlyForecast[i].humidity = h["relative_humidity_2m"][i] | 0.0;
    hourlyForecast[i].pressure = h["pressure_msl"][i] | 0.0;
    hourlyForecast[i].rain = h["precipitation"][i] | 0.0;
    hourlyForecast[i].windSpeed = h["wind_speed_10m"][i] | 0.0;
    hourlyForecast[i].windDirection = h["wind_direction_10m"][i] | 0.0;
    hourlyForecast[i].cloudLow = h["cloud_cover_low"][i] | 0.0;
    hourlyForecast[i].cloudMid = h["cloud_cover_mid"][i] | 0.0;
    hourlyForecast[i].cloudHigh = h["cloud_cover_high"][i] | 0.0;
    hourlyForecast[i].cond = h["weather_code"][i] | -1;
    hourlyForecast[i].valid = true;
  }
  for (int i = count; i < 48; i++) hourlyForecast[i].valid = false;
  hourlyForecastValid = count > 0;
  hourlyForecastUpdatedMs = millis();
  if (hourlyForecastValid) hourlyForecastSource = "open_meteo";
  Serial.println(hourlyForecastValid ? "Open-Meteo hourly OK" : "Open-Meteo hourly empty");
  return hourlyForecastValid;
}

bool fetchHourlyForecast() {
  if (fetchTmdHourlyPrimary()) return true;
  Serial.println("TMD hourly unavailable; using Open-Meteo fallback");
  return fetchOpenMeteoHourly();
}

// =====================
// AGROMONITORING NDVI
// =====================
bool fetchNdvi() {
  if (!ensureWiFi()) return false;

  time_t now = time(nullptr);
  if (now < 1700000000 && !waitForTime()) return false;

  unsigned long startTs = (unsigned long)now - AGRO_LOOKBACK_SEC;
  String url = String(AGRO_ENDPOINT) +
               "?polyid=" + String(AGRO_POLYID) +
               "&start=" + String(startTs) +
               "&end=" + String((unsigned long)now) +
               "&appid=" + String(AGRO_APPID);

  WiFiClientSecure client;
  client.setInsecure();
  HTTPClient http;
  http.begin(client, url);
  int code = http.GET();
  String res = http.getString();
  http.end();

  Serial.print("NDVI HTTP: ");
  Serial.println(code);
  if (code != 200) {
    Serial.println(res);
    return false;
  }

  StaticJsonDocument<256> filter;
  filter[0]["dt"] = true;
  filter[0]["source"] = true;
  filter[0]["cl"] = true;
  filter[0]["data"]["mean"] = true;
  filter[0]["data"]["min"] = true;
  filter[0]["data"]["max"] = true;
  filter[0]["data"]["median"] = true;

  DynamicJsonDocument doc(8192);
  DeserializationError err = deserializeJson(
    doc, res, DeserializationOption::Filter(filter)
  );
  if (err) {
    Serial.print("NDVI JSON error: ");
    Serial.println(err.c_str());
    return false;
  }

  JsonArray entries = doc.as<JsonArray>();
  JsonObject latest;
  unsigned long latestDt = 0;
  for (JsonObject item : entries) {
    unsigned long dt = item["dt"] | 0UL;
    if (dt > latestDt) {
      latestDt = dt;
      latest = item;
    }
  }

  ndviUpdatedMs = millis();
  if (latestDt == 0) {
    ndvi.valid = false;
    Serial.println("NDVI history empty");
    return false;
  }

  ndvi.mean = latest["data"]["mean"] | 0.0;
  ndvi.minVal = latest["data"]["min"] | 0.0;
  ndvi.maxVal = latest["data"]["max"] | 0.0;
  ndvi.median = latest["data"]["median"] | 0.0;
  ndvi.cloudCoverage = latest["cl"] | 0.0;
  ndvi.captureDt = latestDt;
  ndvi.source = latest["source"].as<String>();
  ndvi.valid = true;
  Serial.println("NDVI OK");
  return true;
}

// =====================
// SOIL SENSOR MODBUS RTU
// =====================
uint16_t modbusCrc16(const uint8_t* data, size_t length) {
  uint16_t crc = 0xFFFF;
  for (size_t i = 0; i < length; ++i) {
    crc ^= data[i];
    for (uint8_t bit = 0; bit < 8; ++bit) {
      crc = (crc & 1) ? (crc >> 1) ^ 0xA001 : crc >> 1;
    }
  }
  return crc;
}

bool readSoilSensor() {
  // Exact request from the original working soil sender. Do not reduce this
  // to the four-register example from the generic sensor manual: this probe
  // also supplies N, P and K in registers 0004H-0006H.
  static const uint8_t request[] = {
    0x01, 0x03, 0x00, 0x00, 0x00, 0x07, 0x04, 0x08
  };

  while (soilSerial.available()) soilSerial.read();
  soilSerial.write(request, sizeof(request));
  soilSerial.flush();
  Serial.println("Soil Modbus TX: 01 03 00 00 00 07 04 08");

  // Collect the complete response and scan it for a valid frame. A larger
  // buffer also tolerates a converter that echoes bytes before the reply.
  uint8_t response[64];
  size_t received = 0;
  unsigned long startedAt = millis();
  while (millis() - startedAt < 1500 && received < sizeof(response)) {
    while (soilSerial.available() && received < sizeof(response)) {
      response[received++] = soilSerial.read();
    }
    delay(1);
  }

  Serial.printf("Soil Modbus RX (%u bytes): ", (unsigned)received);
  for (size_t i = 0; i < received; ++i) Serial.printf("%02X ", response[i]);
  Serial.println();

  for (size_t offset = 0; offset + 19 <= received; ++offset) {
    uint8_t* frame = response + offset;
    if (frame[0] != SOIL_ADDRESS || frame[1] != 0x03 || frame[2] != 0x0E) continue;

    uint16_t calculatedCrc = modbusCrc16(frame, 17);
    uint16_t receivedCrc = frame[17] | (uint16_t(frame[18]) << 8);
    if (calculatedCrc != receivedCrc) continue;

    auto reg = [&](uint8_t index) -> uint16_t {
      uint8_t pos = 3 + index * 2;
      return (uint16_t(frame[pos]) << 8) | frame[pos + 1];
    };

    soil.moisture = reg(0) / 10.0f;
    soil.temp = int16_t(reg(1)) / 10.0f;
    soil.ec = reg(2);
    soil.ph = reg(3) / 10.0f;
    soil.n = reg(4);
    soil.p = reg(5);
    soil.k = reg(6);
    soil.valid = true;
    soil.updatedMs = millis();

    Serial.printf("Soil OK: moisture=%.1f%% temp=%.1fC EC=%d pH=%.1f N=%d P=%d K=%d\n",
                  soil.moisture, soil.temp, soil.ec, soil.ph,
                  soil.n, soil.p, soil.k);
    return true;
  }

  soil.valid = false;
  Serial.println("Soil RS485 failed: no valid 19-byte Modbus frame");
  return false;
}

// =====================
// COMBINED JSON / SEND
// =====================
String buildCombinedJson() {
  DynamicJsonDocument doc(forecastsPendingUpload ? 32768 : 6144);

  doc["device_id"] = "farm_gateway_s3";
  doc["location_id"] = "farm-main";
  doc["polygon_id"] = AGRO_POLYID;
  doc["uptime_ms"] = millis();

  time_t now = scheduledRecordedAt > 0 ? scheduledRecordedAt : time(nullptr);
  if (now >= 1700000000) {
    struct tm utc;
    gmtime_r(&now, &utc);
    char isoTime[25];
    strftime(isoTime, sizeof(isoTime), "%Y-%m-%dT%H:%M:%SZ", &utc);
    doc["recorded_at"] = isoTime;
    doc["event_id"] = String("farm_gateway_s3:") + String((unsigned long)now);
  }

  JsonObject s = doc.createNestedObject("soil");
  s["valid"] = soil.valid;
  s["moisture_percent"] = soil.moisture;
  s["temperature_c"] = soil.temp;
  s["ec"] = soil.ec;
  s["ph"] = soil.ph;
  s["n"] = soil.n;
  s["p"] = soil.p;
  s["k"] = soil.k;
  s["age_sec"] = ageSec(soil.valid, soil.updatedMs);

  JsonObject w = doc.createNestedObject("weather");
  w["valid"] = weather.valid;
  w["age_sec"] = ageSec(weather.valid, weather.updatedMs);
  w["source"] = weather.source;
  w["wind_unit"] = "km/h";
  w["light_unit"] = "lux";

  if (weather.hasAirTemp) w["air_temperature_c"] = weather.airTemp;
  if (weather.hasHumidity) w["humidity_percent"] = weather.humidity;
  if (weather.hasOutdoorTemp) w["outdoor_temperature_c"] = weather.outdoorTemp;
  if (weather.hasOutdoorHumidity) w["outdoor_humidity_percent"] = weather.outdoorHumidity;
  if (weather.hasPressure) w["pressure_hpa"] = weather.pressure;
  if (weather.hasWindAvg) w["wind_avg"] = weather.windAvg;
  if (weather.hasWindGust) w["wind_gust"] = weather.windGust;
  if (weather.hasRain1h) w["rain_1h_mm"] = weather.rain1h;
  if (weather.hasRain24h) w["rain_24h_mm"] = weather.rain24h;
  if (weather.hasRainRate) w["rain_rate_mm_h"] = weather.rainRate;
  if (weather.hasUv) w["uv_index"] = weather.uv;
  if (weather.hasDewPoint) w["dew_point_c"] = weather.dewPoint;
  if (weather.hasFeelsLike) w["feels_like_c"] = weather.feelsLike;
  if (weather.hasHeatIndex) w["heat_index_c"] = weather.heatIndex;
  if (weather.hasLight) w["light_lux"] = weather.light;

  if (forecastsPendingUpload) {
    doc["forecast_valid"] = forecastValid;
    doc["forecast_age_sec"] = ageSec(forecastValid, forecastUpdatedMs);
    doc["forecast_source"] = forecastSource;
    JsonArray fc = doc.createNestedArray("forecast_7day");
    for (int i = 0; i < 7; i++) {
      if (!forecast[i].valid) continue;
      JsonObject day = fc.createNestedObject();
      day["date"] = forecast[i].date;
      day["temp_max_c"] = forecast[i].tempMax;
      day["temp_min_c"] = forecast[i].tempMin;
      day["humidity_percent"] = forecast[i].humidity;
      day["rain_mm"] = forecast[i].rain;
      day["pressure_hpa"] = forecast[i].pressure;
      day["wind_speed_ms"] = forecast[i].windSpeed;
      day["wind_direction_deg"] = forecast[i].windDirection;
      day["cloud_low_percent"] = forecast[i].cloudLow;
      day["cloud_mid_percent"] = forecast[i].cloudMid;
      day["cloud_high_percent"] = forecast[i].cloudHigh;
      day["shortwave"] = forecast[i].shortwave;
      day["cond"] = forecast[i].cond;
    }

    doc["hourly_forecast_valid"] = hourlyForecastValid;
    doc["hourly_forecast_source"] = hourlyForecastSource;
    JsonArray hourly = doc.createNestedArray("forecast_hourly");
    for (int i = 0; i < 48; i++) {
      if (!hourlyForecast[i].valid) continue;
      JsonObject hour = hourly.createNestedObject();
      hour["time"] = hourlyForecast[i].time;
      hour["temperature_c"] = hourlyForecast[i].temperature;
      hour["humidity_percent"] = hourlyForecast[i].humidity;
      hour["pressure_hpa"] = hourlyForecast[i].pressure;
      hour["rain_mm"] = hourlyForecast[i].rain;
      hour["wind_speed_ms"] = hourlyForecast[i].windSpeed;
      hour["wind_direction_deg"] = hourlyForecast[i].windDirection;
      hour["cloud_low_percent"] = hourlyForecast[i].cloudLow;
      hour["cloud_mid_percent"] = hourlyForecast[i].cloudMid;
      hour["cloud_high_percent"] = hourlyForecast[i].cloudHigh;
      hour["cond"] = hourlyForecast[i].cond;
    }
  }

  JsonObject n = doc.createNestedObject("ndvi");
  n["valid"] = ndvi.valid;
  n["age_sec"] = ageSec(ndvi.valid, ndviUpdatedMs);
  if (ndvi.valid) {
    n["mean"] = ndvi.mean;
    n["min"] = ndvi.minVal;
    n["max"] = ndvi.maxVal;
    n["median"] = ndvi.median;
    n["cloud_coverage"] = ndvi.cloudCoverage;
    n["source"] = ndvi.source;
    n["captured_epoch"] = ndvi.captureDt;
  }

  String json;
  serializeJson(doc, json);
  return json;
}

bool postJson(const char* label, const String& url, const String& json, bool addDeviceHeader) {
  if (!ensureWiFi()) {
    Serial.print(label);
    Serial.println(" skipped: WiFi not connected");
    return false;
  }

  WiFiClientSecure client;
  client.setInsecure();
  client.setTimeout(45000);

  HTTPClient http;
  http.begin(client, url);
  const bool isGoogleSheets = strcmp(label, "Google Sheets") == 0;
  // Google Apps Script redirects the POST and may take longer than the
  // library's short default timeout, especially with weak farm Wi-Fi.
  http.setConnectTimeout(15000);
  http.setTimeout(45000);
  // Apps Script runs doPost() and then redirects to the response page. Do not
  // POST the JSON again to googleusercontent; the original /exec POST already
  // reached the sheet script when the 3xx response is returned.
  http.setFollowRedirects(isGoogleSheets
      ? HTTPC_DISABLE_FOLLOW_REDIRECTS
      : HTTPC_FORCE_FOLLOW_REDIRECTS);
  http.addHeader("Content-Type", "application/json");
  if (addDeviceHeader) {
    http.addHeader("x-device-key", DEVICE_INGEST_KEY);
  }

  int code = http.POST(json);
  String res = http.getString();
  http.end();

  Serial.print(label);
  Serial.print(" HTTP: ");
  Serial.println(code);
  if (res.length() > 0) {
    Serial.println(res);
  }

  if (isGoogleSheets && code >= 300 && code < 400) {
    Serial.println("Google Sheets POST accepted (redirect not followed)");
    return true;
  }
  return code >= 200 && code < 300;
}

bool forwardCombinedData(const String& json) {
  bool ok = true;
  if (ENABLE_SUPABASE && String(SUPABASE_INGEST_URL).length() > 0) {
    ok = postJson("Supabase", SUPABASE_INGEST_URL, json, true) && ok;
  }

  if (ENABLE_GOOGLE_SHEETS && String(GOOGLE_SHEETS_URL).length() > 0) {
    String sheetsUrl = String(GOOGLE_SHEETS_URL) + "?key=" + DEVICE_INGEST_KEY;
    ok = postJson("Google Sheets", sheetsUrl, json, false) && ok;
  }
  return ok;
}

void sendCombinedData() {
  String json = buildCombinedJson();

  Serial.println("Combined JSON ready:");
  Serial.println(json);

  if (forwardCombinedData(json) && forecastsPendingUpload) forecastsPendingUpload = false;
}

bool requestFreshSoilReading(time_t slotTime) {
  (void)slotTime;
  return readSoilSensor();
}

// =====================
// SETUP / LOOP
// =====================
void setup() {
  Serial.begin(115200);
  unsigned long serialStart = millis();
  while (!Serial && millis() - serialStart < 3000) {
  }

  Serial.println();
  Serial.println("=== S3 RS485 SOIL + WIFI + TUYA LOCAL GATEWAY ===");

  soilSerial.begin(SOIL_BAUD, SERIAL_8N1, SOIL_RX_PIN, SOIL_TX_PIN);
  Serial.printf("Soil RS485 ready: RX=GPIO%d TX=GPIO%d baud=%lu address=%u\n",
                SOIL_RX_PIN, SOIL_TX_PIN, (unsigned long)SOIL_BAUD, SOIL_ADDRESS);

  ensureWiFi();
  waitForTime();

  Serial.println("Startup soil test (not uploaded)");
  readSoilSensor();

  fetchTuyaWeather();

  fetchTmdForecast();
  fetchHourlyForecast();
  forecastsPendingUpload = true;

  fetchNdvi();

  time_t now = time(nullptr);
  if (now >= 1700000000) {
    struct tm localNow;
    localtime_r(&now, &localNow);
    int dateKey = (localNow.tm_year + 1900) * 1000 + localNow.tm_yday;
    lastForecastDateKey = dateKey;
    lastNdviDateKey = dateKey;
    // Do not create a backdated row immediately after boot. Start at the next
    // exact 15-minute boundary instead.
    lastUploadSlot = (long long)now / 900LL;
  }
}

void runClockAlignedSchedule() {
  time_t now = time(nullptr);
  if (now < 1700000000) return;

  struct tm localNow;
  localtime_r(&now, &localNow);
  int dateKey = (localNow.tm_year + 1900) * 1000 + localNow.tm_yday;

  // Refresh forecasts once per local day at/after 06:00. Setup performs the
  // first refresh immediately, then following days stay aligned to 06:00.
  if (localNow.tm_hour == 6 && lastForecastDateKey != dateKey) {
    lastForecastDateKey = dateKey;
    fetchTmdForecast();
    fetchHourlyForecast();
    forecastsPendingUpload = true;
  }

  // NDVI is intentionally offset by five minutes so the external APIs are not
  // all called at the same instant.
  if (localNow.tm_hour == 6 && localNow.tm_min >= 5 && lastNdviDateKey != dateKey) {
    lastNdviDateKey = dateKey;
    fetchNdvi();
  }

  long long slot = (long long)now / 900LL;
  if (slot == lastUploadSlot) return;
  lastUploadSlot = slot;

  // The row timestamp is the exact boundary (:00, :15, :30, :45), even if
  // network work completes a few seconds later.
  scheduledRecordedAt = (time_t)(slot * 900LL);
  if (!requestFreshSoilReading(scheduledRecordedAt)) {
    // Keep the clock-aligned cloud row even when this Modbus read fails.
    // valid=false distinguishes it from a successful fresh soil sample.
    soil.valid = false;
    Serial.println("Soil unavailable; uploading scheduled row with soil.valid=false");
  }
  fetchTuyaWeather();
  sendCombinedData();
  scheduledRecordedAt = 0;
}

void loop() {
  // USB diagnostic command: send T to read the soil sensor immediately.
  while (Serial.available() > 0) {
    char command = (char)Serial.read();
    if (command == 'T' || command == 't') {
      Serial.println("Manual soil RS485 test requested");
      if (readSoilSensor()) {
        Serial.println("Manual soil test PASSED (not uploaded)");
      } else {
        Serial.println("Manual soil test FAILED");
      }
    }
  }

  runClockAlignedSchedule();
  delay(10);
}
