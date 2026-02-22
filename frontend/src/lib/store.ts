import { create } from "zustand";

export interface SessionUser {
  id: string;
  fullname: string;
  email: string;
  isAdmin: boolean;
  teamIds: string[];
  emailNotifications: boolean;
  smsNotifications: boolean;
  hasPhone: boolean;
}

interface AppState {
  sessionUser: SessionUser | null;
  isHydratingSession: boolean;
  setSessionUser: (user: SessionUser | null) => void;
  setSessionHydrating: (isHydrating: boolean) => void;
  setSessionNotificationPreferences: (prefs: {
    emailNotifications: boolean;
    smsNotifications: boolean;
    hasPhone: boolean;
  }) => void;
  logout: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  sessionUser: null,
  isHydratingSession: true,
  setSessionUser: (user) => set({ sessionUser: user }),
  setSessionHydrating: (isHydrating) => set({ isHydratingSession: isHydrating }),
  setSessionNotificationPreferences: (prefs) =>
    set((state) => ({
      sessionUser: state.sessionUser ? { ...state.sessionUser, ...prefs } : null,
    })),
  logout: () => set({ sessionUser: null, isHydratingSession: false }),
}));
