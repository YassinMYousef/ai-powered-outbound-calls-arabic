---
name: test-call-flow
description: Simulate the Twilio webhook call loop (/telephony/voice, /gather, /status) with curl and trigger real outbound calls through an ngrok/cloudflared tunnel. Use when testing or debugging the outbound-call flow, telephony webhooks, place_call, TwiML/Arabic voice output, dialog intent phrases, or when wiring up live Twilio calls in dev.
---

## Ground truth (re-verify against the code — it moves fast)
- IMPLEMENTED: `app/telephony/client.py::place_call` (real Twilio dial; appends `?call_id=<id>` to both webhook URLs), `POST /telephony/voice` (TwiML `<Say>` with voice `Polly.Zeina`, language `arb` — MSA; Twilio has no Egyptian-dialect voice), `POST /telephony/status` (logs CallSid/CallStatus/CallDuration + `call_id` query param, returns 204).
- NOT implemented: `POST /telephony/gather` raises `NotImplementedError` → HTTP 500. Also `/voice`'s TwiML has no `<Gather>` verb yet, so a real call plays the greeting then hangs up; Twilio will only POST `/gather` once `<Gather input="speech" action="…/telephony/gather?call_id=…">` is added to `/voice`.

## Start the API
```bash
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload        # :8000, docs at http://localhost:8000/docs
```
Postgres/Redis are not needed for this loop (webhooks don't touch the DB yet). Config is read from `backend/.env` (gitignored; on a fresh clone: `cp .env.example .env`). Restart uvicorn after editing `.env` — `--reload` only watches code.

## The loop being simulated
`place_call(to_number, call_id)` dials via Twilio with `url={PUBLIC_BASE_URL}/telephony/voice?call_id=<id>` and `status_callback={PUBLIC_BASE_URL}/telephony/status?call_id=<id>` (`status_callback_event=["completed"]`, POST). Twilio then POSTs form-encoded bodies: `/voice` when answered, `/gather` with the speech result (once wired), `/status` at call end. The `call_id` query param is the correlation key back to the CallLog row.

## Simulate the loop locally with curl
Call answered:
```bash
curl -si -X POST 'http://localhost:8000/telephony/voice?call_id=1' \
  --data-urlencode 'CallSid=CAtest0000000000000000000000000001' \
  --data-urlencode 'AccountSid=ACtest000000000000000000000000000' \
  --data-urlencode 'From=+15005550006' --data-urlencode 'To=+201001234567' \
  --data-urlencode 'CallStatus=in-progress'
```
Expect `200`, `content-type: application/xml`, body exactly:
`<?xml version="1.0" encoding="UTF-8"?><Response><Say language="arb" voice="Polly.Zeina">مرحبًا بك. هذه مكالمة متابعة للتأكد من أن مشكلتك قد تم حلها.</Say></Response>`

Speech result (use `--data-urlencode` so Arabic is encoded correctly):
```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST 'http://localhost:8000/telephony/gather?call_id=1' \
  --data-urlencode 'CallSid=CAtest0000000000000000000000000001' \
  --data-urlencode 'SpeechResult=نعم' --data-urlencode 'Confidence=0.91'
```
Expect `500` today (`NotImplementedError` traceback in uvicorn output). Once `/gather` is implemented, expect `200` + TwiML.

Final status:
```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST 'http://localhost:8000/telephony/status?call_id=1' \
  -d 'CallSid=CAtest0000000000000000000000000001' -d 'CallStatus=completed' -d 'CallDuration=42'
```
Expect `204`. The handler logs `call finished: sid=… status=completed duration=42s call_id=1` at INFO, but uvicorn's default logging drops app-logger INFO records — judge success by the 204, not the log line.

## Arabic test phrases per intent (`Intent` enum in app/conversation/dialog.py)
`classify_intent` and `next_action` are IMPLEMENTED (rule-based, offline; covered by `tests/test_dialog.py`). Unmatched or empty speech returns `Intent.UNKNOWN`. Use these as `SpeechResult` values once `/gather` is wired — the full phrase tables live in `dialog.py` as `YES_WORDS` / `NO_WORDS` / `UNCERTAIN_WORDS` / `AGENT_WORDS`:
- YES → `نعم` · `أيوه` · `اه تمام`
- NO → `لا` · `لأ` · `لسه معملتش`
- UNCERTAIN → `غير متأكد` · `مش متأكد` · `مش عارف`
- AGENT → `عايز أكلم موظف` · `حولني لحد`
- UNKNOWN → `` (silence) · `الجو حر النهاردة` (unrelated speech)

`next_action(state, intent)` escalates by turn (0-indexed customer reply): YES → `MARK_RESOLVED` always; AGENT → `TRANSFER_TO_AGENT` always; NO → `OFFER_HELP` then transfer; UNCERTAIN → `REPEAT_QUESTION`, `OFFER_HELP`, then transfer; UNKNOWN → repeat twice, then transfer. `END_CALL` is never returned — every dead end goes to a human, and `/gather` owns hanging up.

## Real Twilio call through a tunnel
1. Expose the API: `ngrok http 8000` (or `cloudflared tunnel --url http://localhost:8000`); copy the https URL.
2. In `backend/.env` set `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, and `PUBLIC_BASE_URL=https://<tunnel-host>`. `TWILIO_FROM_NUMBER` is E.164; Twilio does not sell Egyptian (+20) numbers — use a Twilio number from a supported country or a number verified as an outgoing caller ID. No uvicorn restart needed: the webhook handlers never read Twilio settings, and the step-3 command is a fresh process that reads `.env` on start (`place_call` raises RuntimeError if SID/token/from-number are unset).
3. Trigger the call:
```bash
cd backend && .venv/bin/python -c \
  "from app.telephony.client import place_call; print(place_call('+2010XXXXXXXX', 1))"
```
Prints the Twilio call SID (`CA…`). The answered phone hears the MSA greeting, then the call ends (no `<Gather>` yet). On completion Twilio POSTs `/telephony/status?call_id=1` through the tunnel — a `POST /telephony/status?call_id=1 … 204` line in uvicorn's access log confirms the full round trip.
