"""Fit cfg.blur_gain on a CALIBRATION set (seeds 500+), disjoint from the evaluation set used by run_eval.py (seeds 100+).
Dev tool: prints the best gain and the error with/without correction."""
import itertools
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np

from hairline import cvcore, synth
from hairline.config import Config

cfg = Config()
rows = []
for i, (w, ppm, b) in enumerate(itertools.product([0.3, 0.5, 1.0, 2.0], [6.0, 4.5], [0.0, 1.0, 2.0, 2.5, 3.0])):
    img, _ = synth.render(seed=500 + i, widths_mm=[w], ppm=ppm, blur=b, cfg=cfg)
    a = cvcore.analyse_image(img, cfg, cfg.marker_id)
    q = a["quality"]
    if q["blocked"]:
        continue
    m = cvcore.segment_and_measure(a["rect"], cfg, uncertainty_mm=0.2, blur_sigma_mm=0.0)
    if m["found"]:
        rows.append((w, m["width_med_mm"], q["metrics"]["blur_sigma_mm"]))
print(len(rows), "usable scenes")
best = None
for g in (1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0):
    for c in (1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0):
        cfg.blur_gain, cfg.blur_scale = g, c
        err = [abs(float(cvcore.deblur_width(m, s, cfg)) - w) for (w, m, s) in rows]
        wide = [abs(float(cvcore.deblur_width(m, s, cfg)) - w) for (w, m, s) in rows if w >= 1.0]
        mae = float(np.mean(err))
        if best is None or mae < best[2]:
            best = (g, c, mae, float(np.mean(wide)))
cfg.blur_gain = 0.0
raw = float(np.mean([abs(m - w) for (w, m, s) in rows]))
print(f"no correction: MAE {raw:.3f} mm")
print(f"BEST gain={best[0]} scale={best[1]}: MAE {best[2]:.3f} mm (wide cracks >=1 mm: {best[3]:.3f} mm)")
