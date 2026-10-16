import { invalidateWorkspaceCaches } from "@/lib/workspaceCacheLifecycle";
import { apiFetch } from "@/lib/apiClient";
import { lazy, Suspense, useEffect } from "react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useLocation,
} from "react-router-dom";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import { LanguageProvider } from "@/contexts/LanguageContext";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { VoiceAssistantButton } from "@/components/VoiceAssistantButton";
import { ClassicWorkspaceSwitch } from "@/components/assistant/ClassicWorkspaceSwitch";
const Login = lazy(() => import("./pages/Login"));
const Signup = lazy(() => import("./pages/Signup"));
const Landing = lazy(() => import("./pages/Landing"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Trends = lazy(() => import("./pages/Trends"));
const Reports = lazy(() => import("./pages/Reports"));
const AIHardwareAccelerator = lazy(
  () => import("./pages/AIHardwareAccelerator"),
);
const MandiRates = lazy(() => import("./pages/MandiRates"));
const DatabaseExplorer = lazy(() => import("./pages/DatabaseExplorer"));
const NotFound = lazy(() => import("./pages/NotFound"));
const Profile = lazy(() => import("./pages/Profile"));
const HardwareSetup = lazy(() => import("./pages/HardwareSetup"));
const BuyHardware = lazy(() => import("./pages/BuyHardware"));
const Marketplace = lazy(() => import("./pages/Marketplace"));
const FarmersMap = lazy(() => import("./pages/FarmersMap"));
const LegacyAdvisor = lazy(() => import("./pages/LegacyAdvisor"));
const LegacyOverview = lazy(() => import("./pages/LegacyOverview"));
const Advisor = lazy(() => import("./pages/Advisor"));
const CropDoctor = lazy(() => import("./pages/CropDoctor"));

import { ThemeProvider } from "next-themes";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // ── Ultra-Cache read-only enterprise caching defaults ──────────
      staleTime: 5 * 60_000, // data fresh for 5 min — zero repeated network stalls
      gcTime: 30 * 60_000, // retain memory cache for 30 min
      refetchOnWindowFocus: false, // instant background performance without tab flutter
      retry: 1,
    },
  },
});

// Redirect authenticated users away from login
// Farming tools work before hardware commissioning; station APIs disclose missing data.
function LoginRoute() {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) return <Login />;
  return <Navigate to={"/dashboard"} replace />;
}

import { AnimatePresence, motion } from "framer-motion";

// ─── DB Explorer Background Pre-fetching Types & Helpers ─────────────────────
type ColumnMeta = {
  name: string;
  type: string;
  nullable: boolean;
  default: string | null;
  primary_key: boolean;
};

type TableMeta = {
  name: string;
  row_count: number;
  columns: ColumnMeta[];
  primary_key?: string[];
  sample_columns?: string[];
};

