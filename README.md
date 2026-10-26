# HAIRLINE

**Measure the crack. Know when to look again.**
A phone photo plus a printed marker becomes a crack width in millimetres, with an error bar. An evidence-driven agent decides what happens next: *re-shoot* (and exactly how), *keep watching*, or *ask an engineer*. Closing a ticket needs engineer authorisation **and** after-repair photo evidence; residents can dispute a closure.

Built for the OpenCV AI Competition 2026 (OpenCV 5 + AWS; Agentic Vision path). MIT licensed.

> **Honesty box.** All demo cases are *simulated* (synthetic walls with known crack widths). Widths are *estimates* shown with uncertainty. Severity bands are configurable triage heuristics, not engineering standards. No pilot with a real ward office or housing society has been run yet. Tested and verified on **OpenCV 5.0.0** (`opencv-python-headless==5.0.0.93`) with all 46 unit tests and smoke tests passing; exact pins locked in `requirements.lock.txt`. AWS integrations are written in `infra/template.yaml` (live cloud deployment blocked by local AWS session expiry). Real printed gauge-card study is not measured. See `docs/VERIFICATION_RESULTS.md`, `docs/EVALUATION.md`, and `docs/JUDGING_MAP.md` for full evidence.

## Quick start (local, 2 minutes)
```bash
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/verify_opencv5.py --allow-4         # prints your OpenCV version (use without --allow-4 in production)
HL_SEED_DEMO=1 python -m hairline.server           # http://localhost:8080  (Windows PowerShell: $env:HL_SEED_DEMO=1; python -m hairline.server)
```
Open the site, pick a sample (good / tilted / blurry / glare / no marker), press **Assess**. Sign in (demo) as *resident* or *engineer* to try the full workflow on the seeded cases.

## What to do before submitting (the order matters)
1. **OpenCV 5.** On the deployment machine: `pip install -r requirements.txt && python scripts/verify_opencv5.py && python -m unittest discover -s tests -t .` Then `sh scripts/freeze_deps.sh` and commit `requirements.lock.txt` (exact pins).
2. **Deploy.** `docs/DEPLOY_AWS.md` (CloudFormation: Graviton EC2 + CloudFront HTTPS + private S3 + DynamoDB + Cognito).
3. **Real-photo evidence.** Print `samples/gauge_card_A4_600dpi.png`, photograph it about 30 times, run `python scripts/eval_card.py PHOTOS`, paste the numbers into `docs/EVALUATION.md`.
4. **Video.** Follow `docs/DEMO_SCRIPT.md` (live phone, face on camera, real printed marker).
5. **Freeze.** `python scripts/make_release.py`, git tag, no commits after (checklist in `docs/SUBMISSION_CHECKLIST.md`).

## Repo map
| Path | What |
|---|---|
| `hairline/cvcore.py` | OpenCV engine: marker, homography rectification, tilt, quality gates, blur estimate, segmentation, width in mm, visit comparison |
| `hairline/agent.py` | Perception, decision, action loop; rules planner, optional Bedrock planner, guardrail, trace |
| `hairline/policy.py`, `policy/hairline.policy.json` | Default-deny authorisation, forbid beats permit |
| `hairline/service.py` | Case lifecycle, duplicate merge, repair evidence, dispute, CSV import, visitor counter |
| `hairline/server.py`, `hairline/static/` | Flask API and the web UI (no build step) |
| `hairline/store.py`, `blobs.py`, `auth.py` | SQLite or DynamoDB, local or S3, demo or Cognito auth |
| `hairline/synth.py` | Synthetic walls with known widths (tests, samples, benchmark) |
| `scripts/` | benchmark, calibration, printed-card evaluation, release manifest, import, smoke tests |
| `tests/` | 46 Python tests + front-end runtime smoke test (`tests/ui_smoke.js`) |
| `infra/template.yaml` | CloudFormation for the AWS deployment |
| `docs/` | Technical report, architecture, evaluation, agentic evidence, responsible use, security, auth, pilot plan, judging map, submission pack |

## Commands
```bash
make test          # 46 tests (about 45 s)
make eval-quick    # small synthetic benchmark
python scripts/run_eval.py --shard 0/3 ; ... 1/3 ; ... 2/3 ; python scripts/run_eval.py --merge   # full benchmark in short runs
python scripts/calibrate_blur.py                      # refit the blur correction (disjoint seeds)
python scripts/import_complaints.py samples/complaints_demo.csv --url http://localhost:8080
python scripts/smoke.py https://your-site             # post-deploy check (requires OpenCV 5)
```

## Print the marker
Download from the site (`/api/marker.png?id=7`) or use `samples/hairline_marker_id7_50mm_300dpi.png`. Print at **100%**, then verify with a ruler that the black square is **50 mm**. Stick it flat on the wall within about 15 cm of the crack.

## Visitor counter
`POST /api/visit` is called once per page load. Unique visitors are counted by a random first-party cookie that is hashed with the server secret before storage; no IP address or user agent is stored, and obvious bots are ignored. Shown in the footer and at `/api/stats`.
