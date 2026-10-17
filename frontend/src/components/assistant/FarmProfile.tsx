import { onWorkspaceCacheInvalidated } from "@/lib/workspaceCacheLifecycle";
import { applyLanguagePreference, APP_LANGUAGES } from "@/lib/languagePreference";
import { useEffect, useState } from "react";
import { ArrowUpRight, Check, Pencil, UserRound, X } from "lucide-react";
import { workspaceRequest } from "@/lib/farmWorkspaceClient";
import { WorkspaceVoiceField } from "@/components/WorkspaceVoiceField";
import { ProvenanceBadge, type Provenance } from "./DataStatus";
import { ExportMenu } from "./ExportMenu";
import "./farm-profile.css";

type Profile = {
  id: string;
  name: string;
  phone?: string;
  location?: string;
  state?: string;
  district?: string;
  preferred_language?: string;
  land_size_acres?: number;
  mapped_plot_area_acres?: number;
  crops?: string[];
  excess_resources?: string[];
  required_resources?: string[];
  provenance?: Provenance;
  data_origin?: string;
};
type Farm = {
  id: string;
  name: string;
  ownership_type?: string;
  irrigation_method?: string;
  water_source?: string;
};
type Plot = {
  id: string;
  farm_id: string;
  name?: string;
  area_ha?: number;
  soil_texture?: string;
};
type Edit = {
  name: string;
  location: string;
  district: string;
  preferred_language: string;
  crops: string;
  excess_resources: string;
  required_resources: string;
};
const editFrom = (p: Profile): Edit => ({
  name: p.name || "",
  location: p.location || "",
  district: p.district || "",
  preferred_language: p.preferred_language?.split("-")[0] || "en",
  crops: (p.crops || []).join(", "),
  excess_resources: (p.excess_resources || []).join(", "),
  required_resources: (p.required_resources || []).join(", "),
});
const list = (value: string) =>
  value
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
export default function FarmProfile({
  onNavigate,
}: {
  onNavigate: (view: string) => void;
}) {
  const [profile, setProfile] = useState<Profile | null>(null),
    [farms, setFarms] = useState<Farm[]>([]),
    [plots, setPlots] = useState<Plot[]>([]);
  const [edit, setEdit] = useState<Edit | null>(null),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(true),
    [revision, setRevision] = useState(0);
  useEffect(() => onWorkspaceCacheInvalidated(() => setRevision(r => r + 1)), []);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    void Promise.all([
      workspaceRequest<{ profile: Profile | null }>("/api/profile"),
      workspaceRequest<{ farms: Farm[] }>("/api/farms"),
      workspaceRequest<{ plots: Plot[] }>("/api/plots"),
    ])
      .then(([p, f, fields]) => {
        if (active) {
          setProfile(p.profile);
          setFarms(f.farms || []);
          setPlots(fields.plots || []);
        }
      })
      .catch((e) => {
        if (active) {
          setError(e.message);
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [revision]);
  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!edit) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await workspaceRequest("/api/profile/save", "POST", {
        name: edit.name.trim(),
        location: edit.location.trim(),
        district: edit.district.trim(),
        preferred_language: edit.preferred_language,
        crops: list(edit.crops),
        excess_resources: list(edit.excess_resources),
        required_resources: list(edit.required_resources),
      });
      applyLanguagePreference(edit.preferred_language);
      setEdit(null);
      setNotice("Your profile has been saved.");
      setRevision((r) => r + 1);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const change = (key: keyof Edit, value: string) =>
    setEdit((e) => (e ? { ...e, [key]: value } : e));
  return (
    <section className="farm-profile" aria-label="Your farmer profile">
      <header className="farm-profile-heading">
        <div>
          <span className="farm-profile-eyebrow">Your place in the farm</span>
          <h1>Your profile.</h1>
          <p>The details Mitra uses to understand your farm.</p>
        </div>
        {profile && (
          <ExportMenu
            filename="my-farmer-profile"
            rows={[{ ...profile, farms, plots }]}
            provenance={profile.provenance}
            disabled={loading}
            note="Private farmer profile and owned fields. Share only with people you trust."
          />
        )}
      </header>
      {error && (
        <p className="workspace-error" role="alert">
          {error}
          <button
            className="farm-profile-retry"
            onClick={() => setRevision((r) => r + 1)}
          >
            Retry
          </button>
        </p>
      )}
      {notice && (
        <p className="farm-profile-notice" role="status">
          <Check size={15} />
          {notice}
        </p>
      )}
      {loading && !profile ? (
        <p>Loading your profile…</p>
      ) : !profile ? (
        <p>
          No farmer profile is available for this account. Your identity has not
          been inferred.
        </p>
      ) : (
        <>
          <div className="farm-profile-identity">
            <span className="farm-profile-avatar" aria-hidden="true">
              <UserRound size={28} />
            </span>
            <div>
              <h2>{profile.name}</h2>
              <p>
                {[profile.district, profile.state]
                  .filter(Boolean)
                  .join(" · ") ||
                  profile.location ||
                  "Location not set"}
              </p>
              <ProvenanceBadge
                value={profile.provenance || { origin: profile.data_origin }}
              />
            </div>
            <button
              className="farm-profile-edit"
              onClick={() => {
                setEdit(editFrom(profile));
                setNotice("");
              }}
              disabled={busy}
            >
              <Pencil size={14} />
              Edit details
            </button>
          </div>
          {edit ? (
            <form className="farm-profile-editor" onSubmit={save}>
              <div className="farm-profile-edit-heading">
                <h3>Make it yours</h3>
                <button
                  type="button"
                  aria-label="Cancel profile edit"
                  onClick={() => setEdit(null)}
                  disabled={busy}
                >
                  <X size={18} />
                </button>
              </div>
              <div className="farm-profile-form-grid">
                {(
                  [
                    ["name", "Your name"],
                    ["location", "Recorded location"],
                    ["district", "District"],
                    ["crops", "Crops (separate with commas)"],
                    [
                      "excess_resources",
                      "Resources you can offer (comma separated)",
                    ],
                    [
                      "required_resources",
                      "Resources you need (comma separated)",
                    ],
                  ] as [keyof Edit, string][]
                ).map(([key, label]) => (
                  <label key={key}>
                    {label}
                    <WorkspaceVoiceField
                      label={`Speak ${label.toLowerCase()}`}
                      onTranscript={(value) => change(key, value)}
                      disabled={busy}
                    >
                      <input
                        aria-label={label}
                        value={edit[key]}
                        onChange={(e) => change(key, e.target.value)}
                        required={key === "name"}
                        maxLength={key === "name" ? 100 : 200}
                        disabled={busy}
                      />
                    </WorkspaceVoiceField>
                  </label>
                ))}
                <label>
                  Preferred language
                  <select
                    aria-label="Preferred language"
                    value={edit.preferred_language}
                    onChange={(e) =>
                      change("preferred_language", e.target.value)
                    }
                    disabled={busy}
                  >
                    {!APP_LANGUAGES.some(
                      ([code]) =>
                        code === edit.preferred_language,
                    ) && (
                      <option value={edit.preferred_language}>
                        {edit.preferred_language}
                      </option>
                    )}
                    {APP_LANGUAGES.map(([code, name]) => (
                      <option key={code} value={code}>
                        {name}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <p>
                These details are saved to your account. Editing this profile
                does not publish a listing or change your field boundaries.
              </p>
              <footer>
                <button
                  type="button"
                  onClick={() => setEdit(null)}
                  disabled={busy}
                >
                  Cancel
                </button>
                <button
                  className="feature-primary"
                  disabled={busy || !edit.name.trim()}
                >
                  {busy ? "Saving…" : "Save profile"}
                </button>
              </footer>
            </form>
          ) : (
            <dl className="farm-profile-details">
              <div>
                <dt>Contact number</dt>
                <dd>{profile.phone || "Not provided"}</dd>
              </div>
              <div>
                <dt>Recorded location</dt>
                <dd>{profile.location || "Not set"}</dd>
              </div>
              <div>
                <dt>Preferred language</dt>
                <dd>
                  {APP_LANGUAGES.find(
                    ([code]) =>
                      code ===
                      profile.preferred_language?.split("-")[0],
                  )?.[1] ||
                    profile.preferred_language ||
                    "Not set"}
                </dd>
              </div>
              <div>
                <dt>Reported land area</dt>
                <dd>
                  {profile.land_size_acres != null
                    ? `${Number(profile.land_size_acres).toLocaleString("en-IN", { maximumFractionDigits: 2 })} acres`
                    : "Not set"}
                </dd>
              </div>
              <div>
                <dt>Area in saved fields</dt>
                <dd>
                  {profile.mapped_plot_area_acres != null
                    ? `${Number(profile.mapped_plot_area_acres).toLocaleString("en-IN", { maximumFractionDigits: 2 })} acres`
                    : "No fields saved"}
                </dd>
              </div>
              <div>
                <dt>Crops in your profile</dt>
                <dd>{profile.crops?.join(", ") || "Not set"}</dd>
              </div>
              <div>
                <dt>Resources to offer</dt>
                <dd>{profile.excess_resources?.join(", ") || "None added"}</dd>
              </div>
              <div>
                <dt>Resources you need</dt>
                <dd>
                  {profile.required_resources?.join(", ") || "None added"}
                </dd>
              </div>
            </dl>
          )}
          <section className="farm-profile-land">
            <header>
              <div>
                <h3>Your farms & fields</h3>
                <p>Saved field areas are separate from your reported total.</p>
              </div>
              <button onClick={() => onNavigate("records")}>
                Open farm notebook
                <ArrowUpRight size={15} />
              </button>
            </header>
            {farms.length ? (
              <ol>
                {farms.map((farm) => (
                  <li key={farm.id}>
                    <div>
                      <strong>{farm.name}</strong>
                      <span>
                        {[farm.ownership_type, farm.irrigation_method]
                          .filter(Boolean)
                          .join(" · ")
                          .replace(/_/g, " ")}
                      </span>
                    </div>
                    <ul>
                      {plots
                        .filter((plot) => plot.farm_id === farm.id)
                        .map((plot) => (
                          <li key={plot.id}>
                            <span>{plot.name || "Saved field"}</span>
                            <span>
                              {plot.area_ha} ha
                              {plot.soil_texture
                                ? ` · ${plot.soil_texture}`
                                : ""}
                            </span>
                          </li>
                        ))}
                    </ul>
                  </li>
                ))}
              </ol>
            ) : (
              <p>No farms saved yet. Add your first farm in My fields.</p>
            )}
          </section>
        </>
      )}
    </section>
  );
}
