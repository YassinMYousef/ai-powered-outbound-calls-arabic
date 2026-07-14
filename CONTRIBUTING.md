# Contributing

Engineering procedures for the CallCenter team (5 people, one module each).
Architecture and conventions: [CLAUDE.md](CLAUDE.md). Setup: [README Quickstart](README.md#quickstart).

## Local setup

1. Follow the [README Quickstart](README.md#quickstart). Backend needs Python 3.11+; frontend needs Node 22 LTS.
   - Backend deps (from `backend/`): `pip install -e ".[dev]"` — includes pytest, ruff, and pre-commit.
   - Frontend deps (from `frontend/`): `npm ci`.
2. Copy config: `cp backend/.env.example backend/.env` (`.env` is gitignored).
3. Install the git hooks once, from the repo root with the backend venv active:
   `source backend/.venv/bin/activate && pre-commit install`. Hooks live in
   [.pre-commit-config.yaml](.pre-commit-config.yaml).
4. Use the project skills in `.claude/skills/` for recurring workflows: `run-stack` (dev stack),
   `verify` (end-to-end verification), `test-call-flow` (Twilio loop), `db-migrate` (Alembic).

## Branch workflow

- `main` is protected — never commit to it directly.
- Branch from `main`, named `<module>/<short-desc>` where module is one of
  `speech`, `telephony`, `conversation`, `data`, `frontend`. Example: `telephony/gather-handler`.
- Rebase or merge `main` into your branch before opening the PR.

## Commits

- Use Conventional Commits: `feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `chore:`.
- Write the subject in imperative mood: `feat: add gather webhook handler`, not "added".
- Scope each commit to one change.

## Pull requests

- Keep PRs small and single-purpose — one feature or fix per PR.
- CI must be green: the `backend` check (ruff + pytest) and the `frontend` check (build),
  both defined in [.github/workflows/ci.yml](.github/workflows/ci.yml).
- Get at least one approval from the owning module's person.
  [.github/CODEOWNERS](.github/CODEOWNERS) auto-requests the owner where one is mapped —
  only telephony is mapped so far; add your own GitHub username for your module
  (usernames are never guessed on someone else's behalf).
- Say in the PR description how you verified the change: run the
  [verify skill](.claude/skills/verify/SKILL.md) and summarize what you drove live.

## Definition of done

A change is done when all of the following hold (full procedure:
[verify skill](.claude/skills/verify/SKILL.md)):

- `ruff check app tests` and `pytest` pass clean (from `backend/`); frontend changes also
  pass `npm run build`.
- The changed surface has been driven live per the verify skill — a green unit suite alone
  is not done.
- Schema changes ship an Alembic migration in the same PR — use the
  [db-migrate skill](.claude/skills/db-migrate/SKILL.md) (it also covers the first-time
  Alembic setup, which hasn't happened yet).
- Docs stay current: update README.md / CLAUDE.md when behavior, commands, or config keys change.

## Repo admin (one-time)

For the repo owner (@YassinMYousef) — GitHub UI only, after CI has run at least once
(status checks must exist before they can be required):

1. GitHub → **Settings → Branches → Add branch protection rule**.
2. Branch name pattern: `main`.
3. Enable **Require a pull request before merging**, with **1 required approval**.
4. Enable **Require status checks to pass before merging**; select the `backend` and
   `frontend` checks.
5. Enable **Block force pushes**.
