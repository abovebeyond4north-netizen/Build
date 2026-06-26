# Hugging Face External Verification

Hugging Face Jobs can act as an external verification runner for this project.

Current account status observed during setup:

- Authenticated Hugging Face user: `coDEbEYOND`
- Running a Job returned: `402 Payment Required`
- Meaning: the Hugging Face account needs prepaid credits before Jobs can run.

## Intended verification loop

The external runner should perform this sequence:

1. Clone the GitHub repository.
2. Enter `verified-coding-loop-dashboard`.
3. Install dependencies.
4. Run deterministic tests.
5. Build the app.
6. Run the verified improvement gate.
7. Re-run tests.
8. Re-build.
9. Produce a verification report.

## Command to run once Hugging Face Jobs credits are available

Use a Node 22 container and run the dashboard verification commands inside the project folder.

Recommended sequence:

```text
git clone --depth 1 https://github.com/abovebeyond4north-netizen/Build.git
cd Build/verified-coding-loop-dashboard
npm install
npm run verify:full
```

## Safety boundary

The Hugging Face job should only verify the project. It should not auto-merge, deploy, browse the web, or execute unreviewed generated code.

GitHub Actions remains the source of truth for pull requests and human review.
