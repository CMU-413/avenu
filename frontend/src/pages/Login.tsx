import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAppStore } from "@/lib/store";
import { members } from "@/lib/mock-data";
import { Mail } from "lucide-react";
import { Button } from "@/components/ui/button";

const Login = () => {
  const navigate = useNavigate();
  const login = useAppStore((s) => s.login);
  const [selectedMember, setSelectedMember] = useState(members[0].id);

  const handleAdmin = () => {
    login("admin");
    navigate("/admin");
  };

  const handleMember = () => {
    login("member", selectedMember);
    navigate("/member");
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
          <Button onClick={handleAdmin} className="w-full h-12 text-base" variant="default">
            Sign in as Admin
          </Button>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-background px-2 text-muted-foreground">or</span>
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">Member account</label>
            <select
              value={selectedMember}
              onChange={(e) => setSelectedMember(e.target.value)}
              className="w-full h-10 rounded-lg border border-input bg-background px-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            >
              {members.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
            <Button onClick={handleMember} variant="secondary" className="w-full h-12 text-base">
              Sign in as Member
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;
