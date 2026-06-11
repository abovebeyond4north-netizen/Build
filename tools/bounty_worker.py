#!/usr/bin/env python3
"""
AutoIncome Forge GitHub Bounty Worker

Safe autonomous bounty claiming and completion for GitHub Issues.

What it does:
- Reads an issue body from GitHub Actions event payload.
- Scans for unsafe or high-risk terms.
- Claims safe bounties by producing a local deliverable package.
- Writes status markdown for a GitHub issue comment.
- Never sends external messages, scrapes leads, accesses accounts, or spends money.
"""

from __future__ import annotations

import json
import os
import re
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "bounty-outputs"

REJECT_TERMS = [
    "spam", "scrape", "scraping", "phishing", "credential", "password",
    "malware", "hack", "impersonate", "harass", "fake review", "guaranteed income",
    "bypass", "evade", "steal", "illegal", "stolen", "botnet", "bulk email",
]

REVIEW_TERMS = [
    "cold email", "lead list", "account access", "login", "payment account",
    "legal advice", "tax advice", "medical advice", "financial advice", "investment",
]

ALLOWED_TYPES = [
    "quote intake workflow",
    "booking workflow",
    "follow-up sequence",
    "invoice reminder workflow",
    "lead qualification workflow",
    "sop/checklist",
    "landing page copy",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "bounty"


def extract_field(body: str, label: str) -> str:
    # GitHub issue forms render markdown headings like: ### Business type
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
    for allowed in ALLOWED_TYPES:
        if allowed.replace("/", " ") in low or allowed in low:
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


def quality_score(files: dict[str, str]) -> tuple[int, list[str]]:
    text = "\n".join(files.values()).lower()
    score = 100
    issues = []
    for concept in ["workflow", "template", "checklist", "no spam"]:
        if concept not in text:
            score -= 10
            issues.append(f"Missing concept: {concept}")
    if len(text) < 900:
        score -= 15
        issues.append("Content may be thin")
    return max(0, score), issues


def build_package(issue_number: int, title: str, body: str) -> dict[str, str]:
    business = extract_field(body, "Business type") or "Local service business"
    work_type_raw = extract_field(body, "Work type") or "Lead qualification workflow"
    outcome = extract_field(body, "Desired outcome") or "Create a practical workflow package."
    budget = extract_field(body, "Budget") or "Not specified"
    deadline = extract_field(body, "Deadline") or "Not specified"
    notes = extract_field(body, "Extra notes") or ""
    work_type = classify(work_type_raw, outcome)

    bounty_id = f"GH-{issue_number}"
    package_dir = OUT / bounty_id
    package_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "README.md": f"""# Bounty Package — {title}

**Bounty ID:** {bounty_id}  
**Generated:** {now()}  
**Business type:** {business}  
**Work type:** {work_type}  
**Budget:** {budget}  
**Deadline:** {deadline}

## Desired outcome

{outcome}

## Extra notes

{notes or 'None provided.'}

## Package contents

- workflow.md
- customer_questions.md
- message_templates.md
- implementation_checklist.md
- handoff_email_draft.txt
- delivery_package.json

## Safety boundary

No spam, scraping, phishing, account access, fake reviews, illegal work, or guaranteed-income claims.
""",
        "workflow.md": f"""# {work_type.title()} — Workflow

## Goal

Help a {business} business handle this outcome:

{outcome}

## Workflow

1. Customer reaches out with a service request.
2. Business sends the intake template.
3. Customer provides missing details.
4. Business reviews the details.
5. Business quotes, books, follows up, or closes the loop.
6. Business records outcome for weekly improvement.

## Rules

- Use this for inbound leads or existing contacts.
- No spam.
- No scraping.
- No impersonation.
- No guaranteed-income claims.
""",
        "customer_questions.md": f"""# Customer Questions

Use these questions for a {business} request:

- What is your name?
- What service do you need?
- Where is the job located?
- What date or time works best?
- Do you have photos or extra details?
- Is there anything urgent or unusual?
- What is the best phone number or email for follow-up?
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
""",
        "implementation_checklist.md": f"""# Implementation Checklist

- [ ] Copy the intake reply into SMS/email/CRM.
- [ ] Add the business phone number or booking link.
- [ ] Test with one fake customer request.
- [ ] Remove unnecessary questions.
- [ ] Save the final workflow.
- [ ] Track inbound requests weekly.
- [ ] Track booked jobs weekly.
- [ ] Improve after real replies.
""",
        "handoff_email_draft.txt": f"""Subject: Completed bounty package ready for review — {title}

Hey,

The {work_type} package for {business} is complete and ready for review.

Included:
- workflow
- customer questions
- message templates
- implementation checklist
- delivery summary

Release gates:
- quality review passed
- payment/deposit confirmed if required
- human approval before final client delivery

Bounty ID: {bounty_id}
""",
        "delivery_package.json": json.dumps({
            "bounty_id": bounty_id,
            "generated_at": now(),
            "business_type": business,
            "work_type": work_type,
            "budget": budget,
            "deadline": deadline,
            "status": "completed_pending_human_review",
            "release_gates": {
                "quality_review": True,
                "payment_confirmation_required": True,
                "human_approval_required": True,
                "auto_send": False,
            },
        }, indent=2),
    }

    for filename, content in files.items():
        (package_dir / filename).write_text(content, encoding="utf-8")

    score, issues = quality_score(files)
    review = {
        "bounty_id": bounty_id,
        "quality_score": score,
        "status": "pass" if score >= 80 else "needs_review",
        "issues": issues,
        "generated_at": now(),
    }
    (package_dir / "quality_review.json").write_text(json.dumps(review, indent=2), encoding="utf-8")

    return {
        "bounty_id": bounty_id,
        "business": business,
        "work_type": work_type,
        "budget": budget,
        "deadline": deadline,
        "package_dir": str(package_dir.relative_to(ROOT)),
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
**Budget:** {package['budget']}  
**Deadline:** {package['deadline']}  
**Quality score:** `{package['quality_score']}`  
**Package path:** `{package['package_dir']}`

Release gates remain active:

- payment/deposit confirmation if required
- human review before final client delivery
- no auto-sending
"""

    (OUT / "worker_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (OUT / "issue_comment.md").write_text(comment, encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
