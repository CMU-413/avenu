/** Normalize text for fuzzy mailbox / receiver matching. */
export function normalizeForMailboxMatch(s: string): string {
  return s
    .toLowerCase()
    .normalize("NFKD")
    .replace(/\p{M}/gu, "")
    .replace(/[^\w\s']/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function levenshtein(a: string, b: string): number {
  if (a.length === 0) return b.length;
  if (b.length === 0) return a.length;
  let prev = new Array<number>(b.length + 1);
  let cur = new Array<number>(b.length + 1);
  for (let j = 0; j <= b.length; j++) prev[j] = j;
  for (let i = 1; i <= a.length; i++) {
    cur[0] = i;
    for (let j = 1; j <= b.length; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost);
    }
    [prev, cur] = [cur, prev];
  }
  return prev[b.length];
}

function similarity(a: string, b: string): number {
  if (!a.length || !b.length) return 0;
  const dist = levenshtein(a, b);
  return 1 - dist / Math.max(a.length, b.length);
}

/** True if every word (len ≥ 2) in `shorter` appears as substring in `longer`. */
function allWordsContained(shorter: string, longer: string): boolean {
  const words = shorter.split(" ").filter((w) => w.length >= 2);
  if (words.length === 0) return false;
  return words.every((w) => longer.includes(w));
}

/**
 * Score how well `query` matches `candidate` after normalization.
 * Returns 0–1; only high scores should trigger auto-select.
 */
export function scoreReceiverToLabel(queryNorm: string, candidateNorm: string): number {
  if (!queryNorm || !candidateNorm) return 0;
  if (queryNorm === candidateNorm) return 1;
  if (queryNorm.length >= 4 && candidateNorm.length >= 4) {
    if (queryNorm.includes(candidateNorm) || candidateNorm.includes(queryNorm)) {
      const shorter = Math.min(queryNorm.length, candidateNorm.length);
      const longer = Math.max(queryNorm.length, candidateNorm.length);
      return 0.92 + 0.06 * (shorter / longer);
    }
  }
  const shorter = queryNorm.length <= candidateNorm.length ? queryNorm : candidateNorm;
  const longer = queryNorm.length <= candidateNorm.length ? candidateNorm : queryNorm;
  if (shorter.length >= 5 && allWordsContained(shorter, longer)) {
    return 0.9;
  }
  return similarity(queryNorm, candidateNorm);
}

const MIN_QUERY_LEN = 3;
const MIN_SCORE = 0.88;
const MIN_SCORE_GAP = 0.03;

export type MailboxForMatch = {
  id: string;
  name: string;
  memberNames: string[];
};

/**
 * If the receiver string matches one mailbox name or member very closely (and unambiguously), return its id.
 */
export function findCloseMailboxMatch(
  receiverName: string | null | undefined,
  mailboxes: MailboxForMatch[]
): { id: string; score: number } | null {
  const firstLine = receiverName?.split("\n")[0]?.trim() ?? "";
  const queryNorm = normalizeForMailboxMatch(firstLine);
  if (queryNorm.length < MIN_QUERY_LEN) return null;

  const perMailbox: { id: string; score: number }[] = [];
  for (const mb of mailboxes) {
    const labels = [mb.name, ...mb.memberNames].filter((s) => s?.trim());
    let best = 0;
    for (const label of labels) {
      const candNorm = normalizeForMailboxMatch(label);
      if (!candNorm.length) continue;
      best = Math.max(best, scoreReceiverToLabel(queryNorm, candNorm));
    }
    if (best >= MIN_SCORE) {
      perMailbox.push({ id: mb.id, score: best });
    }
  }

  if (perMailbox.length === 0) return null;
  perMailbox.sort((a, b) => b.score - a.score);
  const top = perMailbox[0]!;
  const second = perMailbox[1];
  if (second && top.score - second.score < MIN_SCORE_GAP) {
    return null;
  }
  return top;
}
