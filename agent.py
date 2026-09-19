"""AppealMate — the appeal agent.

A deliberately simple state machine, because the caller is the product: an
older adult, on the phone, stressed. Aria introduces herself warmly, asks one
question at a time, matches the story to policy criteria, drafts the strongest
supportable argument, and files only with explicit consent.

Two rules keep this humane, and both exist because a real member's answer
usually IS "I don't know":

1. A missing answer must never cost the member their appeal. The provider who
   requested the service and whether the request was formally denied are fields
   members routinely cannot answer — Aria accepts "I don't know", records the
   field as not provided, and moves on.
2. Aria never refuses before asking a clarifying question first. A short answer
   like "a CT scan" is not enough to match policy, but it is also not a reason
   to send someone away — she asks one more question, then decides.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field, asdict

import argument
import policies
import store
import voice


# The introduction Aria speaks first. Confident and warm, not tentative: the
# member has just been told their care is denied, and they need to hear someone
# who sounds certain they can help. The safety promise is still here, stated
# plainly rather than hedged.
INTRO = (
    "Hello, I'm Aria. I help people appeal health insurance denials, and I'm "
    "good at it. Tell me what was denied, and I'll find the rule your plan "
    "overlooked and write your appeal for you. I won't file anything until you "
    "tell me to. Let's start — what's your name?"
)

# Fields Aria asks about, in order. The two on the ID card and the member's own
# description of what was denied are the ones people can answer. The denial
# reason, the requesting provider and whether the request was formally denied
# come afterwards, optional and clearly marked as skippable — they are the
# questions members most often cannot answer, so asking them first loses people.
ASK_ORDER = ["member_name", "member_id", "service_denied"]

# Optional questions asked after the required ones. Each is explicitly
# skippable, and "I don't know" moves on without comment.
OPTIONAL_ORDER = ["provider_requested", "was_denied"]
UNKNOWN_PHRASES = (
    "i don't know", "i dont know", "dont know", "don't know", "not sure",
    "i'm not sure", "im not sure", "no idea", "i have no idea", "no clue",
    "i forget", "i forgot", "don't remember", "dont remember",
    "can't remember", "cant remember", "unknown", "dunno", "n/a", "na",
    "none", "nothing", "not really", "no",
)

# Fields that are commonly unknown and NEVER block the appeal. If the member
# cannot answer, Aria records "Not provided" and keeps going.
SOFT_FIELDS = {
    "denial_reason", "provider_requested", "was_denied",
    "date_of_denial", "plan_name",
}

# Reassuring lines for the soft fields — no pressure, no repetition of the
# question, and a plain statement that it does not hurt their case.
SOFT_ACK = {
    "denial_reason": ("That's completely fine — plenty of people don't have the "
                      "letter in front of them. I'll work from what you told me "
                      "instead, and it won't hurt your appeal."),
    "provider_requested": ("No problem at all. We can leave that blank and the "
                           "plan will fill it in from their own records."),
    "was_denied": ("That's alright — the denial letter is the proof, so we don't "
                   "need you to confirm it."),
    "date_of_denial": ("That's fine. I'll note it as recent and we can add the "
                       "exact date later."),
    "plan_name": ("That's okay — your member ID tells the plan which plan it is."),
}


@dataclass
class Step:
    tool: str
    status: str
    detail: str


@dataclass
class Session:
    session_id: str
    state: str = "intro"
    # Phases, in order: required questions -> optional questions -> the policy
    # interview -> drafted/refused -> filed/stopped. "clarifying" is the single
    # extra question asked when the story cannot be matched at all.
    phase: str = "required"
    cursor: int = 0
    data: dict = field(default_factory=dict)
    facts: dict = field(default_factory=dict)   # the patient's own answers
    interview: list = field(default_factory=list)  # [(fact_id, question)]
    story: str = ""
    scenario_id: str | None = None
    clarifications: int = 0
    steps: list[Step] = field(default_factory=list)
    created: float = field(default_factory=time.time)

    def trace(self) -> list[dict]:
        return [asdict(s) for s in self.steps]


SESSIONS: dict[str, Session] = {}

# In-memory cache. On a serverless host each request may land in a fresh
# process, so the database is the source of truth and this is only a fast path.


def _to_payload(s: Session) -> dict:
    return {"session_id": s.session_id, "state": s.state, "phase": s.phase,
            "cursor": s.cursor,
            "data": s.data, "facts": s.facts,
            "interview": [list(x) for x in s.interview],
            "story": s.story, "scenario_id": s.scenario_id,
            "clarifications": s.clarifications,
            "steps": [asdict(x) for x in s.steps], "created": s.created}


def _from_payload(p: dict) -> Session:
    s = Session(session_id=p["session_id"], state=p.get("state", "intro"),
                phase=p.get("phase", "required"),
                cursor=p.get("cursor", 0), data=p.get("data", {}),
                facts=p.get("facts", {}),
                interview=[tuple(x) for x in p.get("interview", [])],
                story=p.get("story", ""), scenario_id=p.get("scenario_id"),
                clarifications=p.get("clarifications", 0),
                created=p.get("created", time.time()))
    s.steps = [Step(**x) for x in p.get("steps", [])]
    return s


def _save(s: Session) -> None:
    SESSIONS[s.session_id] = s
    store.save_session(s.session_id, _to_payload(s))


def _load(sid: str) -> Session | None:
    if sid in SESSIONS:
        return SESSIONS[sid]
    p = store.load_session(sid)
    if not p:
        return None
    s = _from_payload(p)
    SESSIONS[sid] = s
    return s


def _log(s: Session, tool: str, status: str, detail: str) -> None:
    s.steps.append(Step(tool, status, detail))
    store.log_audit("agent", tool, s.session_id, {"status": status, "detail": detail[:300]})


def is_unknown(text: str) -> bool:
    """Did the member say they don't know? Deliberately forgiving."""
    t = (text or "").strip().lower().strip(".!?,")
    if not t:
        return True
    if t in UNKNOWN_PHRASES:
        return True
    # "I really don't know", "sorry I don't know" ...
    return any(p in t for p in ("don't know", "dont know", "not sure",
                                "no idea", "can't remember", "cant remember",
                                "don't remember", "dont remember"))


