import { apiFetch } from "../../http/client";
import type { ApiTeam } from "../contracts/types";

export function listTeams(): Promise<ApiTeam[]> {
  return apiFetch<ApiTeam[]>("/api/teams");
}
