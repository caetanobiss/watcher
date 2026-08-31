# 🤖 Watcher AI Session Log & Architecture Context

This document tracks AI-assisted session changes, architectural decisions, and version history so that any developer or AI assistant on a new machine can immediately resume work efficiently.

---

## 📌 Version History & Session Log

### [v1.3.2] - 2026-08-31
- **Context & Problem:** Running tests a second time without reloading the page caused execution to get stuck at `0 / 0 specs (0%)` and `Iniciando execução dos testes RSpec...`.
- **Changes Made:**
  1. **Reset Cancellation Flag (`run_parallel_tests_stream`):** Ensured `self.is_cancelled = False` is explicitly reset at the master level before starting parallel thread workers.
  2. **Disabled Spring & Decoupled Stdin (`src/test_runner.py`):** Added `env["DISABLE_SPRING"] = "1"` and `stdin=subprocess.DEVNULL` to `subprocess.Popen`. This prevents Spring daemon locks and terminal stdin blocking on subsequent test executions.
  3. **File Descriptor Leak Fix:** Added `self.active_fds.discard(master_fd)` in the `finally:` block so closed PTY file descriptors are properly removed from the set.
  4. **Robust Line-by-Line SSE Parser (`src/ui/index.html`):** Updated the frontend EventSource/reader to split chunks line-by-line (`chunk.split('\n')`), preventing JSON parse errors when multiple SSE payloads are received in a single chunk.

### [v1.3.1] - 2026-08-31
- **Context & Problem:** (1) Test cancellation was delayed by up to 20 seconds because `os.read(master_fd, 1024)` in `test_runner.py` was a blocking system call. (2) Scope filtering (e.g. `services`) failed or skipped if `spec/services` didn't exist directly at the top level of `spec/`. (3) RSpec startup/initialization errors were not visibly alerting developers in the UI.
- **Changes Made:**
  1. **Instant Cancellation (Non-blocking PTY I/O):** Replaced blocking `os.read` with `select.select([master_fd], [], [], 0.05)` (50ms non-blocking polling loop). When the user clicks Cancel, Python checks `self.is_cancelled` in <50ms and sends `SIGKILL` to all OS process groups immediately. Frontend client connection is aborted in 0ms.
  2. **Multi-Location Scope Path Resolution (`_resolve_scope_args`):** Test runner now checks `spec/<scope>`, `spec/app/<scope>`, `spec/unit/<scope>`, `spec/<engine>/<scope>` and searches recursively for `*_spec.rb` matching the requested scope.
  3. **High-Visibility Error & Skip Banners:** Added explicit red/yellow Alert Banners in the UI (`index.html`) when RSpec fails to start, encounters gems/DB errors, or when specs are skipped, making test execution problems immediately obvious to the developer.

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
