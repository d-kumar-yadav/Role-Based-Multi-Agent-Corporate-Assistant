"""
Migrate existing PDF policy documents to Markdown with YAML frontmatter.

Usage:
    python scripts/migrate_pdfs.py --step extract
    python scripts/migrate_pdfs.py --step convert
    python scripts/migrate_pdfs.py --step convert --use-llm
"""

import os
import re
import sys
import argparse
from pathlib import Path
from datetime import date, timedelta

import pdfplumber
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

SOURCE_DIR = Path("app/rag/documents")
EXTRACTED_DIR = Path("data/_extracted")
OUTPUT_DIR = Path("data/policies")

# Mapping: PDF filename -> target metadata
MIGRATION_MAP = {
    "crossdomain_01_it_finance_Remote_Equipment_Policy.pdf": {
        "doc_id": "CROSS-EQUIP-001",
        "title": "Remote Equipment Policy",
        "department": "crossdomain",
        "access_level": "internal",
        "roles": ["employee", "manager", "it", "finance"],
        "owner": "IT Infrastructure Team & Finance Team",
    },
    "finance_01_Policies_and_Memos.pdf": {
        "doc_id": "FIN-POLICY-001",
        "title": "Finance Policies and Expense Memos",
        "department": "finance",
        "access_level": "internal",
        "roles": ["employee", "manager", "finance"],
        "owner": "Finance & Accounts Team",
    },
    "finance_02_Quarterly_Budget_Report.pdf": {
        "doc_id": "FIN-BUDGET-001",
        "title": "Quarterly Budget Report Q3 FY2025-26",
        "department": "finance",
        "access_level": "finance_only",
        "roles": ["finance", "executive"],
        "owner": "FP&A Team",
    },
    "finance_03_Vendor_and_Procurement_Policy.pdf": {
        "doc_id": "FIN-VENDOR-001",
        "title": "Vendor and Procurement Policy",
        "department": "finance",
        "access_level": "internal",
        "roles": ["employee", "manager", "finance"],
        "owner": "Procurement Team",
    },
    "hr_02_Recruitment_and_Hiring_Policy.pdf": {
        "doc_id": "HR-RECRUIT-001",
        "title": "Recruitment and Hiring Policy",
        "department": "hr",
        "access_level": "internal",
        "roles": ["manager", "hr"],
        "owner": "Talent Acquisition Team",
    },
    "hr_04_Recruitment_Process_and_Hiring_Funnel.pdf": {
        "doc_id": "HR-FUNNEL-001",
        "title": "Recruitment Process and Hiring Funnel",
        "department": "hr",
        "access_level": "internal",
        "roles": ["manager", "hr"],
        "owner": "Talent Acquisition Team",
    },
    "hr_05_Performance_and_Compensation_Bands.pdf": {
        "doc_id": "HR-COMP-001",
        "title": "Performance and Compensation Bands",
        "department": "hr",
        "access_level": "hr_only",
        "roles": ["hr", "executive"],
        "owner": "People & Culture Team",
    },
    "it_01_Runbooks_and_Support.pdf": {
        "doc_id": "IT-RUNBOOK-001",
        "title": "IT Runbooks and Support Procedures",
        "department": "it",
        "access_level": "it_only",
        "roles": ["it"],
        "owner": "IT Infrastructure Team",
    },
    "it_02_Acceptable_Use_and_Security.pdf": {
        "doc_id": "IT-SEC-001",
        "title": "Acceptable Use and Security Rules",
        "department": "it",
        "access_level": "internal",
        "roles": ["employee", "manager", "it"],
        "owner": "IT Security Team",
    },
    "it_03_Software_and_Asset_Catalog.pdf": {
        "doc_id": "IT-ASSET-001",
        "title": "Software and Asset Catalog",
        "department": "it",
        "access_level": "internal",
        "roles": ["employee", "manager", "it"],
        "owner": "IT Infrastructure Team",
    },
    "it_04_Helpdesk_and_Team_Structure.pdf": {
        "doc_id": "IT-TEAM-001",
        "title": "IT Helpdesk and Team Structure",
        "department": "it",
        "access_level": "it_only",
        "roles": ["it"],
        "owner": "IT Infrastructure Team",
    },
    "public_01_Company_Rules_and_Code_of_Conduct.pdf": {
        "doc_id": "PUB-CONDUCT-001",
        "title": "Company Rules and Code of Conduct",
        "department": "public",
        "access_level": "public",
        "roles": ["employee", "manager", "hr", "finance", "it"],
        "owner": "Legal & Compliance Team",
    },
    "public_02_Company_Overview_and_Org_Structure.pdf": {
        "doc_id": "PUB-ORG-001",
        "title": "Company Overview and Org Structure",
        "department": "public",
        "access_level": "public",
        "roles": ["employee", "manager", "hr", "finance", "it"],
        "owner": "Corporate Communications",
    },
    "public_03_Employee_Handbook.pdf": {
        "doc_id": "PUB-HANDBOOK-001",
        "title": "HR Employee Handbook",
        "department": "public",
        "access_level": "internal",
        "roles": ["employee", "manager", "hr"],
        "owner": "People & Culture Team",
    },
    "public_04_Leave_and_Attendance_Policy.pdf": {
        "doc_id": "PUB-LEAVE-001",
        "title": "Leave and Attendance Policy",
        "department": "public",
        "access_level": "internal",
        "roles": ["employee", "manager", "hr"],
        "owner": "People & Culture Team",
    },
    "public_05_Org_Hierarchy_and_Reporting_Structure.pdf": {
        "doc_id": "PUB-HIERARCHY-001",
        "title": "Org Hierarchy and Reporting Structure",
        "department": "public",
        "access_level": "public",
        "roles": ["employee", "manager", "hr", "finance", "it"],
        "owner": "Corporate Communications",
    },
    "public_06_New_Employee_Onboarding_Checklist.pdf": {
        "doc_id": "PUB-ONBOARD-001",
        "title": "New Employee Onboarding Checklist",
        "department": "public",
        "access_level": "internal",
        "roles": ["employee", "manager", "hr"],
        "owner": "HR Operations",
    },
}

