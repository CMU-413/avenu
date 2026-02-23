export type MailboxType = "user" | "team";
export type MailType = "letter" | "package";

export interface ApiMailbox {
  id: string;
  type: MailboxType;
  refId: string;
  displayName: string;
  createdAt: string;
  updatedAt: string;
}

export interface ApiMailRecord {
  id: string;
  mailboxId: string;
  date: string;
  type: MailType;
  count: number;
  receiverAddress?: string | null;
  senderInfo?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ApiUser {
  id: string;
  optixId: number;
  isAdmin: boolean;
  fullname: string;
  email: string;
  phone: string | null;
  teamIds: string[];
  notifPrefs: string[];
  createdAt: string;
  updatedAt: string;
}

export interface ApiTeam {
  id: string;
  optixId: number;
  name: string;
  createdAt: string;
  updatedAt: string;
}

export interface ApiSessionMe {
  id: string;
  email: string;
  fullname: string;
  isAdmin: boolean;
  teamIds: string[];
  emailNotifications: boolean;
  smsNotifications: boolean;
  hasPhone: boolean;
}

export interface ApiMemberMailboxDay {
  date: string;
  letters: number;
  packages: number;
}

export interface ApiMemberMailboxSummary {
  mailboxId: string;
  name: string;
  type: "personal" | "company";
  days: ApiMemberMailboxDay[];
}

export interface ApiMemberMailSummary {
  start: string;
  end: string;
  mailboxes: ApiMemberMailboxSummary[];
}

export interface ApiMemberPreferences {
  id: string;
  emailNotifications: boolean;
  smsNotifications: boolean;
  hasPhone: boolean;
}

export type ApiMailRequestStatus = "ACTIVE" | "CANCELLED" | "RESOLVED";
export type ApiMailRequestNotificationStatus = "SENT" | "FAILED";

export interface ApiMailRequest {
  id: string;
  memberId: string;
  mailboxId: string;
  expectedSender: string | null;
  description: string | null;
  startDate: string | null;
  endDate: string | null;
  status: ApiMailRequestStatus;
  resolvedAt: string | null;
  resolvedBy: string | null;
  lastNotificationStatus: ApiMailRequestNotificationStatus | null;
  lastNotificationAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ApiNotifyChannelResult {
  channel: string;
  status: "sent" | "failed";
  messageId?: string;
  error?: string;
}

export interface ApiNotifyResult {
  status: "sent" | "skipped" | "failed";
  reason?: string;
  channelResults: ApiNotifyChannelResult[];
}

export interface ApiOptixTokenResult {
  created: boolean;
  user: ApiUser;
}