def start_session() -> dict:
    sid = "s-%d" % int(time.time() * 1000)
    s = Session(session_id=sid)
    _save(s)
    store.log_audit("agent", "session_start", sid, {"intro": True})
    return {"session_id": sid, "state": s.state,
            "say": voice.speak(INTRO), "transcript": INTRO}


def _next_question(s: Session, fid: str) -> dict:
    qs = {
        "member_id": "Thank you. What's your member ID number? It's on your insurance card.",
        "service_denied": "What service or item was denied? Take your time.",
        # The two optional questions. Both are phrased so that not knowing is a
        # normal answer, not a failure — and both say what happens if they skip.
        "provider_requested": ("Last two things, and you can skip either one. "
                               "Do you remember the name of the doctor who asked "
                               "for it? If not, just say you're not sure — the "
                               "plan can look that up."),
        "was_denied": ("And did the plan tell you in writing that the request was "
                       "denied? If you're not sure, that's fine — the denial "
                       "letter itself is the proof."),
    }
    q = qs.get(fid, "Can you tell me more about that?")
    s.state = "asking"
    _log(s, "ask_field", "ok", fid)
    return {"session_id": s.session_id, "state": s.state, "field": fid,
            "say": voice.speak(q), "transcript": q}


def _ask_interview(s: Session) -> dict:
    """Ask the next question from the policy interview."""
    fid, q = s.interview[s.cursor]
    s.state = "interview"
    _log(s, "ask_fact", "ok", fid)
    return {"session_id": s.session_id, "state": s.state, "field": fid,
            "say": voice.speak(q), "transcript": q}


def send(sid: str, user_text: str) -> dict:
    """Main conversational turn. Returns what Aria says next."""
    result = _send_inner(sid, user_text)
    s = SESSIONS.get(sid)
    if s is not None:
        _save(s)
    return result


