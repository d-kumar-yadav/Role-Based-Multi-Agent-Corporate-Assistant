"""
fix_docs.py — Apply corrections to migrated policy markdown files in place.

Fixes:
  1. roles: a, b, c   ->  roles: [a, b, c]
  2. classification casing and value for public/internal files
  3. related_docs: [] -> populated with cross-references
  4. Known broken tables (PUB-ORG-001, PUB-HIERARCHY-001, PUB-HANDBOOK-001)

Run from project root:
    python scripts/fix_docs.py
"""

import re
from pathlib import Path

POLICY_DIR = Path("data/policies")

RELATED_DOCS = {
    "HR-RECRUIT-001.md":     "[HR-FUNNEL-001, PUB-HANDBOOK-001, FIN-VENDOR-001]",
    "HR-FUNNEL-001.md":      "[HR-RECRUIT-001, PUB-ONBOARD-001, PUB-HIERARCHY-001]",
    "HR-COMP-001.md":        "[PUB-HANDBOOK-001, PUB-HIERARCHY-001]",
    "IT-RUNBOOK-001.md":     "[IT-SEC-001, IT-TEAM-001, IT-ASSET-001]",
    "IT-SEC-001.md":         "[IT-RUNBOOK-001, IT-ASSET-001, PUB-ONBOARD-001]",
    "IT-ASSET-001.md":       "[IT-RUNBOOK-001, IT-SEC-001, CROSS-EQUIP-001]",
    "IT-TEAM-001.md":        "[IT-RUNBOOK-001, IT-SEC-001, IT-ASSET-001]",
    "PUB-CONDUCT-001.md":    "[PUB-HANDBOOK-001, PUB-ORG-001]",
    "PUB-ORG-001.md":        "[PUB-HIERARCHY-001, PUB-CONDUCT-001]",
    "PUB-HANDBOOK-001.md":   "[PUB-LEAVE-001, PUB-CONDUCT-001, HR-COMP-001]",
    "PUB-LEAVE-001.md":      "[PUB-HANDBOOK-001, HR-COMP-001, PUB-CONDUCT-001]",
    "PUB-HIERARCHY-001.md":  "[PUB-ORG-001, PUB-HANDBOOK-001, HR-COMP-001]",
    "PUB-ONBOARD-001.md":    "[HR-FUNNEL-001, HR-RECRUIT-001, PUB-HANDBOOK-001, PUB-CONDUCT-001, IT-RUNBOOK-001, IT-ASSET-001]",
    "FIN-POLICY-001.md":     "[FIN-BUDGET-001, FIN-VENDOR-001, CROSS-EQUIP-001]",
    "FIN-BUDGET-001.md":     "[FIN-POLICY-001, FIN-VENDOR-001]",
    "FIN-VENDOR-001.md":     "[FIN-POLICY-001, IT-SEC-001, HR-RECRUIT-001]",
    "CROSS-EQUIP-001.md":    "[IT-ASSET-001, FIN-POLICY-001, PUB-LEAVE-001]",
}

CLASSIFICATION_FIXES = {
    '"Internal — Hr"':           '"Internal — HR"',
    '"Internal — It"':           '"Internal — IT"',
    '"Internal — Public"':       '"Public (within organization)"',
    '"Internal — Crossdomain"':  '"Internal — Cross-Functional (IT + Finance)"',
}

