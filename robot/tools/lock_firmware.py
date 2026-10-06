#!/usr/bin/env python3
"""
lock_firmware.py — re-record the sketch's fingerprint after a deliberate change.

  python3 robot/tools/lock_firmware.py

WHY. The version is how anything knows what is on the board: `tof_test.py`
reads it, `cores3_link` warns on an older one, and every runbook says which to
expect. All of that assumes a version means one sketch -- and on 2026-10-06 it
stopped: PALM_ENTER went 250 to 300 inside v17, so a board flashed that morning
and the repo that evening both answered `v17` while behaving differently. The
wake looked broken for reasons that were not in the code being read.

So the sketch is hashed and the hash is committed. Change the .ino and the
tests fail until you bump FIRMWARE_V *and* run this -- which is the moment to
remember that a bump means somebody has to reflash.
"""
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INO = os.path.join(ROOT, "robot", "firmware", "cores3_sidekick",
                   "cores3_sidekick.ino")
LOCK = os.path.join(ROOT, "robot", "firmware", "cores3_sidekick",
                    "VERSION_LOCK.json")


def sketch_version(src):
    vs = set(re.findall(r"cores3_sidekick (v\d+)", src))
    if len(vs) != 1:
        sys.exit(f"the sketch says {sorted(vs) or 'nothing'} -- it must say "
                 f"exactly one version")
    return vs.pop()


def main():
    src = open(INO, "rb").read()
    ver = sketch_version(src.decode("utf-8", "ignore"))
    old = {}
    if os.path.exists(LOCK):
        old = json.load(open(LOCK))
    digest = hashlib.sha256(src).hexdigest()
    if old.get("sha256") == digest and old.get("version") == ver:
        print(f"unchanged: {ver} {digest[:16]}")
        return 0
    if old and old.get("version") == ver and old.get("sha256") != digest:
        print(f"!! the sketch changed but still says {ver}.")
        print("   Bump it first: a board flashed before this change and one "
              "flashed after\n   would both answer "
              f"{ver}, and nothing downstream could tell them apart.")
        return 1
    json.dump({"_why": old.get("_why", ""), "version": ver, "sha256": digest},
              open(LOCK, "w"), indent=2)
    open(LOCK, "a").write("\n")
    print(f"locked {ver} {digest[:16]} -- REFLASH THE BOARD")
    return 0


if __name__ == "__main__":
    sys.exit(main())
