"""Write RELEASE.json: SHA-256 of every shipped file plus a manifest hash. Run right before tagging/zipping.
Judges can recompute it to confirm nothing changed after the deadline (a late commit cost another entry points)."""
import hashlib
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", "__pycache__", "data", ".venv", "node_modules", ".ui_fixtures"}
files = {}
for d, dirs, names in os.walk(ROOT):
    dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS)
    for n in sorted(names):
        if n in ("RELEASE.json",) or n.endswith(".pyc"):
            continue
        p = os.path.join(d, n)
        files[os.path.relpath(p, ROOT).replace(os.sep, "/")] = hashlib.sha256(open(p, "rb").read()).hexdigest()
manifest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
git = None
try:
    git = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, stderr=subprocess.DEVNULL).decode().strip()
except Exception:
    pass
out = {"built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "git_commit": git, "manifest_sha256": manifest, "file_count": len(files), "files": files}
json.dump(out, open(os.path.join(ROOT, "RELEASE.json"), "w"), indent=1)
print("RELEASE.json written:", manifest, len(files), "files")
