# Demo video script (5:00 max, face on camera, real phone, real wall)

Props: printed marker taped on a real wall near a real crack (or the printed gauge card), phone, a second printed copy rotated to show it works.

| Time | Shot | Say / show |
|---|---|---|
| 0:00-0:25 | **You on camera** (team shown, as required) beside the wall | "Cracks in old buildings get reported as words and blurry photos. HAIRLINE measures them in millimetres and tells you when to look again." |
| 0:25-1:05 | Phone: deliberately take a bad photo (tilted, blurry) | The agent **refuses to measure** and says exactly why with numbers ("tilted 31 degrees, aim for under 18"). Show the gate list. |
| 1:05-1:50 | Retake properly | Overlay, "0.6 +/- 0.13 mm over 117 mm", severity, one-tap case. Point at the 50 mm scale bar and the marker outline. |
| 1:50-2:30 | Open the **trace** screen | Perception -> decision -> action timeline; say "the OpenCV numbers chose this action, not a script". |
| 2:30-3:05 | Second visit from a **different angle** (or the seeded growth case) | Marker frame makes both visits comparable; width +0.7 mm beyond the error bar; agent drafts a review request, sends nothing. |
| 3:05-3:45 | Switch role to engineer | Try to close: denied with the reason. Authorise, add after-repair photo, close succeeds. Show the audit log with the denial. Open a resident dispute. |
| 3:45-4:15 | Architecture slide (`docs/architecture.svg`) | Graviton EC2, CloudFront HTTPS, private S3, DynamoDB, Cognito, optional Bedrock planner with guardrail. |
| 4:15-4:45 | Results slide | Synthetic benchmark: MAE 0.187 to 0.100 mm, p90 0.532 to 0.200 mm; show a failure case; real printed-card numbers if you have them (say if you do not). |
| 4:45-5:00 | Limits and close | "Triage not certification; demo data simulated; widths estimated with uncertainty; no pilot yet; here is the repo." |

Tips: record at the live HTTPS URL; show the visitor counter once; keep the voiceover short and let the screen and the wall do the talking; do not cover failures, show one.
