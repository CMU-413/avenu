from __future__ import annotations

from typing import Any

from errors import APIError
from validators import is_e164_phone

UNSET = object()
_EMAIL_PREF = "email"
_SMS_PREF = "text"


def _normalize_phone(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized


def _normalize_storage_prefs(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    normalized: set[str] = set()
    for item in value:
        if item == _EMAIL_PREF or item == _SMS_PREF:
            normalized.add(item)
    return normalized


def _to_ordered_storage_prefs(prefs: set[str]) -> list[str]:
    ordered: list[str] = []
    if _EMAIL_PREF in prefs:
        ordered.append(_EMAIL_PREF)
    if _SMS_PREF in prefs:
        ordered.append(_SMS_PREF)
    return ordered


def normalize_effective_notification_state(
    *,
    current_user: dict[str, Any],
    phone_patch: Any = UNSET,
    notif_prefs_patch: Any = UNSET,
    email_notifications_patch: Any = UNSET,
    sms_notifications_patch: Any = UNSET,
) -> dict[str, Any]:
    effective_phone = _normalize_phone(current_user.get("phone"))
    if phone_patch is not UNSET:
        effective_phone = _normalize_phone(phone_patch)

    effective_prefs = _normalize_storage_prefs(current_user.get("notifPrefs"))
    explicit_sms_enable = False
    if notif_prefs_patch is not UNSET:
        effective_prefs = _normalize_storage_prefs(notif_prefs_patch)
        explicit_sms_enable = _SMS_PREF in effective_prefs

    if email_notifications_patch is not UNSET:
        if bool(email_notifications_patch):
            effective_prefs.add(_EMAIL_PREF)
        else:
            effective_prefs.discard(_EMAIL_PREF)

    if sms_notifications_patch is not UNSET:
        explicit_sms_enable = bool(sms_notifications_patch)
        if explicit_sms_enable:
            effective_prefs.add(_SMS_PREF)
        else:
            effective_prefs.discard(_SMS_PREF)

    has_phone = effective_phone is not None
    has_sms_phone = bool(effective_phone and is_e164_phone(effective_phone))
    if not has_sms_phone:
        if explicit_sms_enable:
            if not has_phone:
                raise APIError(400, "SMS notifications require a valid phone number")
            raise APIError(
                400,
                "SMS notifications require a phone number in E.164 format (for example +15551234567)",
            )
        effective_prefs.discard(_SMS_PREF)

    return {
        "phone": effective_phone,
        "hasPhone": has_phone,
        "hasSmsPhone": has_sms_phone,
        "notifPrefs": _to_ordered_storage_prefs(effective_prefs),
        "emailNotifications": _EMAIL_PREF in effective_prefs,
        "smsNotifications": _SMS_PREF in effective_prefs,
    }

