import { DataStatus } from "@/components/assistant/DataStatus";
import { WorkspaceHeaderActions } from "@/components/assistant/WorkspaceHeaderActions";
import { WeatherShortcut } from "@/components/assistant/WeatherShortcut";
import { classicDestination } from "@/lib/workspaceNavigation";
import { useEffect, useState, lazy, Suspense } from "react";
import { FarmCalendar } from "@/components/assistant/FarmCalendar";
import {
  Link,
  useLocation,
  useNavigate,
  useSearchParams,
} from "react-router-dom";
import {
  Box,
  MessageCircle,
  CalendarDays,
  PanelsTopLeft,
  Stethoscope,
  TrendingUp,
  HandHeart,
  NotebookPen,
  Handshake,
  UserRound,
  CloudSun,
} from "lucide-react";
import { AssistantChat } from "@/components/assistant/AssistantChat";
import "@/components/assistant/assistant.css";
const Features = lazy(() => import("@/components/assistant/WorkspaceFeatures"));
const Exchange = lazy(() => import("@/components/assistant/FarmExchange"));
const Profile = lazy(() => import("@/components/assistant/FarmProfile"));
const views = [
  {
    id: "chat",
    label: "Assistant",
    caption: "A little help, whenever you need it",
    icon: MessageCircle,
  },
  {
    id: "calendar",
    label: "Calendar",
    caption: "Your season, one day at a time",
    icon: CalendarDays,
  },
  {
    id: "station",
    label: "Farm station",
    caption: "A closer look at your land",
    icon: Box,
  },
  {
    id: "weather",
    label: "Farm weather",
    caption: "Today, next hours and the days ahead",
    icon: CloudSun,
  },
  {
    id: "crops",
    label: "Crop Doctor",
    caption: "A careful check for your crops",
    icon: Stethoscope,
  },
  {
    id: "markets",
    label: "Market prices",
    caption: "Dated prices, clearer choices",
    icon: TrendingUp,
  },
  {
    id: "schemes",
    label: "Farm support",
    caption: "Benefits and application checklists",
    icon: HandHeart,
  },
  {
    id: "records",
    label: "Farm notebook",
    caption: "Your files, plans and saved costs",
    icon: NotebookPen,
  },
  {
    id: "exchange",
    label: "Farmer exchange",
    caption: "Find a resource, agree together, track the handover",
    icon: Handshake,
  },
  {
    id: "profile",
    label: "My farm profile",
    caption: "Your identity, location and farm details",
    icon: UserRound,
  },
];
const Station = lazy(() => import("./SystemOverview"));
const Weather = lazy(() => import("@/components/assistant/WeatherWorkspace"));
export default function Advisor() {
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  useEffect(() => {
    const draft = location.state?.voiceDraft;
    if (typeof draft !== "string") return;
    window.dispatchEvent(
      new CustomEvent("mitra-voice-draft", { detail: draft }),
    );
    navigate(`${location.pathname}${location.search}`, {
      replace: true,
      state: null,
    });
  }, [location, navigate]);
  const view = views.some((item) => item.id === params.get("view"))
    ? params.get("view")!
    : "chat";
  const active = views.find((item) => item.id === view)!;
  const setView = (next: string) => {
    const updated = new URLSearchParams(params);
    updated.set("view", next);
    setParams(updated);
  };
  const [companionAnchor, setCompanionAnchor] = useState<HTMLDivElement | null>(null);
  const classic = classicDestination(params.get("from"));
  return (
    <main className="mitra-page">
      <nav className="workspace-feature-dock" aria-label="Farm tools">
        {views
          .slice(3)
          .filter(({ id }) => id !== "profile")
          .map(({ id, label, caption, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setView(id)}
              aria-label={label}
              aria-pressed={view === id}
              className={view === id ? "active" : ""}
            >
              <Icon size={19} aria-hidden="true" />
              <span className="workspace-nav-tooltip">
                <strong>{label}</strong>
                <small>{caption}</small>
              </span>
            </button>
          ))}
      </nav>
      <section className="mitra-page-workspace">
        <header className="mitra-page-header">
          <div>
            <button
              className="header-leaf workspace-profile-control"
              aria-label="My farm profile"
              aria-pressed={view === "profile"}
              onClick={() => setView("profile")}
            >
              <UserRound size={17} />
              <span className="profile-control-tooltip">My farm profile</span>
            </button>
            <strong>Kisan Mitra</strong>
            <span className="workspace-label">{active.label}</span>
          </div>
          <div className="workspace-companion-anchor" ref={setCompanionAnchor} />
          <nav className="workspace-core-nav" aria-label="Workspace views">
            {views.slice(0, 3).map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setView(id)}
                aria-label={label}
                aria-pressed={view === id}
                data-tooltip={label}
                className={view === id ? "active" : ""}
              >
                <Icon size={19} aria-hidden="true" />
              </button>
            ))}
            <Link
              to={classic}
              aria-label="Back to classic interface"
              data-tooltip="Classic interface"
              className="workspace-classic-control"
            >
              <PanelsTopLeft size={19} aria-hidden="true" />
            </Link>
          </nav>
        </header>
        <div className="workspace-status-row">
          <DataStatus />
          <WeatherShortcut onOpen={() => setView("weather")} />
          <WorkspaceHeaderActions />
        </div>
        <div className={`mitra-page-chat workspace-pane workspace-${view}`}>
          <div
            style={{
              display: view === "chat" ? "flex" : "none",
              height: "100%",
              minHeight: 0,
              flexDirection: "column",
            }}
          >
            <AssistantChat active={view === "chat"} companionAnchor={companionAnchor} onCompanionVoice={() => setView("chat")} />
          </div>
          {view === "weather" && (
            <Suspense fallback={<div className="workspace-loading">Reading your farm weather…</div>}>
              <Weather onNavigate={setView} />
            </Suspense>
          )}
          {view === "station" && (
            <Suspense
              fallback={
                <div className="workspace-loading">Preparing your station…</div>
              }
            >
              <Station embedded />
            </Suspense>
          )}
          {view === "exchange" && (
            <Suspense
              fallback={
                <div className="workspace-loading">
                  Opening farmer exchange…
                </div>
              }
            >
              <Exchange initialListingId={params.get("listing") || undefined} />
            </Suspense>
          )}
          {view === "profile" && (
            <Suspense
              fallback={
                <div className="workspace-loading">
                  Opening your farm profile…
                </div>
              }
            >
              <Profile onNavigate={setView} />
            </Suspense>
          )}
          <div
            hidden={!["crops", "markets", "schemes", "records"].includes(view)}
          >
            <Suspense
              fallback={
                <div className="workspace-loading">
                  Opening your farm workspace…
                </div>
              }
            >
              <Features view={view} onNavigate={setView} />
            </Suspense>
          </div>
          <div style={{ display: view === "calendar" ? "block" : "none" }}>
            <FarmCalendar onChat={() => setView("chat")} />
          </div>
        </div>
      </section>
    </main>
  );
}
