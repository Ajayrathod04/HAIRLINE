"""Record real API responses (seeded demo data) so tests/ui_smoke.js can render every page offline.
Usage: python tests/record_ui_fixtures.py DIR"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hairline.config import Config
from hairline.server import create_app

out = sys.argv[1] if len(sys.argv) > 1 else ".ui_fixtures"
os.makedirs(out, exist_ok=True)
d = tempfile.mkdtemp(prefix="hl_ui_")
cfg = Config()
cfg.sqlite_path, cfg.blob_dir, cfg.seed_demo = os.path.join(d, "db"), os.path.join(d, "b"), True
app = create_app(cfg)
H = {"X-HL": "1"}
dump = lambda name, c, path: json.dump(c.get(path).get_json(), open(os.path.join(out, name + ".json"), "w"))
anon = app.test_client()
for n, p in [("health", "/api/health"), ("samples", "/api/samples"), ("transparency", "/api/transparency"), ("policy", "/api/policy"), ("stats", "/api/stats")]:
    dump(n, anon, p)
eng, res = app.test_client(), app.test_client()
eng.post("/api/login", json={"role": "engineer", "name": "Rao"}, headers=H)
res.post("/api/login", json={"role": "resident", "name": "Asha"}, headers=H)
who = {"anon": anon, "eng": eng, "res": res}
for k, c in who.items():
    dump("me_" + k, c, "/api/me")
    dump("cases_" + k, c, "/api/cases")
for x in eng.get("/api/cases").get_json():
    for k, c in who.items():
        dump(f"case_{x['status']}_{k}", c, f"/api/cases/{x['id']}")
    json.dump(x["id"], open(os.path.join(out, f"id_{x['status']}.json"), "w"))
print("fixtures written to", out)
