import { apiFetch } from "../../http/client";
import type { ApiUser } from "../contracts/types";

export function listUsers(): Promise<ApiUser[]> {
  return apiFetch<ApiUser[]>("/users");
}
