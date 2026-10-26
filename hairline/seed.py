"""Demo data. EVERY case is flagged simulated: photos are synthetic renders with known widths, and the
whole pipeline (marker, gates, measurement, comparison, policy) runs for real on them."""
from __future__ import annotations
import cv2

from . import synth
from .auth import demo_principal


def _jpg(img) -> bytes:
    ok, b = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return b.tobytes()


def seed_demo(svc) -> None:
    cfg = svc.cfg
    res = demo_principal("resident", "Asha (demo resident)")
    eng = demo_principal("engineer", "Eng. Rao (demo engineer)")

    def case(site, desc, mid, lat, lon):
        return svc.create_case(res, site + " [SIMULATED]", desc, mid, lat, lon, simulated=True, source="seed")["id"]

    def shot(seed, widths, mid, **kw):
        img, _ = synth.render(seed=seed, widths_mm=widths, marker_id=mid, cfg=cfg, **kw)
        return _jpg(img)

    # A: growing crack -> agent escalates
    a = case("Stairwell wall, Sunrise Society", "Hairline crack widening after monsoon", 7, 19.0760, 72.8777)
    svc.add_visit(res, a, shot(11, [0.5], 7, tilt_deg=(8, 0)), "baseline")
    svc.add_visit(res, a, shot(11, [1.2], 7, tilt_deg=(0, 12), ppm=6.5), "followup")
    # B: stable thin crack -> keep watching
    b = case("Compound wall, Gate 2", "Thin crack near the gate pillar", 8, 19.0765, 72.8790)
    svc.add_visit(res, b, shot(12, [0.3], 8), "baseline")
    # C: urgent -> escalated + engineer authorised, awaiting repair evidence
    c = case("Ceiling corner, Flat 4B", "Wide diagonal crack above the window", 9, 19.0801, 72.8702)
    svc.add_visit(res, c, shot(13, [3.4], 9, tilt_deg=(5, 5)), "baseline")
    svc.authorise(eng, c, "Schedule structural check and repair this week.")
    # D: full lifecycle -> closed with after-repair evidence
    d = case("Staircase landing, Block C", "Crack along the landing slab", 10, 19.0733, 72.8811)
    svc.add_visit(res, d, shot(14, [1.2], 10), "baseline")
    svc.authorise(eng, d, "Repair approved.")
    svc.add_visit(res, d, shot(14, [], 10, tilt_deg=(6, 4)), "after_repair", "Repaired and repainted")
    svc.close(eng, d, "Closed after engineer review of after-repair evidence.")
    # E: closed, then disputed by the resident
    e = case("Passage wall, Block A", "Crack reappeared after repaint", 11, 19.0742, 72.8820)
    svc.add_visit(res, e, shot(15, [0.9], 11), "baseline")
    svc.authorise(eng, e, "Patch and repaint.")
    svc.add_visit(res, e, shot(15, [], 11), "after_repair")
    svc.close(eng, e, "Closed.")
    svc.open_dispute(res, e, "The crack is back after two weeks.")
    svc.add_visit(res, e, shot(15, [0.9], 11, tilt_deg=(0, 6)), "dispute", "Photo taken today")
    # F: unusable photo -> agent asks for a re-shoot
    f = case("Water tank wall, Terrace", "Crack under the tank", 12, 19.0770, 72.8760)
    svc.add_visit(res, f, shot(16, [0.6], 12, tilt_deg=(40, 0), blur=2.5), "baseline")
