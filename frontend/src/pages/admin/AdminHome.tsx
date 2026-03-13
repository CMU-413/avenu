import { useNavigate } from "react-router-dom";
import { ClipboardList, Bell, MailOpen, Wrench, Camera } from "lucide-react";
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

      <div className="px-4 py-6 max-w-lg mx-auto space-y-4">
        <Button
          onClick={() => navigate("/admin/recording")}
          className="w-full h-16 justify-start gap-3 text-base shadow-sm"
        >
          <ClipboardList className="h-5 w-5" />
          Record Mail
        </Button>

        <Button
          onClick={() => navigate("/admin/ocr-queue")}
          className="w-full h-14 justify-start gap-3 text-base shadow-sm"
          variant="secondary"
        >
          <Camera className="h-5 w-5" />
          Bulk OCR Queue
        </Button>

        <section className="rounded-xl border bg-card p-3 space-y-2">
          <div className="flex items-center gap-2 px-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            <Wrench className="h-3.5 w-3.5" />
            Maintenance
          </div>
          <Button
            onClick={() => navigate("/admin/notifications")}
            className="w-full h-10 justify-start gap-2 text-sm"
            variant="secondary"
          >
            <Bell className="h-4 w-4" />
            Send Weekly Notifications (Manual)
          </Button>
          <Button
            onClick={() => navigate("/admin/mail-requests")}
            className="w-full h-10 justify-start gap-2 text-sm"
            variant="secondary"
          >
            <MailOpen className="h-4 w-4" />
            View Expected Mail Requests
          </Button>
        </section>
      </div>
    </div>
  );
};

export default AdminHome;
