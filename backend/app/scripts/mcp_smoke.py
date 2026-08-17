"""Smoke-test the CockroachDB Managed MCP Server connection.

Run once ``MCP_ENDPOINT`` + ``MCP_API_KEY`` are set in the environment/.env:

    .venv/bin/python -m app.scripts.mcp_smoke

It initializes an MCP session, lists the exposed tools, and runs a trivial
read query, printing what came back. Purely diagnostic; makes no writes.
"""

import asyncio
import logging

from app.memory import mcp_client

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    endpoint, api_key, cluster_id = mcp_client.get_mcp_settings()
    if not (endpoint and api_key):
        print("MCP not configured: set MCP_ENDPOINT and MCP_API_KEY in .env")
        return
    print(f"Connecting to MCP server: {endpoint} (cluster {cluster_id or 'unset'})")
    async with mcp_client.MCPClient(endpoint, api_key, cluster_id=cluster_id) as mcp:
        tools = await mcp.list_tools()
        print(f"Exposed tools ({len(tools)}):")
        for t in tools:
            print(f"  - {t.get('name')}: {t.get('description', '')[:70]}")
    print("\nRunning a trivial read query via run_read_query()...")
    try:
        out = await mcp_client.run_read_query(
            "SELECT count(*) AS memory_notes FROM memory_notes"
        )
        print("Result:\n", out)
    except mcp_client.MCPError as exc:
        print("Query failed:", exc)


if __name__ == "__main__":
    asyncio.run(main())
