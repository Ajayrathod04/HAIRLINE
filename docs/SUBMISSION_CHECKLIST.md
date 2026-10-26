# Submission checklist (OpenCV AI Competition 2026)

Deadline: Devpost banner says **Oct 26, 11:45 PM PDT = Tue 27 Oct, 12:15 PM IST** (other pages say 11:59 PM PT). Use the earlier. Target: **submitted by Mon 26 Oct, 11:00 PM IST**. Re-read the Rules and Updates tabs once more before you press submit.

## Requirement -> where it is
| Requirement (from the page) | Artifact | Status |
|---|---|---|
| OpenCV 5 for substantive image analysis | `hairline/cvcore.py` | Verified on OpenCV 5.0.0 (`scripts/verify_opencv5.py` and 46 tests passed); see `docs/VERIFICATION_RESULTS.md` |
| Meaningful component on AWS | `infra/template.yaml`, `docs/DEPLOY_AWS.md` | Deploy and record the `SiteUrl` |
| Technical report | `docs/TECHNICAL_REPORT.md` | Export to PDF |
| Code repo with pinned deps, build, deploy, test steps | whole repo, `requirements.lock.txt` (created on verified OpenCV 5 env), README | Done (`requirements.lock.txt` generated) |
| Architecture diagram | `docs/architecture.svg` | Export PNG |
| Working web endpoint | CloudFront `SiteUrl` | Deploy |
| Video, 5 minutes or less, shows team, app, architecture, results | `docs/DEMO_SCRIPT.md` | Record, upload unlisted |
| Evaluation evidence incl. failure cases | `docs/EVALUATION.md`, `eval/results.json` | Add printed-card results |
| Responsible-use considerations | `docs/RESPONSIBLE_USE.md` | done |
| Agentic Vision evidence | `docs/AGENTIC_EVIDENCE.md`, `docs/traces/` | done; record the live trace in the video |

## Order of work
1. Create the AWS stack (45 min), run the OpenCV 5 check, run the tests on the instance, freeze deps, commit the lock file.
2. Print the marker and the gauge card, take about 30 photos (30 min), run `scripts/eval_card.py`, paste results into `docs/EVALUATION.md`.
3. Record the video (60 to 90 min including retakes).
4. Fill the Devpost form from `docs/DEVPOST_TEXT.md`; add the repo link, video link, endpoint, report PDF, diagram PNG.
5. **Freeze:** `python scripts/make_release.py`, commit, `git tag v1.0-submission`, push. **No commits after this.** (A late "final polish" commit cost another entry points.)
6. Submit, then open the live site once from a phone to confirm the endpoint and the visitor counter work.

## Do not
Claim COOL, AVP, real accuracy, or a pilot unless they exist. Leave simulated data unlabelled. Edit the repository after the freeze tag.
