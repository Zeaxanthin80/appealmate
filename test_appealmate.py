"""AppealMate — tests. Happy path, refusal path, stop path, and the form.

Run:  python run_tests.py   (from the appealmate/ directory)

Two tests exist specifically because a real member hit these bugs:
  * test_unknown_denial_reason_does_not_block — the member answered "I don't
    know" and the agent refused to help.
  * test_terse_answer_gets_a_clarifying_question — a short answer triggered a
    dead-stop refusal instead of one follow-up question.
"""

from __future__ import annotations

import unittest

import agent
import policies
import voice


class TestScenarioMatching(unittest.TestCase):
    def test_heart_scan_story_matches(self):
        s = policies.find_scenario(
            "My doctor ordered a CT angiography because I have chest pain when I walk "
            "and my brother died of a heart attack at 58. They denied it because they "
            "said I need a stress test first, but mine was inconclusive and I can't "
            "exercise because of my knees."
        )
        self.assertIsNotNone(s)
        self.assertEqual(s["id"], "scan-1")

    def test_pt_story_matches(self):
        s = policies.find_scenario(
            "They denied more physical therapy after my hip replacement. They said I hit "
            "my session cap. My therapist wrote a note that I still need twelve more "
            "visits because I keep falling."
        )
        self.assertIsNotNone(s)
        self.assertEqual(s["id"], "scan-2")

    def test_wheelchair_story_matches(self):
        s = policies.find_scenario(
            "They denied the motorized wheelchair for my mother. They said a scooter "
            "would be enough, but she can't sit up safely on a scooter and she has "
            "tremors in her hands so she can't steer it."
        )
        self.assertIsNotNone(s)
        self.assertEqual(s["id"], "scan-3")

    def test_short_answers_still_match(self):
        """A member who speaks in a few words must still be helped."""
        s = policies.find_scenario("denied my wheelchair")
        self.assertIsNotNone(s)
        self.assertEqual(s["id"], "scan-3")

    def test_unrelated_story_fails_closed(self):
        s = policies.find_scenario(
            "Hello I would like to order a large pepperoni pizza please to my house"
        )
        self.assertIsNone(s)


class TestUnknownAnswers(unittest.TestCase):
    """The member rarely knows everything. Ignorance must not cost them."""

    def test_is_unknown_recognises_real_phrasings(self):
        for phrase in ["I don't know", "i dont know", "not sure", "I'm not sure",
                       "no idea", "I forget", "can't remember", "dunno", "", "  "]:
            self.assertTrue(agent.is_unknown(phrase), "should be unknown: %r" % phrase)

    def test_is_unknown_does_not_swallow_real_answers(self):
        for phrase in ["they said it wasn't medically necessary",
                       "the letter said I need a stress test first",
                       "denied for no good reason"]:
            self.assertFalse(agent.is_unknown(phrase), "should be an answer: %r" % phrase)

    def test_unknown_denial_reason_does_not_block(self):
        """The exact bug from the screenshot: the member knows only the basics."""
        agent.SESSIONS.clear()
        sid = agent.start_session()["session_id"]
        agent.send(sid, "Maria Fernandez")
        agent.send(sid, "A123456789")
        r = agent.send(sid, "a heart CT scan, denied because they said a stress test "
                            "should come first but mine was inconclusive and I can't "
                            "exercise because of my knees")
        # The descriptive answer is enough to move to the optional questions.
        self.assertNotEqual(r["state"], "refused")

    def test_optional_questions_accept_i_dont_know(self):
        """The screenshot scenario: skip both optional questions, still proceed."""
        agent.SESSIONS.clear()
        sid = agent.start_session()["session_id"]
        agent.send(sid, "Maria Fernandez")
        agent.send(sid, "A123456789")
        r = agent.send(sid, "a heart CT scan, denied because they said a stress test "
                            "should come first but mine was inconclusive and I can't "
                            "exercise because of my knees")
        self.assertEqual(r["state"], "asking")
        self.assertEqual(r["field"], "provider_requested")
        r = agent.send(sid, "I don't know")           # provider — unknown
        self.assertEqual(r["state"], "asking")
        self.assertEqual(r["field"], "was_denied")
        r = agent.send(sid, "I don't know")           # was denied — unknown
        # The optional questions are skipped and the policy interview begins.
        self.assertEqual(r["state"], "interview")
        self.assertFalse(r.get("refused", False))


class TestClarifyingQuestion(unittest.TestCase):
    """Refusal must come after one clarifying question, never instead of it."""

    def test_terse_answer_gets_a_clarifying_question(self):
        agent.SESSIONS.clear()
        sid = agent.start_session()["session_id"]
        agent.send(sid, "Sam")
        agent.send(sid, "A1")
        agent.send(sid, "they denied something")   # too thin to match
        # The two optional questions come first, both skippable.
        agent.send(sid, "I don't know")
        r = agent.send(sid, "I don't know")
        # Only then, with the story still unmatched, does Aria ask to clarify
        # rather than refusing outright.
        self.assertEqual(r["state"], "clarifying")
        self.assertIn("?", r["transcript"])

    def test_clarifying_answer_can_still_match(self):
        agent.SESSIONS.clear()
        sid = agent.start_session()["session_id"]
        agent.send(sid, "Sam")
        agent.send(sid, "A1")
        agent.send(sid, "they denied something")
        agent.send(sid, "I don't know")
        agent.send(sid, "I don't know")
        r = agent.send(sid, "it was a wheelchair for my mother")
        self.assertNotEqual(r["state"], "refused")


