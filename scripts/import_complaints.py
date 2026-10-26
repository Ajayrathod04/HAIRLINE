"""Push a complaint register (CSV) into a running HAIRLINE as an engineer.
CSV columns: site,description,lat,lon,marker_id  (lat/lon/marker_id optional)
Usage: python scripts/import_complaints.py complaints.csv --url https://your-host --name "Eng. Rao"
Needs HL_AUTH_MODE=demo on the server, or pass --token with a Cognito access token."""
import argparse
import json
import sys
import urllib.request
import http.cookiejar

ap = argparse.ArgumentParser()
ap.add_argument("csv")
ap.add_argument("--url", default="http://localhost:8080")
ap.add_argument("--name", default="Import engineer")
ap.add_argument("--token")
a = ap.parse_args()
jar = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def call(path, data, ctype):
    h = {"X-HL": "1", "Content-Type": ctype}
    if a.token:
        h["Authorization"] = "Bearer " + a.token
    r = op.open(urllib.request.Request(a.url + path, data=data, headers=h, method="POST"))
    return json.loads(r.read())


if not a.token:
    call("/api/login", json.dumps({"role": "engineer", "name": a.name}).encode(), "application/json")
print(json.dumps(call("/api/import", open(a.csv, "rb").read(), "text/csv"), indent=1))
