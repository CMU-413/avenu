import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import RecordEntry from "./RecordEntry";
import { useAppStore } from "@/lib/store";

const {
  toastSpy,
  listMailboxesMock,
  listMailMock,
  listAdminMailRequestsMock,
  resolveAdminMailRequestMock,
  retryAdminMailRequestNotificationMock,
  createMailMock,
  updateMailMock,
  deleteMailMock,
} = vi.hoisted(() => ({
  toastSpy: vi.fn(),
  listMailboxesMock: vi.fn(),
  listMailMock: vi.fn(),
  listAdminMailRequestsMock: vi.fn(),
  resolveAdminMailRequestMock: vi.fn(),
  retryAdminMailRequestNotificationMock: vi.fn(),
  createMailMock: vi.fn(),
  updateMailMock: vi.fn(),
  deleteMailMock: vi.fn(),
}));

vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({ toast: toastSpy }),
}));

vi.mock("@/lib/api", () => {
  class ApiError extends Error {
    status: number;

    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  }

  return {
    ApiError,
    listMailboxes: listMailboxesMock,
    listMail: listMailMock,
    listAdminMailRequests: listAdminMailRequestsMock,
    resolveAdminMailRequest: resolveAdminMailRequestMock,
    retryAdminMailRequestNotification: retryAdminMailRequestNotificationMock,
    createMail: createMailMock,
    updateMail: updateMailMock,
    deleteMail: deleteMailMock,
  };
});

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/admin/mailboxes/mailbox-1?date=2026-02-20"]}>
      <Routes>
        <Route path="/admin/mailboxes/:mailboxId" element={<RecordEntry />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("RecordEntry expected-mail side panel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAppStore.setState({
      sessionUser: {
        id: "admin-1",
        fullname: "Admin",
        email: "admin@example.com",
        isAdmin: true,
        teamIds: [],
        emailNotifications: true,
      },
      isHydratingSession: false,
    });

    listMailboxesMock.mockResolvedValue([{ id: "mailbox-1", displayName: "Main Mailbox" }]);
    listMailMock.mockResolvedValue([]);
    listAdminMailRequestsMock.mockResolvedValue([
      {
        id: "req-match",
        memberId: "member-1",
        mailboxId: "mailbox-1",
        expectedSender: "Sender Match",
        description: null,
        startDate: "2026-02-19",
        endDate: "2026-02-21",
        status: "ACTIVE",
        resolvedAt: null,
        resolvedBy: null,
        lastNotificationStatus: null,
        lastNotificationAt: null,
        createdAt: "2026-02-18T00:00:00Z",
        updatedAt: "2026-02-18T00:00:00Z",
      },
      {
        id: "req-outside",
        memberId: "member-1",
        mailboxId: "mailbox-1",
        expectedSender: "Sender Outside",
        description: null,
        startDate: "2026-02-22",
        endDate: "2026-02-23",
        status: "ACTIVE",
        resolvedAt: null,
        resolvedBy: null,
        lastNotificationStatus: null,
        lastNotificationAt: null,
        createdAt: "2026-02-18T00:00:00Z",
        updatedAt: "2026-02-18T00:00:00Z",
      },
    ]);
  });

  it("renders active requests matching selected date window only", async () => {
    renderPage();

    await screen.findByText("Sender Match");
    expect(screen.queryByText("Sender Outside")).not.toBeInTheDocument();
  });

  it("resolves request and removes it from active panel", async () => {
    resolveAdminMailRequestMock.mockResolvedValue({
      id: "req-match",
      memberId: "member-1",
      mailboxId: "mailbox-1",
      expectedSender: "Sender Match",
      description: null,
      startDate: "2026-02-19",
      endDate: "2026-02-21",
      status: "RESOLVED",
      resolvedAt: "2026-02-20T01:00:00Z",
      resolvedBy: "admin-1",
      lastNotificationStatus: "FAILED",
      lastNotificationAt: "2026-02-20T01:00:00Z",
      createdAt: "2026-02-18T00:00:00Z",
      updatedAt: "2026-02-20T01:00:00Z",
    });

    renderPage();

    await screen.findByText("Sender Match");
    fireEvent.click(screen.getByRole("button", { name: "Resolve & Notify" }));

    await waitFor(() => {
      expect(resolveAdminMailRequestMock).toHaveBeenCalledWith("req-match");
    });
    await waitFor(() => {
      expect(screen.queryByRole("button", { name: "Resolve & Notify" })).not.toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Retry Notification" })).toBeInTheDocument();
  });

  it("retries notification and updates status metadata", async () => {
    resolveAdminMailRequestMock.mockResolvedValue({
      id: "req-match",
      memberId: "member-1",
      mailboxId: "mailbox-1",
      expectedSender: "Sender Match",
      description: null,
      startDate: "2026-02-19",
      endDate: "2026-02-21",
      status: "RESOLVED",
      resolvedAt: "2026-02-20T01:00:00Z",
      resolvedBy: "admin-1",
      lastNotificationStatus: "FAILED",
      lastNotificationAt: "2026-02-20T01:00:00Z",
      createdAt: "2026-02-18T00:00:00Z",
      updatedAt: "2026-02-20T01:00:00Z",
    });
    retryAdminMailRequestNotificationMock.mockResolvedValue({
      id: "req-match",
      memberId: "member-1",
      mailboxId: "mailbox-1",
      expectedSender: "Sender Match",
      description: null,
      startDate: "2026-02-19",
      endDate: "2026-02-21",
      status: "RESOLVED",
      resolvedAt: "2026-02-20T01:00:00Z",
      resolvedBy: "admin-1",
      lastNotificationStatus: "SENT",
      lastNotificationAt: "2026-02-20T02:00:00Z",
      createdAt: "2026-02-18T00:00:00Z",
      updatedAt: "2026-02-20T02:00:00Z",
    });

    renderPage();

    await screen.findByText("Sender Match");
    fireEvent.click(screen.getByRole("button", { name: "Resolve & Notify" }));
    await screen.findByRole("button", { name: "Retry Notification" });

    fireEvent.click(screen.getByRole("button", { name: "Retry Notification" }));
    await waitFor(() => {
      expect(retryAdminMailRequestNotificationMock).toHaveBeenCalledWith("req-match");
    });
    await waitFor(() => {
      expect(screen.getByText(/Notification: SENT/)).toBeInTheDocument();
    });
  });
});
