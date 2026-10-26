import unittest
from tests.helpers import render
from hairline import agent
from hairline.config import Config

cfg = Config()


class Stub:
    def __init__(self, action=None, boom=False):
        self.name, self.action, self.boom = "stub", action, boom

    def next(self, state, allowed):
        if self.boom:
            raise RuntimeError("llm down")
        return {"action": self.action, "reason": "stub"}


class Agent(unittest.TestCase):
    def test_bad_photo_triggers_reshoot_with_specific_advice(self):
        img, _ = render(seed=7, widths_mm=[0.6], tilt_deg=(45, 0))
        r = agent.run_agent(img, cfg, agent.Context())
        self.assertEqual(r.status, "NEEDS_RESHOOT")
        self.assertIn("tilted", r.guidance)
        self.assertEqual(r.trace[0]["action"], "reshoot")
        self.assertIsNone(r.measurement)

    def test_measurement_changes_next_action(self):
        thin, _ = render(seed=21, widths_mm=[0.4])
        wide, _ = render(seed=22, widths_mm=[2.0])
        a = agent.run_agent(thin, cfg, agent.Context())
        b = agent.run_agent(wide, cfg, agent.Context())
        self.assertEqual(a.status, "MEASURED")
        self.assertEqual(b.status, "REVIEW_REQUESTED")
        self.assertNotEqual(a.trace[-1]["action"], b.trace[-1]["action"])

    def test_growth_escalates_even_when_severity_is_low(self):
        cfg2 = Config()
        base, _ = render(seed=31, widths_mm=[0.4])
        r0 = agent.run_agent(base, cfg2, agent.Context())
        later, _ = render(seed=31, widths_mm=[0.9], tilt_deg=(0, 8))
        ctx = agent.Context(kind="followup", prev_meas={k: v for k, v in r0.measurement.items() if k not in ("mask", "skeleton")}, prev_mask=r0.mask)
        r1 = agent.run_agent(later, cfg2, ctx)
        self.assertIn("compare_prev", [t["tool"] for t in r1.trace])
        self.assertEqual(r1.status, "REVIEW_REQUESTED")
        self.assertIn("grew", r1.review_reason)

    def test_guardrail_blocks_llm_from_under_reacting(self):
        wide, _ = render(seed=22, widths_mm=[2.0])
        r = agent.run_agent(wide, cfg, agent.Context(), Stub("accept"))
        self.assertEqual(r.status, "REVIEW_REQUESTED")
        self.assertTrue(any("guardrail" in t["note"] for t in r.trace))

    def test_guardrail_blocks_illegal_action(self):
        bad, _ = render(seed=7, widths_mm=[0.6], tilt_deg=(45, 0))
        r = agent.run_agent(bad, cfg, agent.Context(), Stub("measure"))
        self.assertEqual(r.status, "NEEDS_RESHOOT")  # LLM cannot force a measurement through a blocked gate

    def test_llm_failure_falls_back_to_rules(self):
        thin, _ = render(seed=21, widths_mm=[0.4])
        r = agent.run_agent(thin, cfg, agent.Context(), Stub(boom=True))
        self.assertEqual(r.status, "MEASURED")
        self.assertTrue(any("fell back" in t["note"] for t in r.trace))

    def test_repeated_failures_escalate_to_human(self):
        bad, _ = render(seed=7, widths_mm=[0.6], blur=4.5)
        r = agent.run_agent(bad, cfg, agent.Context(failed_attempts=cfg.max_reshoots - 1))
        self.assertEqual(r.status, "REVIEW_REQUESTED")

    def test_repair_verification(self):
        before, _ = render(seed=41, widths_mm=[1.2])
        r0 = agent.run_agent(before, cfg, agent.Context())
        prev = {k: v for k, v in r0.measurement.items() if k not in ("mask", "skeleton")}
        fixed, _ = render(seed=41, widths_mm=[], tilt_deg=(0, 6))
        ok = agent.run_agent(fixed, cfg, agent.Context(kind="after_repair", prev_meas=prev, prev_mask=r0.mask))
        self.assertEqual(ok.status, "REPAIR_EVIDENCE_OK")
        still, _ = render(seed=41, widths_mm=[1.2], tilt_deg=(0, 6))
        bad = agent.run_agent(still, cfg, agent.Context(kind="after_repair", prev_meas=prev, prev_mask=r0.mask))
        self.assertEqual(bad.status, "REPAIR_NOT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
