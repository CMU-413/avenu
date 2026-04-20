import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import Login from "./pages/Login";
import AdminHome from "./pages/admin/AdminHome";
import AdminDashboard from "./pages/admin/AdminDashboard";
import AdminNotifications from "./pages/admin/AdminNotifications";
import AdminMailRequests from "./pages/admin/AdminMailRequests";
import AdminUsersTeams from "./pages/admin/AdminUsersTeams";
import SearchMailbox from "./pages/admin/SearchMailbox";
import RecordEntry from "./pages/admin/RecordEntry";
import OcrQueue from "./pages/admin/OcrQueue";
import MemberDashboard from "./pages/member/MemberDashboard";
import NotificationSettings from "./pages/member/NotificationSettings";
import NotFound from "./pages/NotFound";
import {
  ApiError,
  ApiSessionMe,
  bootstrapOptixSession,
  fetchFeatureFlags,
  redeemMagicLink,
  sessionMe,
} from "./lib/api";
import { SessionUser, useAppStore } from "./lib/store";
import { ConfirmDialogProvider } from "./components/ConfirmDialogProvider";

const queryClient = new QueryClient();
const OPTIX_BOOTSTRAP_QUERY_KEYS = ["token", "org_id", "user_id"] as const;
const MAGIC_LINK_QUERY_KEYS = ["token_id", "signature"] as const;
const APP_ROOT_PATH = (() => {
  const raw = import.meta.env.VITE_BASE_PATH || "/mail/";
  return raw.endsWith("/") ? raw : `${raw}/`;
})();

export function stripAuthBootstrapParams(url: string): string {
  const current = new URL(url);
  let changed = false;
  for (const key of [...OPTIX_BOOTSTRAP_QUERY_KEYS, ...MAGIC_LINK_QUERY_KEYS]) {
    if (current.searchParams.has(key)) {
      current.searchParams.delete(key);
      changed = true;
    }
  }
  if (!changed) return url;
  const nextSearch = current.searchParams.toString();
  return `${current.pathname}${nextSearch ? `?${nextSearch}` : ""}${current.hash}`;
}

export function stripAuthBootstrapParamsFromWindow(): void {
  const nextUrl = stripAuthBootstrapParams(window.location.href);
  if (nextUrl !== `${window.location.pathname}${window.location.search}${window.location.hash}`) {
    window.history.replaceState({}, "", nextUrl);
  }
}

function redirectToAppRoot(): void {
  window.location.replace(APP_ROOT_PATH);
}

export function getMagicLinkParams(search: string): { tokenId: string; signature: string } | null {
  const params = new URLSearchParams(search);
  const tokenId = params.get("token_id");
  const signature = params.get("signature");
  if (!tokenId || !signature) {
    return null;
  }
  return { tokenId, signature };
}

function toSessionUser(session: ApiSessionMe): SessionUser {
  return {
    id: session.id,
    fullname: session.fullname,
    email: session.email,
    isAdmin: session.isAdmin,
    teamIds: session.teamIds,
    emailNotifications: session.emailNotifications,
    smsNotifications: session.smsNotifications,
    hasPhone: session.hasPhone,
  };
}