class TestFullConversation(unittest.TestCase):
    """Walk a complete happy-path conversation and check every turn."""

    def setUp(self):
        agent.SESSIONS.clear()
        self.start = agent.start_session()
        self.sid = self.start["session_id"]

    def _say(self, text):
        return agent.send(self.sid, text)

    def _to_interview(self, story=None):
        """Drive the required + optional questions, stopping at the interview."""
        self._say("Maria Fernandez")
        self._say("A123456789")
        r = self._say(story or (
            "a heart CT scan, they said it wasn't medically necessary and a "
            "stress test should come first, but my stress test was inconclusive "
            "and I cannot exercise because of my knees"))
        if r["state"] == "asking" and r.get("field") == "provider_requested":
            self._say("Dr. Rodriguez")
            r = self._say("yes, it was denied")
        return r

    def _finish_interview(self, answers=None):
        """Answer interview questions until the state leaves 'interview'."""
        answers = list(answers or [])
        while True:
            text = answers.pop(0) if answers else "I don't know"
            r = self._say(text)
            if r["state"] != "interview":
                return r

    def test_intro_is_confident_and_promises_consent(self):
        """The intro must sound certain, and still promise no filing without consent.

        An earlier version said "we'll take this one step at a time" and "you can
        tell me to stop at any moment" — accurate, but hesitant, which is the
        opposite of what someone just denied needs to hear. The stop capability
        is unchanged and is covered by test_stop_word_works_immediately.
        """
        t = self.start["transcript"]
        self.assertIn("Aria", t)
        self.assertIn("your name", t)
        self.assertIn("won't file", t)          # the consent promise
        for hedge in ("one step at a time", "I'm sorry", "maybe", "I'll try"):
            self.assertNotIn(hedge, t)

    def test_happy_path_collects_fields_and_drafts(self):
        r = self._to_interview()
        # The interview is the new step: Aria asks for the facts her argument
        # will stand on.
        self.assertEqual(r["state"], "interview")
        self.assertTrue(r["transcript"])

        # Answer with the patient's real facts.
        r = self._say("I get chest pain when I walk, and I have to stop")
        self.assertEqual(r["state"], "interview")
        r = self._say("I had a stress test last year, it was inconclusive")
        r = self._say("No, I can't walk on a treadmill, my knees are too bad")
        r = self._say("Yes, my brother died of a heart attack at 58")
        self.assertEqual(r["state"], "drafted")
        self.assertFalse(r["refused"])
        self.assertIn("CPB", r["policy_citation"])
        self.assertIn("0228", r["policy_citation"])

    def test_argument_is_built_from_the_patients_own_words(self):
        """The core of this design: the argument reflects their facts, not a template."""
        self._to_interview()
        self._say("I get chest pain when I walk, and I have to stop")
        self._say("I had a treadmill test last April and it was inconclusive")
        self._say("I cannot walk on a treadmill because of my knees")
        r = self._say("My brother died of a heart attack at 58")
        text = r["appeal_text"]
        # Their specific details appear.
        self.assertIn("chest pain when I walk", text)
        self.assertIn("April", text)           # the date they gave
        self.assertIn("knees", text)
        self.assertIn("brother", text)
        # And the policy it is anchored to.
        self.assertIn("CPB 0228", text)

    def test_facts_the_patient_cannot_supply_are_not_asserted(self):
        """Missing facts become items for the plan to verify, never claimed."""
        self._to_interview()
        r = self._finish_interview()           # answer everything "I don't know"
        self.assertEqual(r["state"], "drafted")
        text = r["appeal_text"]
        # Missing facts are delegated to the plan...
        self.assertIn("asked to confirm from its own records", text)
        # ...and are not invented. The patient never described symptoms, so no
        # symptom claim may appear. (The word "inconclusive" does appear, but only
        # inside the quotation of the plan's own criteria, so we check that no
        # patient-evidence sentence was fabricated.)
        self.assertNotIn("I am symptomatic as the criteria require", text)
        self.assertNotIn("I fall within the bulletin's first alternative", text)
        self.assertNotIn("My symptoms", text)

    def test_comments_field_holds_the_argument(self):
        self._to_interview()
        self._say("chest pain when I walk")
        self._say("my stress test was inconclusive")
        self._say("I cannot exercise because of my knees")
        self._say("my brother had a heart attack")
        self._say("file it")
        form = agent.generate_form(agent._load(self.sid))
        by_id = {f["id"]: f for f in form["fields"]}
        self.assertIn("comments", by_id)
        self.assertTrue(by_id["comments"]["filled"])
        self.assertIn("CPB 0228", by_id["comments"]["value"])
        self.assertEqual(by_id["provider_requested"]["value"], "Dr. Rodriguez")

    def test_file_only_after_consent(self):
        r = self._to_interview()
        r = self._finish_interview(["chest pain", "inconclusive test",
                                    "cannot exercise", "family history"])
        self.assertEqual(r["state"], "drafted")
        r = self._say("sounds good")
        self.assertNotEqual(r["state"], "filed")
        r = self._say("file it")
        self.assertEqual(r["state"], "filed")
        self.assertTrue(r["form"]["confirmation"].startswith("AM-"))

    def test_stop_word_works_immediately(self):
        self._say("Maria Fernandez")
        r = self._say("stop")
        self.assertEqual(r["state"], "stopped")
        sess = agent.get_session(self.sid)
        self.assertNotEqual(sess["state"], "filed")


