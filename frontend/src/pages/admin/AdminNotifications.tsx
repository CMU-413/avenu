import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { useAppStore } from "@/lib/store";
import { ApiError, listUsers, sendMailArrivedNotification, sendWeeklySummaryNotification } from "@/lib/api";

function computePreviousWeekRange(reference: Date): { weekStart: string; weekEnd: string } {
  const date = new Date(reference);
  date.setHours(0, 0, 0, 0);
  const daysSinceMonday = (date.getDay() + 6) % 7;
  const currentWeekStart = new Date(date);
  currentWeekStart.setDate(date.getDate() - daysSinceMonday);

  const previousWeekStart = new Date(currentWeekStart);
  previousWeekStart.setDate(currentWeekStart.getDate() - 7);
  const previousWeekEnd = new Date(currentWeekStart);
  previousWeekEnd.setDate(currentWeekStart.getDate() - 1);

  const formatDate = (value: Date) => value.toISOString().slice(0, 10);
  return {
    weekStart: formatDate(previousWeekStart),
    weekEnd: formatDate(previousWeekEnd),
  };
}

const AdminNotifications = () => {
  const navigate = useNavigate();
  const logout = useAppStore((s) => s.logout);
  const { toast } = useToast();

  const [users, setUsers] = useState<{ id: string; fullname: string }[]>([]);
  const [selectedUserId, setSelectedUserId] = useState("");
  const [sendingWeekly, setSendingWeekly] = useState(false);
  const [sendingSpecial, setSendingSpecial] = useState(false);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const userItems = await listUsers();
        if (!alive) return;
        setUsers(
          userItems
            .filter((item) => item.isAdmin !== true)
            .map((item) => ({ id: item.id, fullname: item.fullname }))
        );
      } catch (err) {
        if (!alive) return;
        const message = err instanceof Error ? err.message : "Failed to load notification data";
        toast({ title: message, variant: "destructive" });
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          logout();
          navigate("/");
        }
      }
    };

    load();
    return () => {
      alive = false;
    };
  }, [logout, navigate, toast]);

  const handleSendWeekly = async () => {
    if (!selectedUserId) {
      toast({ title: "Select a recipient", variant: "destructive" });
      return;
    }

    const { weekStart, weekEnd } = computePreviousWeekRange(new Date());
    if (!window.confirm(`Send Weekly Mail Notification for ${weekStart} to ${weekEnd}?`)) {
      return;
    }

    setSendingWeekly(true);
    try {
      const result = await sendWeeklySummaryNotification({
        userId: selectedUserId,
        weekStart,
        weekEnd,
      });
      if (result.status === "sent") {
        toast({ title: "Weekly notification sent" });
      } else {
        toast({ title: `Weekly notification ${result.status}`, description: result.reason || undefined });
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to send weekly notification";
      toast({ title: message, variant: "destructive" });
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        logout();
        navigate("/");
      }
    } finally {
      setSendingWeekly(false);
    }
  };

  const handleSendSpecial = async () => {
    if (!selectedUserId) {
      toast({ title: "Select a recipient", variant: "destructive" });
      return;
    }
    if (!window.confirm("Send Mail Arrived Notification?")) {
      return;
    }

    setSendingSpecial(true);
    try {
      const result = await sendMailArrivedNotification({
        userId: selectedUserId,
      });
      if (result.status === "sent") {
        toast({ title: "Notification sent" });
      } else {
        toast({ title: `Notification ${result.status}`, description: result.reason || undefined });
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to send notification";
      toast({ title: message, variant: "destructive" });
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        logout();
        navigate("/");
      }
    } finally {
      setSendingSpecial(false);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur">
        <div className="relative flex items-center justify-center px-4 h-14">
          <button
            onClick={() => navigate("/admin")}
            className="absolute left-4 text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <h1 className="text-lg font-bold text-foreground">Avenu</h1>
        </div>
      </header>

      <div className="px-4 py-6 max-w-lg mx-auto space-y-3">
        <select
          value={selectedUserId}
          onChange={(e) => setSelectedUserId(e.target.value)}
          className="w-full h-10 rounded-lg border border-input bg-background px-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="">Select recipient</option>
          {users.map((user) => (
            <option key={user.id} value={user.id}>
              {user.fullname}
            </option>
          ))}
        </select>

        <Button onClick={handleSendWeekly} disabled={sendingWeekly || sendingSpecial} className="w-full h-11 text-sm">
          {sendingWeekly ? "Sending..." : "Send Weekly Mail Notification"}
        </Button>

        <Button onClick={handleSendSpecial} disabled={sendingWeekly || sendingSpecial} className="w-full h-11 text-sm">
          {sendingSpecial ? "Sending..." : "Send Mail Arrived Notification"}
        </Button>
      </div>
    </div>
  );
};

export default AdminNotifications;
