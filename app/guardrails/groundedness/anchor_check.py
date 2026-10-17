import re

ANCHOR_PATTERNS = {
    "monetary":   re.compile(r"(?:INR|USD|\$|Rs\.?)\s*[\d,]+(?:\.\d+)?"),
    "percentage": re.compile(r"\d+(?:\.\d+)?\s*%"),
    "duration":   re.compile(r"\d+\s*(?:hours?|days?|weeks?|months?|years?)"),
    "date":       re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
}

SPACE_REPLACEMENTS = {
    "\u00a0": " ",   # no-break space
    "\u2007": " ",   # figure space
    "\u2009": " ",   # thin space
    "\u200a": " ",   # hair space
    "\u2002": " ",   # en space
    "\u2003": " ",   # em space
    "\u2004": " ",   # three-per-em space
    "\u2005": " ",   # four-per-em space
    "\u2006": " ",   # six-per-em space
    "\u202f": " ",   # narrow no-break space
    "\u3000": " ",   # ideographic space
}


def _normalize_spaces(text: str) -> str:
    if not text:
        return ""
    for bad, good in SPACE_REPLACEMENTS.items():
        text = text.replace(bad, good)
    return re.sub(r" {2,}", " ", text)


_normalize_text = _normalize_spaces


def extract_anchors(text: str) -> dict:
    """Extract structured anchors (numbers, dates, IDs) from the answer."""
    found = {}
    for anchor_type, pattern in ANCHOR_PATTERNS.items():
        matches = pattern.findall(text)
        if matches:
            found[anchor_type] = matches
    return found


def verify_anchors(anchors: dict, context: str) -> dict:
    """
    Stage 3: check that every anchor in the answer appears in the context.
    Returns {"valid": bool, "unverified": [...], "total": int, "verified": int}
    """
    context = _normalize_text(context)
    unverified = []
    total = 0
    verified = 0

    if isinstance(anchors, dict):
        all_anchors = [v for values in anchors.values() for v in values]
    elif isinstance(anchors, list):
        all_anchors = anchors
    else:
        all_anchors = []

    for anchor_str in all_anchors:
        total += 1
        normalized_anchor = _normalize_text(anchor_str)
        is_verified = False

        if normalized_anchor in context:
            is_verified = True
        elif normalized_anchor.lower() in context.lower():
            is_verified = True
        elif any(c.isdigit() for c in normalized_anchor):
            anchor_nc = normalized_anchor.replace(",", "")
            if anchor_nc in context.replace(",", ""):
                is_verified = True
            elif anchor_nc.lower() in context.replace(",", "").lower():
                is_verified = True

        if is_verified:
            verified += 1
        else:
            unverified.append(anchor_str)

    return {
        "valid": len(unverified) == 0,
        "unverified": unverified,
        "total": total,
        "verified": verified,
    }

