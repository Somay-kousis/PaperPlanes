# Deploying PaperPlanes (single EC2 + CockroachDB Cloud)

The live demo runs the **same containers as local dev** on one small EC2 box, with
CockroachDB Cloud as the memory layer and Caddy terminating HTTPS. Rationale: solo
project, the judges score the memory engine — not the IaC — so one deployment
artifact, one box, a live URL that's up early. The ECS Fargate path is documented in
[`PRODUCTION.md`](PRODUCTION.md).

```
Internet ──443──▶ Caddy (auto-TLS) ──▶ frontend (nginx: SPA + /api proxy) ──▶ backend (FastAPI)
                                                                                    │
                                                              instance profile (IMDSv2) ─▶ Bedrock + S3
                                                                                    │
                                                                          CockroachDB Cloud (verify-full)
```

Artifacts live in [`deploy/`](../deploy):

| File | What it is |
|---|---|
| `docker-compose.prod.yml` | prod stack: backend + frontend + Caddy (no local cockroach, no mounted AWS keys) |
| `Caddyfile` | Caddy edge, automatic Let's Encrypt for `$DOMAIN` |
| `.env.prod.example` | the prod env template — copy to repo-root `.env.prod` and fill in |
| `user-data.sh` | EC2 first-boot machine prep (Docker + repo clone) |
| `iam-instance-policy.json` | least-privilege policy for the EC2 instance role |
| `iam-mcp-cli-admin-policy.json` | least-privilege replacement for AdministratorAccess on the `mcp-cli-admin` user |

---

## One-time cloud setup

### 1. CockroachDB Cloud — create the prod database
In the Cloud SQL console (or `cockroach sql`):
```sql
CREATE DATABASE paperplanes_prod;
```
Grab the `verify-full` connection string and point its path at `paperplanes_prod` — that's your `DATABASE_URL`.

### 2. AWS — instance role (least privilege)
1. IAM → **Roles** → create a role for **EC2**.
2. Attach an inline policy = the contents of [`deploy/iam-instance-policy.json`](../deploy/iam-instance-policy.json).
3. This becomes the instance profile the box launches with. **No AWS keys touch the server** — boto3 reads credentials from IMDSv2.

### 3. AWS — EC2 instance
- Ubuntu 22.04/24.04, **t3.small**, the instance profile from step 2.
- **User data** = paste [`deploy/user-data.sh`](../deploy/user-data.sh) (edit the git URL if your fork differs).
- **IMDSv2 hop limit = 2** (containers reach IMDS through one extra network hop; the default of 1 blocks boto3 inside Docker):
  ```
  Advanced details → Metadata response hop limit → 2
  ```
  (or after launch: `aws ec2 modify-instance-metadata-options --instance-id <id> --http-put-response-hop-limit 2 --http-tokens required`)
- **Security group**: inbound `443` and `80` from anywhere (80 is required for the ACME HTTP challenge), `22` from your IP only.
- Allocate an **Elastic IP** and associate it (so the DNS name stays stable across reboots).

### 4. DNS
Point a hostname at the Elastic IP. Free option: a **DuckDNS** subdomain (`paperplanes.duckdns.org`) → set it to the Elastic IP. This hostname is your `DOMAIN`.

---

## Bring the app up (over SSH)

```bash
ssh ubuntu@<elastic-ip>
cd /opt/paperplanes

# 1. Secrets (never in git)
cp deploy/.env.prod.example .env.prod
nano .env.prod
#   DOMAIN=paperplanes.duckdns.org
#   DATABASE_URL=...paperplanes_prod?sslmode=verify-full
#   MCP_API_KEY=...   MCP_CLUSTER_ID=...
#   APP_API_TOKEN=$(openssl rand -hex 32)   ← generate a strong one

# 1b. Download the CockroachDB Cloud cluster CA cert (verify-full needs it — the
#     cluster signs with its own CA, not a public one). Do this BEFORE any compose
#     command, since the backend mounts deploy/cockroach-ca.crt.
curl --create-dirs -o deploy/cockroach-ca.crt \
  "https://cockroachlabs.cloud/clusters/<CLUSTER_ID>/cert"
#     (<CLUSTER_ID> is your MCP_CLUSTER_ID / the id in the Cloud console URL)

# 2. Apply the prod schema to CockroachDB Cloud (idempotent; safe to re-run)
docker compose --env-file .env.prod --project-directory . \
  -f deploy/docker-compose.prod.yml run --rm backend python -m app.scripts.init_db

# 3. Start everything (Caddy fetches the TLS cert on first boot)
docker compose --env-file .env.prod --project-directory . \
  -f deploy/docker-compose.prod.yml up -d --build
```

> `--project-directory .` is required: it makes the compose file's relative paths
> (`./backend`, `.env.prod`, `./deploy/Caddyfile`) resolve against the repo root
> rather than the `deploy/` folder the file lives in. Run all compose commands from
> the repo root.

---

## Verify

```bash
# health, from the box, hitting the backend over the compose network
# (only Caddy publishes ports, and it answers only for $DOMAIN — so don't curl localhost)
docker compose --env-file .env.prod --project-directory . -f deploy/docker-compose.prod.yml \
  exec caddy wget -qO- http://backend:8000/api/healthz && echo OK

# HTTPS + cert (from your laptop, after DNS propagates — usually < 1 min)
curl -sfI https://paperplanes.duckdns.org/ | head -1

# auth is enforced in prod: a data route without the token should 401
curl -s -o /dev/null -w '%{http_code}\n' https://paperplanes.duckdns.org/api/memory/notes
#   → 401  (add  -H "Authorization: Bearer $APP_API_TOKEN"  → 200)
```

Then open `https://paperplanes.duckdns.org/` — the landing page, and upload an arXiv id
to watch ingestion → memory write end-to-end.

**Logs / ops:**
```bash
docker compose --env-file .env.prod --project-directory . -f deploy/docker-compose.prod.yml logs -f backend
docker compose --env-file .env.prod --project-directory . -f deploy/docker-compose.prod.yml ps
```

To ship a new build: `git pull` then re-run the `up -d --build` command.

---

## Tighten the `mcp-cli-admin` IAM user (do this before submitting)

That user currently has `AdministratorAccess` — over-privileged for a user whose keys
only power local Bedrock/S3 dev calls. Replace it:

1. IAM → Users → `mcp-cli-admin` → **detach** `AdministratorAccess`.
2. Attach an inline policy = [`deploy/iam-mcp-cli-admin-policy.json`](../deploy/iam-mcp-cli-admin-policy.json).
3. Local dev keeps working (same Bedrock + S3 grants). Re-attach admin only for a one-off
   infra change, then remove it again.

See [`SECURITY.md`](SECURITY.md) for the full security posture.
