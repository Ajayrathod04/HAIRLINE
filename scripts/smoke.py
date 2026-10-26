"""Post-deploy smoke test: python scripts/smoke.py https://your-host"""
import json
import sys
import urllib.request

base = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080").rstrip("/")


def get(p):
    return json.loads(urllib.request.urlopen(base + p, timeout=20).read())


h = get("/api/health")
print("health:", h)
assert h["status"] == "ok"
assert h["opencv_major"] == 5, "OpenCV 5 is required by the competition (found %s)" % h["opencv"]
print("stats:", get("/api/stats"))
print("cases:", len(get("/api/cases")))
print("SMOKE OK")
