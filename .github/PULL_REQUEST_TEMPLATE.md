## Summary
<!-- One or two sentences: what changed and why. -->

Closes #<!-- issue number — delete this line if none -->

## How verified
<!-- Definition of done lives in `.claude/skills/verify`. Paste the actual commands you ran
     and the key output: pytest run, curls with realistic Arabic/Twilio payloads, Celery
     worker [tasks] banner, or `npm run build`. "It imports" / "the app boots" doesn't count. -->

```
<commands + relevant output>
```

## Checklist
- [ ] `ruff check app tests` + `pytest` pass (from `backend/`) / `npm run build` passes (from `frontend/`)
- [ ] New or changed endpoints driven live with a realistic payload (see `.claude/skills/verify`)
- [ ] Alembic migration included if `backend/app/data/models.py` changed (see `.claude/skills/db-migrate`)
- [ ] Docs updated (`README.md` / `CLAUDE.md` / `.claude/skills/*`) if commands or behavior changed
