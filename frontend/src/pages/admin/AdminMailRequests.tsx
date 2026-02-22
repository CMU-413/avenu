import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { ApiError, listAdminMailRequests, listMailboxes, listUsers } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import { useAppStore } from "@/lib/store";

const AdminMailRequests = () => {
  const navigate = useNavigate();
  const logout = useAppStore((s) => s.logout);
  const { toast } = useToast();

  const [memberIdFilter, setMemberIdFilter] = useState("");
  const [mailboxIdFilter, setMailboxIdFilter] = useState("");
  const [loading, setLoading] = useState(true);

  const [users, setUsers] = useState<{ id: string; fullname: string }[]>([]);
  const [mailboxes, setMailboxes] = useState<{ id: string; displayName: string }[]>([]);
  const [requests, setRequests] = useState<
    {
      id: string;
      memberId: string;
      mailboxId: string;
      expectedSender: string | null;
      description: string | null;
      startDate: string | null;
      endDate: string | null;
      createdAt: string;
    }[]
  >([]);

  useEffect(() => {
    let alive = true;
    const loadLookups = async () => {
      try {
        const [usersResult, mailboxesResult] = await Promise.all([listUsers(), listMailboxes()]);
        if (!alive) return;
        setUsers(usersResult.filter((user) => !user.isAdmin).map((user) => ({ id: user.id, fullname: user.fullname })));
        setMailboxes(mailboxesResult.map((mailbox) => ({ id: mailbox.id, displayName: mailbox.displayName })));
      } catch (err) {
        if (!alive) return;
        const message = err instanceof Error ? err.message : "Failed to load filters";
        toast({ title: message, variant: "destructive" });
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          logout();
          navigate("/");
        }
      }
    };
    void loadLookups();
    return () => {
      alive = false;
    };
  }, [logout, navigate, toast]);

  useEffect(() => {
    let alive = true;
    const loadRequests = async () => {
      setLoading(true);
      try {
        const data = await listAdminMailRequests({
          memberId: memberIdFilter || undefined,
          mailboxId: mailboxIdFilter || undefined,
        });
        if (!alive) return;
        setRequests(data);
      } catch (err) {
        if (!alive) return;
        const message = err instanceof Error ? err.message : "Failed to load requests";
        toast({ title: message, variant: "destructive" });
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          logout();
          navigate("/");
        }
      } finally {
        if (alive) setLoading(false);
      }
    };
    void loadRequests();
    return () => {
      alive = false;
    };
  }, [logout, navigate, toast, memberIdFilter, mailboxIdFilter]);

  const userMap = useMemo(() => new Map(users.map((user) => [user.id, user.fullname])), [users]);
  const mailboxMap = useMemo(() => new Map(mailboxes.map((mailbox) => [mailbox.id, mailbox.displayName])), [mailboxes]);

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
          <h1 className="text-lg font-bold text-foreground">Expected Mail Requests</h1>
        </div>
      </header>

      <div className="px-4 py-6 max-w-4xl mx-auto space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          <div className="space-y-1">
            <label htmlFor="member-filter" className="text-xs font-medium text-muted-foreground">
              Member Filter
            </label>
            <select
              id="member-filter"
              value={memberIdFilter}
              onChange={(e) => setMemberIdFilter(e.target.value)}
              className="w-full h-10 rounded-lg border border-input bg-background px-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="">All members</option>
              {users.map((user) => (
                <option key={user.id} value={user.id}>
                  {user.fullname}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <label htmlFor="mailbox-filter" className="text-xs font-medium text-muted-foreground">
              Mailbox Filter
            </label>
            <select
              id="mailbox-filter"
              value={mailboxIdFilter}
              onChange={(e) => setMailboxIdFilter(e.target.value)}
              className="w-full h-10 rounded-lg border border-input bg-background px-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="">All mailboxes</option>
              {mailboxes.map((mailbox) => (
                <option key={mailbox.id} value={mailbox.id}>
                  {mailbox.displayName}
                </option>
              ))}
            </select>
          </div>
        </div>

        {loading ? (
          <div className="py-12 text-center text-sm text-muted-foreground">Loading...</div>
        ) : requests.length === 0 ? (
          <div className="py-12 text-center text-sm text-muted-foreground">No active requests</div>
        ) : (
          <div className="rounded-xl border bg-card overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-muted/40">
                <tr className="text-left">
                  <th className="px-3 py-2">Member</th>
                  <th className="px-3 py-2">Mailbox</th>
                  <th className="px-3 py-2">Sender / Description</th>
                  <th className="px-3 py-2">Date Window</th>
                  <th className="px-3 py-2">Created</th>
                </tr>
              </thead>
              <tbody>
                {requests.map((request) => (
                  <tr key={request.id} className="border-t">
                    <td className="px-3 py-2">{userMap.get(request.memberId) || request.memberId}</td>
                    <td className="px-3 py-2">{mailboxMap.get(request.mailboxId) || request.mailboxId}</td>
                    <td className="px-3 py-2">{request.expectedSender || request.description || "—"}</td>
                    <td className="px-3 py-2">
                      {request.startDate || request.endDate ? `${request.startDate || "?"} to ${request.endDate || "?"}` : "—"}
                    </td>
                    <td className="px-3 py-2">{new Date(request.createdAt).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default AdminMailRequests;
