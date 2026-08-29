"""Start cloudflared tunnel briefly and exercise local webhook ingress."""

from __future__ import annotations

import hashlib
import hmac
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portable_core" / "src"))
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from aip.config import settings
from apps.api.main import app


def main() -> int:
    client = TestClient(app)
    before = client.get("/api/tunnel").json()
    print("before:", {k: before.get(k) for k in ("status", "binary", "public_base")})
    started = client.post("/api/tunnel/start").json()
    print(
        "start:",
        {
            k: started.get(k)
            for k in ("status", "running", "binary", "public_base", "error", "install_hint")
        },
    )
    public = ""
    for _ in range(20):
        time.sleep(1)
        st = client.get("/api/tunnel").json()
        public = st.get("public_base") or ""
        if public:
            print("ready:", st.get("status"), public, st.get("urls"))
            break
    else:
        print("wait_timeout:", client.get("/api/tunnel").json())
        client.post("/api/tunnel/stop")
        return 1

    payload = b'{"action":"opened","repository":{"full_name":"n1shanthb/analytics-resume"}}'
    headers = {"X-GitHub-Event": "issues", "Content-Type": "application/json"}
    secret = (settings.github_webhook_secret or "").strip()
    if secret:
        digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        headers["X-Hub-Signature-256"] = f"sha256={digest}"
    resp = client.post("/api/webhooks/github", content=payload, headers=headers)
    body = resp.json()
    print("webhook:", resp.status_code, body.get("ok"), body.get("delivery", {}).get("webhook_id"))
    deliveries = client.get("/api/webhooks/deliveries").json().get("deliveries") or []
    print("deliveries:", deliveries[:1])
    stop = client.post("/api/tunnel/stop").json()
    print("stop:", stop.get("status"))
    ok = bool(public) and resp.status_code == 200 and body.get("ok")
    print("OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
