#!/usr/bin/env python3
"""
AutoIncome Forge GitHub Bounty Worker v2

Safe autonomous bounty claiming and completion for GitHub Issues.

It turns a structured [BOUNTY] issue into a complete local-service workflow package.

It does not send external messages, scrape leads, access accounts, spend money,
or bypass payment/human release gates.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "bounty-outputs"
CATALOG_PATH = ROOT / "data" / "bounty_catalog.json"

REJECT_TERMS = [
    "spam", "scrape", "scraping", "phishing", "credential", "password",
    "malware", "hack", "impersonate", "harass", "fake review", "guaranteed income",
    "bypass", "evade", "steal", "illegal", "stolen", "botnet", "bulk email",
]

REVIEW_TERMS = [
    "cold email", "lead list", "account access", "login", "payment account",
    "legal advice", "tax advice", "medical advice", "financial advice", "investment",
]

BASE_PRICES = {
    "quote intake workflow": 150,
    "booking workflow": 175,
    "follow-up sequence": 125,
    "invoice reminder workflow": 125,
    "lead qualification workflow": 150,
    "sop/checklist": 100,
    "landing page copy": 175,
}

ALLOWED_TYPES = list(BASE_PRICES.keys())


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "bounty"


def extract_field(body: str, label: str) -> str:
    pattern = rf"###\s+{re.escape(label)}\s*\n+(.+?)(?=\n###\s+|\Z)"
    match = re.search(pattern, body, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    value = match.group(1).strip()
    value = re.sub(r"\n+", "\n", value)
    return value.strip()


def scan(text: str) -> tuple[list[str], list[str]]:
    low = text.lower()
    reject = [term for term in REJECT_TERMS if term in low]
    review = [term for term in REVIEW_TERMS if term in low]
    return reject, review


def classify(work_type: str, outcome: str) -> str:
    low = f"{work_type} {outcome}".lower()
    normalized = low.replace("/", " ")
    for allowed in ALLOWED_TYPES:
        if allowed.replace("/", " ") in normalized or allowed in low:
            return allowed
    if "quote" in low or "estimate" in low:
        return "quote intake workflow"
    if "book" in low or "appointment" in low:
        return "booking workflow"
    if "follow" in low:
        return "follow-up sequence"
    if "invoice" in low or "reminder" in low:
        return "invoice reminder workflow"
    if "landing" in low:
        return "landing page copy"
    if "sop" in low or "checklist" in low:
        return "sop/checklist"
    return "lead qualification workflow"


def parse_budget(value: str, work_type: str) -> tuple[int, int, str]:
    nums = re.findall(r"\d+", value or "")
    posted = int(nums[0]) if nums else 0
    suggested = max(posted, BASE_PRICES.get(work_type, 150))
    deposit = round(suggested * 0.5)
    return suggested, deposit, "CAD"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def quality_score(files: dict[str, str]) -> tuple[int, list[str]]:
    text = "\n".join(files.values()).lower()
    score = 100
    issues = []
    required = ["workflow", "template", "checklist", "no spam", "release gates", "human approval"]
    for concept in required:
        if concept not in text:
            score -= 8
            issues.append(f"Missing concept: {concept}")
    if len(text) < 1400:
        score -= 12
        issues.append("Content may be thin")
    if "guaranteed income" not in text:
        score -= 4
        issues.append("Missing guaranteed-income boundary")
    return max(0, score), issues


def build_package(issue_number: int, title: str, body: str) -> dict[str, str]:
    business = extract_field(body, "Business type") or "Local service business"
    work_type_raw = extract_field(body, "Work type") or "Lead qualification workflow"
    outcome = extract_field(body, "Desired outcome") or "Create a practical workflow package."
    budget = extract_field(body, "Budget") or "Not specified"
    deadline = extract_field(body, "Deadline") or "Not specified"
    notes = extract_field(body, "Extra notes") or ""
    work_type = classify(work_type_raw, outcome)
    suggested, deposit, currency = parse_budget(budget, work_type)

    bounty_id = f"GH-{issue_number}"
    package_dir = OUT / bounty_id
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "README.md": f"""# Bounty Package — {title}

**Bounty ID:** {bounty_id}  
**Generated:** {now()}  
**Business type:** {business}  
**Work type:** {work_type}  
**Posted budget:** {budget}  
**Suggested price:** {currency} {suggested}  
**Suggested deposit:** {currency} {deposit}  
**Deadline:** {deadline}

## Desired outcome

{outcome}

