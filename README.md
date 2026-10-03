# A public homelab website through Cloudflare Tunnel

Start with [GitOps, the bootstrap order, and why the repos are separate](docs/START-HERE.md).

Review draft: local example only. Nothing has been applied or published. This is a small learning exercise, not a production baseline or a copy of someone's private estate.

A visitor reaches Cloudflare over HTTPS. A connector inside your lab opens outbound connections to Cloudflare and proxies the request to a web container bound to `127.0.0.1:8080`. Your router needs no inbound port forward. Your origin needs no publicly reachable IP address; it does need internet connectivity. This works behind NAT/CGNAT when outbound connectivity is available. It does not require disabling IPv6: enforce the same security boundary for both address families.

```text
visitor -> Cloudflare HTTPS edge -> outbound-established tunnel
                                   cloudflared on DMZ guest
                                   -> 127.0.0.1:8080 website
DMZ guest -- firewall DENY --> private LAN / hypervisor management
```

## What is automated, and why

Terraform manages **one proxied DNS CNAME** to an existing named tunnel. The helper creates a **locally managed named tunnel through the official Cloudflare API** and writes a protected credential file and local ingress configuration outside this repository. Tunnel lifecycle is deliberately outside Terraform in this beginner version.

Managing the tunnel secret or fetching a connector token through Terraform can put that secret into Terraform state and saved plans. `sensitive = true` hides some display output; it does not encrypt state. Here, Terraform receives only the zone ID, hostname and tunnel UUID. Even this state contains operational metadata, so keep it private, backed up and access-controlled. Do not commit state, plans or secrets.

This approach keeps the important distinction visible: DNS is declarative; API-created tunnel lifecycle is a separate step with separate cleanup. The helper is not a reconciliation engine. If a request times out, inspect account inventory before retrying rather than creating duplicates.

Benefits include encrypted edge transport, no changing residential address in DNS, no router port forwarding, and a narrow origin binding. Costs and limits include dependence on Cloudflare and your uplink, service terms, application security, and no automatic redundancy from this single connector. Do not promise availability from a successful setup command.

## Prerequisites and credentials

Use a Linux lab host or Linux VM, Python3, Terraform1.6+, Docker Compose, and `cloudflared` installed from Cloudflare's official distribution. Use a domain/zone you control already active on Cloudflare. Domain registration and DNS delegation are prerequisites, not provisioned here. Follow authoritative installation and service documentation linked below; all example operations use CLI/API, with no portal walkthrough.

Bring scoped API credentials through your existing approved secret-management/bootstrap process:

- `CLOUDFLARE_TUNNEL_API_TOKEN`: account-scoped Cloudflare Tunnel write permission for creation. Do not reuse it for the long-running connector.
- `CLOUDFLARE_API_TOKEN`: DNS edit for just your intended zone, used by the Terraform provider.
- `CLOUDFLARE_ACCOUNT_ID`: account identifier; `TF_VAR_zone_id`: zone identifier. These are not passwords.

If you must mint a token programmatically, Cloudflare's official token API provides permission-group discovery and scoped token creation. That requires an existing authorized bootstrap credential; this example does not manufacture authority. Resolve the account/zone permission scopes before running, and do not place bootstrap tokens in source files. Input secret values through a protected shell environment or secret manager. Disable shell tracing, avoid terminal recording, and never paste credentials into command arguments or a public issue.

Provider version **5.26.0** was verified against the Terraform Registry API during preparation. It is pinned exactly, rather than relying on a moving `latest` version. Recheck official release notes and update intentionally later. Container tags are versioned but not immutable; for production, inspect and pin the image digest appropriate to your architecture.

## Bare metal and Proxmox placement

On bare metal, dedicate a Linux machine/NIC to your DMZ VLAN. On Proxmox, create a Linux VM whose guest NIC is attached to the DMZ VLAN through the appropriate VLAN-aware bridge. Keep the Proxmox management interface and SSH/API on a separate management network. Do not run this tutorial's Docker stack on the hypervisor itself.

Use the same guest paths in either arrangement: checkout under `/opt/homelab/cloudflare-homelab-tunnel`, protected runtime files under `/etc/cloudflared-homelab`, and container content under the checkout's `site/`. A non-root learning session can instead use an external mode700 directory under your home directory. Do not give the VM a second LAN interface that bypasses the firewall.

## The DMZ is a firewall boundary

A VLAN names a network; policy makes it an isolation boundary. Configure your router/firewall through its reviewed IaC or CLI. The exact syntax depends on the platform, so this repository supplies a policy contract rather than a misleading universal firewall script:

