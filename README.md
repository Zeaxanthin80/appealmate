# AppealMate

**A voice-first agent that helps Medicare Advantage beneficiaries appeal denied
prior authorizations.** The caller presses one button, speaks to Aria, and Aria
drafts the appeal argument with the highest chance of getting the denial
overturned — citing the plan's own clinical policy criteria. Nothing is filed
until the caller says "file it."

Built for the Miami AI Hackathon (Agentic Finance track) with Mel. Voice by
ElevenLabs. **Zero third-party dependencies — Python stdlib only.**

---

## Run it

```bash
cd appealmate
python server.py
```

- App: **http://localhost:8080** — press the big button, speak to Aria
- Slides: **http://localhost:8080/slides**

Set `ELEVENLABS_API_KEY` in the environment for real text-to-speech; without a
key Aria still speaks (captions + browser speech input work; the transcript is
shown as captions).

## Test it

```bash
cd appealmate
python run_tests.py
```

## Deploy to Vercel

The repo is Vercel-ready. `api/index.py` is a WSGI adapter serving the same endpoint as `server.py`, and `vercel.json` routes everything to it.

1. Go to `vercel.com/new` and sign in with GitHub.
2. **Import** the `Zeaxanthin80/appealmate` repository.
3. Framework preset: **Other**. Leave build/output commands empty — Vercel detects `api/index.py` as a Python function.
4. Add env var `ELEVENLABS_API_KEY` (optional — without it the app shows captions instead of audio).
5. Deploy. Every push to `main` redeploys automatically.

**Serverless caveats, stated plainly:** Vercel's filesystem is read-only except `/tmp`, so the SQLite database lives at `/tmp/appealmate.db` — per-instance and lost on cold start, so audit history and run counts reset. Fine for a demo; for durable audit records swap `store.py` to hosted Postgres (Vercel Postgres, Supabase, Neon). Sessions are stored in the database rather than memory because each request is its own invocation. Run `python verify_vercel_adapter.py` to check the serverless entry point locally.

## The three demo scenarios (arbitrary denials for presentation)

| # | Short name | The denial | The counter-argument Aria files |
|---|---|---|---|
| 1 | Heart CT scan | "Not medically necessary; stress test first" | A prior stress test was **inconclusive** and the patient **cannot exercise** — both exceptions in the plan's own coronary CTA criteria are already met. |
| 2 | Extra physical therapy | "Session cap reached; maintenance not covered" | Medicare Advantage plans may not impose hard therapy caps; documented **fall risk** + restorative goals meet the plan's own extended-PT criteria. |
| 3 | Power wheelchair | "A scooter is sufficient" | The patient **cannot transfer safely** and has **hand tremors** — the plan's own power-mobility policy says that is exactly when a power wheelchair is indicated, not a scooter. |

In each: **the plan's denial contradicts the plan's own policy.** Aria finds that
contradiction and files it.

## How the agent works (tool trace)

`session_start` → `ask_field` ×7 (one question at a time) → `match_policy` →
`draft_appeal` (or `refuse_no_match` / `refuse_weak_evidence`) → explicit spoken
consent → `file_appeal`.

Every step is logged to an append-only audit log (`/api/audit`), and run counts
(`/api/evidence`) expose the evidence denominator: drafted / refused / filed out
of total sessions.

## Safety design

- **Fail-closed refusal:** no policy match or weak evidence → Aria refuses to
  file and says why, in plain words.
- **Read-back before filing:** the entire appeal is spoken aloud; only "file it"
  submits. Anything else holds.
- **"Stop" works instantly** at any point in the conversation.
- **Append-only audit trail** of every tool step.
- **Honest metrics:** drafts and filings are measured; overturns are not claimed.

## Honest limits

- Policy criteria in `policies.py` are **verbatim excerpts from real Aetna
  Clinical Policy Bulletins** — CPB 0228 (Cardiac CT/Angiography), CPB 0325
  (Physical Therapy), CPB 0271 (Wheelchairs/POVs) — fetched from Aetna's public
  clinical-policy pages. The appeal form structure comes from Aetna's public
  Medicare Part C appeal form page. This is demo content, not clinical or legal
  advice.
- Three scenarios ship in the demo library.
- An appeal is not an approval: we report drafts and filings, not overturns.

## Project layout

```
appealmate/
  server.py          # HTTP API + serves the UI and slides
  agent.py           # Aria: conversation state machine, refusal logic, form fill
  policies.py        # demo denial scenarios + representative CPB criteria
  voice.py           # ElevenLabs TTS (offline transcript fallback) + commands
  store.py           # SQLite append-only audit log + run counts
  index.html         # senior-friendly voice UI (big buttons, live captions)
  slides.html        # HTML/CSS/JS presentation deck (arrow keys to navigate)
  test_appealmate.py # unittest suite incl. refusal + stop paths
```