## Package contents

- workflow.md
- customer_questions.md
- message_templates.md
- implementation_checklist.md
- release_checklist.md
- invoice_draft.md
- client_status.md
- handoff_email_draft.txt
- delivery_package.json
- quality_review.json
- package_manifest.json

## Safety boundary

No spam, scraping, phishing, account access, fake reviews, illegal work, or guaranteed income claims.

## Release gates

- quality review passed
- payment/deposit confirmation
- human approval before final delivery
- no auto-sending
""",
        "workflow.md": f"""# {work_type.title()} — Workflow

## Goal

Help a {business} business handle this outcome:

{outcome}

## Operating workflow

1. Customer reaches out with a service request.
2. Business sends the intake template.
3. Customer provides missing details.
4. Business reviews the details.
5. Business quotes, books, follows up, or closes the loop.
6. Business records the outcome for weekly improvement.

## Internal tracking

Track these numbers weekly:

- inbound requests
- completed intakes
- quotes sent
- bookings confirmed
- lost leads
- average response time

## Rules

- Use for inbound leads or existing contacts.
- No spam.
- No scraping.
- No impersonation.
- No guaranteed income claims.
""",
        "customer_questions.md": f"""# Customer Questions

Use these questions for a {business} request:

- What is your name?
- What service do you need?
- Where is the job located?
- What date or time works best?
- Do you have photos or extra details?
- Is there anything urgent or unusual?
- Are there access notes, parking notes, stairs, pets, or gate codes?
- What is the best phone number or email for follow-up?

## Keep it simple

Ask only what the business needs to quote, book, or decide the next step.
""",
        "message_templates.md": f"""# Message Templates

## Intake reply

Hi, thanks for reaching out. To help with your {business} request, please send:

- service address or area
- preferred timing
- photos if helpful
- key details about the job
- any access notes

Once I have that, I can give you the next step.

## Follow-up

Hey, just checking in on your request. I can still help if you want to move forward, adjust the scope, or ask a question. No pressure.

## Confirmation

Thanks — I have the details. Next step: {{next_step}}. Please reply YES to confirm or send any changes.

## Close-the-loop reply

Thanks for the update. I will close this request for now. If you need help later, just send a new message and I can reopen it.
""",
        "implementation_checklist.md": f"""# Implementation Checklist

- [ ] Copy the intake reply into SMS, email, CRM, or saved replies.
- [ ] Add the business phone number or booking link.
- [ ] Remove questions that do not matter.
- [ ] Add questions specific to {business}.
- [ ] Test with one fake customer request.
- [ ] Save the final workflow.
- [ ] Track inbound requests weekly.
- [ ] Track booked jobs weekly.
- [ ] Improve after real replies.
""",
        "release_checklist.md": f"""# Release Checklist

Before delivery:

- [ ] Quality review score is 80 or higher.
- [ ] The workflow solves one clear problem.
- [ ] The client can use the files without technical knowledge.
- [ ] Safety language is included.
- [ ] Payment/deposit is confirmed if required.
- [ ] Human approval is recorded.
- [ ] Final files are ready for client delivery.

Do not release automatically. Human approval is required.
""",
        "invoice_draft.md": f"""# Invoice Draft

**Bounty ID:** {bounty_id}  
**Business type:** {business}  
**Work type:** {work_type}  
**Suggested amount:** {currency} {suggested}  
**Suggested deposit:** {currency} {deposit}  
**Status:** requested

## Line item

Safe digital automation workflow package for {business}.

## Note

This is a draft. Confirm payment details manually before release.
""",
        "client_status.md": f"""# Client Status

**Bounty ID:** {bounty_id}  
**Current status:** completed_pending_release_gates

## Completed

- workflow package created
- templates created
- checklist created
- invoice draft created
- release checklist created

## Still required

- payment/deposit confirmation
- human review
- manual delivery approval
""",
        "handoff_email_draft.txt": f"""Subject: Completed bounty package ready for review — {title}

Hey,

The {work_type} package for {business} is complete and ready for review.

Included:
- workflow
- customer questions
- message templates
- implementation checklist
- release checklist
- invoice draft
- delivery summary

Release gates:
- quality review passed
- payment/deposit confirmed if required
- human approval before final client delivery