def _send_inner(sid: str, user_text: str) -> dict:
    s = _load(sid)
    if not s:
        return {"error": "unknown session"}

    text = (user_text or "").strip()

    # Global safety: the member can always stop.
    if text.lower() in ("stop", "cancel", "never mind", "stop it"):
        s.state = "stopped"
        q = ("Of course. I've stopped and I won't file anything. "
             "Your session is saved if you change your mind.")
        _log(s, "caller_stopped", "ok", "caller ended session")
        return {"session_id": sid, "state": s.state, "say": voice.speak(q), "transcript": q}

    if s.state == "intro":
        s.data["member_name"] = text
        s.story += " " + text
        s.cursor = 1
        s.phase = "required"
        return _next_question(s, ASK_ORDER[s.cursor])

    if s.state == "interview":
        # The patient's answers here become the appeal argument, so they go into
        # `facts` (not `data`, which is the form) and also into the story so the
        # policy match keeps improving as they talk.
        fid = s.interview[s.cursor][0] if s.cursor < len(s.interview) else None
        if fid:
            if is_unknown(text):
                s.facts[fid] = ""
                _log(s, "fact_not_provided", "ok", "%s unknown; left blank" % fid)
            else:
                s.facts[fid] = text
                s.story += " " + text
                _log(s, "fact_learned", "ok", "%s: %s" % (fid, text[:80]))
        s.cursor += 1
        if s.cursor < len(s.interview):
            return _ask_interview(s)
        return _analyze(s)

    if s.state in ("asking", "clarifying"):
        if s.state == "clarifying":
            # The clarifying answer is rich signal — always add it to the story.
            s.story += " " + text
            return _analyze(s)

        # Which question list are we working through?
        order = ASK_ORDER if s.phase == "required" else OPTIONAL_ORDER
        fid = order[s.cursor] if s.cursor < len(order) else None
        if fid:
            # A member who doesn't know an answer is not a dead end. Record the
            # field as blank and carry on. It must stay genuinely empty rather
            # than storing the words "Not provided" — otherwise the form review
            # reports the field as filled when the plan still needs to supply it.
            if is_unknown(text):
                s.data[fid] = ""
                _log(s, "field_not_provided", "ok", "%s unknown; left blank" % fid)
            else:
                s.data[fid] = text
                s.story += " " + text
        s.cursor += 1

        # Required questions first, then the skippable ones, then the analysis.
        if s.cursor < len(order):
            return _next_question(s, order[s.cursor])
        if s.phase == "required":
            s.phase = "optional"
            s.cursor = 0
            return _next_question(s, OPTIONAL_ORDER[0])
        return _analyze(s)

    if s.state in ("drafted", "refused"):
        low = text.lower()
        if any(k in low for k in ("file it", "file the appeal", "go ahead",
                                  "yes, file", "please file")):
            if s.state == "drafted":
                return _file(s)
            q = ("I haven't drafted an appeal yet because I couldn't match your "
                 "denial to a policy. Nothing has been filed.")
            return {"session_id": sid, "state": s.state, "say": voice.speak(q), "transcript": q}
        if s.state == "drafted":
            q = ("Just say 'file it' when you're ready, or tell me what to change. "
                 "I won't submit anything until you do.")
        else:
            q = ("If you'd like, I can give you the number on your denial letter. "
                 "Nothing has been filed.")
        return {"session_id": sid, "state": s.state, "say": voice.speak(q), "transcript": q}

    q = "I'm here. Tell me about your denial."
    return {"session_id": sid, "state": s.state, "say": voice.speak(q), "transcript": q}


# One question, asked once, when the story is too thin to match a policy.
CLARIFY_Q = (
    "I want to make sure I send this to the right place. Was the care that was "
    "denied an imaging scan or test, a course of therapy, or a piece of "
    "equipment like a wheelchair or a walker?"
)


def _analyze(s: Session, lead: str | None = None) -> dict:
    """Match the story to policy. Asks one clarifying question before refusing."""
    _log(s, "match_policy", "ok", "matching story to policy library")
    scenario = policies.find_scenario(s.story)

    # Before giving up, ask ONE clarifying question. A member answering "a scan"
    # is being cooperative, not unhelpable.
    if not scenario and s.clarifications < 1:
        s.clarifications += 1
        s.state = "clarifying"
        _log(s, "clarify_once", "ok", "story too thin; asking one clarifying question")
        q = (CLARIFY_Q if not lead else lead + " " + CLARIFY_Q)
        return {"session_id": s.session_id, "state": s.state,
                "say": voice.speak(q), "transcript": q}

    if not scenario:
        s.state = "refused"
        q = ("I've listened carefully, but I couldn't match your denial to the "
             "policies I know. I don't want to guess with something this "
             "important, so I won't file anything. Here's what I'd suggest: call "
             "your plan directly, or use the number on your denial letter. "
             "Nothing has been filed.")
        _log(s, "refuse_no_match", "refused", "no policy match after clarifying")
        store.record_run("appealmate", "refused", s.session_id)
        return {"session_id": s.session_id, "state": s.state, "refused": True,
                "say": voice.speak(q), "transcript": q}

    pol = scenario["policy"]
    if not pol["supports_overturn"]:
        s.state = "refused"
        q = ("I found the policy for your situation, but honestly, the criteria "
             "don't support an appeal right now. I'd rather tell you that "
             "straight than file something the plan will deny again. Nothing has "
             "been filed.")
        _log(s, "refuse_weak_evidence", "refused", "policy does not support overturn")
        store.record_run("appealmate", "refused", s.session_id)
        return {"session_id": s.session_id, "state": s.state, "refused": True,
                "say": voice.speak(q), "transcript": q}

    s.scenario_id = scenario["id"]

    # The policy is known. Now ask the patient the specific things the plan's
    # criteria turn on, so the argument is built from their facts rather than
    # from a template applied to everyone.
    if not s.interview and not s.facts:
        script = argument.interview_for(scenario["id"])
        if script:
            s.interview = list(script)
            s.cursor = 0
            lead = ("Good news — I found the rule your plan overlooked. %s "
                    "Now I need a few details from you, because those details are "
                    "what make the argument land. A few short questions."
                    % pol["cpb"].split("—")[0].strip().rstrip(".") + ".")
            first = _ask_interview(s)
            first["transcript"] = lead + " " + first["transcript"]
            first["say"] = voice.speak(first["transcript"])
            return first

    return _draft(s, scenario, pol)


