import { buildUrl } from "../../http/client";

export interface ApiOcrResponse {
  text: string;
  provider: string;
  error?: string;
}

/**
 * Upload an image and extract text via OCR.
 * Fails gracefully: returns empty text on OCR failure (does not throw).
 */
export async function ocrExtract(imageFile: File): Promise<ApiOcrResponse> {
  const formData = new FormData();
  formData.append("file", imageFile);

  const response = await fetch(buildUrl("/ocr"), {
    method: "POST",
    credentials: "include",
    body: formData,
  });

  if (!response.ok) {
    let message = `OCR request failed (${response.status})`;
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

  const data = (await response.json()) as ApiOcrResponse;
  return data;
}
