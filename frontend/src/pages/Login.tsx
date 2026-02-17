import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAppStore } from "@/lib/store";
import { members } from "@/lib/mock-data";
import { Mail } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError, listMailboxes, sessionLogin } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

const Login = () => {
  const navigate = useNavigate();
  const login = useAppStore((s) => s.login);
  const { toast } = useToast();
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!email.trim()) {
      toast({ title: "Enter email", variant: "destructive" });
      return;
    }
    setLoading(true);
    try {
      const normalized = email.trim().toLowerCase();
      await sessionLogin(normalized);

      try {
        await listMailboxes();
        login("admin");
        navigate("/admin");
        return;
      } catch (roleErr) {
        if (roleErr instanceof ApiError && roleErr.status === 403) {
          const member = members.find((m) => m.email.toLowerCase() === normalized);
          login("member", member?.id);
          navigate("/member");
          return;
        }
        throw roleErr;
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to sign in";
      toast({ title: message, variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm space-y-8">
        <div className="text-center space-y-2">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-primary">
            <Mail className="h-7 w-7 text-primary-foreground" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Avenu</h1>
          <p className="text-sm text-muted-foreground">Coworking mail management</p>
        </div>

        <div className="space-y-3">
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full h-10 rounded-lg border border-input bg-background px-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <Button onClick={handleSubmit} className="w-full h-12 text-base" variant="default" disabled={loading}>
              {loading ? "Signing in..." : "Sign in"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;
