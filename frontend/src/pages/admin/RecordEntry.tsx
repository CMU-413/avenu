import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAppStore } from "@/lib/store";
import { mailboxes } from "@/lib/mock-data";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";

const RecordEntry = () => {
  const { mailboxId } = useParams<{ mailboxId: string }>();
  const navigate = useNavigate();
  const addRecord = useAppStore((s) => s.addRecord);
  const { toast } = useToast();

  const mailbox = mailboxes.find((m) => m.id === mailboxId);

  const [date, setDate] = useState(() => new Date().toISOString().split("T")[0]);
  const [letters, setLetters] = useState(0);
  const [packages, setPackages] = useState(0);

  if (!mailbox) {
    return (
      <div className="min-h-screen flex items-center justify-center text-muted-foreground">
        Mailbox not found
      </div>
    );
  }

  const handleSave = () => {
    if (letters === 0 && packages === 0) {
      toast({ title: "Enter at least 1 letter or package", variant: "destructive" });
      return;
    }
    addRecord({ mailboxId: mailbox.id, date, letters, packages });
    toast({ title: "Record saved" });
    navigate("/admin");
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur">
        <div className="flex items-center gap-3 px-4 h-14">
          <button onClick={() => navigate(-1)} className="text-muted-foreground hover:text-foreground transition-colors">
            <ArrowLeft className="h-5 w-5" />
          </button>
          <h1 className="text-lg font-bold text-foreground truncate">{mailbox.name}</h1>
        </div>
      </header>

      <div className="px-4 py-6 max-w-lg mx-auto space-y-6">
        {/* Date */}
        <div className="space-y-1.5">
          <label className="text-sm font-medium text-foreground">Date</label>
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="w-full h-11 rounded-lg border border-input bg-card px-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        {/* Letters */}
        <div className="space-y-1.5">
          <label className="text-sm font-medium text-foreground">Letters</label>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setLetters(Math.max(0, letters - 1))}
              className="h-11 w-11 rounded-lg border border-input bg-card text-foreground text-xl font-medium flex items-center justify-center hover:bg-muted transition-colors"
            >
              −
            </button>
            <span className="text-2xl font-bold text-foreground w-12 text-center">{letters}</span>
            <button
              onClick={() => setLetters(letters + 1)}
              className="h-11 w-11 rounded-lg border border-input bg-card text-foreground text-xl font-medium flex items-center justify-center hover:bg-muted transition-colors"
            >
              +
            </button>
          </div>
        </div>

        {/* Packages */}
        <div className="space-y-1.5">
          <label className="text-sm font-medium text-foreground">Packages</label>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setPackages(Math.max(0, packages - 1))}
              className="h-11 w-11 rounded-lg border border-input bg-card text-foreground text-xl font-medium flex items-center justify-center hover:bg-muted transition-colors"
            >
              −
            </button>
            <span className="text-2xl font-bold text-foreground w-12 text-center">{packages}</span>
            <button
              onClick={() => setPackages(packages + 1)}
              className="h-11 w-11 rounded-lg border border-input bg-card text-foreground text-xl font-medium flex items-center justify-center hover:bg-muted transition-colors"
            >
              +
            </button>
          </div>
        </div>

        <Button onClick={handleSave} className="w-full h-12 text-base">
          Save
        </Button>
      </div>
    </div>
  );
};

export default RecordEntry;
