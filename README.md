# A public homelab website through Cloudflare Tunnel

Start with [GitOps, the bootstrap order, and why the repos are separate](docs/START-HERE.md).

A public learning example with executable code and CI. Real homelab deployment requires your own inputs and credentials; this is not a production baseline.

A visitor reaches Cloudflare over HTTPS. A connector inside your lab opens outbound connections to Cloudflare and proxies the request to a web container bound to `127.0.0.1:8080`. Your router needs no inbound port forward. Your origin needs no publicly reachable IP address; it does need internet connectivity. This works behind NAT/CGNAT when outbound connectivity is available. It does not require disabling IPv6: enforce the same security boundary for both address families.

```text
visitor -> Cloudflare HTTPS edge -> outbound-established tunnel
                                   cloudflared on DMZ guest
                                   -> 127.0.0.1:8080 website
DMZ guest -- firewall DENY --> private LAN / hypervisor management
```


## Capacity and reachability before deployment

This example provisions **no VM**. Its website container and existing cloudflared connector run on your existing dedicated DMZ Linux host. Check free RAM, disk, service conflicts and sustained connector egress there before deploy. Terraform changes only the intended DNS record; start with local Compose to learn the origin before exposing its intended public hostname.

**No GPU is required** for this DNS, Kubernetes, Rancher, telemetry or tunnel lesson. AI inference is a separate optional workload: model size, precision, context and concurrency determine RAM/VRAM requirements; these examples do not reserve or promise that capacity. Account separately for the chosen runner, GitLab if self-hosted, host OS and existing services. Check `free -h`, `df -h`, and Proxmox `pvesm status`/`pvesh get /nodes/YOUR_NODE/status` on the actual intended machines. On an existing cluster compare allocatable and requested resources with `kubectl describe nodes` and storage/PVC inventory before adding LGTM.

| Initiator | Destination and port | Purpose / when needed |
| --- | --- | --- |
| Workstation | Selected GitHub or GitLab HTTPS 443 (or configured trusted local TLS port) | Clone, CLI API and pipeline control; not a substitute for runner network reach |
| Dedicated selected runner | Proxmox TLS API TCP 8006 | VM Terraform path only; trust its CA, keep management outside DMZ |
| Dedicated selected runner | Intended guest TCP 22 | Reviewed SSH/bootstrap paths; pin unique host keys |
| Runner / guests | Approved package and container registries TCP 443 | Downloads; add only repository-specific approved HTTP 80 sources if required |
| Workload runner | Intended Kubernetes TLS API TCP 6443, or configured KAS TLS route | Manifest/Helm paths only; scoped credentials and verified TLS |
| Trusted LAN DNS clients | Intended DNS server UDP and TCP 53 | DNS paths only; deliberate listener and narrow ACL/firewall, not demo high ports |
| DMZ tunnel host | Cloudflare UDP/TCP 7844 and approved HTTPS 443 | Cloudflare connector/install path only; no inbound router forward |

A hosted GitHub validation runner has **no assumed route to your private LAN**. Configure only the selected private execution runner with necessary routes, DNS and firewall permissions. Keep DMZ-to-LAN/admin denial intact; tunnel connectivity alone does not segment your network. Test the selected route from the actual runner with TLS-verifying `curl`, pinned-key SSH and the README runtime commands before deploying, rather than opening management broadly.


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

The commands below are instructions for your lab, not evidence that this example has been deployed to a real homelab.

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

## Choose one CI provider before configuring deployment

GitHub and GitLab are **alternative complete paths**. [CI-PATHS.md](CI-PATHS.md) provides the runner setup, GitLab CLI inputs and job controls alongside the GitHub commands below. Choose one owner for each lab. A source-control server stores code and schedules jobs; the selected **runner machine** executes Terraform, SSH, Ansible or Helm and needs the documented network access. Cloning this repository does not install a runner or create a route to Proxmox.

| Choice | Source and job scheduler | Execution machine | Kubernetes access |
| --- | --- | --- | --- |
| GitHub | Your private GitHub repository and Actions | Your dedicated self-hosted Linux runner | Scoped kubeconfig where needed; GitLab/KAS not required |
| GitLab | Your private GitLab project and GitLab CI | Your dedicated protected GitLab Linux runner | Scoped kubeconfig; GitLab agent/KAS is an optional separately configured route |

The public upstream runs unprivileged hosted validation only. A local GitLab is useful if you want to host your own source and scheduler, but is **not** a prerequisite for the GitHub path. KAS does not provision VMs and is not a general-purpose Terraform runner.

