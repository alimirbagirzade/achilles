# Local Claude Operator Dry-Run Task

Task:
Add one harmless sentence to docs/PHASE4_GITHUB_AUTOMATION.md under a new “Local dry-run note” heading.

Allowed files:
- docs/PHASE4_GITHUB_AUTOMATION.md

Forbidden files:
- app/**
- tests/**
- data/**
- storage/**
- vector_db/**
- models/**
- .env
- .github/workflows/**

Acceptance criteria:
- Only docs/PHASE4_GITHUB_AUTOMATION.md changed.
- Protected-path guard passes.
- Local CI passes.
- No push.
- No PR.
- No GitHub Actions.
- No training.
