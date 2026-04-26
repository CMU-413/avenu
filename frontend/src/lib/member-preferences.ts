export interface NotificationPreferenceState {
  emailNotifications: boolean;
  smsNotifications: boolean;
  hasPhone: boolean;
  /** Backend: phone is E.164 and can be used for SMS. */
  hasSmsPhone: boolean;
}

export interface NotificationSettingsState extends NotificationPreferenceState {
  smsNotifications: boolean;
  smsDisabled: boolean;
  smsInlineMessage: string | null;
}

export function deriveSettingsState(state: NotificationPreferenceState): NotificationSettingsState {
  const smsDisabled = !state.hasSmsPhone;
  return {
    ...state,
    smsNotifications: state.hasSmsPhone ? state.smsNotifications : false,
    smsDisabled,
    smsInlineMessage: smsDisabled
      ? state.hasPhone
        ? "Use a phone number in international format (E.164, e.g. +1…) to enable SMS notifications."
        : "Add a phone number to enable SMS notifications."
      : null,
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
    patch.smsNotifications = current.hasSmsPhone ? updates.smsNotifications : false;
  } else if (!current.hasSmsPhone && current.smsNotifications) {
    patch.smsNotifications = false;
  }

  return patch;
}
