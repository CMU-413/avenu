import { apiFetch } from "../../http/client";
import type { ApiTeam } from "../contracts/types";

export function listTeams(): Promise<ApiTeam[]> {
  return apiFetch<ApiTeam[]>("/teams");
}

export function deleteTeam(teamId: string, options?: { pruneUsers?: boolean }): Promise<void> {
  const pruneQuery = options?.pruneUsers ? "?pruneUsers=true" : "";
  return apiFetch<void>(`/teams/${teamId}${pruneQuery}`, {
    method: "DELETE",
  });
}
