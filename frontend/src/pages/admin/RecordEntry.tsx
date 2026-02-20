import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useAppStore } from "@/lib/store";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import {
  ApiError,
  ApiMailRequest,
  createMail,
  deleteMail,
  listAdminMailRequests,
  listMail,
  listMailboxes,
  resolveAdminMailRequest,
  retryAdminMailRequestNotification,
  updateMail,
} from "@/lib/api";

function matchesSelectedDate(request: ApiMailRequest, selectedDay: string): boolean {
  const hasStart = !!request.startDate;
  const hasEnd = !!request.endDate;
  if (!hasStart && !hasEnd) return true;
  if (hasStart && hasEnd) return request.startDate! <= selectedDay && selectedDay <= request.endDate!;
  if (hasStart) return request.startDate! <= selectedDay;
  return selectedDay <= request.endDate!;
}

const RecordEntry = () => {
  const { mailboxId } = useParams<{ mailboxId: string }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const logout = useAppStore((s) => s.logout);
  const { toast } = useToast();
  const [mailboxName, setMailboxName] = useState<string>("");
  const [loadingMailbox, setLoadingMailbox] = useState(true);
  const [loadingExisting, setLoadingExisting] = useState(true);
  const [existingRows, setExistingRows] = useState<
    { id: string; type: "letter" | "package"; count: number }[]
  >([]);
  const [activeRequests, setActiveRequests] = useState<ApiMailRequest[]>([]);
  const [resolvedRequests, setResolvedRequests] = useState<ApiMailRequest[]>([]);
  const [loadingRequests, setLoadingRequests] = useState(true);
  const [saving, setSaving] = useState(false);
  const [resolvingRequestId, setResolvingRequestId] = useState<string | null>(null);
  const [retryingRequestId, setRetryingRequestId] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      if (!mailboxId) {
        setLoadingMailbox(false);
        return;
      }
      try {
        const mailboxes = await listMailboxes();
        if (!alive) return;
        const mailbox = mailboxes.find((mb) => mb.id === mailboxId);
        setMailboxName(mailbox?.displayName || "");
      } catch (err) {
        if (!alive) return;
        const message = err instanceof Error ? err.message : "Failed to load mailbox";
        toast({ title: message, variant: "destructive" });
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          logout();
          navigate("/");
        }
      } finally {
        if (alive) setLoadingMailbox(false);
      }
    };
    load();
    return () => {
      alive = false;
    };
  }, [mailboxId, logout, navigate, toast]);

  const [date, setDate] = useState(
    () => searchParams.get("date") || new Date().toISOString().split("T")[0]
  );
  const [letters, setLetters] = useState(0);
  const [packages, setPackages] = useState(0);

  useEffect(() => {
    let alive = true;
    const loadExisting = async () => {
      if (!mailboxId) {
        setLoadingExisting(false);
        return;
      }
      setLoadingExisting(true);
      try {
        const rows = await listMail({ date, mailboxId });
        if (!alive) return;
        const mapped = rows.map((row) => ({
          id: row.id,
          type: row.type,
          count: row.count,
        }));
        setExistingRows(mapped);
        setLetters(mapped.filter((row) => row.type === "letter").reduce((sum, row) => sum + row.count, 0));
        setPackages(mapped.filter((row) => row.type === "package").reduce((sum, row) => sum + row.count, 0));
      } catch (err) {
        if (!alive) return;
        const message = err instanceof Error ? err.message : "Failed to load existing record";
        toast({ title: message, variant: "destructive" });
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          logout();
          navigate("/");
        }
      } finally {
        if (alive) setLoadingExisting(false);
      }
    };
    loadExisting();
    return () => {
      alive = false;
    };
  }, [date, mailboxId, logout, navigate, toast]);

  useEffect(() => {
    let alive = true;
    const loadRequests = async () => {
      if (!mailboxId) {
        setLoadingRequests(false);
        return;
      }
      setLoadingRequests(true);
      try {
        const requests = await listAdminMailRequests({ mailboxId });
        if (!alive) return;
        setActiveRequests(requests.filter((request) => matchesSelectedDate(request, date)));
      } catch (err) {
        if (!alive) return;
        const message = err instanceof Error ? err.message : "Failed to load expected mail requests";
        toast({ title: message, variant: "destructive" });
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          logout();
          navigate("/");
        }
      } finally {
        if (alive) setLoadingRequests(false);
      }
    };

    void loadRequests();
    return () => {
      alive = false;
    };
  }, [date, mailboxId, logout, navigate, toast]);

  if (loadingMailbox || loadingExisting) {
    return (
      <div className="min-h-screen flex items-center justify-center text-muted-foreground">
        Loading...
      </div>
    );
  }

  if (!mailboxId || !mailboxName) {
    return (
      <div className="min-h-screen flex items-center justify-center text-muted-foreground">
        Mailbox not found
      </div>
    );
  }

  const toIsoDay = (day: string) => `${day}T00:00:00Z`;

  const makeIdempotencyKey = () => {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      return crypto.randomUUID();
    }
    return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  };

  const handleSave = async () => {
    if (letters === 0 && packages === 0) {
      toast({ title: "Enter at least 1 letter or package", variant: "destructive" });
      return;
    }
    setSaving(true);
    try {
      const ops: Promise<unknown>[] = [];
      const dateIso = toIsoDay(date);

      const syncType = (type: "letter" | "package", targetCount: number) => {
        const typedRows = existingRows.filter((row) => row.type === type);
        if (targetCount <= 0) {
          ops.push(...typedRows.map((row) => deleteMail(row.id)));
          return;
        }
        if (typedRows.length === 0) {
          ops.push(
            createMail({
              mailboxId,
              date: dateIso,
              type,
              count: targetCount,
              idempotencyKey: makeIdempotencyKey(),
            })
          );
          return;
        }

        const [primary, ...extra] = typedRows;
        ops.push(
          updateMail(primary.id, {
            count: targetCount,
            date: dateIso,
          })
        );
        ops.push(...extra.map((row) => deleteMail(row.id)));
      };

      syncType("letter", letters);
      syncType("package", packages);

      await Promise.all(ops);
      toast({ title: "Record saved" });
      navigate(`/admin/recording?date=${date}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to save record";
      toast({ title: message, variant: "destructive" });
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        logout();
        navigate("/");
      }
    } finally {
      setSaving(false);
    }
  };

  const handleResolve = async (requestId: string) => {
    setResolvingRequestId(requestId);
    try {
      const updated = await resolveAdminMailRequest(requestId);
      setActiveRequests((items) => items.filter((item) => item.id !== requestId));
      setResolvedRequests((items) => [updated, ...items.filter((item) => item.id !== requestId)]);
      toast({ title: "Request resolved and notification attempted" });
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setActiveRequests((items) => items.filter((item) => item.id !== requestId));
        toast({ title: "Request was already resolved or unavailable" });
        return;
      }
      const message = err instanceof Error ? err.message : "Failed to resolve request";
      toast({ title: message, variant: "destructive" });
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        logout();
        navigate("/");
      }
    } finally {
      setResolvingRequestId(null);
    }
  };

  const handleRetry = async (requestId: string) => {
    setRetryingRequestId(requestId);
    try {
      const updated = await retryAdminMailRequestNotification(requestId);
      setResolvedRequests((items) => items.map((item) => (item.id === requestId ? updated : item)));
      toast({ title: "Notification retry attempted" });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to retry notification";
      toast({ title: message, variant: "destructive" });
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        logout();
        navigate("/");
      }
    } finally {
      setRetryingRequestId(null);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur">
        <div className="flex items-center gap-3 px-4 h-14">
          <button onClick={() => navigate(-1)} className="text-muted-foreground hover:text-foreground transition-colors">
            <ArrowLeft className="h-5 w-5" />
          </button>
          <h1 className="text-lg font-bold text-foreground truncate">{mailboxName}</h1>
        </div>
      </header>

      <div className="px-4 py-6 max-w-5xl mx-auto grid gap-6 lg:grid-cols-[1fr_360px]">
        <div className="space-y-6">
          {/* Date */}
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-foreground">Date</label>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="w-full h-11 rounded-lg border border-input bg-card px-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          {/* Letters */}
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-foreground">Letters</label>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setLetters(Math.max(0, letters - 1))}
                className="h-11 w-11 rounded-lg border border-input bg-card text-foreground text-xl font-medium flex items-center justify-center hover:bg-muted transition-colors"
              >
                −
              </button>
              <span className="text-2xl font-bold text-foreground w-12 text-center">{letters}</span>
              <button
                onClick={() => setLetters(letters + 1)}
                className="h-11 w-11 rounded-lg border border-input bg-card text-foreground text-xl font-medium flex items-center justify-center hover:bg-muted transition-colors"
              >
                +
              </button>
            </div>
          </div>

          {/* Packages */}
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-foreground">Packages</label>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setPackages(Math.max(0, packages - 1))}
                className="h-11 w-11 rounded-lg border border-input bg-card text-foreground text-xl font-medium flex items-center justify-center hover:bg-muted transition-colors"
              >
                −
              </button>
              <span className="text-2xl font-bold text-foreground w-12 text-center">{packages}</span>
              <button
                onClick={() => setPackages(packages + 1)}
                className="h-11 w-11 rounded-lg border border-input bg-card text-foreground text-xl font-medium flex items-center justify-center hover:bg-muted transition-colors"
              >
                +
              </button>
            </div>
          </div>

          <Button onClick={handleSave} className="w-full h-12 text-base" disabled={saving}>
            {saving ? "Saving..." : "Save"}
          </Button>
        </div>

        <aside className="rounded-xl border bg-card p-3 space-y-3 h-fit">
          <h2 className="text-sm font-semibold text-foreground">Expected Mail Requests</h2>
          {loadingRequests ? (
            <p className="text-xs text-muted-foreground">Loading requests...</p>
          ) : activeRequests.length === 0 ? (
            <p className="text-xs text-muted-foreground">No active requests for selected date.</p>
          ) : (
            <div className="space-y-2">
              {activeRequests.map((request) => (
                <div key={request.id} className="rounded-lg border p-2 space-y-1.5">
                  <p className="text-xs text-card-foreground">{request.expectedSender || request.description || "No details"}</p>
                  <p className="text-xs text-muted-foreground">
                    {request.startDate || request.endDate ? `${request.startDate || "?"} to ${request.endDate || "?"}` : "No date window"}
                  </p>
                  <Button
                    onClick={() => handleResolve(request.id)}
                    disabled={resolvingRequestId === request.id}
                    className="w-full h-8 text-xs"
                  >
                    {resolvingRequestId === request.id ? "Resolving..." : "Resolve & Notify"}
                  </Button>
                </div>
              ))}
            </div>
          )}

          {resolvedRequests.length > 0 && (
            <div className="space-y-2 border-t pt-3">
              <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Recently Resolved</h3>
              {resolvedRequests.map((request) => (
                <div key={request.id} className="rounded-lg border p-2 space-y-1.5">
                  <p className="text-xs text-card-foreground">{request.expectedSender || request.description || "No details"}</p>
                  <p className="text-xs text-muted-foreground">
                    Notification: {request.lastNotificationStatus || "—"}
                    {request.lastNotificationAt ? ` at ${new Date(request.lastNotificationAt).toLocaleString()}` : ""}
                  </p>
                  <Button
                    onClick={() => handleRetry(request.id)}
                    disabled={retryingRequestId === request.id}
                    variant="secondary"
                    className="w-full h-8 text-xs"
                  >
                    {retryingRequestId === request.id ? "Retrying..." : "Retry Notification"}
                  </Button>
                </div>
              ))}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
};

export default RecordEntry;