const AppRoutes = () => {
  const navigate = useNavigate();
  const {
    sessionUser,
    isHydratingSession,
    setSessionHydrating,
    setSessionUser,
    featureFlags,
    isHydratingFeatureFlags,
    setFeatureFlags,
    setFeatureFlagsHydrating,
  } = useAppStore();

  useEffect(() => {
    let alive = true;
    const hydrate = async () => {
      setSessionHydrating(true);
      const params = new URLSearchParams(window.location.search);
      const tokenParam = params.get("token");
      const orgId = params.get("org_id");
      const userId = params.get("user_id");
      const magicLink = getMagicLinkParams(window.location.search);

      try {
        if (tokenParam) {
          const token = tokenParam.trim().replace(/ /g, "+");
          await bootstrapOptixSession({ token, orgId, userId });
          if (!alive) return;
        } else if (magicLink) {
          await redeemMagicLink(magicLink);
          if (!alive) return;
        }
        const me = await sessionMe();
        if (!alive) return;
        setSessionUser(toSessionUser(me));
        if (tokenParam || magicLink) {
          stripAuthBootstrapParamsFromWindow();
          navigate(me.isAdmin ? "/admin" : "/member", { replace: true });
        }
      } catch (err) {
        if (!alive) return;
        if (err instanceof ApiError && err.status === 401) {
          setSessionUser(null);
        } else {
          setSessionUser(null);
        }
        if (tokenParam || magicLink) {
          stripAuthBootstrapParamsFromWindow();
          redirectToAppRoot();
        }
      } finally {
        if (alive) setSessionHydrating(false);
      }
    };
    hydrate();
    return () => {
      alive = false;
    };
  }, [navigate, setSessionHydrating, setSessionUser]);

  useEffect(() => {
    let alive = true;
    const hydrateFlags = async () => {
      setFeatureFlagsHydrating(true);
      try {
        const flags = await fetchFeatureFlags();
        if (!alive) return;
        setFeatureFlags({
          adminOcr: flags.adminOcr ?? false,
          ocrQueueV2: flags.ocrQueueV2 ?? false,
          ocrShadowLaunch: flags.ocrShadowLaunch ?? false,
        });
      } catch (err) {
        if (!alive) return;
        setFeatureFlags({
          adminOcr: false,
          ocrQueueV2: false,
          ocrShadowLaunch: false,
        });
      } finally {
        if (alive) setFeatureFlagsHydrating(false);
      }
    };
    hydrateFlags();
    return () => {
      alive = false;
    };
  }, [setFeatureFlags, setFeatureFlagsHydrating]);

  if (isHydratingSession || isHydratingFeatureFlags) {
    return (
      <div className="min-h-screen flex items-center justify-center text-muted-foreground">
        Loading...
      </div>
    );
  }

  const isAdmin = sessionUser?.isAdmin === true;
  const isMember = !!sessionUser && !isAdmin;

  return (
    <Routes>
      <Route
        path="/"
        element={sessionUser ? <Navigate to={isAdmin ? "/admin" : "/member"} replace /> : <Login />}
      />
      <Route path="/admin" element={isAdmin ? <AdminHome /> : <Navigate to={isMember ? "/member" : "/"} replace />} />
      <Route
        path="/admin/users-teams"
        element={isAdmin ? <AdminUsersTeams /> : <Navigate to={isMember ? "/member" : "/"} replace />}
      />
      <Route
        path="/admin/recording"
        element={
          isAdmin ? (
            featureFlags.adminOcr && featureFlags.ocrQueueV2 ? (
              <OcrQueue />
            ) : (
              <Navigate to="/admin/mailboxes" replace />
            )
          ) : (
            <Navigate to={isMember ? "/member" : "/"} replace />
          )
        }
      />
      <Route
        path="/admin/dashboard"
        element={isAdmin ? <AdminDashboard /> : <Navigate to={isMember ? "/member" : "/"} replace />}
      />
      <Route
        path="/admin/notifications"
        element={isAdmin ? <AdminNotifications /> : <Navigate to={isMember ? "/member" : "/"} replace />}
      />
      <Route
        path="/admin/mail-requests"
        element={isAdmin ? <AdminMailRequests /> : <Navigate to={isMember ? "/member" : "/"} replace />}
      />
      <Route
        path="/admin/mailboxes"
        element={isAdmin ? <SearchMailbox /> : <Navigate to={isMember ? "/member" : "/"} replace />}
      />
      <Route
        path="/admin/mailboxes/:mailboxId"
        element={isAdmin ? <RecordEntry /> : <Navigate to={isMember ? "/member" : "/"} replace />}
      />
      <Route path="/member" element={isMember ? <MemberDashboard /> : <Navigate to={isAdmin ? "/admin" : "/"} replace />} />
      <Route
        path="/member/settings"
        element={isMember ? <NotificationSettings /> : <Navigate to={isAdmin ? "/admin" : "/"} replace />}
      />
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
};


const App = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <ConfirmDialogProvider>
          <Toaster />
          <Sonner />
          <AppRoutes />
        </ConfirmDialogProvider>
      </TooltipProvider>
    </QueryClientProvider>
  );
};

export default App;
