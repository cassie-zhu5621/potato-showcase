"""
robot_voice.py -- the robot says a line out of its own speaker (CoreS3, v20).

  from session.robot_voice import RobotVoice
  voice = RobotVoice(link, voice="Samantha")
  voice.say("OK! I'll look out for a blue water bottle.")    # returns at once

The line is made on the Mac by `say` (a synthetic voice, so it sounds like the
machine rather than a recording of a person), sent to the CoreS3 as a small WAV
in base64 lines, and played from the robot's own speaker -- the sound comes
from the body, which is the point (robot/tools/make_voice.py says why).

8 kHz, 8-bit: the 1 W speaker reproduces nothing above ~4 kHz, and a 3 s line
is then ~24 KB.

FLOW CONTROL (v21). The board's USB receive buffer is ~256 bytes, so lines are
kept under that and each one waits for the board's IN WAVACK before the next.
v20 sent back to back, overran the buffer, and played nothing; paced sending
(no acks) worked but took 12 s for one line.

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

RATE = 8000           # the 1 W speaker has nothing above ~4 kHz to give
CHUNK = 200            # base64 characters per line: line < 256 bytes, the
                       # board's USB receive buffer (v20 sent 512 and lost it)
PACE_S = 0.03          # only for a board that does not answer (v20): with v21
                       # each line waits for its IN WAVACK instead
ACK_TIMEOUT_S = 0.5


def make_wav(text: str, voice: str = "Samantha", rate_wpm: int = 175):
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
    def __init__(self, link, voice="Samantha", muted=False, pace_s=None, chunk=None):
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
        has_wait = hasattr(self.link, "wait_wav")
        if has_wait:
            self.link.clear_wav()
        self.link.event("WAVBEGIN", len(wav))
        if has_wait and not self.link.wait_wav(("IN WAV ready",), 1.0):
            print("[voice] the board did not get ready to listen (firmware v20+?)")
            return
        acked = has_wait                 # assume v21; fall back on the first miss
        for i in range(0, len(b64), self.chunk):
            if gen != self._gen:                 # a newer line replaced this one
                return
            self.link.event("WAVDATA", b64[i:i + self.chunk])
            if acked:
                got = self.link.wait_wav(("IN WAVACK", "IN WAVBAD"), ACK_TIMEOUT_S)
                if got is None:
                    acked = False        # an older board: pace instead of waiting
                    print("[voice] no IN WAVACK -- older firmware, sending slowly")
                elif got.startswith("IN WAVBAD"):
                    print(f"[voice] the board could not decode a chunk ({got})")
                    return
            if not acked:
                time.sleep(self.pace_s)
        self.link.event("WAVPLAY")
