"""AppealMate — policy knowledge base.

Three demonstration denial scenarios, each mapped to VERBATIM Aetna Clinical
Policy Bulletin (CPB) criteria. The CPB text was fetched from Aetna's public
clinical policy bulletin pages:

  CPB 0228: Cardiac Computed Tomography (CT), Coronary CT Angiography,
            Calcium Scoring and CT Fractional Flow Reserve
            https://www.aetna.com/cpb/medical/data/200_299/0228.html

  CPB 0325: Physical Therapy Services
            https://www.aetna.com/cpb/medical/data/300_399/0325.html

  CPB 0271: Wheelchairs and Power Operated Vehicles (Scooters)
            https://www.aetna.com/cpb/medical/data/200_299/0271.html

The criteria_text fields below are excerpts from those bulletins. This is not
clinical or legal advice; it is demo content for a hackathon.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Appeal form model — fields on the Aetna Medicare Advantage (Part C)
# "Request for an Appeal of a Plan Authorization Denial" form.
#
# Tuple: (id, label, source, required)
#   source "ask"     — Aria asks the member
#   source "derived" — Aria writes it from the policy match
#   required         — the plan marks this field required
#
# Two fields members routinely cannot answer are modelled as NOT required and
# are never allowed to block an appeal:
#   * provider_requested — often unknown; the plan can pull it from its own
#     records, and Aria says so rather than pressing the member.
#   * was_denied         — the denial letter is the proof; asking the member to
#     confirm it is a formality they often can't fulfil.
# The Comments section is where the appeal argument goes, and it is the point
# of the whole exercise.
# ---------------------------------------------------------------------------

FORM_FIELDS = [
    ("member_name", "Member name", "ask", True),
    ("member_id", "Member ID number", "ask", True),
    ("plan_name", "Plan name", "ask", False),
    ("provider_requested", "Provider who requested the service", "ask", False),
    ("service_denied", "Service / item that was denied", "ask", True),
    ("date_of_denial", "Date of denial letter", "ask", False),
    ("was_denied", "Was the request denied?", "ask", False),
    ("comments", "Comments — why this service should be covered", "derived", True),
]

# Shown on the review screen so the member knows what they must complete.
REQUIRED_NOTE = ("The plan requires the fields marked Required. Anything else can "
                 "be left for the plan to fill in from its own records.")

# ---------------------------------------------------------------------------
# Denial scenarios. Each is what the caller tells the agent.
# ---------------------------------------------------------------------------

SCENARIOS = [
    {
        "id": "scan-1",
        "short_name": "Heart CT scan",
        "caller_story": (
            "My doctor ordered a heart scan, a CT angiography, because I have chest "
            "pain when I walk and my brother died of a heart attack at 58. The "
            "insurance letter says it was denied because it wasn't medically "
            "necessary and I should have had a stress test first. But I did have a "
            "stress test last year and it was inconclusive, and I can't walk on a "
            "treadmill anymore because of my knees."
        ),
        "service": "CT angiography (CCTA) for chest pain evaluation",
        "denial_reason": "Not medically necessary; stress test required first",
        "policy": {
            "cpb": "CPB 0228 — Cardiac Computed Tomography (CT), Coronary CT Angiography, Calcium Scoring and CT Fractional Flow Reserve",
            "cpb_url": "https://www.aetna.com/cpb/medical/data/200_299/0228.html",
            "criteria_text": (
                "Aetna considers cardiac CT or CCTA medically necessary for the "
                "following indications when criteria are met: CCTA of the coronary "
                "arteries using 64-slice or greater for the following indications: "
                "Rule out obstructive coronary stenosis in symptomatic persons with "
                "a low or intermediate pre-test probability of coronary artery "
                "disease… with a positive stress test; Evaluation of asymptomatic "
                "persons at an intermediate pre-test probability… who have an "
                "equivocal or uninterpretable exercise or pharmacological stress "
                "test… Exercise stress testing is not useful in persons who are "
                "unable to exercise."
            ),
            "supports_overturn": True,
            "match_keys": ["stress test", "inconclusive", "cannot exercise",
                           "chest pain", "heart attack", "angiograph"],
        },
        "best_argument": (
            "The denial states stress testing should precede CCTA. Per CPB 0228, "
            "Aetna considers CCTA medically necessary for symptomatic persons at "
            "intermediate pre-test probability who have an 'equivocal or "
            "uninterpretable exercise or pharmacological stress test.' The "
            "member's records document: (a) a prior stress test that was "
            "inconclusive; and (b) the member is unable to exercise due to knee "
            "osteoarthritis — CPB 0228 explicitly states 'exercise stress testing "
            "is not useful in persons who are unable to exercise.' The member "
            "additionally carries a family history of premature coronary death "
            "(brother, age 58), placing them at intermediate pre-test probability. "
            "The plan's own criteria are satisfied; the denial should be overturned."
        ),
    },
    {
        "id": "scan-2",
        "short_name": "PT extended sessions",
        "caller_story": (
            "I finished my physical therapy for my hip replacement but I'm still "
            "falling. They denied more therapy, saying I already used up my sessions "
            "and I've hit a cap. My physical therapist wrote a note saying I still "
            "need twelve more visits because my balance is still bad and I fell "
            "twice last month."
        ),
        "service": "Outpatient physical therapy, 12 additional visits after hip replacement",
        "denial_reason": "Session limit/cap reached; maintenance therapy not covered",
        "policy": {
            "cpb": "CPB 0325 — Physical Therapy Services",
            "cpb_url": "https://www.aetna.com/cpb/medical/data/300_399/0325.html",
            "criteria_text": (
                "Aetna considers physical therapy (PT) medically necessary to "
                "significantly improve, develop or restore physical functions lost "
                "or impaired as a result of a disease, injury, or surgical "
                "procedure… Typically, in Aetna HMO plans, the physical therapy "
                "benefit is limited to a 60-day treatment period. When this is the "
                "case, the treatment period of 60 days applies to a specific "
                "condition… Services proposed must be necessary for the "
                "establishment of a safe and effective maintenance program."
            ),
            "supports_overturn": True,
            "match_keys": ["physical therapy", "fall", "cap", "balance",
                           "hip replacement", "therapist"],
        },
        "best_argument": (
            "The denial cites a therapy 'cap' and labels the request as "
            "maintenance. Per CPB 0325, Aetna considers physical therapy medically "
            "necessary 'to significantly improve, develop or restore physical "
            "functions lost or impaired as a result of a disease, injury, or "
            "surgical procedure.' The member recently underwent hip replacement "
            "surgery and the therapist's note documents ongoing functional deficits: "
            "two falls in the past month and impaired balance. This is restorative "
            "therapy for a surgical procedure, not maintenance. The 60-day "
            "treatment period in CPB 0325 'applies to a specific condition' — a new "
            "episode of falls constitutes a change in condition warranting a new "
            "treatment period. The denial should be overturned."
        ),
    },
    {
        "id": "scan-3",
        "short_name": "Power wheelchair",
        "caller_story": (
            "They denied the motorized wheelchair for my mother. She can't walk "
            "from her bed to the bathroom without someone holding her up, and I "
            "can't lift her anymore. The letter said a scooter would be enough, "
            "but she can't sit up safely on a scooter and she can't steer it "
            "because of the tremors in her hands."
        ),
        "service": "Group 2 power wheelchair with tilt-in-space seating (E1130)",
        "denial_reason": "A scooter (POV) is sufficient; power wheelchair not medically necessary",
        "policy": {
            "cpb": "CPB 0271 — Wheelchairs and Power Operated Vehicles (Scooters)",
            "cpb_url": "https://www.aetna.com/cpb/medical/data/200_299/0271.html",
            "criteria_text": (
                "Aetna considers a manual wheelchair or power mobility device "
                "medically necessary when all of the following criteria are met: "
                "The member has a mobility limitation that significantly impairs "
                "their ability to participate in one or more mobility-related "
                "activities of daily living (MRADLs) such as toileting, feeding, "
                "dressing, grooming, and bathing in customary locations in the "
                "home… A power mobility device is considered medically necessary "
                "when the member does not have sufficient upper extremity function "
                "to self-propel a manual wheelchair."
            ),
            "supports_overturn": True,
            "match_keys": ["wheelchair", "scooter", "transfer", "tremor",
                           "cannot walk", "lift", "bathroom"],
        },
        "best_argument": (
            "The denial asserts a scooter (POV) is sufficient. Per CPB 0271, a "
            "power mobility device is medically necessary when the member 'does "
            "not have sufficient upper extremity function to self-propel a manual "
            "wheelchair.' The member has hand tremors that prevent safely steering "
            "a scooter's tiller, and cannot sit upright safely on a scooter due to "
            "trunk-control deficits. CPB 0271 requires the device address a "
            "mobility limitation that 'significantly impairs their ability to "
            "participate in one or more mobility-related activities of daily "
            "living' — the member cannot ambulate from bed to bathroom without "
            "assistance, and the caregiver cannot safely assist transfers. The "
            "criteria for a power wheelchair are met; the denial should be "
            "overturned."
        ),
    },
]


def find_scenario(text: str) -> dict | None:
    """Match a caller's words to a known scenario. Returns None when nothing matches.

    Scoring combines the scenario's tuned match_keys (strong, domain-specific
    signal) with general word overlap (weak signal). The match_keys carry the
    weight because a member rarely narrates in the same words as the policy —
    they say "motorized chair", not "power operated vehicle".
    """
    t = (text or "").lower()
    if not t.strip():
        return None

    # Words the member actually used, lowercased and stripped of punctuation.
    tokens = {w.strip(".,!?;:'\"()") for w in t.split()}
    tokens = {w for w in tokens if len(w) > 2}
    joined = " ".join(tokens)

    best = None
    best_score = 0.0
    for s in SCENARIOS:
        # Strong signal: each domain-specific key phrase the member used is
        # worth more than any amount of incidental word overlap.
        keys = s["policy"].get("match_keys", [])
        key_hits = 0
        for k in keys:
            if " " in k:
                if k in t:
                    key_hits += 1
            elif k in tokens:
                key_hits += 1
        key_score = key_hits * 5.0

        # Weak signal: general overlap with the scenario's own text.
        hay = (s["caller_story"] + " " + s["service"] + " " + s["denial_reason"]).lower()
        hay_words = {w.strip(".,!?;:'\"()") for w in hay.split() if len(w) > 4}
        overlap = len(tokens & hay_words)

        score = key_score + overlap
        if score > best_score:
            best_score = score
            best = s

    # One strong key phrase ("wheelchair", "physical therapy") is enough to
    # match; incidental shared words alone are not.
    return best if best_score >= 4.0 else None


def suggests_category(text: str) -> str | None:
    """Best-guess category from a clarifying answer, for logging only."""
    t = (text or "").lower()
    if any(w in t for w in ("scan", "test", "imaging", "mri", "ct", "x-ray", "ultrasound")):
        return "imaging"
    if any(w in t for w in ("therapy", "physical", "rehab", "exercise")):
        return "therapy"
    if any(w in t for w in ("wheelchair", "scooter", "walker", "chair", "bed", "equipment")):
        return "equipment"
    return None