## Actual CI deployment: use your private deployment copy

The public source is `https://github.com/RayEvelyn/cloudflare-homelab-tunnel.git`. Public examples run **hosted validation only**. The deployment job is intentionally ineligible in the public repository. Clone the code, review it, and create your **own private** repository/project for access to a dedicated homelab runner:

```bash
git clone https://github.com/RayEvelyn/cloudflare-homelab-tunnel.git
cd cloudflare-homelab-tunnel
# Replace YOUR_ACCOUNT with your own account; preserve the upstream origin.
gh repo create YOUR_ACCOUNT/cloudflare-homelab-tunnel --private --source . --remote deployment --push
```

This includes a functional deployment path, not a claim that CI has deployed your lab already. The GitHub workflow requires an explicit `workflow_dispatch`, your private repository, its default branch, `DEPLOY_ENABLED=true`, runner labels `self-hosted,linux,homelab`, and environment `homelab`. Never attach a LAN-capable self-hosted runner to the public source repo. Configure protected branch/environment controls and restrict runner use to this private copy. Environment approval features depend on your GitHub plan; verify enforced behavior rather than assuming an environment name creates approval.

### A persistent runner and explicit state ownership

Use a dedicated persistent Linux runner with Terraform, Python3, OpenSSH tools, GNU `flock`, and network reachability to the intended lab host. State is not a CI cache or disposable workspace. Provision a private directory owned by the runner service account:

```bash
# On the dedicated runner; use its actual service account instead of homelab-runner.
sudo install -d -m700 -o homelab-runner -g homelab-runner /var/lib/homelab-terraform
```

`TF_STATE_ROOT=/var/lib/homelab-terraform` and the private repository ID resolve to `/var/lib/homelab-terraform/<repository-id>/terraform.tfstate`. The local backend is explicit. A per-state `flock`, Terraform's local locking and CI per-repository concurrency serialize execution. This is **one persistent runner**, not a distributed locking design. Do not schedule the same state on multiple hosts. Back up this root independently; the helper preserves a timestamped private pre-apply state copy, which is not a substitute for off-host recovery. Never upload state or plans as public artifacts.

The helper defaults to `plan`. It generates protected temporary inputs, validates, creates a saved plan, and rejects delete/replacement actions. `plan` exits without changing infrastructure. In the DNS VM repositories, `provision` applies that exact plan and returns without SSH/bootstrap. This Cloudflare repository rejects that action because it does not create a VM. `deploy` applies the exact plan, then uses an isolated SSH configuration to install/update the reviewed sample. No automatic destroy is included. Planned replacements require separate deliberate recovery review.

### Configure inputs using CLI

Define your target with nonsecret JSON in repository variable `HOMELAB_TFVARS_JSON`; do not put tokens, passwords or private keys there. For the DNS VM examples, use the fields from `terraform/terraform.tfvars.example`, omitting `ssh_public_key_path`: the helper writes the provided public key to a temporary file and supplies the path. For Cloudflare, use `zone_id`, `hostname`, and the **existing** `tunnel_id`. An API token is provider environment input, never a Terraform credential variable.

```bash
# Run against your private repository. Files below belong outside the public checkout.
gh api --method PUT repos/YOUR_ACCOUNT/cloudflare-homelab-tunnel/environments/homelab
gh variable set TF_STATE_ROOT --repo YOUR_ACCOUNT/cloudflare-homelab-tunnel --body /var/lib/homelab-terraform
gh variable set HOMELAB_TFVARS_JSON --repo YOUR_ACCOUNT/cloudflare-homelab-tunnel < /secure/local/inputs.json
# The public SSH key is not a secret; match the protected private key used for deployment.
gh variable set SSH_PUBLIC_KEY --repo YOUR_ACCOUNT/cloudflare-homelab-tunnel < /secure/local/id_ed25519.pub
gh secret set SSH_PRIVATE_KEY --repo YOUR_ACCOUNT/cloudflare-homelab-tunnel < /secure/local/id_ed25519
gh secret set SSH_KNOWN_HOSTS --repo YOUR_ACCOUNT/cloudflare-homelab-tunnel < /secure/local/known_hosts
# Enable only after reviewing runner placement, inputs and permission boundaries.
gh variable set DEPLOY_ENABLED --repo YOUR_ACCOUNT/cloudflare-homelab-tunnel --body true
gh workflow run homelab.yml --repo YOUR_ACCOUNT/cloudflare-homelab-tunnel -f action=plan
```

