"""Synthetic benchmark with KNOWN ground truth: does the quality-gate + re-shoot agent beat 'accept the first photo'?

Honest scope: synthetic walls validate geometry, gating and measurement. They do NOT replace the real printed-card
protocol (scripts/eval_card.py). Re-shoot results ASSUME the user follows the agent's advice.
Usage: python scripts/run_eval.py [--quick] [--out eval]
"""
import argparse
import itertools
import json
import os
import platform
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2
import numpy as np

from hairline import cvcore, synth
from hairline.config import Config

CFG = Config()
CONDS = {"clean": {}, "blur2.5": {"blur": 2.5}, "glare0.6": {"glare": 0.6}}


def measure(img, force=False, deblur=True):
    a = cvcore.analyse_image(img, CFG, CFG.marker_id)
    q = a["quality"]
    if a["rect"] is None:
        return None, q
    if q["blocked"] and not force:
        return None, q
    mt = q["metrics"] or {}
    m = cvcore.segment_and_measure(a["rect"], CFG, uncertainty_mm=mt.get("uncertainty_mm", 0.2),
                                   blur_sigma_mm=mt.get("blur_sigma_mm", 0.0) if deblur else 0.0)
    return m, q


def one(args):
    seed, w, ppm, tilt, cname = args
    kw = dict(CONDS[cname])
    img, _ = synth.render(seed=seed, widths_mm=[w], ppm=ppm, tilt_deg=(tilt, 0), cfg=CFG, **kw)
    base, _ = measure(img, force=True, deblur=False)  # naive baseline: accept first photo, no gates, no blur correction
    agent_m, q = measure(img, force=False)           # agent: gate first
    failed = [g["name"] for g in q["gates"] if not g["pass"] and g["level"] == "block"]
    reshot = None
    if agent_m is None:                               # compliant re-shoot following the advice
        img2, _ = synth.render(seed=seed, widths_mm=[w], ppm=6.0, tilt_deg=(5, 0), cfg=CFG)
        reshot, _ = measure(img2, force=False)
    f = lambda m: (round(m["width_med_mm"], 4) if m and m["found"] else None)
    unc = round(agent_m["uncertainty_mm"], 4) if agent_m and agent_m["found"] else None
    return {"seed": seed, "w": w, "ppm": ppm, "tilt": tilt, "cond": cname, "baseline": f(base), "agent_first": f(agent_m), "unc": unc,
            "accepted_first": agent_m is not None, "failed_gates": failed, "reshoot": f(reshot)}


