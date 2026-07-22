# Security & IAM

PaperPlanes is built to the hackathon's production-readiness bar: least-privilege
IAM, secrets kept out of the repo, and an audited data path. This document is the
reference for locking the AWS side down before submission.

## Principle

The application needs exactly two AWS capabilities at runtime:

1. **Bedrock `InvokeModel`** on the specific models it uses — Amazon Nova Pro
   (chat), Nova Lite (fast extraction; still referenced by some paths), and
   Titan Text Embeddings V2 (embeddings). Nothing else in Bedrock.
2. **S3 read/write** on the single PDF bucket, `paperplanes-pdfs-380906049984`.

No console access, no IAM, no other services. The dev IAM user `mcp-cli-admin`
currently carries `AdministratorAccess` — that must be replaced with the policy
below (or split into a scoped deploy user + the EC2 instance profile).

## Least-privilege policy (`PaperPlanesRuntime`)

Account `380906049984`, region `us-east-1`. The Nova models are invoked through
cross-region inference profiles (the `us.` prefix), so the policy grants
`InvokeModel` on both the inference-profile ARNs and the underlying
foundation-model ARNs in the regions those profiles route to (us-east-1,
us-east-2, us-west-2). Titan is a direct model and needs only the plain
foundation-model ARN.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "BedrockInvokeNovaAndTitan",
      "Effect": "Allow",
      "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
      "Resource": [
        "arn:aws:bedrock:us-east-1:380906049984:inference-profile/us.amazon.nova-pro-v1:0",
        "arn:aws:bedrock:us-east-1:380906049984:inference-profile/us.amazon.nova-lite-v1:0",
        "arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-pro-v1:0",
        "arn:aws:bedrock:us-east-2::foundation-model/amazon.nova-pro-v1:0",
        "arn:aws:bedrock:us-west-2::foundation-model/amazon.nova-pro-v1:0",
        "arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-lite-v1:0",
        "arn:aws:bedrock:us-east-2::foundation-model/amazon.nova-lite-v1:0",
        "arn:aws:bedrock:us-west-2::foundation-model/amazon.nova-lite-v1:0",
        "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0"
      ]
    },
    {
      "Sid": "S3PdfBucketOnly",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::paperplanes-pdfs-380906049984/*"
    },
    {
      "Sid": "S3ListThatOneBucket",
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::paperplanes-pdfs-380906049984"
    }
  ]
}
```

## Applying it

**Tighten the dev user (`mcp-cli-admin`):**
1. IAM → Policies → Create policy → JSON → paste the above → name it
   `PaperPlanesRuntime`.
2. IAM → Users → `mcp-cli-admin` → detach `AdministratorAccess`, attach
   `PaperPlanesRuntime`.
3. Re-run the eval suite / a chat turn to confirm Bedrock + S3 still work; if a
   call is denied, the deny in CloudTrail names the exact missing action/ARN.

**EC2 instance profile (for the live demo):** create a role
`PaperPlanesInstanceRole` with the same `PaperPlanesRuntime` policy and attach it
to the EC2 instance. The app's `has_aws_credentials` already resolves instance
profiles via the botocore credential chain, so no keys are deployed to the box.

## Secrets

- Real secrets (DB DSN with password, MCP API key, any AWS keys for local dev)
  live only in the repo-root `.env` and `~/.aws`, both git-ignored. `.env.example`
  documents the keys with empty values.
- On EC2, prefer the instance profile (above) over any AWS keys; keep the DB DSN
  and MCP key in SSM Parameter Store (SecureString) or the instance's `.env`,
  never in git.
- The CockroachDB managed MCP server is reached with a **service-account** key
  scoped to `mcp:read`/`mcp:write` on the one cluster — not an org-admin
  credential — and every query it runs is audited server-side by CockroachDB
  Cloud.

## MCP introspection tool — scope note

The chat agent's `memory_introspect` tool executes LLM-composed SQL against the
cluster through the Managed MCP Server. This is constrained two ways: the
service-account key carries only `mcp:read`, and the server's `select_query`
tool rejects anything that isn't a `SELECT`. So no writes, DDL, or destructive
statements are reachable through it regardless of what the model is asked to do.

One thing to carry into any multi-tenant future: this path does not go through
the app's per-user `WHERE user_id = …` filtering. Today the app is single-tenant
(one demo user), so there is nothing to cross. Before going multi-tenant, point
the MCP credential at a per-tenant database/role or validate the tool's SQL
against an allow-list, so a prompt-injected query can't read across tenants.

## API authentication

Every `/api` **data** route (chat, papers, memory, contradictions, reflections) is
gated by a bearer token when `APP_API_TOKEN` is set — see
`app/api/deps.py:require_api_token`. Health/readiness routes stay open so probes
and load balancers don't need the token. The check is constant-time and, when the
token is unset, a no-op (so local dev, CI, and the eval suite run open).

**A deployment MUST set `APP_API_TOKEN`** to a strong random value
(`openssl rand -hex 32`). The React SPA is a static bundle with nowhere to keep a
secret, so it does *not* hold the token: the frontend's nginx attaches
`Authorization: Bearer <token>` server-side when proxying `/api` to the backend
(`frontend/nginx.conf.template`). The token never reaches the browser and rotates
with a restart rather than a rebuild.

**Be explicit about what that does and does not buy.** It closes direct
unauthenticated access to the backend — the container publishes no ports, so the
proxy is the only path in — but it does *not* authenticate end users. Anyone who
can reach the public demo can drive the API through that proxy, by design: the
hosted demo is meant to be clicked through without handing out a credential. The
mitigations that actually apply there are nginx rate limits (5 r/s reads, 10 r/min
writes per IP, `limit_req_status 429`) to bound Bedrock spend and abuse.

A deployment carrying real user data needs genuine per-user authentication
(OIDC/session) in front of this, not a shared token.

Known limitation: `user_id` is still taken from the request rather than derived
from the authenticated identity, so this is single-tenant access control (the one
token holder is the one user). A real multi-tenant deployment must derive `user_id`
from the token/session and drop the client-supplied field — otherwise a token
holder can address another user's `user_id` (IDOR).

## Network (EC2)

Security group: 22 restricted to the developer IP only; 80/443 open for the
public demo. Caddy terminates TLS (automatic HTTPS). The CockroachDB connection
uses `sslmode=verify-full`.
