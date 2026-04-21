import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useAppStore } from "@/lib/store";
import { ArrowLeft, ChevronRight, ImagePlus, Trash2, Pencil, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import {
  ApiError,
  ApiMailRecord,
  ApiMailRequest,
  MailType,
  createMail,
  deleteMail,
  listAdminMailRequests,
  listMail,
  listMailboxes,
  ocrExtract,
  resolveAdminMailRequest,
  retryAdminMailRequestNotification,
  updateMail,
} from "@/lib/api";

function matchesSelectedDate(request: ApiMailRequest, selectedDay: string): boolean {
  const hasStart = !!request.startDate;
  const hasEnd = !!request.endDate;
  if (!hasStart && !hasEnd) return true;
  if (hasStart && hasEnd) return request.startDate! <= selectedDay && selectedDay <= request.endDate!;
  if (hasStart) return request.startDate! <= selectedDay;
  return selectedDay <= request.endDate!;
}

const SKIP_PATTERNS = /(?:priority\s*mail|tracking\s*#|weight\s*:|usps|ups|fedex|\d+\s*lbs?|\d+\s*oz|postage\s*req|firmly\s*to\s*seal|united\s*states)/i;
const SHIP_TO_PATTERN = /(?:ship\s*to|deliver\s*to|recipient|\bto)\s*:\s*/i;
const FROM_PATTERN = /(?:f\s*:?\s*o\s*:?\s*m|from|fe[il1]om|sender|return)\s*:\s*/i;
const ADDRESS_LINE = /\b[A-Z]{2}\s+\d{5}\b|\b\d{5}[\s-]+\d{4}\b|\b\d{5}\b.*\b[A-Z]{2}\b/i;

function stripLeadingNoise(line: string): string {
  return line.replace(/^[^a-zA-Z]*/, "");
}

/** Light cleanup: add space before/after Ave/Blvd/St etc. when missing, fix comma spacing */
function cleanAddressText(s: string): string {
  return s
    .replace(/([a-z])(Ave\.?)/gi, "$1 $2")
    .replace(/([a-z])(Blvd\.?)/gi, "$1 $2")
    .replace(/([a-z])(St\.?|Street)/gi, "$1 $2")
    .replace(/([a-z])(Dr\.?|Drive)/gi, "$1 $2")
    .replace(/([a-z])(Rd\.?|Road)/gi, "$1 $2")
    .replace(/(Blvd\.?|Ave\.?|St\.)([A-Za-z])/gi, "$1 $2") // "Blvd.Everytown" -> "Blvd. Everytown"
    .replace(/,([A-Za-z])/g, ", $1") // "Anywhere,PA" -> "Anywhere, PA"
    .replace(/([a-z])(North|South|East|West)\b/gi, "$1 $2"); // "SmithNorth" -> "Smith North"
}

function parseOcrText(raw: string): { receiver: string; sender: string } {
  const lines = raw.split("\n").map((l) => l.trim()).filter(Boolean);

  const receiver: string[] = [];
  const sender: string[] = [];
  let currentTarget: "receiver" | "sender" | "none" = "none";
  let usedLabels = false;

  for (const rawLine of lines) {
    const line = stripLeadingNoise(rawLine);

    if (SKIP_PATTERNS.test(line)) {
      currentTarget = "none";
      continue;
    }

    const shipMatch = line.match(SHIP_TO_PATTERN);
    if (shipMatch) {
      currentTarget = "receiver";
      usedLabels = true;
      const before = line.slice(0, shipMatch.index!).trim();
      const rest = line.slice(shipMatch.index! + shipMatch[0].length).trim();
      if (before) receiver.push(before);
      if (rest) receiver.push(rest);
      continue;
    }

    const fromMatch = line.match(FROM_PATTERN);
    if (fromMatch) {
      currentTarget = "sender";
      usedLabels = true;
      const before = line.slice(0, fromMatch.index!).trim();
      const rest = line.slice(fromMatch.index! + fromMatch[0].length).trim();
      if (before) sender.push(before);
      if (rest) sender.push(rest);
      continue;
    }

    if (currentTarget === "receiver") {
      receiver.push(line);
    } else if (currentTarget === "sender") {
      sender.push(line);
    }
  }

  if (usedLabels) {
    return {
      receiver: cleanAddressText(receiver.join("\n").trim()),
      sender: cleanAddressText(sender.join("\n").trim()),
    };
  }

  const filtered = lines
    .map((l) => stripLeadingNoise(l))
    .filter((l) => !SKIP_PATTERNS.test(l));

  const blocks: string[][] = [];
  let current: string[] = [];

  for (const line of filtered) {
    current.push(line);
    if (ADDRESS_LINE.test(line)) {
      blocks.push(current);
      current = [];
    }
  }
  if (current.length > 0) {
    const last = blocks[blocks.length - 1];
    if (last) {
      last.push(...current);
    } else {
      blocks.push(current);
    }
  }

  if (blocks.length >= 2) {
    return {
      sender: cleanAddressText(blocks[0].join("\n").trim()),
      receiver: cleanAddressText(blocks.slice(1).map((b) => b.join("\n")).join("\n").trim()),
    };
  }

  return { receiver: cleanAddressText(raw.trim()), sender: "" };
}

type DraftEntry = {
  receiverName: string;
  senderInfo: string;
  type: MailType;
  isPromotional: boolean;
};

const EMPTY_DRAFT: DraftEntry = { receiverName: "", senderInfo: "", type: "letter", isPromotional: false };

function mailPieceQty(entry: ApiMailRecord): number {
  const c = entry.count;
  if (typeof c === "number" && Number.isInteger(c) && c >= 1) return c;
  return 1;
}

const RecordEntry = () => {
  const { mailboxId } = useParams<{ mailboxId: string }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const logout = useAppStore((s) => s.logout);
  const adminOcrEnabled = useAppStore((s) => s.featureFlags.adminOcr);
  const ocrQueueV2 = useAppStore((s) => s.featureFlags.ocrQueueV2);
  const promoClassificationEnabled = useAppStore((s) => s.featureFlags.promoClassification);
  const { toast } = useToast();

  const [mailboxName, setMailboxName] = useState<string>("");
  const [loadingMailbox, setLoadingMailbox] = useState(true);
  const [loadingExisting, setLoadingExisting] = useState(true);
  const [entries, setEntries] = useState<ApiMailRecord[]>([]);
  const [activeRequests, setActiveRequests] = useState<ApiMailRequest[]>([]);
  const [resolvedRequests, setResolvedRequests] = useState<ApiMailRequest[]>([]);
  const [loadingRequests, setLoadingRequests] = useState(true);
  const [resolvingRequestId, setResolvingRequestId] = useState<string | null>(null);
  const [retryingRequestId, setRetryingRequestId] = useState<string | null>(null);

  const [date, setDate] = useState(
    () => searchParams.get("date") || new Date().toISOString().split("T")[0]
  );

  const [draft, setDraft] = useState<DraftEntry>({ ...EMPTY_DRAFT });
  const [showDraftForm, setShowDraftForm] = useState(false);
  const [ocrLoading, setOcrLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  /** Simple count mode (admin OCR off): same as main — totals per type, one save syncs DB rows */
  const [letters, setLetters] = useState(0);
  const [packages, setPackages] = useState(0);
  const [legacySaving, setLegacySaving] = useState(false);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<DraftEntry>({ ...EMPTY_DRAFT });
  const [editSaving, setEditSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      if (!mailboxId) { setLoadingMailbox(false); return; }
      try {
        const mailboxes = await listMailboxes();
        if (!alive) return;
        const mailbox = mailboxes.find((mb) => mb.id === mailboxId);
        setMailboxName(mailbox?.displayName || "");
      } catch (err) {
        if (!alive) return;
        const message = err instanceof Error ? err.message : "Failed to load mailbox";
        toast({ title: message, variant: "destructive" });
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          logout();
          navigate("/");
        }
      } finally {
        if (alive) setLoadingMailbox(false);
      }
    };
    load();
    return () => { alive = false; };
  }, [mailboxId, logout, navigate, toast]);

  const reloadEntries = async () => {
    if (!mailboxId) return;
    setLoadingExisting(true);
    try {
      const rows = await listMail({ date, mailboxId });
      setEntries(rows);
      if (!adminOcrEnabled) {
        const l = rows.filter((e) => e.type === "letter").reduce((s, e) => s + mailPieceQty(e), 0);
        const p = rows.filter((e) => e.type === "package").reduce((s, e) => s + mailPieceQty(e), 0);
        setLetters(l);
        setPackages(p);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load entries";
      toast({ title: message, variant: "destructive" });
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        logout();
        navigate("/");
      }
    } finally {
      setLoadingExisting(false);
    }
  };

  useEffect(() => {
    let alive = true;
    const load = async () => {
      if (!mailboxId) { setLoadingExisting(false); return; }
      setLoadingExisting(true);
      try {
        const rows = await listMail({ date, mailboxId });
        if (!alive) return;
        setEntries(rows);
        if (!adminOcrEnabled) {
          const l = rows.filter((e) => e.type === "letter").reduce((s, e) => s + mailPieceQty(e), 0);
          const p = rows.filter((e) => e.type === "package").reduce((s, e) => s + mailPieceQty(e), 0);
          setLetters(l);
          setPackages(p);
        }
      } catch (err) {
        if (!alive) return;
        const message = err instanceof Error ? err.message : "Failed to load entries";
        toast({ title: message, variant: "destructive" });
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          logout();
          navigate("/");
        }
      } finally {
        if (alive) setLoadingExisting(false);
      }
    };
    load();
    return () => { alive = false; };
  }, [adminOcrEnabled, date, mailboxId, logout, navigate, toast]);

  useEffect(() => {
    let alive = true;
    const loadRequests = async () => {
      if (!mailboxId) { setLoadingRequests(false); return; }
      setLoadingRequests(true);
      try {
        const requests = await listAdminMailRequests({ mailboxId });
        if (!alive) return;
        setActiveRequests(requests.filter((r) => matchesSelectedDate(r, date)));
      } catch (err) {
        if (!alive) return;
        const message = err instanceof Error ? err.message : "Failed to load mail requests";
        toast({ title: message, variant: "destructive" });
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          logout();
          navigate("/");
        }
      } finally {
        if (alive) setLoadingRequests(false);
      }
    };
    void loadRequests();
    return () => { alive = false; };
  }, [date, mailboxId, logout, navigate, toast]);

  const letterCount = useMemo(
    () => entries.reduce((s, e) => s + (e.type === "letter" ? mailPieceQty(e) : 0), 0),
    [entries]
  );
  const packageCount = useMemo(
    () => entries.reduce((s, e) => s + (e.type === "package" ? mailPieceQty(e) : 0), 0),
    [entries]
  );

  if (loadingMailbox) {
    return (
      <div className="min-h-screen flex items-center justify-center text-muted-foreground">
        Loading...
      </div>
    );
  }

  if (!mailboxId || !mailboxName) {
    return (
      <div className="min-h-screen flex items-center justify-center text-muted-foreground">
        Mailbox not found
      </div>
    );
  }

  const toIsoDay = (day: string) => `${day}T00:00:00Z`;

  const makeIdempotencyKey = () => {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      return crypto.randomUUID();
    }
    return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  };

  const handleOcrUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!adminOcrEnabled) return;
    const file = e.target.files?.[0];
    if (!file) return;
    const allowed = ["image/png", "image/jpeg", "image/jpg", "image/gif"];
    if (!allowed.includes(file.type)) {
      toast({ title: "Use PNG, JPEG, or GIF", variant: "destructive" });
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      toast({ title: "Image must be under 2MB", variant: "destructive" });
      return;
    }
    setOcrLoading(true);
    e.target.value = "";
    try {
      const data = await ocrExtract(file);
      if (data.text) {
        const parsed = parseOcrText(data.text);
        setDraft((prev) => ({
          ...prev,
          receiverName: parsed.receiver,
          senderInfo: parsed.sender,
        }));
        setShowDraftForm(true);
        toast({ title: "Text extracted. Review and confirm before saving." });
      } else {
        toast({ title: "No text found in image. Enter manually." });
        setShowDraftForm(true);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "OCR failed";
      toast({ title: message, variant: "destructive" });
    } finally {
      setOcrLoading(false);
    }
  };

  const handleAddEntry = async () => {
    setSaving(true);
    try {
      await createMail({
        mailboxId,
        date: toIsoDay(date),
        type: draft.type,
        receiverName: draft.receiverName.trim() || undefined,
        senderInfo: draft.senderInfo.trim() || undefined,
        isPromotional: promoClassificationEnabled && draft.isPromotional ? true : undefined,
        idempotencyKey: makeIdempotencyKey(),
      });
      setDraft({ ...EMPTY_DRAFT });
      setShowDraftForm(false);
      toast({ title: "Entry added" });
      await reloadEntries();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to add entry";
      toast({ title: message, variant: "destructive" });
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        logout();
        navigate("/");
      }
    } finally {
      setSaving(false);
    }
  };

  const handleLegacySave = async () => {
    if (letters === 0 && packages === 0) {
      toast({ title: "Enter at least 1 letter or package", variant: "destructive" });
      return;
    }
    setLegacySaving(true);
    try {
      const ops: Promise<unknown>[] = [];
      const dateIso = toIsoDay(date);

      const syncType = (type: MailType, targetCount: number) => {
        const typedRows = entries.filter((row) => row.type === type);
        if (targetCount <= 0) {
          ops.push(...typedRows.map((row) => deleteMail(row.id)));
          return;
        }
        if (typedRows.length === 0) {
          ops.push(
            createMail({
              mailboxId: mailboxId!,
              date: dateIso,
              type,
              count: targetCount,
              idempotencyKey: makeIdempotencyKey(),
            })
          );
          return;
        }

        const [primary, ...extra] = typedRows;
        ops.push(
          updateMail(primary.id, {
            count: targetCount,
            date: dateIso,
          })
        );
        ops.push(...extra.map((row) => deleteMail(row.id)));
      };

      syncType("letter", letters);
      syncType("package", packages);

      await Promise.all(ops);
      toast({ title: "Record saved" });
      await reloadEntries();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to save record";
      toast({ title: message, variant: "destructive" });
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        logout();
        navigate("/");
      }
    } finally {
      setLegacySaving(false);
    }
  };

  const handleDeleteEntry = async (entryId: string) => {
    setDeletingId(entryId);
    try {
      await deleteMail(entryId);
      toast({ title: "Entry deleted" });
      await reloadEntries();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to delete entry";
      toast({ title: message, variant: "destructive" });
    } finally {
      setDeletingId(null);
    }
  };

  const startEditing = (entry: ApiMailRecord) => {
    setEditingId(entry.id);
    setEditDraft({
      receiverName: entry.receiverName || "",
      senderInfo: entry.senderInfo || "",
      type: entry.type,
      isPromotional: !!entry.isPromotional,
    });
  };

  const handleSaveEdit = async () => {
    if (!editingId) return;
    setEditSaving(true);
    try {
      await updateMail(editingId, {
        type: editDraft.type,
        receiverName: editDraft.receiverName.trim(),
        senderInfo: editDraft.senderInfo.trim(),
        ...(promoClassificationEnabled ? { isPromotional: editDraft.isPromotional } : {}),
      });
      setEditingId(null);
      toast({ title: "Entry updated" });
      await reloadEntries();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to update entry";
      toast({ title: message, variant: "destructive" });
    } finally {
      setEditSaving(false);
    }
  };

  const handleResolve = async (requestId: string) => {
    setResolvingRequestId(requestId);
    try {
      const updated = await resolveAdminMailRequest(requestId);
      setActiveRequests((items) => items.filter((item) => item.id !== requestId));
      setResolvedRequests((items) => [updated, ...items.filter((item) => item.id !== requestId)]);
      toast({ title: "Request resolved and notification attempted" });
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setActiveRequests((items) => items.filter((item) => item.id !== requestId));
        toast({ title: "Request was already resolved or unavailable" });
        return;
      }
      const message = err instanceof Error ? err.message : "Failed to resolve request";
      toast({ title: message, variant: "destructive" });
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        logout();
        navigate("/");
      }
    } finally {
      setResolvingRequestId(null);
    }
  };

  const handleRetry = async (requestId: string) => {
    setRetryingRequestId(requestId);
    try {
      const updated = await retryAdminMailRequestNotification(requestId);
      setResolvedRequests((items) => items.map((item) => (item.id === requestId ? updated : item)));
      toast({ title: "Notification retry attempted" });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to retry notification";
      toast({ title: message, variant: "destructive" });
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        logout();
        navigate("/");
      }
    } finally {
      setRetryingRequestId(null);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur">
        <div className="flex items-center gap-3 px-4 h-14">
          <button
            onClick={() =>
              navigate(
                adminOcrEnabled && ocrQueueV2
                  ? `/admin/recording${date ? `?date=${date}` : ""}`
                  : "/admin"
              )
            }
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <h1 className="text-lg font-bold text-foreground truncate flex-1">{mailboxName}</h1>
          <Button
            variant="secondary"
            size="sm"
            className="gap-1.5 shrink-0"
            onClick={() => navigate(`/admin/mailboxes?date=${date}`)}
          >
            <ChevronRight className="h-4 w-4" />
            Next user
          </Button>
        </div>
      </header>

      <div className="px-4 py-6 max-w-5xl mx-auto grid gap-6 lg:grid-cols-[1fr_360px]">
        <div className="space-y-6">
          {/* Date */}
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-foreground">Date</label>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="w-full h-11 rounded-lg border border-input bg-card px-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          {adminOcrEnabled && (
            <>
              {/* Summary counts */}
              <div className="flex items-center gap-4 text-sm text-muted-foreground">
                <span>{letterCount} letter{letterCount !== 1 ? "s" : ""}</span>
                <span>{packageCount} package{packageCount !== 1 ? "s" : ""}</span>
              </div>

              {/* Existing entries */}
              <div className="space-y-2">
                <h2 className="text-sm font-semibold text-foreground">Mail Items</h2>
                {loadingExisting ? (
                  <p className="text-sm text-muted-foreground">Loading...</p>
                ) : entries.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No entries for this date. Scan or add manually below.</p>
                ) : (
                  <div className="divide-y divide-border rounded-xl border bg-card overflow-hidden">
                    {entries.map((entry) => (
                      <div key={entry.id} className="px-4 py-3">
                        {editingId === entry.id ? (
                          <div className="space-y-2">
                            <div className="flex items-center gap-2">
                              <select
                                value={editDraft.type}
                                onChange={(e) => setEditDraft((d) => ({ ...d, type: e.target.value as MailType }))}
                                className="h-9 rounded-lg border border-input bg-background px-2 text-sm"
                              >
                                <option value="letter">Letter</option>
                                <option value="package">Package</option>
                              </select>
                            </div>
                            <input
                              type="text"
                              value={editDraft.receiverName}
                              onChange={(e) => setEditDraft((d) => ({ ...d, receiverName: e.target.value }))}
                              placeholder="Receiver name/company"
                              className="w-full h-9 rounded-lg border border-input bg-background px-3 text-sm"
                            />
                            <input
                              type="text"
                              value={editDraft.senderInfo}
                              onChange={(e) => setEditDraft((d) => ({ ...d, senderInfo: e.target.value }))}
                              placeholder="Sender (optional)"
                              className="w-full h-9 rounded-lg border border-input bg-background px-3 text-sm"
                            />
                            {promoClassificationEnabled && (
                              <label className="flex items-center gap-2 text-sm text-foreground">
                                <input
                                  type="checkbox"
                                  checked={editDraft.isPromotional}
                                  onChange={(e) => setEditDraft((d) => ({ ...d, isPromotional: e.target.checked }))}
                                  className="h-4 w-4"
                                />
                                Promotional
                              </label>
                            )}
                            <div className="flex gap-2">
                              <Button size="sm" onClick={handleSaveEdit} disabled={editSaving}>
                                {editSaving ? "Saving..." : "Save"}
                              </Button>
                              <Button size="sm" variant="ghost" onClick={() => setEditingId(null)}>Cancel</Button>
                            </div>
                          </div>
                        ) : (
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="inline-block rounded-md bg-muted px-2 py-0.5 text-xs font-medium capitalize">
                                  {entry.type}
                                  {mailPieceQty(entry) > 1 ? ` ×${mailPieceQty(entry)}` : ""}
                                </span>
                                {entry.isPromotional && (
                                  <span className="inline-block rounded-md bg-amber-100 text-amber-900 px-2 py-0.5 text-xs font-medium">
                                    Promo
                                  </span>
                                )}
                              </div>
                              {entry.receiverName && (
                                <p className="text-sm text-card-foreground mt-1 truncate">{entry.receiverName}</p>
                              )}
                              {entry.senderInfo && (
                                <p className="text-xs text-muted-foreground mt-0.5 truncate">From: {entry.senderInfo}</p>
                              )}
                              {!entry.receiverName && !entry.senderInfo && (
                                <p className="text-xs text-muted-foreground mt-1 italic">No details</p>
                              )}
                            </div>
                            <div className="flex items-center gap-1 shrink-0">
                              <button
                                onClick={() => startEditing(entry)}
                                className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                              >
                                <Pencil className="h-3.5 w-3.5" />
                              </button>
                              <button
                                onClick={() => handleDeleteEntry(entry.id)}
                                disabled={deletingId === entry.id}
                                className="p-1.5 rounded-md text-muted-foreground hover:text-destructive hover:bg-muted transition-colors disabled:opacity-50"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}

          {/* Simple counts (no OCR): same UX as main */}
          <div className="space-y-3">
            {!adminOcrEnabled ? (
              <>
                {loadingExisting ? (
                  <p className="text-sm text-muted-foreground">Loading...</p>
                ) : (
                  <>
                    <p className="text-xs text-muted-foreground">
                      Set totals for this mailbox and date, then save. Use 0 for a type to clear it.
                    </p>
                    <div className="space-y-1.5">
                      <label className="text-sm font-medium text-foreground">Letters</label>
                      <div className="flex items-center gap-3">
                        <button
                          type="button"
                          onClick={() => setLetters(Math.max(0, letters - 1))}
                          className="h-11 w-11 rounded-lg border border-input bg-card text-foreground text-xl font-medium flex items-center justify-center hover:bg-muted transition-colors"
                        >
                          −
                        </button>
                        <input
                          className="text-2xl font-bold text-foreground w-14 text-center bg-transparent border-0 focus:outline-none focus:ring-0"
                          onChange={(e) => setLetters(Math.max(0, parseInt(e.target.value, 10) || 0))}
                          value={letters}
                          inputMode="numeric"
                        />
                        <button
                          type="button"
                          onClick={() => setLetters(letters + 1)}
                          className="h-11 w-11 rounded-lg border border-input bg-card text-foreground text-xl font-medium flex items-center justify-center hover:bg-muted transition-colors"
                        >
                          +
                        </button>
                      </div>
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-sm font-medium text-foreground">Packages</label>
                      <div className="flex items-center gap-3">
                        <button
                          type="button"
                          onClick={() => setPackages(Math.max(0, packages - 1))}
                          className="h-11 w-11 rounded-lg border border-input bg-card text-foreground text-xl font-medium flex items-center justify-center hover:bg-muted transition-colors"
                        >
                          −
                        </button>
                        <input
                          className="text-2xl font-bold text-foreground w-14 text-center bg-transparent border-0 focus:outline-none focus:ring-0"
                          onChange={(e) => setPackages(Math.max(0, parseInt(e.target.value, 10) || 0))}
                          value={packages}
                          inputMode="numeric"
                        />
                        <button
                          type="button"
                          onClick={() => setPackages(packages + 1)}
                          className="h-11 w-11 rounded-lg border border-input bg-card text-foreground text-xl font-medium flex items-center justify-center hover:bg-muted transition-colors"
                        >
                          +
                        </button>
                      </div>
                    </div>
                    <Button onClick={handleLegacySave} className="w-full h-12 text-base" disabled={legacySaving}>
                      {legacySaving ? "Saving..." : "Save"}
                    </Button>
                  </>
                )}
              </>
            ) : (
              <>
                <div className="flex flex-wrap items-center gap-2">
                  <label className="inline-flex items-center gap-1.5 h-10 px-3 rounded-lg border border-input bg-card text-sm font-medium text-foreground cursor-pointer hover:bg-muted transition-colors relative overflow-hidden">
                    <ImagePlus className="h-4 w-4 pointer-events-none" />
                    <span className="pointer-events-none">{ocrLoading ? "Extracting..." : "Scan image"}</span>
                    <input
                      type="file"
                      accept="image/png,image/jpeg,image/jpg,image/gif"
                      capture="environment"
                      onChange={handleOcrUpload}
                      disabled={ocrLoading}
                      className="absolute inset-0 opacity-0 w-full h-full cursor-pointer"
                    />
                  </label>
                  <Button
                    variant="outline"
                    className="h-10 gap-1.5"
                    onClick={() => { setDraft({ ...EMPTY_DRAFT }); setShowDraftForm(true); }}
                  >
                    <Plus className="h-4 w-4" />
                    Add manually
                  </Button>
                </div>

                {showDraftForm && (
                  <div className="rounded-xl border bg-card p-4 space-y-3">
                    <h3 className="text-sm font-semibold text-foreground">New Entry — Review & Confirm</h3>
                    <div className="flex items-center gap-2">
                      <label className="text-sm text-muted-foreground">Type</label>
                      <select
                        value={draft.type}
                        onChange={(e) => setDraft((d) => ({ ...d, type: e.target.value as MailType }))}
                        className="h-9 rounded-lg border border-input bg-background px-2 text-sm"
                      >
                        <option value="letter">Letter</option>
                        <option value="package">Package</option>
                      </select>
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-sm font-medium text-foreground">Receiver name / company</label>
                      <textarea
                        value={draft.receiverName}
                        onChange={(e) => setDraft((d) => ({ ...d, receiverName: e.target.value }))}
                        placeholder="Extracted from scan, or type manually…"
                        className="w-full min-h-20 rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-sm font-medium text-foreground">Sender (optional)</label>
                      <input
                        type="text"
                        value={draft.senderInfo}
                        onChange={(e) => setDraft((d) => ({ ...d, senderInfo: e.target.value }))}
                        placeholder="Sender name or return address…"
                        className="w-full h-10 rounded-lg border border-input bg-background px-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                      />
                    </div>
                    {promoClassificationEnabled && (
                      <label className="flex items-center gap-2 text-sm text-foreground">
                        <input
                          type="checkbox"
                          checked={draft.isPromotional}
                          onChange={(e) => setDraft((d) => ({ ...d, isPromotional: e.target.checked }))}
                          className="h-4 w-4"
                        />
                        Promotional
                      </label>
                    )}
                    <div className="flex gap-2">
                      <Button onClick={handleAddEntry} disabled={saving} className="h-10">
                        {saving ? "Saving..." : "Confirm & Add"}
                      </Button>
                      <Button variant="ghost" className="h-10" onClick={() => { setShowDraftForm(false); setDraft({ ...EMPTY_DRAFT }); }}>
                        Cancel
                      </Button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* Sidebar: Mail Requests */}
        <aside className="rounded-xl border bg-card p-3 space-y-3 h-fit">
          <h2 className="text-sm font-semibold text-foreground">Expected Mail Requests</h2>
          {loadingRequests ? (
            <p className="text-xs text-muted-foreground">Loading requests...</p>
          ) : activeRequests.length === 0 ? (
            <p className="text-xs text-muted-foreground">No active requests for selected date.</p>
          ) : (
            <div className="space-y-2">
              {activeRequests.map((request) => (
                <div key={request.id} className="rounded-lg border p-2 space-y-1.5">
                  <p className="text-xs text-card-foreground">{request.expectedSender || request.description || "No details"}</p>
                  <p className="text-xs text-muted-foreground">
                    {request.startDate || request.endDate ? `${request.startDate || "?"} to ${request.endDate || "?"}` : "No date window"}
                  </p>
                  <Button
                    onClick={() => handleResolve(request.id)}
                    disabled={resolvingRequestId === request.id}
                    className="w-full h-8 text-xs"
                  >
                    {resolvingRequestId === request.id ? "Resolving..." : "Resolve & Notify"}
                  </Button>
                </div>
              ))}
            </div>
          )}

          {resolvedRequests.length > 0 && (
            <div className="space-y-2 border-t pt-3">
              <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Recently Resolved</h3>
              {resolvedRequests.map((request) => (
                <div key={request.id} className="rounded-lg border p-2 space-y-1.5">
                  <p className="text-xs text-card-foreground">{request.expectedSender || request.description || "No details"}</p>
                  <p className="text-xs text-muted-foreground">
                    Notification: {request.lastNotificationStatus || "—"}
                    {request.lastNotificationAt ? ` at ${new Date(request.lastNotificationAt).toLocaleString()}` : ""}
                  </p>
                  <Button
                    onClick={() => handleRetry(request.id)}
                    disabled={retryingRequestId === request.id}
                    variant="secondary"
                    className="w-full h-8 text-xs"
                  >
                    {retryingRequestId === request.id ? "Retrying..." : "Retry Notification"}
                  </Button>
                </div>
              ))}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
};

export default RecordEntry;
