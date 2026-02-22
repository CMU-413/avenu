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

type DashboardView = "MAILBOX" | "EXPECTED";
type MailRequestView = "ACTIVE" | "RESOLVED";
type MailboxWeekSummary = {
  mailboxId: string;
  name: string;
  type: "personal" | "company";
  letters: number;
  packages: number;
  days: ApiMemberMailSummary["mailboxes"][number]["days"];
};

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

  const formatShort = (d: Date) => `${d.getMonth() + 1}/${d.getDate()}`;

  return {
    label: `${formatShort(startOfThisWeek)} - ${formatShort(endOfWeek)}`,
    start: formatIsoDateLocal(startOfThisWeek),
    end: formatIsoDateLocal(endOfWeek),
  };
}

function summarizeWeek(mailSummary: ApiMemberMailSummary | null) {
  const totals = new Map<string, MailboxWeekSummary>();

  for (const mailbox of mailSummary?.mailboxes || []) {
    const letters = mailbox.days.reduce((sum, day) => sum + day.letters, 0);
    const packages = mailbox.days.reduce((sum, day) => sum + day.packages, 0);
    totals.set(mailbox.mailboxId, {
      mailboxId: mailbox.mailboxId,
      name: mailbox.name,
      type: mailbox.type,
      letters,
      packages,
      days: mailbox.days,
    });
  }

  return Array.from(totals.values());
}

function MailCounts({ letters, packages }: { letters: number; packages: number }) {
  const hasMail = letters > 0 || packages > 0;
  if (!hasMail) {
    return <span className="text-xs text-muted-foreground">No mail</span>;
  }

  return (
    <div className="flex items-center gap-3 text-xs">
      {letters > 0 && (
        <span className="flex items-center gap-1 text-muted-foreground">
          {letters} <Mail className="h-3.5 w-3.5" />
        </span>
      )}
      {packages > 0 && (
        <span className="flex items-center gap-1 text-muted-foreground">
          {packages} <Package className="h-3.5 w-3.5" />
        </span>
      )}
    </div>
  );
}

