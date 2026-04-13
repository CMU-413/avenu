import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BrowserRouter } from "react-router-dom";
import App, { getMagicLinkParams, stripAuthBootstrapParams } from "@/App";
import { useAppStore } from "@/lib/store";

const {
  bootstrapOptixSessionMock,
  redeemMagicLinkMock,
  sessionMeMock,
  sessionLogoutMock,
} = vi.hoisted(() => ({
  bootstrapOptixSessionMock: vi.fn(),
  redeemMagicLinkMock: vi.fn(),
  sessionMeMock: vi.fn(),
  sessionLogoutMock: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  },
  bootstrapOptixSession: bootstrapOptixSessionMock,
  redeemMagicLink: redeemMagicLinkMock,
  sessionMe: sessionMeMock,
  sessionLogout: sessionLogoutMock,
}));

describe("auth bootstrap helpers", () => {
  it("parses magic link params from the URL search string", () => {
    expect(getMagicLinkParams("?token_id=abc&signature=def")).toEqual({
      tokenId: "abc",
      signature: "def",
    });
    expect(getMagicLinkParams("?token_id=abc")).toBeNull();
  });

  it("strips optix and magic-link bootstrap params while preserving others", () => {
    expect(
      stripAuthBootstrapParams(
        "https://hub.avenuworkspaces.com/mail/?token_id=abc&signature=def&keep=1#frag",
      ),
    ).toBe("/mail/?keep=1#frag");
    expect(
      stripAuthBootstrapParams(
        "https://hub.avenuworkspaces.com/mail/?token=x+y&org_id=1&user_id=2",
      ),
    ).toBe("/mail/");
  });
});

describe("App magic-link bootstrap", () => {
  beforeEach(() => {
    bootstrapOptixSessionMock.mockReset();
    redeemMagicLinkMock.mockReset();
    sessionMeMock.mockReset();
    sessionLogoutMock.mockReset();
    useAppStore.setState({ sessionUser: null, isHydratingSession: true });
    window.history.replaceState({}, "", "/mail/?token_id=abc&signature=def");
  });

  it("redeems the magic link, strips query params, and lands on admin", async () => {
    redeemMagicLinkMock.mockResolvedValue(undefined);
    sessionMeMock.mockResolvedValue({
      id: "user-1",
      fullname: "Admin User",
      email: "admin@example.com",
      isAdmin: true,
      teamIds: [],
      emailNotifications: true,
      smsNotifications: false,
      hasPhone: false,
    });

    render(
      <BrowserRouter basename="/mail">
        <App />
      </BrowserRouter>,
    );

    await waitFor(() => {
      expect(redeemMagicLinkMock).toHaveBeenCalledWith({ tokenId: "abc", signature: "def" });
    });
    expect(await screen.findByText("Avenu Admin")).toBeInTheDocument();
    expect(window.location.search).toBe("");
    expect(window.location.pathname).toBe("/mail/admin");
  });
});
