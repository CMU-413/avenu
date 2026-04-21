import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createMail, updateMail } from "@/lib/api/routes/mail";

function captureRequest() {
  const calls: { url: string; init: RequestInit | undefined }[] = [];
  const response = new Response(JSON.stringify({ id: "m1" }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    return response.clone();
  });
  vi.stubGlobal("fetch", fetchMock);
  return { calls };
}

function bodyOf(init: RequestInit | undefined): Record<string, unknown> {
  return JSON.parse(String(init?.body ?? "{}"));
}

describe("mail api payload normalization", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("createMail_omits_isPromotional_when_absent", async () => {
    const { calls } = captureRequest();
    await createMail({
      mailboxId: "mb1",
      date: "2026-04-21T00:00:00Z",
      type: "letter",
      idempotencyKey: "k1",
    });
    expect(calls).toHaveLength(1);
    expect(bodyOf(calls[0].init)).not.toHaveProperty("isPromotional");
  });

  it("createMail_omits_isPromotional_when_false", async () => {
    const { calls } = captureRequest();
    await createMail({
      mailboxId: "mb1",
      date: "2026-04-21T00:00:00Z",
      type: "letter",
      isPromotional: false,
      idempotencyKey: "k1",
    });
    expect(bodyOf(calls[0].init)).not.toHaveProperty("isPromotional");
  });

  it("createMail_includes_isPromotional_true_when_toggled", async () => {
    const { calls } = captureRequest();
    await createMail({
      mailboxId: "mb1",
      date: "2026-04-21T00:00:00Z",
      type: "package",
      isPromotional: true,
      idempotencyKey: "k1",
    });
    expect(bodyOf(calls[0].init)).toMatchObject({ isPromotional: true });
  });

  it("updateMail_passes_isPromotional_false_through", async () => {
    const { calls } = captureRequest();
    await updateMail("m1", { isPromotional: false });
    expect(bodyOf(calls[0].init)).toEqual({ isPromotional: false });
  });

  it("updateMail_passes_isPromotional_true_through", async () => {
    const { calls } = captureRequest();
    await updateMail("m1", { isPromotional: true });
    expect(bodyOf(calls[0].init)).toEqual({ isPromotional: true });
  });
});
