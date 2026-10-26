# HAIRLINE: technical report
OpenCV AI Competition 2026 (OpenCV 5 + AWS). Path entered: Overall + Agentic Vision. COOL: not claimed.

## 1. Summary
HAIRLINE turns a phone photo of a wall crack, taken next to a printed 50 mm ArUco marker, into a **crack width in millimetres with an uncertainty**, and runs a perception-decision-action loop around it. When the photo cannot support a measurement the agent says exactly how to retake it; when the crack is serious or growing it drafts a review request for an engineer. A governance layer (default-deny policy, separation of duties, after-repair evidence, resident dispute, audit log) decides what may happen next. Demo data is simulated and labelled as such.

## 2. Problem and users
Cracks in old Indian buildings (Mumbai's monsoon season is the motivating case) are reported with words and unscaled photos, so residents, society committees and ward engineers cannot tell a stable hairline crack from a growing one, cannot compare visits, and cannot verify that a repair happened. Users: **residents** (photograph and report), **engineers** (triage, authorise, close), **committees/wards** (ranked list, import of complaint registers). HAIRLINE is a triage aid: it never certifies structural safety.

## 3. Architecture
See `docs/ARCHITECTURE.md` and `docs/architecture.svg`. One Flask service on a Graviton EC2 instance behind CloudFront, private S3, DynamoDB, Cognito, CloudWatch; optional Bedrock planner.

## 4. OpenCV implementation
Only long-stable APIs are used so the code runs on 4.x and 5.x; `scripts/verify_opencv5.py` asserts major version 5 and exercises the pipeline on the target machine.
* **Marker and scale:** `cv2.aruco.ArucoDetector` (DICT_4X4_50, sub-pixel corner refinement), per-case marker id. Marker side in pixels gives source px/mm.
* **Rectification:** `cv2.getPerspectiveTransform` from the four marker corners to a 50 mm square on a 6 px/mm canvas; `cv2.warpPerspective` (bicubic) for the photo and for a validity mask. The wall plane is metric and *marker-anchored*, so two visits from different poses live in the same frame.
* **Tilt without intrinsics:** the local Jacobian of the homography at the marker centre; tilt = acos(s_min / s_max) of its singular values.
* **Quality gates:** px/mm, tilt, sharpness (top-1% Sobel gradient of the marker's edges over its contrast), coverage of the window, glare (saturated fraction), exposure, contrast. Marker sharpness also yields a blur radius estimate.
* **Segmentation:** Gaussian blur, black-hat via `cv2.morphologyEx` with a 10 mm closing kernel, threshold at median + 4.5 x 1.4826 x MAD (robust to textured walls), `cv2.connectedComponentsWithStats`, skeleton length and elongation filters (pits and stains are rejected), half-maximum re-threshold.
* **Width:** `cv2.distanceTransform` on the mask, width = 2 x DT - 1 on skeleton pixels; blur correction (fitted on calibration seeds) fades out for cracks wider than the blur; reported statistic is p90 with uncertainty = hypot(0.75 to 1.0 px, 0.5 x excess blur).
* **Comparison:** dilate the previous mask by 0.7 mm, new crack length outside it, delta in p90 width against combined uncertainty.
* **Privacy:** `cv2.imencode` re-encodes uploads (drops EXIF/GPS).

## 5. Agentic design
`agent.run_agent`: step 1 gates, step 2 measure, step 3 compare or verify repair, then accept or request review. The planner is rules by default, or an LLM on Amazon Bedrock; in both cases a guardrail limits the LLM to the actions legal in the current state and overrides it when the evidence demands escalation. LLM errors fall back to rules and are recorded in the trace. The agent has **no actuators**: it cannot message anyone, only draft a review request. Details and sample traces: `docs/AGENTIC_EVIDENCE.md`.

## 6. AWS deployment
`infra/template.yaml`: Graviton EC2 (Docker, gunicorn), CloudFront with HTTPS and no caching of the API, private S3 (SSE, versioning, TLS-only), DynamoDB (PITR), Cognito pool with `resident` and `engineer` groups, CloudWatch Logs via the Docker awslogs driver, IAM least privilege, SSM instead of SSH. **Not deployed or linted in the build sandbox**; `docs/DEPLOY_AWS.md` lists the validation steps. Graviton vs x86 timing is measured by `scripts/run_eval.py` on each machine (not yet collected).

## 7. Evaluation
Synthetic benchmark (144 scenes, known widths): MAE 0.187 mm (naive) vs 0.100 mm (agent-accepted), p90 0.532 vs 0.200 mm, out-of-tolerance 25% vs 16%; error within the reported uncertainty 84% (100% within 2x). Failure cases and bugs found are in `docs/EVALUATION.md`. Real-photo accuracy is measured by the printed-card protocol and is **pending**.

## 8. Limitations
Planar surfaces only; marker must be visible and flat; cracks at or below about 0.3 mm are at the resolution floor; lens distortion is not calibrated; blur correction is fitted on synthetic data; severity bands are heuristics; repair evidence is visual and does not certify a structural fix; no real-world pilot yet; AWS services not run live in the build; OpenCV 5 is verified in runtime (5.0.0, exact pins in `requirements.lock.txt`).

## 9. Responsible use
`docs/RESPONSIBLE_USE.md`: triage not certification, uncertainty always shown, human authorisation for every consequential step, simulated/estimated labelling, privacy (EXIF stripped, hashed visitor ids, no faces or plates requested), data minimisation, audit trail, fail-closed permissions.

## 10. Reproducibility
Pinned dependency flow (`requirements.txt` -> `scripts/freeze_deps.sh` -> `requirements.lock.txt`), seeded synthetic data, `scripts/run_eval.py`, 46 tests, `RELEASE.json` manifest of file hashes.
