"""AppealMate — turning a patient's own story into an appeal argument.

The policy bulletins in policies.py say what the plan must cover. This module
does the other half: it works out which facts the plan's criteria actually turn
on, asks the patient for those facts in plain language, and writes the argument
out of the patient's own answers.

Why an interview rather than a template: CPB 0228 does not cover "a heart scan"
in the abstract — it covers a person at intermediate pre-test probability whose
stress test was equivocal, or who cannot exercise. Which of those applies is a
question only the patient can answer. A generated template would claim all of
them for everyone, which is both weaker and dishonest if the facts are not
there.

Two rules govern the writing:

1. A piece of evidence appears only if the patient supplied it. Missing facts
   are listed as items for the plan to verify from its own records, never
   asserted.
2. The argument quotes the plan's own criteria back at it, because the strongest
   appeal is not "please reconsider" but "your denial contradicts your policy".
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Interview scripts
#
# Each entry is (fact_id, spoken question). The question is written to be
# answerable by someone who is unwell, and every one can be answered "I don't
# know" without harming the appeal.
#
# The fact ids are the joins between this file, the composer below, and the
# policy criteria in policies.py. Change one, change all three.
# ---------------------------------------------------------------------------

INTERVIEWS = {
    "scan-1": [
        ("symptoms",
         "What symptoms made your doctor order this scan? Tell me what you've "
         "been feeling."),
        ("prior_test",
         "Before this scan, did you have a stress test or a treadmill test? "
         "What did it show?"),
        ("can_exercise",
         "Can you walk on a treadmill for a stress test now, or does something "
         "stop you?"),
        ("family_history",
         "Does heart disease run in your family?"),
    ],
    "scan-2": [
        ("condition",
         "What surgery or injury are you recovering from?"),
        ("deficits",
         "What can't you do now that you could do before — walking, stairs, "
         "getting dressed?"),
        ("change",
         "Has anything changed recently? A fall, or the progress stopping?"),
        ("goals",
         "What does your therapist say you still need to work on?"),
    ],
    "scan-3": [
        ("limitations",
         "What can't she do without someone helping her?"),
        ("transfers",
         "Can she get in and out of a chair, or onto a scooter, on her own?"),
        ("upper_body",
         "Does she have the strength and steadiness in her hands and arms to "
         "steer a scooter?"),
        ("goals",
         "What does she need to do at home that she can't do right now?"),
    ],
}

# Phrases that mean "no answer". Kept here too so the composer can decide
# whether a fact is usable without importing the agent's copy.
_BLANK = {"", "not provided", "i don't know", "dont know", "not sure",
          "no", "none", "n/a", "na", "unknown", "nothing"}


def _usable(value: str | None) -> bool:
    return bool(value) and str(value).strip().lower() not in _BLANK


def _sentence(value: str) -> str:
    """Tidy a spoken answer into something that reads well in a letter."""
    v = str(value).strip().rstrip(".")
    if not v:
        return v
    return v[0].upper() + v[1:] + "."


def _first_person(value: str) -> str:
    """Convert a patient's spoken answer to first person for the letter."""
    v = str(value).strip().rstrip(".")
    swaps = [
        ("my ", "my "), ("she ", "she "),
        ("i am", "I am"), ("i'm", "I am"), ("i have", "I have"),
        ("i can't", "I cannot"), ("i cant", "I cannot"),
        ("i cannot", "I cannot"), ("i don't", "I do not"),
        ("i dont", "I do not"), ("my ", "my "),
    ]
    low = v.lower()
    for a, b in swaps:
        if low.startswith(a):
            v = b + v[len(a):]
            break
    else:
        if v and v[0].islower():
            v = v[0].upper() + v[1:]
    return v


