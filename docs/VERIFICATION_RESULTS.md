# HAIRLINE Verification Results

**Date:** 2026-10-27 (00:19 IST)
**Host Machine:** Windows 11 (AMD64)
**Python Runtime:** CPython 3.12.14
**Package Manager:** uv 0.12.13
**OpenCV Engine:** OpenCV 5.0.0 (`opencv-python-headless==5.0.0.93`)
**Core Dependencies:** NumPy 2.5.4, scikit-image 0.26.0, SciPy 1.18.1, Flask 3.1.3, Gunicorn 26.2.0, Boto3 1.43.118, PyJWT 2.15.1

---

## 1. OpenCV 5 Verification Gate

**Command:**
```powershell
.venv\Scripts\python.exe scripts/verify_opencv5.py
```

**Result:** `PASSED` (Exit code: 0)
**Actual Output:**
```
OpenCV version: 5.0.0 | major: 5
cv2.aruco: present
cv2.dnn: present
pipeline smoke test: OK, width 0.83 mm (truth 1.00)
```

---

## 2. Automated Python Test Suite

**Command:**
```powershell
.venv\Scripts\python.exe -u -m unittest discover -s tests -t .
```

**Result:** `PASSED` (Exit code: 0)
**Actual Output:**
```
Ran 46 tests in 78.893s

OK
```
All 46 test cases covering CV core, ArUco detection, homography rectification, quality gating, agentic decision loop, policy authorisation, API endpoints, visitor counter, and lifecycle workflows passed with 0 failures and 0 errors.

---

## 3. Local Server Health & Smoke Test

**Command:**
```powershell
# Background server run on port 8080:
.venv\Scripts\python.exe scripts/smoke.py http://127.0.0.1:8080
```

**Result:** `PASSED` (Exit code: 0)
**Actual Output:**
```
health: {'auth_mode': 'demo', 'blobs': 'local', 'built_at': '2026-10-26T18:49:01Z', 'opencv': '5.0.0', 'opencv_major': 5, 'planner': 'rules', 'release': '201d6f312e46e1c6cb000e226c188904863343e0f53e5019e9bdea4653f62299', 'status': 'ok', 'store': 'sqlite', 'version': '1.0.0'}
stats: {'cases': 0, 'page_views': 0, 'quick_assessments': 0, 'unique_visitors': 0, 'visits_processed': 0}
cases: 0
SMOKE OK
```

---

## 4. Synthetic Benchmark (OpenCV 5)

**Command:**
```powershell
.venv\Scripts\python.exe scripts/run_eval.py --quick
```

**Result:** `PASSED` (Exit code: 0)
**Actual Summary:**
- 24 synthetic scenes evaluated with known ground-truth crack widths (0.5 mm, 1.0 mm) across tilt and noise.
- **Naive baseline (accept every first photo):** MAE 0.266 mm, median 0.167 mm, p90 0.532 mm (8 scenes outside tolerance).
- **Agent (quality gates + blur correction):** MAE 0.112 mm, median 0.085 mm, p90 0.167 mm (only 1 false accept).
- **Agent compliant re-shoot:** MAE 0.075 mm, median 0.050 mm.

---

## 5. Status of Other Verification Categories

| Category | Status | Details / Notes |
|---|---|---|
| **OpenCV 5 Engine** | **VERIFIED** | OpenCV 5.0.0 installed, `verify_opencv5.py` passed, test suite passed. |
| **Dependency Lockfile** | **GENERATED** | Genuine `requirements.lock.txt` generated directly from the OpenCV 5 passing environment. |
| **AWS Cloud Deployment** | **NOT DEPLOYED (BLOCKED)** | AWS CLI authentication failed (`Your session has expired. Please reauthenticate using 'aws login'`). CloudFormation template `infra/template.yaml` is intact. |
| **Real Printed Gauge-Card Study** | **NOT MEASURED** | Physical card photos taken in real environments with physical cameras have not been captured. Stated truthfully as not measured. |
| **Live Browser UI Inspection** | **NOT PERFORMED** | Reserved for manual user check in browser per non-negotiable constraints. |
| **AWS Graviton / Arm COOL Workload** | **NOT CLAIMED** | COOL is not claimed as no Graviton ARM workload and baseline comparison were measured. |
