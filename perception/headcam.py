"""
headcam.py -- the camera on the robot's head, latest frame only.

Moved here from noticebot_loop.py unchanged, so the sidekick mode and the tools
can use it without importing the whole paper loop.
"""
import threading
import time
from collections import deque

import cv2


class HeadCam:
    """Keeps only the latest frame. A queue would be wrong here: an old frame is
    worse than no frame, because the head has moved since it was taken."""

    def __init__(self, index, width=1280, height=720):
        self.cap = cv2.VideoCapture(index)
        if width:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        # MJPG so a 720p+ UVC stream is not limited to a few fps over USB 2
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        if not self.cap.isOpened():
            raise RuntimeError(f"cannot open camera {index} -- try --list-cams")
        self.latest, self.seq, self._stop = None, 0, False
        # ~7 s at 10 Hz, JPEG-compressed. The judge reaches back 4 s
        # (EVENT_OFFSETS_S) and the deque has to outlive that with room to
        # spare, or the oldest offset resolves to whatever happens to still be
        # in it -- silently, since nearest-match always returns something.
        self.event_frames = deque(maxlen=70)
        self._last_event_frame = 0.0
        threading.Thread(target=self._run, daemon=True).start()
        t0 = time.time()
        while self.latest is None:
            if time.time() - t0 > 8:
                raise RuntimeError(f"camera {index} opened but produced no "
                                   f"frames in 8s")
            time.sleep(0.05)
        h, w = self.latest.shape[:2]
        print(f"[cam] {index}: {w}x{h}")

    def _run(self):
        while not self._stop:
            ok, fr = self.cap.read()
            if ok:
                self.latest, self.seq = fr, self.seq + 1
                now = time.time()
                if now - self._last_event_frame >= 0.1:
                    ok_jpg, jpg = cv2.imencode(
                        ".jpg", fr, [cv2.IMWRITE_JPEG_QUALITY, 82])
                    if ok_jpg:
                        self.event_frames.append((now, jpg.tobytes()))
                        self._last_event_frame = now
            else:
                time.sleep(0.05)

    def close(self):
        self._stop = True
        time.sleep(0.1)
        self.cap.release()
