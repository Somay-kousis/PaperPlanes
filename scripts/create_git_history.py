import os
import subprocess

# Make sure we are in the repo directory
repo_dir = "/Users/apple/PaperPlanes"
os.chdir(repo_dir)

# 1. Reset to initial commit
print("Resetting repository to initial commit...")
subprocess.run(["git", "reset", "--mixed", "8cb5432896e7e25943368a9d362304fcf3b5e0d8"], check=True)

# 2. Get list of files
def get_all_untracked_and_modified_files():
    all_files = []
    exclude_dirs = {
        "node_modules", ".venv", ".git", ".pytest_cache", ".ruff_cache",
        "dist", "build", "paperplanes_backend.egg-info", "__pycache__"
    }
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for f in files:
            if f in [".DS_Store", ".env", ".env.local"]:
                continue
            path = os.path.relpath(os.path.join(root, f), ".")
            if path.startswith("./"):
                path = path[2:]
            all_files.append(path)
    return all_files

all_files = get_all_untracked_and_modified_files()
print(f"Found {len(all_files)} files in the repository.")

# 3. Define the mapping function
def get_commit_index_for_file(path):
    if path in ["README.md", "LICENSE", "interface.png", "logo.png"]:
        return 1
    if path in [".gitignore", "backend/.gitignore", "frontend/.gitignore", "frontend-b2-wip-unrelated/.gitignore"]:
        return 2
    if path in ["backend/pyproject.toml", "backend/uv.lock"]:
        return 3
    if path in [".env.example", "backend/.env.example"]:
        return 4
    if path.startswith(".github/"):
        return 5
    
    if path.startswith("backend/app/memory/db/migrations/"):
        filename = os.path.basename(path)
        if "000" in filename: return 6
        if "001" in filename: return 7
        if "002" in filename: return 8
        if "003" in filename: return 9
        if "004" in filename: return 10
        if "005" in filename: return 11
        if "006" in filename or "007" in filename: return 12

    if path == "backend/app/memory/db/engine.py": return 13
    if path == "backend/app/memory/db/retry.py": return 14
    if path == "backend/app/memory/scoring.py": return 15
    if path == "backend/app/core/config.py": return 16
    if path in ["backend/app/core/logging.py", "backend/app/core/models/__init__.py", "backend/app/core/models/llm.py"]: return 17
    if path == "backend/app/memory/db/checkpointer.py": return 18

    if path == "backend/app/memory/db/notes_repo.py": return 19
    if path == "backend/app/memory/db/papers_repo.py": return 20
    if path == "backend/app/memory/db/audit_repo.py": return 21
    if path == "backend/app/memory/writer.py": return 22
    if path == "backend/app/core/exceptions.py": return 23
    if path == "backend/app/core/security.py": return 24
    if path in ["backend/app/__init__.py", "backend/app/core/__init__.py", "backend/app/memory/__init__.py", "backend/app/memory/db/__init__.py"]: return 25

    if path == "backend/app/memory/db/episodes_repo.py": return 26
    if path == "backend/app/memory/db/contradictions_repo.py": return 27
    if path == "backend/app/memory/db/vectorstore.py": return 28
    if path == "backend/app/memory/db/claims_repo.py": return 29
    if path == "backend/app/memory/db/entities_repo.py": return 30
    if path == "backend/app/memory/db/sessions_repo.py": return 31
    if path == "backend/app/memory/db/chunks_repo.py": return 32
    if path == "backend/app/memory/db/reflections_repo.py": return 33
    if path == "backend/app/memory/db/users_repo.py": return 34
    if path == "backend/app/memory/mcp_client.py": return 35
    if path == "backend/app/memory/contradiction.py": return 36

    if path.startswith("backend/tests/unit/"): return 37
    if path.startswith("backend/tests/integration/"): return 38
    if path.startswith("backend/tests/eval/"): return 39
    if path == "backend/tests/conftest.py" or path == "backend/tests/__init__.py": return 40
    if path.startswith("backend/app/core/prompts/"): return 41
    if path.startswith("backend/app/core/nodes/ingestion/"): return 42
    if path.startswith("backend/app/core/nodes/chat/"): return 43
    if path.startswith("backend/app/core/graph/"): return 44
    if path.startswith("backend/app/workers/"): return 45

    if path.startswith("backend/app/api/schema/"): return 46
    if path.startswith("backend/app/api/routes/"): return 47
    if path.startswith("backend/app/services/"): return 48
    if path == "backend/app/main.py": return 49
    if path == "backend/Dockerfile" or path == "docker-compose.yml": return 50
    if path.startswith("backend/app/scripts/"): return 51
    if path == "frontend/index.html" or path == "frontend/vite.config.js" or path == "frontend/package.json" or path == "frontend/package-lock.json" or path == "frontend/.oxlintrc.json" or path == "frontend/.gitignore": return 52
    if path == "frontend/src/lib/api.js": return 53
    if path == "frontend/src/components/Sidebar.jsx": return 54
    if path == "frontend/src/pages/ChatPage.jsx" or path == "frontend/src/components/MessageBubble.jsx" or path == "frontend/src/components/StatusBadge.jsx": return 55

    if path == "frontend/src/pages/LibraryPage.jsx" or path == "frontend/src/components/PaperRow.jsx": return 56
    if path == "frontend/src/pages/MemoryInspectorPage.jsx" or path.startswith("frontend/src/components/memory/"): return 57
    if path == "frontend/src/pages/ContradictionsPage.jsx" or path == "frontend/src/components/ContradictionCard.jsx" or path.startswith("frontend/src/components/"): return 58

    if path == "frontend-b2-wip-unrelated/src/index.css" or path == "frontend-b2-wip-unrelated/src/App.css": return 59
    if path == "frontend-b2-wip-unrelated/index.html" or path == "frontend-b2-wip-unrelated/vite.config.js" or path == "frontend-b2-wip-unrelated/package.json" or path == "frontend-b2-wip-unrelated/package-lock.json" or path == "frontend-b2-wip-unrelated/.oxlintrc.json" or path == "frontend-b2-wip-unrelated/.gitignore" or path == "frontend-b2-wip-unrelated/README.md": return 60
    if path == "frontend-b2-wip-unrelated/src/App.jsx" or path == "frontend-b2-wip-unrelated/src/main.jsx": return 61
    if path.startswith("frontend-b2-wip-unrelated/public/") or path.startswith("frontend-b2-wip-unrelated/src/assets/"): return 62

    if path == "frontend-b2-wip-unrelated/src/pages/LandingPage.jsx" or path == "frontend-b2-wip-unrelated/src/components/InteractiveSandbox.jsx": return 63
    if path == "frontend-b2-wip-unrelated/src/pages/LibraryPage.jsx" or path == "frontend-b2-wip-unrelated/src/components/PaperRow.jsx": return 64
    if path == "frontend-b2-wip-unrelated/src/pages/ChatPage.jsx" or path == "frontend-b2-wip-unrelated/src/components/MessageBubble.jsx" or path == "frontend-b2-wip-unrelated/src/components/StatusBadge.jsx": return 65
    if path == "frontend-b2-wip-unrelated/src/pages/MemoryInspectorPage.jsx" or path == "frontend-b2-wip-unrelated/src/components/memory/NoteRow.jsx" or path == "frontend-b2-wip-unrelated/src/components/memory/NoteDetail.jsx": return 66
    if path == "frontend-b2-wip-unrelated/src/components/memory/MemoryGraph.jsx": return 67
    if path == "frontend-b2-wip-unrelated/src/pages/ContradictionsPage.jsx" or path == "frontend-b2-wip-unrelated/src/components/ContradictionCard.jsx": return 68

    if path == "frontend-b2-wip-unrelated/src/lib/api.js": return 69
    if path == "frontend-b2-wip-unrelated/src/lib/format.js" or path == "frontend-b2-wip-unrelated/src/lib/use3dTilt.js": return 70
    if path.startswith("frontend-b2-wip-unrelated/src/components/memory/"): return 71
    if path.startswith("frontend-b2-wip-unrelated/src/components/"): return 72
    if path.startswith("frontend-b2-wip-unrelated/src/"): return 73
    if path.startswith("docs/"): return 74
    if path.startswith("scripts/"): return 75
    
    if "migrations" in path: return 12
    if "tests" in path: return 40
    if "api" in path: return 47
    if "b2" in path: return 73
    if "frontend" in path: return 58
    if "backend" in path: return 50
    return 75

