# 🤖 Watcher AI Session Log & Architecture Context

This document tracks AI-assisted session changes, architectural decisions, and version history so that any developer or AI assistant on a new machine can immediately resume work efficiently.

---

## 📌 Version History & Session Log

### [v1.3.0] - 2026-08-31
- **Context & Problem:** Watcher was moved out of `workspace/auriga_project/watcher` into `workspace/watcher`. Moving it caused relative path lookup failures because `os.path.dirname(watcher_dir)` pointed to `workspace/` instead of `auriga_project/`.
- **Changes Made:**
  1. **Dynamic Root Resolution (`src/config.py`):** Created `get_default_root_dir()` with prioritized fallback hierarchy:
     - Explicit argument -> Env vars (`WATCHER_PROJECT_DIR`, `WATCHER_TARGET_DIR`, `WATCHER_ROOT_DIR`) -> `settings.json` (`project_dir`) -> Auto-detect `auriga_project` folder -> Subdirs with engine signatures -> Parent dir fallback.
  2. **Configurable Project Path UI (`src/ui/index.html` & `src/server.py`):** Added a project path configuration field in the Settings Modal. POST to `/api/settings` automatically re-initializes engine scanners and test runners live without restarting the server.
  3. **Version Increment:** Updated version to `1.3.0` across `VERSION` file, `src/config.py`, `/api/settings`, and Web UI header.
- **Key Decisions:**
  - Kept settings persistence in `settings.json` local to watcher.
  - Used `WatcherHTTPHandler.refresh_config()` class method to achieve hot-reload of target directory.

### [v1.2.0] - 2026-08-28
- **Changes:** Spec resolution fixes, RSpec process group cancellation via SIGKILL, and interactive progress streaming UI.

---

## 🛠️ Architecture Quick Reference

- **`watcher.py`**: Main CLI entrypoint (`server`, `analyze`, `engines`).
- **`src/config.py`**: Centralized configuration, `VERSION`, and `get_default_root_dir()`.
- **`src/engine_scanner.py`**: Scans target project for Rails Engines (`app/`), Frontends (`package.json`), etc.
- **`src/git_diff_extractor.py`**: Extracts unified git diffs (`working`, `staged`, `branch`, `last_commit`).
- **`src/entity_parser.py`**: Parses changed Ruby classes/modules, methods, associations, schema columns.
- **`src/impact_tracer.py`**: Fast `ripgrep` tracer across modules matching Gemfile dependency graph.
- **`src/risk_evaluator.py`**: Evaluates risk rating (HIGH/MEDIUM/LOW) per file and engine.
- **`src/test_runner.py`**: Parallel RSpec test runner with process group cancellation and SSE progress stream.
- **`src/server.py`**: Built-in HTTP server (`http://localhost:3019`).
- **`src/ui/index.html`**: Single-page dashboard UI (Dark, Light, Neon, Mechanicus themes).

---

## 🚀 How to Run

```bash
# Start Web Server
python3 watcher.py server --port 3019

# CLI Engine Discovery
python3 watcher.py engines

# CLI Impact Analysis
python3 watcher.py analyze --engine stock --format text
```

## ⚙️ Environment Variables (Optional Override)
- `WATCHER_PROJECT_DIR`: Absolute path to target project containing engine folders.