class TestFormModel(unittest.TestCase):
    """The form must match the real Aetna form and protect the member."""

    def test_provider_and_was_denied_are_not_required(self):
        by_id = {f[0]: f for f in policies.FORM_FIELDS}
        self.assertFalse(by_id["provider_requested"][3],
                         "provider who requested must not be required")
        self.assertFalse(by_id["was_denied"][3],
                         "was the request denied? must not be required")

    def test_comments_is_required_and_derived(self):
        by_id = {f[0]: f for f in policies.FORM_FIELDS}
        self.assertTrue(by_id["comments"][3], "comments must be required")
        self.assertEqual(by_id["comments"][2], "derived")

    def test_unknown_field_stays_blank_not_the_words_not_provided(self):
        """Regression: 'Not provided' was stored as a value and read as filled."""
        agent.SESSIONS.clear()
        sid = agent.start_session()["session_id"]
        agent.send(sid, "Maria Fernandez")
        agent.send(sid, "A123456789")
        agent.send(sid, "a heart CT scan, denied because they said a stress test "
                        "should come first but mine was inconclusive and I can't "
                        "exercise because of my knees")
        agent.send(sid, "I don't know")   # provider
        agent.send(sid, "I don't know")   # was_denied
        # Walk the policy interview, answering nothing.
        for _ in range(6):
            r = agent.send(sid, "I don't know")
            if r["state"] != "interview":
                break
        r = agent.send(sid, "file it")
        by_id = {f["id"]: f for f in r["form"]["fields"]}
        self.assertEqual(by_id["provider_requested"]["value"], "")
        self.assertFalse(by_id["provider_requested"]["filled"],
                         "a blank optional field must not report as filled")
        self.assertEqual(by_id["was_denied"]["value"], "")

    def test_blank_optional_fields_do_not_block_filing(self):
        agent.SESSIONS.clear()
        sid = agent.start_session()["session_id"]
        agent.send(sid, "Maria Fernandez")
        agent.send(sid, "A123456789")
        agent.send(sid, "a heart CT scan, they said it wasn't medically necessary "
                        "and a stress test should come first, but my stress test "
                        "was inconclusive and I cannot exercise because of my knees")
        agent.send(sid, "I don't know")   # provider unknown
        agent.send(sid, "I don't know")   # was_denied unknown
        for _ in range(6):
            r = agent.send(sid, "I don't know")
            if r["state"] != "interview":
                break
        r = agent.send(sid, "file it")
        self.assertEqual(r["state"], "filed")
        # The required fields are filled; the unknowns are simply blank.
        self.assertEqual(r["form"]["missing_required"], [])
        by_id = {f["id"]: f for f in r["form"]["fields"]}
        self.assertEqual(by_id["provider_requested"]["value"], "")
        self.assertFalse(by_id["provider_requested"]["required"])


class TestRefusalPath(unittest.TestCase):
    """Fail-closed: an unmatched story refuses, but only after clarifying."""

    def test_gibberish_story_refuses_after_clarifying(self):
        agent.SESSIONS.clear()
        sid = agent.start_session()["session_id"]
        for text in ("Sam Smith", "Z999999999", "a hot tub"):
            agent.send(sid, text)
        # Optional questions come first; answer them, then the clarifying
        # question is reached when the story still cannot be matched.
        agent.send(sid, "I don't know")
        agent.send(sid, "I don't know")
        r = agent.send(sid, "still nothing related at all")
        self.assertEqual(r["state"], "refused")
        self.assertTrue(r["refused"])
        self.assertIn("Nothing has been filed", r["transcript"])


class TestVoice(unittest.TestCase):
    def test_speak_offline_returns_transcript(self):
        import os
        os.environ.pop("ELEVENLABS_API_KEY", None)
        out = voice.speak("Hello there")
        self.assertFalse(out["audio"])
        self.assertEqual(out["transcript"], "Hello there")

    def test_parse_commands_fail_closed(self):
        self.assertEqual(voice.parse_command("file it please"), "file")
        self.assertEqual(voice.parse_command("stop"), "stop")
        self.assertEqual(voice.parse_command(""), "answer")
        self.assertEqual(voice.parse_command("purple elephant"), "answer")


if __name__ == "__main__":
    unittest.main(verbosity=2)
