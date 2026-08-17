"""Seed the database with demo data (a user, a session, a few papers/notes).

Week 1+ responsibility: once the memory-write and ingestion paths exist,
populate a demo user with a handful of papers, memory notes, and a
conversation, for demoing/testing the full retrieval + reflection loop.
"""

import asyncio


async def seed() -> None:
    """Insert demo data. Not yet implemented."""
    raise NotImplementedError


if __name__ == "__main__":
    asyncio.run(seed())
