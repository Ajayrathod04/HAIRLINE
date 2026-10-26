"""Flask API + static UI. One process serves both so the whole product is a single deployable unit."""
from __future__ import annotations
import base64
import glob
import json
import logging
import os
import re
import secrets
import sys
import time
from collections import defaultdict, deque

import cv2
from flask import Flask, Response, g, jsonify, make_response, request, send_from_directory

from . import __version__, auth
from . import policy as policy_mod
from .blobs import make_blobs
from .config import Config
from .service import Denied, Invalid, NotFound, Service
from .store import make_store

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
SAMPLES = os.path.join(ROOT, "samples")
BOT = re.compile(r"bot|crawl|spider|curl|wget|python-requests|monitor|uptime|headless", re.I)
log = logging.getLogger("hairline")


def create_app(cfg: Config | None = None, store=None, blobs=None) -> Flask:
    cfg = cfg or Config.from_env()
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")
    store = store or make_store(cfg)
    blobs = blobs or make_blobs(cfg)
    svc = Service(cfg, store, blobs)
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = (cfg.max_upload_mb + 1) * 1024 * 1024
    app.config["JSON_SORT_KEYS"] = False
    app.extensions["hairline"] = svc
    cognito = None
    if cfg.auth_mode == "cognito":
        cognito = auth.CognitoVerifier(cfg)
    hits = defaultdict(deque)

    release = {}
    rp = os.path.join(ROOT, "RELEASE.json")
    if os.path.isfile(rp):
        with open(rp, encoding="utf-8") as f:
            release = json.load(f)

    # ---------------------------------------------------------------- plumbing
    def principal():
        if cognito:
            h = request.headers.get("Authorization", "")
            if h.startswith("Bearer "):
                p = cognito.principal(h[7:])
                if p:
                    return p
            return auth.ANON
        tok = request.cookies.get("hl_token")
        return (auth.verify(cfg, tok) if tok else None) or auth.ANON

    def rate_limit(key: str, limit: int, per: int = 60):
        now = time.time()
        q = hits[(key, request.remote_addr)]
        while q and q[0] < now - per:
            q.popleft()
        if len(q) >= limit:
            raise Invalid("rate limit exceeded; try again in a minute")
        q.append(now)

    @app.before_request
    def _pre():
        g.t0 = time.time()
        g.p = principal()
        if request.method in ("POST", "PUT", "DELETE") and request.path.startswith("/api/") and request.headers.get("X-HL") != "1":
            return jsonify(error="missing X-HL header (CSRF guard)"), 400

    @app.after_request
    def _post(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Permissions-Policy"] = "camera=(self), geolocation=(self), microphone=()"
        resp.headers["Content-Security-Policy"] = ("default-src 'self'; img-src 'self' data: blob:; "
                                                   "style-src 'self' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; "
                                                   "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        if request.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
            log.info(json.dumps({"ts": int(time.time()), "m": request.method, "p": request.path, "s": resp.status_code,
                                 "ms": int((time.time() - g.t0) * 1000), "role": g.p["role"]}))
        return resp

    @app.errorhandler(Denied)
    def _denied(e):
        return jsonify(error="forbidden", decision=e.decision.as_dict()), 403

    @app.errorhandler(NotFound)
    def _nf(e):
        return jsonify(error="not found"), 404

    @app.errorhandler(Invalid)
    def _inv(e):
        return jsonify(error=str(e)), 400

    @app.errorhandler(413)
    def _big(e):
        return jsonify(error=f"upload larger than {cfg.max_upload_mb} MB"), 413

    def view_case(case: dict) -> dict:
        p = g.p
        out = {k: v for k, v in case.items()}
        out["allowed"] = svc.allowed_actions(p, case)
        if p["role"] == "anonymous" and not case.get("simulated"):
            out["reported_name"] = "resident"
            out["audit"] = []
        return out

    def check(action, case=None):
        d = policy_mod.evaluate(svc.policy, g.p, action, case)
        if not d.allow:
            raise Denied(d)

    # ---------------------------------------------------------------- static
    @app.get("/")
    def index():
        return send_from_directory(STATIC, "index.html")

    @app.get("/static/<path:name>")
    def static_files(name):
        resp = send_from_directory(STATIC, name)
        resp.headers["Cache-Control"] = "public, max-age=300"
        return resp

    @app.get("/samples/<path:name>")
    def sample_file(name):
        return send_from_directory(SAMPLES, name)

    @app.get("/api/marker.png")
    def marker_png():
        from .cvcore import make_marker_image
        mid = int(request.args.get("id", cfg.marker_id))
        if not 0 <= mid < 50:
            raise Invalid("marker id must be 0-49")
        ok, buf = cv2.imencode(".png", make_marker_image(cfg, mid))
        return Response(buf.tobytes(), mimetype="image/png",
                        headers={"Content-Disposition": f"inline; filename=hairline_marker_{mid}_{int(cfg.marker_mm)}mm.png"})

    # ---------------------------------------------------------------- meta
    @app.get("/api/health")
    def health():
        return jsonify(status="ok", version=__version__, opencv=cv2.__version__, opencv_major=int(cv2.__version__.split(".")[0]),
                       auth_mode=cfg.auth_mode, store=store.name, blobs=blobs.name, planner=svc.planner.name,
                       release=release.get("manifest_sha256"), built_at=release.get("built_at"))

    @app.post("/api/visit")
    def visit():
        vid = request.cookies.get("hl_vid") or secrets.token_hex(8)
        stats = svc.track_visitor(vid, bool(BOT.search(request.headers.get("User-Agent", ""))))
        resp = make_response(jsonify(stats))
        resp.set_cookie("hl_vid", vid, max_age=365 * 86400, httponly=True, samesite="Lax", secure=request.is_secure)
        return resp

    @app.get("/api/stats")
    def stats():
        return jsonify(svc.stats())

    @app.get("/api/policy")
    def get_policy():
        return jsonify(svc.policy)

    @app.get("/api/transparency")
    def transparency():
        return jsonify({
            "simulated": ["All demo cases, their photos and their histories are synthetic renders with known crack widths.",
                          "Demo accounts (resident / engineer) are a role picker, not real identity."],
            "estimated": ["Widths are measured from photos with a printed marker; uncertainty is shown with every number.",
                          "Severity bands and the priority score are configurable triage heuristics, not engineering standards.",
                          "Repair evidence is visual only; an engineer must authorise closure."],
            "not_done": ["No pilot with a real ward office or society has been run yet (see docs/PILOT_PLAN.md).",
                         "Accuracy on real walls is measured only by the printed-card protocol in docs/EVALUATION.md."]})

    @app.get("/api/samples")
    def samples():
        out = []
        for p in sorted(glob.glob(os.path.join(SAMPLES, "sample_*.jpg"))):
            n = os.path.basename(p)
            out.append({"file": n, "label": n[7:-4].replace("_", " "), "url": "/samples/" + n})
        return jsonify(out)

    # ---------------------------------------------------------------- auth (demo)
    @app.post("/api/login")
    def login():
        if cfg.auth_mode != "demo":
            raise Invalid("demo login disabled; sign in with Cognito")
        d = request.get_json(silent=True) or {}
        if d.get("role") not in auth.ROLES:
            raise Invalid("role must be resident or engineer")
        p = auth.demo_principal(d["role"], d.get("name", ""))
        resp = make_response(jsonify(p))
        resp.set_cookie("hl_token", auth.sign(cfg, p), max_age=12 * 3600, httponly=True, samesite="Lax", secure=request.is_secure)
        return resp

    @app.post("/api/logout")
    def logout():
        resp = make_response(jsonify(ok=True))
        resp.delete_cookie("hl_token")
        return resp

    @app.get("/api/me")
    def me():
        return jsonify(**g.p, auth_mode=cfg.auth_mode)

    # ---------------------------------------------------------------- stateless try-it
    @app.post("/api/assess")
    def assess():
        rate_limit("assess", 30)
        data = None
        name = request.form.get("sample")
        if name:
            if not re.fullmatch(r"sample_[a-z0-9_]+\.jpg", name):
                raise Invalid("bad sample name")
            path = os.path.join(SAMPLES, name)
            if not os.path.isfile(path):
                raise NotFound(name)
            with open(path, "rb") as f:
                data = f.read()
        elif "image" in request.files:
            data = request.files["image"].read()
        out = svc.quick_assess(data)
        jpg = out.pop("overlay_jpeg")
        out["overlay"] = ("data:image/jpeg;base64," + base64.b64encode(jpg).decode()) if jpg else None
        return jsonify(out)

    # ---------------------------------------------------------------- cases
    @app.get("/api/cases")
    def cases():
        return jsonify([view_case(c) for c in svc.list_cases()])

    @app.post("/api/cases")
    def create_case():
        d = request.get_json(silent=True) or {}
        def num(k):
            v = d.get(k)
            return None if v in (None, "") else float(v)
        mid = d.get("marker_id")
        c = svc.create_case(g.p, d.get("site", ""), d.get("description", ""), None if mid in (None, "") else int(mid), num("lat"), num("lon"))
        return jsonify(view_case(c)), 201

    @app.get("/api/cases/<cid>")
    def case(cid):
        return jsonify(view_case(svc.get_case(cid)))

    @app.post("/api/cases/<cid>/visits")
    def add_visit(cid):
        rate_limit("visit", 20)
        f = request.files.get("image")
        if f is None:
            raise Invalid("image file required")
        r = svc.add_visit(g.p, cid, f.read(), request.form.get("kind", "followup"), request.form.get("note", ""))
        return jsonify({"case": view_case(r["case"]), "visit": r["visit"]}), 201

    def _json():
        return request.get_json(silent=True) or {}

    @app.post("/api/cases/<cid>/review")
    def review(cid):
        return jsonify(view_case(svc.request_review(g.p, cid, _json().get("reason", ""))))

    @app.post("/api/cases/<cid>/authorise")
    def authorise(cid):
        return jsonify(view_case(svc.authorise(g.p, cid, _json().get("note", ""))))

    @app.post("/api/cases/<cid>/close")
    def close(cid):
        return jsonify(view_case(svc.close(g.p, cid, _json().get("note", ""))))

    @app.post("/api/cases/<cid>/dispute")
    def dispute(cid):
        return jsonify(view_case(svc.open_dispute(g.p, cid, _json().get("reason", ""))))

    @app.post("/api/cases/<cid>/dispute/resolve")
    def dispute_resolve(cid):
        d = _json()
        return jsonify(view_case(svc.resolve_dispute(g.p, cid, d.get("decision", ""), d.get("note", ""))))

    @app.post("/api/import")
    def import_csv():
        text = request.get_data(as_text=True)
        return jsonify(svc.import_csv(g.p, text))

    @app.get("/api/blob/<path:key>")
    def blob(key):
        m = re.fullmatch(r"cases/([a-f0-9]+)/[A-Za-z0-9_.]+", key)
        if not m:
            raise NotFound(key)
        c = svc.get_case(m.group(1))
        if g.p["role"] == "anonymous" and not c.get("simulated"):
            raise Denied(policy_mod.Decision(False, [], "photos of real cases require sign-in"))
        data = blobs.get(key)
        if data is None:
            raise NotFound(key)
        ctype = "image/png" if key.endswith(".png") else "image/jpeg"
        return Response(data, mimetype=ctype, headers={"Cache-Control": "private, max-age=300"})

    if cfg.seed_demo and not store.list("case"):
        from .seed import seed_demo
        seed_demo(svc)
    return app


def main():
    app = create_app()
    app.run(host=os.environ.get("HOST", "0.0.0.0"), port=int(os.environ.get("PORT", "8080")))


if __name__ == "__main__":
    main()