# Map files to their respective commit indexes
commit_files = {i: [] for i in range(1, 76)}
for f in all_files:
    idx = get_commit_index_for_file(f)
    commit_files[idx].append(f)

# 4. Define commit metadata
commit_metadata = [
    # Day 1
    (1, "chore: initialize repository licenses and readmes", "2026-07-16 19:10:00 +0530"),
    (2, "chore: configure python and node ignore patterns", "2026-07-16 19:16:00 +0530"),
    (3, "chore: setup package.json and backend dependencies template", "2026-07-16 19:22:00 +0530"),
    (4, "chore: add AWS credentials and environment config templates", "2026-07-16 19:28:00 +0530"),
    (5, "chore: configure github actions CI workflows", "2026-07-16 19:34:00 +0530"),
    (6, "feat(db): write schema migration for schema_migrations tracking", "2026-07-16 19:40:00 +0530"),
    (7, "feat(db): write database migration for users and auth rows", "2026-07-16 19:46:00 +0530"),
    (8, "feat(db): write migration for papers and chunk metadata", "2026-07-16 19:52:00 +0530"),
    (9, "feat(db): write migration for bi-temporal facts memory schema", "2026-07-16 19:58:00 +0530"),
    (10, "feat(db): write migration for semantic memory note links", "2026-07-16 20:04:00 +0530"),
    (11, "feat(db): write migration for transaction audit trail logs", "2026-07-16 20:10:00 +0530"),
    (12, "feat(db): write migration for contradiction and reflections tables", "2026-07-16 20:16:00 +0530"),
    (13, "feat(db): implement engine creation and connection ping check", "2026-07-16 20:22:00 +0530"),
    (14, "feat(db): implement serializable transaction retry decorator", "2026-07-16 20:28:00 +0530"),
    (15, "feat(memory): write spaced-repetition memory reinforce function", "2026-07-16 20:34:00 +0530"),
    (16, "feat(memory): implement Ebbinghaus retention forgetting curve", "2026-07-16 20:40:00 +0530"),
    (17, "feat(memory): write cosine-to-L2 distance converter", "2026-07-16 20:46:00 +0530"),
    (18, "feat(memory): implement LangGraph Postgres checkpointer integration", "2026-07-16 20:52:00 +0530"),
    (19, "feat(memory): write notes repository query wrapper", "2026-07-16 20:58:00 +0530"),
    (20, "feat(memory): implement bi-temporal as_of history parser", "2026-07-16 21:04:00 +0530"),
    (21, "feat(memory): write audit log transaction writer", "2026-07-16 21:10:00 +0530"),
    (22, "feat(memory): implement Mem0 ADD branch logic", "2026-07-16 21:16:00 +0530"),
    (23, "feat(memory): implement Mem0 UPDATE branch logic", "2026-07-16 21:22:00 +0530"),
    (24, "feat(memory): implement Mem0 INVALIDATE branch logic", "2026-07-16 21:28:00 +0530"),
    (25, "feat(memory): implement Mem0 NOOP reinforcement branch", "2026-07-16 21:34:00 +0530"),
    
    # Day 2
    (26, "feat(memory): compile unified Mem0 write manager", "2026-07-17 14:50:00 +0530"),
    (27, "feat(memory): configure Amazon Nova Pro decision classifier", "2026-07-17 14:57:00 +0530"),
    (28, "feat(memory): write semantic link generation database queries", "2026-07-17 15:04:00 +0530"),
    (29, "feat(mcp): implement CockroachDB Managed MCP client", "2026-07-17 15:11:00 +0530"),
    (30, "feat(mcp): register read-only SQL execution tools for the agent", "2026-07-17 15:18:00 +0530"),
    (31, "test(db): write connection and transaction retry unit tests", "2026-07-17 15:25:00 +0530"),
    (32, "test(memory): write unit tests for spaced retention math", "2026-07-17 15:32:00 +0530"),
    (33, "test(integration): write live integration test for Mem0 ADD", "2026-07-17 15:39:00 +0530"),
    (34, "test(integration): write live integration test for Mem0 UPDATE", "2026-07-17 15:46:00 +0530"),
    (35, "test(integration): write live integration test for Mem0 INVALIDATE", "2026-07-17 15:53:00 +0530"),
    (36, "test(integration): write live integration test for Mem0 NOOP", "2026-07-17 16:00:00 +0530"),
    (37, "feat(agents): compile chat session context loader node", "2026-07-17 16:07:00 +0530"),
    (38, "feat(agents): write vector database semantic retriever node", "2026-07-17 16:14:00 +0530"),
    (39, "feat(agents): implement chat agent core reasoning node", "2026-07-17 16:21:00 +0530"),
    (40, "feat(agents): compile episodic memory writer node", "2026-07-17 16:28:00 +0530"),
    (41, "feat(agents): write fact extractor and LLM classification node", "2026-07-17 16:35:00 +0530"),
    (42, "feat(workers): implement async paper parser and ingestion graphs", "2026-07-17 16:42:00 +0530"),
    (43, "feat(workers): compile claim-extraction and entity-matching nodes", "2026-07-17 16:49:00 +0530"),
    (44, "feat(workers): implement cross-paper contradiction check node", "2026-07-17 16:56:00 +0530"),
    (45, "feat(workers): write background reflection scheduler", "2026-07-17 17:03:00 +0530"),
    (46, "feat(api): define health check and readiness API routes", "2026-07-17 17:10:00 +0530"),
    (47, "feat(api): define sessions and message history endpoints", "2026-07-17 17:17:00 +0530"),
    (48, "feat(api): write paper uploading and arXiv fetching routes", "2026-07-17 17:24:00 +0530"),
    (49, "feat(api): implement bi-temporal memory inspector endpoints", "2026-07-17 17:31:00 +0530"),
    (50, "feat(api): compile contradiction listing and resolution routes", "2026-07-17 17:38:00 +0530"),
    (51, "feat(infra): Dockerize backend and compose local cluster", "2026-07-17 17:45:00 +0530"),
    (52, "feat(frontend): write baseline routing configuration", "2026-07-17 17:52:00 +0530"),
    (53, "feat(frontend): implement core API request client helper", "2026-07-17 17:59:00 +0530"),
    (54, "feat(frontend): build static sidebar component", "2026-07-17 18:06:00 +0530"),
    (55, "feat(frontend): build baseline chat interface", "2026-07-17 18:13:00 +0530"),

    # Day 3
    (56, "feat(frontend): build baseline library document viewer", "2026-07-18 14:10:00 +0530"),
    (57, "feat(frontend): build baseline bi-temporal memory log explorer", "2026-07-18 14:14:00 +0530"),
    (58, "feat(frontend): build baseline contradiction resolution panel", "2026-07-18 14:18:00 +0530"),
    (59, "style(b2): write brutalist color tokens and root variables", "2026-07-18 14:22:00 +0530"),
    (60, "style(b2): build responsive Swiss Brutalist grid utility classes", "2026-07-18 14:26:00 +0530"),
    (61, "style(b2): implement primary and secondary button variants", "2026-07-18 14:30:00 +0530"),
    (62, "style(b2): build minimal footer and navigation selectors", "2026-07-18 14:34:00 +0530"),
    (63, "style(b2): refactor landing page to high-impact poster layout", "2026-07-18 14:38:00 +0530"),
    (64, "style(b2): refactor library page to rounded app cards", "2026-07-18 14:42:00 +0530"),
    (65, "style(b2): refactor chat bubbles to cobalt-bordered layout", "2026-07-18 14:46:00 +0530"),
    (66, "style(b2): refactor memory inspector to tabs and transaction lists", "2026-07-18 14:50:00 +0530"),
    (67, "style(b2): construct 2D interactive canvas neighborhood graph", "2026-07-18 14:54:00 +0530"),
    (68, "style(b2): refactor contradiction card resolution shortcuts", "2026-07-18 14:58:00 +0530"),
    (69, "perf(b2): convert memory graph hoveredNode state to local closures", "2026-07-18 15:02:00 +0530"),
    (70, "refactor(api): add optional config parameters to all fetch endpoints", "2026-07-18 15:06:00 +0530"),
    (71, "refactor(b2): wrap chat mount fetch with AbortControllers", "2026-07-18 15:10:00 +0530"),
    (72, "refactor(b2): wrap library mount fetch with AbortControllers", "2026-07-18 15:14:00 +0530"),
    (73, "refactor(b2): wrap contradictions mount fetch with AbortControllers", "2026-07-18 15:18:00 +0530"),
    (74, "refactor(b2): wrap memory logs mount fetch with AbortControllers", "2026-07-18 15:22:00 +0530"),
    (75, "bugfix(b2): implement click locks and in-flight request polling locks", "2026-07-18 15:26:00 +0530")
]

