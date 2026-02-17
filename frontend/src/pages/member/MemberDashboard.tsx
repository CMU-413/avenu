import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAppStore } from "@/lib/store";
import { Settings, LogOut, Mail, Package } from "lucide-react";
import { ApiError, ApiMemberMailSummary, getMemberMail, sessionLogout } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function formatIsoDateLocal(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function getWeekRange(weeksAgo: number) {
  const now = new Date();
  now.setHours(12, 0, 0, 0);
  const dayOfWeek = now.getDay();
  const startOfThisWeek = new Date(now);
  startOfThisWeek.setDate(now.getDate() - dayOfWeek - weeksAgo * 7);
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

  const week = useMemo(() => getWeekRange(weeksAgo), [weeksAgo]);

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
      </div>
    </div>
  );
};

export default MemberDashboard;
