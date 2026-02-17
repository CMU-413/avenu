export interface Mailbox {
  id: string;
  name: string;
  type: "company" | "personal";
  memberNames: string[]; // members associated with this mailbox
}

export interface MailRecord {
  id: string;
  mailboxId: string;
  date: string; // YYYY-MM-DD
  letters: number;
  packages: number;
}

export interface Member {
  id: string;
  name: string;
  email: string;
  mailboxIds: string[];
  emailNotifications: boolean;
}

export const mailboxes: Mailbox[] = [
  { id: "mb1", name: "Autumn Q's Personal", type: "personal", memberNames: ["Autumn Quigley"] },
  { id: "mb2", name: "Matthew W's Personal", type: "personal", memberNames: ["Matthew Wong"] },
  { id: "mb3", name: "Matthew Z's Personal", type: "personal", memberNames: ["Matthew Zhang"] },
  { id: "mb4", name: "Company 1", type: "company", memberNames: ["Matthew Wong", "Matthew Zhang"] },
  { id: "mb5", name: "Mattress Warehouse", type: "company", memberNames: [] },
  { id: "mb6", name: "Acme Corp", type: "company", memberNames: ["Autumn Quigley"] },
];

const today = new Date();
const fmt = (d: Date) => d.toISOString().split("T")[0];
const daysAgo = (n: number) => {
  const d = new Date(today);
  d.setDate(d.getDate() - n);
  return fmt(d);
};

export const initialRecords: MailRecord[] = [
  { id: "r1", mailboxId: "mb1", date: fmt(today), letters: 5, packages: 0 },
  { id: "r2", mailboxId: "mb2", date: fmt(today), letters: 0, packages: 3 },
  { id: "r3", mailboxId: "mb4", date: fmt(today), letters: 2, packages: 1 },
  { id: "r4", mailboxId: "mb1", date: daysAgo(1), letters: 2, packages: 1 },
  { id: "r5", mailboxId: "mb4", date: daysAgo(1), letters: 5, packages: 2 },
  { id: "r6", mailboxId: "mb6", date: daysAgo(2), letters: 1, packages: 0 },
  { id: "r7", mailboxId: "mb2", date: daysAgo(3), letters: 3, packages: 0 },
  { id: "r8", mailboxId: "mb4", date: daysAgo(4), letters: 0, packages: 1 },
];

export const members: Member[] = [
  { id: "m1", name: "Autumn Quigley", email: "autumn@example.com", mailboxIds: ["mb1", "mb6"], emailNotifications: true },
  { id: "m2", name: "Matthew Wong", email: "mwong@example.com", mailboxIds: ["mb2", "mb4"], emailNotifications: false },
  { id: "m3", name: "Matthew Zhang", email: "mzhang@example.com", mailboxIds: ["mb3", "mb4"], emailNotifications: true },
];
