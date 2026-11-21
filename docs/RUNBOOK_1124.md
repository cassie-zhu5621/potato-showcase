# Booth runbook (11.24) -- for the person running it

What the demo does and why: docs/SHOWCASE_1124_PLAN.md. This page is only how
to run it. Written for a Mac (Apple Silicon).

---

## A. Set up the laptop (once, at home, with internet)

### What you need
- The robot (servo board on USB), the CoreS3 board (USB-C), the head camera (USB).
  The CoreS3 already has its firmware (v21); nothing needs flashing.
- Access to the GitHub repo `cassie-zhu5621/potato-showcase` (ask Cassie).
- A **Gemini API key** (ask Cassie; she sends it privately). Never put it in a
  chat, a screenshot or a commit.

### 1. Miniconda (skip if `conda --version` already works)
Download "Miniconda3 macOS Apple M1 64-bit pkg" from
https://docs.anaconda.com/miniconda/ and install it. Open a new Terminal.

### 2. Get the code
```bash
mkdir -p ~/Documents/potatobot && cd ~/Documents/potatobot
git clone -b showcase-1124 https://github.com/cassie-zhu5621/potato-showcase.git showcase
cd showcase
```

### 3. The Python environment
```bash
conda create -n sidekick python=3.11 -y
conda activate sidekick
pip install -r requirements.txt          # takes several minutes
```

### 4. The API key
```bash
cp .env.example .env
open -e .env                               # replace your_gemini_api_key_here with the key, save
```
`.env` is ignored by git, so the key stays on this laptop.

### 5. Download the vision model now (not at the booth)
```bash
python3 -c "from ultralytics import YOLOWorld; m = YOLOWorld('yolov8s-world.pt'); m.set_classes(['cup']); print('detector OK')"
```
The first time, it downloads the detector (~25 MB) and its text model. It must
print `detector OK`.

### 6. Dry run without the robot
```bash
python3 sidekick_loop.py --no-robot --cam 0
```
- macOS asks to let Terminal use the camera: **Allow** (then run it again).
- Open **http://localhost:8000/**: you should see yourself live.
- In the small "sidekick" window press **t** = a pat on the head. Then hold a
  cup up close to the camera for a second: after a few seconds "Looking for:"
  shows it.
- **Ctrl-C** in Terminal to stop.

If all of that works, the laptop is ready.

---

## B. At the booth, every day

### Plug in
Robot servo board, CoreS3, head camera -> laptop. Servo power on.
**Do not touch the robot's head while the CoreS3 starts** (its touch sensor
calibrates at power-on).

### Start
```bash
cd ~/Documents/potatobot/showcase
conda activate sidekick
git pull                                   # in case Cassie fixed something
python3 robot/tools/check_bus.py           # must say all three servos answer, 5-6 V
python3 noticebot_loop.py --list-cams      # find the head camera's number N
caffeinate -di python3 sidekick_loop.py --cam N --cores3
```
(`caffeinate -di` keeps the laptop from sleeping while it runs.)

Open **http://localhost:8000/** in the browser and make it full screen.

### Stop
**Ctrl-C** in Terminal. The robot lies down and relaxes. Then unplug.

---

## C. One visitor

| visitor | robot |
|---|---|
| walks up in front of it | lifts its head a little, sleeps on |
| **pats its head** | wakes, light turns **blue**, looks at them and follows them as they move |
| holds something **up to its eye**, still, for a second | leans in, "hm?", then nods: it will look out for it. The web UI shows "Looking for: ..." |
| hides it for a few seconds, brings it back | turns to it and calls |
| pats its head (any time) | presses up into the hand; while it calls = "I've seen it" |

When they are done: press **NEXT**. It goes back to sleep and forgets them and
their object. (It also does this by itself a minute after they leave.)

Ask visitors to **crouch a little** while they play: the camera finds faces
best at that height. One person in front of it at a time.

## D. The web UI

- **Looking for** -- what it is looking out for now.
- **- 0.8 m +** -- how close someone must come (in front) for the sleeping
  robot to lift its head; `on/off` turns that off. "now:" is what the distance
  sensor reads, and the bar turns green when someone is inside. Kept for the
  next run.
- **NEXT** -- next visitor.
- The live picture: boxes around people and things it sees.

## E. If something is off

| problem | do |
|---|---|
| `check_bus.py`: servos do not answer | servo power on? USB cable in? Replug and run it again |
| `no CoreS3 found` | replug the CoreS3 (USB-C), wait 5 s, start again |
| a pat does not wake it | Ctrl-C, replug the CoreS3 **without touching the head**, start again |
| no live picture / black | wrong camera number: `--list-cams` again; reload the web page |
| it ignores things held up | closer to its eye and still for a second (the % next to the box should be about 4.5% or more) |
| "I couldn't tell what that was" | the network: check Wi-Fi; if it keeps happening, restart with `--offline` added |
| it follows someone else | one person in front of it at a time; or NEXT and pat again |
| lifts its head all the time / never | change the distance on the web UI; "now:" shows what it measures |
| servos stop or shake | Ctrl-C, `check_bus.py`, check the power supply |

What happened is saved in `session_feed/sidekick_<date_time>/run.log`. If
something went wrong, send that file to Cassie. Delete `session_feed/` after the
event (it holds camera pictures of visitors).
