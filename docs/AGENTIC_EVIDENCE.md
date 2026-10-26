# Agentic Vision: evidence against the rubric

Rule being met: image results must change a later plan, tool call, action, or request for human approval; a chatbot explaining a fixed result is not enough. A coding assistant writing the project does not count, so the evidence below is about the *running* agent.

## Workflow (perception, decision, action)
```
photo -> [1 detect_marker + quality_gates] --blocked--> RESHOOT (advice from the failing gate's numbers)
                         |--passed--> [2 segment_and_measure] --> severity, width +/- unc
                                         |-- prior visit? --> [3 compare_prev] (same marker frame)
                                         |-- after-repair? --> [3 verify_repair] (area/length vs pre-repair)
                                         v
                              decide: accept | request_review (drafted, never sent)
repeated failures (3 unusable photos) --> request_review "engineer should inspect in person"
```

## Where OpenCV output changes what the system does next
| Observation (from OpenCV) | Next action chosen |
|---|---|
| marker not found / tilt 45 deg / blur / glare / too far / too dark | `reshoot` with advice built from the measured value and its limit; measurement is not attempted |
| p90 width below the priority band, no growth | `accept` and keep monitoring |
| p90 width in the priority or urgent band | `request_review` (draft for an engineer) |
| width grew beyond the error bar between two visits | `compare_prev` then `request_review`, even if severity is low |
| after-repair photo still shows the crack | `REPAIR_NOT_VERIFIED`, closure stays blocked |
| three unusable photos in a row | stop asking the resident, `request_review` for an in-person look |

Real traces recorded from the running agent: `docs/traces/sample_tilted_45deg.json` (blocked at step 1, action `reshoot`), `sample_good_0p6mm.json` (measure then accept), `sample_wide_2p0mm.json` (measure then `request_review`). The same code produced different next actions from different measurements.

## Autonomy and human control
* The agent may autonomously: ask for a re-shoot, measure, compare, draft a review request.
* The agent may **not**: notify anyone, authorise, close, or change permissions. Authorisation and closure are engineer-only and fail closed (policy rules P-AUTHORISE, P-CLOSE, F-CLOSE-NEEDS-EVIDENCE).
* Separation of duties: a reporter cannot authorise or close their own report.
* LLM planner (optional, Bedrock): constrained to the legal actions for the current state; if it picks `accept` where the rules require review, the guardrail overrides it and says so in the trace; if the model errors, rules take over (`bedrock->rules-fallback`). Not exercised against a live Bedrock account in the build.

## Task success, failure handling, observability
* **Task success:** synthetic benchmark (error and out-of-tolerance rates, accepted vs naive) and the printed-card protocol (`docs/EVALUATION.md`).
* **Failure handling:** every gate has a test; wrong marker id is rejected; undecodable uploads rejected; LLM failure falls back; retries escalate to a human; repair evidence that still shows the crack blocks closure.
* **Observability:** each visit stores the full trace (step, tool, numeric observation, planner, action, reason, milliseconds). The UI shows it as a timeline; JSON request logs go to CloudWatch; `/api/health` reports OpenCV version, planner and release hash.

## Tests that prove it
`tests/test_agent.py`: `test_bad_photo_triggers_reshoot_with_specific_advice`, `test_measurement_changes_next_action`, `test_growth_escalates_even_when_severity_is_low`, `test_guardrail_blocks_llm_from_under_reacting`, `test_guardrail_blocks_illegal_action`, `test_llm_failure_falls_back_to_rules`, `test_repeated_failures_escalate_to_human`, `test_repair_verification`.
