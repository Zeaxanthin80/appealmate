"""AppealMate — tests. Happy path, refusal path, stop path, and the form.

Run:  python -m unittest test_appealmate -v   (from the appealmate/ directory)
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

    def test_unrelated_story_fails_closed(self):
        s = policies.find_scenario(
            "Hello I would like to order a large pepperoni pizza please to my house"
        )
        self.assertIsNone(s)


class TestFullConversation(unittest.TestCase):
    """Walk a complete happy-path conversation and check every turn."""

    def setUp(self):
        agent.SESSIONS.clear()
        self.start = agent.start_session()
        self.sid = self.start["session_id"]

    def _say(self, text):
        return agent.send(self.sid, text)

    def test_intro_is_safe_and_warm(self):
        t = self.start["transcript"]
        self.assertIn("Aria", t)
        self.assertIn("your name", t)             # asks for name
        self.assertTrue("stop" in t or "Stop" in t)  # tells caller they can stop

    def test_happy_path_collects_fields_and_drafts(self):
        r = self._say("Maria Fernandez")
        self.assertEqual(r["state"], "asking")
        r = self._say("A123456789")
        r = self._say("Aetna Medicare Prime")
        r = self._say("a heart CT scan")
        r = self._say("September 10th")
        r = self._say("they said it wasn't medically necessary, stress test first")
        r = self._say("Dr. Rodriguez")
        # last answer triggers analysis
        self.assertEqual(r["state"], "drafted")
        self.assertFalse(r["refused"])
        self.assertIn("CT", r["appeal_text"] + self.sid)  # appeal drafted
        self.assertIn("CPB", r["policy_citation"])  # cites a real CPB

    def test_file_only_after_consent(self):
        self._say("Maria Fernandez")
        self._say("A123456789")
        self._say("Aetna Medicare Prime")
        self._say("a heart CT scan")
        self._say("September 10th")
        self._say("they said it wasn't medically necessary, stress test first")
        r = self._say("Dr. Rodriguez")
        self.assertEqual(r["state"], "drafted")
        # Not "file it" -> must NOT file
        r = self._say("sounds good")
        self.assertNotEqual(r["state"], "filed")
        # Explicit consent -> files
        r = self._say("file it")
        self.assertEqual(r["state"], "filed")
        self.assertIn("form", r)
        self.assertTrue(r["form"]["confirmation"].startswith("AM-"))
        # form contains the derived appeal text
        fields = {f["id"]: f["value"] for f in r["form"]["fields"]}
        self.assertIn("The denial", fields["appeal_text"])

    def test_stop_word_works_immediately(self):
        self._say("Maria Fernandez")
        r = self._say("stop")
        self.assertEqual(r["state"], "stopped")
        # and nothing was filed
        sess = agent.get_session(self.sid)
        self.assertNotEqual(sess["state"], "filed")


class TestRefusalPath(unittest.TestCase):
    """The fail-closed behavior: no policy match -> refuse, file nothing."""

    def test_gibberish_story_refuses(self):
        agent.SESSIONS.clear()
        start = agent.start_session()
        sid = start["session_id"]
        # Fill all fields with an unrelated story
        for text in ("Sam Smith", "Z999999999", "Some Other Plan",
                     "a hot tub", "last Tuesday", "no reason given",
                     "Dr. Who"):
            r = agent.send(sid, text)
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