def compose(scenario_id: str, facts: dict, service: str,
            denial_reason: str = "") -> str:
    """Build the Comments text for the appeal from the patient's own answers.

    Returns a letter the patient can read, edit and paste into the plan's form.
    Facts the patient could not supply are gathered into a short list of items
    for the plan to confirm from its records, rather than being asserted.
    """
    composer = _COMPOSERS.get(scenario_id)
    if not composer:
        # Unknown scenario: state the request without inventing support.
        return (
            "I am appealing the plan's denial of %s. The reason given was: %s. "
            "I am requesting that the plan review this decision and provide the "
            "specific coverage criteria that were applied, along with the "
            "records relied upon, so that I can respond to them."
            % (service, denial_reason or "not stated in the denial letter")
        )
    return composer(facts, service, denial_reason)


# ---------------------------------------------------------------------------
# Per-scenario composition. Each writer maps the patient's answers onto the
# criteria of the corresponding CPB, and quotes the plan's own language.
# ---------------------------------------------------------------------------

def _compose_scan_1(f: dict, service: str, denial_reason: str) -> str:
    """CPB 0228 — Coronary CT Angiography."""
    parts = ["I am appealing the denial of %s." % service]
    if _usable(denial_reason):
        parts.append("The denial stated: \u201c%s\u201d" % _sentence(denial_reason).rstrip("."))
    parts.append(
        "The plan's own clinical coverage criteria, CPB 0228, provide that "
        "coronary CT angiography is medically necessary for a symptomatic person "
        "at intermediate pre-test probability of coronary artery disease, and "
        "specifically where the person has \u201can equivocal or uninterpretable "
        "exercise or pharmacological stress test.\u201d The same bulletin states "
        "that \u201cexercise stress testing is not useful in persons who are "
        "unable to exercise.\u201d"
    )

    # Each fact is stated together with the criterion it satisfies, so the
    # letter reads as an argument rather than a dump followed by conclusions.
    grounded, to_verify = [], []

    if _usable(f.get("symptoms")):
        grounded.append(
            "I am symptomatic as the criteria require. %s"
            % _sentence(_first_person(f["symptoms"]))
        )
    else:
        to_verify.append("the symptoms recorded by my doctor at the time of the order")

    if _usable(f.get("prior_test")):
        grounded.append(
            "I fall within the bulletin's first alternative, an equivocal or "
            "uninterpretable stress test. %s"
            % _sentence(_first_person(f["prior_test"]))
        )
    else:
        to_verify.append("the results of any prior stress or functional testing")

    if _usable(f.get("can_exercise")):
        grounded.append(
            "I also fall within the bulletin's statement that exercise stress "
            "testing is not useful in persons who are unable to exercise. %s"
            % _sentence(_first_person(f["can_exercise"]))
        )
    else:
        to_verify.append("my documented exercise capacity or limitation")

    if _usable(f.get("family_history")):
        grounded.append(
            "This risk factor supports the intermediate pre-test probability the "
            "criteria assume. %s" % _sentence(_first_person(f["family_history"]))
        )
    else:
        to_verify.append("my pre-test probability as calculated under the bulletin")

    parts.extend(grounded)
    if to_verify:
        parts.append(
            "The plan is asked to confirm from its own records: %s."
            % "; ".join(to_verify)
        )

    parts.append(
        "On the facts above, the criteria in CPB 0228 are satisfied and the "
        "service should be covered. I am requesting that the plan reverse this "
        "denial and authorize %s, and that it identify in writing which specific "
        "criterion it contends is not met." % service
    )
    return "\n\n".join(parts)


