import unittest
from tests.helpers import render, jpg, make_service, RES, ENG, ENG2
from hairline.service import Denied, Invalid


def shot(seed, widths, mid=7, **kw):
    img, _ = render(seed=seed, widths_mm=widths, marker_id=mid, **kw)
    return jpg(img)


class Workflow(unittest.TestCase):
    def setUp(self):
        self.svc, self.cfg = make_service()

    def test_full_lifecycle_with_evidence_gate(self):
        s = self.svc
        c = s.create_case(RES, "Stairwell", "crack", marker_id=7)
        cid = c["id"]
        r = s.add_visit(RES, cid, shot(51, [1.4], 7), "baseline")
        self.assertEqual(r["case"]["status"], "REVIEW_REQUESTED")
        with self.assertRaises(Invalid):          # evidence before authorisation is refused
            s.add_visit(RES, cid, shot(51, [], 7), "after_repair")
        with self.assertRaises(Denied):           # resident cannot authorise
            s.authorise(RES, cid)
        s.authorise(ENG, cid, "go")
        with self.assertRaises(Denied) as cm:     # authorised but no repair evidence yet
            s.close(ENG, cid)
        self.assertIn("F-CLOSE-NEEDS-EVIDENCE", cm.exception.decision.rules)
        s.add_visit(RES, cid, shot(51, [], 7, tilt_deg=(0, 5)), "after_repair")
        self.assertTrue(s.get_case(cid)["repair_evidence_ok"])
        closed = s.close(ENG, cid, "ok")
        self.assertEqual(closed["status"], "CLOSED")
        # denials are in the audit log too
        self.assertTrue(any(a["action"].endswith(".DENIED") for a in closed["audit"]))

    def test_failed_repair_evidence_blocks_closure(self):
        s = self.svc
        cid = s.create_case(RES, "Wall", marker_id=8)["id"]
        s.add_visit(RES, cid, shot(52, [1.4], 8), "baseline")
        s.authorise(ENG, cid)
        s.add_visit(RES, cid, shot(52, [1.4], 8, tilt_deg=(0, 5)), "after_repair")
        self.assertFalse(s.get_case(cid)["repair_evidence_ok"])
        with self.assertRaises(Denied):
            s.close(ENG, cid)

    def test_dispute_flow_uphold_reopens(self):
        s = self.svc
        cid = s.create_case(RES, "Landing", marker_id=9)["id"]
        s.add_visit(RES, cid, shot(53, [1.2], 9), "baseline")
        s.authorise(ENG, cid)
        s.add_visit(RES, cid, shot(53, [], 9), "after_repair")
        s.close(ENG, cid)
        with self.assertRaises(Denied):
            s.open_dispute(ENG, cid, "engineers cannot dispute")
        s.open_dispute(RES, cid, "it is back")
        self.assertEqual(s.get_case(cid)["status"], "DISPUTED")
        s.add_visit(RES, cid, shot(53, [1.2], 9, tilt_deg=(0, 6)), "dispute")
        self.assertTrue(s.get_case(cid)["dispute"]["evidence_confirms_crack"])
        s.resolve_dispute(ENG, cid, "uphold", "confirmed")
        c = s.get_case(cid)
        self.assertEqual(c["status"], "REVIEW_REQUESTED")
        self.assertFalse(c["repair_evidence_ok"])
        self.assertIsNone(c["authorisation"])

    def test_reporter_cannot_authorise_own_report(self):
        s = self.svc
        cid = s.create_case(ENG, "Engineer-reported", marker_id=10)["id"]
        with self.assertRaises(Denied):
            s.authorise(ENG, cid)
        s.authorise(ENG2, cid)

    def test_duplicate_merge_by_marker_and_geo(self):
        s = self.svc
        a = s.create_case(RES, "A", marker_id=11, lat=19.0, lon=72.0)
        b = s.create_case(RES, "A again", marker_id=11)
        self.assertTrue(b["merged"])
        self.assertEqual(b["id"], a["id"])
        c = s.create_case(RES, "Near", marker_id=12, lat=19.0001, lon=72.0001)  # ~15 m away
        self.assertEqual(c["possible_duplicates"], [a["id"]])
        far = s.create_case(RES, "Far", marker_id=13, lat=19.1, lon=72.1)
        self.assertEqual(far["possible_duplicates"], [])

    def test_csv_import_merges_within_30m_and_reports_errors(self):
        s = self.svc
        csv = ("site,description,lat,lon,marker_id\n"
               "Ward 5 wall,leak crack,19.0000,72.0000,\n"
               "Ward 5 wall again,same crack,19.0001,72.0001,\n"
               "Ward 9,far away,19.5,72.5,\n"
               "Bad,row,notanumber,72.5,\n")
        out = s.import_csv(ENG, csv)
        self.assertEqual(out["created"], 2)
        self.assertEqual(out["merged_duplicates"], 1)
        self.assertEqual(len(out["errors"]), 1)
        with self.assertRaises(Denied):
            s.import_csv(RES, csv)

    def test_reshoot_streak_escalates_after_max_attempts(self):
        s = self.svc
        cid = s.create_case(RES, "Hard wall", marker_id=14)["id"]
        bad = shot(54, [0.6], 14, blur=4.5)
        statuses = [s.add_visit(RES, cid, bad, "baseline")["visit"]["status"] for _ in range(self.cfg.max_reshoots)]
        self.assertEqual(statuses[:-1], ["NEEDS_RESHOOT"] * (self.cfg.max_reshoots - 1))
        self.assertEqual(statuses[-1], "REVIEW_REQUESTED")

    def test_wrong_marker_is_rejected_by_gate(self):
        s = self.svc
        cid = s.create_case(RES, "Wrong", marker_id=15)["id"]
        r = s.add_visit(RES, cid, shot(55, [0.6], 20), "baseline")
        self.assertEqual(r["visit"]["status"], "NEEDS_RESHOOT")

    def test_bad_upload_rejected(self):
        s = self.svc
        cid = s.create_case(RES, "Up", marker_id=16)["id"]
        with self.assertRaises(Invalid):
            s.add_visit(RES, cid, b"not an image", "baseline")

    def test_ranking_puts_urgent_first_and_closed_last(self):
        s = self.svc
        a = s.create_case(RES, "thin", marker_id=17)["id"]
        b = s.create_case(RES, "wide", marker_id=18)["id"]
        s.add_visit(RES, a, shot(56, [0.4], 17), "baseline")
        s.add_visit(RES, b, shot(57, [3.5], 18), "baseline")
        order = [c["id"] for c in s.list_cases()]
        self.assertEqual(order[0], b)


if __name__ == "__main__":
    unittest.main()
