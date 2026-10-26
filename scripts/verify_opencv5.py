"""Run this FIRST on the deployment machine. The competition requires OpenCV 5.
Exit 0 only if OpenCV major version is 5 and the engine's APIs work. Use --allow-4 for local development."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2

allow4 = "--allow-4" in sys.argv
major = int(cv2.__version__.split(".")[0])
print("OpenCV version:", cv2.__version__, "| major:", major)
ok = True
for name in ("aruco", "dnn"):
    has = hasattr(cv2, name)
    print(f"cv2.{name}:", "present" if has else "MISSING")
    ok &= has
from hairline import cvcore, synth
from hairline.config import Config

cfg = Config()
img, _ = synth.render(seed=1, widths_mm=[1.0], cfg=cfg)
a = cvcore.analyse_image(img, cfg, cfg.marker_id)
m = cvcore.segment_and_measure(a["rect"], cfg) if not a["quality"]["blocked"] else None
print("pipeline smoke test:", "OK, width %.2f mm (truth 1.00)" % m["width_med_mm"] if m and m["found"] else "FAILED")
ok &= bool(m and m["found"])
if major != 5 and not allow4:
    print("NOT OpenCV 5: install with  pip install 'opencv-python-headless>=5.0,<6'  (version availability UNVERIFIED in this build)")
    ok = False
sys.exit(0 if ok else 1)
