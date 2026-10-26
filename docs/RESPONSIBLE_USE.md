# Responsible use

| Risk | What HAIRLINE does |
|---|---|
| Treating an estimate as a safety certificate | Triage only. Every width is shown with +/- uncertainty; the footer and About page say so. No "safe" verdict exists in the product. |
| Over-trusting AI | The agent cannot notify, authorise or close. Escalation is a *draft* for a human. The LLM planner (optional) is boxed in by a guardrail. |
| A bad photo producing a confident number | Quality gates run first and block measurement; advice names the failing value. |
| Closing a ticket without proof | Closure needs engineer authorisation AND after-repair photo evidence; reporters cannot close their own cases; residents can dispute and force re-review. |
| Fake or inflated results | Demo data is badged SIMULATED; severity and priority are labelled estimates; the benchmark reports failures and the resolution floor; no real-world accuracy is claimed until the printed-card results are in. |
| Privacy | EXIF/GPS dropped by re-encoding; photos stay in a private bucket and are shown only through the API (real cases need sign-in); the visitor counter stores a salted hash of a random cookie, no IP or user agent; the capture guidance asks for walls, not people or plates. |
| Data rights | Users upload their own photos; MIT code; synthetic data generated here; no scraped or third-party datasets. |
| Misuse as surveillance | Per-case, per-marker, consent-based monitoring of a wall the user is entitled to photograph; no face, plate or person detection exists in the code. |
| Unfair ranking | The priority score is a visible, simple formula (width, growth, length) with no demographic inputs; a human decides. |
| Abuse and load | Upload size cap (12 MB), rate limits, CSRF header, CSP, default-deny permissions, audit of denials. |
| Safety-critical situations | UI copy and docs tell users that a wide, growing or sudden crack, bulging, or water ingress needs an engineer or the authority immediately, not an app. |

Known gaps: no accessibility audit with assistive-technology users; no independent security review; no real-world pilot (see `docs/PILOT_PLAN.md`).
