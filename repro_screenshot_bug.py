"""Reproduce the exact scenario from the user's screenshot.

Their transcript was:
  Aria: When did you get the denial letter?   You: 2 days ago
  Aria: What reason did the letter give?      You: I don't know
  Aria: And what's the name of the doctor?    You: Dr Richard Crespo
  Aria: (refused - "I couldn't match your denial to the policies I know")

It must now reach a drafted appeal with the argument in the Comments field.
"""
import sys
sys.path.insert(0, ".")
import agent  # noqa: E402

agent.SESSIONS.clear()
sid = agent.start_session()["session_id"]
print("ARIA:", agent.start_session()["transcript"][:70] + "...")

turns = [
    "Maria Fernandez",
    "A123456789",
    "a heart CT scan. They denied it because they said I need a stress test "
    "first, but my stress test was inconclusive and I can't exercise because "
    "of my knees",
    "I don't know",              # <- the answer that broke it
]
for t in turns:
    r = agent.send(sid, t)
    print("\nYOU :", t)
    print("ARIA:", r["transcript"][:150].replace("\n", " "), "...")
    print("     state:", r["state"])

print("\n" + "=" * 60)
print("FINAL STATE:", agent.get_session(sid)["state"])

form = agent.generate_form(agent._load(sid))
print("CONFIRMATION:", form["confirmation"])
print("MISSING REQUIRED:", form["missing_required"] or "none")
print("\nFORM FIELDS:")
for f in form["fields"]:
    val = f["value"] or "(blank)"
    print("  %-22s req=%-5s %s" % (f["id"], f["required"], val[:70]))

comments = [f for f in form["fields"] if f["id"] == "comments"][0]
ok = bool(comments["value"]) and "CPB 0228" in comments["value"]
print("\nCOMMENTS POPULATED WITH ARGUMENT:", ok)
print("RESULT:", "PASS - the screenshot bug is fixed" if ok else "FAIL")
sys.exit(0 if ok else 1)
