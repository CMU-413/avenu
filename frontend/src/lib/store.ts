import { create } from "zustand";
import { MailRecord, initialRecords, members as initialMembers, Member } from "./mock-data";

interface AppState {
  userRole: "admin" | "member" | null;
  currentMemberId: string | null;
  records: MailRecord[];
  members: Member[];
  login: (role: "admin" | "member", memberId?: string) => void;
  logout: () => void;
  addRecord: (record: Omit<MailRecord, "id">) => void;
  toggleNotifications: (memberId: string) => void;
}

export const useAppStore = create<AppState>((set) => ({
  userRole: null,
  currentMemberId: null,
  records: [...initialRecords],
  members: [...initialMembers],
  login: (role, memberId) => set({ userRole: role, currentMemberId: memberId || null }),
  logout: () => set({ userRole: null, currentMemberId: null }),
  addRecord: (record) =>
    set((state) => ({
      records: [...state.records, { ...record, id: `r${Date.now()}` }],
    })),
  toggleNotifications: (memberId) =>
    set((state) => ({
      members: state.members.map((m) =>
        m.id === memberId ? { ...m, emailNotifications: !m.emailNotifications } : m
      ),
    })),
}));
