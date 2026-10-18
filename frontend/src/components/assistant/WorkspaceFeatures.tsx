import { CollectionFilters, useCollectionFilters } from "./CollectionFilters";
import { reportedMarketsOnly } from "@/lib/localPresentation";
import "./feature-form.css";
import "./feature-experiences.css";
import { apiFetch } from "@/lib/apiClient";
import { workspaceRequest } from "@/lib/farmWorkspaceClient";
import { ExportMenu } from "./ExportMenu";
import { FarmNotebook, notebookSections } from "./FarmNotebook";
import { FarmWorkspace, type NotebookTab } from "./FarmWorkspace";
import { WorkspaceVoiceField } from "@/components/WorkspaceVoiceField";
import { ProvenanceBadge, type Provenance } from "./DataStatus";
import { useEffect, useId, useRef, useState } from "react";
import {
  ArrowUpRight,
  Camera,
  Check,
  Download,
  FileText,
  Loader2,
  MapPin,
  Search,
  Sprout,
  Wallet,
  Handshake,
  Compass,
  FolderOpen,
  Sparkles,
  X,
} from "lucide-react";
import { MitraHelper } from "./MitraHelper";
import { PreparedBySaathi } from "./PreparedBySaathi";
import { FarmResult } from "./FarmResult";
import {
  inspectWorkspaceTool,
  uploadAttachment,
  useAssistant,
  type Artifact,
} from "@/lib/assistantClient";
import type { FarmContext } from "./suggestions";
export type FeatureView = "crops" | "markets" | "schemes" | "records";
const titles = {
  crops: [
    "CROP DOCTOR",
    "A little closer to a healthier crop.",
    "Start with a clear photo. Get a careful check, then decide your next step.",
  ],
  markets: [
    "YOUR MANDI COMPASS",
    "Find the market that works for you.",
    "Follow the price, compare your costs, and choose your next stop.",
  ],
  schemes: [
    "SUPPORT FOR YOUR FARM",
    "Your next opportunity, all in one folder.",
    "Find support, check what you need, and prepare with Mitra.",
  ],
  records: [
    "YOUR FARM NOTEBOOK",
    "Good records. A clearer season.",
    "Your reports, spreadsheets and saved costs, all in one quiet place.",
  ],
};
function FeatureSearchField({
  label,
  voiceLabel,
  value,
  onChange,
  placeholder,
  optional = false,
  required = false,
  busy = false,
  options = [],
}: {
  label: string;
  voiceLabel: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  optional?: boolean;
  required?: boolean;
  busy?: boolean;
  options?: string[];
}) {
  const id = useId();
  return (
    <div className="feature-search-field">
      <label htmlFor={id}>
        {label}
        {optional && <span>optional</span>}
      </label>
      <WorkspaceVoiceField
        label={voiceLabel}
        disabled={busy}
        onTranscript={onChange}
      >
        <input
          id={id}
          list={options.length ? `${id}-options` : undefined}
          autoComplete="off"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          maxLength={100}
          required={required}
        />
      </WorkspaceVoiceField>
      {options.length > 0 && <datalist id={`${id}-options`}>{options.map(option => <option key={option} value={option} />)}</datalist>}
    </div>
  );
}
function Failure({ message }: { message: string }) {
  return message ? (
    <p className="workspace-error" role="alert">
      {message}
    </p>
  ) : null;
}
function Quiet({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="workspace-empty">
      <Sprout size={25} />
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
function FeatureFrame({
  context,
  children,
  active = true,
}: {
  context: FarmContext;
  children: React.ReactNode;
  active?: boolean;
}) {
  return (
    <div className="feature-with-helper">
      <div className="feature-main">{(context === "markets" || context === "schemes" || context === "crops") && <PreparedBySaathi area={context} active={active} />}{children}</div>
      <aside className="feature-helper-side">
        <MitraHelper context={context} />
      </aside>
    </div>
  );
}
interface Diagnostic {
  bounding_boxes?: {x:number;y:number;width:number;height:number}[];
  bounding_box_explanation?: string;
  disease_name: string;
  crop_identified: string;
  confidence: number;
  description: string;
  symptoms: string[];
  solutions: { title: string; details: string; stage: string }[];
  prevention: string[];
}
function Crops({ active }: { active: boolean }) {
  const input = useRef<HTMLInputElement>(null);
  const [photo, setPhoto] = useState("");
  const [fileId, setFileId] = useState("");
  const [result, setResult] = useState<Diagnostic | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const actionFilter = useCollectionFilters(result?.solutions || [], item => `${item.title} ${item.details}`, item => item.stage);
  const operation = useRef(0);
  useEffect(
    () => () => {
      if (photo) URL.revokeObjectURL(photo);
    },
    [photo],
  );
  async function choose(file?: File) {
    if (!file || busy) return;
    const current = ++operation.current;
    setBusy(true);
    setError("");
    setResult(null);
    setFileId("");
    try {
      const attachment = await uploadAttachment(file);
      if (current === operation.current) {
        setPhoto(URL.createObjectURL(file));
        setFileId(attachment.id);
      }
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "This photo could not be uploaded.",
      );
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }
  async function diagnose() {
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const data = await inspectWorkspaceTool<{ diagnostic: Diagnostic }>(
        "diagnose_crop",
        { file_id: fileId },
      );
      setResult(data.diagnostic);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "This crop check could not finish.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <FeatureFrame context="crops" active={active}>
      <div className="feature-split">
        <section className="feature-card crop-photo-card">
          <div className="feature-card-heading">
            <span>01 / THE PHOTO</span>
            <Camera size={18} />
          </div>
          <input
            ref={input}
            type="file"
            hidden
            accept="image/jpeg,image/png,image/webp"
            onChange={(e) => void choose(e.target.files?.[0])}
          />
          <button
            className={`crop-photo ${photo ? "has-photo" : ""}`}
            onClick={() => input.current?.click()}
            disabled={busy}
            aria-label="Choose crop photo"
          >
            {photo ? (
              <span className="crop-annotated-photo" style={{position:"relative",display:"block",width:"100%",lineHeight:0}}>
                <img src={photo} alt="Crop photo selected for inspection" style={{display:"block",height:"auto",maxHeight:"none",width:"100%"}} />
                {!!result?.bounding_boxes?.length && <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="Areas identified in the crop assessment" style={{position:"absolute",inset:0,width:"100%",height:"100%",pointerEvents:"none"}}>
                  {result.bounding_boxes.map((box,i)=><rect key={i} x={box.x} y={box.y} width={box.width} height={box.height} fill="rgba(245,158,11,.12)" stroke="#f59e0b" strokeWidth=".5" />)}
                </svg>}
              </span>
            ) : (
              <>
                <Camera size={35} />
                <strong>A leaf tells a story.</strong>
                <span>Choose a clear crop photo</span>
                <small>JPEG, PNG or WebP · up to 5 MB</small>
              </>
            )}
          </button>
          <div className="crop-photo-actions">
            <button
              className="feature-secondary"
              onClick={() => input.current?.click()}
              disabled={busy}
            >
              {photo ? "Change photo" : "Choose photo"}
            </button>
            <button
              className="feature-primary"
              disabled={!fileId || busy}
              onClick={() => void diagnose()}
            >
              {busy ? (
                <>
                  <Loader2 size={16} className="spin" />{" "}
                  {fileId ? "Checking…" : "Uploading…"}
                </>
              ) : (
                "Check this crop"
              )}
            </button>
          </div>
          <p className="feature-footnote">
            Use daylight. Keep the affected leaf in focus and include a little
            healthy tissue.
          </p>
        </section>
        <section className="feature-card">
          <div className="feature-card-heading">
            <span>02 / THE CHECK</span>
            <Sprout size={18} />
          </div>
          <Failure message={error} />
          {result ? (
            <div className="crop-diagnostic">
              <ExportMenu
                filename="crop-photo-assessment"
                rows={[result]}
                note="AI photo assessment; not a lab diagnosis. Check the recorded uncertainty and consult a local agronomist before treatment."
              />
              <span className="feature-source">
                Photo assessment · {result.crop_identified}
              </span>
              <h2>{result.disease_name}</h2>
              <p>{result.description}</p>
              <span className="diagnostic-confidence">
                Model confidence {Math.round(result.confidence)}% · a photo
                assessment, not lab confirmation
              </span>
              {result.confidence > 0 && result.symptoms?.length > 0 && (
                <>
                  <h3>What to look for</h3>
                  <ul>
                    {result.symptoms.map((text, i) => (
                      <li key={i}>{text}</li>
                    ))}
                  </ul>
                </>
              )}
              <CollectionFilters control={actionFilter} label="Crop care steps" />
              {result.confidence > 0 &&
                actionFilter.items.map((solution, i) => (
                  <div className="crop-action" key={i}>
                    <span>{solution.stage}</span>
                    <h3>{solution.title}</h3>
                    <p>{solution.details}</p>
                  </div>
                ))}
              <p className="feature-footnote">
                Confirm uncertain symptoms with a local agronomist before
                treatment.
              </p>
            </div>
          ) : (
            <Quiet
              title={
                busy
                  ? fileId
                    ? "Taking a careful look…"
                    : "Getting your photo ready…"
                  : "Let’s start with the leaf."
              }
            >
              {busy
                ? fileId
                  ? "Checking what is visible in your photo. Your result will appear here."
                  : "Your photo is uploading. The crop check starts after it is ready."
                : "Your result will explain what is visible, what is uncertain and what to check next."}
            </Quiet>
          )}
        </section>
      </div>
    </FeatureFrame>
  );
}
interface MarketRow {
  provenance?: Provenance;
  market?: string;
  state?: string;
  district?: string;
  arrival_date?: string;
  commodity?: string;
  variety?: string;
  modal_price?: string | number;
  min_price?: string | number;
  max_price?: string | number;
  unit?: string;
}
function marketKey(row: MarketRow) {
  return [row.market, row.state, row.district, row.commodity, row.variety, row.unit, row.arrival_date].join("|");
}
function comparablePrice(row: MarketRow) {
  const unit = (row.unit || "quintal").replace(/^INR\//i, "").trim().toLowerCase();
  return ["quintal", "quintals", "qtl", "100 kg"].includes(unit) && row.modal_price !== "" && row.modal_price != null && Number.isFinite(Number(row.modal_price)) && Number(row.modal_price) >= 0;
}
const rupees = (value: number) => `₹${value.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
function MarketComparison({ rows, onRemove }: { rows: MarketRow[]; onRemove: (key: string) => void }) {
  const [quantity, setQuantity] = useState("10");
  const [costs, setCosts] = useState<Record<string, { transport: string; fees: string }>>({});
  const amount = Number(quantity);
  const positiveQuantity = quantity.trim() !== "" && Number.isFinite(amount) && amount > 0;
  const comparisons = rows.map(row => {
    const key = marketKey(row), cost = costs[key] || { transport: "", fees: "" };
    const entered = positiveQuantity && [cost.transport, cost.fees].every(value => value.trim() !== "" && Number.isFinite(Number(value)) && Number(value) >= 0);
    return { row, key, cost, net: entered ? amount * Number(row.modal_price) - Number(cost.transport) - Number(cost.fees) : null };
  });
  const complete = comparisons.length >= 2 && comparisons.every(item => item.net !== null);
  const best = complete ? Math.max(...comparisons.map(item => item.net!)) : null;
  return <section className="mandi-comparison" aria-label="Compare take-home amount">
    <div className="compass-heading"><div><span className="experience-eyebrow"><Compass size={15} /> YOUR TAKE-HOME COMPARISON</span><h2>A good price is only half the story.</h2><p>Choose up to three mandis below. Add the costs for your whole trip.</p></div><label>Harvest to sell <span><input type="number" min="0.01" step="0.01" value={quantity} onChange={event => setQuantity(event.target.value)} aria-label="Quantity to sell in quintals" /> quintals</span></label></div>
    {!positiveQuantity && <p role="alert" className="workspace-error">Enter a quantity greater than zero.</p>}
    {rows.length ? <div className="comparison-stops">{comparisons.map(({ row, key, cost, net }) => <article className={complete && net === best ? "comparison-stop is-best" : "comparison-stop"} key={key}>
      <header><div><strong>{row.market}</strong><small>{row.state} · {row.arrival_date || "Date unavailable"}</small><small>{row.variety || row.commodity || "Variety not supplied"} · {rupees(Number(row.modal_price))}/quintal</small></div><button type="button" aria-label={`Remove ${row.market} from comparison`} onClick={() => onRemove(key)}><X size={15} /></button></header>
      <div className="comparison-costs">{(["transport", "fees"] as const).map(field => <label key={field}>{field === "transport" ? "Transport · ₹" : "Other charges · ₹"}<input type="number" min="0" step="1" placeholder="Enter cost" aria-label={`${row.market} ${field}`} value={cost[field]} onChange={event => setCosts(previous => ({ ...previous, [key]: { ...cost, [field]: event.target.value } }))} /></label>)}</div>
      <footer><span>{complete && net === best ? "Highest estimated return" : "Estimated take-home"}</span><strong>{net === null ? "Add your costs" : rupees(net)}</strong></footer>
    </article>)}</div> : <p className="comparison-invitation"><MapPin size={18} /> Use “Compare take-home” on a mandi to begin.</p>}
    {rows.length > 0 && <p className="feature-footnote">Price × quantity − transport − other charges. Enter 0 when a cost does not apply. Compare the same variety and quality; dated prices are estimates, not confirmed offers.</p>}
  </section>;
}
interface MarketCatalogue { commodities: string[]; states: string[]; markets: { id: string; name: string; state: string; district?: string; data_origin?: string; source_url?: string; has_price_series?: boolean }[]; as_of_date?: string }
const apiBase = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
function useMarketCatalogue(active: boolean, commodity = "", state = "") {
  const [catalogue, setCatalogue] = useState<MarketCatalogue>({ commodities: [], states: [], markets: [] });
  useEffect(() => {
    if (!active) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      const params = new URLSearchParams({ commodity: reportedMarketsOnly ? "" : commodity, state, limit: "200", observed_only: String(reportedMarketsOnly) });
      void apiFetch(`${apiBase}/api/mandi/catalogue?${params}`, { signal: controller.signal }).then(async response => {
        if (!response.ok) return;
        const data = await response.json();
        if (!controller.signal.aborted) setCatalogue(data);
      }).catch(() => {});
    }, 180);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [active, commodity, state]);
  return catalogue;
}
function Markets({ active }: { active: boolean }) {
  const [commodity, setCommodity] = useState("Wheat"),
    [state, setState] = useState("");
  const [market, setMarket] = useState("");
  const [comparison, setComparison] = useState<MarketRow[]>([]);
  const catalogue = useMarketCatalogue(active, commodity, state);
  const operation = useRef(0);
  const loaded = useRef(false);
  const [visibleMarkets, setVisibleMarkets] = useState(9);
  const [prices, setPrices] = useState<{
    records?: MarketRow[];
    source?: string;
    provenance?: Provenance;
    message?: string;
  } | null>(null);
  const [trend, setTrend] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [searched, setSearched] = useState("");
  async function search(e?: React.FormEvent, selectedMarket = market) {
    e?.preventDefault();
    if (!commodity.trim()) return;
    const current = ++operation.current;
    setBusy(true);
    setVisibleMarkets(9);
    setError("");
    setPrices(null);
    setTrend(null);
    setComparison([]);
    setSearched(commodity.trim());
    const args = { observed_only: reportedMarketsOnly, commodity: commodity.trim(), state: state.trim(), ...(selectedMarket.trim() ? { market: selectedMarket.trim() } : {}) };
    const results = await Promise.allSettled([
      inspectWorkspaceTool<{
        records?: MarketRow[];
        source?: string;
        message?: string;
      }>("market_prices", args),
      inspectWorkspaceTool("market_trend", args),
    ]);
    if (current !== operation.current) return;
    if (results[0].status === "fulfilled") {
      const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date());
      const part = (type: string) => parts.find(value => value.type === type)?.value;
      const today = `${part("year")}-${part("month")}-${part("day")}`;
      const value = results[0].value;
      setPrices({ ...value, records: value.records?.filter(row => !row.arrival_date || row.arrival_date.slice(0, 10) <= today) });
    }
    if (results[1].status === "fulfilled") setTrend(results[1].value);
    const failures = results.filter(
      (r): r is PromiseRejectedResult => r.status === "rejected",
    );
    if (failures.length)
      setError(
        failures
          .map((r) =>
            r.reason instanceof Error
              ? r.reason.message
              : "Some market data is unavailable.",
          )
          .join(" "),
      );
    setBusy(false);
  }
  useEffect(() => {
    if (active && !loaded.current) { loaded.current = true; void search(); }
  }, [active]);
  const money = (value: unknown) => {
    const n = Number(value);
    return value !== null &&
      value !== undefined &&
      value !== "" &&
      Number.isFinite(n)
      ? n.toLocaleString("en-IN")
      : "—";
  };
  return (
    <FeatureFrame context="markets" active={active}>
      {prices?.records?.length ? (
        <div className="market-export-row">
          <ExportMenu
            filename="dated-mandi-observations"
            rows={prices.records}
            provenance={prices.provenance}
          />
        </div>
      ) : null}
      <form className="feature-search" onSubmit={(e) => void search(e)}>
        <FeatureSearchField
          label="Crop"
          voiceLabel="Speak crop name"
          value={commodity}
          onChange={setCommodity}
          placeholder="Wheat, onion, cotton…"
          options={catalogue.commodities}
          required
          busy={busy}
        />
        <FeatureSearchField
          label="State"
          voiceLabel="Speak state"
          value={state}
          onChange={(value) => { setState(value); setMarket(""); }}
          options={catalogue.states}
          placeholder="All states"
          optional
          busy={busy}
        />
        <FeatureSearchField label="Mandi" voiceLabel="Speak mandi name" value={market} onChange={setMarket} options={catalogue.markets.map(item => item.name)} placeholder="Any mandi" optional busy={busy} />
        <button className="feature-primary" disabled={busy}>
          {busy ? <Loader2 size={16} className="spin" /> : <Search size={16} />}{" "}
          {busy ? "Looking up…" : "Find prices"}
        </button>
      </form>
      <div className="market-search-context"><span>{catalogue.commodities.length ? `${catalogue.commodities.length} crops · ${catalogue.states.length} states & territories` : "Search by crop, state and mandi"}</span><span>Search date: {new Intl.DateTimeFormat("en-IN", { timeZone: "Asia/Kolkata", dateStyle: "medium" }).format(new Date())}</span></div>
      {catalogue.markets.length > 0 && <details className="market-directory">
        <summary key={`${commodity}:${state}:${catalogue.markets.length}`}>Mandi directory · {catalogue.markets.length} markets</summary>
        <div className="market-directory-list">{catalogue.markets.filter(item => !market.trim() || item.name.toLowerCase().includes(market.trim().toLowerCase())).slice(0, 12).map(item => <article key={item.id}>
          <div><strong>{item.name}</strong><small>{[item.district, item.state].filter(Boolean).join(" · ")}</small><small>{item.has_price_series ? "Price history available" : "Reported prices not available yet"}</small></div>
          <div>{item.source_url && /^https:\/\//i.test(item.source_url) && <a href={item.source_url} target="_blank" rel="noopener noreferrer">Source <ArrowUpRight size={12} /></a>}<button type="button" disabled={busy} onClick={() => { setMarket(item.name); void search(undefined, item.name); }}>Select mandi</button></div>
        </article>)}</div><small>Up to 12 directory entries shown. Narrow the state or mandi name for a closer match.</small>
      </details>}
      <Failure message={error} />
      {busy && <p className="feature-loading-line" role="status"><Loader2 size={15} className="spin" /> Loading dated prices and history…</p>}
      {prices?.records?.length ? (
        <>
          <MarketComparison rows={comparison} onRemove={key => setComparison(previous => previous.filter(row => marketKey(row) !== key))} />
          <div className="feature-section-heading">
            <h2>{searched} around the markets</h2>
            <span>
              {prices.source}{prices.provenance && <> · <ProvenanceBadge value={prices.provenance} /></>}
            </span>
          </div>
          <div className="market-observations">
            {prices.records.slice(0, visibleMarkets).map((row, i) => (
              <article className={`feature-card market-observation ${comparison.some(item => marketKey(item) === marketKey(row)) ? "is-comparing" : ""}`} key={marketKey(row) || i}>
                <div>
                  <span className="feature-source">
                    <MapPin size={12} />
                    {row.state || "State not supplied"}
                  </span>
                  <h3>{row.market || "Market not supplied"}</h3>
                  <p>{row.variety || row.commodity}</p>
                </div>
                <strong className="market-price">
                  ₹{money(row.modal_price)}
                  <small> / {row.unit?.replace("INR/", "") || "quintal"}</small>
                </strong>
                <div className="market-range">
                  <span>Low ₹{money(row.min_price)}</span>
                  <span>High ₹{money(row.max_price)}</span>
                </div>
                <button type="button" className="market-compare-button" aria-pressed={comparison.some(item => marketKey(item) === marketKey(row))} disabled={!comparablePrice(row) || (comparison.length >= 3 && !comparison.some(item => marketKey(item) === marketKey(row)))} onClick={() => setComparison(previous => previous.some(item => marketKey(item) === marketKey(row)) ? previous.filter(item => marketKey(item) !== marketKey(row)) : [...previous, row])}>{comparison.some(item => marketKey(item) === marketKey(row)) ? <><Check size={14} /> In your comparison</> : <><Compass size={14} /> Compare take-home</>}</button>
                <button type="button" className="market-history-link" disabled={busy} onClick={() => { setMarket(row.market || ""); void search(undefined, row.market || ""); }}>View this mandi’s history <ArrowUpRight size={14} /></button>
                <footer>
                  <ProvenanceBadge
                    value={row.provenance ?? prices.provenance}
                  />{" "}
                  · {row.arrival_date || "date not supplied"}
                </footer>
              </article>
            ))}
          </div>
          <div className="market-result-count"><span>{Math.min(visibleMarkets, prices.records.length)} of {prices.records.length} matching mandis loaded</span>{visibleMarkets < prices.records.length && <button type="button" className="feature-secondary" onClick={() => setVisibleMarkets(value => value + 9)}>More mandis</button>}</div>
        </>
      ) : (
        !busy && (
          <Quiet
            title={
              prices
                ? "Reported prices aren’t available for this search yet."
                : error && searched
                  ? "Current prices could not be loaded."
                  : "A better sale starts with a little context."
            }
          >
            {prices?.message ||
              (error && searched
                ? "Try the price lookup again. Any available historical observations appear separately below."
                : prices ? "Browse the mandi directory, or try another crop or market. Prices appear here when reported by the source." : "Choose your crop and state to look up actual market observations.")}
          </Quiet>
        )
      )}
      {trend && (
        <section className="feature-card market-history">
          <div className="feature-card-heading">
            <span>THE LONGER VIEW</span>
            <span>One market · one variety</span>
          </div>
          {trend.chart ? (
            <FarmResult result={trend} />
          ) : (
            <p>
              There aren’t enough dated observations for a reliable trend in
              this search.
            </p>
          )}
        </section>
      )}
      <p className="feature-footnote">
        Observed prices are not guaranteed offers. Confirm the date, variety,
        unit and quality with the market.
      </p>
    </FeatureFrame>
  );
}
interface Scheme {
  scheme_id?: string;
  scheme_type?: string;
  id?: string;
  scheme_name?: string;
  name?: string;
  title?: string;
  benefit_description?: string;
  description?: string;
  eligibility?: string;
  official_url?: string;
  website?: string;
  source?: string;
  category?: string;
  state?: string;
}
const preparationLabels = [
  ["eligibility_reviewed", "I have checked who can apply"],
  ["documents_reviewed", "I have checked the documents needed"],
  ["application_reviewed", "I have checked the deadline and application route"],
] as const;
type PreparationFlag = typeof preparationLabels[number][0];
type Preparation = Record<PreparationFlag, boolean> & { row_version: number };
function SupportChecklist({ schemeId }: { schemeId?: string }) {
  const assistant = useAssistant();
  const [saved, setSaved] = useState<Preparation | null>(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const generation = useRef(0);
  const valid = Boolean(schemeId && /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(schemeId));
  const path = `/api/support-folder/${schemeId}`;
  useEffect(() => {
    const current = ++generation.current;
    const controller = new AbortController();
    setSaved(null); setError(""); setBusy(false);
    if (!valid || !assistant.ready) return () => { controller.abort(); generation.current++; };
    setBusy(true);
    void workspaceRequest<Preparation>(path, "GET", undefined, { signal: controller.signal, fresh: true }).then(value => {
      if (current === generation.current) setSaved(value);
    }).catch(reason => { if (!controller.signal.aborted && current === generation.current) setError(reason instanceof Error ? reason.message : "Could not load your checklist."); })
      .finally(() => { if (current === generation.current) setBusy(false); });
    return () => { controller.abort(); generation.current++; };
  }, [path, valid, assistant.ready, retry]);
  async function update(flag: PreparationFlag, checked: boolean) {
    if (!saved || busy) return;
    const current = generation.current, previous = saved;
    const next = { row_version: saved.row_version, eligibility_reviewed: saved.eligibility_reviewed, documents_reviewed: saved.documents_reviewed, application_reviewed: saved.application_reviewed, [flag]: checked };
    setSaved(next); setBusy(true); setError("");
    try {
      const value = await workspaceRequest<Preparation>(path, "PUT", next);
      if (current === generation.current) setSaved(value);
    } catch (reason) {
      if (current === generation.current) { setSaved(previous); setError(reason instanceof Error ? reason.message : "Your change was not saved. Reload and try again."); }
    } finally { if (current === generation.current) setBusy(false); }
  }
  return <section className="support-readiness"><div><h3>Your preparation checklist</h3><small aria-live="polite">{busy ? "Syncing…" : saved ? `${preparationLabels.filter(([key]) => saved[key]).length} of 3 checked${saved.row_version > 0 ? " · Saved" : ""}` : ""}</small></div><p>Your progress stays with your farm. Mitra can help you check each step.</p>
    {!valid && <p>Saved checklists are available for programmes in your connected catalogue.</p>}
    {preparationLabels.map(([flag, label]) => <label key={flag}><input type="checkbox" checked={Boolean(saved?.[flag])} disabled={!saved || busy || Boolean(error)} onChange={event => void update(flag, event.target.checked)} /><span>{label}</span></label>)}
    {error && <div role="alert" className="workspace-error">{error} <button type="button" className="feature-secondary" onClick={() => setRetry(value => value + 1)}>Reload checklist</button></div>}
  </section>;
}
function Schemes({ active, onNavigate }: { active: boolean; onNavigate: (view: string) => void }) {
  const [selectedScheme, setSelectedScheme] = useState(0);
  const catalogue = useMarketCatalogue(active);
  const loaded = useRef(false);
  const [visibleSchemes, setVisibleSchemes] = useState(6);
  const operation = useRef(0);
  const [query, setQuery] = useState(""),
    [state, setState] = useState("");
  const [items, setItems] = useState<Scheme[] | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function search(e?: React.FormEvent) {
    e?.preventDefault();
    const current = ++operation.current;
    setBusy(true);
    setVisibleSchemes(6);
    setSelectedScheme(0);
    setError("");
    setItems(null);
    try {
      const data = await inspectWorkspaceTool<{ schemes: Scheme[] }>(
        "scheme_search",
        { query: query.trim(), state: state.trim() },
      );
      if (current === operation.current) setItems(data.schemes ?? []);
    } catch (e) {
      if (current === operation.current) setError(e instanceof Error ? e.message : "The catalog is unavailable.");
    } finally {
      if (current === operation.current) setBusy(false);
    }
  }
  useEffect(() => { if (active && !loaded.current) { loaded.current = true; void search(); } }, [active]);
  return (
    <FeatureFrame context="schemes" active={active}>
      {items?.length ? (
        <div className="market-export-row">
          <ExportMenu
            filename="farm-support-references"
            rows={items}
            note="Reference scheme information; verify current eligibility and deadlines with the official source."
          />
        </div>
      ) : null}
      <form className="feature-search" onSubmit={(e) => void search(e)}>
        <FeatureSearchField
          label="What do you need help with?"
          voiceLabel="Speak support search"
          value={query}
          onChange={setQuery}
          placeholder="Insurance, solar pumps, soil…"
          busy={busy}
        />
        <FeatureSearchField
          label="State"
          voiceLabel="Speak state"
          value={state}
          onChange={setState}
          options={catalogue.states}
          placeholder="All states"
          optional
          busy={busy}
        />
        <button className="feature-primary" disabled={busy}>
          {busy ? <Loader2 size={16} className="spin" /> : <Search size={16} />}{" "}
          Explore support
        </button>
      </form>
      <div className="market-search-context"><span>National and state support · official references</span><span>Search insurance, irrigation, credit, seeds or soil</span></div>
      <Failure message={error} />
      {busy && <p className="feature-loading-line" role="status"><Loader2 size={15} className="spin" /> Finding relevant support…</p>}
      {items?.length ? (
        <>
        <div className="support-folder">
          <nav className="support-folder-tabs" aria-label="Support programmes">
            <span className="experience-eyebrow"><FolderOpen size={15} /> YOUR SUPPORT FOLDER</span>
            {items.slice(0, visibleSchemes).map((scheme, i) => <button type="button" key={scheme.id || scheme.scheme_id || i} className={selectedScheme === i ? "is-selected" : ""} aria-pressed={selectedScheme === i} onClick={() => setSelectedScheme(i)}><span>{scheme.category || scheme.scheme_type?.replace(/_/g, " ") || "Farm support"}</span><strong>{scheme.scheme_name || scheme.name || scheme.title || "Farmer support scheme"}</strong><small>{scheme.state || "National support"}</small><ArrowUpRight size={15} /></button>)}
          </nav>
          {(() => {
            const scheme = items[selectedScheme] || items[0];
            const title = scheme.scheme_name || scheme.name || scheme.title || "Farmer support scheme";
            const url = scheme.official_url || scheme.website;
            return <article className="support-folder-page" aria-label="Selected programme details">
              <div className="support-page-heading"><FolderOpen size={24} /><span>{scheme.source === "fallback" ? "Reference catalog" : "Programme details"}</span></div>
              <h2>{title}</h2><p className="support-benefit">{scheme.benefit_description || scheme.description || "Read the official scheme page for benefit details."}</p>
              <section><h3>Who can apply?</h3><p>{scheme.eligibility || "Check the current eligibility rules on the official page."}</p></section>
              <SupportChecklist key={scheme.scheme_id || scheme.id || title} schemeId={scheme.scheme_id || scheme.id} />
              <div className="support-folder-actions"><button type="button" className="feature-primary" onClick={() => { onNavigate("chat"); window.dispatchEvent(new CustomEvent("mitra-voice-draft", { detail: `Help me prepare for ${title}${scheme.state ? ` in ${scheme.state}` : ""}. Explain the benefits, check my eligibility with questions, and make a document checklist using the official source${url && /^https?:\/\//i.test(url) ? `: ${url}` : ". Please find its official source"}. Tell me what needs verification before applying.` })); }}><Sparkles size={16} /> Prepare with Mitra</button>{url && /^https?:\/\//i.test(url) && <a className="scheme-official" href={url} target="_blank" rel="noopener noreferrer">Official information <ArrowUpRight size={15} /></a>}</div>
              <small className="feature-footnote">Confirm current terms and deadlines with the official programme before applying.</small>
            </article>;
          })()}
        </div>
        <div className="market-result-count"><span>{Math.min(visibleSchemes, items.length)} of {items.length} relevant references loaded</span>{visibleSchemes < items.length && <button type="button" className="feature-secondary" onClick={() => setVisibleSchemes(value => value + 6)}>More support</button>}</div>
        </>
      ) : (
        !busy && (
          <Quiet
            title={
              items
                ? "Let’s try a broader search."
                : "Support that starts with your needs."
            }
          >
            {items
              ? "No matching catalog entries. Try another keyword or leave the state blank."
              : "Find relevant programs, then ask Mitra to turn the requirements into a checklist."}
          </Quiet>
        )
      )}
    </FeatureFrame>
  );
}
interface Expense {
  id: string;
  description: string;
  amount: number;
  date: string;
}
function Files({ active }: { active: boolean }) {
  const assistant = useAssistant();
  const [selected, setSelected] = useState<Artifact | null>(null),
    [expenses, setExpenses] = useState<Expense[]>([]),
    [error, setError] = useState("");
  useEffect(() => {
    if (!active || !assistant.ready) return;
    let cancelled = false;
    void inspectWorkspaceTool<{ expenses: Expense[] }>("list_expenses", {})
      .then((data) => {
        if (!cancelled) {
          setExpenses(data.expenses);
          setError("");
        }
      })
      .catch((e) => {
        if (!cancelled)
          setError(
            e instanceof Error ? e.message : "Saved costs are unavailable.",
          );
      });
    return () => {
      cancelled = true;
    };
  }, [active, assistant.ready, assistant.running]);
  const fileFilter = useCollectionFilters(assistant.artifacts, file => file.title, file => file.format);
  const total = expenses.reduce(
    (sum, e) => sum + (Number.isFinite(e.amount) ? e.amount : 0),
    0,
  );
  return (
    <div className="notebook-files">
      <CollectionFilters control={fileFilter} label="Files" />
      <div className="record-overview">
        <div>
          <FileText size={19} />
          <span>Available files</span>
          <strong>{assistant.artifacts.length}</strong>
        </div>
        <div>
          <Wallet size={19} />
          <span>Latest recorded costs</span>
          <strong>₹{total.toLocaleString("en-IN")}</strong>
        </div>
        <div>
          <Check size={19} />
          <span>Open farm tasks</span>
          <strong>{assistant.tasks.filter((t) => !t.completed).length}</strong>
        </div>
      </div>
      <div className="feature-split records-split">
        <section className="feature-card">
          <div className="feature-card-heading">
            <span>YOUR FILES</span>
            <span>Latest 100</span>
          </div>
          {assistant.artifacts.length ? (
            <div className="record-file-list">
              {fileFilter.items.map((file) => (
                <button
                  className={selected?.id === file.id ? "selected" : ""}
                  key={file.id}
                  onClick={() => setSelected(file)}
                >
                  <FileText size={19} />
                  <span>
                    <strong>{file.title}</strong>
                    <small>
                      {file.format.toUpperCase()} ·{" "}
                      {Math.max(1, Math.round(file.size / 1024))} KB
                    </small>
                  </span>
                  <ArrowUpRight size={16} />
                </button>
              ))}
            </div>
          ) : (
            <Quiet title="Your notebook has room to grow.">
              Ask Mitra to create a field report, a budget or a checklist. It
              will appear here.
            </Quiet>
          )}
        </section>
        <section className="feature-card record-preview">
          <div className="feature-card-heading">
            <span>TAKE A LOOK INSIDE</span>
            <Download size={17} />
          </div>
          {selected ? (
            <FarmResult result={{ artifact: selected }} />
          ) : (
            <Quiet title="A small preview. The whole story inside.">
              Choose a file to preview its content or download it.
            </Quiet>
          )}
        </section>
      </div>
      <section className="feature-card expense-records">
        <div className="feature-card-heading">
          <span>SAVED EXPENSES</span>
          <span>Latest 100 · INR</span>
        </div>
        <Failure message={error} />
        {expenses.length ? (
          <div className="artifact-preview-table">
            <table>
              <thead>
                <tr>
                  <th>What it was for</th>
                  <th>Date</th>
                  <th>Amount</th>
                </tr>
              </thead>
              <tbody>
                {expenses.map((e) => (
                  <tr key={e.id}>
                    <td>{e.description}</td>
                    <td>{e.date}</td>
                    <td>₹{e.amount.toLocaleString("en-IN")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p>
            No saved expenses yet. Ask Mitra to record a cost; you’ll review it
            before it is saved.
          </p>
        )}
      </section>
    </div>
  );
}
function Records({
  active,
  onNavigate,
}: {
  active: boolean;
  onNavigate: (view: string) => void;
}) {
  const [tab, setTab] = useState<NotebookTab>(() => { const requested = new URLSearchParams(window.location.search).get("tab"); return notebookSections.some(([key]) => key === requested) ? requested as NotebookTab : "today"; });
  return active ? (
    <FarmNotebook tab={tab} onChange={setTab}>
      {tab === "files" ? <Files active /> : <FarmWorkspace tab={tab} onNavigate={view => {
        const next = view.replace(/^notebook-/, "");
        if (view.startsWith("notebook-") && notebookSections.some(([key]) => key === next)) setTab(next as NotebookTab);
        else onNavigate(view);
      }} />}
    </FarmNotebook>
  ) : null;
}

export default function WorkspaceFeatures({
  view,
  onNavigate = () => {},
}: {
  view: string;
  onNavigate?: (view: string) => void;
}) {
  const current = titles[view as FeatureView];
  return (
    <div className="workspace-feature-page">
      {current && view !== "records" && (
        <header className="feature-hero">
          <span>{current[0]}</span>
          <h1>{current[1]}</h1>
          <p>{current[2]}</p>
        </header>
      )}
      <div hidden={view !== "crops"}>
        <Crops active={view === "crops"} />
      </div>
      <div hidden={view !== "markets"}>
        <div className="market-exchange-link">
          <span>Need transport, equipment or a swap for your harvest?</span>
          <button type="button" onClick={() => onNavigate("exchange")}>
            <Handshake size={16} /> Open farmer exchange{" "}
            <ArrowUpRight size={14} />
          </button>
        </div>
        <Markets active={view === "markets"} />
      </div>
      <div hidden={view !== "schemes"}>
        <Schemes active={view === "schemes"} onNavigate={onNavigate} />
      </div>
      <div hidden={view !== "records"}>
        <Records active={view === "records"} onNavigate={onNavigate} />
      </div>
    </div>
  );
}
