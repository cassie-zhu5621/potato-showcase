# Booth runbook (11.24) -- for the person running it

Branch `showcase-1124`. What it does: docs/SHOWCASE_1124_PLAN.md.

## Start

```bash
cd ~/Documents/potatobot/showcase
conda activate sidekick
python3 robot/tools/check_bus.py                 # 3 servos answer, 5-6 V
python3 sidekick_loop.py --cam N --cores3        # N: the head camera
```

Then open **http://localhost:8000/** in the browser, full screen.
(`python3 noticebot_loop.py --list-cams` lists the camera numbers.)

Stop: **Ctrl-C** in the terminal. It lies down and relaxes.

## One visitor

| visitor | robot |
|---|---|
| walks up (within the ToF distance, in front) | stirs: lifts its head a little, sleeps on |
| **pats its head** | wakes, light turns blue, looks at them and follows them |
| holds something up **to its eyes**, still | leans in, "hm?", nods: it will look out for it. The web UI shows "Looking for: ..." |
| hides it a few seconds, brings it back | turns to it and calls |
| pats its head (any time) | purrs; while calling = "seen it" |

When they are done: press **NEXT**. It goes back to sleep and forgets them and
their object. (It also does this by itself a minute after they leave.)

Tell visitors to **crouch a little** to play: the camera sees faces at a
seated / crouching height best.

## On the web UI

- **NEXT** -- next visitor.
- **Stir when someone is within ... m** -- `-` / `+` changes it (0.3-2.0 m),
  `on/off` turns the stir off. "now:" is what the sensor reads right now; the
  bar turns green when someone is inside the distance. Kept for the next run.

## If something is off

| problem | do |
|---|---|
| a pat does not wake it | Ctrl-C, unplug and replug the CoreS3 **without touching the head**, start again |
| it ignores things held up | hold it closer to its eye and still for a second; the % next to the box should be about 4.5% or more |
| "I couldn't tell what that was" | network: try again; if it keeps happening restart with `--offline` |
| it follows someone else | only one person in front of it at a time; or NEXT and pat again |
| stirs all the time / never | adjust the distance on the web UI; "now:" shows what it measures |
| no live picture | reload the page; check the terminal is still running |
| servos stop / jitter | Ctrl-C, `check_bus.py`, check the power supply |
