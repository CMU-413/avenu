export interface NotificationPreferenceState {
  emailNotifications: boolean;
  smsNotifications: boolean;
  hasPhone: boolean;
}

export interface NotificationSettingsState extends NotificationPreferenceState {
  smsNotifications: boolean;
  smsDisabled: boolean;
  smsInlineMessage: string | null;
}

export function deriveSettingsState(state: NotificationPreferenceState): NotificationSettingsState {
  const smsDisabled = !state.hasPhone;
  return {
    ...state,
    smsNotifications: state.hasPhone ? state.smsNotifications : false,
    smsDisabled,
    smsInlineMessage: smsDisabled ? "Add a phone number to enable SMS notifications." : null,
  };
}

export function buildPreferencePatch(
  current: NotificationPreferenceState,
  updates: Partial<Pick<NotificationPreferenceState, "emailNotifications" | "smsNotifications">>,
): { emailNotifications?: boolean; smsNotifications?: boolean } {
  const patch: { emailNotifications?: boolean; smsNotifications?: boolean } = {};

  if (typeof updates.emailNotifications === "boolean") {
    patch.emailNotifications = updates.emailNotifications;
  }

  if (typeof updates.smsNotifications === "boolean") {
    patch.smsNotifications = current.hasPhone ? updates.smsNotifications : false;
  } else if (!current.hasPhone && current.smsNotifications) {
    patch.smsNotifications = false;
  }

  return patch;
}
