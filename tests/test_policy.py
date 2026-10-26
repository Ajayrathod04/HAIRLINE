import unittest
from hairline import policy
from tests.helpers import RES, ENG, ENG2, ANON

P = policy.load()
OPEN = {"status": "MEASURED", "reported_by": RES["id"]}


class Policy(unittest.TestCase):
    def test_default_deny_for_unknown_action(self):
        self.assertFalse(policy.evaluate(P, ENG, "database.drop", OPEN).allow)

    def test_anonymous_read_only(self):
        self.assertTrue(policy.evaluate(P, ANON, "case.read").allow)
        self.assertFalse(policy.evaluate(P, ANON, "case.create").allow)
        self.assertFalse(policy.evaluate(P, ANON, "visit.add", OPEN).allow)

    def test_resident_cannot_authorise_or_close(self):
        self.assertFalse(policy.evaluate(P, RES, "review.authorise", OPEN).allow)
        self.assertFalse(policy.evaluate(P, RES, "case.close", OPEN).allow)

    def test_close_needs_authorisation_and_evidence(self):
        self.assertFalse(policy.evaluate(P, ENG, "case.close", OPEN).allow)
        c = {**OPEN, "authorisation": {"by": ENG["id"]}}
        d = policy.evaluate(P, ENG, "case.close", c)
        self.assertFalse(d.allow)
        self.assertEqual(d.rules, ["F-CLOSE-NEEDS-EVIDENCE"])
        c["repair_evidence_ok"] = True
        self.assertTrue(policy.evaluate(P, ENG, "case.close", c).allow)

    def test_separation_of_duties(self):
        own = {"status": "MEASURED", "reported_by": ENG["id"]}
        self.assertFalse(policy.evaluate(P, ENG, "review.authorise", own).allow)
        self.assertTrue(policy.evaluate(P, ENG2, "review.authorise", own).allow)

    def test_dispute_only_on_closed_by_resident(self):
        self.assertFalse(policy.evaluate(P, RES, "dispute.open", OPEN).allow)
        self.assertTrue(policy.evaluate(P, RES, "dispute.open", {"status": "CLOSED"}).allow)
        self.assertFalse(policy.evaluate(P, ENG, "dispute.open", {"status": "CLOSED"}).allow)

    def test_dispute_resolution_only_engineer_when_disputed(self):
        c = {"status": "DISPUTED", "reported_by": RES["id"]}
        self.assertTrue(policy.evaluate(P, ENG, "dispute.resolve", c).allow)
        self.assertFalse(policy.evaluate(P, RES, "dispute.resolve", c).allow)
        self.assertFalse(policy.evaluate(P, ENG, "dispute.resolve", OPEN).allow)

    def test_import_engineer_only(self):
        self.assertTrue(policy.evaluate(P, ENG, "import.csv").allow)
        self.assertFalse(policy.evaluate(P, RES, "import.csv").allow)


if __name__ == "__main__":
    unittest.main()
