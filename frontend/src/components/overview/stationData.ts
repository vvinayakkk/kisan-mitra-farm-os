import type { Provenance } from "@/components/assistant/DataStatus";
import { apiFetch } from "@/lib/apiClient";
export const sensors = [
  {
    id: "windVane",
    name: "Wind direction",
    category: "Atmosphere",
    description:
      "The vane aligns with airflow to track the direction wind is coming from.",
    spec: "Directional vane · 16 compass points",
    position: [-2.5, 3, 0],
    label: [-2.5, 4.7, 0],
    exploded: [-3.2, 4, 0],
  },
  {
    id: "anemometer",
    name: "Wind speed",
    category: "Atmosphere",
    description:
      "Three cups rotate around a spindle. Rotation frequency is converted into wind speed.",
    spec: "Cup anemometer · km/h",
    position: [2.5, 3, 0],
    label: [2.5, 4.7, 0],
    exploded: [3.2, 4, 0],
  },
  {
    id: "rainGauge",
    name: "Rainfall",
    category: "Atmosphere",
    description:
      "A collector directs rain into a tipping bucket. Each tip contributes to accumulated rainfall.",
    spec: "Tipping bucket · mm",
    position: [-1.8, 0.4, 1.2],
    label: [-2, 1.9, 1.4],
    exploded: [-3, 1.5, 2],
  },
  {
    id: "controller",
    name: "ESP32 controller",
    category: "Processing",
    description:
      "Collects measurements from the sensor array and sends packets to the platform through the station radio link.",
    spec: "ESP32 · Wi-Fi / LoRa architecture",
    position: [0.8, 0.2, -0.2],
    label: [0.8, 1.3, -0.7],
    exploded: [1, 1.5, -2],
  },
  {
    id: "lcd",
    name: "Status display",
    category: "Interface",
    description:
      "An on-site display for station readings. Here it shows the current temperature when telemetry is available.",
    spec: "Local readout · temperature",
    position: [0, 0.2, 1.5],
    label: [0, 1.1, 2.2],
    exploded: [0, 1.3, 3],
  },
  {
    id: "solarPanel",
    name: "Solar array",
    category: "Power",
    description:
      "Harvests solar energy to support the station power system. Charging information appears when reported by the device.",
    spec: "Photovoltaic module · voltage",
    position: [1.8, 0.2, 1.2],
    label: [2.1, 1.2, 2.5],
    exploded: [3, 1.3, 3],
  },
  {
    id: "soilSensor",
    name: "Soil moisture",
    category: "Soil",
    description:
      "The buried probe measures soil moisture to support irrigation decisions.",
    spec: "Soil probe · moisture %",
    position: [3.8, 0.2, 1.5],
    label: [4, 2.6, 1.5],
    exploded: [5, 1, 1],
  },
] as const;
export type SensorId = (typeof sensors)[number]["id"] | "board";
export interface Telemetry {
  provenance?: Provenance;
  timestamp: string;
  windSpeed: number | null;
  windDirection: string | null;
  rainfall: number | null;
  soilMoisture: number | null;
  temperature: number | null;
  batteryVoltage: number | null;
  solarVoltage: number | null;
}
export const demoTelemetry: Telemetry = {
  timestamp: "",
  windSpeed: 12.3,
  windDirection: "NNE",
  rainfall: 2.5,
  soilMoisture: 42,
  temperature: 28.5,
  batteryVoltage: 12.8,
  solarVoltage: 5.2,
};
export function reading(id: SensorId, data?: Telemetry | null): string {
  if (!data || id === "board") return "—";
  const value =
    id === "windVane"
      ? data.windDirection
      : id === "anemometer"
        ? data.windSpeed
        : id === "rainGauge"
          ? data.rainfall
          : id === "soilSensor"
            ? data.soilMoisture
            : id === "controller"
              ? data.batteryVoltage
              : id === "lcd"
                ? data.temperature
                : data.solarVoltage;
  if (value === null || value === undefined) return "—";
  return `${value}${id === "windVane" ? "" : id === "anemometer" ? " km/h" : id === "rainGauge" ? " mm" : id === "soilSensor" ? "%" : id === "lcd" ? " °C" : " V"}`;
}
export async function fetchStation(): Promise<Telemetry> {
  const host = (
    import.meta.env.VITE_ASSISTANT_API_URL ??
    import.meta.env.VITE_API_URL ??
    ""
  ).replace(/\/$/, "");
  const station = import.meta.env.VITE_STATION_ID || "WS01";
  const response = await apiFetch(
    `${host}/api/assistant/station/${encodeURIComponent(station)}`,
    { signal: AbortSignal.timeout(8000) },
  );
  if (!response.ok) throw new Error("Station unavailable");
  const envelope = await response.json();
  if (envelope.available === false) throw new Error("No measured station data");
  const d = envelope.data ?? envelope;

  if (["mock", "demo", "fallback"].includes(d._source) && !d.provenance && !envelope.provenance && !d.data_origin)
    throw new Error("No measured station data");
  const timestamp =
    typeof d.timestamp === "string"
      ? d.timestamp.replace(" ", "T") +
        (/(Z|[+-]\d{2}:\d{2})$/.test(d.timestamp) ? "" : "Z")
      : "";
  if (!timestamp || !Number.isFinite(Date.parse(timestamp)))
    throw new Error("Invalid station timestamp");
  const number = (...keys: string[]) => {
    const v = keys.map((k) => d[k]).find((v) => v !== undefined && v !== null);
    return typeof v === "number" && Number.isFinite(v) ? v : null;
  };
  return {
    provenance: d.provenance ?? envelope.provenance ?? (d.data_origin ? typeof d.data_origin === "string" ? { origin: d.data_origin } : d.data_origin : undefined),
    timestamp,
    windSpeed: number("windSpeed", "wind_speed"),
    windDirection:
      typeof (d.windDirection ?? d.wind_direction) === "string"
        ? (d.windDirection ?? d.wind_direction)
        : null,
    rainfall: number("rainfall"),
    soilMoisture: number("soilMoisture", "soil_moisture"),
    temperature: number("temperature"),
    batteryVoltage: number("batteryVoltage", "battery_voltage"),
    solarVoltage: number("solarVoltage", "solar_voltage"),
  };
}