# ---------------------------------------------------------------------------
# STEP 1: EXTRACTION
# ---------------------------------------------------------------------------


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract text page by page from a PDF."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            pages.append(f"===== Page {i} =====\n\n{text}")
    return "\n\n".join(pages)


def clean_extracted_text(text: str) -> str:
    """Remove common PDF extraction artifacts."""
    # Remove page markers
    text = re.sub(r"=====\s*Page\s+\d+\s*=====", "", text)

    # Remove headers/footers that repeat
    lines = text.split("\n")
    seen = {}
    for line in lines:
        stripped = line.strip()
        if 10 < len(stripped) < 80:
            seen[stripped] = seen.get(stripped, 0) + 1

    # Drop any line that repeats more than 3 times (likely header/footer)
    repeats = {line for line, count in seen.items() if count > 3}
    lines = [l for l in lines if l.strip() not in repeats]

    # Remove phantom numbered lists (1. 2. 3. 4. ...)
    text = "\n".join(lines)
    text = re.sub(r"(\d+\.\s+){10,}", "", text)

    # Remove repeated identical rows (L139 L139 L139...)
    text = re.sub(r"(\b\w+\b)(\s+\1){5,}", r"\1", text)

    # Fix hyphenation
    text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)

    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def step_extract():
    """Extract all PDFs to text files."""
    if not SOURCE_DIR.exists():
        print(f"ERROR: {SOURCE_DIR} not found.")
        print("Adjust SOURCE_DIR at the top of this script.")
        sys.exit(1)

    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)

    pdfs = list(SOURCE_DIR.rglob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {SOURCE_DIR}")
        sys.exit(1)

    print(f"Found {len(pdfs)} PDFs to extract.\n")

    for pdf_path in sorted(pdfs):
        name = pdf_path.name
        if name not in MIGRATION_MAP:
            print(f"  SKIP (not in migration map): {name}")
            continue

        try:
            raw = extract_pdf_text(pdf_path)
            cleaned = clean_extracted_text(raw)
            out_path = EXTRACTED_DIR / f"{pdf_path.stem}.txt"
            out_path.write_text(cleaned, encoding="utf-8")
            print(f"  OK  {name} -> {out_path}  ({len(cleaned)} chars)")
        except Exception as e:
            print(f"  FAIL {name}: {e}")

    print(f"\nDone. Extracted files are in {EXTRACTED_DIR}")
    print("Review each .txt file for leftover artifacts, then run --step convert")


# ---------------------------------------------------------------------------
# STEP 2: CONVERSION (no LLM — basic structural cleanup)
# ---------------------------------------------------------------------------


def build_frontmatter(meta: dict) -> str:
    """Build YAML frontmatter string from metadata dict."""
    today = date.today()
    review = today + timedelta(days=180)

    roles_str = ", ".join(meta["roles"])
    lines = [
        "---",
        f"doc_id: {meta['doc_id']}",
        f'title: "{meta["title"]}"',
        f"department: {meta['department']}",
        f'owner: "{meta["owner"]}"',
        f"access_level: {meta['access_level']}",
        f"roles: [{roles_str}]",
        f'version: "1.0"',
        f"effective_date: {today.isoformat()}",
        f"review_date: {review.isoformat()}",
        f"systems: []",
        f"tags: []",
        f"related_docs: []",
        f'classification: "Internal — {meta["department"].title()}"',
        "---",
    ]
    return "\n".join(lines)


def basic_structure_cleanup(text: str, meta: dict) -> str:
    """Convert raw text to Markdown with basic structure."""
    lines = text.split("\n")
    out_lines = []
    seen_section = set()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            out_lines.append("")
            continue

        # Detect headings: numbered sections like "1. Purpose"
        m = re.match(r"^(\d+)\.\s+([A-Z][A-Za-z\s&/,\-]+)$", stripped)
        if m and len(m.group(2)) < 80:
            heading = f"## {m.group(2).strip()}"
            if heading not in seen_section:
                seen_section.add(heading)
                out_lines.append("")
                out_lines.append(heading)
                out_lines.append("")
                continue

        # Detect ALL CAPS headings
        if stripped.isupper() and 5 < len(stripped) < 80:
            out_lines.append("")
            out_lines.append(f"## {stripped.title()}")
            out_lines.append("")
            continue

        out_lines.append(stripped)

    body = "\n".join(out_lines)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()


def step_convert_basic():
    """Convert extracted text to Markdown with frontmatter (no LLM)."""
    extracted_files = list(EXTRACTED_DIR.glob("*.txt"))
    if not extracted_files:
        print(f"No extracted files in {EXTRACTED_DIR}. Run --step extract first.")
        sys.exit(1)

    print(f"Converting {len(extracted_files)} files (basic mode).\n")

    for txt_path in sorted(extracted_files):
        stem = txt_path.stem
        pdf_name = next((n for n in MIGRATION_MAP if n.startswith(stem)), None)
        if not pdf_name:
            print(f"  SKIP (no mapping): {txt_path.name}")
            continue

        meta = MIGRATION_MAP[pdf_name]
        body = txt_path.read_text(encoding="utf-8")
        structured = basic_structure_cleanup(body, meta)
        fm = build_frontmatter(meta)

        out_dir = OUTPUT_DIR / meta["department"]
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{meta['doc_id']}.md"
        out_path.write_text(f"{fm}\n\n{structured}\n", encoding="utf-8")
        print(f"  OK  {txt_path.name} -> {out_path}")

    print(f"\nDone. Files written to {OUTPUT_DIR}")
    print("Review each .md file. For better quality, run with --use-llm")


# ---------------------------------------------------------------------------
# STEP 2b: CONVERSION (LLM-assisted — much better quality)
# ---------------------------------------------------------------------------

CONVERT_PROMPT = """You are converting an enterprise policy document's extracted 
text into clean Markdown with YAML frontmatter.

METADATA (use exactly as given, do not invent):
- doc_id: {doc_id}
- title: {title}
- department: {department}
- access_level: {access_level}
- roles: {roles}
- owner: {owner}

INSTRUCTIONS:

1. Start with YAML frontmatter using the metadata above. Add:
   version: "1.0"
   effective_date: {today}
   review_date: {review_date}
   systems: [extract systems mentioned like Okta, Jira, Slack — or leave empty]
   tags: [extract 3-5 keyword tags]
   related_docs: [extract doc_id references, e.g. HR-RECRUIT-001 — or leave empty]
   classification: "Internal — {department_title}"

2. Clean the text:
   - Remove duplicate lines, page numbers, leftover artifacts
   - Remove sequences like "1. 2. 3. 4. ..." or "L139 L139 L139"
   - Fix broken hyphenation
   - Remove any header/footer text

3. Structure the content:
   - Use ## for top-level sections (Purpose, Scope, Policy Statement, etc.)
   - Use ### for subsections
   - Convert any tables to proper Markdown tables
   - Preserve ALL substantive content — do NOT summarize or omit anything

4. Convert cross-references:
   - "see Section X of the Recruitment Policy" -> "see HR-RECRUIT-001, Section X"
   - Replace document names with their doc_ids

5. Add at the bottom if missing:
   ## Revision History
   (table with one row: "1.0 | {today} | {owner} | Initial version")
   
   ## Document Control
   (table: Owner, Approver, Distribution, Review Cycle)

6. Do NOT add AI filler: "In today's fast-paced world", "It is important to note", 
   "Navigating the complexities of", "In the realm of". Use plain corporate English.

7. Do NOT use emojis. Do NOT use em-dashes excessively.

OUTPUT: Return ONLY the Markdown document. Start with the --- of the frontmatter.
No preamble, no explanation.

EXTRACTED TEXT:
{text}
"""


def convert_with_llm(text: str, meta: dict) -> str:
    from groq import Groq

    client = Groq(api_key=os.environ["GROQ_API_KEY"])

    today = date.today()
    review = today + timedelta(days=180)

    prompt = CONVERT_PROMPT.format(
        doc_id=meta["doc_id"],
        title=meta["title"],
        department=meta["department"],
        access_level=meta["access_level"],
        roles=", ".join(meta["roles"]),
        owner=meta["owner"],
        today=today.isoformat(),
        review_date=review.isoformat(),
        department_title=meta["department"].title(),
        text=text[:50000],
    )

    resp = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=8000,
    )
    return resp.choices[0].message.content.strip()


