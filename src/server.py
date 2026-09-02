import os
import json
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from typing import Dict, Any

from src.config import VERSION, LAST_UPDATE, is_db_migration_file, is_path_blacklisted
from src.engine_scanner import EngineScanner
from src.git_diff_extractor import GitDiffExtractor
from src.entity_parser import EntityParser
from src.impact_tracer import ImpactTracer
from src.risk_evaluator import RiskEvaluator
from src.test_runner import TestRunner

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "settings.json")

def load_settings() -> Dict[str, Any]:
    defaults = {
        "theme": "dark",
        "notifications_enabled": True,
        "toasts_enabled": True,
        "sound_enabled": True,
        "project_dir": "auriga_project",
        "hide_db_migrations": True,
        "impact_blacklist": []
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                defaults.update(json.load(f))
        except Exception:
            pass
    return defaults

def save_settings(data: Dict[str, Any]):
    current = load_settings()
    current.update(data)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)

class WatcherHTTPHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler providing REST API and serving the Web Dashboard UI."""

    scanner = EngineScanner()
    diff_extractor = GitDiffExtractor()
    tracer = ImpactTracer()
    evaluator = RiskEvaluator()
    test_runner = TestRunner()

    @classmethod
    def refresh_config(cls):
        """Re-initializes all system components using the latest target project path."""
        cls.scanner = EngineScanner()
        cls.diff_extractor = GitDiffExtractor()
        cls.tracer = ImpactTracer()
        cls.evaluator = RiskEvaluator()
        cls.test_runner = TestRunner()

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query_params = urllib.parse.parse_qs(parsed_url.query)

        if path == "/" or path == "/index.html":
            self._serve_ui()
        elif path == "/api/engines":
            self._handle_get_engines()
        elif path == "/api/diff":
            engine = query_params.get("engine", ["stock"])[0]
            target = query_params.get("target", ["working"])[0]
            self._handle_get_diff(engine, target)
        elif path == "/api/settings":
            self._send_json({
                "status": "success",
                "settings": load_settings(),
                "active_root_dir": self.scanner.root_dir,
                "version": VERSION,
                "last_update": LAST_UPDATE
            })
        elif path == "/api/update/check":
            from src.updater import WatcherUpdater
            updater = WatcherUpdater()
            res = updater.check_for_updates()
            self._send_json(res)
        elif path in ["/assets/logo.png", "/logo.png", "/favicon.ico"]:
            logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "logo.png")
            if os.path.exists(logo_path):
                with open(logo_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            else:
                self._send_json({"error": "Logo file not found"}, status=404)
        elif path in ["/assets/bg_tentacles.png", "/bg_tentacles.png"]:
            bg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "bg_tentacles.png")
            if os.path.exists(bg_path):
                with open(bg_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            else:
                self._send_json({"error": "Background file not found"}, status=404)
        elif path in ["/assets/bg_mechanicus.png", "/bg_mechanicus.png"]:
            bg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "bg_mechanicus.png")
            if os.path.exists(bg_path):
                with open(bg_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            else:
                self._send_json({"error": "Mechanicus background file not found"}, status=404)
        elif path in ["/assets/logo_cogitator.png", "/logo_cogitator.png"]:
            logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "logo_cogitator.png")
            artifact_source = "/home/caetano/.gemini/antigravity/brain/06512383-a23d-4d7b-a1b2-241ea4c095c9/logo_cogitator_pure_eye_1788376989190.png"
            if os.path.exists(artifact_source):
                import shutil
                shutil.copy(artifact_source, logo_path)
            if os.path.exists(logo_path):
                with open(logo_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            else:
                self._send_json({"error": "Cogitator logo file not found"}, status=404)
        elif path.startswith("/css/"):
            rel_path = path[5:]
            css_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "css", rel_path)
            css_file_path = os.path.abspath(css_file_path)
            css_base_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "css"))
            if css_file_path.startswith(css_base_dir) and os.path.exists(css_file_path) and os.path.isfile(css_file_path):
                with open(css_file_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/css; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            else:
                self._send_json({"error": "CSS file not found"}, status=404)
        elif path.startswith("/js/"):
            rel_path = path[4:]
            js_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "js", rel_path)
            js_file_path = os.path.abspath(js_file_path)
            js_base_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "js"))
            if js_file_path.startswith(js_base_dir) and os.path.exists(js_file_path) and os.path.isfile(js_file_path):
                with open(js_file_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/javascript; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            else:
                self._send_json({"error": "JS file not found"}, status=404)
        else:
            self._send_json({"error": "Endpoint not found"}, status=404)

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path == "/api/analyze":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                body = json.loads(post_data.decode('utf-8'))
            except Exception:
                body = {}
            self._handle_analyze(body)
        elif path in ["/api/run-tests", "/api/run-tests-stream"]:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                body = json.loads(post_data.decode('utf-8'))
            except Exception:
                body = {}
            if path == "/api/run-tests-stream":
                self._handle_run_tests_stream(body)
            else:
                self._handle_run_tests(body)
        elif path == "/api/cancel-tests":
            self.test_runner.cancel_all_tests()
            self._send_json({"status": "success", "message": "Tests cancelled"})
        elif path == "/api/settings":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                body = json.loads(post_data.decode('utf-8'))
            except Exception:
                body = {}
            new_settings = save_settings(body)
            if "project_dir" in body:
                WatcherHTTPHandler.refresh_config()
            self._send_json({
                "status": "success",
                "settings": new_settings,
                "active_root_dir": self.scanner.root_dir
            })
        elif path == "/api/update/perform":
            from src.updater import WatcherUpdater
            updater = WatcherUpdater()
            res = updater.perform_update()
            if res.get("status") == "success":
                WatcherHTTPHandler.refresh_config()
            self._send_json(res)
        else:
            self._send_json({"error": "Endpoint not found"}, status=404)

    def _serve_ui(self):
        ui_path = os.path.join(os.path.dirname(__file__), "ui", "index.html")
        components_dir = os.path.join(os.path.dirname(__file__), "ui", "components")
        if os.path.exists(ui_path):
            with open(ui_path, "r", encoding="utf-8") as f:
                html_content = f.read()

            import re
            pattern = re.compile(r'\{\{COMPONENTS:([a-zA-Z0-9_/.-]+)\}\}')
            def replace_component(match):
                comp_name = match.group(1)
                comp_path = os.path.abspath(os.path.join(components_dir, comp_name))
                if comp_path.startswith(components_dir) and os.path.exists(comp_path):
                    with open(comp_path, "r", encoding="utf-8") as cf:
                        return cf.read()
                return f"<!-- Component {comp_name} not found -->"

            html_content = pattern.sub(replace_component, html_content)
            content = html_content.encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self._send_json({"error": "UI file index.html not found"}, status=404)

    def _handle_get_engines(self):
        try:
            engines = self.scanner.discover_engines()
            self._send_json({"status": "success", "count": len(engines), "engines": engines})
        except Exception as e:
            self._send_json({"status": "error", "message": str(e)}, status=500)

    def _handle_get_diff(self, engine: str, target: str):
        try:
            diff_data = self.diff_extractor.get_engine_diff(engine, target)
            self._send_json({"status": "success", "diff": diff_data})
        except Exception as e:
            self._send_json({"status": "error", "message": str(e)}, status=500)

    def _handle_analyze(self, body: Dict[str, Any]):
        engine = body.get("engine", "stock")
        target = body.get("target", "working")
        settings = load_settings()
        hide_db_migrations = settings.get("hide_db_migrations", True)
        impact_blacklist = settings.get("impact_blacklist", [])

        try:
            # 1. Diff
            diff_data = self.diff_extractor.get_engine_diff(engine, target)
            diff_files = diff_data.get("files", [])

            if hide_db_migrations or impact_blacklist:
                diff_files = [
                    f for f in diff_files
                    if not (hide_db_migrations and is_db_migration_file(f.get("file_path", ""))) and
                    not (impact_blacklist and is_path_blacklisted(f.get("file_path", ""), impact_blacklist))
                ]
                diff_data["files"] = diff_files
                diff_data["total_changed_files"] = len(diff_files)

            # 2. Entity Parsing
            parser = EntityParser(engine)
            parsed_entities = parser.parse_changed_files(diff_files)
            entities_list = parsed_entities.get("entities", [])

            # Fallback: If no diff lines found (clean working tree), parse all models/services of selected engine for manual inspection!
            if not entities_list:
                engine_path = os.path.join(self.scanner.root_dir, engine)
                sample_files = []
                for sub in ['app/models', 'app/services', 'app/builders']:
                    p = os.path.join(engine_path, sub)
                    if os.path.exists(p):
                        for root, _, files in os.walk(p):
                            for f in files:
                                if f.endswith('.rb'):
                                    rel = os.path.relpath(os.path.join(root, f), engine_path)
                                    if hide_db_migrations and is_db_migration_file(rel):
                                        continue
                                    if impact_blacklist and is_path_blacklisted(rel, impact_blacklist):
                                        continue
                                    sample_files.append({"file_path": rel, "full_path": os.path.join(root, f), "status": "modified"})
                parsed_entities = parser.parse_changed_files(sample_files[:10])
                entities_list = parsed_entities.get("entities", [])

            # 3. Cross-Module Tracer
            raw_impact_report = self.tracer.trace_impacts(engine, entities_list, hide_db_migrations=hide_db_migrations, impact_blacklist=impact_blacklist)

            # 4. Risk Evaluator
            final_report = self.evaluator.evaluate_impacts(raw_impact_report, entities_list)

            self._send_json({
                "status": "success",
                "engine": engine,
                "target": target,
                "diff_summary": {
                    "total_files_changed": diff_data.get("total_changed_files", 0),
                    "files": [f["file_path"] for f in diff_files]
                },
                "entities_count": len(entities_list),
                "entities": entities_list,
                "report": final_report
            })

        except Exception as e:
            self._send_json({"status": "error", "message": str(e)}, status=500)

    def _handle_run_tests(self, body: Dict[str, Any]):
        engines_req = body.get("engines", [])
        if not engines_req:
            self._send_json({"status": "error", "message": "Nenhum módulo selecionado para execução de testes."}, status=400)
            return

        try:
            results = self.test_runner.run_parallel_tests(engines_req, max_workers=4)
            self._send_json({
                "status": "success",
                "results": results
            })
        except Exception as e:
            self._send_json({"status": "error", "message": str(e)}, status=500)

    def _handle_run_tests_stream(self, body: Dict[str, Any]):
        engines_req = body.get("engines", [])
        if not engines_req:
            self._send_json({"status": "error", "message": "Nenhum módulo selecionado para execução de testes."}, status=400)
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        def send_sse(data_dict):
            if self.test_runner.is_cancelled:
                return
            try:
                payload = f"data: {json.dumps(data_dict)}\n\n".encode('utf-8')
                self.wfile.write(payload)
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                # Connection dropped by client -> cancel tests immediately
                self.test_runner.cancel_all_tests()
            except Exception:
                pass

        try:
            results = self.test_runner.run_parallel_tests_stream(engines_req, progress_callback=send_sse, max_workers=4)
            send_sse({"type": "complete", "results": results})
        except Exception as e:
            send_sse({"type": "error", "message": str(e)})

    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data, indent=2).encode('utf-8')
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Clean logging output
        return

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

def run_server(port: int = 3019):
    current_port = port
    max_attempts = 10
    httpd = None
    
    for attempt in range(max_attempts):
        try:
            server_address = ('', current_port)
            httpd = ThreadedHTTPServer(server_address, WatcherHTTPHandler)
            break
        except OSError as e:
            if e.errno == 98:
                print(f"⚠️ Porta {current_port} já está em uso. Tentando porta {current_port + 1}...")
                current_port += 1
            else:
                raise e

    if not httpd:
        print(f"❌ Não foi possível vincular uma porta após {max_attempts} tentativas.")
        return

    print(f"🚀 Watcher Server running on http://localhost:{current_port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Watcher server.")
        httpd.server_close()

if __name__ == '__main__':
    run_server(3019)