def _draft(s: Session, scenario: dict, pol: dict) -> dict:
    """Compose the appeal argument from the patient's own answers."""
    s.state = "drafted"
    # Use the scenario's clean service name, not the patient's spoken sentence.
    # The raw answer is a paragraph ("a heart CT scan, they said it wasn't...")
    # and reads badly inside "I am appealing the denial of X."
    statement = argument.compose(
        scenario["id"], s.facts,
        service=scenario["service"],
        denial_reason=s.data.get("denial_reason", "") or scenario["denial_reason"],
    )
    s.data["appeal_text"] = statement
    _log(s, "draft_appeal", "ok", "composed appeal from %d fact(s) citing %s"
         % (len([v for v in s.facts.values() if v]), pol["cpb"]))
    store.record_run("appealmate", "drafted", s.session_id)

    q = ("I've written your appeal from what you told me, and before we do "
         "anything I want to read it to you. %s That's your argument. You can "
         "copy that into the Comments section of the form. Would you like me to "
         "file it, or change something first? Say 'file it' when you're ready."
         % statement)
    return {
        "session_id": s.session_id, "state": s.state, "refused": False,
        "appeal_text": s.data["appeal_text"],
        "policy_citation": pol["cpb"],
        "criteria_text": pol["criteria_text"],
        "say": voice.speak(q), "transcript": q,
    }


def _file(s: Session) -> dict:
    s.state = "filed"
    form = generate_form(s)
    store.record_run("appealmate", "filed", s.session_id)
    _log(s, "file_appeal", "ok", "appeal filed with explicit consent")
    q = ("Done. Your appeal has been submitted. Keep your confirmation number: "
         "%s. Your plan must answer within the Medicare redetermination window. "
         "I'm proud of you for fighting this." % form["confirmation"])
    return {"session_id": s.session_id, "state": s.state, "form": form,
            "say": voice.speak(q), "transcript": q}


def generate_form(s: Session) -> dict:
    """Produce the filled Aetna Medicare Part C appeal form fields.

    Every field carries its label and whether the plan requires it, so the
    review screen can show the member exactly what is filled in, what was left
    blank, and what still needs their attention before they sign.
    """
    conf = "AM-" + hashlib.sha1((s.session_id + str(time.time())).encode()).hexdigest()[:8].upper()
    form = {"confirmation": conf, "fields": [], "missing_required": []}
    for entry in policies.FORM_FIELDS:
        fid, label, _src, required = entry
        value = s.data.get(fid, "")
        # The Comments section is where the appeal argument goes. The agent
        # stores it as appeal_text; surface it under the form's own field id.
        if fid == "comments" and not value:
            value = s.data.get("appeal_text", "")
        if fid == "provider_requested" and not value:
            value = s.data.get("provider_name", "")
        filled = bool(value)
        form["fields"].append({"id": fid, "label": label, "value": value,
                               "required": required, "filled": filled})
        if required and not filled:
            form["missing_required"].append(label)
    return form


def get_session(sid: str) -> dict | None:
    s = _load(sid)
    if not s:
        return None
    return {"session_id": s.session_id, "state": s.state, "data": s.data,
            "scenario_id": s.scenario_id, "trace": s.trace()}
