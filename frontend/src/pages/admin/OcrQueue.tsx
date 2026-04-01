import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  ArrowLeft,
  Camera,
  ChevronLeft,
  ChevronRight,
  Check,
  Loader2,
  Search,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import {
  ApiError,
  listMailboxes,
  listTeams,
  listUsers,
  createOcrJob,
  listOcrJobs,
  getOcrJob,
  updateOcrQueueItem,
  confirmOcrQueueItem,
  deleteOcrQueueItem,
  updateOcrJobStage,
  type ApiOcrJob,
  type ApiOcrQueueItem,
} from "@/lib/api";
import { useAppStore } from "@/lib/store";

const POLL_INTERVAL_MS = 2000;

const OcrQueue = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const jobIdFromUrl = searchParams.get("job");
  const logout = useAppStore((s) => s.logout);
  const { toast } = useToast();
  const toastRef = useRef(toast);
  toastRef.current = toast;

  const [jobs, setJobs] = useState<ApiOcrJob[]>([]);
  const [loadingJobs, setLoadingJobs] = useState(true);
  const [currentJob, setCurrentJob] = useState<{
    job: ApiOcrJob;
    items: ApiOcrQueueItem[];
  } | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [stagedFiles, setStagedFiles] = useState<File[]>([]);
  const [pendingJobId, setPendingJobId] = useState<string | null>(null);
  const [mailboxes, setMailboxes] = useState<
    { id: string; name: string; type: "company" | "personal"; memberNames: string[] }[]
  >([]);
  const [loadingMailboxes, setLoadingMailboxes] = useState(false);
  const [showMailboxPicker, setShowMailboxPicker] = useState(false);
  const [mailboxQuery, setMailboxQuery] = useState("");
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [editingItem, setEditingItem] = useState<Partial<ApiOcrQueueItem>>({});

  const date = searchParams.get("date") || new Date().toISOString().split("T")[0];

  const loadJobs = useCallback(async () => {
    try {
      const { jobs: list } = await listOcrJobs();
      setJobs(list);
    } catch (err) {
      toastRef.current({ title: err instanceof Error ? err.message : "Failed to load jobs", variant: "destructive" });
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        logout();
        navigate("/");
      }
    } finally {
      setLoadingJobs(false);
    }
  }, [logout, navigate]);

  const loadJobDetail = useCallback(
    async (id: string) => {
      try {
        const data = await getOcrJob(id);
        setCurrentJob(data);
        setCurrentIndex(0);
        setEditingItem({});
      } catch (err) {
        toastRef.current({ title: err instanceof Error ? err.message : "Failed to load job", variant: "destructive" });
      }
    },
    []
  );

  useEffect(() => {
    if (!jobIdFromUrl) {
      loadJobs();
    }
  }, [jobIdFromUrl, loadJobs]);

  useEffect(() => {
    if (jobIdFromUrl) {
      loadJobDetail(jobIdFromUrl);
    } else {
      setCurrentJob(null);
      setCurrentIndex(0);
    }
  }, [jobIdFromUrl, loadJobDetail]);

  useEffect(() => {
    if (currentJob?.job.status === "processing") {
      const t = setInterval(() => loadJobDetail(currentJob.job.id), POLL_INTERVAL_MS);
      return () => clearInterval(t);
    }
  }, [currentJob?.job.id, currentJob?.job.status, loadJobDetail]);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      setLoadingMailboxes(true);
      try {
        const [mailboxList, userList, teamList] = await Promise.all([
          listMailboxes(),
          listUsers(),
          listTeams(),
        ]);
        if (!alive) return;
        const usersById = new Map(userList.map((u) => [u.id, u]));
        const teamMembers = new Map<string, string[]>();
        for (const team of teamList) {
          teamMembers.set(
            team.id,
            userList.filter((u) => u.teamIds.includes(team.id)).map((u) => u.fullname)
          );
        }
        setMailboxes(
          mailboxList.map((mb) => ({
            id: mb.id,
            name: mb.displayName,
            type: (mb.type === "team" ? "company" : "personal") as "company" | "personal",
            memberNames:
              mb.type === "user"
                ? ([usersById.get(mb.refId)?.fullname].filter(Boolean) as string[])
                : teamMembers.get(mb.refId) || [],
          }))
        );
      } finally {
        if (alive) setLoadingMailboxes(false);
      }
    };
    load();
    return () => {
      alive = false;
    };
  }, []);

  const filteredMailboxes = useMemo(() => {
    const q = mailboxQuery.toLowerCase().trim();
    if (!q) {
      return {
        company: mailboxes.filter((m) => m.type === "company"),
        personal: mailboxes.filter((m) => m.type === "personal"),
      };
    }
    const matchedByName = mailboxes.filter((m) => m.name.toLowerCase().includes(q));
    const matchedByMember = mailboxes.filter(
      (m) => !matchedByName.includes(m) && m.memberNames.some((n) => n?.toLowerCase().includes(q))
    );
    const all = [...matchedByName, ...matchedByMember];
    return {
      company: all.filter((m) => m.type === "company"),
      personal: all.filter((m) => m.type === "personal"),
    };
  }, [mailboxes, mailboxQuery]);

  useEffect(() => {
    setEditingItem({});
    setShowMailboxPicker(false);
  }, [currentIndex]);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files?.length) return;
    const list = Array.from(files).filter((f) => f.type.startsWith("image/"));
    if (!list.length) {
      toast({ title: "No valid images selected", variant: "destructive" });
      return;
    }
    setStagedFiles((prev) => [...prev, ...list]);
    toast({ title: `${list.length} photo${list.length > 1 ? "s" : ""} added (${stagedFiles.length + list.length} total)` });
    e.target.value = "";
  };

  const handleRemoveStaged = (index: number) => {
    setStagedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleProcessAll = async () => {
    if (!stagedFiles.length) return;
    setUploading(true);
    try {
      const job = await createOcrJob(stagedFiles, date);
      toast({ title: `Uploaded ${stagedFiles.length} images. Processing in background...` });
      setStagedFiles([]);
      setPendingJobId(job.id);
      loadJobs();
    } catch (err) {
      toast({ title: err instanceof Error ? err.message : "Upload failed", variant: "destructive" });
    } finally {
      setUploading(false);
    }
  };

  useEffect(() => {
    if (!pendingJobId) return;
    const poll = setInterval(async () => {
      try {
        const data = await getOcrJob(pendingJobId);
        if (data.job.status === "completed" || data.job.status === "processed" || data.job.status === "failed") {
          clearInterval(poll);
          setPendingJobId(null);
          loadJobs();
          if (data.job.status === "completed" || data.job.status === "processed") {
            toastRef.current({ title: "All images parsed. Ready to review." });
            navigate(`/admin/recording?job=${pendingJobId}&date=${date}`);
          } else {
            toastRef.current({ title: "OCR processing failed", variant: "destructive" });
          }
        }
      } catch {
        /* keep polling */
      }
    }, POLL_INTERVAL_MS);
    return () => clearInterval(poll);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingJobId, date, navigate]);

  const item = currentJob?.items[currentIndex];
  const effectiveItem = item
    ? {
        ...item,
        receiverName: editingItem.receiverName ?? item.receiverName ?? "",
        senderInfo: editingItem.senderInfo ?? item.senderInfo ?? "",
        type: editingItem.type ?? item.type ?? "letter",
        mailboxId: editingItem.mailboxId ?? item.mailboxId,
      }
    : null;

  const handleUpdateItem = async (updates: Partial<ApiOcrQueueItem>) => {
    if (!item) return;
    try {
      await updateOcrQueueItem(item.id, updates);
      setEditingItem((prev) => ({ ...prev, ...updates }));
      if (currentJob) {
        const next = currentJob.items.map((i) =>
          i.id === item.id ? { ...i, ...updates } : i
        );
        setCurrentJob({ ...currentJob, items: next });
      }
    } catch (err) {
      toast({ title: err instanceof Error ? err.message : "Update failed", variant: "destructive" });
    }
  };

  const handleConfirm = async () => {
    if (!item) return;
    if (!effectiveItem?.mailboxId) {
      toast({ title: "Select a mailbox first", variant: "destructive" });
      return;
    }
    setConfirmingId(item.id);
    try {
      if (Object.keys(editingItem).length > 0) {
        await updateOcrQueueItem(item.id, {
          receiverName: effectiveItem.receiverName || undefined,
          senderInfo: effectiveItem.senderInfo || undefined,
          type: effectiveItem.type,
          mailboxId: effectiveItem.mailboxId,
        });
      }
      await confirmOcrQueueItem(item.id);
      toast({ title: "Mail recorded" });
      if (currentJob) {
        const next = currentJob.items.map((i) =>
          i.id === item.id ? { ...i, status: "confirmed" as const, confirmedAt: new Date().toISOString() } : i
        );
        setCurrentJob({ ...currentJob, items: next });
        setEditingItem({});
        const nextUnconfirmed = next.findIndex((i) => i.status !== "confirmed");
        setCurrentIndex(nextUnconfirmed >= 0 ? nextUnconfirmed : currentJob.items.length - 1);
      }
    } catch (err) {
      toast({ title: err instanceof Error ? err.message : "Confirm failed", variant: "destructive" });
    } finally {
      setConfirmingId(null);
    }
  };

  const handleDelete = async () => {
    if (!item) return;
    try {
      await deleteOcrQueueItem(item.id);
      toast({ title: "Item deleted" });
      if (currentJob) {
        // Optimistically remove
        const next = currentJob.items.filter((i) => i.id !== item.id);
        setCurrentJob({ ...currentJob, items: next });
        setEditingItem({});
        if (next.length === 0) {
          setCurrentIndex(0);
        } else if (currentIndex >= next.length) {
          setCurrentIndex(next.length - 1);
        }
      }
    } catch (err) {
      toast({ title: "Delete failed", variant: "destructive" });
    }
  };

  const openMailboxPicker = () => {
    const firstLine = effectiveItem?.receiverName?.split("\n")[0]?.trim() || "";
    setMailboxQuery(firstLine);
    setShowMailboxPicker(true);
  };

  const selectMailbox = (mailboxId: string) => {
    handleUpdateItem({ mailboxId });
    setShowMailboxPicker(false);
  };

  const allConfirmed =
    currentJob?.items.every((i) => i.status === "confirmed") ?? false;
  const confirmedCount = currentJob?.items.filter((i) => i.status === "confirmed").length ?? 0;

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur">
        <div className="flex items-center gap-3 px-4 h-14">
          <button
            onClick={() =>
              jobIdFromUrl ? navigate("/admin/recording") : navigate("/admin")
            }
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <h1 className="text-lg font-bold text-foreground">
            {currentJob ? `Verify (${confirmedCount}/${currentJob.items.length})` : "Record Mail"}
          </h1>
        </div>
      </header>

      <div className="px-4 py-4 max-w-lg mx-auto space-y-4">
        {!currentJob && (
          <>
            <div className="rounded-xl border border-dashed border-muted-foreground/30 bg-muted/20 p-6 flex flex-col items-center justify-center gap-3">
              <Camera className="h-10 w-10 text-muted-foreground" />
              <p className="text-sm text-muted-foreground text-center">
                Snap or upload photos of all mail, then process in one batch.
              </p>
              <div>
                <input
                  id="ocr-file-input"
                  type="file"
                  accept="image/*"
                  multiple
                  className="hidden"
                  onChange={handleFileSelect}
                  disabled={uploading}
                />
                <Button
                  variant="outline"
                  disabled={uploading}
                  className="gap-2"
                  onClick={() => document.getElementById("ocr-file-input")?.click()}
                >
                  <Camera className="h-4 w-4" />
                  {stagedFiles.length > 0 ? "Add more photos" : "Add photos"}
                </Button>
              </div>
            </div>

            {stagedFiles.length > 0 && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-foreground">
                    {stagedFiles.length} photo{stagedFiles.length !== 1 ? "s" : ""} ready
                  </h3>
                  <button
                    onClick={() => setStagedFiles([])}
                    className="text-xs text-muted-foreground hover:text-destructive transition-colors"
                  >
                    Clear all
                  </button>
                </div>
                <div className="grid grid-cols-4 gap-2">
                  {stagedFiles.map((file, i) => (
                    <div key={i} className="relative group rounded-lg overflow-hidden border bg-muted aspect-square">
                      <img
                        src={URL.createObjectURL(file)}
                        alt={file.name}
                        className="w-full h-full object-cover"
                      />
                      <button
                        onClick={() => handleRemoveStaged(i)}
                        className="absolute top-0.5 right-0.5 bg-black/60 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        &times;
                      </button>
                    </div>
                  ))}
                </div>
                <Button
                  className="w-full gap-2"
                  onClick={handleProcessAll}
                  disabled={uploading}
                >
                  {uploading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Check className="h-4 w-4" />
                  )}
                  {uploading ? "Uploading..." : `Process ${stagedFiles.length} photo${stagedFiles.length !== 1 ? "s" : ""}`}
                </Button>
              </div>
            )}

            <div className="space-y-2">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground px-1">
                Recent jobs
              </h3>
              {loadingJobs ? (
                <p className="text-sm text-muted-foreground py-4">Loading...</p>
              ) : jobs.length === 0 ? (
                <p className="text-sm text-muted-foreground py-4">No jobs yet</p>
              ) : (
                <div className="divide-y rounded-xl border bg-card overflow-hidden">
                  {jobs.map((j) => (
                    <button
                      key={j.id}
                      onClick={() => navigate(`/admin/recording?job=${j.id}&date=${date}`)}
                      className="w-full flex items-center justify-between px-4 py-3 hover:bg-muted/50 transition-colors text-left"
                    >
                      <div>
                        <p className="text-sm font-medium">
                          {j.totalCount} items • {j.date}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {j.status === "processing"
                            ? `${j.completedCount}/${j.totalCount} parsed`
                            : j.status}
                        </p>
                      </div>
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    </button>
                  ))}
                </div>
              )}
            </div>
          </>
        )}

        {currentJob?.job.status === "processing" && (
          <div className="rounded-xl border bg-card p-6 flex flex-col items-center gap-3">
            <Loader2 className="h-10 w-10 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">
              Parsing {currentJob.job.completedCount} of {currentJob.job.totalCount} images...
            </p>
            <p className="text-xs text-muted-foreground">Review will start automatically when done.</p>
          </div>
        )}

        {!currentJob && pendingJobId && (
          <div className="rounded-xl border bg-card p-4 flex items-center gap-3">
            <Loader2 className="h-5 w-5 animate-spin text-primary shrink-0" />
            <p className="text-sm text-muted-foreground">
              Processing images in the background. You can keep adding more or wait...
            </p>
          </div>
        )}

        {((currentJob?.job.status === "processed" || currentJob?.job.status === "completed") && currentJob.items.length > 0 && !allConfirmed) && (
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between gap-2">
              <Button
                variant="outline"
                size="icon"
                disabled={currentIndex <= 0}
                onClick={() => setCurrentIndex((i) => Math.max(0, i - 1))}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="text-sm text-muted-foreground">
                {currentIndex + 1} of {currentJob.items.length}
              </span>
              <Button
                variant="outline"
                size="icon"
                disabled={currentIndex >= currentJob.items.length - 1}
                onClick={() => setCurrentIndex((i) => Math.min(currentJob.items.length - 1, i + 1))}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Left Column: Image */}
              <div className="rounded-xl overflow-hidden bg-muted flex items-center justify-center border aspect-[3/4] md:aspect-auto">
                {effectiveItem?.fileId ? (
                   <img 
                     src={`/api/ocr/queue/${effectiveItem.id}/image`} 
                     alt="Mail Item" 
                     className="max-h-full max-w-full object-contain"
                   />
                ) : (
                  <p className="text-muted-foreground text-sm">No image available</p>
                )}
              </div>

              {/* Right Column: Form */}
              <div className="flex flex-col gap-4">
                {effectiveItem?.status === "failed" && (
                  <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-4">
                    <p className="text-sm font-medium text-destructive">OCR failed</p>
                    <p className="text-xs text-muted-foreground mt-1">{item?.error}</p>
                    <div className="flex justify-between items-center mt-2">
                        <p className="text-xs text-muted-foreground">Skip to next or add manually later.</p>
                        <Button variant="destructive" size="sm" onClick={handleDelete}>Delete</Button>
                    </div>
                  </div>
                )}

                {effectiveItem && effectiveItem.status !== "confirmed" && effectiveItem.status !== "failed" && (
                  <div className="rounded-xl border bg-card p-4 space-y-4">
                <div>
                  <label className="text-xs font-medium text-muted-foreground">Receiver</label>
                  <textarea
                    value={effectiveItem.receiverName ?? ""}
                    onChange={(e) => setEditingItem((p) => ({ ...p, receiverName: e.target.value }))}
                    placeholder="Recipient name/address"
                    rows={3}
                    className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground">Sender</label>
                  <textarea
                    value={effectiveItem.senderInfo ?? ""}
                    onChange={(e) => setEditingItem((p) => ({ ...p, senderInfo: e.target.value }))}
                    placeholder="Sender / return address"
                    rows={2}
                    className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground">Type</label>
                  <div className="mt-1 flex gap-2">
                    <Button
                      variant={effectiveItem.type === "letter" ? "default" : "outline"}
                      size="sm"
                      onClick={() => handleUpdateItem({ type: "letter" })}
                    >
                      Letter
                    </Button>
                    <Button
                      variant={effectiveItem.type === "package" ? "default" : "outline"}
                      size="sm"
                      onClick={() => handleUpdateItem({ type: "package" })}
                    >
                      Package
                    </Button>
                  </div>
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground">Mailbox</label>
                  {showMailboxPicker ? (
                    <div className="mt-1 space-y-2 rounded-lg border border-input bg-background p-3">
                      <div className="relative">
                        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                        <input
                          type="text"
                          value={mailboxQuery}
                          onChange={(e) => setMailboxQuery(e.target.value)}
                          placeholder="Search mailbox or member..."
                          className="w-full h-9 pl-8 pr-3 rounded border border-input text-sm"
                          autoFocus
                        />
                      </div>
                      {loadingMailboxes ? (
                        <p className="text-xs text-muted-foreground">Loading...</p>
                      ) : (
                        <div className="max-h-48 overflow-y-auto space-y-2">
                          {[
                            ...filteredMailboxes.company,
                            ...filteredMailboxes.personal,
                          ].map((mb) => (
                            <button
                              key={mb.id}
                              onClick={() => selectMailbox(mb.id)}
                              className="block w-full text-left px-2 py-1.5 rounded hover:bg-muted text-sm"
                            >
                              {mb.name}
                              <span className="text-xs text-muted-foreground ml-2">
                                {mb.type}
                              </span>
                            </button>
                          ))}
                          {filteredMailboxes.company.length === 0 &&
                            filteredMailboxes.personal.length === 0 && (
                              <p className="text-xs text-muted-foreground py-2">No mailboxes found</p>
                            )}
                        </div>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setShowMailboxPicker(false)}
                      >
                        Cancel
                      </Button>
                    </div>
                  ) : (
                    <div className="mt-1 flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        className="gap-1"
                        onClick={openMailboxPicker}
                      >
                        <Search className="h-3.5 w-3.5" />
                        {effectiveItem.mailboxId
                          ? mailboxes.find((m) => m.id === effectiveItem.mailboxId)?.name ?? "Change"
                          : "Select mailbox"}
                      </Button>
                    </div>
                  )}
                </div>
                <Button
                  className="w-full gap-2"
                  onClick={handleConfirm}
                  disabled={!effectiveItem.mailboxId || confirmingId === item?.id}
                >
                  {confirmingId === item?.id ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Check className="h-4 w-4" />
                  )}
                  Confirm & record
                </Button>
                <div className="flex justify-end pt-2">
                    <Button variant="ghost" size="sm" className="text-destructive hover:text-destructive text-xs h-auto py-1" onClick={handleDelete}>Delete this item</Button>
                </div>
              </div>
            )}

            {effectiveItem?.status === "confirmed" && (
              <div className="rounded-xl border border-green-500/30 bg-green-500/5 p-4">
                <p className="text-sm font-medium text-green-700 dark:text-green-400">Recorded</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Move to next item or go back when done.
                </p>
              </div>
            )}
            </div>
            </div>
          </div>
        )}

        {currentJob && allConfirmed && (
          <div className="rounded-xl border border-green-500/30 bg-green-500/5 p-6 text-center">
            <Check className="h-12 w-12 text-green-600 dark:text-green-400 mx-auto mb-3" />
            <p className="font-medium text-green-700 dark:text-green-400">All items recorded</p>
            <p className="text-sm text-muted-foreground mt-1">Review complete.</p>
            <Button
              className="mt-4 w-full"
              onClick={async () => {
                try {
                  await updateOcrJobStage(currentJob.job.id, "audited");
                  toast({ title: "Job marked as audited" });
                  navigate("/admin/recording");
                  setCurrentJob(null);
                  loadJobs();
                } catch (err) {
                   toast({ title: "Failed to update job stage", variant: "destructive" });
                }
              }}
            >
              Finish Auditing
            </Button>
            <Button
              variant="outline"
              className="mt-2 w-full"
              onClick={() => {
                navigate("/admin/recording");
                setCurrentJob(null);
                loadJobs();
              }}
            >
              Back to queue
            </Button>
          </div>
        )}
      </div>
    </div>
  );
};

export default OcrQueue;
