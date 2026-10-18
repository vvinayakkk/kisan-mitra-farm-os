import { ProvenanceBadge } from "@/components/assistant/DataStatus";
import { lazy, Suspense, useEffect, useState } from "react";
import {
  ArrowLeft,
  Layers,
  Leaf,
  Minus,
  Plus,
  RotateCcw,
  RotateCw,
  Tag,
  X,
  Box,
} from "lucide-react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { MitraHelper } from "@/components/assistant/MitraHelper";
import { FloatingAssistant } from "@/components/assistant/FloatingAssistant";
import {
  demoTelemetry,
  fetchStation,
  reading,
  sensors,
  type SensorId,
} from "@/components/overview/stationData";
import "./SystemOverview.css";
const WeatherStation = lazy(
  () => import("@/components/overview/WeatherStation"),
);
export default function SystemOverview({
  embedded = false,
}: {
  embedded?: boolean;
}) {
  const [selected, setSelected] = useState<SensorId | null>(null);
  const [readingGroup, setReadingGroup] = useState("all");
  const [autoRotate, setAutoRotate] = useState(false);
  const [exploded, setExploded] = useState(false);
  const [labels, setLabels] = useState(true);
  const [view, setView] = useState("perspective");
  const [reset, setReset] = useState(0);
  const [zoom, setZoom] = useState(0);
  const [demo, setDemo] = useState(false);
  const [motion, setMotion] = useState(
    () => !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  const [now, setNow] = useState(Date.now());
  const query = useQuery({
    queryKey: ["overview-station"],
    queryFn: fetchStation,
    refetchInterval: 10000,
    retry: false,
  });
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSelected(null);
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  const age = query.data
    ? Math.max(0, Math.floor((now - Date.parse(query.data.timestamp)) / 1000))
    : null;
  const elapsed =
    age === null
      ? ""
      : age < 60
        ? `${age}s ago`
        : age < 3600
          ? `${Math.floor(age / 60)} min ago`
          : age < 86400
            ? `${Math.floor(age / 3600)} hours ago`
            : `${Math.floor(age / 86400)} days ago`;
  const synthetic = query.data?.provenance?.origin === "synthetic" || query.data?.provenance?.lane === "demo";
  const status = demo || synthetic
    ? "Station"
    : query.isError
      ? "Offline"
      : query.isPending
        ? "Connecting"
        : age !== null && age > 60
          ? "Stale"
          : "Live";
  const data = demo ? demoTelemetry : (query.data ?? null);
  const sensor = sensors.find((s) => s.id === selected);
  const resetView = () => {
    setSelected(null);
    setZoom(0);
    setView("perspective");
    setReset((n) => n + 1);
  };
  return (
    <main className={`station-explorer ${embedded ? "station-embedded" : ""}`}>
      {!embedded && (
        <header className="explorer-header">
          <Link to="/dashboard" className="explorer-brand">
            <span className="brand-symbol">
              <Leaf size={19} />
            </span>
            SkyView<span className="brand-ai">AI</span>
          </Link>
          <span className="header-location">Your farm station</span>
          <Link to="/workspace" className="header-mitra">
            <Leaf size={14} /> Farm assistant
          </Link>
          <Link
            to="/dashboard"
            className="back-dashboard"
            aria-label="Dashboard"
          >
            <ArrowLeft size={16} />
          </Link>
        </header>
      )}
      <section className="explorer-stage" aria-label="Interactive farm station">
        <div className="stage-heading">
          <div className="eyebrow">AGRISENSE WS01</div>
          <h1>A closer look at your land.</h1>
          <p>Tap a part to see what it does.</p>
        </div>
        <div className="stage-status">
          {!demo && query.data?.provenance && <ProvenanceBadge value={query.data.provenance} />}
          <span className={`status-dot ${status.toLowerCase()}`} />
          {demo || synthetic
            ? "Station readings"
            : status === "Live"
              ? "Live · " + elapsed
              : status === "Stale"
                ? "Last reading · " + elapsed
                : status === "Offline"
                  ? "Station offline"
                  : "Connecting"}
        </div>
        <div className="three-viewport">
          <Suspense
            fallback={
              <div className="scene-message">Preparing your station…</div>
            }
          >
            <WeatherStation
              selected={selected}
              onSelect={setSelected}
              autoRotate={autoRotate}
              motion={motion}
              exploded={exploded}
              labels={labels}
              view={view}
              reset={reset}
              zoom={zoom}
              data={data}
              sensorMotion={demo || synthetic || status === "Live"}
            />
          </Suspense>
        </div>
        <div className="station-readings" aria-label="Field readings">
          <label style={{fontSize:10}}>Readings<select aria-label="Station reading group" value={readingGroup} onChange={e=>setReadingGroup(e.target.value)}><option value="all">All readings</option><option value="soil">Soil</option><option value="weather">Weather</option></select></label>
          {[
            [
              "Temperature",
              data?.temperature == null ? "—" : data.temperature + "°C",
            ],
            ["Soil moisture", reading("soilSensor", data)],
            ["Wind", reading("anemometer", data)],
            ["Rain", reading("rainGauge", data)],
          ].filter(([name]) => readingGroup === "all" || (readingGroup === "soil" ? name === "Soil moisture" : name !== "Soil moisture")).map(([name, value]) => (
            <div key={name}>
              <span>{name}</span>
              <strong>{value}</strong>
            </div>
          ))}
        </div>
        {selected && (
          <div className="station-part-card" role="status">
            <span className="part-icon">
              <Box size={19} />
            </span>
            <div>
              <strong>
                {sensor?.name ?? "Station base"}
                <span>
                  {sensor ? reading(sensor.id, data) : "AgriSense WS01"}
                </span>
              </strong>
              <p>
                {sensor?.description ??
                  "The sturdy base keeps all your station components mounted together."}
              </p>
            </div>
            <button
              aria-label="Clear selection"
              onClick={() => setSelected(null)}
            >
              <X size={15} />
            </button>
          </div>
        )}
        <div className="station-controls">
          <div className="view-switch">
            {["perspective", "front", "top"].map((v) => (
              <button
                key={v}
                className={view === v ? "active" : ""}
                aria-pressed={view === v}
                onClick={() => setView(v)}
              >
                {v === "perspective"
                  ? "Overview"
                  : v === "front"
                    ? "Front"
                    : "Top"}
              </button>
            ))}
          </div>
          <div className="scene-toolbar">
            <button
              aria-label="Reset view"
              title="Reset view"
              onClick={resetView}
            >
              <RotateCcw size={16} />
            </button>
            <button
              aria-label="Zoom in"
              title="Zoom in"
              disabled={zoom >= 3}
              onClick={() => setZoom((n) => n + 1)}
            >
              <Plus size={16} />
            </button>
            <button
              aria-label="Zoom out"
              title="Zoom out"
              disabled={zoom <= 0}
              onClick={() => setZoom((n) => n - 1)}
            >
              <Minus size={16} />
            </button>
            <span />
            <button
              className={autoRotate ? "active" : ""}
              aria-label="Auto rotate"
              title="Auto rotate"
              aria-pressed={autoRotate}
              onClick={() => setAutoRotate((v) => !v)}
            >
              <RotateCw size={16} />
            </button>
            <button
              className={labels ? "active" : ""}
              aria-label="Show labels"
              title="Show labels"
              aria-pressed={labels}
              onClick={() => setLabels((v) => !v)}
            >
              <Tag size={16} />
            </button>
            <button
              className={exploded ? "active" : ""}
              aria-label="Exploded assembly"
              title="Exploded assembly"
              aria-pressed={exploded}
              onClick={() => {
                setSelected(null);
                setExploded((v) => !v);
              }}
            >
              <Layers size={16} />
            </button>
          </div>
        </div>
        <div className="station-options">
          <label>
            <input
              type="checkbox"
              checked={demo}
              onChange={(e) => setDemo(e.target.checked)}
            />
            Local station
          </label>
          <label>
            <input
              type="checkbox"
              checked={motion}
              onChange={(e) => setMotion(e.target.checked)}
            />
            Motion
          </label>
        </div>
        <div className="stage-hint">Drag to look around · Scroll to zoom</div>
      </section>
      {embedded ? (
        <MitraHelper
          context="station"
          collapsible
          className="station-mitra-helper"
        />
      ) : (
        <FloatingAssistant />
      )}
    </main>
  );
}
