# Security notes (threat model summary)
* **AuthN/AuthZ:** production uses Cognito groups (`resident`, `engineer`) verified as JWTs by the API; demo mode is a labelled role picker with HMAC-signed, HttpOnly, SameSite=Lax cookies (12 h) and must not be used in production. Every action passes `policy.evaluate` (default deny, forbid beats permit); denials are audited.
* **CSRF:** all state-changing API calls require the custom header `X-HL: 1` (not sendable cross-site without CORS approval) plus SameSite cookies.
* **Uploads:** size cap, decode check, dimension cap, re-encode (EXIF dropped), blob keys validated against a strict pattern, no path traversal (tested).
* **Browser:** CSP (`default-src 'self'`, scripts and styles from self; Google Fonts only for CSS/font files), `X-Frame-Options: DENY`, `nosniff`, no referrer, permissions policy; no inline script or style; all user text is HTML-escaped in the UI.
* **Secrets:** `HL_SECRET_KEY` required to be changed (CloudFormation parameter is `NoEcho`); never committed.
* **Infra:** private S3 with SSE, versioning, TLS-only policy; DynamoDB PITR+SSE; IMDSv2 required; no SSH (SSM Session Manager); security group limited to CloudFront's prefix list when supplied; least-privilege instance role.
* **Rate limiting** is in-process (per IP, per worker): fine for a single instance, replace with WAF rate rules at scale.
* **Not done:** third-party penetration test, WAF, automated dependency scanning in CI, malware scanning of uploads (images are decoded and re-encoded, never executed).
