import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Trash2, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { useConfirmDialog } from "@/hooks/use-confirm-dialog";
import { useAppStore } from "@/lib/store";
import { ApiError, deleteTeam, deleteUser, listTeams, listUsers } from "@/lib/api";

type UserRow = {
  id: string;
  fullname: string;
  email: string;
  teamIds: string[];
};

type TeamRow = {
  id: string;
  name: string;
};

const AdminUsersTeams = () => {
  const navigate = useNavigate();
  const logout = useAppStore((s) => s.logout);
  const { toast } = useToast();
  const confirm = useConfirmDialog();

  const [users, setUsers] = useState<UserRow[]>([]);
  const [teams, setTeams] = useState<TeamRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingKey, setDeletingKey] = useState<string | null>(null);

  const handleUnauthorized = () => {
    logout();
    navigate("/");
  };

  useEffect(() => {
    let alive = true;

    const loadData = async () => {
      setLoading(true);
      try {
        const [userItems, teamItems] = await Promise.all([listUsers(), listTeams()]);
        if (!alive) return;
        setUsers(
          userItems
            .filter((item) => item.isAdmin !== true)
            .map((item) => ({
              id: item.id,
              fullname: item.fullname,
              email: item.email,
              teamIds: item.teamIds,
            })),
        );
        setTeams(
          teamItems.map((item) => ({
            id: item.id,
            name: item.name,
          })),
        );
      } catch (err) {
        if (!alive) return;
        const message = err instanceof Error ? err.message : "Failed to load users and teams";
        toast({ title: message, variant: "destructive" });
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          logout();
          navigate("/");
        }
      } finally {
        if (alive) {
          setLoading(false);
        }
      }
    };

    void loadData();
    return () => {
      alive = false;
    };
  }, [logout, navigate, toast]);

  const teamMemberCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const user of users) {
      for (const teamId of user.teamIds) {
        counts.set(teamId, (counts.get(teamId) || 0) + 1);
      }
    }
    return counts;
  }, [users]);

  const teamNamesById = useMemo(() => {
    return new Map(teams.map((team) => [team.id, team.name]));
  }, [teams]);

  const handleDeleteUser = async (user: UserRow) => {
    const confirmed = await confirm({
      title: "Delete User",
      message: `Delete ${user.fullname}? This permanently removes the user and their mailbox records.`,
      confirmLabel: "Delete User",
      cancelLabel: "Cancel",
    });
    if (!confirmed) return;

    setDeletingKey(`user:${user.id}`);
    try {
      await deleteUser(user.id);
      setUsers((current) => current.filter((item) => item.id !== user.id));
      toast({ title: "User deleted" });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to delete user";
      toast({ title: message, variant: "destructive" });
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        handleUnauthorized();
      }
    } finally {
      setDeletingKey(null);
    }
  };

  const handleDeleteTeam = async (team: TeamRow, pruneUsers: boolean) => {
    const memberCount = teamMemberCounts.get(team.id) || 0;
    const confirmed = await confirm({
      title: pruneUsers ? "Prune And Delete Team" : "Delete Team",
      message: pruneUsers
        ? `Delete ${team.name} and remove ${memberCount} member association${memberCount === 1 ? "" : "s"} first?`
        : `Delete ${team.name}? This is only allowed when no users still belong to the team.`,
      confirmLabel: pruneUsers ? "Prune And Delete" : "Delete Team",
      cancelLabel: "Cancel",
    });
    if (!confirmed) return;

    setDeletingKey(`team:${team.id}:${pruneUsers ? "prune" : "default"}`);
    try {
      await deleteTeam(team.id, pruneUsers ? { pruneUsers: true } : undefined);
      setTeams((current) => current.filter((item) => item.id !== team.id));
      if (pruneUsers) {
        setUsers((current) =>
          current.map((user) => ({
            ...user,
            teamIds: user.teamIds.filter((teamId) => teamId !== team.id),
          })),
        );
      }
      toast({ title: "Team deleted" });
    } catch (err) {
      if (err instanceof ApiError && err.status === 409 && !pruneUsers) {
        toast({
          title: "Team still has members",
          description: "Use Prune And Delete to remove member associations first.",
          variant: "destructive",
        });
        return;
      }
      const message = err instanceof Error ? err.message : "Failed to delete team";
      toast({ title: message, variant: "destructive" });
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        handleUnauthorized();
      }
    } finally {
      setDeletingKey(null);
    }
  };

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
          <h1 className="text-lg font-bold text-foreground">Manage Users & Teams</h1>
        </div>
      </header>

      <div className="px-4 py-6 max-w-4xl mx-auto space-y-6">
        {loading ? (
          <div className="py-12 text-center text-sm text-muted-foreground">Loading...</div>
        ) : (
          <>
            <section className="space-y-2">
              <div className="flex items-center gap-2 px-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <Users className="h-3.5 w-3.5" />
                Users
              </div>
              <div className="rounded-xl border bg-card overflow-hidden">
                {users.length === 0 ? (
                  <div className="px-4 py-8 text-sm text-muted-foreground">No non-admin users found.</div>
                ) : (
                  <div className="divide-y divide-border">
                    {users.map((user) => (
                      <div key={user.id} className="flex items-center justify-between gap-3 px-4 py-3">
                        <div className="min-w-0">
                          <div className="text-sm font-medium text-card-foreground">{user.fullname}</div>
                          <div className="text-xs text-muted-foreground">{user.email}</div>
                          <div className="text-xs text-muted-foreground">
                            Teams:{" "}
                            {user.teamIds.length === 0
                              ? "None"
                              : user.teamIds.map((teamId) => teamNamesById.get(teamId) || teamId).join(", ")}
                          </div>
                        </div>
                        <Button
                          variant="destructive"
                          size="sm"
                          disabled={deletingKey !== null}
                          onClick={() => handleDeleteUser(user)}
                        >
                          <Trash2 className="h-4 w-4" />
                          {deletingKey === `user:${user.id}` ? "Deleting..." : "Delete"}
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </section>

            <section className="space-y-2">
              <div className="flex items-center gap-2 px-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <Users className="h-3.5 w-3.5" />
                Teams
              </div>
              <div className="rounded-xl border bg-card overflow-hidden">
                {teams.length === 0 ? (
                  <div className="px-4 py-8 text-sm text-muted-foreground">No teams found.</div>
                ) : (
                  <div className="divide-y divide-border">
                    {teams.map((team) => {
                      const memberCount = teamMemberCounts.get(team.id) || 0;
                      const defaultDeleteKey = `team:${team.id}:default`;
                      const pruneDeleteKey = `team:${team.id}:prune`;

                      return (
                        <div key={team.id} className="flex items-center justify-between gap-3 px-4 py-3">
                          <div className="min-w-0">
                            <div className="text-sm font-medium text-card-foreground">{team.name}</div>
                            <div className="text-xs text-muted-foreground">
                              {memberCount} member{memberCount === 1 ? "" : "s"}
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <Button
                              variant="destructive"
                              size="sm"
                              disabled={deletingKey !== null}
                              onClick={() => handleDeleteTeam(team, false)}
                            >
                              <Trash2 className="h-4 w-4" />
                              {deletingKey === defaultDeleteKey ? "Deleting..." : "Delete"}
                            </Button>
                            {memberCount > 0 ? (
                              <Button
                                variant="outline"
                                size="sm"
                                disabled={deletingKey !== null}
                                onClick={() => handleDeleteTeam(team, true)}
                              >
                                {deletingKey === pruneDeleteKey ? "Pruning..." : "Prune & Delete"}
                              </Button>
                            ) : null}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </section>
          </>
        )}
      </div>
    </div>
  );
};

export default AdminUsersTeams;
