#!/usr/bin/env python3
"""Create a local named tunnel; save credentials outside the checkout (never print secrets)."""
import argparse, base64, json, os, re, secrets, sys, urllib.error, urllib.request
from pathlib import Path

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--name", required=True)
    p.add_argument("--hostname", required=True)
    p.add_argument("--credential-dir", type=Path, required=True)
    p.add_argument("--create", action="store_true", help="Explicitly permit one API create operation")
    a = p.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9-]{0,62}", a.name):
        p.error("name must be a DNS-style label")
    if not re.fullmatch(r"[a-zA-Z0-9.-]+", a.hostname) or "." not in a.hostname:
        p.error("hostname must be a fully-qualified DNS name")
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    if not re.fullmatch(r"[a-fA-F0-9]{32}", account):
        p.error("set CLOUDFLARE_ACCOUNT_ID to your account identifier")
    if not a.create:
        p.error("--create required; read README and check existing named tunnels first")
    token = os.environ.get("CLOUDFLARE_TUNNEL_API_TOKEN")
    if not token:
        p.error("set CLOUDFLARE_TUNNEL_API_TOKEN; do not pass tokens as arguments")
    directory = a.credential_dir.expanduser().resolve()
    repo = Path(__file__).resolve().parent.parent
    if directory == repo or repo in directory.parents:
        p.error("credential directory must be outside this checkout")
    os.umask(0o077)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if directory.is_symlink() or directory.stat().st_mode & 0o077:
        p.error("credential directory must have mode700 and not be a symlink")
    config = directory / "config.yml"
    if config.exists():
        p.error("config already exists: preserve it; this helper will not replace a tunnel")
    secret = base64.b64encode(secrets.token_bytes(32)).decode()
    payload = json.dumps({"name": a.name, "config_src": "local", "tunnel_secret": secret}).encode()
    req = urllib.request.Request(f"https://api.cloudflare.com/client/v4/accounts/{account}/cfd_tunnel", data=payload, headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.load(response)
    except (urllib.error.URLError, TimeoutError):
        sys.exit("Tunnel creation failed or is uncertain. Check account inventory before retrying; no response body logged.")
    if not result.get("success"):
        sys.exit("Cloudflare rejected creation; check token scope/account without logging response secrets.")
    tunnel_id = result["result"]["id"]
    if not re.fullmatch(r"[a-fA-F0-9-]{36}", tunnel_id):
        sys.exit("Unexpected tunnel UUID; inspect account inventory before retrying.")
    credential = directory / (tunnel_id + ".json")
    with credential.open("x") as stream:
        json.dump({"AccountTag": account, "TunnelSecret": secret, "TunnelID": tunnel_id}, stream)
    with config.open("x") as stream:
        stream.write(f"tunnel: {tunnel_id}\ncredentials-file: {json.dumps(str(credential))}\ningress:\n  - hostname: {a.hostname}\n    service: http://127.0.0.1:8080\n  - service: http_status:404\n")
    print("Created tunnel UUID:", tunnel_id)
    print("Protected credential/config directory:", directory)
    print("If saving fails after creation, do not blindly rerun: reconcile the remote named tunnel first.")

if __name__ == "__main__":
    main()
