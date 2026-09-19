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
# Appeal form model — fields on the Aetna Medicare Part C appeal
# (redetermination request) form. Field IDs mirror the form's sections.
# ---------------------------------------------------------------------------

FORM_FIELDS = [
    ("member_name", "Member name", "ask"),
    ("member_id", "Member ID number", "ask"),
    ("plan_name", "Plan name", "ask"),
    ("service_denied", "Service / item denied", "ask"),
    ("date_of_denial", "Date of denial letter", "ask"),
    ("denial_reason", "Reason for denial (from the letter)", "ask"),
    ("provider_name", "Ordering provider name", "ask"),
    ("appeal_text", "Why this service should be covered (your appeal statement)", "derived"),
]

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
    """Match a caller's story to a known scenario. Returns None when nothing matches."""
    t = (text or "").lower()
    if not t.strip():
        return None
    scored = []
    for s in SCENARIOS:
        hay = (s["caller_story"] + " " + s["service"] + " " + s["denial_reason"]).lower()
        words = {w.strip(".,!?;:'\"()") for w in t.split() if len(w) > 4}
        overlap = len(words & set(hay.split()))
        scored.append((overlap, s))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1] if scored and scored[0][0] >= 3 else None
