import { apiFetch } from "../../http/client";

export interface ApiFeatureFlags {
  ocrQueueV2: boolean;
  ocrShadowLaunch: boolean;
}

export function fetchFeatureFlags(): Promise<ApiFeatureFlags> {
  return apiFetch<ApiFeatureFlags>("/feature-flags");
}