function MailboxWeekCards({
  mailboxes,
  scope,
  expandedMailboxIds,
  onToggle,
}: {
  mailboxes: MailboxWeekSummary[];
  scope: "current" | "historical";
  expandedMailboxIds: Record<string, boolean>;
  onToggle: (scope: "current" | "historical", mailboxId: string) => void;
}) {
  return (
    <div className="space-y-2">
      {mailboxes.map((mailbox) => {
        const expandKey = `${scope}:${mailbox.mailboxId}`;
        const isExpanded = !!expandedMailboxIds[expandKey];
        return (
          <div key={`${scope}-${mailbox.mailboxId}`} className="rounded-xl border bg-card overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3">
              <div>
                <p className="text-sm font-medium text-card-foreground">{mailbox.type === "personal" ? "You" : mailbox.name}</p>
                <MailCounts letters={mailbox.letters} packages={mailbox.packages} />
              </div>
              <button
                onClick={() => onToggle(scope, mailbox.mailboxId)}
                className="text-xs text-muted-foreground hover:text-foreground"
              >
                {isExpanded ? "Hide daily" : "Show daily"}
              </button>
            </div>
            {isExpanded && (
              <div className="border-t divide-y divide-border">
                {mailbox.days.map((day) => (
                  <div key={day.date} className="flex items-center justify-between px-4 py-2.5">
                    <span className="text-sm text-card-foreground">{day.date}</span>
                    <MailCounts letters={day.letters} packages={day.packages} />
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

const MemberDashboard = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { sessionUser, logout } = useAppStore();

  const [dashboardView, setDashboardView] = useState<DashboardView>("MAILBOX");
  const [historicalWeeksAgo, setHistoricalWeeksAgo] = useState(1);

  const [currentSummary, setCurrentSummary] = useState<ApiMemberMailSummary | null>(null);
  const [historicalSummary, setHistoricalSummary] = useState<ApiMemberMailSummary | null>(null);
  const [mailSummaryLoading, setMailSummaryLoading] = useState(true);
  const [historicalLoading, setHistoricalLoading] = useState(false);
  const [expandedMailboxIds, setExpandedMailboxIds] = useState<Record<string, boolean>>({});

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

  const currentWeek = useMemo(() => getWeekRange(0), []);
  const historicalWeek = useMemo(() => getWeekRange(historicalWeeksAgo), [historicalWeeksAgo]);
  const currentMailboxTotals = useMemo(() => summarizeWeek(currentSummary), [currentSummary]);
  const historicalMailboxTotals = useMemo(() => summarizeWeek(historicalSummary), [historicalSummary]);

  const mailboxMap = useMemo(() => {
    const map = new Map<string, { name: string; type: "personal" | "company" }>();
    for (const mailbox of currentSummary?.mailboxes || []) {
      map.set(mailbox.mailboxId, { name: mailbox.name, type: mailbox.type });
    }
    return map;
  }, [currentSummary]);

  const loadMemberMail = useCallback(async (params: { start: string; end: string }) => {
    return getMemberMail({ start: params.start, end: params.end });
  }, []);

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
      setMailSummaryLoading(true);
      try {
        const summary = await loadMemberMail({ start: currentWeek.start, end: currentWeek.end });
        if (!alive) return;
        setCurrentSummary(summary);
      } catch (err) {
        if (!alive) return;
        const message = err instanceof Error ? err.message : "Failed to load mail";
        toast({ title: message, variant: "destructive" });
        if (err instanceof ApiError && err.status === 401) {
          logout();
          navigate("/");
        }
      } finally {
        if (alive) setMailSummaryLoading(false);
      }
    };

    void load();
    return () => {
      alive = false;
    };
  }, [currentWeek.end, currentWeek.start, loadMemberMail, logout, navigate, toast]);

  useEffect(() => {
    if (dashboardView !== "MAILBOX") {
      return;
    }

    let alive = true;
    const load = async () => {
      setHistoricalLoading(true);
      try {
        const summary = await loadMemberMail({ start: historicalWeek.start, end: historicalWeek.end });
        if (!alive) return;
        setHistoricalSummary(summary);
      } catch (err) {
        if (!alive) return;
        const message = err instanceof Error ? err.message : "Failed to load mail history";
        toast({ title: message, variant: "destructive" });
        if (err instanceof ApiError && err.status === 401) {
          logout();
          navigate("/");
        }
      } finally {
        if (alive) setHistoricalLoading(false);
      }
    };

    void load();
    return () => {
      alive = false;
    };
  }, [dashboardView, historicalWeek.end, historicalWeek.start, loadMemberMail, logout, navigate, toast]);

  useEffect(() => {
    if (dashboardView !== "EXPECTED") {
      return;
    }
    void loadMailRequests(mailRequestView);
  }, [dashboardView, loadMailRequests, mailRequestView]);

  useEffect(() => {
    if (mailboxId) return;
    const firstMailbox = currentSummary?.mailboxes[0];
    if (firstMailbox) {
      setMailboxId(firstMailbox.mailboxId);
    }
  }, [currentSummary, mailboxId]);

  const toggleMailboxExpanded = (scope: "current" | "historical", id: string) => {
    const key = `${scope}:${id}`;
    setExpandedMailboxIds((prev) => ({ ...prev, [key]: !prev[key] }));
  };

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
        <div className="inline-flex rounded-lg border bg-card p-1">
          <button
            onClick={() => setDashboardView("MAILBOX")}
            className={`px-3 py-1.5 text-xs rounded-md ${dashboardView === "MAILBOX" ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}
          >
            Mailbox
          </button>
          <button
            onClick={() => setDashboardView("EXPECTED")}
            className={`px-3 py-1.5 text-xs rounded-md ${dashboardView === "EXPECTED" ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}
          >
            Expected Mail
          </button>
        </div>

        {dashboardView === "MAILBOX" ? (
          <div className="space-y-4">
            <div className="space-y-2">
              <h2 className="text-sm font-semibold text-primary uppercase tracking-wider px-1">This week</h2>
              {mailSummaryLoading ? (
                <div className="py-8 text-center text-sm text-muted-foreground">Loading...</div>
              ) : currentMailboxTotals.length === 0 ? (
                <div className="py-8 text-center text-sm text-muted-foreground">No mailboxes</div>
              ) : (
                <MailboxWeekCards
                  mailboxes={currentMailboxTotals}
                  scope="current"
                  expandedMailboxIds={expandedMailboxIds}
                  onToggle={toggleMailboxExpanded}
                />
              )}
              <p className="px-1 text-xs text-muted-foreground">Week {currentWeek.label}</p>
            </div>

            <div className="space-y-3">
              <div className="space-y-2">
                <h2 className="text-sm font-semibold text-primary uppercase tracking-wider px-1">Previous weeks</h2>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-muted-foreground">Week of</span>
                  <select
                    aria-label="Previous weeks"
                    value={historicalWeeksAgo}
                    onChange={(e) => setHistoricalWeeksAgo(Number(e.target.value))}
                    className="h-9 rounded-lg border border-input bg-card px-2 text-sm font-medium text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                  >
                    {[1, 2, 3, 4, 5, 6].map((w) => (
                      <option key={w} value={w}>
                        {getWeekRange(w).label}
                      </option>
                    ))}
                  </select>
                </div>

                {historicalLoading ? (
                  <div className="py-4 text-center text-sm text-muted-foreground">Loading week...</div>
                ) : historicalMailboxTotals.length === 0 ? (
                  <div className="py-4 text-center text-sm text-muted-foreground">No mailboxes</div>
                ) : (
                  <MailboxWeekCards
                    mailboxes={historicalMailboxTotals}
                    scope="historical"
                    expandedMailboxIds={expandedMailboxIds}
                    onToggle={toggleMailboxExpanded}
                  />
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="rounded-xl border bg-card p-3 space-y-2">
              <select
                aria-label="Expected Mailbox"
                value={mailboxId}
                onChange={(e) => setMailboxId(e.target.value)}
                className="w-full h-10 rounded-lg border border-input bg-background px-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="">Select mailbox</option>
                {(currentSummary?.mailboxes || []).map((mb) => (
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
                {submittingRequest ? "Creating..." : "Create Mail Request"}
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
                  const detail = req.expectedSender || req.description || "-";
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
        )}
      </div>
    </div>
  );
};

export default MemberDashboard;
