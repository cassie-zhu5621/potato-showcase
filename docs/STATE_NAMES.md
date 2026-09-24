# State names — the 2026-09 renumbering

The paper's state numbers changed. This repository was renamed to match, so the
**clip filename, the .blend filename, the generator script and the runtime state
ID are now one string**, and that string is the paper's.

Before, they were four different conventions for the same eight states, and the
worst of it was silent: `S7a.csv` was the paper's S5 Call while `S8_ERROR.csv`
was the paper's S7 Error, so a number read off the figure and a number read off
the filesystem could both be "S7" and mean different states.

## The map

| paper state | clip | .blend | generator |
|---|---|---|---|
| **S0 Idle** | `S0_IDLE.csv` | `S0_IDLE.blend` | `generate_s0_idle.py` |
| **S1 Attend** | `S1_ATTEND.csv` | `S1_ATTEND.blend` | `generate_s1_attend.py` |
| **S2 Acknowledge** | `S2_ACKNOWLEDGE.csv` | `S2_ACKNOWLEDGE.blend` | `generate_s2_acknowledge.py` |
| **S3 Scan** | `S3_SCAN.csv` | `S3_SCAN.blend` | `generate_s3_scan.py` |
| **S4 Watch** (arrival) | `S4A_SETTLE.csv` | `S4_WATCH.blend` | `generate_s4a_settle.py` |
| **S4 Watch** (hold) | `S4B_WATCH.csv` | `S4_WATCH.blend` | `generate_s4b_watch.py` |
| **S5 Call** (found) | `S5A_FOUND.csv` | `S5A_FOUND.blend` | `generate_s5a_found.py` |
| **S5 Call** (beckon) | `S5B_BECKON.csv` | `S5B_BECKON.blend` | `generate_s5b_beckon.py` |
| **S6 Correct** | `S6_CORRECT.csv` | `S6_CORRECT.blend` | `generate_s6_correct.py` |
| **S7 Error** | `S7_ERROR.csv` | `S7_ERROR.blend` | `generate_s7_error.py` |

S4 Watch has one .blend and two clips: the arrival beat and the hold are cut
from the same source.

## What it used to be called

Old names, in case an older note, a commit message or a session record uses one:

    S1_IDLE -> S0_IDLE          S5A_SETTLE -> S4A_SETTLE
    S2_LISTEN -> S1_ATTEND      S5B_TRACK  -> S4B_WATCH
    S3_ACK -> S2_ACKNOWLEDGE    S7a -> S5A_FOUND
    S4_PLAN -> S3_SCAN          S7b -> S5B_BECKON
    S6_FINETUNE -> S6_CORRECT   S8_ERROR -> S7_ERROR

`tools/crop_s1.py` and `tools/film_s1.py` were NOT renamed. Their "S1" is
Study 1, not a state.

## The debt this left, deliberately

975 full identifiers were rewritten mechanically and the 363 tests were run
against the result. **Bare numbers inside prose comments were not touched**,
and several hundred of them are still on the old numbering.

They were left because they cannot be rewritten mechanically: the comments in
`motion/blender/` are a record of design decisions, each one written on the day
a mistake was found, and a wrong automatic edit inside one would destroy the
most valuable thing in this repository while looking like a successful rename.

So when a COMMENT says a bare `S5` or `S7`, read it as the OLD numbering:

    an old bare S5 means today's S4 Watch
    an old bare S7 means today's S5 Call
    an old bare S8 means today's S7 Error

A worked example, in `generate_s5a_found.py`, which is otherwise correct:

    "the head is still on the watched region -- S5 left it there"

That `S5` is the old S5, i.e. **S4 Watch**. The sentence is true; only the
number is stale.

Fix these by hand as the files are worked on, not in a batch.
