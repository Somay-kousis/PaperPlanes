"""Shared pytest fixtures."""

import os

# Ensure a predictable, harmless DATABASE_URL for tests that import
# app.core.config even if the developer's shell has something else set.
os.environ.setdefault("DATABASE_URL", "postgresql://root@localhost:26257/defaultdb?sslmode=disable")
os.environ.setdefault("ENV", "test")
