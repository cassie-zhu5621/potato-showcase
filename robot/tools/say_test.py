#!/usr/bin/env python3
"""
say_test.py -- does the robot speak? (firmware v20)

  python3 robot/tools/say_test.py
  python3 robot/tools/say_test.py --voice Samantha "Hello, I'm awake."

Sends one line to the CoreS3: it should come out of the robot's own speaker and
appear under its face for a few seconds. Prints what the board answered.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from session.cores3_link import CoreS3Link, find_cores3   # noqa: E402
from session.robot_voice import RobotVoice, make_wav      # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("text", nargs="?",
                    default="OK! I'll look out for a blue water bottle.")
    ap.add_argument("--voice", default="Samantha")
    ap.add_argument("--pitch", type=float, default=1.0,
                    help="1.3 = higher, smaller, cuter (needs ffmpeg)")
    ap.add_argument("--here", action="store_true",
                    help="play it on this Mac instead of the robot (audition)")
    ap.add_argument("--pace", type=float, default=None,
                    help="seconds between data lines (default session.robot_voice.PACE_S)")
    ap.add_argument("--chunk", type=int, default=None,
                    help="base64 characters per line (default 512)")
    a = ap.parse_args()
    wav = make_wav(a.text, a.voice, pitch=a.pitch)
    if not wav:
        sys.exit("`say` could not make the line (this needs a Mac).")
    print(f"line: {a.text!r}  ({len(wav) / 1024:.0f} KB of audio)")
    if a.here:
        import subprocess
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".wav") as f:
            f.write(wav)
            f.flush()
            subprocess.run(["afplay", f.name])
        return
    port = find_cores3()
    if not port:
        sys.exit("no CoreS3 found")
    lines = []
    link = CoreS3Link(port, on_input=lambda s: lines.append(s))
    link.claim(volume=100)
    link.skface("^_^")
    link.sksay(a.text)
    t0 = time.time()
    voice = RobotVoice(link, voice=a.voice, pace_s=a.pace, chunk=a.chunk,
                       pitch=a.pitch)
    voice._send(a.text, voice._gen)        # in this thread, so we can time it
    print(f"sent in {time.time() - t0:.1f}s")
    time.sleep(4)
    for s in lines:
        if "WAV" in s or "PONG" in s or "HELLO" in s:
            print("  board:", s)
    print(f"  ({len([l for l in lines if l])} lines from the board in all)")
    if not any("WAV play" in s for s in lines):
        print("!! the board never said `IN WAV play` -- is it v20? "
              "(python3 robot/tools/tof_test.py)")
    link.sksay("")
    link.close()


if __name__ == "__main__":
    main()
