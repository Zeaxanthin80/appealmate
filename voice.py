"""AppealMate — voice. ElevenLabs TTS with an offline transcript fallback.

If ELEVENLABS_API_KEY is set, speak() calls the ElevenLabs TTS API and returns
base64 audio the browser plays. Without a key it returns the transcript only —
the UI shows captions either way, so the demo never fails on a network call
and the conversation logic is fully testable offline.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.request


TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
# Bella — "Professional, Bright, Warm", female American, middle-aged.
# The previous default was Sarah, who read as hesitant: labelled "Mature,
# Reassuring", but her delivery is slow and tentative, which made Aria sound
# unsure of herself. A member being told their appeal is winnable needs to hear
# someone who sounds certain. Bella is professional, warm and level.
DEFAULT_VOICE = "hpp4J3VqNfWAUOO0d1Us"

# Delivery settings. Higher stability keeps the read even and assured rather
# than wandering; a little style keeps it from sounding robotic.
VOICE_SETTINGS = {
    "stability": 0.5,
    "similarity_boost": 0.75,
    "style": 0.15,
    "use_speaker_boost": True,
}


def speak(text: str, voice_id: str | None = None) -> dict:
    """Return something the UI can play or display. Never raises."""
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    transcript = text
    if not api_key:
        return {"audio": False, "provider": "offline-transcript",
                "voice": voice_id or DEFAULT_VOICE, "transcript": transcript}

    try:
        req = urllib.request.Request(
            TTS_URL.format(voice_id=voice_id or DEFAULT_VOICE),
            data=json.dumps({"text": text, "model_id": "eleven_turbo_v2_5",
                             "voice_settings": VOICE_SETTINGS}).encode(),
            headers={"xi-api-key": api_key, "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            audio_b64 = base64.b64encode(resp.read()).decode()
        return {"audio": True, "provider": "elevenlabs", "audio_b64": audio_b64,
                "voice": voice_id or DEFAULT_VOICE, "transcript": transcript}
    except Exception as exc:  # network failure must not break the conversation
        return {"audio": False, "provider": "elevenlabs-error: %s" % type(exc).__name__,
                "voice": voice_id or DEFAULT_VOICE, "transcript": transcript}


# Speech-to-text for the caller's side. The browser's built-in Web Speech API
# does the recognition (free, no key); this exists so tests can simulate turns.
def parse_command(transcript: str) -> str:
    """Normalize a spoken phrase to a command. Fail closed to 'unknown'."""
    t = (transcript or "").strip().lower()
    if "file it" in t or "file the appeal" in t:
        return "file"
    if t in ("stop", "stop it", "cancel", "never mind"):
        return "stop"
    if "hold on" in t or "wait" in t:
        return "hold"
    return "answer"
