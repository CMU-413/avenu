import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useAppStore } from "@/lib/store";
import { mailboxes } from "@/lib/mock-data";
import { Settings, LogOut, Mail, Package } from "lucide-react";

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function getWeekRange(weeksAgo: number) {
  const now = new Date();
  const dayOfWeek = now.getDay();
  const startOfThisWeek = new Date(now);
  startOfThisWeek.setDate(now.getDate() - dayOfWeek - weeksAgo * 7);
  startOfThisWeek.setHours(0, 0, 0, 0);

  const endOfWeek = new Date(startOfThisWeek);
  endOfWeek.setDate(startOfThisWeek.getDate() + 6);

  const dates: string[] = [];
  for (let i = 0; i < 7; i++) {
    const d = new Date(startOfThisWeek);
    d.setDate(startOfThisWeek.getDate() + i);
    dates.push(d.toISOString().split("T")[0]);
  }

  const formatShort = (d: Date) =>
    `${d.getMonth() + 1}/${d.getDate()}`;

  return {
    label: `${formatShort(startOfThisWeek)} – ${formatShort(endOfWeek)}`,
    dates,
  };
}

const MemberDashboard = () => {
  const navigate = useNavigate();
  const { records, currentMemberId, members, logout } = useAppStore();
  const [weeksAgo, setWeeksAgo] = useState(0);

  const member = members.find((m) => m.id === currentMemberId);
  const memberMailboxes = mailboxes.filter((mb) => member?.mailboxIds.includes(mb.id));

  const week = useMemo(() => getWeekRange(weeksAgo), [weeksAgo]);

  const handleLogout = () => {
    logout();
    navigate("/");
  };

  if (!member) {
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
        {memberMailboxes.map((mb) => {
          const mbRecords = records.filter(
            (r) => r.mailboxId === mb.id && week.dates.includes(r.date)
          );

          return (
            <div key={mb.id} className="space-y-2">
              <h2 className="text-sm font-semibold text-primary uppercase tracking-wider px-1">
                {mb.type === "personal" ? "You received" : `${mb.name} received`}
              </h2>
              <div className="rounded-xl border bg-card overflow-hidden divide-y divide-border">
                {week.dates.map((date, i) => {
                  const dayRecords = mbRecords.filter((r) => r.date === date);
                  const totalLetters = dayRecords.reduce((s, r) => s + r.letters, 0);
                  const totalPackages = dayRecords.reduce((s, r) => s + r.packages, 0);
                  const hasMail = totalLetters > 0 || totalPackages > 0;

                  return (
                    <div key={date} className="flex items-center justify-between px-4 py-2.5">
                      <span className="text-sm font-medium text-card-foreground w-10">{DAYS[i]}</span>
                      {hasMail ? (
                        <div className="flex items-center gap-3 text-sm">
                          {totalLetters > 0 && (
                            <span className="flex items-center gap-1 text-card-foreground">
                              {totalLetters} <Mail className="h-3.5 w-3.5 text-muted-foreground" />
                            </span>
                          )}
                          {totalPackages > 0 && (
                            <span className="flex items-center gap-1 text-card-foreground">
                              {totalPackages} <Package className="h-3.5 w-3.5 text-muted-foreground" />
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
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default MemberDashboard;
