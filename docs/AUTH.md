# Authorisation design and the path to Cognito + Verified Permissions

Today (implemented): `policy/hairline.policy.json` is the single source of truth, enforced in-process by `hairline/policy.py` before every state change. Principals come from a Cognito JWT (`cognito:groups` -> role) when `HL_AUTH_MODE=cognito`, or from the labelled demo role picker. The Cognito verification code path and the CloudFormation pool/groups exist but were **not exercised against a live user pool in the build sandbox**.

Not implemented: Amazon Verified Permissions (AVP). The policy file maps one-to-one to Cedar, so moving to AVP means replacing `policy.evaluate` with an `IsAuthorized` call. Reference mapping (illustrative, not executed here):
```
permit (principal in Role::"engineer", action == Action::"authorise", resource)
  when { principal != resource.reporter && resource.open };
forbid (principal, action == Action::"close", resource)
  unless { resource.hasAuthorisation && resource.repairEvidenceOk };
permit (principal in Role::"resident", action == Action::"openDispute", resource) when { resource.status == "CLOSED" };
```
Why not claim AVP now: it was not integrated or tested, and the policy engine already gives default-deny, forbid-over-permit, separation of duties and an audit trail with the same semantics.
