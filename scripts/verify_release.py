"""Recompute file hashes and compare with RELEASE.json. Exit 1 if anything changed since the release was cut.
Judges (and you, right before submitting) can run this to confirm no late edits."""
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP = {".git", "__pycache__", "data", ".venv", "node_modules", ".ui_fixtures"}
rel = json.load(open(os.path.join(ROOT, "RELEASE.json")))
now = {}
for d, dirs, names in os.walk(ROOT):
    dirs[:] = sorted(x for x in dirs if x not in SKIP)
    for n in sorted(names):
        if n == "RELEASE.json" or n.endswith(".pyc"):
            continue
        p = os.path.join(d, n)
        now[os.path.relpath(p, ROOT).replace(os.sep, "/")] = hashlib.sha256(open(p, "rb").read()).hexdigest()
manifest = hashlib.sha256(json.dumps(now, sort_keys=True).encode()).hexdigest()
changed = sorted(k for k in set(now) | set(rel["files"]) if now.get(k) != rel["files"].get(k))
if manifest == rel["manifest_sha256"]:
    print("RELEASE OK:", manifest, f"({len(now)} files, built {rel['built_at']})")
    sys.exit(0)
print("RELEASE MISMATCH. Changed/added/removed files:", *changed, sep="\n  ")
sys.exit(1)
