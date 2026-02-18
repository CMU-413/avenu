import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminNotifications from "./AdminNotifications";

const {
  toastSpy,
  listUsersMock,
  sendMailArrivedNotificationMock,
} = vi.hoisted(() => ({
  toastSpy: vi.fn(),
  listUsersMock: vi.fn(),
  sendMailArrivedNotificationMock: vi.fn(),
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
    listUsers: listUsersMock,
    sendMailArrivedNotification: sendMailArrivedNotificationMock,
  };
});

describe("AdminNotifications", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listUsersMock.mockResolvedValue([
      {
        id: "user-1",
        isAdmin: false,
        fullname: "Member One",
        teamIds: [],
      },
    ]);
    sendMailArrivedNotificationMock.mockResolvedValue({
      status: "sent",
      channelResults: [{ channel: "email", status: "sent" }],
    });
    vi.stubGlobal("confirm", vi.fn(() => true));
  });

  it("requires recipient selection", async () => {
    render(
      <MemoryRouter>
        <AdminNotifications />
      </MemoryRouter>
    );

    await screen.findByText("Mail Arrived Notification");
    fireEvent.click(screen.getByRole("button", { name: "Send Mail Arrived Notification" }));

    expect(toastSpy).toHaveBeenCalledWith({ title: "Select a recipient", variant: "destructive" });
    expect(sendMailArrivedNotificationMock).not.toHaveBeenCalled();
  });

  it("submits selected recipient", async () => {
    render(
      <MemoryRouter>
        <AdminNotifications />
      </MemoryRouter>
    );

    await screen.findByText("Mail Arrived Notification");
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "user-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Send Mail Arrived Notification" }));

    await waitFor(() => {
      expect(sendMailArrivedNotificationMock).toHaveBeenCalledWith({ userId: "user-1" });
    });
    expect(toastSpy).toHaveBeenCalledWith({ title: "Notification sent" });
  });
});
