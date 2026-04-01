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

export interface FeatureFlags {
  ocrQueueV2: boolean;
  ocrShadowLaunch: boolean;
}

interface AppState {
  sessionUser: SessionUser | null;
  isHydratingSession: boolean;
  featureFlags: FeatureFlags;
  isHydratingFeatureFlags: boolean;
  setSessionUser: (user: SessionUser | null) => void;
  setSessionHydrating: (isHydrating: boolean) => void;
  setFeatureFlags: (flags: FeatureFlags) => void;
  setFeatureFlagsHydrating: (isHydrating: boolean) => void;
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
  featureFlags: {
    ocrQueueV2: true,
    ocrShadowLaunch: false,
  },
  isHydratingFeatureFlags: true,
  setSessionUser: (user) => set({ sessionUser: user }),
  setSessionHydrating: (isHydrating) => set({ isHydratingSession: isHydrating }),
  setFeatureFlags: (flags) => set({ featureFlags: flags }),
  setFeatureFlagsHydrating: (isHydrating) => set({ isHydratingFeatureFlags: isHydrating }),
  setSessionNotificationPreferences: (prefs) =>
    set((state) => ({
      sessionUser: state.sessionUser ? { ...state.sessionUser, ...prefs } : null,
    })),
  logout: () => set({ sessionUser: null, isHydratingSession: false }),
}));
