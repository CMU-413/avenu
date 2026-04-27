import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAppStore } from "@/lib/store";
import { ArrowLeft } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { ApiError, updateMemberPreferences } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import { buildPreferencePatch, deriveSettingsState, type NotificationPreferenceState } from "@/lib/member-preferences";

const NotificationSettings = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { sessionUser, logout, setSessionNotificationPreferences } = useAppStore();
  const [pending, setPending] = useState(false);
  const [optimisticPrefs, setOptimisticPrefs] = useState<NotificationPreferenceState | null>(null);

  const basePrefs: NotificationPreferenceState = useMemo(
    () => ({
      emailNotifications: sessionUser?.emailNotifications ?? false,
      smsNotifications: sessionUser?.smsNotifications ?? false,
      hasPhone: sessionUser?.hasPhone ?? false,
      hasSmsPhone: sessionUser?.hasSmsPhone ?? false,
    }),
    [
      sessionUser?.emailNotifications,
      sessionUser?.smsNotifications,
      sessionUser?.hasPhone,
      sessionUser?.hasSmsPhone,
    ],
  );
  const activePrefs = optimisticPrefs ?? basePrefs;
  const settings = deriveSettingsState(activePrefs);

  const persistPreferences = useCallback(
    async (
      patch: { emailNotifications?: boolean; smsNotifications?: boolean },
      optimisticNext: NotificationPreferenceState,
      fallback: NotificationPreferenceState,
    ) => {
      if (!("emailNotifications" in patch) && !("smsNotifications" in patch)) return;
      setPending(true);
      setOptimisticPrefs(optimisticNext);
      try {
        const updated = await updateMemberPreferences(patch);
        const next = {
          emailNotifications: updated.emailNotifications,
          smsNotifications: updated.smsNotifications,
          hasPhone: updated.hasPhone,
          hasSmsPhone: updated.hasSmsPhone,
        };
        setSessionNotificationPreferences(next);
        setOptimisticPrefs(next);
      } catch (err) {
        setSessionNotificationPreferences(fallback);
        setOptimisticPrefs(fallback);
        const message = err instanceof Error ? err.message : "Failed to update notification settings";
        toast({ title: message, variant: "destructive" });
        if (err instanceof ApiError && err.status === 401) {
          logout();
          navigate("/");
        }
      } finally {
        setPending(false);
      }
    },
    [logout, navigate, setSessionNotificationPreferences, toast],
  );

  useEffect(() => {
    if (pending) return;
    if (!activePrefs.hasSmsPhone && activePrefs.smsNotifications) {
      const patch = buildPreferencePatch(basePrefs, { smsNotifications: false });
      const optimisticNext = {
        ...basePrefs,
        smsNotifications: false,
      };
      void persistPreferences(patch, optimisticNext, basePrefs);
    }
  }, [pending, activePrefs.hasSmsPhone, activePrefs.smsNotifications, basePrefs, persistPreferences]);

  if (!sessionUser) return null;

  const handleEmailToggle = async (nextValue: boolean) => {
    if (pending) return;
    const patch = buildPreferencePatch(basePrefs, { emailNotifications: nextValue });
    const optimisticNext = {
      ...basePrefs,
      emailNotifications: nextValue,
    };
    await persistPreferences(patch, optimisticNext, basePrefs);
  };

  const handleSmsToggle = async (nextValue: boolean) => {
    if (pending || settings.smsDisabled) return;
    const patch = buildPreferencePatch(basePrefs, { smsNotifications: nextValue });
    const optimisticNext = {
      ...basePrefs,
      smsNotifications: nextValue,
    };
    await persistPreferences(patch, optimisticNext, basePrefs);
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur">
        <div className="flex items-center gap-3 px-4 h-14">
          <button onClick={() => navigate(-1)} className="text-muted-foreground hover:text-foreground transition-colors">
            <ArrowLeft className="h-5 w-5" />
          </button>
          <h1 className="text-lg font-bold text-foreground">Settings</h1>
        </div>
      </header>

      <div className="px-4 py-6 max-w-lg mx-auto">
        <div className="rounded-xl border bg-card p-4 flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-card-foreground">Email Notifications</p>
            <p className="text-xs text-muted-foreground">Receive weekly mail summaries</p>
          </div>
          <Switch
            checked={settings.emailNotifications}
            onCheckedChange={handleEmailToggle}
            disabled={pending}
          />
        </div>
        <div className="mt-3 rounded-xl border bg-card p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-card-foreground">SMS Notifications</p>
              <p className="text-xs text-muted-foreground">Receive weekly summaries by text message</p>
            </div>
            <Switch
              checked={settings.smsNotifications}
              onCheckedChange={handleSmsToggle}
              disabled={pending || settings.smsDisabled}
            />
          </div>
          {settings.smsInlineMessage ? (
            <p className="mt-2 text-xs text-muted-foreground">{settings.smsInlineMessage}</p>
          ) : null}
        </div>
      </div>
    </div>
  );
};

export default NotificationSettings;
