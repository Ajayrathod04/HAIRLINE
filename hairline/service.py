"""Case workflow: reports -> measured visits -> review -> engineer authorisation -> repair evidence -> close -> dispute.
Every state change passes the policy engine and is written to the case audit log (denials included)."""
from __future__ import annotations
import csv
import io
import math
import time
import uuid
import hashlib
from typing import Optional

import cv2
import numpy as np

from . import agent as agent_mod
from . import policy as policy_mod
from .config import Config


class Denied(Exception):
    def __init__(self, decision):
        self.decision = decision
        super().__init__(decision.reason)


class NotFound(Exception):
    pass


class Invalid(Exception):
    pass


def _now() -> int:
    return int(time.time())


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class Service:
    def __init__(self, cfg: Config, store, blobs, policy=None):
        self.cfg, self.store, self.blobs = cfg, store, blobs
        self.policy = policy or policy_mod.load()
        self.planner = agent_mod.make_planner(cfg)

    # ------------------------------------------------------------------ helpers
    def _case(self, cid: str) -> dict:
        c = self.store.get("case", cid)
        if not c:
            raise NotFound(cid)
        return c

    def _audit(self, case: dict, principal: dict, action: str, dec, details: Optional[dict] = None):
        case.setdefault("audit", []).append({"at": _now(), "actor": principal["id"], "name": principal["name"], "role": principal["role"],
                                             "action": action, "allowed": dec.allow if dec is not None else True,
                                             "rules": dec.rules if dec is not None else [], "reason": dec.reason if dec is not None else "system",
                                             "details": details or {}})
        case["audit"] = case["audit"][-200:]

    def _authorize(self, principal: dict, action: str, case: Optional[dict] = None):
        dec = policy_mod.evaluate(self.policy, principal, action, case)
        if not dec.allow:
            if case is not None:
                self._audit(case, principal, action + ".DENIED", dec)
                self.store.put("case", case["id"], case)
            raise Denied(dec)
        return dec

    def allowed_actions(self, principal: dict, case: dict) -> dict:
        out = {}
        for a in ("visit.add", "review.request", "review.authorise", "case.close", "dispute.open", "dispute.resolve"):
            d = policy_mod.evaluate(self.policy, principal, a, case)
            out[a] = {"allow": d.allow, "reason": d.reason}
        return out

    @staticmethod
    def priority_score(meas: Optional[dict], cmp_: Optional[dict]) -> int:
        if not meas or not meas.get("found"):
            return 0
        w = min(meas["width_p90_mm"] / 3.0, 1.0)
        g = min(max((cmp_ or {}).get("delta_width_mm", 0.0), 0.0) / 0.5, 1.0)
        l = min(meas["length_mm"] / 300.0, 1.0)
        return int(round(100 * (0.5 * w + 0.3 * g + 0.2 * l)))

    # ------------------------------------------------------------------ cases
    def next_marker_id(self) -> int:
        used = {c.get("marker_id") for c in self.store.list("case")}
        for i in range(self.cfg.marker_id, 50):
            if i not in used:
                return i
        return self.cfg.marker_id

    def create_case(self, principal: dict, site: str, description: str = "", marker_id: Optional[int] = None,
                    lat: Optional[float] = None, lon: Optional[float] = None, simulated: bool = False,
                    source: str = "app", auto_merge_geo: bool = False) -> dict:
        self._authorize(principal, "case.create")
        site = (site or "").strip()[:120]
        if not site:
            raise Invalid("site name required")
        cases = self.store.list("case")
        open_cases = [c for c in cases if c["status"] != "CLOSED"]
        if marker_id is not None:
            for c in open_cases:
                if c["marker_id"] == marker_id:
                    c.setdefault("duplicate_reports", []).append({"at": _now(), "by": principal["name"], "site": site, "how": "same marker"})
                    self._audit(c, principal, "case.duplicate_merged", None, {"how": "same marker id", "site": site})
                    self.store.put("case", c["id"], c)
                    return {**c, "merged": True}
        near = []
        if lat is not None and lon is not None:
            for c in open_cases:
                if c.get("lat") is not None and haversine_m(lat, lon, c["lat"], c["lon"]) <= self.cfg.dup_radius_m:
                    near.append(c["id"])
            if near and auto_merge_geo:
                c = self._case(near[0])
                c.setdefault("duplicate_reports", []).append({"at": _now(), "by": principal["name"], "site": site, "how": f"within {self.cfg.dup_radius_m:.0f} m"})
                self._audit(c, principal, "case.duplicate_merged", None, {"how": "geo", "site": site})
                self.store.put("case", c["id"], c)
                return {**c, "merged": True}
        case = {"id": uuid.uuid4().hex[:10], "site": site, "description": (description or "")[:500],
                "marker_id": marker_id if marker_id is not None else self.next_marker_id(),
                "lat": lat, "lon": lon, "reported_by": principal["id"], "reported_name": principal["name"],
                "created_at": _now(), "status": "AWAITING_PHOTO", "severity": "unknown", "priority_score": 0,
                "simulated": simulated, "source": source, "visits": [], "reshoot_streak": 0, "review": None,
                "authorisation": None, "repair_evidence_ok": False, "closed_at": None, "dispute": None,
                "duplicate_reports": [], "possible_duplicates": near, "audit": []}
        self._audit(case, principal, "case.create", None, {"site": site, "marker_id": case["marker_id"]})
        self.store.put("case", case["id"], case)
        self.store.incr("cases_created")
        return {**case, "merged": False}

    def list_cases(self) -> list:
        cases = self.store.list("case")
        rank = {"urgent": 4, "priority": 3, "watch": 2, "low": 1}
        cases.sort(key=lambda c: (c["status"] == "CLOSED", -rank.get(c.get("severity"), 0), -c.get("priority_score", 0), -c["created_at"]))
        return cases

    def get_case(self, cid: str) -> dict:
        return self._case(cid)

    # ------------------------------------------------------------------ visits (the agent runs here)
    def add_visit(self, principal: dict, cid: str, image_bytes: bytes, kind: str = "followup", note: str = "") -> dict:
        case = self._case(cid)
        self._authorize(principal, "visit.add", case)
        if kind not in ("baseline", "followup", "after_repair", "dispute"):
            raise Invalid("bad visit kind")
        if kind == "dispute" and case["status"] != "DISPUTED":
            raise Invalid("dispute photos are only accepted while a dispute is open")
        if kind == "after_repair" and not case.get("authorisation"):
            raise Invalid("after-repair evidence is accepted only after an engineer authorised the repair")
        img = self.decode(image_bytes)
        prev_visit = next((v for v in reversed(case["visits"]) if v.get("measurement") and v["kind"] != "after_repair"), None)
        prev_mask = None
        if prev_visit and prev_visit.get("mask_key"):
            raw = self.blobs.get(prev_visit["mask_key"])
            if raw is not None:
                prev_mask = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_GRAYSCALE)
        ctx = agent_mod.Context(kind=kind, expected_marker_id=case["marker_id"],
                                prev_meas=prev_visit["measurement"] if prev_mask is not None else None,
                                prev_mask=prev_mask, failed_attempts=case.get("reshoot_streak", 0))
        res = agent_mod.run_agent(img, self.cfg, ctx, self.planner)
        vid = uuid.uuid4().hex[:8]
        base = f"cases/{cid}/{vid}"
        ok, jpg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 88])  # re-encode strips EXIF/GPS
        self.blobs.put(base + "_photo.jpg", jpg.tobytes(), "image/jpeg")
        visit = {"id": vid, "kind": kind, "at": _now(), "by": principal["name"], "note": (note or "")[:300],
                 "status": res.status, "severity": res.severity, "guidance": res.guidance, "planner": res.planner_used,
                 "quality": {"blocked": res.quality["blocked"], "warned": res.quality["warned"], "gates": res.quality["gates"],
                             "metrics": {k: round(v, 3) for k, v in res.quality["metrics"].items()}},
                 "trace": res.trace, "compare": res.compare, "repair": res.repair,
                 "photo_key": base + "_photo.jpg", "overlay_key": None, "mask_key": None, "measurement": None}
        if res.overlay is not None:
            ok, ov = cv2.imencode(".jpg", res.overlay, [cv2.IMWRITE_JPEG_QUALITY, 85])
            self.blobs.put(base + "_overlay.jpg", ov.tobytes(), "image/jpeg")
            visit["overlay_key"] = base + "_overlay.jpg"
        if res.measurement is not None:
            m = {k: v for k, v in res.measurement.items() if k not in ("mask", "skeleton")}
            visit["measurement"] = m
            ok, mk = cv2.imencode(".png", res.mask * 255)
            self.blobs.put(base + "_mask.png", mk.tobytes(), "image/png")
            visit["mask_key"] = base + "_mask.png"
        case["visits"].append(visit)
        self._apply(case, principal, kind, res, visit)
        self._audit(case, principal, "visit.add", None, {"visit": vid, "kind": kind, "result": res.status, "planner": res.planner_used})
        self.store.put("case", cid, case)
        self.store.incr("visits_processed")
        return {"case": case, "visit": visit}

    def _apply(self, case: dict, principal: dict, kind: str, res, visit: dict):
        s = res.status
        case["reshoot_streak"] = case.get("reshoot_streak", 0) + 1 if s == "NEEDS_RESHOOT" else 0
        if s == "NEEDS_RESHOOT":
            if not any(v.get("measurement") for v in case["visits"][:-1]):
                case["status"] = "NEEDS_RESHOOT"
            return
        if visit.get("measurement"):
            case["severity"] = res.severity
            case["priority_score"] = self.priority_score(visit["measurement"], visit.get("compare"))
        if kind == "dispute":
            confirms = bool(visit.get("measurement") and visit["measurement"]["found"] and visit["measurement"]["width_p90_mm"] >= self.cfg.sev_watch_mm)
            case["dispute"]["evidence_confirms_crack"] = confirms
            case["dispute"]["evidence_visit"] = visit["id"]
            return
        if s == "REPAIR_EVIDENCE_OK":
            case["repair_evidence_ok"] = True
            if case["status"] not in ("AUTHORISED", "CLOSED"):
                case["status"] = "REPAIR_EVIDENCE_OK"
            return
        if s == "REPAIR_NOT_VERIFIED":
            case["repair_evidence_ok"] = False
            self._set_review(case, principal, res.review_reason or "repair not verified", by_agent=True)
            return
        if s == "REVIEW_REQUESTED":
            self._set_review(case, principal, res.review_reason or "agent escalation", by_agent=True)
            return
        if s in ("MEASURED", "NO_CRACK") and case["status"] in ("AWAITING_PHOTO", "NEEDS_RESHOOT", "MEASURED"):
            case["status"] = "MEASURED"

    def _set_review(self, case: dict, principal: dict, reason: str, by_agent: bool):
        case["review"] = {"requested_at": _now(), "reason": reason, "requested_by": "agent" if by_agent else principal["name"]}
        if case["status"] not in ("AUTHORISED", "CLOSED", "DISPUTED"):
            case["status"] = "REVIEW_REQUESTED"

    # ------------------------------------------------------------------ governance
    def request_review(self, principal: dict, cid: str, reason: str = "") -> dict:
        case = self._case(cid)
        dec = self._authorize(principal, "review.request", case)
        self._set_review(case, principal, (reason or "requested by user")[:300], by_agent=False)
        self._audit(case, principal, "review.request", dec, {"reason": reason})
        self.store.put("case", cid, case)
        return case

    def authorise(self, principal: dict, cid: str, note: str = "") -> dict:
        case = self._case(cid)
        dec = self._authorize(principal, "review.authorise", case)
        case["authorisation"] = {"by": principal["id"], "name": principal["name"], "at": _now(), "note": (note or "")[:300]}
        case["status"] = "AUTHORISED"
        self._audit(case, principal, "review.authorise", dec, {"note": note})
        self.store.put("case", cid, case)
        return case

    def close(self, principal: dict, cid: str, note: str = "") -> dict:
        case = self._case(cid)
        dec = self._authorize(principal, "case.close", case)
        case["status"], case["closed_at"], case["closure_note"] = "CLOSED", _now(), (note or "")[:300]
        self._audit(case, principal, "case.close", dec, {"note": note})
        self.store.put("case", cid, case)
        return case

    def open_dispute(self, principal: dict, cid: str, reason: str) -> dict:
        case = self._case(cid)
        dec = self._authorize(principal, "dispute.open", case)
        if not (reason or "").strip():
            raise Invalid("dispute reason required")
        case["status"] = "DISPUTED"
        case["dispute"] = {"opened_by": principal["name"], "at": _now(), "reason": reason[:500], "evidence_confirms_crack": None, "resolution": None}
        self._audit(case, principal, "dispute.open", dec, {"reason": reason[:200]})
        self.store.put("case", cid, case)
        return case

    def resolve_dispute(self, principal: dict, cid: str, decision: str, note: str = "") -> dict:
        case = self._case(cid)
        dec = self._authorize(principal, "dispute.resolve", case)
        if decision not in ("uphold", "reject"):
            raise Invalid("decision must be uphold or reject")
        case["dispute"]["resolution"] = {"decision": decision, "by": principal["name"], "at": _now(), "note": (note or "")[:300]}
        if decision == "uphold":  # resident was right: reopen
            case["status"] = "REVIEW_REQUESTED"
            case["authorisation"], case["repair_evidence_ok"], case["closed_at"] = None, False, None
            case["review"] = {"requested_at": _now(), "reason": "dispute upheld", "requested_by": principal["name"]}
        else:
            case["status"] = "CLOSED"
        self._audit(case, principal, "dispute.resolve", dec, {"decision": decision, "note": note})
        self.store.put("case", cid, case)
        return case

    # ------------------------------------------------------------------ io
    def decode(self, data: bytes) -> np.ndarray:
        if not data or len(data) > self.cfg.max_upload_mb * 1024 * 1024:
            raise Invalid("image missing or too large")
        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise Invalid("not a decodable image")
        h, w = img.shape[:2]
        m = max(h, w)
        if m > self.cfg.max_image_side:
            s = self.cfg.max_image_side / m
            img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
        return img

    def quick_assess(self, image_bytes: bytes) -> dict:
        """Stateless 'try it' run: no case, nothing stored."""
        img = self.decode(image_bytes)
        res = agent_mod.run_agent(img, self.cfg, agent_mod.Context(kind="quick"), self.planner)
        out = {"status": res.status, "severity": res.severity, "guidance": res.guidance, "planner": res.planner_used,
               "quality": {"blocked": res.quality["blocked"], "warned": res.quality["warned"], "gates": res.quality["gates"],
                           "metrics": {k: round(v, 3) for k, v in res.quality["metrics"].items()}},
               "trace": res.trace, "measurement": None, "overlay_jpeg": None}
        if res.measurement is not None:
            out["measurement"] = {k: v for k, v in res.measurement.items() if k not in ("mask", "skeleton")}
        if res.overlay is not None:
            ok, ov = cv2.imencode(".jpg", res.overlay, [cv2.IMWRITE_JPEG_QUALITY, 85])
            out["overlay_jpeg"] = ov.tobytes()
        self.store.incr("quick_assessments")
        return out

    def import_csv(self, principal: dict, text: str) -> dict:
        """Complaint intake from a ward office / society register. Columns: site,description,lat,lon,marker_id."""
        self._authorize(principal, "import.csv")
        rows = list(csv.DictReader(io.StringIO(text)))
        if len(rows) > 500:
            raise Invalid("max 500 rows per import")
        created = merged = 0
        errors = []
        for n, r in enumerate(rows, start=2):
            try:
                lat = float(r["lat"]) if r.get("lat") not in (None, "") else None
                lon = float(r["lon"]) if r.get("lon") not in (None, "") else None
                mid = int(r["marker_id"]) if r.get("marker_id") not in (None, "") else None
                res = self.create_case(principal, r.get("site", ""), r.get("description", ""), mid, lat, lon, source="import", auto_merge_geo=True)
                merged += 1 if res.get("merged") else 0
                created += 0 if res.get("merged") else 1
            except Exception as e:
                errors.append({"row": n, "error": str(e)})
        return {"created": created, "merged_duplicates": merged, "errors": errors}

    # ------------------------------------------------------------------ visitors + stats
    def track_visitor(self, visitor_id: str, is_bot: bool = False) -> dict:
        if not is_bot and visitor_id:
            h = hashlib.sha256((visitor_id + self.cfg.secret_key).encode()).hexdigest()[:32]
            if self.store.put_if_absent("visitor", h, {"first": _now()}):
                self.store.incr("unique_visitors")
            self.store.incr("page_views")
        return self.stats()

    def stats(self) -> dict:
        return {"unique_visitors": self.store.counter("unique_visitors"), "page_views": self.store.counter("page_views"),
                "cases": len(self.store.list("case")), "visits_processed": self.store.counter("visits_processed"),
                "quick_assessments": self.store.counter("quick_assessments")}
