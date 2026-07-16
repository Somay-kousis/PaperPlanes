"""Application configuration.

Single source of truth for runtime configuration, loaded from environment
variables and an optional ``.env`` file via ``pydantic-settings``. Every
other module should import ``get_settings()`` rather than reading
``os.environ`` directly, so tests can override configuration cleanly.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# The .env lives at the repo root, but backend scripts are typically run from
# ``backend/``. Resolve both locations by absolute path so a local invocation
# (e.g. ``python -m app.scripts.mcp_smoke`` from ``backend/``) still loads it.
# In containers the environment is injected directly, so a missing file is fine.
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_ENV_FILES = (str(_BACKEND_DIR / ".env"), str(_BACKEND_DIR.parent / ".env"))


class Settings(BaseSettings):
    """Runtime configuration for the PaperPlanes backend.

    Defaults are tuned for a local CockroachDB instance started with
    ``cockroach start-single-node --insecure`` (or `cockroach demo`), and for
    running the app entirely without AWS credentials (echo-only chat).
    """

    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENV: str = "dev"

    # --- Auth ----------------------------------------------------------
    # When set, every /api data route requires ``Authorization: Bearer <token>``
    # matching this value. Left unset (the default) the API is open -- convenient
    # for local dev, CI, and the eval suite, but a deployment MUST set this. See
    # app.api.deps.require_api_token.
    APP_API_TOKEN: str | None = None

    # --- Database -----------------------------------------------------
    DATABASE_URL: str = "postgresql://root@localhost:26257/defaultdb?sslmode=disable"

    # --- AWS / Bedrock --------------------------------------------------
    AWS_REGION: str = "us-east-1"
    # Amazon Nova (first-party) models — billed via standard AWS consumption,
    # avoiding the Bedrock Marketplace payment-instrument requirement that blocks
    # Anthropic models on this account. Nova supports Converse tool use.
    BEDROCK_CHAT_MODEL_ID: str = "us.amazon.nova-pro-v1:0"
    BEDROCK_FAST_MODEL_ID: str = "us.amazon.nova-lite-v1:0"
    BEDROCK_EMBED_MODEL_ID: str = "amazon.titan-embed-text-v2:0"
    EMBED_DIM: int = 1024

    # --- Storage ---------------------------------------------------------
    S3_BUCKET: str = "paperplanes-pdfs-380906049984"

    # --- MCP (tool/context server for later weeks) ------------------------
    MCP_ENDPOINT: str | None = None
    MCP_API_KEY: str | None = None
    # The managed server multiplexes every cluster in the org behind one
    # endpoint; the ``mcp-cluster-id`` header selects which one to target.
    MCP_CLUSTER_ID: str | None = None
    # Database the agent's memory tables live in on the MCP-targeted cluster;
    # used to qualify table names in the `memory_introspect` tool guidance.
    # (paperplanes_prod in deployment, paperplanes_dev when pointing at the
    # shared dev cluster.)
    MCP_MEMORY_DATABASE: str = "paperplanes_prod"

    @property
    def has_aws_credentials(self) -> bool:
        """Best-effort guess as to whether AWS/Bedrock calls are viable.

        This does NOT validate credentials; it only checks that the app has
        some resolvable credential source. Real invocation errors are caught
        by callers and treated as a fallback to the echo agent.

        Env vars are the cheap fast path. But credentials also arrive via the
        shared ``~/.aws`` files (mounted into the dev container) and via EC2
        instance profiles / IMDS (production) -- neither sets an env var -- so
        we defer to botocore's full credential chain as the authoritative
        check. The result is cached module-side to avoid re-resolving per call.
        """
        import os

        if (
            os.environ.get("AWS_ACCESS_KEY_ID")
            or os.environ.get("AWS_PROFILE")
            or os.environ.get("AWS_CONTAINER_CREDENTIALS_RELATIVE_URI")
            or os.environ.get("AWS_ROLE_ARN")
        ):
            return True
        return _aws_credentials_resolvable()


@lru_cache
def _aws_credentials_resolvable() -> bool:
    """Whether botocore can resolve credentials from any source (file/IMDS/etc.).

    Cached because credential-chain resolution (which may probe the instance
    metadata service) is comparatively expensive and does not change over a
    process's lifetime. Any failure is treated as "no credentials".
    """
    try:
        import boto3

        return boto3.Session().get_credentials() is not None
    except Exception:
        return False


@lru_cache
def get_settings() -> Settings:
    """Return a cached, process-wide Settings instance."""
    return Settings()
