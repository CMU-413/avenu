import { useNavigate } from "react-router-dom";
import { useAppStore } from "@/lib/store";
import { ArrowLeft } from "lucide-react";
import { Switch } from "@/components/ui/switch";

const NotificationSettings = () => {
  const navigate = useNavigate();
  const { currentMemberId, members, toggleNotifications } = useAppStore();
  const member = members.find((m) => m.id === currentMemberId);

  if (!member) return null;

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
            checked={member.emailNotifications}
            onCheckedChange={() => toggleNotifications(member.id)}
          />
        </div>
      </div>
    </div>
  );
};

export default NotificationSettings;
