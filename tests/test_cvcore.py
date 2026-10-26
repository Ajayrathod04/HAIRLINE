import unittest
from tests.helpers import render
from hairline import cvcore
from hairline.config import Config


def measure(**kw):
    cfg = Config()
    img, truth = render(**kw)
    a = cvcore.analyse_image(img, cfg, cfg.marker_id)
    q = a["quality"]
    m = None
    if not q["blocked"]:
        m = cvcore.segment_and_measure(a["rect"], cfg, uncertainty_mm=q["metrics"]["uncertainty_mm"])
    return a, q, m


class CvCore(unittest.TestCase):
    def test_marker_detected_and_scale(self):
        a, q, _ = measure(seed=1, widths_mm=[0.5])
        self.assertIsNotNone(a["marker"])
        self.assertAlmostEqual(q["metrics"]["src_ppm"], 6.0, delta=0.15)

    def test_width_accuracy_on_synthetic_truth(self):
        for w in (0.5, 1.0, 2.0):
            _, q, m = measure(seed=3, widths_mm=[w])
            self.assertFalse(q["blocked"])
            self.assertTrue(m["found"], w)
            self.assertAlmostEqual(m["width_med_mm"], w, delta=0.25, msg=f"truth {w}")

    def test_accuracy_survives_tilt_and_roll(self):
        _, q, m = measure(seed=4, widths_mm=[1.0], tilt_deg=(15, 10), roll_deg=20)
        self.assertFalse(q["blocked"])
        self.assertAlmostEqual(m["width_med_mm"], 1.0, delta=0.3)

    def test_tilt_estimate(self):
        _, q, _ = measure(seed=5, widths_mm=[0.6], tilt_deg=(20, 0))
        self.assertAlmostEqual(q["metrics"]["tilt_deg"], 20.0, delta=3.0)

    def test_pits_and_texture_are_not_cracks(self):
        _, q, m = measure(seed=6, widths_mm=[])
        self.assertFalse(q["blocked"])
        self.assertFalse(m["found"])

    def test_gates_block_bad_photos(self):
        cases = {"tilt": dict(tilt_deg=(45, 0)), "blur": dict(blur=4.5), "dark": dict(gain=0.25), "far": dict(ppm=3.0)}
        for name, kw in cases.items():
            _, q, _ = measure(seed=7, widths_mm=[0.6], **kw)
            self.assertTrue(q["blocked"], name)
        _, q, _ = measure(seed=7, widths_mm=[0.6], marker=False)
        self.assertTrue(q["blocked"])
        self.assertEqual(q["gates"][0]["name"], "marker")

    def test_glare_blocks(self):
        _, q, _ = measure(seed=8, widths_mm=[0.6], glare=0.9)
        self.assertTrue(q["blocked"])
        self.assertIn("glare_fraction", [g["name"] for g in q["gates"] if not g["pass"]])

    def test_severity_bands(self):
        cfg = Config()
        mk = lambda w: {"found": True, "width_p90_mm": w}
        self.assertEqual(cvcore.severity(mk(0.1), cfg), "low")
        self.assertEqual(cvcore.severity(mk(0.5), cfg), "watch")
        self.assertEqual(cvcore.severity(mk(1.5), cfg), "priority")
        self.assertEqual(cvcore.severity(mk(4.0), cfg), "urgent")
        self.assertEqual(cvcore.severity({"found": False}, cfg), "none")

    def test_growth_detected_across_different_camera_poses(self):
        cfg = Config()
        _, q1, m1 = measure(seed=11, widths_mm=[0.5], tilt_deg=(8, 0))
        _, q2, m2 = measure(seed=11, widths_mm=[1.2], tilt_deg=(0, 12), ppm=6.5)
        cmp_ = cvcore.compare_visits(m1["mask"], m1, m2["mask"], m2, cfg)
        self.assertGreater(cmp_["delta_width_mm"], 0.4)
        self.assertTrue(cmp_["significant"])

    def test_no_growth_when_unchanged(self):
        cfg = Config()
        _, _, m1 = measure(seed=12, widths_mm=[0.8], tilt_deg=(5, 0))
        _, _, m2 = measure(seed=12, widths_mm=[0.8], tilt_deg=(0, 9))
        cmp_ = cvcore.compare_visits(m1["mask"], m1, m2["mask"], m2, cfg)
        self.assertLess(abs(cmp_["delta_width_mm"]), 0.25)
        self.assertLess(cmp_["new_crack_length_mm"], 15.0)


if __name__ == "__main__":
    unittest.main()
