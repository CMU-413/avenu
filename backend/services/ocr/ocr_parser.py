"""Parse raw OCR text into receiver and sender fields. Mirrors frontend parseOcrText logic."""

from __future__ import annotations

import re

SKIP_PATTERNS = re.compile(
    r"(?:priority\s*mail|tracking\s*#|weight\s*:|usps|ups|fedex|"
    r"\d+\s*lbs?|\d+\s*oz|postage\s*req|firmly\s*to\s*seal|united\s*states)",
    re.I,
)
SHIP_TO_PATTERN = re.compile(
    r"(?:ship\s*to|deliver\s*to|recipient|\bto)\s*:\s*",
    re.I,
)
FROM_PATTERN = re.compile(
    r"(?:f\s*:?\s*o\s*:?\s*m|from|fe[il1]om|sender|return)\s*:\s*",
    re.I,
)
ADDRESS_LINE = re.compile(
    r"\b[A-Z]{2}\s+\d{5}\b|\b\d{5}[\s-]+\d{4}\b|\b\d{5}\b.*\b[A-Z]{2}\b",
    re.I,
)


def _strip_leading_noise(line: str) -> str:
    return re.sub(r"^[^a-zA-Z]*", "", line).strip()


def _clean_address_text(s: str) -> str:
    s = re.sub(r"([a-z])(Ave\.?)", r"\1 \2", s, flags=re.I)
    s = re.sub(r"([a-z])(Blvd\.?)", r"\1 \2", s, flags=re.I)
    s = re.sub(r"([a-z])(St\.?|Street)", r"\1 \2", s, flags=re.I)
    s = re.sub(r"([a-z])(Dr\.?|Drive)", r"\1 \2", s, flags=re.I)
    s = re.sub(r"([a-z])(Rd\.?|Road)", r"\1 \2", s, flags=re.I)
    s = re.sub(r"(Blvd\.?|Ave\.?|St\.?)([A-Za-z])", r"\1 \2", s, flags=re.I)
    s = re.sub(r",([A-Za-z])", r", \1", s)
    s = re.sub(r"([a-z])(North|South|East|West)\b", r"\1 \2", s, flags=re.I)
    return s


def parse_ocr_text(raw: str) -> tuple[str, str]:
    """Split raw OCR text into (receiver, sender). Returns (receiver, sender) strings."""
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    receiver: list[str] = []
    sender: list[str] = []
    current_target: str | None = None
    used_labels = False

    for raw_line in lines:
        line = _strip_leading_noise(raw_line)

        if SKIP_PATTERNS.search(line):
            current_target = None
            continue

        ship_match = SHIP_TO_PATTERN.search(line)
        if ship_match:
            current_target = "receiver"
            used_labels = True
            before = line[: ship_match.start()].strip()
            rest = line[ship_match.end() :].strip()
            if before:
                receiver.append(before)
            if rest:
                receiver.append(rest)
            continue

        from_match = FROM_PATTERN.search(line)
        if from_match:
            current_target = "sender"
            used_labels = True
            before = line[: from_match.start()].strip()
            rest = line[from_match.end() :].strip()
            if before:
                sender.append(before)
            if rest:
                sender.append(rest)
            continue

        if current_target == "receiver":
            receiver.append(line)
        elif current_target == "sender":
            sender.append(line)

    if used_labels:
        return (
            _clean_address_text("\n".join(receiver).strip()),
            _clean_address_text("\n".join(sender).strip()),
        )

    filtered = [_strip_leading_noise(l) for l in lines if not SKIP_PATTERNS.search(_strip_leading_noise(l))]
    blocks: list[list[str]] = []
    current: list[str] = []

    for line in filtered:
        current.append(line)
        if ADDRESS_LINE.search(line):
            blocks.append(current)
            current = []
    if current:
        if blocks:
            blocks[-1].extend(current)
        else:
            blocks.append(current)

    if len(blocks) >= 2:
        return (
            _clean_address_text("\n".join(b for block in blocks[1:] for b in block).strip()),
            _clean_address_text("\n".join(blocks[0]).strip()),
        )

    return (_clean_address_text(raw.strip()), "")