BROKEN_TABLES = {
    "PUB-ORG-001.md": [
        (
            r"\| Function \| Head \| Core Responsibility \|\n\|[-\s|]+\|\n"
            r"(\|[^\n]*\|\n)*?\| Legal & Compliance \| General Counsel \| Contracts, regulatory, ethics \|",
            """| Function | Head | Core Responsibility |
|---|---|---|
| Engineering | CTO | Product development, infrastructure, security |
| Sales & Marketing | Chief Revenue Officer | New business, renewals, brand |
| Customer Success | VP Customer Success | Onboarding, retention, support |
| People & Culture (HR) | Head of HR | Talent, culture, employee experience |
| Finance & Admin | CFO | Financial planning, accounting, facilities |
| Legal & Compliance | General Counsel | Contracts, regulatory, ethics |""",
        ),
    ],
    "PUB-HIERARCHY-001.md": [
        (
            r"\| Workflow \| Starts With \| Handoff To \| Ends With \|[\s\S]*?\| New software request \|[^\n]+\|",
            """| Workflow | Starts With | Handoff To | Ends With |
|---|---|---|---|
| New hire | HR (Talent Acquisition) | IT (asset provisioning), Facilities | HR (Onboarding complete) |
| Employee exit | HR (resignation processed) | IT (access revocation), Finance (final settlement) | HR (exit interview closed) |
| Expense reimbursement | Employee (any dept.) | Manager (approval) | Finance (payment) |
| New software request | Employee (any dept.) | IT (security review) | Procurement (if paid license) |""",
        ),
    ],
    "PUB-HANDBOOK-001.md": [
        (
            r"\| Category\s*\|[^\n]*\n\|[-\s|]+\|\n(\|[^\n]*\n){2,}",
            """| Category | Description | Benefits Eligibility |
|---|---|---|
| Full-time permanent | Regular, indefinite employment | Full benefits |
| Fixed-term contract | Employment for a defined period (6-24 months) | Pro-rated benefits |
| Intern | Structured training placement, 3-6 months | Stipend only |
| Consultant | Engaged via separate service agreement | Not applicable |""",
        ),
        (
            r"\| Step\s*\| Action\s*\| Documentation\s*\|[\s\S]*?\| 4th occurrence \|[^\n]+\|",
            """| Step | Action | Documentation |
|---|---|---|
| 1st occurrence | Verbal warning | Noted in HR file |
| 2nd occurrence | Written warning | Signed acknowledgment required |
| 3rd occurrence | Final written warning | HR Business Partner involved |
| 4th occurrence | Termination review | Formal hearing, HR + Legal |""",
        ),
    ],
}


def fix_roles(content: str) -> str:
    def repl(m):
        return f"roles: [{m.group(1).strip()}]"
    return re.sub(r"roles:\s+([a-z][a-z,\s]+?)(?=\n)", repl, content)


def fix_classification(content: str) -> str:
    for old, new in CLASSIFICATION_FIXES.items():
        content = content.replace(old, new)
    return content


def fix_related_docs(content: str, filename: str) -> str:
    if filename in RELATED_DOCS:
        content = re.sub(
            r"related_docs:\s*\[\]",
            f"related_docs: {RELATED_DOCS[filename]}",
            content,
        )
    return content


def fix_tables(content: str, filename: str) -> str:
    if filename not in BROKEN_TABLES:
        return content
    for pattern, replacement in BROKEN_TABLES[filename]:
        new_content = re.sub(pattern, replacement, content)
        if new_content == content:
            print(f"  WARNING: table pattern did not match in {filename}")
        content = new_content
    return content


def process_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    content = original
    content = fix_roles(content)
    content = fix_classification(content)
    content = fix_related_docs(content, path.name)
    content = fix_tables(content, path.name)

    if content != original:
        path.write_text(content, encoding="utf-8")
        return True
    return False


def main():
    if not POLICY_DIR.exists():
        print(f"ERROR: {POLICY_DIR} not found. Run from project root.")
        return
    files = sorted(POLICY_DIR.rglob("*.md"))
    if not files:
        print("No .md files found.")
        return

    print(f"Processing {len(files)} files...\n")
    fixed = 0
    for f in files:
        changed = process_file(f)
        marker = "FIXED" if changed else "ok   "
        print(f"  {marker}  {f.relative_to(POLICY_DIR.parent)}")
        if changed:
            fixed += 1

    print(f"\nDone. {fixed} of {len(files)} files updated.")


if __name__ == "__main__":
    main()