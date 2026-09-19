"""Live check: does the real ElevenLabs key produce audio through voice.py?

Spends a small number of characters (the intro only). Exits non-zero if the
key is missing or the API rejects the request, so this is real evidence rather
than an assumption.
"""
import base64
import os
import sys

sys.path.insert(0, ".")
import voice  # noqa: E402

print("ELEVENLABS_API_KEY present in this shell: %s" % bool(os.environ.get("ELEVENLABS_API_KEY")))

result = voice.speak("Hello, I'm Aria. I'm here to help you appeal your denial.")
print("provider      :", result.get("provider"))
print("audio present :", result.get("audio"))
print("voice id      :", result.get("voice"))
print("transcript    :", result.get("transcript", "")[:60])

if not result.get("audio"):
    print("\nRESULT: FAIL - no audio was produced (see provider above)")
    sys.exit(1)

raw = base64.b64decode(result["audio_b64"])
print("audio bytes   :", len(raw))
print("looks like MP3:", raw[:3] == b"ID3" or raw[:2] == b"\xff\xfb")

out = "voice_sample.mp3"
with open(out, "wb") as f:
    f.write(raw)
print("saved         :", out)

ok = len(raw) > 2000 and (raw[:3] == b"ID3" or raw[:2] == b"\xff\xfb")
print("\nRESULT: %s" % ("PASS - real audio generated" if ok else "FAIL - audio looks malformed"))
sys.exit(0 if ok else 1)
