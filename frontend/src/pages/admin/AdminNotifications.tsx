import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { useAppStore } from "@/lib/store";
import { ApiError, listUsers, sendMailArrivedNotification } from "@/lib/api";

const AdminNotifications = () => {
  const navigate = useNavigate();
  const logout = useAppStore((s) => s.logout);
  const { toast } = useToast();

  const [users, setUsers] = useState<{ id: string; fullname: string }[]>([]);
  const [selectedUserId, setSelectedUserId] = useState("");
  const [sending, setSending] = useState(false);

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

  const handleSend = async () => {
    if (!selectedUserId) {
      toast({ title: "Select a recipient", variant: "destructive" });
      return;
    }
    if (!window.confirm("Send Mail Arrived Notification?")) {
      return;
    }

    setSending(true);
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
      setSending(false);
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

        <Button onClick={handleSend} disabled={sending} className="w-full h-11 text-sm">
          {sending ? "Sending..." : "Send Mail Arrived Notification"}
        </Button>
      </div>
    </div>
  );
};

export default AdminNotifications;
