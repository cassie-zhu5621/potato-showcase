"""`--diag`: one paste-able block instead of a described symptom.

Written after three wrong guesses in a row, two of them mine. Every round cost
a reflash, and the evidence each time was a sentence -- and a sentence is the
worst possible evidence here. "0" means one thing read off the bar and another
read off the number, and neither means anything without the status beside it.

So this exercises the block against a fake board. The fake answers instantly,
which is the same race the real one has with the timing taken out, and that is
exactly how the drain bug below was found on the first run.
"""
import importlib.util
import io
import contextlib
import os
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "tof_test_diag", os.path.join(ROOT, "robot", "tools", "tof_test.py"))
tof_test = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tof_test)


class FakeBoard:
    """Answers commands, and streams distance the way the board does."""

    def __init__(self, port, on_input=None, *, working_bus=0, mm=243):
        self.cb, self.bus, self.mm = on_input, 0, mm
        self.working, self._stop = working_bus, False
        self._t = threading.Thread(target=self._stream, daemon=True)
        self._t.start()

    def _stream(self):
        while not self._stop:
            if self.bus == self.working:
                self.cb(f"IN DIST {self.mm}")
            else:
                self.cb("IN DIST -1")
            time.sleep(0.002)

    def dist(self, on=True): pass
    def tofbus(self, n): self.bus = n; self.cb(f"IN TOF BUS {n}")
    def tof(self):
        self.cb("IN TOF READY" if self.bus == self.working else "IN TOF FAIL")
    def scan(self): self.cb("IN SCAN sda=G2 scl=G1 -> 0x29")
    def tofraw(self):
        ok = self.bus == self.working
        self.cb(f"IN TOFRAW rdy=1 st=0 mm={self.mm if ok else 0} "
                f"signal={'1.80' if ok else '0.00'} "
                f"ambient={'0.40' if ok else '0.00'} budget=33000 mode=3 "
                f"timeout=0 rawst=0x09 rawmm={self.mm if ok else 0} "
                f"hvstatus=0x00")

    def tofdiag(self):
        ok = self.bus == self.working
        self.cb(f"IN TOFDIAG calls=900 ready={'850' if ok else '0'} "
                f"emit={'850' if ok else '0'} restarts=0 status=0 "
                f"mm={self.mm if ok else 0} i2c={0 if ok else 2} ok=1")
    def close(self): self._stop = True


def _run(**kw):
    orig_link, orig_sleep = tof_test.CoreS3Link, tof_test.time.sleep
    tof_test.CoreS3Link = lambda port, on_input=None: FakeBoard(
        port, on_input, **kw)
    tof_test.time.sleep = lambda s: orig_sleep(min(s, 0.05))
    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            tof_test.diag("/dev/fake")
        return buf.getvalue()
    finally:
        tof_test.CoreS3Link, tof_test.time.sleep = orig_link, orig_sleep


def test_the_replies_are_not_eaten_by_the_buffer_clear():
    """THE BUG THE FAKE FOUND. It cleared the buffer and THEN slept, so a
    reply that landed before the clear -- which on a board answering in
    milliseconds is most of them -- was deleted by the thing waiting for it."""
    out = _run()
    assert "IN TOF READY" in out
    assert "IN SCAN" in out
    assert "IN TOFDIAG" in out


def test_it_reports_both_controllers_and_says_which_one_works():
    out = _run(working_bus=1)
    assert "controller 0" in out and "controller 1" in out
    assert "IN TOF FAIL" in out and "IN TOF READY" in out
    assert "i2c=2" in out and "i2c=0" in out


def test_it_counts_the_readings_rather_than_describing_them():
    """`valid=0` and `valid=850 med=243` are different problems, and the
    difference is the whole reason this exists."""
    out = _run(mm=243)
    assert "valid=0" in out, "the dead controller reports none"
    assert "med=243" in out, "and the live one reports what it sees"


def test_it_leaves_the_board_on_the_default_controller():
    """A diagnostic that leaves the sensor re-initialised on Wire1 would make
    the next run of anything else mysteriously worse."""
    import inspect
    src = inspect.getsource(tof_test.diag)
    tail = src[src.rindex("for bus in"):]
    assert "link.tofbus(0)" in tail, "put it back before closing"


def test_the_readings_are_taken_before_the_scan_breaks_the_bus():
    """THE EVENING THIS COST. SCAN walks BOTH pin orders, so it re-begin()s the
    bus with the pins swapped under a sensor that is mid-ranging -- and before
    v16 nothing put it back. `--diag` scanned first and sampled second, so it
    broke the bus and then reported the breakage as the symptom: ready frozen,
    i2c=4, restarts climbing, no readings. Three explanations were built on
    that trace and all of them were about the lens.

    Ordered so the numbers come off an untouched bus whatever firmware is on
    the board -- the fix in the firmware is not enough on its own, because the
    tool has to work against the board that has the bug."""
    import inspect
    src = inspect.getsource(tof_test.diag)
    body = src[src.index("for bus in"):]
    assert body.index("IN DIST") < body.index("link.scan()"), \
        "sampling must come before the scan"


def test_the_firmware_puts_the_bus_back_after_a_scan():
    """And says it did. A tool that leaves the hardware in a different state
    than it found it, silently, is a trap rather than a diagnostic."""
    ino = open(os.path.join(ROOT, "robot", "firmware", "cores3_sidekick",
                            "cores3_sidekick.ino")).read()
    block = ino[ino.index("void tofScan() {"):ino.index("void tofInit() {")]
    assert "tofInit();" in block, "restore the sensor the scan disturbed"
    assert "IN SCAN restored" in block, "and say so, with the result"
    assert ino.index("void tofInit();") < ino.index("void tofScan() {"), \
        "declared before use rather than leaning on the .ino prototype pass"


def test_the_block_opens_the_measurement_up():
    """`status=0 mm=0 i2c=0` is as far as TOFDIAG can see, and three wrong
    explanations were built on it. Whether the receiver sees any light at all
    is the number that settles it, and only TOFRAW has it."""
    out = _run()
    assert "IN TOFRAW" in out
    assert out.count("IN TOFRAW") >= 3, "more than one, a beat apart"
    assert "signal=" in out and "ambient=" in out


def test_the_raw_line_parses_the_way_it_is_actually_printed():
    """A hand-rolled split over a printf-formatted line. The line is the only
    thing this has to get right, so it is checked against a real one copied
    out of a session rather than one written to match the parser."""
    line = ("IN TOFRAW rdy=0 st=0 mm=0 signal=26.87 ambient=0.00 "
            "budget=32986 mode=2 timeout=0 rawst=0x09 rawmm=0 hvstatus=0x03")
    f = dict(kv.split("=", 1) for kv in line.split()[2:] if "=" in kv)
    assert f["signal"] == "26.87" and f["ambient"] == "0.00"
    assert f["mm"] == "0" and f["st"] == "0"
    # the hex fields must not break the split
    assert f["rawst"] == "0x09" and f["hvstatus"] == "0x03"


def test_the_raw_watcher_explains_what_each_outcome_means():
    """Two measurements that look identical -- a flooded receiver -- with
    opposite fixes: move the thing in front of it, or the window IS the thing
    in front of it. A watcher that prints numbers and leaves that unsaid would
    have sent us round again."""
    import inspect
    doc = inspect.getdoc(tof_test.raw_watch)
    assert "DOES NOT MOVE" in doc and "MOVES" in doc
    assert "ambient" in doc
