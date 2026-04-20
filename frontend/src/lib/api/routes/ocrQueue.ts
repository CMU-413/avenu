import { apiFetch, buildUrl } from "../../http/client";

export type OcrJobStatus = "processing" | "processed" | "failed" | "audited";
export type OcrQueueItemStatus = "pending" | "completed" | "failed" | "confirmed" | "deleted";

export interface ApiOcrJob {
  id: string;
  createdBy: string;
  date: string;
  status: OcrJobStatus;
  totalCount: number;
  completedCount: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface ApiOcrQueueItem {
  id: string;
  jobId: string;
  index: number;
  status: OcrQueueItemStatus;
  receiverName?: string | null;
  senderInfo?: string | null;
  type: "letter" | "package";
  rawText?: string | null;
  error?: string | null;
  mailboxId?: string | null;
  fileId?: string | null;
  confirmedAt?: string | null;
}

export interface ApiOcrJobWithItems {
  job: ApiOcrJob;
  items: ApiOcrQueueItem[];
}

/** Create OCR job with bulk image upload. Starts async processing. */
export async function createOcrJob(files: File[], date?: string): Promise<ApiOcrJob> {
  const formData = new FormData();
  for (const f of files) {
    formData.append("files", f);
  }
  if (date) {
    formData.append("date", date);
  }

  const response = await fetch(buildUrl("/ocr/jobs"), {
    method: "POST",
    credentials: "include",
    body: formData,
  });

  if (!response.ok) {
    let message = `Upload failed (${response.status})`;
    try {
      const body = await response.json();
      if (body?.error && typeof body.error === "string") {
        message = body.error;
      }
    } catch {
      /* ignore */
    }
    throw new Error(message);
  }

  return response.json() as Promise<ApiOcrJob>;
}

/** List OCR jobs for current admin. */
export async function listOcrJobs(limit = 50): Promise<{ jobs: ApiOcrJob[] }> {
  return apiFetch<{ jobs: ApiOcrJob[] }>(`/ocr/jobs?limit=${limit}`);
}

/** Get job with its queue items. */
export async function getOcrJob(jobId: string): Promise<ApiOcrJobWithItems> {
  return apiFetch<ApiOcrJobWithItems>(`/ocr/jobs/${jobId}`);
}

/** Update queue item (receiver, sender, type, mailbox). */
export async function updateOcrQueueItem(
  itemId: string,
  payload: Partial<{
    receiverName: string;
    senderInfo: string;
    type: "letter" | "package";
    mailboxId: string | null;
  }>
): Promise<{ item: ApiOcrQueueItem }> {
  return apiFetch<{ item: ApiOcrQueueItem }>(`/ocr/queue/${itemId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

/** Confirm item: create mail entry and mark confirmed. */
export async function confirmOcrQueueItem(
  itemId: string
): Promise<{ item: ApiOcrQueueItem; mail: { id: string; [k: string]: unknown } }> {
  return apiFetch<{ item: ApiOcrQueueItem; mail: { id: string; [k: string]: unknown } }>(
    `/ocr/queue/${itemId}/confirm`,
    { method: "POST" }
  );
}

/** Delete a queue item. */
export async function deleteOcrQueueItem(itemId: string): Promise<void> {
  return apiFetch<void>(`/ocr/queue/${itemId}`, { method: "DELETE" });
}

/** Update job stage (e.g. processing -> processed -> audited). */
export async function updateOcrJobStage(jobId: string, stage: "processed" | "audited"): Promise<{ job: ApiOcrJob }> {
  return apiFetch<{ job: ApiOcrJob }>(`/ocr/jobs/${jobId}/stage`, {
    method: "POST",
    body: JSON.stringify({ stage }),
  });
}