def _compose_scan_2(f: dict, service: str, denial_reason: str) -> str:
    """CPB 0325 — Physical Therapy."""
    parts = ["I am appealing the denial of %s." % service]
    if _usable(denial_reason):
        parts.append("The denial stated: \u201c%s\u201d" % _sentence(denial_reason).rstrip("."))
    parts.append(
        "CPB 0325 provides that physical therapy is medically necessary \u201cto "
        "significantly improve, develop or restore physical functions lost or "
        "impaired as a result of a disease, injury or surgical procedure.\u201d "
        "The bulletin's 60-day treatment period \u201capplies to a specific "
        "condition.\u201d"
    )

    grounded, to_verify = [], []

    if _usable(f.get("condition")):
        grounded.append(
            "My therapy follows a surgical procedure, which is the circumstance "
            "the criteria address. %s" % _sentence(_first_person(f["condition"]))
        )
    else:
        to_verify.append("the operative or treating diagnosis")

    if _usable(f.get("deficits")):
        grounded.append(
            "I have functional losses of the kind the bulletin describes, and "
            "they are not yet restored. %s"
            % _sentence(_first_person(f["deficits"]))
        )
    else:
        to_verify.append("the functional limitations documented by my therapist")

    if _usable(f.get("change")):
        grounded.append(
            "Because the 60-day period applies to a specific condition, the "
            "following change begins a new treatment period. %s"
            % _sentence(_first_person(f["change"]))
        )
    else:
        to_verify.append("the date and nature of any change in my condition")

    if _usable(f.get("goals")):
        grounded.append(
            "Therapy therefore remains restorative, directed at gains not yet "
            "achieved, rather than maintenance of a plateau. %s"
            % _sentence(_first_person(f["goals"]))
        )
    else:
        to_verify.append("the remaining goals in my plan of care")

    parts.extend(grounded)
    if to_verify:
        parts.append(
            "The plan is asked to confirm from its own records: %s."
            % "; ".join(to_verify)
        )

    parts.append(
        "The criteria in CPB 0325 are satisfied and the requested visits should "
        "be covered. I am requesting reversal of this denial and authorization "
        "of %s." % service
    )
    return "\n\n".join(parts)


def _compose_scan_3(f: dict, service: str, denial_reason: str) -> str:
    """CPB 0271 — Wheelchairs and Power Operated Vehicles."""
    parts = ["I am appealing the denial of %s." % service]
    if _usable(denial_reason):
        parts.append("The denial stated: \u201c%s\u201d" % _sentence(denial_reason).rstrip("."))
    parts.append(
        "CPB 0271 provides that a power mobility device is medically necessary "
        "where the member has a mobility limitation that significantly impairs "
        "one or more mobility-related activities of daily living in the home, and "
        "lacks sufficient upper extremity function to self-propel a manual "
        "wheelchair. A scooter is appropriate only where the member can transfer "
        "safely, sit upright with adequate trunk control, and operate the tiller."
    )

    grounded, to_verify = [], []

    if _usable(f.get("limitations")):
        grounded.append(
            "There is a limitation in mobility-related activities of daily living "
            "in the home, which is the criterion the bulletin sets. %s"
            % _sentence(_first_person(f["limitations"]))
        )
    else:
        to_verify.append("the mobility limitation as documented in the evaluation")

    if _usable(f.get("transfers")):
        grounded.append(
            "A scooter therefore is not appropriate, because it requires the "
            "member to transfer safely and to sit upright with trunk control. %s"
            % _sentence(_first_person(f["transfers"]))
        )
    else:
        to_verify.append("the ability to transfer safely")

    if _usable(f.get("upper_body")):
        grounded.append(
            "This bears on the criterion concerning sufficient upper extremity "
            "function to self-propel a manual wheelchair and to operate a "
            "tiller. %s" % _sentence(_first_person(f["upper_body"]))
        )
    else:
        to_verify.append("upper extremity strength and coordination")

    if _usable(f.get("goals")):
        grounded.append(
            "The home activities affected are as follows. %s"
            % _sentence(_first_person(f["goals"]))
        )

    parts.extend(grounded)
    if to_verify:
        parts.append(
            "The plan is asked to confirm from its own records: %s."
            % "; ".join(to_verify)
        )

    parts.append(
        "On these facts the criteria in CPB 0271 are met and the requested "
        "equipment should be covered. I am requesting reversal of this denial."
    )
    return "\n\n".join(parts)


_COMPOSERS = {
    "scan-1": _compose_scan_1,
    "scan-2": _compose_scan_2,
    "scan-3": _compose_scan_3,
}


def interview_for(scenario_id: str) -> list[tuple[str, str]]:
    """The (fact_id, question) list for a scenario, or empty if unknown."""
    return INTERVIEWS.get(scenario_id, [])
