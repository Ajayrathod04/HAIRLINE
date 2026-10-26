# Lessons taken from the BOOND submission (and what we did differently)

BOOND (water-leak reporting: map, 30 m duplicate merge, priority by estimated impact, engineer authorisation with Cedar, after-repair photo evidence, resident dispute, honest labelling of simulated and estimated data) was praised for its real civic problem, its governance loop and its transparency. Its judged weaknesses and our response:

| BOOND weakness | HAIRLINE response | Honest status |
|---|---|---|
| Cedar used as a library, no Cognito / Verified Permissions | Same governance loop; default-deny policy file; Cognito pool + groups + JWT verification path; mapping to Cedar/AVP documented | AVP **not** integrated; Cognito path not run live |
| Front end from a raw public S3 URL, no CloudFront | One origin behind CloudFront HTTPS; private bucket; CSP and security headers | Template not deployed in the build |
| All data simulated, no path to real systems | CSV/API import, per-case markers, pilot plan, printed-card real-photo protocol | Still no real pilot; real-card numbers pending |
| A frontend commit after the deadline | `RELEASE.json` file-hash manifest, `/api/health` shows the release hash, tag-and-freeze checklist | Needs the author to follow the checklist |
| Demo mostly narration over screens | Demo script built on a live phone, a real printed marker, a face-on-camera intro and live failure cases | Needs recording |
| 30 backend tests | 46 Python tests + a front-end runtime smoke test + a 144-scene benchmark with failure cases | OpenCV 5 run still pending |
| Standard serverless stack | Stack chosen for the workload: OpenCV native libs on Graviton; alternative documented | Not a weakness per se |

What we kept: simulated and estimated data are labelled everywhere; the priority formula is visible; closure is evidence-gated; disputes exist; duplicates merge.
What is new relative to a leak-reporting tool: the evidence is **measured by OpenCV in millimetres** and the **agent's next action depends on that measurement**.
