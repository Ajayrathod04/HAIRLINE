import io
import os
import unittest
from tests.helpers import render, jpg
from hairline.config import Config
from hairline.server import create_app
import tempfile

HDR = {"X-HL": "1"}


class Api(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = tempfile.mkdtemp(prefix="hl_api_")
        cfg = Config()
        cfg.sqlite_path, cfg.blob_dir = os.path.join(d, "a.db"), os.path.join(d, "b")
        cls.app = create_app(cfg)

    def setUp(self):
        self.c = self.app.test_client()

    def login(self, role, name):
        r = self.c.post("/api/login", json={"role": role, "name": name}, headers=HDR)
        self.assertEqual(r.status_code, 200)

    def test_health_reports_opencv(self):
        j = self.c.get("/api/health").get_json()
        self.assertEqual(j["status"], "ok")
        self.assertIn("opencv", j)
        self.assertEqual(j["opencv_major"], 5)

    def test_security_headers(self):
        r = self.c.get("/")
        self.assertIn("default-src 'self'", r.headers["Content-Security-Policy"])
        self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(r.status_code, 200)

    def test_csrf_header_required(self):
        self.assertEqual(self.c.post("/api/login", json={"role": "resident", "name": "x"}).status_code, 400)

    def test_visitor_counter_counts_unique_once_per_cookie(self):
        a = self.c.post("/api/visit", headers={**HDR, "User-Agent": "Mozilla/5.0"}).get_json()
        b = self.c.post("/api/visit", headers={**HDR, "User-Agent": "Mozilla/5.0"}).get_json()  # same cookie jar
        self.assertEqual(b["unique_visitors"], a["unique_visitors"])
        self.assertEqual(b["page_views"], a["page_views"] + 1)
        other = self.app.test_client()
        c = other.post("/api/visit", headers={**HDR, "User-Agent": "Mozilla/5.0"}).get_json()
        self.assertEqual(c["unique_visitors"], a["unique_visitors"] + 1)

    def test_bots_are_not_counted(self):
        before = self.c.get("/api/stats").get_json()
        self.app.test_client().post("/api/visit", headers={**HDR, "User-Agent": "Googlebot/2.1"})
        self.assertEqual(self.c.get("/api/stats").get_json()["unique_visitors"], before["unique_visitors"])

    def test_anonymous_cannot_write(self):
        r = self.c.post("/api/cases", json={"site": "x"}, headers=HDR)
        self.assertEqual(r.status_code, 403)
        self.assertFalse(r.get_json()["decision"]["allow"])

    def test_assess_sample_and_upload(self):
        r = self.c.post("/api/assess", data={"sample": "sample_good_0p6mm.jpg"}, headers=HDR)
        j = r.get_json()
        self.assertEqual(j["status"], "MEASURED")
        self.assertTrue(j["overlay"].startswith("data:image/jpeg;base64,"))
        r = self.c.post("/api/assess", data={"sample": "../../etc/passwd"}, headers=HDR)
        self.assertEqual(r.status_code, 400)
        img, _ = render(seed=7, widths_mm=[0.6], tilt_deg=(45, 0))
        r = self.c.post("/api/assess", data={"image": (io.BytesIO(jpg(img)), "p.jpg")}, headers=HDR, content_type="multipart/form-data")
        self.assertEqual(r.get_json()["status"], "NEEDS_RESHOOT")
        r = self.c.post("/api/assess", data={"image": (io.BytesIO(b"junk"), "p.jpg")}, headers=HDR, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 400)

    def test_end_to_end_case_over_http_and_blob_privacy(self):
        self.login("resident", "Asha")
        cid = self.c.post("/api/cases", json={"site": "HTTP wall", "marker_id": 30}, headers=HDR).get_json()["id"]
        img, _ = render(seed=61, widths_mm=[1.5], marker_id=30)
        r = self.c.post(f"/api/cases/{cid}/visits", data={"image": (io.BytesIO(jpg(img)), "p.jpg"), "kind": "baseline"},
                        headers=HDR, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 201)
        v = r.get_json()["visit"]
        self.assertEqual(v["status"], "REVIEW_REQUESTED")
        self.assertEqual(self.c.get("/api/blob/" + v["overlay_key"]).status_code, 200)
        anon = self.app.test_client()
        self.assertEqual(anon.get("/api/blob/" + v["overlay_key"]).status_code, 403)  # real (non-simulated) case photos need sign-in
        self.assertEqual(anon.get("/api/blob/../../etc/passwd").status_code, 404)
        self.login("engineer", "Rao")
        self.assertEqual(self.c.post(f"/api/cases/{cid}/close", json={}, headers=HDR).status_code, 403)
        self.assertEqual(self.c.post(f"/api/cases/{cid}/authorise", json={"note": "ok"}, headers=HDR).status_code, 200)

    def test_marker_download(self):
        r = self.c.get("/api/marker.png?id=7")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.mimetype, "image/png")
        self.assertEqual(self.c.get("/api/marker.png?id=99").status_code, 400)

    def test_static_assets_served(self):
        for p in ("/static/app.js", "/static/app.css", "/static/favicon.svg"):
            self.assertEqual(self.c.get(p).status_code, 200, p)
        self.assertEqual(self.c.get("/static/../server.py").status_code, 404)


if __name__ == "__main__":
    unittest.main()
