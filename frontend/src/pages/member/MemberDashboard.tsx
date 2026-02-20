import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAppStore } from "@/lib/store";
import { Settings, LogOut, Mail, Package } from "lucide-react";
import {
  ApiError,
  ApiMailRequest,
  ApiMemberMailSummary,
  cancelMailRequest,
  createMailRequest,
  getMemberMail,
  listMemberMailRequests,
  sessionLogout,
} from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
type MailRequestView = "ACTIVE" | "RESOLVED";

function formatIsoDateLocal(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function getWeekRange(weeksAgo: number) {
  const now = new Date();
  now.setHours(12, 0, 0, 0);
  const daysSinceMonday = (now.getDay() + 6) % 7;
  const startOfThisWeek = new Date(now);
  startOfThisWeek.setDate(now.getDate() - daysSinceMonday - weeksAgo * 7);
  startOfThisWeek.setHours(12, 0, 0, 0);

  const endOfWeek = new Date(startOfThisWeek);
  endOfWeek.setDate(startOfThisWeek.getDate() + 6);
  endOfWeek.setHours(12, 0, 0, 0);

  const dates: string[] = [];
  for (let i = 0; i < 7; i++) {
    const d = new Date(startOfThisWeek);
    d.setDate(startOfThisWeek.getDate() + i);
    dates.push(formatIsoDateLocal(d));
  }

  const formatShort = (d: Date) =>
    `${d.getMonth() + 1}/${d.getDate()}`;

  return {
    label: `${formatShort(startOfThisWeek)} – ${formatShort(endOfWeek)}`,
    start: dates[0],
    end: dates[6],
  };
}

const MemberDashboard = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { sessionUser, logout } = useAppStore();
  const [weeksAgo, setWeeksAgo] = useState(0);
  const [mailSummary, setMailSummary] = useState<ApiMemberMailSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [mailRequests, setMailRequests] = useState<ApiMailRequest[]>([]);
  const [mailRequestsLoading, setMailRequestsLoading] = useState(true);
  const [mailRequestView, setMailRequestView] = useState<MailRequestView>("ACTIVE");
  const [mailboxId, setMailboxId] = useState("");
  const [expectedSender, setExpectedSender] = useState("");
  const [description, setDescription] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [submittingRequest, setSubmittingRequest] = useState(false);
  const [cancellingRequestId, setCancellingRequestId] = useState<string | null>(null);

  const week = useMemo(() => getWeekRange(weeksAgo), [weeksAgo]);
  const mailboxMap = useMemo(() => {
    const map = new Map<string, { name: string; type: "personal" | "company" }>();
    for (const mailbox of mailSummary?.mailboxes || []) {
      map.set(mailbox.mailboxId, { name: mailbox.name, type: mailbox.type });
    }
    return map;
  }, [mailSummary]);

  const loadMailRequests = useCallback(async (status: MailRequestView) => {
    setMailRequestsLoading(true);
    try {
      const requests = await listMemberMailRequests({ status });
      setMailRequests(requests);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load expected mail";
      toast({ title: message, variant: "destructive" });
      if (err instanceof ApiError && err.status === 401) {
        logout();
        navigate("/");
      }
    } finally {
      setMailRequestsLoading(false);
    }
  }, [logout, navigate, toast]);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      setLoading(true);
      try {
        const summary = await getMemberMail({ start: week.start, end: week.end });
        if (!alive) return;
        setMailSummary(summary);
      } catch (err) {
        if (!alive) return;
        const message = err instanceof Error ? err.message : "Failed to load mail";
        toast({ title: message, variant: "destructive" });
        if (err instanceof ApiError && err.status === 401) {
          logout();
          navigate("/");
        }
      } finally {
        if (alive) setLoading(false);
      }
    };
    load();
    return () => {
      alive = false;
    };
  }, [logout, navigate, toast, week.start, week.end]);

  useEffect(() => {
    void loadMailRequests(mailRequestView);
  }, [loadMailRequests, mailRequestView]);

  useEffect(() => {
    if (mailboxId) return;
    const firstMailbox = mailSummary?.mailboxes[0];
    if (firstMailbox) {
      setMailboxId(firstMailbox.mailboxId);
    }
  }, [mailSummary, mailboxId]);

  const handleCreateRequest = async () => {
    if (!mailboxId) {
      toast({ title: "Select a mailbox", variant: "destructive" });
      return;
    }
    if (!expectedSender.trim() && !description.trim()) {
      toast({ title: "Enter a sender or description", variant: "destructive" });
      return;
    }

    setSubmittingRequest(true);
    try {
      await createMailRequest({
        mailboxId,
        expectedSender: expectedSender.trim() || undefined,
        description: description.trim() || undefined,
        startDate: startDate || undefined,
        endDate: endDate || undefined,
      });
      setExpectedSender("");
      setDescription("");
      setStartDate("");
      setEndDate("");
      toast({ title: "Expected mail request created" });
      await loadMailRequests(mailRequestView);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to create request";
      toast({ title: message, variant: "destructive" });
      if (err instanceof ApiError && err.status === 401) {
        logout();
        navigate("/");
      }
    } finally {
      setSubmittingRequest(false);
    }
  };

  const handleCancelRequest = async (requestId: string) => {
    setCancellingRequestId(requestId);
    try {
      await cancelMailRequest(requestId);
      toast({ title: "Expected mail request cancelled" });
      await loadMailRequests(mailRequestView);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to cancel request";
      toast({ title: message, variant: "destructive" });
      if (err instanceof ApiError && err.status === 401) {
        logout();
        navigate("/");
      }
    } finally {
      setCancellingRequestId(null);
    }
  };

  const handleLogout = async () => {
    try {
      await sessionLogout();
    } finally {
      logout();
      navigate("/");
    }
  };

  if (!sessionUser) {
    return (
      <div className="min-h-screen flex items-center justify-center text-muted-foreground">
        Not logged in
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur">
        <div className="flex items-center justify-between px-4 h-14">
          <h1 className="text-lg font-bold text-foreground">Avenu</h1>
          <div className="flex items-center gap-3">
            <button onClick={() => navigate("/member/settings")} className="text-muted-foreground hover:text-foreground transition-colors">
              <Settings className="h-5 w-5" />
            </button>
            <button onClick={handleLogout} className="text-muted-foreground hover:text-foreground transition-colors">
              <LogOut className="h-5 w-5" />
            </button>
          </div>
        </div>
      </header>

      <div className="px-4 py-4 max-w-lg mx-auto space-y-4">
        {/* Week selector */}
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-muted-foreground">Week of</span>
          <select
            value={weeksAgo}
            onChange={(e) => setWeeksAgo(Number(e.target.value))}
            className="h-9 rounded-lg border border-input bg-card px-2 text-sm font-medium text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          >
            {[0, 1, 2, 3, 4].map((w) => (
              <option key={w} value={w}>
                {getWeekRange(w).label}
              </option>
            ))}
          </select>
        </div>

        {/* Mailbox sections */}
        {loading ? (
          <div className="py-8 text-center text-sm text-muted-foreground">Loading...</div>
        ) : !mailSummary || mailSummary.mailboxes.length === 0 ? (
          <div className="py-8 text-center text-sm text-muted-foreground">No mailboxes</div>
        ) : (
          mailSummary.mailboxes.map((mb) => {
            const hasMailInWeek = mb.days.some((day) => day.letters > 0 || day.packages > 0);

            return (
              <div key={mb.mailboxId} className="space-y-2">
                <h2 className="text-sm font-semibold text-primary uppercase tracking-wider px-1">
                  {mb.type === "personal" ? "You received" : `${mb.name} received`}
                </h2>
                <div className="rounded-xl border bg-card overflow-hidden divide-y divide-border">
                  {mb.days.map((day, i) => {
                    const hasMail = day.letters > 0 || day.packages > 0;

                    return (
                      <div key={day.date} className="flex items-center justify-between px-4 py-2.5">
                        <span className="text-sm font-medium text-card-foreground w-10">{DAYS[i]}</span>
                        {hasMail ? (
                          <div className="flex items-center gap-3 text-sm">
                            {day.letters > 0 && (
                              <span className="flex items-center gap-1 text-card-foreground">
                                {day.letters} <Mail className="h-3.5 w-3.5 text-muted-foreground" />
                              </span>
                            )}
                            {day.packages > 0 && (
                              <span className="flex items-center gap-1 text-card-foreground">
                                {day.packages} <Package className="h-3.5 w-3.5 text-muted-foreground" />
                              </span>
                            )}
                          </div>
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                      </div>
                    );
                  })}
                </div>
                {!hasMailInWeek && (
                  <p className="px-1 text-xs text-muted-foreground">No mail in selected range</p>
                )}
              </div>
            );
          })
        )}

        <div className="space-y-3 pt-2">
          <h2 className="text-sm font-semibold text-primary uppercase tracking-wider px-1">Expected Mail</h2>
          <div className="rounded-xl border bg-card p-3 space-y-2">
            <select
              aria-label="Expected Mailbox"
              value={mailboxId}
              onChange={(e) => setMailboxId(e.target.value)}
              className="w-full h-10 rounded-lg border border-input bg-background px-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="">Select mailbox</option>
              {(mailSummary?.mailboxes || []).map((mb) => (
                <option key={mb.mailboxId} value={mb.mailboxId}>
                  {mb.name}
                </option>
              ))}
            </select>
            <input
              aria-label="Expected Sender"
              value={expectedSender}
              onChange={(e) => setExpectedSender(e.target.value)}
              placeholder="Expected sender (optional)"
              className="w-full h-10 rounded-lg border border-input bg-background px-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <textarea
              aria-label="Expected Description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Description (optional)"
              className="w-full min-h-20 rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <div className="grid grid-cols-2 gap-2">
              <input
                aria-label="Expected Start Date"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-full h-10 rounded-lg border border-input bg-background px-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <input
                aria-label="Expected End Date"
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="w-full h-10 rounded-lg border border-input bg-background px-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <button
              onClick={handleCreateRequest}
              disabled={submittingRequest}
              className="w-full h-10 rounded-lg bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50"
            >
              {submittingRequest ? "Creating..." : "Create Request"}
            </button>
          </div>

          <div className="inline-flex rounded-lg border bg-card p-1">
            <button
              onClick={() => setMailRequestView("ACTIVE")}
              className={`px-3 py-1.5 text-xs rounded-md ${mailRequestView === "ACTIVE" ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}
            >
              Active
            </button>
            <button
              onClick={() => setMailRequestView("RESOLVED")}
              className={`px-3 py-1.5 text-xs rounded-md ${mailRequestView === "RESOLVED" ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}
            >
              Resolved
            </button>
          </div>

          {mailRequestsLoading ? (
            <div className="py-4 text-center text-sm text-muted-foreground">Loading requests...</div>
          ) : mailRequests.length === 0 ? (
            <div className="py-4 text-center text-sm text-muted-foreground">
              {mailRequestView === "ACTIVE" ? "No active requests" : "No resolved requests"}
            </div>
          ) : (
            <div className="rounded-xl border bg-card divide-y divide-border">
              {mailRequests.map((req) => {
                const mailbox = mailboxMap.get(req.mailboxId);
                const detail = req.expectedSender || req.description || "—";
                const dateWindow = req.startDate || req.endDate ? `${req.startDate || "?"} to ${req.endDate || "?"}` : "No date window";
                const createdLabel = new Date(req.createdAt).toLocaleString();
                const resolvedLabel = req.resolvedAt ? new Date(req.resolvedAt).toLocaleString() : null;

                return (
                  <div key={req.id} className="p-3 space-y-1.5">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-medium text-card-foreground">{mailbox?.name || "Mailbox"}</p>
                        <p className="text-xs text-muted-foreground">{detail}</p>
                        <p className="text-xs text-muted-foreground">{dateWindow}</p>
                        <p className="text-xs text-muted-foreground">Created {createdLabel}</p>
                        {mailRequestView === "RESOLVED" && resolvedLabel && (
                          <p className="text-xs text-muted-foreground">Resolved {resolvedLabel}</p>
                        )}
                      </div>
                      {mailRequestView === "ACTIVE" && (
                        <button
                          onClick={() => handleCancelRequest(req.id)}
                          disabled={cancellingRequestId === req.id}
                          className="text-xs text-destructive hover:underline disabled:opacity-50"
                        >
                          {cancellingRequestId === req.id ? "Cancelling..." : "Cancel"}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default MemberDashboard;
