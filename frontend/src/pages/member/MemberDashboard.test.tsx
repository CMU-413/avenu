import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import MemberDashboard from "./MemberDashboard";
import { useAppStore } from "@/lib/store";

const {
  toastSpy,
  getMemberMailMock,
  listMemberMailRequestsMock,
  createMailRequestMock,
  cancelMailRequestMock,
  sessionLogoutMock,
} = vi.hoisted(() => ({
  toastSpy: vi.fn(),
  getMemberMailMock: vi.fn(),
  listMemberMailRequestsMock: vi.fn(),
  createMailRequestMock: vi.fn(),
  cancelMailRequestMock: vi.fn(),
  sessionLogoutMock: vi.fn(),
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
    getMemberMail: getMemberMailMock,
    listMemberMailRequests: listMemberMailRequestsMock,
    createMailRequest: createMailRequestMock,
    cancelMailRequest: cancelMailRequestMock,
    sessionLogout: sessionLogoutMock,
  };
});

describe("MemberDashboard expected mail section", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAppStore.setState({
      sessionUser: {
        id: "member-1",
        fullname: "Member One",
        email: "member@example.com",
        isAdmin: false,
        teamIds: [],
        emailNotifications: true,
      },
      isHydratingSession: false,
    });

    getMemberMailMock.mockResolvedValue({
      start: "2026-02-16",
      end: "2026-02-22",
      mailboxes: [
        {
          mailboxId: "mailbox-1",
          name: "My Mailbox",
          type: "personal",
          days: [],
        },
      ],
    });
    listMemberMailRequestsMock.mockResolvedValue([
      {
        id: "req-1",
        memberId: "member-1",
        mailboxId: "mailbox-1",
        expectedSender: "Sender Inc",
        description: null,
        startDate: null,
        endDate: null,
        status: "ACTIVE",
        createdAt: "2026-02-18T00:00:00Z",
        updatedAt: "2026-02-18T00:00:00Z",
      },
    ]);
    createMailRequestMock.mockResolvedValue({});
    cancelMailRequestMock.mockResolvedValue(undefined);
  });

  it("blocks submit when sender and description are both empty", async () => {
    render(
      <MemoryRouter>
        <MemberDashboard />
      </MemoryRouter>
    );

    await screen.findByText("Expected Mail");
    fireEvent.change(screen.getByLabelText("Expected Mailbox"), { target: { value: "mailbox-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Create Request" }));

    expect(toastSpy).toHaveBeenCalledWith({ title: "Enter a sender or description", variant: "destructive" });
    expect(createMailRequestMock).not.toHaveBeenCalled();
  });

  it("submits valid create payload and refreshes requests", async () => {
    render(
      <MemoryRouter>
        <MemberDashboard />
      </MemoryRouter>
    );

    await screen.findByText("Expected Mail");
    fireEvent.change(screen.getByLabelText("Expected Sender"), { target: { value: "Acme Corp" } });
    fireEvent.click(screen.getByRole("button", { name: "Create Request" }));

    await waitFor(() => {
      expect(createMailRequestMock).toHaveBeenCalledWith({
        mailboxId: "mailbox-1",
        expectedSender: "Acme Corp",
        description: undefined,
        startDate: undefined,
        endDate: undefined,
      });
    });
    expect(listMemberMailRequestsMock.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it("cancels selected request and refreshes requests", async () => {
    render(
      <MemoryRouter>
        <MemberDashboard />
      </MemoryRouter>
    );

    await screen.findByText("Sender Inc");
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    await waitFor(() => {
      expect(cancelMailRequestMock).toHaveBeenCalledWith("req-1");
    });
    expect(listMemberMailRequestsMock.mock.calls.length).toBeGreaterThanOrEqual(2);
  });
});
