# Autonomous Bounty Claims and Completions

This repo now includes a safe GitHub-native bounty worker.

## How to create a bounty

1. Go to Issues.
2. Choose **Automation Bounty**.
3. Fill in:
   - business type
   - work type
   - desired outcome
   - budget
   - deadline
4. Submit the issue.

The issue title must include:

```text
[BOUNTY]
```

## What happens automatically

When a bounty issue is opened or edited, GitHub Actions runs:

```text
tools/bounty_worker.py
```

The worker:

1. Reads the issue body.
2. Scans for unsafe or high-risk terms.
3. Blocks unsafe requests.
4. Escalates risky requests for human review.
5. Claims safe requests.
6. Generates deliverables into:

```text
bounty-outputs/GH-<issue-number>/
```

7. Commits the output package.
8. Comments on the issue with status.
9. Applies labels.

## Generated deliverables

Safe completed bounties receive:

```text
README.md
workflow.md
customer_questions.md
message_templates.md
implementation_checklist.md
handoff_email_draft.txt
delivery_package.json
quality_review.json
```

## Release gates

Even when a bounty is completed, final release still requires:

- human review
- payment/deposit confirmation if required
- manual delivery approval

The worker does not auto-send messages or files.

## Safety blocks

The worker blocks or escalates terms related to:

- spam
- scraping
- phishing
- account access
- malware
- hacking
- impersonation
- fake reviews
- illegal work
- guaranteed income claims

## Labels

The workflow may apply:

```text
bounty:claimed
bounty:completed
needs-human-release
bounty:needs-human-review
bounty:blocked
```