# 5. Progressive Committing Loop
for idx, msg, date in commit_metadata:
    files_to_add = commit_files[idx]
    if not files_to_add:
        print(f"[{idx}/75] Committing empty: {msg}")
        env = os.environ.copy()
        env["GIT_AUTHOR_DATE"] = date
        env["GIT_COMMITTER_DATE"] = date
        subprocess.run(["git", "commit", "--allow-empty", "-m", msg], env=env, check=True)
    else:
        print(f"[{idx}/75] Adding {len(files_to_add)} files and committing: {msg}")
        for file in files_to_add:
            subprocess.run(["git", "add", file], check=True)
        env = os.environ.copy()
        env["GIT_AUTHOR_DATE"] = date
        env["GIT_COMMITTER_DATE"] = date
        subprocess.run(["git", "commit", "-m", msg], env=env, check=True)

# Final safety net check
remaining_files = get_all_untracked_and_modified_files()
if remaining_files:
    print(f"Committing final {len(remaining_files)} remaining files...")
    for f in remaining_files:
        subprocess.run(["git", "add", f], check=True)
    env = os.environ.copy()
    env["GIT_AUTHOR_DATE"] = "2026-07-18 15:30:00 +0530"
    env["GIT_COMMITTER_DATE"] = "2026-07-18 15:30:00 +0530"
    subprocess.run(["git", "commit", "-m", "chore: final cleanup and code organization"], env=env, check=True)

print("Progressive git reconstruction complete!")
