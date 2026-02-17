import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { mailboxes } from "@/lib/mock-data";
import { Search, ArrowLeft, ChevronRight } from "lucide-react";

const SearchMailbox = () => {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.toLowerCase().trim();
    if (!q) return { company: mailboxes.filter((m) => m.type === "company"), personal: mailboxes.filter((m) => m.type === "personal") };

    const matchedByName = mailboxes.filter((m) => m.name.toLowerCase().includes(q));
    const matchedByMember = mailboxes.filter(
      (m) => !matchedByName.includes(m) && m.memberNames.some((n) => n.toLowerCase().includes(q))
    );
    const all = [...matchedByName, ...matchedByMember];
    return {
      company: all.filter((m) => m.type === "company"),
      personal: all.filter((m) => m.type === "personal"),
    };
  }, [query]);

  const hasResults = filtered.company.length > 0 || filtered.personal.length > 0;

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur">
        <div className="flex items-center gap-3 px-4 h-14">
          <button onClick={() => navigate("/admin")} className="text-muted-foreground hover:text-foreground transition-colors">
            <ArrowLeft className="h-5 w-5" />
          </button>
          <h1 className="text-lg font-bold text-foreground">Select Mailbox</h1>
        </div>
      </header>

      <div className="px-4 py-4 max-w-lg mx-auto space-y-4">
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search mailbox or member name..."
            autoFocus
            className="w-full h-11 rounded-lg border border-input bg-card pl-10 pr-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        {!hasResults && (
          <p className="py-8 text-center text-sm text-muted-foreground">No mailboxes found</p>
        )}

        {/* Company */}
        {filtered.company.length > 0 && (
          <div className="space-y-1">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-primary px-1">Company</h3>
            <div className="divide-y divide-border rounded-xl border bg-card overflow-hidden">
              {filtered.company.map((mb) => (
                <button
                  key={mb.id}
                  onClick={() => navigate(`/admin/add/record/${mb.id}`)}
                  className="w-full flex items-center justify-between px-4 py-3 hover:bg-muted/50 transition-colors text-left"
                >
                  <span className="text-sm font-medium text-card-foreground">{mb.name}</span>
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Personal */}
        {filtered.personal.length > 0 && (
          <div className="space-y-1">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-primary px-1">Personal</h3>
            <div className="divide-y divide-border rounded-xl border bg-card overflow-hidden">
              {filtered.personal.map((mb) => (
                <button
                  key={mb.id}
                  onClick={() => navigate(`/admin/add/record/${mb.id}`)}
                  className="w-full flex items-center justify-between px-4 py-3 hover:bg-muted/50 transition-colors text-left"
                >
                  <span className="text-sm font-medium text-card-foreground">{mb.name}</span>
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SearchMailbox;
