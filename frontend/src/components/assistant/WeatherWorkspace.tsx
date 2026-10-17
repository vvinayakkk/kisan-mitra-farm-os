import { useEffect, useState } from "react";
import {
  ArrowUpRight, Cloud, CloudDrizzle, CloudLightning, CloudMoon, CloudRain,
  CloudSnow, CloudSun, Compass, Droplets, MapPin, Moon, RefreshCw, Search, Sun, Sunrise, Sunset,
  Thermometer, Wind,
} from "lucide-react";
import { workspaceRequest } from "@/lib/farmWorkspaceClient";
import { MitraHelper } from "./MitraHelper";
import { weatherPhase } from "./weatherPhase";
import "./weather-workspace.css";

type Series = Record<string, Array<string | number | null>>;
type ForecastDay = { valid_on: string; temperature_min_c?: number | null; temperature_max_c?: number | null; rainfall_mm?: number | null };
type City = { id: number; name: string; admin1: string; country: string };
type Dashboard = {
  available: boolean;
  message?: string;
  requires_farm_selection?: boolean;
  farm_choices?: { farm_key: string; name: string }[];
  city?: City;
  forecast?: { farm: string; farm_key: string; records: ForecastDay[]; provenance: { source: string; issued_at: string; stale?: boolean }; note: string };
  live?: { current: Record<string, number | string | null>; hourly: Series; daily: Series; air: Record<string, number | string | null> | null; air_grid?: (number | null)[]; captured_at: string; source: string; air_source: string | null; timezone?: string } | null;
  live_error?: string;
};

const number = (value: unknown) => typeof value === "number" && Number.isFinite(value) ? value : null;
const rounded = (value: unknown, suffix = "") => { const n = number(value); return n === null ? "—" : `${Math.round(n)}${suffix}`; };
const rainAmount = (value: unknown) => { const n = number(value); return n === null ? "—" : `${n > 0 && n < 1 ? n.toFixed(1) : Math.round(n)} mm`; };
function condition(code: unknown) {
  const n = number(code);
  if (n === null) return { label: "Forecast", icon: CloudSun };
  if (n >= 95) return { label: "Thunderstorms", icon: CloudLightning };
  if (n >= 85 && n < 90) return { label: "Snow showers", icon: CloudSnow };
  if (n >= 71 && n < 80) return { label: "Snow", icon: CloudSnow };
  if (n >= 61) return { label: "Rain", icon: CloudRain };
  if (n >= 51) return { label: "Drizzle", icon: CloudDrizzle };
  if (n >= 45) return { label: "Fog", icon: Cloud };
  if (n >= 1) return { label: "Cloudy spells", icon: CloudSun };
  return { label: "Clear sky", icon: Sun };
}
function clock(value: unknown, timezone = "Asia/Kolkata") {
  if (typeof value !== "string") return "—";
  const localTime = value.includes("T") && !value.endsWith("Z") && !/[+-]\d\d:\d\d$/.test(value);
  const date = new Date(localTime ? `${value}Z` : value);
  return Number.isNaN(date.getTime()) ? "—" : new Intl.DateTimeFormat("en-IN", { hour: "numeric", minute: "2-digit", timeZone: localTime ? "UTC" : timezone }).format(date);
}
function dayLabel(value: unknown) {
  if (typeof value !== "string") return "—";
  const date = new Date(`${value.slice(0, 10)}T00:00:00+05:30`);
  return Number.isNaN(date.getTime()) ? "—" : new Intl.DateTimeFormat("en-IN", { weekday: "short", day: "numeric", timeZone: "Asia/Kolkata" }).format(date);
}
function aqiText(value: unknown) {
  const n = number(value);
  if (n === null) return "Unavailable";
  if (n <= 50) return "Good";
  if (n <= 100) return "Moderate";
  if (n <= 150) return "Sensitive groups";
  if (n <= 200) return "Unhealthy";
  if (n <= 300) return "Very unhealthy";
  return "Hazardous";
}
function aqiColor(value: unknown) {
  const n = number(value);
  if (n === null) return "#dce7d8";
  if (n <= 50) return "#a8d3ae";
  if (n <= 100) return "#d9dd9f";
  if (n <= 150) return "#efcb94";
  if (n <= 200) return "#e8a491";
  return "#c88fa5";
}
function at(series: Series | undefined, key: string, index: number) { return series?.[key]?.[index] ?? null; }
const cityLabel = (city: City) => [city.name, city.admin1, city.country].filter(Boolean).join(", ");
const particles = Array.from({ length: 24 }, (_, index) => index);

