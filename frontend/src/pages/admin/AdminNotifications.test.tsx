import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminNotifications from "./AdminNotifications";
import { ConfirmDialogProvider } from "@/components/ConfirmDialogProvider";

const {
  toastSpy,
  listUsersMock,
  sendMailArrivedNotificationMock,
  sendWeeklySummaryNotificationMock,
} = vi.hoisted(() => ({
  toastSpy: vi.fn(),
  listUsersMock: vi.fn(),
  sendMailArrivedNotificationMock: vi.fn(),
  sendWeeklySummaryNotificationMock: vi.fn(),
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
    sendWeeklySummaryNotification: sendWeeklySummaryNotificationMock,
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
    sendWeeklySummaryNotificationMock.mockResolvedValue({
      status: "sent",
      channelResults: [{ channel: "email", status: "sent" }],
    });
  });

  it("requires recipient selection for special notification", async () => {
    render(
      <MemoryRouter>
        <ConfirmDialogProvider>
          <AdminNotifications />
        </ConfirmDialogProvider>
      </MemoryRouter>
    );

    await screen.findByRole("button", { name: "Send Mail Arrived Notification" });
    fireEvent.click(screen.getByRole("button", { name: "Send Mail Arrived Notification" }));

    expect(toastSpy).toHaveBeenCalledWith({ title: "Select a recipient", variant: "destructive" });
    expect(sendMailArrivedNotificationMock).not.toHaveBeenCalled();
  });

  it("submits selected recipient for special notification", async () => {
    render(
      <MemoryRouter>
        <ConfirmDialogProvider>
          <AdminNotifications />
        </ConfirmDialogProvider>
      </MemoryRouter>
    );

    await screen.findByRole("button", { name: "Send Mail Arrived Notification" });
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "user-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Send Mail Arrived Notification" }));
    fireEvent.click(await screen.findByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(sendMailArrivedNotificationMock).toHaveBeenCalledWith({ userId: "user-1" });
    });
    expect(toastSpy).toHaveBeenCalledWith({ title: "Notification sent" });
  });

  it("submits selected recipient for weekly notification", async () => {
    const now = new Date();
    now.setHours(0, 0, 0, 0);
    const currentWeekStart = new Date(now);
    currentWeekStart.setDate(now.getDate() - ((now.getDay() + 6) % 7));
    const previousWeekStart = new Date(currentWeekStart);
    previousWeekStart.setDate(currentWeekStart.getDate() - 7);
    const previousWeekEnd = new Date(currentWeekStart);
    previousWeekEnd.setDate(currentWeekStart.getDate() - 1);
    const weekStart = previousWeekStart.toISOString().slice(0, 10);
    const weekEnd = previousWeekEnd.toISOString().slice(0, 10);

    render(
      <MemoryRouter>
        <ConfirmDialogProvider>
          <AdminNotifications />
        </ConfirmDialogProvider>
      </MemoryRouter>
    );

    await screen.findByRole("button", { name: "Send Weekly Mail Notification" });
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "user-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Send Weekly Mail Notification" }));
    fireEvent.click(await screen.findByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(sendWeeklySummaryNotificationMock).toHaveBeenCalledWith({
        userId: "user-1",
        weekStart,
        weekEnd,
      });
    });
    expect(toastSpy).toHaveBeenCalledWith({ title: "Weekly notification sent" });
  });
});
