import { useState } from "react";
interface Plot {
  id: string;
  name?: string;
  latitude: number;
  longitude: number;
  area_ha: number;
  boundary_geojson?: {
    type: string;
    coordinates: number[][][] | number[][][][];
  } | null;
}

export function FieldMap({
  plots,
  onEdit,
}: {
  plots: Plot[];
  onEdit: (plot: Plot) => void;
}) {
  const [selected, setSelected] = useState("");
  const valid = plots.filter(
    (p) =>
      Number.isFinite(Number(p.latitude)) &&
      Number.isFinite(Number(p.longitude)),
  );
  if (!valid.length) return null;
  const rings = (p: Plot): number[][][] => {
    if (!p.boundary_geojson) return [];
    return p.boundary_geojson.type === "Polygon"
      ? (p.boundary_geojson.coordinates as number[][][])
      : (p.boundary_geojson.coordinates as number[][][][]).flat();
  };
  const coordinates = valid.flatMap((p) => [
    [Number(p.longitude), Number(p.latitude)],
    ...rings(p).flat(),
  ]);
  const xs = coordinates.map((c) => c[0]),
    ys = coordinates.map((c) => c[1]);
  const west = Math.min(...xs),
    east = Math.max(...xs),
    south = Math.min(...ys),
    north = Math.max(...ys);
  const longitudeFactor = Math.max(
    0.01,
    Math.cos((((south + north) / 2) * Math.PI) / 180),
  );
  const scale = Math.min(
    540 / ((east - west) * longitudeFactor || 0.001),
    140 / (north - south || 0.001),
  );
  const project = ([x, y]: number[]) => [
    300 + (x - (west + east) / 2) * longitudeFactor * scale,
    100 - (y - (south + north) / 2) * scale,
  ];
  return (
    <details className="farm-history field-map">
      <summary>Field map · {valid.length} saved locations</summary>
      <p>
        Local sketch from your saved coordinates. Outlines appear only when you
        supplied a boundary; marker locations do not prove a field’s extent. No
        satellite image or map provider is used.
      </p>
      <svg
        viewBox="0 0 600 200"
        role="img"
        aria-label="Sketch of your saved field positions"
      >
        <defs>
          <pattern
            id="field-map-grid"
            width="25"
            height="25"
            patternUnits="userSpaceOnUse"
          >
            <path
              d="M 25 0 L 0 0 0 25"
              fill="none"
              stroke="#d7dfce"
              strokeWidth=".6"
            />
          </pattern>
        </defs>
        <rect width="600" height="200" rx="12" fill="url(#field-map-grid)" />
        {valid.map((p, index) => {
          const [x, y] = project([Number(p.longitude), Number(p.latitude)]);
          return (
            <g key={p.id}>
              {rings(p).map((ring, i) => (
                <polygon
                  key={i}
                  points={ring.map((c) => project(c).join(",")).join(" ")}
                  fill="none"
                  stroke="#738b55"
                  strokeWidth="1"
                />
              ))}
              <circle
                cx={x}
                cy={y}
                r={selected === p.id ? 9 : 7}
                fill="#607c43"
              />
              <text x={x + 12} y={y + 5} fontSize="12" fill="#2f4728">
                {(p.name || `Field ${index + 1}`).slice(0, 36)}
              </text>
            </g>
          );
        })}
        <text x="574" y="20" fill="#758466" fontSize="10">
          N ↑
        </text>
      </svg>
      <div className="field-map-key">
        {valid.map((p, index) => (
          <button
            key={p.id}
            type="button"
            aria-pressed={selected === p.id}
            onClick={() => setSelected(p.id)}
          >
            {p.name || `Field ${index + 1}`} · {Number(p.area_ha)} ha
          </button>
        ))}
      </div>
      {valid.find((p) => p.id === selected) && (
        <button
          type="button"
          className="farm-text-action"
          onClick={() => onEdit(valid.find((p) => p.id === selected)!)}
        >
          Edit selected field
        </button>
      )}
    </details>
  );
}
