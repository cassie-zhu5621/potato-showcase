#!/usr/bin/env python3
"""
check_prompt.py — will this sentence actually fire?

  python3 robot/tools/check_prompt.py "tell me when someone picks up the cup"
  python3 robot/tools/check_prompt.py --offline 9:cup 10 4:bag
  python3 robot/tools/check_prompt.py -f prompts.txt

WHY THIS EXISTS. A prompt is compiled by the VLM into relation ids, and the ids
are not equally reachable: three of the eleven need two people, four need an
object the detector must independently find, one needs that object to be on a
hard-coded list, and one cannot be performed facing the robot at all. None of
that is visible in the sentence, so a prompt reads fine, compiles fine, and
then nothing ever happens -- which at a stand is ninety seconds of a robot
looking attentive and reporting nothing.

The checks here are read off the code that does the work (planner.VOCAB's
object arity, relations.ARTIFACT_TYPES, the focus gate's object-directed set),
not off a table written beside it, so they cannot drift from it.

WITHOUT AN API KEY, pass compiled ids instead: `--offline 9:cup` is "hands on,
bound to cup". That path needs no network and is the one the tests use.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from perception.relations import ARTIFACT_TYPES
from planning.planner import _CATALOG
from planning.spec_utils import OBJECT_DIRECTED, _expand, canonical

ARITY = {r["id"]: r["object_arity"] for r in _CATALOG["relations"]}
KEY = {r["id"]: r["key"] for r in _CATALOG["relations"]}

# Rows whose truth needs a SECOND person in frame. Read from the engine: these
# are the ones computed over `pairs`, plus gathering, which needs the count to
# change. A stand has people, but a visitor standing alone at the table does
# not satisfy any of them by themselves.
NEEDS_TWO = {2, 5, 6, 11}

# Measured on this rig, 2026-10: an arm aimed at the robot foreshortens to a
# point in the image plane and hits nothing, and that is the gesture everybody
# makes first. Loosening the extension threshold from 140 to 110 deg did not
# fix it. Reachable only side-on, at a boxed object.
HARD = {4: "only works side-on to the camera -- pointing AT the robot cannot "
           "hit anything, the ray is computed in the image plane"}


def verdicts(ids, on=None, props=()):
    """-> list of (level, text). level is 'stop', 'warn' or 'ok'."""
    ids = sorted(set(ids))
    on = (on or "").strip().lower()
    out = []
    if not ids:
        return [("stop", "no relations at all -- the planner compiled nothing")]

    for i in ids:
        if i not in KEY:
            out.append(("stop", f"{i} is not a relation in the catalogue"))

    need_obj = [i for i in ids if ARITY.get(i) == "required"]
    if need_obj and not on:
        out.append(("stop", f"{', '.join(KEY[i] for i in need_obj)} needs an "
                            f"object and the entry names none -- it can never "
                            f"pass the focus gate"))
    if on and not (ids & OBJECT_DIRECTED if isinstance(ids, set)
                   else set(ids) & OBJECT_DIRECTED):
        out.append(("warn", f"bound to {on!r}, but none of these rows is "
                            f"object-directed -- the binding does nothing"))

    if 11 in ids:
        # The one whitelist in the system, and it is silent: a handoff of
        # anything not on this list simply never evaluates.
        if on and on not in ARTIFACT_TYPES:
            out.append(("stop", f"turn_taking only ever looks at "
                                f"{sorted(ARTIFACT_TYPES)} -- {on!r} is not "
                                f"one, so it cannot fire at all"))
        else:
            out.append(("warn", "turn_taking needs the object to pass from one "
                                "person to another, and both to be tracked"))

    two = sorted(set(ids) & NEEDS_TWO)
    if two:
        out.append(("warn", f"{', '.join(KEY[i] for i in two)} needs two people "
                            f"in frame -- a visitor alone cannot set it off"))

    for i in sorted(set(ids) & set(HARD)):
        out.append(("stop", f"{KEY[i]}: {HARD[i]}"))

    if on:
        want = _expand([on])
        # CANONICALISE THE PROPS TOO, because the detector does: `smartphone`
        # on the table and `phone` in the plan are the same object by the time
        # either reaches the gate. Comparing the raw strings would send her
        # renaming props to satisfy a checker rather than the system.
        if props and not (want & {canonical(p.strip()) for p in props}):
            out.append(("stop", f"{on!r} is not among the props you listed "
                                f"({', '.join(props)}) -- the detector will "
                                f"never box it"))
        elif not props:
            out.append(("warn", f"{on!r} has to be found by the detector every "
                                f"frame. Small things in a hand sit near the "
                                f"threshold -- check with --conf 0.2"))

    if not any(l == "stop" for l, _ in out):
        easy = sorted(set(ids) - NEEDS_TWO - set(HARD))
        if easy and not need_obj:
            out.append(("ok", f"{', '.join(KEY[i] for i in easy)} needs no "
                              f"object detected -- the most reliable kind"))
    return out


def report(label, ids, on, props):
    print(f"\n  {label}")
    print(f"    compiles to: {sorted(set(ids))}"
          + (f"  on {on!r}" if on else "  (no object)"))
    worst = "ok"
    for level, text in verdicts(ids, on, props):
        mark = {"stop": "!!", "warn": " ~", "ok": " +"}[level]
        print(f"    {mark} {text}")
        if level == "stop":
            worst = "stop"
        elif level == "warn" and worst != "stop":
            worst = "warn"
    print({"stop": "    -> WILL NOT FIRE",
           "warn": "    -> can fire, with the conditions above",
           "ok": "    -> should fire"}[worst])
    return worst


def main():
    ap = argparse.ArgumentParser(description="will this prompt actually fire?")
    ap.add_argument("prompt", nargs="*", help="sentences to compile and check")
    ap.add_argument("-f", "--file", help="one prompt per line")
    ap.add_argument("--props", default="",
                    help="comma-separated list of what is actually on the "
                         "table. Bindings to anything else are refused")
    ap.add_argument("--offline", nargs="*", default=None, metavar="ID[:OBJ]",
                    help="skip the VLM and check compiled ids directly, e.g. "
                         "9:cup 10")
    a = ap.parse_args()
    props = [p for p in a.props.split(",") if p.strip()]

    if a.offline is not None:
        ids, on = [], None
        for tok in a.offline:
            i, _, obj = tok.partition(":")
            ids.append(int(i))
            if obj:
                on = obj
        return 0 if report("offline", ids, on, props) != "stop" else 1

    prompts = list(a.prompt)
    if a.file:
        prompts += [l.strip() for l in open(a.file) if l.strip()]
    if not prompts:
        ap.error("give it a sentence, or --offline")

    # THE REAL PLANNER, text-only. No sweep images: the question here is what
    # a SENTENCE compiles to, and the pictures only change which objects it
    # names -- which `--props` checks separately and offline.
    from planning.planner import plan
    bad = 0
    for text in prompts:
        try:
            spec = plan(text).get("spec") or {}
        except Exception as e:
            print(f"\n  {text!r}\n    !! planner failed: "
                  f"{type(e).__name__}: {str(e)[:140]}")
            bad += 1
            continue
        entries = spec.get("watch") or []
        if not entries:
            print(f"\n  {text!r}\n    !! compiled to NO watch entries")
            bad += 1
            continue
        for e in entries:
            ids = (e.get("all") or []) + (e.get("any") or []) + (e.get("then") or [])
            if report(f"{text!r}  [{e.get('label', '')}]",
                      ids, e.get("on"), props) == "stop":
                bad += 1
    print()
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
