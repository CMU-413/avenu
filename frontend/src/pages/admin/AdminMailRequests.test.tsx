import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminMailRequests from "./AdminMailRequests";
import { useAppStore } from "@/lib/store";

const {
  toastSpy,
  listAdminMailRequestsMock,
  listUsersMock,
  listMailboxesMock,
} = vi.hoisted(() => ({
  toastSpy: vi.fn(),
  listAdminMailRequestsMock: vi.fn(),
  listUsersMock: vi.fn(),
  listMailboxesMock: vi.fn(),
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
    listAdminMailRequests: listAdminMailRequestsMock,
    listUsers: listUsersMock,
    listMailboxes: listMailboxesMock,
  };
});

describe("AdminMailRequests", () => {
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

    listUsersMock.mockResolvedValue([
      { id: "member-1", fullname: "Member One", isAdmin: false },
      { id: "admin-2", fullname: "Admin Two", isAdmin: true },
    ]);
    listMailboxesMock.mockResolvedValue([
      { id: "mailbox-1", displayName: "Main Mailbox" },
    ]);
    listAdminMailRequestsMock.mockResolvedValue([
      {
        id: "req-1",
        memberId: "member-1",
        mailboxId: "mailbox-1",
        expectedSender: "Sender Inc",
        description: null,
        startDate: "2026-02-01",
        endDate: "2026-02-05",
        createdAt: "2026-02-02T10:00:00Z",
      },
    ]);
  });

  it("loads and renders request rows with mapped member/mailbox names", async () => {
    render(
      <MemoryRouter>
        <AdminMailRequests />
      </MemoryRouter>
    );

    await screen.findByRole("cell", { name: "Member One" });
    expect(screen.getByRole("cell", { name: "Main Mailbox" })).toBeInTheDocument();
    expect(screen.getByText("Sender Inc")).toBeInTheDocument();
    expect(listAdminMailRequestsMock).toHaveBeenCalledWith({ memberId: undefined, mailboxId: undefined });
  });

  it("applies member and mailbox filters to API query", async () => {
    render(
      <MemoryRouter>
        <AdminMailRequests />
      </MemoryRouter>
    );

    await screen.findByLabelText("Member Filter");
    fireEvent.change(screen.getByLabelText("Member Filter"), { target: { value: "member-1" } });
    fireEvent.change(screen.getByLabelText("Mailbox Filter"), { target: { value: "mailbox-1" } });

    await waitFor(() => {
      expect(listAdminMailRequestsMock).toHaveBeenLastCalledWith({
        memberId: "member-1",
        mailboxId: "mailbox-1",
      });
    });
  });
});
