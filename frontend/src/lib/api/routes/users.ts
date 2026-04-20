import { apiFetch } from "../../http/client";
import type { ApiUser } from "../contracts/types";

export function listUsers(): Promise<ApiUser[]> {
  return apiFetch<ApiUser[]>("/users");
}

export function deleteUser(userId: string): Promise<void> {
  return apiFetch<void>(`/users/${userId}`, {
    method: "DELETE",
  });
}
