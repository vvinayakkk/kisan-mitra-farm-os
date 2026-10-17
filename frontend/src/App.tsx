import { WorkspaceEntry } from "@/components/WorkspaceEntry";
import { invalidateWorkspaceCaches } from "@/lib/workspaceCacheLifecycle";
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
const Admin = lazy(() => import("./pages/Admin"));
const Onboarding = lazy(() => import("./pages/Onboarding"));
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

      staleTime: 5 * 60_000,
      gcTime: 30 * 60_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});



function LoginRoute() {
  const { isAuthenticated, authReady } = useAuth();
  if (!authReady) return <div role="status" className="workspace-loading">Opening your farm…</div>;
  if (!isAuthenticated) return <Login />;
  return <Navigate to={"/workspace"} replace />;
}

import { AnimatePresence, motion } from "framer-motion";


import { ultraCache } from "@/lib/ultraCache";
import { warmWorkspaceReads } from "@/lib/assistantClient";

function GlobalAssistanceButtons() {
  const { pathname } = useLocation();
  if (
    pathname === "/control" ||
    pathname === "/onboarding" ||
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

  useEffect(() => {
    if (!isAuthenticated) return;
    ultraCache.warmUpPlatform();
    const timer = setTimeout(warmWorkspaceReads, 250);
    const onVisible = () => { if (document.visibilityState === "visible" && navigator.onLine) { invalidateWorkspaceCaches("refresh"); ultraCache.warmUpPlatform(); warmWorkspaceReads(); } };
    window.addEventListener("online", onVisible);
    document.addEventListener("visibilitychange", onVisible);
    return () => { clearTimeout(timer); document.removeEventListener("visibilitychange", onVisible); window.removeEventListener("online", onVisible); };
  }, [isAuthenticated]);



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
          <Route path="/control" element={<Admin />} />
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<LoginRoute />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/onboarding" element={<ProtectedRoute><Onboarding /></ProtectedRoute>} />

          {                                                         }
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

          {                                                                                }
          <Route
            path="/profile"
            element={
              <ProtectedRoute>
                <Profile />
              </ProtectedRoute>
            }
          />

          {                                                                                 }
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
                  <WorkspaceEntry><Advisor /></WorkspaceEntry>
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

          {                                                         }
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
