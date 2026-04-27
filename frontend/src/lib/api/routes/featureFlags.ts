import { apiFetch } from "../../http/client";

export interface ApiFeatureFlags {
  /** Master switch: false disables /api/ocr and the OCR queue API */
  adminOcr: boolean;
  ocrQueueV2: boolean;
  ocrShadowLaunch: boolean;
  /**
   * When true, uploaded queue images are OCR'd automatically; when false they land as
   * `pending` for manual review. Implies `adminOcr`.
   */
  ocrAutoExtract: boolean;
}

export function fetchFeatureFlags(): Promise<ApiFeatureFlags> {
  return apiFetch<ApiFeatureFlags>("/feature-flags");
}