def stats(errs):
    if not errs:
        return {"n": 0}
    s = sorted(errs)
    return {"n": len(s), "mae_mm": round(statistics.mean(s), 3), "median_mm": round(statistics.median(s), 3),
            "p90_mm": round(s[int(0.9 * (len(s) - 1))], 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--shard", help="k/n: run only every n-th scene starting at k and save rows (for short runs); then use --merge")
    ap.add_argument("--merge", action="store_true", help="combine shard files and write the final report")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "eval"))
    a = ap.parse_args()
    widths = [0.5, 1.0] if a.quick else [0.3, 0.5, 1.0, 2.0]
    ppms = [6.0, 4.5] if a.quick else [8.0, 6.0, 4.5]
    tilts = [0, 25, 40] if a.quick else [0, 12, 25, 40]
    conds = ["clean", "blur2.5"] if a.quick else list(CONDS)
    grid = [(100 + i, w, p, t, c) for i, (w, p, t, c) in enumerate(itertools.product(widths, ppms, tilts, conds))]
    t0 = time.time()
    os.makedirs(a.out, exist_ok=True)
    if a.shard:
        k, n = map(int, a.shard.split("/"))
        part = grid[k::n]
        with ProcessPoolExecutor(max_workers=os.cpu_count()) as ex:
            rows = list(ex.map(one, part, chunksize=2))
        json.dump({"rows": rows, "elapsed": time.time() - t0}, open(os.path.join(a.out, f"_shard_{k}.json"), "w"))
        print(f"shard {k}/{n}: {len(rows)} scenes in {time.time() - t0:.0f}s")
        return
    if a.merge:
        rows, elapsed = [], 0.0
        for fn in sorted(os.listdir(a.out)):
            if fn.startswith("_shard_"):
                d = json.load(open(os.path.join(a.out, fn)))
                rows += d["rows"]
                elapsed += d["elapsed"]
        rows.sort(key=lambda r: r["seed"])
    else:
        with ProcessPoolExecutor(max_workers=os.cpu_count()) as ex:
            rows = list(ex.map(one, grid, chunksize=2))
        elapsed = time.time() - t0
    err = lambda r, key: abs(r[key] - r["w"]) if r[key] is not None else None
    base_all = [err(r, "baseline") for r in rows]
    base_missing = sum(1 for e in base_all if e is None)
    base_err = [e for e in base_all if e is not None]
    acc = [r for r in rows if r["accepted_first"]]
    acc_err = [err(r, "agent_first") for r in acc if r["agent_first"] is not None]
    acc_missed = sum(1 for r in acc if r["agent_first"] is None)
    tol = lambda w: max(0.15, 0.3 * w)
    cov1 = [abs(r["agent_first"] - r["w"]) <= r["unc"] for r in acc if r["agent_first"] is not None]
    cov2 = [abs(r["agent_first"] - r["w"]) <= 2 * r["unc"] for r in acc if r["agent_first"] is not None]
    false_acc = sum(1 for r in acc if r["agent_first"] is not None and abs(r["agent_first"] - r["w"]) > tol(r["w"]))
    rej = [r for r in rows if not r["accepted_first"]]
    re_err = [err(r, "reshoot") for r in rej if r["reshoot"] is not None]
    base_bad = sum(1 for r in rows if r["baseline"] is not None and abs(r["baseline"] - r["w"]) > tol(r["w"]))
    gate_counts = {}
    for r in rej:
        for g in r["failed_gates"]:
            gate_counts[g] = gate_counts.get(g, 0) + 1
    by_w = {str(w): {"baseline": stats([err(r, "baseline") for r in rows if r["w"] == w and r["baseline"] is not None]),
                     "agent_accepted": stats([err(r, "agent_first") for r in acc if r["w"] == w and r["agent_first"] is not None])} for w in widths}
    out = {"kind": "synthetic", "scenes": len(rows), "elapsed_s": round(elapsed, 1), "opencv": cv2.__version__, "numpy": np.__version__,
           "python": platform.python_version(), "machine": platform.machine(), "grid": {"widths_mm": widths, "ppm": ppms, "tilt_deg": tilts, "conditions": conds},
           "tolerance_rule": "max(0.15 mm, 30% of true width)",
           "baseline_accept_first": {**stats(base_err), "no_scale_no_measurement": base_missing, "out_of_tolerance": base_bad},
           "agent_first_shot_accepted": {**stats(acc_err), "accepted_share": round(len(acc) / len(rows), 3), "no_crack_found": acc_missed, "false_accepts_out_of_tolerance": false_acc,
                                       "error_within_reported_uncertainty": round(sum(cov1) / max(1, len(cov1)), 3),
                                       "error_within_2x_uncertainty": round(sum(cov2) / max(1, len(cov2)), 3)},
           "agent_rejected_share": round(len(rej) / len(rows), 3), "reject_reasons": gate_counts,
           "after_compliant_reshoot": {**stats(re_err)}, "by_true_width": by_w, "rows": rows}
    os.makedirs(a.out, exist_ok=True)
    name = "results_quick" if a.quick else "results"
    with open(os.path.join(a.out, name + ".json"), "w") as f:
        json.dump(out, f, indent=1)
    md = [f"# Synthetic benchmark ({'quick' if a.quick else 'full'})", "",
          f"{len(rows)} synthetic scenes with known crack widths, OpenCV {cv2.__version__}, {elapsed:.0f} s on {platform.machine()}.",
          "Synthetic only: validates geometry, gating and measurement, NOT accuracy on real walls. Re-shoot rows assume the user follows the advice.", "",
          "| Strategy | n | MAE mm | median mm | p90 mm | notes |", "|---|---|---|---|---|---|",
          f"| Naive: accept every first photo (no gates, no blur fix) | {out['baseline_accept_first']['n']} | {out['baseline_accept_first'].get('mae_mm')} | {out['baseline_accept_first'].get('median_mm')} | {out['baseline_accept_first'].get('p90_mm')} | {base_bad} outside tolerance, {base_missing} with no scale |",
          f"| Agent (gates + blur fix): measured first shots only | {out['agent_first_shot_accepted']['n']} | {out['agent_first_shot_accepted'].get('mae_mm')} | {out['agent_first_shot_accepted'].get('median_mm')} | {out['agent_first_shot_accepted'].get('p90_mm')} | {false_acc} false accepts; accepted share {out['agent_first_shot_accepted']['accepted_share']} |",
          f"| Agent: rejected, then compliant re-shoot | {out['after_compliant_reshoot']['n']} | {out['after_compliant_reshoot'].get('mae_mm')} | {out['after_compliant_reshoot'].get('median_mm')} | {out['after_compliant_reshoot'].get('p90_mm')} | rejected share {out['agent_rejected_share']} |",
          "", f"Tolerance rule: {out['tolerance_rule']}.", "", "Reject reasons (a scene can fail several gates): " + json.dumps(gate_counts), "",
          "| True width mm | baseline MAE | agent-accepted MAE |", "|---|---|---|"]
    for w, d in by_w.items():
        md.append(f"| {w} | {d['baseline'].get('mae_mm')} (n={d['baseline']['n']}) | {d['agent_accepted'].get('mae_mm')} (n={d['agent_accepted']['n']}) |")
    with open(os.path.join(a.out, name.upper().replace("RESULTS", "RESULTS") + ".md"), "w") as f:
        f.write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