| Source | Destination | Policy |
|---|---|---|
| DMZ | LAN, storage, management, hypervisor networks | Deny new sessions, IPv4 and IPv6 |
| Internet | DMZ | Deny unsolicited inbound; no port forwards |
| DMZ connector | Cloudflare documented tunnel endpoints | Allow outbound TCP/UDP7844; QUIC uses UDP, HTTP/2 TCP |
| DMZ | Approved DNS resolver | Allow required TCP/UDP53, narrowly scoped |
| DMZ | Approved time service | Allow required UDP123 |
| DMZ | Approved package/registry/API endpoints | Allow required HTTPS443; provisioning/update scope separately |
| Approved management source | DMZ guest SSH | Optional narrow TCP22 administration rule |
| Any permitted established session | Return traffic | Allow stateful established/related return |

Use Cloudflare's maintained endpoint list rather than a copied stale IP allowlist. Restrict the resolver exception so it does not accidentally open the entire LAN. Check for alternate paths, IPv6 routes, permissive bridge rules and existing established sessions. Container networking is not a substitute for the router boundary. **Tunnel does not isolate your LAN**: a compromised application or connector still has the access your firewall allows.

Cloudflare Access is appropriate for private applications; a public website in this exercise is intentionally public. Do not tunnel hypervisor management, Vault, Rancher or GitLab administration to the public without a separately reviewed identity/access policy. Access policy is not installed by this DNS-only example.

## Run the example after reviewing it

The commands below are instructions for your lab, not evidence that this draft has run live.

```bash
# Set account/zone identifiers and tokens through your approved environment.
# The helper requires a mode700 credential directory outside this checkout.
install -d -m 700 "$HOME/.local/share/homelab-tunnel"
python3 scripts/create_tunnel.py --name homelab-website \
  --hostname lab.example.com \
  --credential-dir "$HOME/.local/share/homelab-tunnel" --create
# Read the printed UUID; it is an identifier, not the credential.
export TF_VAR_tunnel_id='REPLACE_WITH_PRINTED_UUID'
export TF_VAR_hostname='lab.example.com'
terraform -chdir=terraform init
terraform -chdir=terraform validate
terraform -chdir=terraform plan -out=website.tfplan
# Review the one-record plan and confirm it does not replace unrelated DNS.
terraform -chdir=terraform apply website.tfplan
rm -f terraform/website.tfplan
docker compose up -d
curl --fail http://127.0.0.1:8080/
cloudflared tunnel --config "$HOME/.local/share/homelab-tunnel/config.yml" ingress validate
cloudflared tunnel --config "$HOME/.local/share/homelab-tunnel/config.yml" run
```

Use a second terminal for `PUBLIC_HOSTNAME=lab.example.com bash scripts/verify.sh`. Test from an external client too. A response on localhost verifies the origin, while HTTPS verifies the public route. Use `cloudflared tunnel ... ingress rule https://lab.example.com` and connector logs to diagnose matching, DNS and origin failures independently. Never post credential files or full secret-bearing logs.

For persistent Linux service operation, first copy the generated config and UUID JSON to `/etc/cloudflared-homelab` using `sudo install -d -m700` and `sudo install -m600`; update `credentials-file` to the destination with a local CLI script. Then use `sudo cloudflared --config /etc/cloudflared-homelab/config.yml service install` and verify `systemctl status cloudflared`, connector logs and the external route. Review any existing unit before installation; do not overwrite unrelated services. Account-level API credentials are unnecessary for a running locally managed connector; retain only its tunnel credential.

The credentials JSON contains the tunnel secret: mode600, protected backups, never Git. A remotely managed alternative uses a connector token with the same sensitivity; never pass it inline in scripts, cloud-init, Docker command history or tfvars. Use an approved service credential facility and verify the process does not expose it.

## Verification and cleanup

Check origin binding with `ss -ltn`, public HTTPS with `curl`, connector health/logs, DMZ-to-LAN denial from the actual guest, and the same checks for IPv6. Confirm the management plane is unavailable from the DMZ. Browser success alone does not prove segmentation. Preserve evidence of what you checked and what remains untested.

`docker compose down` stops the sample application. `terraform -chdir=terraform plan -destroy` lets you review removing this single DNS record, followed by an explicitly reviewed destroy. Stop the connector/service before deleting the named tunnel through the Cloudflare API `DELETE /accounts/{account_id}/cfd_tunnel/{tunnel_id}` using your authorized token. Terraform destroy does **not** delete the independently created tunnel. Reconcile remote inventory, then securely retire local credentials and backups under your retention policy. Do not delete your broader zone or unrelated DNS.

## Official sources

- [Cloudflare Tunnel architecture](https://developers.cloudflare.com/tunnel/)
- [Create tunnel API: local configuration and tunnel secret](https://developers.cloudflare.com/api/resources/zero_trust/subresources/tunnels/subresources/cloudflared/methods/create/)
- [Locally managed configuration](https://developers.cloudflare.com/tunnel/features/locally-managed-tunnels/create-local-tunnel/)
- [Tunnel outbound connectivity](https://developers.cloudflare.com/tunnel/configuration/)
- [Cloudflare Terraform DNS record](https://registry.terraform.io/providers/cloudflare/cloudflare/latest/docs/resources/dns_record)
- [API token creation](https://developers.cloudflare.com/api/resources/user/subresources/tokens/methods/create/)
