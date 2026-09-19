"""AppealMate — the appeal agent.

A deliberately simple state machine, because the caller is the product: an
older adult, on the phone, stressed. Aria introduces herself warmly, asks one
question at a time, matches the story to policy criteria, drafts the strongest
supportable argument, and REFUSES to file when the evidence doesn't support an
appeal — with the reason stated plainly.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field, asdict

import policies
import store
import voice


# The introduction Aria speaks first. Warm, safe, on the caller's side.
INTRO = (
    "Hello! I'm Aria, your health-insurance appeal assistant. I'm here to help "
    "you fight a denial, and everything you tell me stays between us. We'll take "
    "this one step at a time, and I'll only file your appeal when you say you're "
    "ready. You can tell me to stop at any moment. What's your name?"
)

# Ordered fields the agent asks for, one at a time (from the form model).
ASK_ORDER = ["member_name", "member_id", "plan_name", "service_denied",
             "date_of_denial", "denial_reason", "provider_name"]


@dataclass
class Step:
    tool: str
    status: str
    detail: str


@dataclass
class Session:
    session_id: str
    state: str = "intro"          # intro -> asking -> analyzing -> drafted/refused -> filed/stopped
    cursor: int = 0               # index into ASK_ORDER
    data: dict = field(default_factory=dict)
    story: str = ""
    scenario_id: str | None = None
    steps: list[Step] = field(default_factory=list)
    created: float = field(default_factory=time.time)

    def trace(self) -> list[dict]:
        return [asdict(s) for s in self.steps]


SESSIONS: dict[str, Session] = {}

# In-memory cache. On a serverless host each request may land in a fresh
# process, so the database is the source of truth and this is only a fast path.


def _to_payload(s: Session) -> dict:
    return {"session_id": s.session_id, "state": s.state, "cursor": s.cursor,
            "data": s.data, "story": s.story, "scenario_id": s.scenario_id,
            "steps": [asdict(x) for x in s.steps], "created": s.created}


def _from_payload(p: dict) -> Session:
    s = Session(session_id=p["session_id"], state=p.get("state", "intro"),
                cursor=p.get("cursor", 0), data=p.get("data", {}),
                story=p.get("story", ""), scenario_id=p.get("scenario_id"),
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
        "plan_name": "Got it. What's the name of your insurance plan?",
        "service_denied": "What service or item was denied? Take your time.",
        "date_of_denial": "When did you get the denial letter?",
        "denial_reason": "What reason did the letter give for the denial?",
        "provider_name": "And what's the name of the doctor who ordered it for you?",
    }
    q = qs.get(fid, "Can you tell me more about that?")
    s.state = "asking"
    _log(s, "ask_field", "ok", fid)
    return {"session_id": s.session_id, "state": s.state, "field": fid,
            "say": voice.speak(q), "transcript": q}


def send(sid: str, user_text: str) -> dict:
    """Main conversational turn. Returns what Aria says next."""
    result = _send_inner(sid, user_text)
    # Persist whatever the turn produced, so the next request — which may land
    # in a different serverless instance — resumes from the same state.
    s = SESSIONS.get(sid)
    if s is not None:
        _save(s)
    return result


def _send_inner(sid: str, user_text: str) -> dict:
    s = _load(sid)
    if not s:
        return {"error": "unknown session"}

    text = (user_text or "").strip()

    # Global safety: caller can always stop.
    if text.lower() in ("stop", "cancel", "never mind", "stop it"):
        s.state = "stopped"
        q = ("Of course. I've stopped and I won't file anything. "
             "Your session is saved if you change your mind.")
        _log(s, "caller_stopped", "ok", "caller ended session")
        return {"session_id": sid, "state": s.state, "say": voice.speak(q), "transcript": q}

    if s.state == "intro":
        # First reply is the caller's name.
        s.data["member_name"] = text
        s.story += " " + text
        s.cursor = 1
        return _next_question(s, ASK_ORDER[s.cursor])

    if s.state == "asking":
        fid = ASK_ORDER[s.cursor] if s.cursor < len(ASK_ORDER) else None
        if fid:
            s.data[fid] = text
            s.story += " " + text
        s.cursor += 1
        if s.cursor < len(ASK_ORDER):
            return _next_question(s, ASK_ORDER[s.cursor])
        return _analyze(s)

    if s.state in ("drafted", "refused"):
        low = text.lower()
        if any(k in low for k in ("file it", "file the appeal", "go ahead", "yes, file", "please file")):
            if s.state == "drafted":
                return _file(s)
            q = "I haven't drafted an appeal because the policy didn't support one. Nothing has been filed."
            return {"session_id": sid, "state": s.state, "say": voice.speak(q), "transcript": q}
        if s.state == "drafted":
            q = ("Just say 'file it' when you're ready, or tell me what to change. "
                 "I won't submit anything until you do.")
        else:
            q = ("If you'd like, I can connect you to the number on your denial letter. "
                 "Nothing has been filed.")
        return {"session_id": sid, "state": s.state, "say": voice.speak(q), "transcript": q}

    q = "I'm here. Tell me about your denial."
    return {"session_id": sid, "state": s.state, "say": voice.speak(q), "transcript": q}


def _analyze(s: Session) -> dict:
    """Match the story to policy, decide support, draft the appeal or refuse."""
    s.state = "analyzing"
    _log(s, "match_policy", "ok", "matching story to policy library")
    scenario = policies.find_scenario(s.story)

    if not scenario:
        s.state = "refused"
        q = ("I've listened carefully, but I couldn't match your denial to the "
             "policies I know. I don't want to guess with something this "
             "important, so I won't file anything. Here's what I'd suggest: call "
             "your plan directly, or use the number on your denial letter. "
             "Nothing has been filed.")
        _log(s, "refuse_no_match", "refused", "no policy match; fail closed")
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

    s.data["appeal_text"] = scenario["best_argument"]
    s.scenario_id = scenario["id"]
    s.state = "drafted"
    _log(s, "draft_appeal", "ok", "drafted appeal citing %s" % pol["cpb"])
    store.record_run("appealmate", "drafted", s.session_id)

    q = ("I've drafted your appeal, and before we do anything I want to read it "
         "to you. %s That's the heart of it. Would you like me to file it, or "
         "change something first? Say 'file it' when you're ready." % s.data["appeal_text"])
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
    """Produce the filled Aetna Medicare Part C appeal form fields."""
    conf = "AM-" + hashlib.sha1((s.session_id + str(time.time())).encode()).hexdigest()[:8].upper()
    form = {"confirmation": conf, "fields": []}
    for fid, label, _src in policies.FORM_FIELDS:
        form["fields"].append({"id": fid, "label": label, "value": s.data.get(fid, "")})
    return form


def get_session(sid: str) -> dict | None:
    s = _load(sid)
    if not s:
        return None
    return {"session_id": s.session_id, "state": s.state, "data": s.data,
            "scenario_id": s.scenario_id, "trace": s.trace()}
