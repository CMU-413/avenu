import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useAppStore } from "@/lib/store";
import { mailboxes } from "@/lib/mock-data";
import { Plus, LogOut, Search, Mail, Package } from "lucide-react";
import { Button } from "@/components/ui/button";

const AdminDashboard = () => {
  const navigate = useNavigate();
  const { records, logout } = useAppStore();
  const [selectedDate, setSelectedDate] = useState(() => new Date().toISOString().split("T")[0]);

  const dayRecords = useMemo(() => {
    return records.filter((r) => r.date === selectedDate);
  }, [records, selectedDate]);

  // Aggregate by mailbox
  const aggregated = useMemo(() => {
    const map = new Map<string, { letters: number; packages: number }>();
    for (const r of dayRecords) {
      const existing = map.get(r.mailboxId) || { letters: 0, packages: 0 };
      map.set(r.mailboxId, {
        letters: existing.letters + r.letters,
        packages: existing.packages + r.packages,
      });
    }
    return Array.from(map.entries()).map(([mbId, counts]) => ({
      mailbox: mailboxes.find((m) => m.id === mbId),
      ...counts,
    }));
  }, [dayRecords]);

  const handleLogout = () => {
    logout();
    navigate("/");
  };

  const formatDisplayDate = (dateStr: string) => {
    const d = new Date(dateStr + "T12:00:00");
    return d.toLocaleDateString("en-US", { month: "numeric", day: "numeric", year: "2-digit" });
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="flex items-center justify-between px-4 h-14">
          <h1 className="text-lg font-bold text-foreground">Avenu</h1>
          <button onClick={handleLogout} className="text-muted-foreground hover:text-foreground transition-colors">
            <LogOut className="h-5 w-5" />
          </button>
        </div>
      </header>

      <div className="px-4 py-4 space-y-4 max-w-lg mx-auto">
        {/* Date selector */}
        <input
          type="date"
          value={selectedDate}
          onChange={(e) => setSelectedDate(e.target.value)}
          className="w-full h-11 rounded-lg border border-input bg-card px-3 text-sm font-medium text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        />

        {/* Add record button */}
        <Button onClick={() => navigate("/admin/add")} className="w-full h-12 text-base gap-2">
          <Plus className="h-5 w-5" />
          Add Record
        </Button>

        {/* Records list */}
        <div className="space-y-1">
          <div className="flex items-center justify-between px-1 pb-2">
            <h2 className="text-sm font-semibold text-foreground uppercase tracking-wider">
              Recorded — {formatDisplayDate(selectedDate)}
            </h2>
            <div className="flex items-center gap-3 text-xs font-medium text-muted-foreground">
              <span className="flex items-center gap-1">
                <Mail className="h-3.5 w-3.5" /> L
              </span>
              <span className="flex items-center gap-1">
                <Package className="h-3.5 w-3.5" /> P
              </span>
            </div>
          </div>

          {aggregated.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground text-sm">
              No records for this date
            </div>
          ) : (
            <div className="divide-y divide-border rounded-xl border bg-card overflow-hidden">
              {aggregated.map((item, i) => (
                <div key={i} onClick={() => navigate(`/admin/add/record/${item.mailbox?.id}`)} className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-muted/50 transition-colors">
                  <div>
                    <p className="text-sm font-medium text-card-foreground">{item.mailbox?.name}</p>
                    <p className="text-xs text-muted-foreground capitalize">{item.mailbox?.type}</p>
                  </div>
                  <div className="flex items-center gap-6 text-sm font-mono">
                    <span className="text-card-foreground w-6 text-center">{item.letters}</span>
                    <span className="text-card-foreground w-6 text-center">{item.packages}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AdminDashboard;
