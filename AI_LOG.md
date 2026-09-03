# 🤖 Watcher AI Session Log & Architecture Context

This document tracks AI-assisted session changes, architectural decisions, and version history so that any developer or AI assistant on a new machine can immediately resume work efficiently.

---

## 📌 Version History & Session Log

### [v1.4.4] - 2026-09-03
- **Context & Problem:**
  Developers needed a way to execute the entire Bitbucket CI pipeline locally (including all RSpec test suites and RuboCop code quality / linting checks) before committing or submitting code for pull request review.
- **Changes Made:**
  1. **Pipeline Runner Module (`src/pipeline_runner.py`):** Parses `bitbucket-pipelines.yml` dynamically for any engine, extracts test & lint steps, filters out slow CI setup commands (`gem install`, `bundle install`, `rails db:test:prepare`), and executes `bundle exec rspec` and `bundle exec rubocop` locally.
  2. **Server Endpoints (`src/server.py`):** Added `/api/pipeline/inspect`, `/api/run-pipeline-stream` (SSE), and `/api/cancel-pipeline`.
  3. **UI Integration (`test_runner.html`, `scanner.js`, `renderers.js`):** Added button `🚀 Executar Pipeline (RSpec + RuboCop)`, streaming progress indicator, and formatted tab output highlighting RuboCop offenses (`Convention`, `Warning`, `Error`) alongside RSpec test results.

### [v1.4.3] - 2026-09-02
- **Context & Problem:**
  `src/ui/index.html` grew into an unmaintainable monolithic file containing 1,800+ lines of mixed HTML markup and inline JavaScript functions, making code maintenance and future feature development difficult and error-prone.
- **Changes Made:**
  1. **HTML Component Templates (`src/ui/components/`):** Separated monolithic HTML into documented, reusable template partials:
     - `header.html`: Top navigation bar with branding, module selector, diff target, and primary action controls.
     - `overview_grid.html`: 2x2 KPI summary cards and cross-module dependency network graph container.
     - `impact_list.html`: Impact report table container, severity filters, search bar, and quick hide actions.
     - `test_runner.html`: RSpec parallel execution dashboard, scope selector, impacted module checkboxes, and live log tabs.
     - `modals/markdown_modal.html`: Markdown impact report viewer and clipboard exporter.
     - `modals/ai_export_modal.html`: Structured AI context & prompt exporter for code impacts and RSpec errors.
     - `modals/settings_modal.html`: 860px 2-column settings modal for themes, project directory, notifications, DB filters, and blacklist manager.
  2. **Modular JavaScript Engine (`src/ui/js/`):** Extracted 1,344 lines of inline JS into 5 focused ES6/vanilla scripts:
     - `app.js`: Application lifecycle initialization and global state store.
     - `api.js`: Low-level backend HTTP requests (`/api/engines`, `/api/analyze`, `/api/settings`, `/api/update/*`).
     - `scanner.js`: Scanner widget animations, SVG sonar progress ring, SSE live log streamer, test timers, and execution controls.
     - `renderers.js`: DOM rendering functions for KPI stats, impact tables, risk tags, dependency graph nodes, and test tabs.
     - `modals.js`: Modal window controls, theme switcher, settings form sync, blacklist manager, and AI prompt generator.
  3. **Server Component Stitching Engine (`src/server.py`):** Implemented regex-based component stitching in `_serve_ui()` (`{{COMPONENTS:...}}`) and added a static handler for `/js/` with `Content-Type: application/javascript`.
  4. **Compact Skeleton (`src/ui/index.html`):** Reduced `index.html` from 1,800+ lines to 48 lines of readable skeleton markup.
  5. **Execução de Testes em Paralelo Total (Monorepo All Engines):** Adicionado suporte no escopo das specs (`all_engines`) e novo botão `🔥 Rodar em TODAS as Engines` para disparar a execução RSpec multithread em todas as engines simultaneamente.

### [v1.4.2] - 2026-09-02
- **Context & Problem:**
  1. The Cyberpunk Neon theme lacked vivid neon contrast and punchy glowing borders.
  2. The Phosphor Green theme caused eye strain and headaches due to a flickering CRT scanlines grid, fuzzy text-shadow blurs, and harsh `#00ff66` text.
  3. The phosphor theme name ("Adeptus Mechanicus") presented trademark compliance risks and required rebranding.
  4. The theme required a dedicated gear logo icon that incorporated the signature Watcher Octopus Eye in the center, completely free of text/typography graphics.
