import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Search, ArrowLeft, ChevronRight } from "lucide-react";
import { ApiError, listMailboxes, listTeams, listUsers } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import { useAppStore } from "@/lib/store";

type MailboxResult = {
  id: string;
  name: string;
  type: "company" | "personal";
  memberNames: string[];
};

type FilteredMailboxResult = MailboxResult & {
  matchedMemberNames: string[];
};

function formatMemberMatchHint(names: string[]): string | null {
  if (names.length === 0) {
    return null;
  }
  if (names.length === 1) {
    return `Member match: ${names[0]}`;
  }
  return `Member match: ${names[0]} +${names.length - 1} more`;
}

const SearchMailbox = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const selectedDate = new URLSearchParams(location.search).get("date");
  const logout = useAppStore((s) => s.logout);
  const { adminOcr, ocrQueueV2 } = useAppStore((s) => s.featureFlags);
  const { toast } = useToast();
  const [query, setQuery] = useState("");
  const [mailboxes, setMailboxes] = useState<MailboxResult[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      setLoading(true);
      try {
        const [mailboxList, userList, teamList] = await Promise.all([
          listMailboxes(),
          listUsers(),
          listTeams(),
        ]);
        if (!alive) return;

        const usersById = new Map(userList.map((u) => [u.id, u]));
        const teamMembers = new Map<string, string[]>();
        for (const team of teamList) {
          teamMembers.set(
            team.id,
            userList
              .filter((u) => u.teamIds.includes(team.id))
              .map((u) => u.fullname)
          );
        }

        setMailboxes(
          mailboxList.map((mb) => {
            const memberNames =
              mb.type === "user"
                ? [usersById.get(mb.refId)?.fullname].filter(Boolean) as string[]
                : teamMembers.get(mb.refId) || [];
            return {
              id: mb.id,
              name: mb.displayName,
              type: mb.type === "team" ? "company" : "personal",
              memberNames,
            };
          })
        );
      } catch (err) {
        if (!alive) return;
        const message = err instanceof Error ? err.message : "Failed to load mailboxes";
        toast({ title: message, variant: "destructive" });
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          logout();
          navigate("/");
        }
      } finally {
        if (alive) setLoading(false);
      }
    };

    load();
    return () => {
      alive = false;
    };
  }, [logout, navigate, toast]);

  const filtered = useMemo(() => {
    const q = query.toLowerCase().trim();
    const grouped = (items: FilteredMailboxResult[]) => ({
      company: items.filter((m) => m.type === "company"),
      personal: items.filter((m) => m.type === "personal"),
    });

    if (!q) {
      return grouped(mailboxes.map((m) => ({ ...m, matchedMemberNames: [] })));
    }

    const matches = mailboxes
      .map((m) => ({
        ...m,
        nameMatches: m.name.toLowerCase().includes(q),
        matchedMemberNames: m.memberNames.filter((n) => n.toLowerCase().includes(q)),
      }))
      .filter((m) => m.nameMatches || m.matchedMemberNames.length > 0)
      .map(({ nameMatches: _nameMatches, ...m }) => m);

    return grouped(matches);
  }, [mailboxes, query]);

  const hasResults = filtered.company.length > 0 || filtered.personal.length > 0;

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur">
        <div className="flex items-center gap-3 px-4 h-14">
          <button
            onClick={() =>
              navigate(
                adminOcr && ocrQueueV2
                  ? `/admin/recording${selectedDate ? `?date=${selectedDate}` : ""}`
                  : "/admin"
              )
            }
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
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

        {loading && (
          <p className="py-8 text-center text-sm text-muted-foreground">Loading...</p>
        )}

        {!loading && !hasResults && (
          <p className="py-8 text-center text-sm text-muted-foreground">No mailboxes found</p>
        )}

        {/* Company */}
        {filtered.company.length > 0 && (
          <div className="space-y-1">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-primary px-1">Company</h3>
            <div className="divide-y divide-border rounded-xl border bg-card overflow-hidden">
              {filtered.company.map((mb) => {
                const memberMatchHint = formatMemberMatchHint(mb.matchedMemberNames);
                return (
                  <button
                    key={mb.id}
                    onClick={() => navigate(`/admin/mailboxes/${mb.id}${selectedDate ? `?date=${selectedDate}` : ""}`)}
                    className="w-full flex items-center justify-between gap-3 px-4 py-3 hover:bg-muted/50 transition-colors text-left"
                  >
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-card-foreground">{mb.name}</div>
                      {memberMatchHint && (
                        <div className="text-xs text-muted-foreground">{memberMatchHint}</div>
                      )}
                    </div>
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  </button>
                );
              })}
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
                  onClick={() => navigate(`/admin/mailboxes/${mb.id}${selectedDate ? `?date=${selectedDate}` : ""}`)}
                  className="w-full flex items-center justify-between gap-3 px-4 py-3 hover:bg-muted/50 transition-colors text-left"
                >
                  <span className="min-w-0 text-sm font-medium text-card-foreground">{mb.name}</span>
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
