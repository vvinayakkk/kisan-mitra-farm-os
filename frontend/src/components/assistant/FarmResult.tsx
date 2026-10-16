import { ResearchSources, type ResearchResult } from "./ResearchSources";
import { localPresentation } from "@/lib/localPresentation";
import { ProvenanceBadge, type Provenance } from "./DataStatus";
import { useState } from "react";
import { FileText, Download, Pencil } from "lucide-react";
import { downloadArtifact, sendAssistant, type Artifact } from "@/lib/assistantClient";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
interface Chart {
  type?: string;
  kind?: "market" | "weather_forecast" | "weather_history" | "budget";
  caption?: string;
  value_name?: string;
  title: string;
  unit: string;
  points: { date: string; value: number }[];
}
function FileResult({ artifact }: { artifact: Artifact }) {
  const [error, setError] = useState("");
  return (
    <div className="message-file-result">
      <button
        onClick={() => {
          setError("");
          void downloadArtifact(artifact).catch((e) =>
            setError(
              e instanceof Error
                ? e.message
                : "This download could not finish.",
            ),
          );
        }}
      >
        <FileText size={16} />
        <span>
          <strong>{artifact.title}</strong>
          <small>{artifact.format.toUpperCase()} · Ready to download</small>
        </span>
        <Download size={15} />
      </button>
      <button className="artifact-revise" onClick={() => void sendAssistant(`Help me revise the file “${artifact.title}” (file ID ${artifact.file_id}). Ask me what I would like to change, then create a new version preserving the original.`)}><Pencil size={13}/> Revise {artifact.revision && artifact.revision > 1 ? `· version ${artifact.revision}` : ""}</button>
      {artifact.preview && (
        <details
          className={`artifact-preview artifact-preview-${artifact.format}`}
          open
        >
          <summary>
            Preview · {artifact.preview.partial ? "excerpt" : "content"}
          </summary>
          <div className="artifact-preview-paper">
            <h3>{artifact.preview.title}</h3>
            {artifact.preview.sections.map((section, i) => (
              <section key={i}>
                <h4>{section.heading}</h4>
                <p>{section.text}</p>
              </section>
            ))}
            {artifact.preview.columns.length > 0 && (
              <div className="artifact-preview-table">
                <table>
                  <thead>
                    <tr>
                      {artifact.preview.columns.map((column, i) => (
                        <th key={i}>{column}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {artifact.preview.rows.map((row, i) => (
                      <tr key={i}>
                        {row.map((cell, j) => (
                          <td key={j}>{cell ?? "—"}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {artifact.preview.row_count > artifact.preview.rows.length && (
              <small>
                Showing {artifact.preview.rows.length} of{" "}
                {artifact.preview.row_count} rows
              </small>
            )}
          </div>
          <small className="artifact-preview-caption">
            Content preview · Download for the full formatted file
          </small>
        </details>
      )}
      {error && (
        <p role="alert" className="mitra-error">
          {error}
        </p>
      )}
    </div>
  );
}
export function FarmResult({ result }: { result: Record<string, unknown> }) {
  if ("search_suggestions_html" in result || ("sources" in result && "retrieved_at" in result && "query" in result)) return <ResearchSources result={result as ResearchResult}/>;
  if (result.artifact)
    return <FileResult artifact={result.artifact as Artifact} />;
  const chart = result.chart as Chart | undefined;
  const provenance = result.provenance as Provenance | undefined;
  if (
    !chart ||
    !Array.isArray(chart.points) ||
    chart.points.length < (chart.type === "bar" ? 1 : 2)
  )
    return null;
  const weather = chart.kind === "weather_forecast" || chart.kind === "weather_history";
  const caption = chart.caption || (weather ? chart.kind === "weather_forecast" ? "Issued weather forecast" : "Grid weather history / reanalysis" : chart.type === "bar" ? "Calculated from your inputs" : provenance?.origin === "synthetic" ? localPresentation ? "Market price history" : "Simulated market history" : provenance?.origin === "scenario" ? "Planning scenario" : provenance?.origin === "forecast" ? "Price forecast" : "Dated market records");
  const valueName = chart.value_name || (weather ? "Rainfall" : chart.type === "bar" ? "Cost" : "Modal price");
  const note = weather ? chart.kind === "weather_forecast" ? "Model forecast, not station readings or guaranteed rainfall." : "Grid observations or reanalysis, not farm sensor or soil measurements." : chart.type === "bar" ? "Calculated costs" : provenance?.origin === "synthetic" || provenance?.origin === "scenario" ? localPresentation ? "Compare the date, variety and unit before choosing a market." : "Fictional planning data, not actual mandi offers." : "Prices are dated records, not guaranteed offers.";
  const ChartComponent = chart.type === "bar" ? BarChart : LineChart;
  return (
    <figure className="inline-farm-chart">
      <strong>{chart.title}</strong> <ProvenanceBadge value={provenance} />
      <p>
        {chart.unit} · {caption}
      </p>
      <ResponsiveContainer width="100%" height={210}>
        <ChartComponent
          data={chart.points}
          margin={{ top: 12, right: 15, bottom: 8, left: 0 }}
        >
          <CartesianGrid
            stroke="#bdcdb0"
            strokeDasharray="3 5"
            vertical={false}
          />
          <XAxis dataKey="date" tick={{ fontSize: 10 }} minTickGap={30} />
          <YAxis
            tick={{ fontSize: 10 }}
            width={52}
            domain={chart.type === "bar" ? [0, "auto"] : ["auto", "auto"]}
          />
          <Tooltip
            contentStyle={{
              borderRadius: 12,
              borderColor: "#aabf98",
              fontSize: 12,
            }}
          />
          {chart.type === "bar" ? (
            <Bar
              dataKey="value"
              name={valueName}
              fill="#6c8e50"
              radius={[5, 5, 0, 0]}
              isAnimationActive={false}
            />
          ) : (
            <Line
              type="linear"
              dataKey="value"
              name={valueName}
              stroke="#51763a"
              strokeWidth={2.5}
              dot={chart.points.length <= 30 ? { r: 3 } : false}
              activeDot={{ r: 4 }}
              isAnimationActive={false}
            />
          )}
        </ChartComponent>
      </ResponsiveContainer>
      <figcaption>
        <p>
          {String(result.source ?? "")} ·{" "}
          {note}
        </p>
      </figcaption>
    </figure>
  );
}