type TableResponse = {
  table: string;
  columns: ColumnMeta[];
  records: Record<string, unknown>[];
  pagination: {
    page: number;
    page_size: number;
    total_rows: number;
    total_pages: number;
  };
  filters: {
    search?: string | null;
    filter_column?: string | null;
    filter_value?: string | null;
    order_by?: string | null;
    desc?: boolean;
  };
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;

const normalizeColumn = (column: unknown): ColumnMeta => {
  if (typeof column === "string") {
    return {
      name: column,
      type: "unknown",
      nullable: true,
      default: null,
      primary_key: column === "id",
    };
  }
  const col = isRecord(column) ? column : {};
  const name = String(col.name ?? "");
  return {
    name,
    type: String(col.type ?? "unknown"),
    nullable: Boolean(col.nullable ?? true),
    default:
      col.default === null || col.default === undefined
        ? null
        : String(col.default),
    primary_key: Boolean(col.primary_key ?? name === "id"),
  };
};

const normalizeTables = (payload: unknown): TableMeta[] => {
  const body = isRecord(payload) ? payload : {};
  const rowCounts = isRecord(body.row_counts) ? body.row_counts : {};
  const rawTables = Array.isArray(body.tables) ? body.tables : [];
  return rawTables
    .map((table): TableMeta | null => {
      if (typeof table === "string") {
        return {
          name: table,
          row_count: Number(rowCounts[table] ?? 0),
          columns: [],
          primary_key: [],
          sample_columns: [],
        };
      }
      if (!isRecord(table)) return null;
      const name = String(table.name ?? "");
      if (!name) return null;
      const columns = Array.isArray(table.columns)
        ? table.columns.map(normalizeColumn).filter((c) => c.name)
        : [];
      return {
        name,
        row_count: Number(table.row_count ?? rowCounts[name] ?? 0),
        columns,
        primary_key: Array.isArray(table.primary_key)
          ? table.primary_key.map(String)
          : [],
        sample_columns: Array.isArray(table.sample_columns)
          ? table.sample_columns.map(String)
          : [],
      };
    })
    .filter((table): table is TableMeta => Boolean(table));
};

const normalizeTableResponse = (
  payload: unknown,
  fallbackPage: number,
  fallbackPageSize: number,
): TableResponse => {
  const body = isRecord(payload) ? payload : {};
  const columns = Array.isArray(body.columns)
    ? body.columns.map(normalizeColumn).filter((c) => c.name)
    : [];
  const records = Array.isArray(body.records)
    ? body.records.filter(isRecord)
    : [];
  const pagination = isRecord(body.pagination) ? body.pagination : {};
  return {
    table: String(body.table ?? ""),
    columns,
    records,
    pagination: {
      page: Number(pagination.page ?? fallbackPage),
      page_size: Number(pagination.page_size ?? fallbackPageSize),
      total_rows: Number(pagination.total_rows ?? records.length),
      total_pages: Number(pagination.total_pages ?? 1),
    },
    filters: isRecord(body.filters) ? body.filters : {},
  };
};

const API_URL = import.meta.env.VITE_API_URL || "";

import { useQueryClient } from "@tanstack/react-query";
import { ultraCache } from "@/lib/ultraCache";
import { warmWorkspaceReads } from "@/lib/assistantClient";

function GlobalAssistanceButtons() {
  const { pathname } = useLocation();
  if (
    pathname === "/advisor" ||
    pathname === "/overview" ||
    pathname === "/station" ||
    pathname === "/workspace"
  )
    return null;
  return <VoiceAssistantButton />;
}

const AppContent = () => {
  const { isAuthenticated } = useAuth();
  const { pathname } = useLocation();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!isAuthenticated) return;
    ultraCache.warmUpPlatform();
    const timer = setTimeout(warmWorkspaceReads, 250);
    const onVisible = () => { if (document.visibilityState === "visible" && navigator.onLine) { invalidateWorkspaceCaches("refresh"); ultraCache.warmUpPlatform(); warmWorkspaceReads(); } };
    window.addEventListener("online", onVisible);
    document.addEventListener("visibilitychange", onVisible);
    return () => { clearTimeout(timer); document.removeEventListener("visibilitychange", onVisible); window.removeEventListener("online", onVisible); };
  }, [isAuthenticated]);

  useEffect(() => {
    if (!isAuthenticated || pathname !== "/db") return;

    // The explorer's metadata is only needed when that page is opened.
    const prefetchDatabaseData = async () => {
      try {
        const tablesRes = await apiFetch(`${API_URL}/admin/tables`);
        if (!tablesRes.ok) return;
        const tablesData = await tablesRes.json();

        const normalizedTables = normalizeTables(tablesData);
        queryClient.setQueryData(["dbTables"], normalizedTables);

        if (normalizedTables.length > 0) {
          const firstTable = normalizedTables[0];
          const primaryKey =
            firstTable.columns.find((c) => c.primary_key)?.name ||
            firstTable.columns[0]?.name ||
            "id";

          const fetchTableData = async (orderByVal: string) => {
            const params = new URLSearchParams();
            params.set("page", "1");
            params.set("page_size", "50");
            params.set("desc", "true");
            if (orderByVal) params.set("order_by", orderByVal);

            const res = await apiFetch(
              `${API_URL}/admin/tables/${encodeURIComponent(firstTable.name)}?${params.toString()}`,
            );
            if (!res.ok) return null;
            const data = await res.json();
            return normalizeTableResponse(data, 1, 50);
          };

          const [dataWithEmpty, dataWithPrimary] = await Promise.all([
            fetchTableData(""),
            fetchTableData(primaryKey),
          ]);

          if (dataWithEmpty) {
            queryClient.setQueryData(
              ["dbTableData", firstTable.name, 1, 50, "", "", "", "", true],
              dataWithEmpty,
            );
          }
          if (dataWithPrimary) {
            queryClient.setQueryData(
              [
                "dbTableData",
                firstTable.name,
                1,
                50,
                "",
                "",
                "",
                primaryKey,
                true,
              ],
              dataWithPrimary,
            );
          }
        }
      } catch (err) {
        console.warn("Background database pre-fetch skipped/failed:", err);
      }
    };

    prefetchDatabaseData();
  }, [isAuthenticated, queryClient, pathname]);

  return (
    <>
      <Suspense
        fallback={
          <div className="workspace-loading" role="status">
            Opening your farm…
          </div>
        }
      >
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<LoginRoute />} />
          <Route path="/signup" element={<Signup />} />

          {/* Hardware onboarding — protected but no HardwareGate */}
          <Route
            path="/hardware-setup"
            element={
              <ProtectedRoute>
                <HardwareSetup />
              </ProtectedRoute>
            }
          />
          <Route
            path="/buy-hardware"
            element={
              <ProtectedRoute>
                <BuyHardware />
              </ProtectedRoute>
            }
          />

          {/* Profile — protected, no HardwareGate (user needs to connect hardware here) */}
          <Route
            path="/profile"
            element={
              <ProtectedRoute>
                <Profile />
              </ProtectedRoute>
            }
          />

          {/* Farmer pages use authenticated data, with independent station availability. */}
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/crop-doctor"
            element={
              <ProtectedRoute>
                <CropDoctor />
              </ProtectedRoute>
            }
          />
          <Route
            path="/trends"
            element={
              <ProtectedRoute>
                <Trends />
              </ProtectedRoute>
            }
          />
          <Route
            path="/reports"
            element={
              <ProtectedRoute>
                <Reports />
              </ProtectedRoute>
            }
          />
          <Route
            path="/advisor"
            element={
              <ProtectedRoute>
                <Suspense
                  fallback={
                    <div style={{ padding: 40 }}>
                      Opening your farm workspace…
                    </div>
                  }
                >
                  <LegacyAdvisor />
                </Suspense>
              </ProtectedRoute>
            }
          />
          <Route
            path="/overview"
            element={
              <ProtectedRoute>
                <Suspense fallback={<div>Opening station…</div>}>
                  <LegacyOverview />
                </Suspense>
              </ProtectedRoute>
            }
          />
          <Route
            path="/workspace"
            element={
              <ProtectedRoute>
                <Suspense fallback={<div>Opening workspace…</div>}>
                  <Advisor />
                </Suspense>
              </ProtectedRoute>
            }
          />
          <Route
            path="/station"
            element={<Navigate to="/workspace?view=station" replace />}
          />
          <Route
            path="/accelerator"
            element={
              <ProtectedRoute>
                <AIHardwareAccelerator />
              </ProtectedRoute>
            }
          />
          <Route
            path="/mandi"
            element={
              <ProtectedRoute>
                <MandiRates />
              </ProtectedRoute>
            }
          />
          <Route
            path="/db"
            element={
              <ProtectedRoute>
                <DatabaseExplorer />
              </ProtectedRoute>
            }
          />
          <Route
            path="/marketplace"
            element={
              <ProtectedRoute>
                <Marketplace />
              </ProtectedRoute>
            }
          />
          <Route
            path="/map"
            element={
              <ProtectedRoute>
                <FarmersMap />
              </ProtectedRoute>
            }
          />

          {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Suspense>
      {isAuthenticated && (
        <>
          <GlobalAssistanceButtons />
          <ClassicWorkspaceSwitch />
        </>
      )}
    </>
  );
};

const App = () => (
  <QueryClientProvider client={queryClient}>
    <ThemeProvider attribute="class" defaultTheme="light" enableSystem={false}>
      <LanguageProvider>
        <AuthProvider>
          <TooltipProvider>
            <Toaster />
            <Sonner />
            <BrowserRouter>
              <AppContent />
            </BrowserRouter>
          </TooltipProvider>
        </AuthProvider>
      </LanguageProvider>
    </ThemeProvider>
  </QueryClientProvider>
);

export default App;
