import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import AdminUsersTeams from "@/pages/admin/AdminUsersTeams";

const {
  listUsersMock,
  listTeamsMock,
  deleteTeamMock,
  deleteUserMock,
  confirmMock,
  toastMock,
  logoutMock,
} = vi.hoisted(() => ({
  listUsersMock: vi.fn(),
  listTeamsMock: vi.fn(),
  deleteTeamMock: vi.fn(),
  deleteUserMock: vi.fn(),
  confirmMock: vi.fn(),
  toastMock: vi.fn(),
  logoutMock: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  },
  listUsers: listUsersMock,
  listTeams: listTeamsMock,
  deleteTeam: deleteTeamMock,
  deleteUser: deleteUserMock,
}));

vi.mock("@/hooks/use-confirm-dialog", () => ({
  useConfirmDialog: () => confirmMock,
}));

vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({
    toast: toastMock,
  }),
}));

vi.mock("@/lib/store", () => ({
  useAppStore: (selector: (state: { logout: typeof logoutMock }) => unknown) =>
    selector({ logout: logoutMock }),
}));

describe("AdminUsersTeams", () => {
  beforeEach(() => {
    listUsersMock.mockReset();
    listTeamsMock.mockReset();
    deleteTeamMock.mockReset();
    deleteUserMock.mockReset();
    confirmMock.mockReset();
    toastMock.mockReset();
    logoutMock.mockReset();

    listUsersMock.mockResolvedValue([
      {
        id: "user-1",
        fullname: "Member One",
        email: "member@example.com",
        isAdmin: false,
        teamIds: ["team-1"],
      },
    ]);
    listTeamsMock.mockResolvedValue([
      {
        id: "team-1",
        name: "Operations",
      },
    ]);
    confirmMock.mockResolvedValue(true);
    deleteTeamMock.mockResolvedValue(undefined);
  });

  it("shows Remove Members & Delete and keeps pruneUsers in the delete request", async () => {
    render(
      <MemoryRouter>
        <AdminUsersTeams />
      </MemoryRouter>,
    );

    const removeMembersButton = await screen.findByRole("button", {
      name: "Remove Members & Delete",
    });
    fireEvent.click(removeMembersButton);

    await waitFor(() => {
      expect(confirmMock).toHaveBeenCalledWith({
        title: "Remove Members & Delete Team",
        message: "Delete Operations and remove 1 member association first?",
        confirmLabel: "Remove Members & Delete",
        cancelLabel: "Cancel",
      });
    });

    await waitFor(() => {
      expect(deleteTeamMock).toHaveBeenCalledWith("team-1", { pruneUsers: true });
    });
  });
});
