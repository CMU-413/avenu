import { useNavigate } from "react-router-dom";
import { ClipboardList, Bell, MailOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAppStore } from "@/lib/store";
import { sessionLogout } from "@/lib/api";

const AdminHome = () => {
  const navigate = useNavigate();
  const logout = useAppStore((s) => s.logout);

  const handleLogout = async () => {
    try {
      await sessionLogout();
    } finally {
      logout();
      navigate("/");
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="flex items-center justify-between px-4 h-14">
          <h1 className="text-lg font-bold text-foreground">Avenu Admin</h1>
          <button onClick={handleLogout} className="text-muted-foreground hover:text-foreground transition-colors text-sm">
            Logout
          </button>
        </div>
      </header>

      <div className="px-4 py-6 max-w-lg mx-auto space-y-3">
        <Button onClick={() => navigate("/admin/recording")} className="w-full h-14 justify-start gap-3 text-base">
          <ClipboardList className="h-5 w-5" />
          Record Mail
        </Button>

        <Button onClick={() => navigate("/admin/notifications")} className="w-full h-14 justify-start gap-3 text-base" variant="secondary">
          <Bell className="h-5 w-5" />
          Send Weekly Notifications
        </Button>

        <Button onClick={() => navigate("/admin/mail-requests")} className="w-full h-14 justify-start gap-3 text-base" variant="secondary">
          <MailOpen className="h-5 w-5" />
          View Expected Mail Requests
        </Button>
      </div>
    </div>
  );
};

export default AdminHome;
