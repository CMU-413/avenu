import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAppStore } from "@/lib/store";
import { ArrowLeft } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { ApiError, updateMemberPreferences } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

const NotificationSettings = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { sessionUser, logout, setSessionEmailNotifications } = useAppStore();
  const [pending, setPending] = useState(false);
  const [optimisticValue, setOptimisticValue] = useState<boolean | null>(null);
  const emailNotifications =
    optimisticValue !== null ? optimisticValue : sessionUser?.emailNotifications ?? false;

  if (!sessionUser) return null;

  const handleToggle = async (nextValue: boolean) => {
    if (pending) return;
    const prev = sessionUser.emailNotifications;
    setPending(true);
    setOptimisticValue(nextValue);
    try {
      const updated = await updateMemberPreferences(nextValue);
      setSessionEmailNotifications(updated.emailNotifications);
      setOptimisticValue(updated.emailNotifications);
    } catch (err) {
      setSessionEmailNotifications(prev);
      setOptimisticValue(prev);
      const message = err instanceof Error ? err.message : "Failed to update notification settings";
      toast({ title: message, variant: "destructive" });
      if (err instanceof ApiError && err.status === 401) {
        logout();
        navigate("/");
      }
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur">
        <div className="flex items-center gap-3 px-4 h-14">
          <button onClick={() => navigate(-1)} className="text-muted-foreground hover:text-foreground transition-colors">
            <ArrowLeft className="h-5 w-5" />
          </button>
          <h1 className="text-lg font-bold text-foreground">Settings</h1>
        </div>
      </header>

      <div className="px-4 py-6 max-w-lg mx-auto">
        <div className="rounded-xl border bg-card p-4 flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-card-foreground">Email Notifications</p>
            <p className="text-xs text-muted-foreground">Receive weekly mail summaries</p>
          </div>
          <Switch
            checked={emailNotifications}
            onCheckedChange={handleToggle}
            disabled={pending}
          />
        </div>
      </div>
    </div>
  );
};

export default NotificationSettings;
