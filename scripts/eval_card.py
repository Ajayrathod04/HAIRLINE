"""REAL-photo evaluation. Photograph the printed gauge card (scripts/make_gauge_card.py) under varied conditions,
put the photos in a folder, and run:  python scripts/eval_card.py PHOTO_DIR [--out eval/real_card_results.json]
Optional filename tags describe the condition (e.g. card_d30_t10_sun.jpg): any text is kept in the report.
For each photo: gates, then width of each gauge line vs its printed width. Failures are listed, not hidden."""
import argparse
import glob
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2

from hairline import cvcore
from hairline.config import Config

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("photos")
    ap.add_argument("--layout", default=os.path.join(ROOT, "samples", "gauge_card_layout.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "eval", "real_card_results.json"))
    a = ap.parse_args()
    layout = json.load(open(a.layout))
    cfg = Config()
    cfg.marker_id = layout["marker_id"]
    rows, fails = [], []
    paths = sorted(p for ext in ("*.jpg", "*.jpeg", "*.png", "*.JPG") for p in glob.glob(os.path.join(a.photos, ext)))
    if not paths:
        sys.exit("no photos found")
    for p in paths:
        img = cv2.imread(p)
        all_rois = [ln["roi_mm"] for ln in layout["lines"]]
        an = cvcore.analyse_image(img, cfg, cfg.marker_id, roi_boxes_mm=all_rois)
        q = an["quality"]
        name = os.path.basename(p)
        if q["blocked"]:
            fails.append({"photo": name, "blocked_by": [g["name"] for g in q["gates"] if not g["pass"] and g["level"] == "block"]})
            continue
        for ln in layout["lines"]:
            m = cvcore.segment_and_measure(an["rect"], cfg, roi_boxes_mm=[ln["roi_mm"]], uncertainty_mm=q["metrics"]["uncertainty_mm"])
            rows.append({"photo": name, "true_mm": ln["width_mm"], "measured_mm": round(m["width_med_mm"], 3) if m["found"] else None,
                         "found": m["found"], "src_ppm": round(q["metrics"]["src_ppm"], 2), "tilt_deg": round(q["metrics"]["tilt_deg"], 1)})
    errs = [abs(r["measured_mm"] - r["true_mm"]) for r in rows if r["measured_mm"] is not None]
    missed = sum(1 for r in rows if not r["found"])
    summary = {"photos": len(paths), "blocked_by_gates": len(fails), "measurements": len(rows), "lines_not_found": missed,
               "mae_mm": round(statistics.mean(errs), 3) if errs else None, "median_mm": round(statistics.median(errs), 3) if errs else None,
               "opencv": cv2.__version__, "blocked_detail": fails, "rows": rows}
    with open(a.out, "w") as f:
        json.dump(summary, f, indent=1)
    print(json.dumps({k: v for k, v in summary.items() if k not in ("rows", "blocked_detail")}, indent=1))
    print("per-width MAE:")
    for w in sorted({r["true_mm"] for r in rows}):
        e = [abs(r["measured_mm"] - w) for r in rows if r["true_mm"] == w and r["measured_mm"] is not None]
        print(f"  {w} mm -> n={len(e)} mae={statistics.mean(e):.3f}" if e else f"  {w} mm -> not detected")


if __name__ == "__main__":
    main()
