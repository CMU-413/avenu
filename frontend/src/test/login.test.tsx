import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import Login from "@/pages/Login";

const { requestMagicLinkMock, toastMock } = vi.hoisted(() => ({
  requestMagicLinkMock: vi.fn(),
  toastMock: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  requestMagicLink: requestMagicLinkMock,
}));

vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({
    toast: toastMock,
  }),
}));

describe("Login", () => {
  beforeEach(() => {
    requestMagicLinkMock.mockReset();
    toastMock.mockReset();
  });

  it("requests a magic link and shows confirmation state", async () => {
    requestMagicLinkMock.mockResolvedValue({ status: "ok" });

    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText("Admin email"), {
      target: { value: "Admin@Example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Email sign-in link" }));

    await waitFor(() => {
      expect(requestMagicLinkMock).toHaveBeenCalledWith("admin@example.com");
    });
    expect(
      await screen.findByText(/If an admin account exists for/i),
    ).toHaveTextContent("admin@example.com");
  });

  it("shows an error toast when email is missing", async () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Email sign-in link" }));

    await waitFor(() => {
      expect(toastMock).toHaveBeenCalledWith({ title: "Enter email", variant: "destructive" });
    });
    expect(requestMagicLinkMock).not.toHaveBeenCalled();
  });
});
