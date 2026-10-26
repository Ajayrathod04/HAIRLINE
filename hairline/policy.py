"""Fail-closed authorisation policy (default deny, forbid beats permit, every decision auditable).

policy/hairline.policy.json is the single source of truth. docs/AUTH.md maps it to Cedar / Amazon
Verified Permissions for production; this module is the in-process enforcement point used by the API.
"""
from __future__ import annotations
import json
import os
from dataclasses import dataclass

DEFAULT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "policy", "hairline.policy.json")


@dataclass
class Decision:
    allow: bool
    rules: list
    reason: str

    def as_dict(self):
        return {"allow": self.allow, "rules": self.rules, "reason": self.reason}


def load(path: str = DEFAULT_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _conds(case: dict, principal: dict) -> dict:
    case = case or {}
    return {
        "not_reporter": principal.get("id") != case.get("reported_by"),
        "case_closed": case.get("status") == "CLOSED",
        "case_disputed": case.get("status") == "DISPUTED",
        "has_authorisation": bool((case.get("authorisation") or {}).get("by")),
        "repair_evidence_ok": bool(case.get("repair_evidence_ok")),
        "case_open": case.get("status") not in (None, "CLOSED"),
    }


def evaluate(policy: dict, principal: dict, action: str, case: dict | None = None) -> Decision:
    role = principal.get("role", "anonymous")
    conds = _conds(case, principal)
    for r in policy["rules"]:
        if r["effect"] != "forbid":
            continue
        if action in r["actions"] and (not r.get("roles") or role in r["roles"]):
            failing = [c for c in r.get("unless", []) if not conds.get(c, False)]
            if failing:
                return Decision(False, [r["id"]], f"forbidden by {r['id']}: requires {', '.join(failing)}")
    for r in policy["rules"]:
        if r["effect"] != "permit":
            continue
        if action in r["actions"] and role in r["roles"] and all(conds.get(c, False) for c in r.get("when", [])):
            return Decision(True, [r["id"]], f"permitted by {r['id']}")
    return Decision(False, [], f"default deny: role '{role}' may not '{action}' here")
