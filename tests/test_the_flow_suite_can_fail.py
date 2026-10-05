"""test_session_flow.py is a script, and its summary has to be the last thing
in it.

It was not, twice. Sections appended after the `raise AssertionError` ran,
filled `fails`, and were never looked at again -- under pytest the module
imports cleanly and the suite is green whatever those sections found. Three
sections of coverage that existed, executed, and could not fail; the second
time, the section being added was the one for the bug under investigation.

Appending to the end of a file is the obvious thing to do, so this guards the
obvious thing rather than asking anyone to remember.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUITE = os.path.join(ROOT, "tests", "test_session_flow.py")


def test_nothing_runs_after_the_summary():
    src = open(SUITE).read()
    raise_at = src.rindex('raise AssertionError("; ".join(fails))')
    after = src[raise_at:].split("\n", 1)[1].strip()
    assert not after, (
        "test_session_flow.py has code after its summary. Anything down there "
        "runs, records failures into `fails`, and is never checked:\n\n"
        + after[:400])


def test_the_summary_actually_raises():
    """A summary that only prints is a suite that cannot fail under pytest."""
    src = open(SUITE).read()
    assert 'raise AssertionError("; ".join(fails))' in src
    assert src.count("raise AssertionError") == 1


def test_a_deliberate_failure_is_caught():
    """The guards above are about placement. This one asks the suite to fail."""
    import subprocess
    import sys
    src = open(SUITE).read()
    broken = src.replace('expect(f.state == "S5B_BECKON", "reporting")',
                         'expect(f.state == "NONSENSE", "reporting")', 1)
    assert broken != src, "anchor moved -- pick another line in the suite"
    tmp = os.path.join(ROOT, "tests", "_tmp_flow_suite.py")
    try:
        open(tmp, "w").write(broken)
        r = subprocess.run([sys.executable, tmp], capture_output=True, text=True,
                           cwd=ROOT)
        assert r.returncode != 0, "a broken expectation did not fail the suite"
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
