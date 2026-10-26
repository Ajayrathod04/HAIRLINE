# Evaluation

Two separate things are evaluated, and they must not be confused:

| | What it proves | What it does NOT prove |
|---|---|---|
| **A. Synthetic benchmark** (done, reproducible) | Geometry, gating, blur handling and width measurement against *known* ground truth; the agent beats "accept the first photo" | Accuracy on real walls, real cameras, real cracks |
| **B. Printed gauge-card protocol** (you run it, about 30 photos) | Accuracy on real phone photos against printed known widths | Behaviour on cracked masonry; printer accuracy limits the claim |

## A. Synthetic benchmark
*(Full 144-scene baseline in `eval/results.json`; OpenCV 5.0.0 runtime verification run documented in `docs/VERIFICATION_RESULTS.md` and `eval/results_quick.json`).*
144 scenes = 4 widths (0.3, 0.5, 1.0, 2.0 mm) x 3 distances (8, 6, 4.5 source px/mm) x 4 tilts (0, 12, 25, 40 deg) x 3 conditions (clean, blur sigma 2.5 px, glare). Each scene has a textured wall with pits and stains (false-positive bait), a perspective camera, noise. Tolerance rule: `max(0.15 mm, 30% of true width)`. Seeds 100+ (disjoint from calibration seeds 500+ and held-out seeds 700+). Reproduce: `python scripts/run_eval.py --shard 0/3` (then 1/3, 2/3) and `--merge`. Raw rows: `eval/results.json`, summary: `eval/RESULTS.md`.

| Strategy | Scenes measured | MAE (mm) | Median (mm) | p90 (mm) | Outside tolerance |
|---|---|---|---|---|---|
| Naive: accept every first photo, no gates, no blur fix | 142 (2 had no scale) | 0.187 | 0.167 | 0.532 | 35 (25%) |
| **Agent: gates + blur fix, measured first shots** | 70 of 72 accepted | **0.100** | 0.101 | **0.200** | 11 (16%) |
| Agent: rejected shots, then compliant re-shoot | 72 | 0.100 | 0.101 | 0.200 | assumes the user follows the advice |

* The agent rejected **50%** of scenes (the grid is deliberately harsh): glare in 48, tilt over 35 deg in 36 (a scene can fail both).
* **Reported uncertainty is honest but not perfect:** the error was inside the reported +/- in **84%** of accepted measurements and inside 2x the reported +/- in **100%**.
* Per true width, baseline MAE vs agent-accepted MAE: 0.3 mm: 0.261 vs 0.130; 0.5 mm: 0.190 vs 0.078; 1.0 mm: 0.187 vs 0.107; 2.0 mm: 0.115 vs 0.090.

### Failure cases (kept, not hidden)
The 11 accepted-but-out-of-tolerance scenes fall in three groups:
1. **0.3 mm cracks (9 scenes).** 4 clean scenes read 0.50 mm and 5 blurred scenes read 0.45 to 0.63 mm. One rectified pixel is 0.167 mm and a 0.3 mm crack is under 2 pixels wide: this is the resolution floor of the method at 6 px/mm. Do not claim sub-0.3 mm accuracy.
2. **One over-correction:** a 0.5 mm crack at 8 px/mm, tilt 25 deg, blur 2.5 px read 0.27 mm (error 0.23 mm): the blur correction overshot.
3. **One bad one:** 0.5 mm crack, 4.5 px/mm, blur 2.5 px read 1.12 mm (error 0.62 mm, reported +/- 0.35). Low resolution plus blur is the worst combination; a stricter joint gate is listed in future work.

### Bugs this benchmark found (and the fixes)
* The first blur correction subtracted a fixed width term and over-corrected wide cracks (a 2 mm crack under blur read about 1.6 mm). Fix: the correction fades out as the crack gets wider than the blur and only corrects blur *beyond* the optics' own; parameters refit on calibration seeds 500+ (38 scenes: MAE 0.299 to 0.121) and checked on held-out seeds 700+ (23 scenes: MAE 0.226 to 0.092; sharp photos unchanged at 0.092, blurred 0.298 to 0.093).
* The first gauge-card layout put the widest lines outside the reliable window edge, so they were never measured. Fix: tighter layout (`scripts/make_gauge_card.py`).
* A white printed card tripped the glare gate. Fix: gates are evaluated only over the region that will be measured; the protocol below says to expose so paper is not clipped.

## B. Real-photo protocol (printed gauge card)
1. `python scripts/make_gauge_card.py`, print `samples/gauge_card_A4_600dpi.png` at **100%**, matte paper, 600 dpi or better. With a ruler confirm the marker square is 50 mm and the ruler bar is 100 mm. Printer dot gain limits how well the 0.2 and 0.3 mm lines are true to size: say so in your report.
2. Tape the card flat on a wall. Take about 30 phone photos: 3 distances (about 20, 30, 45 cm) x 3 tilts (0, 15, 30 deg) x 2 lightings (soft daylight, indoor light) plus 6 deliberately bad shots (blur, glare, 45 deg tilt, marker partly hidden). Expose so the white paper is about 200 to 235, not clipped.
3. Put them in a folder and run `python scripts/eval_card.py PHOTO_DIR`. It reports, per photo, whether the gates blocked it (and why) and, per gauge line, measured vs printed width. Blocked photos are listed, not discarded.
4. Paste the summary here: photos, blocked share, MAE per width, median error, and the 3 worst photos with the reason.

Real results: **not collected in this build** (no printed card was available in the sandbox). The pipeline path was checked on simulated card photos only (all 15 gauge lines found), which is a software check, not accuracy evidence.

## C. Automated tests (46 Python + 25 UI renders)
`python -m unittest discover -s tests -t .` covers: marker detection and scale, width accuracy against ground truth (0.5, 1.0, 2.0 mm), tilt and roll robustness, tilt estimate, pits not reported as cracks, every gate blocking its bad photo, severity bands, growth across different camera poses, no false growth when unchanged; policy default-deny, separation of duties, close needs evidence, dispute rules; agent re-shoot advice, measurement changing the next action, growth escalation, LLM guardrails (cannot under-react, cannot force a blocked measurement, falls back on failure), retries escalate to a human, repair verification; full case lifecycle, failed repair evidence, dispute upheld, duplicate merge by marker and by 30 m, CSV import, ranking; API security headers, CSRF header, anonymous read-only, blob privacy, visitor counter (unique once per cookie, bots ignored), uploads.
`WHO=anon|res|eng node tests/ui_smoke.js DIR` renders every page for every role against recorded API responses and fails on `undefined`/`NaN`.
