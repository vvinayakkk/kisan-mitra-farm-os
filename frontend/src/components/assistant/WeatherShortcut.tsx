import { useQuery } from "@tanstack/react-query";
import { CloudSun } from "lucide-react";
import { workspaceRequest } from "@/lib/farmWorkspaceClient";

type Forecast = { available: boolean; forecast?: { records?: { temperature_max_c?: number | null; temperature_min_c?: number | null; rainfall_mm?: number | null }[] }; live?: { daily?: Record<string, (number | string | null)[]> } | null };

export function WeatherShortcut({ onOpen }: { onOpen: () => void }) {
  const { data } = useQuery({
    queryKey: ["workspace-weather-shortcut"],
    queryFn: () => workspaceRequest<Forecast>("/api/weather/dashboard"),
    staleTime: 15 * 60 * 1000,
    refetchOnWindowFocus: false,
    retry: false,
  });
  const today = data?.available ? data.forecast?.records?.[0] : null;
  const live = data?.live?.daily;
  const value = (key: string, fallback: number | null | undefined) => typeof live?.[key]?.[0] === "number" ? live[key][0] as number : fallback;
  const highValue = value("temperature_2m_max", today?.temperature_max_c);
  const lowValue = value("temperature_2m_min", today?.temperature_min_c);
  const rainValue = value("precipitation_sum", today?.rainfall_mm);
  const high = typeof highValue === "number" ? `${Math.round(highValue)}°` : "—";
  const low = typeof lowValue === "number" ? `${Math.round(lowValue)}°` : "—";
  const rain = typeof rainValue === "number" ? `${Math.round(rainValue)} mm` : "—";
  return <button className="workspace-weather-shortcut" onClick={onOpen} aria-label={`Farm weather, high ${high}, low ${low}, rain ${rain}`}>
    <CloudSun size={15} aria-hidden="true" /><span>Weather</span>{today && <strong>{high} / {low} <i>·</i> {rain}</strong>}
  </button>;
}
