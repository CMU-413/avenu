import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import Login from "./pages/Login";
import AdminHome from "./pages/admin/AdminHome";
import AdminDashboard from "./pages/admin/AdminDashboard";
import AdminNotifications from "./pages/admin/AdminNotifications";
import SearchMailbox from "./pages/admin/SearchMailbox";
import RecordEntry from "./pages/admin/RecordEntry";
import MemberDashboard from "./pages/member/MemberDashboard";
import NotificationSettings from "./pages/member/NotificationSettings";
import NotFound from "./pages/NotFound";
import { ApiError, ApiSessionMe, sessionMe } from "./lib/api";
import { SessionUser, useAppStore } from "./lib/store";

const queryClient = new QueryClient();

function toSessionUser(session: ApiSessionMe): SessionUser {
  return {
    id: session.id,
    fullname: session.fullname,
    email: session.email,
    isAdmin: session.isAdmin,
    teamIds: session.teamIds,
    emailNotifications: session.emailNotifications,
  };
}

const AppRoutes = () => {
  const {
    sessionUser,
    isHydratingSession,
    setSessionHydrating,
    setSessionUser,
  } = useAppStore();

  useEffect(() => {
    let alive = true;
    const hydrate = async () => {
      setSessionHydrating(true);
      try {
        const me = await sessionMe();
        if (!alive) return;
        setSessionUser(toSessionUser(me));
      } catch (err) {
        if (!alive) return;
        if (err instanceof ApiError && err.status === 401) {
          setSessionUser(null);
        } else {
          setSessionUser(null);
        }
      } finally {
        if (alive) setSessionHydrating(false);
      }
    };
    hydrate();
    return () => {
      alive = false;
    };
  }, [setSessionHydrating, setSessionUser]);

  if (isHydratingSession) {
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
        path="/admin/recording"
        element={isAdmin ? <AdminDashboard /> : <Navigate to={isMember ? "/member" : "/"} replace />}
      />
      <Route
        path="/admin/notifications"
        element={isAdmin ? <AdminNotifications /> : <Navigate to={isMember ? "/member" : "/"} replace />}
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
  const navigate = useNavigate();
  const { setSessionUser } = useAppStore();
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    let token = params.get("token");
    const orgId = params.get("org_id");
    const userId = params.get("user_id");
    if (token) {
      token = decodeURIComponent(token);
      fetch("/api/optix-token", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ token, orgId, userId })
      })
        .then(res => res.json())
        .then(async data => {
          // Optionally handle response
          console.log("Backend response:", data);
          // Hydrate session after backend sets it
          try {
            const me = await sessionMe();
            setSessionUser(toSessionUser(me));
            if (me.isAdmin) {
              navigate("/admin", { replace: true });
            } else {
              navigate("/member", { replace: true });
            }
          } catch (err) {
            setSessionUser(null);
            navigate("/", { replace: true });
          }
        })
        .catch(err => {
          console.error("Error sending token to backend:", err);
        });
    }
  }, [navigate, setSessionUser]);

  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </TooltipProvider>
    </QueryClientProvider>
  );
};

export default App;
