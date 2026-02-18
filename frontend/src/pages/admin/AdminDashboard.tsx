import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAppStore } from "@/lib/store";
import { Plus, LogOut, Mail, Package, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError, listMail, listMailboxes, sessionLogout } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

const AdminDashboard = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const logout = useAppStore((s) => s.logout);
  const { toast } = useToast();
  const [selectedDate, setSelectedDate] = useState(
    () => searchParams.get("date") || new Date().toISOString().split("T")[0]
  );
  const [mailboxes, setMailboxes] = useState<
    { id: string; name: string; type: "company" | "personal" }[]
  >([]);
  const [records, setRecords] = useState<
    { id: string; mailboxId: string; type: "letter" | "package"; count: number }[]
  >([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    const loadMailboxes = async () => {
      try {
        const items = await listMailboxes();
        if (!alive) return;
        setMailboxes(
          items.map((mb) => ({
            id: mb.id,
            name: mb.displayName,
            type: mb.type === "team" ? "company" : "personal",
          }))
        );
      } catch (err) {
        if (!alive) return;
        const message = err instanceof Error ? err.message : "Failed to load mailboxes";
        toast({ title: message, variant: "destructive" });
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          logout();
          navigate("/");
        }
      }
    };
    loadMailboxes();
    return () => {
      alive = false;
    };
  }, [logout, navigate, toast]);

  useEffect(() => {
    let alive = true;
    const loadMail = async () => {
      setLoading(true);
      try {
        const items = await listMail({ date: selectedDate });
        if (!alive) return;
        setRecords(
          items.map((item) => ({
            id: item.id,
            mailboxId: item.mailboxId,
            type: item.type,
            count: item.count,
          }))
        );
      } catch (err) {
        if (!alive) return;
        const message = err instanceof Error ? err.message : "Failed to load records";
        toast({ title: message, variant: "destructive" });
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          logout();
          navigate("/");
        }
      } finally {
        if (alive) setLoading(false);
      }
    };
    loadMail();
    return () => {
      alive = false;
    };
  }, [selectedDate, logout, navigate, toast]);

  useEffect(() => {
    setSearchParams({ date: selectedDate }, { replace: true });
  }, [selectedDate, setSearchParams]);

  const aggregated = useMemo(() => {
    const map = new Map<string, { letters: number; packages: number }>();
    for (const r of records) {
      const existing = map.get(r.mailboxId) || { letters: 0, packages: 0 };
      map.set(r.mailboxId, {
        letters: existing.letters + (r.type === "letter" ? r.count : 0),
        packages: existing.packages + (r.type === "package" ? r.count : 0),
      });
    }
    return Array.from(map.entries())
      .map(([mbId, counts]) => ({
        mailbox: mailboxes.find((m) => m.id === mbId),
        ...counts,
      }))
      .filter((item) => !!item.mailbox);
  }, [mailboxes, records]);

  const handleLogout = async () => {
    try {
      await sessionLogout();
    } finally {
      logout();
      navigate("/");
    }
  };

  const formatDisplayDate = (dateStr: string) => {
    const d = new Date(dateStr + "T12:00:00");
    return d.toLocaleDateString("en-US", { month: "numeric", day: "numeric", year: "2-digit" });
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="flex items-center justify-between px-4 h-14">
          <button onClick={() => navigate("/admin")} className="text-muted-foreground hover:text-foreground transition-colors">
            <ArrowLeft className="h-5 w-5" />
          </button>
          <h1 className="text-lg font-bold text-foreground">Avenu</h1>
          <button onClick={handleLogout} className="text-muted-foreground hover:text-foreground transition-colors">
            <LogOut className="h-5 w-5" />
          </button>
        </div>
      </header>

      <div className="px-4 py-4 space-y-4 max-w-lg mx-auto">
        <input
          type="date"
          value={selectedDate}
          onChange={(e) => setSelectedDate(e.target.value)}
          className="w-full h-11 rounded-lg border border-input bg-card px-3 text-sm font-medium text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        />

        <Button onClick={() => navigate(`/admin/mailboxes?date=${selectedDate}`)} className="w-full h-12 text-base gap-2">
          <Plus className="h-5 w-5" />
          Add Record
        </Button>

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

          {loading ? (
            <div className="py-12 text-center text-muted-foreground text-sm">Loading...</div>
          ) : aggregated.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground text-sm">No records for this date</div>
          ) : (
            <div className="divide-y divide-border rounded-xl border bg-card overflow-hidden">
              {aggregated.map((item, i) => (
                <div
                  key={i}
                  onClick={() => navigate(`/admin/mailboxes/${item.mailbox?.id}?date=${selectedDate}`)}
                  className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-muted/50 transition-colors"
                >
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
