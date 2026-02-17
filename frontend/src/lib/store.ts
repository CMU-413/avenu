import { create } from "zustand";

export interface SessionUser {
  id: string;
  fullname: string;
  email: string;
  isAdmin: boolean;
  teamIds: string[];
  emailNotifications: boolean;
}

interface AppState {
  sessionUser: SessionUser | null;
  isHydratingSession: boolean;
  setSessionUser: (user: SessionUser | null) => void;
  setSessionHydrating: (isHydrating: boolean) => void;
  setSessionEmailNotifications: (emailNotifications: boolean) => void;
  logout: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  sessionUser: null,
  isHydratingSession: true,
  setSessionUser: (user) => set({ sessionUser: user }),
  setSessionHydrating: (isHydrating) => set({ isHydratingSession: isHydrating }),
  setSessionEmailNotifications: (emailNotifications) =>
    set((state) => ({
      sessionUser: state.sessionUser ? { ...state.sessionUser, emailNotifications } : null,
    })),
  logout: () => set({ sessionUser: null, isHydratingSession: false }),
}));