export default function WeatherWorkspace({ onNavigate }: { onNavigate: (view: string) => void }) {
  const [farmKey, setFarmKey] = useState("");
  const [nearby, setNearby] = useState<{latitude: number; longitude: number} | null>(null);
  const [locating, setLocating] = useState(false);
  function useNearby() {
    if (!navigator.geolocation) { setError("Location is unavailable. Search for a city instead."); return; }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(position => {
      setSelectedCity(null); setCityQuery(""); setData(null);
      setNearby({latitude: Number(position.coords.latitude.toFixed(2)), longitude: Number(position.coords.longitude.toFixed(2))});
      setLocating(false);
    }, () => { setLocating(false); setError("Location was not available. You can still search for a city."); }, {timeout: 10000, maximumAge: 300000, enableHighAccuracy: false});
  }
  const [data, setData] = useState<Dashboard | null>(null);
  const [selectedCity, setSelectedCity] = useState<City | null>(null);
  const [cityData, setCityData] = useState<Dashboard | null>(null);
  const [cityQuery, setCityQuery] = useState("");
  const [cityResults, setCityResults] = useState<City[]>([]);
  const [citySearching, setCitySearching] = useState(false);
  const [farmOptions, setFarmOptions] = useState<{ farm_key: string; name: string }[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const [wallClock, setWallClock] = useState(() => new Date());
  useEffect(() => {
    const tick = () => setWallClock(new Date());
    const timer = window.setInterval(tick, 60_000);
    document.addEventListener("visibilitychange", tick);
    return () => { window.clearInterval(timer); document.removeEventListener("visibilitychange", tick); };
  }, []);
  useEffect(() => {
    if (selectedCity) return;
    const controller = new AbortController();
    setLoading(true);
    setError("");
    void workspaceRequest<Dashboard>(nearby ? `/api/weather/location-dashboard?latitude=${nearby.latitude}&longitude=${nearby.longitude}` : `/api/weather/dashboard${farmKey ? `?farm_key=${encodeURIComponent(farmKey)}` : ""}`, "GET", undefined, { signal: controller.signal, fresh: revision > 0 })
      .then(result => { if (!controller.signal.aborted) { setData(result); if (result.farm_choices?.length) setFarmOptions(result.farm_choices); } })
      .catch(reason => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Weather could not be loaded."); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [farmKey, revision, selectedCity, nearby]);

  useEffect(() => {
    const query = cityQuery.trim();
    if (query.length < 2 || selectedCity) { setCityResults([]); setCitySearching(false); return; }
    const controller = new AbortController();
    setCitySearching(true);
    const timer = window.setTimeout(() => {
      void workspaceRequest<{ cities: City[] }>(`/api/weather/cities?q=${encodeURIComponent(query)}`, "GET", undefined, { signal: controller.signal })
        .then(result => { if (!controller.signal.aborted) setCityResults(result.cities); })
        .catch(() => { if (!controller.signal.aborted) setCityResults([]); })
        .finally(() => { if (!controller.signal.aborted) setCitySearching(false); });
    }, 280);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [cityQuery, selectedCity]);

  useEffect(() => {
    if (!selectedCity) return;
    const controller = new AbortController();
    setCityData(null);
    setLoading(true);
    setError("");
    void workspaceRequest<Dashboard>(`/api/weather/city-dashboard?city_id=${selectedCity.id}`, "GET", undefined, { signal: controller.signal, fresh: revision > 0 })
      .then(result => { if (!controller.signal.aborted) setCityData(result); })
      .catch(reason => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "City weather could not be loaded."); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [selectedCity, revision]);

  const displayed = selectedCity ? cityData : data;
  const forecast = displayed?.forecast;
  const live = displayed?.live;
  const current = live?.current;
  const daily = live?.daily;
  const dateList = (daily?.time || forecast?.records.map(row => row.valid_on) || []) as string[];
  const days = dateList.slice(0, 10).map((date, index) => ({
    date,
    high: daily ? at(daily, "temperature_2m_max", index) : forecast?.records[index]?.temperature_max_c,
    low: daily ? at(daily, "temperature_2m_min", index) : forecast?.records[index]?.temperature_min_c,
    rain: daily ? at(daily, "precipitation_sum", index) : forecast?.records[index]?.rainfall_mm,
    probability: daily ? at(daily, "precipitation_probability_max", index) : null,
    code: daily ? at(daily, "weather_code", index) : null,
  }));
  const nowIndex = live?.hourly.time?.findIndex(value => String(value) >= String(current?.time || "")) ?? -1;
  const hours = nowIndex < 0 ? [] : (live?.hourly.time || []).slice(nowIndex, nowIndex + 12).map((time, i) => ({
    time,
    temperature: at(live?.hourly, "temperature_2m", nowIndex + i),
    probability: at(live?.hourly, "precipitation_probability", nowIndex + i),
    code: at(live?.hourly, "weather_code", nowIndex + i),
  }));
  const weather = condition(current?.weather_code ?? days[0]?.code);
  const code = number(current?.weather_code);
  const isNight = weatherPhase(wallClock, live?.timezone || "Asia/Kolkata", daily, current?.is_day) === "night";
  const isRain = (code !== null && ((code >= 51 && code <= 67) || (code >= 80 && code <= 82) || code >= 95)) || (number(current?.precipitation) || 0) > 0;
  const isSnow = code !== null && ((code >= 71 && code <= 77) || code === 85 || code === 86);
  const WeatherIcon = isNight && code !== null && code < 3 ? Moon : isNight && code !== null && code < 45 ? CloudMoon : weather.icon;
  const atmosphere = !current ? "calm" : isSnow ? isNight ? "snow-night" : "snow" : isRain ? isNight ? "rain-night" : "rain" : isNight ? "night" : "day";
  const high = days[0]?.high;
  const low = days[0]?.low;
  const issued = live?.captured_at || forecast?.provenance.issued_at;

  return <div className="farm-weather-page">
    <div className="farm-weather-layout">
      <aside className="farm-weather-farms" aria-label="Weather locations">
        <div className="farm-weather-side-heading"><CloudSun size={17} /><strong>Your weather</strong></div>
        <p>Regional outlook for your farm</p>
        {farmOptions.map(farm => <button key={farm.farm_key} className={!selectedCity && farmKey === farm.farm_key ? "selected" : ""} onClick={() => { setSelectedCity(null); setCityQuery(""); setFarmKey(farm.farm_key); }}>{farm.name}{!selectedCity && farmKey === farm.farm_key ? <span>{rounded(current?.temperature_2m, "°")}</span> : <ArrowUpRight size={14} />}</button>)}
        {data?.forecast && !farmOptions.length && <button className={!selectedCity ? "selected" : ""} onClick={() => { setSelectedCity(null); setCityQuery(""); setFarmKey(data.forecast?.farm_key || ""); }}>{data.forecast.farm}{!selectedCity && <span>{rounded(current?.temperature_2m, "°")}</span>}</button>}
        <div className="farm-weather-city-picker">
          <label htmlFor="weather-city-search"><Search size={15}/> Another city</label>
          <input id="weather-city-search" value={cityQuery} placeholder="Search any city" autoComplete="off" onChange={event => { setSelectedCity(null); setCityQuery(event.target.value); }} />
          {citySearching && <small>Looking up cities…</small>}
          {cityQuery.trim().length >= 2 && !selectedCity && !citySearching && !cityResults.length && <small>No cities found. Try city and state.</small>}
          {cityResults.length > 0 && <div className="farm-weather-city-results" role="listbox" aria-label="Matching cities">{cityResults.map(city => <button key={city.id} role="option" aria-selected={false} onClick={() => { setSelectedCity(city); setCityQuery(cityLabel(city)); setCityResults([]); }}><MapPin size={14}/><span>{city.name}<small>{[city.admin1, city.country].filter(Boolean).join(", ")}</small></span></button>)}</div>}
          {selectedCity && <button className="farm-weather-return" onClick={() => { setSelectedCity(null); setCityQuery(""); }}>Back to my farm</button>}
        </div>
        <MitraHelper context="weather" collapsible weatherCity={selectedCity ? cityLabel(selectedCity) : undefined} className="farm-weather-mitra" />
        <div className="farm-weather-side-note">Farm forecasts use an approximate regional grid. City views are regional forecasts too.</div>
      </aside>
      <div className="farm-weather-main">
        <div className="farm-weather-toolbar"><button disabled={locating} onClick={useNearby}>{locating ? "Finding your area…" : "Use my location"}</button>{nearby && <button onClick={() => {setNearby(null); setSelectedCity(null); setData(null);}}>Back to farm weather</button>}<span>{selectedCity ? "CITY WEATHER" : nearby ? "NEAR YOU" : "FARM WEATHER"}</span><button onClick={() => setRevision(n => n + 1)} disabled={loading}><RefreshCw size={15} className={loading ? "spin" : ""} /> Refresh</button></div>
        {loading && !displayed && <div className="farm-weather-loading">Getting the forecast…</div>}
        {error && <div className="farm-weather-message" role="alert">{error}</div>}
        {displayed?.requires_farm_selection && <div className="farm-weather-message">Select a farm to see its local outlook.</div>}
        {displayed && !displayed.available && !displayed.requires_farm_selection && <div className="farm-weather-message"><Cloud size={32} /><h2>Weather is waiting for your farm</h2><p>{displayed.message || "Link a plot to your farm’s weather grid to see the forecast."}</p><button onClick={() => onNavigate("records")}>Open farm notebook <ArrowUpRight size={15} /></button></div>}
        {forecast && <>
          <section className={`farm-weather-hero weather-${atmosphere}`} aria-label="Current weather">
            <div className="farm-weather-orbit orbit-one" /><div className="farm-weather-orbit orbit-two" />
            {(isNight || isRain || isSnow) && <div className={`farm-weather-particles ${isRain ? "weather-drops" : isSnow ? "weather-flakes" : "weather-stars"}`} aria-hidden="true">{particles.map(index => <i key={index} style={{ "--particle-x": `${(index * 37 + 13) % 97}%`, "--particle-y": `${(index * 23 + 7) % 78}%`, "--particle-delay": `${(index * 7) % 19 / 10}s`, "--particle-duration": `${1.1 + index % 5 * .21}s` } as React.CSSProperties} />)}</div>}
            <div className="farm-weather-hero-copy"><span className="farm-weather-eyebrow">{selectedCity ? "CITY OUTLOOK" : nearby ? "NEAR YOUR DEVICE" : "YOUR FARM"} · {selectedCity ? cityLabel(selectedCity) : forecast.farm}</span><div className="farm-weather-hero-temp"><WeatherIcon size={48} strokeWidth={1.4}/><strong>{rounded(current?.temperature_2m, "°")}</strong></div><h1>{current ? weather.label : "Daily outlook"}</h1><p>{current ? `Feels like ${rounded(current.apparent_temperature, "°")} · High ${rounded(high, "°")} · Low ${rounded(low, "°")}` : `High ${rounded(high, "°")} · Low ${rounded(low, "°")}`}</p></div>
            <div className="farm-weather-hero-bottom"><span>{current ? "Current regional model" : "Latest stored regional forecast"}</span><span>Updated {clock(issued, live?.timezone)}</span></div>
          </section>
          {displayed?.live_error && <p className="farm-weather-soft-note" role="status">{displayed.live_error}</p>}
          <div className="farm-weather-grid">
            <section className="farm-weather-card farm-weather-hourly"><div className="farm-weather-card-title"><CloudSun size={16}/> Next hours</div>{hours.length ? <div className="farm-weather-hour-strip">{hours.map((hour, i) => { const HourIcon = condition(hour.code).icon; return <div key={String(hour.time)}><span>{i === 0 ? "Now" : clock(hour.time, live?.timezone)}</span><HourIcon size={22}/><strong>{rounded(hour.temperature, "°")}</strong><small><Droplets size={11}/>{rounded(hour.probability, "%")}</small></div>; })}</div> : <p className="farm-weather-card-empty">Hourly outlook is temporarily unavailable.</p>}</section>
            <section className="farm-weather-card farm-weather-ten-day"><div className="farm-weather-card-title"><Sun size={16}/> 10-day forecast</div><div className="farm-weather-day-list">{days.map((day, i) => { const Icon = condition(day.code).icon; return <div key={day.date}><span>{i === 0 ? "Today" : dayLabel(day.date)}</span><Icon size={18}/><span className="farm-weather-rain"><Droplets size={12}/>{day.probability === null ? rainAmount(day.rain) : rounded(day.probability, "%")}</span><span className="farm-weather-range"><small>{rounded(day.low, "°")}</small><i style={{ width: `${Math.max(16, Math.min(100, ((Number(day.high || 0) - Number(day.low || 0)) / 18) * 100))}%` }}/><strong>{rounded(day.high, "°")}</strong></span></div>; })}</div></section>
            <div className="farm-weather-detail-grid">
              <section className="farm-weather-card"><div className="farm-weather-card-title"><Wind size={16}/> Wind</div><strong>{rounded(current?.wind_speed_10m, " km/h")}</strong><p>Gusts {rounded(current?.wind_gusts_10m, " km/h")}</p><div className="farm-weather-compass"><Compass size={25} style={{ transform: `rotate(${number(current?.wind_direction_10m) || 0}deg)` }}/><span>{rounded(current?.wind_direction_10m, "°")}</span></div></section>
              <section className="farm-weather-card"><div className="farm-weather-card-title"><Droplets size={16}/> Humidity</div><strong>{rounded(current?.relative_humidity_2m, "%")}</strong><p>Regional model estimate</p></section>
              <section className="farm-weather-card"><div className="farm-weather-card-title"><CloudRain size={16}/> Rain today</div><strong>{rainAmount(days[0]?.rain)}</strong><p>{days[0]?.probability === null ? "Daily forecast amount" : `${rounded(days[0]?.probability, "%")} highest chance`}</p></section>
              <section className="farm-weather-card"><div className="farm-weather-card-title"><Thermometer size={16}/> Feels like</div><strong>{rounded(current?.apparent_temperature, "°")}</strong><p>Current regional estimate</p></section>
              <section className="farm-weather-card"><div className="farm-weather-card-title"><Sunrise size={16}/> Sunrise</div><strong className="farm-weather-time">{clock(at(daily, "sunrise", 0), live?.timezone)}</strong><p><Sunset size={13}/> Sunset {clock(at(daily, "sunset", 0), live?.timezone)}</p></section>
              <section className="farm-weather-card"><div className="farm-weather-card-title"><Sun size={16}/> UV peak</div><strong>{rounded(at(daily, "uv_index_max", 0))}</strong><p>Forecast maximum today</p></section>
            </div>
            <section className="farm-weather-card farm-weather-air"><div className="farm-weather-card-title"><Wind size={16}/> Air quality</div><div className="farm-weather-air-row"><strong>{rounded(live?.air?.us_aqi)}</strong><span>{aqiText(live?.air?.us_aqi)}<small>US AQI · CAMS regional model</small></span></div>{live?.air_grid?.length === 9 && <div className="farm-weather-air-map" aria-label="Regional air quality around this location"><span className="farm-weather-map-north">N</span>{live.air_grid.map((aqi, index) => <i key={index} title={`Regional US AQI ${rounded(aqi)}`} style={{ backgroundColor: aqiColor(aqi) }}>{index === 4 && <b aria-label="Selected region">●</b>}</i>)}</div>}<div className="farm-weather-aqi-scale"/><p>PM2.5 {rounded(live?.air?.pm2_5, " µg/m³")} · PM10 {rounded(live?.air?.pm10, " µg/m³")}</p><small className="farm-weather-map-caption">Nearby model grid · regional view</small></section>
          </div>
          <footer className="farm-weather-footer"><span>Forecast from {live?.source || forecast.provenance.source} · {live?.air_source ? `${live.air_source} air quality · ` : ""}Captured {issued ? new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short", timeZone: live?.timezone || "Asia/Kolkata" }).format(new Date(issued)) : "—"}</span><p>Regional model estimates, not measurements at your field. Check local conditions before changing irrigation or spraying.</p></footer>
        </>}
      </div>
    </div>
  </div>;
}