Bounty ID: {bounty_id}
""",
    }

    score, issues = quality_score(files)
    delivery_package = {
        "bounty_id": bounty_id,
        "generated_at": now(),
        "business_type": business,
        "work_type": work_type,
        "budget_posted": budget,
        "suggested_amount": suggested,
        "suggested_deposit": deposit,
        "currency": currency,
        "deadline": deadline,
        "status": "completed_pending_human_review",
        "quality_score": score,
        "release_gates": {
            "quality_review": score >= 80,
            "payment_confirmation_required": True,
            "human_approval_required": True,
            "auto_send": False,
        },
    }
    files["delivery_package.json"] = json.dumps(delivery_package, indent=2)

    for filename, content in files.items():
        write(package_dir / filename, content)

    review = {
        "bounty_id": bounty_id,
        "quality_score": score,
        "status": "pass" if score >= 80 else "needs_review",
        "issues": issues,
        "generated_at": now(),
    }
    write(package_dir / "quality_review.json", json.dumps(review, indent=2))

    manifest_items = []
    for path in sorted(package_dir.glob("*")):
        if path.is_file():
            manifest_items.append({
                "file": path.name,
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            })
    manifest = {
        "bounty_id": bounty_id,
        "created_at": now(),
        "file_count": len(manifest_items),
        "files": manifest_items,
    }
    write(package_dir / "package_manifest.json", json.dumps(manifest, indent=2))

    zip_base = OUT / bounty_id
    zip_path = shutil.make_archive(str(zip_base), "zip", root_dir=package_dir)

    index = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{bounty_id} Status</title></head>
<body style="font-family:system-ui;max-width:860px;margin:40px auto;line-height:1.6">
<h1>{bounty_id} — Bounty Package</h1>
<p><strong>Status:</strong> completed pending release gates</p>
<p><strong>Business:</strong> {business}</p>
<p><strong>Work type:</strong> {work_type}</p>
<p><strong>Quality score:</strong> {score}</p>
<h2>Release gates</h2>
<ul><li>Payment/deposit confirmation</li><li>Human review</li><li>Manual delivery approval</li></ul>
<p>No auto-sending. No spam. No scraping. No guaranteed income claims.</p>
</body></html>
"""
    write(package_dir / "status.html", index)

    return {
        "bounty_id": bounty_id,
        "business": business,
        "work_type": work_type,
        "budget": budget,
        "suggested_amount": str(suggested),
        "suggested_deposit": str(deposit),
        "currency": currency,
        "deadline": deadline,
        "package_dir": str(package_dir.relative_to(ROOT)),
        "zip_path": str(Path(zip_path).relative_to(ROOT)),
        "quality_score": str(score),
        "review_status": review["status"],
    }


def main() -> int:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        print("GITHUB_EVENT_PATH not set", file=sys.stderr)
        return 1

    event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    issue = event.get("issue", {})
    title = issue.get("title", "Untitled bounty")
    body = issue.get("body", "") or ""
    issue_number = int(issue.get("number", 0))
    text = f"{title}\n{body}"

    reject, review = scan(text)
    OUT.mkdir(exist_ok=True)

    if reject:
        result = {
            "status": "rejected_by_worker",
            "reason": "Safety risk terms found.",
            "flags": reject,
            "human_review_required": True,
        }
        comment = f"""## Bounty blocked by safety scan

Status: `rejected_by_worker`

Flags found: `{', '.join(reject)}`

This request needs human review and was not completed automatically.
"""
    elif review:
        result = {
            "status": "needs_human_review",
            "reason": "Review terms found.",
            "flags": review,
            "human_review_required": True,
        }
        comment = f"""## Bounty needs human review

Status: `needs_human_review`

Review flags: `{', '.join(review)}`

No autonomous completion was performed.
"""
    else:
        package = build_package(issue_number, title, body)
        result = {"status": "claimed_and_completed", **package}
        comment = f"""## Bounty claimed and completed by AutoIncome Forge

Status: `claimed_and_completed`

**Bounty ID:** `{package['bounty_id']}`  
**Business:** {package['business']}  
**Work type:** {package['work_type']}  
**Posted budget:** {package['budget']}  
**Suggested amount:** {package['currency']} {package['suggested_amount']}  
**Suggested deposit:** {package['currency']} {package['suggested_deposit']}  
**Deadline:** {package['deadline']}  
**Quality score:** `{package['quality_score']}`  
**Package path:** `{package['package_dir']}`  
**ZIP path:** `{package['zip_path']}`

Release gates remain active:

- payment/deposit confirmation if required
- human review before final client delivery
- no auto-sending
"""

    write(OUT / "worker_result.json", json.dumps(result, indent=2))
    write(OUT / "issue_comment.md", comment)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
