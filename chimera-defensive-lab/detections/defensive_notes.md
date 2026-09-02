# Defensive Notes

These notes are for safe review of a quarantined archive. They avoid operational details and focus on handling discipline.

## Static indicators to review

- File and folder names that suggest risky automation.
- Install notes that request broad system permissions.
- Imports or commands that would affect the host environment.
- Logs that describe automated changes or hidden behavior.

## Safe response checklist

1. Do not run the package.
2. Record SHA-256 hashes and file sizes.
3. Preserve the original in a private evidence store.
4. Review only in an isolated analysis environment.
5. Publish only non-operational summaries, manifests, and safe simulators.
6. Add repository rules that block accidental upload of private evidence.

## GitHub guardrails

- Add `quarantine/`, `evidence-private/`, `*.tar.gz`, and `*.zip` to `.gitignore`.
- Require review before changes to `src/`.
- Keep CI limited to tests and static checks.