- **Changes Made:**
  1. **Hyper-Vivid Cyberpunk Neon Theme (`src/ui/css/themes/neon.css`):** Upgraded Cyberpunk Neon with electric cyan `#00f0ff`, hot magenta `#ff007f`, neon green `#00ff88`, 2px thick glowing borders (`box-shadow` neon glow), gradient dual-glow buttons, glowing text-shadows, and neon chip hover transitions.
  2. **Ergonomic Cogitator Terminal Theme (`src/ui/css/themes/phosphor.css`):** Redesigned the theme based on Ergonomics and HCI principles. Disabled the CRT scanline grid overlay (eliminating flicker/serrilhado), replaced harsh green text with ergonomic soft sage `#d1fae5` and high-contrast white `#ffffff`, and removed fuzzy text-shadow blurs for sharp typography legibility.
  3. **Custom Pure Watcher Eye Gear Emblem (`assets/logo_cogitator.png`):** Generated a custom mechanical gear wheel logo with the signature Watcher Octopus Eye in the center, free of any text or letters (`logo_cogitator_pure_eye`), configured to display exclusively when `body.theme-phosphor` is active.
  4. **Trademark Compliance & Rebranding:** Renamed theme to "Cogitator Terminal (Modo Tático)" across `index.html`, `phosphor.css`, `VERSION`, and `AI_LOG.md`.

### [v1.4.1] - 2026-09-02
- **Context & Problem:**
  1. Developer needed a dynamic "Impact Blacklist" system to hide specific noise files (e.g. `spec/dummy/db/schema.rb`, dummy folders `spec/dummy/`, or migrations) from impact reports while keeping core evaluation active.
  2. Database migration files (`db/migrate/`, `schema.rb`, `structure.sql`) generated unnecessary impact clutter across multi-engine analyses.
  3. Stopping the Watcher server via `Ctrl+C` was killing the entire terminal window due to `exec` wrapper in `watcher.sh`.
  4. The Settings modal UI was too small (`max-width: 450px`), cramped, and required excessive scrolling.
- **Changes Made:**
  1. **Impact Blacklist Engine (`src/config.py` & `src/impact_tracer.py`):** Implemented `is_path_blacklisted()` supporting exact file paths, directory prefixes, and glob wildcards (`fnmatch`). Integrated blacklist matching across Ripgrep scan (`-g`), Python fallback scanner, and `_handle_analyze` in `src/server.py`.
  2. **Quick Hide Actions in UI (`src/ui/index.html`):** Added an "Ações" column to the impact report table with `🚫 Arq` (hide exact file) and `📁 Pasta` (hide parent folder). Clicking any action updates `settings.json` and re-runs impact analysis immediately.
  3. **DB & Migrations Filter (`hide_db_migrations`):** Added `is_db_migration_file()` helper and UI toggle in Settings to filter database/schema files across diffs and cross-module impact tracing.
  4. **Graceful Terminal Shutdown (`watcher.sh`):** Removed `exec` from `watcher.sh` so `Ctrl+C` stops the Python process cleanly while preserving the active terminal session.
  5. **Spacious Settings Modal UI (`src/ui/index.html`):** Redesigned the Settings modal from 450px to `max-width: 860px`, restructuring options into a spacious 2-column grid. Column 1 holds General/Target Folder/Notifications, while Column 2 groups Filters (Banco de Dados & Migrations positioned right above Blacklist de Impactos) and System Status.

### [v1.3.5] - 2026-08-31
- **Context & Problem:** `src/ui/index.html` contained over 1,060 lines of inline CSS rules and theme overrides mixed into the HTML body.
- **Changes Made:**
  1. **Modular CSS Architecture (`src/ui/css/`):** Created `base.css` (variables and global resets), `layout.css` (header, grid, main, modal layouts), and `components.css` (buttons, cards, tables, scanner animations).
  2. **Dedicated Theme Files (`src/ui/css/themes/`):** Separated theme definitions into individual files (`dark.css`, `neon.css`, `phosphor.css`, `light.css`).
  3. **Master Stylesheet (`src/ui/css/main.css`):** Consolidated all sub-stylesheets and themes via `@import`.
  4. **Server Static CSS Support (`src/server.py`):** Added `/css/` static file handler with proper MIME type headers (`text/css`).
  5. **File Size Reduction:** Reduced `index.html` from 2,590 lines (~100KB) to 1,525 lines (~65KB).

### [v1.3.4] - 2026-08-31
- **Context & Problem:** Developer requested changing the primary Git branch naming convention from `main` to `master`.
- **Changes Made:** Renamed local branch `main` to `master`, pushed `master` to remote `origin`, and updated tracking upstream to `origin/master`.

### [v1.3.3] - 2026-08-31
- **Context & Problem:** Developer reported requiring server restart and page reload for subsequent runs. Python's default `http.server.HTTPServer` is single-threaded; during long-running `/api/run-tests-stream` SSE streaming, the HTTP server loop was completely blocked and could not process incoming `/api/cancel-tests` or new test requests.
- **Changes Made:**
  1. **Multithreaded HTTP Server (`src/server.py`):** Converted `HTTPServer` to `ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer)` with `daemon_threads = True`. Every HTTP request now runs in an independent thread, allowing concurrent API calls, instant cancellations, and UI requests without blocking socket queues.
  2. **Pre-flight Execution Cleanup (`reset_state_for_new_run` in `src/test_runner.py`):** Added cleanup before launching parallel test runs to kill any lingering processes/file descriptors and clear cancellation flags.
  3. **Client Disconnect Detection:** Handled `BrokenPipeError` / `ConnectionResetError` in `send_sse` to automatically kill backend test processes if the client closes the SSE stream or aborts the connection.

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
