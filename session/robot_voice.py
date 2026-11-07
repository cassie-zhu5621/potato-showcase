"""
robot_voice.py -- the robot says a line out of its own speaker (CoreS3, v20).

  from session.robot_voice import RobotVoice
  voice = RobotVoice(link, voice="Zarvox")
  voice.say("OK! I'll look out for a blue water bottle.")    # returns at once

The line is made on the Mac by `say` (a synthetic voice, so it sounds like the
machine rather than a recording of a person), sent to the CoreS3 as a small WAV
in base64 lines, and played from the robot's own speaker -- the sound comes
from the body, which is the point (robot/tools/make_voice.py says why).

11 kHz, 8-bit: the 1 W speaker reproduces nothing above ~5 kHz, and a 2.5 s
line is then ~27 KB -- under a second to send, where 16-bit 16 kHz took three.

One line at a time, in a background thread: a new line replaces one still
being sent. Silently does nothing where `say` does not exist (not a Mac), so
the booth runs anywhere.
"""
from __future__ import annotations

import base64
import os
import shutil
import subprocess
import tempfile
import threading
import time

RATE = 11025
CHUNK = 512            # base64 characters per serial line
PACE_S = 0.008         # between lines: the board drains its serial buffer
                       # every loop (~5 ms); sending faster overruns it


def make_wav(text: str, voice: str = "Zarvox", rate_wpm: int = 175):
    """-> WAV bytes, or None if this machine cannot speak."""
    if not shutil.which("say"):
        return None
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "line.wav")
        for v in (voice, "Samantha", None):          # a missing voice is not fatal
            cmd = ["say", "-r", str(rate_wpm), "-o", out,
                   "--file-format=WAVE", f"--data-format=UI8@{RATE}"]
            if v:
                cmd[1:1] = ["-v", v]
            if subprocess.run(cmd + [text], capture_output=True).returncode == 0:
                break
        else:
            return None
        return open(out, "rb").read()


class RobotVoice:
    def __init__(self, link, voice="Zarvox", muted=False, pace_s=None, chunk=None):
        self.pace_s = PACE_S if pace_s is None else pace_s
        self.chunk = CHUNK if chunk is None else chunk
        self.link = link
        self.voice = voice
        self.muted = muted
        self._gen = 0
        self._lock = threading.Lock()

    def say(self, text: str):
        if not text or self.link is None or self.muted:
            return
        with self._lock:
            self._gen += 1
            gen = self._gen
        threading.Thread(target=self._send, args=(text, gen), daemon=True).start()

    def _send(self, text, gen):
        wav = make_wav(text, self.voice)
        if not wav:
            return
        b64 = base64.b64encode(wav).decode("ascii")
        self.link.event("WAVBEGIN", len(wav))
        time.sleep(0.03)
        for i in range(0, len(b64), self.chunk):
            if gen != self._gen:                 # a newer line replaced this one
                return
            self.link.event("WAVDATA", b64[i:i + self.chunk])
            time.sleep(self.pace_s)
        self.link.event("WAVPLAY")