Secret commands read stdin; credential values are not command-line arguments. Disable shell tracing and avoid logged terminals when handling secrets. Do not echo credentials for troubleshooting. Keep an independently verified host-key file rather than trusting an unauthenticated `ssh-keyscan` result.

SSH uses mode600 temporary credentials and an isolated `HOMELAB_SSH_CONFIG`; every connection passes `-F`, strict host-key checking and batch mode. The target defaults to ubuntu on port22 and needs intended passwordless sudo for the reviewed guest bootstrap. Pin its key through your trusted administration path before deployment. This example uses an existing DMZ host and has no new-VM provision phase.

### Existing bare-metal or VM target

The same workload upload is available through `scripts/deploy-existing-host.sh` for a dedicated Linux host without Terraform provisioning. Supply the isolated `HOMELAB_SSH_CONFIG`, runtime directory and deployment inputs exactly as the CI helper does. It requires the same preverified keys, sudo authority and network policy. Review `scripts/deploy-local.py` before running it directly on the intended host; never on a Proxmox hypervisor. Package installation and container restart are actual changes.

### GitLab option

The included `.gitlab-ci.yml` runs hosted/shared validation and exposes a **manual** homelab job only for a private project, protected default branch and `DEPLOY_ENABLED=true`. Register a dedicated Linux runner tagged `homelab`, assign protected variables/secrets with the same names, and protect the `homelab` environment as your GitLab plan supports. It invokes the same helpers. Default `HOMELAB_ACTION=plan`; deliberately select `provision` or `deploy` only after reviewing the previous stage. Do not attach this runner to untrusted forks or public pipelines.

Repository/runner access controls and token permissions are part of your lab setup; example YAML cannot enforce a router policy or your hosting account's approval settings by itself.

### Cloudflare-specific deployment boundary

This repo provisions a DNS record, **not a Proxmox VM**. Use `plan` or `deploy`; `provision` is refused. Set `HOMELAB_SSH_HOST` to your existing DMZ Linux host IP, plus `CLOUDFLARE_API_TOKEN` as a scoped DNS-edit secret. No tunnel-account creation credential belongs in CI.

Before deployment, create the named tunnel once with the documented helper on the DMZ host and retain `/etc/cloudflared-homelab/config.yml` plus its protected external credential JSON there. Install cloudflared from its official distribution. CI reuses that existing configuration; it does not create a tunnel every run or put a tunnel token in Terraform state. The configuration must route the intended hostname to localhost8080 and end with the404 catch-all. Protect and back up the credential on the DMZ host.

The deploy helper checks these prerequisites, deploys only the sample website, validates existing tunnel ingress and installs/starts a dedicated `homelab-cloudflared.service`. Existing dedicated unit configuration is backed up before editing; unrelated SSH/service configuration is untouched. Inspect existing connector services first to avoid unintended duplicate connectors. Runtime origin health is checked; verify the public HTTPS hostname independently and confirm DMZ-to-LAN denial. Cloudflare Access remains a separate deliberate policy for private applications.

```bash
gh variable set HOMELAB_SSH_HOST --repo YOUR_ACCOUNT/cloudflare-homelab-tunnel --body YOUR_DMZ_HOST_IP
gh secret set CLOUDFLARE_API_TOKEN --repo YOUR_ACCOUNT/cloudflare-homelab-tunnel < /secure/local/cloudflare-dns-token
gh workflow run homelab.yml --repo YOUR_ACCOUNT/cloudflare-homelab-tunnel -f action=plan
gh workflow run homelab.yml --repo YOUR_ACCOUNT/cloudflare-homelab-tunnel -f action=deploy
```

Cloudflare does not require Proxmox variables, DNS_BIND_IP or DNS_ALLOWED_CIDRS; its origin remains loopback8080.

For a complete existing-host command path, load `SSH_PRIVATE_KEY` and `SSH_KNOWN_HOSTS` from your protected local secret facility, set `HOMELAB_SSH_HOST` (and DNS binding/ACL variables for the DNS repos), then run:

```bash
bash scripts/deploy-bare-metal.sh
```

This creates its own temporary isolated SSH files and performs the reviewed guest deployment, with no Terraform apply or VM creation. The existing host must be dedicated to this lab and already have the intended network segmentation and unique host keys. It installs packages and restarts only the named example workload; inspect the helper before using it on a host with existing services.
