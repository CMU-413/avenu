import { describe, expect, it } from "vitest";

import { buildPreferencePatch, deriveSettingsState } from "@/lib/member-preferences";

describe("member preferences helpers", () => {
  it("buildPreferencePatch_clears_sms_when_phone_missing", () => {
    const patch = buildPreferencePatch(
      {
        emailNotifications: true,
        smsNotifications: true,
        hasPhone: false,
      },
      {},
    );

    expect(patch).toEqual({ smsNotifications: false });
  });

  it("buildPreferencePatch_preserves_sms_when_phone_present", () => {
    const patch = buildPreferencePatch(
      {
        emailNotifications: true,
        smsNotifications: false,
        hasPhone: true,
      },
      { smsNotifications: true },
    );

    expect(patch).toEqual({ smsNotifications: true });
  });

  it("buildPreferencePatch_supports_partial_toggle_updates", () => {
    const patch = buildPreferencePatch(
      {
        emailNotifications: false,
        smsNotifications: false,
        hasPhone: true,
      },
      { emailNotifications: true },
    );

    expect(patch).toEqual({ emailNotifications: true });
  });

  it("deriveSettingsState_disables_sms_without_phone", () => {
    const state = deriveSettingsState({
      emailNotifications: true,
      smsNotifications: true,
      hasPhone: false,
    });

    expect(state.smsDisabled).toBe(true);
    expect(state.smsNotifications).toBe(false);
    expect(state.smsInlineMessage).toBe("Add a phone number to enable SMS notifications.");
  });
});
