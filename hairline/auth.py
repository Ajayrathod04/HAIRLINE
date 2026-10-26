"""Authentication.
demo    : role picker that issues an HMAC-signed cookie. Clearly labelled DEMO in the UI. Not for production.
cognito : verifies an Amazon Cognito JWT (groups -> role). UNVERIFIED against a live user pool in this build.
"""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import time

ROLES = ("resident", "engineer")
ANON = {"id": "anonymous", "name": "Visitor", "role": "anonymous"}


def sign(cfg, principal: dict, ttl: int = 12 * 3600) -> str:
    body = base64.urlsafe_b64encode(json.dumps({**principal, "exp": int(time.time()) + ttl}).encode()).decode()
    mac = hmac.new(cfg.secret_key.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{mac}"


def verify(cfg, token: str):
    try:
        body, mac = token.rsplit(".", 1)
        want = hmac.new(cfg.secret_key.encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(mac, want):
            return None
        d = json.loads(base64.urlsafe_b64decode(body.encode()))
        if d.get("exp", 0) < time.time() or d.get("role") not in ROLES:
            return None
        return {"id": d["id"], "name": d["name"], "role": d["role"]}
    except Exception:
        return None


def demo_principal(role: str, name: str) -> dict:
    name = (name or "").strip()[:40] or role.title()
    pid = f"{role}:" + hashlib.sha256(name.lower().encode()).hexdigest()[:10]
    return {"id": pid, "name": name, "role": role}


class CognitoVerifier:
    def __init__(self, cfg):
        import jwt  # PyJWT[crypto]
        self.jwt = jwt
        self.cfg = cfg
        self.issuer = f"https://cognito-idp.{cfg.cognito_region}.amazonaws.com/{cfg.cognito_pool_id}"
        self.jwks = jwt.PyJWKClient(self.issuer + "/.well-known/jwks.json")

    def principal(self, token: str):
        try:
            key = self.jwks.get_signing_key_from_jwt(token).key
            c = self.jwt.decode(token, key, algorithms=["RS256"], issuer=self.issuer, options={"verify_aud": False})
            if c.get("token_use") == "access" and c.get("client_id") != self.cfg.cognito_client_id:
                return None
            groups = c.get("cognito:groups", [])
            role = "engineer" if "engineer" in groups else "resident" if "resident" in groups else None
            if not role:
                return None
            return {"id": c["sub"], "name": c.get("username", c["sub"])[:40], "role": role}
        except Exception:
            return None
