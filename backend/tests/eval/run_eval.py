"""Runnable entrypoint for the memory-eval suite.

Run from ``backend/`` (with the venv active, or via ``.venv/bin/python``):

    python -m tests.eval.run_eval

Runs each probe in ``tests.eval.probes.ALL_PROBES`` sequentially against a
*real, running* PaperPlanes stack over HTTP (default
``http://localhost:8000``; override with ``PAPERPLANES_BASE_URL``),
prints a scorecard, and exits non-zero if any probe fails.

This is not a pytest suite: it talks to whatever server is actually up
(docker compose), the same way a human clicking through the app would, so
a green scorecard is evidence the memory engine is really driving
behavior -- not evidence that mocks were wired up correctly. Requires the
stack to be reachable (checked via ``GET /api/readyz`` before running any
probe); if it isn't, this prints a clear message and exits 2 rather than
hanging on the first probe's requests.
"""

from __future__ import annotations

import asyncio
import sys

import httpx

from tests.eval.probes import ALL_PROBES
from tests.eval.support import ProbeResult, get_base_url, make_client

_COL_NAME = 42
_COL_STATUS = 6
_COL_TIME = 8


def _print_scorecard(results: list[ProbeResult]) -> None:
    header = f"{'PROBE':<{_COL_NAME}} {'STATUS':<{_COL_STATUS}} {'TIME':>{_COL_TIME}}  WHY"
    print(header)
    print("-" * len(header))
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        time_s = f"{result.duration_s}s"
        row = f"{result.name:<{_COL_NAME}} {status:<{_COL_STATUS}} {time_s:>{_COL_TIME}}"
        print(f"{row}  {result.detail}")
    print("-" * len(header))
    passed = sum(1 for r in results if r.passed)
    print(f"{passed}/{len(results)} probes passed")


async def _check_stack_reachable(base_url: str) -> str | None:
    """Return an error message if the stack isn't reachable, else ``None``."""
    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
            response = await client.get("/api/readyz")
    except httpx.HTTPError as exc:
        return f"could not reach {base_url}: {exc}"
    if response.status_code != 200:
        return f"{base_url}/api/readyz returned {response.status_code}: {response.text}"
    return None


async def _run_all() -> list[ProbeResult]:
    async with make_client() as client:
        results = []
        for probe in ALL_PROBES:
            result = await probe(client)
            results.append(result)
        return results


def main() -> int:
    base_url = get_base_url()
    print(f"Running memory-eval suite against {base_url}\n")

    unreachable = asyncio.run(_check_stack_reachable(base_url))
    if unreachable is not None:
        print(f"ERROR: stack not ready -- {unreachable}", file=sys.stderr)
        print("Start it with `docker compose up` at the repo root and retry.", file=sys.stderr)
        return 2

    results = asyncio.run(_run_all())
    print()
    _print_scorecard(results)

    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
