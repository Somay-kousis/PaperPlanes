# Production & Provisioning

The live demo runs the same `docker-compose.yml` as local dev on a single EC2
instance, pointed at CockroachDB Cloud. This document records the productionization
path (what we'd do past the hackathon) and the CockroachDB provisioning tooling.

## Cluster provisioning with `ccloud` (bonus CockroachDB tool)

The cluster and its databases can be provisioned non-interactively with the
CockroachDB Cloud CLI (`ccloud`), rather than clicking through the console:

```bash
# Authenticate (opens a browser once; stores a token).
ccloud auth login

# Create the Basic (free-tier, serverless) cluster on AWS us-east-1.
ccloud cluster create serverless paperplanes --cloud aws --region us-east-1

# Grab the SQL connection string for the app's DATABASE_URL.
ccloud cluster sql paperplanes --format json

# Create a SQL user and the app databases.
ccloud cluster user create paperplanes somay
```

Then apply the schema with the repo's own migration runner:

```bash
DATABASE_URL="postgresql://somay:<pw>@<host>:26257/paperplanes_prod?sslmode=verify-full" \
  python -m app.scripts.init_db
```

`ccloud` is a provisioning-time tool (not a runtime dependency), which is why it's
listed as a *bonus* CockroachDB tool alongside the two we integrate at runtime —
Distributed Vector Indexing and the Managed MCP Server.

## Deploy topology (current)

- **Single EC2 t3.small** running `docker compose up` (backend + frontend), plus
  Caddy for automatic HTTPS (see `scripts/` and the Caddyfile added at deploy time).
- **CockroachDB Cloud** (`wooden-swan`, Basic tier, AWS us-east-1) holds all
  memory tiers + LangGraph checkpoints. `DATABASE_URL` points the app at
  `paperplanes_prod`.
- **IAM instance profile** scoped to `bedrock:InvokeModel*` on the Nova/Titan
  model ARNs + the one S3 bucket (see `docs/SECURITY.md`) — no static keys on the box.
- **S3** private bucket for PDFs, presigned GETs.

## Scaling path (documented, not built)

For higher availability past a single instance:

- **ECS Fargate + ALB**: run the backend as a Fargate service behind an
  Application Load Balancer (TLS at the ALB), frontend as static assets on
  S3 + CloudFront. The app is already stateless — all state lives in CockroachDB
  Cloud — so horizontal scaling is just raising the desired task count.
- **Multi-instance caveat**: the memory writer serialises consolidation with a
  *process-local* per-user lock (`app/memory/writer.py`). Running more than one
  backend instance would require replacing that with a database advisory lock (or
  a unique constraint on the note being consolidated) so per-user consolidation
  stays serialised across instances.
- **Reflection scheduler**: the APScheduler-based reflection worker runs in-process;
  multi-instance would move it to a single leader (or a scheduled ECS task) so the
  cycle doesn't run N times in parallel.
