# AppealMate — submission description

Rules require the description in **300 characters or fewer**. All four options
below are verified within that limit by `_desc.py`.

---

## Recommended (263 characters)

> AppealMate is a voice agent that helps Medicare Advantage patients appeal denied prior authorizations. You press one button and talk; Aria interviews you, cites the exact rule your plan's denial violates, and drafts your appeal. Nothing is filed until you say so.

*Why this one:* it names the user, the problem, the mechanism — and it ends on
the consent guarantee, which is the point judges score under "verification and
responsible human oversight."

---

## Alternative: benefit-led (246 characters)

> Most Medicare Advantage denials are never appealed because the paperwork is brutal. AppealMate lets a patient press one button and talk. Aria gathers the facts, cites the plan's own policy, and drafts the appeal. Nothing is filed without consent.

*Why this one:* leads with why it matters rather than what it is. Stronger if the
judging panel weighs problem importance heavily.

---

## Alternative: shortest (195 characters)

> A voice agent that helps Medicare Advantage patients appeal denied care. Press one button, talk to Aria, and she drafts an appeal citing your plan's own policy. Nothing is filed until you say so.

*Why this one:* maximum headroom, and the easiest to read aloud on stage.

---

## Alternative: mechanism-led (204 characters)

> Press one button and talk. AppealMate interviews you about a denied prior authorization, finds the rule your plan's own policy says it broke, and drafts your appeal. Nothing is filed until you approve it.

---

## Claims in these descriptions, and whether they hold

I checked each factual claim against the code rather than the pitch. Judges are
scoring "claims must match the evidence demonstrated."

| Claim | Verified? |
|---|---|
| Voice agent, one button to talk | Yes — single centred button, browser speech recognition |
| Interviews the patient | Yes — required questions, then a policy interview phase |
| Cites the rule the denial violates | Yes — quotes the plan's own CPB criteria verbatim |
| Drafts the appeal | Yes — composed from the patient's own answers |
| Nothing filed without consent | Yes — `test_file_only_after_consent` passes |

**Deliberately not claimed:** that appeals are *won*. The README states plainly
that drafts and filings are measured, not overturns, and the guide warns that
"an invoice flagged is not money recovered." Same discipline here.

---

## If you also need the longer-form items

The submission package (per the event rules) asks for more than the 300-character
description. These are ready to reuse:

- **Repository:** https://github.com/Zeaxanthin80/appealmate
- **Live app:** https://appealmate.vercel.app
- **Slides:** available at `/slides` on the deployed app
- **README** covers setup, tests, architecture, and honest limits

**Still outstanding before you submit:** the Mel session recording and the
3-minute demo video. Both are mandatory and a submission without them cannot be
accepted. The demo video is the one to prioritise — it is what judges watch.