def step_convert_llm():
    """Convert extracted text using Groq for high-quality Markdown."""
    if not os.environ.get("GROQ_API_KEY"):
        print("ERROR: GROQ_API_KEY not set in .env")
        sys.exit(1)

    extracted_files = list(EXTRACTED_DIR.glob("*.txt"))
    if not extracted_files:
        print(f"No extracted files in {EXTRACTED_DIR}. Run --step extract first.")
        sys.exit(1)

    print(f"Converting {len(extracted_files)} files via Groq (LLM mode).\n")
    print("This will take ~30 seconds per document.\n")

    for txt_path in sorted(extracted_files):
        stem = txt_path.stem
        pdf_name = next((n for n in MIGRATION_MAP if n.startswith(stem)), None)
        if not pdf_name:
            print(f"  SKIP (no mapping): {txt_path.name}")
            continue

        meta = MIGRATION_MAP[pdf_name]
        body = txt_path.read_text(encoding="utf-8")

        try:
            md = convert_with_llm(body, meta)
            out_dir = OUTPUT_DIR / meta["department"]
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{meta['doc_id']}.md"
            out_path.write_text(md + "\n", encoding="utf-8")
            print(f"  OK  {txt_path.name} -> {out_path}  ({len(md)} chars)")
        except Exception as e:
            print(f"  FAIL {txt_path.name}: {e}")

    print(f"\nDone. Files written to {OUTPUT_DIR}")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", choices=["extract", "convert"], required=True)
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Use Groq for high-quality conversion (convert step only)",
    )
    args = parser.parse_args()

    if args.step == "extract":
        step_extract()
    elif args.step == "convert":
        if args.use_llm:
            step_convert_llm()
        else:
            step_convert_basic()


if __name__ == "__main__":
    main()