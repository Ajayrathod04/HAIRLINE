# Path to real municipal and society data

Status: **no pilot has been run.** This is the plan and the software that supports it.

## What exists now
* `POST /api/import` and `scripts/import_complaints.py`: engineer imports a complaint register (CSV: `site,description,lat,lon,marker_id`). Reports within 30 m of an open case merge automatically; the same marker id merges into the open case; errors are returned per row.
* Per-case printed marker ids (0 to 49) so a physical location maps to one case.
* Ranked case list, audit log, engineer authorisation, after-repair evidence, resident dispute.

## Pilot design (4 weeks, one ward office or one housing society)
| Week | Activity | Success measure |
|---|---|---|
| 0 | Agree scope and consent with the committee or ward engineer; print 20 markers; train 2 engineers and 10 residents (15 minutes) | Written consent; data-handling note signed |
| 1 | Import the existing complaint register; residents baseline 20 cracks | % of photos accepted on the first try; median retakes |
| 2-3 | Follow-up photos; engineers triage from the ranked list | Time to first engineer decision vs the old process; growth cases found |
| 4 | Close 3 to 5 repairs with after-repair evidence; run one dispute drill | Evidence-gated closures; resident feedback |
Report honestly: acceptance rate, retakes, disagreement between HAIRLINE's severity and the engineer's judgement, anything the tool got wrong.

## What a real integration still needs
Authentication through the organisation's identity (Cognito federation), an agreed data-retention period, a written statement of liability (triage aid only), accessibility testing with real users, and export to the ward's complaint system (CSV out is trivial to add; a vendor API depends on the system).

## Who to approach
Housing-society committees and ward engineering sections in your own area (you can reach them; this plan does not claim any relationship exists).
